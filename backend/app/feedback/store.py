"""反馈存储（JSON 文件，MVP）。

用户对回答点 👍/👎，记录在 data/feedback.json（已 gitignore），供人工评审后回流到语义层。
"""
import json
import threading
import time
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FILE = PROJECT_ROOT / "data" / "feedback.json"
_lock = threading.Lock()


def _load() -> list:
    if not FILE.exists():
        return []
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save(items: list) -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def add(item: dict) -> dict:
    with _lock:
        items = _load()
        item = {**item, "id": uuid.uuid4().hex[:8], "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
        items.append(item)
        _save(items)
    return item


def list_all() -> list:
    return list(reversed(_load()))  # 新的在前
