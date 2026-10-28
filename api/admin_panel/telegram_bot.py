# api/admin_panel/telegram_bot.py
"""Telegram bot for admin alerts and commands."""
from __future__ import annotations
import logging
from typing import Dict, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class TelegramBot:
    BOT_TOKEN  = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    ADMIN_CHAT = getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', '')
    API_BASE   = 'https://api.telegram.org/bot'

    @classmethod
    def send_message(cls, chat_id: str, text: str, parse_mode: str = 'HTML') -> Dict:
        if not cls.BOT_TOKEN:
            return {'success': False, 'error': 'TELEGRAM_BOT_TOKEN not configured'}
        try:
            import requests
            resp = requests.post(
                f"{cls.API_BASE}{cls.BOT_TOKEN}/sendMessage",
                json={'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode},
                timeout=10,
            )
            data = resp.json()
            return {'success': data.get('ok', False), 'response': data}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def alert_admin(cls, message: str, severity: str = 'info') -> Dict:
        if not cls.ADMIN_CHAT:
            return {'success': False, 'error': 'TELEGRAM_ADMIN_CHAT_ID not configured'}
        emoji = {'critical': '🚨', 'high': '⚠️', 'medium': 'ℹ️', 'low': '✅'}.get(severity, 'ℹ️')
        text = emoji + ' <b>AdminPanel Alert</b>\n\n' + message
        return cls.send_message(cls.ADMIN_CHAT, text)

    @classmethod
    def send_daily_stats(cls, stats: Dict) -> Dict:
        if not cls.ADMIN_CHAT:
            return {'success': False}
        users_new   = stats.get('users', {}).get('new_today', 0)
        revenue     = stats.get('revenue', {}).get('total_earned', 0)
        pending     = stats.get('pending_payouts', {}).get('count', 0)
        fraud       = stats.get('fraud', {}).get('total', 0)
        health      = stats.get('health_score', 100)
        lines = [
            '📊 <b>Daily Platform Summary</b>',
            '',
            f'👤 New Users: {users_new}',
            f'💰 Revenue: ৳{revenue:,.0f}',
            f'💳 Pending Payouts: {pending}',
            f'🚨 Fraud Alerts: {fraud}',
            f'🏥 Health: {health}%',
        ]
        text = '\n'.join(lines)
        return cls.send_message(cls.ADMIN_CHAT, text)

    @classmethod
    def process_webhook(cls, update: Dict) -> Optional[str]:
        message = update.get('message', {})
        text    = message.get('text', '').strip()
        chat_id = str(message.get('chat', {}).get('id', ''))
        commands = {
            '/status':  cls._cmd_status,
            '/pending': cls._cmd_pending,
            '/fraud':   cls._cmd_fraud,
            '/help':    cls._cmd_help,
        }
        cmd = text.split()[0] if text else ''
        fn  = commands.get(cmd)
        if fn:
            reply = fn()
            cls.send_message(chat_id, reply)
            return reply
        return None

    @classmethod
    def _cmd_status(cls) -> str:
        try:
            from api.admin_panel.monitoring import get_system_health_score
            score = get_system_health_score()
            return f'🏥 System Health: {score}%'
        except Exception:
            return '🏥 Status: OK'

    @classmethod
    def _cmd_pending(cls) -> str:
        try:
            from api.payout_queue.models import PayoutItem
            from django.db.models import Count, Sum
            s = PayoutItem.objects.filter(status='QUEUED').aggregate(
                c=Count('id'), a=Sum('gross_amount')
            )
            return f"💳 Pending Payouts: {s['c']} items, ৳{s['a'] or 0:,.0f}"
        except Exception:
            return '💳 Pending: N/A'

    @classmethod
    def _cmd_fraud(cls) -> str:
        try:
            from api.fraud_detection.models import FraudAttempt
            from django.utils import timezone
            from datetime import timedelta
            count = FraudAttempt.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            return f'🚨 Fraud alerts (1h): {count}'
        except Exception:
            return '🚨 Fraud: N/A'

    @classmethod
    def _cmd_help(cls) -> str:
        return (
            'Commands:\n'
            '/status — System health\n'
            '/pending — Pending payouts\n'
            '/fraud — Recent fraud\n'
            '/help — This help'
        )

    @classmethod
    def alert_fraud(cls, user_id, risk_score: int, detail: str) -> Dict:
        msg = f'User {user_id} | Score: {risk_score}/100 | {detail}'
        return cls.alert_admin(msg, severity='critical')

    @classmethod
    def alert_large_withdrawal(cls, user_id, amount: float) -> Dict:
        msg = f'User {user_id} requested ৳{amount:,.2f}'
        return cls.alert_admin(msg, severity='high')

    @classmethod
    def alert_system_down(cls, service: str, error: str) -> Dict:
        msg = f'Service: {service} | Error: {error}'
        return cls.alert_admin(msg, severity='critical')


telegram_bot = TelegramBot()