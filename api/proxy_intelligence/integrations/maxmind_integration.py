"""
MaxMind GeoIP2 Integration  (PRODUCTION-READY - COMPLETE)
===========================================================
Provides geo-location, ISP, and connection-type data via MaxMind GeoIP2.

API key priority:
  1. IntegrationCredential model (per-tenant, stored in DB)
  2. settings.MAXMIND_ACCOUNT_ID / settings.MAXMIND_LICENSE_KEY
  3. os.environ['MAXMIND_ACCOUNT_ID'] / os.environ['MAXMIND_LICENSE_KEY']

Supports BOTH:
  - Local .mmdb database file (fastest, free tier)
  - MaxMind GeoIP2 Precision Web Service (requires paid account)
"""
import logging
import os
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from ..exceptions import MaxMindError

logger = logging.getLogger(__name__)

CACHE_TTL = 86400  # 24 hours — geo data is very stable


class MaxMindIntegration:
    """
    Full MaxMind GeoIP2 integration.
    Tries local .mmdb first, then web service.
    Loads credentials from IntegrationCredential or settings.
    """

    def __init__(self, tenant=None):
        self.tenant = tenant
        creds = self._resolve_credentials()
        self.account_id   = creds['account_id']
        self.license_key  = creds['license_key']
        self.db_path      = creds.get('db_path') or getattr(settings, 'MAXMIND_DB_PATH', None)

    # ── Credential Resolution ────────────────────────────────────────────

    def _resolve_credentials(self) -> dict:
        # 1. IntegrationCredential model
        try:
            from ..models import IntegrationCredential
            qs = IntegrationCredential.objects.filter(
                service='maxmind',
                is_active=True
            )
            if self.tenant:
                qs = qs.filter(tenant=self.tenant)
            cred = qs.first()
            if cred and cred.api_key:
                # api_key stores "account_id:license_key" for MaxMind
                cfg = cred.config or {}
                account_id  = cfg.get('account_id', '')
                license_key = cred.api_key  # primary secret field
                IntegrationCredential.objects.filter(pk=cred.pk).update(
                    used_today=cred.used_today + 1
                )
                return {
                    'account_id':  account_id,
                    'license_key': license_key,
                    'db_path':     cfg.get('db_path', ''),
                }
        except Exception as e:
            logger.debug(f"MaxMind IntegrationCredential lookup failed: {e}")

        # 2. Django settings
        return {
            'account_id':  getattr(settings, 'MAXMIND_ACCOUNT_ID', None)
                           or os.environ.get('MAXMIND_ACCOUNT_ID', ''),
            'license_key': getattr(settings, 'MAXMIND_LICENSE_KEY', None)
                           or os.environ.get('MAXMIND_LICENSE_KEY', ''),
            'db_path':     getattr(settings, 'MAXMIND_DB_PATH', ''),
        }

    # ── Public API ───────────────────────────────────────────────────────

    def lookup(self, ip_address: str) -> dict:
        """
        Full IP enrichment. Tries local .mmdb, then web service.
        Returns empty result (never raises) if both fail.
        """
        cache_key = f"pi:maxmind:{ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        result = {}

        # Try local database first (no quota usage)
        if self.db_path:
            try:
                result = self._lookup_local(ip_address)
            except Exception as e:
                logger.debug(f"MaxMind local DB failed for {ip_address}: {e}")

        # Fall back to web service
        if not result and self.account_id and self.license_key:
            try:
                result = self._lookup_web_service(ip_address)
            except MaxMindError as e:
                logger.warning(f"MaxMind web service failed for {ip_address}: {e}")
            except Exception as e:
                logger.error(f"MaxMind unexpected error for {ip_address}: {e}")

        if not result:
            result = self._empty_result(ip_address)

        cache.set(cache_key, result, CACHE_TTL)
        return result

    def enrich_ip_intelligence(self, ip_address: str) -> bool:
        """Lookup MaxMind data and persist to IPIntelligence record."""
        try:
            data = self.lookup(ip_address)
            if data.get('source') == 'maxmind_unavailable':
                return False

            from ..models import IPIntelligence
            obj, _ = IPIntelligence.objects.get_or_create(
                ip_address=ip_address,
                defaults={'tenant': self.tenant}
            )
            # Only overwrite if we got real data
            if data.get('country_code'):
                obj.country_code = data['country_code']
            if data.get('country_name'):
                obj.country_name = data['country_name']
            if data.get('city'):
                obj.city = data['city']
            if data.get('region'):
                obj.region = data['region']
            if data.get('latitude'):
                obj.latitude = data['latitude']
            if data.get('longitude'):
                obj.longitude = data['longitude']
            if data.get('timezone'):
                obj.timezone = data['timezone']
            if data.get('isp'):
                obj.isp = data['isp']
            if data.get('asn'):
                obj.asn = data['asn']
            if data.get('asn_name'):
                obj.asn_name = data['asn_name']

            # MaxMind Insights includes connection type flags
            if data.get('is_vpn') is not None:
                obj.is_vpn |= data['is_vpn']
            if data.get('is_proxy') is not None:
                obj.is_proxy |= data['is_proxy']
            if data.get('is_hosting') is not None:
                obj.is_hosting = data['is_hosting']

            obj.save()
            return True
        except Exception as e:
            logger.error(f"MaxMind enrich failed for {ip_address}: {e}")
            return False

    # ── Local Database Lookup ─────────────────────────────────────────────

    def _lookup_local(self, ip_address: str) -> dict:
        """Use local .mmdb file via the geoip2 Python library."""
        try:
            import geoip2.database
        except ImportError:
            logger.debug("geoip2 library not installed. Run: pip install geoip2")
            return {}

        try:
            with geoip2.database.Reader(self.db_path) as reader:
                try:
                    # Try City database (most complete)
                    response = reader.city(ip_address)
                    return {
                        'source':       'maxmind_local_city',
                        'country_code': response.country.iso_code or '',
                        'country_name': response.country.name or '',
                        'city':         response.city.name or '',
                        'region':       response.subdivisions.most_specific.name or '',
                        'postal_code':  response.postal.code or '',
                        'latitude':     float(response.location.latitude or 0),
                        'longitude':    float(response.location.longitude or 0),
                        'accuracy_radius': response.location.accuracy_radius or 0,
                        'timezone':     response.location.time_zone or '',
                        'asn':          '',   # not in City DB
                        'isp':          '',
                        'asn_name':     '',
                        'is_vpn':       None,
                        'is_proxy':     None,
                        'is_hosting':   None,
                    }
                except Exception:
                    pass

                try:
                    # Try ASN database
                    asn_response = reader.asn(ip_address)
                    return {
                        'source': 'maxmind_local_asn',
                        'asn':    f"AS{asn_response.autonomous_system_number}",
                        'asn_name': asn_response.autonomous_system_organization or '',
                        'country_code': '', 'country_name': '', 'city': '',
                        'region': '', 'latitude': 0.0, 'longitude': 0.0,
                        'timezone': '', 'isp': '', 'is_vpn': None,
                        'is_proxy': None, 'is_hosting': None,
                    }
                except Exception:
                    pass

        except Exception as e:
            logger.debug(f"MaxMind local DB read error: {e}")
        return {}

    # ── Web Service Lookup ────────────────────────────────────────────────

    def _lookup_web_service(self, ip_address: str) -> dict:
        """Use MaxMind GeoIP2 Precision Web Service."""
        try:
            import geoip2.webservice
            import geoip2.errors
        except ImportError:
            logger.debug("geoip2 library not installed.")
            return {}

        try:
            with geoip2.webservice.Client(
                int(self.account_id), self.license_key,
                host='geolite.info'
            ) as client:
                try:
                    response = client.insights(ip_address)
                    traits = response.traits
                    return {
                        'source':        'maxmind_insights',
                        'country_code':  response.country.iso_code or '',
                        'country_name':  response.country.name or '',
                        'city':          response.city.name or '',
                        'region':        response.subdivisions.most_specific.name or '',
                        'postal_code':   response.postal.code or '',
                        'latitude':      float(response.location.latitude or 0),
                        'longitude':     float(response.location.longitude or 0),
                        'accuracy_radius': response.location.accuracy_radius or 0,
                        'timezone':      response.location.time_zone or '',
                        'asn':           f"AS{traits.autonomous_system_number}"
                                         if traits.autonomous_system_number else '',
                        'asn_name':      traits.autonomous_system_organization or '',
                        'isp':           traits.isp or '',
                        'organization':  traits.organization or '',
                        'domain':        traits.domain or '',
                        'connection_type': traits.connection_type or '',
                        'user_type':     traits.user_type or '',
                        # Anonymizer flags (Insights only)
                        'is_anonymous':            bool(getattr(traits, 'is_anonymous', False)),
                        'is_vpn':                  bool(getattr(traits, 'is_vpn', False)),
                        'is_proxy':                bool(getattr(traits, 'is_anonymous_proxy', False)),
                        'is_hosting':              bool(getattr(traits, 'is_hosting_provider', False)),
                        'is_tor':                  bool(getattr(traits, 'is_tor_exit_node', False)),
                        'is_legitimate_proxy':     bool(getattr(traits, 'is_legitimate_proxy', False)),
                        'is_residential_proxy':    bool(getattr(traits, 'is_residential_proxy', False)),
                    }
                except geoip2.errors.AddressNotFoundError:
                    return {}

        except geoip2.errors.AuthenticationError as e:
            raise MaxMindError(f"MaxMind authentication failed: {e}")
        except geoip2.errors.OutOfQueriesError:
            raise MaxMindError("MaxMind quota exhausted.")
        except Exception as e:
            raise MaxMindError(f"MaxMind web service error: {e}")

    @staticmethod
    def _empty_result(ip_address: str) -> dict:
        return {
            'source':       'maxmind_unavailable',
            'ip_address':   ip_address,
            'country_code': '', 'country_name': '',
            'city': '', 'region': '',
            'latitude': 0.0, 'longitude': 0.0,
            'timezone': '', 'isp': '', 'asn': '', 'asn_name': '',
            'is_vpn': None, 'is_proxy': None, 'is_hosting': None,
        }
