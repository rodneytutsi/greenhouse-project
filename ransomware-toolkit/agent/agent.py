"""Endpoint agent entry point.

Deploys canary files, watches the configured directories for ransomware-
like activity, sends periodic heartbeats to the central server, and posts
alerts the moment something suspicious is seen. Designed to run as a
long-lived process (systemd service / Windows service / cron @reboot).
"""
import argparse
import logging
import threading
import time

import requests
from watchdog.observers import Observer

from .canary import deploy_canaries_in_paths, find_missing_or_modified
from .config import AgentConfig
from .detector import MassEncryptionDetector
from .responder import isolate_host
from .watcher import RansomwareEventHandler

log = logging.getLogger("rwt.agent")


class Agent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {config.api_key}"})
        self.canary_manifest = {}
        self.detector = MassEncryptionDetector(
            count_threshold=config.mass_change_count_threshold,
            window_seconds=config.mass_change_window_seconds,
            entropy_threshold=config.entropy_threshold,
        )
        self._stop = threading.Event()

    def _post(self, endpoint: str, payload: dict):
        url = f"{self.config.server_url.rstrip('/')}/{endpoint.lstrip('/')}"
        try:
            resp = self.session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.warning("Failed to reach server at %s: %s", url, exc)

    def send_alert(self, severity: str, alert_type: str, details: str):
        log.error("ALERT[%s] %s: %s", severity, alert_type, details)
        self._post(
            "api/alert",
            {
                "agent_id": self.config.agent_id,
                "severity": severity,
                "type": alert_type,
                "details": details,
                "timestamp": time.time(),
            },
        )
        if severity == "critical" and self.config.autonomous_response_enabled:
            server_host = self.config.server_url.split("//")[-1].split(":")[0].split("/")[0]
            result = isolate_host(dry_run=self.config.dry_run, allow_host=server_host)
            log.warning("Autonomous response result: %s", result)
            self._post(
                "api/alert",
                {
                    "agent_id": self.config.agent_id,
                    "severity": "info",
                    "type": "autonomous_response",
                    "details": result,
                    "timestamp": time.time(),
                },
            )

    def _on_mass_encryption(self, sample_paths):
        self.send_alert(
            severity="critical",
            alert_type="mass_encryption_suspected",
            details=f"High-entropy/suspicious file activity burst. Sample paths: {sample_paths}",
        )

    def _heartbeat_loop(self):
        while not self._stop.is_set():
            self._post(
                "api/heartbeat",
                {"agent_id": self.config.agent_id, "timestamp": time.time()},
            )
            self._stop.wait(self.config.heartbeat_interval_seconds)

    def _canary_check_loop(self):
        while not self._stop.is_set():
            tampered = find_missing_or_modified(self.canary_manifest)
            if tampered:
                self.send_alert(
                    severity="critical",
                    alert_type="canary_tampered",
                    details=f"Canary file(s) modified or deleted: {tampered}",
                )
                # Re-deploy so we keep detecting further tampering rather
                # than alerting once and going blind.
                self.canary_manifest = deploy_canaries_in_paths(
                    self.config.watch_paths,
                    self.config.canary_dir_name,
                    self.config.canary_files_per_dir,
                )
            self._stop.wait(15)

    def run(self):
        log.info("Deploying canary files in %s", self.config.watch_paths)
        self.canary_manifest = deploy_canaries_in_paths(
            self.config.watch_paths,
            self.config.canary_dir_name,
            self.config.canary_files_per_dir,
        )

        observer = Observer()
        handler = RansomwareEventHandler(self.detector, self._on_mass_encryption)
        for path in self.config.watch_paths:
            observer.schedule(handler, path, recursive=True)
        observer.start()

        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        threading.Thread(target=self._canary_check_loop, daemon=True).start()

        log.info("Agent %s running, watching %s", self.config.agent_id, self.config.watch_paths)
        try:
            while not self._stop.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self._stop.set()
            observer.stop()
            observer.join()


def main():
    parser = argparse.ArgumentParser(description="Ransomware early warning endpoint agent")
    parser.add_argument("--config", default=None, help="Path to agent config JSON")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = AgentConfig.load(args.config) if args.config else AgentConfig.load()
    Agent(config).run()


if __name__ == "__main__":
    main()
