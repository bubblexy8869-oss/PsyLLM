"""
Module: 聚合节点（按维度聚合得分，计算严重性）
"""
import logging
from langchain_core.runnables import RunnableConfig
from src.graph.types import TaskExecutionState
from src.graph.common import add_execution_result, handle_node_error
from src.services.aggregator import aggregate_scores

logger = logging.getLogger(__name__)

async def aggregator_node(state: TaskExecutionState, config: RunnableConfig) -> TaskExecutionState:
    try:
        res = aggregate_scores(state.get("item_scores", []))
        state["dim_scores"] = res.get("dim_scores", {})
        state["overall_score"] = res.get("overall_score")
        state["severity"] = res.get("severity", {})
        state["overall_severity"] = res.get("overall_severity")

        add_execution_result(state, "aggregator", "completed", {
            "dim_scores": state["dim_scores"],
            "overall_score": state["overall_score"],
            "overall_severity": state["overall_severity"],
        })
        return state
    except Exception as e:
        return handle_node_error(state, "aggregator", e)