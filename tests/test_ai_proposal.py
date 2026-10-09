"""Secret-shape, package test-control, and patch-target boundary tests."""
import hashlib
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ai_proposal as proposal


@pytest.mark.parametrize("secret", [
    "AKIAIOSFODNN7EXAMPLE",
    "ASIAIOSFODNN7EXAMPLE",
    "AIza" + "a" * 35,
    "glpat-" + "a" * 20,
    "xoxb-" + "1" * 20,
    "npm_" + "a" * 36,
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "-----BEGIN PRIVATE KEY-----",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.eyJzaWduIn0xMjM0NTY3ODkw",
])
def test_extended_secret_shapes_are_detected(secret):
    assert proposal.SECRET_PATTERN.search("token=" + secret)


def test_benign_source_is_not_secret_shaped():
    source = "checksum = hashlib.sha256(payload).hexdigest()  # not a credential"
    assert not proposal.SECRET_PATTERN.search(source)


@pytest.mark.parametrize("section", [
    "[tool.pdm.scripts]", "[tool.tox.envlist]", "[tool.tox4.legacy_tox_ini]",
    "[tool.taskipy.tasks]", "[tool.invoke]", "[tool.nox]", "[tool.doit]",
])
def test_package_script_runner_sections_cannot_be_rewritten(tmp_path, section):
    original = section + '\nsetting="real"\n[project]\ndependencies=["lib==1"]\n'
    content = section + '\nsetting="disabled"\n[project]\ndependencies=["lib==2"]\n'
    (tmp_path / "pyproject.toml").write_text(original)
    with pytest.raises(proposal.BoundaryError, match="test_controls_changed"):
        proposal.apply_patches(tmp_path, [{
            "path": "pyproject.toml",
            "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "content": content,
        }])
    assert (tmp_path / "pyproject.toml").read_text() == original


def test_pyproject_dependency_repair_with_runner_section_still_allowed(tmp_path):
    original = '[project]\ndependencies=["lib==1"]\n[tool.pdm.scripts]\ntest="real"\n'
    content = original.replace("lib==1", "lib==2")
    (tmp_path / "pyproject.toml").write_text(original)
    changed = proposal.apply_patches(tmp_path, [{
        "path": "pyproject.toml",
        "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "content": content,
    }])
    assert changed == ["pyproject.toml"]
    assert (tmp_path / "pyproject.toml").read_text() == content


def test_directory_patch_target_is_rejected_not_crashed(tmp_path):
    (tmp_path / "src").mkdir()
    with pytest.raises(proposal.BoundaryError, match="patch_target_not_regular_file"):
        proposal.apply_patches(tmp_path, [{"path": "src", "original_sha256": None, "content": "x"}])