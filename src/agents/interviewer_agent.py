from __future__ import annotations
import asyncio
from typing import Any, Dict, Callable
from src.utils.prompt_utils import render_prompt, call_json_with_stream_legacy
from src.services.event_types import StreamEvent, StreamEventType

async def run_interviewer(state: Dict[str, Any], emit: Callable[[StreamEvent], Any], llm_client) -> Dict[str, Any]:
    idx = int(state.get("q_index", 0))
    plan = state.get("plan", [])
    if idx >= len(plan):
        await emit(StreamEvent(type=StreamEventType.summary, payload={"message": "no more questions"}))
        return state

    item = plan[idx]
    prompt = render_prompt("interviewer", {
        "dimension_name": item.get("dimension"),
        "question_id": item.get("question_id"),
        "question_text": item.get("question_text"),
        "reverse_scored": item.get("reverse_scored", False),
        "progress": {"current": idx + 1, "total": len(plan)},
        "last_user_reply": state.get("last_user_reply", ""),
        "needs_clarify": bool(state.get("last_score", {}).get("needs_clarify", False)),
        "confidence": state.get("last_score", {}).get("confidence"),
        "anchors": state.get("last_score", {}).get("anchors"),
    })
    await emit(StreamEvent(type=StreamEventType.node_start, payload={"stage": "Interviewer", "q_index": idx}))

    def _on_tok(tok: str):
        asyncio.create_task(emit(StreamEvent(type=StreamEventType.token, payload={"text": tok}, node="Interviewer")))

    data = call_json_with_stream_legacy(llm_client, prompt, on_token=_on_tok)
    await emit(StreamEvent(type=StreamEventType.summary, payload={"interviewer": data}))
    await emit(StreamEvent(type=StreamEventType.node_end, payload={"stage": "Interviewer"}))
    return state