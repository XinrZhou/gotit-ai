# cold-start-calibration

## Why

新用户或新材料进来时，claim 全是 `not_yet`、due 要么空要么一坨排队——学习者不知道从哪摸底，排程与弱点图谱也要从零挂科才长出来。

对应 `docs/PRODUCT.md`：痛点「今天碰什么不清楚」「假懂」；演进 §2（下次练什么更老实）与 §5（用使用痕迹小步改进）。  
目标：用**最少题数、最高信息量**的校准，初始化间隔复习与 `confused_with`，当天「欠什么」就有内容——不是普通问卷，也不是无头刷题。

## What changes

| 块 | 内容 |
|----|------|
| A | **确定性 CAT 核心**（`gotit.core.calibration`）：难度/区分度、信息量选题、难度自适应、知识点轮换、早停+硬上限 |
| B | **题目标注 + 会话持久化**：claim 校准元数据；`CalibrationSession` + per-step trace |
| C | **写回闭环**：答对→`passed`；答错→`owe_next`+`fail_events`+`schedule.py`；校准专用 confuse 种子；结束保证当日 due 有料 |
| D | **REST + MCP** 镜像同一套 `db.ops.calibration` |
| E | **可观测 + synthetic**：trace 可回放；已知能力模拟用户回灌，监控估计精度 |
| F | **最小 Web 入口**：空态 / 笔记后 CTA + 极简校准页（出题→对错→结束摘要） |

## Out

- 用 LLM 裁定掌握档位、due 日期或选题终审  
- 每题跑完整 Examine→Critic→gate（正式「考我」仍走原路径）  
- 整仓搬 Anki / 完整 IRT 服务 / 向量 RAG  
- 第二大脑、多租户、娱乐人设  
- 改日常 verify 的 confuse 生长规则（仍要求同 topic 已失败 peer）  
- Companion 白名单挂 `start_calibration`（可选小迭代，非本夹阻塞）  
- 华丽 CAT 仪表盘 / Settings 大改

## 为何一个夹

选题、写回、due、trace、最小 UI 同属一条用户故事：「进来摸底 → 当天有欠账」。拆夹会重复改 `SYSTEM` / claim 形状，且无法一次验收闭环。

## Acceptance（一句话）

新材料/冷用户能跑完 ≤12 题的信息量校准；答错进 fail + 排程 + 校准种子易混边；答对近期不排；结束后今日 due 非空（有弱项时）；每次校准有 trace；synthetic 回灌可测估计误差——门与排程仍是代码。
