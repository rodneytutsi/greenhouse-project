"""Filesystem watcher that feeds every create/modify/move event into the
mass-encryption detector and periodically re-checks canary integrity."""
import logging
import os

from watchdog.events import FileSystemEventHandler

from .detector import MassEncryptionDetector

log = logging.getLogger("rwt.watcher")


class RansomwareEventHandler(FileSystemEventHandler):
    def __init__(self, detector: MassEncryptionDetector, on_mass_encryption):
        self.detector = detector
        self.on_mass_encryption = on_mass_encryption

    def _handle(self, path: str):
        if not path or os.path.isdir(path):
            return
        event = self.detector.observe(path)
        if event.is_suspicious:
            log.debug("Suspicious file event: %s (entropy=%.2f)", path, event.entropy)
        if self.detector.is_mass_encryption_in_progress():
            self.on_mass_encryption(self.detector.recent_suspicious_paths())

    def on_created(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._handle(event.dest_path)
