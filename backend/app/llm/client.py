"""LLM 客户端：统一封装 OpenAI 兼容接口。

DeepSeek / Qwen / Moonshot / GLM 等国产模型都提供 OpenAI 兼容 endpoint，
因此切换供应商只需改 .env 里的 base_url 与 model，无需改代码。
"""
from openai import OpenAI

from ..config import settings

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
    return _client


def chat(messages: list[dict], **kwargs) -> str:
    """发送消息，返回模型文本回复（可传入 temperature 等参数）。"""
    resp = get_client().chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        **kwargs,
    )
    return resp.choices[0].message.content or ""


def chat_with_tools(messages: list[dict], tools: list[dict], **kwargs):
    """发送消息并返回完整 message 对象（含 tool_calls），供函数调用循环使用。

    与 chat() 不同：chat() 只取文本 content，这里需要读 message.tool_calls
    并把工具结果以 role=tool 消息回填，因此返回整个 message。
    """
    resp = get_client().chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        **kwargs,
    )
    return resp.choices[0].message


def chat_stream(messages: list[dict], **kwargs):
    """流式发送消息，逐段产出文本增量（供 SSE 使用）。"""
    stream = get_client().chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        stream=True,
        **kwargs,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
