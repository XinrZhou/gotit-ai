"""Teach-back → shared verify finalize mapping (framework-free)."""

from __future__ import annotations


def teach_examine_verdict(you_taught_well: bool) -> str:
    """Map Echo boolean close to examine-scale verdict for Critic + gate.

    Teach has no middle ``almost`` from Echo; gaps close as ``owe_next``.
    """
    return "passed" if you_taught_well else "owe_next"
