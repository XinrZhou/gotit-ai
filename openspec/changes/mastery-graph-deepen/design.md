# Design: mastery-graph-deepen

## Framing

Mastery graph = verify-derived structure for **retrieval + interference +
prerequisites**. Not a general knowledge graph.

## API enrichment (`GET /v1/obs/graph`)

### Claim node `meta` (additive)

| key | meaning |
|-----|---------|
| `claim_id` | bare UUID string |
| `fail_count` | existing |
| `topic` | existing |
| `status` | existing |
| `preferred_check_mode` | probe\|teach_back\|drill\|null |
| `project_id` | optional |
| `last_fail_at` | ISO datetime or null |
| `last_fail_reason` | short string or null |
| `recent` | true if last fail within `active_days` (default 14) |

### Edge `meta` (additive)

**confused_with:** `active`, `cross_topic`, `source_topic`, `target_topic`,
`reason_summary` (newest fail tip on either endpoint, ≤80 chars)

**depends_on:** `unmet` (prereq not mastered), `prereq_label` short

No new `rel` values. No schema migration.

## UI

- Toolbar: 薄弱 | 全部 | **近14天**（filter claims with `meta.recent` or
  endpoints of confuse/depends touching recent claims；保留相关 topic）
- Detail card: label + fail/topic + edge explanation + primary CTA
  （开考/回讲/练深挖；drill 仍 prep-only 文案旁注）
- Cross-topic confuse: slightly stronger stroke
- Unmet depends: keep dash；detail 标明「前置未过」
- Close graph on launch verify

## Store

`queueVerifyClaim(claim)` → existing `pendingExamineClaim` → ChatPage
`startVerifyClaim`（form-follows-claim）。

## Tests

- Enrichment: cross_topic true when topics differ；depends unmet
- Recent flag when fail within window
- Existing writeback tests still pass

## Out

GraphRAG, LLM edges, new edge types, Harness UI.
