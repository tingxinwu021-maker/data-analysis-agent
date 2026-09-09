# Data Analysis Agent（数据分析 Agent）

基于 LLM 的数据分析助手：用自然语言查询数据、生成图表、探索分析。
面向**用户行为 / 产品分析**场景（埋点事件、留存、转化漏斗、产品指标）。

## 技术栈

- 后端：Python 3.11 + FastAPI + SQLAlchemy + MySQL
- 模型：DeepSeek（OpenAI 兼容接口，可切换 Qwen / Moonshot 等）
- 数据源：MySQL（关系库）+ 文件（CSV/Excel，经代码解释器 pandas）
- 前端：Next.js + ECharts（聊天界面，已完成）

## 目录结构

```
data-analysis-agent/
├── backend/            # 后端服务
│   └── app/
│       ├── main.py     # FastAPI 入口
│       ├── config.py   # 配置（读 .env）
│       ├── llm/        # LLM 客户端封装
│       ├── db/         # 数据源连接（MySQL）
│       ├── semantic/   # 语义层加载器
│       ├── agent/      # 查询编排（Text-to-SQL + 代码解释器）
│       └── routers/    # API 路由
├── semantic/           # 语义层定义（唯一事实源）
├── frontend/           # 前端（Next.js 聊天界面）
├── data/               # 示例数据（不入库）
├── scripts/            # 生成数据 / 校验 SQL / CLI 问答与分析
├── requirements.txt
└── .env.example
```

## 快速开始

```powershell
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. 配置环境变量（复制示例后填入真实 key）
copy .env.example .env   # 编辑 .env，替换 LLM_API_KEY

# 3. 启动（从项目根目录运行）
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

启动后访问 http://127.0.0.1:8000/health 验证。

# 启动前端（另开终端；自动代理 /api 到后端）
cd frontend
npm install   # 首次
npm run dev   # http://localhost:3000

# 命令行直接问数据（无需启动服务）
.venv\Scripts\python.exe scripts\ask.py "每个国家的活跃用户数是多少？"

# 命令行分析文件（代码解释器）
.venv\Scripts\python.exe scripts\analyze.py data/raw/users.csv "每个套餐分别有多少用户？"

# golden-SQL 回归评测（改模型/提示词后跑，防退化）
.venv\Scripts\python.exe scripts\eval.py

# 或调用接口：
#   POST http://127.0.0.1:8000/chat    body: {"question": "..."}
#   POST http://127.0.0.1:8000/upload  (multipart 文件) -> 返回 file_id
#   POST http://127.0.0.1:8000/analyze body: {"file_id": "...", "question": "..."}

## 当前进度

- [x] Phase 0 — 项目骨架与接入
- [x] Phase 1 — 语义层建模
- [x] Phase 2 — 查数 MVP（Text-to-SQL）
- [x] Phase 3 — 分析引擎（代码解释器）
- [x] 前端聊天界面（Next.js + ECharts，含仪表盘/多轮对话/流式输出）
- [x] Phase 4 — 可维护性（golden-SQL 评测 / 反馈闭环 / 追踪审计）
- [ ] Phase 5 — 生产化（多用户权限/限流/部署）
