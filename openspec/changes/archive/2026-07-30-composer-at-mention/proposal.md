# Composer `@` mention

## Why

Chat already routes via sticky `mentions` + `+` tray, but the product language is
`@mention`. Typing `@` in the composer should switch the sticky companion without
embedding `@昵称` in the message body.

## In

- Chat composer only: `@` opens a quiet agent picker (filter by id / 中文昵称)
- Select → update sticky mention, strip the `@query` token from draft
- Keyboard: ↑↓ · Enter/Tab · Esc
- Keep `+` tray as the discoverable path

## Out

- Slash `/skill` commands
- Multi-@ or leaving `@` text for the model to parse
- `@` inside examine / teach / drill composers
