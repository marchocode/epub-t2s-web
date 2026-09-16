# syntax=docker/dockerfile:1

FROM python:3.12-slim

# 时区：影响统计按天聚合，可按需修改
ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖，利用镜像层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt waitress

# 拷贝应用代码
COPY app.py convert_epub.py stats.py site_config.py ./
COPY templates/ ./templates/

# 统计数据库目录（挂载卷持久化）
RUN mkdir -p /data && \
    useradd --create-home --uid 10001 appuser && \
    chown -R appuser:appuser /app /data

# 数据库路径指向可持久化的卷
ENV STATS_DB=/data/stats.db

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status==200 else 1)"

# 生产级 WSGI 服务器（单进程多线程，兼容 SQLite 写入）
CMD ["waitress-serve", "--host=0.0.0.0", "--port=8000", "--threads=8", "app:app"]
