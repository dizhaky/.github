"""Pinned bundle integrity boundary; only then import the trusted launcher."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

FILES = {"ai_delivery.py", "ai_proposal.py", "global_auto_merge.py", "read_ownership_feed.py",
         "ai-delivery-policy.json", "launch_ai_delivery.py", "bootstrap_ai_delivery.py", "ai_delivery_bundle.py"}


def verify(root, manifest_hash):
    manifest = root / "manifest.json"
    if root.is_symlink() or manifest.is_symlink() or not manifest.is_file():
        raise ValueError("untrusted_bundle")
    raw = manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest_hash:
        raise ValueError("manifest_hash_changed")
    data = json.loads(raw)
    if data.get("schema") != 1 or set(data.get("files", {})) != FILES:
        raise ValueError("invalid_bundle_manifest")
    if {path.name for path in root.iterdir()} != FILES | {"manifest.json"}:
        raise ValueError("unexpected_bundle_file")
    for name, digest in data["files"].items():
        path = root / name
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("bundle_file_changed")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-sha256", required=True)
    args, remainder = parser.parse_known_args()
    root = Path(__file__).resolve().parent
    verify(root, args.manifest_sha256)
    sys.path.insert(0, str(root))
    from launch_ai_delivery import main as launch
    sys.argv = [str(root / "launch_ai_delivery.py"), *remainder]
    launch()


if __name__ == "__main__":
    main()
