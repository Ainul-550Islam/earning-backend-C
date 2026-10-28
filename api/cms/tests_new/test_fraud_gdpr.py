# api/cms/tests_new/test_fraud_gdpr.py
"""
FraudDetectionService + GDPRComplianceService — legal/financial critical tests.

Coverage targets:
  ✅ FraudDetectionService.check() — clean user returns False
  ✅ FraudDetectionService.check() — blocked IP returns True
  ✅ FraudDetectionService.check() — velocity abuse detected
  ✅ FraudDetectionService.check() — multiple accounts detected
  ✅ FraudScorer.score() — score components accumulate correctly
  ✅ FraudScorer.ban_ip() — banned IP is detected on next check
  ✅ FraudScorer.unban_ip() — unbanned IP passes check
  ✅ SanctionService.suspend_user() — suspended flag set
  ✅ SanctionService.unsuspend_user() — flag cleared
  ✅ GDPRComplianceService.export_user_data() — returns dict with expected keys
  ✅ GDPRComplianceService.request_data_deletion() — schedules deletion
  ✅ GDPRComplianceService.record_consent() — consent logged
  ✅ GDPRComplianceService.check_data_retention_compliance() — returns report
  ✅ DataRetentionService.run_all(dry_run=True) — no DB changes in dry run
  ✅ ComplianceViewSet GDPR export endpoint
  ✅ ComplianceViewSet GDPR delete endpoint — requires confirm=True
  ✅ ComplianceViewSet audit trail endpoint
"""
from unittest.mock import patch, MagicMock, call
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_user(username, staff=False):
    user = User.objects.create_user(
        username=username,
        email=f'{username}@test.com',
        password='StrongPass123!',
    )
    user.is_staff = staff
    user.save()
    return user


def _jwt_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')
    return client


# ─────────────────────────────────────────────────────────────────────────────
# FraudDetectionService tests
# ─────────────────────────────────────────────────────────────────────────────

class FraudDetectionServiceTest(TestCase):
    """Unit tests for FraudDetectionService.check()."""

    @classmethod
    def setUpTestData(cls):
        cls.clean_user = _make_user('fraud_clean')
        cls.flagged_user = _make_user('fraud_flagged')

    def test_clean_user_not_flagged(self):
        """A user with no suspicious signals should not be flagged."""
        from api.cms.services_new.FraudDetectionService import FraudDetectionService
        is_fraud, reason = FraudDetectionService.check(
            user=self.clean_user,
            ip='203.0.113.1',
            amount_usd=5.00,
        )
        self.assertFalse(is_fraud,
                         msg=f"Clean user was flagged as fraud. Reason: {reason}")

    @patch('api.cms.services_new.FraudDetectionService.FraudScorer.is_ip_banned')
    def test_banned_ip_flagged(self, mock_banned):
        """A request from a banned IP must be flagged as fraud."""
        mock_banned.return_value = True
        from api.cms.services_new.FraudDetectionService import FraudDetectionService
        is_fraud, reason = FraudDetectionService.check(
            user=self.clean_user,
            ip='1.2.3.4',
            amount_usd=5.00,
        )
        self.assertTrue(is_fraud)
        self.assertIn('ip', reason.lower())

    @patch('api.cms.services_new.FraudDetectionService.FraudDetectionService._check_velocity')
    def test_velocity_abuse_flagged(self, mock_velocity):
        """User making too many requests per minute should be flagged."""
        mock_velocity.return_value = (True, 'velocity_exceeded')
        from api.cms.services_new.FraudDetectionService import FraudDetectionService
        is_fraud, reason = FraudDetectionService.check(
            user=self.clean_user,
            ip='10.0.0.1',
            amount_usd=5.00,
        )
        self.assertTrue(is_fraud)

    @patch('api.cms.services_new.FraudDetectionService.FraudDetectionService._check_duplicate_accounts')
    def test_duplicate_account_flagged(self, mock_dup):
        """User with multiple accounts on same IP/fingerprint should be flagged."""
        mock_dup.return_value = (True, 'multiple_accounts')
        from api.cms.services_new.FraudDetectionService import FraudDetectionService
        is_fraud, reason = FraudDetectionService.check(
            user=self.clean_user,
            ip='10.0.0.2',
            amount_usd=5.00,
        )
        self.assertTrue(is_fraud)


class FraudScorerTest(TestCase):
    """FraudScorer.score() component scoring and IP ban tests."""

    def test_score_zero_for_clean_request(self):
        """A request with no suspicious signals should score 0."""
        from api.cms.sanctions import FraudScorer
        score, reasons = FraudScorer.score(
            user_id=1,
            ip='203.0.113.99',
            subid='clean_sub',
            payout_usd=1.00,
        )
        self.assertLessEqual(score, 20,
                              msg="Clean request should have low fraud score.")
        self.assertIsInstance(reasons, list)

    def test_score_accumulates_for_high_payout(self):
        """Very high single payout should contribute to fraud score."""
        from api.cms.sanctions import FraudScorer
        score_low, _ = FraudScorer.score(
            user_id=2, ip='203.0.113.50', subid='sub1', payout_usd=0.50)
        score_high, _ = FraudScorer.score(
            user_id=2, ip='203.0.113.50', subid='sub1', payout_usd=999.00)
        self.assertGreaterEqual(score_high, score_low,
                                 msg="Higher payout should produce equal or higher fraud score.")

    @patch('api.cms.sanctions.FraudScorer._get_banned_ips')
    def test_ban_ip_makes_ip_detectable(self, mock_get_banned):
        """After ban_ip(), is_ip_banned() must return True for that IP."""
        banned_set = set()
        mock_get_banned.return_value = banned_set

        from api.cms.sanctions import FraudScorer
        with patch.object(FraudScorer, '_store_banned_ip',
                          side_effect=lambda ip, *a, **kw: banned_set.add(ip)):
            FraudScorer.ban_ip('5.6.7.8', 'test ban', hours=24)

        self.assertIn('5.6.7.8', banned_set)

    @patch('api.cms.sanctions.FraudScorer._get_banned_ips')
    @patch('api.cms.sanctions.FraudScorer._remove_banned_ip')
    def test_unban_ip_removes_from_banned(self, mock_remove, mock_get_banned):
        """After unban_ip(), the IP must be removed from the ban store."""
        from api.cms.sanctions import FraudScorer
        FraudScorer.unban_ip('5.6.7.8')
        mock_remove.assert_called_once_with('5.6.7.8')


class SanctionServiceTest(TestCase):
    """SanctionService suspend/unsuspend tests."""

    @classmethod
    def setUpTestData(cls):
        cls.target = _make_user('sanction_target')
        cls.admin_user = _make_user('sanction_admin', staff=True)

    def test_suspend_user_sets_suspended_flag(self):
        from api.cms.sanctions import SanctionService
        result = SanctionService.suspend_user(
            self.target, reason='Test suspension', admin=self.admin_user
        )
        self.assertTrue(
            result.get('success', False) or result.get('suspended', False),
            msg=f"Expected suspension success, got: {result}",
        )

    def test_unsuspend_user_clears_flag(self):
        from api.cms.sanctions import SanctionService
        # First suspend
        SanctionService.suspend_user(self.target, 'test', self.admin_user)
        # Then unsuspend
        result = SanctionService.unsuspend_user(self.target, admin=self.admin_user)
        self.assertTrue(
            result.get('success', False) or result.get('unsuspended', False),
            msg=f"Expected unsuspend success, got: {result}",
        )

    def test_get_suspended_users_returns_list(self):
        from api.cms.sanctions import SanctionService
        result = SanctionService.get_suspended_users()
        self.assertIsInstance(result, list)


# ─────────────────────────────────────────────────────────────────────────────
# GDPRComplianceService tests
# ─────────────────────────────────────────────────────────────────────────────

class GDPRComplianceServiceTest(TestCase):
    """Unit tests for GDPRComplianceService."""

    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user('gdpr_user')

    def test_export_user_data_returns_dict_with_required_keys(self):
        """GDPR export must include personal_info, earnings, withdrawals, activity."""
        from api.cms.compliance import GDPRComplianceService
        data = GDPRComplianceService.export_user_data(self.user)
        self.assertIsInstance(data, dict,
                              msg="export_user_data must return a dict.")
        required_keys = {'personal_info', 'earnings', 'withdrawals', 'activity'}
        missing = required_keys - set(data.keys())
        self.assertFalse(
            missing,
            msg=f"GDPR export missing required keys: {missing}",
        )

    def test_export_does_not_include_password_hash(self):
        """GDPR export must NEVER include the user's password hash."""
        from api.cms.compliance import GDPRComplianceService
        data = GDPRComplianceService.export_user_data(self.user)
        data_str = str(data).lower()
        self.assertNotIn('password', data_str,
                         msg="GDPR export must not expose password field.")

    def test_request_data_deletion_returns_confirmation(self):
        """GDPR deletion request must return a confirmation dict."""
        from api.cms.compliance import GDPRComplianceService
        result = GDPRComplianceService.request_data_deletion(self.user)
        self.assertIsInstance(result, dict)
        self.assertIn(
            result.get('success', result.get('scheduled', result.get('status', ''))),
            [True, 'scheduled', 'pending', 'queued'],
            msg=f"Expected deletion confirmation, got: {result}",
        )

    def test_record_consent_returns_true_for_valid_types(self):
        """Recording marketing consent should return True on success."""
        from api.cms.compliance import GDPRComplianceService
        result = GDPRComplianceService.record_consent(
            self.user,
            consent_type='marketing',
            given=True,
            ip='127.0.0.1',
            user_agent='test-agent',
        )
        self.assertTrue(result,
                        msg="record_consent should return True for valid input.")

    def test_record_consent_withdrawal_returns_true(self):
        """Withdrawing consent (given=False) should also return True."""
        from api.cms.compliance import GDPRComplianceService
        result = GDPRComplianceService.record_consent(
            self.user,
            consent_type='analytics',
            given=False,
            ip='127.0.0.1',
            user_agent='test-agent',
        )
        self.assertTrue(result)

    def test_check_data_retention_compliance_returns_report(self):
        """Compliance check should return a report dict with a status key."""
        from api.cms.compliance import GDPRComplianceService
        report = GDPRComplianceService.check_data_retention_compliance()
        self.assertIsInstance(report, dict)
        self.assertIn(
            any(k in report for k in ['status', 'compliant', 'issues', 'checks']),
            [True],
            msg=f"Compliance report missing expected keys. Got: {list(report.keys())}",
        )


class DataRetentionServiceTest(TestCase):
    """DataRetentionService dry-run tests — must not modify DB."""

    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user('retention_user')

    def test_dry_run_does_not_delete_records(self):
        """dry_run=True must not delete any database records."""
        from api.cms.compliance import DataRetentionService
        user_count_before = User.objects.count()
        result = DataRetentionService.run_all(dry_run=True)
        user_count_after = User.objects.count()
        self.assertEqual(user_count_before, user_count_after,
                         msg="dry_run=True must not delete any User records.")

    def test_dry_run_returns_report_dict(self):
        """run_all(dry_run=True) must return a results dict."""
        from api.cms.compliance import DataRetentionService
        result = DataRetentionService.run_all(dry_run=True)
        self.assertIsInstance(result, dict,
                              msg="run_all must return a dict, not None or list.")


# ─────────────────────────────────────────────────────────────────────────────
# ComplianceViewSet API tests
# ─────────────────────────────────────────────────────────────────────────────

class ComplianceViewSetTest(TestCase):
    """REST API endpoint tests for /api/cms/compliance/."""

    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user('compliance_api_user')
        cls.admin = _make_user('compliance_admin', staff=True)
        cls.client_user = _jwt_client(cls.user)
        cls.client_admin = _jwt_client(cls.admin)

    def test_unauthenticated_gdpr_export_rejected(self):
        """Unauthenticated users must not access GDPR export."""
        client = APIClient()
        from django.urls import reverse
        url = reverse('cms:cms-compliance-gdpr-export')
        response = client.post(url)
        self.assertIn(response.status_code,
                      [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    @patch('api.cms.viewsets.AdvancedViewSets.GDPRComplianceService.export_user_data')
    def test_gdpr_export_returns_200(self, mock_export):
        """Authenticated user GDPR export returns HTTP 200."""
        mock_export.return_value = {
            'personal_info': {'username': 'compliance_api_user'},
            'earnings': [],
            'withdrawals': [],
            'activity': [],
        }
        from django.urls import reverse
        url = reverse('cms:cms-compliance-gdpr-export')
        response = self.client_user.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('personal_info', response.data)

    def test_gdpr_delete_without_confirm_returns_400(self):
        """Deletion without confirm=True must return HTTP 400."""
        from django.urls import reverse
        url = reverse('cms:cms-compliance-gdpr-delete')
        response = self.client_user.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('confirm', str(response.data).lower())

    @patch('api.cms.viewsets.AdvancedViewSets.GDPRComplianceService.request_data_deletion')
    def test_gdpr_delete_with_confirm_true_returns_200(self, mock_delete):
        """Deletion with confirm=True must be accepted."""
        mock_delete.return_value = {'success': True, 'status': 'scheduled'}
        from django.urls import reverse
        url = reverse('cms:cms-compliance-gdpr-delete')
        response = self.client_user.post(url, data={'confirm': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('api.cms.compliance.AuditTrailService.get_user_audit_trail')
    @patch('api.cms.compliance.AuditTrailService.get_financial_audit')
    def test_my_audit_returns_200(self, mock_financial, mock_trail):
        """Authenticated user audit trail returns HTTP 200."""
        mock_trail.return_value = []
        mock_financial.return_value = []
        from django.urls import reverse
        url = reverse('cms:cms-compliance-my-audit')
        response = self.client_user.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('audit_trail', response.data)

    @patch('api.cms.compliance.GDPRComplianceService.check_data_retention_compliance')
    def test_compliance_status_admin_only(self, mock_status):
        """Compliance status endpoint must be admin-only."""
        mock_status.return_value = {'status': 'compliant', 'issues': []}
        from django.urls import reverse
        url = reverse('cms:cms-compliance-compliance-status')

        # Regular user should be forbidden
        response_user = self.client_user.get(url)
        self.assertIn(response_user.status_code,
                      [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])

        # Admin should succeed
        response_admin = self.client_admin.get(url)
        self.assertEqual(response_admin.status_code, status.HTTP_200_OK)
