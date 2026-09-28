"""Canary (decoy) files: planted in watched directories where ransomware's
indiscriminate directory-walk is likely to touch them early. Any
modification, rename, or deletion of a canary is treated as a
high-confidence signal, since nothing legitimate should ever touch them.
"""
import hashlib
import os
from pathlib import Path
from typing import Dict

CANARY_CONTENT = (
    b"This file is a security monitoring decoy planted by the "
    b"Ransomware Early Warning Toolkit. Do not move, rename, edit, or "
    b"delete this file.\n"
)

# Filenames chosen to look attractive to a ransomware directory walk
# (alphabetically early, common document extensions).
CANARY_FILENAMES = [
    "0000_patient_records_backup.docx",
    "0001_billing_master.xlsx",
    "0002_insurance_claims.pdf",
    "AAA_important_do_not_delete.docx",
    "Financials_2024.xlsx",
]


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def deploy_canaries(directory: str, count: int) -> Dict[str, str]:
    """Create up to `count` canary files in `directory`. Returns a map of
    absolute path -> sha256 hash for later integrity checks."""
    os.makedirs(directory, exist_ok=True)
    manifest = {}
    for name in CANARY_FILENAMES[:count]:
        path = os.path.join(directory, name)
        if not os.path.exists(path):
            with open(path, "wb") as fh:
                fh.write(CANARY_CONTENT)
        manifest[path] = _hash(CANARY_CONTENT)
    return manifest


def deploy_canaries_in_paths(watch_paths, dirname: str, per_dir: int) -> Dict[str, str]:
    manifest = {}
    for base in watch_paths:
        target = os.path.join(base, dirname)
        try:
            manifest.update(deploy_canaries(target, per_dir))
        except OSError:
            continue
    return manifest


def check_canary(path: str, expected_hash: str) -> bool:
    """Returns True if the canary is intact (unchanged and present)."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except (OSError, PermissionError):
        return False
    return _hash(data) == expected_hash


def find_missing_or_modified(manifest: Dict[str, str]):
    """Returns list of canary paths that were tampered with or removed."""
    return [path for path, digest in manifest.items() if not check_canary(path, digest)]
