# Design — companion-arch

## Approach

把"验证流水线"翻转为"学习搭子"：对话面 + 持久人格 agent + A2A + 读写记忆是产品主面，verify-loop 降级为搭子在对话里可触发的一个工作流。平台层与模型层分离，纪律（mastery gate）是确定性代码不是 LLM。Python 后端 + React 前端演进。

### 三层分离（借鉴 clowder，形态差异化）

| 层 | 负责 | 不负责 |
|----|------|--------|
| Model | 推理、生成 | 长期记忆、身份、纪律 |
| Agent runtime（pydantic-ai 外裹） | 加载身份、读写记忆、收发 A2A、产出结构化输出 | 路由、gate 判定 |
| Platform（core/messaging + core/loop + db.ops） | 身份、通信、记忆、确定性 gate、编排 | 推理 |

gotit 与 clowder 的关键差异：clowder 的 review 无客观标准（人写代码另一模型审）；gotit 的 review 有——verify-loop 的 rubric 和确定性 mastery gate。这是护城河，重设计必须保住。

### Identity 层

持久人格 = personality prompt + 稳定 rubric + 每 agent 记忆命名空间。**复用现有 `prompt_versions` 表承载 rubric**；新增 `agent_identities` 表承载人格元数据与模型配置。

```
agent_identities
  id            uuid pk
  agent_name    varchar(32) unique indexed   -- axiom | compass | echo | sage | critic(新)
  display_name  varchar(64)
  personality   text
  role          varchar(32)                   -- examiner | curator | teachback | reviewer | critic
  model_config  jsonb
  memory_scope  jsonb
  prompt_version_id uuid fk -> prompt_versions.id
  created_at    timestamptz
  updated_at    timestamptz
```

### Messaging 层

threads / messages / @mention 路由 / ball-custody handoff。取代 API 直接 `await run_axiom()`。

```
threads
  id / user_id / title / kind(chat|verify) / status / timestamps

messages
  id / thread_id / agent_name / role(user|agent|system) / text / mentions / metadata / created_at

ball_custody
  id / thread_id unique / holder / stage(examine|recheck|gate|chat) / context / acquired_at / expires_at
```

- @mention 优先 → 持棒 → 默认搭子。
- verify-loop：棒在 examine→recheck→gate 间传递。
- 自由 chat：handoff 时 `set_ball(stage=chat)`，无 mention 由最近持棒 agent 接。

### Agent runtime

- `AgentContext`：identity + memory reader/writer + message reader。
- agent 返回后由编排层写 message + memory + 状态转移（agent 不直接写 DB）。
- 现有 4 agent rubric 保留；新增 **critic**（recheck 专用）。

### Memory 层（扩展）

- `MemoryWriter` Protocol；kinds：`decision_log` / `lesson` / `evidence` / `trajectory`。
- examine/recheck 结论由编排层写回；同主题再次 examine 时读失败模式；trajectory 驱动 SR。

### Verify-loop（持久 ball-custody）

- 状态在 `ball_custody`；COACH 废弃。
- **mastery gate 是确定性代码**（阈值映射，不调 LLM）。
- recheck 由 **critic** 执行（不同 agent + 不同 rubric）。

```
examine(axiom) --> recheck(critic) --> gate(deterministic)
  gate: passed -> MASTERED ; owe_next -> QUEUED+SR ; almost -> IN_PROGRESS
```

### A2A 接力（原 a2a-handoff）

`run_chat` 产出 `ChatTurn{text, handoff_to, reason}`。一轮内链式接力：

```
route(user_msg) -> agent_A
loop (turn < MAX_A2A_TURNS=4):
    turn_out = run_chat(...)
    persist agent_message(..., metadata.handoff_to=...)
    if no handoff / self / unknown: break
    set_ball(holder=target, stage=chat); inject handoff reason into next context
return {user_message, agent_messages: [...]}
```

- bypass：`MessagePost.handoff_to` + `run_chat(force_handoff)`（无 LLM 可测接力链）。
- 共享编排：`api/chat_orchestrator.py`（REST ↔ MCP）。

### 对话面 API + 前端导航（含原 companion-nav）

| REST | MCP | 说明 |
|------|-----|------|
| `POST/GET /v1/threads` | `gotit_create_thread` / `gotit_list_threads` | thread |
| `GET/POST .../messages` | `gotit_list_messages` / `gotit_post_message` | 消息 + A2A |
| `POST .../verify` | `gotit_start_verify` | verify-loop |
| identities / skills | 对应 MCP | seed / 列表 |

前端布局（chat-first 两栏）：

```
[资料库 drawer，默认关] | navRail | conversation
```

- `Shell` 只挂 `ChatPage`；`Sidebar` 为资料抽屉。
- navRail：品牌、资料开关、工作流 tab、thread 列表。
- 有 thread 自动打开最近一条；空态主 CTA「开新对话」。
- 考我/回讲/深挖：右栏内嵌专页（ModeHeader ← 搭子）。

## REST ↔ MCP parity

chat / workflow / skills 与 MCP 共享 `core` + `db.ops`；`gotit_post_message` 同步接力与 `agent_messages`。

## Postgres impact

Alembic `0005_companion_arch`：`agent_identities` / `threads` / `messages` / `ball_custody`。
`memory_entries` / `prompt_versions` 无 schema 变更。A2A 无新表（复用 metadata + ball）。

## Risks

- 范围大：按 P1–P5 分期；现有 examine/teach/curate 签名兼容。
- gate 确定性：harness `gate-no-llm` 回归。
- A2A 死循环：`MAX_A2A_TURNS` + 自环检测；返回结构 `agent_message` → `agent_messages` 破坏性同步。
