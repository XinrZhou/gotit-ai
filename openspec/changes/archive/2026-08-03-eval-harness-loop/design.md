# Design: eval-harness-loop

## 现状（代码事实）

| 能力 | 路径 | 深度 |
|------|------|------|
| Runner | `src/gotit/harness/__init__.py` | 跑 case → 两表落库 |
| Case 集 | `harness/cases/dev.py`、`gold.py` | 接线 + 部分 gate/写回 |
| CLI | `scripts/run_harness.py`；`gate.sh` 跑 dev | 有 |
| REST | `api/routes/harness.py` POST/GET + PATCH decision | 有；summary 偏 total/passed |
| 人审 | `adopt\|observe\|reject` 进 summary | 有；无自动副作用 |

已归档相关：`archive/2026-08-03-verify-spine-deepen`（API 面已上）。

## 指标契约（SHALL）

每次 run 的 `HarnessRun.summary`（及关键 case 的 `metrics`）应能回答：

| 键 | 含义 | 来源 |
|----|------|------|
| `total` / `passed` / `failed` | 已有 | runner |
| `gate_consistent` | deterministic_gate 相关 case 全过（bool 或子计数） | 新聚合或 case metrics 上卷 |
| `routing_ok` | check_routing：probe→examine、teach_back→teach 等（bool） | 新 case |
| `no_spurious_write` | 无 LLM key / stub 路径不产生假掌握写回（bool） | 新 case |
| `failure_hook_ok` | 失败写回相关断言全过（bool；依赖 B 或现有行为） | 新 case；B 未完成前可 skip/xfail 策略见下 |
| `decision` | 人审后：`adopt\|observe\|reject` + 可选 `note` | 已有 PATCH；保持可查询 |

说明：

- 指标名稳定，供面试/文档引用；实现可用扁平 bool 或 `{ok, n_pass, n_total}`。
- **禁止**把 LLM 主观分当掌握终审；harness 断言的是代码行为。

## Case 加深范围

优先 **dev**（`gate.sh` 默认）：

1. **Gate**：stricter-of-two + score/evidence 降档信号（已有则收紧 metrics 上卷）。
2. **Routing**：`core/check_routing.py` — APPLY→probe；drill 无 project→probe；
   teach_back→teach CTA。
3. **Stub / no-key**：finalize 或 companion 路径在无 key 时不伪造 `passed` 写回
   （对齐现有 stub 行为，写成显式 case）。
4. **Failure hook**：调用 `maybe_record_failure_digest` / select+budget 纯函数，
   或跑一条「owe_next → digest 存在 → 再选课注入非空」的 DB case。
   - 若 B 尚未落地「再考注入」缺口：case 标 `layer=loop`，对缺失行为
     `pytest.importorskip` / harness 内明确 `passed=False` 仅在 A 单独合入前
     用「仅测已存在 API」子集；**合并主线前 A+B 都绿**。

Gold：仅当需要矩阵对照时加**确定性**段；不新增强制在线 LLM case。

## 人审

- PATCH decision 只写审计字段，**不**调用 prompt register / skill install。
- 可选：list runs 按 `decision` 过滤（小改，非必须）。
- 文档一句：VISION P5 — holdout evidence before adopt；adopt ≠ auto-apply。

## 协作（与方向 B）

| 事项 | Owner |
|------|--------|
| `select_failure_lessons` / budget / digest 去重行为 | B |
| harness case「挂过 → digest → 注入块非空且 ≤600 字」 | A 写 case，断言 B 的公共 API |
| 改 `core/schedule.py` 公式 | **都不要**（除非修 bug）；排程人话/表在 B |

合并顺序建议：B 行为先或同 PR 族；A 的 `failure_hook_ok` 以 B 的稳定函数为契约。

## 非目标回顾

不做 UI；不做自动 adopt；不做 RAG eval；不换 Agent 框架。
