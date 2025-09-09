from __future__ import annotations
import asyncio
from typing import Any, Dict, Callable
from utils.prompt_utils import render_prompt, call_json_with_stream_legacy
from services.event_types import StreamEvent, StreamEventType

async def run_report_writer(state: Dict[str, Any], emit: Callable[[StreamEvent], Any], llm_client) -> Dict[str, Any]:
    payload = {
        "meta": {"user_display_name": state.get("profile", {}).get("nickname") or state.get("profile", {}).get("name") or "朋友",
                 "session_id": state.get("session_id", "S-unknown"),
                 "report_date": state.get("report_date", "")},
        "profile": state.get("profile", {}),
        "dim_scores": state.get("dim_scores", {}),
        "severity": state.get("severity", {}),
        "overall_score": state.get("overall_score"),
        "overall_severity": state.get("overall_severity"),
        "interventions": state.get("interventions", []),
        "guidance": {"tone": "温和、可操作"},
        "thresholds": {"severe": 2.5, "moderate": 3.5},
    }
    prompt = render_prompt("report_writer", payload)
    await emit(StreamEvent(type=StreamEventType.node_start, payload={"stage": "ReportWriter"}))

    def _on_tok(tok: str):
        asyncio.create_task(emit(StreamEvent(type=StreamEventType.token, payload={"text": tok}, node="ReportWriter")))

    data = call_json_with_stream_legacy(llm_client, prompt, on_token=_on_tok)
    state["report"] = data

    await emit(StreamEvent(type=StreamEventType.summary, payload={"report_header": data.get("header", {})}))
    await emit(StreamEvent(type=StreamEventType.node_end, payload={"stage": "ReportWriter"}))
    return state