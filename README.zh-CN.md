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

读完一章、一篇文章、一次 Agent Runtime 深挖，感觉很熟，收藏了。两天后被追问一句，答案塌成「我好像见过……」

这种落差有个名字：**假懂（false fluency）**——看起来会了，却拿不出证据。

> 「我不需要又一个只负责存更多的第二大脑。」
> 「我需要一支小队追问：你是真会了吗？」

**gotit-ai** 是一个多 Agent 学习检验台。贴上刚学的内容，小队用多种方式检验——追问、短练、应用题、回讲，按知识点选形式。不过 → 针对性补一小块 → 再检。只有证据过关，才算会。

多数助手在总结。gotit-ai 在**压力测试你是否真的 Got it。**

## 它能做什么

| 能力 | 含义 |
|------|------|
| **多 Agent 检验闭环** | Librarian 收束 → Examiner 检验 → Coach 补洞 → Examiner 再检 |
| **多种检验形式** | 追问、短练、应用、回讲——不锁死某一种 |
| **掌握门禁** | 主题默认「还不会」；读过 ≠ 会了 |
| **错题 / 未掌握回归** | 失败点进重测队列，稍后回炉 |
| **Context 预算** | 检验时注入「待检主张」，而不是整本笔记 |
| **OpenClaw via MCP** | 频道入口在 OpenClaw；gotit 暴露检验工具 |
| **小型评测 Harness** | case 快照 + holdout，进步可测 |
| **轨迹与指标** | 轮次、通过与否、延迟、Token |

## 架构

```
OpenClaw（频道 / 会话）
        │  MCP + Skill
        ▼
gotit-ai（Python / uv）
  检验闭环 · FastAPI · MCP · harness
  Postgres · Redis · React Web
```

**设计原则：** 总结很便宜。**验证才是产品。**

## 技术栈

| 层 | 选型 |
|----|------|
| 运行时 | Python 3.12 · **uv** · FastAPI · MCP |
| 数据 | Postgres 16 · Redis 7 |
| Web | React · Vite · **npm**（`web/`） |
| 工程 | OpenSpec · ADR · AGENTS.md · `scripts/gate.sh` |
| 集成 | OpenClaw MCP（`skills/gotit`） |

## 快速开始

**环境：** Python 3.12+ · [uv](https://docs.astral.sh/uv/) · Node.js 20+ · Docker · 至少一家大模型 API Key

```bash
git clone https://github.com/<you>/gotit-ai.git
cd gotit-ai

uv sync --all-extras
cp .env.example .env

docker compose up -d postgres redis
uv run gotit-api          # http://127.0.0.1:8787/health

cd web && npm install && npm run dev
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

详见 `skills/gotit/SKILL.md`。

## 一轮怎么走

1. **导入** — 粘贴笔记、文档片段或学习大纲  
2. **检验** — Examiner 选形式并出检  
3. **门禁** — 过 → 暂标掌握；不过 → Coach 只补缺口  
4. **再检** — Examiner 再跑；仍不过 → 留在未掌握队列  
5. **回归** — 之后抽出未掌握项，再证明一次  

## 路线图

| 功能 | 状态 |
|------|------|
| 仓库脚手架（uv / API / MCP / web / harness 桩） | 完成 |
| OpenSpec + VISION + ADR | 完成 |
| Librarian / Examiner / Coach 闭环 | 进行中 |
| 多种检验形式 | 规划中 |
| 掌握门禁 + 未掌握队列 | 规划中 |
| MCP streamable-http + OpenClaw Skill | 规划中 |
| Web UI | 进行中 |
| 小 Harness（快照 + holdout） | 规划中 |
| 「只总结」vs「先检验」对比 | 规划中 |

## 理念

### 收集 vs 检验

- **收集** = 更多笔记、更多上下文、更多「回头再看」。  
- **检验** = 一条待检主张、一种形式、一次通过/失败、一条重测路径。

gotit-ai 明显偏向 **检验**。

### 三条原则

| # | 原则 | 含义 |
|---|------|------|
| P1 | 验证过 = 会了 | 自信不是证据 |
| P2 | 失败有用 | 未过应收成小课 + 再检 |
| P3 | 形式服从知识点 | 追问、短练、应用、回讲——选能测到的 |

## 了解更多

- **[README.md](README.md)** — English  
- **[AGENTS.md](AGENTS.md)** — Agent / 贡献者操作说明  
- **[docs/VISION.md](docs/VISION.md)** · **[docs/adr/](docs/adr/)**  

## 参与贡献

- 产品焦点保持在 **验证**  
- 改动尽量小、可审；提交信息用英文 Conventional Commits  
- 非琐碎改动走 OpenSpec；行为变化尽量带 harness 证据  

## License

[MIT](LICENSE)

---

*没被检验过，就别标「会了」。*

**Got it? Prove it.**
