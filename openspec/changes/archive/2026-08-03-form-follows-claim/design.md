# Design: form-follows-claim

## Routing (deterministic)

```text
resolve_check_mode(preferred, project_id) → CheckMode
  preferred invalid / null / apply → probe
  preferred == drill and project_id is None → probe   # cannot open drill
  else → preferred

route_verify_action(mode) →
  probe      → examine / start_examine / 「开考」 / open_examine
  teach_back → teach   / start_teach   / 「回讲」 / open_teach
  drill      → drill   / start_drill   / 「深挖」 / open_drill
```

Gate path unchanged: examine + claim-bound teach still
`finalize_examine_with_gate`. Drill CTA only opens Sage session.

## Persist

`claims.preferred_check_mode VARCHAR(32) NULL`

Ingest heuristic (`suggest_preferred_check_mode`):

| Signal | Mode |
|--------|------|
| text/tags 含 回讲 / 口述 / teach_back … | teach_back |
| `project_id` set | drill |
| else | leave null → resolve as probe |

## Surfaces

- `_claim_view` + `/v1/today` due claims expose field
- `owed_claim_block` / verdict「再练」用 resolved route for action id/label
- companion `start_verify(claim_id?)` prepares the right open-*
- Web: DailyBrief CTA label; ActionBlocks `start_teach`; ChatPage
  `startVerifyClaim` → examine | teach | drill
