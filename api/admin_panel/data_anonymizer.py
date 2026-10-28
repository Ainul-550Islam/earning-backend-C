# api/admin_panel/data_anonymizer.py
"""GDPR data anonymization — replaces PII with anonymized values."""
from __future__ import annotations
import hashlib, secrets, logging
from typing import Any, Dict, List
from django.utils import timezone

logger = logging.getLogger(__name__)

class DataAnonymizer:
    SALT = secrets.token_hex(16)  # Per-instance salt

    @classmethod
    def anonymize_user(cls, user_id: Any, actor) -> Dict:
        """Anonymize a user account — replace PII with hashed/fake values."""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(pk=user_id)
            anon_suffix = hashlib.sha256(f"{cls.SALT}{user_id}".encode()).hexdigest()[:8]
            user.username  = f"deleted_user_{anon_suffix}"
            user.email     = f"deleted_{anon_suffix}@anonymized.invalid"
            user.first_name = 'Deleted'
            user.last_name  = 'User'
            user.is_active  = False
            user.set_unusable_password()
            user.save()
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='anonymize_user', model_name='User',
                              object_id=str(user_id), changes={'anonymized': True})
            return {'success': True, 'user_id': user_id, 'new_username': user.username}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def anonymize_field(cls, value: str, field_type: str = 'generic') -> str:
        """Anonymize a single field value."""
        if not value: return ''
        anon_hash = hashlib.sha256(f"{cls.SALT}{value}".encode()).hexdigest()[:12]
        templates = {
            'email': f"anon_{anon_hash}@deleted.invalid",
            'phone': f"+880{anon_hash[:10]}",
            'name':  f"User_{anon_hash[:8]}",
            'ip':    '0.0.0.0',
            'generic': f"[REDACTED_{anon_hash[:8]}]",
        }
        return templates.get(field_type, templates['generic'])

    @classmethod
    def batch_anonymize_old_users(cls, days_inactive: int = 365*3, dry_run: bool = True) -> Dict:
        """Batch anonymize users inactive for N days."""
        from django.contrib.auth import get_user_model
        from datetime import timedelta
        User = get_user_model()
        cutoff = timezone.now() - timedelta(days=days_inactive)
        qs = User.objects.filter(is_active=False, last_login__lt=cutoff)
        count = qs.count()
        if not dry_run:
            logger.warning(f"[Anonymizer] Batch anonymizing {count} users")
        return {'eligible': count, 'dry_run': dry_run, 'days_inactive': days_inactive}

data_anonymizer = DataAnonymizer()