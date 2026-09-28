"""Notification channels for high/critical alerts. Both are free-tier
friendly: SMTP (any existing office email account or a free provider) and
a generic webhook (Slack/Teams/Discord all accept the same simple POST
shape), so a clinic doesn't need to pay for a paging service."""
import json
import logging
import smtplib
from email.mime.text import MIMEText

import requests

log = logging.getLogger("rwt.notifier")


class NotifierConfig:
    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int = 587,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        alert_email_to: str | None = None,
        webhook_url: str | None = None,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.alert_email_to = alert_email_to
        self.webhook_url = webhook_url

    @classmethod
    def from_env(cls, env: dict):
        return cls(
            smtp_host=env.get("RWT_SMTP_HOST"),
            smtp_port=int(env.get("RWT_SMTP_PORT", "587")),
            smtp_user=env.get("RWT_SMTP_USER"),
            smtp_password=env.get("RWT_SMTP_PASSWORD"),
            alert_email_to=env.get("RWT_ALERT_EMAIL_TO"),
            webhook_url=env.get("RWT_WEBHOOK_URL"),
        )


def notify(config: NotifierConfig, agent_id: str, severity: str, alert_type: str, details: str):
    subject = f"[Ransomware Toolkit] {severity.upper()} alert on {agent_id}: {alert_type}"
    body = f"Agent: {agent_id}\nSeverity: {severity}\nType: {alert_type}\nDetails: {details}"

    if config.smtp_host and config.alert_email_to:
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = config.smtp_user or "ransomware-toolkit@localhost"
            msg["To"] = config.alert_email_to
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10) as server:
                server.starttls()
                if config.smtp_user and config.smtp_password:
                    server.login(config.smtp_user, config.smtp_password)
                server.sendmail(msg["From"], [config.alert_email_to], msg.as_string())
        except (smtplib.SMTPException, OSError) as exc:
            log.error("Failed to send email alert: %s", exc)

    if config.webhook_url:
        try:
            requests.post(
                config.webhook_url,
                data=json.dumps({"text": f"{subject}\n{body}"}),
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
        except requests.RequestException as exc:
            log.error("Failed to send webhook alert: %s", exc)
