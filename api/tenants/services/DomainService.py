"""
Domain Service

This service handles domain management operations including
DNS verification, SSL setup, and domain configuration.
"""

import dns.resolver
import ssl
import socket
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ..models import Tenant
from ..models.branding import TenantDomain
from ..models.security import TenantAuditLog

User = get_user_model()


class DomainService:
    """
    Service class for domain management operations.
    
    This service handles DNS verification, SSL certificate
    management, and domain configuration for tenants.
    """
    
    @staticmethod
    def verify_dns_record(domain, record_type='TXT', expected_value=None):
        """
        Verify DNS record for domain.
        
        Args:
            domain (TenantDomain): Domain to verify
            record_type (str): Type of DNS record to check
            expected_value (str): Expected value for the record
            
        Returns:
            dict: Verification result
        """
        try:
            # Query DNS record
            answers = dns.resolver.resolve(domain.domain, record_type)
            records = [str(rdata) for rdata in answers]
            
            if expected_value:
                is_verified = expected_value in records
            else:
                is_verified = len(records) > 0
            
            return {
                'success': True,
                'verified': is_verified,
                'records': records,
                'record_type': record_type,
            }
            
        except dns.resolver.NXDOMAIN:
            return {
                'success': False,
                'error': 'Domain does not exist',
                'record_type': record_type,
            }
        except dns.resolver.NoAnswer:
            return {
                'success': False,
                'error': f'No {record_type} record found',
                'record_type': record_type,
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'record_type': record_type,
            }
    
    @staticmethod
    def check_ssl_certificate(domain):
        """
        Check SSL certificate for domain.
        
        Args:
            domain (TenantDomain): Domain to check
            
        Returns:
            dict: SSL certificate information
        """
        try:
            # Get SSL certificate
            context = ssl.create_default_context()
            with socket.create_connection((domain.domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain.domain) as ssock:
                    cert = ssock.getpeercert()
            
            # Parse certificate
            subject = dict(x[0] for x in cert['subject'])
            issuer = dict(x[0] for x in cert['issuer'])
            
            # Get expiration date
            not_after = timezone.make_aware(
                timezone.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
            )
            
            days_until_expiry = (not_after - timezone.now()).days
            
            return {
                'success': True,
                'subject': subject,
                'issuer': issuer,
                'expires_at': not_after,
                'days_until_expiry': days_until_expiry,
                'is_valid': days_until_expiry > 0,
                'serial_number': cert.get('serialNumber'),
                'version': cert.get('version'),
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    @staticmethod
    def setup_ssl_letsencrypt(domain):
        """
        Setup SSL certificate using Let's Encrypt.
        
        Args:
            domain (TenantDomain): Domain to setup SSL for
            
        Returns:
            dict: SSL setup result
        """
        # This would integrate with Let's Encrypt API
        # For now, just simulate the process
        
        try:
            # Check if domain is accessible
            domain_check = DomainService.check_domain_accessibility(domain)
            if not domain_check['accessible']:
                return {
                    'success': False,
                    'error': 'Domain is not accessible from the internet',
                }
            
            # Simulate certificate generation
            cert_data = {
                'certificate': '-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----',
                'private_key': '-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----',
                'expires_at': timezone.now() + timedelta(days=90),
            }
            
            # Update domain record
            domain.ssl_certificate = cert_data['certificate']
            domain.ssl_private_key = cert_data['private_key']
            domain.ssl_status = 'verified'
            domain.ssl_expires_at = cert_data['expires_at']
            domain.save()
            
            return {
                'success': True,
                'message': 'SSL certificate setup successfully',
                'expires_at': cert_data['expires_at'],
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    @staticmethod
    def check_domain_accessibility(domain):
        """
        Check if domain is accessible from the internet.
        
        Args:
            domain (TenantDomain): Domain to check
            
        Returns:
            dict: Accessibility check result
        """
        try:
            import requests
            response = requests.get(f"https://{domain.domain}", timeout=10)
            
            return {
                'accessible': True,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'server': response.headers.get('Server', 'Unknown'),
            }
            
        except requests.exceptions.Timeout:
            return {
                'accessible': False,
                'error': 'Connection timeout',
            }
        except requests.exceptions.ConnectionError:
            return {
                'accessible': False,
                'error': 'Connection failed',
            }
        except Exception as e:
            return {
                'accessible': False,
                'error': str(e),
            }
    
    @staticmethod
    def renew_ssl_certificate(domain):
        """
        Renew SSL certificate for domain.
        
        Args:
            domain (TenantDomain): Domain to renew SSL for
            
        Returns:
            dict: Renewal result
        """
        if domain.ssl_status != 'verified':
            return {
                'success': False,
                'error': 'No SSL certificate to renew',
            }
        
        # Check if renewal is needed (within 30 days of expiry)
        if domain.days_until_ssl_expiry > 30:
            return {
                'success': False,
                'error': 'SSL certificate does not need renewal yet',
                'days_until_expiry': domain.days_until_ssl_expiry,
            }
        
        # Setup new certificate
        return DomainService.setup_ssl_letsencrypt(domain)
    
    @staticmethod
    def get_domain_health(domain):
        """
        Get comprehensive domain health information.
        
        Args:
            domain (TenantDomain): Domain to check
            
        Returns:
            dict: Domain health information
        """
        health = {
            'domain': domain.domain,
            'is_active': domain.is_active,
            'is_primary': domain.is_primary,
            'dns_status': domain.dns_status,
            'ssl_status': domain.ssl_status,
            'checks': {},
        }
        
        # DNS verification
        if domain.dns_verification_token:
            dns_check = DomainService.verify_dns_record(
                domain, 'TXT', domain.dns_verification_token
            )
            health['checks']['dns_verification'] = dns_check
        
        # SSL certificate check
        if domain.ssl_status in ['verified', 'expired']:
            ssl_check = DomainService.check_ssl_certificate(domain)
            health['checks']['ssl_certificate'] = ssl_check
        
        # Domain accessibility
        accessibility_check = DomainService.check_domain_accessibility(domain)
        health['checks']['accessibility'] = accessibility_check
        
        # Overall health score
        health['score'] = DomainService._calculate_health_score(health['checks'])
        
        return health
    
    @staticmethod
    def _calculate_health_score(checks):
        """Calculate overall domain health score."""
        score = 100
        
        # DNS verification
        dns_check = checks.get('dns_verification', {})
        if dns_check.get('success') and dns_check.get('verified'):
            score += 0
        else:
            score -= 30
        
        # SSL certificate
        ssl_check = checks.get('ssl_certificate', {})
        if ssl_check.get('success') and ssl_check.get('is_valid'):
            days_until_expiry = ssl_check.get('days_until_expiry', 0)
            if days_until_expiry < 7:
                score -= 20
            elif days_until_expiry < 30:
                score -= 10
        else:
            score -= 40
        
        # Accessibility
        accessibility_check = checks.get('accessibility', {})
        if not accessibility_check.get('accessible'):
            score -= 30
        
        return max(0, score)
    
    @staticmethod
    def monitor_ssl_expiration():
        """
        Monitor SSL certificate expiration for all domains.
        
        Returns:
            list: Domains needing attention
        """
        from django.db.models import Q
        
        # Find domains with SSL expiring soon
        warning_threshold = timezone.now() + timedelta(days=30)
        expiring_domains = TenantDomain.objects.filter(
            Q(ssl_status='verified') &
            Q(ssl_expires_at__lte=warning_threshold) &
            Q(is_active=True)
        )
        
        attention_needed = []
        
        for domain in expiring_domains:
            days_until_expiry = domain.days_until_ssl_expiry
            
            if days_until_expiry <= 7:
                priority = 'critical'
            elif days_until_expiry <= 15:
                priority = 'high'
            else:
                priority = 'medium'
            
            attention_needed.append({
                'domain': domain,
                'days_until_expiry': days_until_expiry,
                'priority': priority,
                'expires_at': domain.ssl_expires_at,
            })
        
        return attention_needed
    
    @staticmethod
    def auto_renew_ssl_certificates():
        """
        Automatically renew SSL certificates for eligible domains.
        
        Returns:
            dict: Auto-renewal results
        """
        expiring_domains = DomainService.monitor_ssl_expiration()
        
        results = {
            'total_checked': len(expiring_domains),
            'renewed': 0,
            'failed': 0,
            'skipped': 0,
            'details': [],
        }
        
        for domain_info in expiring_domains:
            domain = domain_info['domain']
            
            # Only auto-renew if enabled and within 7 days
            if domain.ssl_auto_renew and domain_info['days_until_expiry'] <= 7:
                renewal_result = DomainService.renew_ssl_certificate(domain)
                
                if renewal_result['success']:
                    results['renewed'] += 1
                    results['details'].append({
                        'domain': domain.domain,
                        'status': 'renewed',
                        'message': renewal_result.get('message'),
                    })
                else:
                    results['failed'] += 1
                    results['details'].append({
                        'domain': domain.domain,
                        'status': 'failed',
                        'error': renewal_result.get('error'),
                    })
            else:
                results['skipped'] += 1
                results['details'].append({
                    'domain': domain.domain,
                    'status': 'skipped',
                    'reason': 'Auto-renewal disabled or not yet due',
                })
        
        return results
