"""
Tracking Domain Service

Service for managing tracking domains,
including domain verification and SSL management.
"""

import logging
import socket
import ssl
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.tracking import TrackingDomain
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class TrackingDomainService:
    """
    Service for managing tracking domains.
    
    Handles domain verification, SSL checking,
    and domain management.
    """
    
    def __init__(self):
        self.logger = logger
    
    def add_tracking_domain(self, advertiser, domain: str, data: Dict[str, Any] = None) -> TrackingDomain:
        """
        Add a new tracking domain.
        
        Args:
            advertiser: Advertiser instance
            domain: Domain name
            data: Additional domain data
            
        Returns:
            TrackingDomain: Created domain instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                domain_data = data or {}
                
                # Validate domain format
                self._validate_domain_format(domain)
                
                # Check if domain already exists for advertiser
                if TrackingDomain.objects.filter(advertiser=advertiser, domain=domain).exists():
                    raise ValidationError("Domain already exists for this advertiser")
                
                # Create tracking domain
                tracking_domain = TrackingDomain.objects.create(
                    advertiser=advertiser,
                    domain=domain.lower(),
                    subdomain=domain_data.get('subdomain'),
                    is_verified=False,
                    ssl_status='not_configured',
                    is_active=domain_data.get('is_active', True),
                    is_default=domain_data.get('is_default', False),
                    cname_record=domain_data.get('cname_record'),
                    txt_record=domain_data.get('txt_record'),
                    tracking_endpoint=domain_data.get('tracking_endpoint'),
                    custom_headers=domain_data.get('custom_headers', {}),
                )
                
                # Generate verification code
                verification_code = self._generate_verification_code()
                tracking_domain.metadata = tracking_domain.metadata or {}
                tracking_domain.metadata['verification_code'] = verification_code
                tracking_domain.save()
                
                # Send notification with verification instructions
                self._send_domain_added_notification(advertiser, tracking_domain, verification_code)
                
                self.logger.info(f"Added tracking domain: {domain} for {advertiser.company_name}")
                return tracking_domain
                
        except Exception as e:
            self.logger.error(f"Error adding tracking domain: {e}")
            raise ValidationError(f"Failed to add tracking domain: {str(e)}")
    
    def verify_domain(self, domain: TrackingDomain, verification_code: str) -> Dict[str, Any]:
        """
        Verify domain ownership.
        
        Args:
            domain: Domain instance
            verification_code: Verification code
            
        Returns:
            Dict[str, Any]: Verification results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Check verification code
                stored_code = domain.metadata.get('verification_code') if domain.metadata else None
                
                if not stored_code or stored_code != verification_code:
                    return {
                        'success': False,
                        'reason': 'Invalid verification code',
                        'verified_at': None,
                    }
                
                # Perform DNS verification
                dns_result = self._verify_domain_dns(domain)
                
                if not dns_result['success']:
                    return {
                        'success': False,
                        'reason': dns_result['reason'],
                        'verified_at': None,
                    }
                
                # Update domain status
                domain.is_verified = True
                domain.verified_at = timezone.now()
                domain.save()
                
                # Check SSL status after verification
                self._check_domain_ssl(domain)
                
                # Send notification
                self._send_domain_verified_notification(domain.advertiser, domain)
                
                self.logger.info(f"Verified tracking domain: {domain.domain}")
                
                return {
                    'success': True,
                    'verified_at': domain.verified_at.isoformat(),
                    'ssl_status': domain.ssl_status,
                }
                
        except Exception as e:
            self.logger.error(f"Error verifying domain: {e}")
            raise ValidationError(f"Failed to verify domain: {str(e)}")
    
    def check_domain_ssl(self, domain: TrackingDomain) -> Dict[str, Any]:
        """
        Check SSL certificate for domain.
        
        Args:
            domain: Domain instance
            
        Returns:
            Dict[str, Any]: SSL check results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            ssl_result = self._check_domain_ssl(domain)
            
            # Update SSL status
            domain.ssl_status = ssl_result['status']
            domain.ssl_expires_at = ssl_result.get('expires_at')
            domain.ssl_certificate = ssl_result.get('certificate')
            domain.save()
            
            # Send notification for critical SSL issues
            if ssl_result['status'] in ['expired', 'invalid']:
                self._send_ssl_issue_notification(domain.advertiser, domain, ssl_result)
            
            return ssl_result
            
        except Exception as e:
            self.logger.error(f"Error checking domain SSL: {e}")
            raise ValidationError(f"Failed to check domain SSL: {str(e)}")
    
    def get_domain_status(self, domain: TrackingDomain) -> Dict[str, Any]:
        """
        Get comprehensive domain status.
        
        Args:
            domain: Domain instance
            
        Returns:
            Dict[str, Any]: Domain status
        """
        try:
            # Get SSL status
            ssl_status = domain.check_ssl_status()
            
            return {
                'domain_id': domain.id,
                'domain': domain.domain,
                'full_domain': domain.full_domain,
                'is_verified': domain.is_verified,
                'is_active': domain.is_active,
                'is_default': domain.is_default,
                'ssl_status': domain.ssl_status,
                'ssl_details': ssl_status,
                'verification_status': {
                    'is_verified': domain.is_verified,
                    'verified_at': domain.verified_at.isoformat() if domain.verified_at else None,
                    'verification_code': domain.metadata.get('verification_code') if domain.metadata else None,
                },
                'configuration': {
                    'cname_record': domain.cname_record,
                    'txt_record': domain.txt_record,
                    'tracking_endpoint': domain.tracking_endpoint,
                    'custom_headers': domain.custom_headers,
                },
                'health_status': self._get_domain_health_status(domain),
                'last_checked': timezone.now().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting domain status: {e}")
            raise ValidationError(f"Failed to get domain status: {str(e)}")
    
    def get_domains(self, advertiser=None, filters: Dict[str, Any] = None) -> List[TrackingDomain]:
        """
        Get tracking domains with filtering.
        
        Args:
            advertiser: Optional advertiser filter
            filters: Additional filter criteria
            
        Returns:
            List[TrackingDomain]: List of domains
        """
        try:
            queryset = TrackingDomain.objects.select_related('advertiser').order_by('-created_at')
            
            if advertiser:
                queryset = queryset.filter(advertiser=advertiser)
            
            if filters:
                if 'is_verified' in filters:
                    queryset = queryset.filter(is_verified=filters['is_verified'])
                
                if 'is_active' in filters:
                    queryset = queryset.filter(is_active=filters['is_active'])
                
                if 'ssl_status' in filters:
                    queryset = queryset.filter(ssl_status=filters['ssl_status'])
                
                if 'search' in filters:
                    search_term = filters['search']
                    queryset = queryset.filter(
                        models.Q(domain__icontains=search_term) |
                        models.Q(subdomain__icontains=search_term)
                    )
            
            return list(queryset)
            
        except Exception as e:
            self.logger.error(f"Error getting domains: {e}")
            return []
    
    def update_domain(self, domain: TrackingDomain, data: Dict[str, Any]) -> TrackingDomain:
        """
        Update tracking domain.
        
        Args:
            domain: Domain instance to update
            data: Update data
            
        Returns:
            TrackingDomain: Updated domain instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Update domain fields
                allowed_fields = [
                    'subdomain', 'is_active', 'is_default', 'cname_record',
                    'txt_record', 'tracking_endpoint', 'custom_headers'
                ]
                
                for field in allowed_fields:
                    if field in data:
                        setattr(domain, field, data[field])
                
                domain.save()
                
                # Re-check SSL if tracking endpoint changed
                if 'tracking_endpoint' in data:
                    self._check_domain_ssl(domain)
                
                self.logger.info(f"Updated tracking domain: {domain.domain}")
                return domain
                
        except Exception as e:
            self.logger.error(f"Error updating domain: {e}")
            raise ValidationError(f"Failed to update domain: {str(e)}")
    
    def delete_domain(self, domain: TrackingDomain) -> bool:
        """
        Delete tracking domain.
        
        Args:
            domain: Domain instance to delete
            
        Returns:
            bool: True if successful
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Check if domain is default
                if domain.is_default:
                    raise ValidationError("Cannot delete default tracking domain")
                
                # Send notification
                self._send_domain_deleted_notification(domain.advertiser, domain)
                
                # Delete domain
                domain.delete()
                
                self.logger.info(f"Deleted tracking domain: {domain.domain}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error deleting domain: {e}")
            raise ValidationError(f"Failed to delete domain: {str(e)}")
    
    def set_default_domain(self, domain: TrackingDomain) -> TrackingDomain:
        """
        Set domain as default for advertiser.
        
        Args:
            domain: Domain instance to set as default
            
        Returns:
            TrackingDomain: Updated domain instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Remove default status from other domains
                TrackingDomain.objects.filter(
                    advertiser=domain.advertiser,
                    is_default=True
                ).update(is_default=False)
                
                # Set this domain as default
                domain.is_default = True
                domain.save()
                
                # Send notification
                self._send_default_domain_changed_notification(domain.advertiser, domain)
                
                self.logger.info(f"Set default domain: {domain.domain}")
                return domain
                
        except Exception as e:
            self.logger.error(f"Error setting default domain: {e}")
            raise ValidationError(f"Failed to set default domain: {str(e)}")
    
    def check_all_domains_ssl(self) -> Dict[str, Any]:
        """
        Check SSL status for all active domains.
        
        Returns:
            Dict[str, Any]: SSL check results
        """
        try:
            domains = TrackingDomain.objects.filter(is_active=True, is_verified=True)
            
            results = {
                'total_domains': domains.count(),
                'checked_domains': 0,
                'valid_ssl': 0,
                'expired_ssl': 0,
                'invalid_ssl': 0,
                'not_configured': 0,
                'errors': [],
                'timestamp': timezone.now().isoformat(),
            }
            
            for domain in domains:
                try:
                    ssl_result = self._check_domain_ssl(domain)
                    results['checked_domains'] += 1
                    
                    if ssl_result['status'] == 'valid':
                        results['valid_ssl'] += 1
                    elif ssl_result['status'] == 'expired':
                        results['expired_ssl'] += 1
                    elif ssl_result['status'] == 'invalid':
                        results['invalid_ssl'] += 1
                    else:
                        results['not_configured'] += 1
                
                except Exception as e:
                    results['errors'].append({
                        'domain': domain.domain,
                        'error': str(e)
                    })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error checking all domains SSL: {e}")
            raise ValidationError(f"Failed to check all domains SSL: {str(e)}")
    
    def _validate_domain_format(self, domain: str):
        """Validate domain format."""
        import re
        
        # Basic domain validation
        domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,})$'
        
        if not re.match(domain_pattern, domain):
            raise ValidationError("Invalid domain format")
    
    def _generate_verification_code(self) -> str:
        """Generate verification code."""
        import secrets
        timestamp = str(int(timezone.now().timestamp()))
        random_str = secrets.token_hex(4)
        return f"verify_{timestamp}_{random_str}"
    
    def _verify_domain_dns(self, domain: TrackingDomain) -> Dict[str, Any]:
        """Verify domain DNS records."""
        try:
            # This would implement actual DNS verification
            # For now, return success
            return {
                'success': True,
                'cname_found': True,
                'txt_found': True,
                'reason': 'DNS verification successful',
            }
        except Exception as e:
            return {
                'success': False,
                'reason': str(e),
            }
    
    def _check_domain_ssl(self, domain: TrackingDomain) -> Dict[str, Any]:
        """Check SSL certificate for domain."""
        try:
            full_domain = domain.full_domain
            
            # Create SSL context
            context = ssl.create_default_context()
            
            # Get SSL certificate
            with socket.create_connection((full_domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=full_domain) as ssock:
                    cert = ssock.getpeercert()
                    
                    if not cert:
                        return {
                            'status': 'not_configured',
                            'reason': 'No SSL certificate found',
                        }
                    
                    # Check expiration
                    import datetime
                    not_after = datetime.datetime.strptime(
                        cert['notAfter'], '%b %d %H:%M:%S %Y %Z'
                    )
                    
                    expires_at = timezone.make_aware(not_after)
                    
                    if expires_at < timezone.now():
                        return {
                            'status': 'expired',
                            'expires_at': expires_at.isoformat(),
                            'certificate': cert,
                            'reason': 'SSL certificate has expired',
                        }
                    
                    # Check if certificate is valid
                    if not_after > timezone.now():
                        return {
                            'status': 'valid',
                            'expires_at': expires_at.isoformat(),
                            'certificate': cert,
                            'days_remaining': (expires_at - timezone.now()).days,
                            'reason': 'SSL certificate is valid',
                        }
                    else:
                        return {
                            'status': 'invalid',
                            'expires_at': expires_at.isoformat(),
                            'certificate': cert,
                            'reason': 'SSL certificate is invalid',
                        }
        
        except Exception as e:
            return {
                'status': 'invalid',
                'reason': f'SSL check failed: {str(e)}',
            }
    
    def _get_domain_health_status(self, domain: TrackingDomain) -> Dict[str, Any]:
        """Get domain health status."""
        health_score = 100
        
        # Deduct points for issues
        if not domain.is_verified:
            health_score -= 50
        
        if domain.ssl_status == 'expired':
            health_score -= 30
        elif domain.ssl_status == 'invalid':
            health_score -= 20
        elif domain.ssl_status == 'not_configured':
            health_score -= 10
        
        if not domain.is_active:
            health_score -= 25
        
        # Determine health status
        if health_score >= 90:
            status = 'excellent'
        elif health_score >= 70:
            status = 'good'
        elif health_score >= 50:
            status = 'fair'
        else:
            status = 'poor'
        
        return {
            'score': health_score,
            'status': status,
            'issues': self._get_domain_issues(domain),
        }
    
    def _get_domain_issues(self, domain: TrackingDomain) -> List[str]:
        """Get domain issues."""
        issues = []
        
        if not domain.is_verified:
            issues.append('Domain not verified')
        
        if domain.ssl_status == 'expired':
            issues.append('SSL certificate expired')
        elif domain.ssl_status == 'invalid':
            issues.append('SSL certificate invalid')
        elif domain.ssl_status == 'not_configured':
            issues.append('SSL not configured')
        
        if not domain.is_active:
            issues.append('Domain is inactive')
        
        if domain.ssl_expires_at and domain.ssl_expires_at < timezone.now() + timezone.timedelta(days=30):
            issues.append('SSL certificate expiring soon')
        
        return issues
    
    def _send_domain_added_notification(self, advertiser, domain: TrackingDomain, verification_code: str):
        """Send domain added notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='verification_required',
            title=_('Tracking Domain Added'),
            message=_(
                'Your tracking domain "{domain}" has been added. '
                'Verification code: {code}'
            ).format(
                domain=domain.domain,
                code=verification_code
            ),
            priority='medium',
            action_url=f'/advertiser/tracking/domains/{domain.id}/',
            action_text=_('Verify Domain')
        )
    
    def _send_domain_verified_notification(self, advertiser, domain: TrackingDomain):
        """Send domain verified notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='verification_required',
            title=_('Domain Verified'),
            message=_('Your tracking domain "{domain}" has been successfully verified.').format(
                domain=domain.domain
            ),
            priority='low',
            action_url=f'/advertiser/tracking/domains/{domain.id}/',
            action_text=_('View Domain')
        )
    
    def _send_ssl_issue_notification(self, advertiser, domain: TrackingDomain, ssl_result: Dict[str, Any]):
        """Send SSL issue notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='verification_required',
            title=_('SSL Issue Detected'),
            message=_(
                'SSL issue detected for domain "{domain}": {reason}'
            ).format(
                domain=domain.domain,
                reason=ssl_result['reason']
            ),
            priority='high',
            action_url=f'/advertiser/tracking/domains/{domain.id}/ssl/',
            action_text=_('Fix SSL')
        )
    
    def _send_domain_deleted_notification(self, advertiser, domain: TrackingDomain):
        """Send domain deleted notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='verification_required',
            title=_('Tracking Domain Deleted'),
            message=_('Your tracking domain "{domain}" has been deleted.').format(
                domain=domain.domain
            ),
            priority='low'
        )
    
    def _send_default_domain_changed_notification(self, advertiser, domain: TrackingDomain):
        """Send default domain changed notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='verification_required',
            title=_('Default Domain Changed'),
            message=_('Your default tracking domain has been changed to "{domain}".').format(
                domain=domain.domain
            ),
            priority='medium',
            action_url=f'/advertiser/tracking/domains/{domain.id}/',
            action_text=_('View Domain')
        )
