# Design — yuque-md-convert-wipe

## Root cause (content wipe)

`yuque-editor-core` 的 `YuqueRichText` 在 `value` 变化时：

```ts
if (api.getContent(scheme) !== value) api.setContent(value, scheme);
```

Markdown「立即转换」会先清空再写入富文本，中间一次 `contentchange("")`
若写进 React state，随后 sync 用空 `value` 覆盖已转换正文。

## Approach

1. 冻结初始 `value`（`useState` 一次），挂载后不走受控回写。
2. 宿主用 `ref.getHtml` / `ref.setHtml` 读写与清空。
3. 若仍监听 `onChange`：对空白文档 `rAF` 后再读一次，避免空闪烁外传。

## Compose shell

- 默认 `Modal wide`（800px）+ 编辑器高度 320。
- 「放大预览」→ `Modal fill`（近视口）+ 编辑器 `flex:1`；**同一实例**，只改壳尺寸，避免 remount 丢正文。
- `Esc` 先收起放大；关弹窗仍走原关闭。

## Alternatives

- Fork 库去掉 sync effect — 维护成本高，不值。
- 放大时 portal 第二编辑器 — 需同步正文，易再踩受控坑。
