from __future__ import annotations
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)

def add_execution_result(state: Dict[str, Any], step: str, status: str, payload: Dict[str, Any]):
    state.setdefault("execution_log", []).append({"step": step, "status": status, "payload": payload})

def add_ai_message(state: Dict[str, Any], role: str, content: str):
    """添加消息到状态中，使用LangChain消息对象格式"""
    from langchain_core.messages import HumanMessage, AIMessage
    
    if role in ("user", "human"):
        message = HumanMessage(content=content)
    else:
        message = AIMessage(content=content)
    
    state.setdefault("messages", []).append(message)

def get_latest_human_message(state: Dict[str, Any]) -> str:
    for msg in reversed(state.get("messages", [])):
        # Handle both dict and LangChain message objects
        if hasattr(msg, 'type') and msg.type == 'human':
            return msg.content
        elif hasattr(msg, 'get') and msg.get("role") in ("user", "human"):
            return msg.get("content", "")
        elif isinstance(msg, dict) and msg.get("role") in ("user", "human"):
            return msg.get("content", "")
        # 处理LangGraph Studio中的消息格式
        elif isinstance(msg, dict) and msg.get("type") == "human":
            return msg.get("content", "")
    return ""

def handle_node_error(state: Dict[str, Any], node_name: str, err: Exception) -> Dict[str, Any]:
    logger.exception("Node %s error: %s", node_name, err)
    add_execution_result(state, node_name, "error", {"message": str(err)})
    state.setdefault("errors", []).append({"node": node_name, "error": str(err)})
    return state