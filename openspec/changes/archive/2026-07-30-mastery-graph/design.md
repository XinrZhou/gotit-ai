# mastery-graph — design

## Model

```text
Claim ──has_topic──► Topic   (existing v0)
Claim ──confused_with──► Claim  (weight, undirected canonical)
FailEvent(claim, gate_verdict, reason, …) on almost|owe_next
```

**Confused growth (no LLM):** on fail of A, for each other claim B in the same
topic that already has ≥1 fail_event, increment undirected edge weight. Edge is
**active** when `weight >= CONFUSED_THRESHOLD` (2).

**Budget subgraph (P4):** target claim + up to 2 active confused neighbors
(highest weight) + recent fail reasons for target. Inject into Axiom only.

**Plan fill:** sort due claims by fail_event count desc before enqueue.

## Storage

Postgres / SQLite via SQLAlchemy: `fail_events`, `graph_edges`. Nodes remain
`claims`. Observation reuses `GraphView` with `rel=confused_with` + meta.weight.

## Surfaces

| Surface | Role |
|---------|------|
| verify (REST/MCP) | write FailEvent + edges after gate |
| examine/verify Axiom | read budget text |
| fill_today_from_queue | fail-count soft sort |
| Settings → 图谱 | force-graph viz (obs only) |

## Constants (`gotit.core.mastery_graph`)

- `CONFUSED_THRESHOLD = 2`
- `BUDGET_CONFUSED_MAX = 2`
- `BUDGET_FAIL_REASONS_MAX = 3`
