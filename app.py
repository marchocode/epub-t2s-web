#!/usr/bin/env python3
"""
EPUB 繁转简 Web 服务 (Flask)。

启动 (开发):
    python app.py                     # 默认 http://127.0.0.1:8000
    python app.py --host 0.0.0.0 --port 9000

发布到公网请参考 DEPLOY.md，并通过环境变量配置站点信息:
    SITE_URL=https://epub.example.com
"""

import argparse
import os
import shutil
import tempfile
import time
import traceback
import uuid
from datetime import datetime, timezone

from flask import (Flask, Response, jsonify, render_template, request,
                   send_file)

import site_config as cfg
import stats
from convert_epub import convert_epub

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 允许的最大上传体积，默认 200 MB
MAX_UPLOAD = 200 * 1024 * 1024

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD

# 初始化统计数据库
stats.init_db()


@app.context_processor
def inject_site_config():
    """让模板能直接使用站点配置。"""
    return {
        "site_url": cfg.SITE_URL,
        "site_name": cfg.SITE_NAME,
        "site_description": cfg.SITE_DESCRIPTION,
        "site_keywords": cfg.SITE_KEYWORDS,
        "google_verification": cfg.GOOGLE_SITE_VERIFICATION,
        "bing_verification": cfg.BING_SITE_VERIFICATION,
        "baidu_verification": cfg.BAIDU_SITE_VERIFICATION,
    }


@app.after_request
def add_security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return resp


@app.before_request
def track_visit():
    """记录页面访问量（只统计 HTML 页面，不统计静态/接口）。"""
    if request.method == "GET" and request.path in ("/", "/stats"):
        try:
            stats.record_visit(
                ip=stats.get_client_ip(request),
                path=request.path,
                user_agent=request.headers.get("User-Agent"),
            )
        except Exception:
            app.logger.exception("记录访问失败")


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/robots.txt")
def robots():
    """告诉搜索引擎可以抓取哪些内容。"""
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /api/",
    ]
    if not cfg.INDEX_STATS_PAGE:
        lines.append("Disallow: /stats")
    lines += [
        "",
        "# 爬虫不限速（本服务很轻）",
        "User-agent: Baiduspider",
        "Allow: /",
        "",
        "Sitemap: %s/sitemap.xml" % cfg.SITE_URL,
        "",
    ]
    return Response("\n".join(lines), mimetype="text/plain")


@app.get("/sitemap.xml")
def sitemap():
    """站点地图，帮助搜索引擎发现页面。"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = [("%s/" % cfg.SITE_URL, "1.0", "daily")]
    if cfg.INDEX_STATS_PAGE:
        urls.append(("%s/stats" % cfg.SITE_URL, "0.3", "daily"))

    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, priority, freq in urls:
        parts.append(
            "  <url><loc>%s</loc><lastmod>%s</lastmod>"
            "<changefreq>%s</changefreq><priority>%s</priority></url>"
            % (loc, today, freq, priority)
        )
    parts.append("</urlset>")
    return Response("\n".join(parts), mimetype="application/xml")



@app.get("/stats")
def stats_page():
    return render_template("stats.html")


_FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    '<rect width="64" height="64" rx="14" fill="#4f8cff"/>'
    '<text x="32" y="44" font-size="34" text-anchor="middle" '
    'fill="#fff" font-family="sans-serif">简</text></svg>'
).encode("utf-8")


@app.get("/favicon.ico")
@app.get("/favicon.svg")
def favicon():
    return Response(_FAVICON, mimetype="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/stats")
def stats_api():
    try:
        days = max(1, min(int(request.args.get("days", 30)), 365))
    except ValueError:
        days = 30
    return jsonify(stats.get_stats(days))


@app.get("/health")
def health():
    return "ok", 200


@app.post("/convert")
def convert():
    ip = stats.get_client_ip(request)
    ua = request.headers.get("User-Agent")
    file = request.files.get("file")
    if file is None or not file.filename:
        return "未收到文件字段 'file'", 400

    filename = os.path.basename(file.filename)
    if not filename.lower().endswith(".epub"):
        stats.record_convert(ip, filename, 0, success=False, user_agent=ua)
        return "只支持 .epub 文件", 400

    tmpdir = tempfile.mkdtemp(prefix="epub_web_")
    in_path = os.path.join(tmpdir, "in_" + uuid.uuid4().hex + ".epub")
    out_path = os.path.join(tmpdir, "out.epub")
    started = time.monotonic()
    size = 0
    try:
        file.save(in_path)
        size = os.path.getsize(in_path)
        app.logger.info("转换 %s ...", filename)
        converted = convert_epub(in_path, out_path)
        elapsed = time.monotonic() - started
        app.logger.info("完成 %s (转换 %d 个文本文件)", filename, converted)

        stats.record_convert(ip, filename, size, success=True,
                             files=converted, duration=elapsed, user_agent=ua)

        base, _ = os.path.splitext(filename)
        out_name = base + "_简体.epub"

        response = send_file(
            out_path,
            mimetype="application/epub+zip",
            as_attachment=True,
            download_name=out_name,
        )
        # 让响应发送完成后再删除临时文件
        response.call_on_close(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        return response
    except Exception:
        elapsed = time.monotonic() - started
        try:
            stats.record_convert(ip, filename, size, success=False,
                                 duration=elapsed, user_agent=ua)
        except Exception:
            app.logger.exception("记录转换失败状态时出错")
        shutil.rmtree(tmpdir, ignore_errors=True)
        app.logger.error("转换失败:\n%s", traceback.format_exc())
        return "转换失败:\n" + traceback.format_exc(), 500


@app.errorhandler(413)
def too_large(_e):
    return "文件过大 (上限 %d MB)" % (MAX_UPLOAD // 1024 // 1024), 413


@app.errorhandler(404)
def not_found(_e):
    return render_template("index.html"), 404


def main():
    parser = argparse.ArgumentParser(description="EPUB 繁转简 Web 服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    print("EPUB 繁转简服务已启动: http://%s:%d" % (args.host, args.port))
    print("按 Ctrl+C 停止")
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
