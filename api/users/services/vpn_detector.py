# api/users/services/vpn_detector.py

import requests
from django.conf import settings
from django.core.cache import cache
import ipaddress


class VPNDetectorService:
    """
    Advanced VPN/Proxy/Tor detection service
    Uses multiple detection methods for accuracy
    """
    
    # Free VPN detection APIs
    PROXYCHECK_API = "https://proxycheck.io/v2/"
    IPQUALITYSCORE_API = "https://ipqualityscore.com/api/json/ip"
    VPNAPI_API = "https://vpnapi.io/api/"
    
    # Known VPN/Datacenter IP ranges (example list - expand as needed)
    DATACENTER_ASNS = [
        'AS16509',  # Amazon AWS
        'AS14618',  # Amazon AWS
        'AS15169',  # Google Cloud
        'AS8075',   # Microsoft Azure
        'AS20473',  # Choopa (Vultr)
        'AS14061',  # DigitalOcean
        'AS63949',  # Linode
    ]
    
    def __init__(self):
        # API keys from settings (optional - many APIs have free tiers)
        self.proxycheck_key = getattr(settings, 'PROXYCHECK_API_KEY', None)
        self.ipqs_key = getattr(settings, 'IPQUALITYSCORE_API_KEY', None)
        self.vpnapi_key = getattr(settings, 'VPNAPI_KEY', None)
    
    def detect_vpn(self, ip_address):
        """
        Main detection method - combines multiple checks
        Returns: {
            'is_vpn': bool,
            'is_proxy': bool,
            'is_tor': bool,
            'is_datacenter': bool,
            'confidence': int (0-100),
            'details': dict
        }
        """
        # Check cache first
        cache_key = f"vpn_check_{ip_address}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        result = {
            'is_vpn': False,
            'is_proxy': False,
            'is_tor': False,
            'is_datacenter': False,
            'confidence': 0,
            'details': {}
        }
        
        try:
            # Method 1: ProxyCheck.io (Free tier: 1000 queries/day)
            proxycheck_result = self._check_proxycheck(ip_address)
            if proxycheck_result:
                result['is_proxy'] = proxycheck_result.get('proxy', False)
                result['is_vpn'] = proxycheck_result.get('vpn', False)
                result['details']['proxycheck'] = proxycheck_result
            
            # Method 2: IP Quality Score (if API key available)
            if self.ipqs_key:
                ipqs_result = self._check_ipqualityscore(ip_address)
                if ipqs_result:
                    result['is_vpn'] = result['is_vpn'] or ipqs_result.get('vpn', False)
                    result['is_proxy'] = result['is_proxy'] or ipqs_result.get('proxy', False)
                    result['is_tor'] = ipqs_result.get('tor', False)
                    result['details']['ipqualityscore'] = ipqs_result
            
            # Method 3: VPN API (if API key available)
            if self.vpnapi_key:
                vpnapi_result = self._check_vpnapi(ip_address)
                if vpnapi_result:
                    result['is_vpn'] = result['is_vpn'] or vpnapi_result.get('vpn', False)
                    result['details']['vpnapi'] = vpnapi_result
            
            # Method 4: Check if IP is from known datacenter
            datacenter_check = self._check_datacenter_ip(ip_address)
            if datacenter_check:
                result['is_datacenter'] = True
                result['details']['datacenter'] = datacenter_check
            
            # Calculate confidence score
            result['confidence'] = self._calculate_confidence(result)
            
            # Cache result for 1 hour
            cache.set(cache_key, result, 3600)
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def _check_proxycheck(self, ip_address):
        """
        Check using ProxyCheck.io API
        Free tier: 1000 queries/day, no API key needed
        """
        try:
            url = f"{self.PROXYCHECK_API}{ip_address}"
            params = {
                'vpn': 1,  # Check for VPN
                'asn': 1,  # Get ASN info
            }
            
            if self.proxycheck_key:
                params['key'] = self.proxycheck_key
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if ip_address in data:
                    ip_data = data[ip_address]
                    return {
                        'proxy': ip_data.get('proxy') == 'yes',
                        'vpn': ip_data.get('type') == 'VPN',
                        'asn': ip_data.get('asn'),
                        'provider': ip_data.get('provider'),
                        'country': ip_data.get('country'),
                    }
        except Exception as e:
            print(f"ProxyCheck error: {e}")
        
        return None
    
    def _check_ipqualityscore(self, ip_address):
        """
        Check using IPQualityScore API
        Requires API key (free tier available)
        """
        if not self.ipqs_key:
            return None
        
        try:
            url = f"{self.IPQUALITYSCORE_API}/{self.ipqs_key}/{ip_address}"
            params = {
                'strictness': 1,  # 0-3, higher = more strict
                'allow_public_access_points': 'false',
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'vpn': data.get('vpn', False),
                    'proxy': data.get('proxy', False),
                    'tor': data.get('tor', False),
                    'fraud_score': data.get('fraud_score', 0),
                    'isp': data.get('ISP'),
                    'asn': data.get('ASN'),
                }
        except Exception as e:
            print(f"IPQualityScore error: {e}")
        
        return None
    
    def _check_vpnapi(self, ip_address):
        """
        Check using VPNAPI.io
        Free tier: 1000 requests/day
        """
        try:
            url = f"{self.VPNAPI_API}{ip_address}"
            params = {}
            
            if self.vpnapi_key:
                params['key'] = self.vpnapi_key
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                security = data.get('security', {})
                return {
                    'vpn': security.get('vpn', False),
                    'proxy': security.get('proxy', False),
                    'tor': security.get('tor', False),
                    'relay': security.get('relay', False),
                }
        except Exception as e:
            print(f"VPNAPI error: {e}")
        
        return None
    
    def _check_datacenter_ip(self, ip_address):
        """
        Check if IP belongs to known datacenter/hosting provider
        This is a simple heuristic - datacenter IPs often indicate VPN/proxy
        """
        # This is a simplified version
        # In production, you'd use a comprehensive datacenter IP database
        
        # Example: Check if IP is in AWS range
        # You can expand this with actual IP ranges
        
        try:
            # Convert to IP object
            ip = ipaddress.ip_address(ip_address)
            
            # Check against known datacenter ranges
            # Example AWS ranges (very limited - expand in production)
            datacenter_ranges = [
                ipaddress.ip_network('54.0.0.0/8'),      # AWS
                ipaddress.ip_network('52.0.0.0/8'),      # AWS
                ipaddress.ip_network('35.0.0.0/8'),      # Google Cloud
                ipaddress.ip_network('34.0.0.0/8'),      # Google Cloud
                ipaddress.ip_network('13.64.0.0/11'),    # Azure
                ipaddress.ip_network('104.40.0.0/13'),   # Azure
            ]
            
            for network in datacenter_ranges:
                if ip in network:
                    return {
                        'is_datacenter': True,
                        'network': str(network),
                    }
            
        except Exception as e:
            print(f"Datacenter check error: {e}")
        
        return None
    
    def _calculate_confidence(self, result):
        """
        Calculate confidence score (0-100) based on detection results
        """
        confidence = 0
        
        # Multiple sources agreeing increases confidence
        detection_count = sum([
            result.get('is_vpn', False),
            result.get('is_proxy', False),
            result.get('is_tor', False),
            result.get('is_datacenter', False),
        ])
        
        # Check how many APIs confirmed
        api_confirmations = len([
            d for d in result.get('details', {}).values()
            if isinstance(d, dict) and (d.get('vpn') or d.get('proxy'))
        ])
        
        # Base confidence on detections
        if detection_count >= 3:
            confidence = 95
        elif detection_count == 2:
            confidence = 80
        elif detection_count == 1:
            confidence = 60
        
        # Boost confidence if multiple APIs agree
        if api_confirmations >= 2:
            confidence = min(100, confidence + 10)
        
        return confidence
    
    def is_suspicious_ip(self, ip_address):
        """
        Quick check if IP is suspicious (VPN/Proxy/Tor)
        Returns True if confidence >= 60%
        """
        result = self.detect_vpn(ip_address)
        return (
            result.get('is_vpn') or 
            result.get('is_proxy') or 
            result.get('is_tor')
        ) and result.get('confidence', 0) >= 60


# Singleton instance
vpn_detector = VPNDetectorService()