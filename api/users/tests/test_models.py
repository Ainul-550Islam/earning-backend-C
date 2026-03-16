## **Api/users/tests/test_models.py**
from django.test import TestCase
from ..models import User, UserProfile, OTP
from ..factories import UserFactory


class UserModelTest(TestCase):
    
    def setUp(self):
        self.user = UserFactory()
    
    def test_user_creation(self):
        self.assertIsNotNone(self.user.id)
        self.assertTrue(self.user.is_verified)
    
    def test_user_profile_created(self):
        profile = UserProfile.objects.get(user=self.user)
        self.assertIsNotNone(profile)
    
    def test_referral_code_generated(self):
        self.assertIsNotNone(self.user.referral_code)
        self.assertEqual(len(self.user.referral_code), 8)