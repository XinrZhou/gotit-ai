"""Fixed personal-gold claim slugs for small-sample quality compare.

Stable *document* IDs (slugs) — harness creates fresh UUIDs at runtime.
See ``openspec/changes/archive/2026-07-30-companion-tools-and-schedule/notes-gold.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Verdict = Literal["passed", "almost", "owe_next"]


@dataclass(frozen=True)
class GoldClaim:
    slug: str
    text: str
    role: str
    # Expected examine/critic pair for offline gate cases (None = not a gate pair case).
    examine: Verdict | None = None
    critic: Verdict | None = None
    expect_gate: Verdict | None = None


GOLD_CLAIMS: tuple[GoldClaim, ...] = (
    GoldClaim(
        slug="gold-01-pointer",
        text="指针保存的是地址，不是对象本身",
        role="清晰过了",
        examine="passed",
        critic="passed",
        expect_gate="passed",
    ),
    GoldClaim(
        slug="gold-02-free-null",
        text="free 之后必须把指针置空，否则悬空",
        role="还差点边界",
        examine="almost",
        critic="almost",
        expect_gate="almost",
    ),
    GoldClaim(
        slug="gold-03-softmax",
        text="Softmax 把 logits 归一成概率分布",
        role="欠着下次",
        examine="owe_next",
        critic="owe_next",
        expect_gate="owe_next",
    ),
    GoldClaim(
        slug="gold-04-gate-code",
        text="gotit 的 gate 必须是确定性代码，不能交给 LLM",
        role="门分歧（考官宽、复核严）",
        examine="passed",
        critic="owe_next",
        expect_gate="owe_next",
    ),
    GoldClaim(
        slug="gold-05-attention",
        text="Self-Attention 用 Q/K 算权重再加权 V",
        role="门分歧（复核宽、考官严→仍严）",
        examine="almost",
        critic="passed",
        expect_gate="almost",
    ),
    GoldClaim(
        slug="gold-06-retest",
        text="验证闭环：examine → critic → gate → trajectory",
        role="再考转化",
        # First-round expected pair; second round handled in retest case.
        examine="owe_next",
        critic="owe_next",
        expect_gate="owe_next",
    ),
    GoldClaim(
        slug="gold-07-array-decay",
        text="数组名在多数表达式里会退化成指针",
        role="易混邻居 A",
    ),
    GoldClaim(
        slug="gold-08-stack-heap",
        text="栈对象离开作用域自动释放，堆需要显式 free",
        role="易混邻居 B",
    ),
)

# Confuse pair for documentation / future schedule cases (A ↔ B).
GOLD_CONFUSE_PAIR: tuple[str, str] = ("gold-07-array-decay", "gold-01-pointer")


def gate_pair_claims() -> list[GoldClaim]:
    return [c for c in GOLD_CLAIMS if c.expect_gate is not None and c.slug != "gold-06-retest"]


def by_slug(slug: str) -> GoldClaim:
    for c in GOLD_CLAIMS:
        if c.slug == slug:
            return c
    raise KeyError(slug)
