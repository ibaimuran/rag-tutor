# RAG Tutor — 课程知识私教助手

基于 **DeepSeek** + **RAG** + **BKT（贝叶斯知识追踪）** 的智能一对一私教系统。

## 核心特性

- **主题驱动课程生成**：输入一个主题（如"初中化学"），LLM 自动生成完整课程结构（K12 学科按人教版教材目录生成全部章节和知识点）
- **三模式学习**：阅读（AI 生成教材）| 对话（知识问答，化学课程支持方程式配平）| 测验（10 题逐题作答 + BKT 综合评估）
- **知识问答对话**：无需选择知识点即可自由提问，AI 基于 RAG 检索的教材内容准确回答，支持清空聊天记录
- **化学方程式配平**：化学类课程自动检测配平请求，LLM 逐步展示配平过程，LaTeX 格式输出 + KaTeX 渲染化学式
- **数据完全持久化**：SQLite WAL 模式，聊天历史、测验记录、学习进度全部实时保存，刷新页面或重启服务后自动恢复
- **跨课程会话复用**：切换课程自动复用已有 session（localStorage + 服务端双重保障），再次进入课程历史记录不丢失
- **BKT 知识追踪**：贝叶斯知识追踪模型在测验中量化每个知识点的掌握概率，区分"真掌握"与"蒙对"，答题一致性分析
- **可视化路线图**：可点击的学习路线图，深色玻璃态 UI，知识点掌握状态一目了然

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

**本地运行（推荐）**

```powershell
pip install -r requirements.txt
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Docker 部署**

```bash
docker-compose up -d --build
```

### 3. 打开浏览器

访问 `http://localhost:8000`

> 首次启动自动建库 + 创建默认用户，无需手动初始化。数据存储在 `backend/data/tutor.db`。

## 使用流程

1. 打开首页，左侧显示已有课程（可删除，级联清理数据库 + ChromaDB + 教材文件），右侧输入想学的主题
2. 点击「开始学习」，LLM 8 路并发生成课程结构 + 知识点 MD 教材，大课程约 2-3 分钟
3. 自动跳转到学习主页面，左侧显示学习路线图
4. 点击知识点切换内容，模式标签切换阅读 / 对话 / 测验
5. 对话模式下自由提问，聊天记录实时保存，点「清空记录」可清除当前课程聊天
6. 测验模式逐题作答，完成自动评估，再次进入显示历史结果
7. 切换课程自动复用已有 session，返回首页再进入记录不丢失

### 三种学习模式

| 模式 | 功能 | BKT 追踪 |
|------|------|----------|
| **阅读** | 查看 AI 生成的 MD 教材内容，包含核心概念、关键定义、示例、误区、思考题 | — |
| **对话** | 知识问答模式，无需选知识点即可自由提问；化学课程支持配平方程式，KaTeX 渲染化学式 | — |
| **测验** | 10 道选择题逐题作答即时反馈，完成综合 BKT 评估，刷新自动恢复 | 10 题完成后综合评估 |

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
| GET | `/api/v1/sessions/active` | 查询活跃会话（优先返回有聊天记录的） |
| POST | `/api/v1/sessions/{id}/chat` | 知识问答对话 |
| GET | `/api/v1/sessions/{id}/chat/history` | 对话历史 |
| DELETE | `/api/v1/sessions/{id}/chat/history` | 清空对话历史 |
| POST | `/api/v1/sessions/{id}/quiz/start` | 启动测验 |
| POST | `/api/v1/sessions/{id}/quiz/{qid}/answer` | 提交测验答案 |
| GET | `/api/v1/sessions/{id}/quiz/{qid}/result` | 测验结果 |
| GET | `/api/v1/sessions/{id}/quiz/current` | 查询当前测验（含已完成的） |
| GET | `/api/v1/sessions/{id}/roadmap` | 学习路线图 |
| GET | `/api/v1/sessions/knowledge-points/{id}/content/html` | 知识点教材 |
| POST | `/api/v1/admin/generate-course-from-topic` | 从主题生成课程 |
| GET | `/api/v1/admin/courses` | 课程列表 |
| DELETE | `/api/v1/admin/courses/{id}` | 删除课程（级联清理所有关联数据） |

启动后访问 `http://localhost:8000/docs` 查看 Swagger 文档。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI (async) |
| 数据库 | SQLite WAL 模式 + SQLAlchemy 2.0 |
| 向量库 | ChromaDB（持久化） |
| 嵌入模型 | BAAI/bge-large-zh-v1.5（本地 CPU） |
| LLM | DeepSeek (OpenAI SDK) |
| 前端 | Vanilla HTML/CSS/JS + Jinja2 + KaTeX |
| 部署 | 本地 Uvicorn / Docker |

## 项目结构

```
rag-tutor/
├── .env                    # API Key 配置
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 入口，shutdown 时 WAL checkpoint
│   │   ├── config.py        # 全局配置
│   │   ├── models/          # ORM 模型（SQLite WAL + FK 约束）
│   │   ├── bkt/             # BKT 贝叶斯引擎（更新器 + EM 估计器）
│   │   ├── llm/             # DeepSeek 客户端 + Prompt 模板
│   │   ├── core/            # 核心引擎（qa_agent / course_generator / mastery_gate）
│   │   ├── testing/         # 章节测试（出题 / 评分 / 自适应）
│   │   ├── rag/             # RAG 管线（向量嵌入 / ChromaDB 检索）
│   │   ├── api/routes/      # API 路由（chat / quiz / sessions / admin 等）
│   │   └── schemas/         # Pydantic 请求/响应模型
│   └── data/                # SQLite + ChromaDB + materials/（自动生成）
├── frontend/
│   ├── landing.html         # 首页
│   ├── templates/
│   │   └── base.html        # 学习主页面
│   └── static/
│       ├── css/             # 样式文件
│       └── js/              # 前端逻辑（app / chat / quiz / api 等）
└── scripts/
    └── init_db.py
```
