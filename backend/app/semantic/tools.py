"""语义层检索工具（function calling 的定义 + 执行器）。

配合 agent/prompts.build_system_prompt：prompt 里只放「目录」（表名/描述、指标、示例问题），
字段详情与示例 SQL 由模型按需通过这里的工具拉取，让注入上下文跟「问题」成正比，
而不是跟「整份 semantic.yaml」成正比。

- get_table_schema：某张表的字段清单（字段名/类型/含义/同义词）
- search_examples：按关键词匹配精选示例（问题 → 正确 SQL）
- submit_query：模型最终结构化提交 SQL（由 sql_agent 直接消费，不经过 execute_tool）
"""
import json

from .loader import SemanticLayer


def build_tool_defs() -> list[dict]:
    """返回 OpenAI function calling 的 tools 参数列表。"""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_table_schema",
                "description": "获取某张表的字段清单（字段名/类型/含义/同义词）。写 SQL 前先调用它确认可用字段，避免臆造。",
                "parameters": {
                    "type": "object",
                    "properties": {"table": {"type": "string", "description": "表名（users / events / sessions）"}},
                    "required": ["table"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_examples",
                "description": "按关键词搜索精选示例（问题 → 正确 SQL）。留存、漏斗等复杂问题用它找参考写法。",
                "parameters": {
                    "type": "object",
                    "properties": {"keyword": {"type": "string", "description": "关键词，如：留存 / 漏斗 / 日活 / 国家"}},
                    "required": ["keyword"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "submit_query",
                "description": "提交最终 SQL。确认字段与逻辑无误后调用，只传一条只读的 SELECT / WITH 查询。",
                "parameters": {
                    "type": "object",
                    "properties": {"sql": {"type": "string", "description": "一条只读 MySQL 查询"}},
                    "required": ["sql"],
                },
            },
        },
    ]


def _find_model(sl: SemanticLayer, name: str):
    for m in sl.models:
        if m.name == name:
            return m
    return None


def _get_table_schema(sl: SemanticLayer, table: str) -> str:
    m = _find_model(sl, (table or "").strip())
    if m is None:
        return json.dumps({"error": f"表不存在：{table}"}, ensure_ascii=False)
    return json.dumps(
        {
            "table": m.name,
            "description": m.description,
            "columns": [
                {"name": c.name, "type": c.type, "description": c.description, "synonyms": c.synonyms}
                for c in m.columns
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def _search_examples(sl: SemanticLayer, keyword: str) -> str:
    """关键词检索示例（简单子串匹配，规模大了可换向量/BM25）。"""
    kw = (keyword or "").strip().lower()
    if not kw:
        return json.dumps(
            {"hint": "请提供一个关键词", "available": [e.question for e in sl.examples]},
            ensure_ascii=False,
        )
    hits = [e for e in sl.examples if kw in e.question.lower() or kw in e.sql.lower()]
    if not hits:
        return json.dumps(
            {"hint": "没有匹配的示例，换一个关键词", "available": [e.question for e in sl.examples]},
            ensure_ascii=False,
        )
    return json.dumps(
        {"examples": [{"question": e.question, "sql": e.sql} for e in hits]},
        ensure_ascii=False,
        indent=2,
    )


def execute_tool(name: str, args: dict, sl: SemanticLayer) -> str:
    """执行一个检索工具，返回 JSON 字符串（作为 role=tool 消息回填给模型）。"""
    if name == "get_table_schema":
        return _get_table_schema(sl, args.get("table"))
    if name == "search_examples":
        return _search_examples(sl, args.get("keyword"))
    # submit_query 由 sql_agent 直接消费，不应走到这里
    return json.dumps({"error": f"未知工具：{name}"}, ensure_ascii=False)
