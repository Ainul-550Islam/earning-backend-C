# api/admin_panel/slack_integration.py
"""Slack alerts for critical admin events."""
from __future__ import annotations
import logging
from typing import Dict, List, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class SlackIntegration:
    """Send admin alerts to Slack via webhook."""

    WEBHOOK_URL = getattr(settings, 'SLACK_WEBHOOK_URL', '')
    CHANNEL     = getattr(settings, 'SLACK_ADMIN_CHANNEL', '#admin-alerts')

    SEVERITY_COLORS = {
        'critical': '#FF0000',
        'high':     '#FF6600',
        'medium':   '#FFCC00',
        'low':      '#00CC00',
        'info':     '#0066CC',
    }

    @classmethod
    def send(cls, title: str, message: str, severity: str = 'info',
              fields: List[Dict] = None, actor: str = 'System') -> bool:
        if not cls.WEBHOOK_URL:
            logger.debug("[Slack] SLACK_WEBHOOK_URL not configured")
            return False
        try:
            import requests
            color = cls.SEVERITY_COLORS.get(severity, '#0066CC')
            payload = {
                'channel': cls.CHANNEL,
                'username': 'AdminPanel Bot',
                'icon_emoji': ':robot_face:',
                'attachments': [{
                    'color': color,
                    'title': title,
                    'text': message,
                    'fields': fields or [],
                    'footer': f'AdminPanel | {actor}',
                    'ts': __import__('time').time(),
                }],
            }
            resp = requests.post(cls.WEBHOOK_URL, json=payload, timeout=5)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"[Slack] Send failed: {e}")
            return False

    @classmethod
    def alert_fraud(cls, user_id, risk_score: int, detail: str) -> bool:
        return cls.send(
            title=f"🚨 Fraud Detected — User {user_id}",
            message=detail, severity='critical',
            fields=[{'title': 'Risk Score', 'value': f'{risk_score}/100', 'short': True}]
        )

    @classmethod
    def alert_large_withdrawal(cls, user_id, amount: float) -> bool:
        return cls.send(
            title=f"💰 Large Withdrawal Request — ৳{amount:,.0f}",
            message=f"User {user_id} requested ৳{amount:,.2f}",
            severity='high'
        )

    @classmethod
    def alert_system_down(cls, service: str, error: str) -> bool:
        return cls.send(
            title=f"🔴 Service Down — {service}",
            message=error, severity='critical'
        )

    @classmethod
    def notify_new_advertiser(cls, advertiser_name: str) -> bool:
        return cls.send(
            title=f"🎯 New Advertiser — {advertiser_name}",
            message="A new advertiser has registered and requires approval.",
            severity='info'
        )


slack = SlackIntegration()