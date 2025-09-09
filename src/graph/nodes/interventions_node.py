"""
Module: 干预卡节点（根据维度与严重性挑选干预卡）
"""
import logging
from langchain_core.runnables import RunnableConfig
from src.graph.types import TaskExecutionState
from src.graph.common import add_execution_result, handle_node_error
from src.services.intervention import select_interventions

logger = logging.getLogger(__name__)

def _map_dim_key(name: str) -> str:
    mapping = {
        "沟通": "communication", "信任": "trust", "亲密/性生活": "intimacy",
        "子女教育": "parenting", "冲突处理": "conflict", "价值观/角色分工": "values_roles"
    }
    return mapping.get(name, name)

async def interventions_node(state: TaskExecutionState, config: RunnableConfig) -> TaskExecutionState:
    try:
        dim_scores = state.get("dim_scores", {})
        severity = state.get("severity", {})
        cards_out = []
        for dim in dim_scores.keys():
            sev = severity.get(dim, "中度")
            cards = select_interventions(
                dimension=_map_dim_key(dim),
                severity=sev,
                yaml_path="data/plans/plans_minimal_v1.yaml",
                top_k=2
            )
            cards_out.append({"dimension": dim, "cards": cards})
        state["interventions"] = cards_out
        add_execution_result(state, "interventions", "completed", {"count": len(cards_out)})
        return state
    except Exception as e:
        return handle_node_error(state, "interventions", e)