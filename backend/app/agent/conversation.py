"""会话历史（内存存储，MVP）。

单用户、单进程够用；多用户/重启丢失，后续可换 Redis 或数据库。
上下文长度集中在 MAX_STORED / MAX_INJECTED 两个常量，避免散落各处。
"""
import time
from collections import defaultdict, deque

# 上下文长度：内存里最多保留几轮 / 实际注入 prompt 最多几轮
MAX_STORED = 10
MAX_INJECTED = 5
# 会话无活动超过该时长则被懒清理（兜底，防止前端异常退出导致内存无限增长）
SESSION_TTL_SEC = 60 * 60

_store: dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_STORED))
_last_active: dict[str, float] = {}


def _touch(session_id: str) -> None:
    _last_active[session_id] = time.monotonic()


def _sweep() -> None:
    """清理超过 TTL 的会话（懒清理，每次操作时顺带执行）。"""
    now = time.monotonic()
    stale = [sid for sid, ts in _last_active.items() if now - ts > SESSION_TTL_SEC]
    for sid in stale:
        _store.pop(sid, None)
        _last_active.pop(sid, None)


def add_turn(session_id: str, question: str, sql: str) -> None:
    """记录一轮问答（只存问题与生成的 SQL，用于理解后续指代）。"""
    _sweep()
    _store[session_id].append({"question": question, "sql": sql})
    _touch(session_id)


def get_history(session_id: str, limit: int = MAX_INJECTED) -> list[dict]:
    """返回最近 limit 轮历史（默认只取注入上限，控制上下文长度）。"""
    _sweep()
    _touch(session_id)
    return list(_store[session_id])[-limit:]


def clear(session_id: str) -> None:
    """清空某个会话的历史（前端「新对话」时调用）。"""
    _store.pop(session_id, None)
    _last_active.pop(session_id, None)
