"""
Interactive LangGraph Builder - 支持对话式交互
修复版本，实现正确的对话流程
"""
from __future__ import annotations
from typing import Any

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from src.graph.types import TaskExecutionState
from src.graph.common import add_ai_message, get_latest_human_message


def interactive_receptionist(state: TaskExecutionState, config: RunnableConfig) -> TaskExecutionState:
    """交互式接待员 - 基于消息历史判断对话阶段"""
    
    # 获取消息历史
    messages = state.get("messages", [])
    
    # 统计AI消息数量来判断对话阶段
    ai_message_count = 0
    for msg in messages:
        if hasattr(msg, 'type') and msg.type == 'ai':
            ai_message_count += 1
        elif isinstance(msg, dict) and msg.get("role") == "assistant":
            ai_message_count += 1
    
    # 根据AI消息数量判断对话阶段
    if ai_message_count == 0:
        # 第一次访问：发送欢迎消息
        state["awaiting_user_reply"] = True
        add_ai_message(state, "assistant", 
            "您好！我是您的心理健康评估助手。请告诉我您的姓名和目前最关心的心理健康问题，我会为您提供专业的帮助。")
        
    elif ai_message_count == 1:
        # 第二轮：询问详细问题
        state["awaiting_user_reply"] = True
        user_message = get_latest_human_message(state)
        
        add_ai_message(state, "assistant", 
            f"感谢您的分享。为了更好地了解您的情况，请详细描述一下您遇到的具体问题，以及这个问题对您的日常生活有什么影响？")
        
    elif ai_message_count == 2:
        # 第三轮：提供建议并结束评估
        state["awaiting_user_reply"] = False
        
        add_ai_message(state, "assistant", 
            "我已经了解了您的基本情况。基于您的描述，我建议您可以通过以下几种方式来改善：\n\n"
            "1. 建立规律的作息时间\n"
            "2. 进行适量的体育锻炼\n"
            "3. 练习深呼吸和冥想\n"
            "4. 必要时寻求专业心理咨询师的帮助\n\n"
            "如果您需要更详细的建议或有其他问题，请随时告诉我。")
        
    else:
        # 后续对话：开放式回复
        state["awaiting_user_reply"] = True
        add_ai_message(state, "assistant", "请告诉我更多信息，我会尽力帮助您。")
    
    return state


def should_continue(state: TaskExecutionState) -> str:
    """判断是否继续对话"""
    return "wait" if state.get("awaiting_user_reply") else "end"


def build_interactive_graph():
    """构建交互式graph"""
    sg = StateGraph(TaskExecutionState)
    
    # 添加对话节点
    sg.add_node("receptionist", interactive_receptionist)
    
    # 设置入口
    sg.set_entry_point("receptionist")
    
    # 添加条件边
    sg.add_conditional_edges(
        "receptionist",
        should_continue,
        {
            "wait": END,  # 等待用户回复
            "end": END,   # 对话结束
        }
    )
    
    return sg.compile()


# 导出给Studio使用
interactive_graph = build_interactive_graph()