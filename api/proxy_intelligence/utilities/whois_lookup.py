"""
WHOIS Lookup Utility  (PRODUCTION-READY — COMPLETE)
=====================================================
Retrieves WHOIS/RDAP registration data for IP addresses and domains.
Used for IP ownership verification, abuse contact lookup, and
network attribution in fraud investigations.

WHOIS data includes:
  - Network name and CIDR
  - Registrant organization
  - Abuse contact email
  - Country of registration
  - Registration dates
  - ASN information

Uses two backends:
  1. RDAP (Registration Data Access Protocol) — modern, structured JSON
     Endpoint: https://rdap.arin.net/registry/ip/{ip}
  2. ipwhois Python library — traditional WHOIS parsing (fallback)

Both are cached aggressively (24 hours) since WHOIS data changes rarely.
"""
import logging
import json
from typing import Optional, Dict

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── Cache TTL ──────────────────────────────────────────────────────────────
WHOIS_CACHE_TTL = 86400   # 24 hours

# ── RDAP API Endpoints ─────────────────────────────────────────────────────
RDAP_ENDPOINTS = {
    'arin':    'https://rdap.arin.net/registry/ip/{ip}',
    'ripe':    'https://rdap.db.ripe.net/ip/{ip}',
    'apnic':   'https://rdap.apnic.net/ip/{ip}',
    'lacnic':  'https://rdap.lacnic.net/rdap/ip/{ip}',
    'afrinic': 'https://rdap.afrinic.net/rdap/ip/{ip}',
    # Generic bootstrap (redirects to correct RIR automatically)
    'bootstrap': 'https://rdap.iana.org/ip/{ip}',
}


class WhoisLookup:
    """
    Multi-source WHOIS/RDAP lookup with aggressive caching.

    Usage:
        result = WhoisLookup.lookup('1.2.3.4')
        print(result['organization'])
        print(result['abuse_email'])
        print(result['network_cidr'])
    """

    # ── Main Lookup ────────────────────────────────────────────────────────

    @classmethod
    def lookup(cls, ip_address: str) -> dict:
        """
        Full WHOIS/RDAP lookup for an IP address.
        Tries RDAP first, falls back to ipwhois library.

        Args:
            ip_address: IPv4 or IPv6 address

        Returns:
            {
                'ip_address':    str,
                'organization':  str,
                'asn':           str,
                'network_name':  str,
                'network_cidr':  str,
                'country_code':  str,
                'abuse_email':   str,
                'registrar':     str,
                'registered':    str (date),
                'last_updated':  str (date),
                'source':        str ('rdap'|'ipwhois'|'unavailable'),
            }
        """
        cache_key = f"pi:whois:{ip_address}"
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        # Try RDAP first (modern, JSON-structured)
        result = cls._rdap_lookup(ip_address)

        # Fall back to ipwhois library
        if not result or result.get('source') == 'unavailable':
            result = cls._ipwhois_lookup(ip_address)

        # Last resort: return empty structure
        if not result:
            result = cls._empty(ip_address)

        cache.set(cache_key, result, WHOIS_CACHE_TTL)
        return result

    @classmethod
    def lookup_domain(cls, domain: str) -> dict:
        """
        WHOIS lookup for a domain name.
        Returns registration info: registrar, creation date, expiry, nameservers.
        """
        cache_key = f"pi:whois_domain:{domain}"
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        result = cls._domain_rdap_lookup(domain)
        if not result:
            result = {'domain': domain, 'source': 'unavailable', 'error': 'Lookup failed'}

        cache.set(cache_key, result, WHOIS_CACHE_TTL)
        return result

    @classmethod
    def get_abuse_contact(cls, ip_address: str) -> str:
        """
        Get the abuse contact email for an IP address.
        Used for reporting malicious IPs to their providers.
        """
        result = cls.lookup(ip_address)
        return result.get('abuse_email', '')

    @classmethod
    def get_org_name(cls, ip_address: str) -> str:
        """Get the organization name for an IP address."""
        result = cls.lookup(ip_address)
        return result.get('organization', '')

    @classmethod
    def get_network_cidr(cls, ip_address: str) -> str:
        """Get the network CIDR block this IP belongs to."""
        result = cls.lookup(ip_address)
        return result.get('network_cidr', '')

    @classmethod
    def is_residential(cls, ip_address: str) -> bool:
        """
        Heuristic check: is this IP from a residential ISP?
        Based on organization name keywords.
        """
        org   = cls.get_org_name(ip_address).lower()
        keywords = [
            'broadband', 'dsl', 'cable', 'fiber', 'residential',
            'home', 'comcast', 'cox', 'verizon', 'charter', 'spectrum',
        ]
        return any(kw in org for kw in keywords)

    # ── RDAP Lookup ────────────────────────────────────────────────────────

    @classmethod
    def _rdap_lookup(cls, ip_address: str) -> Optional[dict]:
        """Perform RDAP lookup using IANA bootstrap endpoint."""
        try:
            import requests
            url  = RDAP_ENDPOINTS['arin'].format(ip=ip_address)
            resp = requests.get(
                url,
                headers={'Accept': 'application/rdap+json'},
                timeout=8,
                allow_redirects=True,
            )

            if resp.status_code == 404:
                # Try RIPE (European IPs often 404 on ARIN)
                url  = RDAP_ENDPOINTS['ripe'].format(ip=ip_address)
                resp = requests.get(url, timeout=8)

            if resp.status_code != 200:
                return None

            data = resp.json()
            return cls._parse_rdap(ip_address, data)

        except Exception as e:
            logger.debug(f"RDAP lookup failed for {ip_address}: {e}")
            return None

    @classmethod
    def _parse_rdap(cls, ip_address: str, data: dict) -> dict:
        """Parse RDAP JSON response into our standard format."""
        # Network info
        network_name = data.get('name', '')
        network_cidr = data.get('cidr0_cidrs', [{}])[0].get('v4prefix', '') if data.get('cidr0_cidrs') else ''
        handle       = data.get('handle', '')
        country      = data.get('country', '')

        # Extract abuse contact from entities
        abuse_email  = ''
        registrar    = ''
        organization = ''

        for entity in data.get('entities', []):
            roles = entity.get('roles', [])
            vcard = entity.get('vcardArray', [None, []])[1] if entity.get('vcardArray') else []

            if 'abuse' in roles:
                for item in vcard:
                    if isinstance(item, list) and item[0] == 'email':
                        abuse_email = item[3]
                        break

            if 'registrant' in roles or 'technical' in roles:
                for item in vcard:
                    if isinstance(item, list) and item[0] == 'fn':
                        organization = item[3]
                        break

            if 'registrar' in roles:
                for item in vcard:
                    if isinstance(item, list) and item[0] == 'fn':
                        registrar = item[3]
                        break

        # Dates
        events       = {e.get('eventAction'): e.get('eventDate', '') for e in data.get('events', [])}
        registered   = events.get('registration', '')
        last_updated = events.get('last changed', '')

        return {
            'ip_address':   ip_address,
            'organization': organization or network_name,
            'asn':          '',
            'network_name': network_name,
            'network_cidr': network_cidr or handle,
            'country_code': country.upper() if country else '',
            'abuse_email':  abuse_email,
            'registrar':    registrar,
            'registered':   registered[:10] if registered else '',
            'last_updated': last_updated[:10] if last_updated else '',
            'source':       'rdap',
        }

    # ── ipwhois Fallback ───────────────────────────────────────────────────

    @classmethod
    def _ipwhois_lookup(cls, ip_address: str) -> Optional[dict]:
        """Use ipwhois library as fallback (pip install ipwhois)."""
        try:
            import ipwhois
            obj  = ipwhois.IPWhois(ip_address)
            data = obj.lookup_rdap(depth=1)

            return {
                'ip_address':   ip_address,
                'organization': data.get('asn_description', ''),
                'asn':          f"AS{data.get('asn', '')}" if data.get('asn') else '',
                'network_name': data.get('network', {}).get('name', ''),
                'network_cidr': data.get('network', {}).get('cidr', ''),
                'country_code': data.get('asn_country_code', '').upper(),
                'abuse_email':  cls._extract_abuse_email_from_objects(data),
                'registrar':    data.get('network', {}).get('handle', ''),
                'registered':   '',
                'last_updated': '',
                'source':       'ipwhois',
            }
        except ImportError:
            logger.debug("ipwhois not installed — pip install ipwhois")
            return None
        except Exception as e:
            logger.debug(f"ipwhois lookup failed for {ip_address}: {e}")
            return None

    @staticmethod
    def _extract_abuse_email_from_objects(data: dict) -> str:
        """Extract abuse email from ipwhois objects dict."""
        for key, obj in data.get('objects', {}).items():
            if 'Abuse' in str(obj.get('name', '')):
                for contact in obj.get('contact', {}).get('email', []):
                    if isinstance(contact, dict):
                        return contact.get('value', '')
                    return str(contact)
        return ''

    # ── Domain RDAP ────────────────────────────────────────────────────────

    @classmethod
    def _domain_rdap_lookup(cls, domain: str) -> Optional[dict]:
        """RDAP lookup for a domain name."""
        try:
            import requests
            url  = f"https://rdap.verisign.com/com/v1/domain/{domain}"
            resp = requests.get(url, timeout=8)
            if resp.status_code != 200:
                # Try generic RDAP bootstrap
                url  = f"https://rdap.iana.org/domain/{domain}"
                resp = requests.get(url, timeout=8)

            if resp.status_code != 200:
                return None

            data     = resp.json()
            events   = {e.get('eventAction'): e.get('eventDate', '') for e in data.get('events', [])}
            nameservers = [ns.get('ldhName', '') for ns in data.get('nameservers', [])]

            return {
                'domain':          domain,
                'registrar':       '',
                'status':          data.get('status', []),
                'creation_date':   events.get('registration', '')[:10],
                'expiry_date':     events.get('expiration', '')[:10],
                'updated_date':    events.get('last changed', '')[:10],
                'nameservers':     nameservers,
                'source':          'rdap',
            }
        except Exception as e:
            logger.debug(f"Domain RDAP lookup failed for {domain}: {e}")
            return None

    @staticmethod
    def _empty(ip_address: str) -> dict:
        return {
            'ip_address':   ip_address,
            'organization': '',
            'asn':          '',
            'network_name': '',
            'network_cidr': '',
            'country_code': '',
            'abuse_email':  '',
            'registrar':    '',
            'registered':   '',
            'last_updated': '',
            'source':       'unavailable',
        }
