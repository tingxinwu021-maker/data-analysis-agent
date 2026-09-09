"""仪表盘存储（JSON 文件，MVP）。

单用户够用；多用户/并发可换数据库。文件在 data/dashboards.json（已 gitignore）。
"""
import json
import threading
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FILE = PROJECT_ROOT / "data" / "dashboards.json"
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


def list_all() -> list:
    return _load()


def add(item: dict) -> dict:
    with _lock:
        items = _load()
        item = {**item, "id": uuid.uuid4().hex[:8]}
        items.append(item)
        _save(items)
    return item


def delete(item_id: str) -> bool:
    with _lock:
        items = [i for i in _load() if i.get("id") != item_id]
        _save(items)
    return True
