"""Rotate All Secrets Management Command

This Django management command rotates all webhook secrets
for security and compliance purposes.
"""

import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from ...services.core import SecretRotationService
from ...models import WebhookEndpoint, WebhookSecret
from ...choices import WebhookStatus

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to rotate all webhook secrets.
    Rotates secrets for all active endpoints for security.
    """
    
    help = 'Rotate secrets for all active webhook endpoints'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force rotation even if secret is not expired',
        )
        parser.add_argument(
            '--grace-period',
            type=int,
            default=7,
            help='Grace period in days before old secret expires',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be rotated without executing',
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        force = options['force']
        grace_period = options['grace_period']
        dry_run = options['dry_run']
        
        self.stdout.write("Starting secret rotation for all endpoints...")
        
        try:
            # Get all active endpoints
            active_endpoints = WebhookEndpoint.objects.filter(
                status=WebhookStatus.ACTIVE
            )
            
            if not active_endpoints.exists():
                self.stdout.write("No active webhook endpoints found")
                return
            
            # Get rotation service
            rotation_service = SecretRotationService()
            
            rotated_count = 0
            skipped_count = 0
            error_count = 0
            
            for endpoint in active_endpoints:
                try:
                    # Check if rotation is needed
                    if not force and not rotation_service.is_rotation_needed(endpoint, grace_period):
                        self.stdout.write(
                            f"Skipping {endpoint.url}: rotation not needed"
                        )
                        skipped_count += 1
                        continue
                    
                    if dry_run:
                        self.stdout.write(
                            f"Would rotate secret for {endpoint.url}"
                        )
                        rotated_count += 1
                    else:
                        # Perform rotation
                        success = rotation_service.rotate_secret(endpoint)
                        
                        if success:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Rotated secret for {endpoint.url}"
                                )
                            )
                            rotated_count += 1
                        else:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"Failed to rotate secret for {endpoint.url}"
                                )
                            )
                            error_count += 1
                
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Error rotating {endpoint.url}: {e}"
                        )
                    )
                    error_count += 1
            
            # Summary
            self.stdout.write("\nSecret rotation summary:")
            self.stdout.write(f"  Total endpoints: {len(active_endpoints)}")
            self.stdout.write(f"  Rotated: {rotated_count}")
            self.stdout.write(f"  Skipped: {skipped_count}")
            self.stdout.write(f"  Errors: {error_count}")
            
            if dry_run:
                self.stdout.write("\nDry run completed. Use without --dry-run to execute.")
            else:
                self.stdout.write("\nSecret rotation completed!")
            
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Secret rotation failed: {e}")
            )
            logger.error(f"Secret rotation command failed: {e}")
    
    def _get_secret_status(self, endpoint) -> dict:
        """Get status information for a secret."""
        try:
            secret = endpoint.secrets.filter(is_active=True).first()
            
            if not secret:
                return {
                    'status': 'No secret',
                    'expires_at': None,
                    'days_until_expiry': None,
                }
            
            days_until_expiry = (secret.expires_at - timezone.now()).days if secret.expires_at else None
            
            return {
                'status': 'Active' if secret.is_active else 'Inactive',
                'expires_at': secret.expires_at,
                'days_until_expiry': days_until_expiry,
            }
            
        except Exception as e:
            return {
                'status': 'Error',
                'error': str(e),
            }
