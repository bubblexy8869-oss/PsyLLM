"""
Module: 问题探索（多轮鼓励用户讲出困扰 -> 生成同理回应与“探索笔记”）
"""
import asyncio
import logging
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

from src.graph.types import TaskExecutionState
from src.graph.common import (
    add_execution_result, handle_node_error, get_latest_human_message, add_ai_message
)
from src.llms.adapter import LegacyLLMAdapter
from src.agents.problem_exploration_agent import run_problem_exploration
from src.services.event_types import StreamEvent, StreamEventType

logger = logging.getLogger(__name__)

async def problem_exploration_node(state: TaskExecutionState, config: RunnableConfig) -> TaskExecutionState:
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    logger.info(f"[{thread_id}] ProblemExploration start (round={state.get('exploration_round', 0)+1})")

    try:
        # 取最近一条用户输入，作为上下文补充（可选）
        latest = get_latest_human_message(state)
        if latest:
            state.setdefault("exploration_notes", []).append(latest)

        llm = LegacyLLMAdapter()

        async def _emit(event: StreamEvent):
            # 这里你可以顺带转发到 SSE；下方先记录到 execution_log
            add_execution_result(
                state,
                "problem_exploration_event",
                event.type.value,
                {"payload": event.payload, "node": event.node or "ProblemExploration"},
            )

        new_state = await run_problem_exploration(state, _emit, llm, version="v2")

        # 在对话里回显一段“同理-引导”的话术（如果 prompt 产出了 empathic_reply）
        # 这段只是用于对话可视化；真正的结构化证据在 exploration_notes 里
        last_summary = new_state.get("exploration_notes", [])[-1:]  # 只取最近一条以免太长
        empathic = "(探索中) 我理解了你的处境，我们可以先聚焦最困扰你的一个情境继续聊聊。"
        add_ai_message(new_state, "assistant", empathic)

        add_execution_result(new_state, "problem_exploration", "completed", {
            "round": new_state.get("exploration_round"),
            "notes_count": len(new_state.get("exploration_notes", [])),
            "latest_note": last_summary[0] if last_summary else None,
        })
        return new_state
    except Exception as e:
        return handle_node_error(state, "problem_exploration", e)