"""Execute documented isolation examples in a disposable pytest child."""

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class IsolationBlueprintTest(unittest.TestCase):
    def test_documented_scaffold_and_guard(self):
        doc = (ROOT / "docs/TEST-ISOLATION.md").read_text()
        scaffold_section = doc.split("## 3. Canonical")[1].split("## 4.")[0]
        scaffold = re.search(r"```python\n(.*?)```", scaffold_section, re.S).group(1)
        guard_section = doc.split("### Canonical Guard Test")[1].split("## 5.")[0]
        guard = re.search(r"```python\n(.*?)```", guard_section, re.S).group(1)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "conftest.py").write_text(scaffold)
            (root / "test_isolation_guard.py").write_text(guard)
            env = {
                "PATH": os.environ["PATH"],
                "HOME": directory,
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                "PYTHONHASHSEED": "0",
            }
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "test_isolation_guard.py"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_template_inherits_standard(self):
        template = ROOT / ".github/repo-templates/AGENTS.md.template"
        self.assertIn("TEST-ISOLATION.md", template.read_text())

    def test_scaffold_does_not_overclaim_platform_guards(self):
        doc = (ROOT / "docs/TEST-ISOLATION.md").read_text()
        scaffold_section = doc.split("## 3. Canonical")[1].split("## 4.")[0]
        self.assertIn("not an OS sandbox", scaffold_section)
        self.assertIn("does not by itself block", scaffold_section)
        self.assertNotIn("Hermes", doc)
