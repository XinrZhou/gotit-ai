"""Messaging layer — threads, @mention routing, ball-custody handoff.

Framework-free: routing is pure logic over the `Message` / `BallCustody` DTOs.
DB-backed ops live in `gotit.db.ops.thread`.
"""

from __future__ import annotations

from gotit.core.models import BallCustody, Message

DEFAULT_AGENT = "axiom"


def route_message(
    message: Message,
    ball: BallCustody | None = None,
) -> str:
    """Decide which agent handles a message.

    Priority: explicit @mention > current ball holder (verify-loop) > default.
    """
    if message.mentions:
        return message.mentions[0]
    if ball is not None:
        return ball.holder
    return DEFAULT_AGENT
