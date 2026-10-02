"""Read an owner-authored bounded lease snapshot from an existing private issue.

The scheduler that publishes this feed must actually query the native task
system; this reader never stamps old claims with a new time itself.
"""
import argparse
from datetime import datetime, timezone
import json
import global_auto_merge as merge
from ai_proposal import BoundaryError, SECRET_PATTERN
from ai_delivery import active_authority

MARKER = "<!-- ai-delivery-ownership-v1 -->\n"


def read_feed(api,repo,number,author,max_age=4500,comment_id=None):
    identity,metadata=active_authority(api,repo)
    if metadata.get("private") is not True or author!=identity:
        raise BoundaryError("private_owned_feed_required")
    rows=[api.rest(f"repos/{repo}/issues/comments/{comment_id}")] if comment_id else api.rest(f"repos/{repo}/issues/{number}/comments?per_page=100",paginate=True)
    candidates=[row for row in rows if row.get("user",{}).get("login")==author and row.get("user",{}).get("id")==213320850 and (row.get("body") or "").startswith(MARKER)]
    if not candidates:
        raise BoundaryError("ownership_feed_missing")
    row=max(candidates,key=lambda value:value["id"])
    if not row.get("issue_url","").endswith(f"/repos/{repo}/issues/{number}") or comment_id and row["id"]!=comment_id:
        raise BoundaryError("ownership_feed_issue_binding_invalid")
    body=row["body"][len(MARKER):]
    if len(body.encode())>100_000 or SECRET_PATTERN.search(body):
        raise BoundaryError("ownership_feed_invalid")
    snapshot=json.loads(body)
    if set(snapshot)!={"leasesVerifiedAt","leases"} or not isinstance(snapshot["leases"],list):
        raise BoundaryError("ownership_feed_invalid")
    stamp=datetime.fromisoformat(snapshot["leasesVerifiedAt"].replace("Z","+00:00"))
    published=datetime.fromisoformat(row["updated_at"].replace("Z","+00:00"))
    age=(datetime.now(timezone.utc)-stamp).total_seconds()
    publication_age=(datetime.now(timezone.utc)-published).total_seconds()
    if not 300<=max_age<=5400 or age>max_age or age< -60 or publication_age>max_age or publication_age< -60 or (stamp-published).total_seconds()>60:
        raise BoundaryError("ownership_feed_stale")
    for lease in snapshot["leases"]:
        if not isinstance(lease,dict) or not {"repo","expiresAt"}.issubset(lease) or not (lease.get("number") or lease.get("branch")) or lease["repo"].split("/")[0].casefold()!=identity.casefold():
            raise BoundaryError("ownership_feed_invalid_lease")
        datetime.fromisoformat(lease["expiresAt"].replace("Z","+00:00"))
    return snapshot


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo",required=True)
    parser.add_argument("--issue",type=int,required=True)
    parser.add_argument("--author",required=True)
    parser.add_argument("--max-age",type=int,default=4500)
    parser.add_argument("--comment-id",type=int)
    args=parser.parse_args()
    try:
        print(json.dumps(read_feed(merge.GitHub(),args.repo,args.issue,args.author,args.max_age,args.comment_id)))
    except (BoundaryError,merge.APIError,KeyError,ValueError,TypeError):
        raise SystemExit("ownership_feed_read_failed") from None


if __name__=="__main__":
    main()
