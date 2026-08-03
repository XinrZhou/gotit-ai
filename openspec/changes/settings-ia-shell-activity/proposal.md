# Proposal: settings-ia-shell-activity

## Why

Settings was a flat dump of subsystems (资料 / Skills / MCP / 计划推送 / 动态)
with product jargon like「倒计时升温」. 动态 is an observation surface, not a
preference. Shell activity had no delete path.

## What changes

- Settings tabs → **我 / 提醒 / 高级** (Skills+MCP under 高级; Skills/MCP names kept)
- Interview copy → **临近备考提醒**
- **动态** moves to conversation top bar (beside 弱点图谱); fill Modal panel
- Delete shell_event/interest: `DELETE /v1/shell/activity/{id}`,
  `POST /v1/shell/activity/delete`, MCP `gotit_delete_shell_activity`; UI single + batch

## Out

- Cron UI redesign beyond light copy
- Auto-purge policies
- Moving Skills/MCP out of Settings
