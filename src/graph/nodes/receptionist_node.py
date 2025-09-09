"""
Module: Receptionist Node（接待/信息采集）
- 调用 receptionist agent 从用户自然语言解析 & 完善 profile
- 若仍有缺失字段：发出下一问，设置 awaiting_user_reply=True（图在此暂停，等待用户回复）
- 若资料齐全：awaiting_user_reply=False，直接进入后续“探索→意图识别”
"""
import logging
from langchain_core.runnables import RunnableConfig

from src.graph.types import TaskExecutionState
from src.graph.common import add_execution_result, handle_node_error, add_ai_message
from src.llms.adapter import LegacyLLMAdapter
from src.agents.receptionist_agent import run_receptionist
from src.services.event_types import StreamEvent, StreamEventType

logger = logging.getLogger(__name__)

async def receptionist_node(state: TaskExecutionState, config: RunnableConfig) -> TaskExecutionState:
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    logger.info(f"[{thread_id}] Receptionist start")

    try:
        # 创建LLM客户端
        llm_client = LegacyLLMAdapter()
        
        # 创建事件发射器
        async def emit(event: StreamEvent):
            # 只记录事件到日志，不直接添加消息到状态
            # 消息添加由 agent 内部处理
            if event.type == StreamEventType.token:
                pass  # 令牌流暂时忽略
            elif event.type == StreamEventType.summary:
                # 记录到执行日志，但不直接添加消息
                add_execution_result(state, "receptionist_event", "summary", {
                    "payload": event.payload,
                    "node": event.node or "Receptionist"
                })

        # 调用原来的receptionist agent逻辑
        updated_state = await run_receptionist(state, emit, llm_client)
        
        # 检查返回类型并处理
        if isinstance(updated_state, dict):
            # 更新状态 - 确保正确复制所有重要字段
            for key, value in updated_state.items():
                state[key] = value
        else:
            logger.warning(f"run_receptionist returned unexpected type: {type(updated_state)}")
        
        # 确保关键状态字段存在并设置正确的初始值
        if "awaiting_user_reply" not in state or state["awaiting_user_reply"] is None:
            # 如果 profile_completeness 低于阈值，等待用户输入
            profile_complete = float(state.get("profile_completeness", 0.0))
            state["awaiting_user_reply"] = bool(profile_complete < 0.8)
        
        if "profile_completeness" not in state or state["profile_completeness"] is None:
            state["profile_completeness"] = 0.0
        
        # 确保布尔值类型正确    
        state["awaiting_user_reply"] = bool(state["awaiting_user_reply"])
        state["profile_completeness"] = float(state["profile_completeness"])
            
        print(f"[DEBUG] receptionist_node end: awaiting_user_reply={state.get('awaiting_user_reply')}, profile_completeness={state.get('profile_completeness')}")
            
        add_execution_result(state, "receptionist", "completed", {
            "profile_completeness": state.get("profile_completeness", 0.0),
            "awaiting_user_reply": state.get("awaiting_user_reply", False),
        })
        
        return state

    except Exception as e:
        logger.error(f"Receptionist node error: {e}")
        # 在错误情况下设置合理的默认值
        state["awaiting_user_reply"] = True
        state["profile_completeness"] = 0.0
        
        # 确保布尔值类型正确
        state["awaiting_user_reply"] = bool(state["awaiting_user_reply"])
        state["profile_completeness"] = float(state["profile_completeness"])
        
        return handle_node_error(state, "receptionist", e)