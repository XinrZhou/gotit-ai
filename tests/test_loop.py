from gotit.core.loop import VerifyLoop
from gotit.core.models import Claim, LoopState


def test_verify_loop_happy_path() -> None:
    loop = VerifyLoop()
    assert loop.state == LoopState.INGEST

    loop.ingest_claims([Claim(text="Context budget beats dumping whole notes")])
    assert loop.state == LoopState.CLAIM

    loop.begin_examine()
    assert loop.state == LoopState.EXAMINE

    loop.begin_gate()
    assert loop.state == LoopState.GATE

    loop.mark_done()
    assert loop.state == LoopState.DONE
