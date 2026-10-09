"""Prepare a deterministic bundle by default; explicit install never starts it.

Activation and service-only uninstall are separate exact-target operations.
No credentials, repository settings or branch protections are configured here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys

from bootstrap_ai_delivery import FILES, verify

LABEL = "com.dizhaky.ai-delivery"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(source, *args):
    return subprocess.check_output(["git", "-c", "core.fsmonitor=false",
                                    "-C", str(source), *args], text=True).strip()


def safe_path(path, anchor):
    path, anchor = Path(path), Path(anchor)
    if not path.is_absolute() or not path.is_relative_to(anchor) or path == anchor:
        raise ValueError("invalid_install_path")
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError("symlink_install_path")
        if parent == anchor:
            break
    return path


def executable(value):
    path = Path(value)
    if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError("absolute_existing_executable_required")
    return str(path.resolve())


def prepare(source, output, python, gh):
    source, output = Path(source), Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("bundle_output_exists")
    revision = git(source, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or git(source, "status", "--porcelain"):
        raise ValueError("clean_committed_source_required")
    if (source / "scripts").is_symlink():
        raise ValueError("symlink_source_directory")
    data = {"schema": 1, "sourceRepo": "dizhaky/.github", "sourceRevision": revision,
            "service": LABEL, "python": executable(python), "gh": executable(gh), "files": {}}
    contents = {}
    for name in sorted(FILES):
        path = source / "scripts" / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("regular_source_file_required")
        mode = git(source, "ls-files", "--stage", "--", "scripts/" + name).split()
        if not mode or mode[0] != "100644":
            raise ValueError("tracked_regular_source_required")
        contents[name] = path.read_bytes()
        actual_blob = hashlib.sha1(b"blob " + str(len(contents[name])).encode() + b"\0" + contents[name]).hexdigest()
        if actual_blob != mode[1]:
            raise ValueError("source_blob_changed")
        data["files"][name] = sha(contents[name])
    output.mkdir(parents=True, mode=0o700)
    for name, raw in contents.items():
        (output / name).write_bytes(raw)
        (output / name).chmod(0o600)
    raw = (json.dumps(data, sort_keys=True, indent=2) + "\n").encode()
    (output / "manifest.json").write_bytes(raw)
    (output / "manifest.json").chmod(0o600)
    return sha(raw)


def paths(home):
    home = Path(home)
    if not home.is_absolute() or home.is_symlink():
        raise ValueError("invalid_home")
    return (safe_path(home / ".local/share/codex-ai-delivery", home),
            safe_path(home / "Library/LaunchAgents" / (LABEL + ".plist"), home))


def install(bundle, manifest_hash, home, *, gate=None):
    bundle, home = Path(bundle), Path(home)
    data = verify(bundle, manifest_hash)
    if data.get("sourceRepo") != "dizhaky/.github" or data.get("service") != LABEL:
        raise ValueError("wrong_bundle_authority")
    if gate is None:
        from ai_delivery import GitHub
        from launch_ai_delivery import source_revision
        gate = lambda: source_revision(GitHub())
    # Native protected source/CI/required-signature gate must match the reviewed bundle.
    if gate()[2] != data["sourceRevision"]:
        raise ValueError("bundle_not_current_trusted_source")
    for key in ("python", "gh"):
        executable(data[key])
    root, plist = paths(home)
    if root.exists() or plist.exists():
        raise ValueError("existing_install_preserved")
    root.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir(mode=0o700)
    version = root / "versions" / data["sourceRevision"]
    version.parent.mkdir(mode=0o700)
    shutil.copytree(bundle, version)
    for path in version.iterdir():
        path.chmod(0o600)
    for name in ("state", "checkouts", "logs"):
        (root / name).mkdir(mode=0o700)
    # Recheck after materialization and before creating a scheduled-service definition.
    if gate()[2] != data["sourceRevision"]:
        raise ValueError("source_changed_during_install")
    doc = {"Label": LABEL, "ProgramArguments": [data["python"], "-I", "-B", str(version / "bootstrap_ai_delivery.py"),
           "--manifest-sha256", manifest_hash, "--state-dir", str(root / "state"),
           "--checkout-root", str(root / "checkouts"), "--log-dir", str(root / "logs"),
           "--report", str(root / "state/report.json"), "--budget", "1"],
           "RunAtLoad": False, "StartInterval": 900, "WorkingDirectory": str(version),
           "EnvironmentVariables": {"HOME": str(home), "PATH": str(Path(data["gh"]).parent) + ":/opt/homebrew/bin:/usr/bin:/bin",
                                    "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"},
           "StandardOutPath": str(root / "logs/launcher.stdout.log"),
           "StandardErrorPath": str(root / "logs/launcher.stderr.log")}
    raw = plistlib.dumps(doc, sort_keys=True)
    receipt = {"schema": 1, "service": LABEL, "manifestSha256": manifest_hash,
               "sourceRevision": data["sourceRevision"], "plistSha256": sha(raw)}
    (root / "install-receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    (root / "install-receipt.json").chmod(0o600)
    plist.parent.mkdir(parents=True, exist_ok=True)
    with plist.open("xb") as stream:
        stream.write(raw)
    plist.chmod(0o600)
    return receipt  # No launchctl call, inference or delivery.


def installed(home):
    root, plist = paths(home)
    receipt_path = safe_path(root / "install-receipt.json", Path(home))
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("schema") != 1 or receipt.get("service") != LABEL or sha(plist.read_bytes()) != receipt["plistSha256"]:
        raise ValueError("installed_service_changed")
    if plistlib.loads(plist.read_bytes()).get("Label") != LABEL:
        raise ValueError("wrong_service")
    version = safe_path(root / "versions" / receipt["sourceRevision"], Path(home))
    data = verify(version, receipt["manifestSha256"])
    if data.get("sourceRevision") != receipt["sourceRevision"]:
        raise ValueError("installed_revision_changed")
    return root, plist, receipt


def service(home, *, activate=False, runner=subprocess.run):
    root, plist, receipt = installed(home)
    domain = "gui/" + str(os.getuid())
    target = domain + "/" + LABEL
    def probe():
        result = runner(["launchctl", "print", target], capture_output=True, text=True, check=False)
        missing = result.returncode == 113 and ('Could not find service "' + LABEL + '"') in result.stderr
        if result.returncode and not missing:
            raise ValueError("service_identity_unreadable")
        if not missing:
            doc = plistlib.loads(plist.read_bytes())
            fields = {}; arguments = []; in_arguments = False
            for line in result.stdout.splitlines():
                value = line.strip()
                if in_arguments:
                    if value == "}": in_arguments = False
                    else: arguments.append(value)
                elif value == "arguments = {": in_arguments = True
                elif " = " in value:
                    key, item = value.split(" = ", 1)
                    if key in {"path", "program"}:
                        if key in fields: raise ValueError("loaded_service_identity_changed")
                        fields[key] = item
            if in_arguments or fields != {"path": str(plist), "program": doc["ProgramArguments"][0]} or arguments != doc["ProgramArguments"]:
                raise ValueError("loaded_service_identity_changed")
        return not missing
    if activate:
        from ai_delivery import GitHub
        from launch_ai_delivery import source_revision
        if source_revision(GitHub())[2] != receipt["sourceRevision"]:
            raise ValueError("activation_source_changed")
        command = ["launchctl", "bootstrap", domain, str(plist)]
        result = runner(command, capture_output=True, text=True, check=False)
        if result.returncode or not probe():
            raise ValueError("service_activation_not_verified")
    else:
        if probe():
            result = runner(["launchctl", "bootout", target], capture_output=True, text=True, check=False)
            if result.returncode or probe():
                raise ValueError("service_unload_not_verified")
        # Only the verified exact plist is removed; state, receipts and code are retained.
        installed(home)
        plist.unlink()
    return {"service": LABEL, "activated": activate, "stateRetained": str(root)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--install", action="store_true")
    mode.add_argument("--activate", action="store_true")
    mode.add_argument("--uninstall", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--gh", default=shutil.which("gh"))
    args = parser.parse_args()
    home = Path.home()
    if args.install:
        if not args.bundle or not args.manifest_sha256:
            parser.error("install requires reviewed --bundle and --manifest-sha256")
        result = install(args.bundle, args.manifest_sha256, home)
    elif args.activate or args.uninstall:
        result = service(home, activate=args.activate)
    else:
        if not args.output or not args.gh:
            parser.error("prepare requires --output and an existing gh executable")
        digest = prepare(Path(__file__).resolve().parents[1], args.output, args.python, args.gh)
        result = {"prepared": str(args.output), "manifestSha256": digest, "installed": False, "activated": False}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
