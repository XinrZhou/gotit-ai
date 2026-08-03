# Design — note ingest next step

## Flow

```text
idle → generating（弹窗不关 · 正在出题…）
     → ready（claim 摘要 · [去开考] [先不考]）
去开考 → 关弹窗/资料库 → startExamineClaim(first) → Examine「思考中」
先不考 → 清状态 · 关弹窗；今日简报已有新行可开考
```

## State

`ingestUi` in `useNotes`:

| phase | fields |
|-------|--------|
| generating | `noteId`, `surface: view \| compose` |
| ready | `noteId`, `claims[]`, `surface` |

`pendingExamineClaim` handoff: modal CTA sets claim → ChatPage `useEffect` →
`startExamineClaim`（建 thread + `mode=examine`）。

## API

`POST /v1/notes/{id}/ingest` already returns `{ note_id, claims, plan_items }` —
type it on the client; no backend change.

## UI

Shared `IngestOutcome` in `components/`（ViewNote + Compose）. Quiet Apple select;
primary `btn-ink`「去开考」.
