# api/cms/services_new/FormBuilderService.py
"""FormBuilder Service — no-code dynamic forms. CMS owns this."""
import logging
import html
import re
from typing import Dict, List, Any, Optional
logger = logging.getLogger(__name__)


def _sanitize_value(value: str, field_type: str = 'text') -> str:
    """Sanitize user input to prevent XSS and injection."""
    if not isinstance(value, str):
        return value
    # For all text fields: escape HTML entities
    value = html.escape(value, quote=True)
    # Remove null bytes
    value = value.replace('\x00', '')
    # Limit length
    return value[:10000]


class FormBuilderService:

    @staticmethod
    def get_form(slug: str) -> Optional[Any]:
        from api.cms.models_new.forms import DynamicForm
        try:
            return DynamicForm.objects.prefetch_related('fields').get(slug=slug, is_active=True)
        except DynamicForm.DoesNotExist:
            return None

    @staticmethod
    def get_form_schema(form) -> Dict:
        return {
            'id': form.id, 'slug': form.slug, 'title': form.title or form.name,
            'description': form.description, 'submit_text': form.submit_text,
            'success_message': form.success_message,
            'redirect_url': form.redirect_url,
            'requires_login': form.requires_login,
            'fields': [{
                'id': f.id, 'label': f.label, 'name': f.name,
                'type': f.field_type, 'placeholder': f.placeholder,
                'help_text': f.help_text, 'is_required': f.is_required,
                'choices': f.get_choices_list(),
                'default_value': f.default_value,
                'min_length': f.min_length, 'max_length': f.max_length,
                'css_class': f.css_class,
            } for f in form.fields.filter(is_visible=True).order_by('order')],
        }

    @staticmethod
    def validate_submission(form, data: dict) -> List[str]:
        errors = []
        for field in form.fields.filter(is_required=True, is_visible=True):
            value = data.get(field.name, '')
            if not value:
                errors.append(f"{field.label} is required")
                continue
            if field.min_length and len(str(value)) < field.min_length:
                errors.append(f"{field.label}: min {field.min_length} characters")
            if field.max_length and len(str(value)) > field.max_length:
                errors.append(f"{field.label}: max {field.max_length} characters")
            if field.field_type == 'email' and value and '@' not in str(value):
                errors.append(f"{field.label}: invalid email")
        return errors

    @staticmethod
    def submit_form(form_id: int, data: dict, user=None,
                    session_key: str = '', ip: str = '', user_agent: str = '') -> Dict:
        from api.cms.models_new.forms import DynamicForm, FormSubmission
        from django.db.models import F
        try:
            form = DynamicForm.objects.prefetch_related('fields').get(id=form_id, is_active=True)
        except DynamicForm.DoesNotExist:
            return {'success': False, 'error': 'Form not found'}

        # Check max submissions
        if form.max_submissions_per_user > 0 and user:
            user_count = FormSubmission.objects.filter(form=form, user=user).count()
            if user_count >= form.max_submissions_per_user:
                return {'success': False, 'error': 'Maximum submissions reached'}

        # Validate
        errors = FormBuilderService.validate_submission(form, data)
        if errors:
            return {'success': False, 'errors': errors}

        # Sanitize all submitted values to prevent XSS
        sanitized_data = {}
        for key, value in data.items():
            field_type = 'text'
            for field in form.fields.all():
                if field.name == key:
                    field_type = field.field_type
                    break
            sanitized_data[key] = _sanitize_value(str(value), field_type) if isinstance(value, str) else value
        data = sanitized_data

        submission = FormSubmission.objects.create(
            form=form, user=user, session_key=session_key,
            data=data, ip_address=ip or None, user_agent=user_agent,
        )
        DynamicForm.objects.filter(pk=form_id).update(total_submissions=F('total_submissions') + 1)

        # Reward on submission
        reward_coins = 0
        if form.reward_on_submit and form.reward_coins > 0 and user:
            try:
                from api.cms.services_new.CPALeadService import VirtualCurrencyService
                VirtualCurrencyService.award_coins(
                    user=user, amount=form.reward_coins,
                    reason=f"Form submission: {form.name}", tx_type='earn_bonus',
                )
                FormSubmission.objects.filter(pk=submission.pk).update(
                    reward_given=True, reward_coins=form.reward_coins
                )
                reward_coins = float(form.reward_coins)
            except Exception as e:
                logger.warning(f"FormBuilder reward failed: {e}")

        # Send email notifications
        if form.send_email_to:
            try:
                FormBuilderService._send_notification_email(form, submission, data)
            except Exception as e:
                logger.warning(f"FormBuilder notification email failed: {e}")

        return {
            'success': True,
            'submission_id': submission.id,
            'success_message': form.success_message,
            'redirect_url': form.redirect_url,
            'reward_coins': reward_coins,
        }

    @staticmethod
    def _send_notification_email(form, submission, data: dict):
        from django.core.mail import send_mail
        from django.conf import settings
        body = f"New submission for: {form.name}\n\n"
        for key, value in data.items():
            body += f"{key}: {value}\n"
        try:
            send_mail(
                subject=f"[CMS Form] {form.name}",
                message=body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@site.com'),
                recipient_list=[form.send_email_to],
                fail_silently=True,
            )
        except Exception:
            pass

    @staticmethod
    def get_submissions(form_id: int, limit: int = 100) -> List[Dict]:
        from api.cms.models_new.forms import FormSubmission
        subs = FormSubmission.objects.filter(form_id=form_id).order_by('-submitted_at')[:limit]
        return [{
            'id': s.id, 'data': s.data,
            'user': s.user.username if s.user else '',
            'ip': s.ip_address,
            'submitted_at': s.submitted_at.isoformat(),
        } for s in subs]
