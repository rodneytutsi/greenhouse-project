#!/usr/bin/env bash
# Installs the endpoint agent as a systemd service on a Linux workstation
# or server. Run as root. For Windows endpoints, use NSSM or Task
# Scheduler to run `python -m agent.agent` at startup instead.
set -euo pipefail

INSTALL_DIR="/opt/ransomware-toolkit"
CONFIG_DIR="/etc/ransomware-toolkit"
SERVICE_FILE="/etc/systemd/system/rwt-agent.service"

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root." >&2
  exit 1
fi

echo "Installing to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}" "${CONFIG_DIR}"
cp -r "$(dirname "$0")/../agent" "${INSTALL_DIR}/"
cp -r "$(dirname "$0")/../requirements.txt" "${INSTALL_DIR}/"

if [[ ! -f "${CONFIG_DIR}/agent.json" ]]; then
  cat > "${CONFIG_DIR}/agent.json" <<'EOF'
{
  "server_url": "http://CHANGE-ME:8080",
  "api_key": "change-me",
  "watch_paths": ["/home", "/srv/shared"],
  "autonomous_response_enabled": false,
  "dry_run": true
}
EOF
  echo "Wrote default config to ${CONFIG_DIR}/agent.json — edit it before starting the service."
fi

python3 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install --quiet -r "${INSTALL_DIR}/requirements.txt"

cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Ransomware Early Warning Agent
After=network.target

[Service]
Type=simple
Environment=RWT_AGENT_CONFIG=${CONFIG_DIR}/agent.json
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python -m agent.agent
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
echo "Installed. Edit ${CONFIG_DIR}/agent.json then run:"
echo "  systemctl enable --now rwt-agent"
