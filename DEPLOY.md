# 发布与搜索引擎收录指南

## 零、Docker 快速部署（推荐）

```bash
cp .env.example .env      # 按需修改 SITE_URL 等

docker compose up -d --build
docker compose logs -f    # 查看日志
```

默认只监听 `127.0.0.1:8000`，避免直接暴露；统计数据库持久化在名为 `stats-data` 的卷中。

### 启用自动 HTTPS（Caddy）

1. 把域名解析到服务器；
2. 在 `.env` 里设置：
   ```
   SITE_URL=https://你的域名
   DOMAIN=你的域名
   ```
3. 打开 `docker-compose.yml`，取消 `caddy:` 服务的注释，并把 `web` 的 `ports` 注释掉；
4. `docker compose up -d`，Caddy 会自动申请并续期证书。

> 构建产物已内置 Waitress（单进程多线程），兼容 SQLite 写入。
> 容器以非 root 用户运行，并带有 `/health` 健康检查。

### 常用命令

```bash
docker compose ps                          # 状态
docker compose logs -f web                 # 日志
docker compose up -d --build               # 重新构建并启动
docker compose down                        # 停止（保留数据卷）
docker compose down -v                     # 停止并删除统计数据

docker compose exec web python -c "..."    # 在容器内执行命令
```

## 一、前置条件（必须）

搜索引擎**不会收录** `127.0.0.1`、局域网 IP 或纯 IP 地址的站点。你需要：

1. **公网域名**，例如 `epub.example.com`
2. **HTTPS**（强烈建议，Google 明确对 HTTPS 优先，且浏览器对 HTTP 页面会提示不安全）
3. **公网可达**，443 端口可从外网访问

## 二、配置站点信息

所有 SEO 相关内容都通过环境变量配置，无需改代码：

```bash
export SITE_URL="https://epub.example.com"     # 必须，末尾不要带斜杠
export SITE_NAME="EPUB 繁转简"
export SITE_DESCRIPTION="免费在线将繁体中文 EPUB 电子书转换为简体中文……"
export SITE_KEYWORDS="epub 繁转简,繁体转简体,epub 转换,电子书简繁转换"

# 可选：搜索引擎站长平台验证码
export GOOGLE_SITE_VERIFICATION="xxxx"
export BING_SITE_VERIFICATION="xxxx"
export BAIDU_SITE_VERIFICATION="xxxx"

# 可选：是否允许收录 /stats 统计页（默认不收录）
export INDEX_STATS_PAGE="0"
```

## 三、用生产级服务器运行（非 Docker 场景）

如果不用 Docker，请**不要**用 Flask 自带的开发服务器对外提供服务。推荐 Waitress（纯 Python，跨平台）：

```bash
.venv/bin/pip install waitress
.venv/bin/waitress-serve --host 127.0.0.1 --port 8000 app:app
```

或 Gunicorn（Linux/macOS）：

```bash
.venv/bin/pip install gunicorn
.venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 app:app
```

> 注意：`stats.py` 使用 WAL 模式的 SQLite + 线程锁，适合多线程单进程。
> 若用 Gunicorn 多 worker（`-w 4`），SQLite 写入偶发 `database is locked`，
> 建议 `-w 1 --threads 8`，或改用 Waitress（单进程多线程）。

## 四、反向代理 + HTTPS

### 方案 A：Caddy（自动 HTTPS，最省事）

`Caddyfile`：

```
epub.example.com {
    encode zstd gzip
    request_body {
        max_size 210MB
    }
    reverse_proxy 127.0.0.1:8000
}
```

启动：`caddy run`。Caddy 会自动申请并续期 Let's Encrypt 证书。

### 方案 B：Nginx + certbot

```nginx
server {
    listen 443 ssl http2;
    server_name epub.example.com;

    ssl_certificate     /etc/letsencrypt/live/epub.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/epub.example.com/privkey.pem;

    client_max_body_size 210m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name epub.example.com;
    return 301 https://$host$request_uri;
}
```

> `X-Real-IP` / `X-Forwarded-For` 一定要传，否则统计里所有访问都会记成代理 IP（127.0.0.1）。
> 服务优先读取 `X-Real-IP`，其次 `X-Forwarded-For` 的第一个地址。

## 五、已内置的 SEO 支持

发布后这些路由即可用：

| 路径 | 作用 |
|------|------|
| `/robots.txt` | 允许抓取，屏蔽 `/api/` 与 `/stats`，并指向 sitemap |
| `/sitemap.xml` | 站点地图 |
| `/favicon.svg` | 站点图标 |

页面已包含：

- `<title>` / `<meta name="description">` / `keywords`
- `<link rel="canonical">` 与 `hreflang`
- Open Graph / Twitter Card（社交分享预览）
- **JSON-LD 结构化数据**：`WebApplication`（工具类）+ `FAQPage`（常见问题，有机会在搜索结果中展示富摘要）
- 页面底部有**可抓取的纯文本内容**（工具说明、使用步骤、常见问题）。
  纯 JS 应用搜索引擎可能抓不到内容，因此这段文本很关键。

## 六、提交到搜索引擎

配置好域名与验证码后：

1. **Google**：<https://search.google.com/search-console>
   - 添加资源 → 域名验证（DNS TXT 或 HTML 标签，填 `GOOGLE_SITE_VERIFICATION`）
   - 「站点地图」提交 `https://epub.example.com/sitemap.xml`
   - 用「网址检查」请求编入索引
2. **Bing**：<https://www.bing.com/webmasters>
   - 可直接从 Google Search Console 导入
3. **百度**：<https://ziyuan.baidu.com>
   - 提交站点 + sitemap（百度对国内中文站点收录较积极）

## 七、加速收录的建议

- **获取外链**：在相关论坛、博客、GitHub README、Docker Hub 等地方放上你的网址，外链是收录的强信号
- **保证内容原创且有价值**：可在页面补充更详细的使用教程、支持格式说明、与原书对照的示例
- **保持可访问性**：搜索引擎抓取失败会降低频率，确保服务稳定（可加 Uptime 监控）
- **提交后耐心等待**：Google 通常几天到几周；百度对新站可能更久
- **HTTPS 必须稳定**：证书过期会导致大量页面抓取失败

## 八、合规提醒

- 提供**版权内容转换**服务可能涉及法律风险，请在页面明确说明工具用途（用户对自己拥有的合法电子书做格式转换），并保留必要的免责声明。
- 不要托管或分享用户上传的书籍，本项目已做到处理后立即删除。
