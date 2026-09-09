# CLAUDE.md — 项目交接文档（每次会话先读这里）

> 详细开发流程、架构、下一步：见 [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)。

## 项目是什么
「数据分析 Agent」：用自然语言查询 / 分析数据。面向**用户行为 / 产品分析**场景（埋点事件、留存、转化漏斗、产品指标）。
目标：真实可用、可维护，不是 demo。

## 技术栈
- 后端：Python 3.11 + FastAPI + SQLAlchemy + MySQL
- 模型：DeepSeek（OpenAI 兼容接口，封装在 `backend/app/llm/client.py`，可切换 Qwen 等）
- 数据源：MySQL（关系库）+ 文件（CSV/Excel，经代码解释器 pandas）
- 前端：Next.js + ECharts（聊天界面已实现，`frontend/`，代理 `/api` 到后端）

## 关键架构决策（为什么这么做）
1. **语义层是命门**：`semantic/semantic.yaml` 是「唯一事实源」，LLM 只能通过它理解数据。
   提升准确率的重点是语义层 + 精选示例，而不是换更聪明的模型。
2. **两条执行引擎**：引擎 A = Text-to-SQL（确定性、可审计，业务取数）；引擎 B = 代码解释器（灵活，探索式分析，跑在 subprocess 沙箱）。A、B 均已实现。
3. **用 openai SDK 而非 LiteLLM**：DeepSeek/Qwen/Moonshot 都是 OpenAI 兼容接口，切供应商只改 `.env`，依赖更少更好维护。
4. **MySQL 直连取数**：引擎 A 走 MySQL（SQLAlchemy，`db/connection.py`）；示例数据由 `scripts/generate_sample_data.py` 灌入 `analytics_demo` 库，确定性可复现。

## 目录结构
- `backend/app/` —— 后端（`main.py` 入口、`config.py` 配置、`llm/` 客户端、`db/` 连接、`semantic/` 加载器、`routers/` 路由、`agent/` 查询编排）
- `semantic/semantic.yaml` —— 语义层（表/字段/指标/精选示例）
- `scripts/` —— 生成数据、校验示例 SQL、CLI 问答
- `data/` —— 生成的数据（不入库）

## 当前进度
- [x] Phase 0 — 骨架（`/health` 可用）
- [x] Phase 1 — 语义层 + 示例数据（示例 SQL 校验 5/5 通过）
- [x] Phase 2 — Text-to-SQL 核心链路（生成/校验/执行/解释 + `/chat` + CLI）
- [x] Phase 3 — 代码解释器（上传 + pandas 沙箱分析 + `/upload` + `/analyze`）
- [x] 前端聊天界面（Next.js + ECharts，含仪表盘/多轮对话/流式输出，代理 `/api`）
- [x] Phase 4 — 可维护性（golden-SQL 评测 / 反馈闭环 / 追踪审计）
- [ ] Phase 5 — 生产化（多用户权限/限流/部署）

## 常用命令（都在项目根目录运行）
- 生成数据：`.venv\Scripts\python.exe scripts\generate_sample_data.py`
- 校验示例 SQL：`.venv\Scripts\python.exe scripts\validate_examples.py`
- golden-SQL 回归评测：`.venv\Scripts\python.exe scripts\eval.py`
- 从 MySQL 生成语义层 models：`.venv\Scripts\python.exe scripts\export_mysql_schema.py`
- 启动服务：`.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload`
- 健康检查：http://127.0.0.1:8000/health
- CLI 问答：`.venv\Scripts\python.exe scripts\ask.py "问题"`
- CLI 分析文件：`.venv\Scripts\python.exe scripts\analyze.py <文件> "问题"`
- 启动前端：`cd frontend; npm run dev`（http://localhost:3000，代理 `/api` 到后端）

## 约定
- 代码注释用中文
- 命令从项目根目录运行
- `.env` 含密钥，已 gitignore，不入库；改配置要同时更新 `.env.example`
