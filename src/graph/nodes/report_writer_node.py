"""
Module: 报告生成节点（调用 report_writer prompt 输出结构化 JSON）
"""
import asyncio
import logging
from langchain_core.runnables import RunnableConfig
from src.graph.types import TaskExecutionState
from src.graph.common import add_execution_result, handle_node_error
from src.llms.adapter import LegacyLLMAdapter
from src.agents.report_writer_agent import run_report_writer
from src.services.event_types import StreamEvent, StreamEventType

logger = logging.getLogger(__name__)

async def report_writer_node(state: TaskExecutionState, config: RunnableConfig) -> TaskExecutionState:
    try:
        llm = LegacyLLMAdapter()

        async def _emit(event: StreamEvent):
            # 如需把 token/state 转发给 SSE，可在此对接；这里仅记录
            pass

        state["report_date"] = state.get("report_date")
        new_state = await run_report_writer(state, _emit, llm)

        add_execution_result(new_state, "report_writer", "completed", {
            "has_report": bool(new_state.get("report")),
            "overall_severity": new_state.get("overall_severity"),
        })
        return new_state
    except Exception as e:
        return handle_node_error(state, "report_writer", e)