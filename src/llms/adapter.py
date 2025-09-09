# src/llm/adapter.py
from __future__ import annotations
from typing import Any, Callable, Optional
import os, types

from . import llm as legacy_llm  # 直接用你的 llm.py（包内相对导入）

class LegacyLLMAdapter:
    """
    将旧的 llm.py 适配成统一接口：
      - invoke(prompt: str) -> str
      - stream(prompt: str, on_token: Callable[[str], None]) -> str
    尽量兼容 OpenAI/Anthropic/自研/本地网关等多种客户端风格。
    """
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None, **kwargs: Any) -> None:
        self.provider = (provider or os.getenv("MODEL_PROVIDER") or "").lower().strip()
        self.model = model or os.getenv("MODEL_NAME") or os.getenv("BASIC_MODEL__model", "qwen-max")
        self.kwargs = kwargs
        
        # 优先尝试使用新的LLM系统
        try:
            from . import llm as legacy_llm
            self.client = (
                self._try_call(legacy_llm, "get_basic_llm")
                or self._try_call(legacy_llm, "get_chat_model", self.provider, self.model, **kwargs)
                or self._try_call(legacy_llm, "get_client", self.provider, self.model, **kwargs)
                or self._try_call(legacy_llm, "build_client", self.provider, self.model, **kwargs)
                or self._try_call(legacy_llm, "create_chat_client", self.provider, self.model, **kwargs)
                or self._create_direct_client()
            )
        except Exception as e:
            print(f"Warning: Failed to load LLM module: {e}")
            self.client = self._create_direct_client()

    def _create_direct_client(self):
        """直接创建OpenAI兼容客户端"""
        try:
            from langchain_openai import ChatOpenAI
            
            # 从环境变量获取配置
            api_key = (
                os.getenv("BASIC_MODEL__api_key") 
                or os.getenv("DASHSCOPE_API_KEY")
                or os.getenv("OPENAI_API_KEY")
            )
            base_url = (
                os.getenv("BASIC_MODEL__base_url")
                or os.getenv("BASE_URL")
                or os.getenv("OPENAI_BASE_URL")
            )
            
            if not api_key:
                print("Warning: No API key found in environment variables")
                return self._fallback_dummy()
                
            client_kwargs = {
                "model": self.model,
                "api_key": api_key,
                "temperature": float(os.getenv("BASIC_MODEL__temperature", "0.3")),
                "max_tokens": int(os.getenv("BASIC_MODEL__max_tokens", "4000")),
            }
            
            if base_url:
                client_kwargs["base_url"] = base_url
                
            return ChatOpenAI(**client_kwargs)
            
        except Exception as e:
            print(f"Warning: Failed to create direct client: {e}")
            return self._fallback_dummy()

    # === public API ===
    def invoke(self, prompt: str) -> str:
        # 优先尝试直接使用底层OpenAI客户端API
        if hasattr(self.client, 'client') and hasattr(self.client.client, 'chat'):
            # ChatOpenAI对象的底层OpenAI客户端
            try:
                openai_client = self.client.client
                resp = openai_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}]
                )
                return self._extract_openai_text(resp)
            except Exception as e:
                print(f"Direct OpenAI client failed: {e}")
        
        if self._has_path(self.client, "chat.completions.create"):
            create = self._get_path(self.client, "chat.completions.create")
            resp = create(model=self.model, messages=[{"role": "user", "content": prompt}])
            return self._extract_openai_text(resp)
            
        if self._has_path(self.client, "messages.create"):
            create = self._get_path(self.client, "messages.create")
            resp = create(model=self.model, messages=[{"role": "user", "content": prompt}], max_tokens=2048)
            return self._extract_anthropic_text(resp)
            
        # 如果上面都不行，尝试LangChain客户端
        if hasattr(self.client, "invoke"):
            # LangChain客户端，使用正确的消息格式
            try:
                from langchain_core.messages import HumanMessage
                # 创建简单的消息格式
                messages = [HumanMessage(content=prompt)]
                result = self.client.invoke(messages)
                if hasattr(result, 'content'):
                    return str(result.content)
                return str(result)
            except Exception as e:
                print(f"LangChain invoke failed: {e}")
                # 如果LangChain失败，尝试直接使用OpenAI API格式
                pass
        if self._has_path(self.client, "chat.completions.create"):
            create = self._get_path(self.client, "chat.completions.create")
            resp = create(model=self.model, messages=[{"role": "user", "content": prompt}])
            return self._extract_openai_text(resp)
        if self._has_path(self.client, "messages.create"):
            create = self._get_path(self.client, "messages.create")
            resp = create(model=self.model, messages=[{"role": "user", "content": prompt}], max_tokens=2048)
            return self._extract_anthropic_text(resp)
        for name in ("call", "generate", "text", "__call__"):
            if hasattr(self.client, name):
                fn = getattr(self.client, name)
                try:
                    out = fn(prompt)
                except TypeError:
                    out = fn(messages=[{"role":"user","content":prompt}])
                return self._to_str(out)
        return "{}"

    def stream(self, prompt: str, on_token: Callable[[str], None]) -> str:
        # 优先尝试直接使用底层OpenAI流式API
        if hasattr(self.client, 'client') and hasattr(self.client.client, 'chat'):
            # ChatOpenAI对象的底层OpenAI客户端
            try:
                openai_client = self.client.client
                stream = openai_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True
                )
                parts=[]
                for chunk in stream:
                    delta = self._extract_openai_delta(chunk)
                    if delta:
                        parts.append(delta)
                        if on_token:
                            on_token(delta)
                return "".join(parts)
            except Exception as e:
                print(f"Direct OpenAI stream failed: {e}")
        
        if self._has_path(self.client, "chat.completions.create"):
            create = self._get_path(self.client, "chat.completions.create")
            stream = create(model=self.model, messages=[{"role":"user","content":prompt}], stream=True)
            parts=[]
            for chunk in stream:
                delta = self._extract_openai_delta(chunk)
                if delta:
                    parts.append(delta)
                    if on_token:
                        on_token(delta)
            return "".join(parts)
            
        if self._has_path(self.client, "messages.stream"):
            stream_fn = self._get_path(self.client, "messages.stream")
            parts=[]
            with stream_fn(model=self.model, messages=[{"role":"user","content":prompt}], max_tokens=2048) as s:
                for event in s:
                    token = self._extract_anthropic_delta(event)
                    if token:
                        parts.append(token)
                        if on_token:
                            on_token(token)
            try: s.get_final_message()
            except Exception: pass
            return "".join(parts)
            
        # 如果底层API不可用，尝试LangChain客户端
        if hasattr(self.client, "stream") and hasattr(self.client, 'invoke'):
            # LangChain客户端，需要Messages格式
            try:
                from langchain_core.messages import HumanMessage
                messages = [HumanMessage(content=prompt)]
                # LangChain stream方法不接受回调函数，只接受消息和配置
                result = self.client.stream(messages)
                parts = []
                for chunk in result:
                    if hasattr(chunk, 'content') and chunk.content:
                        parts.append(chunk.content)
                        if on_token:
                            on_token(chunk.content)
                return ''.join(parts)
            except Exception as e:
                print(f"LangChain stream failed: {e}")
                # 如果LangChain失败，降级到invoke
                text = self.invoke(prompt)
                if on_token:
                    on_token(text)
                return text
        if self._has_path(self.client, "chat.completions.create"):
            create = self._get_path(self.client, "chat.completions.create")
            stream = create(model=self.model, messages=[{"role":"user","content":prompt}], stream=True)
            parts=[]
            for chunk in stream:
                delta = self._extract_openai_delta(chunk)
                if delta:
                    parts.append(delta)
                    if on_token:
                        on_token(delta)
            return "".join(parts)
        if self._has_path(self.client, "messages.stream"):
            stream_fn = self._get_path(self.client, "messages.stream")
            parts=[]
            with stream_fn(model=self.model, messages=[{"role":"user","content":prompt}], max_tokens=2048) as s:
                for event in s:
                    token = self._extract_anthropic_delta(event)
                    if token:
                        parts.append(token)
                        if on_token:
                            on_token(token)
                try: s.get_final_message()
                except Exception: pass
            return "".join(parts)
        # 降级：无流式 -> 一次性回调
        text = self.invoke(prompt)
        if on_token:
            on_token(text)
        return text

    # === helpers ===
    def _try_call(self, obj: Any, name: str, *args, **kw):
        if hasattr(obj, name):
            fn = getattr(obj, name)
            if isinstance(fn,(types.FunctionType,types.MethodType)) or callable(fn):
                try: return fn(*args, **kw)
                except Exception: return None
        return None
    def _has_path(self, obj: Any, dotted: str) -> bool:
        try: self._get_path(obj, dotted); return True
        except Exception: return False
    def _get_path(self, obj: Any, dotted: str) -> Any:
        cur = obj
        for p in dotted.split("."): cur = getattr(cur, p)
        return cur
    def _to_str(self, x: Any) -> str:
        if x is None: return ""
        if isinstance(x, str): return x
        # 处理生成器对象
        if hasattr(x, '__iter__') and not isinstance(x, (str, bytes, dict, list)):
            try:
                return ''.join(str(chunk) for chunk in x)
            except Exception:
                pass
        for name in ("text","content","output"):
            if hasattr(x, name):
                v=getattr(x,name)
                if isinstance(v,str): return v
                if hasattr(v, '__iter__') and not isinstance(v, (str, bytes, dict, list)):
                    try:
                        return ''.join(str(chunk) for chunk in v)
                    except Exception:
                        pass
        try: return str(x)
        except Exception: return ""
    def _extract_openai_text(self, resp: Any) -> str:
        try:
            choices = getattr(resp,"choices",None) or resp.get("choices",[])
            if choices:
                msg = getattr(choices[0],"message",None) or choices[0].get("message",{})
                content = getattr(msg,"content",None) or msg.get("content","")
                return content or ""
        except Exception: pass
        return self._to_str(resp)
    def _extract_openai_delta(self, chunk: Any) -> str:
        try:
            choices = getattr(chunk,"choices",None) or chunk.get("choices",[])
            if choices:
                delta = getattr(choices[0],"delta",None) or choices[0].get("delta",{})
                content = getattr(delta,"content",None) or delta.get("content","")
                return content or ""
        except Exception: pass
        return ""
    def _extract_anthropic_text(self, resp: Any) -> str:
        try:
            content = getattr(resp,"content",None) or resp.get("content",[])
            parts=[]
            for block in content or []:
                t = getattr(block,"text",None) or (block.get("text") if isinstance(block,dict) else None)
                if t: parts.append(t)
            return "".join(parts)
        except Exception: pass
        return self._to_str(resp)
    def _extract_anthropic_delta(self, event: Any) -> str:
        try:
            et = getattr(event,"type",None) or (event.get("type") if isinstance(event,dict) else None)
            if et == "content_block_delta":
                delta = getattr(event,"delta",None) or event.get("delta",{})
                if (getattr(delta,"type",None) or delta.get("type")) == "text_delta":
                    return getattr(delta,"text",None) or delta.get("text","") or ""
        except Exception: pass
        return ""
    def _fallback_dummy(self):
        class _Dummy:
            def invoke(self, prompt:str)->str: return "{}"
            def stream(self, prompt:str, on_token:Callable[[str],None])->str:
                on_token("{}"); return "{}"
        return _Dummy()