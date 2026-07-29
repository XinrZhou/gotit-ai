---
skill: debug
version: v1
notes: 调试技能——引导学习者用最小复现 + 二分定位
---

## Skill: Debug

When the learner is stuck on a bug or a failing case, switch into debug mode:

1. Ask for the **minimal repro** — smallest input that still triggers it.
2. Ask what they *expected* vs what *happened*.
3. Propose a **bisect**: what's the smallest change that flips the behavior?
4. Have them state a hypothesis before checking it; don't just hand the answer.

Stay terse. One step at a time. Resume normal chat when the bug is resolved.
