# api/tests/test_referral.py
from django.test import TestCase
from django.contrib.auth import get_user_model
import uuid
from api.referral.models import Referral, ReferralEarning, ReferralSettings

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]

class ReferralModelTest(TestCase):

    def setUp(self):
        # ইউনিক ইউজার তৈরি
        self.referrer = User.objects.create_user(
            username=f'ref_{uid()}', email=f'{uid()}@test.com', password='x'
        )
        self.referred = User.objects.create_user(
            username=f'new_{uid()}', email=f'{uid()}@test.com', password='x'
        )

    def test_referral_creation(self):
        # মডেলে 'referred_user' আছে, তাই এখানেও সেটিই ব্যবহার হবে
        r = Referral.objects.create(
            referrer=self.referrer,
            referred_user=self.referred, # ✅ এখানে 'referred' এর বদলে 'referred_user' হবে
        )
        self.assertEqual(r.referrer, self.referrer)
        self.assertEqual(r.referred_user, self.referred)

    def test_referral_earning(self):
        referral = Referral.objects.create(
            referrer=self.referrer,
            referred_user=self.referred, # ✅ এখানেও আপডেট করা হয়েছে
        )
        
        earning = ReferralEarning.objects.create(
            referral=referral,
            referrer=self.referrer,
            referred_user=self.referred,
            amount=50.00,
            commission_rate=10.00,
        )
        self.assertEqual(earning.referrer, self.referrer)
        self.assertEqual(earning.amount, 50.00)

    def test_referral_settings(self):
        settings_obj, _ = ReferralSettings.objects.get_or_create(
            defaults={
                'direct_signup_bonus': 20,
                'referrer_signup_bonus': 50,
                'lifetime_commission_rate': 10,
            }
        )
        self.assertIsNotNone(settings_obj)