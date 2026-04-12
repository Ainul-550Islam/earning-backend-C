import socket
import secrets
import logging
from django.utils import timezone
from ...models.publisher import PublisherDomain
from ...choices import DomainVerificationStatus
from ...exceptions import DomainVerificationFailed
from ...constants import DOMAIN_DNS_TXT_PREFIX, DOMAIN_VERIFY_TIMEOUT_SECONDS

logger = logging.getLogger('smartlink.domain')


class DomainService:
    """
    Custom domain verification and SSL status management.
    Publishers verify ownership via DNS TXT record.
    """

    def initiate_verification(self, publisher, domain: str) -> PublisherDomain:
        """
        Start domain verification process.
        Generates a unique token the publisher must add as a DNS TXT record.
        """
        token = secrets.token_urlsafe(32)
        domain_obj, created = PublisherDomain.objects.get_or_create(
            publisher=publisher,
            domain=domain,
            defaults={
                'verification_token': token,
                'verification_status': DomainVerificationStatus.PENDING,
            }
        )
        if not created:
            # Regenerate token on re-initiation
            domain_obj.verification_token = token
            domain_obj.verification_status = DomainVerificationStatus.PENDING
            domain_obj.verified_at = None
            domain_obj.save(update_fields=['verification_token', 'verification_status', 'verified_at', 'updated_at'])

        logger.info(f"Domain verification initiated: {domain} for publisher#{publisher.pk}")
        return domain_obj

    def verify(self, domain_obj: PublisherDomain) -> bool:
        """
        Check DNS TXT record to verify domain ownership.
        Returns True if verified, raises DomainVerificationFailed otherwise.
        """
        expected_record = domain_obj.dns_txt_record
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain_obj.domain, 'TXT', lifetime=DOMAIN_VERIFY_TIMEOUT_SECONDS)
            for rdata in answers:
                for txt_string in rdata.strings:
                    record = txt_string.decode('utf-8')
                    if record == expected_record:
                        self._mark_verified(domain_obj)
                        return True
        except Exception as e:
            logger.warning(f"DNS resolution failed for {domain_obj.domain}: {e}")

        domain_obj.verification_status = DomainVerificationStatus.FAILED
        domain_obj.last_checked_at = timezone.now()
        domain_obj.save(update_fields=['verification_status', 'last_checked_at', 'updated_at'])
        raise DomainVerificationFailed(
            f"TXT record not found. Add: {expected_record} to DNS for {domain_obj.domain}"
        )

    def verify_by_http(self, domain_obj: PublisherDomain) -> bool:
        """
        Alternative: verify via HTTP challenge file at /.well-known/smartlink-verify.txt
        """
        import urllib.request
        url = f"http://{domain_obj.domain}/.well-known/smartlink-verify.txt"
        try:
            with urllib.request.urlopen(url, timeout=DOMAIN_VERIFY_TIMEOUT_SECONDS) as resp:
                content = resp.read().decode('utf-8').strip()
                if content == domain_obj.verification_token:
                    self._mark_verified(domain_obj)
                    return True
        except Exception as e:
            logger.warning(f"HTTP verification failed for {domain_obj.domain}: {e}")

        raise DomainVerificationFailed(f"HTTP challenge not found at {url}")

    def check_ssl(self, domain_obj: PublisherDomain) -> dict:
        """Check SSL certificate status for a custom domain."""
        import ssl
        import datetime
        result = {'ssl_enabled': False, 'expires_at': None, 'issuer': None}

        try:
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(
                socket.socket(), server_hostname=domain_obj.domain
            ) as ssock:
                ssock.settimeout(DOMAIN_VERIFY_TIMEOUT_SECONDS)
                ssock.connect((domain_obj.domain, 443))
                cert = ssock.getpeercert()
                expire_date = datetime.datetime.strptime(
                    cert['notAfter'], '%b %d %H:%M:%S %Y %Z'
                )
                result['ssl_enabled'] = True
                result['expires_at'] = timezone.make_aware(expire_date, timezone.utc)
                result['issuer'] = dict(x[0] for x in cert.get('issuer', []))

                domain_obj.ssl_enabled = True
                domain_obj.ssl_expires_at = result['expires_at']
                domain_obj.save(update_fields=['ssl_enabled', 'ssl_expires_at', 'updated_at'])
        except Exception as e:
            logger.warning(f"SSL check failed for {domain_obj.domain}: {e}")

        return result

    def get_redirect_base_url(self, publisher) -> str:
        """
        Get the redirect base URL for a publisher.
        Uses their verified primary domain if available, otherwise platform default.
        """
        from django.conf import settings
        default_base = getattr(settings, 'SMARTLINK_BASE_URL', 'https://go.example.com')
        try:
            domain = PublisherDomain.objects.get(
                publisher=publisher,
                is_primary=True,
                verification_status=DomainVerificationStatus.VERIFIED,
                is_active=True,
            )
            protocol = 'https' if domain.ssl_enabled else 'http'
            return f"{protocol}://{domain.domain}"
        except PublisherDomain.DoesNotExist:
            return default_base

    def _mark_verified(self, domain_obj: PublisherDomain):
        """Mark domain as verified."""
        domain_obj.verification_status = DomainVerificationStatus.VERIFIED
        domain_obj.verified_at = timezone.now()
        domain_obj.last_checked_at = timezone.now()
        domain_obj.save(update_fields=[
            'verification_status', 'verified_at', 'last_checked_at', 'updated_at'
        ])
        logger.info(f"Domain verified: {domain_obj.domain}")
