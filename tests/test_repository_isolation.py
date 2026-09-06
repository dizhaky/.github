"""Prove ambient paths and credentials are scrubbed before collection."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_PROBE = "GITHUB_TEMPLATE_ISOLATION_PROBE"
_SENTINEL = "LIVE-HOME-SENTINEL"


def test_child_probe():
    if _PROBE not in os.environ:
        pytest.skip("child-only isolation probe")
    assert _SENTINEL not in os.environ["HOME"]
    assert "TEST_SERVICE_API_KEY" not in os.environ
    assert "TEST_SERVICE_AES_KEY" not in os.environ
    assert "TEST_APP_ENCRYPT_KEY" not in os.environ
    assert os.environ["AWS_EC2_METADATA_DISABLED"] == "true"


def test_collection_isolation(tmp_path: Path):
    live_home = tmp_path / _SENTINEL
    live_home.mkdir()
    env = {
        **os.environ,
        "HOME": str(live_home),
        "TEST_SERVICE_API_KEY": "secret-sentinel",
        "TEST_SERVICE_AES_KEY": "secret-sentinel",
        "TEST_APP_ENCRYPT_KEY": "secret-sentinel",
        _PROBE: "1",
    }
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", f"{__file__}::test_child_probe"],
        cwd=Path(__file__).parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
