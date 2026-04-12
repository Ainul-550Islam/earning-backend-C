# api/promotions/services/notification_service.py
import logging
logger = logging.getLogger('services.notification')

class NotificationService:
    """Multi-channel notifications — Email, Push, Telegram, In-app。"""

    def send(self, user_id: int, notification_type: str, data: dict) -> bool:
        handlers = {
            'task_approved':    self._task_approved,
            'task_rejected':    self._task_rejected,
            'payment_received': self._payment_received,
            'fraud_alert':      self._fraud_alert,
        }
        fn = handlers.get(notification_type)
        if not fn: logger.warning(f'Unknown notification type: {notification_type}'); return False
        return fn(user_id, data)

    def _task_approved(self, user_id, data):
        self._email(user_id, 'task_approved', data)
        self._push(user_id, f'✅ Task Approved! You earned ${data.get("reward",0):.2f}')
        return True

    def _task_rejected(self, user_id, data):
        self._email(user_id, 'task_rejected', data)
        self._push(user_id, f'❌ Task rejected: {data.get("reason","See details")}')
        return True

    def _payment_received(self, user_id, data):
        self._email(user_id, 'payment_received', data)
        self._telegram(user_id, f'💰 Payment received: ${data.get("amount",0):.2f}')
        return True

    def _fraud_alert(self, user_id, data):
        self._email(user_id, 'fraud_alert', data)
        return True

    def _email(self, user_id, template: str, ctx: dict):
        try:
            from django.contrib.auth import get_user_model
            from django.core.mail import send_mail
            from django.template.loader import render_to_string
            user = get_user_model().objects.get(pk=user_id)
            html = render_to_string(f'emails/{template}.html', ctx)
            send_mail(template.replace('_',' ').title(), '', None, [user.email], html_message=html, fail_silently=True)
        except Exception as e:
            logger.error(f'Email {template} to user={user_id} failed: {e}')

    def _push(self, user_id, message: str):
        from django.core.cache import cache
        notifs = cache.get(f'notif:push:{user_id}') or []
        notifs.append({'message': message})
        cache.set(f'notif:push:{user_id}', notifs[-20:], timeout=86400)

    def _telegram(self, user_id, message: str):
        try:
            from django.contrib.auth import get_user_model
            from api.promotions.utils.telegram_bot import TelegramBot
            user = get_user_model().objects.get(pk=user_id)
            tg_id = getattr(user, 'telegram_id', None)
            if tg_id: TelegramBot().send_message(tg_id, message)
        except Exception: pass
