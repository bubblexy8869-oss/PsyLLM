"""
Graph state types and definitions
LangGraph状态类型定义 - 参考deer-flow设计模式
"""

from datetime import datetime
from typing import Dict, List, Optional, Annotated
from typing_extensions import NotRequired
from langgraph.graph import MessagesState, add_messages
from langchain_core.messages import BaseMessage


class TaskExecutionState(MessagesState):
    """任务执行状态数据模型 - TypedDict格式
    
    参考 deer-flow 设计，使用 MessagesState 和结构化字段管理状态
    遵循LangGraph最佳实践，集中管理图状态定义
    """
    
    # 消息管理（继承自MessagesState）
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 用户输入解析 - 参考 deer-flow
    extracted_topic: NotRequired[Optional[str]]  # 从用户输入提取的主题
    locale: NotRequired[str]  # 语言设置，默认"zh-CN"
    creation_time: NotRequired[Optional[datetime]]
    
    # 用户操作环境
    user_context: NotRequired[Optional[Dict]]
    # {
    #   "selected_target": "TARGET_2004",
    #   "selected_area": "Zone_A", 
    #   "selected_device": "UAV_01",
    #   "map_view": {"zoom": 8, "center": [lat, lng]},
    #   "user_role": "operator"
    # }
    
    # 意图解析结果 - 直接字段定义，不使用字典
    execution_type: NotRequired[str]  # single_command|workflow_template|complex_task|knowledge_qa
    confidence_score: NotRequired[float]  # 置信度评分 0.0-1.0
    matched_command: NotRequired[Optional[str]]
    matched_workflow: NotRequired[Optional[str]]
    extracted_parameters: NotRequired[Dict]  # 提取的参数
    missing_parameters: NotRequired[List[str]]  # 缺失的必需参数
    uncertainty_reason: NotRequired[Optional[str]]  # 置信度低的原因
    intent_understanding_completed: NotRequired[bool]
    
    # 工作流执行信息（适用于所有LangGraph工作流）
    workflow_thread_id: NotRequired[Optional[str]]  # 启动的工作流线程ID
    current_node: NotRequired[Optional[str]]
    
    # 复杂任务执行信息（仅复杂任务使用）
    dynamic_workflow_definition: NotRequired[Optional[Dict]]  # 生成的LangGraph工作流定义
    task_decomposition: NotRequired[Optional[Dict]]  # 任务分解结果
    
    # 执行跟踪信息
    execution_results: NotRequired[List[Dict]]
    
    # 监控与状态
    current_status: NotRequired[str]  # pending|executing|paused|completed|failed
    error_messages: NotRequired[List[str]]
    
    # 人工交互 (仅用于意图识别阶段)
    requires_human_feedback: NotRequired[bool]  # 是否需要人工反馈
    
    # 结果数据
    response_text: NotRequired[str]  # 最终响应文本


def create_task_execution_state(**kwargs) -> TaskExecutionState:
    """创建带默认值的TaskExecutionState实例
    
    工厂函数，遵循LangGraph最佳实践创建状态实例
    直接使用messages字段，符合MessagesState标准
    
    Args:
        messages: 消息历史列表 (推荐使用)
        **kwargs: 其他状态字段
        
    Examples:
        # 新会话
        state = create_task_execution_state(
            messages=[HumanMessage(content="查看状态")],
            user_context={"role": "operator"}
        )
        
        # 继续会话  
        state = create_task_execution_state(
            messages=previous_messages + [HumanMessage(content="新指令")],
            user_context={"role": "operator"}
        )
    """
    defaults = {
        # 用户输入解析字段
        "extracted_topic": None,
        "locale": "zh-CN",  # 默认中文
        "creation_time": None,
        "user_context": None,
        "execution_type": "",
        "confidence_score": 0.0,
        "matched_command": None,
        "matched_workflow": None,
        "extracted_parameters": {},
        "missing_parameters": [],
        "uncertainty_reason": None,
        "intent_understanding_completed": False,
        "workflow_thread_id": None,
        "current_node": None,
        "dynamic_workflow_definition": None,
        "task_decomposition": None,
        "execution_results": [],
        "current_status": "pending",
        "error_messages": [],
        "requires_human_feedback": False,
        "response_text": "",
        "messages": []  # MessagesState 继承字段
    }
    
    # 合并默认值和传入的参数
    result = {**defaults, **kwargs}
    
    # 确保messages是列表
    if "messages" not in result or result["messages"] is None:
        result["messages"] = []
    
    return TaskExecutionState(result)


# 导出所有状态类型 - 遵循deer-flow模式
__all__ = [
    "TaskExecutionState",
    "create_task_execution_state"
]