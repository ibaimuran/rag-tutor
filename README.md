# RAG Tutor — 课程知识私教助手

基于 **Bloom 2-Sigma 掌握式学习** + **DeepSeek** + **RAG** + **BKT（贝叶斯知识追踪）** 的智能一对一私教系统。

## 核心特性

- **主题驱动课程生成**：输入一个主题（如"初中化学"），LLM 自动生成完整课程结构（K12 学科按人教版教材目录生成全部章节和知识点）
- **三模式学习**：阅读（AI 生成教材）| 对话（苏格拉底式 AI 私教，一问一答引导思考）| 测验（10 题逐题作答 + BKT 综合评估）
- **Bloom 2-Sigma 私教对话**：AI 导师通过苏格拉底式提问循序渐进教学，根据掌握概率动态调整问题难度，从不直接给答案
- **BKT 知识追踪**：贝叶斯知识追踪模型量化每个知识点的掌握概率，区分"真知道"和"蒙对"
- **自适应门控**：掌握度 <60% 强制重学，>=80% 自动晋级下一个知识点
- **可视化路线图**：可点击的学习路线图，深色玻璃态 UI，实时反映学习进度

## 快速开始

### 1. 配置 API Key

在项目根目录创建 `.env` 文件：

```powershell
# Windows PowerShell
echo DEEPSEEK_API_KEY=sk-your-api-key > .env
```

```bash
# Mac / Linux
echo "DEEPSEEK_API_KEY=sk-your-api-key" > .env
```

### 2. 启动服务

**Docker 部署（推荐）**

```powershell
# Windows PowerShell
docker-compose up -d --build
```

```bash
# Mac / Linux
docker-compose up -d --build
```

**本地运行**

```powershell
# Windows PowerShell
pip install -r requirements.txt
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```bash
# Mac / Linux
pip install -r requirements.txt
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. 打开浏览器

访问 `http://localhost:8000`

> 首次启动会自动创建数据库和默认用户，无需手动初始化。

## 使用流程

1. 打开首页，左侧显示已有课程，右侧输入想学的主题（如"初中化学"、"Python编程"、"提示词工程"）
2. 点击「开始学习」，LLM 自动生成课程结构 + 每个知识点的 MD 教材
3. 自动跳转到学习主页面，左侧显示学习路线图

### 三种学习模式

| 模式 | 功能 | BKT 追踪 |
|------|------|----------|
| **阅读** | 查看 AI 生成的 MD 教材内容，包含核心概念、关键定义、示例、误区、思考题 | — |
| **对话** | 苏格拉底式 AI 私教，一问一答循序渐进教学，点击选项即可作答 | 每次答题后实时更新 |
| **测验** | 10 道选择题逐题作答，即时反馈，答完综合 BKT 评估 | 10 题完成后综合评估 |

## BKT（贝叶斯知识追踪）

| 参数 | 含义 | 默认值 |
|------|------|--------|
| P(L₀) | 初始掌握概率 | 0.50 |
| P(T) | 学习转移概率 | 0.20 |
| P(G) | 猜对概率 | 0.15 |
| P(S) | 失误概率 | 0.10 |

掌握阈值：**>=80% 通过（自动晋级）**，**<60% 强制重学**

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 首页 |
| GET | `/app` | 学习主页面 |
| POST | `/api/v1/sessions` | 创建学习会话 |
| POST | `/api/v1/sessions/{id}/chat` | 对话模式消息 |
| GET | `/api/v1/sessions/{id}/chat/history` | 对话历史 |
| POST | `/api/v1/sessions/{id}/quiz/start` | 启动测验 |
| POST | `/api/v1/sessions/{id}/quiz/{qid}/answer` | 提交测验答案 |
| GET | `/api/v1/sessions/{id}/quiz/{qid}/result` | 测验结果 |
| GET | `/api/v1/sessions/{id}/roadmap` | 学习路线图 |
| GET | `/api/v1/sessions/knowledge-points/{id}/content/html` | 知识点教材 |
| POST | `/api/v1/admin/generate-course-from-topic` | 从主题生成课程 |
| GET | `/api/v1/admin/courses` | 课程列表 |
| DELETE | `/api/v1/admin/courses/{id}` | 删除课程 |

启动后访问 `http://localhost:8000/docs` 查看 Swagger 文档。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI (async) |
| 数据库 | SQLite + SQLAlchemy 2.0 |
| 向量库 | ChromaDB |
| 嵌入模型 | BAAI/bge-large-zh-v1.5 |
| LLM | DeepSeek (OpenAI SDK) |
| 前端 | Vanilla HTML/CSS/JS + Jinja2 |
| 部署 | Docker + docker-compose |

## 项目结构

```
rag-tutor/
├── .env                    # API Key 配置（放在项目根目录）
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
├── DESIGN.md
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 入口，启动自动建库
│   │   ├── config.py        # 全局配置（读取 ../.env）
│   │   ├── models/          # ORM 模型
│   │   ├── bkt/             # BKT 贝叶斯引擎
│   │   ├── llm/             # DeepSeek 客户端 + Prompt 模板
│   │   ├── core/            # 教学引擎（对话/课程生成/掌握度门控）
│   │   ├── testing/         # 测验模块（出题/评分/自适应）
│   │   ├── rag/             # RAG 管线（向量嵌入/检索）
│   │   ├── api/routes/      # API 路由
│   │   └── schemas/         # Pydantic 请求/响应模型
│   └── data/                # SQLite + ChromaDB（自动生成）
├── frontend/
│   ├── landing.html         # 首页
│   ├── templates/
│   │   └── base.html        # 学习主页面
│   └── static/
│       ├── css/             # 样式文件
│       └── js/              # 前端逻辑
└── scripts/
    └── init_db.py           # 手动初始化脚本（非必须）
```
