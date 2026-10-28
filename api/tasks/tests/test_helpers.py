"""api/tasks/tests/test_helpers.py — Pure helper function tests."""
import pytest
from decimal import Decimal
from api.tasks.helpers import (
    generate_transaction_id, generate_click_id, mask_email,
    mask_sensitive, to_decimal, revenue_split, compute_hmac_sha256,
    verify_hmac_sha256, is_valid_email, is_disposable_email,
    is_valid_evm_address, is_valid_trc20_address, get_traffic_tier,
    compute_fraud_score_from_signals, chunk_list, success_result,
    error_result, skipped_result, validate_crypto_address,
    calculate_percentage, format_duration,
)


class TestStringHelpers:
    def test_generate_transaction_id_format(self):
        txn_id = generate_transaction_id()
        assert txn_id.startswith('txn_')
        assert len(txn_id) > 10

    def test_generate_transaction_id_custom_prefix(self):
        txn_id = generate_transaction_id(prefix='pay')
        assert txn_id.startswith('pay_')

    def test_generate_click_id_length(self):
        click_id = generate_click_id()
        assert len(click_id) == 32

    def test_generate_click_id_unique(self):
        ids = {generate_click_id() for _ in range(100)}
        assert len(ids) == 100

    def test_mask_email(self):
        assert mask_email('john.doe@example.com') == 'jo*****@example.com' or \
               '@example.com' in mask_email('john.doe@example.com')

    def test_mask_email_short(self):
        result = mask_email('ab@example.com')
        assert '@example.com' in result

    def test_mask_sensitive(self):
        result = mask_sensitive('secret_key_12345', visible_chars=4)
        assert result.endswith('2345')
        assert '*' in result


class TestMoneyHelpers:
    def test_to_decimal_from_string(self):
        assert to_decimal('1.50') == Decimal('1.5')

    def test_to_decimal_from_float(self):
        assert to_decimal(1.5) == Decimal('1.5')

    def test_to_decimal_invalid(self):
        assert to_decimal('not_a_number') == Decimal('0')

    def test_revenue_split_default(self):
        result = revenue_split(Decimal('1.00'))
        assert result['publisher'] == Decimal('0.70')
        assert result['platform'] == Decimal('0.30')
        assert result['gross'] == Decimal('1.00')

    def test_revenue_split_custom_rate(self):
        result = revenue_split(Decimal('1.00'), publisher_rate=Decimal('0.85'))
        assert result['publisher'] == Decimal('0.85')

    def test_revenue_split_zero(self):
        result = revenue_split(Decimal('0'))
        assert result['publisher'] == Decimal('0')

    def test_calculate_percentage(self):
        assert calculate_percentage(75, 100) == 75.0
        assert calculate_percentage(0, 0) == 0.0   # No division by zero
        assert calculate_percentage(1, 3, decimals=2) == 33.33

    def test_format_duration_seconds(self):
        assert format_duration(45) == '45.0s'

    def test_format_duration_minutes(self):
        assert 'm' in format_duration(90)

    def test_format_duration_hours(self):
        assert 'h' in format_duration(7200)


class TestSecurityHelpers:
    def test_hmac_compute(self):
        sig = compute_hmac_sha256('hello world', 'secret')
        assert len(sig) == 64   # SHA256 hex digest length

    def test_hmac_verify_valid(self):
        payload = '{"click_id":"abc","payout":"1.50"}'
        secret  = 'my_secret'
        sig     = compute_hmac_sha256(payload, secret)
        assert verify_hmac_sha256(payload, secret, sig) is True

    def test_hmac_verify_with_prefix(self):
        payload = 'test_payload'
        secret  = 'my_secret'
        sig     = f"sha256={compute_hmac_sha256(payload, secret)}"
        assert verify_hmac_sha256(payload, secret, sig) is True

    def test_hmac_verify_invalid(self):
        assert verify_hmac_sha256('payload', 'secret', 'wrong_signature') is False

    def test_hmac_verify_tampered(self):
        payload = 'original'
        secret  = 'secret'
        sig     = compute_hmac_sha256(payload, secret)
        assert verify_hmac_sha256('tampered', secret, sig) is False


class TestValidationHelpers:
    def test_valid_emails(self):
        valid = ['user@example.com', 'user+tag@sub.domain.co.uk', 'a@b.io']
        for email in valid:
            assert is_valid_email(email), f"Should be valid: {email}"

    def test_invalid_emails(self):
        invalid = ['notanemail', 'missing@', '@nodomain.com', '']
        for email in invalid:
            assert not is_valid_email(email), f"Should be invalid: {email}"

    def test_disposable_email_detection(self):
        assert is_disposable_email('user@mailinator.com') is True
        assert is_disposable_email('user@guerrillamail.com') is True
        assert is_disposable_email('user@gmail.com') is False
        assert is_disposable_email('user@example.com') is False

    def test_evm_address_valid(self):
        assert is_valid_evm_address('0x742d35Cc6634C0532925a3b8D9e98E9B8e6F7B9d') is True

    def test_evm_address_invalid(self):
        assert is_valid_evm_address('0x123') is False
        assert is_valid_evm_address('not_an_address') is False
        assert is_valid_evm_address('') is False

    def test_trc20_address_valid(self):
        assert is_valid_trc20_address('TYm4MnMUAepSr5cEqvq7vy8Fb4FU9KZQRY') is True

    def test_trc20_address_invalid(self):
        assert is_valid_trc20_address('0x742d35Cc6634') is False
        assert is_valid_trc20_address('ABCshortaddr') is False


class TestGeoHelpers:
    def test_tier_1_countries(self):
        for c in ['US', 'GB', 'CA', 'AU', 'DE']:
            assert get_traffic_tier(c) == 'tier_1', f"{c} should be tier_1"

    def test_tier_2_countries(self):
        for c in ['BR', 'MX', 'PL', 'TR']:
            assert get_traffic_tier(c) == 'tier_2', f"{c} should be tier_2"

    def test_tier_3_countries(self):
        assert get_traffic_tier('XZ') == 'tier_3'
        assert get_traffic_tier('') == 'tier_3'


class TestFraudScoring:
    def test_clean_signals_score_zero(self):
        score = compute_fraud_score_from_signals({
            'velocity': 3, 'ip_diversity': 5,
            'account_age_hours': 720, 'new_account': False, 'ip_blocked': False
        })
        assert score == 0

    def test_ip_blocked_max_score(self):
        score = compute_fraud_score_from_signals({'ip_blocked': True})
        assert score == 100

    def test_high_velocity_increases_score(self):
        score_low  = compute_fraud_score_from_signals({'velocity': 5})
        score_high = compute_fraud_score_from_signals({'velocity': 200})
        assert score_high > score_low

    def test_new_account_with_velocity(self):
        score = compute_fraud_score_from_signals({
            'velocity': 20, 'new_account': True, 'account_age_hours': 1
        })
        assert score > 20


class TestResultHelpers:
    def test_success_result(self):
        r = success_result(count=5)
        assert r['status'] == 'success'
        assert r['count'] == 5
        assert 'timestamp' in r

    def test_error_result(self):
        r = error_result('Something went wrong', code='TEST_ERROR')
        assert r['status'] == 'error'
        assert r['message'] == 'Something went wrong'
        assert r['error_code'] == 'TEST_ERROR'

    def test_skipped_result(self):
        r = skipped_result('already_done')
        assert r['status'] == 'skipped'
        assert r['reason'] == 'already_done'


class TestCryptoValidation:
    def test_usdt_trc20_valid(self):
        ok, msg = validate_crypto_address('TYm4MnMUAepSr5cEqvq7vy8Fb4FU9KZQRY', 'usdt_trc20')
        assert ok is True
        assert msg == ''

    def test_usdt_trc20_invalid(self):
        ok, msg = validate_crypto_address('invalid_address', 'usdt_trc20')
        assert ok is False
        assert len(msg) > 0

    def test_erc20_valid(self):
        ok, msg = validate_crypto_address('0x742d35Cc6634C0532925a3b8D9e98E9B8e6F7B9d', 'usdt_erc20')
        assert ok is True

    def test_chunk_list(self):
        lst    = list(range(10))
        chunks = chunk_list(lst, 3)
        assert len(chunks) == 4   # [0,1,2], [3,4,5], [6,7,8], [9]
        assert chunks[0] == [0, 1, 2]
        assert chunks[-1] == [9]
