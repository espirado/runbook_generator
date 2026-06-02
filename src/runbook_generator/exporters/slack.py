"""Slack notification payload renderer and optional webhook sender."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

from runbook_generator.agent.models import IncidentReport
from runbook_generator.models import JsonDict


@dataclass(frozen=True, slots=True)
class SlackTarget:
    """Slack destination metadata for a generated notification."""

    webhook_url: str | None
    channel: str | None
    username: str
    send: bool = False


class SlackNotifier:
    """Render Slack messages and optionally send them via incoming webhook."""

    def __init__(self, target: SlackTarget) -> None:
        self.target = target

    def render_payload(self, report: IncidentReport) -> JsonDict:
        text = (
            f"{report.title} [{report.severity}] "
            f"for {report.environment}"
        )
        payload: JsonDict = {
            "username": self.target.username,
            "text": text,
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": report.title,
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Environment:*\n{report.environment}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Service:*\n{report.service or 'unknown'}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Severity:*\n{report.severity}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Status:*\n{report.status}",
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": report.summary,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": self._actions_text(report),
                    },
                },
            ],
        }
        if self.target.channel:
            payload["channel"] = self.target.channel
        return {
            "destination": {
                "type": "slack",
                "webhook_configured": bool(self.target.webhook_url),
                "channel": self.target.channel,
                "username": self.target.username,
            },
            "payload": payload,
            "publish_state": "send_requested" if self.target.send else "dry_run",
        }

    def send(self, payload: JsonDict) -> JsonDict:
        if not self.target.send:
            return {
                "sent": False,
                "status": "dry_run",
                "message": "Slack send was not requested.",
            }
        if not self.target.webhook_url:
            return {
                "sent": False,
                "status": "missing_webhook",
                "message": "RUNBOOK_SLACK_WEBHOOK_URL is required to send Slack notifications.",
            }

        request = urllib.request.Request(
            self.target.webhook_url,
            data=json.dumps(payload["payload"]).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read().decode("utf-8")
                return {
                    "sent": 200 <= response.status < 300,
                    "status": response.status,
                    "message": body,
                }
        except Exception as exc:  # pragma: no cover - network failures vary.
            return {
                "sent": False,
                "status": "send_failed",
                "message": str(exc),
            }

    @staticmethod
    def _actions_text(report: IncidentReport) -> str:
        actions = report.recommended_actions[:5]
        if not actions:
            return "*Recommended actions:*\nNo actions were generated."
        return "*Recommended actions:*\n" + "\n".join(
            f"{index}. {action}" for index, action in enumerate(actions, 1)
        )
