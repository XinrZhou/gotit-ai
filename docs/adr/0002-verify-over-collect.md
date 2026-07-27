# ADR-0002: Verify-over-collect product floor

- Status: Accepted
- Date: 2026-07-27

## Context

Many study tools optimize for capture. gotit-ai exists to fight false fluency.

## Decision

Mastery defaults to **not yet**. Pass requires check evidence. Failures enter a recheck queue. Summarization-only paths are baselines for harness comparison, not the default product path.

## Consequences

- Feature work is judged by verification outcomes and harness verdicts.
- Storage/notes features are supporting infrastructure, not the hero.
