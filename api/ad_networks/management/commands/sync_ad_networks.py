"""
api/ad_networks/management/commands/sync_ad_networks.py
Manual full sync command for ad networks
SaaS-ready with tenant support
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from datetime import timedelta
import logging
import time

from api.ad_networks.models import AdNetwork, Offer, NetworkAPILog
from api.ad_networks.services.AdNetworkFactory import AdNetworkFactory
from api.ad_networks.constants import (
    API_TIMEOUT_SECONDS,
    API_RETRY_ATTEMPTS,
    SUPPORTED_NETWORKS,
    LOG_CATEGORIES
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manual full sync of all ad networks'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--network-type',
            type=str,
            help='Specific network type to sync (optional)',
            choices=SUPPORTED_NETWORKS
        )
        parser.add_argument(
            '--tenant-id',
            type=str,
            help='Specific tenant ID to sync (optional)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sync even if recently synced'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for processing offers'
        )
    
    def handle(self, *args, **options):
        self.verbose = options.get('verbose', False)
        self.dry_run = options.get('dry_run', False)
        self.batch_size = options.get('batch_size', 100)
        self.network_type = options.get('network_type')
        self.tenant_id = options.get('tenant_id')
        self.force = options.get('force', False)
        
        self.stdout.write(self.style.SUCCESS('Starting ad networks sync...'))
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        try:
            # Get networks to sync
            networks = self._get_networks_to_sync()
            
            if not networks:
                self.stdout.write(self.style.WARNING('No networks found to sync'))
                return
            
            self.stdout.write(f'Found {len(networks)} networks to sync')
            
            # Sync each network
            total_offers_synced = 0
            total_errors = 0
            
            for network in networks:
                try:
                    offers_synced, errors = self._sync_network(network)
                    total_offers_synced += offers_synced
                    total_errors += errors
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Failed to sync {network.name}: {str(e)}')
                    )
                    total_errors += 1
                    continue
            
            # Summary
            self._print_summary(total_offers_synced, total_errors, len(networks))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Sync failed: {str(e)}'))
            raise CommandError(f'Sync failed: {str(e)}')
    
    def _get_networks_to_sync(self):
        """Get networks that need to be synced"""
        queryset = AdNetwork.objects.filter(is_active=True)
        
        if self.network_type:
            queryset = queryset.filter(network_type=self.network_type)
        
        if self.tenant_id:
            queryset = queryset.filter(tenant_id=self.tenant_id)
        
        if not self.force:
            # Only sync networks that haven't been synced recently
            recent_sync = timezone.now() - timedelta(hours=1)
            queryset = queryset.filter(
                models.Q(last_sync__isnull=True) | 
                models.Q(last_sync__lt=recent_sync)
            )
        
        return queryset.select_related().order_by('priority')
    
    def _sync_network(self, network):
        """Sync a single network"""
        self.stdout.write(f'Syncing {network.name} ({network.network_type})...')
        
        offers_synced = 0
        errors = 0
        
        try:
            # Get network service
            service = AdNetworkFactory.get_service(network.network_type)
            
            if not service:
                self.stdout.write(
                    self.style.WARNING(f'No service found for {network.network_type}')
                )
                return offers_synced, errors
            
            # Check network health first
            if not self._check_network_health(network, service):
                self.stdout.write(
                    self.style.WARNING(f'Skipping {network.name} - health check failed')
                )
                return offers_synced, errors
            
            # Get offers from network
            offers_data = self._fetch_offers_from_network(network, service)
            
            if not offers_data:
                self.stdout.write(f'No offers found for {network.name}')
                return offers_synced, errors
            
            # Process offers in batches
            for i in range(0, len(offers_data), self.batch_size):
                batch = offers_data[i:i + self.batch_size]
                batch_synced, batch_errors = self._process_offer_batch(
                    network, batch
                )
                offers_synced += batch_synced
                errors += batch_errors
                
                if self.verbose:
                    self.stdout.write(
                        f'  Processed batch {i//self.batch_size + 1}: '
                        f'{batch_synced} offers, {batch_errors} errors'
                    )
            
            # Update network sync status
            if not self.dry_run:
                network.last_sync = timezone.now()
                network.next_sync = timezone.now() + timedelta(hours=1)
                network.save(update_fields=['last_sync', 'next_sync'])
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Synced {network.name}: {offers_synced} offers, {errors} errors'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error syncing {network.name}: {str(e)}')
            )
            errors += 1
            
            # Log error
            self._log_api_error(network, 'sync', str(e))
        
        return offers_synced, errors
    
    def _check_network_health(self, network, service):
        """Check if network is healthy"""
        try:
            is_healthy = service.health_check()
            
            if not self.dry_run:
                # Create health check record
                from api.ad_networks.models import NetworkHealthCheck
                NetworkHealthCheck.objects.create(
                    network=network,
                    is_healthy=is_healthy,
                    check_type='api_call',
                    endpoint_checked=getattr(service, 'base_url', ''),
                    response_time_ms=getattr(service, 'last_response_time', 0)
                )
            
            return is_healthy
            
        except Exception as e:
            if self.verbose:
                self.stdout.write(f'Health check failed for {network.name}: {str(e)}')
            return False
    
    def _fetch_offers_from_network(self, network, service):
        """Fetch offers from network API"""
        try:
            offers_data = service.get_offers()
            
            # Log API call
            if not self.dry_run:
                NetworkAPILog.objects.create(
                    network=network,
                    endpoint='offers',
                    method='GET',
                    request_data={},
                    response_data={'offers_count': len(offers_data) if offers_data else 0},
                    status_code=200,
                    is_success=True,
                    latency_ms=getattr(service, 'last_response_time', 0)
                )
            
            return offers_data or []
            
        except Exception as e:
            # Log API error
            if not self.dry_run:
                NetworkAPILog.objects.create(
                    network=network,
                    endpoint='offers',
                    method='GET',
                    request_data={},
                    response_data={'error': str(e)},
                    status_code=500,
                    is_success=False,
                    error_message=str(e),
                    error_type='API_ERROR'
                )
            
            raise e
    
    def _process_offer_batch(self, network, offers_batch):
        """Process a batch of offers"""
        offers_synced = 0
        errors = 0
        
        if self.dry_run:
            return len(offers_batch), 0
        
        with transaction.atomic():
            for offer_data in offers_batch:
                try:
                    self._create_or_update_offer(network, offer_data)
                    offers_synced += 1
                    
                except Exception as e:
                    if self.verbose:
                        self.stdout.write(f'    Error processing offer: {str(e)}')
                    errors += 1
                    continue
        
        return offers_synced, errors
    
    def _create_or_update_offer(self, network, offer_data):
        """Create or update an offer"""
        external_id = offer_data.get('external_id')
        
        if not external_id:
            raise ValueError('Offer missing external_id')
        
        # Try to find existing offer
        offer = Offer.objects.filter(
            ad_network=network,
            external_id=external_id
        ).first()
        
        # Prepare offer data
        offer_fields = {
            'title': offer_data.get('title', '')[:255],
            'description': offer_data.get('description', ''),
            'reward_amount': offer_data.get('reward_amount', 0),
            'network_payout': offer_data.get('payout', 0),
            'click_url': offer_data.get('click_url', ''),
            'thumbnail': offer_data.get('thumbnail', ''),
            'countries': offer_data.get('countries', []),
            'platforms': offer_data.get('platforms', ['android', 'ios', 'web']),
            'device_type': offer_data.get('device_type', 'any'),
            'difficulty': offer_data.get('difficulty', 'easy'),
            'estimated_time': offer_data.get('estimated_time', 5),
            'max_conversions': offer_data.get('max_conversions'),
            'expires_at': offer_data.get('expires_at'),
            'status': 'active' if offer_data.get('is_available', True) else 'paused',
            'metadata': offer_data.get('metadata', {}),
        }
        
        if offer:
            # Update existing offer
            for field, value in offer_fields.items():
                setattr(offer, field, value)
            offer.save()
        else:
            # Create new offer
            offer_fields.update({
                'ad_network': network,
                'external_id': external_id,
            })
            offer = Offer.objects.create(**offer_fields)
    
    def _log_api_error(self, network, operation, error_message):
        """Log API error"""
        try:
            NetworkAPILog.objects.create(
                network=network,
                endpoint=operation,
                method='SYNC',
                request_data={},
                response_data={'error': error_message},
                status_code=500,
                is_success=False,
                error_message=error_message,
                error_type='SYNC_ERROR'
            )
        except Exception as e:
            logger.error(f'Failed to log API error: {str(e)}')
    
    def _print_summary(self, total_offers_synced, total_errors, total_networks):
        """Print sync summary"""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('SYNC SUMMARY'))
        self.stdout.write('='*50)
        self.stdout.write(f'Total networks processed: {total_networks}')
        self.stdout.write(f'Total offers synced: {total_offers_synced}')
        self.stdout.write(f'Total errors: {total_errors}')
        
        if total_errors > 0:
            self.stdout.write(
                self.style.WARNING(f'Sync completed with {total_errors} errors')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Sync completed successfully!')
            )
        
        self.stdout.write('='*50)
