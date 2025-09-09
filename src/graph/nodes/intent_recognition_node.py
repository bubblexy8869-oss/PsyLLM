"""
Module: 意图识别（从探索笔记中识别主意图 + 置信度）
"""
import logging
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig
from src.graph.types import TaskExecutionState
from src.graph.common import add_execution_result, handle_node_error, add_ai_message
from src.llms.adapter import LegacyLLMAdapter
from src.agents.intent_recognition_agent import run_intent_recognition

logger = logging.getLogger(__name__)
INTENT_THRESHOLD = 0.6

async def intent_recognition_node(state: TaskExecutionState, config: RunnableConfig) -> TaskExecutionState:
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    logger.info(f"[{thread_id}] IntentRecognition start")

    try:
        llm = LegacyLLMAdapter()
        
        # 创建异步事件处理器
        async def emit_handler(event):
            if event:
                logger.debug(f"Intent recognition event: {event}")
        
        new_state = await run_intent_recognition(state, emit_handler, llm)
        
        # 记录
        add_execution_result(new_state, "intent_recognition", "completed", {
            "primary_intent": new_state.get("primary_intent"),
            "confidence": new_state.get("intent_confidence"),
            "intents": new_state.get("intents", []),
        })
        add_ai_message(new_state, "assistant",
                       f"(识别) 可能的关注点：{new_state.get('primary_intent')} "
                       f"（置信度 {new_state.get('intent_confidence')}）")

        # 是否需要回到探索（这个"回跳"在 graph 边里实现）
        intent_confidence = float(new_state.get("intent_confidence", 0.0))
        new_state["need_more_exploration"] = bool(intent_confidence < INTENT_THRESHOLD)
        
        # 确保布尔值类型正确
        new_state["need_more_exploration"] = bool(new_state["need_more_exploration"])
        
        print(f"[DEBUG] intent_recognition end: need_more_exploration={new_state.get('need_more_exploration')}, confidence={new_state.get('intent_confidence')}")
        
        return new_state
    except Exception as e:
        logger.error(f"Intent recognition error: {e}")
        # 设置默认值避免条件边错误
        state["need_more_exploration"] = False
        state["primary_intent"] = "unknown"
        state["intent_confidence"] = 1.0
        
        # 确保布尔值类型正确
        state["need_more_exploration"] = bool(state["need_more_exploration"])
        
        return handle_node_error(state, "intent_recognition", e)