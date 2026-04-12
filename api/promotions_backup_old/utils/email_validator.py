# api/promotions/utils/email_validator.py
import re, logging
from django.core.cache import cache
logger = logging.getLogger('utils.email')

DISPOSABLE_DOMAINS = {'mailinator.com','guerrillamail.com','temp-mail.org','throwaway.email',
                      'yopmail.com','sharklasers.com','guerrillamailblock.com','10minutemail.com',
                      'trashmail.com','tempmail.com','fakeinbox.com','dispostable.com'}

class EmailValidator:
    def validate(self, email: str) -> dict:
        email = email.strip().lower()
        result = {'email': email, 'valid': False, 'disposable': False, 'reason': ''}

        if not re.match(r'^[\w\.\+\-]+@[\w\-]+\.[\w\.]{2,}$', email):
            return {**result, 'reason': 'invalid_format'}

        domain = email.split('@')[1]
        if domain in DISPOSABLE_DOMAINS:
            return {**result, 'disposable': True, 'reason': 'disposable_domain'}

        # Basic MX check
        if not self._has_mx(domain):
            return {**result, 'reason': 'no_mx_record'}

        return {**result, 'valid': True}

    def is_disposable(self, email: str) -> bool:
        domain = email.strip().lower().split('@')[-1] if '@' in email else ''
        return domain in DISPOSABLE_DOMAINS

    def _has_mx(self, domain: str) -> bool:
        ck = f'mx:{domain}'
        if cache.get(ck) is not None: return cache.get(ck)
        try:
            import dns.resolver
            dns.resolver.resolve(domain, 'MX')
            cache.set(ck, True, timeout=86400)
            return True
        except Exception:
            cache.set(ck, False, timeout=3600)
            return False
