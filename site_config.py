#!/usr/bin/env python3
"""
站点级配置。发布时请通过环境变量覆盖，例如:

    export SITE_URL="https://epub.example.com"
    export SITE_NAME="EPUB 繁转简"
"""

import os

# 站点对外访问根地址，末尾不要带斜杠。发布后必须改成真实域名+协议。
SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8000").rstrip("/")

SITE_NAME = os.environ.get("SITE_NAME", "EPUB 繁转简")

SITE_DESCRIPTION = os.environ.get(
    "SITE_DESCRIPTION",
    "免费在线将繁体中文 EPUB 电子书转换为简体中文，保留原排版与目录结构，"
    "转换完成后直接下载，文件不会被保存。",
)

# 用于 <meta name="keywords">，影响很小，但无害
SITE_KEYWORDS = os.environ.get(
    "SITE_KEYWORDS",
    "epub 繁转简,繁体转简体,epub 转换,电子书简繁转换,在线 epub 转换,"
    "繁体中文字幕转换,中文电子书转换",
)

# 统计页不收录（避免被当成内容页），如需可改为 True
INDEX_STATS_PAGE = os.environ.get("INDEX_STATS_PAGE", "0") == "1"

# 搜索引擎站点验证（可选，填到对应环境变量即可）
GOOGLE_SITE_VERIFICATION = os.environ.get("GOOGLE_SITE_VERIFICATION", "")
BING_SITE_VERIFICATION = os.environ.get("BING_SITE_VERIFICATION", "")
BAIDU_SITE_VERIFICATION = os.environ.get("BAIDU_SITE_VERIFICATION", "")
