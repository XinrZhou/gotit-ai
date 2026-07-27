"""Eval harness: cases, holdout runs, and verdicts (skeleton)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Case:
    id: str
    material: str
    expected_pass: bool | None = None


def load_cases(directory: Path) -> list[Case]:
    """Load JSON/YAML cases later; empty list for now."""
    if not directory.exists():
        return []
    return []


def run_holdout(cases: list[Case]) -> dict[str, object]:
    """Placeholder holdout runner — returns a keep_observe verdict."""
    return {
        "verdict": "keep_observe",
        "case_count": len(cases),
        "message": "harness runner not wired yet",
    }
