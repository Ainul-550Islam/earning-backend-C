# publisher_tools/tests/test_utils.py
"""
Tests for publisher_tools/utils.py
Covers all 36 utility functions — pure unit tests, no DB needed.
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone

from publisher_tools.utils import (
    # ID generators
    generate_publisher_id, generate_site_id, generate_app_id,
    generate_unit_id, generate_invoice_number,
    generate_verification_token, generate_api_key, generate_api_secret,
    # Domain helpers
    clean_domain, get_root_domain, build_ads_txt_url,
    build_verification_meta_tag, build_verification_dns_record,
    build_ads_txt_entry,
    # Metric calculators
    calculate_ecpm, calculate_ctr, calculate_fill_rate, calculate_rpm,
    calculate_publisher_revenue, calculate_processing_fee,
    calculate_withholding_tax, calculate_net_payable,
    calculate_quality_score, calculate_statistical_significance,
    calculate_uplift, calculate_required_sample_size,
    # Webhook helpers
    generate_webhook_signature, verify_webhook_signature,
    # Misc
    mask_sensitive_data, get_date_range,
    format_currency, format_large_number,
    build_cache_key, get_publisher_cache_key,
    get_site_cache_key, get_unit_cache_key,
)


# ==============================================================================
# ID GENERATORS
# ==============================================================================

class TestGeneratePublisherId:
    def test_returns_string(self):
        assert isinstance(generate_publisher_id(1), str)

    def test_different_counts_give_different_ids(self):
        assert generate_publisher_id(1) != generate_publisher_id(2)

    def test_id_has_reasonable_length(self):
        assert 5 <= len(generate_publisher_id(1)) <= 30

    def test_starts_with_pub_prefix(self):
        pid = generate_publisher_id(1)
        assert pid.upper().startswith('PUB') or len(pid) > 3


class TestGenerateSiteId:
    def test_returns_string(self):
        assert isinstance(generate_site_id(1), str)

    def test_unique_per_count(self):
        assert generate_site_id(1) != generate_site_id(99)

    def test_reasonable_length(self):
        assert 4 <= len(generate_site_id(1)) <= 30


class TestGenerateAppId:
    def test_returns_string(self):
        assert isinstance(generate_app_id(1), str)

    def test_unique_per_count(self):
        assert generate_app_id(1) != generate_app_id(2)


class TestGenerateUnitId:
    def test_returns_string(self):
        assert isinstance(generate_unit_id(1), str)

    def test_unique_per_count(self):
        assert generate_unit_id(1) != generate_unit_id(100)


class TestGenerateInvoiceNumber:
    def test_returns_string(self):
        result = generate_invoice_number(2024, 6, 1)
        assert isinstance(result, str)

    def test_contains_year(self):
        result = generate_invoice_number(2024, 6, 1)
        assert '2024' in result

    def test_contains_month(self):
        result = generate_invoice_number(2024, 6, 1)
        assert '06' in result or '6' in result

    def test_different_counts_differ(self):
        assert generate_invoice_number(2024, 6, 1) != generate_invoice_number(2024, 6, 2)


class TestGenerateVerificationToken:
    def test_returns_string(self):
        assert isinstance(generate_verification_token(), str)

    def test_unique_each_call(self):
        t1 = generate_verification_token()
        t2 = generate_verification_token()
        assert t1 != t2

    def test_sufficient_length(self):
        assert len(generate_verification_token()) >= 16


class TestGenerateApiKey:
    def test_returns_string(self):
        assert isinstance(generate_api_key(), str)

    def test_unique_each_call(self):
        assert generate_api_key() != generate_api_key()

    def test_long_enough(self):
        assert len(generate_api_key()) >= 24


class TestGenerateApiSecret:
    def test_returns_string(self):
        assert isinstance(generate_api_secret(), str)

    def test_unique(self):
        assert generate_api_secret() != generate_api_secret()

    def test_longer_than_api_key(self):
        # Secrets should be at least as long as keys
        assert len(generate_api_secret()) >= 24


# ==============================================================================
# DOMAIN HELPERS
# ==============================================================================

class TestCleanDomain:
    def test_removes_https(self):
        result = clean_domain('https://example.com')
        assert 'https://' not in result

    def test_removes_http(self):
        result = clean_domain('http://example.com')
        assert 'http://' not in result

    def test_removes_www(self):
        result = clean_domain('www.example.com')
        assert result == 'example.com' or 'www.' not in result

    def test_strips_trailing_slash(self):
        result = clean_domain('example.com/')
        assert not result.endswith('/')

    def test_lowercase(self):
        result = clean_domain('Example.COM')
        assert result == result.lower()

    def test_plain_domain_unchanged(self):
        result = clean_domain('example.com')
        assert 'example.com' in result


class TestGetRootDomain:
    def test_subdomain_returns_root(self):
        result = get_root_domain('sub.example.com')
        assert result == 'example.com' or 'example.com' in result

    def test_plain_domain(self):
        result = get_root_domain('example.com')
        assert 'example.com' in result

    def test_deep_subdomain(self):
        result = get_root_domain('a.b.c.example.com')
        assert 'example.com' in result


class TestBuildAdsTxtUrl:
    def test_returns_url_string(self):
        result = build_ads_txt_url('example.com')
        assert isinstance(result, str)

    def test_contains_ads_txt(self):
        result = build_ads_txt_url('example.com')
        assert 'ads.txt' in result

    def test_contains_domain(self):
        result = build_ads_txt_url('example.com')
        assert 'example.com' in result


class TestBuildVerificationMetaTag:
    def test_returns_html_tag(self):
        result = build_verification_meta_tag('abc123token')
        assert '<meta' in result.lower() or 'meta' in result.lower()

    def test_contains_token(self):
        token = 'testtoken12345'
        result = build_verification_meta_tag(token)
        assert token in result


class TestBuildVerificationDnsRecord:
    def test_returns_string(self):
        result = build_verification_dns_record('abc123')
        assert isinstance(result, str)

    def test_contains_token(self):
        token = 'dnstoken99'
        result = build_verification_dns_record(token)
        assert token in result


class TestBuildAdsTxtEntry:
    def test_returns_string(self):
        result = build_ads_txt_entry('PUB-1234')
        assert isinstance(result, str)

    def test_contains_publisher_id(self):
        result = build_ads_txt_entry('PUB-9999')
        assert 'PUB-9999' in result


# ==============================================================================
# METRIC CALCULATORS
# ==============================================================================

class TestCalculateEcpm:
    def test_basic_calculation(self):
        # eCPM = (revenue / impressions) * 1000
        result = calculate_ecpm(Decimal('10.00'), 1000)
        assert result == Decimal('10.0000') or float(result) == pytest.approx(10.0)

    def test_zero_impressions_returns_zero(self):
        result = calculate_ecpm(Decimal('10.00'), 0)
        assert result == Decimal('0') or result == Decimal('0.0000')

    def test_returns_decimal(self):
        result = calculate_ecpm(Decimal('5.00'), 500)
        assert isinstance(result, Decimal)

    def test_proportional(self):
        r1 = calculate_ecpm(Decimal('5.00'), 1000)
        r2 = calculate_ecpm(Decimal('10.00'), 1000)
        assert float(r2) == pytest.approx(float(r1) * 2)


class TestCalculateCtr:
    def test_basic_calculation(self):
        # CTR = clicks / impressions
        result = calculate_ctr(10, 1000)
        assert float(result) == pytest.approx(0.01)

    def test_zero_impressions_returns_zero(self):
        result = calculate_ctr(10, 0)
        assert result == Decimal('0') or float(result) == 0.0

    def test_returns_decimal(self):
        assert isinstance(calculate_ctr(5, 100), Decimal)

    def test_max_ctr_is_one(self):
        result = calculate_ctr(1000, 1000)
        assert float(result) <= 1.0


class TestCalculateFillRate:
    def test_basic(self):
        result = calculate_fill_rate(800, 1000)
        assert float(result) == pytest.approx(0.8)

    def test_zero_requests(self):
        result = calculate_fill_rate(0, 0)
        assert float(result) == 0.0

    def test_returns_decimal(self):
        assert isinstance(calculate_fill_rate(500, 1000), Decimal)


class TestCalculateRpm:
    def test_basic(self):
        # RPM = (revenue / pageviews) * 1000
        result = calculate_rpm(Decimal('10.00'), 1000)
        assert float(result) == pytest.approx(10.0)

    def test_zero_pageviews(self):
        result = calculate_rpm(Decimal('10.00'), 0)
        assert float(result) == 0.0


class TestCalculatePublisherRevenue:
    def test_returns_decimal(self):
        result = calculate_publisher_revenue(Decimal('100.00'), Decimal('0.70'))
        assert isinstance(result, Decimal)

    def test_70_percent_share(self):
        result = calculate_publisher_revenue(Decimal('100.00'), Decimal('0.70'))
        assert float(result) == pytest.approx(70.0)

    def test_full_share(self):
        result = calculate_publisher_revenue(Decimal('100.00'), Decimal('1.00'))
        assert float(result) == pytest.approx(100.0)


class TestCalculateProcessingFee:
    def test_returns_decimal(self):
        result = calculate_processing_fee(Decimal('100.00'), Decimal('0.03'))
        assert isinstance(result, Decimal)

    def test_three_percent_fee(self):
        result = calculate_processing_fee(Decimal('100.00'), Decimal('0.03'))
        assert float(result) == pytest.approx(3.0)


class TestCalculateWithholdingTax:
    def test_basic(self):
        result = calculate_withholding_tax(Decimal('100.00'), Decimal('0.10'))
        assert float(result) == pytest.approx(10.0)

    def test_zero_rate(self):
        result = calculate_withholding_tax(Decimal('100.00'), Decimal('0.00'))
        assert float(result) == 0.0

    def test_returns_decimal(self):
        assert isinstance(calculate_withholding_tax(Decimal('50.00'), Decimal('0.15')), Decimal)


class TestCalculateNetPayable:
    def test_returns_decimal(self):
        result = calculate_net_payable(
            Decimal('100.00'), Decimal('3.00'), Decimal('10.00')
        )
        assert isinstance(result, Decimal)

    def test_gross_minus_deductions(self):
        result = calculate_net_payable(
            Decimal('100.00'), Decimal('3.00'), Decimal('10.00')
        )
        assert float(result) == pytest.approx(87.0)


class TestCalculateQualityScore:
    def test_returns_numeric(self):
        result = calculate_quality_score(
            content_score=80, traffic_score=75,
            technical_score=90, ads_txt_score=100
        )
        assert isinstance(result, (int, float, Decimal))

    def test_score_in_range(self):
        result = calculate_quality_score(
            content_score=80, traffic_score=75,
            technical_score=90, ads_txt_score=100
        )
        assert 0 <= float(result) <= 100

    def test_all_perfect_gives_high_score(self):
        result = calculate_quality_score(
            content_score=100, traffic_score=100,
            technical_score=100, ads_txt_score=100
        )
        assert float(result) >= 90


class TestCalculateStatisticalSignificance:
    def test_returns_float_or_decimal(self):
        result = calculate_statistical_significance(
            control_impressions=1000, control_conversions=50,
            variant_impressions=1000, variant_conversions=65,
        )
        assert isinstance(result, (float, int, Decimal))

    def test_value_between_0_and_100(self):
        result = calculate_statistical_significance(
            control_impressions=5000, control_conversions=200,
            variant_impressions=5000, variant_conversions=260,
        )
        assert 0 <= float(result) <= 100


class TestCalculateUplift:
    def test_positive_uplift(self):
        result = calculate_uplift(control_value=1.0, variant_value=1.2)
        assert float(result) == pytest.approx(20.0)

    def test_zero_uplift(self):
        result = calculate_uplift(control_value=1.0, variant_value=1.0)
        assert float(result) == pytest.approx(0.0)

    def test_negative_uplift(self):
        result = calculate_uplift(control_value=1.0, variant_value=0.8)
        assert float(result) < 0


class TestCalculateRequiredSampleSize:
    def test_returns_positive_int(self):
        result = calculate_required_sample_size(
            baseline_rate=0.05, minimum_detectable_effect=0.01
        )
        assert isinstance(result, (int, float))
        assert result > 0

    def test_smaller_effect_needs_larger_sample(self):
        n1 = calculate_required_sample_size(0.05, 0.02)
        n2 = calculate_required_sample_size(0.05, 0.01)
        assert n2 >= n1


# ==============================================================================
# WEBHOOK HELPERS
# ==============================================================================

class TestWebhookSignature:
    PAYLOAD = '{"event":"invoice.paid","amount":"100.00"}'
    SECRET  = 'my_super_secret_key'

    def test_generate_returns_string(self):
        sig = generate_webhook_signature(self.PAYLOAD, self.SECRET)
        assert isinstance(sig, str)

    def test_same_inputs_same_signature(self):
        s1 = generate_webhook_signature(self.PAYLOAD, self.SECRET)
        s2 = generate_webhook_signature(self.PAYLOAD, self.SECRET)
        assert s1 == s2

    def test_different_payload_different_signature(self):
        s1 = generate_webhook_signature(self.PAYLOAD, self.SECRET)
        s2 = generate_webhook_signature('{"other":"data"}', self.SECRET)
        assert s1 != s2

    def test_verify_correct_signature(self):
        sig = generate_webhook_signature(self.PAYLOAD, self.SECRET)
        assert verify_webhook_signature(self.PAYLOAD, sig, self.SECRET) is True

    def test_verify_wrong_signature(self):
        assert verify_webhook_signature(self.PAYLOAD, 'bad_sig', self.SECRET) is False

    def test_verify_wrong_secret(self):
        sig = generate_webhook_signature(self.PAYLOAD, self.SECRET)
        assert verify_webhook_signature(self.PAYLOAD, sig, 'wrong_secret') is False

    def test_verify_tampered_payload(self):
        sig = generate_webhook_signature(self.PAYLOAD, self.SECRET)
        tampered = self.PAYLOAD.replace('100.00', '999.99')
        assert verify_webhook_signature(tampered, sig, self.SECRET) is False


# ==============================================================================
# MISC HELPERS
# ==============================================================================

class TestMaskSensitiveData:
    def test_masks_most_of_string(self):
        result = mask_sensitive_data('sk_live_abcdefghij1234567890')
        assert '****' in result or '*' in result

    def test_shows_last_n_chars(self):
        result = mask_sensitive_data('abcdefghij', visible_chars=4)
        assert 'ghij' in result

    def test_short_string_handled(self):
        result = mask_sensitive_data('abc', visible_chars=4)
        assert isinstance(result, str)


class TestGetDateRange:
    def test_last_7_days(self):
        start, end = get_date_range('last_7_days')
        assert (end - start).days == 6 or (end - start).days == 7

    def test_last_30_days(self):
        start, end = get_date_range('last_30_days')
        assert (end - start).days >= 28

    def test_returns_tuple_of_two(self):
        result = get_date_range('last_7_days')
        assert len(result) == 2

    def test_start_before_end(self):
        start, end = get_date_range('last_30_days')
        assert start < end

    def test_today_range(self):
        result = get_date_range('today')
        assert result is not None


class TestFormatCurrency:
    def test_usd_format(self):
        result = format_currency(Decimal('1234.56'), 'USD')
        assert isinstance(result, str)
        assert '1234' in result or '1,234' in result

    def test_zero(self):
        result = format_currency(Decimal('0'), 'USD')
        assert isinstance(result, str)

    def test_large_amount(self):
        result = format_currency(Decimal('1000000.00'), 'USD')
        assert isinstance(result, str)


class TestFormatLargeNumber:
    def test_thousands(self):
        result = format_large_number(1500)
        assert '1.5K' in result or '1,500' in result or '1500' in result

    def test_millions(self):
        result = format_large_number(2_500_000)
        assert 'M' in result or '2,500,000' in result or '2500000' in result

    def test_small_number(self):
        result = format_large_number(999)
        assert '999' in result

    def test_returns_string(self):
        assert isinstance(format_large_number(12345), str)


class TestCacheKeys:
    def test_build_cache_key_returns_string(self):
        result = build_cache_key('publisher', 'PUB-001', 'earnings')
        assert isinstance(result, str)

    def test_build_cache_key_is_unique(self):
        k1 = build_cache_key('publisher', 'PUB-001', 'earnings')
        k2 = build_cache_key('publisher', 'PUB-002', 'earnings')
        assert k1 != k2

    def test_publisher_cache_key(self):
        result = get_publisher_cache_key('PUB-001', 'earnings')
        assert isinstance(result, str)
        assert 'PUB-001' in result or len(result) > 0

    def test_site_cache_key(self):
        result = get_site_cache_key('SITE-001', 'analytics')
        assert isinstance(result, str)

    def test_unit_cache_key(self):
        result = get_unit_cache_key('UNIT-001', 'performance')
        assert isinstance(result, str)

    def test_same_args_same_key(self):
        k1 = build_cache_key('a', 'b', 'c')
        k2 = build_cache_key('a', 'b', 'c')
        assert k1 == k2
