# Proposal: eval-harness-loop（方向 A）

## Why

大厂 AI 应用岗 JD / 面试分水岭是「效果凭什么信」：离线 case → 跑通 →
指标 → 人审决策。仓库已有 harness（dev/gold、`gate.sh`、REST
`/v1/harness/*`、人工 `adopt|observe|reject`），但仍偏「能跑通接线」，
缺少**固定指标契约**与**覆盖验证脊柱关键断言**的 case 深度。

本变更把评测从「脚手架」推成可回归的效果闭环——服务日用质量，也服务
面试可讲述性。不自动改 prompt（人仍是 judge）。

## What changes

1. **指标契约**：在 `summary` / case `metrics` 中固定 3–5 个可解析字段
   （见 design），`gate.sh` / CLI / REST 同一套语义。
2. **Case 加深（不烧 LLM）**：在 `dev`（及必要的 `gold` 确定性段）补齐：
   gate 一致性、check_routing 开考/回讲、stub 不乱写、失败写回钩子断言
   （与方向 B 协作：B 实现行为，A 用 harness case 锁住）。
3. **人审决策可追溯**：`adopt|observe|reject` 写入可查询；文档说明
   「不自动 register prompt」仍是铁律。
4. **文档**：`docs/SYSTEM.md` 补「评测闭环」短段；本夹验收清单。

## Out

- Harness 学习者 UI / Settings tab
- 自动 adopt → 改 prompt/skill
- 工业 LLM-as-judge 平台、LangSmith 级 tracing 大盘
- 重写 LangGraph / 换编排框架
- 向量 RAG 评测套件

## Success

- `./scripts/gate.sh` 仍绿；新增 case 不依赖真实 `LLM_API_KEY`
- 指标名字稳定，有单测或 harness case 钉死
- 人审决策路径有测；SYSTEM 写明评测如何服务 Verified=done

## Impact

- 主改：`src/gotit/harness/`、`db/ops/harness.py`、`api/routes/harness.py`、
  `scripts/run_harness.py`、相关 `tests/`
- 次要：`docs/SYSTEM.md`；可选 MCP 只读列出 run（非必须）
- **不改** Web UX（产品主路径文案由作者自管）

## Agent handoff

见同目录 `AGENT.md`。与 `failure-writeback-regress`（方向 B）并行：
A 拥有 harness/指标；B 拥有 digest→注入行为；交界 case 约定见 design §协作。
