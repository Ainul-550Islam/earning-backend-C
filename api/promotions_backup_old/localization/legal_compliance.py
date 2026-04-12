# =============================================================================
# api/promotions/localization/legal_compliance.py
# Legal Compliance — GDPR, COPPA, local ad regulations, age verification
# Country-specific legal requirements enforce করে
# =============================================================================

import logging
from dataclasses import dataclass, field
from typing import Optional
from django.core.cache import cache

logger = logging.getLogger('localization.legal')
CACHE_PREFIX_LEGAL = 'loc:legal:{}'


@dataclass
class ComplianceCheck:
    is_compliant:   bool
    violations:     list
    warnings:       list
    required_actions: list
    jurisdiction:   str


@dataclass
class ConsentRecord:
    user_id:        int
    consent_type:   str         # gdpr_data, marketing, cookies, age_verification
    granted:        bool
    ip_address:     str
    user_agent:     str
    timestamp:      float
    jurisdiction:   str


# Country compliance rules
COMPLIANCE_RULES = {
    'EU': {
        'gdpr_required':         True,
        'cookie_consent':        True,
        'data_retention_days':   730,    # 2 years max
        'right_to_forget':       True,
        'min_age':               16,
        'countries': ['DE', 'FR', 'IT', 'ES', 'NL', 'BE', 'PL', 'SE', 'DK', 'FI'],
    },
    'US': {
        'coppa_required':        True,   # Under 13
        'ccpa_required':         True,   # California
        'min_age':               13,
        'countries': ['US'],
    },
    'BD': {
        'local_ad_standards':    True,
        'min_age':               18,
        'prohibited_categories': ['gambling', 'alcohol', 'adult'],
        'countries': ['BD'],
    },
    'IN': {
        'it_act_compliance':     True,
        'min_age':               18,
        'countries': ['IN'],
    },
    'DEFAULT': {
        'min_age': 13,
        'data_retention_days': 365,
    },
}


class LegalComplianceManager:
    """
    Legal compliance enforcement।

    Covers:
    1. GDPR (EU) — data consent, right to forget, data portability
    2. COPPA (US) — under-13 protection
    3. CCPA (California) — opt-out rights
    4. Local ad regulations — Bangladesh, India, Pakistan
    5. Age verification
    6. Prohibited content by jurisdiction
    """

    def check_campaign_compliance(
        self,
        campaign_id:  int,
        target_countries: list,
    ) -> ComplianceCheck:
        """Campaign দেওয়া countries তে legal কিনা check করে।"""
        violations = []
        warnings   = []
        actions    = []

        try:
            from api.promotions.models import Campaign
            campaign = Campaign.objects.select_related('category').get(pk=campaign_id)
            category = campaign.category.name.lower() if campaign.category else ''

            for country in target_countries:
                rules = self._get_rules_for_country(country)

                # Prohibited categories
                prohibited = rules.get('prohibited_categories', [])
                if category in prohibited:
                    violations.append(f'{category}_prohibited_in_{country}')

                # Age restrictions — needs targeting check
                min_age = rules.get('min_age', 13)
                if min_age >= 18:
                    actions.append(f'age_verification_required_for_{country}')

                # GDPR
                if rules.get('gdpr_required'):
                    actions.append('gdpr_consent_required')
                    actions.append('privacy_policy_link_required')

        except Exception as e:
            logger.error(f'Compliance check failed: {e}')
            warnings.append('compliance_check_partial')

        return ComplianceCheck(
            is_compliant  = len(violations) == 0,
            violations    = violations,
            warnings      = warnings,
            required_actions = list(set(actions)),
            jurisdiction  = ','.join(target_countries),
        )

    def record_consent(
        self,
        user_id:      int,
        consent_type: str,
        granted:      bool,
        ip_address:   str,
        user_agent:   str,
        country:      str,
    ) -> ConsentRecord:
        """GDPR consent record করে।"""
        import time
        record = ConsentRecord(
            user_id=user_id, consent_type=consent_type, granted=granted,
            ip_address=ip_address, user_agent=user_agent,
            timestamp=time.time(), jurisdiction=country,
        )
        # Database তে save করো
        self._save_consent(record)
        # Cache
        cache_key = CACHE_PREFIX_LEGAL.format(f'consent:{user_id}:{consent_type}')
        cache.set(cache_key, granted, timeout=86400)
        return record

    def has_consent(self, user_id: int, consent_type: str) -> bool:
        """User এর consent আছে কিনা।"""
        cache_key = CACHE_PREFIX_LEGAL.format(f'consent:{user_id}:{consent_type}')
        cached    = cache.get(cache_key)
        if cached is not None:
            return bool(cached)

        try:
            from api.promotions.models import UserConsent
            return UserConsent.objects.filter(
                user_id=user_id, consent_type=consent_type, granted=True
            ).exists()
        except Exception:
            return False

    def process_gdpr_deletion(self, user_id: int) -> dict:
        """
        GDPR Right to Erasure — user data anonymize করে।
        Hard delete করা যাবে না (audit trail রাখতে হয়)।
        """
        from api.promotions.models import TaskSubmission, PromotionTransaction, UserReputation
        from django.contrib.auth import get_user_model
        User = get_user_model()

        actions_taken = []

        try:
            user = User.objects.get(pk=user_id)
            # PII anonymize
            user.email      = f'deleted_{user_id}@deleted.invalid'
            user.first_name = 'Deleted'
            user.last_name  = 'User'
            user.save(update_fields=['email', 'first_name', 'last_name'])
            actions_taken.append('pii_anonymized')
        except User.DoesNotExist:
            pass

        # IP addresses anonymize
        TaskSubmission.objects.filter(worker_id=user_id).update(
            ip_address='0.0.0.0',
            device_fingerprint='deleted',
        )
        actions_taken.append('submission_pii_cleared')

        logger.info(f'GDPR deletion: user={user_id}, actions={actions_taken}')
        return {'user_id': user_id, 'actions': actions_taken, 'status': 'completed'}

    def get_age_restriction(self, country: str) -> int:
        """Country তে minimum age return করে।"""
        rules = self._get_rules_for_country(country)
        return rules.get('min_age', 13)

    def is_allowed_content(self, category: str, country: str) -> tuple[bool, str]:
        """Content country তে allowed কিনা।"""
        rules      = self._get_rules_for_country(country)
        prohibited = rules.get('prohibited_categories', [])
        if category.lower() in prohibited:
            return False, f'{category} is prohibited in {country}'
        return True, 'allowed'

    def _get_rules_for_country(self, country: str) -> dict:
        for jurisdiction, rules in COMPLIANCE_RULES.items():
            if jurisdiction == 'DEFAULT':
                continue
            if country.upper() in rules.get('countries', []):
                return {**COMPLIANCE_RULES['DEFAULT'], **rules}
        return COMPLIANCE_RULES['DEFAULT']

    def _save_consent(self, record: ConsentRecord) -> None:
        try:
            from api.promotions.models import UserConsent
            from django.utils import timezone
            UserConsent.objects.update_or_create(
                user_id=record.user_id, consent_type=record.consent_type,
                defaults={
                    'granted': record.granted, 'ip_address': record.ip_address,
                    'user_agent': record.user_agent[:500], 'jurisdiction': record.jurisdiction,
                    'consented_at': timezone.now(),
                },
            )
        except Exception as e:
            logger.error(f'Consent save failed: {e}')
