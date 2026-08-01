# Tasks: main-path-converge

> 明天执行：先 Task 0，再 Audit，再按优先级勾选实现。机制诱惑 → Later，不进本表。

## 0. 归档（先做）

- [ ] 确认各夹对应代码已在 `main`（对照 git log / SYSTEM）
- [ ] 归档已 ship：`verify-spine-deepen`、`form-follows-claim`、
      `cat-param-writeback`、`note-ingest-next-step`（及已合的
      `daily-brief-polish` / `yuque-md-convert-wipe`）
      → `openspec/changes/archive/2026-08-01-*`（日期按执行日可改）
- [ ] 更新 `openspec/changes/README.md`：Current active 以本夹为主；
      Later 保留 APPLY / harness auto-adopt 等，不新开夹

## 1. 主路径走查（产出清单，先别大改）

- [ ] 空库：打开 → bootcamp/空态 → 添加资料 → 出题 → 去开考 → 见门禁芯片
- [ ] 有欠账：打开 → 今日简报 → 一键开练（含回讲/深挖分流若有）→ 芯片
- [ ] 记摩擦表（建议写在本文件底部「Audit log」）：至少 5 条
- [ ] 从摩擦表挑 **≤5** 条进 Task 2（其余放 Later）

## 2. 收敛实现（仅审计入选的）

优先级默认（审计可推翻）：

- [ ] P0：任何「做完不知道下一步」的断点（文案 / 主按钮 / 关闭弹窗后落点）
- [ ] P0：空态主 CTA 过多时收成一个主动作 + 次要安静入口
- [ ] P1：主路径上的工程黑话（dev/gold/adopt/layer/case…）改为人话或删除暴露
- [ ] P1：IngestOutcome / DailyBrief / SessionStart 文案语气对齐（搭子不是监工）
- [ ] P2：重复 brief / 重复开考入口去重
- [ ] P2：设置页对学习者噪音降一级（不删 Skills/MCP，可调标签或说明句）

## 3. 文档短同步

- [ ] `docs/SYSTEM.md`：补 3～6 行「Main path (learner)」指向上述闭环；
      Not done 不膨胀
- [ ] 若 README 功能表与主路径措辞严重漂移，各改一句（中英）
- [ ] 本夹 `tasks.md` 勾选；准备归档本夹的条件写清（主路径摩擦表清零或只剩 Later）

## 4. 门禁

- [ ] 改了代码则跑相关测试 / `./scripts/gate.sh`（或 pytest + web build）
- [ ] 提交按故事拆：`docs(openspec): archive …` 与 `fix(web): …` / `refactor(web): …` 分开

---

## Audit log（执行时填写）

| # | 场景 | 卡点 | 期望 | 入选？ |
|---|------|------|------|--------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |

## Later（本波次不做）

- 完整 APPLY 验证工作流
- Harness 用户向 UI / auto-adopt prompt
- Compass 自动打 `preferred_check_mode`（LLM）
- 新算法：FSRS 全量、工业 CAT、更大知识图谱
- 多模型按 agent 广绑（除已有 Critic）
