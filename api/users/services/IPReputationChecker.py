"""
IP Reputation & VPN/Proxy Detection System
Detects suspicious IPs, VPNs, proxies, and maintains IP reputation database
"""
import requests
import logging
import ipaddress
from typing import Dict, Tuple, List, Optional
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


class IPReputationChecker:
    """
    IP reputation checking and VPN/Proxy detection
    
    Features:
    - VPN detection
    - Proxy detection
    - Tor network detection
    - Datacenter IP detection
    - IP geolocation
    - IP blacklist checking
    - Reputation scoring
    """
    
    CACHE_PREFIX = 'ip_rep:'
    CACHE_TIMEOUT = 3600 * 24  # 24 hours
    
    # External API endpoints (you can configure these)
    IPQUALITYSCORE_API_KEY = None  # Set in settings
    PROXYCHECK_API_KEY = None
    IPHUB_API_KEY = None
    
    # Thresholds
    FRAUD_SCORE_HIGH = 75
    FRAUD_SCORE_MEDIUM = 50
    FRAUD_SCORE_LOW = 25
    
    # Private/Reserved IP ranges
    PRIVATE_IP_RANGES = [
        '10.0.0.0/8',
        '172.16.0.0/12',
        '192.168.0.0/16',
        '127.0.0.0/8',
        '169.254.0.0/16',
        '::1/128',
        'fe80::/10',
        'fc00::/7',
    ]
    
    def __init__(self, ip_address: str = None):
        """
        Initialize IP reputation checker
        
        Args:
            ip_address: IP address to check
        """
        self.ip_address = ip_address
        self.reputation_data = {}
    
    def is_private_ip(self, ip: str = None) -> bool:
        """
        Check if IP is private/internal
        
        Args:
            ip: IP address (optional, uses self.ip_address if not provided)
        
        Returns:
            True if private IP
        """
        ip = ip or self.ip_address
        
        if not ip:
            return False
        
        try:
            ip_obj = ipaddress.ip_address(ip)
            
            # Check if private
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                return True
            
            # Check against custom ranges
            for range_str in self.PRIVATE_IP_RANGES:
                if ip_obj in ipaddress.ip_network(range_str, strict=False):
                    return True
            
            return False
        
        except ValueError:
            logger.error(f"Invalid IP address: {ip}")
            return False
    
    def check_cached_reputation(self, ip: str) -> Optional[Dict]:
        """
        Check if IP reputation is cached
        
        Args:
            ip: IP address
        
        Returns:
            Cached reputation data or None
        """
        cache_key = f"{self.CACHE_PREFIX}{ip}"
        return cache.get(cache_key)
    
    def cache_reputation(self, ip: str, reputation_data: Dict) -> None:
        """
        Cache IP reputation data
        
        Args:
            ip: IP address
            reputation_data: Reputation data to cache
        """
        cache_key = f"{self.CACHE_PREFIX}{ip}"
        cache.set(cache_key, reputation_data, self.CACHE_TIMEOUT)
    
    def check_database_reputation(self, ip: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check IP reputation in database
        
        Args:
            ip: IP address
        
        Returns:
            Tuple of (exists: bool, reputation_data: dict)
        """
        from api.fraud_detection.models import IPReputation
        
        try:
            ip_rep = IPReputation.objects.get(ip_address=ip)
            
            reputation_data = {
                'fraud_score': ip_rep.fraud_score,
                'spam_score': ip_rep.spam_score,
                'is_blacklisted': ip_rep.is_blacklisted,
                'is_vpn': 'vpn' in ip_rep.threat_types,
                'is_proxy': 'proxy' in ip_rep.threat_types,
                'is_tor': 'tor' in ip_rep.threat_types,
                'is_datacenter': 'datacenter' in ip_rep.threat_types,
                'country': ip_rep.country,
                'region': ip_rep.region,
                'city': ip_rep.city,
                'isp': ip_rep.isp,
                'threat_types': ip_rep.threat_types,
                'last_checked': ip_rep.last_threat_check,
            }
            
            return True, reputation_data
        
        except IPReputation.DoesNotExist:
            return False, None
    
    def check_with_ipqualityscore(self, ip: str) -> Dict:
        """
        Check IP with IPQualityScore API
        
        Args:
            ip: IP address
        
        Returns:
            Reputation data from IPQualityScore
        """
        if not self.IPQUALITYSCORE_API_KEY:
            return {}
        
        try:
            url = f"https://ipqualityscore.com/api/json/ip/{self.IPQUALITYSCORE_API_KEY}/{ip}"
            params = {
                'strictness': 1,
                'allow_public_access_points': 'true',
                'fast': 'true',
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                return {
                    'fraud_score': data.get('fraud_score', 0),
                    'is_vpn': data.get('vpn', False),
                    'is_proxy': data.get('proxy', False),
                    'is_tor': data.get('tor', False),
                    'is_bot': data.get('bot_status', False),
                    'recent_abuse': data.get('recent_abuse', False),
                    'country_code': data.get('country_code', ''),
                    'region': data.get('region', ''),
                    'city': data.get('city', ''),
                    'isp': data.get('ISP', ''),
                    'connection_type': data.get('connection_type', ''),
                    'abuse_velocity': data.get('abuse_velocity', ''),
                }
            
        except Exception as e:
            logger.error(f"IPQualityScore API error: {e}")
        
        return {}
    
    def check_with_proxycheck(self, ip: str) -> Dict:
        """
        Check IP with ProxyCheck.io API
        
        Args:
            ip: IP address
        
        Returns:
            Reputation data from ProxyCheck
        """
        if not self.PROXYCHECK_API_KEY:
            return {}
        
        try:
            url = f"https://proxycheck.io/v2/{ip}"
            params = {
                'key': self.PROXYCHECK_API_KEY,
                'vpn': 1,
                'asn': 1,
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                ip_data = data.get(ip, {})
                
                return {
                    'is_proxy': ip_data.get('proxy') == 'yes',
                    'proxy_type': ip_data.get('type', ''),
                    'country': ip_data.get('country', ''),
                    'isp': ip_data.get('provider', ''),
                    'risk_score': int(ip_data.get('risk', 0)),
                }
            
        except Exception as e:
            logger.error(f"ProxyCheck API error: {e}")
        
        return {}
    
    def check_with_iphub(self, ip: str) -> Dict:
        """
        Check IP with IPHub API
        
        Args:
            ip: IP address
        
        Returns:
            Reputation data from IPHub
        """
        if not self.IPHUB_API_KEY:
            return {}
        
        try:
            url = f"http://v2.api.iphub.info/ip/{ip}"
            headers = {'X-Key': self.IPHUB_API_KEY}
            
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                block = data.get('block', 0)
                
                return {
                    'is_proxy': block == 1,
                    'is_datacenter': block == 2,
                    'country_code': data.get('countryCode', ''),
                    'country_name': data.get('countryName', ''),
                    'isp': data.get('isp', ''),
                    'hostname': data.get('hostname', ''),
                }
            
        except Exception as e:
            logger.error(f"IPHub API error: {e}")
        
        return {}
    
    def perform_comprehensive_check(self, ip: str) -> Dict:
        """
        Perform comprehensive IP reputation check using multiple sources
        
        Args:
            ip: IP address
        
        Returns:
            Comprehensive reputation data
        """
        # Check if private IP
        if self.is_private_ip(ip):
            return {
                'is_private': True,
                'fraud_score': 0,
                'is_vpn': False,
                'is_proxy': False,
                'is_tor': False,
                'is_safe': True,
            }
        
        # Check cache first
        cached = self.check_cached_reputation(ip)
        if cached:
            logger.info(f"Using cached reputation for {ip}")
            return cached
        
        # Check database
        exists, db_data = self.check_database_reputation(ip)
        if exists:
            # Check if data is recent (less than 24 hours old)
            if db_data.get('last_checked'):
                age = timezone.now() - db_data['last_checked']
                if age < timedelta(hours=24):
                    self.cache_reputation(ip, db_data)
                    return db_data
        
        # Fetch from external APIs
        logger.info(f"Fetching fresh reputation data for {ip}")
        
        results = {}
        
        # Try multiple APIs
        ipqs_data = self.check_with_ipqualityscore(ip)
        proxy_data = self.check_with_proxycheck(ip)
        iphub_data = self.check_with_iphub(ip)
        
        # Merge results
        fraud_scores = []
        
        if ipqs_data:
            fraud_scores.append(ipqs_data.get('fraud_score', 0))
        if proxy_data:
            fraud_scores.append(proxy_data.get('risk_score', 0))
        
        # Calculate average fraud score
        fraud_score = sum(fraud_scores) / len(fraud_scores) if fraud_scores else 0
        
        # Determine VPN/Proxy status (if ANY service detects it)
        is_vpn = (
            ipqs_data.get('is_vpn', False) or
            False  # Add other checks
        )
        
        is_proxy = (
            ipqs_data.get('is_proxy', False) or
            proxy_data.get('is_proxy', False) or
            iphub_data.get('is_proxy', False)
        )
        
        is_tor = ipqs_data.get('is_tor', False)
        is_datacenter = iphub_data.get('is_datacenter', False)
        
        # Compile comprehensive data
        comprehensive_data = {
            'ip_address': ip,
            'fraud_score': int(fraud_score),
            'is_vpn': is_vpn,
            'is_proxy': is_proxy,
            'is_tor': is_tor,
            'is_datacenter': is_datacenter,
            'is_bot': ipqs_data.get('is_bot', False),
            'country': (
                ipqs_data.get('country_code') or
                proxy_data.get('country') or
                iphub_data.get('country_code') or
                ''
            ),
            'region': ipqs_data.get('region', ''),
            'city': ipqs_data.get('city', ''),
            'isp': (
                ipqs_data.get('isp') or
                proxy_data.get('isp') or
                iphub_data.get('isp') or
                ''
            ),
            'connection_type': ipqs_data.get('connection_type', ''),
            'threat_types': self._compile_threat_types(
                is_vpn, is_proxy, is_tor, is_datacenter
            ),
            'is_safe': self._calculate_safety(fraud_score, is_vpn, is_proxy, is_tor),
            'checked_at': timezone.now(),
        }
        
        # Save to database
        self._save_to_database(comprehensive_data)
        
        # Cache results
        self.cache_reputation(ip, comprehensive_data)
        
        return comprehensive_data
    
    def _compile_threat_types(
        self, 
        is_vpn: bool, 
        is_proxy: bool, 
        is_tor: bool, 
        is_datacenter: bool
    ) -> List[str]:
        """Compile list of threat types"""
        threats = []
        
        if is_vpn:
            threats.append('vpn')
        if is_proxy:
            threats.append('proxy')
        if is_tor:
            threats.append('tor')
        if is_datacenter:
            threats.append('datacenter')
        
        return threats
    
    def _calculate_safety(
        self, 
        fraud_score: int, 
        is_vpn: bool, 
        is_proxy: bool, 
        is_tor: bool
    ) -> bool:
        """Calculate if IP is safe to allow"""
        if fraud_score >= self.FRAUD_SCORE_HIGH:
            return False
        
        if is_vpn or is_proxy or is_tor:
            return False
        
        return True
    
    def _save_to_database(self, reputation_data: Dict) -> None:
        """
        Save reputation data to database
        
        Args:
            reputation_data: Reputation data to save
        """
        from api.fraud_detection.models import IPReputation
        
        try:
            IPReputation.objects.update_or_create(
                ip_address=reputation_data['ip_address'],
                defaults={
                    'fraud_score': reputation_data['fraud_score'],
                    'spam_score': 0,  # Can be added if available
                    'is_blacklisted': not reputation_data['is_safe'],
                    'country': reputation_data['country'],
                    'region': reputation_data.get('region', ''),
                    'city': reputation_data.get('city', ''),
                    'isp': reputation_data['isp'],
                    'threat_types': reputation_data['threat_types'],
                    'last_threat_check': timezone.now(),
                }
            )
            
            logger.info(f"IP reputation saved: {reputation_data['ip_address']}")
        
        except Exception as e:
            logger.error(f"Error saving IP reputation: {e}")
    
    def check_ip_for_registration(self, ip: str, strict_mode: bool = True) -> Tuple[bool, str, Dict]:
        """
        Check if IP is allowed for registration
        
        Args:
            ip: IP address
            strict_mode: If True, blocks VPNs and high-risk IPs
        
        Returns:
            Tuple of (is_allowed: bool, reason: str, details: dict)
        """
        # Check if private IP (allow local development)
        if self.is_private_ip(ip):
            return True, 'PRIVATE_IP', {'is_private': True}
        
        # Perform comprehensive check
        reputation = self.perform_comprehensive_check(ip)
        
        # Check blacklist
        if reputation.get('is_blacklisted', False):
            return False, 'IP_BLACKLISTED', {
                'ip': ip,
                'message': 'This IP address has been blacklisted due to suspicious activity.'
            }
        
        # Strict mode checks
        if strict_mode:
            # Check VPN
            if reputation.get('is_vpn', False):
                return False, 'VPN_DETECTED', {
                    'ip': ip,
                    'message': 'VPN usage is not allowed during registration.'
                }
            
            # Check Proxy
            if reputation.get('is_proxy', False):
                return False, 'PROXY_DETECTED', {
                    'ip': ip,
                    'message': 'Proxy usage is not allowed during registration.'
                }
            
            # Check Tor
            if reputation.get('is_tor', False):
                return False, 'TOR_DETECTED', {
                    'ip': ip,
                    'message': 'Tor network usage is not allowed during registration.'
                }
            
            # Check fraud score
            fraud_score = reputation.get('fraud_score', 0)
            
            if fraud_score >= self.FRAUD_SCORE_HIGH:
                return False, 'HIGH_FRAUD_SCORE', {
                    'ip': ip,
                    'fraud_score': fraud_score,
                    'message': f'This IP has a high fraud score ({fraud_score}/100).'
                }
        
        # IP is safe
        return True, 'IP_ALLOWED', {
            'ip': ip,
            'fraud_score': reputation.get('fraud_score', 0),
            'country': reputation.get('country', ''),
            'is_safe': reputation.get('is_safe', True),
        }
    
    def get_ip_risk_level(self, ip: str) -> str:
        """
        Get risk level for IP
        
        Args:
            ip: IP address
        
        Returns:
            Risk level: 'low', 'medium', 'high', or 'critical'
        """
        reputation = self.perform_comprehensive_check(ip)
        
        fraud_score = reputation.get('fraud_score', 0)
        is_vpn = reputation.get('is_vpn', False)
        is_proxy = reputation.get('is_proxy', False)
        is_tor = reputation.get('is_tor', False)
        
        # Critical risk
        if is_tor or fraud_score >= self.FRAUD_SCORE_HIGH:
            return 'critical'
        
        # High risk
        if is_vpn or is_proxy or fraud_score >= self.FRAUD_SCORE_MEDIUM:
            return 'high'
        
        # Medium risk
        if fraud_score >= self.FRAUD_SCORE_LOW:
            return 'medium'
        
        # Low risk
        return 'low'
    
    def blacklist_ip(self, ip: str, reason: str = '') -> bool:
        """
        Add IP to blacklist
        
        Args:
            ip: IP address to blacklist
            reason: Reason for blacklisting
        
        Returns:
            Success status
        """
        from api.fraud_detection.models import IPReputation
        
        try:
            ip_rep, created = IPReputation.objects.update_or_create(
                ip_address=ip,
                defaults={
                    'is_blacklisted': True,
                    'blacklist_reason': reason,
                    'blacklisted_at': timezone.now(),
                    'fraud_score': 100,
                }
            )
            
            # Clear cache
            cache_key = f"{self.CACHE_PREFIX}{ip}"
            cache.delete(cache_key)
            
            logger.warning(f"IP blacklisted: {ip} - Reason: {reason}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error blacklisting IP: {e}")
            return False
    
    def whitelist_ip(self, ip: str) -> bool:
        """
        Remove IP from blacklist
        
        Args:
            ip: IP address to whitelist
        
        Returns:
            Success status
        """
        from api.fraud_detection.models import IPReputation
        
        try:
            IPReputation.objects.filter(ip_address=ip).update(
                is_blacklisted=False,
                blacklist_reason='',
                blacklisted_at=None,
            )
            
            # Clear cache
            cache_key = f"{self.CACHE_PREFIX}{ip}"
            cache.delete(cache_key)
            
            logger.info(f"IP whitelisted: {ip}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error whitelisting IP: {e}")
            return False