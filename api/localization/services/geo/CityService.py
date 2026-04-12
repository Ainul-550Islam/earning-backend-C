# services/geo/CityService.py
"""City search and data service"""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class CityService:
    """City search, autocomplete, and data service"""

    def autocomplete(self, query: str, country_code: str = '', limit: int = 10) -> List[Dict]:
        """City name autocomplete"""
        try:
            from ..models.core import City
            from django.db.models import Q
            qs = City.objects.filter(
                is_active=True
            ).filter(
                Q(name__istartswith=query) | Q(native_name__istartswith=query)
            ).order_by('-is_capital', 'name').select_related('country')
            if country_code:
                qs = qs.filter(country__code=country_code.upper())
            return [{
                'id': c.id, 'name': c.name, 'native_name': c.native_name,
                'country_code': c.country.code if c.country else '',
                'is_capital': c.is_capital,
            } for c in qs[:limit]]
        except Exception as e:
            logger.error(f"City autocomplete failed: {e}")
            return []

    def get_capitals(self) -> List[Dict]:
        """All capital cities"""
        try:
            from ..models.core import City
            capitals = City.objects.filter(is_capital=True, is_active=True).select_related('country', 'timezone')
            return [{
                'name': c.name, 'country_code': c.country.code if c.country else '',
                'timezone': c.timezone.name if c.timezone else '',
            } for c in capitals]
        except Exception as e:
            logger.error(f"Get capitals failed: {e}")
            return []
