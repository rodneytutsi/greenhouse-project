# Ransomware Early Warning & Response Toolkit

An affordable ransomware early-warning and response toolkit built for
small U.S. healthcare providers (single clinics, small practice groups)
that have no dedicated security team or budget for commercial EDR/SIEM
products. Everything here runs on free/open-source components and modest
existing hardware — see `docs/ARCHITECTURE.md` for the full design
rationale.

## What it does

- **Canary files**: decoy documents planted in shared/patient-data
  folders. Any access, rename, or edit of one is a near-zero-false-positive
  signal that something is walking the filesystem indiscriminately.
- **Behavioral detection**: a Shannon-entropy check flags files that
  suddenly look encrypted, combined with a sliding-window burst detector
  that catches the "many files touched in seconds" pattern typical of
  ransomware — no signatures to keep updated.
- **Central dashboard**: a single lightweight Flask + SQLite server
  collects heartbeats/alerts from every endpoint and shows status at a
  glance, auto-refreshing.
- **Alerting**: email (any SMTP account) and/or webhook (Slack/Teams/
  Discord) notifications the moment a high/critical alert fires.
- **Optional automated response**: off by default. Once tuned and tested,
  a clinic can opt into automatic network isolation of a compromised host.
- **Backup integrity checks**: a standalone script to catch ransomware that
  reaches backup storage before it's too late to notice.
- **HIPAA-aware incident response runbook** and breach-assessment checklist
  for the people who'll actually be handling an incident at 2am.

## Quick start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 1. Start the central server (run this on one always-on machine)
export RWT_API_KEY=some-long-random-string
export RWT_ALERT_EMAIL_TO=oncall@yourclinic.example
export RWT_SMTP_HOST=smtp.yourprovider.example
export RWT_SMTP_USER=alerts@yourclinic.example
export RWT_SMTP_PASSWORD=...
python -m server.app
# Dashboard at http://<server-host>:8080/

# 2. On each workstation/file server, configure and run the agent
cat > agent.json <<'EOF'
{
  "server_url": "http://<server-host>:8080",
  "api_key": "some-long-random-string",
  "watch_paths": ["/home/clinicuser/Documents", "/srv/shared"]
}
EOF
export RWT_AGENT_CONFIG=$(pwd)/agent.json
python -m agent.agent -v
```

For a permanent Linux install, see `scripts/install_agent.sh` (creates a
systemd service). For Windows endpoints, run `python -m agent.agent` via
Task Scheduler or NSSM.

## Running the tests

```bash
pip install pytest
pytest tests/
```

## Repository layout

```
ransomware-toolkit/
  agent/      endpoint agent: canary deployment, filesystem watcher,
              entropy/burst detection, optional isolation response
  server/     Flask dashboard + collection API + SQLite storage + notifier
  scripts/    backup integrity checker, systemd installer
  docs/       architecture notes, incident response runbook, HIPAA
              breach-assessment checklist
  tests/      unit tests for detection and canary logic
```

## Important limitations

This toolkit gives you *earlier warning* and a *documented response
process* — it does not replace patching, MFA, offline backups, and staff
phishing training, which remain the highest-leverage defenses against
ransomware. See `docs/ARCHITECTURE.md` for known false-positive scenarios
and tuning guidance before enabling automated response.
