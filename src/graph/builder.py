"""
LangGraph Builder（M-QoL 对话式评估）
Flow:
  Receptionist
    └─(await?)─> END (等待用户补充基础信息)
    └──────────> ProblemExploration
                    ⇅ (need more)
                 IntentRecognition
    └──────────> Planner
                    └> Interviewer
                          └─(await?)─> END (等待用户回答/澄清)
                          └──────────> Scorer
                                         └─(clarify/await?)─> END
                                         └──────────> (ask next | aggregate)
                                └> Aggregator → Interventions → ReportWriter → END
"""
from __future__ import annotations
from typing import Any

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

# Node impls
from src.graph.nodes.receptionist_node import receptionist_node
from src.graph.nodes.problem_exploration_node import problem_exploration_node
from src.graph.nodes.intent_recognition_node import intent_recognition_node
from src.graph.nodes.planner_node import planner_node
from src.graph.nodes.interviewer_node import interviewer_node
from src.graph.nodes.scorer_node import scorer_node
from src.graph.nodes.aggregator_node import aggregator_node
from src.graph.nodes.interventions_node import interventions_node
from src.graph.nodes.report_writer_node import report_writer_node

# State type
from src.graph.types import TaskExecutionState


# ========= 条件边 =========

def _after_receptionist(state: TaskExecutionState) -> str:
    """
    接待后：如果仍需用户输入（缺字段），暂停；否则进入探索
    """
    awaiting = bool(state.get("awaiting_user_reply", False))
    profile_complete = float(state.get("profile_completeness", 0.0))
    
    print(f"[DEBUG] _after_receptionist: awaiting_user_reply={awaiting}, profile_completeness={profile_complete}")
    
    # 如果信息收集完成且不等待用户输入，进入探索阶段
    if not awaiting and profile_complete >= 0.7:
        return "explore"
    
    # 否则等待用户输入
    return "wait"


def _need_more_exploration(state: TaskExecutionState) -> str:
    """
    意图识别：置信度不足 → 回探索（限回合数）；否则进入 Planner
    """
    need_more = bool(state.get("need_more_exploration", False))
    rounds = int(state.get("exploration_round", 0))
    max_rounds = int(state.get("max_intent_rounds", 2))  # 减少最大回合数
    
    print(f"[DEBUG] _need_more_exploration: need_more={need_more}, rounds={rounds}, max_rounds={max_rounds}")
    
    if need_more and rounds < max_rounds:
        return "explore_more"
    
    return "plan"


def _interviewer_or_wait(state: TaskExecutionState) -> str:
    """
    访谈后：若在等待用户作答（或澄清），暂停；否则直接进 Scorer
    """
    return "wait" if bool(state.get("awaiting_user_reply")) else "score"


def _scorer_next_step(state: TaskExecutionState) -> str:
    """
    打分后：
      - 若仍需澄清/等待用户输入：暂停
      - 若 plan 完成：进入聚合
      - 否则回 Interviewer 问下一题
    """
    awaiting = bool(state.get("awaiting_user_reply", False))
    plan_finished = bool(state.get("plan_finished", False))
    
    print(f"[DEBUG] _scorer_next_step: awaiting_user_reply={awaiting}, plan_finished={plan_finished}")
    
    if awaiting:
        return "wait"
    if plan_finished:
        return "aggregate"
    
    return "ask_next"


# ========= Builder =========

def build_assessment_graph():
    """
    编译完整工作流为可执行 Graph。
    - 入口：Receptionist
    - 暂停点：Receptionist/Interviewer/Scorer（通过 awaiting_user_reply 控制）
    - 恢复：将用户回复写回 state["last_user_reply"] 后，再次 app.invoke(state, config)
    """
    sg = StateGraph(TaskExecutionState)

    # 注册节点
    sg.add_node("receptionist", receptionist_node)
    sg.add_node("problem_exploration", problem_exploration_node)
    sg.add_node("intent_recognition", intent_recognition_node)
    sg.add_node("planner", planner_node)
    sg.add_node("interviewer", interviewer_node)
    sg.add_node("scorer", scorer_node)
    sg.add_node("aggregator", aggregator_node)
    sg.add_node("interventions", interventions_node)
    sg.add_node("report_writer", report_writer_node)

    # 入口
    sg.set_entry_point("receptionist")

    # Receptionist -> (等待 or 探索)
    sg.add_conditional_edges(
        "receptionist",
        _after_receptionist,
        {
            "wait": END,                    # 等待用户补充基础信息
            "explore": "problem_exploration",
        },
    )

    # 探索 -> 意图识别
    sg.add_edge("problem_exploration", "intent_recognition")

    # 意图识别 -> (继续探索 or 规划)
    sg.add_conditional_edges(
        "intent_recognition",
        _need_more_exploration,
        {
            "explore_more": "problem_exploration",
            "plan": "planner",
        },
    )

    # 规划 -> 访谈施测
    sg.add_edge("planner", "interviewer")

    # 访谈 -> (等待 or 打分)
    sg.add_conditional_edges(
        "interviewer",
        _interviewer_or_wait,
        {
            "wait": END,         # 等待本题用户作答
            "score": "scorer",
        },
    )

    # 打分 -> (等待澄清 or 下一题 or 聚合)
    sg.add_conditional_edges(
        "scorer",
        _scorer_next_step,
        {
            "wait": END,               # 等待澄清或 1–5 明确分数
            "ask_next": "interviewer", # 回到访谈问下一题
            "aggregate": "aggregator",
        },
    )

    # 聚合 -> 干预 -> 报告 -> 结束
    sg.add_edge("aggregator", "interventions")
    sg.add_edge("interventions", "report_writer")
    sg.add_edge("report_writer", END)

    return sg.compile()

# Studio 需要一个“已编译 graph 对象”的模块级变量：
assessment_graph = build_assessment_graph()
# ========= 使用提示 =========
#
# app = build_assessment_graph()
# state = {
#   "user_id": "U-xxx",
#   "session_id": "S-xxx",
#   "max_intent_rounds": 4,        # 可选：探索↔意图回合上限（默认 4）
# }
# config = {"configurable": {"thread_id": state["session_id"], "planner_per_dim": 10}}
#
# 1) 首次调用（进入接待）
# state = app.invoke(state, config=config)
#
# 若返回后 state["awaiting_user_reply"] = True，表示需要用户输入。
# 前端拿到问题/提示后，收集用户回复并写回：
# state["last_user_reply"] = "用户刚才的自然语言回答"
#
# 2) 继续推进（再次调用 app.invoke）
# state = app.invoke(state, config=config)
#
# 注：在访谈/打分阶段也会频繁出现暂停（END），直到全部题目完成并生成报告。