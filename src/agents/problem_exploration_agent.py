from __future__ import annotations
import asyncio
from typing import Any, Dict, Callable
from utils.prompt_utils import render_prompt, call_json_with_stream_legacy
from services.event_types import StreamEvent, StreamEventType

async def run_problem_exploration(
    state: Dict[str, Any],
    emit: Callable[[StreamEvent], Any],
    llm_client,
    version: str = "v2",
) -> Dict[str, Any]:
    """
    职责：
      - 以咨询师式语气鼓励用户阐述问题、补充情境
      - 从自然语言中提炼结构化“探索笔记”（new_notes）
      - 可流式 token；最终返回 JSON（含 empathic_reply / probe_questions / new_notes 等）
    约定：
      - 使用 prompts/problem_exploration_v2.md（或 v1），输出 JSON
    输入：
      - state.profile / state.exploration_notes（历史）
    输出（写回 state）：
      - state.exploration_round += 1
      - 追加 state.exploration_notes
    """
    state["exploration_round"] = int(state.get("exploration_round", 0)) + 1
    tpl = "problem_exploration_v2" if version == "v2" else "problem_exploration"

    prompt = render_prompt(tpl, {
        "profile": state.get("profile", {}),
        "exploration_notes": state.get("exploration_notes", []),
    })

    async def _emit_token(tok: str):
        await emit(StreamEvent(type=StreamEventType.token, payload={"text": tok}, node="ProblemExploration"))

    # 逐 token 回调（供打字机体验），结束后解析为 JSON
    data = call_json_with_stream_legacy(llm_client, prompt, on_token=lambda t: asyncio.create_task(_emit_token(t)))

    # 结构化结果容错
    new_notes = data.get("new_notes") or []
    if isinstance(new_notes, list):
        state.setdefault("exploration_notes", []).extend([n for n in new_notes if isinstance(n, str)])

    # 回显一个 summary（前端可用于调试或可视化）
    await emit(StreamEvent(type=StreamEventType.summary, payload={
        "exploration": {
            "round": state["exploration_round"],
            "added_notes": len(new_notes) if isinstance(new_notes, list) else 0,
            "empathic_reply": data.get("empathic_reply"),
            "probe_questions": data.get("probe_questions"),
        }
    }))
    await emit(StreamEvent(type=StreamEventType.node_end, payload={"stage": "ProblemExploration"}))
    return state