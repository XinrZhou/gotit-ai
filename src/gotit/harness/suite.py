"""Harness suite version pin for adopt / CI (VISION P5).

Bump when replay/holdout contracts change in a way that invalidates prior
adopt decisions. Audit-only — does not auto-apply prompts.
"""

from __future__ import annotations

# Stamp on harness run summary + human adopt|observe|reject.
SUITE_VERSION = "2026.08.03.agent-runtime-v2.phase3"

__all__ = ["SUITE_VERSION"]
