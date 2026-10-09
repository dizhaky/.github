"""Owned-repository AI proposal → native CI → signed protected delivery.

Run on an already authenticated trusted Mac. Dry-run is the default. The model
has no tools/credentials; only this single-writer controller calls GitHub.
"""
from __future__ import annotations

import argparse
import base64
import copy
import difflib
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
from ai_proposal import BoundaryError, SECRET_PATTERN, apply_patches, evidence_path, propose

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
        self.db.execute("CREATE TABLE IF NOT EXISTS jobs (repo TEXT, number INT, head TEXT, attempts INT, updated REAL, outcome TEXT, worker TEXT, PRIMARY KEY(repo, number, head))")
        if "worker" not in {row[1] for row in self.db.execute("PRAGMA table_info(jobs)")}:
            self.db.execute("ALTER TABLE jobs ADD COLUMN worker TEXT")
        self.db.execute("CREATE TABLE IF NOT EXISTS receipts (id INTEGER PRIMARY KEY, created TEXT, payload TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS cursor (repo TEXT, number INT, seen REAL, PRIMARY KEY(repo,number))")
        self.db.execute("CREATE TABLE IF NOT EXISTS review_evidence (repo TEXT, number INT, head TEXT, fingerprint TEXT, PRIMARY KEY(repo,number,head))")
        self.db.commit()

    def reserve(self, repo, number, head, *, limit=2, cooldown=900, reopen=False, worker=None):
        self.db.execute("BEGIN IMMEDIATE")
        row = self.db.execute("SELECT attempts, updated, outcome, worker FROM jobs WHERE repo=? AND number=? AND head=?", (repo, number, head)).fetchone()
        recent = self.db.execute("SELECT SUM(attempts) FROM jobs WHERE repo=? AND number=? AND updated>?", (repo, number, time.time() - 86400)).fetchone()[0] or 0
        # A verified receipt is trusted only from the worker revision that produced it.
        stale_worker = bool(worker and row and row[3] != worker)
        if row and (row[0] >= limit or time.time() - row[1] < cooldown or row[2] == "verified" and not (reopen or stale_worker)) or recent >= 4:
            self.db.rollback()
            return False
        attempts = row[0] + 1 if row else 1
        self.db.execute("INSERT OR REPLACE INTO jobs (repo, number, head, attempts, updated, outcome, worker) VALUES (?, ?, ?, ?, ?, ?, ?)", (repo, number, head, attempts, time.time(), "running", worker))
        self.db.commit()
        return True

    def record(self, receipt):
        payload = json.dumps({"createdAt": now(), **receipt}, sort_keys=True)
        self.db.execute("INSERT INTO receipts(created,payload) VALUES (?,?)", (now(), payload))
        if all(key in receipt for key in ("repo", "number", "head", "outcome")):
            self.db.execute("UPDATE jobs SET outcome=?, worker=? WHERE repo=? AND number=? AND head=?", (receipt["outcome"], receipt.get("workerRevision"), receipt["repo"], receipt["number"], receipt["head"]))
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

    def create_signed_commit(self,repo,branch,parent,files,tree):
        if not 1<=len(files)<=10 or len(json.dumps(files).encode())>350_000:
            raise BoundaryError("server_patch_outside_budget")
        active_authority(self,repo,{"head":{"ref":branch}})
        query="""mutation($input:CreateCommitOnBranchInput!){createCommitOnBranch(input:$input){commit{oid tree{oid} signature{isValid state}}ref{name target{oid}}}}"""
        data=self.rest("graphql",method="POST",body={"query":query,"variables":{"input":{"branch":{"repositoryNameWithOwner":repo,"branchName":branch},"expectedHeadOid":parent,"message":{"headline":"fix: verified AI repair"},"fileChanges":{"additions":files}}}})
        if data.get("errors"):raise BoundaryError("server_signed_commit_rejected")
        result=data["data"]["createCommitOnBranch"];commit=result["commit"];head=commit["oid"]
        signature=commit.get("signature") or {}
        if not re.fullmatch(r"[0-9a-f]{40}",head) or commit["tree"]["oid"]!=tree or not signature.get("isValid") or signature.get("state")!="VALID" or result["ref"]["name"]!=branch or result["ref"]["target"]["oid"]!=head:
            raise BoundaryError("server_commit_graph_verification_failed",{"remoteHead":head})
        actual=self.rest(f"repos/{repo}/commits/{head}")
        reference=self.rest(f"repos/{repo}/git/ref/heads/{quote(branch,safe='')}")
        verification=actual["commit"]["verification"]
        if actual["commit"]["tree"]["sha"]!=tree or [row["sha"] for row in actual["parents"]]!=[parent] or actual.get("author",{}).get("id")!=213320850 or actual.get("author",{}).get("login")!="dizhaky" or not verification.get("verified") or verification.get("reason")!="valid" or reference["ref"]!="refs/heads/"+branch or reference["object"]["sha"]!=head:
            raise BoundaryError("server_commit_rest_verification_failed",{"remoteHead":head})
        return head

    def resolve_thread(self, thread_id):
        query = "mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{id isResolved}}}"
        result = self.rest("graphql", method="POST", body={"query":query,"variables":{"id":thread_id}})
        if result.get("errors") or not result["data"]["resolveReviewThread"]["thread"]["isResolved"]:
            raise merge.APIError("thread_resolution_not_verified")


def trusted_actor(api):
    identity=api.rest("user")
    if identity.get("login")!="dizhaky" or identity.get("id")!=213320850:
        raise BoundaryError("authenticated_owner_changed")
    return identity["login"]


def owned_repositories(api):
    identity = trusted_actor(api)
    repositories = api.rest("user/repos?affiliation=owner&per_page=100", paginate=True)
    return identity, [row for row in repositories if owned_metadata(row,row.get("full_name",""),identity)]


def owned_metadata(current,repo,actor):
    owner=current.get("owner") or {}
    return bool(repo and repo.split("/")[0].casefold()==actor.casefold()
        and isinstance(current.get("full_name"),str) and current["full_name"].casefold()==repo.casefold()
        and owner.get("login")==actor and owner.get("id")==213320850
        and current.get("archived") is False and current.get("disabled") is False
        and current.get("permissions",{}).get("admin") is True)


def active_authority(api,repo,pr=None):
    actor=trusted_actor(api)
    current=api.rest(f"repos/{repo}")
    if not owned_metadata(current,repo,actor):
        raise BoundaryError("ownership_changed")
    if pr is not None:
        if not isinstance(current.get("default_branch"),str) or not current["default_branch"]:
            raise BoundaryError("default_branch_unknown")
        if pr["head"]["ref"]==current["default_branch"]:
            raise BoundaryError("default_branch_head_prohibited")
        # Enrolled delivery targets only the current default branch, never a
        # side branch; the synthetic branch heads have no base and skip this.
        if isinstance(pr.get("base"),dict) and pr["base"].get("ref")!=current["default_branch"]:
            raise BoundaryError("non_default_base_branch_prohibited")
    return actor,current


def head_or_base_changed(pr, fresh):
    # The model context is bound to the exact head and base it was built from.
    return bool(fresh["head"].get("sha") != pr["head"].get("sha")
        or fresh["head"].get("ref") != pr["head"].get("ref")
        or fresh["base"].get("ref") != pr["base"].get("ref")
        or fresh["base"].get("sha") != pr["base"].get("sha"))


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


def validate_leases(leases):
    for lease in leases:
        number = lease.get("number") if isinstance(lease, dict) else None
        branch = lease.get("branch") if isinstance(lease, dict) else None
        # Mistyped selectors (string "42", bool) never equal the native value in
        # lease_hold, so an active owner lease would be silently dropped.
        if (not isinstance(lease,dict) or not {"repo","expiresAt"}.issubset(lease)
                or not isinstance(lease.get("repo"),str) or not isinstance(lease.get("expiresAt"),str)
                or isinstance(number,bool) or (number is not None and (not isinstance(number,int) or number < 1))
                or (branch is not None and (not isinstance(branch,str) or not branch))
                or not (number or branch)):
            raise BoundaryError("ownership_adapter_invalid_lease")
        datetime.fromisoformat(lease["expiresAt"].replace("Z","+00:00"))


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
        validate_leases(snapshot["leases"])
        policy = {**policy,**snapshot}
    # Validation occurs on every cycle; a failed feed cannot refresh its own age.
    validate_leases(policy.get("leases", []))
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


def server_signed_patch(api,root,repo,pr,paths):
    if not 1<=len(paths)<=10 or len(set(paths))!=len(paths):
        raise BoundaryError("server_patch_outside_budget")
    records=run_git(root,"ls-files","--stage","-z","--",*paths).split("\0")
    additions=[];seen=set()
    for record in records:
        if not record:continue
        metadata,path=record.split("\t",1);mode,blob,stage=metadata.split()
        if path not in paths or path in seen or mode!="100644" or stage!="0":
            raise BoundaryError("server_signing_requires_regular_exact_paths")
        content=(root/path).read_bytes()
        if len(content)>100_000:raise BoundaryError("server_patch_outside_budget")
        expected=hashlib.sha1(b"blob "+str(len(content)).encode()+b"\0"+content).hexdigest()
        if blob!=expected:raise BoundaryError("server_patch_not_exact_staged_blob")
        additions.append({"path":path,"contents":base64.b64encode(content).decode()});seen.add(path)
    if seen!=set(paths):raise BoundaryError("server_signing_incomplete_patch_index")
    tree=run_git(root,"write-tree")
    if not re.fullmatch(r"[0-9a-f]{40}",tree):raise BoundaryError("server_signing_expected_tree_invalid")
    active_authority(api,repo,pr)
    return api.create_signed_commit(repo,pr["head"]["ref"],pr["head"]["sha"],additions,tree)


def complete_native_patch(item):
    patch=item.get("patch")
    if not isinstance(patch,str) or not patch:
        raise BoundaryError("native_patch_missing")
    if len(patch.encode())>80_000:
        raise BoundaryError("native_patch_too_large")
    old=new=0;expected=None;added=deleted=0
    lines=patch.split("\n")
    if lines[-1]=="":lines.pop()
    for line in lines:
        header=re.fullmatch(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*",line)
        if header:
            if expected is not None and (old,new)!=expected:
                raise BoundaryError("native_patch_incomplete")
            expected=(int(header[2] or 1),int(header[4] or 1));old=new=0
        elif expected is None:
            raise BoundaryError("native_patch_incomplete")
        elif line.startswith(" "):old+=1;new+=1
        elif line.startswith("+"):new+=1;added+=1
        elif line.startswith("-"):old+=1;deleted+=1
        elif line!="\\ No newline at end of file":
            raise BoundaryError("native_patch_incomplete")
    if expected is None or (old,new)!=expected or any(type(item.get(key)) is not int for key in ("additions","deletions")) or (added,deleted)!=(item["additions"],item["deletions"]):
        raise BoundaryError("native_patch_incomplete")
    return patch


def context_from_clone(api, root, repo, pr, reason, threads, reviews):
    files = api.rest(f"repos/{repo}/pulls/{pr['number']}/files?per_page=100", paginate=True)
    by_name = {item["filename"]:item for item in files}
    if len(by_name)!=len(files) or len({name.casefold() for name in by_name})!=len(by_name):
        raise BoundaryError("duplicate_or_case_alias_review_files")
    native_names=set(by_name)
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
            target = evidence_path(root, path)
            if item.get("previous_filename"):evidence_path(root,item["previous_filename"])
        except BoundaryError:
            raise BoundaryError("unsafe_or_credential_review_evidence") from None
        if path in native_names and item.get("status")!="removed" and not target.is_file():
            raise BoundaryError("native_review_file_missing")
        content = target.read_bytes() if target.is_file() else b""
        if len(content) > 80_000 or b"\0" in content:
            raise BoundaryError("review_file_too_large_or_binary")
        text = content.decode()
        if SECRET_PATTERN.search(text):
            raise BoundaryError("secret_shaped_source_not_sent_to_model")
        patch=complete_native_patch(item) if path in native_names else None
        if path in native_names and item.get("status")!="removed" and path not in modified and path not in added:
            blob=hashlib.sha1(b"blob "+str(len(content)).encode()+b"\0"+content).hexdigest()
            if item.get("sha")!=blob:
                raise BoundaryError("review_file_not_exact_native_blob")
        candidate=None
        if path in modified:
            candidate=run_git(root,"diff","--no-ext-diff","--no-textconv","--",path)
        elif path in added:
            candidate="".join(difflib.unified_diff([],text.splitlines(keepends=True),fromfile="/dev/null",tofile=path))
        if candidate is not None and (not candidate or len(candidate.encode())>80_000):
            raise BoundaryError("candidate_patch_missing_or_too_large")
        evidence.append({"path": path, "original_sha256": hashlib.sha256(content).hexdigest() if target.is_file() else None,
                         "content": text, "diff": patch, "candidateDiff":candidate,
                         "status":item.get("status"),"previousPath":item.get("previous_filename"),
                         "additions":item.get("additions"),"deletions":item.get("deletions")})
    head = pr["head"]["sha"]
    pages = api.rest(f"repos/{repo}/commits/{head}/check-runs?filter=latest&per_page=100", paginate=True)
    failures = [{"name":row["name"],"conclusion":row.get("conclusion"),"title":(row.get("output") or {}).get("title"),
                 "summary":(row.get("output") or {}).get("summary") or ""} for page in pages for row in page["check_runs"] if row.get("conclusion") in {"failure","timed_out","action_required"} and row["name"] != AI_CONTEXT]
    if any(not isinstance(row["summary"],str) or len(row["summary"].encode())>12_000 for row in failures):
        raise BoundaryError("check_evidence_too_large_or_invalid")
    comments = api.rest(f"repos/{repo}/pulls/{pr['number']}/comments?per_page=100",paginate=True)
    conversation = api.rest(f"repos/{repo}/issues/{pr['number']}/comments?per_page=100",paginate=True)
    if any(len(row.get("body","").encode())>12_000 for row in [*reviews,*comments,*conversation]):
        raise BoundaryError("review_evidence_too_large")
    review_threads=[{key:row.get(key) for key in ("id","isResolved","isOutdated")} | {"comments":{"nodes":[{key:comment.get(key) for key in ("id","databaseId","body","path","line")} for comment in row.get("comments",{}).get("nodes",[])]}} for row in threads]
    context = {"repo": repo, "number": pr["number"], "head": head, "blocker": reason, "failedChecks":failures,
            "failedStatuses":pr.get("deliveryFailedStatuses",[]),
            "files": evidence, "threads": review_threads,
            "comments": [{key:row.get(key) for key in ("id","node_id","in_reply_to_id","body","path","line","original_line","commit_id")} | {"author":row.get("user",{}).get("login")} for row in comments],
            "conversationComments": [{key:row.get(key) for key in ("id","body","created_at","updated_at")} | {"author":row.get("user",{}).get("login")} for row in conversation],
            "reviews": [{"state": r["state"], "body": r.get("body", ""), "reviewer": r.get("user", {}).get("login")} for r in reviews]}
    if SECRET_PATTERN.search(json.dumps(context)):
        raise BoundaryError("secret_shaped_evidence_not_sent_to_model")
    if len(json.dumps(context).encode())>180_000:
        raise BoundaryError("review_context_too_large")
    return context


def deliver(api, ledger, policy, repo, listed, *, apply=False, backend=propose):
    number = listed["number"]
    receipt = {"repo": repo, "number": number, "apply": apply}
    def infer(context):
        return backend(context,receipt_path=ledger.root/"backend.jsonl") if backend is propose else backend(context)
    root = None
    try:
        pr, reason, threads, reviews = precheck(api, repo, number)
        active_authority(api,repo,pr)
        initial_review_evidence = merge.review_evidence(api,repo,number)
        head = pr["head"]["sha"]
        receipt["head"] = head
        receipt["nativeBefore"]=pr.get("deliveryNativeEvidence")
        hard_hold=reason in {"draft_or_closed", "external_head_repository", "explicit_hold", "no_required_checks"} or reason=="required_review_missing" and not (pr.get("deliveryFailedChecks") or pr.get("deliveryFailedStatuses"))
        hold = reason if hard_hold else lease_hold(policy, repo, pr)
        if hold:
            # A queued native auto-merge request would merge on green checks and
            # bypass this hold; the sole writer disarms it, never in dry-run.
            if apply and pr.get("auto_merge"):
                api.merge(repo, number, disable=True)
            return {**receipt, "outcome": "held", "reason": hold}
        if not apply:
            return {**receipt, "outcome": "would_review", "nativeBlocker": reason, "unresolvedThreads": len(threads)}
        if reason in {"missing_required_checks", "checks_not_green", "statuses_not_green"} and not pr.get("deliveryFailedChecks") and not pr.get("deliveryFailedStatuses"):
            return {**receipt, "outcome":"held", "reason":"native_ci_pending"}
        changed_reviews = ledger.review_changed(repo,number,head,threads,reviews)
        code_root = Path(__file__).resolve().parents[1]
        worker_revision = run_git(code_root, "rev-parse", "HEAD")
        receipt["workerRevision"] = worker_revision
        if not ledger.reserve(repo, number, head, reopen=bool(reason or threads or changed_reviews), worker=worker_revision):
            return {**receipt, "outcome": "held", "reason": "attempt_budget_or_cooldown"}
        actor,current=active_authority(api,repo,pr)
        source=api.rest(f"repos/{actor}/.github")
        deployed = api.rest(f"repos/{actor}/.github/commits/{quote(source['default_branch'],safe='')}")["sha"]
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
            if repo=="dizhaky/.github" and any(row["path"].casefold().startswith("scripts/") for row in proposal["patches"]):
                raise BoundaryError("protected_controller_source_change")
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
            active_authority(api,repo,fresh)
            if head_or_base_changed(pr, fresh) or lease_hold(policy, repo, fresh) or fresh_reason in {"draft_or_closed", "explicit_hold", "external_head_repository"}:
                raise BoundaryError("head_or_owner_changed_before_push")
            # Preserve configured/native signing policy, never force unsigned.
            native_signing=api.signatures_required(repo,fresh["base"]["ref"])
            configured_signing=run_git(root,"config","--type=bool","--default=false","--get","commit.gpgsign")=="true"
            signed=native_signing or configured_signing
            receipt["signing"]={"nativeRequired":native_signing,"configured":configured_signing,"requested":signed}
            run_git(root, "add", "--", *receipt["changedFiles"])
            if native_signing and not configured_signing:
                policy=refresh_leases(policy)
                fresh,fresh_reason,_,_=precheck(api,repo,number)
                if head_or_base_changed(pr, fresh) or lease_hold(policy,repo,fresh) or fresh_reason in {"draft_or_closed","explicit_hold","external_head_repository"}:
                    raise BoundaryError("head_or_owner_changed_before_server_commit")
                if run_git(root,"config","--type=bool","--default=false","--get","commit.gpgsign")=="true":
                    raise BoundaryError("configured_signing_changed_before_server_commit")
                new_head=server_signed_patch(api,root,repo,fresh,receipt["changedFiles"])
                receipt["signing"]["backend"]="github_verified"
                return {**receipt,"outcome":"repaired_waiting_native_ci","newHead":new_head}
            receipt["signing"]["backend"]="configured_git"
            commit_args=["commit",*(["-S"] if signed else []),"-m",f"fix: verified AI repair for PR #{number}"]
            run_git(root,*commit_args)
            new_head = run_git(root, "rev-parse", "HEAD")
            fresh,fresh_reason,_,_=precheck(api,repo,number)
            policy=refresh_leases(policy)
            active_authority(api,repo,fresh)
            if head_or_base_changed(pr, fresh) or lease_hold(policy,repo,fresh) or fresh_reason in {"draft_or_closed","explicit_hold","external_head_repository"}:
                raise BoundaryError("head_or_owner_changed_before_push")
            current_signing=api.signatures_required(repo,fresh["base"]["ref"]) or run_git(root,"config","--type=bool","--default=false","--get","commit.gpgsign")=="true"
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
        active_authority(api,repo,fresh)
        if head_or_base_changed(pr, fresh) or lease_hold(policy, repo, fresh):
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
        owner,current=active_authority(api,repo,fresh)
        method = next((method for field, method in (("allow_squash_merge", "squash"), ("allow_merge_commit", "merge"), ("allow_rebase_merge", "rebase")) if current.get(field)), None)
        if not method:
            raise BoundaryError("native_merge_setting_missing")
        # The sole writer repairs every reconciler-flagged setting, never only one.
        repairs={field:True for field in ("allow_auto_merge","delete_branch_on_merge") if not current.get(field)}
        if repairs:
            updated=api.rest(f"repos/{repo}",method="PATCH",body=repairs)
            if not all(updated.get(field) for field in repairs):
                raise BoundaryError("native_auto_merge_setting_not_verified")
        if merge.ai_receipt_gate(api,repo,number,head,actor,worker_revision):
            raise BoundaryError("review_changed_before_enrollment")
        if not verified.get("autoMergeRequest"):
            # Owner intent is rechecked immediately before enrollment: a late
            # hold label or lease must not be bypassed by a queued merge; the
            # native required checks remain the CI gate and are not rejudged.
            final = api.rest(f"repos/{repo}/pulls/{number}")
            policy = refresh_leases(policy)
            if (head_or_base_changed(pr, final) or lease_hold(policy, repo, final)
                    or HOLDS.intersection(str(row.get("name")).casefold() for row in final.get("labels", []) if isinstance(row, dict))):
                raise BoundaryError("hold_before_enrollment")
            api.merge(repo, number, method, head)
        # Enrollment is verified from GitHub, never inferred from command exit.
        result = api.rest(f"repos/{repo}/pulls/{number}")
        if not result.get("merged") and not result.get("auto_merge"):
            raise BoundaryError("native_enrollment_not_verified")
        return {**receipt, "outcome": "verified", "nativeState": "merged" if result.get("merged") else "queued", "verifiedHead": head}
    # OSError (e.g. a filesystem race a model proposal triggers) blocks one PR
    # as a visible receipt instead of crashing the whole delivery cycle.
    except (BoundaryError, merge.APIError, KeyError, TypeError, ValueError, subprocess.TimeoutExpired, OSError) as exc:
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


def sanitize_for_logging(value):
    sensitive_keys = {
        "owner", "login", "id", "token", "secret", "password", "authorization",
        "access_token", "refresh_token", "client_secret", "private_key"
    }
    if isinstance(value, dict):
        redacted = {}
        for k, v in value.items():
            key = str(k).casefold()
            if key in sensitive_keys:
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = sanitize_for_logging(v)
        return redacted
    if isinstance(value, list):
        return [sanitize_for_logging(item) for item in value]
    if isinstance(value, str):
        if SECRET_PATTERN.search(value):
            return "[REDACTED]"
        return value
    return value


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
            # Stdout is a log. Do not print the cycle report: it carries
            # GitHub payloads, and CodeQL treats that print as clear-text
            # logging even after key redaction.
            print("delivery_cycle_complete", flush=True)
            if args.report:
                safe_report = sanitize_for_logging(report)
                args.report.write_text(json.dumps(safe_report, indent=2) + "\n")
            if not args.daemon:
                return
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
