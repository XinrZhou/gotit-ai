# Tasks: main-path-converge

> 产品故事验收见 `design.md`（S1–S8）。机制诱惑 → Later。

## 0. 归档（先做）

- [x] 确认各夹对应代码已在 `main`
- [x] 归档已 ship → `archive/2026-08-03-*`
- [x] 更新 `openspec/changes/README.md`：Current active 仅本夹

## 1. 审计 → 入选实现项（产品故事驱动）

| # | 场景 | 卡点 | 期望 | 入选？ |
|---|------|------|------|--------|
| 1 | 无欠账空态 | 考我/回讲/深挖三芯片并列 | 「添加资料」为主动作 | ✓ S1 |
| 2 | 深挖入口 | 「往下挖」像过关 | 标明练习场、不过门 | ✓ S2 |
| 3 | 过关芯片 | 过了无旁注，欠着用语不一 | 统一 + 过了有证据感 | ✓ S3 |
| 4 | 出题结果 | 已有「过一遍门」 | 保持并与空态语气对齐 | ✓ S4 |
| 5 | 简报/收工 | 偏功能清单 | 人话节奏、次要入口安静 | ✓ S5 |
| 6 | 回讲选题 | 截断 6 条；空态无落点 | 与考我对齐 | ✓ S6 |
| 7 | 气泡/结束语 | 「深挖」像过关 | 练深挖 + 不过门 | ✓ S7 |
| 8 | 设置/摸底 | 旁路暗示会了 | 练习场措辞 | ✓ S8 |

- [x] 空库 / 有欠账路径对照设计主路径
- [x] 摩擦表入选上表

## 2. 收敛实现

- [x] S1–S5（空态 / 深挖诚实 / 芯片 / 出题 / 一日节奏）
- [x] S6：Teach 取消截断；考/回讲空态「添加资料」+ 门禁用语对齐
- [x] S7：ActionBlocks 练深挖 + verdict 旁注；drill 结束明示不过门
- [x] S8：摸底/简历/面试设置文案

## 3. 文档短同步

- [x] `design.md` 验收清单 S1–S8
- [x] `docs/SYSTEM.md` / README 立意对齐
- [ ] 本夹归档条件：S1–S8 手测过 + 真用一周无新主路径断点 → 再 archive

## 4. 门禁

- [x] `cd web && npm run build`（S1–S5）
- [x] `cd web && npm run build`（S6–S8）
- [ ] 提交：`fix(web): …` 与 `docs(openspec): …` 可拆

## Later（下一波次）

- 失败教训注入体验再加深（已有 failure_hint + teach 注入；可加更多表面）
- 深挖接 finalize（仅当备考真需要）
- Harness UI / auto-adopt；全量 MCP 进聊天
- 更深多 Agent 规划；工业 FSRS/CAT
- Settings 大改；弱点图谱抛光

## Spine code (this session)

- [x] ingest 不再因 project_id 建议 drill
- [x] teach finalize 写 `action_blocks`；Echo 注入 failure lessons
- [x] examine/teach 返回 `failure_hint`；ChatLog 安静展示
- [x] PATCH preferred 去掉 apply；companion / badge「练深挖」
- [x] `failure_hint` 写入 thread metadata（首轮）并在 ChatPage 展示
- [x] DailyBrief 欠账行挂 `failure_hint`（from failure_digest；`--faint`）
