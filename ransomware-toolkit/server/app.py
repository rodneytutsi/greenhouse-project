"""Central dashboard + collection API.

A single small Flask app is enough for a clinic with a handful of
endpoints: it receives heartbeats/alerts from agents, stores them in
SQLite, fires notifications on high/critical alerts, and serves a simple
status dashboard for whoever is on call for IT.
"""
import os
import time

from flask import Flask, jsonify, render_template, request

from . import db
from .notifier import NotifierConfig, notify

API_KEY = os.environ.get("RWT_API_KEY", "change-me")
NOTIFIER = NotifierConfig.from_env(os.environ)
NOTIFY_SEVERITIES = {"high", "critical"}

app = Flask(__name__)
db.init_db()


def _check_auth(req) -> bool:
    header = req.headers.get("Authorization", "")
    return header == f"Bearer {API_KEY}"


@app.post("/api/heartbeat")
def api_heartbeat():
    if not _check_auth(request):
        return jsonify({"error": "unauthorized"}), 401
    payload = request.get_json(force=True, silent=True) or {}
    agent_id = payload.get("agent_id")
    timestamp = payload.get("timestamp", time.time())
    if not agent_id:
        return jsonify({"error": "agent_id required"}), 400
    db.upsert_heartbeat(agent_id, timestamp)
    return jsonify({"status": "ok"})


@app.post("/api/alert")
def api_alert():
    if not _check_auth(request):
        return jsonify({"error": "unauthorized"}), 401
    payload = request.get_json(force=True, silent=True) or {}
    agent_id = payload.get("agent_id")
    severity = payload.get("severity", "info")
    alert_type = payload.get("type", "unknown")
    details = payload.get("details", "")
    timestamp = payload.get("timestamp", time.time())
    if not agent_id:
        return jsonify({"error": "agent_id required"}), 400

    db.insert_alert(agent_id, severity, alert_type, details, timestamp)

    if severity in NOTIFY_SEVERITIES:
        notify(NOTIFIER, agent_id, severity, alert_type, details)

    return jsonify({"status": "ok"})


@app.post("/api/alerts/<int:alert_id>/ack")
def api_ack_alert(alert_id):
    if not _check_auth(request):
        return jsonify({"error": "unauthorized"}), 401
    db.acknowledge_alert(alert_id)
    return jsonify({"status": "ok"})


@app.get("/api/agents")
def api_list_agents():
    if not _check_auth(request):
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(db.list_agents())


@app.get("/api/alerts")
def api_list_alerts():
    if not _check_auth(request):
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(db.list_alerts())


@app.get("/")
@app.get("/dashboard")
def dashboard():
    agents = db.list_agents()
    alerts = db.list_alerts(limit=50)
    return render_template(
        "dashboard.html",
        agents=agents,
        alerts=alerts,
        offline_count=sum(1 for a in agents if a["status"] == "offline"),
        critical_count=sum(1 for a in alerts if a["severity"] == "critical" and not a["acknowledged"]),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("RWT_PORT", "8080")))
