# interview-learning-arc

## Why

面试升温、深挖、失败教训已有，但「日常欠账」与「临近面试该抠项目」在今日简报里仍像两张皮，叙事不闭合。

对应 `docs/PRODUCT.md` 演进 §7：临近面试时今日焦点可偏深挖，标准同一套。

## What changes

| 块 | 内容 |
|----|------|
| A | `/v1/today` / 空态简报：当 ramp 为 light/warm/urgent 时增加「建议深挖」条（项目名 + 一键深挖） |
| B | 与既有 companion `get_upcoming_interview`、tool trail「深挖」对齐 |
| C | 文案克制；prefs 关升温则简报不偏深挖 |
| D | 不改分档表；不自动改 plan |

## Out

- 重写 `interview_ramp` 阈值
- 自动开 drill / 自动改掌握
- 高频推送
- 排行榜或羞辱文案

## Acceptance

临近面试时打开空聊天能看到安静的深挖建议且可一点进入既有 drill；关闭升温 prefs 后建议消失；D-1/T-2h 行为不变。

## Agent owns / do not touch

- **Owns:** today brief 组装、SessionStart 面试条、相关文案、测
- **Do not touch:** `core/interview_ramp.py` 分档条件表、gate、digest promote、ActionBlocks 原语（可引用一键深挖按钮）、schedule 公式
