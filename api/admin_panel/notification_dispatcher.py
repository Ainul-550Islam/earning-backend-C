# api/admin_panel/notification_dispatcher.py
"""Central notification dispatch — routes to email/push/SMS/in_app."""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Single entry point for all outbound notifications."""

    CHANNELS = ['email', 'push', 'sms', 'in_app']

    @classmethod
    def send(cls, user_id: Any, template_key: str, context: Dict,
              channels: List[str] = None, priority: str = 'normal') -> Dict:
        """
        Dispatch notification via specified channels.
        channels: ['email', 'push', 'sms', 'in_app'] — default based on priority
        """
        if channels is None:
            channels = ['push', 'in_app'] if priority == 'normal' else ['push', 'sms', 'email', 'in_app']

        results = {'user_id': user_id, 'template': template_key, 'channels': {}}

        for channel in channels:
            try:
                if channel == 'push':
                    from api.admin_panel.notifications_push import push_manager
                    from api.admin_panel.notification_templates import notification_template_manager
                    title   = notification_template_manager.render_template(template_key, context, 'push_title')
                    body    = notification_template_manager.render_template(template_key, context, 'push')
                    r = push_manager.send_to_user(user_id, title or template_key, body)
                    results['channels']['push'] = r

                elif channel == 'email':
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    user = User.objects.get(pk=user_id)
                    if user.email:
                        from api.admin_panel.email_gateway import email_gateway
                        from api.admin_panel.notification_templates import notification_template_manager
                        subject = notification_template_manager.render_template(template_key, context, 'email_subject')
                        body    = notification_template_manager.render_template(template_key, context, 'email')
                        ok = email_gateway.send_simple(user.email, subject or template_key, body)
                        results['channels']['email'] = ok

                elif channel == 'sms':
                    try:
                        from django.contrib.auth import get_user_model
                        User = get_user_model()
                        user = User.objects.get(pk=user_id)
                        phone = getattr(user, 'phone_number', '') or getattr(getattr(user, 'profile', None), 'phone', '')
                        if phone:
                            from api.admin_panel.sms_gateway import sms_gateway
                            from api.admin_panel.notification_templates import notification_template_manager
                            msg = notification_template_manager.render_template(template_key, context, 'sms')
                            r = sms_gateway.send(phone, msg)
                            results['channels']['sms'] = r
                    except Exception as e:
                        results['channels']['sms'] = {'error': str(e)}

                elif channel == 'in_app':
                    from api.notifications.models import Notification
                    from api.admin_panel.notification_templates import notification_template_manager
                    title = notification_template_manager.render_template(template_key, context, 'push_title')
                    body  = notification_template_manager.render_template(template_key, context, 'push')
                    Notification.objects.create(
                        user_id=user_id, title=title or template_key,
                        message=body, notification_type=template_key,
                    )
                    results['channels']['in_app'] = True

            except Exception as e:
                logger.error(f"[Dispatcher] {channel} failed for user {user_id}: {e}")
                results['channels'][channel] = {'error': str(e)[:100]}

        return results

    @classmethod
    def broadcast(cls, template_key: str, context: Dict,
                   channels: List[str] = None, user_filter: Dict = None) -> Dict:
        """Broadcast to all or filtered users."""
        try:
            from celery import current_app
            current_app.send_task(
                'api.admin_panel.background_jobs.send_push_broadcast',
                args=[
                    context.get('title', template_key),
                    context.get('body', ''),
                    context, user_filter or {}
                ],
                queue='admin_panel.bulk',
            )
            return {'success': True, 'queued': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def send_critical_alert(cls, message: str, severity: str = 'critical') -> Dict:
        """Send critical alert to all admin staff."""
        from api.admin_panel.email_gateway import email_gateway
        sent = email_gateway.send_admin_alert(
            subject=f'[{severity.upper()}] Admin Alert',
            body=message, severity=severity
        )
        return {'sent': sent, 'severity': severity}


dispatcher = NotificationDispatcher()