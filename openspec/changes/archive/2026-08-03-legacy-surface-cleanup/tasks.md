# Tasks: legacy-surface-cleanup

- [x] Drop chat_messages model/ops/routes + ChatMessageView
- [x] alembic `0015_drop_chat_messages`
- [x] Remove VerifyLoop; update test_loop + core.__init__
- [x] Remove Redis dep / compose / settings
- [x] Sync SYSTEM (+ README if needed)
- [x] `uv run pytest tests/test_loop.py tests/test_day_ops.py tests/test_gate_signals.py -q`
