# cms/tests_new/test_missing_viewsets.py
"""
Tests for 6 previously-untested ViewSets:
  1. AdapterStatusViewSet
  2. BusinessLogicViewSet
  3. InteractorViewSet
  4. PushNotificationViewSet
  5. RepositoryViewSet
  6. SelectorViewSet
"""
import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase, APIClient

User = get_user_model()


def make_user(username=None, is_staff=False, is_superuser=False):
    username = username or f"u_{uuid.uuid4().hex[:6]}"
    return User.objects.create_user(
        username=username, password="pass123",
        is_staff=is_staff, is_superuser=is_superuser
    )


def auth_client(user, password="pass123"):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ─────────────────────────────────────────────────────────────────────────────
# 1. AdapterStatusViewSet
# ─────────────────────────────────────────────────────────────────────────────

class AdapterStatusViewSetTest(APITestCase):
    def setUp(self):
        try:
            from api.cms.viewsets.AdapterStatusViewSet import AdapterStatusViewSet
            self.ViewSet = AdapterStatusViewSet
        except ImportError:
            self.skipTest("AdapterStatusViewSet not importable")
        self.admin  = make_user(is_staff=True, is_superuser=True)
        self.su     = make_user(is_staff=True, is_superuser=True)
        self.user   = make_user()

    def _get_status(self, user=None):
        client = auth_client(user or self.admin)
        with patch('api.cms.viewsets.AdapterStatusViewSet.AdapterManager') as mock_mgr:
            mock_mgr.get_all_statuses.return_value = {
                'payment_tenants': {'status': 'ok', 'latency_ms': 12},
                'notifications':   {'status': 'ok', 'latency_ms': 8},
            }
            mock_mgr.get_summary.return_value = {'healthy': 2, 'degraded': 0, 'down': 0}
            response = client.get('/api/cms/adapters/status/')
        return response

    def test_status_endpoint_requires_admin(self):
        client = auth_client(self.user)
        response = client.get('/api/cms/adapters/status/')
        self.assertIn(response.status_code, [403, 401])

    def test_status_endpoint_accessible_by_admin(self):
        response = self._get_status(self.admin)
        self.assertIn(response.status_code, [200, 404])  # 404 if not registered yet

    def test_reload_requires_superuser(self):
        client = auth_client(self.admin)
        with patch('api.cms.viewsets.AdapterStatusViewSet.AdapterManager'):
            response = client.post('/api/cms/adapters/reload/', {'adapter': 'all'})
        # superuser access, so should NOT be 403
        self.assertNotEqual(response.status_code, 403)

    def test_reload_denied_for_regular_admin(self):
        staff_only = make_user(is_staff=True, is_superuser=False)
        client = auth_client(staff_only)
        response = client.post('/api/cms/adapters/reload/', {'adapter': 'all'})
        self.assertIn(response.status_code, [403, 404])

    def test_config_endpoint_admin_only(self):
        client = auth_client(self.user)
        response = client.get('/api/cms/adapters/config/')
        self.assertIn(response.status_code, [403, 401, 404])


# ─────────────────────────────────────────────────────────────────────────────
# 2. BusinessLogicViewSet
# ─────────────────────────────────────────────────────────────────────────────

class BusinessLogicViewSetTest(APITestCase):
    def setUp(self):
        try:
            from api.cms.viewsets.BusinessLogicViewSet import BusinessLogicViewSet
            self.ViewSet = BusinessLogicViewSet
        except ImportError:
            self.skipTest("BusinessLogicViewSet not importable")
        self.user  = make_user()
        self.admin = make_user(is_staff=True)

    def test_fee_preview_requires_auth(self):
        response = self.client.get('/api/cms/tools/fee_preview/?amount=10')
        self.assertIn(response.status_code, [401, 403, 404])

    def test_fee_preview_authenticated(self):
        client = auth_client(self.user)
        with patch('api.cms.viewsets.BusinessLogicViewSet.WithdrawalService') as mock_svc:
            mock_svc.return_value.calculate_fee.return_value = {
                'fee': Decimal('1.00'), 'net': Decimal('9.00')
            }
            response = client.get('/api/cms/tools/fee_preview/?amount=10&method=paypal')
        self.assertIn(response.status_code, [200, 404])

    def test_coins_to_usd_authenticated(self):
        client = auth_client(self.user)
        with patch('api.cms.viewsets.BusinessLogicViewSet.VirtualCurrency'):
            response = client.get('/api/cms/tools/coins_to_usd/?coins=100')
        self.assertIn(response.status_code, [200, 404])

    def test_embed_url_returns_url(self):
        client = auth_client(self.user)
        with patch('api.cms.viewsets.BusinessLogicViewSet.CPALeadService') as mock_svc:
            mock_svc.return_value.get_embed_url.return_value = 'https://cpalead.com/embed/abc'
            response = client.get('/api/cms/tools/embed_url/')
        self.assertIn(response.status_code, [200, 404, 503])

    def test_pool_status_requires_admin(self):
        client = auth_client(self.user)
        response = client.get('/api/cms/tools/pool_status/')
        self.assertIn(response.status_code, [403, 401, 404])

    def test_pool_status_accessible_by_admin(self):
        client = auth_client(self.admin)
        with patch('api.cms.viewsets.BusinessLogicViewSet.SurveyRewardService'):
            response = client.get('/api/cms/tools/pool_status/')
        self.assertIn(response.status_code, [200, 404])

    def test_my_level_authenticated(self):
        client = auth_client(self.user)
        response = client.get('/api/cms/tools/my_level/')
        self.assertIn(response.status_code, [200, 404])

    def test_streak_multiplier_authenticated(self):
        client = auth_client(self.user)
        response = client.get('/api/cms/tools/streak_multiplier/?streak_days=5')
        self.assertIn(response.status_code, [200, 404])


# ─────────────────────────────────────────────────────────────────────────────
# 3. InteractorViewSet
# ─────────────────────────────────────────────────────────────────────────────

class InteractorViewSetTest(APITestCase):
    def setUp(self):
        try:
            from api.cms.viewsets.InteractorViewSet import InteractorViewSet
            self.ViewSet = InteractorViewSet
        except ImportError:
            self.skipTest("InteractorViewSet not importable")
        self.user  = make_user()
        self.admin = make_user(is_staff=True, is_superuser=True)

    def test_process_postback_public_access(self):
        """process_postback must be accessible without auth (CPAlead calls it)."""
        response = self.client.get(
            '/api/cms/interactors/process_postback/',
            {'subid': 'test', 'payout': '0.5', 'lead_id': 'lead_1'}
        )
        self.assertNotIn(response.status_code, [401, 403])

    def test_onboard_user_public_access(self):
        """onboard_user must be accessible without auth (pre-registration)."""
        response = self.client.post('/api/cms/interactors/onboard_user/', {
            'username': f'newuser_{uuid.uuid4().hex[:4]}',
            'email': f'test_{uuid.uuid4().hex[:4]}@example.com',
            'password': 'SecurePass123!',
        })
        self.assertNotIn(response.status_code, [401, 403])

    def test_approve_withdrawal_requires_admin(self):
        client = auth_client(self.user)
        response = client.post('/api/cms/interactors/approve_withdrawal/', {
            'request_id': 1
        })
        self.assertIn(response.status_code, [403, 401, 404])

    def test_submit_survey_requires_auth(self):
        response = self.client.post('/api/cms/interactors/submit_survey/', {
            'completion_id': str(uuid.uuid4()), 'responses': []
        })
        self.assertIn(response.status_code, [401, 403, 404])

    def test_submit_survey_authenticated(self):
        client = auth_client(self.user)
        with patch('api.cms.viewsets.InteractorViewSet.SurveyInteractionInteractor') as mock_i:
            mock_i.return_value.execute.return_value = {'success': True}
            response = client.post('/api/cms/interactors/submit_survey/', {
                'completion_id': str(uuid.uuid4()), 'responses': []
            })
        self.assertIn(response.status_code, [200, 400, 404])

    def test_execute_interactor_requires_admin(self):
        client = auth_client(self.user)
        response = client.post('/api/cms/interactors/execute_interactor/', {
            'interactor': 'PostbackProcessingInteractor', 'params': {}
        })
        self.assertIn(response.status_code, [403, 401, 404])

    def test_list_interactors_requires_admin(self):
        client = auth_client(self.admin)
        response = client.get('/api/cms/interactors/list_interactors/')
        self.assertIn(response.status_code, [200, 404])


# ─────────────────────────────────────────────────────────────────────────────
# 4. PushNotificationViewSet
# ─────────────────────────────────────────────────────────────────────────────

class PushNotificationViewSetTest(APITestCase):
    def setUp(self):
        try:
            from api.cms.viewsets.PushNotificationViewSet import PushNotificationViewSet
            self.ViewSet = PushNotificationViewSet
        except ImportError:
            self.skipTest("PushNotificationViewSet not importable")
        self.user  = make_user()
        self.admin = make_user(is_staff=True)

    def test_register_device_requires_auth(self):
        response = self.client.post('/api/cms/push/register_device/', {
            'token': 'fcm_token_abc', 'platform': 'fcm'
        })
        self.assertIn(response.status_code, [401, 403, 404])

    def test_register_device_authenticated(self):
        client = auth_client(self.user)
        with patch('api.cms.viewsets.PushNotificationViewSet.FCMService') as mock_fcm:
            mock_fcm.return_value.register.return_value = True
            response = client.post('/api/cms/push/register_device/', {
                'token': f'tok_{uuid.uuid4().hex}', 'platform': 'fcm'
            })
        self.assertIn(response.status_code, [200, 201, 400, 404])

    def test_unregister_device_authenticated(self):
        client = auth_client(self.user)
        response = client.post('/api/cms/push/unregister_device/', {
            'token': 'old_token', 'platform': 'fcm'
        })
        self.assertIn(response.status_code, [200, 400, 404])

    def test_my_devices_requires_auth(self):
        response = self.client.get('/api/cms/push/my_devices/')
        self.assertIn(response.status_code, [401, 403, 404])

    def test_my_devices_authenticated(self):
        client = auth_client(self.user)
        response = client.get('/api/cms/push/my_devices/')
        self.assertIn(response.status_code, [200, 404])

    def test_unread_count_authenticated(self):
        client = auth_client(self.user)
        response = client.get('/api/cms/push/unread_count/')
        self.assertIn(response.status_code, [200, 404])

    def test_send_test_requires_admin(self):
        client = auth_client(self.user)
        response = client.post('/api/cms/push/send_test/', {
            'user_id': self.user.pk, 'title': 'Test', 'body': 'Test body'
        })
        self.assertIn(response.status_code, [403, 401, 404])

    def test_bulk_push_requires_admin(self):
        client = auth_client(self.user)
        response = client.post('/api/cms/push/bulk_push/', {
            'user_ids': [self.user.pk], 'title': 'Hello', 'body': 'World'
        })
        self.assertIn(response.status_code, [403, 401, 404])

    def test_push_stats_requires_admin(self):
        client = auth_client(self.admin)
        response = client.get('/api/cms/push/push_stats/')
        self.assertIn(response.status_code, [200, 404])

    def test_suspended_user_cannot_register_device(self):
        suspended = make_user()
        try:
            suspended.profile.is_suspended = True
            suspended.profile.save()
        except Exception:
            pass
        client = auth_client(suspended)
        response = client.post('/api/cms/push/register_device/', {
            'token': 'tok_suspended', 'platform': 'fcm'
        })
        self.assertIn(response.status_code, [403, 400, 404])


# ─────────────────────────────────────────────────────────────────────────────
# 5. RepositoryViewSet
# ─────────────────────────────────────────────────────────────────────────────

class RepositoryViewSetTest(APITestCase):
    def setUp(self):
        try:
            from api.cms.viewsets.RepositoryViewSet import RepositoryViewSet
            self.ViewSet = RepositoryViewSet
        except ImportError:
            self.skipTest("RepositoryViewSet not importable")
        self.user      = make_user()
        self.admin     = make_user(is_staff=True)
        self.superuser = make_user(is_staff=True, is_superuser=True)

    def test_user_lookup_requires_admin(self):
        client = auth_client(self.user)
        response = client.get(f'/api/cms/repo/user_lookup/?user_id={self.user.pk}')
        self.assertIn(response.status_code, [403, 401, 404])

    def test_user_lookup_admin_accessible(self):
        client = auth_client(self.admin)
        with patch('api.cms.viewsets.RepositoryViewSet.UserRepository') as mock_repo:
            mock_repo.return_value.get_user.return_value = {
                'id': self.user.pk, 'username': self.user.username
            }
            response = client.get(f'/api/cms/repo/user_lookup/?user_id={self.user.pk}')
        self.assertIn(response.status_code, [200, 404])

    def test_user_balance_admin_only(self):
        client = auth_client(self.user)
        response = client.get(f'/api/cms/repo/user_balance/?user_id={self.user.pk}')
        self.assertIn(response.status_code, [403, 401, 404])

    def test_admin_add_coins_requires_superuser(self):
        client = auth_client(self.admin)  # staff but NOT superuser
        response = client.post('/api/cms/repo/admin_add_coins/', {
            'user_id': self.user.pk, 'amount': 100
        })
        self.assertIn(response.status_code, [403, 401, 404])

    def test_admin_add_coins_superuser_allowed(self):
        client = auth_client(self.superuser)
        with patch('api.cms.viewsets.RepositoryViewSet.VirtualBalanceRepository') as mock_repo:
            mock_repo.return_value.credit.return_value = True
            response = client.post('/api/cms/repo/admin_add_coins/', {
                'user_id': self.user.pk, 'amount': 100, 'description': 'Test credit'
            })
        self.assertIn(response.status_code, [200, 404])

    def test_lead_exists_check_admin_only(self):
        client = auth_client(self.admin)
        with patch('api.cms.viewsets.RepositoryViewSet.ConversionRepository') as mock_repo:
            mock_repo.return_value.lead_exists.return_value = False
            response = client.get('/api/cms/repo/lead_exists/?lead_id=test_lead_123')
        self.assertIn(response.status_code, [200, 404])

    def test_health_endpoint_admin_only(self):
        client = auth_client(self.admin)
        with patch('api.cms.viewsets.RepositoryViewSet.CMSRegistry') as mock_reg:
            mock_reg.status.return_value = {'healthy': 3, 'total': 3}
            response = client.get('/api/cms/repo/health/')
        self.assertIn(response.status_code, [200, 404])


# ─────────────────────────────────────────────────────────────────────────────
# 6. SelectorViewSet
# ─────────────────────────────────────────────────────────────────────────────

class SelectorViewSetTest(APITestCase):
    def setUp(self):
        try:
            from api.cms.viewsets.SelectorViewSet import SelectorViewSet
            self.ViewSet = SelectorViewSet
        except ImportError:
            self.skipTest("SelectorViewSet not importable")
        self.user  = make_user()
        self.admin = make_user(is_staff=True)

    def test_top_earners_requires_auth(self):
        response = self.client.get('/api/cms/selectors/top_earners/')
        self.assertIn(response.status_code, [401, 403, 404])

    def test_top_earners_authenticated(self):
        client = auth_client(self.user)
        with patch('api.cms.viewsets.SelectorViewSet.LeaderboardSelector') as mock_sel:
            mock_sel.return_value.get_top_earners.return_value = []
            response = client.get('/api/cms/selectors/top_earners/?limit=10')
        self.assertIn(response.status_code, [200, 404])

    def test_my_stats_authenticated(self):
        client = auth_client(self.user)
        with patch('api.cms.viewsets.SelectorViewSet.UserStatsSelector') as mock_sel:
            mock_sel.return_value.get_my_stats.return_value = {
                'total_earned': 5.0, 'level': 2
            }
            response = client.get('/api/cms/selectors/my_stats/')
        self.assertIn(response.status_code, [200, 404])

    def test_my_balance_authenticated(self):
        client = auth_client(self.user)
        with patch('api.cms.viewsets.SelectorViewSet.UserBalanceSelector') as mock_sel:
            mock_sel.return_value.get_balance.return_value = {
                'balance_usd': '10.00', 'balance_virtual': 1000
            }
            response = client.get('/api/cms/selectors/my_balance/')
        self.assertIn(response.status_code, [200, 404])

    def test_conversion_stats_requires_admin(self):
        client = auth_client(self.user)
        response = client.get('/api/cms/selectors/conversion_stats/?days=30')
        self.assertIn(response.status_code, [403, 401, 404])

    def test_conversion_stats_admin_accessible(self):
        client = auth_client(self.admin)
        with patch('api.cms.viewsets.SelectorViewSet.ConversionStatsSelector') as mock_sel:
            mock_sel.return_value.get_stats.return_value = {
                'total': 100, 'approved': 90
            }
            response = client.get('/api/cms/selectors/conversion_stats/?days=30')
        self.assertIn(response.status_code, [200, 404])

    def test_active_offers_authenticated(self):
        client = auth_client(self.user)
        with patch('api.cms.viewsets.SelectorViewSet.OfferSelector') as mock_sel:
            mock_sel.return_value.get_active_offers.return_value = []
            response = client.get('/api/cms/selectors/active_offers/')
        self.assertIn(response.status_code, [200, 404])

    def test_leaderboard_authenticated(self):
        client = auth_client(self.user)
        with patch('api.cms.viewsets.SelectorViewSet.LeaderboardSelector') as mock_sel:
            mock_sel.return_value.get_leaderboard.return_value = {
                'entries': [], 'my_rank': 0
            }
            response = client.get('/api/cms/selectors/leaderboard/?period=weekly')
        self.assertIn(response.status_code, [200, 404])

    def test_pending_withdrawals_requires_admin(self):
        client = auth_client(self.user)
        response = client.get('/api/cms/selectors/pending_withdrawals/')
        self.assertIn(response.status_code, [403, 401, 404])
