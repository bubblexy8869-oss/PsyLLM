"""
Module: 打分节点（根据用户自然语言答案推断 Likert 1-5）
- 读取：
    - state["plan"][q_index]
    - state["last_user_reply"]
- 写入：
    - state["answers"] / state["item_scores"] / state["last_score"]
    - 澄清分支：state["clarify"] / awaiting_user_reply / 对话回显
    - 前进分支：q_index += 1 / awaiting_user_reply=False / plan_finished
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
from src.agents.scorer_agent import run_scorer
from src.services.event_types import StreamEvent, StreamEventType

logger = logging.getLogger(__name__)


async def scorer_node(state: TaskExecutionState, config: RunnableConfig) -> TaskExecutionState:
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    q_index = int(state.get("q_index", 0))
    plan = state.get("plan", [])
    total = len(plan)

    logger.info(f"[{thread_id}] Scorer start (q_index={q_index}, total={total})")

    # 基础校验
    if not plan or q_index >= total:
        add_execution_result(state, "scorer", "skipped", {
            "reason": "no_plan_or_finished",
            "q_index": q_index,
            "total": total,
        })
        return state

    # 必须有用户答案
    user_reply = (state.get("last_user_reply") or "").strip()
    if not user_reply:
        add_execution_result(state, "scorer", "skipped", {
            "reason": "missing_user_reply",
            "q_index": q_index,
        })
        # 没有回答就不前进，继续等待
        state["awaiting_user_reply"] = True
        return state

    try:
        item = plan[q_index]

        # 1) LLM（走你的 llm.py）
        llm = LegacyLLMAdapter()

        # 2) emit：流式 token/中间状态的记录（如需转发 SSE，可在此对接）
        async def _emit(event: StreamEvent):
            if event.type == StreamEventType.token:
                add_execution_result(state, "scorer_event", "token", {"text": event.payload.get("text", "")})
            elif event.type in (StreamEventType.state, StreamEventType.score, StreamEventType.summary):
                add_execution_result(state, "scorer_event", event.type.value, event.payload)
            else:
                add_execution_result(state, "scorer_event", "event", {
                    "type": event.type.value, "payload": event.payload
                })

        # 3) 业务主体（自然语言推断优先，低置信度触发澄清）
        new_state = await run_scorer(state, _emit, llm)

        # 4) 读取 scorer 写入的 last_score（我们在 agents/scorer_agent.py 已写入）
        last_score = new_state.get("last_score") or {}
        score = last_score.get("score")
        needs_clarify = bool(last_score.get("needs_clarify", False))
        confidence = float(last_score.get("confidence", 0.0))

        # 5) 分支：需要澄清 —— 保持 q_index，不前进；置等待输入
        if needs_clarify:
            # 生成澄清话术（若 agent 已在 interviewer 里出具 anchors/clarify 提示，也可复用）
            anchors = last_score.get("anchors")
            # 默认澄清问法（可结合 interviewer prompt 的模板更自然）
            clarify_prompt = "为了准确记录，刚才的意思更接近 1（完全不符合）到 5（完全符合）的哪一分呢？"
            if isinstance(anchors, dict):
                # 如果有两个锚点提示，可加到话术中
                lo = anchors.get("low_anchor"); hi = anchors.get("high_anchor")
                if lo or hi:
                    clarify_prompt = f"{clarify_prompt}（例如：{lo or '低分示例'} ↔ {hi or '高分示例'}）"

            new_state["clarify"] = {
                "question_id": item.get("question_id"),
                "prompt": clarify_prompt,
                "confidence": confidence,
            }
            new_state["awaiting_user_reply"] = True  # 继续等用户给出 1-5 的明确选择/更清晰回答

            # 对话回显一条澄清问句
            add_ai_message(new_state, "assistant", clarify_prompt)

            add_execution_result(new_state, "scorer", "clarify_required", {
                "q_index": q_index,
                "question_id": item.get("question_id"),
                "confidence": confidence,
            })
            return new_state

        # 6) 正常通过 —— 写回可视化消息（可选）
        add_execution_result(new_state, "scorer", "scored", {
            "q_index": q_index,
            "question_id": item.get("question_id"),
            "score": score,
            "confidence": confidence,
        })

        # 7) 前进到下一题
        new_state["awaiting_user_reply"] = False
        new_state.pop("clarify", None)
        new_index = q_index + 1

        if new_index >= total:
            # 已完成所有题
            new_state["q_index"] = new_index
            new_state["plan_finished"] = True
            add_execution_result(new_state, "scorer", "plan_finished", {
                "answered": total,
                "total": total,
            })
            # 也可以回显一句阶段性小结
            add_ai_message(new_state, "assistant", "好的，这一部分的问题已经完成啦，我们来看看整体结果～")
            return new_state

        # 还有后续题目，推进索引
        new_state["q_index"] = new_index
        add_execution_result(new_state, "scorer", "next_question_ready", {
            "next_q_index": new_index,
            "remaining": total - new_index,
        })
        return new_state

    except Exception as e:
        return handle_node_error(state, "scorer", e)