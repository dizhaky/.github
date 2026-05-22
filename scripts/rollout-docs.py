#!/usr/bin/env python3
"""Roll out docs/system-log and agent file templates to dizhaky repos.

Seeds CLAUDE.md, AGENTS.md, and docs/system-log/ only when missing or minimal.
Never overwrites substantial existing agent files.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

SKIP = {
    ".github",
    "agent-starter-pack",
    "openclaw-private-hank",
    "medifacture-capital",
    "cloud-admin-toolkit",
    "openclaw-observability",
    "brainsystem",
    "claude-lazy-loading",
    "openclaw",
    "openclaw-infra",
}

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / ".github" / "repo-templates"
MANIFEST = Path(__file__).resolve().parent / "repo-manifest.txt"

MIN_SUBSTANTIAL_LINES = 12  # skip seed if existing file has more lines

REPO_META: dict[str, dict[str, str]] = {
    ".github": {
        "purpose": "Central GitHub templates, reusable workflows, and account hygiene",
        "stack": "GitHub Actions, Python rollout scripts",
        "install": "n/a",
        "run": "gh workflow run nightly-health-check.yml -R dizhaky/.github",
        "test": "python3 scripts/verify-no-pr-reviews.py",
        "lint": "n/a",
    },
    "Organize-the-UST-onedrive-and-sharepoint": {
        "purpose": "UST OneDrive/SharePoint file reorganization automation",
        "stack": "Python, Microsoft Graph API",
        "install": "pip install -r requirements.txt",
        "run": "python3 -m src.main --help",
        "test": "pytest",
        "lint": "ruff check .",
    },
    "cloud-automation-hub": {
        "purpose": "Cloud automation scripts and CI templates",
        "stack": "Python, GitHub Actions",
        "install": "pip install -r requirements.txt",
        "run": "see README.md",
        "test": "pytest",
        "lint": "ruff check .",
    },
    "codex-config": {
        "purpose": "Codex CLI configuration and skills",
        "stack": "Markdown, shell",
        "install": "see README.md",
        "run": "codex",
        "test": "n/a",
        "lint": "n/a",
    },
    "crm-pipeline": {
        "purpose": "CRM data pipeline",
        "stack": "Python",
        "install": "pip install -r requirements.txt",
        "run": "see README.md",
        "test": "pytest",
        "lint": "ruff check .",
    },
    "crm-vault": {
        "purpose": "CRM vault integration",
        "stack": "Python",
        "install": "pip install -r requirements.txt",
        "run": "see README.md",
        "test": "pytest",
        "lint": "ruff check .",
    },
    "danizhaky.com": {
        "purpose": "Personal site",
        "stack": "see README.md",
        "install": "npm install",
        "run": "npm run dev",
        "test": "npm test",
        "lint": "npm run lint",
    },
    "dotfiles": {
        "purpose": "Shell, Cursor, Claude, and machine bootstrap",
        "stack": "zsh, Cursor hooks/rules, install.sh",
        "install": "./install.sh",
        "run": "n/a",
        "test": "n/a",
        "lint": "shellcheck scripts/*.sh 2>/dev/null || true",
    },
    "everything-claude-code": {
        "purpose": "ECC plugin — hooks, skills, agents reference",
        "stack": "Node.js, Cursor/Claude Code",
        "install": "npm install",
        "run": "see README.md",
        "test": "npm test",
        "lint": "npm run lint",
    },
    "falcon-ops": {
        "purpose": "Falcon operations tooling",
        "stack": "see README.md",
        "install": "see README.md",
        "run": "see README.md",
        "test": "see README.md",
        "lint": "see README.md",
    },
    "kb-daemon": {
        "purpose": "Knowledge base ingestion daemon",
        "stack": "Python",
        "install": "pip install -r requirements.txt",
        "run": "python3 -m kb_daemon",
        "test": "pytest",
        "lint": "ruff check .",
    },
    "kb-watcher": {
        "purpose": "Knowledge base file watcher",
        "stack": "Python",
        "install": "pip install -r requirements.txt",
        "run": "python3 -m kb_watcher",
        "test": "pytest",
        "lint": "ruff check .",
    },
    "litellm": {
        "purpose": "LiteLLM proxy fork/config",
        "stack": "Python, LiteLLM",
        "install": "pip install -r requirements.txt",
        "run": "litellm --help",
        "test": "pytest",
        "lint": "ruff check .",
    },
    "litellm-hetzner-config": {
        "purpose": "LiteLLM deployment config for Hetzner",
        "stack": "YAML, Docker",
        "install": "see README.md",
        "run": "docker compose up",
        "test": "n/a",
        "lint": "n/a",
    },
    "mcp-servers": {
        "purpose": "Custom MCP server implementations",
        "stack": "TypeScript/Python",
        "install": "npm install",
        "run": "see README.md",
        "test": "npm test",
        "lint": "npm run lint",
    },
    "mission-control": {
        "purpose": "Agent mission control dashboard",
        "stack": "Next.js, pnpm, SQLite",
        "install": "pnpm install",
        "run": "pnpm dev",
        "test": "pnpm test",
        "lint": "pnpm lint",
    },
    "obsidian-vault": {
        "purpose": "Obsidian vault git mirror",
        "stack": "Markdown, Obsidian",
        "install": "n/a",
        "run": "open in Obsidian",
        "test": "n/a",
        "lint": "n/a",
    },
    "openclaw-monorepo": {
        "purpose": "OpenClaw platform monorepo",
        "stack": "TypeScript, pnpm",
        "install": "pnpm install",
        "run": "pnpm dev",
        "test": "pnpm test",
        "lint": "pnpm lint",
    },
    "paperclip": {
        "purpose": "Paperclip application",
        "stack": "see README.md",
        "install": "see README.md",
        "run": "see README.md",
        "test": "see README.md",
        "lint": "see README.md",
    },
    "persistent-memory": {
        "purpose": "Persistent agent memory service",
        "stack": "see README.md",
        "install": "see README.md",
        "run": "see README.md",
        "test": "see README.md",
        "lint": "see README.md",
    },
    "return-runner": {
        "purpose": "Return processing automation",
        "stack": "see README.md",
        "install": "see README.md",
        "run": "see README.md",
        "test": "see README.md",
        "lint": "see README.md",
    },
    "united-safety-technology": {
        "purpose": "UST corporate site/content",
        "stack": "see README.md",
        "install": "see README.md",
        "run": "see README.md",
        "test": "see README.md",
        "lint": "see README.md",
    },
    "ust-automation-scripts": {
        "purpose": "UST automation and CI scripts",
        "stack": "Python, GitHub Actions",
        "install": "pip install -r requirements.txt",
        "run": "see README.md",
        "test": "pytest",
        "lint": "ruff check .",
    },
}


def gh(*args: str) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout)
    return r.stdout.strip()


def repos_from_manifest() -> list[str]:
    if MANIFEST.exists():
        names = []
        for line in MANIFEST.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            names.append(line)
        return [n for n in names if n not in SKIP]
    out = gh("api", "user/repos", "--paginate", "-q", ".[].name")
    return [n for n in out.splitlines() if n and n not in SKIP]


def get_file(repo: str, path: str) -> tuple[str | None, str | None]:
    try:
        data = json.loads(gh("api", f"repos/dizhaky/{repo}/contents/{path}"))
        if isinstance(data, list):
            return None, None
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data.get("sha")
    except RuntimeError:
        return None, None


def put_file(repo: str, path: str, content: str, msg: str, sha: str | None = None) -> None:
    args = [
        "api",
        "-X",
        "PUT",
        f"repos/dizhaky/{repo}/contents/{path}",
        "-f",
        f"message={msg}",
        "-f",
        f"content={base64.b64encode(content.encode()).decode()}",
    ]
    if sha:
        args.extend(["-f", f"sha={sha}"])
    subprocess.run(["gh", *args], check=True, capture_output=True)


def render_template(template_name: str, repo: str) -> str:
    meta = REPO_META.get(
        repo,
        {
            "purpose": "See README.md",
            "stack": "See README.md",
            "install": "see README.md",
            "run": "see README.md",
            "test": "see README.md",
            "lint": "see README.md",
        },
    )
    text = (TEMPLATE_DIR / template_name).read_text()
    return (
        text.replace("{{REPO_NAME}}", repo)
        .replace("{{REPO_PURPOSE}}", meta["purpose"])
        .replace("{{STACK}}", meta["stack"])
        .replace("{{INSTALL_CMD}}", meta["install"])
        .replace("{{RUN_CMD}}", meta["run"])
        .replace("{{TEST_CMD}}", meta["test"])
        .replace("{{LINT_CMD}}", meta["lint"])
    )


def is_substantial(content: str | None) -> bool:
    if not content:
        return False
    lines = [ln for ln in content.splitlines() if ln.strip()]
    return len(lines) >= MIN_SUBSTANTIAL_LINES


def rollout_repo(repo: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {"added": [], "skipped": [], "errors": []}
    sys_log_readme = (TEMPLATE_DIR / "docs-system-log-README.md").read_text()

    targets = [
        ("docs/system-log/.gitkeep", "", "chore: add docs/system-log directory"),
        ("docs/system-log/README.md", sys_log_readme, "chore: add system log format spec"),
    ]

    for path, content, msg in targets:
        existing, sha = get_file(repo, path)
        if existing is not None:
            result["skipped"].append(f"{path} (exists)")
            continue
        try:
            put_file(repo, path, content, msg)
            result["added"].append(path)
        except subprocess.CalledProcessError as e:
            result["errors"].append(f"{path}: {e.stderr.decode() if e.stderr else e}")

    for dest, template in [("CLAUDE.md", "CLAUDE.md.template"), ("AGENTS.md", "AGENTS.md.template")]:
        existing, sha = get_file(repo, dest)
        if is_substantial(existing):
            result["skipped"].append(f"{dest} (substantial, {len(existing.splitlines())} lines)")
            continue
        if existing and existing.strip():
            result["skipped"].append(f"{dest} (exists, {len(existing.splitlines())} lines)")
            continue
        try:
            body = render_template(template, repo)
            put_file(repo, dest, body, f"chore: seed {dest} from dizhaky/.github template")
            result["added"].append(dest)
        except subprocess.CalledProcessError as e:
            result["errors"].append(f"{dest}: {e.stderr.decode() if e.stderr else e}")

    return result


def main() -> None:
    if not TEMPLATE_DIR.exists():
        print(f"Missing template dir: {TEMPLATE_DIR}", file=sys.stderr)
        sys.exit(1)

    all_repos = repos_from_manifest()
    summary: dict[str, dict] = {}

    for repo in all_repos:
        try:
            result = rollout_repo(repo)
            summary[repo] = result
            status = "OK" if not result["errors"] else "PARTIAL"
            print(f"{status} {repo}: +{len(result['added'])} skip={len(result['skipped'])}")
            for item in result["skipped"]:
                print(f"  skip {item}")
            for err in result["errors"]:
                print(f"  ERR {err}", file=sys.stderr)
        except Exception as e:
            summary[repo] = {"added": [], "skipped": [], "errors": [str(e)]}
            print(f"FAIL {repo}: {e}", file=sys.stderr)

    added_repos = [r for r, s in summary.items() if s.get("added")]
    print(f"\nRolled out doc files to {len(added_repos)} repos with changes")


if __name__ == "__main__":
    main()
