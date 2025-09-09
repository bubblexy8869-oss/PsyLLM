# PsyLLM - M-QoL Assessment API

基于 LangGraph 的心理学质量生活评估(Mental Quality of Life Assessment)对话式评估系统。

## 🚀 快速开始

### 环境要求
- Python 3.11+
- PostgreSQL
- OpenAI API Key

### 安装依赖
```bash
# 使用 pip 安装
pip install -e .

# 或使用项目配置安装
pip install -r requirements.txt  # 如果有的话
```

### 环境配置
1. 复制 `.env.example` 到 `.env`（如果存在）
2. 配置必要的环境变量：
```bash
# 基础配置
DEBUG=true
ENV=dev

# LangSmith 追踪配置
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_PROJECT=MQoL-Dev

# 数据库配置 (请根据实际情况配置)
DATABASE_URL=postgresql://user:password@localhost/psyllm

# OpenAI 配置
OPENAI_API_KEY=your_openai_api_key
```

### 启动服务
```bash
# 启动 FastAPI 应用
uvicorn main:app --reload --port 8000

# 启动 LangGraph 开发服务
langgraph dev
```

访问 [http://localhost:8000/docs](http://localhost:8000/docs) 查看 API 文档。

## 📋 功能特性

### 核心功能
- **对话式心理评估**: 基于 LangGraph 的智能对话流程
- **多角色协作**: 接待员、问题探索、意图识别、规划师、面试官、评分员等
- **实时流式响应**: 基于 SSE 的实时数据流
- **评估报告生成**: 自动生成详细的心理评估报告
- **干预建议**: 基于评估结果提供个性化建议

### 技术特性
- **RESTful API**: 标准的 REST API 接口
- **异步处理**: 基于 FastAPI 的高性能异步处理
- **链路追踪**: 集成 LangSmith 进行完整的调用链追踪
- **模块化设计**: 清晰的代码结构和模块划分
- **类型安全**: 完整的 Python 类型注解

## 🏗️ 系统架构

### 评估工作流
```
用户输入 → 接待员(Receptionist)
    ↓
问题探索(ProblemExploration) ⇄ 意图识别(IntentRecognition)
    ↓
规划师(Planner) → 面试官(Interviewer)
    ↓
评分员(Scorer) → 聚合器(Aggregator)
    ↓
干预建议(Interventions) → 报告生成(ReportWriter)
```

### 目录结构
```
src/
├── agents/          # AI 代理实现
├── config/          # 配置管理
├── db/              # 数据库模型和操作
├── graph/           # LangGraph 工作流定义
├── llms/            # LLM 模型接口
├── prompts/         # 提示词模板
├── services/        # 业务服务层
├── telemetry/       # 监控和遥测
└── utils/           # 工具函数
```

## 📖 API 文档

### 健康检查
```bash
GET /healthz
```

### 评估接口
```bash
POST /api/v1/assessment
Content-Type: application/json

{
  "thread_id": "session_001",
  "user_id": "user_123",
  "payload": {
    "initial_input": "用户初始输入"
  }
}
```

### 交互式对话
```bash
POST /api/v1/chat
Content-Type: application/json

{
  "thread_id": "session_001",
  "message": "用户消息",
  "context": {}
}
```

## 🛠️ 开发指南

### 添加新的评估流程
1. 在 `src/agents/` 创建新的代理类
2. 在 `src/prompts/` 添加相应的提示词模板
3. 在 `src/graph/` 定义工作流图
4. 在 `langgraph.json` 注册新的图形

### 自定义 LLM 模型
1. 在 `src/llms/` 实现新的模型接口
2. 在配置中指定模型参数
3. 更新相关的代理配置

### 数据库迁移
```bash
# 创建迁移文件
alembic revision --autogenerate -m "description"

# 执行迁移
alembic upgrade head
```

## 🔧 配置说明

### LangGraph 配置 (langgraph.json)
```json
{
  "dependencies": [".", "fastapi>=0.110", ...],
  "graphs": {
    "assessment": "src.graph.builder:assessment_graph",
    "interactive_chat": "src.graph.interactive_builder:interactive_graph"
  },
  "env": ".env",
  "python_version": "3.11"
}
```

### 环境变量说明
- `DEBUG`: 调试模式开关
- `ENV`: 环境标识 (dev/staging/prod)
- `LANGCHAIN_*`: LangSmith 相关配置
- `DATABASE_URL`: 数据库连接字符串
- `OPENAI_API_KEY`: OpenAI API 密钥

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行指定测试
pytest tests/test_specific.py

# 测试覆盖率
pytest --cov=src tests/
```

## 📊 监控和调试

### LangSmith 追踪
- 在 LangSmith 控制台查看完整的调用链
- 分析性能瓶颈和错误信息
- 项目名称: `MQoL-Dev`

### 日志配置
- 开发环境: DEBUG 级别
- 生产环境: INFO 级别
- 日志格式: 标准的 Python logging

## 🤝 贡献指南

1. Fork 本项目
2. 创建特性分支: `git checkout -b feature/new-feature`
3. 提交更改: `git commit -am 'Add new feature'`
4. 推送分支: `git push origin feature/new-feature`
5. 创建 Pull Request

### 代码规范
- 遵循 PEP 8 代码风格
- 使用类型注解
- 编写单元测试
- 更新相关文档

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🆘 支持

如果遇到问题或需要帮助：
1. 查看 [Issues](../../issues) 中的已知问题
2. 创建新的 Issue 描述问题
3. 联系项目维护者

## 🗺️ 发展路线图

- [ ] 添加更多评估量表支持
- [ ] 实现多语言支持
- [ ] 增强报告可视化
- [ ] 添加用户管理系统
- [ ] 实现评估数据分析面板

---

**注意**: 本系统涉及心理健康评估，请确保在使用过程中遵循相关的伦理准则和隐私保护规范。