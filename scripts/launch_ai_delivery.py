"""Verified protected-default source, atomic checkout, one fresh delivery process."""
from __future__ import annotations

import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
from urllib.parse import quote

from ai_delivery import AI_CONTEXT, GitHub, active_authority, run_git
from ai_proposal import BoundaryError
import global_auto_merge as merge


def source_revision(api):
    repo="dizhaky/.github"
    _,metadata=active_authority(api,repo)
    branch=metadata["default_branch"]
    native=api.rest(f"repos/{repo}/branches/{quote(branch,safe='')}")
    head=native["commit"]["sha"]
    if not native.get("protected") or not re.fullmatch(r"[0-9a-f]{40}",head):
        raise BoundaryError("source_default_branch_unprotected")
    protection=api.rest(f"repos/{repo}/branches/{quote(branch,safe='')}/protection")
    required=protection.get("required_status_checks") or {}
    rules=api.rest(f"repos/{repo}/rules/branches/{quote(branch,safe='')}?per_page=100",paginate=True)
    checks=[row for page in api.rest(f"repos/{repo}/commits/{head}/check-runs?filter=latest&per_page=100",paginate=True) for row in page["check_runs"] if row["name"]!=AI_CONTEXT]
    statuses=[row for row in api.rest(f"repos/{repo}/commits/{head}/statuses?per_page=100",paginate=True) if row["context"]!=AI_CONTEXT]
    filtered=copy.deepcopy(rules)
    for rule in filtered:
        if rule["type"]=="required_status_checks":
            rule["parameters"]["required_status_checks"]=[row for row in rule["parameters"]["required_status_checks"] if row["context"]!=AI_CONTEXT]
    names=set(required.get("contexts",[]))|{row["context"] for row in required.get("checks",[])}
    for rule in filtered:
        if rule["type"]=="required_status_checks":names.update(row["context"] for row in rule["parameters"]["required_status_checks"])
    names.discard(AI_CONTEXT)
    checks=[row for row in checks if row["name"] in names]
    statuses=[row for row in statuses if row["context"] in names]
    normalized={"state":"OPEN","isDraft":False,"reviewDecision":None,"mergeable":"MERGEABLE","mergeStateStatus":"CLEAN","baseRef":{"branchProtectionRule":{"requiresStatusChecks":bool(required),"requiredStatusCheckContexts":[name for name in required.get("contexts",[]) if name!=AI_CONTEXT],"requiredStatusChecks":[{"context":row["context"],"appId":row.get("app_id")} for row in required.get("checks",[]) if row["context"]!=AI_CONTEXT]}}}
    blocker=merge.blocker(normalized,[],checks,statuses,filtered)
    if blocker:raise BoundaryError("source_native_ci_"+blocker)
    signing=api.signatures_required(repo,branch)
    if signing and not api.rest(f"repos/{repo}/commits/{head}")["commit"]["verification"]["verified"]:
        raise BoundaryError("source_required_signature_unverified")
    return repo,branch,head


def rotate(path,limit=5*1024*1024,keep=5):
    if path.exists() and path.stat().st_size>=limit:
        for index in range(keep,0,-1):
            old=path if index==1 else path.with_name(path.name+"."+str(index-1))
            if old.exists():old.replace(path.with_name(path.name+"."+str(index)))


def run_controller(command,*,cwd,stdout,stderr,timeout,check=False):
    process=subprocess.Popen(command,cwd=cwd,stdout=stdout,stderr=stderr,start_new_session=True)
    try:
        code=process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=5)
        raise
    return subprocess.CompletedProcess(command,code)


def launch(api,state,checkouts,logs,report,*,budget=3,runner=run_controller):
    repo,branch,head=source_revision(api)
    for directory in (state,checkouts,logs):
        directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        if directory.is_symlink():raise BoundaryError("untrusted_runtime_directory")
        directory.chmod(0o700)
    target=checkouts/head
    if not target.exists():
        with tempfile.TemporaryDirectory(prefix="candidate-",dir=checkouts) as temporary:
            candidate=Path(temporary)/"repo"
            run_git(checkouts,"clone","--no-checkout","--single-branch","--branch",branch,"--no-tags",f"https://github.com/{repo}.git",str(candidate))
            if run_git(candidate,"rev-parse","HEAD")!=head:raise BoundaryError("source_changed_during_fetch")
            run_git(candidate,"checkout","--detach",head)
            if run_git(candidate,"status","--porcelain"):raise BoundaryError("source_checkout_dirty")
            candidate.replace(target)
    if target.is_symlink() or run_git(target,"rev-parse","HEAD")!=head or run_git(target,"status","--porcelain") or run_git(target,"remote","get-url","origin")!=f"https://github.com/{repo}.git":
        raise BoundaryError("source_checkout_not_exact_clean_owned")
    if source_revision(api)!=(repo,branch,head):raise BoundaryError("source_changed_before_exec")
    for name in ("scripts/ai_delivery.py","scripts/ai-delivery-policy.json"):
        entry=target/name
        if not entry.is_file() or not entry.resolve().is_relative_to(target.resolve()) or entry.is_symlink() or entry.parent.is_symlink():
            raise BoundaryError("controller_not_deployed_as_regular_trusted_files")
    command=[sys.executable,str(target/"scripts/ai_delivery.py"),"--apply","--state-dir",str(state),"--policy",str(target/"scripts/ai-delivery-policy.json"),"--report",str(report),"--budget",str(budget)]
    stdout,stderr=logs/"ai-delivery.stdout.log",logs/"ai-delivery.stderr.log"
    rotate(stdout);rotate(stderr)
    with stdout.open("a") as out,stderr.open("a") as error:
        result=runner(command,cwd=target,stdout=out,stderr=error,timeout=2400,check=False)
    return {"sourceRepo":repo,"branch":branch,"workerRevision":head,"controllerExitCode":result.returncode,"commandMode":"single_cycle"}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir",type=Path,required=True)
    parser.add_argument("--checkout-root",type=Path,required=True)
    parser.add_argument("--log-dir",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--budget",type=int,default=3,choices=range(1,6))
    args=parser.parse_args()
    args.state_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    args.log_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    if args.state_dir.is_symlink() or args.log_dir.is_symlink():raise SystemExit("untrusted_runtime_directory")
    rotate(args.log_dir/"launcher.stdout.log");rotate(args.log_dir/"launcher.stderr.log")
    with (args.state_dir/"launcher.lock").open("w") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            result=launch(GitHub(),args.state_dir,args.checkout_root,args.log_dir,args.report,budget=args.budget)
            print(json.dumps(result))
            if result["controllerExitCode"]:raise SystemExit(result["controllerExitCode"])
        except (BoundaryError,merge.APIError,KeyError,TypeError,ValueError,subprocess.TimeoutExpired,BlockingIOError) as exc:
            result={"outcome":"held","reason":str(exc) if isinstance(exc,BoundaryError) else type(exc).__name__}
            args.report.write_text(json.dumps(result,indent=2)+"\n")
            with (args.state_dir/"launcher-receipts.jsonl").open("a") as receipt:receipt.write(json.dumps(result)+"\n")
            print(json.dumps(result))
            raise SystemExit(1) from None


if __name__=="__main__":main()
