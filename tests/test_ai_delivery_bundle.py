"""Disposable bundles/HOME and mocked gates/service manager; never live activation."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import sys
import subprocess
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ai_delivery_bundle as bundle
import bootstrap_ai_delivery as bootstrap


def service_text(plist):
    arguments = plistlib.loads(plist.read_bytes())["ProgramArguments"]
    return "path = " + str(plist) + "\nprogram = " + arguments[0] + "\narguments = {\n" + "\n".join(arguments) + "\n}\n"


@pytest.fixture
def built(tmp_path, monkeypatch):
    source = tmp_path / "source"; (source / "scripts").mkdir(parents=True)
    contents = {}
    for name in bootstrap.FILES:
        raw = (name + "\n").encode(); contents[name] = raw; (source / "scripts" / name).write_bytes(raw)
    def git(_, *args):
        if args == ("rev-parse", "HEAD"): return "a" * 40
        if args == ("status", "--porcelain"): return ""
        raw = contents[args[-1].split("/")[-1]]
        oid = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        return "100644 " + oid + " 0\t" + args[-1]
    monkeypatch.setattr(bundle, "git", git)
    output = tmp_path / "bundle"
    digest = bundle.prepare(source, output, sys.executable, sys.executable)
    return source, output, digest


def test_prepare_is_deterministic_and_never_installs(built, tmp_path):
    source, output, digest = built
    other = tmp_path / "second"
    assert bundle.prepare(source, other, sys.executable, sys.executable) == digest
    assert (output / "manifest.json").read_bytes() == (other / "manifest.json").read_bytes()
    assert not (Path.home() / "Library/LaunchAgents" / (bundle.LABEL + ".plist")).exists()


@pytest.mark.parametrize("drift", ["manifest", "file", "symlink", "extra"])
def test_bundle_tampering_fails_before_install(built, drift, tmp_path):
    _, output, digest = built
    p = output / "ai_delivery.py"
    if drift == "manifest": (output / "manifest.json").write_text("{}")
    if drift == "file": p.write_text("changed")
    if drift == "symlink": p.unlink(); p.symlink_to(tmp_path / "outside")
    if drift == "extra": (output / "unexpected").write_text("extra")
    with pytest.raises(ValueError): bundle.install(output, digest, tmp_path / "home", gate=lambda: ("", "", "a" * 40))
    assert not (tmp_path / "home/.local").exists()


def test_install_creates_only_fixed_disabled_service_and_private_state(built, tmp_path):
    _, output, digest = built; home = tmp_path / "home"; home.mkdir()
    receipt = bundle.install(output, digest, home, gate=lambda: ("dizhaky/.github", "main", "a" * 40))
    root, plist = bundle.paths(home); doc = plistlib.loads(plist.read_bytes())
    assert doc["Label"] == bundle.LABEL and doc["RunAtLoad"] is False and doc["StartInterval"] == 900
    assert "--budget" in doc["ProgramArguments"] and doc["ProgramArguments"][-1] == "1"
    assert receipt["manifestSha256"] == digest
    assert root.stat().st_mode & 0o777 == 0o700 and plist.stat().st_mode & 0o777 == 0o600
    assert set(doc["EnvironmentVariables"]) == {"HOME", "PATH", "PYTHONDONTWRITEBYTECODE", "PYTHONNOUSERSITE"}
    with pytest.raises(ValueError, match="existing_install_preserved"):
        bundle.install(output, digest, home, gate=lambda: ("", "", "a" * 40))


@pytest.mark.parametrize("problem", ["source", "symlink"])
def test_source_or_home_boundary_blocks_install(built, tmp_path, problem):
    _, output, digest = built; home = tmp_path / "home"; home.mkdir()
    if problem == "symlink": (home / ".local").symlink_to(tmp_path / "outside", target_is_directory=True)
    with pytest.raises(ValueError):
        bundle.install(output, digest, home, gate=lambda: ("", "", "b" * 40 if problem == "source" else "a" * 40))
    assert not (home / "Library").exists()


def test_uninstall_targets_only_owned_service_and_retains_data(built, tmp_path):
    _, output, digest = built; home = tmp_path / "home"; home.mkdir()
    bundle.install(output, digest, home, gate=lambda: ("", "", "a" * 40))
    root, plist = bundle.paths(home); (root / "state/keep").write_text("receipt")
    calls = []
    def runner(command, **kw):
        calls.append(command)
        if command[1] == "print" and len(calls) == 1:
            return SimpleNamespace(returncode=0, stdout=service_text(plist), stderr="")
        if command[1] == "print":
            return SimpleNamespace(returncode=113, stdout="", stderr='Could not find service "' + bundle.LABEL + '"')
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    result = bundle.service(home, runner=runner)
    assert calls[1] == ["launchctl", "bootout", "gui/" + str(os.getuid()) + "/" + bundle.LABEL]
    assert not plist.exists() and (root / "state/keep").read_text() == "receipt" and not result["activated"]


def test_changed_installed_service_is_never_unloaded(built, tmp_path):
    _, output, digest = built; home = tmp_path / "home"; home.mkdir()
    bundle.install(output, digest, home, gate=lambda: ("", "", "a" * 40))
    _, plist = bundle.paths(home); plist.write_bytes(b"unrelated")
    with pytest.raises(ValueError, match="installed_service_changed"):
        bundle.service(home, runner=lambda *a, **k: pytest.fail("must not unload"))
    assert plist.read_bytes() == b"unrelated"


def test_uninstall_unloaded_service_removes_only_plist(built, tmp_path):
    _, output, digest = built; home = tmp_path / "home"; home.mkdir()
    bundle.install(output, digest, home, gate=lambda: ("", "", "a" * 40))
    root, plist = bundle.paths(home)
    def runner(command, **kwargs):
        assert command[1] == "print"
        return SimpleNamespace(returncode=113, stdout="", stderr='Could not find service "' + bundle.LABEL + '"')
    bundle.service(home, runner=runner)
    assert not plist.exists() and (root / "install-receipt.json").exists()


def test_uninstall_refuses_other_loaded_program(built, tmp_path):
    _, output, digest = built; home = tmp_path / "home"; home.mkdir()
    bundle.install(output, digest, home, gate=lambda: ("", "", "a" * 40))
    _, plist = bundle.paths(home)
    def runner(command, **kwargs):
        assert command[1] == "print"
        return SimpleNamespace(returncode=0, stdout="unrelated", stderr="")
    with pytest.raises(ValueError, match="loaded_service_identity_changed"):
        bundle.service(home, runner=runner)
    assert plist.exists()


def test_activation_rechecks_source_and_verifies_exact_loaded_service(built, tmp_path, monkeypatch):
    import launch_ai_delivery
    _, output, digest = built; home = tmp_path / "home"; home.mkdir()
    bundle.install(output, digest, home, gate=lambda: ("", "", "a" * 40))
    root, plist = bundle.paths(home)
    monkeypatch.setattr(launch_ai_delivery, "source_revision", lambda api: ("dizhaky/.github", "main", "a" * 40))
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=service_text(plist), stderr="")
    assert bundle.service(home, activate=True, runner=runner)["activated"]
    assert [x[1] for x in calls] == ["bootstrap", "print"]
    monkeypatch.setattr(launch_ai_delivery, "source_revision", lambda api: ("", "", "b" * 40))
    with pytest.raises(ValueError, match="activation_source_changed"):
        bundle.service(home, activate=True, runner=lambda *a, **k: pytest.fail("must not activate"))


def test_uninstall_rejects_expected_paths_in_unrelated_fields(built, tmp_path):
    _, output, digest = built; home = tmp_path / "home"; home.mkdir()
    bundle.install(output, digest, home, gate=lambda: ("", "", "a" * 40))
    _, plist = bundle.paths(home)
    args = plistlib.loads(plist.read_bytes())["ProgramArguments"]
    text = "path = " + str(plist) + "\nprogram = /usr/bin/unrelated\nnotes = " + " ".join(args)
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=text, stderr="")
    with pytest.raises(ValueError, match="loaded_service_identity_changed"):
        bundle.service(home, runner=runner)
    assert len(calls) == 1 and plist.exists()


def test_isolated_bootstrap_never_imports_added_stdlib_shadow(built, tmp_path):
    _, output, digest = built
    # Use real bootstrap with correct pinned manifest and inert payloads.
    (output / "bootstrap_ai_delivery.py").write_bytes(Path(bootstrap.__file__).read_bytes())
    data = json.loads((output / "manifest.json").read_text())
    data["files"]["bootstrap_ai_delivery.py"] = hashlib.sha256((output / "bootstrap_ai_delivery.py").read_bytes()).hexdigest()
    raw = json.dumps(data).encode(); (output / "manifest.json").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    marker = tmp_path / "shadow-imported"
    (output / "hashlib.py").write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n")
    result = subprocess.run([sys.executable, "-I", "-B", str(output / "bootstrap_ai_delivery.py"), "--manifest-sha256", digest], capture_output=True, text=True)
    assert result.returncode != 0 and "unexpected_bundle_file" in result.stderr
    assert not marker.exists()
