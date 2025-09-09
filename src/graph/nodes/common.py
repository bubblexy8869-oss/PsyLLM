"""
Common utilities and base classes for graph nodes.
提供所有节点常用的工具函数，避免重复实现。
"""

from typing import Any, Dict, List, Tuple


# ========== 执行日志 & 错误处理 ==========
def add_execution_result(
    state: Dict[str, Any],
    node_name: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
) -> Dict[str, Any]:
    """
    将节点执行的输入/输出追加到 execution_log。
    """
    rec = {
        "node": node_name,
        "inputs": inputs,
        "outputs": outputs,
    }
    if "execution_log" not in state:
        state["execution_log"] = []
    state["execution_log"].append(rec)
    return state


def handle_node_error(state: Dict[str, Any], node_name: str, error: Exception) -> Dict[str, Any]:
    """
    在节点出错时，记录错误并更新 state。
    """
    rec = {
        "node": node_name,
        "error": str(error),
    }
    if "execution_log" not in state:
        state["execution_log"] = []
    state["execution_log"].append(rec)
    state["last_error"] = str(error)
    return state


# ========== 消息/上下文处理 ==========
def get_latest_human_message(state: Dict[str, Any]) -> str:
    """
    从 state['messages'] 中获取用户最近的一条消息。
    如果没有消息则返回空字符串。
    """
    msgs = state.get("messages", [])
    for m in reversed(msgs):
        if m.get("role") == "user":
            return m.get("content", "")
    return ""


class NodeContext:
    """
    节点运行的上下文信息（会话 ID、用户 ID 等）。
    """
    def __init__(self, session_id: str, user_id: str | None = None):
        self.session_id = session_id
        self.user_id = user_id

    def to_dict(self) -> Dict[str, Any]:
        return {"session_id": self.session_id, "user_id": self.user_id}


# ========== 输出归一化 ==========
def normalize_output(output: Any) -> str:
    """
    将 LLM 输出或函数输出转成 string，保证后续节点能统一处理。
    """
    if output is None:
        return ""
    if isinstance(output, dict) and "output" in output:
        return str(output["output"])
    if isinstance(output, (list, tuple)):
        return " ".join(map(str, output))
    return str(output)


# ========== Prompt/消息处理 ==========
def format_message(system_prompt: str, user_prompt: str) -> List[Dict[str, str]]:
    """
    构造 OpenAI/Qwen 兼容的 messages 格式。
    """
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


# ========== Likert 分数解析 ==========
def parse_score(text: str) -> Tuple[int, float]:
    """
    从 LLM 返回的文本里解析 Likert 分数和置信度。
    占位实现：你可以后续写更复杂的正则/JSON 解析。
    """
    score, conf = 3, 0.5
    try:
        if "1" in text:
            score = 1
        elif "5" in text:
            score = 5
    except Exception:
        pass
    return score, conf


# ========== 意图解析 ==========
def parse_intent(text: str) -> str:
    """
    从 LLM 返回的文本里解析意图标签。
    占位实现：后续你可以改成正则/JSON 解析。
    """
    return text.strip().lower()