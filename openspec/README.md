# OpenSpec workspace (manual bootstrap — run `openspec init` when CLI is available)

This repo uses [OpenSpec](https://github.com/Fission-AI/OpenSpec) for change lifecycle:

```text
propose → apply → archive
```

## Layout

```text
openspec/
  specs/           # source of truth (system behavior today)
  changes/         # in-flight change folders
  changes/archive/ # dated completed changes
  config.yaml      # project context for agents
```

Install CLI when ready:

```bash
npm install -g @fission-ai/openspec
# or: npx @fission-ai/openspec init
openspec init
```

Until then, treat `docs/VISION.md` + `docs/adr/` + change folders under `openspec/changes/` as the intent layer.

**Prefer merge:** before `changes/<new>/`, scan active siblings — same subdomain,
UI surface, or follow-up of an open proposal → fold in; do not spawn duplicates.
See `.cursor/rules/openspec.mdc` and `changes/README.md`.
