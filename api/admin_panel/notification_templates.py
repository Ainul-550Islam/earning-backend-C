# api/admin_panel/notification_templates.py
"""Email/push/SMS template management for admin_panel."""
from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class NotificationTemplateManager:
    """Manage notification templates for email, push, and SMS."""

    TEMPLATE_TYPES = ['email', 'push', 'sms', 'in_app']
    DEFAULT_TEMPLATES = {
        'withdrawal_approved': {
            'email_subject': '✅ Withdrawal Approved — ৳{{amount}}',
            'email_body': 'Dear {{username}},\n\nYour withdrawal of ৳{{amount}} via {{gateway}} has been approved.\n\nReference: {{reference}}\n',
            'push_title': '✅ Withdrawal Approved!',
            'push_body':  'Your ৳{{amount}} withdrawal is being processed.',
            'sms':        '✅ Withdrawal ৳{{amount}} approved. Ref: {{reference}}',
        },
        'kyc_approved': {
            'email_subject': '✅ Identity Verified',
            'email_body': 'Dear {{username}},\n\nYour identity has been verified. Enjoy all features!\n',
            'push_title': '✅ Identity Verified!',
            'push_body': 'Your account is now fully verified.',
            'sms': 'Your identity verification is approved. Account fully activated.',
        },
        'maintenance_notice': {
            'email_subject': '⚠️ Scheduled Maintenance — {{date}}',
            'email_body': 'Dear {{username}},\n\nScheduled maintenance on {{date}} for {{duration}} minutes.\n{{message}}\n',
            'push_title': '⚠️ Maintenance Scheduled',
            'push_body': '{{message}} Duration: {{duration}} mins.',
            'sms': 'Platform maintenance on {{date}} for {{duration}} mins. {{message}}',
        },
    }

    @classmethod
    def get_template(cls, template_key: str, channel: str = 'email') -> Optional[str]:
        """Get a template, falling back to defaults."""
        try:
            from api.admin_panel.models.config import EmailTemplate
            tmpl = EmailTemplate.objects.get(template_key=template_key)
            if channel == 'email':
                return tmpl.body_html or tmpl.body_text
            return getattr(tmpl, f'{channel}_body', None) or tmpl.body_text
        except Exception:
            default = cls.DEFAULT_TEMPLATES.get(template_key, {})
            return default.get(f'{channel}_body') or default.get('email_body', '')

    @classmethod
    def render_template(cls, template_key: str, context: Dict, channel: str = 'email') -> str:
        """Render a template with context variables."""
        template = cls.get_template(template_key, channel) or ''
        for key, value in context.items():
            template = template.replace(f'{{{{{{key}}}}}}'.replace('{{', '{{'), str(value))
        # Also handle {{key}} format
        for key, value in context.items():
            template = template.replace('{{' + key + '}}', str(value))
        return template

    @classmethod
    def update_template(cls, template_key: str, body_text: str,
                         body_html: str = '', subject: str = '', actor=None) -> bool:
        try:
            from api.admin_panel.models.config import EmailTemplate
            EmailTemplate.objects.update_or_create(
                template_key=template_key,
                defaults={'body_text': body_text, 'body_html': body_html, 'subject': subject}
            )
            if actor:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=actor, action='update_notification_template',
                                  changes={'template_key': template_key})
            return True
        except Exception:
            return False

    @classmethod
    def list_templates(cls) -> List[Dict]:
        try:
            from api.admin_panel.models.config import EmailTemplate
            db_templates = list(EmailTemplate.objects.values('template_key', 'subject', 'updated_at'))
            keys = {t['template_key'] for t in db_templates}
            # Add defaults not in DB
            for key in cls.DEFAULT_TEMPLATES:
                if key not in keys:
                    db_templates.append({'template_key': key, 'subject': '', 'updated_at': None, 'source': 'default'})
            return db_templates
        except Exception:
            return [{'template_key': k} for k in cls.DEFAULT_TEMPLATES]

    @classmethod
    def send_templated_notification(cls, template_key: str, user_id: Any,
                                     context: Dict, channels: List[str] = None) -> Dict:
        channels = channels or ['push']
        results = {}
        for channel in channels:
            try:
                rendered = cls.render_template(template_key, context, channel)
                if channel == 'push':
                    title = cls.render_template(template_key + '_title', context, 'push_title') or template_key
                    from api.admin_panel.notifications_push import push_manager
                    r = push_manager.send_to_user(user_id, title, rendered)
                    results['push'] = r
                elif channel == 'email':
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    user = User.objects.get(pk=user_id)
                    if user.email:
                        subject = cls.get_template(template_key + '_subject', 'email_subject') or template_key
                        from api.admin_panel.email_gateway import email_gateway
                        ok = email_gateway.send_simple(user.email, subject, rendered)
                        results['email'] = ok
            except Exception as e:
                results[channel] = {'error': str(e)}
        return results

notification_template_manager = NotificationTemplateManager()