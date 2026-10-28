from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/services_new/SmartLinkService.py
"""SmartLink Service — geo+device offer routing. CMS owns this."""
import logging
from typing import Dict, Optional
from django.db.models import F

logger = logging.getLogger(__name__)


class SmartLinkService:

    @staticmethod
    def resolve(slug: str, ip: str = '', user_agent: str = '',
                user=None, session_key: str = '') -> Dict:
        """
        Resolve SmartLink to best offer URL.
        Auto-detects country from IP, device from user_agent.
        """
        from api.cms.models_new.smartlink import SmartLink, SmartLinkClick
        try:
            sl = SmartLink.objects.get(slug=slug, is_active=True)
        except SmartLink.DoesNotExist:
            return {'error': 'SmartLink not found', 'redirect_url': '/'}

        country = SmartLinkService._detect_country(ip)
        device = SmartLinkService._detect_device(user_agent)
        subid = str(user.id) if user and user.is_authenticated else session_key or 'anon'
        rule = sl.get_best_offer(country=country, device=device)

        redirect_url = sl.fallback_url or '/'
        if rule:
            offer_url = rule.offer_url
            if '?' in offer_url:
                redirect_url = f"{offer_url}&subid={subid}"
            else:
                redirect_url = f"{offer_url}?subid={subid}"
            SmartLinkService._record_click(sl, rule, user, ip, country, device, subid)

        SmartLink.objects.filter(pk=sl.pk).update(total_clicks=F('total_clicks') + 1)
        return {
            'redirect_url': redirect_url,
            'country': country,
            'device': device,
            'offer_title': rule.offer_title if rule else '',
            'payout_usd': float(rule.payout_usd) if rule else 0,
        }

    @staticmethod
    def _record_click(sl, rule, user, ip, country, device, subid):
        from api.cms.models_new.smartlink import SmartLinkClick
        try:
            SmartLinkClick.objects.create(
                smartlink=sl, rule_used=rule, user=user,
                ip_address=ip or None, country_code=country,
                device_type=device, subid=subid,
            )
            from django.db.models import F
            rule.__class__.objects.filter(pk=rule.pk).update(click_count=F('click_count') + 1)
        except Exception as e:
            logger.debug(f"SmartLink click record failed: {e}")

    @staticmethod
    def _detect_country(ip: str) -> str:
        """Detect country from IP. Uses geoip2 if available, fallback empty."""
        if not ip:
            return ''
        try:
            import geoip2.database
            from django.conf import settings
            db_path = getattr(settings, 'GEOIP_PATH', '')
            if db_path:
                with geoip2.database.Reader(f"{db_path}/GeoLite2-Country.mmdb") as reader:
                    resp = reader.country(ip)
                    return resp.country.iso_code or ''
        except Exception:
            pass
        return ''

    @staticmethod
    def _detect_device(user_agent: str) -> str:
        """Detect device type from user agent."""
        if not user_agent:
            return 'desktop'
        ua = user_agent.lower()
        if any(kw in ua for kw in ['ipad', 'tablet', 'kindle']):
            return 'tablet'
        if any(kw in ua for kw in ['mobile', 'android', 'iphone', 'ipod', 'phone']):
            return 'mobile'
        return 'desktop'

    @staticmethod
    def get_analytics(slug: str, days: int = 7) -> Dict:
        from api.cms.models_new.smartlink import SmartLink, SmartLinkClick
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        try:
            sl = SmartLink.objects.get(slug=slug)
        except SmartLink.DoesNotExist:
            return {}
        cutoff = timezone.now() - timedelta(days=days)
        clicks = SmartLinkClick.objects.filter(smartlink=sl, created_at__gte=cutoff)
        by_country = dict(clicks.values('country_code').annotate(
            count=Count('id')).values_list('country_code', 'count'))
        by_device = dict(clicks.values('device_type').annotate(
            count=Count('id')).values_list('device_type', 'count'))
        return {
            'slug': slug, 'total_clicks': sl.total_clicks,
            'total_conversions': sl.total_conversions,
            'period_clicks': clicks.count(),
            'by_country': by_country,
            'by_device': by_device,
        }

    @staticmethod
    def create_smartlink(name: str, rotation_mode: str = 'best_payout',
                          offers: list = None, created_by=None) -> Optional[Any]:
        from api.cms.models_new.smartlink import SmartLink, SmartLinkRule
        import re
        slug = re.sub(r'[^a-z0-9-]', '-', name.lower()).strip('-')
        try:
            sl = SmartLink.objects.create(
                name=name, slug=slug,
                rotation_mode=rotation_mode, created_by=created_by,
            )
            for i, offer in enumerate(offers or []):
                SmartLinkRule.objects.create(
                    smartlink=sl,
                    offer_id=offer.get('offer_id', ''),
                    offer_url=offer.get('url', ''),
                    offer_title=offer.get('title', ''),
                    payout_usd=offer.get('payout', 0),
                    target_countries=offer.get('countries', []),
                    target_devices=offer.get('devices', []),
                    weight=offer.get('weight', 1),
                    order=i,
                )
            return sl
        except Exception as e:
            logger.error(f"SmartLink create failed: {e}")
            return None
