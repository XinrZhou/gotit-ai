## Why

Library notes only support one-by-one delete via the ⋯ menu. Users need to
clear multiple materials (e.g. leftover resume notes) quickly.

## What Changes

- `delete_notes` in `db.ops` + `POST /v1/notes/batch-delete` + MCP
  `gotit_delete_notes`
- Sidebar: 选择 mode → checkboxes / 全选 → confirm Modal → batch delete

## Impact

Frontend + thin API/MCP; Apple quiet select + Modal confirm (no `window.confirm`).
