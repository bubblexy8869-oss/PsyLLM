"""
Simple LangGraph Builder for Testing
极简版本，用于调试Studio问题
"""
from __future__ import annotations
from typing import Any

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from src.graph.types import TaskExecutionState
from src.graph.common import add_ai_message


def simple_node(state: TaskExecutionState, config: RunnableConfig) -> TaskExecutionState:
    """极简节点：只发送一条消息然后结束"""
    add_ai_message(state, "assistant", "您好！我是心理评估助手。请问有什么可以帮助您的吗？")
    return state


def build_simple_graph():
    """构建极简graph用于测试"""
    sg = StateGraph(TaskExecutionState)
    
    # 只有一个节点
    sg.add_node("simple", simple_node)
    
    # 设置入口点和出口
    sg.set_entry_point("simple")
    sg.add_edge("simple", END)
    
    return sg.compile()


# 导出给Studio使用
simple_graph = build_simple_graph()