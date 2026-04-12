# api/publisher_tools/site_management/site_verification.py
"""Site Verification — ads.txt, meta tag, DNS verification logic."""
import requests
import logging
from typing import Dict, Tuple
from django.utils import timezone
from core.models import TimeStampedModel
from django.db import models
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def verify_ads_txt(domain: str, publisher_id: str) -> Tuple[bool, str]:
    """ads.txt file-এ publisher_id আছে কিনা চেক করে।"""
    try:
        url = f"https://{domain}/ads.txt"
        response = requests.get(url, timeout=10, headers={'User-Agent': 'PublisherTools-Verifier/1.0'})
        if response.status_code != 200:
            return False, f"ads.txt not accessible (HTTP {response.status_code})"
        content = response.text
        if publisher_id in content:
            return True, "Publisher ID found in ads.txt"
        required_line = f"ads.publishertools.io, {publisher_id}, DIRECT"
        if required_line in content:
            return True, "Verification line found in ads.txt"
        return False, f"Publisher ID '{publisher_id}' not found in ads.txt"
    except requests.Timeout:
        return False, "Request timed out. Please try again."
    except requests.ConnectionError:
        return False, "Could not connect to the domain."
    except Exception as e:
        return False, str(e)


def verify_meta_tag(url: str, token: str) -> Tuple[bool, str]:
    """HTML meta tag verification।"""
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'PublisherTools-Verifier/1.0'})
        if response.status_code != 200:
            return False, f"Site not accessible (HTTP {response.status_code})"
        if token in response.text:
            return True, "Meta tag found on page."
        return False, f"Verification meta tag with token '{token[:8]}...' not found."
    except Exception as e:
        return False, str(e)


def verify_dns_record(domain: str, token: str) -> Tuple[bool, str]:
    """DNS TXT record verification।"""
    try:
        import dns.resolver
        expected = f"publisher-verification={token}"
        answers = dns.resolver.resolve(domain, 'TXT')
        for rdata in answers:
            for txt_string in rdata.strings:
                if expected in txt_string.decode('utf-8', errors='ignore'):
                    return True, "DNS TXT record verified."
        return False, "DNS TXT record not found."
    except Exception as e:
        return False, f"DNS lookup failed: {str(e)}"


def verify_html_file(url: str, token: str) -> Tuple[bool, str]:
    """HTML verification file check।"""
    try:
        verify_url = f"{url.rstrip('/')}/publishertools-{token}.html"
        response = requests.get(verify_url, timeout=10)
        if response.status_code == 200 and token in response.text:
            return True, "Verification file found."
        return False, "Verification file not found or content mismatch."
    except Exception as e:
        return False, str(e)


def perform_verification(site, verification) -> Dict:
    """Site verification perform করে।"""
    method = verification.method
    publisher_id = site.publisher.publisher_id
    success, message = False, "Unknown error"

    if method == 'ads_txt':
        success, message = verify_ads_txt(site.domain, publisher_id)
    elif method == 'meta_tag':
        success, message = verify_meta_tag(site.url, verification.verification_token)
    elif method == 'dns_record':
        success, message = verify_dns_record(site.domain, verification.verification_token)
    elif method == 'file':
        success, message = verify_html_file(site.url, verification.verification_token)
    elif method == 'manual':
        success, message = True, "Manually verified by admin."

    # Update verification record
    verification.attempt_count += 1
    verification.last_checked_at = timezone.now()
    if success:
        verification.status = 'verified'
        verification.verified_at = timezone.now()
        site.ads_txt_verified = (method == 'ads_txt')
        site.status = 'active'
        site.approved_at = timezone.now()
        site.save(update_fields=['ads_txt_verified', 'status', 'approved_at', 'updated_at'])
    else:
        verification.status = 'failed'
        verification.failure_reason = message
    verification.save()
    return {'success': success, 'message': message, 'method': method}
