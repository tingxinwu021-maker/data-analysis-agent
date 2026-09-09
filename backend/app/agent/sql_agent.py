"""Text-to-SQL 核心编排：生成 SQL → 校验 → 执行 → 解释。

当前用 MySQL（SQLAlchemy）执行查询。
"""
import datetime as dt
import json
import re
import time

import numpy as np
import pandas as pd
from sqlalchemy import text

from ..db.connection import get_mysql_engine
from ..llm.client import chat, chat_stream, chat_with_tools
from ..observability import trace
from ..semantic import tools as semantic_tools
from ..semantic.loader import load_semantic_layer
from . import conversation, prompts

# 出现即拒绝的关键字（保守起见，字符串里出现也拒绝）
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|truncate|grant|revoke|merge|"
    r"attach|detach|copy|export|import|pragma|set|replace|call|vacuum|into)\b",
    re.IGNORECASE,
)

MAX_ROWS = 1000   # 返回给前端的最大行数，防止结果过大
MAX_RETRY = 1     # 执行报错后的自动修正次数
MAX_TOOL_ROUNDS = 4  # 检索工具最多来回几轮，防止死循环


def _extract_sql(raw: str) -> str:
    """从模型回复里抽取纯 SQL（去代码块、多余解释、结尾分号）。"""
    raw = raw.strip()
    m = re.search(r"```(?:sql)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
    start = re.search(r"\b(SELECT|WITH)\b", raw, re.IGNORECASE)
    if start:
        raw = raw[start.start():]
    return raw.strip().rstrip(";").strip()


def validate_sql(sql: str) -> tuple[bool, str]:
    """只读校验：只允许单条 SELECT / WITH 查询。"""
    if not sql:
        return False, "SQL 为空"
    if FORBIDDEN.search(sql):
        return False, "包含禁止的写操作关键字"
    stripped = sql.strip().rstrip(";").strip()
    if ";" in stripped:
        return False, "只允许单条 SQL"
    if not re.match(r"^(SELECT|WITH)\b", stripped, re.IGNORECASE):
        return False, "只允许 SELECT / WITH 查询"
    return True, ""


def execute_sql(sql: str) -> pd.DataFrame:
    """在 MySQL 上执行查询，返回 pandas DataFrame。

    用 text() 包裹原始 SQL，让 SQLAlchemy 正确转义 pymysql 的 % 占位符
    （例如 DATE_FORMAT 里的 '%Y-%m-%d' 这类字面百分号）。
    """
    return pd.read_sql(text(sql), get_mysql_engine())


def _jsonable_value(v):
    """把 pandas/numpy 的日期、数值类型转成纯 Python 可 JSON 序列化的值。"""
    if isinstance(v, dt.datetime):          # 含 pandas Timestamp（datetime 子类）
        return v.isoformat(sep=" ")
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, np.generic):           # numpy 标量（int64/float64/datetime64 等）
        return _jsonable_value(v.item())
    return v


def _df_to_jsonable(df) -> list[dict]:
    return [
        {k: _jsonable_value(v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


def _message_to_dict(msg) -> dict:
    """把 OpenAI message 对象转成可回传 messages 列表的 dict（含 tool_calls）。"""
    out = {"role": "assistant", "content": msg.content}
    if msg.tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
    return out


def _generate_sql(question: str, system: str, previous_error: str | None = None) -> tuple[str, list]:
    """通过「语义层检索工具」让模型按需拉取 schema / 示例，最后用 submit_query 结构化提交 SQL。

    返回 (sql, tool_calls)：tool_calls 为本次调用过的工具清单（供审计）。
    若模型没走工具（DeepSeek 兼容兜底），回退到老的文本提取 _extract_sql。
    """
    user = f"问题：{question}"
    if previous_error:
        user += f"\n\n上一次生成的 SQL 执行报错：\n{previous_error}\n请修正后重新提交 SQL。"

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    sl = load_semantic_layer()
    tool_defs = semantic_tools.build_tool_defs()
    tool_calls_log: list[dict] = []

    for _ in range(MAX_TOOL_ROUNDS):
        msg = chat_with_tools(messages, tool_defs, temperature=0)
        messages.append(_message_to_dict(msg))

        # 模型没调用任何工具：回退到文本提取（兼容某些模型忽略 tools 的情况）
        if not msg.tool_calls:
            return _extract_sql(msg.content or ""), tool_calls_log

        submitted_sql = None
        tool_results = []
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls_log.append({"tool": name, "args": args})
            if name == "submit_query":
                submitted_sql = (args.get("sql") or "").strip()
                continue  # 提交工具不需要回填执行结果
            result = semantic_tools.execute_tool(name, args, sl)
            tool_results.append({"id": tc.id, "result": result})

        if submitted_sql is not None:
            return submitted_sql, tool_calls_log

        for item in tool_results:
            messages.append({
                "role": "tool",
                "tool_call_id": item["id"],
                "content": item["result"],
            })

    # 超过轮数仍未提交：返回空 SQL，交给上层校验/重试兜底
    return "", tool_calls_log


def _generate_and_execute(question: str, system: str):
    """生成 SQL 并执行（含一次自动重试），返回 (sql, df, error, tool_calls)。"""
    sql, tool_calls = _generate_sql(question, system)
    ok, err = validate_sql(sql)
    if not ok:
        return sql, None, f"SQL 校验失败：{err}", tool_calls

    df = None
    last_err = None
    for _ in range(MAX_RETRY + 1):
        try:
            df = execute_sql(sql)
            break
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            sql, tc = _generate_sql(question, system, previous_error=last_err)
            tool_calls += tc
            ok, err = validate_sql(sql)
            if not ok:
                return sql, None, f"SQL 校验失败：{err}", tool_calls

    if df is None:
        return sql, None, f"执行失败：{last_err}", tool_calls
    return sql, df, None, tool_calls


def _explain(question: str, sql: str, df) -> str:
    preview = df.head(5).to_string(index=False)
    user = (
        f"问题：{question}\n"
        f"SQL：{sql}\n"
        f"结果共 {len(df)} 行，前 5 行：\n{preview}\n\n"
        "请用 2-4 句简洁中文直接回答用户的问题，不要复述 SQL。"
    )
    raw = chat(
        [{"role": "system", "content": "你是数据分析助手，用简洁中文解释查询结果。"},
         {"role": "user", "content": user}],
        temperature=0,
    )
    return raw.strip()


def _explain_stream(question: str, sql: str, df):
    """流式解释：逐段产出自然语言解释。"""
    preview = df.head(5).to_string(index=False)
    user = (
        f"问题：{question}\n"
        f"SQL：{sql}\n"
        f"结果共 {len(df)} 行，前 5 行：\n{preview}\n\n"
        "请用 2-4 句简洁中文直接回答用户的问题，不要复述 SQL。"
    )
    messages = [
        {"role": "system", "content": "你是数据分析助手，用简洁中文解释查询结果。"},
        {"role": "user", "content": user},
    ]
    yield from chat_stream(messages, temperature=0)


def query(question: str, session_id: str | None = None) -> dict:
    """生成 SQL 并执行（不含解释），返回原始 DataFrame。供评测与内部使用。"""
    t0 = time.time()
    sl = load_semantic_layer()
    history = conversation.get_history(session_id) if session_id else []
    system = prompts.build_system_prompt(sl, history)

    sql, df, err, tool_calls = _generate_and_execute(question, system)
    latency_ms = int((time.time() - t0) * 1000)
    if err:
        trace.log_query(mode="sql", question=question, sql=sql, error=err,
                        latency_ms=latency_ms, session_id=session_id, tool_calls=tool_calls)
        return {"question": question, "sql": sql, "error": err}

    if session_id:
        conversation.add_turn(session_id, question, sql)
    trace.log_query(mode="sql", question=question, sql=sql, row_count=len(df),
                    latency_ms=latency_ms, session_id=session_id, tool_calls=tool_calls)
    return {"question": question, "sql": sql, "df": df}


def answer(question: str, session_id: str | None = None) -> dict:
    """端到端（一次性）：问题 → SQL → 执行 → 自然语言解释。"""
    r = query(question, session_id)
    if "error" in r:
        return r

    df = r["df"]
    truncated = len(df) > MAX_ROWS
    head = df.head(MAX_ROWS)
    explanation = _explain(question, r["sql"], head)

    return {
        "question": question,
        "sql": r["sql"],
        "columns": df.columns.tolist(),
        "rows": _df_to_jsonable(head),
        "row_count": len(df),
        "truncated": truncated,
        "explanation": explanation,
    }


def answer_stream(question: str, session_id: str | None = None):
    """端到端（流式）：按阶段产出事件 dict，供 SSE 逐条推送。

    事件 type：sql / result / delta / error / done
    """
    sl = load_semantic_layer()
    history = conversation.get_history(session_id) if session_id else []
    system = prompts.build_system_prompt(sl, history)

    sql, tool_calls = _generate_sql(question, system)
    yield {"type": "sql", "sql": sql}

    ok, err = validate_sql(sql)
    if not ok:
        trace.log_query(mode="sql", question=question, sql=sql, error=err,
                        session_id=session_id, tool_calls=tool_calls)
        yield {"type": "error", "error": f"SQL 校验失败：{err}"}
        return

    df = None
    last_err = None
    for _ in range(MAX_RETRY + 1):
        try:
            df = execute_sql(sql)
            break
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            sql, tc = _generate_sql(question, system, previous_error=last_err)
            tool_calls += tc
            yield {"type": "sql", "sql": sql}
            ok, err = validate_sql(sql)
            if not ok:
                trace.log_query(mode="sql", question=question, sql=sql, error=err,
                                session_id=session_id, tool_calls=tool_calls)
                yield {"type": "error", "error": f"SQL 校验失败：{err}"}
                return

    if df is None:
        trace.log_query(mode="sql", question=question, sql=sql, error=last_err,
                        session_id=session_id, tool_calls=tool_calls)
        yield {"type": "error", "error": f"执行失败：{last_err}"}
        return

    if session_id:
        conversation.add_turn(session_id, question, sql)
    trace.log_query(mode="sql", question=question, sql=sql, row_count=len(df),
                    session_id=session_id, tool_calls=tool_calls)

    truncated = len(df) > MAX_ROWS
    head = df.head(MAX_ROWS)
    yield {
        "type": "result",
        "columns": df.columns.tolist(),
        "rows": _df_to_jsonable(head),
        "row_count": len(df),
        "truncated": truncated,
    }

    full = ""
    for delta in _explain_stream(question, sql, head):
        full += delta
        yield {"type": "delta", "text": delta}
    yield {"type": "done", "explanation": full}
