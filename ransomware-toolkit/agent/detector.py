"""Heuristics for spotting ransomware behavior without needing signatures:

1. Shannon entropy of file content — encrypted/compressed data reads as
   near-random, so a plaintext document that suddenly becomes high-entropy
   is a strong signal it was just encrypted in place.
2. A sliding window of "suspicious" file events (high entropy, a known
   ransomware extension appended, or a ransom-note filename dropped) —
   ransomware typically touches many files in a short burst, which looks
   very different from normal user activity.
"""
import math
import os
import time
from collections import deque
from dataclasses import dataclass

from .config import RANSOM_NOTE_PATTERNS, SUSPICIOUS_EXTENSIONS


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    length = len(data)
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    entropy = 0.0
    for count in counts:
        if count == 0:
            continue
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def sample_file_entropy(path: str, sample_bytes: int = 4096) -> float:
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(sample_bytes)
        return shannon_entropy(chunk)
    except (OSError, PermissionError):
        return 0.0


def has_suspicious_extension(path: str) -> bool:
    lower = path.lower()
    return any(lower.endswith(ext) for ext in SUSPICIOUS_EXTENSIONS)


def is_ransom_note(path: str) -> bool:
    name = os.path.basename(path).lower()
    return any(pattern in name for pattern in RANSOM_NOTE_PATTERNS)


@dataclass
class FileEvent:
    path: str
    timestamp: float
    entropy: float
    suspicious_extension: bool
    ransom_note: bool

    @property
    def is_suspicious(self) -> bool:
        return (
            self.entropy >= 7.5
            or self.suspicious_extension
            or self.ransom_note
        )


class MassEncryptionDetector:
    """Tracks recent file events in a sliding time window and raises once
    enough of them look like ransomware activity."""

    def __init__(self, count_threshold: int, window_seconds: int, entropy_threshold: float):
        self.count_threshold = count_threshold
        self.window_seconds = window_seconds
        self.entropy_threshold = entropy_threshold
        self._events: deque = deque()
        self._alerted_until = 0.0

    def observe(self, path: str) -> "FileEvent":
        entropy = sample_file_entropy(path)
        event = FileEvent(
            path=path,
            timestamp=time.time(),
            entropy=entropy,
            suspicious_extension=has_suspicious_extension(path),
            ransom_note=is_ransom_note(path),
        )
        if entropy >= self.entropy_threshold or event.suspicious_extension or event.ransom_note:
            self._events.append(event)
        self._trim()
        return event

    def _trim(self):
        cutoff = time.time() - self.window_seconds
        while self._events and self._events[0].timestamp < cutoff:
            self._events.popleft()

    def is_mass_encryption_in_progress(self) -> bool:
        self._trim()
        if len(self._events) < self.count_threshold:
            return False
        # Debounce: don't re-fire every single event once we're already alerting.
        now = time.time()
        if now < self._alerted_until:
            return False
        self._alerted_until = now + self.window_seconds
        return True

    def recent_suspicious_paths(self, limit: int = 20):
        return [e.path for e in list(self._events)[-limit:]]
