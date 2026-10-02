"""Trusted source gates and atomic single-cycle launcher; no network/PR execution."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import launch_ai_delivery as launch
from ai_proposal import BoundaryError

HEAD="a"*40


class API:
    def __init__(self,problem=None):self.problem=problem;self.branch_reads=0
    def signatures_required(self,repo,branch):
        from ai_delivery import GitHub
        return GitHub.signatures_required(self,repo,branch)
    def rest(self,path,**kwargs):
        if path=="graphql":return {"data":{"repository":{"ref":{"branchProtectionRule":{"requiresCommitSignatures":self.problem in {"unsigned_required","signature_without_classic_member"}}}}}}
        if path=="user":return {"login":"dizhaky","id":999 if self.problem=="wrong_identity" else 213320850}
        if path=="repos/dizhaky/.github":return {"full_name":"dizhaky/.github","owner":{"login":"dizhaky","id":213320850},"archived":False,"disabled":False,"permissions":{"admin":self.problem!="no_admin"},"default_branch":"main"}
        if path.endswith("/branches/main"):
            self.branch_reads+=1
            head="b"*40 if self.problem=="head_race" and self.branch_reads>1 else HEAD
            return {"protected":self.problem!="unprotected","commit":{"sha":head}}
        if path.endswith("/protection"):
            data={"required_status_checks":{"contexts":["CI",launch.AI_CONTEXT],"checks":[{"context":"CI","app_id":15368}]}}
            if self.problem!="signature_without_classic_member":data["required_signatures"]={"enabled":self.problem=="unsigned_required"}
            return data
        if "/rules/branches/" in path:return []
        if "/check-runs?" in path:return [{"check_runs":[{"name":"CI","status":"completed","conclusion":"failure" if self.problem=="failed_ci" else "success","app":{"id":1 if self.problem=="spoof_app" else 15368}}]}]
        if "/statuses?" in path:return []
        if "/commits/" in path:return {"commit":{"verification":{"verified":False}}}
        raise AssertionError(path)


@pytest.mark.parametrize("problem",["wrong_identity","no_admin","unprotected","failed_ci","spoof_app","unsigned_required","signature_without_classic_member"])
def test_native_source_gate_blocks_before_clone_or_execution(tmp_path,monkeypatch,problem):
    def never(*args,**kwargs):raise AssertionError("gates must fail before execution")
    monkeypatch.setattr(launch,"run_git",never)
    with pytest.raises(BoundaryError):launch.launch(API(problem),tmp_path/"state",tmp_path/"checkouts",tmp_path/"logs",tmp_path/"report.json",runner=never)


@pytest.mark.parametrize("problem",[None,"dirty","foreign_remote","head_race"])
def test_atomic_exact_checkout_and_second_native_verification(tmp_path,monkeypatch,problem):
    calls=[];executions=[]
    def git(root,*args):
        calls.append(args)
        if args[0]=="clone":
            candidate=Path(args[-1]);(candidate/"scripts").mkdir(parents=True)
            (candidate/"scripts/ai_delivery.py").write_text("trusted")
            (candidate/"scripts/ai-delivery-policy.json").write_text("{}")
        if args==("rev-parse","HEAD"):return HEAD
        if args==("status","--porcelain"):return " M scripts/ai_delivery.py" if problem=="dirty" else ""
        if args==("remote","get-url","origin"):return "https://github.com/outsider/.github.git" if problem=="foreign_remote" else "https://github.com/dizhaky/.github.git"
        return ""
    monkeypatch.setattr(launch,"run_git",git)
    def runner(command,**kwargs):executions.append((command,kwargs));return SimpleNamespace(returncode=0)
    args=(API(problem),tmp_path/"state",tmp_path/"checkouts",tmp_path/"logs",tmp_path/"report.json")
    if problem:
        with pytest.raises(BoundaryError):launch.launch(*args,runner=runner)
        assert executions==[]
    else:
        result=launch.launch(*args,runner=runner)
        assert result["workerRevision"]==HEAD and result["controllerExitCode"]==0
        command,kwargs=executions[0]
        assert kwargs["cwd"]==tmp_path/"checkouts"/HEAD
        assert "--apply" in command and "--daemon" not in command
        assert ("checkout","--detach",HEAD) in calls
        assert all(not word.startswith(("--force","--admin")) for call in calls for word in call)


def test_log_rotation_leaves_permanent_receipts_untouched(tmp_path):
    log=tmp_path/"ai-delivery.stdout.log";log.write_text("12345")
    receipts=tmp_path/"receipts.jsonl";receipts.write_text("permanent")
    launch.rotate(log,limit=5,keep=2)
    assert log.with_name(log.name+".1").read_text()=="12345"
    assert receipts.read_text()=="permanent"


def test_optional_scheduled_reporter_cannot_deadlock_native_source_ci():
    class Optional(API):
        def rest(self,path,**kwargs):
            data=super().rest(path,**kwargs)
            if "/check-runs?" in path:data[0]["check_runs"].append({"name":"Global Reporter","status":"in_progress","conclusion":None})
            return data
    assert launch.source_revision(Optional())==("dizhaky/.github","main",HEAD)


def test_launcher_governance_path_cannot_be_changed_by_ai(tmp_path):
    from ai_proposal import safe_path
    with pytest.raises(BoundaryError):safe_path(tmp_path,"scripts/LaUnCh_AI_DeLiVeRy.py")


def test_timeout_terminates_entire_owned_controller_process_group(monkeypatch,tmp_path):
    import subprocess
    waits=[];signals=[]
    class Process:
        pid=12345
        def wait(self,timeout):
            waits.append(timeout)
            if len(waits)==1:raise subprocess.TimeoutExpired("owned-controller",timeout)
            return -15
    monkeypatch.setattr(launch.subprocess,"Popen",lambda *args,**kwargs:Process() if kwargs["start_new_session"] else None)
    monkeypatch.setattr(launch.os,"killpg",lambda pid,kind:signals.append((pid,kind)))
    with pytest.raises(subprocess.TimeoutExpired):launch.run_controller(["trusted"],cwd=tmp_path,stdout=None,stderr=None,timeout=2400)
    assert signals==[(12345,launch.signal.SIGTERM)] and waits==[2400,5]
