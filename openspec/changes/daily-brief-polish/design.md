# Design — daily brief polish

## Approach

Keep Apple quiet select (`--soft` / `--fill`, no ink pills). Hierarchy via type color (`--faint` → `--muted` on reasons) and grouping, not louder chrome.

| Piece | Before | After |
|-------|--------|-------|
| Rows | Separate soft cards | One rounded group, hairline between rows |
| Row affordance | Faint chevron | Quiet fill chip「开考」 |
| Empty thread chrome | Brief + orphan close/links | `briefStage` + `briefFooter` |

## Files

- `web/src/components/DailyBrief/`
- `web/src/pages/ChatPage/index.tsx` + `index.module.scss`
