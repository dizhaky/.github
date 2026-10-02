"""Read-only trusted guard for every existing local auto-merge writer."""
import argparse
import json
import global_auto_merge as merge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo",required=True)
    parser.add_argument("--number",type=int,required=True)
    parser.add_argument("--head",required=True)
    args = parser.parse_args()
    api = merge.GitHub()
    actor = api.rest("user")["login"]
    if args.repo.split("/")[0].casefold() != actor.casefold():
        raise SystemExit("owned_repository_required")
    revision = api.rest(f"repos/{actor}/.github/commits/main")["sha"]
    # This guard itself runs as an in-progress CI job. It verifies the trusted
    # receipt and current holds; enrollment must still use normal native merge
    # checks. Reading all check runs here would deadlock on the guard's own job.
    pr=api.pull_request(args.repo,args.number)
    live=api.rest(f"repos/{args.repo}/pulls/{args.number}")
    labels={row["name"].casefold() for row in live.get("labels",[])}
    reason=None
    if pr["isDraft"] or pr["state"]!="OPEN" or live["head"]["sha"]!=args.head or (live["head"].get("repo") or {}).get("full_name")!=args.repo:
        reason="draft_closed_or_external_head"
    if labels.intersection({"do-not-merge","hold","manual-merge","ai-delivery-hold"}):
        reason="explicit_hold"
    rules=api.rest(f"repos/{args.repo}/rules/branches/{merge.quote(pr['baseRefName'],safe='')}?per_page=100",paginate=True)
    if merge.required_reviews(pr,rules) and api.native_review_decision(args.repo,args.number)!="APPROVED":
        reason="required_review_missing"
    if pr.get("reviewDecision")=="CHANGES_REQUESTED":
        reason="changes_requested"
    if pr["headRefOid"] != args.head:
        reason = "head_changed"
    if not reason:
        reason = merge.ai_receipt_gate(api,args.repo,args.number,args.head,actor,revision)
    print(json.dumps({"repo":args.repo,"number":args.number,"head":args.head,"verified":reason is None,"reason":reason}))
    raise SystemExit(bool(reason))


if __name__ == "__main__":
    main()
