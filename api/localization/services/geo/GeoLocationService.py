# services/geo/GeoLocationService.py
"""Lat/lng reverse geocoding service"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class GeoLocationService:
    """Geographic location service — reverse geocode, country/city search"""

    def reverse_geocode(self, latitude: float, longitude: float) -> Dict:
        """Latitude/Longitude থেকে country/city/region পাওয়া"""
        try:
            from ..models.core import City, Country
            # Find nearest city by coordinates (simple distance)
            cities = City.objects.filter(
                is_active=True,
                latitude__isnull=False,
                longitude__isnull=False,
            ).select_related('country', 'timezone')
            min_dist = float('inf')
            nearest = None
            for city in cities[:500]:  # Limit for performance
                try:
                    dist = ((float(city.latitude) - latitude) ** 2 +
                            (float(city.longitude) - longitude) ** 2) ** 0.5
                    if dist < min_dist:
                        min_dist = dist
                        nearest = city
                except Exception:
                    pass
            if nearest:
                return {
                    'city': nearest.name,
                    'country_code': nearest.country.code if nearest.country else '',
                    'country_name': nearest.country.name if nearest.country else '',
                    'timezone': nearest.timezone.name if nearest.timezone else '',
                    'distance_deg': round(min_dist, 4),
                }
        except Exception as e:
            logger.error(f"Reverse geocode failed: {e}")
        return {}

    def search_cities(self, query: str, country_code: str = '', limit: int = 10):
        """City search with autocomplete"""
        try:
            from ..models.core import City
            from django.db.models import Q
            qs = City.objects.filter(
                is_active=True
            ).filter(
                Q(name__icontains=query) | Q(native_name__icontains=query)
            ).select_related('country', 'timezone')
            if country_code:
                qs = qs.filter(country__code=country_code.upper())
            return list(qs[:limit].values(
                'id', 'name', 'native_name', 'is_capital',
                'country__code', 'country__name', 'timezone__name'
            ))
        except Exception as e:
            logger.error(f"City search failed: {e}")
            return []
