#!/usr/bin/env python3
"""Backup integrity checker.

Ransomware toolkits are only half the story — if backups get encrypted
too, early warning didn't help. This script builds a manifest of file
hashes for a backup directory and, on later runs, flags anything that:
  * disappeared since the last known-good manifest,
  * now reads as high-entropy where it previously didn't (looks encrypted),
  * or matches a known ransom-note filename pattern.

Intended to run nightly via cron right after the backup job finishes.
Exit code is non-zero if anything looks wrong, so it can gate a "backup OK"
notification.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.detector import sample_file_entropy, is_ransom_note  # noqa: E402

ENTROPY_ALERT_THRESHOLD = 7.5


def hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(backup_dir: str) -> dict:
    manifest = {}
    for root, _, files in os.walk(backup_dir):
        for name in files:
            path = os.path.join(root, name)
            try:
                manifest[path] = {
                    "hash": hash_file(path),
                    "entropy": sample_file_entropy(path),
                }
            except (OSError, PermissionError):
                continue
    return manifest


def compare(old: dict, new: dict) -> list:
    issues = []
    for path in old:
        if path not in new:
            issues.append(f"MISSING: {path} was present before and is now gone")
    for path, info in new.items():
        if is_ransom_note(path):
            issues.append(f"RANSOM NOTE FOUND: {path}")
            continue
        old_entropy = old.get(path, {}).get("entropy", 0.0)
        if info["entropy"] >= ENTROPY_ALERT_THRESHOLD and old_entropy < ENTROPY_ALERT_THRESHOLD:
            issues.append(
                f"LIKELY ENCRYPTED: {path} entropy jumped from {old_entropy:.2f} to {info['entropy']:.2f}"
            )
    return issues


def main():
    parser = argparse.ArgumentParser(description="Verify backup integrity against ransomware tampering")
    parser.add_argument("backup_dir", help="Path to the backup directory to check")
    parser.add_argument(
        "--manifest",
        default=".backup_manifest.json",
        help="Path to the stored manifest from the previous run",
    )
    args = parser.parse_args()

    new_manifest = build_manifest(args.backup_dir)

    if os.path.exists(args.manifest):
        with open(args.manifest, "r") as fh:
            old_manifest = json.load(fh)
        issues = compare(old_manifest, new_manifest)
        if issues:
            print("BACKUP INTEGRITY ISSUES DETECTED:")
            for issue in issues:
                print(f"  - {issue}")
            with open(args.manifest, "w") as fh:
                json.dump(new_manifest, fh)
            sys.exit(1)
        else:
            print(f"OK: {len(new_manifest)} files checked, no issues found.")
    else:
        print(f"No prior manifest found; recording baseline of {len(new_manifest)} files.")

    with open(args.manifest, "w") as fh:
        json.dump(new_manifest, fh)
    sys.exit(0)


if __name__ == "__main__":
    main()
