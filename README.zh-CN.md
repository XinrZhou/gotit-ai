# gotit-ai

**Got it? Prove it.**

*没被检验过，就别标「会了」。*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/packaging-uv-DE5FE9)](https://docs.astral.sh/uv/)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![TypeScript](https://img.shields.io/badge/Web-React%20%2B%20Vite-3178C6?logo=react&logoColor=white)](https://react.dev/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[English](README.md) | **中文**

---

## 为什么做 gotit-ai？

多数学习工具帮你**收集**——笔记、高亮、收藏的对话。很少帮你**验证**。

读完一章感觉很熟；两天后被追问，答案塌成「我好像见过……」

这种落差叫**假懂（false fluency）**——看起来会了，却拿不出证据。

> 「我不需要又一个只负责存更多的第二大脑。」
> 「我需要一群日常陪学的搭子——并追问：你是真会了吗？」

**gotit-ai** 是**日常学习搭子**：带人格的 agent 在 thread 里和你聊、跨会话记住薄弱点，到该证明的时候跑验证工作流。只有证据过关才算会——掌握门禁是**确定性代码**，不是 LLM 随口说一声。

## 它能做什么

| 能力 | 含义 |
|------|------|
| **搭子对话** | Thread、@mention、带记忆的人格回复 |
| **A2A 接力** | Agent 可在同一轮把球转给同伴（ball custody） |
| **工作流** | 考我 / 回讲 / 项目深挖——从聊天主面发起 |
| **验证闭环** | 考察 → Critic 复核 → 确定性 gate → 轨迹 / 间隔复习 / 掌握图谱写回 |
| **笔记 → claim** | 导入资料，抽出可检验主张 + 今日计划 |
| **简历深挖** | 项目 / 简历驱动的模拟面试（桑迪） |
| **设置** | 资料 / Skills / MCP / 计划推送 / 动态 — 技能、连接器、计划推送配置、推送观测 |
| **资料库图谱** | 资料库「图谱」→ 全屏掌握力导向图 |
| **OpenClaw via MCP** | 可选分发渠道；与 REST 共用领域操作 |
| **Harness** | Case 快照，提示词/技能改动可测 |

小队（UI 名）：**章鱼哥**（考官）· **海绵宝宝**（整理）· **派大星**（回讲）· **桑迪**（深挖）· **凯伦**（复核）。

## 架构

```
React Web（ChatPage 主面）
        │  REST
        ▼
gotit-ai（Python / uv）
  core/     身份 · 消息 · agents · verify-loop · skills
  db/ops/   领域操作（REST + MCP 共用）
  api/      FastAPI + A2A orchestrator
  mcp/      OpenClaw 工具（薄封装）
  Postgres · Redis
```

**设计原则：** 搭子拥有聊天面。**验证是脊柱**，不是无头流水线。OpenClaw 是可选渠道。

## 技术栈

| 层 | 选型 |
|----|------|
| 运行时 | Python 3.12 · **uv** · FastAPI · MCP |
| 领域核 | `gotit.core` — 无框架依赖 |
| 数据 | Postgres 16 · Redis 7（本地可用 SQLite） |
| Web | React · Vite · **npm**（`web/`） |
| LLM | OpenAI 兼容接口（如智谱 `glm-4-flash`） |
| 工程 | OpenSpec · ADR · `docs/SYSTEM.md` · `scripts/gate.sh` |

## 快速开始

**环境：** Python 3.12+ · [uv](https://docs.astral.sh/uv/) · Node.js 20+ · Docker（或 SQLite）· 大模型 API Key

```bash
git clone https://github.com/<you>/gotit-ai.git
cd gotit-ai

uv sync --all-extras
cp .env.example .env
# 配置 GOTIT_API_KEY、LLM_BASE_URL、LLM_API_KEY、LLM_MODEL

docker compose up -d postgres redis

uv run gotit-api          # http://127.0.0.1:8787/health
cd web && npm install && npm run dev   # :5173
./scripts/gate.sh
```

### OpenClaw MCP（stdio）

```json
{
  "mcp": {
    "servers": {
      "gotit": {
        "command": "uv",
        "args": ["run", "--directory", "/absolute/path/to/gotit-ai", "gotit-mcp"]
      }
    }
  }
}
```

详见 `skills/gotit/SKILL.md`。微信通道：`docs/openclaw-wechat.md`。
早晚计划触达（早=当日计划 / 晚=明日询问；资讯独立可选）：`docs/openclaw-digest.md`、`skills/digest/`。
Apple 提醒事项/备忘录 → gotit 日计划：`docs/openclaw-apple-plan.md`、`skills/apple-plan/`。

## 日常怎么用

1. **聊** — 开 thread，@ 搭子，可选技能  
2. **导入** — 加笔记，抽 claim 进今日计划  
3. **验证** — 从聊天发起考我 / 回讲 / 深挖  
4. **门禁** — 凯伦复核；代码判定过 / 差点 / 欠下次  
5. **记住** — 结果写入轨迹，下次更有针对性  

## 路线图

| 功能 | 状态 |
|------|------|
| 搭子对话 + 身份 + 记忆 | 完成 |
| A2A 接力 + ball custody | 完成 |
| 聊天主面（工作流内嵌） | 完成 |
| 验证闭环 + 确定性 gate + Critic | 完成 |
| 笔记 / claim / 计划 / 简历深挖 | 完成 |
| REST ↔ MCP + harness gate | 完成 |
| OpenClaw 微信早晚计划触达（资讯独立可选） | 完成（P1c） |
| OpenClaw→gotit 写回 + 设置「计划推送」「动态」 | 完成 |
| Apple 计划桥（提醒事项/备忘录 → gotit 日计划） | 完成（P1d） |
| 掌握图谱（失败事件、易混边、全屏「图谱」） | 完成 |
| Agent 真调 MCP 工具 | 下一步 |
| 按 agent 绑不同模型 | 下一步 |
| 工作流回合写入同一 thread | 下一步 |

## 理念

| # | 原则 | 含义 |
|---|------|------|
| P1 | 验证过 = 会了 | 自信不是证据 |
| P2 | 失败有用 | 未过 → 小课 + 再检 + 轨迹 |
| P3 | 形式服从知识点 | 追问、短练、应用、回讲 |
| P4 | Context 预算 | 注入待检主张，不是整本笔记 |
| P5 | Harness 驱动演进 | 提示词/技能改动要有证据 |
| P6 | 人格与 rubric 稳定 | 人格漂移 ≠ 判断漂移 |
| P7 | 门禁是代码 | 绝不让 LLM 当最终裁判 |

## 了解更多

- **[README.md](README.md)** — English  
- **[docs/SYSTEM.md](docs/SYSTEM.md)** — 精简架构快照（新 Agent 先读这个）  
- **[AGENTS.md](AGENTS.md)** — 贡献者 / Agent 操作说明  
- **[docs/VISION.md](docs/VISION.md)** · **[docs/adr/](docs/adr/)**  

## 参与贡献

- 产品焦点：**搭子 + 验证**，不是又一个笔记堆  
- 小步可审 PR；英文 Conventional Commits  
- 非琐碎改动走 OpenSpec；提交前同步 `docs/SYSTEM.md`（对外变化再改 README）  

## License

[MIT](LICENSE)

---

*没被检验过，就别标「会了」。*

**Got it? Prove it.**
