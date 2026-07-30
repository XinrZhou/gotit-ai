# verify-surface — handoff prompts (tasks 2 & 3)

Paste either block into another agent session. Do **not** implement task 1 here
(structured chips — already owned).

---

## Prompt A — Critic independent model (task 2)

```text
你在 gotit-ai 仓库工作。只做 OpenSpec `openspec/changes/verify-surface/` 的 **Task 2：Critic 独立模型绑定**。不要做 Task 1（结构化 UI）和 Task 3（failure 注入）。

## 产品边界
- gotit 是「人是否学会」的学习搭子，不是 KnowMind / 章鱼 Skill 测评台。
- Mastery **gate 必须仍是确定性代码**，LLM 不当最终判官。
- Critic（凯伦）只负责 recheck；换模型是为了降低与 Axiom 同模型自偏好。

## 现状
- Agent 身份在 DB：`agent_identities`，含 `llm_config` jsonb（见 `src/gotit/db/models.py` / `core/models.py` / `db/ops/identity.py`）。
- Examine → Critic recheck 路径在 examine 相关 `core` + `api/routes/examine.py` + `db/ops/claim.py`。
- 聊天用 `get_model()` / `api/deps` 的全局 LLM；SYSTEM.md Not done 写了 “Per-agent multi-model binding”。
- 规范：`gotit.core` 保持 framework-free；REST↔MCP 走同一 `db.ops`。

## 要做
1. 让 Critic recheck 调用可读身份上的模型配置（如 `llm_config.model` / `base_url` / `api_key` env 引用）；未配置时回退全局 `LLM_*`。
2. 只改 Critic 路径，不要一次做完五人多模型大重构（可抽小 helper，供以后复用）。
3. 测试：配置 Critic 不同 model 时，构建/选用的 model 标识与 Axiom 不同；未配置时行为与现在一致。
4. 更新 `openspec/changes/verify-surface/tasks.md` 勾选 Task 2；短更 `docs/SYSTEM.md`（Not done → 已支持 Critic 可选独立模型）。
5. 遵守 `.cursor/rules`（Apple UI 无关可忽略；commits 仅在我要求时再提交）。

## 不要做
- 改 Chat UI / verdict chip
- 做 failure_digest 注入
- 引入企业 RAG / Skill 发布流水线
- 让 LLM 替代 mastery gate

完成后用中文简短说明：改了哪些文件、如何配置 Critic 模型、如何验证。
```

---

## Prompt B — Failure lessons → Axiom (task 3)

```text
你在 gotit-ai 仓库工作。只做 OpenSpec `openspec/changes/verify-surface/` 的 **Task 3：failure_digest → Axiom 考我上下文注入**。不要做 Task 1（结构化 UI）和 Task 2（Critic 多模型）。

## 产品边界
- 对象是**学习者 claim 掌握**，不是业务 Skill 进化。
- 注入要 **budgeted**（token 预算），符合 VISION P4「Context on a budget」。
- 不要做成第二个章鱼「梦境进化 / patch 发布」；只把失败教训喂给考官。

## 现状
- Examine `almost` / `owe_next` 已写 `failure_digest` memory（见 `db/ops/memory.py`、`skills/failure-digest/`、`tests/test_failure_digest.py`）。
- Axiom examine 组装上下文在 `core` examine / agents 路径 + `api/routes/examine.py`。
- 掌握图谱有 `confused_with` 边（`mastery-graph` 已归档）；可优先同 claim / 易混邻居。
- Iron：`gotit.core` framework-free；gate 仍是代码。

## 要做
1. 在 examine 出题/追问组装上下文时，检索相关 `failure_digest`（优先当前 claim_id，其次同 topic / confuse 邻居）。
2. 硬预算：条数 + 字符/token 上限（写进常量并单测）；超限截断，宁缺毋滥。
3. 注入位置：Axiom 可见的 system/user 上下文（简短「你曾在这些点栽过」列表），不要刷屏，不要替代 claim 正文。
4. 无相关记忆时行为与现在完全一致。
5. 测试覆盖：有/无 digest、预算截断、claim 匹配。
6. 勾选 `openspec/changes/verify-surface/tasks.md` Task 3；短更 `docs/SYSTEM.md`。

## 不要做
- Chat verdict UI
- Critic 换模型
- 新 Settings 页或微信推送改版（failure-digest skill 可不动）
- 自动改 Skill / holdout 发布门禁

完成后用中文说明：注入格式示例、预算参数、如何手动验证一次考我。
```
