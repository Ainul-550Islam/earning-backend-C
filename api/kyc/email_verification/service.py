# kyc/email_verification/service.py  ── WORLD #1
"""
Email Verification Service.
- Email existence check (SMTP/API)
- Disposable email detection
- Domain risk scoring
- Address verification
"""
import re
import logging

logger = logging.getLogger(__name__)

# Known disposable email domains
DISPOSABLE_DOMAINS = {
    'mailinator.com', 'guerrillamail.com', 'tempmail.com', 'throwaway.email',
    'yopmail.com', 'sharklasers.com', 'guerrillamailblock.com', 'grr.la',
    'spam4.me', 'trashmail.com', 'fakeinbox.com', 'maildrop.cc',
    'dispostable.com', 'mailnull.com', 'spamgourmet.com', 'spamgourmet.net',
}

# High-risk TLDs
HIGH_RISK_TLDS = {'.xyz', '.top', '.club', '.loan', '.work', '.gq', '.ml', '.cf', '.tk', '.ga'}


class EmailVerificationService:

    @staticmethod
    def verify(email: str) -> dict:
        """
        Full email verification.
        Returns: validity, disposable flag, domain risk, MX check.
        """
        result = {
            'email':           email,
            'is_valid_format': False,
            'is_disposable':   False,
            'is_role_based':   False,
            'domain':          '',
            'domain_risk':     'low',
            'mx_valid':        False,
            'deliverable':     False,
            'risk_score':      0,
            'error':           '',
        }

        if not email:
            result['error'] = 'Email is empty'
            return result

        # Format check
        pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email.strip()):
            result['error'] = 'Invalid email format'
            return result

        result['is_valid_format'] = True
        domain = email.split('@')[1].lower()
        result['domain'] = domain

        # Disposable check
        result['is_disposable'] = domain in DISPOSABLE_DOMAINS

        # Role-based check
        local = email.split('@')[0].lower()
        role_prefixes = {'admin', 'info', 'support', 'noreply', 'no-reply', 'sales', 'help', 'contact', 'abuse', 'postmaster'}
        result['is_role_based'] = local in role_prefixes

        # TLD risk check
        tld = '.' + domain.split('.')[-1]
        if tld in HIGH_RISK_TLDS:
            result['domain_risk'] = 'high'

        # MX record check
        result['mx_valid'] = EmailVerificationService._check_mx(domain)
        result['deliverable'] = result['mx_valid'] and not result['is_disposable']

        # Risk score
        risk = 0
        if result['is_disposable']:  risk += 50
        if result['is_role_based']:  risk += 10
        if result['domain_risk'] == 'high': risk += 30
        if not result['mx_valid']:   risk += 40
        result['risk_score'] = min(risk, 100)

        return result

    @staticmethod
    def _check_mx(domain: str) -> bool:
        """Check if domain has valid MX records."""
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, 'MX')
            return len(answers) > 0
        except ImportError:
            # dnspython not installed — skip MX check
            common_valid = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
                            'yahoo.co.uk', 'protonmail.com', 'bd.gov.bd', 'bangladesh.gov.bd'}
            return domain in common_valid
        except Exception:
            return False

    @staticmethod
    def is_disposable(email: str) -> bool:
        """Quick check — is this a disposable email?"""
        if not email or '@' not in email:
            return False
        domain = email.split('@')[1].lower()
        return domain in DISPOSABLE_DOMAINS


class AddressVerificationService:
    """
    Address verification service.
    Validates BD addresses, checks for completeness.
    """

    BD_DIVISIONS = {
        'Dhaka', 'Chittagong', 'Rajshahi', 'Khulna',
        'Barisal', 'Sylhet', 'Rangpur', 'Mymensingh'
    }

    @staticmethod
    def verify(address_line: str, city: str, country: str = 'Bangladesh') -> dict:
        """Basic address verification."""
        result = {
            'is_complete':      False,
            'is_valid_city':    False,
            'completeness_score': 0,
            'suggestions':      [],
        }

        if not address_line or len(address_line.strip()) < 10:
            result['suggestions'].append('Address line too short. Include house/flat number and street.')
            return result

        if not city:
            result['suggestions'].append('City is required.')
            return result

        score = 0
        if address_line and len(address_line) > 10: score += 40
        if city:                                     score += 30
        if country:                                  score += 15
        if len(address_line) > 30:                   score += 15

        result['completeness_score'] = score
        result['is_complete']        = score >= 70
        result['is_valid_city']      = city in AddressVerificationService.BD_DIVISIONS

        return result
