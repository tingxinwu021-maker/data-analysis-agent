"""查询追踪/审计日志（JSONL，本地）。

每次查询追加一行：时间、问题、SQL、行数、耗时、错误、会话等。
文件在 data/traces.jsonl（已 gitignore）。
"""
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FILE = PROJECT_ROOT / "data" / "traces.jsonl"


def log_query(**fields) -> None:
    """追加一条查询记录。fields 可含 mode/question/sql/row_count/latency_ms/error/session_id/tool_calls。"""
    rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), **fields}
    try:
        with FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def recent(limit: int = 50) -> list:
    """返回最近 limit 条记录（倒序）。"""
    if not FILE.exists():
        return []
    lines = FILE.read_text(encoding="utf-8").strip().splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(out))
