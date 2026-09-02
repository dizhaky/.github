# Test-Suite Isolation Standard

> **Canonical URL:** [dizhaky/.github — TEST-ISOLATION.md](https://github.com/dizhaky/.github/blob/main/docs/TEST-ISOLATION.md)  
> **Applicability:** All Python and multi-language repositories across `dizhaky/*`

---

## 1. Purpose & Problem Statement

Developer workstations, local agent sessions, and CI runners are stateful environments. A developer machine typically hosts live SQLite databases (`~/.hermes/state.db`, `kanban.db`), live Obsidian vaults, real CRM directories, active logging streams (`~/.hermes/logs/agent.log`), and live API keys in the environment or macOS Keychain.

When automated test suites run, **unisolated suites risk severe state corruption and credential leakage**:

1. **State Mutation & Log Pollution:** Test execution can write bogus session rows to `state.db`, create fake tasks on real Kanban boards, modify real Obsidian notes, or spew hundreds of test-generated error logs into `agent.log`.
2. **Accidental Live API Calls:** Tests executing with ambient developer credentials can trigger real external network requests (e.g. creating real Linear tickets, sending Slack alerts, or incurring billable LLM API usage).
3. **Flaky & Environment-Dependent Failures:** Tests that rely on ambient environment state fail when run in different timezones, locales, hash seeds, or on CI runners lacking local services (such as AWS IMDS timeouts).

### The Invariant

> **A test suite running in any environment (local workstation, CI runner, agent subprocess, or Docker container) must be hermetic and fail-closed.**
> Test execution must **never** leak writes to real state paths or read live credentials.

---

## 2. The 5 Core Principles of Test Isolation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       5 CORE PRINCIPLES OF TEST ISOLATION                   │
├────────────────────────────────┬────────────────────────────────────────────┤
│ 1. Import-Time Sandboxing      │ Redirect state in conftest.py BEFORE any   │
│                                │ product/test module is imported.           │
├────────────────────────────────┼────────────────────────────────────────────┤
│ 2. Default-Deny Credential     │ Scrub all credential-shaped env vars       │
│    Pattern Scrubbing           │ (_API_KEY, _TOKEN, _SECRET, etc.).         │
├────────────────────────────────┼────────────────────────────────────────────┤
│ 3. State Path Sandboxing       │ Redirect HERMES_*, VAULT_*, CRM_*, KB_* to │
│    & Fail-Closed Guards        │ tmpdir; intercept writes to real paths.    │
├────────────────────────────────┼────────────────────────────────────────────┤
│ 4. OS Keychain & Platform      │ Neutralize macOS Keychain / security CLI   │
│    Isolation                   │ lookups and browser/audio popups.          │
├────────────────────────────────┼────────────────────────────────────────────┤
│ 5. Deterministic Runtime       │ Pin TZ=UTC, LANG=C.UTF-8, PYTHONHASHSEED=0 │
│                                │ and disable AWS EC2 metadata lookups.      │
└────────────────────────────────┴────────────────────────────────────────────┘
```

---

### Principle 1: Import-Time Sandboxing

**Problem:** In `pytest`, test collection imports product modules *before* any test fixtures (even `autouse=True` fixtures) execute. If a product module computes a module-level constant at import time:
```python
# product_module.py
DEFAULT_DB_PATH = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "state.db"
```
Or initializes file logging at module scope:
```python
# main.py
setup_logging()  # Attaches FileHandler to ~/.hermes/logs/agent.log
```
An autouse fixture running during test setup is **too late**—the handler or constant has already bound to the developer's real filesystem path.

**Rule:**
- `conftest.py` must sandbox state environment variables **at top-level module scope** before any other project import occurs.
- Use direct assignment (`os.environ["KEY"] = ...`), **never** `os.environ.setdefault()`. `setdefault` defers to pre-exported shell variables, rendering the guard useless on developer machines where the variable is already exported.
- Register temporary directory cleanup using `atexit.register()`.

```python
# conftest.py (top of file)
import atexit
import os
import shutil
import tempfile

if not os.environ.get("HERMES_TEST_ISOLATED"):
    _SESSION_TMP_DIR = tempfile.mkdtemp(prefix="repo-test-sandbox-")
    os.environ["HERMES_HOME"] = _SESSION_TMP_DIR
    os.environ["HERMES_TEST_ISOLATED"] = "1"
    atexit.register(shutil.rmtree, _SESSION_TMP_DIR, True)
```

---

### Principle 2: Default-Deny Credential Pattern Scrubbing

**Problem:** Developers export API keys in their shell profiles (`.zshrc`, `.env`). Tests that test "fallback to provider when key is present" or unauthenticated failure paths will behave differently locally versus in CI. Ambient credentials can also allow mocked client bypasses to hit live APIs.

**Rule:**
- Blank out all credential-bearing environment variables before every test via an autouse fixture.
- Match on standard credential suffixes (`_CREDENTIAL_SUFFIXES`) and explicit known credential names (`_CREDENTIAL_NAMES`).

**Standard Credential Suffixes:**
- `_API_KEY`
- `_TOKEN`
- `_SECRET`
- `_PASSWORD`
- `_CREDENTIALS`
- `_ACCESS_KEY`
- `_SECRET_ACCESS_KEY`
- `_PRIVATE_KEY`
- `_OAUTH_TOKEN`
- `_WEBHOOK_SECRET`
- `_ENCRYPT_KEY`
- `_APP_SECRET`
- `_CLIENT_SECRET`
- `_CORP_SECRET`
- `_AES_KEY`

**Exact Credential Names:**
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`
- `LINEAR_API_KEY`
- `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `ANTHROPIC_TOKEN`
- `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY`, `XAI_API_KEY`, `MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`
- `GITHUB_TOKEN`, `GH_TOKEN`, `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`
- `CLAUDE_CODE_OAUTH_TOKEN`, `BROWSERBASE_API_KEY`, `FIRECRAWL_API_KEY`, `EXA_API_KEY`, `TAVILY_API_KEY`

---

### Principle 3: State Path Sandboxing & Fail-Closed Guards

**Problem:** Repositories interacting with persistent state (Hermes, Obsidian Vault, CRM, Knowledge Base, Memory daemons) use environment variables to locate state directories.

**Rule:**
- Isolate all known state root variables to temporary test directories:
  - `HERMES_*`: `HERMES_HOME`, `HERMES_KANBAN_HOME`, `HERMES_KANBAN_DB`, `HERMES_SESSION_*`
  - `OBSIDIAN_VAULT*` / `CRM_*`: `CRM_VAULT_ROOT`, `CRM_STATE_DIR`, `OBSIDIAN_VAULT`
  - `KB_*`: `KB_STATE_DIR`, `KB_API_TOKEN`
  - `MEMORY_*`: `PERSISTENT_MEMORY_PATH`, `MEMORY_DB_PATH`
- **Fail-Closed Write Guards (Deny-List):** Capture the real user home / state root *before* sandboxing rewires the environment. Install defensive wrappers around database connection functions (e.g. `sqlite3.connect` or domain-specific DB connect functions) that reject any target path resolving inside the operator's real directory tree.

---

### Principle 4: OS Keychain & Platform Isolation

**Problem:** macOS developer environments allow Python libraries or CLI wrappers to query the macOS Keychain (e.g., via `security find-generic-password` or `keyring`). A test reading the Keychain can silently pick up production credentials.

**Rule:**
- Intercept and mock Keychain resolution helpers (e.g. patching `_security_bin` to return `None` or patching credential resolution routines to read exclusively from test-controlled environment variables).
- Neutralize disruptive OS interactions:
  - Patch `webbrowser.open*` to record invocations rather than launching browser windows.
  - Neutralize audio/TTS playback systems.

---

### Principle 5: Deterministic Runtime Environment

**Problem:** Subtle discrepancies between local developer shells and CI lead to non-deterministic test failures:
- Timestamps formatted with local timezones instead of UTC.
- String sorting and collation varying across locales.
- Dictionary and set iteration order changing across runs without fixed hash seeds.
- AWS SDK initialization attempting to reach the EC2 Instance Metadata Service (IMDS) at `169.254.169.254`, causing 2-second timeout hangs per test.

**Rule:**
In the autouse fixture, enforce:
```python
monkeypatch.setenv("TZ", "UTC")
monkeypatch.setenv("LANG", "C.UTF-8")
monkeypatch.setenv("LC_ALL", "C.UTF-8")
monkeypatch.setenv("PYTHONHASHSEED", "0")
monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
monkeypatch.setenv("AWS_METADATA_SERVICE_TIMEOUT", "1")
monkeypatch.setenv("AWS_METADATA_SERVICE_NUM_ATTEMPTS", "1")
```

---

## 3. Canonical `conftest.py` Blueprint

Below is the standard, production-tested blueprint for Python repositories. Copy and adapt this into `<repo>/tests/conftest.py`.

```python
"""Canonical hermetic test configuration and fixtures.

Enforces the 5 Core Principles of Test Isolation:
1. Import-time sandboxing of persistent state directories
2. Default-deny credential pattern scrubbing
3. State path sandboxing & fail-closed write guards
4. OS Keychain and platform isolation
5. Deterministic runtime environment (TZ, LANG, hashseed, IMDS)
"""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── 1. IMPORT-TIME STATE SANDBOXING ─────────────────────────────────────────
# Capture the REAL pre-sandbox roots BEFORE rewiring environment variables.
_REAL_USER_HOME = Path.home().resolve()
_PRE_SANDBOX_HERMES_HOME = os.environ.get("HERMES_HOME", "")
_PRE_SANDBOX_VAULT_ROOT = os.environ.get("CRM_VAULT_ROOT", "")

# Create session-level temporary sandbox directory
_SESSION_SANDBOX = tempfile.mkdtemp(prefix="test-sandbox-")
os.environ["HERMES_HOME"] = str(Path(_SESSION_SANDBOX) / "hermes")
os.environ["CRM_VAULT_ROOT"] = str(Path(_SESSION_SANDBOX) / "vault")
os.environ["CRM_STATE_DIR"] = str(Path(_SESSION_SANDBOX) / "crm_state")
os.environ["KB_STATE_DIR"] = str(Path(_SESSION_SANDBOX) / "kb_state")

# Record for import-time assertion in guard tests
HERMES_HOME_AT_CONFTEST_IMPORT = os.environ.get("HERMES_HOME", "")

atexit.register(shutil.rmtree, _SESSION_SANDBOX, True)


# ── 2. CREDENTIAL PATTERN SCRUBBING RULES ───────────────────────────────────
_CREDENTIAL_SUFFIXES = (
    "_API_KEY",
    "_TOKEN",
    "_SECRET",
    "_PASSWORD",
    "_CREDENTIALS",
    "_ACCESS_KEY",
    "_SECRET_ACCESS_KEY",
    "_PRIVATE_KEY",
    "_OAUTH_TOKEN",
    "_WEBHOOK_SECRET",
    "_ENCRYPT_KEY",
    "_APP_SECRET",
    "_CLIENT_SECRET",
    "_CORP_SECRET",
    "_AES_KEY",
)

_CREDENTIAL_NAMES = frozenset({
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GROQ_API_KEY",
    "XAI_API_KEY",
    "MISTRAL_API_KEY",
    "DEEPSEEK_API_KEY",
    "OLLAMA_API_KEY",
    "LINEAR_API_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "SLACK_BOT_TOKEN",
    "SLACK_APP_TOKEN",
    "BROWSERBASE_API_KEY",
    "FIRECRAWL_API_KEY",
    "EXA_API_KEY",
    "TAVILY_API_KEY",
})


def _is_credential_var(name: str) -> bool:
    """Return True if an environment variable represents a secret/credential."""
    if name in _CREDENTIAL_NAMES:
        return True
    return any(name.endswith(suffix) for suffix in _CREDENTIAL_SUFFIXES)


# ── 3. HERMETIC ENVIRONMENT AUTOUSE FIXTURE ─────────────────────────────────
@pytest.fixture(autouse=True)
def _hermetic_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Isolate credentials, filesystem paths, and runtime determinism per test."""
    # A. Scrub all credential-bearing environment variables
    for var_name in list(os.environ.keys()):
        if _is_credential_var(var_name):
            monkeypatch.delenv(var_name, raising=False)

    # B. Deterministic runtime flags
    monkeypatch.setenv("TZ", "UTC")
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LC_ALL", "C.UTF-8")
    monkeypatch.setenv("PYTHONHASHSEED", "0")

    # C. Disable AWS EC2 Metadata lookups to prevent timeout latency
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_METADATA_SERVICE_TIMEOUT", "1")
    monkeypatch.setenv("AWS_METADATA_SERVICE_NUM_ATTEMPTS", "1")

    # D. Isolate filesystem paths per test
    test_hermes_home = tmp_path / "hermes_home"
    test_hermes_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(test_hermes_home))

    test_vault = tmp_path / "vault"
    test_vault.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CRM_VAULT_ROOT", str(test_vault))
    monkeypatch.setenv("CRM_STATE_DIR", str(tmp_path / "crm_state"))

    # E. Neutralize macOS Keychain lookups by default
    with patch("shutil.which", side_effect=lambda cmd: None if cmd == "security" else shutil.which(cmd)):
        yield


# ── 4. BROWSER & SYSTEM INTERACTION NEUTRALIZATION ──────────────────────────
@pytest.fixture(autouse=True)
def _neutralize_browser_and_ui(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Intercept browser opening attempts and prevent external UI popups."""
    import webbrowser

    opened_urls: list[str] = []

    def _mock_open(url: str, *args, **kwargs) -> bool:
        opened_urls.append(url)
        return True

    for attr in ("open", "open_new", "open_new_tab"):
        monkeypatch.setattr(webbrowser, attr, _mock_open, raising=False)

    return opened_urls
```

---

## 4. Import-Time Guard Test Contract (`test_isolation_guard.py`)

### The Verification Problem

A standard in-process test method cannot verify import-time sandboxing because `conftest.py` has already run inside that process. To guarantee that:
1. Pre-exported ambient environment variables do not leak into modules during import, and
2. A refactor did not remove the import-time sandboxing block,

every repository must maintain a **Guard Test** that spawns an isolated subprocess with explicit sentinels.

### Canonical Guard Test (`tests/test_isolation_guard.py`)

```python
"""Contract test verifying test suite isolation and import-time sandboxing."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_conftest_sandboxes_state_before_module_imports():
    """Verify that conftest.py redirects state paths at import time."""
    from tests.conftest import HERMES_HOME_AT_CONFTEST_IMPORT

    real_home = Path.home().resolve()
    assert HERMES_HOME_AT_CONFTEST_IMPORT, "conftest must set HERMES_HOME at import time"
    assert Path(HERMES_HOME_AT_CONFTEST_IMPORT).resolve() != real_home, (
        f"HERMES_HOME pointed at real home ({HERMES_HOME_AT_CONFTEST_IMPORT}) during conftest import"
    )


def test_subprocess_credential_scrubbing_contract():
    """Spawn a clean Python subprocess with fake exported keys and verify scrubbing."""
    probe_code = """
import os
import pytest
import sys

# Run pytest collection on an in-memory or dummy check
from tests.conftest import _is_credential_var

# Verify credential detection
assert _is_credential_var("TEST_SERVICE_API_KEY") is True
assert _is_credential_var("AWS_SECRET_ACCESS_KEY") is True
assert _is_credential_var("SAFE_CONFIG_PATH") is False
print("GUARD_PROBE_PASSED")
"""
    env = dict(os.environ)
    env["TEST_SERVICE_API_KEY"] = "sentinel-key-12345"
    env["LINEAR_API_KEY"] = "sentinel-linear-key"

    result = subprocess.run(
        [sys.executable, "-c", probe_code],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"Probe failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert "GUARD_PROBE_PASSED" in result.stdout
```

---

## 5. Adoption Checklist for Repositories

When creating or maintaining a repository:

- [ ] **`tests/conftest.py`**: Sandboxes state environment variables at module scope (before project imports).
- [ ] **Credential Filter**: Autouse fixture scrubs `_CREDENTIAL_SUFFIXES` and `_CREDENTIAL_NAMES`.
- [ ] **Deterministic Flags**: Autouse fixture sets `TZ=UTC`, `LANG=C.UTF-8`, `PYTHONHASHSEED=0`, `AWS_EC2_METADATA_DISABLED=true`.
- [ ] **Keychain Neutralization**: Intercepts macOS `security` CLI and keyring resolvers.
- [ ] **Guard Test**: `tests/test_isolation_guard.py` asserts fail-closed behavior.
