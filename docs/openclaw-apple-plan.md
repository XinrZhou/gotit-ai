# OpenClaw Apple 计划桥（companion-os P1d）

**提醒事项（待办）是手机侧主入口**；gotit 是日计划 / 验证真源。
备忘录仅次要（大段 markdown 导入）。

```text
提醒事项 ←── push / rm ── gotit plan
     │                      ▲
     └── import ────────────┘
```

## 用法

```bash
# 提醒 → gotit
uv run python skills/apple-plan/import_plan.py reminders --list "学习计划" --apply

# gotit → 提醒（对话新建后必跑）
uv run python skills/apple-plan/import_plan.py push --day 2026-07-30 --apply

# 删除（gotit + 提醒）
uv run python skills/apple-plan/import_plan.py rm \
  --day 2026-07-30 --title "刷动态规划" --apply
```

列表默认「学习计划」（不存在会在 push 时创建）。导入要求条目带到期日。

权限：系统设置 → 隐私与安全性 → **提醒事项**。

相关：

- OpenSpec：`openspec/changes/companion-os/`（P1d）
- Skill：`skills/apple-plan/`
- 早晚推送（读 gotit plan）：[`docs/openclaw-digest.md`](openclaw-digest.md)（P1c，另一条线）
- MCP：`gotit_delete_plan_item`（`item_id` 或 `day`+`title`）

## 架构

```text
Reminders / Notes ──osascript(JXA)──► skills/apple-plan/import_plan.py
                                              │
                                              ▼
                                    REST 或 db.ops（= MCP）
                                              │
                                              ▼
                                       gotit plan_items
```

**铁律：** 禁止在 `src/gotit/` 内访问 Apple。浏览器 Settings **不**读本机 Apple。

## 安装

```bash
# 软链到 OpenClaw workspace（路径按本机改）
ln -sfn /Users/zxr/workspace2026/gotit-ai/skills/apple-plan \
  ~/.openclaw/workspace/skills/apple-plan
```

可选：编辑 `skills/apple-plan/config.json`：

| 键 | 默认 | 含义 |
|----|------|------|
| `reminders_list` | `学习计划` | 提醒事项列表名 |
| `notes_title_match` | `学习计划` | 备忘录标题包含匹配 |
| `notes_folder` | `""` | 非空则限定文件夹 |
| `gotit.api_url` | `""` | 空=本机 db.ops；可填 `http://127.0.0.1:8787` |

REST 时设置环境变量 `GOTIT_API_KEY`。

## 权限（首次人工）

1. 跑一次 dry-run（见下）。系统弹出权限时点 **允许**。
2. **提醒事项**：系统设置 → 隐私与安全性 → 提醒事项 → 勾选终端 / OpenClaw。
3. **备忘录**：系统设置 → 隐私与安全性 → **自动化** → 允许控制「备忘录」。
4. **不要**为省事开 Full Disk Access；本桥用 Automation / Reminders TCC 即可。
5. 权限缺失时脚本会打印可读错误并非零退出，**不应**拖垮 OpenClaw Gateway。

## 用法

默认 dry-run：

```bash
cd /path/to/gotit-ai
uv run python skills/apple-plan/import_plan.py reminders --list "学习计划"
uv run python skills/apple-plan/import_plan.py notes --title "学习计划"
```

确认输出的 `day / action / title` 后写入：

```bash
uv run python skills/apple-plan/import_plan.py reminders --list "学习计划" --apply
```

日期窗：`--from YYYY-MM-DD --to YYYY-MM-DD`。

本地试 Notes 解析（不启 Notes.app）：

```bash
uv run python skills/apple-plan/import_plan.py notes --file ./my-plan.md
```

验收：`--apply` 后 `gotit_get_plan(day)` / Web 当日计划能看到。

### iPhone

人在手机上写备忘录、Claw 在 Mac 读：依赖 iCloud。
晚报用 **`https://www.icloud.com/notes`**（微信只链 https；`mobilenotes://` 会变纯文本）。
也可手动打开系统「备忘录」App。

## Reminders 约定

- 使用指定列表（默认「学习计划」）。
- **到期日** → gotit 的 `day`；无到期日 → warning 并跳过；若全部无到期日 → 失败退出。
- 已完成的提醒不导入。

## Notes 约定

正文须为：

```markdown
## 2026-07-30
- [ ] 复习 Redis
- 读完第 3 章

## 2026-07-31
- teach-back CAP
```

- 日期标题：`#`～`###` + `YYYY-MM-DD`。
- 条目：`-` / `*`，可选 `[ ]` / `[x]`。
- 日期前杂文、区块内非清单行、空区块 → **硬错误**（不静默丢）。

## 写入策略（v0）

| 规则 | 行为 |
|------|------|
| 真源 | gotit；可重复单向再导入 |
| 去重 | 同日标题 casefold 相同 → **skip**（不改 status / claim_id） |
| source | `manual` |
| 默认 | dry-run；`--apply` 才写 |
| examine | **不**自动 ingest / examine |

## 与 P1c（digest）的关系

| | P1c digest | P1d apple-plan |
|--|------------|----------------|
| 职责 | 早/晚读 gotit plan 推微信；资讯独立 | 把 Apple 计划写入 gotit |
| 改 `fetch_digest.py`？ | 是（A） | **否（B）** |
| 依赖 | plan 已在 gotit | 本 skill 负责灌入 |

## Settings

Web 设置 → **资料** 有导入说明与默认列表名提示；**不会**在浏览器读 Apple。
改列表名请编辑 `skills/apple-plan/config.json` 或 CLI `--list`。

## 手动验收清单

- [ ] dry-run 列出将导入条目
- [ ] `--apply` 后 Web / MCP `gotit_get_plan` 可见
- [ ] 拒绝提醒事项权限时有可读错误、Gateway 不崩
- [ ] Notes 故意写错格式 → 明确报错
- [ ] 再导入同标题 → skip，不覆盖已验证项

## 测试

```bash
uv run pytest tests/test_apple_plan.py -q
```

真机 osascript 不进 CI。
