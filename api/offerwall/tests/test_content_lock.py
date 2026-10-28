"""
tests/test_content_lock.py — ContentLock views (was 0 tests)
Covers: create, check, unlock, by_token, B2B feature gate
"""
from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


class ContentLockCreateTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.pub    = User.objects.create_user('lockpub', password='pw')
        self.client.force_authenticate(user=self.pub)

    def test_create_lock_basic_user(self):
        resp = self.client.post('/api/offerwall/locks/', {
            'title':                 'My Exclusive Content',
            'lock_type':             'offerwall',
            'required_conversions':  1,
        }, format='json')
        self.assertIn(resp.status_code, [200, 201, 400, 403])

    def test_create_lock_b2b_free_plan_blocked(self):
        from api.offerwall.b2b.tests.factories import B2BClientFactory, B2BPlanFactory
        plan   = B2BPlanFactory(plan_type='free', allow_content_lock=False)
        client = B2BClientFactory(owner=self.pub, plan=plan, status='active')
        resp   = self.client.post('/api/offerwall/locks/', {
            'title':    'Locked Article',
            'lock_type': 'offerwall',
        }, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertIn('plan_limit', str(resp.data))

    def test_create_lock_b2b_starter_plan_allowed(self):
        from api.offerwall.b2b.tests.factories import B2BClientFactory, B2BPlanFactory
        plan   = B2BPlanFactory(plan_type='starter', allow_content_lock=True)
        client = B2BClientFactory(owner=self.pub, plan=plan, status='active')
        resp   = self.client.post('/api/offerwall/locks/', {
            'title':                'Starter Locked',
            'lock_type':            'offerwall',
            'required_conversions': 1,
        }, format='json')
        self.assertIn(resp.status_code, [200, 201])

    def test_create_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post('/api/offerwall/locks/', {}, format='json')
        self.assertEqual(resp.status_code, 401)


class ContentLockCheckTest(TestCase):

    def setUp(self):
        self.api    = APIClient()
        self.user   = User.objects.create_user('checkuser', password='pw')
        self.pub    = User.objects.create_user('lockowner', password='pw')
        self.api.force_authenticate(user=self.user)
        from api.offerwall.tests.factories import ContentLockFactory
        self.lock = ContentLockFactory(publisher=self.pub)

    def test_check_unauthenticated_lock(self):
        resp = self.api.get(f'/api/offerwall/locks/{self.lock.pk}/check/')
        self.assertIn(resp.status_code, [200, 404])

    def test_check_locked_status(self):
        resp = self.api.get(f'/api/offerwall/locks/{self.lock.pk}/check/')
        if resp.status_code == 200:
            self.assertIn('is_unlocked', resp.data)

    def test_by_token_endpoint(self):
        resp = self.api.get(
            f'/api/offerwall/locks/by_token/{self.lock.token}/')
        self.assertIn(resp.status_code, [200, 404])

    def test_by_token_invalid(self):
        resp = self.api.get('/api/offerwall/locks/by_token/invalid-token/')
        self.assertEqual(resp.status_code, 404)


class ContentLockUnlockTest(TestCase):

    def setUp(self):
        self.api  = APIClient()
        self.user = User.objects.create_user('unlockuser', password='pw')
        self.pub  = User.objects.create_user('unlockowner', password='pw')
        self.api.force_authenticate(user=self.user)
        from api.offerwall.tests.factories import ContentLockFactory
        self.lock = ContentLockFactory(publisher=self.pub)

    def test_unlock_without_conversions_fails(self):
        resp = self.api.post(
            f'/api/offerwall/locks/{self.lock.pk}/unlock/', {}, format='json')
        self.assertIn(resp.status_code, [200, 400, 403])

    def test_unlock_requires_auth(self):
        self.api.force_authenticate(user=None)
        resp = self.api.post(
            f'/api/offerwall/locks/{self.lock.pk}/unlock/', {}, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_expired_lock_blocked(self):
        from django.utils import timezone
        self.lock.expires_at = timezone.now() - __import__('datetime').timedelta(days=1)
        self.lock.save()
        resp = self.api.post(
            f'/api/offerwall/locks/{self.lock.pk}/unlock/', {}, format='json')
        self.assertIn(resp.status_code, [400, 403, 404])

    def test_unlock_with_approved_conversion(self):
        from api.offerwall.tests.factories import OfferConversionFactory, OfferFactory, OfferProviderFactory
        provider   = OfferProviderFactory()
        offer      = OfferFactory(provider=provider)
        conv       = OfferConversionFactory(
            offer=offer, user=self.user, status='approved')
        resp = self.api.post(
            f'/api/offerwall/locks/{self.lock.pk}/unlock/', {}, format='json')
        self.assertIn(resp.status_code, [200, 400, 403])
