"""
Domain Verify Tasks

Check tracking domain SSL certificates
and domain health status.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q
import ssl
import socket
from urllib.parse import urlparse

from ..models.tracking import TrackingDomain
try:
    from ..services import TrackingDomainService
except ImportError:
    TrackingDomainService = None

import logging
logger = logging.getLogger(__name__)


@shared_task(name="advertiser_portal.check_domain_ssl")
def check_domain_ssl():
    """
    Check SSL certificates for all tracking domains.
    
    This task runs every 6 hours to check SSL certificates
    and update domain health status.
    """
    try:
        domain_service = TrackingDomainService()
        
        # Get all active tracking domains
        active_domains = TrackingDomain.objects.filter(
            is_active=True
        ).select_related('advertiser')
        
        domains_checked = 0
        ssl_issues = 0
        domains_expiring = 0
        
        for domain in active_domains:
            try:
                # Check SSL certificate
                ssl_result = _check_ssl_certificate(domain.domain)
                
                # Update domain SSL status
                domain.ssl_valid = ssl_result.get('valid', False)
                domain.ssl_expires_at = ssl_result.get('expires_at')
                domain.ssl_issuer = ssl_result.get('issuer')
                domain.ssl_checked_at = timezone.now()
                domain.save()
                
                domains_checked += 1
                
                if not ssl_result.get('valid', False):
                    ssl_issues += 1
                    logger.error(f"SSL certificate invalid for domain {domain.domain}: {ssl_result.get('error', 'Unknown error')}")
                    
                    # Send SSL issue notification
                    _send_ssl_issue_notification(domain, ssl_result)
                
                # Check if SSL is expiring soon (within 30 days)
                if ssl_result.get('expires_at'):
                    days_until_expiry = (ssl_result['expires_at'] - timezone.now().date()).days
                    
                    if days_until_expiry <= 30:
                        domains_expiring += 1
                        logger.warning(f"SSL certificate expiring soon for domain {domain.domain}: {days_until_expiry} days")
                        
                        # Send expiry warning notification
                        _send_ssl_expiry_warning(domain, days_until_expiry)
                
            except Exception as e:
                logger.error(f"Error checking SSL for domain {domain.domain}: {e}")
                continue
        
        logger.info(f"Domain SSL check completed: {domains_checked} checked, {ssl_issues} issues, {domains_expiring} expiring")
        
        return {
            'domains_checked': domains_checked,
            'ssl_issues': ssl_issues,
            'domains_expiring': domains_expiring,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in domain SSL check task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.check_domain_health")
def check_domain_health():
    """
    Check health status of tracking domains.
    
    This task runs every hour to check domain availability
    and response times.
    """
    try:
        domain_service = TrackingDomainService()
        
        # Get all active tracking domains
        active_domains = TrackingDomain.objects.filter(
            is_active=True
        ).select_related('advertiser')
        
        domains_checked = 0
        unhealthy_domains = 0
        slow_domains = 0
        
        for domain in active_domains:
            try:
                # Check domain health
                health_result = _check_domain_health(domain.domain)
                
                # Update domain health status
                domain.is_healthy = health_result.get('healthy', False)
                domain.response_time = health_result.get('response_time', 0)
                domain.last_health_check = timezone.now()
                domain.save()
                
                domains_checked += 1
                
                if not health_result.get('healthy', False):
                    unhealthy_domains += 1
                    logger.error(f"Domain unhealthy: {domain.domain} - {health_result.get('error', 'Unknown error')}")
                    
                    # Send domain health issue notification
                    _send_domain_health_issue_notification(domain, health_result)
                
                # Check if domain is slow (response time > 2 seconds)
                if health_result.get('response_time', 0) > 2000:
                    slow_domains += 1
                    logger.warning(f"Domain slow: {domain.domain} - {health_result.get('response_time', 0)}ms")
                    
                    # Send slow domain notification
                    _send_slow_domain_notification(domain, health_result)
                
            except Exception as e:
                logger.error(f"Error checking health for domain {domain.domain}: {e}")
                continue
        
        logger.info(f"Domain health check completed: {domains_checked} checked, {unhealthy_domains} unhealthy, {slow_domains} slow")
        
        return {
            'domains_checked': domains_checked,
            'unhealthy_domains': unhealthy_domains,
            'slow_domains': slow_domains,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in domain health check task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.verify_domain_ownership")
def verify_domain_ownership():
    """
    Verify domain ownership for pending domains.
    
    This task runs every 30 minutes to verify domain ownership
    for domains that are pending verification.
    """
    try:
        domain_service = TrackingDomainService()
        
        # Get domains pending verification
        pending_domains = TrackingDomain.objects.filter(
            verification_status='pending'
        ).select_related('advertiser')
        
        domains_verified = 0
        verifications_failed = 0
        
        for domain in pending_domains:
            try:
                # Verify domain ownership
                verification_result = domain_service.verify_domain_ownership(domain)
                
                if verification_result.get('success'):
                    # Update verification status
                    domain.verification_status = 'verified'
                    domain.verified_at = timezone.now()
                    domain.save()
                    
                    domains_verified += 1
                    logger.info(f"Domain ownership verified: {domain.domain}")
                    
                    # Send verification success notification
                    _send_domain_verified_notification(domain)
                else:
                    verifications_failed += 1
                    logger.error(f"Domain ownership verification failed: {domain.domain} - {verification_result.get('error', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"Error verifying domain ownership for {domain.domain}: {e}")
                continue
        
        logger.info(f"Domain ownership verification completed: {domains_verified} verified, {verifications_failed} failed")
        
        return {
            'domains_checked': pending_domains.count(),
            'domains_verified': domains_verified,
            'verifications_failed': verifications_failed,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in domain ownership verification task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.update_domain_dns")
def update_domain_dns():
    """
    Update DNS records for tracking domains.
    
    This task runs daily to check and update DNS records
    for tracking domains.
    """
    try:
        domain_service = TrackingDomainService()
        
        # Get all verified domains
        verified_domains = TrackingDomain.objects.filter(
            verification_status='verified',
            is_active=True
        ).select_related('advertiser')
        
        domains_updated = 0
        dns_issues = 0
        
        for domain in verified_domains:
            try:
                # Check DNS configuration
                dns_result = domain_service.check_dns_configuration(domain)
                
                if dns_result.get('configured', True):
                    domains_updated += 1
                    logger.info(f"DNS configuration OK for domain: {domain.domain}")
                else:
                    dns_issues += 1
                    logger.error(f"DNS configuration issues for domain: {domain.domain} - {dns_result.get('issues', [])}")
                    
                    # Send DNS issue notification
                    _send_dns_issue_notification(domain, dns_result)
                
                # Update last DNS check
                domain.last_dns_check = timezone.now()
                domain.save()
                
            except Exception as e:
                logger.error(f"Error checking DNS for domain {domain.domain}: {e}")
                continue
        
        logger.info(f"Domain DNS update completed: {domains_updated} updated, {dns_issues} issues")
        
        return {
            'domains_checked': verified_domains.count(),
            'domains_updated': domains_updated,
            'dns_issues': dns_issues,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in domain DNS update task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.cleanup_inactive_domains")
def cleanup_inactive_domains():
    """
    Clean up inactive tracking domains.
    
    This task runs weekly to clean up domains that
    have been inactive for more than 90 days.
    """
    try:
        # Get domains inactive for more than 90 days
        cutoff_date = timezone.now() - timezone.timedelta(days=90)
        
        inactive_domains = TrackingDomain.objects.filter(
            Q(is_active=False) | Q(last_health_check__lt=cutoff_date)
        ).select_related('advertiser')
        
        domains_deactivated = 0
        
        for domain in inactive_domains:
            try:
                # Deactivate domain
                domain.is_active = False
                domain.deactivated_at = timezone.now()
                domain.save()
                
                domains_deactivated += 1
                logger.info(f"Domain deactivated: {domain.domain}")
                
                # Send deactivation notification
                _send_domain_deactivated_notification(domain)
                
            except Exception as e:
                logger.error(f"Error deactivating domain {domain.domain}: {e}")
                continue
        
        logger.info(f"Domain cleanup completed: {domains_deactivated} domains deactivated")
        
        return {
            'cutoff_date': cutoff_date.isoformat(),
            'domains_deactivated': domains_deactivated,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in domain cleanup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _check_ssl_certificate(domain_name):
    """Check SSL certificate for a domain."""
    try:
        # Get SSL certificate info
        context = ssl.create_default_context()
        
        with socket.create_connection((domain_name, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain_name) as ssock:
                cert = ssock.getpeercert()
                
                # Parse certificate
                issuer = dict(x[0] for x in cert.get('issuer', []))
                subject = dict(x[0] for x in cert.get('subject', []))
                
                # Get expiration date
                not_after = cert.get('notAfter')
                if not_after:
                    expires_at = None
                else:
                    # Parse ASN1 time format
                    from datetime import datetime
                    expires_at = datetime.strptime(not_after.decode('ascii'), '%b %d %H:%M:%S %Y %Z').date()
                
                return {
                    'valid': True,
                    'issuer': issuer.get('organizationName', 'Unknown'),
                    'subject': subject.get('commonName', domain_name),
                    'expires_at': expires_at,
                    'days_until_expiry': (expires_at - timezone.now().date()).days if expires_at else None,
                }
    
    except Exception as e:
        return {
            'valid': False,
            'error': str(e),
            'expires_at': None,
        }


def _check_domain_health(domain_name):
    """Check health of a domain."""
    try:
        import requests
        import time
        
        # Make HTTP request to check domain
        start_time = time.time()
        
        response = requests.get(
            f"https://{domain_name}",
            timeout=10,
            allow_redirects=True
        )
        
        response_time = int((time.time() - start_time) * 1000)  # Convert to milliseconds
        
        return {
            'healthy': response.status_code == 200,
            'status_code': response.status_code,
            'response_time': response_time,
            'response_headers': dict(response.headers),
        }
    
    except Exception as e:
        return {
            'healthy': False,
            'error': str(e),
            'response_time': 0,
        }


def _send_ssl_issue_notification(domain, ssl_result):
    """Send SSL issue notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': domain.advertiser,
            'type': 'ssl_issue',
            'title': 'SSL Certificate Issue',
            'message': f'SSL certificate issue detected for domain {domain.domain}: {ssl_result.get("error", "Unknown error")}',
            'data': {
                'domain_id': domain.id,
                'domain_name': domain.domain,
                'ssl_valid': ssl_result.get('valid', False),
                'error': ssl_result.get('error'),
                'checked_at': domain.ssl_checked_at.isoformat() if domain.ssl_checked_at else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending SSL issue notification: {e}")


def _send_ssl_expiry_warning(domain, days_until_expiry):
    """Send SSL expiry warning notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': domain.advertiser,
            'type': 'ssl_expiry_warning',
            'title': 'SSL Certificate Expiring Soon',
            'message': f'SSL certificate for domain {domain.domain} expires in {days_until_expiry} days',
            'data': {
                'domain_id': domain.id,
                'domain_name': domain.domain,
                'expires_at': domain.ssl_expires_at.isoformat() if domain.ssl_expires_at else None,
                'days_until_expiry': days_until_expiry,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending SSL expiry warning notification: {e}")


def _send_domain_health_issue_notification(domain, health_result):
    """Send domain health issue notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': domain.advertiser,
            'type': 'domain_health_issue',
            'title': 'Domain Health Issue',
            'message': f'Domain health issue detected for {domain.domain}: {health_result.get("error", "Unknown error")}',
            'data': {
                'domain_id': domain.id,
                'domain_name': domain.domain,
                'healthy': health_result.get('healthy', False),
                'error': health_result.get('error'),
                'checked_at': domain.last_health_check.isoformat() if domain.last_health_check else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending domain health issue notification: {e}")


def _send_slow_domain_notification(domain, health_result):
    """Send slow domain notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': domain.advertiser,
            'type': 'slow_domain',
            'title': 'Domain Performance Issue',
            'message': f'Domain {domain.domain} is responding slowly: {health_result.get("response_time", 0)}ms',
            'data': {
                'domain_id': domain.id,
                'domain_name': domain.domain,
                'response_time': health_result.get('response_time', 0),
                'checked_at': domain.last_health_check.isoformat() if domain.last_health_check else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending slow domain notification: {e}")


def _send_domain_verified_notification(domain):
    """Send domain verified notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': domain.advertiser,
            'type': 'domain_verified',
            'title': 'Domain Verified',
            'message': f'Domain {domain.domain} has been successfully verified',
            'data': {
                'domain_id': domain.id,
                'domain_name': domain.domain,
                'verified_at': domain.verified_at.isoformat() if domain.verified_at else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending domain verified notification: {e}")


def _send_dns_issue_notification(domain, dns_result):
    """Send DNS issue notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': domain.advertiser,
            'type': 'dns_issue',
            'title': 'DNS Configuration Issue',
            'message': f'DNS configuration issues detected for domain {domain.domain}: {", ".join(dns_result.get("issues", []))}',
            'data': {
                'domain_id': domain.id,
                'domain_name': domain.domain,
                'issues': dns_result.get('issues', []),
                'checked_at': domain.last_dns_check.isoformat() if domain.last_dns_check else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending DNS issue notification: {e}")


def _send_domain_deactivated_notification(domain):
    """Send domain deactivated notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': domain.advertiser,
            'type': 'domain_deactivated',
            'title': 'Domain Deactivated',
            'message': f'Domain {domain.domain} has been deactivated due to inactivity',
            'data': {
                'domain_id': domain.id,
                'domain_name': domain.domain,
                'deactivated_at': domain.deactivated_at.isoformat() if domain.deactivated_at else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending domain deactivated notification: {e}")
