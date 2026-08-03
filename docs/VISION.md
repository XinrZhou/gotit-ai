# Vision

**Got it? Prove it.** — with a companion that remembers you.

gotit-ai is a **daily learning companion**: a small crew of personality-bearing
agents that talk with you in threads, remember your weaknesses across sessions,
and pull you into a verification workflow when it's time to prove you actually
got it. Verification remains the **core loop** — mastery is a criterion
(pass the gate), not model praise — but the companion owns the conversational
surface; it is not a headless pipeline.

## Principles

| # | Principle | Meaning |
|---|-----------|---------|
| P1 | Verified = got it | Confidence is not evidence |
| P2 | Fail is useful | A miss becomes a small lesson + recheck, recorded on a trajectory |
| P3 | Form follows the claim | Probe, drill, apply, teach-back — pick what tests the idea |
| P4 | Context on a budget | Inject the claim under test, not the whole notebook |
| P5 | Harness-backed evolution | Prompt/skill changes need holdout evidence before adopt |
| P6 | Personality is stable, judgement is stable | Agents have persistent identities + pinned rubrics; rubric drift ≠ persona drift |
| P7 | The judge is deterministic code | The mastery gate is a threshold, never an LLM verdict |

## Loops

1. **Companion loop:** talk in a thread → @mention an agent → it replies in-character with memory → on demand triggers a verify-loop
2. **Verify loop (a workflow the companion runs):** examine (Axiom) → recheck (Critic, a different agent) → gate (deterministic) → queue / trajectory
3. **Learning trajectory:** every verify outcome is written back as memory, so the next session recalls your prior failure modes
4. **System evolution loop:** cases → harness → verdict → change → holdout → adopt
5. **Dev loop:** OpenSpec propose → implement → gate → archive

## Non-goals (for now)

- Being a second-brain note dump
- Replacing the learner's judgment on *what* to study
- Letting an LLM act as the mastery gate (the gate is deterministic code)
- Entertainment / companion-for-cute personas — personality serves judgement stability, not vibes
- Multi-user / OAuth

> Note: gotit now **owns** its learning chat surface. OpenClaw remains an
> *optional* distribution channel (gotit exposes MCP tools; OpenClaw can host
> them elsewhere), but the primary product is the in-app companion.
