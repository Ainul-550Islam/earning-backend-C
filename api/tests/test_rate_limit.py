# api/tests/test_rate_limit.py
from django.test import TestCase
from django.contrib.auth import get_user_model
import uuid
from api.rate_limit.models import RateLimitConfig, RateLimitLog, UserRateLimitProfile

User = get_user_model()

def uid(): 
    return uuid.uuid4().hex[:8]

class RateLimitTest(TestCase):

    def setUp(self):
        # একটি টেস্ট ইউজার তৈরি
        self.user = User.objects.create_user(
            username=f'u_{uid()}', 
            email=f'{uid()}@test.com', 
            password='x'
        )

    def test_rate_limit_config(self):
        config = RateLimitConfig.objects.create(
            name=f'test_config_{uid()}',
            rate_limit_type='endpoint',
            requests_per_unit=10,
            time_unit='minute',
        )
        self.assertEqual(config.requests_per_unit, 10)

    def test_rate_limit_log(self):
        log = RateLimitLog.objects.create(
            user=self.user,
            ip_address='127.0.0.1',
            endpoint='/api/auth/login/',
            status='allowed',
        )
        self.assertEqual(log.status, 'allowed')

    def test_user_rate_limit_profile(self):
        # এখানে objects.create() এর বদলে update_or_create ব্যবহার করা হয়েছে
        # কারণ ইউজার তৈরির সাথে সাথে প্রোফাইল অটোমেটিক তৈরি হতে পারে
        profile, created = UserRateLimitProfile.objects.update_or_create(
            user=self.user,
            defaults={
                'is_premium': False,
            }
        )
        self.assertFalse(profile.is_premium)
        
        # একটি ছোট এক্সট্রা চেক: প্রোফাইলটি কি সত্যিই ডাটাবেজে আছে?
        self.assertEqual(UserRateLimitProfile.objects.filter(user=self.user).count(), 1)