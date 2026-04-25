"""
api/ad_networks/management/commands/export_offer_data.py
Export offer data to CSV command
SaaS-ready with tenant support
"""

import csv
import os
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.http import HttpResponse
import logging

from api.ad_networks.models import Offer, UserOfferEngagement, OfferConversion, AdNetwork
from api.ad_networks.choices import OfferStatus, ConversionStatus

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Export offer data to CSV format'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--output-file',
            type=str,
            help='Output CSV file path (default: auto-generated)'
        )
        parser.add_argument(
            '--tenant-id',
            type=str,
            help='Specific tenant ID to export (optional)'
        )
        parser.add_argument(
            '--network-id',
            type=int,
            help='Specific network ID to export (optional)'
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Filter by category (optional)',
            choices=[cat[0] for cat in OfferStatus.CHOICES]
        )
        parser.add_argument(
            '--status',
            type=str,
            help='Filter by offer status (optional)',
            choices=[status[0] for status in OfferStatus.CHOICES]
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to look back (default: 30)'
        )
        parser.add_argument(
            '--include-stats',
            action='store_true',
            help='Include performance statistics'
        )
        parser.add_argument(
            '--include-conversions',
            action='store_true',
            help='Include conversion data'
        )
        parser.add_argument(
            '--format',
            type=str,
            default='offers',
            choices=['offers', 'conversions', 'engagements', 'networks', 'summary'],
            help='Export format (default: offers)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )
    
    def handle(self, *args, **options):
        self.verbose = options.get('verbose', False)
        self.output_file = options.get('output_file')
        self.tenant_id = options.get('tenant_id')
        self.network_id = options.get('network_id')
        self.category = options.get('category')
        self.status = options.get('status')
        self.days = options.get('days', 30)
        self.include_stats = options.get('include_stats', False)
        self.include_conversions = options.get('include_conversions', False)
        self.export_format = options.get('format', 'offers')
        
        self.stdout.write(self.style.SUCCESS(f'Starting {self.export_format} export...'))
        
        try:
            # Generate output filename if not provided
            if not self.output_file:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                self.output_file = f'ad_networks_{self.export_format}_{timestamp}.csv'
            
            # Export based on format
            if self.export_format == 'offers':
                self._export_offers()
            elif self.export_format == 'conversions':
                self._export_conversions()
            elif self.export_format == 'engagements':
                self._export_engagements()
            elif self.export_format == 'networks':
                self._export_networks()
            elif self.export_format == 'summary':
                self._export_summary()
            
            self.stdout.write(
                self.style.SUCCESS(f'Export completed: {self.output_file}')
            )
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Export failed: {str(e)}'))
            raise CommandError(f'Export failed: {str(e)}')
    
    def _export_offers(self):
        """Export offers data"""
        self.stdout.write('Exporting offers data...')
        
        # Get offers queryset
        offers = self._get_offers_queryset()
        
        # Prepare CSV headers
        headers = [
            'ID', 'Title', 'Description', 'Network', 'Category',
            'Reward Amount', 'Currency', 'Status', 'Difficulty',
            'Estimated Time', 'Countries', 'Platforms', 'Device Type',
            'Total Conversions', 'Click Count', 'Conversion Rate',
            'Created At', 'Updated At', 'Expires At'
        ]
        
        if self.include_stats:
            headers.extend([
                'EPC', 'Quality Score', 'Avg Completion Time',
                'Revenue', 'Fraud Score'
            ])
        
        # Write CSV
        with open(self.output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            
            for offer in offers:
                row = [
                    offer.id,
                    offer.title,
                    offer.description[:100] + '...' if len(offer.description) > 100 else offer.description,
                    offer.ad_network.name if offer.ad_network else 'N/A',
                    offer.category.name if offer.category else 'N/A',
                    offer.reward_amount,
                    offer.reward_currency,
                    offer.status,
                    offer.difficulty,
                    offer.estimated_time,
                    str(offer.countries),
                    str(offer.platforms),
                    offer.device_type,
                    offer.total_conversions,
                    offer.click_count,
                    f'{offer.conversion_rate:.2f}%',
                    offer.created_at.isoformat() if offer.created_at else '',
                    offer.updated_at.isoformat() if offer.updated_at else '',
                    offer.expires_at.isoformat() if offer.expires_at else '',
                ]
                
                if self.include_stats:
                    row.extend([
                        offer.epc or 0,
                        offer.quality_score,
                        offer.avg_completion_time,
                        offer.total_conversions * offer.reward_amount,
                        offer.fraud_score
                    ])
                
                writer.writerow(row)
        
        total_offers = offers.count()
        self.stdout.write(f'Exported {total_offers} offers')
    
    def _export_conversions(self):
        """Export conversions data"""
        self.stdout.write('Exporting conversions data...')
        
        # Get conversions queryset
        conversions = self._get_conversions_queryset()
        
        # Prepare CSV headers
        headers = [
            'ID', 'User', 'Offer', 'Network', 'Status',
            'Payout', 'Currency', 'Conversion Status',
            'Fraud Score', 'Risk Level', 'Created At',
            'Verified At', 'Payment Date', 'Payment Method'
        ]
        
        # Write CSV
        with open(self.output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            
            for conversion in conversions.select_related(
                'engagement__user', 'engagement__offer', 'engagement__offer__ad_network'
            ):
                row = [
                    conversion.id,
                    conversion.engagement.user.username if conversion.engagement.user else 'N/A',
                    conversion.engagement.offer.title if conversion.engagement.offer else 'N/A',
                    conversion.engagement.offer.ad_network.name if conversion.engagement.offer and conversion.engagement.offer.ad_network else 'N/A',
                    conversion.conversion_status,
                    conversion.payout,
                    conversion.network_currency,
                    conversion.is_verified,
                    conversion.fraud_score,
                    conversion.risk_level,
                    conversion.created_at.isoformat() if conversion.created_at else '',
                    conversion.verified_at.isoformat() if conversion.verified_at else '',
                    conversion.payment_date.isoformat() if conversion.payment_date else '',
                    conversion.payment_method,
                ]
                
                writer.writerow(row)
        
        total_conversions = conversions.count()
        self.stdout.write(f'Exported {total_conversions} conversions')
    
    def _export_engagements(self):
        """Export user engagements data"""
        self.stdout.write('Exporting engagements data...')
        
        # Get engagements queryset
        engagements = self._get_engagements_queryset()
        
        # Prepare CSV headers
        headers = [
            'ID', 'User', 'Offer', 'Network', 'Status',
            'Reward Earned', 'Click ID', 'Conversion ID',
            'IP Address', 'Country', 'Device', 'Browser',
            'Clicked At', 'Started At', 'Completed At',
            'Time Spent (seconds)', 'Progress'
        ]
        
        # Write CSV
        with open(self.output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            
            for engagement in engagements.select_related(
                'user', 'offer', 'offer__ad_network'
            ):
                row = [
                    engagement.id,
                    engagement.user.username if engagement.user else 'N/A',
                    engagement.offer.title if engagement.offer else 'N/A',
                    engagement.offer.ad_network.name if engagement.offer and engagement.offer.ad_network else 'N/A',
                    engagement.status,
                    engagement.reward_earned,
                    engagement.click_id,
                    engagement.conversion_id,
                    engagement.ip_address,
                    engagement.location_data.get('country', '') if engagement.location_data else '',
                    engagement.device_info.get('device', '') if engagement.device_info else '',
                    engagement.browser,
                    engagement.clicked_at.isoformat() if engagement.clicked_at else '',
                    engagement.started_at.isoformat() if engagement.started_at else '',
                    engagement.completed_at.isoformat() if engagement.completed_at else '',
                    engagement.time_spent or 0,
                    f'{engagement.progress:.1f}%',
                ]
                
                writer.writerow(row)
        
        total_engagements = engagements.count()
        self.stdout.write(f'Exported {total_engagements} engagements')
    
    def _export_networks(self):
        """Export networks data"""
        self.stdout.write('Exporting networks data...')
        
        # Get networks queryset
        networks = self._get_networks_queryset()
        
        # Prepare CSV headers
        headers = [
            'ID', 'Name', 'Network Type', 'Category', 'Status',
            'Country Support', 'Min Payout', 'Max Payout',
            'Commission Rate', 'Payment Methods', 'Rating',
            'Trust Score', 'Total Conversions', 'Total Clicks',
            'Conversion Rate', 'Total Payout', 'EPC',
            'Last Sync', 'Is Active', 'Is Verified'
        ]
        
        # Write CSV
        with open(self.output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            
            for network in networks:
                row = [
                    network.id,
                    network.name,
                    network.network_type,
                    network.category,
                    'Active' if network.is_active else 'Inactive',
                    network.country_support,
                    network.min_payout,
                    network.max_payout,
                    network.commission_rate,
                    str(network.payment_methods),
                    network.rating,
                    network.trust_score,
                    network.total_conversions,
                    network.total_clicks,
                    f'{network.conversion_rate:.2f}%',
                    network.total_payout,
                    network.epc or 0,
                    network.last_sync.isoformat() if network.last_sync else '',
                    network.is_active,
                    network.is_verified,
                ]
                
                writer.writerow(row)
        
        total_networks = networks.count()
        self.stdout.write(f'Exported {total_networks} networks')
    
    def _export_summary(self):
        """Export summary statistics"""
        self.stdout.write('Exporting summary statistics...')
        
        # Get date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=self.days)
        
        # Calculate summary stats
        offers_stats = self._get_offers_queryset().aggregate(
            total_offers=Count('id'),
            active_offers=Count('id', filter=Q(status='active')),
            total_conversions=Sum('total_conversions'),
            total_clicks=Sum('click_count'),
            avg_reward=Avg('reward_amount'),
            total_payout=Sum('total_conversions') * Avg('reward_amount')
        )
        
        networks_stats = self._get_networks_queryset().aggregate(
            total_networks=Count('id'),
            active_networks=Count('id', filter=Q(is_active=True)),
            verified_networks=Count('id', filter=Q(is_verified=True)),
            avg_rating=Avg('rating'),
            avg_trust_score=Avg('trust_score')
        )
        
        conversions_stats = self._get_conversions_queryset().filter(
            created_at__gte=start_date
        ).aggregate(
            total_conversions=Count('id'),
            approved_conversions=Count('id', filter=Q(conversion_status='approved')),
            rejected_conversions=Count('id', filter=Q(conversion_status='rejected')),
            fraud_conversions=Count('id', filter=Q(fraud_score__gte=70)),
            total_payout=Sum('payout'),
            avg_payout=Avg('payout')
        )
        
        # Prepare CSV headers and data
        headers = ['Metric', 'Value', 'Description']
        data = [
            ['Report Generated', timezone.now().isoformat(), 'Timestamp when report was generated'],
            ['Date Range', f'{start_date.date()} to {end_date.date()}', 'Period covered by this report'],
            ['Total Offers', offers_stats['total_offers'] or 0, 'Total number of offers'],
            ['Active Offers', offers_stats['active_offers'] or 0, 'Currently active offers'],
            ['Total Conversions', offers_stats['total_conversions'] or 0, 'Total all-time conversions'],
            ['Total Clicks', offers_stats['total_clicks'] or 0, 'Total all-time clicks'],
            ['Average Reward', f"${offers_stats['avg_reward'] or 0:.2f}", 'Average reward amount per offer'],
            ['Total Networks', networks_stats['total_networks'] or 0, 'Total number of networks'],
            ['Active Networks', networks_stats['active_networks'] or 0, 'Currently active networks'],
            ['Verified Networks', networks_stats['verified_networks'] or 0, 'Verified networks'],
            ['Average Network Rating', f"{networks_stats['avg_rating'] or 0:.1f}", 'Average network rating'],
            ['Average Trust Score', f"{networks_stats['avg_trust_score'] or 0:.1f}", 'Average network trust score'],
            ['Period Conversions', conversions_stats['total_conversions'] or 0, f'Conversions in last {self.days} days'],
            ['Approved Conversions', conversions_stats['approved_conversions'] or 0, 'Approved conversions in period'],
            ['Rejected Conversions', conversions_stats['rejected_conversions'] or 0, 'Rejected conversions in period'],
            ['Fraud Conversions', conversions_stats['fraud_conversions'] or 0, 'High fraud score conversions'],
            ['Period Payout', f"${conversions_stats['total_payout'] or 0:.2f}", f'Total payout in last {self.days} days'],
            ['Average Payout', f"${conversions_stats['avg_payout'] or 0:.2f}", 'Average payout per conversion'],
        ]
        
        # Write CSV
        with open(self.output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            writer.writerows(data)
        
        self.stdout.write(f'Exported summary with {len(data)} metrics')
    
    def _get_offers_queryset(self):
        """Get filtered offers queryset"""
        queryset = Offer.objects.all()
        
        if self.tenant_id:
            queryset = queryset.filter(tenant_id=self.tenant_id)
        
        if self.network_id:
            queryset = queryset.filter(ad_network_id=self.network_id)
        
        if self.category:
            queryset = queryset.filter(category__slug=self.category)
        
        if self.status:
            queryset = queryset.filter(status=self.status)
        
        return queryset.select_related('ad_network', 'category')
    
    def _get_conversions_queryset(self):
        """Get filtered conversions queryset"""
        queryset = OfferConversion.objects.all()
        
        if self.tenant_id:
            queryset = queryset.filter(tenant_id=self.tenant_id)
        
        if self.network_id:
            queryset = queryset.filter(engagement__offer__ad_network_id=self.network_id)
        
        return queryset
    
    def _get_engagements_queryset(self):
        """Get filtered engagements queryset"""
        queryset = UserOfferEngagement.objects.all()
        
        if self.tenant_id:
            queryset = queryset.filter(tenant_id=self.tenant_id)
        
        if self.network_id:
            queryset = queryset.filter(offer__ad_network_id=self.network_id)
        
        if self.days:
            start_date = timezone.now() - timedelta(days=self.days)
            queryset = queryset.filter(created_at__gte=start_date)
        
        return queryset
    
    def _get_networks_queryset(self):
        """Get filtered networks queryset"""
        queryset = AdNetwork.objects.all()
        
        if self.tenant_id:
            queryset = queryset.filter(tenant_id=self.tenant_id)
        
        if self.network_id:
            queryset = queryset.filter(id=self.network_id)
        
        return queryset
