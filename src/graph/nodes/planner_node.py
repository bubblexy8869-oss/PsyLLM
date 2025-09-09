"""
Module: 访谈规划节点（根据意图与题库生成 plan）
"""
import logging
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig
from src.graph.types import TaskExecutionState
from src.graph.common import add_execution_result, handle_node_error
from src.services.question_bank import load_question_bank, select_plan_for_intents

logger = logging.getLogger(__name__)

# 题库默认路径（你也可以放到 config 里）
DEFAULT_BANK_PATHS = [
    "data/questions_mqol_v1.csv",
]

async def planner_node(state: TaskExecutionState, config: RunnableConfig) -> TaskExecutionState:
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    logger.info(f"[{thread_id}] Planner start")

    try:
        # 1) 加载题库（找到第一个存在的文件）
        bank_path = None
        for p in DEFAULT_BANK_PATHS:
            try:
                from pathlib import Path
                if Path(p).exists():
                    bank_path = p
                    break
            except Exception:
                pass

        if bank_path is None:
            logger.warning("题库文件未找到，使用内置最小 demo")
        bank = load_question_bank(bank_path or "NOT_EXIST")

        # 2) 读取意图与次要候选（来自前序节点）
        primary_intent = state.get("primary_intent")
        intents = state.get("intents", [])

        # 最多每个主维度抽多少题（可从 config 传入）
        per_dim = int(config.get("configurable", {}).get("planner_per_dim", 10))

        # 3) 选题
        plan = select_plan_for_intents(
            bank=bank,
            primary_intent=primary_intent,
            intents=intents,
            per_dim=per_dim
        )

        # 4) 写回状态
        state["plan"] = plan
        state["q_index"] = 0
        state["plan_finished"] = False  # 初始化为False，避免条件边错误判断

        # 5) 记录
        add_execution_result(state, "planner", "completed", {
            "bank_path": bank_path or "internal_demo",
            "selected_count": len(plan),
            "primary_intent": primary_intent,
            "per_dim": per_dim,
            "dims_in_plan": sorted({p["dimension"] for p in plan}),
        })

        return state
    except Exception as e:
        return handle_node_error(state, "planner", e)