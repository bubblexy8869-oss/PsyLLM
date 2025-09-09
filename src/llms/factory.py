from __future__ import annotations
from typing import Any, Dict, Optional, Callable, Iterable
import os

# ===== 可直接跑的占位模型 =====
class DummyLLM:
    """
    最小可用占位模型：支持 .invoke 和 .stream（stream 会一次性返回）。
    """
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def invoke(self, prompt: str) -> str:
        # 返回一个空 JSON；方便你全链路不报错
        return "{}"

    def stream(self, prompt: str, on_token: Callable[[str], None]) -> str:
        # 占位：一次性吐出，无真实逐 token
        text = self.invoke(prompt)
        if on_token:
            on_token(text)
        return text


# ====== OpenAI 适配（按需启用） ======
class OpenAILLM:
    """
    轻量封装：满足 .invoke(prompt)->str 和 .stream(prompt,on_token)->str
    需要：
      - OPENAI_API_KEY
      - OPENAI_MODEL (默认 "gpt-4o-mini")
    """
    def __init__(self, model: Optional[str] = None, **kwargs: Any) -> None:
        from openai import OpenAI  # pip install openai>=1.0
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.kwargs = kwargs

    def invoke(self, prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.kwargs.get("temperature", 0.2),
        )
        return resp.choices[0].message.content or ""

    def stream(self, prompt: str, on_token: Callable[[str], None]) -> str:
        """
        逐 token 推送（SSE/WS 可转发）。返回最终完整文本。
        注意：对 JSON 提示，前端可仅用最终 JSON，tokens 用于“打字机体验”。
        """
        text_parts: list[str] = []
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.kwargs.get("temperature", 0.2),
            stream=True,
        )
        for chunk in stream:
            delta = ""
            try:
                delta = chunk.choices[0].delta.content or ""
            except Exception:
                delta = ""
            if delta:
                text_parts.append(delta)
                if on_token:
                    on_token(delta)
        return "".join(text_parts)


# ====== Anthropic（Claude）适配（按需启用） ======
class AnthropicLLM:
    """
    满足 .invoke/.stream
    需要：
      - ANTHROPIC_API_KEY
      - ANTHROPIC_MODEL (默认 "claude-3-5-sonnet-20240620")
    """
    def __init__(self, model: Optional[str] = None, **kwargs: Any) -> None:
        import anthropic  # pip install anthropic
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")
        self.kwargs = kwargs

    def invoke(self, prompt: str) -> str:
        # 简化为单轮 user 提示；若你用 system/tools，可自行扩展
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.kwargs.get("max_tokens", 2048),
            temperature=self.kwargs.get("temperature", 0.2),
            messages=[{"role": "user", "content": prompt}],
        )
        parts = []
        for block in resp.content or []:
            t = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else None)
            if t:
                parts.append(t)
        return "".join(parts)

    def stream(self, prompt: str, on_token: Callable[[str], None]) -> str:
        # 使用 event stream；把 text-delta 累加并回调
        import anthropic
        full = []
        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.kwargs.get("max_tokens", 2048),
            temperature=self.kwargs.get("temperature", 0.2),
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for event in stream:
                # 兼容 SDK 事件：TextDelta/TextCreated 等
                if getattr(event, "type", "") == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta and getattr(delta, "type", "") == "text_delta":
                        token = getattr(delta, "text", "")
                        if token:
                            full.append(token)
                            if on_token:
                                on_token(token)
                # 也兼容 dict 风格
                elif isinstance(event, dict) and event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        token = delta.get("text", "")
                        if token:
                            full.append(token)
                            if on_token:
                                on_token(token)
            # 结束会 flush final message
            try:
                stream.get_final_message()
            except Exception:
                pass
        return "".join(full)


# ===== 工厂方法 =====
def get_llm(config: Dict[str, Any] | None = None):
    cfg = config or {}
    provider = (cfg.get("provider") or os.getenv("MODEL_PROVIDER") or "").lower().strip()
    if provider == "openai":
        return OpenAILLM(model=cfg.get("model"), **cfg)
    if provider == "anthropic":
        return AnthropicLLM(model=cfg.get("model"), **cfg)
    return DummyLLM(**cfg)