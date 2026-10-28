"""
Security Dependencies Management
External service dependencies and integrations
Author: System Security Team
Version: 1.0.0
"""

import logging
import requests
import json
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from abc import ABC, abstractmethod
import hashlib
import hmac
import base64

logger = logging.getLogger(__name__)


class SecurityDependencyError(Exception):
    """Base exception for security dependency errors"""
    pass


class SecurityDependencyTimeout(SecurityDependencyError):
    """Exception for dependency timeout errors"""
    pass


class SecurityDependencyAuthError(SecurityDependencyError):
    """Exception for dependency authentication errors"""
    pass


class SecurityDependencyConfigError(SecurityDependencyError):
    """Exception for dependency configuration errors"""
    pass


class BaseSecurityDependency(ABC):
    """
    Abstract base class for security dependencies
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize dependency with configuration
        
        Args:
            config (Dict[str, Any]): Dependency configuration
        """
        self.config = config
        self.name = config.get('name', self.__class__.__name__)
        self.enabled = config.get('enabled', True)
        self.timeout = config.get('timeout', 30)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.retry_delay = config.get('retry_delay', 1)
        
        # Validate configuration
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self):
        """Validate dependency configuration"""
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """Test connection to dependency"""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get dependency status"""
        pass
    
    def is_enabled(self) -> bool:
        """Check if dependency is enabled"""
        return self.enabled
    
    def get_config_value(self, key: str, default=None):
        """Get configuration value"""
        return self.config.get(key, default)


class ThreatIntelligenceDependency(BaseSecurityDependency):
    """
    Threat intelligence service dependency
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.base_url = config.get('base_url')
        self.rate_limit = config.get('rate_limit', 100)
        self.cache_timeout = config.get('cache_timeout', 3600)
    
    def _validate_config(self):
        """Validate threat intelligence configuration"""
        if not self.api_key:
            raise SecurityDependencyConfigError("API key is required")
        if not self.base_url:
            raise SecurityDependencyConfigError("Base URL is required")
    
    def test_connection(self) -> bool:
        """Test connection to threat intelligence service"""
        try:
            url = f"{self.base_url}/health"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Threat intelligence connection test failed: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get threat intelligence service status"""
        try:
            cache_key = f"threat_intel_status_{hash(self.base_url)}"
            cached_status = cache.get(cache_key)
            
            if cached_status:
                return cached_status
            
            url = f"{self.base_url}/status"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                status_data = response.json()
                status_data['service'] = 'threat_intelligence'
                status_data['healthy'] = True
                status_data['last_check'] = timezone.now().isoformat()
                cache.set(cache_key, status_data, timeout=300)
                return status_data
            else:
                return {
                    'service': 'threat_intelligence',
                    'healthy': False,
                    'error': f"HTTP {response.status_code}",
                    'last_check': timezone.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting threat intelligence status: {e}")
            return {
                'service': 'threat_intelligence',
                'healthy': False,
                'error': str(e),
                'last_check': timezone.now().isoformat()
            }
    
    def check_ip_reputation(self, ip_address: str) -> Dict[str, Any]:
        """
        Check IP reputation using threat intelligence service
        
        Args:
            ip_address (str): IP address to check
            
        Returns:
            Dict[str, Any]: IP reputation data
        """
        try:
            cache_key = f"ip_reputation_{ip_address}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
            
            url = f"{self.base_url}/ip/reputation"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            data = {'ip': ip_address}
            
            response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
            
            if response.status_code == 200:
                result = response.json()
                cache.set(cache_key, result, timeout=self.cache_timeout)
                return result
            else:
                logger.error(f"IP reputation check failed: HTTP {response.status_code}")
                return {
                    'ip': ip_address,
                    'reputation': 'unknown',
                    'error': f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"Error checking IP reputation: {e}")
            return {
                'ip': ip_address,
                'reputation': 'unknown',
                'error': str(e)
            }
    
    def get_threat_feeds(self, feed_types: List[str] = None) -> List[Dict[str, Any]]:
        """
        Get threat feeds from intelligence service
        
        Args:
            feed_types (List[str], optional): Types of feeds to retrieve
            
        Returns:
            List[Dict[str, Any]]: Threat feed data
        """
        try:
            cache_key = f"threat_feeds_{hash(str(feed_types))}"
            cached_feeds = cache.get(cache_key)
            
            if cached_feeds:
                return cached_feeds
            
            url = f"{self.base_url}/feeds"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            params = {}
            if feed_types:
                params['types'] = ','.join(feed_types)
            
            response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                feeds = response.json()
                cache.set(cache_key, feeds, timeout=self.cache_timeout)
                return feeds
            else:
                logger.error(f"Threat feeds retrieval failed: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting threat feeds: {e}")
            return []


class VirusScannerDependency(BaseSecurityDependency):
    """
    Virus scanning service dependency
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.base_url = config.get('base_url')
        self.max_file_size = config.get('max_file_size', 50 * 1024 * 1024)  # 50MB
    
    def _validate_config(self):
        """Validate virus scanner configuration"""
        if not self.api_key:
            raise SecurityDependencyConfigError("API key is required")
        if not self.base_url:
            raise SecurityDependencyConfigError("Base URL is required")
    
    def test_connection(self) -> bool:
        """Test connection to virus scanning service"""
        try:
            url = f"{self.base_url}/health"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Virus scanner connection test failed: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get virus scanner service status"""
        try:
            url = f"{self.base_url}/status"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                status_data = response.json()
                status_data['service'] = 'virus_scanner'
                status_data['healthy'] = True
                status_data['last_check'] = timezone.now().isoformat()
                return status_data
            else:
                return {
                    'service': 'virus_scanner',
                    'healthy': False,
                    'error': f"HTTP {response.status_code}",
                    'last_check': timezone.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting virus scanner status: {e}")
            return {
                'service': 'virus_scanner',
                'healthy': False,
                'error': str(e),
                'last_check': timezone.now().isoformat()
            }
    
    def scan_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Scan file for viruses
        
        Args:
            file_content (bytes): File content to scan
            filename (str): Original filename
            
        Returns:
            Dict[str, Any]: Scan results
        """
        try:
            if len(file_content) > self.max_file_size:
                return {
                    'filename': filename,
                    'clean': False,
                    'error': f'File size exceeds maximum limit of {self.max_file_size} bytes'
                }
            
            url = f"{self.base_url}/scan"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/octet-stream'
            }
            
            files = {'file': (filename, file_content)}
            
            response = requests.post(url, headers=headers, files=files, timeout=self.timeout)
            
            if response.status_code == 200:
                result = response.json()
                result['filename'] = filename
                return result
            else:
                logger.error(f"File scan failed: HTTP {response.status_code}")
                return {
                    'filename': filename,
                    'clean': False,
                    'error': f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"Error scanning file: {e}")
            return {
                'filename': filename,
                'clean': False,
                'error': str(e)
            }


class GeolocationDependency(BaseSecurityDependency):
    """
    Geolocation service dependency
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.base_url = config.get('base_url')
        self.provider = config.get('provider', 'ipapi')
    
    def _validate_config(self):
        """Validate geolocation configuration"""
        if self.provider == 'ipapi' and not self.api_key:
            raise SecurityDependencyConfigError("API key is required for ipapi provider")
        if not self.base_url:
            raise SecurityDependencyConfigError("Base URL is required")
    
    def test_connection(self) -> bool:
        """Test connection to geolocation service"""
        try:
            url = f"{self.base_url}/check"
            params = {'key': self.api_key} if self.api_key else {}
            
            response = requests.get(url, params=params, timeout=self.timeout)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Geolocation connection test failed: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get geolocation service status"""
        try:
            url = f"{self.base_url}/status"
            params = {'key': self.api_key} if self.api_key else {}
            
            response = requests.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                status_data = response.json()
                status_data['service'] = 'geolocation'
                status_data['healthy'] = True
                status_data['last_check'] = timezone.now().isoformat()
                return status_data
            else:
                return {
                    'service': 'geolocation',
                    'healthy': False,
                    'error': f"HTTP {response.status_code}",
                    'last_check': timezone.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting geolocation status: {e}")
            return {
                'service': 'geolocation',
                'healthy': False,
                'error': str(e),
                'last_check': timezone.now().isoformat()
            }
    
    def get_location(self, ip_address: str) -> Dict[str, Any]:
        """
        Get geolocation data for IP address
        
        Args:
            ip_address (str): IP address to lookup
            
        Returns:
            Dict[str, Any]: Geolocation data
        """
        try:
            cache_key = f"geolocation_{ip_address}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
            
            url = f"{self.base_url}/{ip_address}"
            params = {'key': self.api_key} if self.api_key else {}
            
            response = requests.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                result = response.json()
                cache.set(cache_key, result, timeout=86400)  # Cache for 24 hours
                return result
            else:
                logger.error(f"Geolocation lookup failed: HTTP {response.status_code}")
                return {
                    'ip': ip_address,
                    'error': f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"Error getting geolocation: {e}")
            return {
                'ip': ip_address,
                'error': str(e)
            }


class EmailNotificationDependency(BaseSecurityDependency):
    """
    Email notification service dependency
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.smtp_host = config.get('smtp_host')
        self.smtp_port = config.get('smtp_port', 587)
        self.smtp_username = config.get('smtp_username')
        self.smtp_password = config.get('smtp_password')
        self.use_tls = config.get('use_tls', True)
        self.from_email = config.get('from_email')
    
    def _validate_config(self):
        """Validate email notification configuration"""
        if not self.smtp_host:
            raise SecurityDependencyConfigError("SMTP host is required")
        if not self.smtp_username:
            raise SecurityDependencyConfigError("SMTP username is required")
        if not self.smtp_password:
            raise SecurityDependencyConfigError("SMTP password is required")
        if not self.from_email:
            raise SecurityDependencyConfigError("From email is required")
    
    def test_connection(self) -> bool:
        """Test connection to email service"""
        try:
            import smtplib
            
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            if self.use_tls:
                server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.quit()
            return True
            
        except Exception as e:
            logger.error(f"Email service connection test failed: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get email service status"""
        try:
            is_connected = self.test_connection()
            
            return {
                'service': 'email_notification',
                'healthy': is_connected,
                'smtp_host': self.smtp_host,
                'smtp_port': self.smtp_port,
                'use_tls': self.use_tls,
                'last_check': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting email service status: {e}")
            return {
                'service': 'email_notification',
                'healthy': False,
                'error': str(e),
                'last_check': timezone.now().isoformat()
            }
    
    def send_security_alert(self, to_email: str, subject: str, message: str, 
                          priority: str = 'normal') -> Dict[str, Any]:
        """
        Send security alert email
        
        Args:
            to_email (str): Recipient email
            subject (str): Email subject
            message (str): Email message
            priority (str): Email priority (low, normal, high)
            
        Returns:
            Dict[str, Any]: Send result
        """
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add priority header
            if priority == 'high':
                msg['X-Priority'] = '1'
                msg['X-MSMail-Priority'] = 'High'
            elif priority == 'low':
                msg['X-Priority'] = '5'
                msg['X-MSMail-Priority'] = 'Low'
            
            msg.attach(MIMEText(message, 'plain'))
            
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            if self.use_tls:
                server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            
            text = msg.as_string()
            server.sendmail(self.from_email, to_email, text)
            server.quit()
            
            return {
                'success': True,
                'to_email': to_email,
                'subject': subject,
                'sent_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error sending security alert: {e}")
            return {
                'success': False,
                'to_email': to_email,
                'error': str(e)
            }


class SecurityDependencyManager:
    """
    Manager for all security dependencies
    """
    
    def __init__(self):
        self.dependencies = {}
        self._initialize_dependencies()
    
    def _initialize_dependencies(self):
        """Initialize all security dependencies"""
        try:
            from django.conf import settings
            
            security_config = getattr(settings, 'SECURITY_DEPENDENCIES', {})
            
            # Initialize threat intelligence dependency
            if 'threat_intelligence' in security_config:
                self.dependencies['threat_intelligence'] = ThreatIntelligenceDependency(
                    security_config['threat_intelligence']
                )
            
            # Initialize virus scanner dependency
            if 'virus_scanner' in security_config:
                self.dependencies['virus_scanner'] = VirusScannerDependency(
                    security_config['virus_scanner']
                )
            
            # Initialize geolocation dependency
            if 'geolocation' in security_config:
                self.dependencies['geolocation'] = GeolocationDependency(
                    security_config['geolocation']
                )
            
            # Initialize email notification dependency
            if 'email_notification' in security_config:
                self.dependencies['email_notification'] = EmailNotificationDependency(
                    security_config['email_notification']
                )
            
            logger.info(f"Initialized {len(self.dependencies)} security dependencies")
            
        except Exception as e:
            logger.error(f"Error initializing security dependencies: {e}")
    
    def get_dependency(self, name: str) -> Optional[BaseSecurityDependency]:
        """
        Get dependency by name
        
        Args:
            name (str): Dependency name
            
        Returns:
            Optional[BaseSecurityDependency]: Dependency instance
        """
        return self.dependencies.get(name)
    
    def get_all_dependencies(self) -> Dict[str, BaseSecurityDependency]:
        """
        Get all dependencies
        
        Returns:
            Dict[str, BaseSecurityDependency]: All dependencies
        """
        return self.dependencies.copy()
    
    def get_enabled_dependencies(self) -> Dict[str, BaseSecurityDependency]:
        """
        Get enabled dependencies
        
        Returns:
            Dict[str, BaseSecurityDependency]: Enabled dependencies
        """
        return {
            name: dep for name, dep in self.dependencies.items()
            if dep.is_enabled()
        }
    
    def test_all_connections(self) -> Dict[str, bool]:
        """
        Test all dependency connections
        
        Returns:
            Dict[str, bool]: Connection test results
        """
        results = {}
        
        for name, dependency in self.dependencies.items():
            try:
                results[name] = dependency.test_connection()
            except Exception as e:
                logger.error(f"Error testing connection for {name}: {e}")
                results[name] = False
        
        return results
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all dependencies
        
        Returns:
            Dict[str, Dict[str, Any]]: Status of all dependencies
        """
        status = {}
        
        for name, dependency in self.dependencies.items():
            try:
                status[name] = dependency.get_status()
            except Exception as e:
                logger.error(f"Error getting status for {name}: {e}")
                status[name] = {
                    'service': name,
                    'healthy': False,
                    'error': str(e),
                    'last_check': timezone.now().isoformat()
                }
        
        return status
    
    def check_ip_reputation(self, ip_address: str) -> Dict[str, Any]:
        """
        Check IP reputation using available threat intelligence services
        
        Args:
            ip_address (str): IP address to check
            
        Returns:
            Dict[str, Any]: IP reputation data
        """
        threat_intel = self.get_dependency('threat_intelligence')
        
        if threat_intel and threat_intel.is_enabled():
            return threat_intel.check_ip_reputation(ip_address)
        else:
            return {
                'ip': ip_address,
                'reputation': 'unknown',
                'error': 'Threat intelligence service not available'
            }
    
    def scan_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Scan file using available virus scanning services
        
        Args:
            file_content (bytes): File content to scan
            filename (str): Original filename
            
        Returns:
            Dict[str, Any]: Scan results
        """
        virus_scanner = self.get_dependency('virus_scanner')
        
        if virus_scanner and virus_scanner.is_enabled():
            return virus_scanner.scan_file(file_content, filename)
        else:
            return {
                'filename': filename,
                'clean': True,  # Default to clean if scanner not available
                'warning': 'Virus scanner not available'
            }
    
    def get_location(self, ip_address: str) -> Dict[str, Any]:
        """
        Get geolocation data using available services
        
        Args:
            ip_address (str): IP address to lookup
            
        Returns:
            Dict[str, Any]: Geolocation data
        """
        geolocation = self.get_dependency('geolocation')
        
        if geolocation and geolocation.is_enabled():
            return geolocation.get_location(ip_address)
        else:
            return {
                'ip': ip_address,
                'error': 'Geolocation service not available'
            }
    
    def send_security_alert(self, to_email: str, subject: str, message: str, 
                          priority: str = 'normal') -> Dict[str, Any]:
        """
        Send security alert using available email services
        
        Args:
            to_email (str): Recipient email
            subject (str): Email subject
            message (str): Email message
            priority (str): Email priority
            
        Returns:
            Dict[str, Any]: Send result
        """
        email_service = self.get_dependency('email_notification')
        
        if email_service and email_service.is_enabled():
            return email_service.send_security_alert(to_email, subject, message, priority)
        else:
            return {
                'success': False,
                'to_email': to_email,
                'error': 'Email notification service not available'
            }


# Global dependency manager instance
security_dependency_manager = SecurityDependencyManager()

# Export for use in other modules
__all__ = [
    'BaseSecurityDependency',
    'ThreatIntelligenceDependency',
    'VirusScannerDependency',
    'GeolocationDependency',
    'EmailNotificationDependency',
    'SecurityDependencyManager',
    'security_dependency_manager',
    'SecurityDependencyError',
    'SecurityDependencyTimeout',
    'SecurityDependencyAuthError',
    'SecurityDependencyConfigError',
]