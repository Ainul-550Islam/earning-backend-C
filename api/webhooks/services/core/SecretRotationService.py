"""Secret Rotation Service

This module provides webhook secret rotation functionality with grace periods and invalidation.
"""

import logging
import secrets
import string
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from ..models import WebhookEndpoint, WebhookSecret
from ..choices import WebhookStatus

logger = logging.getLogger(__name__)


class SecretRotationService:
    """Service for rotating webhook secrets with grace periods and invalidation."""
    
    def __init__(self):
        """Initialize the secret rotation service."""
        self.default_secret_length = getattr(settings, 'WEBHOOK_SECRET_LENGTH', 32)
        self.grace_period_hours = getattr(settings, 'WEBHOOK_SECRET_GRACE_PERIOD_HOURS', 24)
        self.max_old_secrets = getattr(settings, 'WEBHOOK_MAX_OLD_SECRETS', 3)
    
    def rotate_secret(self, endpoint: WebhookEndpoint) -> str:
        """
        Rotate the secret for a webhook endpoint.
        
        Args:
            endpoint: The webhook endpoint to rotate secret for
            
        Returns:
            The new secret key
        """
        try:
            with transaction.atomic():
                # Generate new secret
                new_secret = self._generate_secret()
                
                # Create old secret record
                if endpoint.secret_key:
                    old_secret = WebhookSecret.objects.create(
                        endpoint=endpoint,
                        secret_key=endpoint.secret_key,
                        is_active=False,
                        expires_at=timezone.now() + timezone.timedelta(hours=self.grace_period_hours),
                        created_by=endpoint.owner
                    )
                
                # Update endpoint with new secret
                endpoint.secret_key = new_secret
                endpoint.save()
                
                # Clean up old expired secrets
                self._cleanup_old_secrets(endpoint)
                
                logger.info(f"Secret rotated for endpoint {endpoint.id}")
                return new_secret
                
        except Exception as e:
            logger.error(f"Error rotating secret for endpoint {endpoint.id}: {str(e)}")
            raise
    
    def rotate_inbound_secret(self, inbound_webhook) -> str:
        """
        Rotate the secret for an inbound webhook.
        
        Args:
            inbound_webhook: The inbound webhook to rotate secret for
            
        Returns:
            The new secret
        """
        try:
            with transaction.atomic():
                # Generate new secret
                new_secret = self._generate_secret()
                
                # Create old secret record
                if inbound_webhook.secret:
                    old_secret = WebhookSecret.objects.create(
                        endpoint=None,  # Inbound webhooks don't have endpoints
                        inbound_webhook=inbound_webhook,
                        secret_key=inbound_webhook.secret,
                        is_active=False,
                        expires_at=timezone.now() + timezone.timedelta(hours=self.grace_period_hours),
                        created_by=inbound_webhook.created_by
                    )
                
                # Update inbound webhook with new secret
                inbound_webhook.secret = new_secret
                inbound_webhook.save()
                
                # Clean up old expired secrets
                self._cleanup_old_inbound_secrets(inbound_webhook)
                
                logger.info(f"Secret rotated for inbound webhook {inbound_webhook.id}")
                return new_secret
                
        except Exception as e:
            logger.error(f"Error rotating secret for inbound webhook {inbound_webhook.id}: {str(e)}")
            raise
    
    def _generate_secret(self, length: int = None) -> str:
        """
        Generate a new secure random secret.
        
        Args:
            length: Length of the secret (defaults to instance default)
            
        Returns:
            Generated secret string
        """
        try:
            if length is None:
                length = self.default_secret_length
            
            # Use cryptographically secure random generator
            alphabet = string.ascii_letters + string.digits
            return ''.join(secrets.choice(alphabet) for _ in range(length))
            
        except Exception as e:
            logger.error(f"Error generating secret: {str(e)}")
            raise
    
    def _cleanup_old_secrets(self, endpoint: WebhookEndpoint) -> int:
        """
        Clean up old expired secrets for an endpoint.
        
        Args:
            endpoint: The webhook endpoint
            
        Returns:
            Number of secrets cleaned up
        """
        try:
            # Get expired secrets
            expired_secrets = WebhookSecret.objects.filter(
                endpoint=endpoint,
                expires_at__lt=timezone.now()
            )
            
            # Delete expired secrets if we have too many
            all_secrets = WebhookSecret.objects.filter(endpoint=endpoint).order_by('-created_at')
            if all_secrets.count() > self.max_old_secrets:
                # Keep only the most recent secrets
                secrets_to_keep = all_secrets[:self.max_old_secrets]
                secrets_to_delete = all_secrets.exclude(id__in=secrets_to_keep)
                deleted_count = secrets_to_delete.count()
                secrets_to_delete.delete()
            else:
                # Only delete expired ones
                deleted_count = expired_secrets.count()
                expired_secrets.delete()
            
            logger.info(f"Cleaned up {deleted_count} old secrets for endpoint {endpoint.id}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old secrets for endpoint {endpoint.id}: {str(e)}")
            return 0
    
    def _cleanup_old_inbound_secrets(self, inbound_webhook) -> int:
        """
        Clean up old expired secrets for an inbound webhook.
        
        Args:
            inbound_webhook: The inbound webhook
            
        Returns:
            Number of secrets cleaned up
        """
        try:
            # Get expired secrets
            expired_secrets = WebhookSecret.objects.filter(
                inbound_webhook=inbound_webhook,
                expires_at__lt=timezone.now()
            )
            
            # Delete expired secrets if we have too many
            all_secrets = WebhookSecret.objects.filter(inbound_webhook=inbound_webhook).order_by('-created_at')
            if all_secrets.count() > self.max_old_secrets:
                # Keep only the most recent secrets
                secrets_to_keep = all_secrets[:self.max_old_secrets]
                secrets_to_delete = all_secrets.exclude(id__in=secrets_to_keep)
                deleted_count = secrets_to_delete.count()
                secrets_to_delete.delete()
            else:
                # Only delete expired ones
                deleted_count = expired_secrets.count()
                expired_secrets.delete()
            
            logger.info(f"Cleaned up {deleted_count} old secrets for inbound webhook {inbound_webhook.id}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old secrets for inbound webhook {inbound_webhook.id}: {str(e)}")
            return 0
    
    def invalidate_secret(self, endpoint: WebhookEndpoint, reason: str = "Manual invalidation") -> bool:
        """
        Immediately invalidate the current secret for an endpoint.
        
        Args:
            endpoint: The webhook endpoint
            reason: Reason for invalidation
            
        Returns:
            True if invalidation was successful, False otherwise
        """
        try:
            with transaction.atomic():
                if not endpoint.secret_key:
                    return False
                
                # Create old secret record with immediate expiration
                old_secret = WebhookSecret.objects.create(
                    endpoint=endpoint,
                    secret_key=endpoint.secret_key,
                    is_active=False,
                    expires_at=timezone.now(),  # Immediate expiration
                    created_by=endpoint.owner
                )
                
                # Generate new secret
                new_secret = self._generate_secret()
                endpoint.secret_key = new_secret
                endpoint.save()
                
                logger.info(f"Secret invalidated for endpoint {endpoint.id}: {reason}")
                return True
                
        except Exception as e:
            logger.error(f"Error invalidating secret for endpoint {endpoint.id}: {str(e)}")
            return False
    
    def validate_secret(self, endpoint: WebhookEndpoint, provided_secret: str) -> bool:
        """
        Validate a provided secret against current and grace period secrets.
        
        Args:
            endpoint: The webhook endpoint
            provided_secret: The secret to validate
            
        Returns:
            True if secret is valid, False otherwise
        """
        try:
            # Check current secret
            if endpoint.secret_key == provided_secret:
                return True
            
            # Check grace period secrets
            grace_secrets = WebhookSecret.objects.filter(
                endpoint=endpoint,
                secret_key=provided_secret,
                is_active=False,
                expires_at__gt=timezone.now()
            )
            
            return grace_secrets.exists()
            
        except Exception as e:
            logger.error(f"Error validating secret for endpoint {endpoint.id}: {str(e)}")
            return False
    
    def get_secret_history(self, endpoint: WebhookEndpoint) -> List[Dict[str, Any]]:
        """
        Get the secret history for an endpoint.
        
        Args:
            endpoint: The webhook endpoint
            
        Returns:
            List of secret history records
        """
        try:
            secrets = WebhookSecret.objects.filter(endpoint=endpoint).order_by('-created_at')
            
            history = []
            for secret in secrets:
                history.append({
                    'secret_id': str(secret.id),
                    'secret_preview': secret.secret_key[:8] + "..." if secret.secret_key else None,
                    'is_active': secret.is_active,
                    'expires_at': secret.expires_at.isoformat() if secret.expires_at else None,
                    'created_at': secret.created_at.isoformat(),
                    'is_expired': secret.expires_at and secret.expires_at < timezone.now()
                })
            
            # Add current secret
            if endpoint.secret_key:
                history.insert(0, {
                    'secret_id': None,
                    'secret_preview': endpoint.secret_key[:8] + "...",
                    'is_active': True,
                    'expires_at': None,
                    'created_at': endpoint.updated_at.isoformat(),
                    'is_expired': False
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting secret history for endpoint {endpoint.id}: {str(e)}")
            return []
    
    def rotate_all_secrets(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Rotate secrets for all endpoints (or for a specific user).
        
        Args:
            user_id: Optional user ID to filter endpoints
            
        Returns:
            Dictionary with rotation results
        """
        try:
            # Get endpoints to rotate
            endpoints = WebhookEndpoint.objects.filter(status=WebhookStatus.ACTIVE)
            if user_id:
                endpoints = endpoints.filter(owner_id=user_id)
            
            rotated_count = 0
            failed_count = 0
            errors = []
            
            for endpoint in endpoints:
                try:
                    self.rotate_secret(endpoint)
                    rotated_count += 1
                except Exception as e:
                    failed_count += 1
                    errors.append(f"Endpoint {endpoint.id}: {str(e)}")
            
            return {
                'total_endpoints': endpoints.count(),
                'rotated_count': rotated_count,
                'failed_count': failed_count,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error rotating all secrets: {str(e)}")
            return {
                'total_endpoints': 0,
                'rotated_count': 0,
                'failed_count': 0,
                'errors': [str(e)]
            }
    
    def get_expiring_secrets(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get secrets that will expire within the specified hours.
        
        Args:
            hours: Hours to look ahead for expiration
            
        Returns:
            List of expiring secrets
        """
        try:
            cutoff_time = timezone.now() + timezone.timedelta(hours=hours)
            
            expiring_secrets = WebhookSecret.objects.filter(
                expires_at__lte=cutoff_time,
                expires_at__gt=timezone.now(),
                is_active=False
            ).select_related('endpoint', 'inbound_webhook')
            
            expiring_list = []
            for secret in expiring_secrets:
                if secret.endpoint:
                    expiring_list.append({
                        'secret_id': str(secret.id),
                        'endpoint_id': str(secret.endpoint.id),
                        'endpoint_label': secret.endpoint.label,
                        'endpoint_url': secret.endpoint.url,
                        'expires_at': secret.expires_at.isoformat(),
                        'hours_until_expiry': (secret.expires_at - timezone.now()).total_seconds() / 3600
                    })
                elif secret.inbound_webhook:
                    expiring_list.append({
                        'secret_id': str(secret.id),
                        'inbound_webhook_id': str(secret.inbound_webhook.id),
                        'inbound_source': secret.inbound_webhook.source,
                        'expires_at': secret.expires_at.isoformat(),
                        'hours_until_expiry': (secret.expires_at - timezone.now()).total_seconds() / 3600
                    })
            
            return expiring_list
            
        except Exception as e:
            logger.error(f"Error getting expiring secrets: {str(e)}")
            return []
    
    def extend_grace_period(self, secret_id: str, additional_hours: int = 24) -> bool:
        """
        Extend the grace period for an old secret.
        
        Args:
            secret_id: The ID of the secret to extend
            additional_hours: Additional hours to extend
            
        Returns:
            True if extension was successful, False otherwise
        """
        try:
            secret = WebhookSecret.objects.get(id=secret_id)
            
            if secret.is_active:
                return False  # Cannot extend active secrets
            
            # Extend expiration
            secret.expires_at = timezone.now() + timezone.timedelta(hours=additional_hours)
            secret.save()
            
            logger.info(f"Extended grace period for secret {secret_id} by {additional_hours} hours")
            return True
            
        except WebhookSecret.DoesNotExist:
            logger.error(f"Secret {secret_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error extending grace period for secret {secret_id}: {str(e)}")
            return False
    
    def get_rotation_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about secret rotation.
        
        Returns:
            Dictionary with rotation statistics
        """
        try:
            # Get total counts
            total_endpoints = WebhookEndpoint.objects.count()
            total_secrets = WebhookSecret.objects.count()
            
            # Get active secrets
            active_endpoints = WebhookEndpoint.objects.filter(secret_key__isnull=False).count()
            
            # Get grace period secrets
            grace_secrets = WebhookSecret.objects.filter(
                is_active=False,
                expires_at__gt=timezone.now()
            ).count()
            
            # Get expired secrets
            expired_secrets = WebhookSecret.objects.filter(
                is_active=False,
                expires_at__lt=timezone.now()
            ).count()
            
            # Get recent rotations
            from datetime import timedelta
            recent_rotations = WebhookSecret.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            return {
                'total_endpoints': total_endpoints,
                'active_endpoints': active_endpoints,
                'total_secrets': total_secrets,
                'grace_period_secrets': grace_secrets,
                'expired_secrets': expired_secrets,
                'recent_rotations_7d': recent_rotations,
                'grace_period_hours': self.grace_period_hours,
                'max_old_secrets': self.max_old_secrets
            }
            
        except Exception as e:
            logger.error(f"Error getting rotation statistics: {str(e)}")
            return {
                'total_endpoints': 0,
                'active_endpoints': 0,
                'total_secrets': 0,
                'grace_period_secrets': 0,
                'expired_secrets': 0,
                'recent_rotations_7d': 0,
                'grace_period_hours': self.grace_period_hours,
                'max_old_secrets': self.max_old_secrets,
                'error': str(e)
            }
