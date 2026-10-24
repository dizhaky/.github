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


def test_noncanonical_repo_is_held_by_canonical_lease(delivery_flow, monkeypatch):
    api, ledger = delivery_flow
    original = api.rest
    def rest(path, **kwargs):
        data = original(path, **kwargs)
        if path == "repos/Dizhaky/example":
            data["full_name"] = "dizhaky/example"
        return data
    monkeypatch.setattr(api, "rest", rest)
    p = policy()
    p["leases"] = [{"repo": "dizhaky/example", "branch": "*", "expiresAt": "2099-01-01T00:00:00Z"}]
    result = delivery.target_cycle(api, ledger, p, ("Dizhaky/example", 1, "a" * 40))
    assert result["target"]["repo"] == "dizhaky/example"
    assert result["results"][0]["outcome"] == "held"
    assert result["results"][0]["reason"] == "active_owner_lease"
    assert api.actions == []


@pytest.mark.parametrize("expected,reason", [("a" * 40, "target_head_changed"), (None, "head_changed")])
def test_changed_head_before_hold_disarm_does_not_write(delivery_flow, monkeypatch, expected, reason):
    api, ledger = delivery_flow
    api.pr["auto_merge"] = {"enabled_at": "now"}
    held = copy.deepcopy(api.pr)
    monkeypatch.setattr(delivery, "precheck", lambda *args: (held, "explicit_hold", [], []))
    api.pr["head"]["sha"] = "b" * 40
    result = delivery.deliver(api, ledger, policy(), "dizhaky/example", {"number": 1}, apply=True, expected_head=expected, backend=lambda ctx: {"verdict": "clean"})
    assert result["outcome"] == "blocked" and result["reason"] == reason
    assert api.actions == [("disable", "dizhaky/example", 1, None, None)]
    assert api.pr["auto_merge"] is None


def test_changed_head_with_lapsed_lease_is_not_disarmed(delivery_flow, monkeypatch):
    api, ledger = delivery_flow
    api.pr["auto_merge"] = {"enabled_at": "now"}
    held = copy.deepcopy(api.pr)
    monkeypatch.setattr(delivery, "precheck", lambda *args: (held, None, [], []))
    monkeypatch.setattr(delivery, "lease_hold", lambda p, r, pr: "active_owner_lease" if pr["head"]["sha"] == "a" * 40 else None)
    api.pr["head"]["sha"] = "b" * 40
    result = delivery.deliver(api, ledger, policy(), "dizhaky/example", {"number": 1}, apply=True, backend=lambda ctx: {"verdict": "clean"})
    assert result["outcome"] == "blocked" and result["reason"] == "head_changed"
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


@pytest.mark.parametrize("exc", [delivery.merge.APIError("boom"), KeyError("x"), TypeError("x"), ValueError("x")])
def test_fresh_precheck_failure_still_disarms(delivery_flow, monkeypatch, exc):
    api, ledger = delivery_flow
    api.pr["auto_merge"] = {"enabled_at": "now"}
    held = copy.deepcopy(api.pr)
    calls = []
    def precheck(*args):
        calls.append(1)
        if len(calls) > 1:
            raise exc
        return held, "explicit_hold", [], []
    monkeypatch.setattr(delivery, "precheck", precheck)
    api.pr["head"]["sha"] = "b" * 40
    result = delivery.deliver(api, ledger, policy(), "dizhaky/example", {"number": 1}, apply=True, backend=lambda ctx: {"verdict": "clean"})
    assert result["outcome"] == "blocked" and result["reason"] == "head_changed"
    assert api.actions == [("disable", "dizhaky/example", 1, None, None)]
