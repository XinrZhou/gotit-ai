# ADR-0001: Python + uv core, OpenClaw via MCP

- Status: Accepted
- Date: 2026-07-27

## Context

gotit-ai must ship as an independent verification engine and integrate with OpenClaw. Package management should use **uv**. A React web UI remains first-class.

## Decision

1. Implement domain + API + MCP + harness in **Python 3.12** with **uv**.
2. Expose **REST/SSE** and **MCP** (stdio + later streamable-http) sharing the same domain operations.
3. Keep **React + Vite** under `web/` using **npm** (uv does not manage JS).
4. Use **Postgres + Redis** from day one.
5. Keep `gotit.core` framework-free so transports can change without domain rewrites.

## Alternatives considered

- Full TypeScript monorepo (closer to OpenClaw): rejected because package management is uv/Python.
- Embedding into OpenClaw as an in-process plugin: rejected to keep a clear product boundary.

## Consequences

- OpenClaw connects via MCP; channels stay outside gotit.
- CoPaw (later) can call the same HTTP/MCP surface.
- Two package managers in one repo (uv + npm) — documented and scoped by directory.
