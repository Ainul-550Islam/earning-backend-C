# api/tests/test_kyc.py
from django.test import TestCase
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]


class KYCModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username=f'u_{uid()}', email=f'{uid()}@test.com', password='x'
        )

    def test_create_kyc(self):
        from api.kyc.models import KYC
        kyc = KYC.objects.create(
            user=self.user,
            full_name='Test User',
            phone_number='01712345678',
            payment_number='01712345678',
            document_type='nid',
            status='pending'
        )
        self.assertEqual(kyc.status, 'pending')

    def test_kyc_status_transition(self):
        from api.kyc.models import KYC
        kyc = KYC.objects.create(
            user=self.user,
            full_name='Test User',
            phone_number='01712345678',
            payment_number='01712345678',
            document_type='passport',
            status='pending'
        )
        kyc.status = 'approved'
        kyc.save()
        kyc.refresh_from_db()
        self.assertEqual(kyc.status, 'approved')

    def test_kyc_verification_log(self):
        from api.kyc.models import KYC, KYCVerificationLog
        kyc = KYC.objects.create(
            user=self.user,
            full_name='Test User',
            phone_number='01712345678',
            payment_number='01712345678',
            document_type='nid',
            status='pending'
        )
        log = KYCVerificationLog.objects.create(
            kyc=kyc,
            action='submitted',
            performed_by=self.user,
            details='Documents submitted',
        )
        self.assertEqual(log.action, 'submitted')