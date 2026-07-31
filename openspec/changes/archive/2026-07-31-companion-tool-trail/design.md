# companion-tool-trail — design

## Boundaries

| 动 | 不动 |
|----|------|
| `ToolCallRecord` 可选 `open_examine`；Chat 气泡下 trail + CTA | 门语义、排程、白名单工具集合 |
| 复用 `startExamineClaim` / note → `/v1/examine` | 新建第二套开考引擎 |

## A — metadata 形状

既有：

```text
metadata.tool_calls[] = { name, args_digest, ok, summary }
```

扩展（仅 `start_examine` 且 `ok`）：

```text
tool_calls[].open_examine = {
  action: "open_examine",
  claim_id? | note_id?,
  claim_text? | note_title?,
  claim_ids? (note 路径),
  thread_id?,
  …
}
```

与工具返回给 LLM 的载荷同构（可略去冗长 `hint`）。失败调用不加 `open_examine`。  
`args_digest` 仍截断；CTA **优先读 `open_examine`**，不依赖解析 digest。

可选：消息级 `metadata.open_examine` = 本 turn 最后一次成功载荷（方便客户端）；trail 仍以 `tool_calls` 为准。

## B — UI（Apple quiet）

位置（agent bubble 内）：

```text
bubble → CompanionToolTrail → VerifyVerdictChip → VerifyTrajectory → handoff
```

- Chip：`--fill` / `--soft`，11px，`font-weight: 400`；对齐 `VerifyTrajectory`
- 文案短 label（今日 / 欠账 / 开考准备 / 教训 / 记下）；`title=summary`
- `ok: false` → soft + muted
- 「开考」：quiet 文本按钮（非 ink pill），对齐 DailyBrief 行点击语义

## C — 开考路径

```text
CTA → startWorkflow("examine")
    → claim_id → onExamineStartClaim(synthetic Claim from open_examine)
    → note_id  → onExamineStart(synthetic DayNote if not in notes list)
```

不跑 Critic/gate 直至 `/v1/examine`；与 DailyBrief 一键开考同一路径。

## Risks

- 旧消息无 `open_examine`：trail 仍可显示；CTA 仅在有载荷时出现  
- Stub（无 LLM key）仍无 `tool_calls` — 不变  
