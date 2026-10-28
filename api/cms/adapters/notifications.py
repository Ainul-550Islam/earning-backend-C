# api/cms/adapters/notifications.py
"""
Adapters for api.notifications, api.messaging, api.alerts

  NotificationAdapter — push/email/in-app notifications
  MessagingAdapter    — direct messages, SMS, chat
  AlertAdapter        — system alert dispatch
"""
import logging
from typing import Optional, Dict, Any, List

from .base import BaseAdapter

logger = logging.getLogger('api.cms.adapters')


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class NotificationAdapter(BaseAdapter):
    """CMS → api.notifications interface."""

    _system_name = 'api.notifications'

    @classmethod
    def _check_available(cls):
        import api.notifications  # noqa

    @classmethod
    def send(
        cls,
        user,
        title: str,
        body: str,
        notif_type: str = 'cms',
        data: Optional[Dict] = None,
        channels: Optional[List[str]] = None,
    ) -> bool:
        """
        Send a notification to a user via api.notifications.
        channels: ['push', 'email', 'in_app'] — defaults to ['in_app']
        """
        try:
            from api.notifications.services import NotificationService
            NotificationService.send(
                user=user,
                title=title,
                body=body,
                notif_type=notif_type,
                data=data or {},
                channels=channels or ['in_app'],
            )
            return True
        except ImportError:
            return cls._unavailable('send', False)
        except Exception as e:
            logger.warning("[CMS→Notifications] send failed for user %s: %s", getattr(user, 'pk', '?'), e)
            return False

    @classmethod
    def send_bulk(cls, user_ids: List[int], title: str, body: str, notif_type: str = 'cms') -> int:
        """Bulk notify multiple users. Returns count sent."""
        try:
            from api.notifications.services import NotificationService
            return NotificationService.send_bulk(
                user_ids=user_ids, title=title, body=body, notif_type=notif_type,
            )
        except ImportError:
            return cls._unavailable('send_bulk', 0)
        except Exception as e:
            logger.warning("[CMS→Notifications] send_bulk failed: %s", e)
            return 0

    @classmethod
    def notify_content_published(cls, user, content_title: str, content_url: str = '') -> bool:
        """Notify content owner when their content is published."""
        return cls.send(
            user=user,
            title="Your content is live!",
            body=f'"{content_title}" has been published.',
            notif_type='content_published',
            data={'content_url': content_url},
        )

    @classmethod
    def notify_reward_earned(cls, user, amount: float, currency: str = 'USD') -> bool:
        """Notify user of a reward credit."""
        return cls.send(
            user=user,
            title="You earned a reward!",
            body=f"You earned {amount} {currency}.",
            notif_type='reward_earned',
            data={'amount': amount, 'currency': currency},
        )

    @classmethod
    def notify_survey_available(cls, user, survey_title: str, survey_id: str) -> bool:
        """Notify user that a new survey is available."""
        return cls.send(
            user=user,
            title="New survey available!",
            body=f'"{survey_title}" is now available. Complete it to earn rewards.',
            notif_type='survey_available',
            data={'survey_id': survey_id},
        )

    @classmethod
    def notify_workflow_action(cls, user, action: str, content_title: str) -> bool:
        """Notify approver/author about a workflow state change."""
        messages = {
            'submitted': f'"{content_title}" has been submitted for review.',
            'approved': f'"{content_title}" has been approved.',
            'rejected': f'"{content_title}" has been rejected.',
        }
        body = messages.get(action, f'"{content_title}" workflow: {action}.')
        return cls.send(
            user=user,
            title=f"Content {action}",
            body=body,
            notif_type='workflow',
            data={'action': action, 'content_title': content_title},
        )


# ══════════════════════════════════════════════════════════════════════════════
# MESSAGING ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class MessagingAdapter(BaseAdapter):
    """CMS → api.messaging interface."""

    _system_name = 'api.messaging'

    @classmethod
    def _check_available(cls):
        import api.messaging  # noqa

    @classmethod
    def send_email(cls, user, subject: str, template: str, context: Optional[Dict] = None) -> bool:
        """Send a transactional email via api.messaging."""
        try:
            from api.messaging.services import EmailService
            EmailService.send_template(
                user=user, subject=subject, template=template, context=context or {}
            )
            return True
        except ImportError:
            return cls._unavailable('send_email', False)
        except Exception as e:
            logger.warning("[CMS→Messaging] send_email failed: %s", e)
            return False

    @classmethod
    def send_sms(cls, user, message: str) -> bool:
        """Send SMS via api.messaging."""
        try:
            from api.messaging.services import SMSService
            SMSService.send(user=user, message=message)
            return True
        except ImportError:
            return cls._unavailable('send_sms', False)
        except Exception as e:
            logger.warning("[CMS→Messaging] send_sms failed: %s", e)
            return False


# ══════════════════════════════════════════════════════════════════════════════
# ALERT ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class AlertAdapter(BaseAdapter):
    """CMS → api.alerts interface."""

    _system_name = 'api.alerts'

    @classmethod
    def _check_available(cls):
        import api.alerts  # noqa

    @classmethod
    def fire(cls, alert_type: str, severity: str = 'info', data: Optional[Dict] = None) -> bool:
        """Fire a system alert."""
        try:
            from api.alerts.services import AlertService
            AlertService.fire(alert_type=alert_type, severity=severity, data=data or {})
            return True
        except ImportError:
            logger.debug("[CMS→Alerts] api.alerts not available — alert '%s' dropped.", alert_type)
            return False
        except Exception as e:
            logger.warning("[CMS→Alerts] fire(%s) failed: %s", alert_type, e)
            return False

    @classmethod
    def cms_error(cls, message: str, data: Optional[Dict] = None) -> bool:
        return cls.fire('cms_error', 'error', {'message': message, **(data or {})})

    @classmethod
    def high_error_rate(cls, endpoint: str, rate: float) -> bool:
        return cls.fire('high_error_rate', 'warning', {'endpoint': endpoint, 'rate': rate})
