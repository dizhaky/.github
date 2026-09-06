"""Import-time isolation for the repository's template tests."""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

import pytest

_SESSION_ROOT = Path(tempfile.mkdtemp(prefix="github-template-tests-"))
atexit.register(shutil.rmtree, _SESSION_ROOT, True)

for _name, _value in {
    "HOME": _SESSION_ROOT,
    "XDG_CACHE_HOME": _SESSION_ROOT / "cache",
    "XDG_CONFIG_HOME": _SESSION_ROOT / "config",
    "XDG_DATA_HOME": _SESSION_ROOT / "data",
    "XDG_STATE_HOME": _SESSION_ROOT / "state",
}.items():
    os.environ[_name] = str(_value)

_CREDENTIAL_SUFFIXES = (
    "_API_KEY",
    "_TOKEN",
    "_SECRET",
    "_PASSWORD",
    "_CREDENTIALS",
    "_ACCESS_KEY",
    "_AES_KEY",
    "_ENCRYPT_KEY",
    "_PRIVATE_KEY",
    "_OAUTH_TOKEN",
)
_CREDENTIAL_NAMES = frozenset(
    {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"}
)


def _is_credential(name: str) -> bool:
    return name in _CREDENTIAL_NAMES or name.endswith(_CREDENTIAL_SUFFIXES)


def _scrub_credentials() -> None:
    for name in list(os.environ):
        if _is_credential(name):
            os.environ.pop(name, None)


_scrub_credentials()
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"


@pytest.fixture(autouse=True)
def _isolate_each_test(monkeypatch):
    for name in list(os.environ):
        if _is_credential(name):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
