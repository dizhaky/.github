#!/usr/bin/env python3
"""Roll out nightly-maintenance.yml and dependabot-auto-merge.yml to dizhaky repos."""
import base64
import json
import subprocess
import sys
from pathlib import Path

SKIP = {".github", "agent-starter-pack", "openclaw-private-hank", "medifacture-capital",
        "cloud-admin-toolkit", "openclaw-observability", "brainsystem", "claude-lazy-loading", "openclaw"}
TEMPLATE_DIR = Path(__file__).resolve().parent / ".github" / "repo-templates"
WORKFLOWS = ["nightly-maintenance.yml", "dependabot-auto-merge.yml"]


def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout)
    return r.stdout.strip()


def repos():
    out = gh("api", "user/repos", "--paginate", "-q", ".[].name")
    return [n for n in out.splitlines() if n and n not in SKIP]


def put_file(repo: str, dest: str, content: str, msg: str):
    path = f".github/workflows/{dest}"
    sha = None
    try:
        existing = json.loads(gh("api", f"repos/dizhaky/{repo}/contents/{path}"))
        sha = existing.get("sha")
    except RuntimeError:
        pass
    args = [
        "api", "-X", "PUT", f"repos/dizhaky/{repo}/contents/{path}",
        "-f", f"message={msg}",
        "-f", f"content={base64.b64encode(content.encode()).decode()}",
    ]
    if sha:
        args.extend(["-f", f"sha={sha}"])
    subprocess.run(["gh", *args], check=True, capture_output=True)


def main():
    template_dir = TEMPLATE_DIR
    if not template_dir.exists():
        template_dir = Path(__file__).resolve().parent.parent / ".github" / "repo-templates"
    updated = []
    for repo in repos():
        try:
            for wf in WORKFLOWS:
                src = template_dir / wf
                if not src.exists():
                    continue
                put_file(repo, wf, src.read_text(), f"chore: add {wf} from dizhaky/.github templates")
            updated.append(repo)
            print(f"OK {repo}")
        except subprocess.CalledProcessError as e:
            print(f"SKIP {repo}: {e.stderr.decode() if e.stderr else e}", file=sys.stderr)
    print(f"\nRolled out to {len(updated)} repos")


if __name__ == "__main__":
    main()
