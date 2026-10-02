# Gates: central AI delivery implementation

OWNS: scripts/ai_delivery.py, scripts/ai_proposal.py, scripts/ai-delivery-policy.json, scripts/read_ownership_feed.py, scripts/verify_ai_receipt.py, scripts/global_auto_merge.py, tests/test_ai_delivery.py, tests/test_global_auto_merge.py, tests/test_dependabot_auto_merge_template.py, tests/test_review_runbook.py, .github/workflows/auto-merge.yml, .github/workflows/dependabot-auto-merge.yml, .github/workflows/global-auto-merge.yml, .github/workflows/reusable-ai-delivery-guard.yml, .github/repo-templates/dependabot-auto-merge.yml, docs/ai-delivery.md, docs/global-auto-merge.md, docs/system-log/2026-10-02.md, AGENTS.md, CLAUDE.md, GATES.md

Plan: existing authenticated Mac, strict tool-free JSON proposals in an empty directory, mechanically validated patches, hardened Git, no-force repairs honoring configured/native signing, actual new-head native CI, fresh required reviews and renewable leases; controller is sole enrollment writer. Parent owns every remote mutation and runtime deployment.

- [x] C1: Offline tests prove ownership, no-tool proposals, protected paths, attempt budgets, lease chronology, repository fairness and current-head native delivery
  CHECK: TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/test_ai_delivery.py tests/test_global_auto_merge.py tests/test_dependabot_auto_merge_template.py tests/test_review_runbook.py
  EXPECT: passed
  EVIDENCE: Actual focused144 PASS in0.20s; final independent full suite evidence recorded below. Actual normalization7/7, Mac casealiases6/6, Git filter/hook/fsmonitor3sentinels and scheduler budget1/3 probes passed in parent rewrite/receipts.

- [x] C2: Existing repository regression suite remains green
  CHECK: TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q --tb=no tests
  EXPECT: passed
  EVIDENCE: Producer finalfull202 PASS,1skip,3subtests in28.73s; independent finalcheckpoint verification is in parent rewrite/receipts/verification.json. Durable independent output: parent rewrite/receipts/verifier-central-final-suite.txt.

- [x] C3: All changed workflows/templates and Python modules pass syntax checks
  CHECK: actionlint .github/workflows/auto-merge.yml .github/workflows/dependabot-auto-merge.yml .github/workflows/global-auto-merge.yml .github/workflows/reusable-ai-delivery-guard.yml .github/repo-templates/dependabot-auto-merge.yml && python3 -m py_compile scripts/ai_delivery.py scripts/ai_proposal.py scripts/global_auto_merge.py scripts/read_ownership_feed.py scripts/verify_ai_receipt.py && printf 'SYNTAX_PASS\n'
  EXPECT: SYNTAX_PASS
  EVIDENCE: All5YAML and5Python modules exit0; git diff--check exit0. Executable source stable at final fullsuite checkpoint.

- [x] C4: Typed manifest and runbook explicitly record prerequisites, runtime proofs and parent release intents without new credentials
  EVIDENCE: Parent rewrite/manifests/central.json records branch/base/current hashes,144focused/finalfull actualtests, exact tool-freeGPT5.5 backendPASS, fixed privatecomment readerPASS, real21-repo readonlycycles, fleetwriter retirement and target-specific signing and deployment/full-cycle release gates. All changed source hashes verified; docs and agentfiles updated. Independent integrity verifier consumes this manifest.

- [ ] C5: Parent deploys the loop and verifies one real repair/new-head native-CI/review/receipt/protected merge cycle honoring native signing
  EVIDENCE: Not deployed by this unit. Existing1Password SSH signing agent has0identities; only Organize main requires it natively in current inventory. Other20repos follow configured signing; parent requested narrowunlock for that target. Parent owns protected shipping, LaunchAgent, native AI-context activation and fullcycle; no remote mutations occurred in this unit.

ABANDON: C5 Delegated deployment/live complete-cycle ownership remains in parent rewrite/GATES.md and DAN-4186. This leaf hands off a verified local implementation; parent task remains open until protected release/live proof pass; missing required signing holds only its target.

## QC Verification
- Method: hermetic regression suite, fresh independent adversarial probes, actionlint, py_compile and typed SHA256 manifest; parent actual backend/feed/read-only API receipts.
- Scope: central controller, model boundary, ownership adapter, reporter/template retirement, tests and runbook.
- Before:2local enrollment writers plus1global setting/enrollment writer; no central AI repair controller.
- After:3read-only reporters plus1sole controller implementation; no remote changes from this leaf.
- Verdict: LOCAL PASS; deployment and complete live cycle BLOCKED in parent.
