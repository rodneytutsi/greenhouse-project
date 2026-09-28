# Architecture

## Why this design

Small U.S. healthcare providers (single clinics, small practice groups)
typically have no dedicated security staff and no budget for commercial
EDR/SIEM licensing. This toolkit is built to run entirely on free/open
components and existing hardware:

- **No paid services required.** SQLite instead of a database server,
  SMTP/webhook alerts instead of a paid paging service, plain HTTP
  instead of a managed message queue.
- **One small always-on machine for the server** (an old PC, a
  Raspberry Pi, or a cheap VPS) plus a lightweight Python agent on each
  workstation/server that touches patient data.
- **Detection without signatures.** Ransomware families change constantly;
  chasing signatures is a losing game for a team with no security budget.
  Instead this watches for the *behavior* that is common to nearly all
  ransomware: fast, bulk file modification that turns readable files into
  high-entropy (encrypted-looking) data, canary files being touched, and
  ransom notes appearing.

## Components

```
 Workstation / File Server              Central Server (one box)
 ┌─────────────────────────┐            ┌───────────────────────────┐
 │ agent/agent.py           │  HTTPS/    │ server/app.py (Flask)     │
 │  - deploys canary files  │  HTTP  --> │  - /api/heartbeat         │
 │  - watches filesystem    │  POST      │  - /api/alert             │
 │  - entropy + burst       │            │  - dashboard (/)          │
 │    detection             │            │  - SQLite storage         │
 │  - sends heartbeats      │            │  - email/webhook notifier │
 │  - optional autonomous   │            └───────────────────────────┘
 │    isolation response    │
 └─────────────────────────┘
```

- **agent/canary.py** — plants a handful of decoy files (named to look
  attractive to a directory walk) in each watched folder and periodically
  verifies their hash. Any change is a near-zero-false-positive signal.
- **agent/detector.py** — Shannon entropy of file contents plus a sliding
  time window; a burst of high-entropy/suspicious-extension file events
  trips a "mass encryption suspected" alert.
- **agent/responder.py** — optional, off by default. When a clinic enables
  it after testing, a critical alert can trigger local network isolation
  (iptables/netsh) so a compromised host stops spreading while still being
  able to reach the monitoring server.
- **server/** — collects heartbeats/alerts, stores them, notifies staff by
  email or webhook (Slack/Teams/Discord) on high/critical severity, and
  serves a simple auto-refreshing dashboard.
- **scripts/verify_backups.py** — a separate, standalone check for backup
  integrity (detection on the *backup* copy, not just live endpoints),
  meant to run right after the nightly backup job.

## Deployment sizing

For a clinic with 5–30 workstations and one file server, a single $200
mini-PC or a $500/year small VPS is enough to run the server component.
Agents use negligible CPU/RAM (a filesystem watch + periodic hash checks).

## Limitations (be upfront about these)

- This is **early warning and response tooling**, not a replacement for
  patching, backups, MFA, or staff phishing training — those remain the
  highest-leverage ransomware defenses.
- Entropy-based detection can false-positive on legitimate bulk compression
  or encryption jobs (e.g., nightly backup encryption). Exclude those
  paths/times in `watch_paths` and tune `mass_change_count_threshold`.
- Autonomous isolation is disruptive; keep it in `dry_run` mode until the
  detection logic has been validated against normal clinic workflow for
  at least a few weeks.
