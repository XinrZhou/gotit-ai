---
name: coding
description: >-
  WeChat-commanded local coding against an allowlisted workspace. Runs edits /
  tests in-repo; replies with a short success summary or failure highlights.
  Optional gotit_add_memory for durable lessons.
---

# coding — 微信指挥本机 coding（OpenClaw）

**落点在 OpenClaw**，不进 gotit 内核。本 skill 约束 workspace，避免任意路径执行。

## Allowlist

编辑 `skills/coding/workspaces.json`（或软链后的副本）：

```json
{
  "workspaces": [
    {
      "id": "gotit",
      "path": "/Users/zxr/workspace2026/gotit-ai",
      "branches_ok": ["main", "feat/*"]
    }
  ]
}
```

命令只能在 listed `path` 下跑（`cwd` 必须是该目录或其子目录）。

## 流程

1. 解析用户意图 → 选 workspace `id`
2. 在 allowlist 内改文件 / 跑 `uv run pytest …` / `./scripts/gate.sh` 子集
3. 成功：微信回 3～6 行摘要（改了什么、测试结果）
4. 失败：回错误要点（首个失败断言 / 编译错误前几行），勿贴整 log
5. （可选）`gotit_add_memory(layer=long, kind=lesson, content={…})` 记可复用教训

## 安全

- 禁止 allowlist 外 `rm` / 写 `.env` / 推远程（除非用户明示且仍在 allowlist）
- 不在 gotit MCP 里暴露 shell 执行

## 软链

```bash
ln -sfn /path/to/gotit-ai/skills/coding ~/.openclaw/workspace/skills/coding
```
