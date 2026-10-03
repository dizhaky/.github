@AGENTS.md

Tests pin these strings here (`tests/test_review_runbook.py`, `tests/test_reusable_workflows.py`):

- Test: `TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests`
- Runner policy: DAN-4030 (see AGENTS.md → Self-hosted runner policy).
