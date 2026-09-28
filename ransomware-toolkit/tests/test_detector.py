import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.detector import (
    MassEncryptionDetector,
    has_suspicious_extension,
    is_ransom_note,
    shannon_entropy,
)


def test_shannon_entropy_low_for_repetitive_data():
    assert shannon_entropy(b"a" * 1000) < 1.0


def test_shannon_entropy_high_for_random_data():
    entropy = shannon_entropy(os.urandom(4096))
    assert entropy > 7.5


def test_shannon_entropy_empty():
    assert shannon_entropy(b"") == 0.0


def test_has_suspicious_extension():
    assert has_suspicious_extension("report.docx.locked")
    assert has_suspicious_extension("photo.jpg.encrypted")
    assert not has_suspicious_extension("report.docx")


def test_is_ransom_note():
    assert is_ransom_note("README_TO_DECRYPT.txt")
    assert is_ransom_note("HOW_TO_DECRYPT_FILES.html")
    assert not is_ransom_note("invoice.pdf")


def test_mass_encryption_detector_trips_after_threshold():
    detector = MassEncryptionDetector(count_threshold=3, window_seconds=10, entropy_threshold=7.5)
    with tempfile.TemporaryDirectory() as tmp:
        assert not detector.is_mass_encryption_in_progress()
        for i in range(3):
            path = os.path.join(tmp, f"file{i}.docx.locked")
            with open(path, "wb") as fh:
                fh.write(os.urandom(4096))
            detector.observe(path)
        assert detector.is_mass_encryption_in_progress()


def test_mass_encryption_detector_does_not_trip_below_threshold():
    detector = MassEncryptionDetector(count_threshold=10, window_seconds=10, entropy_threshold=7.5)
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(3):
            path = os.path.join(tmp, f"file{i}.docx.locked")
            with open(path, "wb") as fh:
                fh.write(os.urandom(4096))
            detector.observe(path)
        assert not detector.is_mass_encryption_in_progress()


def test_mass_encryption_detector_ignores_benign_events():
    detector = MassEncryptionDetector(count_threshold=3, window_seconds=10, entropy_threshold=7.5)
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(5):
            path = os.path.join(tmp, f"notes{i}.txt")
            with open(path, "w") as fh:
                fh.write("just a normal note about patient scheduling")
            detector.observe(path)
        assert not detector.is_mass_encryption_in_progress()


def test_mass_encryption_detector_window_expiry():
    detector = MassEncryptionDetector(count_threshold=3, window_seconds=1, entropy_threshold=7.5)
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(2):
            path = os.path.join(tmp, f"file{i}.docx.locked")
            with open(path, "wb") as fh:
                fh.write(os.urandom(4096))
            detector.observe(path)
        time.sleep(1.1)
        assert not detector.is_mass_encryption_in_progress()
