# Architecture Review — AI Engineering Depth

> Role lens: AI Application Engineer interviewer · Principal AI Engineer · Agent system architecture reviewer.
>
> Scope: judge how gotit becomes a competitive **AI Agent Application** — not a chatbot.
>
> Product north star: long-term technical growth companion
> (`user state → learn assist → ability assess → long-term memory → continuous feedback`).
>
> Date: 2026-08-03. Based on `docs/SYSTEM.md`, `docs/PRODUCT.md`, `docs/VISION.md`, and shipped verify/memory/harness design — not a line-by-line code audit.

---

## Verdict (one screen)

**Classification:** Agent Application with an **LLM Workflow spine** — not a Chatbot Wrapper; not an open Multi-Agent System.

**Competitive edge:** not “agents that call tools in chat,” but a **auditable mastery state machine** — LLM produces evidence; code owns truth.

**Hardest AI Eng floor already shipped:** LLM cannot unilaterally pass mastery or pollute writeback paths.

**Largest AI Eng gap:** Reliability harness proves *we don’t corrupt state*; we still lack a closed loop that proves *teaching got better* (learner outcomes → agent policy).

---

## 1. Agent Architecture

### Taxonomy

| Label | Fit |
|-------|-----|
| Chatbot Wrapper | No |
| LLM Workflow | Yes — core spine |
| Agent Application | Yes — product form |
| Multi-Agent System | Partial — role cast, not open collaboration platform |

**Why:** Multiple named agents, A2A handoff, and a companion tool whitelist sit on top of a **product-defined Verify Workflow**. Autonomy is intentionally short; state transitions are the real “agent.”

Correct interview phrasing:

> Role-specialized agents inside a fixed verify spine.

Incorrect:

> We built a multi-agent system because we have five personas.

### Dimension scorecard

| Dimension | Reality | Depth |
|-----------|---------|-------|
| **Planning** | Decomposition lives mostly in product logic: owed queue, plan items, `check_routing`, CAT, spaced review. Companion does not invent multi-step learning plans. | Plans *what to practice*; almost no agent self-planning |
| **Execution** | Companion tools are largely **prepare-only** (open examine / teach / drill). Mastery close runs through finalize. | Semi-autonomous: can act, cannot alone close mastery |
| **Tool Calling** | Real: builtin whitelist → `db.ops`; MCP for OpenClaw hosts; full MCP catalog is **not** auto-mounted into chat | Controlled capability, not open tool soup |
| **State Management** | Strong: claim / mastery / ball custody / day_closed / owed / prepare vs closed | Primary source of “agent feel” |
| **Reflection** | Critic recheck + `deterministic_gate` (stricter-of-two; score/evidence can only downgrade). Not a free ReAct self-critique loop | Cross-role review + code final judge |

### Architecture diagram (conceptual)

```text
Learner surface (Chat / workflows / MCP host)
        │
        ▼
Companion agents (identity + tools + handoff)
        │  prepare / narrate / examine / teach
        ▼
Verify spine: Axiom → Critic → deterministic_gate
        │
        ▼
Single mastery write path (write_mastery_outcome)
        │
        ▼
Long-lived learner state (claims, schedule, fail graph, digests)
```

---

## 2. Memory Architecture

**Not** conversation-history-only.  
**Is** claim-centric long-term learner state; chat is an entry, not the source of truth.

| Capability | Present? | Shape |
|------------|----------|-------|
| User Profile | Light | resume / prefs / bootcamp / interview — not a thick psychographic |
| Skill State | Yes (core) | claim mastery, `preferred_check_mode`, due / `next_review_at` |
| Knowledge State | Yes | notes → claims; authority on claim rows, not chat summaries |
| Historical Experience | Yes | fail_events, trajectory, failure_digest, confuse edges |
| Growth Tracking | Yes (explainable) | spaced review, mastery graph, CAT item params, Brief `due_reason_*` |

### Design ideas that matter

1. **Authority split** — mastery / structured fail live on claim / graph; `memory_entries` must not become the mastery oracle.
2. **Context on a budget** — re-practice injects failure lessons + graph neighbors with hard trim (VISION P4).
3. **Fail is useful** — misses are first-class state for schedule and re-injection, not disposable logs.

### Honest boundary

This is a **Mastery Graph + Schedule State**, not a full user mental model or open knowledge graph. For a personal growth agent, that is the right cut — not “unfinished RAG.”

---

## 3. LLM Reliability

Strongest AI Engineering cut in the project: clearer than most Agent demos.

### Responsibility split

| Concern | Owner |
|---------|-------|
| Understand / generate / explain / converse / Critic opinion | LLM |
| Mastery band / schedule / writeback / CTA routing / item-param update | Code |
| Authoritative persistence | `write_mastery_outcome` / shared finalize paths |

### Anti-pollution mechanisms (engineering, not prompt theater)

- **Gate is deterministic code, never an LLM** (VISION P7).
- Critic cannot unilaterally pass; low score / empty evidence **downgrade only**.
- Companion tools: **prepare ≠ mastery write**; stub without `LLM_API_KEY` does not fake writes.
- Harness contracts include `no_spurious_write` / `gate_consistent` (and related rollups).
- REST ↔ MCP share `db.ops` + the same finalize path — reduces dual-path drift.

**Judgment:** LLM owns generation; code owns truth.  
Remaining risk is **upstream generative validity** (does the probe actually test the claim?) — not uncontrolled state mutation. That is the next layer, not an unfinished floor.

---

## 4. Evaluation System

| Kind | Status |
|------|--------|
| Rule-based | Yes — gate, schedule, routing, gate signals, CAT params |
| LLM judge | Yes — Critic as **advisor**, not final court |
| User feedback | Yes — mastery chips / Done bar / harness `adopt\|observe\|reject` |
| Quality metrics | Partial — harness rollups offline; weak online learner-outcome loop |

### What this already buys

“Will the system corrupt mastery?” becomes a **regression contract** — rare maturity for Agent Applications.

### What absence costs

1. **Safe ≠ effective** — gate consistency does not prove the learner was taught.
2. Adopt remains audit-only — evolution has discipline, not yet evidence-driven auto-strengthen.
3. Hard interview question unanswered: *How do you know Axiom got better last month?*

---

## 5. Design-thought comparison with clowder-ai

Reference: [clowder-ai](https://github.com/zts212653/clowder-ai).  
**No feature checklist. No code compare.** Design ideology only.

| | Clowder | Gotit |
|---|---------|-------|
| North star | Platform that turns isolated models into a **collaborating team** | Verify loop that turns “feels fluent” into **schedulable mastery state** |
| Floor slogan | Models set the ceiling; platform sets the floor | Verified = done; gate is code |
| Memory | Institutional evidence / lessons / decisions for co-creation | Claim / fail / schedule authority for growth |

### Worth borrowing

1. **Three-layer split** — model reasons; platform owns memory, discipline, identity.
2. **Stable persona serves stable judgment** — character is a rubric anchor, not cosplay.
3. **Evidence as institutional memory** — fail→lesson→recheck is the same family as shared lessons/decision logs.
4. **Eval-before-adopt** — prompt/skill change needs holdout evidence (VISION P5); push further toward explicit contracts.
5. **Hard rails in code** — iron laws enforced by system, not model obedience.

### Do not copy

1. **Open multi-agent collab platform** — gotit’s domain is mastery, not “idea → product” team OS; copying dilutes Verified=done.
2. **Raising agent planning autonomy as the default** — conflicts with the product stance of not lengthening agent autonomy for its own sake.
3. **Self-evolution as the hero story** — grow the learner’s state first; agent self-improvement is secondary.
4. **“Dumb system + smart agent” open knowledge search as mastery authority** — gotit needs code-held truth for pass/fail.
5. **CVO / co-creation team metaphor** — the learner needs an honest examiner + steady companion, not a software cat crew.

---

## 6. Final evaluation

### Most valuable technical story (one line)

**Through an “LLM evidence → Critic recheck → deterministic gate → single mastery writeback” verify spine, gotit turns a stateless generator into a cross-day, pollution-resistant learner mastery state machine — chat is the shell; mastery is the truth.**

### Largest technical shortfall (AI Engineering, not feature laundry)

**Missing learner-outcome → agent-policy measurement loop.**

Offline harness can prove *we don’t corrupt state*, but cannot continuously answer *did teaching improve* — probe validity, check-mode routing quality, and whether lesson injection raises re-pass rates are not yet online evidence that drives policy/prompt evolution.

That is the gap between:

- a highly disciplined verify-workflow product, and
- a growth Agent Application that can **prove it is getting stronger**.

---

## Competitive path (keep the iron laws)

Do not weaken:

- Gate stays in code.
- Mastery stays in authoritative state.
- Agents stay bounded (prepare vs finalize).

Next cut:

> Extend harness from **anti-corruption** to **anti-ineffectiveness** — bind retention / re-pass / due-clearance signals back into routing, injection budget, and examiner/critic policy.

That is the AI-native story that separates gotit from chatbots and from general multi-agent platforms.
