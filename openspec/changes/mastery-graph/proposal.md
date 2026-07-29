# mastery-graph — proposal

## Why

Verification produces trajectories, but failures stay scattered: next exam cannot
reliably use “what you confuse with what,” and dumping whole notes fights P4.
We need a **mastery graph** (not a second-brain KG): claim nodes, fail events,
and `confused_with` edges grown from verify outcomes.

## What

- Postgres `fail_events` + `graph_edges` (`confused_with`, weight/threshold)
- Write on verify gate when verdict is `almost` | `owe_next` (no LLM edge invent)
- Read: budget subgraph → Axiom prompt; soft sort in `fill_today_from_queue`
- Extend `/v1/obs/graph` + Settings tab「图谱」with `react-force-graph-2d`
- No Neo4j, no RAG, no `depends_on` in v1

## Out

- LLM-proposed edges; GraphRAG; claim text dedup; depends_on DAG; editing edges in UI
