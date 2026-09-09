"""构建给 LLM 的提示词：把语义层转成上下文。

策略（配合 semantic/tools.py 的函数调用）：
- 常驻 prompt 只放「目录」：表名/描述 + 指标全文 + 示例问题（无 SQL）+ 规则。
- 字段详情、示例 SQL 由模型通过工具（get_table_schema / search_examples）按需拉取，
  避免整份语义层无脑塞进上下文。
"""
from ..semantic.loader import SemanticLayer


def _format_table_catalog(sl: SemanticLayer) -> str:
    lines = []
    for model in sl.models:
        lines.append(f"- {model.name}：{model.description}")
    return "\n".join(lines)


def _format_metrics(sl: SemanticLayer) -> str:
    lines = []
    for m in sl.metrics:
        expr = m.expression if m.expression else "（需特殊写法，见示例）"
        lines.append(f"- {m.name}：{m.description} 表达式：{expr}（作用于 {m.entity}）")
    return "\n".join(lines)


def _format_example_catalog(sl: SemanticLayer) -> str:
    return "\n".join(f"- {ex.question}" for ex in sl.examples)


def _format_history(history: list[dict]) -> str:
    lines = []
    for h in history:  # 历史已在 conversation.get_history 里按注入上限裁剪
        lines.append(f"问：{h['question']}\nSQL：{h['sql']}")
    return "\n\n".join(lines)


def build_system_prompt(sl: SemanticLayer, history: list[dict] | None = None) -> str:
    """拼装 system prompt：表目录 + 指标 + 示例问题 + 对话历史 + 规则。

    用字符串拼接而非 .format，避免语义层里出现 {} 时被误当占位符。
    """
    history_str = _format_history(history) if history else ""

    parts = [
        "你是一个数据分析助手，负责把用户的自然语言问题转换成 MySQL SQL 查询。\n\n",
        "## 可用的表（需要字段清单时调用 get_table_schema 工具）\n" + _format_table_catalog(sl) + "\n\n",
        "## 业务指标（把用户黑话映射到聚合表达式）\n" + _format_metrics(sl) + "\n\n",
        "## 精选示例（需要参考 SQL 时调用 search_examples 工具）\n" + _format_example_catalog(sl) + "\n\n",
    ]
    if history_str:
        parts.append("## 对话历史（用于理解指代，如「那按国家分呢」）\n" + history_str + "\n\n")
    parts.append(
        "## 规则\n"
        "1. 写 SQL 前，先调用 get_table_schema 工具确认要用的表和字段，不要臆造字段。\n"
        "2. 只能使用 SELECT 或 WITH 查询，禁止任何写操作。\n"
        "3. 只能使用 get_table_schema 返回的表和字段。\n"
        "4. 时间处理：按天用 DATE(event_time)，按周用 YEARWEEK(event_time)，按月用 DATE_FORMAT(event_time, '%Y-%m-01')。\n"
        "5. 用户可能用业务黑话（如「日活」「留存」「漏斗」），参照上面的业务指标；留存/漏斗等复杂指标用 search_examples 工具找参考 SQL。\n"
        "6. 确认无误后，调用 submit_query 工具提交最终 SQL（只一条 SELECT / WITH）。\n"
    )
    return "".join(parts)
