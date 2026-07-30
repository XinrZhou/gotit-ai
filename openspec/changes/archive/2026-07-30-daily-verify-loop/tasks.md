# daily-verify-loop — tasks

## Spec

- [x] proposal / design / tasks
- [x] SYSTEM (+ README if pitch drifts)
- [x] openspec/changes/README.md

## Backend

- [x] Shared finalize: Critic + gate + trajectory + mastery writeback
- [x] `/v1/examine` claim-close uses finalize (note/topic/single)
- [x] `/v1/threads/{id}/verify` calls same helper
- [x] Persist examine/recheck/gate fields in workflow metadata
- [x] Tests

## Frontend

- [x] Workspace loads `due_claims` from `/v1/today`
- [x] `DailyBrief` + wire Chat empty / empty thread
- [x] Examine: start by claim_id; picker shows owed + plan
- [x] `VerifyTrajectory` chips; ChatLog + ChatPage gate messages
