# 数据分析 Agent — 开发流程 / 产品文档

> 本文档是项目「连续性」的权威来源。新开窗口/新会话时：先读 `CLAUDE.md`（概览），再读本文档（详情 + 下一步）。
> 最后更新：2026-09-03

---

## 1. 产品定位

- **是什么**：用自然语言查询、分析数据的 Agent。
- **场景**：用户行为 / 产品分析（埋点事件、留存、转化漏斗、产品指标）。
- **目标**：真实可用、可维护，不是 demo。
- **最终形态**：对话式 Chat + 仪表盘；数据源 = 数据库（MySQL）+ 文件（CSV/Excel）。

## 2. 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 后端 | Python 3.11 + FastAPI | |
| Agent 编排 | 手写轻量编排（`sql_agent.py`） | 链路简单，暂未引入 LangGraph，需要时再引入 |
| 模型 | DeepSeek（OpenAI 兼容接口） | 封装在 `backend/app/llm/client.py`，可切 Qwen/Moonshot |
| 数据源 | MySQL（关系库，SQLAlchemy）+ 文件（CSV/Excel，代码解释器 pandas） | |
| 语义层 | `semantic/semantic.yaml`（YAML） | 唯一事实源 |
| 前端 | Next.js + ECharts | 聊天界面 + 仪表盘 + 流式/多轮（`frontend/`），代理 `/api` 到后端 |
| 代码沙箱 | 本地 subprocess（`sandbox.py`，超时+隔离+静态拦截） | 生产可升级 Docker/E2B |
| 可观测/评测 | 本地 JSONL 追踪 + golden-SQL 评测 + 反馈 JSON | Langfuse 可选 |

## 3. 系统架构

```
用户 ── 前端 (Next.js 聊天界面)
          │  /api/* 代理到后端
     FastAPI 后端 (main.py + routers/)
          │
     agent/sql_agent.py  —— 编排：生成SQL → 校验 → 执行 → 解释
          │
   ┌──────┴──────────────────────────────┐
   │  semantic/semantic.yaml（唯一事实源）  │
   │  表/字段/指标/同义词/精选示例           │
   └──────┬──────────────────────────────┘
          │
   ┌──────┴───────────────┐
   │ 引擎A Text-to-SQL      │  引擎B 代码解释器
   │ MySQL（SQLAlchemy）执行  │  Python/pandas + 沙箱
   └──────────────────────┘
```

**两条引擎分工**：
- 引擎 A（Text-to-SQL）：确定性、可审计，业务日常取数。已实现。
- 引擎 B（代码解释器）：灵活，探索式分析，跑在本地 subprocess 沙箱。已实现。

## 4. 当前状态（已完成）

| 阶段 | 内容 | 状态 |
|---|---|---|
| Phase 0 | 骨架、venv、依赖、配置、`/health`、git init | ✅ |
| Phase 1 | 示例数据 + 语义层 + 加载器 + 校验脚本（5/5 通过） | ✅ |
| Phase 2 | Text-to-SQL 全链路 + `/chat` + CLI 问答 | ✅ |
| Phase 3 | 代码解释器 + `/upload` + `/analyze`（subprocess 沙箱） | ✅ |

- **数据**：5000 用户 / 20.3 万事件 / 3.6 万会话，由 `scripts/generate_sample_data.py` 生成并灌入 MySQL `analytics_demo` 库（确定性可复现）。
- **git**：按阶段提交（Phase 0-1 / Phase 2 / 文档 / Phase 3）。
- **实测通过**：国家活跃用户数、套餐用户数、日活最高日、7 日留存率；代码解释器「按套餐统计用户」结果与 SQL 一致。

## 5. 下一步（路线图）

剩余工作（顺序待用户选择）：

**A. 前端聊天界面 —— 已完成**
- [x] Next.js 聊天页，调用 `POST /chat` 与 `/upload` + `/analyze`
- [x] 结果渲染：表格 + 图表（ECharts，简单启发式选型）
- [x] 仪表盘：保存/删除图表（JSON 存储，`/dashboards`）
- [x] 多轮对话（会话历史）、流式输出（SSE `/chat/stream`）

**C. Phase 4 可维护性 —— 已完成**
- [x] golden-SQL 回归评测（`scripts/eval.py` + `eval/cases.yaml`）
- [x] 用户反馈闭环（👍/👎 → `data/feedback.json`，人工评审后回流到语义层）
- [x] 追踪/审计（本地 JSONL，`GET /traces`；替代 Langfuse，无需外网）
- [ ] 权限 / 限流（多用户场景，归入 Phase 5）

**D. Phase 5 生产化**：部署、成本控制、监控（暂缓）

## 6. 开发流程与规范

1. 每个阶段：**设计 → 实现 → 端到端验证 → git 提交**。
2. 提交信息：`feat: Phase N ...` / `fix: ...`。
3. 代码注释用中文；命令从项目根目录运行。
4. 改动语义层后，必须跑 `scripts/validate_examples.py` 回归。
5. 改配置（`.env`）要同步更新 `.env.example`。

## 7. 本地开发命令（项目根目录）

```powershell
# 生成示例数据
.venv\Scripts\python.exe scripts\generate_sample_data.py

# 校验语义层示例 SQL
.venv\Scripts\python.exe scripts\validate_examples.py

# golden-SQL 回归评测（改模型/提示词/语义层后跑，防退化）
.venv\Scripts\python.exe scripts\eval.py

# 从 MySQL 读取表结构，自动更新 semantic.yaml 的 models 段
.venv\Scripts\python.exe scripts\export_mysql_schema.py

# 启动服务
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload

# 命令行直接问数据
.venv\Scripts\python.exe scripts\ask.py "每个国家的活跃用户数是多少？"

# 命令行分析文件（代码解释器）
.venv\Scripts\python.exe scripts\analyze.py data/raw/users.csv "每个套餐分别有多少用户？"

# 接口：POST http://127.0.0.1:8000/chat   body: {"question": "..."}
# 上传：POST http://127.0.0.1:8000/upload  (multipart 文件) -> 返回 file_id
# 分析：POST http://127.0.0.1:8000/analyze body: {"file_id": "...", "question": "..."}

# 启动前端（另开终端；自动代理 /api 到后端）
cd frontend; npm install; npm run dev   # http://localhost:3000
```

## 8. 关键决策（为什么这么做）

1. **语义层是命门**：准确率靠「语义层 + 精选示例」，不靠换更聪明的模型。
2. **openai SDK 而非 LiteLLM**：国产模型都是 OpenAI 兼容接口，切供应商只改 `.env`，依赖更少。
3. **MySQL 直连取数**：引擎 A 走 MySQL（SQLAlchemy，`db/connection.py`），示例数据由 `generate_sample_data.py` 灌入 `analytics_demo` 库，确定性可复现。
4. **两条引擎分离**：取数走 SQL（可审计），探索式分析走代码（灵活），不混在一起。

## 9. 已知问题 / 待办

- [ ] 日期列显示成 `2026-07-02 00:00:00`（多了 `00:00:00`），可美化。
- [ ] git 身份是占位符 `86198@localhost`，建议改真实姓名/邮箱。
- [ ] 沙箱为 subprocess 级隔离（非 Docker 级），生产环境建议升级 Docker/E2B。
- [ ] 会话历史/仪表盘/反馈/追踪均为单机内存或 JSON（单用户够用，多用户需换 Redis/DB）。
- [ ] 无多用户权限/限流（单用户本地工具，多用户需加认证与限流）。
- [ ] 建议为 LLM 查询建 MySQL 只读账号（当前 `validate_sql` 关键字黑名单可被绕过）。
- [ ] 换行符 LF→CRLF 警告无害（已加 `.gitattributes` 的 `* text=auto`）。
