# DAN-4466 preparation gates
OWNS: scripts/ai_delivery.py, scripts/ai_delivery_bundle.py, scripts/bootstrap_ai_delivery.py, scripts/ai_proposal.py protected-name additions, tests/test_ai_delivery_target.py, tests/test_ai_delivery_bundle.py, docs/ai-delivery.md readiness section, readiness/GATES.md, task-scoped system log.
No install, activation, --apply, live config, credentials, settings or held-repository writes.
- [x] T1: Exact repo/PR/head selection rejects malformed, stale and returned-identity drift; no fallback or unrelated repository discovery.
  CHECK: python3 -m pytest -q tests/test_ai_delivery_target.py
  EXPECT: passed
- [x] T2: Bundle determinism/integrity, default prepare-only behavior, fixed service scope, symlink/existing-target rejection and preserved data on uninstall.
  CHECK: python3 -m pytest -q tests/test_ai_delivery_bundle.py
  EXPECT: passed
- [x] T3: Existing native protection/ownership/review/signature/receipt tests still pass in isolated full suite.
  CHECK: TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests
  EXPECT: passed
- [x] T4: Reviewed artifact specifies installed hashes, exact-source gate, activation and rollback; no deployment success claimed.
  MANUAL: inspect final diff, generated disposable bundle and docs.

## QC Verification
- Method: isolated pytest suite, focused real subprocess import-shadow regression, mocked launchctl identity/rollback probes, independent fresh-context source review, git diff --check.
- Scope: exact-target selector and reproducible bundle only; no live install/activation, applying canary, paid scan or held-source edits.
- Before: protected signed source 7d3757da; 340 existing tests (1 intentionally skipped child-only probe); no installer/selector. Initial preparation had 2 confirmed review findings.
- After: 378 passed, 1 skipped, 3 subtests passed; 38 focused cases passed. Import-shadow and unrelated-service regressions fixed; independent reviewer approved. Diff whitespace clean.
- PASS: T1 identity/head gates and no discovery fallback; T2 integrity/disabled installation/strict rollback identity/data retention; T3 full suite; T4 independent reviewed docs and deterministic manifest tests. Native service readback remains an operational release gate.
- Artifact: prepare the clean signed branch with --output outside this repository; record exact source/manifest hashes in the task receipt after commit. A branch bundle cannot install before its source is the current protected default revision.
- Not claimed: full harden battery/dependency scans, installation, completed AI review, live protected canary, fleet instruction rollout or native CI before publication.
