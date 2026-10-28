# api/admin_panel/geo_routing.py
"""GEO-based offer routing rules — admin control."""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class GeoRoutingAdmin:
    """Admin control for GEO-based offer routing rules."""

    @classmethod
    def get_routing_rules(cls) -> List[Dict]:
        cached = cache.get('admin_panel:geo_rules')
        if cached:
            return cached
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            obj = SystemConfig.objects.get(key='geo_routing_rules')
            rules = json.loads(obj.value)
            cache.set('admin_panel:geo_rules', rules, 300)
            return rules
        except Exception:
            return []

    @classmethod
    def set_routing_rule(cls, country: str, offer_ids: List[Any],
                         priority: str = 'standard', actor=None) -> bool:
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            rules = cls.get_routing_rules()
            existing = next((r for r in rules if r.get('country') == country), None)
            rule_data = {'country': country, 'offer_ids': offer_ids,
                         'priority': priority, 'updated_at': timezone.now().isoformat()}
            if existing:
                existing.update(rule_data)
            else:
                rules.append(rule_data)
            SystemConfig.objects.update_or_create(
                key='geo_routing_rules',
                defaults={'value': json.dumps(rules), 'group': 'routing', 'value_type': 'json'}
            )
            cache.delete('admin_panel:geo_rules')
            return True
        except Exception as e:
            logger.error(f"[GeoRouting.set_rule] {e}")
            return False

    @classmethod
    def get_country_stats(cls, days: int = 7) -> List[Dict]:
        """Conversion stats by country."""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.proxy_intelligence.models import IPIntelligence
            from django.db.models import Count
            return list(
                IPIntelligence.objects.filter(created_at__gte=cutoff)
                .values('country_code').annotate(visits=Count('id')).order_by('-visits')[:30]
            )
        except Exception:
            return []

    @classmethod
    def block_country(cls, country: str, reason: str, actor=None) -> bool:
        """Block all traffic from a country."""
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            blocked_raw = SystemConfig.objects.filter(key='blocked_countries').first()
            blocked = json.loads(blocked_raw.value) if blocked_raw else []
            if country not in [b.get('country') for b in blocked]:
                blocked.append({'country': country, 'reason': reason,
                                 'blocked_at': timezone.now().isoformat()})
                SystemConfig.objects.update_or_create(
                    key='blocked_countries',
                    defaults={'value': json.dumps(blocked), 'group': 'routing'}
                )
                cache.delete('admin_panel:blocked_countries')
            return True
        except Exception:
            return False

    @classmethod
    def get_blocked_countries(cls) -> List[Dict]:
        cached = cache.get('admin_panel:blocked_countries')
        if cached:
            return cached
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            obj = SystemConfig.objects.get(key='blocked_countries')
            countries = json.loads(obj.value)
            cache.set('admin_panel:blocked_countries', countries, 300)
            return countries
        except Exception:
            return []


geo_routing_admin = GeoRoutingAdmin()