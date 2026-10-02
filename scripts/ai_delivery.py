"""Owned-repository AI proposal → native CI → signed protected delivery.

Run on an already authenticated trusted Mac. Dry-run is the default. The model
has no tools/credentials; only this single-writer controller calls GitHub.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import time
from urllib.parse import quote

import global_auto_merge as merge
from ai_proposal import BoundaryError, SECRET_PATTERN, apply_patches, propose, safe_path

AI_CONTEXT = "AI Delivery / verified"
HOLDS = {"do-not-merge", "hold", "manual-merge", "ai-delivery-hold"}


def now():
    return datetime.now(timezone.utc).isoformat()


class Ledger:
    """Atomic attempt reservations and append-only receipts survive sleep/restart."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(self.root / "state.sqlite3")
        self.db.execute("CREATE TABLE IF NOT EXISTS jobs (repo TEXT, number INT, head TEXT, attempts INT, updated REAL, outcome TEXT, PRIMARY KEY(repo, number, head))")
        self.db.execute("CREATE TABLE IF NOT EXISTS receipts (id INTEGER PRIMARY KEY, created TEXT, payload TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS cursor (repo TEXT, number INT, seen REAL, PRIMARY KEY(repo,number))")
        self.db.execute("CREATE TABLE IF NOT EXISTS review_evidence (repo TEXT, number INT, head TEXT, fingerprint TEXT, PRIMARY KEY(repo,number,head))")
        self.db.commit()

    def reserve(self, repo, number, head, *, limit=2, cooldown=900, reopen=False):
        self.db.execute("BEGIN IMMEDIATE")
        row = self.db.execute("SELECT attempts, updated, outcome FROM jobs WHERE repo=? AND number=? AND head=?", (repo, number, head)).fetchone()
        recent = self.db.execute("SELECT SUM(attempts) FROM jobs WHERE repo=? AND number=? AND updated>?", (repo, number, time.time() - 86400)).fetchone()[0] or 0
        if row and (row[0] >= limit or time.time() - row[1] < cooldown or row[2] == "verified" and not reopen) or recent >= 4:
            self.db.rollback()
            return False
        attempts = row[0] + 1 if row else 1
        self.db.execute("INSERT OR REPLACE INTO jobs VALUES (?, ?, ?, ?, ?, ?)", (repo, number, head, attempts, time.time(), "running"))
        self.db.commit()
        return True

    def record(self, receipt):
        payload = json.dumps({"createdAt": now(), **receipt}, sort_keys=True)
        self.db.execute("INSERT INTO receipts(created,payload) VALUES (?,?)", (now(), payload))
        if all(key in receipt for key in ("repo", "number", "head", "outcome")):
            self.db.execute("UPDATE jobs SET outcome=? WHERE repo=? AND number=? AND head=?", (receipt["outcome"], receipt["repo"], receipt["number"], receipt["head"]))
        self.db.commit()
        with (self.root / "receipts.jsonl").open("a") as stream:
            stream.write(payload + "\n")
        return self.db.execute("SELECT last_insert_rowid()").fetchone()[0]

    def priority(self, repo, number):
        row = self.db.execute("SELECT seen FROM cursor WHERE repo=? AND number=?", (repo, number)).fetchone()
        return row[0] if row else 0

    def repository_priority(self, repo):
        return self.db.execute("SELECT COALESCE(MAX(seen),0) FROM cursor WHERE repo=?",(repo,)).fetchone()[0]

    def seen(self, repo, number):
        self.db.execute("INSERT OR REPLACE INTO cursor VALUES(?,?,?)", (repo, number, time.time()))
        self.db.commit()

    def review_changed(self, repo, number, head, threads, reviews):
        fingerprint = hashlib.sha256(json.dumps({"threads":threads,"reviews":reviews},sort_keys=True).encode()).hexdigest()
        row = self.db.execute("SELECT fingerprint FROM review_evidence WHERE repo=? AND number=? AND head=?",(repo,number,head)).fetchone()
        self.db.execute("INSERT OR REPLACE INTO review_evidence VALUES(?,?,?,?)",(repo,number,head,fingerprint))
        self.db.commit()
        return bool(row and row[0] != fingerprint)


class GitHub(merge.GitHub):
    def rest(self, path, *, paginate=False, method="GET", body=None):
        # Retry only reads, never ambiguous external writes or exhausted quota.
        for attempt in range(3):
            try:
                return super().rest(path, paginate=paginate, method=method, body=body)
            except merge.APIError:
                if method != "GET" or attempt == 2:
                    raise
                try:
                    budgets = super().rest("rate_limit")
                except merge.APIError:
                    raise
                if int(budgets.get("resources", {}).get("core", {}).get("remaining", 0)) < 100:
                    raise
                time.sleep(2 ** attempt)

    def threads(self, repo, number):
        owner, name = repo.split("/")
        cursor, found = None, []
        query = """query($owner:String!,$name:String!,$number:Int!,$cursor:String){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewThreads(first:100,after:$cursor){nodes{id isResolved isOutdated comments(first:1){nodes{id databaseId body path line}}}pageInfo{hasNextPage endCursor}}}}}"""
        while True:
            data = self.rest("graphql", method="POST", body={"query": query, "variables": {"owner": owner, "name": name, "number": number, "cursor": cursor}})
            if data.get("errors"):
                raise merge.APIError("review_thread_read_failed")
            connection = data["data"]["repository"]["pullRequest"]["reviewThreads"]
            found.extend(item for item in connection["nodes"] if not item["isResolved"])
            if not connection["pageInfo"]["hasNextPage"]:
                return found
            cursor = connection["pageInfo"]["endCursor"]

    def signatures_required(self,repo,branch):
        owner,name=repo.split("/")
        query="""query($owner:String!,$name:String!,$branch:String!){repository(owner:$owner,name:$name){ref(qualifiedName:$branch){branchProtectionRule{requiresCommitSignatures}}}}"""
        data=self.rest("graphql",method="POST",body={"query":query,"variables":{"owner":owner,"name":name,"branch":"refs/heads/"+branch}})
        if data.get("errors"):
            raise BoundaryError("native_signing_policy_unknown")
        ref=data["data"]["repository"]["ref"]
        if ref is None or "branchProtectionRule" not in ref:
            raise BoundaryError("native_signing_policy_unknown")
        protection=ref["branchProtectionRule"]
        if protection is not None and not isinstance(protection.get("requiresCommitSignatures"),bool):
            raise BoundaryError("native_signing_policy_unknown")
        rules=self.rest(f"repos/{repo}/rules/branches/{quote(branch,safe='')}?per_page=100",paginate=True)
        return bool(protection and protection["requiresCommitSignatures"]) or any(row["type"]=="required_signatures" for row in rules)

    def status(self, repo, head, state, description, *, worker_revision=None):
        body = {"state": state, "context": AI_CONTEXT, "description": description[:140]}
        if worker_revision:
            body["target_url"] = f"https://github.com/{repo.split('/')[0]}/.github/commit/{worker_revision}"
        return self.rest(f"repos/{repo}/statuses/{head}", method="POST", body=body)

    def resolve_thread(self, thread_id):
        query = "mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{id isResolved}}}"
        result = self.rest("graphql", method="POST", body={"query":query,"variables":{"id":thread_id}})
        if result.get("errors") or not result["data"]["resolveReviewThread"]["thread"]["isResolved"]:
            raise merge.APIError("thread_resolution_not_verified")


def owned_repositories(api):
    identity = api.rest("user")["login"]
    repositories = api.rest("user/repos?affiliation=owner&per_page=100", paginate=True)
    return identity, [row for row in repositories if row["full_name"].split("/")[0].casefold() == identity.casefold()
                      and not row.get("archived") and not row.get("disabled") and row.get("permissions", {}).get("admin")]


def active_authority(api,repo):
    actor=api.rest("user")["login"]
    current=api.rest(f"repos/{repo}")
    if repo.split("/")[0].casefold()!=actor.casefold() or current.get("archived") or current.get("disabled") or not current.get("permissions",{}).get("admin"):
        raise BoundaryError("ownership_changed")
    return actor,current


def lease_hold(policy, repo, pr):
    # Root/coordinator provides fresh verified native ownership snapshots.
    stamp = datetime.fromisoformat(policy["leasesVerifiedAt"].replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - stamp).total_seconds()
    maximum_age = policy.get("leaseMaxAgeSeconds",900)
    if not isinstance(maximum_age,int) or not 300 <= maximum_age <= 5400:
        raise BoundaryError("invalid_lease_snapshot_age_policy")
    if age > maximum_age or age < -60:
        return "ownership_snapshot_stale"
    for field in ("created_at","updated_at"):
        if pr.get(field):
            activity=datetime.fromisoformat(pr[field].replace("Z","+00:00"))
            if activity.tzinfo is None:
                raise BoundaryError("invalid_native_pr_timestamp")
            if activity > stamp:
                return "pr_activity_newer_than_ownership_snapshot"
    for lease in policy.get("leases", []):
        expiry = datetime.fromisoformat(lease["expiresAt"].replace("Z", "+00:00"))
        if lease["repo"] == repo and expiry > datetime.now(timezone.utc) and (
            lease.get("number") == pr["number"] or lease.get("branch") in {pr["head"]["ref"],"*"}
        ):
            return "active_owner_lease"
    return None


def refresh_leases(policy, *, runner=subprocess.run):
    """A trusted host adapter refreshes native claims, never a model/PR command."""
    command = policy.get("leaseCommand")
    if command:
        if not isinstance(command,list) or not command or not all(isinstance(value,str) for value in command):
            raise BoundaryError("invalid_trusted_lease_command")
        result = runner(command,text=True,capture_output=True,timeout=60)
        if result.returncode or len(result.stdout.encode()) > 100_000 or SECRET_PATTERN.search(result.stdout):
            raise BoundaryError("ownership_adapter_failed")
        snapshot = json.loads(result.stdout)
        if set(snapshot) != {"leasesVerifiedAt","leases"} or not isinstance(snapshot["leases"],list):
            raise BoundaryError("ownership_adapter_invalid_output")
        for lease in snapshot["leases"]:
            if not isinstance(lease,dict) or not {"repo","expiresAt"}.issubset(lease) or not (lease.get("number") or lease.get("branch")):
                raise BoundaryError("ownership_adapter_invalid_lease")
            datetime.fromisoformat(lease["expiresAt"].replace("Z","+00:00"))
        policy = {**policy,**snapshot}
    # Validation occurs on every cycle; a failed feed cannot refresh its own age.
    if lease_hold(policy,"",{"number":0,"head":{"ref":""}}) == "ownership_snapshot_stale":
        raise BoundaryError("ownership_snapshot_stale")
    return policy


def precheck(api, repo, number):
    normalized = api.pull_request(repo, number)
    pr = api.rest(f"repos/{repo}/pulls/{number}")
    if pr["head"]["sha"] != normalized["headRefOid"]:
        raise BoundaryError("head_changed")
    if pr.get("draft") or pr.get("state") != "open":
        return pr, "draft_or_closed", [], []
    if (pr["head"].get("repo") or {}).get("full_name") != repo:
        return pr, "external_head_repository", [], []
    labels = [row["name"] for row in pr.get("labels", [])]
    if HOLDS.intersection(name.casefold() for name in labels):
        return pr, "explicit_hold", [], []
    head = pr["head"]["sha"]
    pages = api.rest(f"repos/{repo}/commits/{head}/check-runs?filter=latest&per_page=100", paginate=True)
    checks = [item for page in pages for item in page["check_runs"] if item["name"] != AI_CONTEXT]
    latest_statuses={}
    for item in api.rest(f"repos/{repo}/commits/{head}/statuses?per_page=100",paginate=True):
        if item["context"] != AI_CONTEXT:latest_statuses.setdefault(item["context"],item)
    statuses=list(latest_statuses.values())
    rules = api.rest(f"repos/{repo}/rules/branches/{quote(pr['base']['ref'], safe='')}?per_page=100", paginate=True)
    filtered = copy.deepcopy(normalized)
    protection = (filtered.get("baseRef") or {}).get("branchProtectionRule") or {}
    protection["requiredStatusCheckContexts"] = [name for name in protection.get("requiredStatusCheckContexts", []) if name != AI_CONTEXT]
    protection["requiredStatusChecks"] = [row for row in protection.get("requiredStatusChecks", []) if row["context"] != AI_CONTEXT]
    filtered_rules = copy.deepcopy(rules)
    for rule in filtered_rules:
        if rule["type"] == "required_status_checks":
            rule["parameters"]["required_status_checks"] = [row for row in rule["parameters"]["required_status_checks"] if row["context"] != AI_CONTEXT]
    reason = merge.blocker(filtered, labels, checks, statuses, filtered_rules)
    if merge.required_reviews(filtered,filtered_rules) and api.native_review_decision(repo,number)!="APPROVED":
        reason = "required_review_missing"
    pr["deliveryFailedChecks"] = [row["name"] for row in checks if row.get("conclusion") in {"failure", "timed_out", "action_required"}]
    pr["deliveryFailedStatuses"] = [row["context"] for row in statuses if row.get("state") in {"failure", "error"}]
    pr["deliveryNativeEvidence"]={"head":head,
        "checks":[{"name":row["name"],"status":row.get("status"),"conclusion":row.get("conclusion"),"appId":row.get("app",{}).get("id"),"completedAt":row.get("completed_at")} for row in checks],
        "statuses":[{"context":row["context"],"state":row.get("state"),"creator":row.get("creator",{}).get("login")} for row in statuses]}
    threads = api.threads(repo, number)
    reviews = api.rest(f"repos/{repo}/pulls/{number}/reviews?per_page=100", paginate=True)
    return pr, reason, threads, reviews


def run_git(root, *args):
    # Read configuration KEY NAMES only; never inspect credential/filter values.
    # PR attributes can select any installed filter, including a repo-relative
    # executable. Disable every known driver before materializing/staging code.
    listing=subprocess.run(["git","config","--name-only","--get-regexp",r"^filter\."],cwd=root,text=True,capture_output=True,timeout=30)
    if listing.returncode not in {0,1}:
        raise BoundaryError("git_filter_configuration_unknown")
    drivers={match.group(1) for key in listing.stdout.splitlines() if (match:=re.fullmatch(r"filter\.(.+)\.(?:smudge|clean|process|required)",key,re.IGNORECASE))}
    if len(drivers)>100:
        raise BoundaryError("git_filter_configuration_too_large")
    config=["-c","core.hooksPath=/dev/null","-c","core.fsmonitor=false","-c","submodule.recurse=false","-c","protocol.file.allow=never","-c","protocol.ext.allow=never"]
    for driver in sorted(drivers):
        for key,value in (("process",""),("smudge","/bin/cat"),("clean","/bin/cat"),("required","false")):
            config.extend(["-c",f"filter.{driver}.{key}={value}"])
    result = subprocess.run(["git", *config, *args], cwd=root, text=True, capture_output=True, timeout=120)
    if result.returncode:
        raise BoundaryError("git_operation_failed")
    return result.stdout.strip()


def context_from_clone(api, root, repo, pr, reason, threads, reviews):
    files = api.rest(f"repos/{repo}/pulls/{pr['number']}/files?per_page=100", paginate=True)
    by_name = {item["filename"]:item for item in files}
    modified = run_git(root, "diff", "--name-only").splitlines()
    added = run_git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    for path in [*modified, *added]:
        by_name.setdefault(path, {"filename":path})
    files = list(by_name.values())
    if len(files) > 25:
        raise BoundaryError("review_scope_too_large")
    evidence = []
    for item in files:
        path = item["filename"]
        try:
            target = safe_path(root, path)
        except BoundaryError:
            raise BoundaryError("changed_protected_or_symlink_file_requires_owner") from None
        content = target.read_bytes() if target.is_file() else b""
        if len(content) > 80_000 or b"\0" in content:
            raise BoundaryError("review_file_too_large_or_binary")
        text = content.decode()
        if SECRET_PATTERN.search(text):
            raise BoundaryError("secret_shaped_source_not_sent_to_model")
        evidence.append({"path": path, "original_sha256": hashlib.sha256(content).hexdigest() if target.is_file() else None,
                         "content": text, "diff": item.get("patch", "")[:12_000]})
    head = pr["head"]["sha"]
    pages = api.rest(f"repos/{repo}/commits/{head}/check-runs?filter=latest&per_page=100", paginate=True)
    failures = [{"name":row["name"],"conclusion":row.get("conclusion"),"title":(row.get("output") or {}).get("title"),
                 "summary":(row.get("output") or {}).get("summary", "")[:12_000]} for page in pages for row in page["check_runs"] if row.get("conclusion") in {"failure","timed_out","action_required"} and row["name"] != AI_CONTEXT]
    comments = api.rest(f"repos/{repo}/pulls/{pr['number']}/comments?per_page=100",paginate=True)
    if any(len(row.get("body","").encode())>12_000 for row in [*reviews,*comments]):
        raise BoundaryError("review_evidence_too_large")
    context = {"repo": repo, "number": pr["number"], "head": head, "blocker": reason, "failedChecks":failures[:5],
            "files": evidence, "threads": threads,
            "comments": [{key:row.get(key) for key in ("id","node_id","in_reply_to_id","body","path","line","original_line","commit_id")} | {"author":row.get("user",{}).get("login")} for row in comments],
            "reviews": [{"state": r["state"], "body": r.get("body", ""), "reviewer": r.get("user", {}).get("login")} for r in reviews]}
    if SECRET_PATTERN.search(json.dumps(context)):
        raise BoundaryError("secret_shaped_evidence_not_sent_to_model")
    return context


def deliver(api, ledger, policy, repo, listed, *, apply=False, backend=propose):
    number = listed["number"]
    receipt = {"repo": repo, "number": number, "apply": apply}
    def infer(context):
        return backend(context,receipt_path=ledger.root/"backend.jsonl") if backend is propose else backend(context)
    root = None
    try:
        pr, reason, threads, reviews = precheck(api, repo, number)
        initial_review_evidence = merge.review_evidence(api,repo,number)
        head = pr["head"]["sha"]
        receipt["head"] = head
        receipt["nativeBefore"]=pr.get("deliveryNativeEvidence")
        hard_hold=reason in {"draft_or_closed", "external_head_repository", "explicit_hold", "no_required_checks"} or reason=="required_review_missing" and not (pr.get("deliveryFailedChecks") or pr.get("deliveryFailedStatuses"))
        hold = reason if hard_hold else lease_hold(policy, repo, pr)
        if hold:
            return {**receipt, "outcome": "held", "reason": hold}
        if not apply:
            return {**receipt, "outcome": "would_review", "nativeBlocker": reason, "unresolvedThreads": len(threads)}
        if reason in {"missing_required_checks", "checks_not_green", "statuses_not_green"} and not pr.get("deliveryFailedChecks") and not pr.get("deliveryFailedStatuses"):
            return {**receipt, "outcome":"held", "reason":"native_ci_pending"}
        changed_reviews = ledger.review_changed(repo,number,head,threads,reviews)
        if not ledger.reserve(repo, number, head, reopen=bool(reason or threads or changed_reviews)):
            return {**receipt, "outcome": "held", "reason": "attempt_budget_or_cooldown"}
        actor,current=active_authority(api,repo)
        code_root = Path(__file__).resolve().parents[1]
        worker_revision = run_git(code_root, "rev-parse", "HEAD")
        deployed = api.rest(f"repos/{actor}/.github/commits/main")["sha"]
        if worker_revision != deployed or run_git(code_root,"status","--porcelain"):
            raise BoundaryError("trusted_worker_revision_not_deployed")
        api.status(repo, head, "pending", "AI review/repair pending; native checks and reviews remain required")
        directory = tempfile.TemporaryDirectory(prefix="ai-delivery-", dir=ledger.root)
        root = Path(directory.name) / "repo"
        run_git(ledger.root, "clone", "--no-checkout", "--no-tags", f"https://github.com/{repo}.git", str(root))
        run_git(root, "checkout", "--detach", head)
        proposal = infer(context_from_clone(api, root, repo, pr, reason, threads, reviews))
        receipt["proposalVerdict"] = proposal["verdict"]
        if proposal["verdict"] == "blocked":
            raise BoundaryError("ai_evidence_insufficient")
        if proposal["verdict"] == "repair":
            receipt["changedFiles"] = apply_patches(root, proposal["patches"])
            expected_hashes = {path:hashlib.sha256((root/path).read_bytes()).hexdigest() for path in receipt["changedFiles"]}
            receipt["requiredTestBackend"] = "native_ci_on_new_head"
            if any(hashlib.sha256((root/path).read_bytes()).hexdigest() != digest for path,digest in expected_hashes.items()):
                raise BoundaryError("tests_changed_proposed_files")
            staged = run_git(root,"diff","--name-only","--cached")
            tracked = set(run_git(root,"diff","--name-only").splitlines())
            added = set(run_git(root,"ls-files","--others","--exclude-standard").splitlines())
            if staged or tracked | added != set(receipt["changedFiles"]):
                raise BoundaryError("tests_modified_unproposed_files_or_index")
            # Fresh independent model context, no conversation continuation.
            verification = infer(context_from_clone(api, root, repo, pr, reason, threads, reviews))
            if verification["verdict"] != "clean" or verification["patches"]:
                raise BoundaryError("independent_review_not_clean")
            fresh, fresh_reason, _, _ = precheck(api, repo, number)
            policy=refresh_leases(policy)
            active_authority(api,repo)
            if fresh["head"]["sha"] != head or lease_hold(policy, repo, fresh) or fresh_reason in {"draft_or_closed", "explicit_hold", "external_head_repository"}:
                raise BoundaryError("head_or_owner_changed_before_push")
            # Preserve configured/native signing policy, never force unsigned.
            native_signing=api.signatures_required(repo,pr["base"]["ref"])
            configured_signing=run_git(root,"config","--type=bool","--default=false","--get","commit.gpgsign")=="true"
            signed=native_signing or configured_signing
            receipt["signing"]={"nativeRequired":native_signing,"configured":configured_signing,"requested":signed}
            run_git(root, "add", "--", *receipt["changedFiles"])
            commit_args=["commit",*(["-S"] if signed else []),"-m",f"fix: verified AI repair for PR #{number}"]
            run_git(root,*commit_args)
            new_head = run_git(root, "rev-parse", "HEAD")
            active_authority(api,repo)
            current_signing=api.signatures_required(repo,pr["base"]["ref"]) or run_git(root,"config","--type=bool","--default=false","--get","commit.gpgsign")=="true"
            if current_signing and not signed:
                raise BoundaryError("signing_policy_changed_before_push")
            run_git(root, "push", "origin", f"HEAD:refs/heads/{pr['head']['ref']}")
            return {**receipt, "outcome": "repaired_waiting_native_ci", "newHead": new_head}
        if proposal["patches"]:
            raise BoundaryError("unexpected_review_patch")
        if set(proposal["resolved_thread_ids"]) - {row["id"] for row in threads}:
            raise BoundaryError("unknown_review_thread_resolution")
        # Required reviews and unresolved findings are native/independent gates,
        # never satisfied by the model's own clean answer.
        fresh, native_reason, fresh_threads, _ = precheck(api, repo, number)
        policy=refresh_leases(policy)
        active_authority(api,repo)
        if fresh["head"]["sha"] != head or lease_hold(policy, repo, fresh):
            raise BoundaryError("head_or_owner_changed_before_status")
        receipt["nativeAfter"]=fresh.get("deliveryNativeEvidence")
        if merge.review_evidence(api,repo,number) != initial_review_evidence:
            raise BoundaryError("review_changed_during_ai_review")
        if native_reason or fresh_threads:
            known = {thread["id"] for thread in fresh_threads}
            resolved = set(proposal["resolved_thread_ids"])
            if native_reason or resolved != known:
                return {**receipt, "outcome": "held", "reason": native_reason or "unresolved_review_threads"}
            # A fresh no-tool reviewer proved these exact current-code findings
            # satisfied; do not dismiss reviews or self-approve required reviews.
            for thread_id in sorted(resolved):
                api.resolve_thread(thread_id)
            if api.threads(repo, number):
                raise BoundaryError("unresolved_threads_after_resolution")
        review_evidence = merge.review_evidence(api,repo,number)
        review_hash = hashlib.sha256(json.dumps(review_evidence,sort_keys=True).encode()).hexdigest()
        attestation = {**receipt, "outcome":"review_verified", "workerRevision":worker_revision, "verifiedHead":head,"reviewEvidenceSha256":review_hash}
        attestation["receiptId"] = ledger.record(attestation)
        api.status(repo, head, "success", f"AI verified receipt:{review_hash} worker:{worker_revision}", worker_revision=worker_revision)
        if merge.ai_receipt_gate(api,repo,number,head,actor,worker_revision):
            raise BoundaryError("ai_status_receipt_not_verified")
        verified, native_reason = merge.evidence(api, repo, number)
        if verified["headRefOid"] != head or native_reason:
            raise BoundaryError("native_gate_changed_before_enrollment")
        owner,current=active_authority(api,repo)
        method = next((method for field, method in (("allow_squash_merge", "squash"), ("allow_merge_commit", "merge"), ("allow_rebase_merge", "rebase")) if current.get(field)), None)
        if not method:
            raise BoundaryError("native_merge_setting_missing")
        if not current.get("allow_auto_merge"):
            updated=api.rest(f"repos/{repo}",method="PATCH",body={"allow_auto_merge":True})
            if not updated.get("allow_auto_merge"):
                raise BoundaryError("native_auto_merge_setting_not_verified")
        if merge.ai_receipt_gate(api,repo,number,head,actor,worker_revision):
            raise BoundaryError("review_changed_before_enrollment")
        if not verified.get("autoMergeRequest"):
            api.merge(repo, number, method, head)
        # Enrollment is verified from GitHub, never inferred from command exit.
        result = api.rest(f"repos/{repo}/pulls/{number}")
        if not result.get("merged") and not result.get("auto_merge"):
            raise BoundaryError("native_enrollment_not_verified")
        return {**receipt, "outcome": "verified", "nativeState": "merged" if result.get("merged") else "queued", "verifiedHead": head}
    except (BoundaryError, merge.APIError, KeyError, TypeError, ValueError, subprocess.TimeoutExpired) as exc:
        return {**receipt, "outcome": "blocked", "reason": str(exc) if isinstance(exc, BoundaryError) else type(exc).__name__,
                **({"backendEvidence":exc.evidence} if isinstance(exc,BoundaryError) and exc.evidence else {})}
    finally:
        if root is not None:
            directory.cleanup()


def cycle(api, ledger, policy, *, apply=False, budget=3):
    core, graphql = api.rate_limit_remaining()
    if core < 300 or graphql < 100:
        return {"outcome": "backpressure", "reason": "api_rate_budget_low", "core": core, "graphql": graphql}
    owner, repositories = owned_repositories(api)
    results, candidates, discovery_errors = [], {}, []
    for repo_row in repositories:
        repo = repo_row["full_name"]
        try:
            prs = api.rest(f"repos/{repo}/pulls?state=open&per_page=100", paginate=True)
        except (merge.APIError,KeyError,TypeError,ValueError,subprocess.TimeoutExpired) as exc:
            failure={"repo":repo,"outcome":"blocked","reason":"discovery_"+type(exc).__name__}
            ledger.record(failure)
            discovery_errors.append(failure)
            continue
        for pr in prs:
            if pr.get("draft"):
                continue
            candidates.setdefault(repo,[]).append(pr)
    for repo,prs in candidates.items():
        prs.sort(key=lambda pr:(ledger.priority(repo,pr["number"]),pr["number"]))
    ordered=sorted(candidates,key=lambda repo:(ledger.repository_priority(repo),repo))
    selected=[]
    while ordered and len(selected)<budget:
        for repo in ordered:
            selected.append((repo,candidates[repo].pop(0)))
            if len(selected)==budget:
                break
        ordered=[repo for repo in ordered if candidates[repo]]
    for repo,pr in selected:
        ledger.seen(repo,pr["number"])
        receipt = deliver(api, ledger, policy, repo, pr, apply=apply)
        receipt["receiptId"] = ledger.record(receipt)
        results.append(receipt)
    return {"owner": owner, "ownedRepositories": len(repositories), "processed": len(results), "apply": apply, "results": results,"discoveryErrors":discovery_errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path(__file__).with_name("ai-delivery-policy.json"))
    parser.add_argument("--report", type=Path)
    parser.add_argument("--poll-seconds", type=int, default=900)
    parser.add_argument("--budget", type=int, default=3)
    args = parser.parse_args()
    if args.poll_seconds < 300 or not 1 <= args.budget <= 5:
        parser.error("poll >=300 seconds; budget 1..5 PRs per cycle")
    ledger = Ledger(args.state_dir)
    with (args.state_dir / "writer.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("another_delivery_writer_is_running") from None
        while True:
            try:
                policy = refresh_leases(json.loads(args.policy.read_text()))
                report = cycle(GitHub(), ledger, policy, apply=args.apply, budget=args.budget)
            except (BoundaryError, merge.APIError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
                report = {"outcome": "blocked", "reason": str(exc) if isinstance(exc,BoundaryError) else type(exc).__name__}
                ledger.record(report)
            text = json.dumps(report, indent=2)
            print(text, flush=True)
            if args.report:
                args.report.write_text(text + "\n")
            if not args.daemon:
                return
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
