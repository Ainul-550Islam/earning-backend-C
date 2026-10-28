# =============================================================================
# fraud_detection/sanctions.py
# =============================================================================
"""
Sanctions and Compliance Layer for Fraud Detection System.

Provides high-risk country checking, blacklist IP validation,
and sanctions list screening for regulatory compliance.
"""

from __future__ import annotations
from typing import Union

import logging
import ipaddress
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from api.fraud_detection.encryption import encrypt_ip_address
from api.fraud_detection.exceptions import SanctionsError, ComplianceError
from api.fraud_detection.constants import CACHE_KEYS, CACHE_TTL


logger = logging.getLogger(__name__)


class SanctionsListManager:
    """
    Manager for sanctions list screening and compliance checking.
    
    Provides comprehensive sanctions screening against international
    watchlists, blocked countries, and high-risk jurisdictions.
    """
    
    def __init__(self):
        """Initialize sanctions manager with default lists."""
        self.high_risk_countries = self._load_high_risk_countries()
        self.blocked_countries = self._load_blocked_countries()
        self.sanctioned_entities = self._load_sanctioned_entities()
        self.ip_blacklists = self._load_ip_blacklists()
    
    def _load_high_risk_countries(self) -> Set[str]:
        """Load high-risk country codes from configuration."""
        # Default high-risk countries (ISO 3166-1 alpha-2 codes)
        default_countries = {
            'AF', 'IR', 'KP', 'MM', 'SD', 'SY', 'YE', 'ZW'
        }
        
        # Load from settings if available
        settings_countries = getattr(settings, 'FRAUD_HIGH_RISK_COUNTRIES', default_countries)
        return set(settings_countries)
    
    def _load_blocked_countries(self) -> Set[str]:
        """Load completely blocked country codes."""
        # Default blocked countries
        default_countries = {
            'KP', 'IR', 'SY'
        }
        
        # Load from settings if available
        settings_countries = getattr(settings, 'FRAUD_BLOCKED_COUNTRIES', default_countries)
        return set(settings_countries)
    
    def _load_sanctioned_entities(self) -> Dict[str, List[str]]:
        """Load sanctioned entities database."""
        # Simplified sanctioned entities database
        # In practice, this would connect to official sanctions databases
        default_entities = {
            'individuals': [],
            'organizations': [],
            'vessels': [],
            'aircraft': []
        }
        
        # Load from settings if available
        settings_entities = getattr(settings, 'FRAUD_SANCTIONED_ENTITIES', default_entities)
        return settings_entities
    
    def _load_ip_blacklists(self) -> List[str]:
        """Load IP address blacklists."""
        # Default IP ranges and addresses
        default_blacklists = [
            # Known malicious IP ranges (simplified)
            '192.0.2.0/24',  # TEST-NET-1
            '203.0.113.0/24',  # TEST-NET-2
        ]
        
        # Load from settings if available
        settings_blacklists = getattr(settings, 'FRAUD_IP_BLACKLISTS', default_blacklists)
        return settings_blacklists
    
    def is_country_high_risk(self, country_code: str) -> bool:
        """
        Check if country is classified as high-risk.
        
        Args:
            country_code: ISO 3166-1 alpha-2 country code
            
        Returns:
            True if country is high-risk
        """
        return country_code.upper() in self.high_risk_countries
    
    def is_country_blocked(self, country_code: str) -> bool:
        """
        Check if country is completely blocked.
        
        Args:
            country_code: ISO 3166-1 alpha-2 country code
            
        Returns:
            True if country is blocked
        """
        return country_code.upper() in self.blocked_countries
    
    def is_entity_sanctioned(self, entity_name: str, 
                           entity_type: str = 'individual') -> bool:
        """
        Check if entity is on sanctions list.
        
        Args:
            entity_name: Entity name to check
            entity_type: Type of entity (individual, organization, vessel, aircraft)
            
        Returns:
            True if entity is sanctioned
        """
        entity_list = self.sanctioned_entities.get(entity_type.lower(), [])
        
        # Simple name matching (in practice, use fuzzy matching)
        entity_upper = entity_name.upper()
        for sanctioned_name in entity_list:
            if sanctioned_name.upper() in entity_upper or entity_upper in sanctioned_name.upper():
                return True
        
        return False
    
    def is_ip_blacklisted(self, ip_address: str) -> bool:
        """
        Check if IP address is blacklisted.
        
        Args:
            ip_address: IP address to check
            
        Returns:
            True if IP is blacklisted
        """
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            
            # Check against CIDR ranges
            for blacklist_range in self.ip_blacklists:
                if '/' in blacklist_range:
                    # CIDR range
                    network = ipaddress.ip_network(blacklist_range, strict=False)
                    if ip_obj in network:
                        return True
                else:
                    # Single IP
                    if ip_obj == ipaddress.ip_address(blacklist_range):
                        return True
            
            return False
            
        except ValueError as e:
            logger.error(f"Invalid IP address format: {ip_address}, error: {e}")
            return False
    
    def get_country_risk_level(self, country_code: str) -> str:
        """
        Get risk level for country.
        
        Args:
            country_code: ISO 3166-1 alpha-2 country code
            
        Returns:
            Risk level (blocked, high, medium, low)
        """
        if self.is_country_blocked(country_code):
            return 'blocked'
        elif self.is_country_high_risk(country_code):
            return 'high'
        elif country_code in {'US', 'GB', 'CA', 'AU', 'NZ', 'JP', 'SG', 'CH'}:
            return 'low'
        else:
            return 'medium'
    
    def screen_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Screen transaction against sanctions lists.
        
        Args:
            transaction_data: Transaction data to screen
            
        Returns:
            Screening results with recommendations
        """
        screening_result = {
            'passed': True,
            'risk_level': 'low',
            'flags': [],
            'recommendations': [],
            'screening_timestamp': timezone.now().isoformat()
        }
        
        # Screen country
        country = transaction_data.get('country', '')
        if country:
            country_risk = self.get_country_risk_level(country)
            
            if country_risk == 'blocked':
                screening_result['passed'] = False
                screening_result['risk_level'] = 'critical'
                screening_result['flags'].append(f"Country {country} is blocked")
                screening_result['recommendations'].append("Block transaction immediately")
            elif country_risk == 'high':
                screening_result['risk_level'] = 'high'
                screening_result['flags'].append(f"Country {country} is high-risk")
                screening_result['recommendations'].append("Enhanced verification required")
        
        # Screen IP address
        ip_address = transaction_data.get('ip_address', '')
        if ip_address and self.is_ip_blacklisted(ip_address):
            screening_result['passed'] = False
            screening_result['risk_level'] = 'critical'
            screening_result['flags'].append(f"IP address {ip_address} is blacklisted")
            screening_result['recommendations'].append("Block transaction and investigate")
        
        # Screen entity names
        beneficiary_name = transaction_data.get('beneficiary_name', '')
        if beneficiary_name:
            if self.is_entity_sanctioned(beneficiary_name):
                screening_result['passed'] = False
                screening_result['risk_level'] = 'critical'
                screening_result['flags'].append(f"Beneficiary {beneficiary_name} is sanctioned")
                screening_result['recommendations'].append("Freeze assets and report to authorities")
        
        # Update risk level based on flags
        if screening_result['flags'] and screening_result['risk_level'] == 'low':
            screening_result['risk_level'] = 'medium'
        
        return screening_result


class IPReputationChecker:
    """
    IP reputation and threat intelligence checker.
    
    Provides comprehensive IP address analysis including
    geolocation, proxy detection, and threat intelligence.
    """
    
    def __init__(self):
        """Initialize IP reputation checker."""
        self.proxy_indicators = self._load_proxy_indicators()
        self.datacenter_ranges = self._load_datacenter_ranges()
        self.tor_exit_nodes = self._load_tor_exit_nodes()
    
    def _load_proxy_indicators(self) -> List[str]:
        """Load proxy detection indicators."""
        # User agent and header indicators for proxy usage
        indicators = [
            'proxy', 'vpn', 'anonymous', 'hidemyass',
            'nordvpn', 'expressvpn', 'cyberghost'
        ]
        return getattr(settings, 'FRAUD_PROXY_INDICATORS', indicators)
    
    def _load_datacenter_ranges(self) -> List[str]:
        """Load known datacenter IP ranges."""
        # Simplified datacenter ranges
        ranges = [
            '8.8.8.0/24',  # Google DNS (example)
            '1.1.1.0/24',  # Cloudflare DNS (example)
        ]
        return getattr(settings, 'FRAUD_DATACENTER_RANGES', ranges)
    
    def _load_tor_exit_nodes(self) -> List[str]:
        """Load Tor exit node IP addresses."""
        # In practice, this would be updated regularly from Tor project
        return getattr(settings, 'FRAUD_TOR_EXIT_NODES', [])
    
    def is_datacenter_ip(self, ip_address: str) -> bool:
        """
        Check if IP belongs to known datacenter ranges.
        
        Args:
            ip_address: IP address to check
            
        Returns:
            True if IP is from datacenter
        """
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            
            for range_str in self.datacenter_ranges:
                network = ipaddress.ip_network(range_str, strict=False)
                if ip_obj in network:
                    return True
            
            return False
            
        except ValueError:
            return False
    
    def is_tor_exit_node(self, ip_address: str) -> bool:
        """
        Check if IP is known Tor exit node.
        
        Args:
            ip_address: IP address to check
            
        Returns:
            True if IP is Tor exit node
        """
        return ip_address in self.tor_exit_nodes
    
    def is_proxy_ip(self, ip_address: str, headers: Optional[Dict[str, str]] = None) -> bool:
        """
        Check if IP indicates proxy/VPN usage.
        
        Args:
            ip_address: IP address to check
            headers: HTTP headers for additional analysis
            
        Returns:
            True if proxy/VPN detected
        """
        # Check datacenter IPs
        if self.is_datacenter_ip(ip_address):
            return True
        
        # Check headers for proxy indicators
        if headers:
            for header_name, header_value in headers.items():
                header_lower = f"{header_name}:{header_value}".lower()
                for indicator in self.proxy_indicators:
                    if indicator in header_lower:
                        return True
        
        return False
    
    def get_ip_risk_score(self, ip_address: str, 
                         headers: Optional[Dict[str, str]] = None) -> int:
        """
        Calculate comprehensive IP risk score.
        
        Args:
            ip_address: IP address to analyze
            headers: HTTP headers for additional analysis
            
        Returns:
            Risk score (0-100)
        """
        risk_score = 0
        
        # Base risk for datacenter IPs
        if self.is_datacenter_ip(ip_address):
            risk_score += 30
        
        # High risk for Tor exit nodes
        if self.is_tor_exit_node(ip_address):
            risk_score += 50
        
        # Proxy detection
        if self.is_proxy_ip(ip_address, headers):
            risk_score += 25
        
        # Check cache for previous reputation data
        cache_key = f"{CACHE_KEYS['ip_reputation']}_{ip_address}"
        cached_reputation = cache.get(cache_key)
        if cached_reputation:
            risk_score += cached_reputation.get('additional_risk', 0)
        
        return min(risk_score, 100)
    
    def analyze_ip_geolocation(self, ip_address: str) -> Dict[str, Any]:
        """
        Analyze IP geolocation and associated risks.
        
        Args:
            ip_address: IP address to analyze
            
        Returns:
            Geolocation analysis with risk assessment
        """
        # Simplified geolocation analysis
        # In practice, use services like MaxMind GeoIP2
        
        analysis = {
            'ip_address': ip_address,
            'country': 'Unknown',
            'city': 'Unknown',
            'is_datacenter': self.is_datacenter_ip(ip_address),
            'is_tor': self.is_tor_exit_node(ip_address),
            'risk_score': 0,
            'recommendations': []
        }
        
        # Calculate risk score
        analysis['risk_score'] = self.get_ip_risk_score(ip_address)
        
        # Generate recommendations
        if analysis['risk_score'] >= 70:
            analysis['recommendations'].extend([
                "Block or flag this IP address",
                "Require additional verification",
                "Monitor all activities from this IP"
            ])
        elif analysis['risk_score'] >= 40:
            analysis['recommendations'].extend([
                "Increase monitoring",
                "Consider CAPTCHA challenges"
            ])
        
        return analysis


class ComplianceChecker:
    """
    Comprehensive compliance checker for regulatory requirements.
    
    Provides AML compliance, sanctions screening, and regulatory
    reporting functionality.
    """
    
    def __init__(self):
        """Initialize compliance checker."""
        self.sanctions_manager = SanctionsListManager()
        self.ip_checker = IPReputationChecker()
        self.aml_thresholds = self._load_aml_thresholds()
    
    def _load_aml_thresholds(self) -> Dict[str, Any]:
        """Load AML reporting thresholds."""
        default_thresholds = {
            'transaction_amount': 10000,  # USD
            'daily_total': 15000,  # USD
            'weekly_total': 25000,  # USD
            'monthly_total': 50000,  # USD
        }
        return getattr(settings, 'FRAUD_AML_THRESHOLDS', default_thresholds)
    
    def check_aml_compliance(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check Anti-Money Laundering compliance.
        
        Args:
            transaction_data: Transaction data to check
            
        Returns:
            AML compliance results
        """
        compliance_result = {
            'compliant': True,
            'flags': [],
            'reporting_required': False,
            'risk_level': 'low',
            'recommendations': []
        }
        
        amount = transaction_data.get('amount', 0)
        user_id = transaction_data.get('user_id')
        
        # Check transaction amount threshold
        if amount >= self.aml_thresholds['transaction_amount']:
            compliance_result['flags'].append(
                f"Transaction amount ${amount} exceeds threshold ${self.aml_thresholds['transaction_amount']}"
            )
            compliance_result['reporting_required'] = True
            compliance_result['risk_level'] = 'high'
        
        # Check daily total (simplified - would need aggregation)
        daily_total = self._get_user_daily_total(user_id) if user_id else 0
        if daily_total >= self.aml_thresholds['daily_total']:
            compliance_result['flags'].append(
                f"Daily total ${daily_total} exceeds threshold ${self.aml_thresholds['daily_total']}"
            )
            compliance_result['reporting_required'] = True
            compliance_result['risk_level'] = 'high'
        
        # Check for structuring patterns
        if self._detect_structuring_pattern(user_id):
            compliance_result['flags'].append("Potential transaction structuring detected")
            compliance_result['risk_level'] = 'medium'
            compliance_result['recommendations'].append("Review transaction history for structuring")
        
        # Update compliance status
        if compliance_result['flags']:
            compliance_result['compliant'] = False
        
        return compliance_result
    
    def perform_comprehensive_check(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform comprehensive compliance screening.
        
        Args:
            transaction_data: Transaction data to screen
            
        Returns:
            Comprehensive compliance results
        """
        comprehensive_result = {
            'overall_risk': 'low',
            'passed': True,
            'checks': {},
            'flags': [],
            'recommendations': [],
            'reporting_requirements': [],
            'screening_timestamp': timezone.now().isoformat()
        }
        
        # Sanctions screening
        sanctions_result = self.sanctions_manager.screen_transaction(transaction_data)
        comprehensive_result['checks']['sanctions'] = sanctions_result
        
        # IP reputation check
        ip_address = transaction_data.get('ip_address', '')
        ip_analysis = self.ip_checker.analyze_ip_geolocation(ip_address) if ip_address else {}
        comprehensive_result['checks']['ip_reputation'] = ip_analysis
        
        # AML compliance check
        aml_result = self.check_aml_compliance(transaction_data)
        comprehensive_result['checks']['aml'] = aml_result
        
        # Aggregate results
        all_flags = []
        all_recommendations = []
        reporting_requirements = []
        
        # Collect flags and recommendations
        if not sanctions_result['passed']:
            all_flags.extend(sanctions_result['flags'])
            all_recommendations.extend(sanctions_result['recommendations'])
            comprehensive_result['passed'] = False
        
        if ip_analysis.get('risk_score', 0) >= 70:
            all_flags.append(f"High-risk IP: {ip_address}")
            all_recommendations.extend(ip_analysis.get('recommendations', []))
        
        if not aml_result['compliant']:
            all_flags.extend(aml_result['flags'])
            all_recommendations.extend(aml_result['recommendations'])
            if aml_result['reporting_required']:
                reporting_requirements.append('AML report required')
        
        # Determine overall risk
        risk_factors = 0
        if not sanctions_result['passed']:
            risk_factors += 3
        elif sanctions_result['risk_level'] == 'high':
            risk_factors += 2
        
        if ip_analysis.get('risk_score', 0) >= 70:
            risk_factors += 2
        elif ip_analysis.get('risk_score', 0) >= 40:
            risk_factors += 1
        
        if not aml_result['compliant']:
            risk_factors += 2
        
        if risk_factors >= 4:
            comprehensive_result['overall_risk'] = 'critical'
        elif risk_factors >= 2:
            comprehensive_result['overall_risk'] = 'high'
        elif risk_factors >= 1:
            comprehensive_result['overall_risk'] = 'medium'
        
        comprehensive_result['flags'] = all_flags
        comprehensive_result['recommendations'] = all_recommendations
        comprehensive_result['reporting_requirements'] = reporting_requirements
        
        return comprehensive_result
    
    def _get_user_daily_total(self, user_id: Union[int, str]) -> float:
        """Get user's daily transaction total (simplified)."""
        # In practice, this would aggregate user transactions for the day
        return 0.0
    
    def _detect_structuring_pattern(self, user_id: Union[int, str]) -> bool:
        """Detect transaction structuring patterns (simplified)."""
        # In practice, this would analyze transaction patterns for structuring
        return False


# Global instances for easy access
sanctions_manager = SanctionsListManager()
ip_reputation_checker = IPReputationChecker()
compliance_checker = ComplianceChecker()


def screen_transaction_for_sanctions(transaction_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function for sanctions screening.
    
    Args:
        transaction_data: Transaction data to screen
        
    Returns:
        Sanctions screening results
    """
    return sanctions_manager.screen_transaction(transaction_data)


def check_ip_reputation(ip_address: str, 
                       headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Convenience function for IP reputation checking.
    
    Args:
        ip_address: IP address to check
        headers: HTTP headers for additional analysis
        
    Returns:
        IP reputation analysis
    """
    return ip_reputation_checker.analyze_ip_geolocation(ip_address)


def perform_compliance_screening(transaction_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function for comprehensive compliance screening.
    
    Args:
        transaction_data: Transaction data to screen
        
    Returns:
        Comprehensive compliance results
    """
    return compliance_checker.perform_comprehensive_check(transaction_data)
