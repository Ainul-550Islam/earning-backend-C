from .BaseDetector import BaseDetector
import ipaddress
import requests
import socket
import json
import logging
from typing import Dict, List, Any, Optional
from django.core.cache import cache
from django.conf import settings
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class VPNProxyDetector(BaseDetector):
    """
    Detects VPN, Proxy, TOR, and other anonymous network usage
    Integrates with multiple threat intelligence APIs
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        
        # Configuration
        self.api_config = {
            'ipqualityscore': {
                'enabled': config.get('ipqualityscore_enabled', True) if config else True,
                'api_key': config.get('ipqualityscore_key', '') if config else '',
                'url': 'https://ipqualityscore.com/api/json/ip'
            },
            'vpnapi': {
                'enabled': config.get('vpnapi_enabled', True) if config else True,
                'api_key': config.get('vpnapi_key', '') if config else '',
                'url': 'https://vpnapi.io/api'
            },
            'iphub': {
                'enabled': config.get('iphub_enabled', False) if config else False,
                'api_key': config.get('iphub_key', '') if config else '',
                'url': 'https://v2.api.iphub.info/ip'
            }
        }
        
        # Local detection methods
        self.use_local_detection = config.get('use_local_detection', True) if config else True
        
        # Risk thresholds
        self.vpn_risk_score = config.get('vpn_risk_score', 40) if config else 40
        self.proxy_risk_score = config.get('proxy_risk_score', 35) if config else 35
        self.tor_risk_score = config.get('tor_risk_score', 50) if config else 50
        self.hosting_risk_score = config.get('hosting_risk_score', 25) if config else 25
        
    def get_required_fields(self) -> List[str]:
        return ['ip_address']
    
    def detect(self, data: Dict) -> Dict:
        """
        Detect VPN/Proxy/TOR usage
        """
        try:
            ip_address = data.get('ip_address')
            user_id = data.get('user_id')
            
            if not self.validate_data(data):
                return self.get_detection_result()
            
            # Check cache first
            cache_key = f"vpn_detection:{ip_address}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                logger.info(f"Using cached VPN detection result for {ip_address}")
                self._process_cached_result(cached_result)
            else:
                # Perform fresh detection
                detection_results = self._perform_detection(ip_address)
                
                # Cache result for 1 hour
                cache.set(cache_key, detection_results, 3600)
                
                # Process results
                self._process_detection_results(detection_results)
            
            # Set detection result
            self.detected_fraud = self.fraud_score >= 60
            
            # Calculate confidence
            self.confidence = self._calculate_detection_confidence()
            
            # Log detection
            self.log_detection(user_id)
            
            return self.get_detection_result()
            
        except Exception as e:
            logger.error(f"Error in VPNProxyDetector: {str(e)}")
            return {
                'detector': self.detector_name,
                'is_fraud': False,
                'fraud_score': 0,
                'confidence': 0,
                'error': str(e)
            }
    
    def _perform_detection(self, ip_address: str) -> Dict:
        """
        Perform detection using multiple methods
        """
        results = {
            'ip_address': ip_address,
            'detection_timestamp': datetime.now().isoformat(),
            'methods_used': [],
            'results': {}
        }
        
        # 1. Basic IP validation
        basic_checks = self._perform_basic_checks(ip_address)
        results['results']['basic_checks'] = basic_checks
        results['methods_used'].append('basic_checks')
        
        # 2. Local database/rule checks
        if self.use_local_detection:
            local_checks = self._perform_local_checks(ip_address)
            results['results']['local_checks'] = local_checks
            results['methods_used'].append('local_checks')
        
        # 3. API-based detection
        api_results = self._perform_api_checks(ip_address)
        results['results']['api_checks'] = api_results
        results['methods_used'].extend(api_results.get('methods_used', []))
        
        # 4. Network analysis
        network_analysis = self._perform_network_analysis(ip_address)
        results['results']['network_analysis'] = network_analysis
        results['methods_used'].append('network_analysis')
        
        # 5. Threat intelligence lookup
        threat_intel = self._check_threat_intelligence(ip_address)
        results['results']['threat_intelligence'] = threat_intel
        results['methods_used'].append('threat_intelligence')
        
        return results
    
    def _perform_basic_checks(self, ip_address: str) -> Dict:
        """
        Perform basic IP address checks
        """
        try:
            result = {
                'is_valid': False,
                'is_private': False,
                'is_reserved': False,
                'is_loopback': False,
                'ip_version': None,
                'risk_score': 0,
                'issues': []
            }
            
            # Validate IP address
            try:
                ip_obj = ipaddress.ip_address(ip_address)
                result['is_valid'] = True
                result['ip_version'] = ip_obj.version
                
                # Check IP type
                result['is_private'] = ip_obj.is_private
                result['is_reserved'] = ip_obj.is_reserved
                result['is_loopback'] = ip_obj.is_loopback
                result['is_multicast'] = ip_obj.is_multicast
                result['is_unspecified'] = ip_obj.is_unspecified
                
                # Risk assessment
                if result['is_private']:
                    result['risk_score'] += 30
                    result['issues'].append('Private IP address')
                
                if result['is_loopback']:
                    result['risk_score'] += 50
                    result['issues'].append('Loopback IP address')
                
                if result['is_reserved']:
                    result['risk_score'] += 20
                    result['issues'].append('Reserved IP address')
                
                if result['is_multicast']:
                    result['risk_score'] += 10
                    result['issues'].append('Multicast IP address')
                
                # Check for common VPN/Proxy IP ranges
                if self._is_vpn_ip_range(ip_address):
                    result['risk_score'] += 40
                    result['issues'].append('IP belongs to known VPN range')
                
            except ValueError:
                result['is_valid'] = False
                result['issues'].append('Invalid IP address format')
                result['risk_score'] = 100
            
            result['risk_score'] = min(100, result['risk_score'])
            
            return result
            
        except Exception as e:
            logger.error(f"Error in basic checks: {e}")
            return {'error': str(e), 'risk_score': 0}
    
    def _perform_local_checks(self, ip_address: str) -> Dict:
        """
        Check against local database/blocklists
        """
        result = {
            'in_local_blocklist': False,
            'local_vpn_detected': False,
            'local_proxy_detected': False,
            'local_tor_detected': False,
            'risk_score': 0,
            'detections': []
        }
        
        try:
            # Check local VPN IP database
            from ..models import IPReputation
            
            ip_reputation = IPReputation.objects.filter(ip_address=ip_address).first()
            
            if ip_reputation:
                result['reputation_score'] = ip_reputation.fraud_score
                result['is_blacklisted'] = ip_reputation.is_blacklisted
                result['threat_types'] = ip_reputation.threat_types
                
                if ip_reputation.is_blacklisted:
                    result['in_local_blocklist'] = True
                    result['risk_score'] += 50
                    result['detections'].append(f"IP blacklisted: {ip_reputation.blacklist_reason}")
                
                if 'vpn' in ip_reputation.threat_types:
                    result['local_vpn_detected'] = True
                    result['risk_score'] += self.vpn_risk_score
                    result['detections'].append('VPN detected in local database')
                
                if 'proxy' in ip_reputation.threat_types:
                    result['local_proxy_detected'] = True
                    result['risk_score'] += self.proxy_risk_score
                    result['detections'].append('Proxy detected in local database')
                
                if 'tor' in ip_reputation.threat_types:
                    result['local_tor_detected'] = True
                    result['risk_score'] += self.tor_risk_score
                    result['detections'].append('TOR detected in local database')
            
            # Check common VPN ASNs (Autonomous System Numbers)
            common_vpn_asns = [
                'AS396982', 'AS60781', 'AS60068', 'AS209242',  # NordVPN
                'AS36351', 'AS16276', 'AS14061',               # ExpressVPN
                'AS43350',                                     # PureVPN
                'AS199524',                                    # Surfshark
                'AS212238',                                    # Windscribe
                'AS397331', 'AS202425'                         # PIA
            ]
            
            # This would require ASN lookup service
            # For now, we'll check against known VPN IP ranges
            
            result['risk_score'] = min(100, result['risk_score'])
            
            return result
            
        except Exception as e:
            logger.error(f"Error in local checks: {e}")
            return {'error': str(e), 'risk_score': 0}
    
    def _perform_api_checks(self, ip_address: str) -> Dict:
        """
        Perform API-based VPN/Proxy detection
        """
        result = {
            'methods_used': [],
            'api_results': {},
            'consensus_score': 0,
            'risk_score': 0
        }
        
        api_detections = []
        
        # IPQualityScore API
        if self.api_config['ipqualityscore']['enabled']:
            ipqs_result = self._check_ipqualityscore(ip_address)
            if ipqs_result:
                result['api_results']['ipqualityscore'] = ipqs_result
                result['methods_used'].append('ipqualityscore')
                api_detections.append(ipqs_result)
        
        # VPN API
        if self.api_config['vpnapi']['enabled']:
            vpnapi_result = self._check_vpnapi(ip_address)
            if vpnapi_result:
                result['api_results']['vpnapi'] = vpnapi_result
                result['methods_used'].append('vpnapi')
                api_detections.append(vpnapi_result)
        
        # IPHub API
        if self.api_config['iphub']['enabled']:
            iphub_result = self._check_iphub(ip_address)
            if iphub_result:
                result['api_results']['iphub'] = iphub_result
                result['methods_used'].append('iphub')
                api_detections.append(iphub_result)
        
        # Calculate consensus
        if api_detections:
            result['consensus_score'] = self._calculate_consensus(api_detections)
            result['risk_score'] = result['consensus_score']
        
        return result
    
    def _check_ipqualityscore(self, ip_address: str) -> Optional[Dict]:
        """
        Check IP using IPQualityScore API
        """
        try:
            api_key = self.api_config['ipqualityscore']['api_key']
            if not api_key:
                return None
            
            url = f"{self.api_config['ipqualityscore']['url']}/{api_key}/{ip_address}"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                result = {
                    'vpn': data.get('vpn', False),
                    'proxy': data.get('proxy', False),
                    'tor': data.get('tor', False),
                    'fraud_score': data.get('fraud_score', 0),
                    'country_code': data.get('country_code', ''),
                    'region': data.get('region', ''),
                    'city': data.get('city', ''),
                    'isp': data.get('ISP', ''),
                    'organization': data.get('organization', ''),
                    'latitude': data.get('latitude', 0),
                    'longitude': data.get('longitude', 0),
                    'is_crawler': data.get('is_crawler', False),
                    'recent_abuse': data.get('recent_abuse', False),
                    'bot_status': data.get('bot_status', False),
                    'connection_type': data.get('connection_type', ''),
                    'abuse_velocity': data.get('abuse_velocity', '')
                }
                
                # Calculate risk score
                risk_score = 0
                if result['vpn']:
                    risk_score += self.vpn_risk_score
                if result['proxy']:
                    risk_score += self.proxy_risk_score
                if result['tor']:
                    risk_score += self.tor_risk_score
                if result['fraud_score'] >= 75:
                    risk_score += result['fraud_score'] * 0.5
                if result['is_crawler']:
                    risk_score += 20
                if result['recent_abuse']:
                    risk_score += 30
                
                result['risk_score'] = min(100, risk_score)
                
                return result
            
        except Exception as e:
            logger.error(f"IPQualityScore API error: {e}")
        
        return None
    
    def _check_vpnapi(self, ip_address: str) -> Optional[Dict]:
        """
        Check IP using VPN API
        """
        try:
            api_key = self.api_config['vpnapi']['api_key']
            if not api_key:
                return None
            
            url = f"{self.api_config['vpnapi']['url']}/{ip_address}?key={api_key}"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                security = data.get('security', {})
                network = data.get('network', {})
                
                result = {
                    'vpn': security.get('vpn', False),
                    'proxy': security.get('proxy', False),
                    'tor': security.get('tor', False),
                    'relay': security.get('relay', False),
                    'is_hosting': network.get('network') == 'hosting',
                    'autonomous_system_number': network.get('autonomous_system_number', ''),
                    'autonomous_system_organization': network.get('autonomous_system_organization', ''),
                    'network': network.get('network', ''),
                    'country_code': data.get('location', {}).get('country', ''),
                    'region': data.get('location', {}).get('region', ''),
                    'city': data.get('location', {}).get('city', ''),
                    'timezone': data.get('location', {}).get('timezone', ''),
                    'latitude': data.get('location', {}).get('latitude', 0),
                    'longitude': data.get('location', {}).get('longitude', 0)
                }
                
                # Calculate risk score
                risk_score = 0
                if result['vpn']:
                    risk_score += self.vpn_risk_score
                if result['proxy']:
                    risk_score += self.proxy_risk_score
                if result['tor']:
                    risk_score += self.tor_risk_score
                if result['is_hosting']:
                    risk_score += self.hosting_risk_score
                if result['relay']:
                    risk_score += 25
                
                result['risk_score'] = min(100, risk_score)
                
                return result
            
        except Exception as e:
            logger.error(f"VPN API error: {e}")
        
        return None
    
    def _check_iphub(self, ip_address: str) -> Optional[Dict]:
        """
        Check IP using IPHub API
        """
        try:
            api_key = self.api_config['iphub']['api_key']
            if not api_key:
                return None
            
            url = self.api_config['iphub']['url']
            headers = {
                'X-Key': api_key
            }
            
            response = requests.get(f"{url}/{ip_address}", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                result = {
                    'block': data.get('block', 0),
                    'countryCode': data.get('countryCode', ''),
                    'countryName': data.get('countryName', ''),
                    'isp': data.get('isp', ''),
                    'hostname': data.get('hostname', ''),
                    'asn': data.get('asn', '')
                }
                
                # IPHub block levels:
                # 0 - Residential or business IP (i.e. safe IP)
                # 1 - Non-residential IP (hosting provider, proxy, etc.)
                # 2 - Non-residential & residential IP (warning, may flag innocent users)
                
                risk_score = 0
                if result['block'] == 1:
                    risk_score += 30
                elif result['block'] == 2:
                    risk_score += 60
                
                result['risk_score'] = min(100, risk_score)
                
                return result
            
        except Exception as e:
            logger.error(f"IPHub API error: {e}")
        
        return None
    
    def _perform_network_analysis(self, ip_address: str) -> Dict:
        """
        Perform network-level analysis
        """
        result = {
            'dns_lookups': {},
            'reverse_dns': '',
            'ping_response': False,
            'traceroute_hops': 0,
            'risk_score': 0,
            'anomalies': []
        }
        
        try:
            # Reverse DNS lookup
            try:
                hostname, aliaslist, ipaddrlist = socket.gethostbyaddr(ip_address)
                result['reverse_dns'] = hostname
                
                # Check for suspicious hostname patterns
                suspicious_patterns = ['vpn', 'proxy', 'tor', 'anonymizer', 'shield', 'guard']
                hostname_lower = hostname.lower()
                
                for pattern in suspicious_patterns:
                    if pattern in hostname_lower:
                        result['risk_score'] += 20
                        result['anomalies'].append(f"Suspicious hostname pattern: {pattern}")
                        break
                        
            except socket.herror:
                result['reverse_dns'] = 'Not found'
                result['risk_score'] += 10
                result['anomalies'].append('No reverse DNS entry')
            
            # Check for common VPN/Proxy DNS patterns
            vpn_dns_patterns = [
                '.vpn.', '.proxy.', '.tor.', '.anonymizer.',
                '.nordvpn.', '.expressvpn.', '.pia.', '.surfshark.'
            ]
            
            if result['reverse_dns']:
                for pattern in vpn_dns_patterns:
                    if pattern in result['reverse_dns'].lower():
                        result['risk_score'] += 30
                        result['anomalies'].append(f"VPN/Proxy DNS pattern detected: {pattern}")
                        break
            
            # Port scanning (limited)
            common_vpn_ports = [1194, 1723, 1701, 4500, 500, 5500]
            open_ports = []
            
            # Note: This is a simplified check
            # In production, you'd want more sophisticated port scanning
            
            result['risk_score'] = min(100, result['risk_score'])
            
            return result
            
        except Exception as e:
            logger.error(f"Network analysis error: {e}")
            return {'error': str(e), 'risk_score': 0}
    
    def _check_threat_intelligence(self, ip_address: str) -> Dict:
        """
        Check threat intelligence feeds
        """
        result = {
            'abuseipdb': {},
            'virustotal': {},
            'alienvault': {},
            'risk_score': 0,
            'threat_indicators': []
        }
        
        try:
            # AbuseIPDB check (if API key available)
            abuseipdb_key = getattr(settings, 'ABUSEIPDB_API_KEY', '')
            if abuseipdb_key:
                abuse_result = self._check_abuseipdb(ip_address, abuseipdb_key)
                if abuse_result:
                    result['abuseipdb'] = abuse_result
                    
                    if abuse_result.get('abuseConfidenceScore', 0) > 50:
                        result['risk_score'] += abuse_result['abuseConfidenceScore'] * 0.5
                        result['threat_indicators'].append('High abuse confidence score')
            
            # Check for known malware/botnet IPs
            malware_ips = self._get_malware_ip_list()
            if ip_address in malware_ips:
                result['risk_score'] += 70
                result['threat_indicators'].append('IP in malware/botnet list')
            
            # Check spam IP lists
            spam_ips = self._get_spam_ip_list()
            if ip_address in spam_ips:
                result['risk_score'] += 40
                result['threat_indicators'].append('IP in spam list')
            
            result['risk_score'] = min(100, result['risk_score'])
            
            return result
            
        except Exception as e:
            logger.error(f"Threat intelligence error: {e}")
            return {'error': str(e), 'risk_score': 0}
    
    def _calculate_consensus(self, detections: List[Dict]) -> int:
        """
        Calculate consensus score from multiple detection methods
        """
        if not detections:
            return 0
        
        risk_scores = [d.get('risk_score', 0) for d in detections]
        avg_score = sum(risk_scores) / len(risk_scores)
        
        # Weight by number of detections
        vpn_count = sum(1 for d in detections if d.get('vpn', False))
        proxy_count = sum(1 for d in detections if d.get('proxy', False))
        tor_count = sum(1 for d in detections if d.get('tor', False))
        
        consensus_multiplier = 1.0
        
        if vpn_count >= 2:
            consensus_multiplier *= 1.3
        if proxy_count >= 2:
            consensus_multiplier *= 1.2
        if tor_count >= 2:
            consensus_multiplier *= 1.5
        
        final_score = min(100, avg_score * consensus_multiplier)
        
        return int(final_score)
    
    def _process_cached_result(self, cached_result: Dict):
        """
        Process cached detection result
        """
        self._process_detection_results(cached_result)
    
    def _process_detection_results(self, results: Dict):
        """
        Process detection results and update detector state
        """
        # Process basic checks
        basic_checks = results.get('results', {}).get('basic_checks', {})
        if basic_checks.get('risk_score', 0) > 0:
            for issue in basic_checks.get('issues', []):
                self.add_reason(issue, basic_checks['risk_score'] // len(basic_checks.get('issues', [1])))
        
        # Process local checks
        local_checks = results.get('results', {}).get('local_checks', {})
        if local_checks.get('risk_score', 0) > 0:
            for detection in local_checks.get('detections', []):
                if 'VPN' in detection:
                    self.add_reason(detection, self.vpn_risk_score)
                elif 'Proxy' in detection:
                    self.add_reason(detection, self.proxy_risk_score)
                elif 'TOR' in detection:
                    self.add_reason(detection, self.tor_risk_score)
                elif 'blacklisted' in detection:
                    self.add_reason(detection, 50)
        
        # Process API checks
        api_checks = results.get('results', {}).get('api_checks', {})
        consensus_score = api_checks.get('consensus_score', 0)
        
        if consensus_score > 0:
            # Get specific detections from API results
            api_results = api_checks.get('api_results', {})
            
            vpn_detected = any(
                api.get('vpn', False) 
                for api in api_results.values() 
                if isinstance(api, dict)
            )
            
            proxy_detected = any(
                api.get('proxy', False) 
                for api in api_results.values() 
                if isinstance(api, dict)
            )
            
            tor_detected = any(
                api.get('tor', False) 
                for api in api_results.values() 
                if isinstance(api, dict)
            )
            
            if vpn_detected:
                self.add_reason("VPN detected by external APIs", self.vpn_risk_score)
            if proxy_detected:
                self.add_reason("Proxy detected by external APIs", self.proxy_risk_score)
            if tor_detected:
                self.add_reason("TOR detected by external APIs", self.tor_risk_score)
            
            # Add consensus-based reason
            if consensus_score >= 70:
                self.add_reason(f"High VPN/Proxy consensus score: {consensus_score}", 20)
        
        # Process network analysis
        network_analysis = results.get('results', {}).get('network_analysis', {})
        if network_analysis.get('risk_score', 0) > 0:
            for anomaly in network_analysis.get('anomalies', []):
                self.add_reason(anomaly, 15)
        
        # Process threat intelligence
        threat_intel = results.get('results', {}).get('threat_intelligence', {})
        if threat_intel.get('risk_score', 0) > 0:
            for indicator in threat_intel.get('threat_indicators', []):
                self.add_reason(indicator, 25)
        
        # Set fraud score as max of all risk scores
        all_scores = [
            basic_checks.get('risk_score', 0),
            local_checks.get('risk_score', 0),
            consensus_score,
            network_analysis.get('risk_score', 0),
            threat_intel.get('risk_score', 0)
        ]
        
        self.fraud_score = min(100, max(all_scores))
    
    def _calculate_detection_confidence(self) -> int:
        """
        Calculate confidence in detection
        """
        confidence_factors = []
        
        # Number of detection methods used
        methods_count = len(self.evidence.get('detection_methods', []))
        if methods_count >= 3:
            confidence_factors.append(70)
        elif methods_count >= 2:
            confidence_factors.append(50)
        else:
            confidence_factors.append(30)
        
        # Consistency of results
        vpn_detections = self.evidence.get('vpn_detections', 0)
        proxy_detections = self.evidence.get('proxy_detections', 0)
        
        if vpn_detections >= 2 or proxy_detections >= 2:
            confidence_factors.append(80)
        
        # External API confirmation
        if self.evidence.get('external_api_confirmed', False):
            confidence_factors.append(60)
        
        # Threat intelligence hits
        if self.evidence.get('threat_intel_hits', 0) > 0:
            confidence_factors.append(40)
        
        if confidence_factors:
            return min(100, int(sum(confidence_factors) / len(confidence_factors)))
        
        return 50
    
    def _is_vpn_ip_range(self, ip_address: str) -> bool:
        """
        Check if IP belongs to known VPN ranges
        """
        # Known VPN IP ranges (simplified - in production use comprehensive list)
        vpn_ranges = [
            '185.159.0.0/16',  # NordVPN
            '45.134.0.0/15',   # ExpressVPN
            '209.222.0.0/16',  # PIA
            '199.115.0.0/16',  # HideMyAss
            '82.102.0.0/15',   # CyberGhost
        ]
        
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            
            for range_str in vpn_ranges:
                network = ipaddress.ip_network(range_str)
                if ip_obj in network:
                    return True
                    
        except ValueError:
            pass
        
        return False
    
    def _check_abuseipdb(self, ip_address: str, api_key: str) -> Optional[Dict]:
        """
        Check IP on AbuseIPDB
        """
        try:
            url = f"https://api.abuseipdb.com/api/v2/check"
            headers = {
                'Key': api_key,
                'Accept': 'application/json'
            }
            params = {
                'ipAddress': ip_address,
                'maxAgeInDays': 90
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json().get('data', {})
                
                return {
                    'abuseConfidenceScore': data.get('abuseConfidenceScore', 0),
                    'countryCode': data.get('countryCode', ''),
                    'isp': data.get('isp', ''),
                    'domain': data.get('domain', ''),
                    'totalReports': data.get('totalReports', 0),
                    'lastReportedAt': data.get('lastReportedAt', ''),
                    'isWhitelisted': data.get('isWhitelisted', False)
                }
                
        except Exception as e:
            logger.error(f"AbuseIPDB API error: {e}")
        
        return None
    
    def _get_malware_ip_list(self):
        """
        Get list of known malware/botnet IPs
        """
        # In production, this would fetch from external sources
        # or use local threat intelligence database
        return set()
    
    def _get_spam_ip_list(self):
        """
        Get list of known spam IPs
        """
        # In production, this would fetch from external sources
        return set()
    
    def get_detector_config(self) -> Dict:
        base_config = super().get_detector_config()
        base_config.update({
            'description': 'Detects VPN, Proxy, TOR, and anonymous network usage',
            'version': '3.0.0',
            'apis_enabled': {
                'ipqualityscore': self.api_config['ipqualityscore']['enabled'],
                'vpnapi': self.api_config['vpnapi']['enabled'],
                'iphub': self.api_config['iphub']['enabled']
            },
            'risk_scores': {
                'vpn': self.vpn_risk_score,
                'proxy': self.proxy_risk_score,
                'tor': self.tor_risk_score,
                'hosting': self.hosting_risk_score
            }
        })
        return base_config