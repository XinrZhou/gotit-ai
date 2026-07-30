# cold-start-calibration — tasks

> 对齐 `proposal.md` / `design.md`。  
> **A 可先于 B**；**C 依赖 A+B**；**D/E 跟 C**；**F 可与 D 并行**（契约稳定后）。

## Spec（任务 0）

- [x] proposal / design / tasks
- [x] `openspec/changes/README.md` 登记本夹
- [x] 实现过程中保持本 tasks 勾选；整波完成后归档并更新 `docs/SYSTEM.md`（+ README 若用户可见）

---

## A — 确定性 CAT 核心（`gotit.core.calibration`）

- [x] 题目标注类型 + 缺省（difficulty=3, discrimination=1.0, knowledge_key）
- [x] 2PL 正确概率 / Fisher 信息量 / θ·se 更新（docstring 钉公式）
- [x] `select_next_item`：最大信息 + knowledge 轮换 + 已测邻点降权
- [x] `should_stop`：converged / stable / max_items(10) / exhausted；`MIN_ITEMS`
- [x] 纯函数单测：升难/降难、轮换、早停、上限

---

## B — 持久化

- [x] alembic `0010_cold_start_calibration`：claim 校准元数据 + `calibration_sessions`
- [x] ORM + `core.models` 视图（Session / Trace step / Summary）
- [x] 读 claim 时补齐校准缺省（不强制改写旧行也可）

---

## C — `db.ops.calibration` 写回闭环

- [x] `start_calibration`：建 session、选首题、返回视图
- [x] `answer_calibration`：写 trace、更新 θ；correct→`passed`；incorrect→`almost`+`fail_event(reason=calibration)`+`seed_confused_for_calibration`
- [x] `graph.seed_confused_for_calibration`（仅校准用；日常 grow 规则不动）
- [x] 早停/满题 → `finalize`：summary + 可选 `fill_today_from_queue`；保证有错题时当日 due 非空
- [x] barrel `__init__.py` 导出
- [x] pytest：写回 status / next_review_at / fail / confuse / due

---

## D — REST + MCP

- [x] `api/routes/calibration.py`：start / answer / get / synthetic；挂入 `routes/__init__.py`
- [x] MCP：`gotit_calibration_start|answer|get|synthetic` → 同 ops
- [x] 无 LLM 全链路可测

---

## E — Synthetic + harness

- [x] `run_synthetic_calibration`（ops 或 core+ops）：已知 true_theta → hat / error / trace
- [x] pytest + 可选 harness case：方向正确、误差带宽

---

## F — 最小 Web

- [x] API 客户端 + 类型
- [x] 空态 / 无 due 有池：安静 CTA「先摸底一下」
- [x] 极简校准页/面板：题干、进度、对/错、结束摘要 → 回今日欠账
- [x] `ui-apple.mdc`；不鸡血

---

## Docs / Gate

- [x] `docs/SYSTEM.md`：Shipped 冷启动校准；衔接 schedule / fail / confuse
- [x] `README.md` + `README.zh-CN.md`：功能表一句
- [x] `./scripts/gate.sh` 绿
- [x] 归档本夹 → `archive/2026-07-30-cold-start-calibration/`（或当日戳）；更新 changes README
