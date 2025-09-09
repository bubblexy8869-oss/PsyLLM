"""
图节点模块（M-QoL 婚姻质量评估）
只导出本项目用到的 LangGraph 节点，避免循环导入与无关依赖。
"""

# 0) 接待/画像 & 问题探索/意图识别
from src.graph.nodes.receptionist_node import receptionist_node
from src.graph.nodes.problem_exploration_node import problem_exploration_node
from src.graph.nodes.intent_recognition_node import intent_recognition_node

# 1) 量表施测主流程
from src.graph.nodes.planner_node import planner_node          # 读取题库、生成本轮题目计划
from src.graph.nodes.interviewer_node import interviewer_node  # 对话式逐题提问/澄清
from src.graph.nodes.scorer_node import scorer_node            # 自然语言→Likert评分（含置信度、反向题）

# 2) 聚合/干预/报告
from src.graph.nodes.aggregator_node import aggregator_node          # 维度聚合、权重加权、严重性分级
from src.graph.nodes.interventions_node import interventions_node    # RAG 检索+干预卡编排
from src.graph.nodes.report_writer_node import report_writer_node    # 结构化报告生成

# 3) 结束反馈（可选）
#  from .user_feedback_node import user_feedback_node

__all__ = [
    "receptionist_node",
    "problem_exploration_node",
    "intent_recognition_node",
    "planner_node",
    "interviewer_node",
    "scorer_node",
    "aggregator_node",
    "interventions_node",
    "report_writer_node",
    # "user_feedback_node",
]