# kyc/tests/factories.py  ── WORLD #1
"""
Test factories for KYC models.
Requires: factory_boy (pip install factory-boy)
"""
try:
    import factory
    from factory.django import DjangoModelFactory
    FACTORY_BOY_AVAILABLE = True
except ImportError:
    FACTORY_BOY_AVAILABLE = False
    # Provide simple fallback creators
    class DjangoModelFactory:
        pass

import datetime
from django.contrib.auth import get_user_model

User = get_user_model()


def make_user(username=None, email=None, is_staff=False):
    """Create a test user without factory_boy."""
    import uuid
    uid      = str(uuid.uuid4())[:8]
    username = username or f"testuser_{uid}"
    email    = email    or f"{username}@test.com"
    user     = User.objects.create_user(username=username, email=email, password='testpass123')
    if is_staff:
        user.is_staff = True; user.save()
    return user


def make_kyc(user=None, status='pending', risk_score=10):
    """Create a test KYC record."""
    from api.kyc.models import KYC
    user = user or make_user()
    return KYC.objects.create(
        user=user,
        full_name='Test User',
        phone_number='01711111111',
        payment_number='01711111111',
        payment_method='bkash',
        document_type='nid',
        document_number='1234567890',
        status=status,
        risk_score=risk_score,
        address_line='Dhaka, Bangladesh',
        city='Dhaka',
        country='Bangladesh',
    )


def make_kyc_submission(user=None, status='submitted'):
    """Create a test KYCSubmission record."""
    from api.kyc.models import KYCSubmission
    from django.core.files.base import ContentFile
    user = user or make_user()
    dummy_image = ContentFile(b'\x89PNG\r\n\x1a\n' + b'\x00'*100, name='test.png')
    return KYCSubmission.objects.create(
        user=user,
        status=status,
        document_type='nid',
        document_number='1234567890',
        nid_front=dummy_image,
        nid_back=dummy_image,
        selfie_with_note=dummy_image,
        verification_progress=10,
    )


def make_blacklist_entry(btype='phone', value='01700000000', reason='Test'):
    from api.kyc.models import KYCBlacklist
    return KYCBlacklist.objects.create(type=btype, value=value, reason=reason, is_active=True)


def make_admin_note(kyc, author, content='Test note', note_type='general'):
    from api.kyc.models import KYCAdminNote
    return KYCAdminNote.objects.create(kyc=kyc, author=author, content=content, note_type=note_type)


def make_rejection_template(title='Invalid ID', body='Your ID document is invalid.'):
    from api.kyc.models import KYCRejectionTemplate
    return KYCRejectionTemplate.objects.create(title=title, body=body, is_active=True)
