from __future__ import annotations
import os
import asyncio
from typing import Any, Dict, List, Optional

# ---- 尝试使用你项目的 llm.py（优先）----
_llm = None
try:
    # 你的项目里保留了 llm.py，我们尽量复用
    import llms.llm as _llm  # type: ignore
except Exception:
    _llm = None

# ---- 兜底：OpenAI 兼容接口（Qwen 也可走兼容模式）----
import httpx

def _build_openai_messages(system_prompt: str, user_content: str, extras: Optional[List[Dict[str, Any]]] = None):
    msgs = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]
    if extras:
        msgs[1]["content"] = user_content  # 保持 user 内容在末尾
    return msgs

async def _openai_chat_async(
    model: str,
    api_key: str,
    base_url: str,
    system_prompt: str,
    user_content: str,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> str:
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": _build_openai_messages(system_prompt, user_content),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=60.0, base_url=base_url.rstrip("/")) as client:
        r = await client.post("/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]

def _openai_chat_sync(
    model: str,
    api_key: str,
    base_url: str,
    system_prompt: str,
    user_content: str,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> str:
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": _build_openai_messages(system_prompt, user_content),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    with httpx.Client(timeout=60.0, base_url=base_url.rstrip("/")) as client:
        r = client.post("/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]

# ---- Agent 垫片实现 ----
class _SimpleAgent:
    """
    提供 invoke/ainvoke 两种方式。
    期望输入：dict，包含 "input" 或 "text" 字段；也支持直接传 string。
    输出：dict，{"output": "..."}，保持简单通用。
    """
    def __init__(self, system_prompt: str, temperature: float = 0.2, max_tokens: int = 1024):
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens

        # 读取 ENV（Qwen 兼容 OpenAI）
        self.model = os.getenv("MODEL_NAME", "qwen-max")
        self.base_url = os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode")
        self.api_key = os.getenv("QWEN_API_KEY") or os.getenv("OPENAI_API_KEY")

    def _extract_user_text(self, inp: Any) -> str:
        if isinstance(inp, str):
            return inp
        if isinstance(inp, dict):
            return inp.get("input") or inp.get("text") or ""
        return str(inp)

    # --------- 同步 ----------
    def invoke(self, inp: Any, **kwargs) -> Dict[str, Any]:
        text = self._extract_user_text(inp)
        # 优先走你自己的 llm.py（如果可用）
        if _llm is not None:
            # 兼容多种可能的 llm 接口
            if hasattr(_llm, "chat_completion"):  # 例如 chat_completion(system, user)
                out = _llm.chat_completion(self.system_prompt, text, **kwargs)  # type: ignore
                if isinstance(out, dict) and "content" in out:
                    return {"output": out["content"]}
                return {"output": str(out)}

            if hasattr(_llm, "complete"):  # 例如 complete(prompt)
                prompt = f"{self.system_prompt}\n\n用户：{text}"
                out = _llm.complete(prompt, **kwargs)  # type: ignore
                return {"output": str(out)}
            
def create_agent(
    name: str,
    system_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    **kwargs,
):
    """
    统一工厂方法，返回一个具有 .invoke() / .ainvoke() 的 Agent 实例。
    被 nodes 里的代码 import 使用。
    """
    return _SimpleAgent(
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
)