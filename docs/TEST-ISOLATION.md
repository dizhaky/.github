# Test-Suite Isolation Standard

> **Canonical URL:** [dizhaky/.github — TEST-ISOLATION.md](https://github.com/dizhaky/.github/blob/main/docs/TEST-ISOLATION.md)  
> **Applicability:** All Python and multi-language repositories across `dizhaky/*`

---

## 1. Purpose & Problem Statement

Developer workstations, local agent sessions, and CI runners are stateful environments. A developer machine typically hosts live SQLite databases (`~/.app-state/state.db`, `kanban.db`), live Obsidian vaults, real CRM directories, active logging streams (`~/.app-state/logs/agent.log`), and live API keys in the environment or macOS Keychain.

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
│ 3. State Path Redirection      │ Redirect configured state roots to tmpdir; │
│    & Repository Guards         │ add app-specific DB and write guards.       │
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
DEFAULT_DB_PATH = Path(os.environ.get("APP_HOME", Path.home() / ".app-state")) / "state.db"
```
Or initializes file logging at module scope:
```python
# main.py
setup_logging()  # Attaches FileHandler to ~/.app-state/logs/agent.log
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

if not os.environ.get("APP_TEST_ISOLATED"):
    _SESSION_TMP_DIR = tempfile.mkdtemp(prefix="repo-test-sandbox-")
    os.environ["APP_HOME"] = _SESSION_TMP_DIR
    os.environ["APP_TEST_ISOLATED"] = "1"
    atexit.register(shutil.rmtree, _SESSION_TMP_DIR, True)
```

---

### Principle 2: Default-Deny Credential Pattern Scrubbing

**Problem:** Developers export API keys in their shell profiles (`.zshrc`, `.env`). Tests that test "fallback to provider when key is present" or unauthenticated failure paths will behave differently locally versus in CI. Ambient credentials can also allow mocked client bypasses to hit live APIs.

**Rule:**
- Blank out all credential-bearing environment variables at `conftest.py` module scope before project modules are collected, then repeat the scrub in an autouse fixture so individual tests cannot inherit credentials added later.
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

### Principle 3: State Path Redirection & Repository-Specific Guards

**Problem:** Repositories interacting with persistent state (vaults, CRM systems, knowledge bases, and memory daemons) use environment variables to locate state directories.

**Rule:**
- Isolate all known state root variables to temporary test directories:
  - Application-specific variables such as `APP_HOME`, `APP_STATE_DIR`, and `APP_DB_PATH`
  - `OBSIDIAN_VAULT*` / `CRM_*`: `CRM_VAULT_ROOT`, `CRM_STATE_DIR`, `OBSIDIAN_VAULT`
  - `KB_*`: `KB_ROOT`, `KB_STATE_DIR`
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

**Rule:** Set process-wide determinism flags before starting Python, in CI or the
test runner. A fixture is too late to choose the current interpreter's hash seed
or initialize its locale. Repository code that changes `TZ` inside a running
process must also call `time.tzset()` where the platform supports it.
```yaml
env:
  TZ: UTC
  LANG: C.UTF-8
  LC_ALL: C.UTF-8
  PYTHONHASHSEED: '0'
  AWS_EC2_METADATA_DISABLED: 'true'
  AWS_METADATA_SERVICE_TIMEOUT: '1'
  AWS_METADATA_SERVICE_NUM_ATTEMPTS: '1'
```

---

## 3. Canonical `conftest.py` Blueprint

This minimal scaffold redirects configured paths and scrubs ambient credentials before test collection. Adapt it into `<repo>/tests/conftest.py`; it is **not an OS sandbox** and does not by itself block arbitrary filesystem, database, subprocess, keychain, or network access. Run untrusted or integration tests in a disposable container with no secrets and denied outbound network, and add repository-specific write/DB/client guards before claiming fail-closed isolation.

Keep session paths stable for modules that cache them during import. Tests needing distinct paths must inject paths explicitly or use a separate process, rather than changing the environment underneath cached constants. Set `PYTHONHASHSEED=0` in the invoking shell or CI **before Python starts**; setting it in a fixture affects child interpreters only.

```python
"""Baseline test configuration and fixtures.

Provides a safe baseline for:
1. Import-time sandboxing of persistent state directories
2. Default-deny credential pattern scrubbing
3. Configured state path redirection (not an OS write guard)
4. Browser/UI neutralization during test execution

Add repository-specific network, keychain, database, and filesystem guards.
"""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── 1. IMPORT-TIME STATE SANDBOXING ─────────────────────────────────────────
# Configure every state root consumed by the project before importing it.

# Create session-level temporary sandbox directory
_SESSION_SANDBOX = tempfile.mkdtemp(prefix="test-sandbox-")
os.environ["APP_HOME"] = str(Path(_SESSION_SANDBOX) / "app-state")
os.environ["CRM_VAULT_ROOT"] = str(Path(_SESSION_SANDBOX) / "vault")
os.environ["CRM_STATE_DIR"] = str(Path(_SESSION_SANDBOX) / "crm_state")
os.environ["KB_STATE_DIR"] = str(Path(_SESSION_SANDBOX) / "kb_state")

# Record for import-time assertion in guard tests
APP_HOME_AT_CONFTEST_IMPORT = os.environ.get("APP_HOME", "")

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


# Fixtures run after collection: scrub once now, before any project import.
for _name in list(os.environ):
    if _is_credential_var(_name):
        os.environ.pop(_name, None)


# ── 3. HERMETIC ENVIRONMENT AUTOUSE FIXTURE ─────────────────────────────────
@pytest.fixture(autouse=True)
def _hermetic_environment(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Scrub credentials and disable IMDS for clients initialized per test."""
    # A. Scrub all credential-bearing environment variables
    for var_name in list(os.environ.keys()):
        if _is_credential_var(var_name):
            monkeypatch.delenv(var_name, raising=False)

    # B. Disable AWS EC2 Metadata lookups for child clients initialized in tests
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_METADATA_SERVICE_TIMEOUT", "1")
    monkeypatch.setenv("AWS_METADATA_SERVICE_NUM_ATTEMPTS", "1")

    # C. Keep import-time state paths stable; inject per-test paths explicitly.
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
"""Run pytest itself so the real conftest lifecycle is exercised."""
import os
from pathlib import Path
import shutil
import subprocess
import sys


def test_collection_isolation(tmp_path):
    # A non-package directory avoids importing tests.conftest a second time.
    shutil.copyfile(Path(__file__).with_name("conftest.py"), tmp_path / "conftest.py")
    (tmp_path / "test_probe.py").write_text(
        'import os\n'
        'assert "TEST_SERVICE_API_KEY" not in os.environ\n'
        'assert "LINEAR_API_KEY" not in os.environ\n'
        'assert os.environ["CRM_STATE_DIR"] != "ambient-state-sentinel"\n'
        'def test_probe(): pass\n'
    )
    env = {
        "PATH": os.environ["PATH"], "HOME": str(tmp_path),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONHASHSEED": "0",
        "TEST_SERVICE_API_KEY": "sentinel", "LINEAR_API_KEY": "sentinel",
        "CRM_STATE_DIR": "ambient-state-sentinel",
    }
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(tmp_path / "test_probe.py")],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
```

---

## 5. Adoption Checklist for Repositories

When creating or maintaining a repository:

- [ ] **`tests/conftest.py`**: Sandboxes state environment variables at module scope (before project imports).
- [ ] **Credential Filter**: Module initialization and the autouse fixture scrub `_CREDENTIAL_SUFFIXES` and `_CREDENTIAL_NAMES`.
- [ ] **Deterministic Flags**: Set timezone, locale, hashseed, and IMDS variables before invoking Python.
- [ ] **Keychain Neutralization**: Add and test repository-specific guards for every keychain access path; the baseline scaffold does not provide this.
- [ ] **Guard Test**: `tests/test_isolation_guard.py` proves pre-collection credential scrubbing and configured-path redirection. Add separate tests for network, database, subprocess, and filesystem guards.
