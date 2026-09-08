"""Security regressions for the required secret-scan caller."""

import re
from pathlib import Path


TEMPLATE = Path(__file__).resolve().parents[1] / ".github/repo-templates/secret-scan.yml"
RECOVERY_DOC = Path(__file__).resolve().parents[1] / "docs/from-vault/ACCOUNT-OPS-SUPPLEMENT.md"


def test_scanner_uses_immutable_commit():
    assert re.search(
        r"^\s+uses: dizhaky/\.github/\.github/workflows/reusable-secret-scan\.yml@[0-9a-f]{40}$",
        TEMPLATE.read_text(), re.M,
    )


def test_retargeted_pull_request_gets_fresh_scan():
    assert re.search(
        r"^  pull_request:\n    types: \[opened, synchronize, reopened, edited\]$",
        TEMPLATE.read_text(), re.M,
    )


def test_recovery_instructions_keep_the_scanner_pin():
    source = RECOVERY_DOC.read_text()
    assert "reusable-secret-scan.yml@main" not in source
    assert (
        "reusable-secret-scan.yml@"
        "acdcf4d79a54c426087e39d358fad38686648455"
    ) in source
