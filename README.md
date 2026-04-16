# Brand Consultant — AI 品牌战略顾问平台

> 基于多 Agent 协作的品牌战略全案生成系统，参考 Manus 交互范式，支持流式输出、多格式材料下载与 PPT 专业级演示文稿生成。

![Platform Preview](https://img.shields.io/badge/Platform-Web-blue?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.11-green?style=flat-square&logo=python)
![Vue](https://img.shields.io/badge/Vue-3.4-brightgreen?style=flat-square&logo=vue.js)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-teal?style=flat-square&logo=fastapi)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

---

## 功能概览

### 三大 AI 专家 Agent

| Agent | 职责 | 输出内容 |
|-------|------|---------|
| 🎯 **战略规划专家** | 市场分析、品牌定位、竞争策略 | 品牌战略规划报告（MD / PDF） |
| 🎨 **品牌设计专家** | Logo概念、色彩体系、视觉规范 | 品牌设计手册（MD / PDF / PNG）|
| 🚀 **运营实施专家** | 渠道策略、内容营销、执行计划 | 运营实施方案（MD / PDF） |

- **单 Agent 模式**：精准解决单一专业问题
- **多 Agent 协作**：三专家按 战略 → 品牌 → 运营 顺序流水线协作，后序专家自动获取前序输出作为上下文

### 支持的大模型

| 供应商 | 模型示例 |
|--------|---------|
| **OpenAI** | GPT-4o, GPT-4-turbo, GPT-3.5-turbo |
| **Anthropic** | Claude Opus 4.6, Claude Sonnet 4.6 |
| **火山引擎** | Doubao-pro-32k, Doubao-lite-32k |

> 所有模型 API Key 均在管理后台配置，可为每个 Agent 单独指定模型。

### 核心特性

- **实时流式输出**：SSE 技术实现逐字生成，类 Manus 交互体验
- **多格式材料**：MD 文档、PDF 报告、PNG 品牌视觉稿
- **积分体系**：注册赠 100 积分，下载材料消耗积分（MD 5分 / PDF 10分 / PNG 15分）
- **知识库增强**：管理员可为每个 Agent 输入行业案例和方法论，提升输出质量
- **权限分级**：管理员后台 + 普通用户前台，完全隔离

---

## 技术架构

```
┌─────────────────────────────────────────────────────┐
│                     用户浏览器                        │
│         Vue 3 + Element Plus + Pinia                 │
│    登录/注册 | 任务创建 | 实时流式展示 | 文件下载      │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────┐
│                   Nginx 反向代理                      │
│          静态文件服务 + API 代理 + SSE 支持            │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              FastAPI 后端 (Python 3.11)               │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  Auth 模块   │  │  Task 模块   │  │ Admin 模块  │  │
│  │ JWT + bcrypt│  │ SSE流式输出  │  │ 模型/知识库 │  │
│  └─────────────┘  └──────┬───────┘  └────────────┘  │
│                          │                           │
│  ┌───────────────────────▼─────────────────────────┐ │
│  │              Agent 编排服务                       │ │
│  │  strategy → brand → operations (流水线协作)       │ │
│  └───────────────────────┬─────────────────────────┘ │
│                          │                           │
│  ┌───────────────────────▼─────────────────────────┐ │
│  │              LLM 服务层                           │ │
│  │    OpenAI SDK | Anthropic SDK | Volcano API      │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  文件生成服务: ReportLab(PDF) + Pillow(PNG)   │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│            SQLite / MySQL (SQLAlchemy ORM)           │
└─────────────────────────────────────────────────────┘
```

---

## 项目结构

```
Blank_WEB/
├── backend/                    # FastAPI 后端
│   ├── main.py                 # 全部路由（30+ API 端点）
│   ├── models.py               # 6 张数据表
│   ├── schemas.py              # Pydantic 数据模型
│   ├── auth.py                 # JWT 认证 + bcrypt 密码
│   ├── database.py             # SQLAlchemy 配置
│   ├── services/
│   │   ├── agent_service.py    # Agent 编排 + SSE 流式输出
│   │   ├── llm_service.py      # 多模型统一接口
│   │   └── file_service.py     # MD / PDF / PNG 文件生成
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── views/
│   │   │   ├── Login.vue       # 登录/注册（合并页面）
│   │   │   ├── Layout.vue      # 用户端布局
│   │   │   ├── Dashboard.vue   # 任务列表
│   │   │   ├── NewTask.vue     # 新建任务 + Agent 选择
│   │   │   ├── TaskDetail.vue  # 实时流式结果 + 文件下载
│   │   │   └── admin/
│   │   │       ├── Layout.vue      # 管理端布局
│   │   │       ├── Dashboard.vue   # 数据概览
│   │   │       ├── LLMConfig.vue   # 大模型配置
│   │   │       ├── Knowledge.vue   # 知识库管理
│   │   │       ├── Users.vue       # 用户管理
│   │   │       └── Tasks.vue       # 任务记录
│   │   ├── api/index.js        # Axios 封装
│   │   ├── store.js            # Pinia 状态管理
│   │   └── router.js           # Vue Router 路由守卫
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
├── nginx/
│   └── nginx.conf              # SSE 反向代理配置
├── docker-compose.yml          # 生产部署编排
├── deploy.sh                   # 一键部署脚本
└── README.md
```

---

## 快速开始

### 方式一：Docker Compose（推荐生产）

**要求**：Docker 20+，Docker Compose 2+

```bash
# 1. 克隆项目
git clone https://github.com/alecchan2015/Brand-Consultant.git
cd Brand-Consultant

# 2. 配置环境变量（可选）
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env

# 3. 一键启动
bash deploy.sh prod

# 访问地址
# 前台：http://localhost:80
# API文档：http://localhost:8000/docs
```

### 方式二：开发模式（CentOS / macOS）

```bash
# 安装依赖（CentOS）
sudo yum install -y python3 python3-pip nodejs npm gcc libjpeg-turbo-devel

# 一键启动开发模式
bash deploy.sh dev

# 前台：http://localhost:3000
# 后端：http://localhost:8000
```

### 方式三：手动启动

**后端：**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # 按需修改
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**前端：**
```bash
cd frontend
npm install
npm run dev
```

---

## 管理后台配置指南

### 第一步：配置大模型

访问 `http://localhost/admin` 登录管理后台后，进入「模型配置」：

| 字段 | 说明 |
|------|------|
| 供应商 | openai / anthropic / volcano |
| 模型名称 | 如 `gpt-4o`、`claude-opus-4-6`、`doubao-pro-32k` |
| API Key | 对应供应商的密钥 |
| Base URL | 火山引擎必填：`https://ark.volcengineapi.com/api/v3` |
| 适用专家 | 可为不同 Agent 配置不同模型，「全部」作兜底 |

**火山引擎（豆包）配置示例：**
```
供应商: volcano
模型名称: doubao-pro-32k（填写你的推理接入点 Endpoint ID）
API Key: 你的 ARK API Key
Base URL: https://ark.volcengineapi.com/api/v3
```

### 第二步：添加知识库

进入「知识库管理」，为每个专家添加行业知识：

- **战略规划专家**：市场研究报告、品牌定位方法论、竞品分析框架
- **品牌设计专家**：视觉风格指南、色彩心理学知识、成功品牌案例
- **运营实施专家**：渠道运营经验、营销策略模板、执行案例

### 第三步：用户管理

在「用户管理」中可：
- 查看所有注册用户
- 调整用户积分（充值/扣减）
- 禁用/启用用户账号

---

## 数据库说明

| 表名 | 说明 |
|------|------|
| `users` | 用户账号、角色、积分 |
| `llm_configs` | 大模型 API 配置（Key 加密存储） |
| `agent_knowledge` | Agent 知识库条目 |
| `tasks` | 用户任务（含选用的 Agent 列表） |
| `task_results` | 每个 Agent 的输出内容与生成文件 |
| `credit_transactions` | 积分流水记录 |

默认使用 SQLite，生产环境建议切换 MySQL：

```bash
# .env
DATABASE_URL=mysql+pymysql://user:password@localhost/brand_consultant
```

---

## API 文档

启动后访问 `http://localhost:8000/docs` 查看完整 Swagger 文档。

核心端点：

```
POST   /api/auth/register          # 注册
POST   /api/auth/login             # 登录
GET    /api/auth/me                # 当前用户信息

POST   /api/tasks                  # 创建任务
GET    /api/tasks                  # 任务列表
GET    /api/tasks/{id}/stream      # SSE 流式处理（实时输出）

GET    /api/files/{id}/download    # 下载文件（扣积分）
GET    /api/agents                 # 获取 Agent 元信息

POST   /api/admin/llm-configs      # 添加模型配置
POST   /api/admin/knowledge        # 添加知识条目
GET    /api/admin/users            # 用户列表
PUT    /api/admin/users/{id}/credits  # 调整积分
```

---

## 积分体系

| 操作 | 积分变动 |
|------|---------|
| 新用户注册 | +100 |
| 下载 MD 文档 | -5 |
| 下载 PDF 报告 | -10 |
| 下载 PNG 视觉稿 | -15 |
| 管理员手动调整 | 自定义 |

---

## 默认账号

| 账号 | 密码 | 角色 |
|------|------|------|
| `admin` | `Admin@123` | 管理员 |

> ⚠️ 生产环境请立即修改默认密码，并在 `.env` 中设置强 `SECRET_KEY`。

---

## CentOS 系统字体配置

PDF 和 PNG 中文显示需要系统字体支持：

```bash
# CentOS 7/8
sudo yum install -y wqy-microhei-fonts
# 或
sudo yum install -y google-noto-cjk-fonts

# 验证
fc-list | grep -i wqy
```

---

## License

MIT © 2026 Brand Consultant

---

> 本项目由 [Claude Code](https://claude.ai/code) 辅助开发
