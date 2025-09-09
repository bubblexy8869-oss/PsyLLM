# """
# Graph package - 主工作流图构建模块
# 遵循deer-flow模式和LangGraph最佳实践
# """

# from .builder import build_graph, build_graph_with_postgres
# from .types import TaskExecutionState, create_task_execution_state

# __all__ = [
#     "build_graph",
#     "build_graph_with_postgres",
#     "TaskExecutionState",
#     "create_task_execution_state"
# ]


"""
Graph package - 主工作流图构建模块
遵循 deer-flow 模式和 LangGraph 最佳实践

说明：
- 避免在 __init__.py 中直接导入 builder/types，以防止循环导入问题。
- 如果外部需要用 build_graph / build_graph_with_postgres，请直接：
    from src.graph.builder import build_graph, build_graph_with_postgres
- 如果外部需要类型定义，请直接：
    from src.graph.types import TaskExecutionState, create_task_execution_state
"""