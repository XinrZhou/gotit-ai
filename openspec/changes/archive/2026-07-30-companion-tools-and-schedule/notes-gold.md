# notes-gold — 个人小样本质量对照

> 对应 OpenSpec `companion-tools-and-schedule` **分区 E** / 提示词任务 5。  
> 目的：固定一小撮 claim，前后对照「再考是否更稳 / examine vs critic 是否分歧」——**服务产品小步改进，不是对外刷榜**。  
> 对齐 `docs/PRODUCT.md` 演进 §5。

机器目录：`src/gotit/harness/gold_claims.py`（slug 稳定；运行时 UUID 临时）。  
冒烟用例：`src/gotit/harness/cases/gold.py`（gate 矩阵 + 再考转化 + 目录完整性）。

---

## 15 分钟跑完一轮（给接手的人）

前置：仓库根目录、已 `uv sync --all-extras`。冒烟**不需要** LLM。

```bash
# 1) pytest 冒烟（~10s）
uv run pytest tests/test_gold_harness.py -q

# 2) 打印对照表 + 跑 gold harness 集（推荐入口）
uv run python scripts/run_gold_compare.py --label gold-$(date +%Y%m%d)

# 等价：仅 harness
# uv run python scripts/run_harness.py --set gold --label gold-smoke
```

把第 2 步打印的 markdown 表粘进下方「对照记录」（或 `docs/gold-logs/` 自建日志）。  
**一轮验收 = pytest 绿 + harness gold `verdict=pass` + 表已复制保存。**

有 LLM 时另加（可选，不计入 15 分钟硬门槛）：对真 claim 走 examine → 看 UI `VerifyTrajectory` 三档，手工补行。

---

## 选取规则（5～10 条）

| 规则 | 说明 |
|------|------|
| 数量 | **5～10**；当前目录 **8** 条 |
| 覆盖 | ① 三档一致（过了 / 还差点 / 欠着）② **门分歧**两例（考官宽复核严 / 反之）③ **再考转化**一条 ④ **易混邻居**一对 |
| 稳定 ID | 文档与 harness 用 **slug**（如 `gold-04-gate-code`）；库内 UUID 每次跑可新建 |
| 真题优先 | 日常可用自己常挂的 claim 替换 text，但 **保留 slug** 以便跨次对照 |
| 不做 | 不为刷榜扩集；不改 `deterministic_gate` 语义 |

### 目录（占位 slug）

| slug | claim 摘要 | 角色 / 测什么 |
|------|------------|---------------|
| gold-01-pointer | 指针保存的是地址… | 清晰过了（agree passed） |
| gold-02-free-null | free 之后置空… | 还差点边界（agree almost） |
| gold-03-softmax | Softmax 归一… | 欠着下次（agree owe_next） |
| gold-04-gate-code | gate 必须是代码… | **examine vs critic 分歧**（passed×owe_next→owe_next） |
| gold-05-attention | Self-Attention… | **分歧反向**（almost×passed→almost） |
| gold-06-retest | 验证闭环 examine→… | **再考转化** owe_next→passed + trajectory |
| gold-07-array-decay | 数组名退化成指针 | 易混邻居 A |
| gold-08-stack-heap | 栈/堆释放 | 易混邻居 B（与 A 成对文档；排程改动只读备注） |

易混对：`GOLD_CONFUSE_PAIR = (gold-07-array-decay, gold-01-pointer)`。

---

## 测什么

| 观测 | 怎么看 | 个人成功信号 |
|------|--------|--------------|
| **gate 一致性** | harness `gold-gate-pairs` | gate == stricter(examine, critic) |
| **examine vs critic 分歧** | 表中「分歧?=是」行 | 宽严方向后仍取严档；不静默放水 |
| **再考转化** | `gold-06-retest` | 先 owe_next 再 passed → mastered + ≥2 条 trajectory |
| **易混（只读）** | gold-07/08 备注 | 排程/选题改动后是否提到邻居——不改门 |
| **真 LLM（可选）** | UI/API 三档 | 无 key 时 critic 回声，备注写 `stub_critic` |

---

## 对照记录表格模板

`run_gold_compare.py` 会打印同结构表。手工追加真跑时用：

| 日期 | claim | examine | critic | gate | 分歧? | 备注 |
|------|-------|---------|--------|------|-------|------|
| YYYY-MM-DD | gold-01-pointer | passed | passed | passed | 否 | |
| YYYY-MM-DD | gold-04-gate-code | passed | owe_next | owe_next | 是 | 考官宽复核严 |
| YYYY-MM-DD | gold-06-retest | owe_next→passed | … | … | 否 | 再考第 2 轮 |

批次汇总（手算即可）：

| 批次 | 日期 | label | gate 冒烟 | 真 LLM 条数 | 备注 |
|------|------|-------|-----------|-------------|------|
| before | | | pass/fail | | 改 prompt/排程前 |
| after | | | pass/fail | | 改后同集 |

---

## 命令速查

| 目的 | 命令 |
|------|------|
| pytest | `uv run pytest tests/test_gold_harness.py -q` |
| 打印表 + harness | `uv run python scripts/run_gold_compare.py --label …` |
| harness only | `uv run python scripts/run_harness.py --set gold --label …` |
| 日常 CI harness | `uv run python scripts/run_harness.py --label gate` |
| verify e2e（可选） | `uv run pytest tests/test_companion_e2e.py::test_verify_loop_deterministic_gate -q` |

---

## 约束

- 不引入重型评测平台；不为刷榜  
- **不修改**掌握门语义；本夹只读统计 + 冒烟钉死已有公式  
- 不做 FSRS 重写、tool-calling、UI 大改  

## 未完成 / 后续（非本任务阻塞）

- 真 LLM 小样本需 `LLM_*`（可选 `CRITIC_*`）；trajectory 未必存 `recheck_verdict`，真跑以 UI/API 为准  
- 未做 holdout UI / 自动 adopt；人就是 judge  
- `docs/gold-logs/` 可自建存前后表，不进重型平台  
