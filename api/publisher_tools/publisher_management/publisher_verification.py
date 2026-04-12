# api/publisher_tools/publisher_management/publisher_verification.py
"""Publisher Verification — Email, phone, domain verification।"""
import uuid, random, string
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.validators import MinValueValidator
from core.models import TimeStampedModel


class PublisherVerification(TimeStampedModel):
    """Publisher email ও phone verification records।"""

    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_pubverif_tenant', db_index=True)

    VERIFICATION_TYPE_CHOICES = [
        ('email', _('Email Verification')),
        ('phone', _('Phone / SMS Verification')),
        ('domain', _('Domain Ownership')),
        ('two_factor', _('Two-Factor Authentication Setup')),
    ]
    STATUS_CHOICES = [
        ('pending',  _('Pending')),
        ('verified', _('Verified')),
        ('expired',  _('Expired')),
        ('failed',   _('Failed')),
    ]

    publisher         = models.ForeignKey('publisher_tools.Publisher', on_delete=models.CASCADE, related_name='verifications_list')
    verification_type = models.CharField(max_length=20, choices=VERIFICATION_TYPE_CHOICES, db_index=True)
    identifier        = models.CharField(max_length=255, help_text=_("Email address, phone number, or domain"))
    code              = models.CharField(max_length=64, blank=True)
    token             = models.CharField(max_length=128, unique=True, blank=True)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    attempt_count     = models.IntegerField(default=0)
    max_attempts      = models.IntegerField(default=5)
    expires_at        = models.DateTimeField(null=True, blank=True)
    verified_at       = models.DateTimeField(null=True, blank=True)
    ip_address        = models.GenericIPAddressField(null=True, blank=True)
    user_agent        = models.TextField(blank=True)
    metadata          = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_publisher_verifications'
        verbose_name = _('Publisher Verification')
        verbose_name_plural = _('Publisher Verifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher', 'verification_type', 'status']),
            models.Index(fields=['token']),
        ]

    def __str__(self):
        return f"{self.publisher.publisher_id} — {self.verification_type} [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = uuid.uuid4().hex + uuid.uuid4().hex
        if not self.code and self.verification_type in ('email', 'phone', 'two_factor'):
            self.code = ''.join(random.choices(string.digits, k=6))
        if not self.expires_at:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return bool(self.expires_at and timezone.now() > self.expires_at)

    @property
    def can_attempt(self):
        return self.attempt_count < self.max_attempts and not self.is_expired

    def verify(self, code: str) -> bool:
        if not self.can_attempt:
            return False
        self.attempt_count += 1
        if self.code == code:
            self.status = 'verified'
            self.verified_at = timezone.now()
            self.save()
            self._update_publisher_status()
            return True
        if self.attempt_count >= self.max_attempts:
            self.status = 'failed'
        self.save()
        return False

    def verify_by_token(self, token: str) -> bool:
        if self.token == token and not self.is_expired:
            self.status = 'verified'
            self.verified_at = timezone.now()
            self.save()
            self._update_publisher_status()
            return True
        return False

    def _update_publisher_status(self):
        pub = self.publisher
        if self.verification_type == 'email':
            pub.is_email_verified = True
            pub.save(update_fields=['is_email_verified', 'updated_at'])
        elif self.verification_type == 'phone':
            try:
                pub.user.is_phone_verified = True
                pub.user.save(update_fields=['is_phone_verified'])
            except Exception:
                pass

    def send_code(self):
        """Verification code পাঠায়। Production-এ SMS/email gateway use করো।"""
        import logging
        logger = logging.getLogger(__name__)
        if self.verification_type == 'email':
            logger.info(f'Email verification code {self.code} sent to {self.identifier}')
        elif self.verification_type == 'phone':
            logger.info(f'SMS verification code {self.code} sent to {self.identifier}')
        return self.code

    def resend(self):
        if self.attempt_count >= self.max_attempts:
            raise ValueError("Maximum attempts reached. Request a new verification.")
        self.code = ''.join(random.choices(string.digits, k=6))
        from datetime import timedelta
        self.expires_at = timezone.now() + timedelta(hours=24)
        self.save(update_fields=['code', 'expires_at', 'updated_at'])
        return self.send_code()
