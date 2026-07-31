# voice-teachback-verify

## Why

部分主张「讲不清就不算会」。回讲工作流与渠道侧口说技能已有苗头，但口说结果未稳定走同一套 Critic + 确定性门，验证形态与脊柱断裂。

对应 `docs/PRODUCT.md` 演进 §7 + VISION P3（form follows the claim）。

## What changes

| 块 | 内容 |
|----|------|
| A | 应用内回讲：录音/上传 → 转写 → 作为 teach 作答 |
| B | 终审走共享 verify finalize（与 examine 同 Critic+gate 原则；teach 既有路径对齐） |
| C | REST（+ 可选 MCP）；失败写 failure 教训预算注入 |
| D | 无 ASR key 时降级为纯文本回讲，不假装录音成功 |

## Out

- 陪聊式语音伴侣、多角色 TTS 娱乐
- 用模型替换 gate
- 改间隔公式内核（可写回既有 SR）
- 把能力只做在 OpenClaw skill、Web 无入口

## Acceptance

用户可对一 claim 口说回讲（或转写文本）；得到与其它验证一致的档位芯片；无 ASR 时文本路径可用。

## Agent owns / do not touch

- **Owns:** teach 路由/ops、转写适配、Web Teach 口说 UI、finalize 对齐、测
- **Do not touch:** Chat ActionBlocks 大重构、digest、day-close、interview 列表 UI
