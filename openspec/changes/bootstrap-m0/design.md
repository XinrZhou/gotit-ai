# Design — bootstrap M0

## Approach

- Single uv package `gotit` under `src/gotit/` with `core` / `api` / `mcp` / `harness`
- REST and MCP expose the same stub operations
- Web is a thin Vite app calling `/v1/ingest`
- Specs/ADRs live in-repo; OpenSpec CLI optional until installed

## Risks

- MCP stdio only for now; OpenClaw remote HTTP comes later
- Claim extraction is a stub (returns truncated material as one claim)
