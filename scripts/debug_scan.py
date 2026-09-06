#!/usr/bin/env python3
"""Local debug scan for dizhaky/.github — writes NDJSON to .cursor/debug-8bef67.log"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / ".cursor" / "debug-8bef67.log"
SESSION = "8bef67"
RUN_ID = "scan-1"


def log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "sessionId": SESSION,
        "runId": RUN_ID,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": __import__("time").time_ns() // 1_000_000,
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    errors: list[str] = []

    # Hypothesis A: TEMPLATE_DIR in rollout-nightly.py must resolve to repo templates
    script = root / "scripts" / "rollout-nightly.py"
    expected = script.parent.parent / ".github" / "repo-templates"
    # Import-time path: parent.parent / .github / repo-templates
    import importlib.util

    spec = importlib.util.spec_from_file_location("rollout_nightly", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    actual = Path(mod.TEMPLATE_DIR)
    log("A", "debug_scan.py:TEMPLATE_DIR", "template path check", {
        "actual": str(actual),
        "actual_exists": actual.exists(),
        "expected": str(expected),
    })
    if not actual.exists() or actual != expected.resolve():
        errors.append(f"rollout-nightly.py: TEMPLATE_DIR invalid ({actual})")

    # Hypothesis B: ruff lint on scripts
    ruff = subprocess.run(
        ["ruff", "check", str(root / "scripts")],
        capture_output=True,
        text=True,
    )
    log("B", "debug_scan.py:ruff", "ruff check scripts/", {
        "returncode": ruff.returncode,
        "stdout_lines": (ruff.stdout or "").strip().split("\n")[:10],
    })
    if ruff.returncode != 0:
        errors.append(f"ruff: {(ruff.stdout or ruff.stderr or '').strip()[:500]}")

    # Hypothesis C: YAML parse all workflow files
    try:
        import yaml
    except ImportError:
        log("C", "debug_scan.py:yaml", "PyYAML missing", {})
        errors.append("PyYAML not installed")
    else:
        yaml_errors = []
        for p in sorted(root.rglob("*.yml")):
            if ".git" in p.parts:
                continue
            try:
                yaml.safe_load(p.read_text())
            except Exception as e:
                yaml_errors.append(f"{p.relative_to(root)}: {e}")
        log("C", "debug_scan.py:yaml", "yaml safe_load", {
            "file_count": len(list(root.rglob("*.yml"))),
            "errors": yaml_errors,
        })
        errors.extend(yaml_errors)

    # Hypothesis D: dependabot-auto-merge overly broad if condition
    auto_merge = root / ".github" / "repo-templates" / "dependabot-auto-merge.yml"
    if auto_merge.exists():
        text = auto_merge.read_text()
        has_production_or = "dependency-type == 'direct:production'" in text
        has_ecosystem_guard = "package-ecosystem == 'github_actions'" in text
        log("D", "debug_scan.py:auto-merge", "dependabot auto-merge if", {
            "has_direct_production_in_if": has_production_or,
            "has_ecosystem_guard": has_ecosystem_guard,
        })
        if has_production_or and not has_ecosystem_guard:
            errors.append(
                "dependabot-auto-merge.yml: if includes direct:production without github-actions guard"
            )

    # Hypothesis E: nightly-health-check compares secret in bash (always empty)
    nightly = root / ".github" / "workflows" / "nightly-health-check.yml"
    if nightly.exists():
        text = nightly.read_text()
        bad_secret_compare = 'secrets.GH_PAT }}" = ""' in text
        uses_env_check = "GH_PAT: ${{ secrets.GH_PAT }}" in text and '[ -z "${GH_PAT:-}" ]' in text
        log("E", "debug_scan.py:nightly", "GH_PAT bash compare", {
            "bad_secret_compare_in_run": bad_secret_compare,
            "uses_env_check": uses_env_check,
        })
        if bad_secret_compare or not uses_env_check:
            errors.append(
                "nightly-health-check.yml: GH_PAT must be checked via env var, not secrets.* in bash"
            )

    # Hypothesis F: rollout-docs.py template paths and compile
    rollout_docs = root / "scripts" / "rollout-docs.py"
    if rollout_docs.exists():
        compile_ok = True
        compile_err = ""
        try:
            subprocess.run(
                [sys.executable, "-m", "py_compile", str(rollout_docs)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            compile_ok = False
            compile_err = (e.stderr or e.stdout or str(e))[:300]
        import importlib.util

        spec = importlib.util.spec_from_file_location("rollout_docs", rollout_docs)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        docs_template = Path(mod.TEMPLATE_DIR)
        has_dry_run = "--dry-run" in rollout_docs.read_text()
        log("F", "debug_scan.py:rollout-docs", "rollout-docs paths", {
            "compile_ok": compile_ok,
            "compile_err": compile_err,
            "template_dir": str(docs_template),
            "template_exists": docs_template.exists(),
            "has_dry_run_flag": has_dry_run,
        })
        if not compile_ok:
            errors.append(f"rollout-docs.py: py_compile failed: {compile_err}")
        if not docs_template.exists():
            errors.append(f"rollout-docs.py: TEMPLATE_DIR missing ({docs_template})")
        if not has_dry_run:
            errors.append("rollout-docs.py: missing --dry-run safety flag")

    rollout_nightly = root / "scripts" / "rollout-nightly.py"
    if rollout_nightly.exists() and "--dry-run" not in rollout_nightly.read_text():
        errors.append("rollout-nightly.py: missing --dry-run safety flag")

    # Hypothesis G: reusable-ci Build step must skip before node package.json probe on pip
    reusable_ci = root / ".github" / "workflows" / "reusable-ci.yml"
    if reusable_ci.exists():
        text = reusable_ci.read_text()
        build_block = text.split("- name: Build")[1].split("- name:")[0] if "- name: Build" in text else ""
        invoke_idx = build_block.find("if ! has_script")
        pip_exit_idx = build_block.find('manager }}" = "pip"')
        pip_before_invoke = (
            pip_exit_idx != -1
            and invoke_idx != -1
            and pip_exit_idx < invoke_idx
            and "exit 0" in build_block[pip_exit_idx:invoke_idx]
        )
        log("G", "debug_scan.py:reusable-ci", "pip build guard", {
            "pip_exits_before_has_script_invoke": pip_before_invoke,
        })
        if build_block and not pip_before_invoke:
            errors.append("reusable-ci.yml: Build step may invoke has_script before pip exit")

    log("SUMMARY", "debug_scan.py:main", "scan complete", {
        "error_count": len(errors),
        "errors": errors,
    })
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        print(f"\n{len(errors)} issue(s) found. See {LOG_PATH}")
        return 1
    print("Scan PASS — no issues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
