"""Identity card + chat system prompt composition."""

from datetime import UTC, datetime
from uuid import uuid4

from gotit.core.identity.loader import compose_system_prompt, identity_card
from gotit.core.models import AgentIdentity, PromptVersion


def _identity(**kwargs: object) -> AgentIdentity:
    now = datetime.now(UTC)
    base = dict(
        id=uuid4(),
        agent_name="axiom",
        display_name="章鱼哥",
        personality="精准考官。",
        role="examiner",
        llm_config={},
        memory_scope={},
        prompt_version_id=None,
        created_at=now,
        updated_at=now,
    )
    base.update(kwargs)
    return AgentIdentity(**base)  # type: ignore[arg-type]


def test_identity_card_chinese_first() -> None:
    card = identity_card(_identity())
    assert "章鱼哥" in card
    assert "绝不说英文代号" in card
    assert "冒充其他同伴" in card
    assert "职务说明书" in card
    assert "职责：" not in card


def test_chat_excludes_english_rubric() -> None:
    rubric = PromptVersion(
        id=uuid4(),
        agent_name="axiom",
        version_label="v1",
        content_hash="test",
        system_prompt="You are **Axiom** (章鱼哥), the examiner.",
        notes=None,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    chat = compose_system_prompt(_identity(), rubric, include_rubric=False)
    assert "You are **Axiom**" not in chat
    assert "你是「章鱼哥」" in chat
    assert "精准考官" in chat

    full = compose_system_prompt(_identity(), rubric, include_rubric=True)
    assert "You are **Axiom**" in full
    assert full.startswith("# 你是谁")


def test_build_chat_prompt_forces_self_intro() -> None:
    from gotit.core.agents.runtime import build_chat_prompt

    prompt = build_chat_prompt(
        user_text="hi，介绍下你自己",
        history=[],
        memory=[],
        display_name="派大星",
    )
    assert "【自我介绍】" in prompt
    assert "禁止反问爱好" in prompt
    assert "派大星" in prompt
    assert "误判" in prompt
