"""Unit tests for natural-language cron hints."""

from gotit.core.cron_suggest import normalize_cron, suggest_cron_from_text


def test_normalize_cron() -> None:
    assert normalize_cron("0 8 * * *") == "0 8 * * *"
    assert normalize_cron("  30  9 * * * ") == "30 9 * * *"
    assert normalize_cron("bad") is None


def test_suggest_common_chinese() -> None:
    assert suggest_cron_from_text("每天早上9点") == "0 9 * * *"
    assert suggest_cron_from_text("每天晚上9点") == "0 21 * * *"
    assert suggest_cron_from_text("每天早上八点半") == "30 8 * * *"
    assert suggest_cron_from_text("21:30") == "30 21 * * *"
    assert suggest_cron_from_text("每天 8:00") == "0 8 * * *"


def test_suggest_english_ampm() -> None:
    assert suggest_cron_from_text("9am every day") == "0 9 * * *"
    assert suggest_cron_from_text("9 pm") == "0 21 * * *"
