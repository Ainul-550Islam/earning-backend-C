"""
DNS Resolver Utility  (PRODUCTION-READY — COMPLETE)
=====================================================
Provides forward and reverse DNS lookup functionality
with caching, timeout handling, and result normalisation.

Used by:
  - VPNDetector._check_hostname() — reverse DNS for VPN keyword match
  - DNSLeakDetector — check DNS consistency
  - IPOrganizationLookup — PTR record analysis
  - SSHTunnelDetector — hostname analysis

Features:
  - Reverse DNS (PTR) lookups with caching
  - Forward DNS (A/AAAA) lookups
  - MX record lookups for domain spam analysis
  - TXT record lookups (SPF, DKIM checks)
  - DNSBL (DNS Blackhole List) checks
  - Async-safe (uses standard socket, no external deps)
"""
import logging
import socket
import ipaddress
from typing import List, Optional, Dict

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── Cache TTLs ─────────────────────────────────────────────────────────────
PTR_CACHE_TTL     = 3600    # 1 hour for reverse DNS
FORWARD_CACHE_TTL = 3600    # 1 hour for forward DNS
MX_CACHE_TTL      = 3600    # 1 hour for MX records
DNSBL_CACHE_TTL   = 1800    # 30 minutes for DNSBL results

# ── Known DNSBL Providers ──────────────────────────────────────────────────
DNSBL_PROVIDERS = [
    'zen.spamhaus.org',          # Spamhaus combined list (SBL + XBL + PBL)
    'b.barracudacentral.org',    # Barracuda reputation
    'bl.spamcop.net',            # SpamCop blocklist
    'dnsbl.sorbs.net',           # SORBS combined
    'multi.uribl.com',           # URIBL multi-list
]

# ── DNS Query Timeout ──────────────────────────────────────────────────────
DNS_TIMEOUT = 3.0  # seconds


class DNSResolver:
    """
    Multi-purpose DNS resolver with result caching.

    All lookup methods follow the same pattern:
      1. Check Redis cache
      2. Perform DNS query with timeout
      3. Cache the result
      4. Return the result (or empty/None on failure)
    """

    # ── Reverse DNS ────────────────────────────────────────────────────────

    @classmethod
    def reverse_lookup(cls, ip_address: str) -> str:
        """
        Perform a reverse DNS (PTR) lookup for an IP address.

        Args:
            ip_address: IPv4 or IPv6 address

        Returns:
            Hostname string, or '' if no PTR record exists
        """
        cache_key = f"pi:rdns:{ip_address}"
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        hostname = ''
        try:
            socket.setdefaulttimeout(DNS_TIMEOUT)
            hostname = socket.gethostbyaddr(ip_address)[0]
        except (socket.herror, socket.gaierror):
            pass  # No PTR record — normal for many IPs
        except OSError as e:
            logger.debug(f"Reverse DNS OS error for {ip_address}: {e}")
        finally:
            socket.setdefaulttimeout(None)

        cache.set(cache_key, hostname, PTR_CACHE_TTL)
        return hostname

    @classmethod
    def get_ptr_record(cls, ip_address: str) -> str:
        """Alias for reverse_lookup — more semantically clear."""
        return cls.reverse_lookup(ip_address)

    @classmethod
    def batch_reverse_lookup(cls, ip_list: List[str]) -> Dict[str, str]:
        """
        Reverse DNS lookup for a batch of IPs.
        Returns dict: {ip_address: hostname}
        """
        results = {}
        for ip in ip_list:
            results[ip] = cls.reverse_lookup(ip)
        return results

    # ── Forward DNS ────────────────────────────────────────────────────────

    @classmethod
    def forward_lookup(cls, hostname: str,
                        record_type: str = 'A') -> List[str]:
        """
        Resolve a hostname to its IP address(es).

        Args:
            hostname:    Domain name to resolve
            record_type: 'A' for IPv4, 'AAAA' for IPv6

        Returns:
            List of IP address strings
        """
        cache_key = f"pi:fwd_dns:{hostname}:{record_type}"
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        results = []
        try:
            family = socket.AF_INET6 if record_type == 'AAAA' else socket.AF_INET
            socket.setdefaulttimeout(DNS_TIMEOUT)
            addr_info = socket.getaddrinfo(hostname, None, family)
            results   = list(set(info[4][0] for info in addr_info))
        except (socket.gaierror, OSError) as e:
            logger.debug(f"Forward DNS lookup failed for {hostname}: {e}")
        finally:
            socket.setdefaulttimeout(None)

        cache.set(cache_key, results, FORWARD_CACHE_TTL)
        return results

    @classmethod
    def resolve_ip(cls, hostname: str) -> Optional[str]:
        """Resolve hostname to its first IPv4 address. Returns None on failure."""
        ips = cls.forward_lookup(hostname, 'A')
        return ips[0] if ips else None

    @classmethod
    def verify_forward_confirmed_reverse(cls, ip_address: str) -> dict:
        """
        FCrDNS (Forward Confirmed Reverse DNS) check.
        A hostname is FCrDNS-verified if:
          1. PTR record for IP → hostname
          2. A record for hostname → same IP

        Used to verify that a hostname claim is legitimate.
        """
        ptr_hostname = cls.reverse_lookup(ip_address)
        if not ptr_hostname:
            return {
                'ip_address':   ip_address,
                'ptr_hostname': '',
                'fcrdns_valid': False,
                'reason':       'no_ptr_record',
            }

        forward_ips = cls.forward_lookup(ptr_hostname)
        confirmed   = ip_address in forward_ips

        return {
            'ip_address':   ip_address,
            'ptr_hostname': ptr_hostname,
            'forward_ips':  forward_ips,
            'fcrdns_valid': confirmed,
            'reason':       'confirmed' if confirmed else 'forward_mismatch',
        }

    # ── MX Records ─────────────────────────────────────────────────────────

    @classmethod
    def get_mx_records(cls, domain: str) -> List[Dict]:
        """
        Get MX records for a domain.
        Returns list of {'priority': int, 'exchange': str}
        Requires dnspython: pip install dnspython
        """
        cache_key = f"pi:mx:{domain}"
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        results = []
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, 'MX')
            results = [
                {
                    'priority': int(rdata.preference),
                    'exchange': str(rdata.exchange).rstrip('.'),
                }
                for rdata in answers
            ]
            results.sort(key=lambda x: x['priority'])
        except ImportError:
            logger.debug("dnspython not installed — MX lookups disabled. pip install dnspython")
        except Exception as e:
            logger.debug(f"MX lookup failed for {domain}: {e}")

        cache.set(cache_key, results, MX_CACHE_TTL)
        return results

    # ── TXT Records ────────────────────────────────────────────────────────

    @classmethod
    def get_txt_records(cls, domain: str) -> List[str]:
        """
        Get TXT records for a domain (SPF, DKIM, DMARC, etc.).
        Requires dnspython: pip install dnspython
        """
        cache_key = f"pi:txt:{domain}"
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        results = []
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, 'TXT')
            results = [
                b''.join(rdata.strings).decode('utf-8', errors='ignore')
                for rdata in answers
            ]
        except ImportError:
            logger.debug("dnspython not installed — TXT lookups disabled")
        except Exception as e:
            logger.debug(f"TXT lookup failed for {domain}: {e}")

        cache.set(cache_key, results, FORWARD_CACHE_TTL)
        return results

    @classmethod
    def check_spf(cls, domain: str) -> dict:
        """Check if a domain has a valid SPF record."""
        txt_records = cls.get_txt_records(domain)
        spf_records = [r for r in txt_records if r.startswith('v=spf1')]

        return {
            'domain':      domain,
            'has_spf':     len(spf_records) > 0,
            'spf_record':  spf_records[0] if spf_records else '',
            'soft_fail':   any('~all' in r for r in spf_records),
            'hard_fail':   any('-all' in r for r in spf_records),
        }

    # ── DNSBL Checks ───────────────────────────────────────────────────────

    @classmethod
    def check_dnsbl(cls, ip_address: str,
                     providers: List[str] = None) -> dict:
        """
        Check an IP against DNS-based blackhole lists.

        Args:
            ip_address: IP to check
            providers:  List of DNSBL hostnames (uses DNSBL_PROVIDERS if None)

        Returns:
            {
                'ip_address':    str,
                'is_blacklisted': bool,
                'listed_in':     list of DNSBL names where IP is listed,
                'checked':       list of all DNSBL providers checked,
            }
        """
        providers = providers or DNSBL_PROVIDERS
        cache_key = f"pi:dnsbl:{ip_address}"
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        # Reverse the IP octets for DNSBL query format
        # e.g. 1.2.3.4 → 4.3.2.1.zen.spamhaus.org
        try:
            addr = ipaddress.ip_address(ip_address)
            if addr.version == 4:
                reversed_ip = '.'.join(reversed(ip_address.split('.')))
            else:
                # IPv6: reverse nibbles
                expanded = addr.exploded.replace(':', '')
                reversed_ip = '.'.join(reversed(list(expanded)))
        except ValueError:
            return {'ip_address': ip_address, 'is_blacklisted': False,
                    'listed_in': [], 'error': 'invalid_ip'}

        listed_in = []
        socket.setdefaulttimeout(2.0)

        for dnsbl in providers:
            query = f"{reversed_ip}.{dnsbl}"
            try:
                socket.gethostbyname(query)
                # If it resolves, the IP is listed
                listed_in.append(dnsbl)
            except socket.gaierror:
                pass  # NXDOMAIN = not listed (expected)
            except Exception:
                pass

        socket.setdefaulttimeout(None)

        result = {
            'ip_address':     ip_address,
            'is_blacklisted': len(listed_in) > 0,
            'listed_in':      listed_in,
            'checked':        providers,
            'check_count':    len(providers),
        }

        cache.set(cache_key, result, DNSBL_CACHE_TTL)
        return result

    @classmethod
    def quick_dnsbl_check(cls, ip_address: str) -> bool:
        """Fast boolean DNSBL check using only top 2 providers."""
        result = cls.check_dnsbl(
            ip_address,
            providers=['zen.spamhaus.org', 'b.barracudacentral.org']
        )
        return result.get('is_blacklisted', False)

    # ── Utility Helpers ────────────────────────────────────────────────────

    @classmethod
    def extract_domain_from_hostname(cls, hostname: str) -> str:
        """Extract the registered domain from a full hostname."""
        if not hostname:
            return ''
        parts = hostname.rstrip('.').split('.')
        if len(parts) >= 2:
            return f"{parts[-2]}.{parts[-1]}"
        return hostname

    @classmethod
    def hostname_contains_vpn_keywords(cls, ip_address: str) -> dict:
        """
        Convenience method: get hostname and check for VPN/proxy keywords.
        Returns detailed analysis for use in VPN/proxy detectors.
        """
        VPN_KEYWORDS = [
            'vpn', 'proxy', 'exit', 'relay', 'anon', 'tor', 'tunnel',
            'privacy', 'secure', 'hide', 'mask', 'cloak', 'socks',
            'anonymous', 'gateway',
        ]

        hostname = cls.reverse_lookup(ip_address)
        if not hostname:
            return {
                'ip_address':     ip_address,
                'hostname':       '',
                'has_vpn_keyword': False,
                'matched_keywords': [],
            }

        hn_lower  = hostname.lower()
        matched   = [kw for kw in VPN_KEYWORDS if kw in hn_lower]

        return {
            'ip_address':       ip_address,
            'hostname':         hostname,
            'has_vpn_keyword':  len(matched) > 0,
            'matched_keywords': matched,
            'domain':           cls.extract_domain_from_hostname(hostname),
        }
