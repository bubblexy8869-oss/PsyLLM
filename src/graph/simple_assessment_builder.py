"""
Simple Assessment LangGraph Builder - 防止递归错误
只包含基本流程，确保正常运行
"""
from __future__ import annotations
from typing import Any

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

# Node impls
from src.graph.nodes.receptionist_node import receptionist_node

# State type
from src.graph.types import TaskExecutionState


def _after_receptionist(state: TaskExecutionState) -> str:
    """接待后直接结束，避免循环"""
    return "end"


def build_simple_assessment_graph():
    """构建简化的评估graph，避免递归问题"""
    sg = StateGraph(TaskExecutionState)

    # 只注册接待员节点
    sg.add_node("receptionist", receptionist_node)

    # 入口
    sg.set_entry_point("receptionist")

    # 接待员 -> 直接结束
    sg.add_conditional_edges(
        "receptionist",
        _after_receptionist,
        {
            "end": END,
        },
    )

    return sg.compile()


# Studio 需要一个"已编译 graph 对象"的模块级变量：
simple_assessment_graph = build_simple_assessment_graph()