# api/cms/models_new/api_keys.py
"""Per-user API key management for programmatic CMS access."""
import uuid
import secrets
import hashlib
from django.db import models
from django.conf import settings
from django.utils import timezone


class APIKey(models.Model):
    """
    Per-user API keys for programmatic access to CMS.
    Key is hashed — never stored in plaintext after creation.
    """
    SCOPES = [
        ('read',          'Read Only'),
        ('write',         'Read + Write'),
        ('admin',         'Admin Full Access'),
        ('postback',      'Postback Only'),
        ('analytics',     'Analytics Only'),
        ('publisher',     'Publisher Tools'),
    ]
    uuid        = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user        = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.CASCADE,
                                    related_name='cms_api_keys')
    name        = models.CharField(max_length=200, help_text="Friendly name for this key")
    key_prefix  = models.CharField(max_length=12, db_index=True,
                                   help_text="First 8 chars of key for identification")
    key_hash    = models.CharField(max_length=64, unique=True,
                                   help_text="SHA-256 hash of the full key")
    scope       = models.CharField(max_length=20, choices=SCOPES, default='read')
    is_active   = models.BooleanField(default=True, db_index=True)
    # Usage tracking
    last_used_at = models.DateTimeField(null=True, blank=True)
    request_count = models.PositiveIntegerField(default=0)
    allowed_ips  = models.TextField(blank=True,
                                     help_text="Allowed IPs, one per line. Empty = all allowed.")
    expires_at   = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "cms"
        verbose_name = "API Key"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.name} ({self.key_prefix}****)"

    @classmethod
    def create_key(cls, user, name: str, scope: str = 'read',
                    allowed_ips: str = '', expires_at=None) -> tuple:
        """
        Create a new API key. Returns (api_key_instance, raw_key).
        raw_key is shown ONCE — store it securely.
        """
        raw_key = f"cms_{scope[:4]}_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:12]
        api_key = cls.objects.create(
            user=user, name=name, scope=scope,
            key_prefix=key_prefix, key_hash=key_hash,
            allowed_ips=allowed_ips, expires_at=expires_at,
        )
        return api_key, raw_key

    @classmethod
    def verify(cls, raw_key: str, required_scope: str = None) -> 'APIKey':
        """Verify an API key and return the APIKey instance or None."""
        if not raw_key or not raw_key.startswith('cms_'):
            return None
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        try:
            api_key = cls.objects.select_related('user').get(
                key_hash=key_hash, is_active=True
            )
        except cls.DoesNotExist:
            return None
        # Check expiry
        if api_key.expires_at and timezone.now() > api_key.expires_at:
            return None
        # Check scope
        if required_scope:
            scope_levels = ['read', 'analytics', 'postback', 'publisher', 'write', 'admin']
            api_scope_level = scope_levels.index(api_key.scope) if api_key.scope in scope_levels else 0
            required_level = scope_levels.index(required_scope) if required_scope in scope_levels else 0
            if api_scope_level < required_level:
                return None
        # Update usage
        cls.objects.filter(pk=api_key.pk).update(
            last_used_at=timezone.now(),
            request_count=models.F('request_count') + 1,
        )
        return api_key

    def get_allowed_ips_list(self):
        return [ip.strip() for ip in self.allowed_ips.split('\n') if ip.strip()]

    def revoke(self):
        self.is_active = False
        self.save(update_fields=['is_active'])
