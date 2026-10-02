"""Hermetic proposal, ownership, retry, and protected-delivery boundary tests."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ai_delivery as delivery
import ai_proposal as proposal
import global_auto_merge as merge
import read_ownership_feed as ownership


def clean(**extra):
    return {"verdict":"clean","summary":"No findings","patches":[],"resolved_thread_ids":[],**extra}


def policy():
    return {"leasesVerifiedAt":datetime.now(timezone.utc).isoformat(), "leases":[]}


def test_tool_free_backend_uses_empty_cwd_schema_and_existing_model(tmp_path,monkeypatch):
    monkeypatch.setenv("GH_TOKEN","fake-credential")
    monkeypatch.setenv("SSH_AUTH_SOCK","fake-socket")
    def runner(args,**kwargs):
        assert "--ignore-user-config" in args and "--ignore-rules" in args and "--ephemeral" in args
        for value in ["features.shell_tool=false","features.unified_exec=false","features.multi_agent=false","mcp_servers={}","apps._default.enabled=false","gpt-5.5","features.hooks=false","project_doc_max_bytes=0"]:
            assert value in args
        assert "GH_TOKEN" not in kwargs["env"] and "SSH_AUTH_SOCK" not in kwargs["env"]
        assert not (kwargs["cwd"] / ".git").exists()
        Path(args[args.index("--output-last-message")+1]).write_text(json.dumps(clean()))
        return SimpleNamespace(returncode=0,stdout=json.dumps({"type":"item.completed","item":{"type":"agent_message"}}))
    assert proposal.propose({"files":[]},runner=runner)["verdict"] == "clean"


@pytest.mark.parametrize("kind",["command_execution","mcp_tool_call","file_change","web_search","unknown_tool"])
def test_unexpected_model_tools_fail_closed(kind):
    def runner(args,**kwargs):
        return SimpleNamespace(returncode=0,stdout=json.dumps({"type":"item.completed","item":{"type":kind}}))
    with pytest.raises(proposal.BoundaryError,match="unexpected_model_tool_call"):
        proposal.propose({},runner=runner)


@pytest.mark.parametrize("name",["../x","/tmp/x",".git/config",".github/workflows/x.yml",".codex/config.toml",".env","AGENTS.md","scripts/ai_delivery.py",".","a\\b","./.git/config","./.github/workflows/ci.yml","./.codex/config.toml","./secrets/token.txt","a//x.py","a/./x.py","x/.git/config",".github/CODEOWNERS",".GIT/config","agents.md",".ENV","scripts/verify_ai_receipt.py","scripts/read_ownership_feed.py"])
def test_protected_or_traversal_patch_is_rejected(tmp_path,name):
    with pytest.raises(proposal.BoundaryError):
        proposal.apply_patches(tmp_path,[{"path":name,"original_sha256":None,"content":"x"}])


def test_patch_set_is_hash_checked_before_any_write(tmp_path):
    (tmp_path/"a.py").write_text("a=1\n")
    patches=[{"path":"a.py","original_sha256":hashlib.sha256(b"a=1\n").hexdigest(),"content":"a=2\n"},
             {"path":"b.py","original_sha256":"incorrect","content":"b=2\n"}]
    with pytest.raises(proposal.BoundaryError,match="hash_mismatch"):
        proposal.apply_patches(tmp_path,patches)
    assert (tmp_path/"a.py").read_text()=="a=1\n" and not (tmp_path/"b.py").exists()


def test_symlink_patch_cannot_escape(tmp_path):
    target=tmp_path/"outside"; target.mkdir(); (tmp_path/"link").symlink_to(target)
    with pytest.raises(proposal.BoundaryError,match="symlink"):
        proposal.apply_patches(tmp_path,[{"path":"link/x","original_sha256":None,"content":"x"}])


def test_duplicate_and_secret_patches_are_rejected(tmp_path):
    row={"path":"a.py","original_sha256":None,"content":"x"}
    with pytest.raises(proposal.BoundaryError,match="duplicate"):
        proposal.apply_patches(tmp_path,[row,row])
    with pytest.raises(proposal.BoundaryError,match="secret"):
        proposal.apply_patches(tmp_path,[{**row,"content":"ghp_"+"x"*30}])


def test_attempt_budget_and_durable_receipt_survive_restart(tmp_path,monkeypatch):
    ledger=delivery.Ledger(tmp_path)
    assert ledger.reserve("dizhaky/example",1,"a")
    assert not ledger.reserve("dizhaky/example",1,"a")
    assert ledger.reserve("dizhaky/example",1,"a",cooldown=0)
    assert not ledger.reserve("dizhaky/example",1,"a",cooldown=0)
    ledger.record({"repo":"dizhaky/example","number":1,"head":"a","outcome":"blocked","reason":"budget"})
    other=delivery.Ledger(tmp_path)
    assert not other.reserve("dizhaky/example",1,"a",cooldown=0)
    assert json.loads((tmp_path/"receipts.jsonl").read_text())["reason"]=="budget"


def test_ownership_excludes_admin_org_and_archived_repo():
    class API:
        def rest(self,path,**kwargs):
            if path=="user":return {"login":"dizhaky","id":213320850}
            assert "affiliation=owner" in path and kwargs["paginate"]
            return [{"full_name":name,"owner":{"login":name.split("/")[0],"id":213320850},"permissions":{"admin":True},"archived":archived,"disabled":False} for name,archived in [("dizhaky/live",False),("JHJ-Corp/admin",False),("dizhaky/old",True)]]
    owner,rows=delivery.owned_repositories(API())
    assert owner=="dizhaky" and [row["full_name"] for row in rows]==["dizhaky/live"]


@pytest.mark.parametrize("drift",["transferred","renamed","owner_id","owner_missing","admin_shape","archived_shape","disabled_shape"])
def test_authority_uses_actual_native_repository_owner_after_redirect(delivery_flow,monkeypatch,drift):
    api,ledger=delivery_flow;original=api.rest
    def rest(path,**kwargs):
        data=original(path,**kwargs)
        if path=="repos/dizhaky/example":
            if drift=="transferred":data.update(full_name="JHJ-Corp/example",owner={"login":"JHJ-Corp","id":999})
            if drift=="renamed":data["full_name"]="dizhaky/another"
            if drift=="owner_id":data["owner"]["id"]=999
            if drift=="owner_missing":data.pop("owner")
            if drift=="admin_shape":data["permissions"]["admin"]="true"
            if drift=="archived_shape":data["archived"]=None
            if drift=="disabled_shape":data["disabled"]=0
        return data
    monkeypatch.setattr(api,"rest",rest)
    result=delivery.deliver(api,ledger,policy(),"dizhaky/example",{"number":1},apply=True,backend=lambda context:clean())
    assert result["outcome"]=="blocked" and result["reason"]=="ownership_changed"
    assert api.actions==[]


def test_active_lease_and_stale_snapshot_block():
    p=policy(); pr={"number":1,"head":{"ref":"work"}}
    p["leases"]=[{"repo":"dizhaky/example","number":1,"expiresAt":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}]
    assert delivery.lease_hold(p,"dizhaky/example",pr)=="active_owner_lease"
    p["leasesVerifiedAt"]=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
    assert delivery.lease_hold(p,"dizhaky/example",pr)=="ownership_snapshot_stale"


@pytest.mark.parametrize("field",["created_at","updated_at"])
def test_pr_activity_newer_than_snapshot_waits_for_automated_refresh(field):
    p=policy(); pr={"number":1,"head":{"ref":"work"},field:(datetime.now(timezone.utc)+timedelta(seconds=1)).isoformat()}
    assert delivery.lease_hold(p,"dizhaky/example",pr)=="pr_activity_newer_than_ownership_snapshot"
    p["leasesVerifiedAt"]=(datetime.now(timezone.utc)+timedelta(seconds=2)).isoformat()
    assert delivery.lease_hold(p,"dizhaky/example",pr) is None


class DeliveryAPI:
    def __init__(self):
        self.actions=[]; self.status_rows=[]
        self.pr={"number":1,"state":"open","draft":False,"head":{"sha":"a"*40,"ref":"work","repo":{"full_name":"dizhaky/example"}},"base":{"ref":"main"},"merged":False,"auto_merge":None}
    def rest(self,path,**kwargs):
        if path=="user":return {"login":"dizhaky","id":213320850}
        if path.endswith("/.github/commits/main"):return {"sha":"c"*40}
        if path.endswith("/statuses?per_page=100"):return self.status_rows
        if path.endswith("/reviews?per_page=100") or path.endswith("/comments?per_page=100"):return []
        if path.endswith("/pulls/1"):return copy.deepcopy(self.pr)
        return {"full_name":path.removeprefix("repos/"),"owner":{"login":"dizhaky","id":213320850},"archived":False,"disabled":False,"permissions":{"admin":True},"allow_auto_merge":True,"allow_squash_merge":True,"default_branch":"main"}
    def status(self,repo,head,state,description,worker_revision=None):
        self.actions.append(("status",state,head))
        self.status_rows.insert(0,{"context":delivery.AI_CONTEXT,"state":state,"description":description,"created_at":datetime.now(timezone.utc).isoformat(),"creator":{"login":"dizhaky"},"target_url":"https://github.com/dizhaky/.github/commit/"+str(worker_revision)})
    def merge(self,repo,number,method,head):
        self.actions.append(("merge",repo,number,method,head)); self.pr["auto_merge"]={"enabled_at":"now"}
    def threads(self,*args):return []
    def resolve_thread(self,thread):self.actions.append(("resolve",thread))
    def signatures_required(self,*args):return False
    def create_signed_commit(self,repo,branch,parent,files,tree):
        self.actions.append(("server_commit",repo,branch,parent,tree))
        assert files[0]["path"]=="a.py"
        return "b"*40


@pytest.fixture
def delivery_flow(monkeypatch,tmp_path):
    api=DeliveryAPI(); ledger=delivery.Ledger(tmp_path)
    monkeypatch.setattr(delivery,"precheck",lambda *args:(copy.deepcopy(api.pr),None,[],[]))
    monkeypatch.setattr(delivery,"context_from_clone",lambda *args:{"files":[]})
    monkeypatch.setattr(delivery,"run_git",lambda root,*args:"c"*40 if args==("rev-parse","HEAD") else "")
    monkeypatch.setattr(merge,"evidence",lambda *args:({"headRefOid":"a"*40,"autoMergeRequest":None},None))
    return api,ledger


def test_clean_review_publishes_current_head_receipt_then_native_queue(delivery_flow):
    api,ledger=delivery_flow
    result=delivery.deliver(api,ledger,policy(),"dizhaky/example",{"number":1},apply=True,backend=lambda ctx:clean())
    assert result["outcome"]=="verified" and result["nativeState"]=="queued"
    assert api.actions==[("status","pending","a"*40),("status","success","a"*40),("merge","dizhaky/example",1,"squash","a"*40)]
    assert merge.verified_ai_receipt(api.status_rows,"dizhaky","c"*40)


def test_head_race_never_publishes_success_or_merges(delivery_flow,monkeypatch):
    api,ledger=delivery_flow; count=[0]
    def check(*args):
        count[0]+=1; p=copy.deepcopy(api.pr)
        if count[0]>1:p["head"]["sha"]="b"*40
        return p,None,[],[]
    monkeypatch.setattr(delivery,"precheck",check)
    result=delivery.deliver(api,ledger,policy(),"dizhaky/example",{"number":1},apply=True,backend=lambda ctx:clean())
    assert result["reason"]=="head_or_owner_changed_before_status"
    assert api.actions==[("status","pending","a"*40)]


def test_required_changes_request_is_not_self_approved(delivery_flow,monkeypatch):
    api,ledger=delivery_flow
    monkeypatch.setattr(delivery,"precheck",lambda *args:(copy.deepcopy(api.pr),"changes_requested",[],[]))
    result=delivery.deliver(api,ledger,policy(),"dizhaky/example",{"number":1},apply=True,backend=lambda ctx:clean())
    assert result["reason"]=="changes_requested" and not any(a[0]=="merge" for a in api.actions)


def test_stale_or_unshipped_worker_cannot_write_success(delivery_flow,monkeypatch):
    api,ledger=delivery_flow
    monkeypatch.setattr(delivery,"run_git",lambda *args:"dirty")
    result=delivery.deliver(api,ledger,policy(),"dizhaky/example",{"number":1},apply=True,backend=lambda ctx:clean())
    assert result["reason"]=="trusted_worker_revision_not_deployed" and api.actions==[]


def test_round_robin_receipts_prevent_first_repo_starvation(tmp_path):
    ledger=delivery.Ledger(tmp_path)
    assert ledger.priority("dizhaky/first",1)==0
    ledger.seen("dizhaky/first",1)
    assert ledger.priority("dizhaky/first",1)>ledger.priority("dizhaky/last",99)


def test_same_name_check_or_wrong_actor_is_not_ai_receipt():
    status={"context":merge.AI_CONTEXT,"state":"success","creator":{"login":"github-actions[bot]"},"target_url":"https://github.com/dizhaky/.github/commit/"+"c"*40,"description":"AI verified receipt:"+"f"*64+" worker:"+"c"*40}
    assert not merge.verified_ai_receipt([status],"dizhaky","c"*40)
    status["creator"]["login"]="dizhaky"
    assert merge.verified_ai_receipt([status],"dizhaky","c"*40)
    assert not merge.verified_ai_receipt([status],"dizhaky","d"*40)


@pytest.mark.parametrize("missing_review",[False,True])
@pytest.mark.parametrize("native_signing,configured_signing",[(False,False),(True,False),(False,True)])
def test_repair_preserves_signing_policy_no_force_and_waits_for_native_ci(delivery_flow,monkeypatch,missing_review,native_signing,configured_signing):
    api,ledger=delivery_flow; calls=[]; reviews=[]
    monkeypatch.setattr(api,"signatures_required",lambda *args:native_signing)
    if missing_review:
        api.pr["deliveryFailedChecks"]=["CI"]
        monkeypatch.setattr(delivery,"precheck",lambda *args:(copy.deepcopy(api.pr),"required_review_missing",[],[]))
    def git(root,*args):
        calls.append(args)
        if args and args[0]=="clone":
            clone=Path(args[-1]);clone.mkdir();(clone/"a.py").write_text("value=1\n")
        if args==("rev-parse","HEAD"):
            return "c"*40 if root==ROOT else "b"*40
        if args==("diff","--name-only"):return "a.py"
        if args==("config","--type=bool","--default=false","--get","commit.gpgsign"):return str(configured_signing).lower()
        if args[:3]==("ls-files","--stage","-z"):
            blob=hashlib.sha1(b"blob 8\0value=2\n").hexdigest()
            return "100644 "+blob+" 0\ta.py\0"
        if args==("write-tree",):return "d"*40
        return ""
    monkeypatch.setattr(delivery,"run_git",git)
    def backend(context):
        reviews.append(context)
        if len(reviews)>1:return clean()
        return clean(verdict="repair",patches=[{"path":"a.py","original_sha256":hashlib.sha256(b"value=1\n").hexdigest(),"content":"value=2\n"}])
    result=delivery.deliver(api,ledger,policy(),"dizhaky/example",{"number":1},apply=True,backend=backend)
    assert result["outcome"]=="repaired_waiting_native_ci" and result["newHead"]=="b"*40
    assert result["requiredTestBackend"]=="native_ci_on_new_head"
    commits=[call for call in calls if call[0]=="commit"]
    server=native_signing and not configured_signing
    assert len(commits)==(0 if server else 1)
    if commits:assert ("-S" in commits[0])==configured_signing
    assert not any("commit.gpgsign=false" in call for call in calls)
    assert (("push","origin","HEAD:refs/heads/work") in calls)==(not server)
    assert not any("--force" in call or "--admin" in call for call in calls)
    assert len(reviews)==2
    assert api.actions==[("status","pending","a"*40),*(([("server_commit","dizhaky/example","work","a"*40,"d"*40)]) if server else [])]


@pytest.mark.parametrize("protected,rules,expected",[(True,[],True),(False,[],False),(None,[],False),(False,[{"type":"required_signatures"}],True)])
def test_native_signature_policy_uses_live_protection_and_branch_rules(protected,rules,expected):
    class API(delivery.GitHub):
        def rest(self,path,**kwargs):
            if path=="graphql":return {"data":{"repository":{"ref":{"branchProtectionRule":None if protected is None else {"requiresCommitSignatures":protected}}}}}
            assert "/rules/branches/main?" in path and kwargs["paginate"]
            return rules
    assert API().signatures_required("dizhaky/example","main")==expected


def test_unknown_native_signature_policy_fails_closed():
    class API(delivery.GitHub):
        def rest(self,*args,**kwargs):return {"data":{"repository":{"ref":None}}}
    with pytest.raises(proposal.BoundaryError,match="native_signing_policy_unknown"):
        API().signatures_required("dizhaky/example","main")


@pytest.mark.parametrize("problem",["unavailable_signer","new_signature_requirement"])
def test_required_signing_failure_or_policy_drift_never_pushes(delivery_flow,monkeypatch,problem):
    api,ledger=delivery_flow; calls=[]; requirements=iter([True] if problem=="unavailable_signer" else [False,True])
    monkeypatch.setattr(api,"signatures_required",lambda *args:next(requirements))
    def git(root,*args):
        calls.append(args)
        if args[0]=="clone":
            clone=Path(args[-1]);clone.mkdir();(clone/"a.py").write_text("value=1\n")
        if args==("rev-parse","HEAD"):return "c"*40 if root==ROOT else "b"*40
        if args==("diff","--name-only"):return "a.py"
        if args==("config","--type=bool","--default=false","--get","commit.gpgsign"):return "true" if problem=="unavailable_signer" else "false"
        if args[0]=="commit" and problem=="unavailable_signer":
            assert "-S" in args
            raise proposal.BoundaryError("git_command_failed")
        return ""
    monkeypatch.setattr(delivery,"run_git",git)
    outputs=iter([clean(verdict="repair",patches=[{"path":"a.py","original_sha256":hashlib.sha256(b"value=1\n").hexdigest(),"content":"value=2\n"}]),clean()])
    result=delivery.deliver(api,ledger,policy(),"dizhaky/example",{"number":1},apply=True,backend=lambda ctx:next(outputs))
    assert result["outcome"]=="blocked"
    assert result["reason"]==("git_command_failed" if problem=="unavailable_signer" else "signing_policy_changed_before_push")
    assert not any(call[0]=="push" for call in calls)
    assert api.actions==[("status","pending","a"*40)]


@pytest.mark.parametrize("mode,blob",[("100755",None),("100644","f"*40)])
def test_server_signing_rejects_modes_or_staging_transform_before_write(delivery_flow,tmp_path,monkeypatch,mode,blob):
    api,_=delivery_flow;(tmp_path/"a.py").write_text("value=2\n")
    actual=hashlib.sha1(b"blob 8\0value=2\n").hexdigest()
    monkeypatch.setattr(delivery,"run_git",lambda *args:mode+" "+(blob or actual)+" 0\ta.py\0")
    with pytest.raises(proposal.BoundaryError):delivery.server_signed_patch(api,tmp_path,"dizhaky/example",api.pr,["a.py"])
    assert api.actions==[]


@pytest.mark.parametrize("problem",[None,"signature","tree","author","parent","ref","default_head"])
def test_server_signed_commit_verifies_graph_and_independent_rest(problem):
    writes=[]
    class API(delivery.GitHub):
        def rest(self,path,**kwargs):
            if path=="user":return {"login":"dizhaky","id":213320850}
            if path=="repos/dizhaky/example":return {"full_name":"dizhaky/example","owner":{"login":"dizhaky","id":213320850},"archived":False,"disabled":False,"permissions":{"admin":True},"default_branch":"work" if problem=="default_head" else "main"}
            if path=="graphql":
                assert kwargs["method"]=="POST"
                body=kwargs["body"]["variables"]["input"]
                assert body["expectedHeadOid"]=="a"*40 and body["branch"]=={"repositoryNameWithOwner":"dizhaky/example","branchName":"work"}
                writes.append(body)
                return {"data":{"createCommitOnBranch":{"commit":{"oid":"b"*40,"tree":{"oid":"c"*40 if problem=="tree" else "d"*40},"signature":{"isValid":problem!="signature","state":"VALID"}},"ref":{"name":"work","target":{"oid":"b"*40}}}}}
            if "/git/ref/" in path:return {"ref":"refs/heads/work","object":{"sha":"c"*40 if problem=="ref" else "b"*40}}
            assert path.endswith("/commits/"+"b"*40)
            return {"commit":{"tree":{"sha":"d"*40},"verification":{"verified":True,"reason":"valid"}},"parents":[{"sha":"c"*40 if problem=="parent" else "a"*40}],"author":{"id":999 if problem=="author" else 213320850,"login":"dizhaky"}}
    if problem:
        with pytest.raises(proposal.BoundaryError):API().create_signed_commit("dizhaky/example","work","a"*40,[{"path":"a.py","contents":"dmFsdWU9Mgo="}],"d"*40)
        assert len(writes)==(0 if problem=="default_head" else 1)
    else:assert API().create_signed_commit("dizhaky/example","work","a"*40,[{"path":"a.py","contents":"dmFsdWU9Mgo="}],"d"*40)=="b"*40


@pytest.mark.parametrize("problem",["draft_or_closed","explicit_hold","external_head_repository","signing_changed","ambiguous_write"])
def test_server_repair_last_boundary_drift_or_ambiguous_write_never_pushes(delivery_flow,monkeypatch,problem):
    api,ledger=delivery_flow;calls=[];checks=[];config_reads=[]
    monkeypatch.setattr(api,"signatures_required",lambda *args:True)
    def precheck(*args):
        checks.append(True)
        return copy.deepcopy(api.pr),problem if len(checks)==3 and problem in {"draft_or_closed","explicit_hold","external_head_repository"} else None,[],[]
    monkeypatch.setattr(delivery,"precheck",precheck)
    def git(root,*args):
        calls.append(args)
        if args[0]=="clone":
            clone=Path(args[-1]);clone.mkdir();(clone/"a.py").write_text("value=1\n")
        if args==("rev-parse","HEAD"):return "c"*40 if root==ROOT else "b"*40
        if args==("diff","--name-only"):return "a.py"
        if args==("config","--type=bool","--default=false","--get","commit.gpgsign"):
            config_reads.append(True);return "true" if problem=="signing_changed" and len(config_reads)>1 else "false"
        if args[:3]==("ls-files","--stage","-z"):return "100644 "+hashlib.sha1(b"blob 8\0value=2\n").hexdigest()+" 0\ta.py\0"
        if args==("write-tree",):return "d"*40
        return ""
    monkeypatch.setattr(delivery,"run_git",git)
    if problem=="ambiguous_write":
        def commit(*args):
            api.actions.append(("ambiguous_server_write",))
            raise merge.APIError("connection_closed_after_request")
        monkeypatch.setattr(api,"create_signed_commit",commit)
    outputs=iter([clean(verdict="repair",patches=[{"path":"a.py","original_sha256":hashlib.sha256(b"value=1\n").hexdigest(),"content":"value=2\n"}]),clean()])
    result=delivery.deliver(api,ledger,policy(),"dizhaky/example",{"number":1},apply=True,backend=lambda ctx:next(outputs))
    assert result["outcome"]=="blocked"
    assert not any(call[0] in {"push","commit"} for call in calls)
    assert api.actions==[("status","pending","a"*40),*([("ambiguous_server_write",)] if problem=="ambiguous_write" else [])]


def test_server_api_ambiguous_post_is_never_retried(monkeypatch):
    writes=[]
    def rest(self,path,**kwargs):
        writes.append((path,kwargs.get("method")))
        raise merge.APIError("connection_closed_after_request")
    monkeypatch.setattr(merge.GitHub,"rest",rest)
    with pytest.raises(merge.APIError):delivery.GitHub().rest("graphql",method="POST",body={})
    assert writes==[("graphql","POST")]


def test_clean_native_ci_review_does_not_require_local_dependency_bootstrap(delivery_flow):
    api,ledger=delivery_flow;p=policy();p["tests"]={}
    result=delivery.deliver(api,ledger,p,"dizhaky/example",{"number":1},apply=True,backend=lambda ctx:clean())
    assert result["outcome"]=="verified"


def test_ai_cannot_add_host_import_shadow_to_controller_source(delivery_flow):
    api,ledger=delivery_flow
    repair=clean(verdict="repair",patches=[{"path":"scripts/subprocess.py","original_sha256":None,"content":"raise RuntimeError('host shadow')\n"}])
    result=delivery.deliver(api,ledger,policy(),"dizhaky/.github",{"number":1},apply=True,backend=lambda ctx:repair)
    assert result["outcome"]=="blocked" and result["reason"]=="protected_controller_source_change"
    assert api.actions==[("status","pending","a"*40)]


@pytest.mark.parametrize("apply",[False,True])
def test_reverse_pr_with_default_branch_head_is_held_before_any_write(delivery_flow,apply):
    api,ledger=delivery_flow;api.pr["head"]["ref"]="main";api.pr["base"]["ref"]="feature"
    result=delivery.deliver(api,ledger,policy(),"dizhaky/example",{"number":1},apply=apply,backend=lambda ctx:clean())
    assert result["outcome"]=="blocked" and result["reason"]=="default_branch_head_prohibited"
    assert api.actions==[]


def test_default_branch_changed_after_review_cannot_receive_success_or_enrollment(delivery_flow,monkeypatch):
    api,ledger=delivery_flow;original=api.rest;changed=False
    def rest(path,**kwargs):
        data=original(path,**kwargs)
        if path=="repos/dizhaky/example" and changed:data["default_branch"]="work"
        return data
    monkeypatch.setattr(api,"rest",rest)
    def backend(ctx):
        nonlocal changed
        changed=True
        return clean()
    result=delivery.deliver(api,ledger,policy(),"dizhaky/example",{"number":1},apply=True,backend=backend)
    assert result["reason"]=="default_branch_head_prohibited"
    assert api.actions==[("status","pending","a"*40)]


def test_renewable_lease_adapter_validates_actual_json_and_failure():
    snapshot={key:policy()[key] for key in ("leasesVerifiedAt","leases")}
    p={"leaseCommand":["trusted-lease-reader"]}
    refreshed=delivery.refresh_leases(p,runner=lambda *args,**kw:SimpleNamespace(returncode=0,stdout=json.dumps(snapshot)))
    assert refreshed["leases"]==[] and "leasesVerifiedAt" in refreshed
    with pytest.raises(proposal.BoundaryError,match="ownership_adapter_failed"):
        delivery.refresh_leases(p,runner=lambda *args,**kw:SimpleNamespace(returncode=1,stdout=""))


def test_same_head_new_review_reopens_evidence(tmp_path):
    ledger=delivery.Ledger(tmp_path)
    assert not ledger.review_changed("dizhaky/example",1,"a",[],[])
    assert ledger.review_changed("dizhaky/example",1,"a",[],[{"body":"real finding"}])
    assert not ledger.review_changed("dizhaky/example",1,"a",[],[{"body":"real finding"}])


def test_review_digest_change_invalidates_trusted_receipt(delivery_flow):
    api,ledger=delivery_flow
    result=delivery.deliver(api,ledger,policy(),"dizhaky/example",{"number":1},apply=True,backend=lambda ctx:clean())
    assert result["outcome"]=="verified"
    original=api.rest
    api.rest=lambda path,**kw: [{"body":"new required finding","submitted_at":"2026-10-02T00:00:00Z"}] if "/reviews?" in path else original(path,**kw)
    assert merge.ai_receipt_gate(api,"dizhaky/example",1,"a"*40,"dizhaky","c"*40)=="review_changed_after_ai_receipt"


def test_required_app_binding_cannot_be_satisfied_by_spoof_check():
    pr={"state":"OPEN","isDraft":False,"mergeable":"MERGEABLE","mergeStateStatus":"CLEAN","reviewDecision":"APPROVED","baseRef":{"branchProtectionRule":{"requiredStatusCheckContexts":["CI"],"requiredStatusChecks":[{"context":"CI","appId":15368}]}}}
    spoof=[{"name":"CI","status":"completed","conclusion":"success","app":{"id":1}}]
    assert merge.blocker(pr,[],spoof,[],[])=="required_check_app_mismatch"


@pytest.mark.parametrize("suffix",[""," UNEXPECTED arbitrary error tail"])
def test_only_exact_observed_skill_budget_warning_is_allowed(suffix):
    message="Exceeded skills context budget. All skill descriptions were removed and 402 additional skills were not included in the model-visible skills list."+suffix
    def runner(args,**kw):
        Path(args[args.index("--output-last-message")+1]).write_text(json.dumps(clean()))
        return SimpleNamespace(returncode=0,stdout=json.dumps({"type":"item.completed","item":{"type":"error","message":message}}))
    if suffix:
        with pytest.raises(proposal.BoundaryError,match="unexpected_model_tool_call"):
            proposal.propose({},runner=runner)
    else:
        assert proposal.propose({},runner=runner)["verdict"]=="clean"


def test_required_native_reviews_are_held_without_ai_self_approval(delivery_flow,monkeypatch):
    api,ledger=delivery_flow
    monkeypatch.setattr(delivery,"precheck",lambda *args:(copy.deepcopy(api.pr),"required_review_missing",[],[]))
    result=delivery.deliver(api,ledger,policy(),"dizhaky/example",{"number":1},apply=True,backend=lambda ctx:clean())
    assert result["reason"]=="required_review_missing" and api.actions==[]


def test_model_sees_all_inline_replies_and_never_truncated_review_findings(tmp_path,monkeypatch):
    replies=[{"id":1,"body":"initial benign comment"},{"id":2,"in_reply_to_id":1,"body":"later actionable correctness finding"}]
    class API:
        def rest(self,path,**kw):
            assert kw.get("paginate")
            if "/comments?" in path:return replies
            if "/check-runs?" in path:return [{"check_runs":[]}]
            return []
    monkeypatch.setattr(delivery,"run_git",lambda *args:"")
    pr={"number":1,"head":{"sha":"a"*40}}
    context=delivery.context_from_clone(API(),tmp_path,"dizhaky/example",pr,None,[],[])
    assert [row["body"] for row in context["comments"]]==[row["body"] for row in replies]
    assert context["comments"][1]["in_reply_to_id"]==1
    with pytest.raises(proposal.BoundaryError,match="review_evidence_too_large"):
        delivery.context_from_clone(API(),tmp_path,"dizhaky/example",pr,None,[],[{"body":"x"*12_001}])


@pytest.mark.parametrize("field",["archived","disabled"])
def test_live_authority_drift_blocks_all_delivery_writes(delivery_flow,field):
    api,ledger=delivery_flow;original=api.rest
    def read(path,**kw):
        row=original(path,**kw)
        if path=="repos/dizhaky/example":row={**row,field:True}
        return row
    api.rest=read
    result=delivery.deliver(api,ledger,policy(),"dizhaky/example",{"number":1},apply=True,backend=lambda ctx:clean())
    assert result["reason"]=="ownership_changed" and api.actions==[]


def test_repository_wildcard_branch_lease_holds_all_current_prs():
    p=policy();p["leases"]=[{"repo":"dizhaky/example","branch":"*","expiresAt":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}]
    assert delivery.lease_hold(p,"dizhaky/example",{"number":2,"head":{"ref":"other-work"}})=="active_owner_lease"


def test_case_alias_patch_set_is_rejected_before_writes(tmp_path):
    with pytest.raises(proposal.BoundaryError,match="duplicate"):
        proposal.apply_patches(tmp_path,[{"path":name,"original_sha256":None,"content":"x"} for name in ("file.py","FILE.py")])
    assert not (tmp_path/"file.py").exists()


def test_one_repository_read_failure_does_not_starve_other_owned_repos(tmp_path,monkeypatch):
    class API:
        def rate_limit_remaining(self):return 5000,5000
        def rest(self,path,**kw):
            if "dizhaky/broken/pulls" in path:raise merge.APIError("read failed")
            return [{"number":1,"draft":False}]
    monkeypatch.setattr(delivery,"owned_repositories",lambda api:("dizhaky",[{"full_name":"dizhaky/broken"},{"full_name":"dizhaky/live"}]))
    monkeypatch.setattr(delivery,"deliver",lambda api,ledger,p,repo,pr,**kw:{"repo":repo,"number":pr["number"],"outcome":"would_review"})
    report=delivery.cycle(API(),delivery.Ledger(tmp_path),policy())
    assert report["results"][0]["repo"]=="dizhaky/live"
    assert report["discoveryErrors"][0]["repo"]=="dizhaky/broken"


@pytest.mark.parametrize("budget",[1,3])
def test_busy_repository_cannot_starve_other_repositories(tmp_path,monkeypatch,budget):
    class API:
        def rate_limit_remaining(self):return 5000,5000
        def rest(self,path,**kw):
            count=10 if "dizhaky/busy/" in path else 1
            return [{"number":number,"draft":False} for number in range(1,count+1)]
    monkeypatch.setattr(delivery,"owned_repositories",lambda api:("dizhaky",[{"full_name":"dizhaky/busy"},{"full_name":"dizhaky/last"}]))
    monkeypatch.setattr(delivery,"deliver",lambda api,ledger,p,repo,pr,**kw:{"repo":repo,"number":pr["number"],"outcome":"would_review"})
    ledger=delivery.Ledger(tmp_path)
    first=delivery.cycle(API(),ledger,policy(),budget=budget)
    if budget==1:
        second=delivery.cycle(API(),ledger,policy(),budget=budget)
        assert second["results"][0]["repo"]=="dizhaky/last"
    else:
        assert [row["repo"] for row in first["results"][:2]]==["dizhaky/busy","dizhaky/last"]


def test_reporter_contains_no_enrollment_mutation_path():
    import inspect
    source=inspect.getsource(merge.reconcile)
    assert "api.merge(" not in source and 'method="PATCH"' not in source


def test_pending_native_ci_never_runs_model_or_posts_approval(delivery_flow,monkeypatch):
    api,ledger=delivery_flow
    monkeypatch.setattr(delivery,"precheck",lambda *args:(copy.deepcopy(api.pr),"checks_not_green",[],[]))
    def never(context):raise AssertionError("pending CI must hold before inference")
    result=delivery.deliver(api,ledger,policy(),"dizhaky/example",{"number":1},apply=True,backend=never)
    assert result["reason"]=="native_ci_pending" and api.actions==[]


@pytest.mark.parametrize("latest",["pending","success"])
def test_historic_failed_status_does_not_trigger_ai_repair(latest):
    class API(DeliveryAPI):
        def pull_request(self,*args):
            return {"headRefOid":"a"*40,"state":"OPEN","isDraft":False,"reviewDecision":None,"mergeable":"MERGEABLE","mergeStateStatus":"CLEAN","viewerCanEnableAutoMerge":True,"baseRef":{"branchProtectionRule":{"requiresStatusChecks":True,"requiredStatusCheckContexts":["CI"]}}}
        def rest(self,path,**kw):
            if "/check-runs?" in path:return [{"check_runs":[]}]
            if "/statuses?" in path:return [{"context":"CI","state":latest},{"context":"CI","state":"failure"}]
            if "/rules/branches/" in path:return []
            return super().rest(path,**kw)
    pr,reason,_,_=delivery.precheck(API(),"dizhaky/example",1)
    assert pr["deliveryFailedStatuses"]==[]
    assert pr["deliveryNativeEvidence"]["statuses"]==[{"context":"CI","state":latest,"creator":None}]
    assert reason==("statuses_not_green" if latest=="pending" else None)


@pytest.mark.parametrize("problem",[None,"wrong_issue","wrong_actor_id","stale_update"])
def test_fixed_private_ownership_comment_binds_owner_issue_and_actual_update(problem):
    timestamp=datetime.now(timezone.utc).isoformat()
    row={"id":5960945356,"user":{"login":"dizhaky","id":213320850},"issue_url":"https://api.github.com/repos/dizhaky/github-infra/issues/49","updated_at":timestamp,"body":ownership.MARKER+json.dumps({"leasesVerifiedAt":timestamp,"leases":[]})}
    if problem=="wrong_issue":row["issue_url"]="https://api.github.com/repos/dizhaky/github-infra/issues/50"
    if problem=="wrong_actor_id":row["user"]["id"]=999
    if problem=="stale_update":row["updated_at"]=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
    class API:
        def rest(self,path,**kw):
            if path=="user":return {"login":"dizhaky","id":213320850}
            if path=="repos/dizhaky/github-infra":return {"full_name":"dizhaky/github-infra","owner":{"login":"dizhaky","id":213320850},"archived":False,"disabled":False,"private":True,"permissions":{"admin":True}}
            assert path=="repos/dizhaky/github-infra/issues/comments/5960945356" and not kw.get("paginate")
            return row
    if problem:
        with pytest.raises(proposal.BoundaryError):ownership.read_feed(API(),"dizhaky/github-infra",49,"dizhaky",4500,5960945356)
    else:
        assert ownership.read_feed(API(),"dizhaky/github-infra",49,"dizhaky",4500,5960945356)["leases"]==[]


def test_backend_failure_receipt_contains_metadata_without_tool_arguments(tmp_path):
    target=tmp_path/"metadata.jsonl"
    def runner(*args,**kw):return SimpleNamespace(returncode=0,stdout=json.dumps({"type":"item.completed","item":{"type":"command_execution","command":"DO-NOT-PERSIST-RAW-ARGS"}}))
    with pytest.raises(proposal.BoundaryError):proposal.propose({},runner=runner,receipt_path=target)
    receipt=json.loads(target.read_text())
    assert receipt["model"]=="gpt-5.5" and receipt["toolEvents"]==1 and receipt["events"][0]["itemType"]=="command_execution"
    assert "DO-NOT-PERSIST" not in target.read_text()
