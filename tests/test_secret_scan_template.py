"""Security regressions for the required secret-scan caller."""

import re
from pathlib import Path


TEMPLATE = Path(__file__).resolve().parents[1] / ".github/repo-templates/secret-scan.yml"
RECOVERY_DOC = Path(__file__).resolve().parents[1] / "docs/from-vault/ACCOUNT-OPS-SUPPLEMENT.md"
WORKFLOW_REF_RE = re.compile(
    r"^\s+uses: dizhaky/\.github/\.github/workflows/"
    r"reusable-secret-scan\.yml@([0-9a-f]{40})$",
    re.M,
)


def test_scanner_uses_immutable_commit():
    assert WORKFLOW_REF_RE.search(TEMPLATE.read_text())


def test_retargeted_pull_request_gets_fresh_scan():
    assert re.search(
        r"^  pull_request:\n    types: \[opened, synchronize, reopened, edited\]$",
        TEMPLATE.read_text(), re.M,
    )


def test_recovery_instructions_keep_the_scanner_pin():
    source = RECOVERY_DOC.read_text()
    template_match = WORKFLOW_REF_RE.search(TEMPLATE.read_text())
    assert template_match
    assert "reusable-secret-scan.yml@main" not in source
    assert f"reusable-secret-scan.yml@{template_match.group(1)}" in source
