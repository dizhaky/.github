"""Exact-target boundaries; no network, AI, settings or enrollment in dry-run."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ai_delivery as delivery
from ai_proposal import BoundaryError
from test_ai_delivery import delivery_flow, policy


@pytest.mark.parametrize("target", [(None, 1, "a" * 40), ("dizhaky/example", None, "a" * 40),
    ("dizhaky/example", 1, None), ("../example", 1, "a" * 40), ("dizhaky/..", 1, "a" * 40),
    ("dizhaky/example", True, "a" * 40), ("dizhaky/example", 0, "a" * 40),
    ("dizhaky/example", 1, "A" * 40), ("dizhaky/example", 1, "a" * 39)])
def test_bad_selector_fails_closed(target):
    with pytest.raises(BoundaryError, match="invalid_exact_target"):
        delivery.validate_target(*target)


def test_single_target_never_discovers_alternates(delivery_flow, monkeypatch):
    api, ledger = delivery_flow
    monkeypatch.setattr(api, "rate_limit_remaining", lambda: (1000, 1000), raising=False)
    monkeypatch.setattr(delivery, "owned_repositories", lambda *a: pytest.fail("fleet discovery"))
    result = delivery.cycle(api, ledger, policy(), target=("dizhaky/example", 1, "a" * 40), budget=1)
    assert result["target"]["head"] == "a" * 40 and result["processed"] == 1
    assert result["results"][0]["outcome"] == "would_review"
    assert api.actions == [] and ledger.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


@pytest.mark.parametrize("field,value", [("number", 2), ("number", True), ("head", {"sha": "b" * 40})])
def test_native_returned_identity_must_match(delivery_flow, field, value):
    api, ledger = delivery_flow
    api.pr[field] = value
    with pytest.raises(BoundaryError, match="target_identity_or_head_changed"):
        delivery.target_cycle(api, ledger, policy(), ("dizhaky/example", 1, "a" * 40))
    assert api.actions == []


def test_race_after_selection_blocks_before_any_write(delivery_flow, monkeypatch):
    api, ledger = delivery_flow
    original = delivery.precheck
    def precheck(*args):
        pr, reason, threads, reviews = original(*args)
        pr = copy.deepcopy(pr); pr["head"]["sha"] = "b" * 40
        return pr, reason, threads, reviews
    monkeypatch.setattr(delivery, "precheck", precheck)
    result = delivery.target_cycle(api, ledger, policy(), ("dizhaky/example", 1, "a" * 40), apply=True)
    assert result["results"][0]["reason"] == "target_head_changed"
    assert api.actions == []


@pytest.mark.parametrize("hold", ["draft", "claim", "stale", "review", "missing_check", "finding"])
def test_target_preserves_existing_gates_in_dry_run(delivery_flow, monkeypatch, hold):
    api, ledger = delivery_flow; p = policy()
    original = delivery.precheck
    def precheck(*args):
        pr, reason, threads, reviews = original(*args)
        if hold == "draft": reason = "draft_or_closed"
        if hold == "review": reason = "required_review_missing"
        if hold == "missing_check": reason = "no_required_checks"
        if hold == "finding": threads = [{"id": "finding"}]
        return pr, reason, threads, reviews
    monkeypatch.setattr(delivery, "precheck", precheck)
    if hold == "claim": p["leases"] = [{"repo": "dizhaky/example", "branch": "*", "expiresAt": "2099-01-01T00:00:00Z"}]
    if hold == "stale": p["leasesVerifiedAt"] = "2000-01-01T00:00:00Z"
    result = delivery.target_cycle(api, ledger, p, ("dizhaky/example", 1, "a" * 40))
    assert api.actions == []
    assert result["results"][0]["outcome"] == ("would_review" if hold == "finding" else "held")
    if hold == "finding": assert result["results"][0]["unresolvedThreads"] == 1


@pytest.mark.parametrize("extra", [["--repo", "dizhaky/example"],
    ["--repo", "dizhaky/example", "--pr", "1", "--head", "a" * 40],
    ["--repo", "dizhaky/example", "--pr", "1", "--head", "a" * 40, "--budget", "1", "--daemon"]])
def test_cli_rejects_partial_unbounded_or_daemon_target(tmp_path, monkeypatch, extra):
    monkeypatch.setattr(sys, "argv", ["ai_delivery.py", "--state-dir", str(tmp_path / "unused"), *extra])
    with pytest.raises(SystemExit) as error: delivery.main()
    assert error.value.code == 2 and not (tmp_path / "unused").exists()
