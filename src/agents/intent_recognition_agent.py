from __future__ import annotations
import asyncio
from typing import Any, Dict, Callable
from utils.prompt_utils import render_prompt, call_json_with_stream_legacy
from services.event_types import StreamEvent, StreamEventType

INTENT_THRESHOLD = 0.6

async def run_intent_recognition(state: Dict[str, Any], emit: Callable[[StreamEvent], Any], llm_client) -> Dict[str, Any]:
    prompt = render_prompt("intent_recognition", {
        "utterance": " ".join(state.get("exploration_notes", [])[-5:]) if state.get("exploration_notes") else "",
        "context": {"profile": state.get("profile", {})},
    })
    await emit(StreamEvent(type=StreamEventType.node_start, payload={"stage": "IntentRecognition"}))

    def _on_tok(tok: str):
        asyncio.create_task(emit(StreamEvent(type=StreamEventType.token, payload={"text": tok}, node="IntentRecognition")))

    data = call_json_with_stream_legacy(llm_client, prompt, on_token=_on_tok)
    state["intents"] = data.get("intents", [])
    state["primary_intent"] = data.get("primary_intent")
    state["intent_confidence"] = float(data.get("confidence_score", 0.0))

    await emit(StreamEvent(type=StreamEventType.state, payload={
        "intents": state["intents"],
        "primary_intent": state["primary_intent"],
        "confidence": state["intent_confidence"],
    }))
    await emit(StreamEvent(type=StreamEventType.node_end, payload={"stage": "IntentRecognition"}))
    return state