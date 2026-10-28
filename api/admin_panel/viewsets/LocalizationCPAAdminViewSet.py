# api/admin_panel/viewsets/LocalizationCPAAdminViewSet.py
"""
Localization CPAlead Admin Control — Full admin for country targeting & region services.
Controls: CountryTargetingService, ContentRegionService, GeoService, CurrencyService.
Previously missing — now 100% covered.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class LocalizationCPAAdminViewSet(viewsets.ViewSet):
    """
    CPAlead Localization & Country Targeting admin.
    Route: /api/admin-panel/localization-cpa/
    """
    permission_classes = [IsAdminUser]

    # ── OVERVIEW ──────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Full localization system overview."""
        try:
            data = {}
            # ContentRegionService: all regions
            try:
                from api.localization.services.cpalead.ContentRegionService import ContentRegionService
                svc = ContentRegionService()
                regions = svc.get_all_regions_summary()
                data['regions_count'] = len(regions)
                data['regions'] = regions
            except Exception as e:
                data['regions_error'] = str(e)

            # GeoService: supported countries
            try:
                from api.localization.services.services_loca.GeoService import GeoService
                data['geo_service_status'] = 'ok'
            except Exception as e:
                data['geo_service_status'] = f'error: {e}'

            # CurrencyService
            try:
                from api.localization.services.services_loca.CurrencyService import CurrencyService
                data['currency_service_status'] = 'ok'
            except Exception as e:
                data['currency_service_status'] = f'error: {e}'

            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    # ── COUNTRY TARGETING ─────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def country_config(self, request):
        """
        Get full config for a country — payment methods, earning config,
        GDPR requirements, available features.
        """
        try:
            country = request.query_params.get('country', 'BD').upper()
            from api.localization.services.cpalead.CountryTargetingService import (
                CountryTargetingService, PAYMENT_METHODS, COUNTRY_EARNING_CONFIG
            )
            svc = CountryTargetingService()
            data = {
                'country_code':    country,
                'payment_methods': svc.get_payment_methods(country),
                'earning_config':  svc.get_earning_config(country),
                'gdpr':            svc.get_gdpr_requirements(country),
            }
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def all_payment_methods(self, request):
        """List all configured payment methods per country."""
        try:
            from api.localization.services.cpalead.CountryTargetingService import PAYMENT_METHODS
            return Response({'success': True, 'data': PAYMENT_METHODS})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def all_earning_configs(self, request):
        """List earning configs for all countries."""
        try:
            from api.localization.services.cpalead.CountryTargetingService import COUNTRY_EARNING_CONFIG
            return Response({'success': True, 'data': COUNTRY_EARNING_CONFIG})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def offer_availability(self, request):
        """Check if an offer is available in a country."""
        try:
            offer_id = int(request.query_params.get('offer_id', 0))
            country  = request.query_params.get('country', 'BD').upper()
            from api.localization.services.cpalead.CountryTargetingService import CountryTargetingService
            svc = CountryTargetingService()
            available = svc.is_offer_available(offer_id, country)
            return Response({'success': True, 'offer_id': offer_id,
                             'country': country, 'available': available})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def update_country_config(self, request):
        """Update earning config for a country (updates SystemConfig table)."""
        try:
            country    = request.data.get('country_code', '').upper()
            min_withdrawal = request.data.get('min_withdrawal')
            max_daily      = request.data.get('max_daily')
            tax_rate       = request.data.get('tax_rate')

            if not country:
                return Response({'error': 'country_code required'}, status=400)

            from api.admin_panel.models.config import SystemConfig
            updates = {}
            if min_withdrawal is not None:
                SystemConfig.objects.update_or_create(
                    key=f'localization.{country}.min_withdrawal',
                    defaults={'value': str(min_withdrawal), 'group': 'localization'}
                )
                updates['min_withdrawal'] = min_withdrawal
            if max_daily is not None:
                SystemConfig.objects.update_or_create(
                    key=f'localization.{country}.max_daily',
                    defaults={'value': str(max_daily), 'group': 'localization'}
                )
                updates['max_daily'] = max_daily
            if tax_rate is not None:
                SystemConfig.objects.update_or_create(
                    key=f'localization.{country}.tax_rate',
                    defaults={'value': str(tax_rate), 'group': 'localization'}
                )
                updates['tax_rate'] = tax_rate

            cache.delete(f'country_config_{country}')
            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=request.user, action='update_country_config',
                                  model_name='SystemConfig', object_id=country,
                                  changes=updates)
            except Exception:
                pass
            return Response({'success': True, 'country': country, **updates})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ── CONTENT REGIONS ───────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def regions(self, request):
        """List all CPAlead content regions with countries and features."""
        try:
            from api.localization.services.cpalead.ContentRegionService import ContentRegionService
            svc = ContentRegionService()
            data = svc.get_all_regions_summary()
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def region_for_country(self, request):
        """Get region details for a specific country."""
        try:
            country = request.query_params.get('country', 'BD').upper()
            from api.localization.services.cpalead.ContentRegionService import ContentRegionService
            svc = ContentRegionService()
            region = svc.get_region_for_country(country)
            return Response({'success': True, 'country': country, 'data': region})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def feature_availability(self, request):
        """Check if a specific feature is enabled for a country."""
        try:
            country = request.query_params.get('country', 'BD').upper()
            feature = request.query_params.get('feature', 'survey_offers')
            from api.localization.services.cpalead.ContentRegionService import ContentRegionService
            svc = ContentRegionService()
            enabled = svc.is_feature_enabled(country, feature)
            payment_methods = svc.get_payment_methods(country)
            min_payout = svc.get_min_payout(country)
            gdpr_required = svc.requires_gdpr(country)
            return Response({'success': True, 'data': {
                'country': country, 'feature': feature,
                'enabled': enabled,
                'payment_methods': payment_methods,
                'min_payout_usd': min_payout,
                'gdpr_required': gdpr_required,
            }})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_country_feature(self, request):
        """Enable/disable a feature for a specific country via SystemConfig."""
        try:
            country = request.data.get('country', '').upper()
            feature = request.data.get('feature', '')
            enabled = bool(request.data.get('enabled', True))

            if not country or not feature:
                return Response({'error': 'country and feature required'}, status=400)

            from api.admin_panel.models.config import SystemConfig
            SystemConfig.objects.update_or_create(
                key=f'localization.{country}.feature.{feature}',
                defaults={'value': str(enabled).lower(), 'group': 'localization_features'}
            )
            cache.delete(f'region_{country}')
            cache.delete(f'feature_{country}_{feature}')

            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=request.user, action='toggle_country_feature',
                                  model_name='SystemConfig', object_id=f'{country}_{feature}',
                                  changes={'country': country, 'feature': feature, 'enabled': enabled})
            except Exception:
                pass
            return Response({'success': True, 'country': country,
                             'feature': feature, 'enabled': enabled})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ── CURRENCY & GEO ────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def currency_rates(self, request):
        """Get current currency conversion rates."""
        try:
            from api.localization.services.services_loca.CurrencyService import CurrencyService
            svc = CurrencyService()
            base = request.query_params.get('base', 'USD')
            rates = svc.get_rates(base_currency=base)
            return Response({'success': True, 'base': base, 'data': rates})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def geo_lookup(self, request):
        """Look up country/region info for an IP address."""
        try:
            ip = request.query_params.get('ip') or request.META.get('REMOTE_ADDR')
            from api.localization.services.services_loca.GeoService import GeoService
            svc = GeoService()
            result = svc.lookup(ip)
            return Response({'success': True, 'ip': ip, 'data': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def localized_offer_config(self, request):
        """Get full localized offer config for a country."""
        try:
            country = request.query_params.get('country', 'BD').upper()
            from api.localization.services.cpalead.ContentRegionService import ContentRegionService
            svc = ContentRegionService()
            config = svc.get_localized_offer_config(country)
            return Response({'success': True, 'country': country, 'data': config})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    # ── CACHE MANAGEMENT ──────────────────────────────────────────────────────

    @action(detail=False, methods=['post'])
    def flush_localization_cache(self, request):
        """Flush all localization-related cache keys."""
        try:
            country = request.data.get('country')
            if country:
                keys = [
                    f'country_config_{country}', f'region_{country}',
                    f'geo_rate_{country}', f'payment_methods_{country}',
                ]
                for k in keys:
                    cache.delete(k)
                return Response({'success': True, 'flushed': keys})
            else:
                # Try pattern delete
                try:
                    from django.core.cache import caches
                    client = caches['default'].client.get_client()
                    keys = client.keys('*country_config*') + client.keys('*region_*')
                    if keys:
                        client.delete(*keys)
                    return Response({'success': True, 'deleted_count': len(keys)})
                except Exception:
                    return Response({'success': True,
                                     'message': 'Pattern flush not supported. Use country param.'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)