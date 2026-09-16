#!/usr/bin/env python3
"""
SQLite 访问 / 转换统计。

记录:
- visits   : 每次页面访问 (IP、时间、User-Agent)
- converts : 每次转换 (IP、时间、文件名、大小、是否成功、耗时、转换文件数)
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 数据库路径，可通过 STATS_DB 环境变量覆盖（Docker 中指向持久化卷）
DB_PATH = os.environ.get("STATS_DB", os.path.join(BASE_DIR, "stats.db"))

# 本地时区 (用于按“天”聚合)。可按需改成固定时区，如 timezone(timedelta(hours=8))
LOCAL_TZ = datetime.now().astimezone().tzinfo or timezone.utc

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS visits (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT    NOT NULL,          -- ISO8601 (本地时区)
    day        TEXT    NOT NULL,          -- YYYY-MM-DD
    ip         TEXT    NOT NULL,
    path       TEXT    NOT NULL,
    user_agent TEXT
);
CREATE INDEX IF NOT EXISTS idx_visits_day ON visits(day);
CREATE INDEX IF NOT EXISTS idx_visits_ip  ON visits(ip);

CREATE TABLE IF NOT EXISTS converts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT    NOT NULL,
    day        TEXT    NOT NULL,
    ip         TEXT    NOT NULL,
    filename   TEXT,
    size       INTEGER,                   -- 上传字节数
    success    INTEGER NOT NULL,          -- 1 成功 / 0 失败
    files      INTEGER,                   -- 转换的文本文件数
    duration   REAL,                      -- 秒
    user_agent TEXT
);
CREATE INDEX IF NOT EXISTS idx_converts_day ON converts(day);
CREATE INDEX IF NOT EXISTS idx_converts_ip  ON converts(ip);
"""


def init_db():
    """创建表结构 (幂等)。"""
    db_dir = os.path.dirname(os.path.abspath(DB_PATH))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now():
    now = datetime.now(LOCAL_TZ)
    return now.isoformat(timespec="seconds"), now.strftime("%Y-%m-%d")


def get_client_ip(request) -> str:
    """取真实客户端 IP。

    优先级:
      1. X-Real-IP         (nginx 等反向代理设置的真实客户端 IP)
      2. X-Forwarded-For   (取最左侧第一个地址，即原始客户端)
      3. remote_addr       (无代理时的直连地址)
    """
    real_ip = request.headers.get("X-Real-IP")
    if real_ip and real_ip.strip():
        return real_ip.split(",")[0].strip()

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first

    return request.remote_addr or "unknown"


def record_visit(ip, path, user_agent=None):
    ts, day = _now()
    with _lock, connect() as conn:
        conn.execute(
            "INSERT INTO visits (ts, day, ip, path, user_agent) VALUES (?,?,?,?,?)",
            (ts, day, ip, path, (user_agent or "")[:512]),
        )


def record_convert(ip, filename, size, success, files=None,
                   duration=None, user_agent=None):
    ts, day = _now()
    with _lock, connect() as conn:
        conn.execute(
            """INSERT INTO converts
               (ts, day, ip, filename, size, success, files, duration, user_agent)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (ts, day, ip, (filename or "")[:512], size, 1 if success else 0,
             files, duration, (user_agent or "")[:512]),
        )


def get_stats(days: int = 30):
    """返回汇总统计。"""
    with connect() as conn:
        total_visits = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
        total_converts = conn.execute(
            "SELECT COUNT(*) FROM converts WHERE success=1"
        ).fetchone()[0]
        total_failed = conn.execute(
            "SELECT COUNT(*) FROM converts WHERE success=0"
        ).fetchone()[0]
        unique_ips = conn.execute(
            "SELECT COUNT(DISTINCT ip) FROM visits"
        ).fetchone()[0]
        bytes_total = conn.execute(
            "SELECT COALESCE(SUM(size),0) FROM converts WHERE success=1"
        ).fetchone()[0]

        # 每日处理量 (最近 days 天)
        rows = conn.execute(
            """SELECT day,
                      COUNT(*)                              AS converts,
                      COALESCE(SUM(size),0)                 AS bytes,
                      COUNT(DISTINCT ip)                    AS ips
               FROM converts
               WHERE success=1 AND day >= date('now', ?)
               GROUP BY day ORDER BY day""",
            ("-%d days" % days,),
        ).fetchall()
        daily = [dict(r) for r in rows]

        daily_visits = conn.execute(
            """SELECT day, COUNT(*) AS visits, COUNT(DISTINCT ip) AS ips
               FROM visits
               WHERE day >= date('now', ?)
               GROUP BY day ORDER BY day""",
            ("-%d days" % days,),
        ).fetchall()
        visit_map = {r["day"]: dict(r) for r in daily_visits}

        # 合并成完整日期序列 (含 0 的日期)
        merged = {}
        today = datetime.now(LOCAL_TZ).date()
        for i in range(days - 1, -1, -1):
            d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            merged[d] = {
                "day": d,
                "converts": 0,
                "bytes": 0,
                "visits": 0,
                "ips": 0,
            }
        for item in daily:
            merged[item["day"]]["converts"] = item["converts"]
            merged[item["day"]]["bytes"] = item["bytes"]
        for day, item in visit_map.items():
            if day in merged:
                merged[day]["visits"] = item["visits"]
                merged[day]["ips"] = item["ips"]

        daily_merged = list(merged.values())

        recent = conn.execute(
            """SELECT ts, ip, filename, size, success, files, duration
               FROM converts ORDER BY id DESC LIMIT 50"""
        ).fetchall()

        top_ips = conn.execute(
            """SELECT ip, COUNT(*) AS cnt, MAX(ts) AS last_ts
               FROM visits GROUP BY ip ORDER BY cnt DESC LIMIT 20"""
        ).fetchall()

    return {
        "total_visits": total_visits,
        "total_converts": total_converts,
        "total_failed": total_failed,
        "unique_ips": unique_ips,
        "bytes_total": bytes_total,
        "daily": daily_merged,
        "recent": [dict(r) for r in recent],
        "top_ips": [dict(r) for r in top_ips],
    }
