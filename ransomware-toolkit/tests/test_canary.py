import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.canary import deploy_canaries, find_missing_or_modified, check_canary


def test_deploy_canaries_creates_files():
    with tempfile.TemporaryDirectory() as tmp:
        manifest = deploy_canaries(tmp, count=3)
        assert len(manifest) == 3
        for path in manifest:
            assert os.path.exists(path)


def test_check_canary_detects_intact_file():
    with tempfile.TemporaryDirectory() as tmp:
        manifest = deploy_canaries(tmp, count=1)
        path, digest = next(iter(manifest.items()))
        assert check_canary(path, digest)


def test_check_canary_detects_modification():
    with tempfile.TemporaryDirectory() as tmp:
        manifest = deploy_canaries(tmp, count=1)
        path, digest = next(iter(manifest.items()))
        with open(path, "ab") as fh:
            fh.write(b"tampered")
        assert not check_canary(path, digest)


def test_check_canary_detects_deletion():
    with tempfile.TemporaryDirectory() as tmp:
        manifest = deploy_canaries(tmp, count=1)
        path, digest = next(iter(manifest.items()))
        os.remove(path)
        assert not check_canary(path, digest)


def test_find_missing_or_modified_returns_only_bad_ones():
    with tempfile.TemporaryDirectory() as tmp:
        manifest = deploy_canaries(tmp, count=3)
        paths = list(manifest.keys())
        os.remove(paths[0])
        with open(paths[1], "ab") as fh:
            fh.write(b"ransomware touched this")
        tampered = find_missing_or_modified(manifest)
        assert set(tampered) == {paths[0], paths[1]}
