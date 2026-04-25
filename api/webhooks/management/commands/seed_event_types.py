"""
Seed Event Types Management Command

This Django management command seeds all 40+ event types
into the database for webhook system initialization.
"""

import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from ...constants import EventType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to seed event types.
    Creates all 40+ platform event types in the database.
    """
    
    help = 'Seed all webhook event types into the database'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force overwrite existing event types',
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        force = options['force']
        
        self.stdout.write("Starting event types seeding...")
        
        try:
            with transaction.atomic():
                # Get all event type choices
                event_choices = EventType.all_choices()
                
                created_count = 0
                updated_count = 0
                
                for event_type, display_name in event_choices:
                    # Check if event type already exists
                    from ...models import WebhookEventStat
                    existing = WebhookEventStat.objects.filter(
                        event_type=event_type
                    ).first()
                    
                    if existing and not force:
                        self.stdout.write(
                            f"Event type '{event_type}' already exists. "
                            f"Use --force to overwrite."
                        )
                        updated_count += 1
                    else:
                        # Create new event stat record
                        WebhookEventStat.objects.create(
                            event_type=event_type,
                            date=timezone.now().date(),
                            fired_count=0,
                            delivered_count=0,
                            failed_count=0,
                        )
                        created_count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully processed {created_count} event types"
                    )
                )
                
                if updated_count > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipped {updated_count} existing event types"
                        )
                    )
                
                self.stdout.write("Event types seeding completed successfully!")
                
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Failed to seed event types: {e}")
            )
            logger.error(f"Event types seeding failed: {e}")
            raise
    
    def _get_event_type_info(self) -> list:
        """
        Get information about all event types.
        
        Returns:
            list: Event type information
        """
        return [
            {
                'event_type': event_type,
                'display_name': display_name,
                'category': self._get_event_category(event_type),
            }
            for event_type, display_name in EventType.all_choices()
        ]
    
    def _get_event_category(self, event_type: str) -> str:
        """
        Get category for an event type.
        
        Args:
            event_type: Event type identifier
            
        Returns:
            str: Category name
        """
        if event_type.startswith('user.'):
            return 'User Events'
        elif event_type.startswith('wallet.'):
            return 'Wallet Events'
        elif event_type.startswith('withdrawal.'):
            return 'Withdrawal Events'
        elif event_type.startswith('offer.'):
            return 'Offer Events'
        elif event_type.startswith('kyc.'):
            return 'KYC Events'
        elif event_type.startswith('payment.'):
            return 'Payment Events'
        elif event_type.startswith('fraud.'):
            return 'Fraud Events'
        elif event_type.startswith('system.'):
            return 'System Events'
        elif event_type.startswith('analytics.'):
            return 'Analytics Events'
        elif event_type.startswith('security.'):
            return 'Security Events'
        elif event_type.startswith('integration.'):
            return 'Integration Events'
        elif event_type.startswith('notification.'):
            return 'Notification Events'
        elif event_type.startswith('campaign.'):
            return 'Campaign Events'
        elif event_type.startswith('subscription.'):
            return 'Subscription Events'
        elif event_type.startswith('api.'):
            return 'API Events'
        elif event_type.startswith('health.'):
            return 'Health Events'
        elif event_type.startswith('batch.'):
            return 'Batch Events'
        elif event_type.startswith('replay.'):
            return 'Replay Events'
        else:
            return 'Other Events'
