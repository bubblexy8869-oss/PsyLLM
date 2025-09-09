"""
主工作流 PostgreSQL 状态追踪模块
使用基类简化代码
"""

import logging
from src.persistence.base_tracker import BaseWorkflowTracker
from src.graph.nodes import (
    intent_understanding_node,
    command_execution_node,
    workflow_execution_node,
    knowledge_qa_node,
    task_decomposition_node,
    complex_task_execution_node,
    monitoring_node,
    aggregation_node
)
from src.graph.nodes.intent_feedback_node import intent_feedback_node

logger = logging.getLogger(__name__)


class MainWorkflowTracker(BaseWorkflowTracker):
    """主工作流追踪器"""
    
    def __init__(self):
        super().__init__("main_workflow")
    
    def _get_node_specific_fields(self, input_state: dict, output_state: dict, node_name: str) -> dict:
        """获取主工作流节点特定字段，保留完整业务数据但只筛选当前节点的execution_results"""
        # 复制完整的输入状态
        filtered_input_state = input_state.copy()
        
        # 复制完整的输出状态
        filtered_output_state = output_state.copy()
        
        # 只筛选当前节点的execution_results
        input_execution_results = input_state.get("execution_results", [])
        filtered_input_state["execution_results"] = [
            result for result in input_execution_results 
            if result.get("node") == node_name
        ]
        
        output_execution_results = output_state.get("execution_results", [])
        filtered_output_state["execution_results"] = [
            result for result in output_execution_results 
            if result.get("node") == node_name
        ]
        
        return {
            "input_state": filtered_input_state,
            "output_state": filtered_output_state
        }
    


async def create_tracked_nodes():
    """创建所有带追踪的主工作流节点"""
    tracker = MainWorkflowTracker()
    
    return {
        "intent_understanding": tracker.create_tracked_node(intent_understanding_node, "intent_understanding"),
        "intent_feedback": tracker.create_tracked_node(intent_feedback_node, "intent_feedback"),
        "command_execution": tracker.create_tracked_node(command_execution_node, "command_execution"),
        "workflow_execution": tracker.create_tracked_node(workflow_execution_node, "workflow_execution"),
        "knowledge_qa": tracker.create_tracked_node(knowledge_qa_node, "knowledge_qa"),
        "task_decomposition": tracker.create_tracked_node(task_decomposition_node, "task_decomposition"),
        "complex_task_execution": tracker.create_tracked_node(complex_task_execution_node, "complex_task_execution"),
        "monitoring": tracker.create_tracked_node(monitoring_node, "monitoring"),
        "aggregation": tracker.create_tracked_node(aggregation_node, "aggregation")
    }