# EPUB 繁转简

将**繁体中文 EPUB** 电子书在线转换为**简体中文**，保留原排版、样式与目录结构。

Flask + OpenCC + SQLite，支持 Docker 一键部署与搜索引擎收录。

## 特性

- **安全的转换策略** —— 只替换文本节点，保留所有标签、属性、CSS 样式与图片资源，绝不动标签名、`id`、`class`、`href` 等结构信息
- **符合规范** —— 重新打包时保持 `mimetype` 为首个条目且不压缩，并更新 `dc:language` 为 `zh-CN`
- **Web 界面** —— 支持拖拽上传、进度显示、转换完成后直接下载
- **访问统计** —— SQLite 记录访问量、来源 IP、每日及累计处理量，附统计看板
- **SEO 友好** —— `robots.txt`、`sitemap.xml`、Open Graph、JSON-LD 结构化数据与可抓取文本内容
- **部署友好** —— Docker 镜像内置 Waitress，非 root 运行，带健康检查

## 快速开始

### Docker（推荐）

```bash
cp .env.example .env          # 按需修改 SITE_URL 等
docker compose up -d --build
```

访问 http://127.0.0.1:8000

### 本地运行

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py                    # http://127.0.0.1:8000
.venv/bin/python app.py --host 0.0.0.0     # 局域网可访问
```

### 命令行用法

转换逻辑可独立使用：

```bash
.venv/bin/python convert_epub.py 输入.epub [输出.epub]
```

未指定输出路径时，默认生成 `输入_简体.epub`。

## 配置

所有配置通过环境变量注入，无需改代码：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SITE_URL` | `http://127.0.0.1:8000` | 对外访问地址，影响 canonical / sitemap / og:url，**发布时必须修改** |
| `SITE_NAME` | `EPUB 繁转简` | 站点名称 |
| `SITE_DESCRIPTION` | 见 `site_config.py` | 页面描述，用于 SEO |
| `SITE_KEYWORDS` | 见 `site_config.py` | 关键词 |
| `INDEX_STATS_PAGE` | `0` | 是否允许搜索引擎收录统计页 |
| `GOOGLE_SITE_VERIFICATION` | 空 | Google Search Console 验证码 |
| `BING_SITE_VERIFICATION` | 空 | Bing Webmaster 验证码 |
| `BAIDU_SITE_VERIFICATION` | 空 | 百度站长平台验证码 |
| `STATS_DB` | `./stats.db` | SQLite 数据库路径 |
| `TZ` | `Asia/Shanghai` | 时区，影响统计按天聚合 |

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 转换页面 |
| POST | `/convert` | 上传并转换，返回 EPUB 附件（字段名 `file`，上限 200 MB） |
| GET | `/stats` | 统计看板 |
| GET | `/api/stats?days=30` | 统计 JSON 数据（`days` 取值 1–365） |
| GET | `/robots.txt` | 爬虫规则 |
| GET | `/sitemap.xml` | 站点地图 |
| GET | `/health` | 健康检查 |

`POST /convert` 示例：

```bash
curl -F "file=@书籍.epub" http://127.0.0.1:8000/convert -o 书籍_简体.epub
```

## 项目结构

```
.
├── app.py              # Flask 服务：路由、埋点、SEO
├── convert_epub.py     # OpenCC 繁转简核心逻辑
├── stats.py            # SQLite 统计模块
├── site_config.py      # 站点配置
├── templates/
│   ├── index.html      # 转换页面
│   └── stats.html      # 统计看板
├── Dockerfile
├── docker-compose.yml  # 编排（含可选 Caddy 自动 HTTPS）
├── Caddyfile
├── .env.example
├── DEPLOY.md           # 发布与搜索引擎收录指南
└── requirements.txt
```

## 发布到公网

要让搜索引擎收录站点，需要公网域名与 HTTPS。仓库内已内置所需支持，详细步骤见 **[DEPLOY.md](DEPLOY.md)**。

启用 Caddy 自动 HTTPS（Let's Encrypt）：

1. 在 `.env` 设置 `SITE_URL=https://你的域名` 与 `DOMAIN=你的域名`
2. 在 `docker-compose.yml` 取消 `caddy` 服务注释，并注释掉 `web` 的 `ports`
3. `docker compose up -d`

## 技术说明

- **转换范围**：EPUB 内的 `.xhtml` / `.html` / `.htm` / `.opf` / `.ncx` / `.xml` / `.css` 文本资源
- **并发模型**：SQLite 使用 WAL 模式 + 线程锁，适配单进程多线程（Waitress）。
  若用 Gunicorn 多 worker，建议 `-w 1 --threads 8`，否则可能出现 `database is locked`
- **隐私**：上传文件仅在临时目录处理，下载完成后立即删除，不做持久化存储

## 免责声明

本工具仅供用户对自己合法拥有、可自由处理的电子书进行格式转换使用。
请勿用于传播受版权保护的内容，因使用本工具产生的一切后果由使用者自行承担。

## License

MIT
