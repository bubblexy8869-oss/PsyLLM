"""
Module: 访谈施测节点（逐题对话式发问 + 等待用户作答）

职责：
- 读取 planner 生成的 plan 和当前 q_index
- 调用 interviewer agent 生成“共情式问法/澄清问法/提示语”
- 向前端“播报”问题（可流式 token），并在 state 标记等待用户作答
- 不在本节点做打分；用户答复写回 state["last_user_reply"] 后，进入 Scorer 节点
"""

import asyncio
import logging
from typing import Any, Dict
from langchain_core.runnables import RunnableConfig

from src.graph.types import TaskExecutionState
from src.graph.common import (
    add_execution_result,
    add_ai_message,
    handle_node_error,
)
from src.llms.adapter import LegacyLLMAdapter
from src.agents.interviewer_agent import run_interviewer
from src.services.event_types import StreamEvent, StreamEventType

logger = logging.getLogger(__name__)


async def interviewer_node(state: TaskExecutionState, config: RunnableConfig) -> TaskExecutionState:
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    q_index = int(state.get("q_index", 0))
    plan = state.get("plan", [])

    logger.info(f"[{thread_id}] Interviewer start (q_index={q_index}, total={len(plan)})")

    # 基础校验
    if not plan or q_index >= len(plan):
        add_execution_result(state, "interviewer", "skipped", {
            "reason": "no_plan_or_finished",
            "q_index": q_index,
            "total": len(plan) if plan else 0,
        })
        return state

    try:
        # 1) LLM（走你的 llm.py）
        llm = LegacyLLMAdapter()

        # 2) 取得当前题目
        item = plan[q_index]  # {dimension, question_id, question_text, weight, reverse_scored}

        # 3) emit：把 token/state 往前端发（供 SSE/WS）
        async def _emit(event: StreamEvent):
            # 这里不直接耦合 SSE；我们把事件记到 execution_log，
            # 若你已有全局事件总线，在此处同时转发即可。
            add_execution_result(
                state,
                "interviewer_event",
                "progress",
                {
                    "event": event.type.value,
                    "node": event.node or "Interviewer",
                    "payload": event.payload,
                },
            )

        # 4) 调用 interviewer agent（内部会以流式 token 回调 _emit(token)）
        new_state = await run_interviewer(state, _emit, llm)

        # 5) 生成展示层输出（给前端一个“可直接发给用户”的话术）
        #    我们尽量从 agent 返回的 JSON 里取，如果没有，就兜底用题干生成。
        interviewer_json = None
        try:
            # 在 run_interviewer 内，最后会 StreamEvent(summary={"interviewer": data})；
            # 这里我们直接从 new_state 组合展示层内容
            interviewer_json = {
                "question_id": item.get("question_id"),
                "dimension": item.get("dimension"),
                "question_text": item.get("question_text"),
                # 这些字段要看你的 interviewer prompt 输出结构
                # 常见字段（示例）：assistant_utterance / clarify_prompt / empathy_lead / tips
            }
        except Exception:
            interviewer_json = None

        # 6) 写回 state：当前题目上下文 + 等待用户作答
        new_state["current_question"] = {
            "index": q_index,
            "total": len(plan),
            "question_id": item.get("question_id"),
            "dimension": item.get("dimension"),
            "text": item.get("question_text"),
            "reverse_scored": bool(item.get("reverse_scored", False)),
            "weight": float(item.get("weight", 1.0)),
        }
        new_state["awaiting_user_reply"] = True
        # 清空上一轮的澄清标记（如果上一题用过）
        new_state.pop("clarify", None)

        # 7) 记录与消息回显（方便在对话流中显示“咨询师问句”）
        #    如果你 interviewer 的 prompt已经产出了自然语言问句，
        #    可以把那句放到 add_ai_message；否则用题干兜底。
        displayed_question = item.get("question_text")
        add_ai_message(new_state, "assistant", displayed_question)

        add_execution_result(new_state, "interviewer", "completed", {
            "q_index": q_index,
            "question_id": item.get("question_id"),
            "dimension": item.get("dimension"),
        })

        return new_state

    except Exception as e:
        return handle_node_error(state, "interviewer", e)