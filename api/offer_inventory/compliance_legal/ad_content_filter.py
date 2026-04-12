# api/offer_inventory/compliance_legal/ad_content_filter.py
"""Ad Content Filter — Validate offer content against platform policies."""
import logging
import re

logger = logging.getLogger(__name__)

PROHIBITED_KEYWORDS = [
    'guaranteed income', 'get rich quick', 'no risk',
    'unlimited earnings', 'work from home scam', 'pyramid',
    'ponzi', 'investment returns', 'binary options',
    'adult content', 'weapons', 'drugs', 'tobacco',
]

REQUIRED_DISCLAIMERS = [
    'results may vary',
]

MAX_PAYOUT_CLAIM   = 10000   # BDT — reject unrealistic payout claims
MIN_DESCRIPTION_LEN = 20


class AdContentFilter:
    """Validate offer content against platform advertising policies."""

    @staticmethod
    def validate_offer(offer) -> dict:
        """Full offer content validation."""
        violations = []
        warnings   = []

        title       = (offer.title or '').lower()
        description = (offer.description or '').lower()
        combined    = f'{title} {description}'

        # Prohibited keywords
        for kw in PROHIBITED_KEYWORDS:
            if kw in combined:
                violations.append(f'prohibited_keyword:{kw}')

        # Unrealistic payout
        try:
            from decimal import Decimal
            if offer.reward_amount and float(offer.reward_amount) > MAX_PAYOUT_CLAIM:
                violations.append(f'unrealistic_payout:{offer.reward_amount}')
        except Exception:
            pass

        # Short description
        if len(offer.description or '') < MIN_DESCRIPTION_LEN:
            warnings.append('description_too_short')

        # Missing offer URL
        if not offer.offer_url:
            violations.append('missing_offer_url')

        is_approved = len(violations) == 0
        return {
            'approved'  : is_approved,
            'violations': violations,
            'warnings'  : warnings,
            'offer_id'  : str(offer.id),
        }

    @staticmethod
    def scan_creative(creative) -> dict:
        """Scan ad creative for policy violations."""
        violations = []
        alt_text   = (getattr(creative, 'alt_text', '') or '').lower()
        asset_url  = (creative.asset_url or '').lower()

        for kw in PROHIBITED_KEYWORDS:
            if kw in alt_text:
                violations.append(f'prohibited_in_alt:{kw}')

        is_approved = len(violations) == 0
        return {'approved': is_approved, 'violations': violations}

    @staticmethod
    def bulk_scan_offers(offer_ids: list = None) -> dict:
        """Scan multiple offers and return compliance report."""
        from api.offer_inventory.models import Offer
        qs = Offer.objects.filter(status='active')
        if offer_ids:
            qs = qs.filter(id__in=offer_ids)

        results    = {'approved': 0, 'flagged': 0, 'flagged_offers': []}
        for offer in qs[:500]:
            res = AdContentFilter.validate_offer(offer)
            if res['approved']:
                results['approved'] += 1
            else:
                results['flagged'] += 1
                results['flagged_offers'].append({
                    'offer_id' : str(offer.id),
                    'title'    : offer.title,
                    'violations': res['violations'],
                })
        return results
