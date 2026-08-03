# Tasks: form-follows-claim

## 1. Core + schema

- [x] `Claim.preferred_check_mode` + `ClaimRow` + alembic `0014`
- [x] `core/check_routing.py` (resolve / route / suggest) + unit tests
- [x] `_claim_view` + note ingest persist + heuristic

## 2. API / companion

- [x] `owed_claim_block` / verdict actions use routing
- [x] `PATCH /v1/claims/{id}` preferred_check_mode
- [x] companion `start_verify` + `open_teach` lift in orchestrator

## 3. Web

- [x] types + `lib/checkRouting`
- [x] DailyBrief CTA by mode
- [x] ActionBlocks / ToolTrail `start_teach` / open_teach
- [x] ChatPage `startVerifyClaim` (+ pending ingest handoff)

## 4. Docs

- [x] `docs/SYSTEM.md` + openspec README
- [x] Check off tasks when done
