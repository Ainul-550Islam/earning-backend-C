# api/payment_gateways/blacklist/BlacklistEngine.py
# Traffic blacklist checking engine

from django.core.cache import cache
import ipaddress
import logging

logger = logging.getLogger(__name__)


class BlacklistEngine:
    """
    Checks incoming traffic against advertiser blacklists.
    Results cached 5 minutes for performance.

    Called by:
        - ClickTracker before recording a click
        - PostbackEngine before processing a conversion
        - RTB BiddingEngine before serving an offer
    """

    CACHE_TTL = 300  # 5 minutes

    def is_blocked(self, offer_id: int, advertiser_id: int,
                   ip: str, country: str, device: str,
                   os_name: str = '', sub_id: str = '',
                   publisher_id: int = None) -> dict:
        """
        Check if traffic should be blocked.

        Returns:
            dict: {'blocked': bool, 'reason': str, 'rule_type': str}
        """
        cache_key = f'bl:{offer_id}:{ip}:{country}:{device}'
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        result = self._check_all(offer_id, advertiser_id, ip, country,
                                  device, os_name, sub_id, publisher_id)
        cache.set(cache_key, result, self.CACHE_TTL)
        return result

    def _check_all(self, offer_id, advertiser_id, ip, country,
                   device, os_name, sub_id, publisher_id) -> dict:
        from .models import TrafficBlacklist
        from django.db.models import Q
        from django.utils import timezone

        # Get all active rules for this advertiser + offer
        rules = TrafficBlacklist.objects.filter(
            Q(offer_id=offer_id) | Q(offer__isnull=True),
            owner_id=advertiser_id,
            is_active=True,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )

        for rule in rules:
            blocked, reason = self._check_rule(rule, ip, country, device,
                                                os_name, sub_id, publisher_id)
            if blocked:
                # Increment block counter
                TrafficBlacklist.objects.filter(id=rule.id).update(
                    block_count=rule.block_count + 1
                )
                return {'blocked': True, 'reason': reason, 'rule_type': rule.block_type}

        return {'blocked': False, 'reason': '', 'rule_type': ''}

    def _check_rule(self, rule, ip, country, device,
                    os_name, sub_id, publisher_id) -> tuple:
        bt  = rule.block_type
        val = rule.value.strip().lower()

        if bt == 'ip' and ip:
            if ip.lower() == val:
                return True, f'IP {ip} is blacklisted'

        elif bt == 'ip_range' and ip:
            try:
                if ipaddress.ip_address(ip) in ipaddress.ip_network(val, strict=False):
                    return True, f'IP {ip} is in blacklisted range {val}'
            except ValueError:
                pass

        elif bt == 'country' and country:
            if country.lower() == val:
                return True, f'Country {country} is blacklisted'

        elif bt == 'device' and device:
            if device.lower() == val:
                return True, f'Device type {device} is blacklisted'

        elif bt == 'os' and os_name:
            if os_name.lower() == val:
                return True, f'OS {os_name} is blacklisted'

        elif bt == 'sub_id' and sub_id:
            if sub_id.lower() == val:
                return True, f'Sub-ID {sub_id} is blacklisted'

        elif bt == 'publisher' and publisher_id:
            if str(publisher_id) == val:
                return True, f'Publisher {publisher_id} is blacklisted'

        elif bt == 'source':
            # Check if referer domain matches
            pass

        return False, ''

    def add_rule(self, owner_id: int, block_type: str, value: str,
                 offer_id: int = None, reason: str = '',
                 created_by: str = 'advertiser') -> 'TrafficBlacklist':
        """Add a blacklist rule."""
        from .models import TrafficBlacklist
        rule, _ = TrafficBlacklist.objects.get_or_create(
            owner_id=owner_id,
            block_type=block_type,
            value=value,
            offer_id=offer_id,
            defaults={
                'reason':          reason,
                'created_by_type': created_by,
                'is_active':       True,
            }
        )
        # Clear cache
        cache.delete_pattern(f'bl:*') if hasattr(cache, 'delete_pattern') else None
        return rule

    def auto_blacklist_low_quality(self, threshold: int = 20):
        """
        Auto-blacklist publishers with quality score below threshold.
        Called by scheduled task.
        """
        from .models import OfferQualityScore
        from django.utils import timezone

        low_quality = OfferQualityScore.objects.filter(
            quality_score__lt=threshold,
            is_blacklisted=False,
            total_clicks__gte=100,  # Need enough data
        )

        blocked = 0
        for score in low_quality:
            self.add_rule(
                owner_id=score.offer.advertiser_id,
                block_type='publisher',
                value=str(score.publisher_id),
                offer_id=score.offer_id,
                reason=f'Auto-blacklist: quality score {score.quality_score}/100',
                created_by='auto',
            )
            score.is_blacklisted    = True
            score.blacklisted_at    = timezone.now()
            score.blacklisted_reason= f'Quality score {score.quality_score} < threshold {threshold}'
            score.save()
            blocked += 1

        logger.info(f'Auto-blacklisted {blocked} low-quality publishers')
        return blocked
