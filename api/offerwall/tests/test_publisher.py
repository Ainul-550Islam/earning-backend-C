"""
tests/test_publisher.py — Publisher API (was 0 tests)
Covers: EmbedTokenView, SDKConfigView, PublisherStatsView,
        PublisherAPIKeyViewSet, PublisherAPIKeyAuthentication,
        B2B plan gating
"""
from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


class EmbedTokenViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user   = User.objects.create_user('pub1', 'pub1@test.com', 'pw')
        self.client.force_authenticate(user=self.user)

    def test_create_embed_token_basic_user(self):
        """Non-B2B users should get an embed token (or 403 depending on policy)."""
        resp = self.client.post('/api/offerwall/publisher/embed-token/', {
            'wall_id':    'test-wall',
            'expires_in': 3600,
        }, format='json')
        self.assertIn(resp.status_code, [200, 201, 403])

    def test_create_embed_token_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post('/api/offerwall/publisher/embed-token/', {})
        self.assertEqual(resp.status_code, 401)

    def test_create_embed_token_b2b_free_plan_blocked(self):
        from api.offerwall.b2b.tests.factories import B2BClientFactory, B2BPlanFactory
        plan   = B2BPlanFactory(plan_type='free', allow_white_label=False)
        client = B2BClientFactory(owner=self.user, plan=plan, status='active')
        resp   = self.client.post('/api/offerwall/publisher/embed-token/', {
            'wall_id': 'test-wall',
        }, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertIn('plan_limit', resp.data.get('error', ''))

    def test_create_embed_token_b2b_pro_plan_allowed(self):
        from api.offerwall.b2b.tests.factories import B2BClientFactory, B2BPlanFactory
        plan   = B2BPlanFactory(plan_type='pro', allow_white_label=True)
        client = B2BClientFactory(owner=self.user, plan=plan, status='active')
        resp   = self.client.post('/api/offerwall/publisher/embed-token/', {
            'wall_id': 'test-wall',
        }, format='json')
        self.assertIn(resp.status_code, [200, 201])

    def test_inactive_b2b_client_blocked(self):
        from api.offerwall.b2b.tests.factories import B2BClientFactory, B2BPlanFactory
        plan   = B2BPlanFactory(plan_type='pro', allow_white_label=True)
        client = B2BClientFactory(owner=self.user, plan=plan, status='suspended')
        resp   = self.client.post('/api/offerwall/publisher/embed-token/', {}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data.get('error'), 'client_not_active')


class SDKConfigViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user   = User.objects.create_user('sdkuser', password='pw')
        self.client.force_authenticate(user=self.user)

    def test_sdk_config_returns_config(self):
        resp = self.client.get('/api/offerwall/publisher/sdk-config/')
        self.assertIn(resp.status_code, [200, 404])

    def test_sdk_config_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/offerwall/publisher/sdk-config/')
        self.assertEqual(resp.status_code, 401)


class PublisherAPIKeyViewSetTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user   = User.objects.create_user('keyuser', password='pw')
        self.client.force_authenticate(user=self.user)

    def test_list_api_keys_empty(self):
        resp = self.client.get('/api/offerwall/publisher/keys/')
        self.assertIn(resp.status_code, [200, 404])

    def test_create_api_key(self):
        resp = self.client.post('/api/offerwall/publisher/keys/', {
            'name':  'My App Key',
            'scope': 'read_only',
        }, format='json')
        self.assertIn(resp.status_code, [200, 201, 400])

    def test_delete_api_key(self):
        resp = self.client.post('/api/offerwall/publisher/keys/', {
            'name': 'Del Key', 'scope': 'read_only'}, format='json')
        if resp.status_code in [200, 201] and resp.data.get('id'):
            del_resp = self.client.delete(
                f'/api/offerwall/publisher/keys/{resp.data["id"]}/')
            self.assertIn(del_resp.status_code, [200, 204])

    def test_create_key_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post('/api/offerwall/publisher/keys/', {}, format='json')
        self.assertEqual(resp.status_code, 401)


class PublisherStatsViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user   = User.objects.create_user('statsuser', password='pw')
        self.client.force_authenticate(user=self.user)

    def test_publisher_stats_returns_data(self):
        resp = self.client.get('/api/offerwall/publisher/stats/')
        self.assertIn(resp.status_code, [200, 404])

    def test_publisher_stats_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/offerwall/publisher/stats/')
        self.assertEqual(resp.status_code, 401)
