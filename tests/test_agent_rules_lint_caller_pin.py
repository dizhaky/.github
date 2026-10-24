"""Live caller docs must pin the hub composite, not the GH leftover."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STANDARD = ROOT / "rules" / "AGENT-INSTRUCTIONS-STANDARD.md"
HOST_DOC = ROOT / "docs" / "agent-rules-lint-host.md"
HUB_PIN = "dizhaky/.github/.github/actions/agent-rules-lint@40a05d9f2362b7e4621e83d789a7f563c262a8c6"
LEFTOVER_USES = re.compile(
    r"uses:\s*dizhaky/dotfiles/\.github/actions/agent-rules-lint@"
)


def test_standard_caller_template_pins_hub_composite():
    source = STANDARD.read_text()
    assert HUB_PIN in source
    assert LEFTOVER_USES.search(source) is None


def test_host_doc_caller_pin_matches_standard():
    source = HOST_DOC.read_text()
    assert HUB_PIN in source
    # Historical past-tense mention of the leftover path is fine; only
    # copy-paste `uses:` lines are forbidden for new callers.
    assert LEFTOVER_USES.search(source) is None
