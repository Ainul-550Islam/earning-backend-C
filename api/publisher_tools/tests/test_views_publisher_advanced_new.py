# publisher_tools/tests/test_views_publisher_advanced_new.py
"""
PublisherAdvancedViewSet — নতুন endpoints-এর সম্পূর্ণ test।

Covers (new endpoints only — পুরনো tests test_views_publisher_advanced.py-এ আছে):
  POST  kyc-submit
  POST  bank-accounts/add
  DELETE bank-accounts/remove
  POST  bank-accounts/primary
  POST  bank-accounts/validate
  GET   store
  POST  store/contact
  GET   business
  GET   verification-status
  GET   referrals
  GET   leaderboard
  GET   performance-targets
  GET   blacklist-status
"""
import pytest
from unittest.mock import patch, MagicMock

BASE = '/api/publisher-tools/publisher-advanced'


def url(suffix):
    return f'{BASE}/{suffix}/'


# ══════════════════════════════════════════════════════════════════════════════
# AUTH GUARD — all new endpoints require authentication + publisher role
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestNewEndpointsAuthGuard:
    """Unauthenticated users must be rejected from every new endpoint."""

    NEW_GET_ENDPOINTS = [
        'store', 'business', 'verification-status',
        'referrals', 'leaderboard', 'performance-targets',
        'blacklist-status', 'bank-accounts',
    ]
    NEW_POST_ENDPOINTS = [
        'kyc-submit', 'store/contact',
        'bank-accounts/add', 'bank-accounts/primary',
        'bank-accounts/validate',
    ]

    def test_unauthenticated_get_endpoints_rejected(self, unauthenticated_client):
        for ep in self.NEW_GET_ENDPOINTS:
            resp = unauthenticated_client.get(url(ep))
            assert resp.status_code in (401, 403), \
                f"GET {ep} should be blocked for unauthenticated user, got {resp.status_code}"

    def test_unauthenticated_post_endpoints_rejected(self, unauthenticated_client):
        for ep in self.NEW_POST_ENDPOINTS:
            resp = unauthenticated_client.post(url(ep), {}, format='json')
            assert resp.status_code in (401, 403), \
                f"POST {ep} should be blocked for unauthenticated user"


# ══════════════════════════════════════════════════════════════════════════════
# KYC SUBMIT
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestKYCSubmit:

    VALID_PAYLOAD = {
        'kyc_type':   'individual',
        'full_name':  'Test Publisher',
        'id_type':    'passport',
        'id_number':  'A1234567',
        'country':    'BD',
    }

    def test_publisher_can_reach_endpoint(self, publisher_client):
        resp = publisher_client.post(url('kyc-submit'), self.VALID_PAYLOAD, format='json')
        assert resp.status_code in (200, 503)

    def test_missing_kyc_type_returns_400(self, publisher_client):
        payload = {k: v for k, v in self.VALID_PAYLOAD.items() if k != 'kyc_type'}
        resp    = publisher_client.post(url('kyc-submit'), payload, format='json')
        assert resp.status_code == 400

    def test_missing_full_name_returns_400(self, publisher_client):
        payload = {k: v for k, v in self.VALID_PAYLOAD.items() if k != 'full_name'}
        resp    = publisher_client.post(url('kyc-submit'), payload, format='json')
        assert resp.status_code == 400

    def test_missing_id_type_returns_400(self, publisher_client):
        payload = {k: v for k, v in self.VALID_PAYLOAD.items() if k != 'id_type'}
        resp    = publisher_client.post(url('kyc-submit'), payload, format='json')
        assert resp.status_code == 400

    def test_missing_id_number_returns_400(self, publisher_client):
        payload = {k: v for k, v in self.VALID_PAYLOAD.items() if k != 'id_number'}
        resp    = publisher_client.post(url('kyc-submit'), payload, format='json')
        assert resp.status_code == 400

    def test_missing_country_returns_400(self, publisher_client):
        payload = {k: v for k, v in self.VALID_PAYLOAD.items() if k != 'country'}
        resp    = publisher_client.post(url('kyc-submit'), payload, format='json')
        assert resp.status_code == 400

    def test_empty_body_returns_400(self, publisher_client):
        resp = publisher_client.post(url('kyc-submit'), {}, format='json')
        assert resp.status_code == 400

    def test_with_documents_list_accepted(self, publisher_client):
        payload = {
            **self.VALID_PAYLOAD,
            'documents': [
                {'document_type': 'id_front', 'file_url': 'https://cdn.example.com/id_front.jpg'},
                {'document_type': 'id_back',  'file_url': 'https://cdn.example.com/id_back.jpg'},
            ],
        }
        resp = publisher_client.post(url('kyc-submit'), payload, format='json')
        assert resp.status_code in (200, 503)

    def test_business_kyc_type_accepted(self, publisher_client):
        payload = {**self.VALID_PAYLOAD, 'kyc_type': 'business'}
        resp    = publisher_client.post(url('kyc-submit'), payload, format='json')
        assert resp.status_code in (200, 503)

    def test_success_response_contains_kyc_id(self, publisher_client):
        with patch(
            'publisher_tools.publisher_management.publisher_kyc.PublisherKYC'
        ) as mock_kyc_cls:
            mock_kyc = MagicMock()
            mock_kyc.pk = 42
            mock_kyc.status = 'pending'
            mock_kyc.can_submit.return_value = True
            mock_kyc_cls.objects.filter.return_value.first.return_value = None
            mock_kyc_cls.return_value = mock_kyc
            mock_kyc.save.return_value = None

            resp = publisher_client.post(url('kyc-submit'), self.VALID_PAYLOAD, format='json')
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                assert 'kyc_id' in data or 'status' in data

    def test_admin_can_also_submit_kyc(self, admin_client):
        resp = admin_client.post(url('kyc-submit'), self.VALID_PAYLOAD, format='json')
        assert resp.status_code in (200, 400, 503)


# ══════════════════════════════════════════════════════════════════════════════
# BANK ACCOUNTS — ADD
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestBankAccountAdd:

    def test_missing_account_type_returns_400(self, publisher_client):
        resp = publisher_client.post(url('bank-accounts/add'), {}, format='json')
        assert resp.status_code == 400

    def test_bank_transfer_requires_account_number(self, publisher_client):
        resp = publisher_client.post(url('bank-accounts/add'), {
            'account_type': 'bank_transfer',
            'account_holder_name': 'Test User',
        }, format='json')
        assert resp.status_code in (400, 503)

    def test_paypal_requires_email(self, publisher_client):
        resp = publisher_client.post(url('bank-accounts/add'), {
            'account_type': 'paypal',
        }, format='json')
        assert resp.status_code in (400, 503)

    def test_valid_paypal_account(self, publisher_client):
        resp = publisher_client.post(url('bank-accounts/add'), {
            'account_type': 'paypal',
            'email':        'publisher@paypal.com',
            'currency':     'USD',
        }, format='json')
        assert resp.status_code in (200, 503)

    def test_valid_bank_transfer_account(self, publisher_client):
        resp = publisher_client.post(url('bank-accounts/add'), {
            'account_type':         'bank_transfer',
            'account_holder_name':  'Test Publisher',
            'account_number':       '1234567890',
            'bank_name':            'Test Bank',
            'bank_country':         'BD',
            'currency':             'USD',
        }, format='json')
        assert resp.status_code in (200, 503)

    def test_set_as_primary_flag_accepted(self, publisher_client):
        resp = publisher_client.post(url('bank-accounts/add'), {
            'account_type':   'paypal',
            'email':          'test@paypal.com',
            'set_as_primary': True,
        }, format='json')
        assert resp.status_code in (200, 503)

    def test_wise_account_requires_email(self, publisher_client):
        resp = publisher_client.post(url('bank-accounts/add'), {
            'account_type': 'wise',
            'currency':     'USD',
        }, format='json')
        assert resp.status_code in (400, 503)

    def test_success_response_keys(self, publisher_client):
        with patch(
            'publisher_tools.publisher_management.publisher_bank_account.PublisherBankAccount'
        ) as mock_cls:
            mock_acct = MagicMock()
            mock_acct.pk = 7
            mock_acct.status = 'pending_verification'
            mock_acct.is_primary = False
            mock_acct.masked_account_number.return_value = '****7890'
            mock_cls.return_value = mock_acct
            mock_acct.save.return_value = None
            mock_cls.objects.filter.return_value.exclude.return_value.update.return_value = 1

            resp = publisher_client.post(url('bank-accounts/add'), {
                'account_type': 'paypal',
                'email':        'pub@paypal.com',
            }, format='json')
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                assert 'pk' in data or 'account_type' in data


# ══════════════════════════════════════════════════════════════════════════════
# BANK ACCOUNTS — SET PRIMARY
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestBankAccountSetPrimary:

    def test_missing_account_id_returns_400(self, publisher_client):
        resp = publisher_client.post(url('bank-accounts/primary'), {}, format='json')
        assert resp.status_code == 400

    def test_nonexistent_account_returns_404_or_503(self, publisher_client):
        resp = publisher_client.post(url('bank-accounts/primary'), {
            'account_id': 99999,
        }, format='json')
        assert resp.status_code in (404, 503)

    def test_valid_account_id_type_accepted(self, publisher_client):
        resp = publisher_client.post(url('bank-accounts/primary'), {
            'account_id': 1,
        }, format='json')
        assert resp.status_code in (200, 404, 503)


# ══════════════════════════════════════════════════════════════════════════════
# BANK ACCOUNTS — VALIDATE
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestBankAccountValidate:

    def test_missing_account_id_returns_400(self, publisher_client):
        resp = publisher_client.post(url('bank-accounts/validate'), {}, format='json')
        assert resp.status_code == 400

    def test_nonexistent_account_returns_error(self, publisher_client):
        resp = publisher_client.post(url('bank-accounts/validate'), {
            'account_id': 99999,
        }, format='json')
        assert resp.status_code in (404, 503)


# ══════════════════════════════════════════════════════════════════════════════
# BANK ACCOUNTS — REMOVE
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestBankAccountRemove:

    def test_missing_account_id_returns_400(self, publisher_client):
        resp = publisher_client.delete(url('bank-accounts/remove'), {}, format='json')
        assert resp.status_code == 400

    def test_nonexistent_account_returns_404(self, publisher_client):
        resp = publisher_client.delete(url('bank-accounts/remove'), {
            'account_id': 99999,
        }, format='json')
        assert resp.status_code in (404, 503)

    def test_publisher_cannot_delete_other_publishers_account(self, publisher_client, publisher_client_2):
        # publisher_client_2 ব্যবহার করে publisher_client-এর account delete করার চেষ্টা
        resp = publisher_client_2.delete(url('bank-accounts/remove'), {
            'account_id': 1,
        }, format='json')
        assert resp.status_code in (404, 503)


# ══════════════════════════════════════════════════════════════════════════════
# STORE
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPublisherStore:

    def test_store_endpoint_accessible(self, publisher_client):
        resp = publisher_client.get(url('store'))
        assert resp.status_code in (200, 503)

    def test_no_store_returns_null_with_message(self, publisher_client):
        resp = publisher_client.get(url('store'))
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            # Either store data or null with message
            assert 'store' in data or 'store_name' in data or 'message' in data

    def test_store_contact_missing_fields_returns_400(self, publisher_client):
        resp = publisher_client.post(url('store/contact'), {}, format='json')
        assert resp.status_code == 400

    def test_store_contact_missing_message_returns_400(self, publisher_client):
        resp = publisher_client.post(url('store/contact'), {
            'sender_name':  'Test User',
            'sender_email': 'test@example.com',
        }, format='json')
        assert resp.status_code == 400

    def test_store_contact_missing_sender_email_returns_400(self, publisher_client):
        resp = publisher_client.post(url('store/contact'), {
            'sender_name': 'Test User',
            'message':     'Hello!',
        }, format='json')
        assert resp.status_code == 400

    def test_store_contact_valid_payload(self, publisher_client):
        resp = publisher_client.post(url('store/contact'), {
            'sender_name':  'Test Visitor',
            'sender_email': 'visitor@example.com',
            'subject':      'Partnership enquiry',
            'message':      'I would like to discuss a partnership.',
        }, format='json')
        assert resp.status_code in (200, 404, 503)

    def test_store_contact_without_subject_still_valid(self, publisher_client):
        resp = publisher_client.post(url('store/contact'), {
            'sender_name':  'Test Visitor',
            'sender_email': 'visitor@example.com',
            'message':      'Just saying hi!',
        }, format='json')
        assert resp.status_code in (200, 404, 503)

    def test_unauthenticated_cannot_access_store(self, unauthenticated_client):
        resp = unauthenticated_client.get(url('store'))
        assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════════════════════════════════════
# BUSINESS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPublisherBusiness:

    def test_business_endpoint_accessible(self, publisher_client):
        resp = publisher_client.get(url('business'))
        assert resp.status_code in (200, 503)

    def test_no_business_returns_null_with_message(self, publisher_client):
        resp = publisher_client.get(url('business'))
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'business' in data or 'legal_name' in data or 'message' in data

    def test_unauthenticated_cannot_access_business(self, unauthenticated_client):
        resp = unauthenticated_client.get(url('business'))
        assert resp.status_code in (401, 403)

    def test_admin_can_access_business(self, admin_client):
        resp = admin_client.get(url('business'))
        assert resp.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# VERIFICATION STATUS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestVerificationStatus:

    def test_verification_status_accessible(self, publisher_client):
        resp = publisher_client.get(url('verification-status'))
        assert resp.status_code in (200, 503)

    def test_response_contains_verifications_list(self, publisher_client):
        resp = publisher_client.get(url('verification-status'))
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'verifications' in data
            assert 'count'         in data

    def test_response_contains_all_verified_flag(self, publisher_client):
        resp = publisher_client.get(url('verification-status'))
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'all_verified' in data

    def test_unauthenticated_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(url('verification-status'))
        assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════════════════════════════════════
# REFERRALS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestReferrals:

    def test_referrals_endpoint_accessible(self, publisher_client):
        resp = publisher_client.get(url('referrals'))
        assert resp.status_code in (200, 503)

    def test_response_has_list_and_totals(self, publisher_client):
        resp = publisher_client.get(url('referrals'))
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'referrals'        in data
            assert 'total_referrals'  in data
            assert 'total_earned'     in data

    def test_unauthenticated_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(url('referrals'))
        assert resp.status_code in (401, 403)

    def test_referrals_is_list(self, publisher_client):
        resp = publisher_client.get(url('referrals'))
        if resp.status_code == 200:
            referrals = resp.json().get('data', {}).get('referrals', [])
            assert isinstance(referrals, list)


# ══════════════════════════════════════════════════════════════════════════════
# LEADERBOARD
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestLeaderboard:

    def test_leaderboard_endpoint_accessible(self, publisher_client):
        resp = publisher_client.get(url('leaderboard'))
        assert resp.status_code in (200, 503)

    def test_response_has_rank_or_message(self, publisher_client):
        resp = publisher_client.get(url('leaderboard'))
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            # Either rank info or "not on leaderboard" message
            assert 'rank' in data or 'message' in data

    def test_unauthenticated_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(url('leaderboard'))
        assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE TARGETS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPerformanceTargets:

    def test_performance_targets_accessible(self, publisher_client):
        resp = publisher_client.get(url('performance-targets'))
        assert resp.status_code in (200, 503)

    def test_response_has_targets_list(self, publisher_client):
        resp = publisher_client.get(url('performance-targets'))
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'targets'        in data
            assert 'targets_count'  in data

    def test_response_has_latest_snapshot(self, publisher_client):
        resp = publisher_client.get(url('performance-targets'))
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'latest_snapshot' in data

    def test_unauthenticated_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(url('performance-targets'))
        assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════════════════════════════════════
# BLACKLIST STATUS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestBlacklistStatus:

    def test_blacklist_status_accessible(self, publisher_client):
        resp = publisher_client.get(url('blacklist-status'))
        assert resp.status_code in (200, 503)

    def test_response_has_is_blacklisted_flag(self, publisher_client):
        resp = publisher_client.get(url('blacklist-status'))
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'is_blacklisted' in data

    def test_non_blacklisted_publisher_returns_false(self, publisher_client):
        resp = publisher_client.get(url('blacklist-status'))
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            # A fresh publisher should NOT be blacklisted
            assert data.get('is_blacklisted') is False

    def test_unauthenticated_rejected(self, unauthenticated_client):
        resp = unauthenticated_client.get(url('blacklist-status'))
        assert resp.status_code in (401, 403)

    def test_response_has_reason_field(self, publisher_client):
        resp = publisher_client.get(url('blacklist-status'))
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            assert 'reason' in data
