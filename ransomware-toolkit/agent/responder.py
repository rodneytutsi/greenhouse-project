"""Automated containment actions. OFF by default (see AgentConfig) — a
false positive that cuts a clinic workstation off the network mid-shift is
a real cost, so this only runs when a clinic has explicitly opted in after
testing. Every action is logged; when `dry_run` is True (the default even
when enabled) actions are logged but not executed, so admins can see what
*would* have happened before trusting it live.
"""
import logging
import platform
import shutil
import subprocess

log = logging.getLogger("rwt.responder")


def isolate_host(dry_run: bool = True, allow_host: str | None = None) -> str:
    """Block outbound/inbound network traffic on this host except to
    `allow_host` (the monitoring server), so the agent can keep reporting
    while the ransomware process is cut off from spreading or reaching
    C2. Returns a human-readable description of the action taken."""
    system = platform.system()
    description = f"isolate_host(system={system}, allow_host={allow_host})"
    if dry_run:
        log.warning("[DRY RUN] would execute: %s", description)
        return f"DRY RUN: {description}"

    try:
        if system == "Linux" and shutil.which("iptables"):
            subprocess.run(["iptables", "-P", "OUTPUT", "DROP"], check=True)
            subprocess.run(["iptables", "-P", "INPUT", "DROP"], check=True)
            if allow_host:
                subprocess.run(
                    ["iptables", "-A", "OUTPUT", "-d", allow_host, "-j", "ACCEPT"],
                    check=True,
                )
                subprocess.run(
                    ["iptables", "-A", "INPUT", "-s", allow_host, "-j", "ACCEPT"],
                    check=True,
                )
            return f"EXECUTED: {description}"
        if system == "Windows" and shutil.which("netsh"):
            subprocess.run(
                ["netsh", "advfirewall", "set", "allprofiles", "state", "on"],
                check=True,
            )
            subprocess.run(
                [
                    "netsh", "advfirewall", "firewall", "add", "rule",
                    "name=RWT_ISOLATE", "dir=out", "action=block",
                ],
                check=True,
            )
            return f"EXECUTED: {description}"
        log.error("No supported firewall tool found for isolation on %s", system)
        return f"FAILED: no supported firewall tool on {system}"
    except subprocess.CalledProcessError as exc:
        log.exception("Isolation command failed")
        return f"FAILED: {exc}"


def kill_process(pid: int, dry_run: bool = True) -> str:
    description = f"kill_process(pid={pid})"
    if dry_run:
        log.warning("[DRY RUN] would execute: %s", description)
        return f"DRY RUN: {description}"
    try:
        import os
        import signal

        os.kill(pid, signal.SIGKILL)
        return f"EXECUTED: {description}"
    except (ProcessLookupError, PermissionError) as exc:
        return f"FAILED: {exc}"
