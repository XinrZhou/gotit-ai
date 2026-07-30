# Composer `@` — design

## Model

Unchanged API: `POST …/messages` still sends `mentions: [agent_id]`.
`@` is a **UI accelerator** for sticky `mention` state, not message syntax.

## Trigger

At caret, match `(^|whitespace)@([^\s@]*)`. Open menu when match exists and
not Esc-suppressed. Filter agents by `id` or `AGENT_UI.label` (case-insensitive
for ascii).

## Select

Replace `@query` with empty string; set `mention`; refocus caret at strip point.
Do not insert the nickname into the draft.

## Chrome

Popup above `.composerField`, Apple quiet select (`--fill` active row).
Placeholder / title hint: `@` 切换搭子.
