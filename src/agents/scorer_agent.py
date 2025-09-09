from __future__ import annotations
import asyncio
from typing import Any, Dict, Callable
from utils.prompt_utils import render_prompt, call_json_with_stream_legacy
from services.event_types import StreamEvent, StreamEventType

async def run_scorer(state: Dict[str, Any], emit: Callable[[StreamEvent], Any], llm_client) -> Dict[str, Any]:
    idx = int(state.get("q_index", 0))
    plan = state.get("plan", [])
    if idx >= len(plan):
        return state
    item = plan[idx]

    prompt = render_prompt("scorer", {
        "question_id": item.get("question_id"),
        "question_text": item.get("question_text"),
        "reverse_scored": item.get("reverse_scored", False),
        "user_reply": state.get("last_user_reply", ""),
        "clarify": state.get("clarify"),
        "confidence_threshold": state.get("confidence_threshold", 0.6),
    })
    await emit(StreamEvent(type=StreamEventType.node_start, payload={"stage": "Scorer", "q_index": idx}))

    def _on_tok(tok: str):
        asyncio.create_task(emit(StreamEvent(type=StreamEventType.token, payload={"text": tok}, node="Scorer")))

    data = call_json_with_stream_legacy(llm_client, prompt, on_token=_on_tok)

    raw_score = float(data.get("score", 3))
    score = 6 - raw_score if item.get("reverse_scored", False) else raw_score
    record = {
        "question_id": item.get("question_id"),
        "dimension": item.get("dimension"),
        "score": score,
        "weight": item.get("weight", 1.0),
        "confidence": float(data.get("confidence", 0.0)),
        "needs_clarify": bool(data.get("needs_clarify", False)),
        "method": data.get("method", "nl_infer"),
    }
    state["last_score"] = record
    state.setdefault("answers", []).append({
        "question_id": item.get("question_id"),
        "text": state.get("last_user_reply", ""),
        "score": score,
        "weight": item.get("weight", 1.0),
        "dimension": item.get("dimension"),
    })
    state.setdefault("item_scores", []).append({
        "question_id": item.get("question_id"),
        "dimension": item.get("dimension"),
        "score": score,
        "weight": item.get("weight", 1.0),
    })

    await emit(StreamEvent(type=StreamEventType.score, payload=record))
    await emit(StreamEvent(type=StreamEventType.node_end, payload={"stage": "Scorer"}))
    return state