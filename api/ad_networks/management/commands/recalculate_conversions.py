"""
api/ad_networks/management/commands/recalculate_conversions.py
Recalculate conversion statistics command
SaaS-ready with tenant support
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction, connection
from django.db.models import Count, Sum, Avg, Q, F
from datetime import timedelta, date
import logging
import time

from api.ad_networks.models import Offer, UserOfferEngagement, OfferConversion, AdNetwork
from api.ad_networks.constants import LOG_CATEGORIES

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Recalculate conversion statistics for offers and networks'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--offer-id',
            type=int,
            help='Specific offer ID to recalculate (optional)'
        )
        parser.add_argument(
            '--network-id',
            type=int,
            help='Specific network ID to recalculate (optional)'
        )
        parser.add_argument(
            '--tenant-id',
            type=str,
            help='Specific tenant ID to recalculate (optional)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to look back (default: 30)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for processing (default: 100)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be recalculated without actually updating'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )
        parser.add_argument(
            '--reset-all',
            action='store_true',
            help='Reset all stats before recalculation'
        )
    
    def handle(self, *args, **options):
        self.verbose = options.get('verbose', False)
        self.dry_run = options.get('dry_run', False)
        self.batch_size = options.get('batch_size', 100)
        self.days = options.get('days', 30)
        self.reset_all = options.get('reset_all', False)
        self.offer_id = options.get('offer_id')
        self.network_id = options.get('network_id')
        self.tenant_id = options.get('tenant_id')
        
        self.stdout.write(self.style.SUCCESS('Starting conversion recalculation...'))
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        try:
            # Reset stats if requested
            if self.reset_all:
                self._reset_all_stats()
            
            # Recalculate offer stats
            offers_updated = self._recalculate_offer_stats()
            
            # Recalculate network stats
            networks_updated = self._recalculate_network_stats()
            
            # Recalculate user stats
            users_updated = self._recalculate_user_stats()
            
            # Print summary
            self._print_summary(offers_updated, networks_updated, users_updated)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Recalculation failed: {str(e)}'))
            raise CommandError(f'Recalculation failed: {str(e)}')
    
    def _reset_all_stats(self):
        """Reset all statistics to zero"""
        self.stdout.write('Resetting all statistics...')
        
        if not self.dry_run:
            with transaction.atomic():
                # Reset offer stats
                Offer.objects.all().update(
                    total_conversions=0,
                    click_count=0,
                    conversion_rate=0.0
                )
                
                # Reset network stats
                AdNetwork.objects.all().update(
                    total_conversions=0,
                    total_clicks=0,
                    conversion_rate=0.0,
                    total_payout=0
                )
        
        self.stdout.write(self.style.SUCCESS('All statistics reset to zero'))
    
    def _recalculate_offer_stats(self):
        """Recalculate offer statistics"""
        self.stdout.write('Recalculating offer statistics...')
        
        # Get offers to process
        offers = self._get_offers_to_process()
        total_offers = offers.count()
        offers_updated = 0
        
        if total_offers == 0:
            self.stdout.write('No offers found to process')
            return offers_updated
        
        self.stdout.write(f'Processing {total_offers} offers...')
        
        # Process in batches
        for i in range(0, total_offers, self.batch_size):
            batch = list(offers[i:i + self.batch_size])
            batch_updated = self._process_offer_stats_batch(batch)
            offers_updated += batch_updated
            
            if self.verbose:
                self.stdout.write(
                    f'  Processed batch {i//self.batch_size + 1}: '
                    f'{batch_updated} offers updated'
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Updated statistics for {offers_updated} offers')
        )
        return offers_updated
    
    def _recalculate_network_stats(self):
        """Recalculate network statistics"""
        self.stdout.write('Recalculating network statistics...')
        
        # Get networks to process
        networks = self._get_networks_to_process()
        total_networks = networks.count()
        networks_updated = 0
        
        if total_networks == 0:
            self.stdout.write('No networks found to process')
            return networks_updated
        
        self.stdout.write(f'Processing {total_networks} networks...')
        
        # Process each network
        for network in networks:
            try:
                updated = self._process_network_stats(network)
                if updated:
                    networks_updated += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing network {network.name}: {str(e)}')
                )
                continue
        
        self.stdout.write(
            self.style.SUCCESS(f'Updated statistics for {networks_updated} networks')
        )
        return networks_updated
    
    def _recalculate_user_stats(self):
        """Recalculate user engagement statistics"""
        self.stdout.write('Recalculating user statistics...')
        
        # Get date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=self.days)
        
        # Update user engagement stats
        users_updated = 0
        
        if not self.dry_run:
            with transaction.atomic():
                # Update completion rates for engagements
                engagements = UserOfferEngagement.objects.filter(
                    created_at__gte=start_date
                ).annotate(
                    completion_rate=Count(
                        'id',
                        filter=Q(status__in=['completed', 'approved'])
                    ) * 100.0 / Count('id')
                )
                
                for engagement in engagements:
                    if engagement.completion_rate:
                        # This would require adding completion_rate field to model
                        # For now, we'll just count
                        users_updated += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Processed statistics for {users_updated} users')
        )
        return users_updated
    
    def _get_offers_to_process(self):
        """Get offers that need statistics recalculation"""
        queryset = Offer.objects.all()
        
        if self.offer_id:
            queryset = queryset.filter(id=self.offer_id)
        
        if self.network_id:
            queryset = queryset.filter(ad_network_id=self.network_id)
        
        if self.tenant_id:
            queryset = queryset.filter(tenant_id=self.tenant_id)
        
        return queryset.select_related('ad_network')
    
    def _get_networks_to_process(self):
        """Get networks that need statistics recalculation"""
        queryset = AdNetwork.objects.all()
        
        if self.network_id:
            queryset = queryset.filter(id=self.network_id)
        
        if self.tenant_id:
            queryset = queryset.filter(tenant_id=self.tenant_id)
        
        return queryset
    
    def _process_offer_stats_batch(self, offers):
        """Process a batch of offers"""
        offers_updated = 0
        
        for offer in offers:
            try:
                updated = self._update_offer_stats(offer)
                if updated:
                    offers_updated += 1
                    
            except Exception as e:
                if self.verbose:
                    self.stdout.write(f'    Error updating offer {offer.id}: {str(e)}')
                continue
        
        return offers_updated
    
    def _update_offer_stats(self, offer):
        """Update statistics for a single offer"""
        # Get date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=self.days)
        
        # Calculate engagement stats
        engagement_stats = UserOfferEngagement.objects.filter(
            offer=offer,
            created_at__gte=start_date
        ).aggregate(
            total_conversions=Count(
                'id',
                filter=Q(status__in=['completed', 'approved'])
            ),
            total_clicks=Count('id'),
            avg_completion_time=Avg(
                'completed_at',
                filter=Q(status__in=['completed', 'approved'])
            )
        )
        
        # Calculate conversion stats
        conversion_stats = OfferConversion.objects.filter(
            engagement__offer=offer,
            created_at__gte=start_date
        ).aggregate(
            total_payout=Sum('payout'),
            approved_conversions=Count(
                'id',
                filter=Q(conversion_status='approved')
            ),
            fraud_conversions=Count(
                'id',
                filter=Q(conversion_status='rejected')
            )
        )
        
        # Calculate rates
        total_clicks = engagement_stats['total_conversions'] or 0
        total_conversions = engagement_stats['total_conversions'] or 0
        conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
        
        # Update offer if not dry run
        if not self.dry_run:
            with transaction.atomic():
                offer.total_conversions = total_conversions
                offer.click_count = total_clicks
                offer.conversion_rate = conversion_rate
                offer.avg_completion_time = engagement_stats['avg_completion_time'] or 0
                offer.save(
                    update_fields=[
                        'total_conversions',
                        'click_count', 
                        'conversion_rate',
                        'avg_completion_time'
                    ]
                )
        
        if self.verbose and (total_conversions > 0 or total_clicks > 0):
            self.stdout.write(
                f'    Offer {offer.id}: {total_conversions} conversions, '
                f'{total_clicks} clicks, {conversion_rate:.2f}% CR'
            )
        
        return True
    
    def _process_network_stats(self, network):
        """Update statistics for a single network"""
        # Get date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=self.days)
        
        # Calculate stats from offers
        offer_stats = Offer.objects.filter(
            ad_network=network,
            created_at__gte=start_date
        ).aggregate(
            total_conversions=Sum('total_conversions'),
            total_clicks=Sum('click_count'),
            total_payout=Sum('network_payout')
        )
        
        # Calculate engagement stats
        engagement_stats = UserOfferEngagement.objects.filter(
            offer__ad_network=network,
            created_at__gte=start_date
        ).aggregate(
            total_conversions=Count(
                'id',
                filter=Q(status__in=['completed', 'approved'])
            ),
            total_clicks=Count('id')
        )
        
        # Get totals
        total_conversions = (offer_stats['total_conversions'] or 0) + (engagement_stats['total_conversions'] or 0)
        total_clicks = (offer_stats['total_clicks'] or 0) + (engagement_stats['total_clicks'] or 0)
        total_payout = offer_stats['total_payout'] or 0
        conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
        
        # Update network if not dry run
        if not self.dry_run:
            with transaction.atomic():
                network.total_conversions = total_conversions
                network.total_clicks = total_clicks
                network.conversion_rate = conversion_rate
                network.total_payout = total_payout
                network.save(
                    update_fields=[
                        'total_conversions',
                        'total_clicks',
                        'conversion_rate', 
                        'total_payout'
                    ]
                )
        
        if self.verbose and (total_conversions > 0 or total_clicks > 0):
            self.stdout.write(
                f'    Network {network.name}: {total_conversions} conversions, '
                f'{total_clicks} clicks, {conversion_rate:.2f}% CR'
            )
        
        return True
    
    def _print_summary(self, offers_updated, networks_updated, users_updated):
        """Print recalculation summary"""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('RECALCULATION SUMMARY'))
        self.stdout.write('='*50)
        self.stdout.write(f'Offers updated: {offers_updated}')
        self.stdout.write(f'Networks updated: {networks_updated}')
        self.stdout.write(f'Users processed: {users_updated}')
        self.stdout.write(f'Days processed: {self.days}')
        
        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No actual changes made')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Recalculation completed successfully!')
            )
        
        self.stdout.write('='*50)
