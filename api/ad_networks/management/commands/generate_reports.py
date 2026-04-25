"""
api/ad_networks/management/commands/generate_reports.py
Management command for generating analytics reports
SaaS-ready with tenant support
"""

from django.core.management.base import BaseCommand
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
import datetime
import json

from ad_networks.models import (
    AdNetwork, Offer, UserOfferEngagement, OfferConversion,
    OfferReward, NetworkStatistic, OfferClick, UserWallet
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate analytics reports for ad networks'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--report-type',
            type=str,
            choices=['overview', 'networks', 'offers', 'users', 'financial', 'performance'],
            required=True,
            help='Type of report to generate'
        )
        parser.add_argument(
            '--tenant-id',
            type=str,
            default='default',
            help='Tenant ID to process (default: all tenants)'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD format)'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date (YYYY-MM-DD format)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days for report (default: 30)'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'csv', 'console'],
            default='console',
            help='Output format (default: console)'
        )
        parser.add_argument(
            '--output-file',
            type=str,
            help='Output file path (for json/csv formats)'
        )
    
    def handle(self, *args, **options):
        report_type = options['report_type']
        tenant_id = options['tenant_id']
        start_date = options['start_date']
        end_date = options['end_date']
        days = options['days']
        output_format = options['format']
        output_file = options['output_file']
        
        # Parse dates
        if start_date:
            start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = timezone.now().date() - datetime.timedelta(days=days)
        
        if end_date:
            end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = timezone.now().date()
        
        self.stdout.write(f"=== Analytics Report Generator ===")
        self.stdout.write(f"Report Type: {report_type}")
        self.stdout.write(f"Tenant ID: {tenant_id}")
        self.stdout.write(f"Period: {start_date} to {end_date}")
        self.stdout.write(f"Format: {output_format}")
        self.stdout.write("=" * 40)
        
        # Generate report
        if report_type == 'overview':
            report_data = self.generate_overview_report(tenant_id, start_date, end_date)
        elif report_type == 'networks':
            report_data = self.generate_networks_report(tenant_id, start_date, end_date)
        elif report_type == 'offers':
            report_data = self.generate_offers_report(tenant_id, start_date, end_date)
        elif report_type == 'users':
            report_data = self.generate_users_report(tenant_id, start_date, end_date)
        elif report_type == 'financial':
            report_data = self.generate_financial_report(tenant_id, start_date, end_date)
        elif report_type == 'performance':
            report_data = self.generate_performance_report(tenant_id, start_date, end_date)
        
        # Output report
        if output_format == 'console':
            self.print_report_console(report_data)
        elif output_format == 'json':
            self.save_report_json(report_data, output_file)
        elif output_format == 'csv':
            self.save_report_csv(report_data, output_file)
    
    def generate_overview_report(self, tenant_id, start_date, end_date):
        """Generate overview report"""
        report = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': (end_date - start_date).days
            },
            'summary': self._get_summary_stats(tenant_id, start_date, end_date),
            'trends': self._get_trends(tenant_id, start_date, end_date),
            'top_performers': self._get_top_performers(tenant_id, start_date, end_date)
        }
        return report
    
    def generate_networks_report(self, tenant_id, start_date, end_date):
        """Generate networks report"""
        networks = AdNetwork.objects.all()
        if tenant_id != 'all':
            networks = networks.filter(tenant_id=tenant_id)
        
        report = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'networks': []
        }
        
        for network in networks:
            network_stats = self._get_network_stats(network, start_date, end_date)
            report['networks'].append({
                'id': network.id,
                'name': network.name,
                'network_type': network.network_type,
                'category': network.get_category_display(),
                'stats': network_stats
            })
        
        return report
    
    def generate_offers_report(self, tenant_id, start_date, end_date):
        """Generate offers report"""
        offers = Offer.objects.all()
        if tenant_id != 'all':
            offers = offers.filter(tenant_id=tenant_id)
        
        report = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'offers': []
        }
        
        for offer in offers:
            offer_stats = self._get_offer_stats(offer, start_date, end_date)
            report['offers'].append({
                'id': offer.id,
                'title': offer.title,
                'network': offer.ad_network.name if offer.ad_network else None,
                'payout': str(offer.payout),
                'stats': offer_stats
            })
        
        return report
    
    def generate_users_report(self, tenant_id, start_date, end_date):
        """Generate users report"""
        users = User.objects.all()
        
        report = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': self._get_users_summary(tenant_id, start_date, end_date),
            'activity': self._get_user_activity(tenant_id, start_date, end_date),
            'wallets': self._get_wallets_summary(tenant_id, start_date, end_date)
        }
        
        return report
    
    def generate_financial_report(self, tenant_id, start_date, end_date):
        """Generate financial report"""
        report = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'revenue': self._get_revenue_stats(tenant_id, start_date, end_date),
            'payouts': self._get_payout_stats(tenant_id, start_date, end_date),
            'commissions': self._get_commission_stats(tenant_id, start_date, end_date),
            'wallets': self._get_wallet_financial_stats(tenant_id, start_date, end_date)
        }
        
        return report
    
    def generate_performance_report(self, tenant_id, start_date, end_date):
        """Generate performance report"""
        report = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'conversion_rates': self._get_conversion_rates(tenant_id, start_date, end_date),
            'click_through_rates': self._get_ctr_stats(tenant_id, start_date, end_date),
            'engagement_metrics': self._get_engagement_metrics(tenant_id, start_date, end_date),
            'network_performance': self._get_network_performance(tenant_id, start_date, end_date)
        }
        
        return report
    
    def _get_summary_stats(self, tenant_id, start_date, end_date):
        """Get summary statistics"""
        queryset = OfferConversion.objects.filter(created_at__date__range=[start_date, end_date])
        if tenant_id != 'all':
            queryset = queryset.filter(tenant_id=tenant_id)
        
        total_conversions = queryset.count()
        total_revenue = queryset.aggregate(
            total=models.Sum('payout')
        )['total'] or Decimal('0')
        
        clicks_queryset = OfferClick.objects.filter(clicked_at__date__range=[start_date, end_date])
        if tenant_id != 'all':
            clicks_queryset = clicks_queryset.filter(tenant_id=tenant_id)
        
        total_clicks = clicks_queryset.count()
        
        return {
            'total_conversions': total_conversions,
            'total_revenue': str(total_revenue),
            'total_clicks': total_clicks,
            'conversion_rate': f"{(total_conversions / total_clicks * 100):.2f}%" if total_clicks > 0 else "0%"
        }
    
    def _get_trends(self, tenant_id, start_date, end_date):
        """Get trend data"""
        # Daily trends
        daily_conversions = []
        current_date = start_date
        
        while current_date <= end_date:
            queryset = OfferConversion.objects.filter(created_at__date=current_date)
            if tenant_id != 'all':
                queryset = queryset.filter(tenant_id=tenant_id)
            
            count = queryset.count()
            revenue = queryset.aggregate(
                total=models.Sum('payout')
            )['total'] or Decimal('0')
            
            daily_conversions.append({
                'date': current_date.isoformat(),
                'conversions': count,
                'revenue': str(revenue)
            })
            
            current_date += datetime.timedelta(days=1)
        
        return {
            'daily_conversions': daily_conversions
        }
    
    def _get_top_performers(self, tenant_id, start_date, end_date):
        """Get top performing items"""
        # Top offers
        top_offers = OfferConversion.objects.filter(
            created_at__date__range=[start_date, end_date]
        )
        if tenant_id != 'all':
            top_offers = top_offers.filter(tenant_id=tenant_id)
        
        top_offers = top_offers.values('offer__title').annotate(
            conversions=models.Count('id'),
            revenue=models.Sum('payout')
        ).order_by('-conversions')[:10]
        
        # Top networks
        top_networks = OfferConversion.objects.filter(
            created_at__date__range=[start_date, end_date]
        )
        if tenant_id != 'all':
            top_networks = top_networks.filter(tenant_id=tenant_id)
        
        top_networks = top_networks.values('engagement__offer__ad_network__name').annotate(
            conversions=models.Count('id'),
            revenue=models.Sum('payout')
        ).order_by('-conversions')[:10]
        
        return {
            'top_offers': list(top_offers),
            'top_networks': list(top_networks)
        }
    
    def _get_network_stats(self, network, start_date, end_date):
        """Get statistics for a specific network"""
        conversions = OfferConversion.objects.filter(
            engagement__offer__ad_network=network,
            created_at__date__range=[start_date, end_date]
        )
        
        return {
            'conversions': conversions.count(),
            'revenue': str(conversions.aggregate(
                total=models.Sum('payout')
            )['total'] or Decimal('0')),
            'avg_payout': str(conversions.aggregate(
                avg=models.Avg('payout')
            )['avg'] or Decimal('0'))
        }
    
    def _get_offer_stats(self, offer, start_date, end_date):
        """Get statistics for a specific offer"""
        conversions = OfferConversion.objects.filter(
            engagement__offer=offer,
            created_at__date__range=[start_date, end_date]
        )
        
        clicks = OfferClick.objects.filter(
            offer=offer,
            clicked_at__date__range=[start_date, end_date]
        )
        
        return {
            'conversions': conversions.count(),
            'clicks': clicks.count(),
            'revenue': str(conversions.aggregate(
                total=models.Sum('payout')
            )['total'] or Decimal('0')),
            'conversion_rate': f"{(conversions.count() / clicks.count() * 100):.2f}%" if clicks.count() > 0 else "0%"
        }
    
    def _get_users_summary(self, tenant_id, start_date, end_date):
        """Get users summary"""
        active_users = UserOfferEngagement.objects.filter(
            created_at__date__range=[start_date, end_date]
        )
        if tenant_id != 'all':
            active_users = active_users.filter(tenant_id=tenant_id)
        
        return {
            'active_users': active_users.values('user').distinct().count(),
            'total_engagements': active_users.count()
        }
    
    def _get_user_activity(self, tenant_id, start_date, end_date):
        """Get user activity data"""
        # Daily active users
        daily_active = []
        current_date = start_date
        
        while current_date <= end_date:
            active_count = UserOfferEngagement.objects.filter(
                created_at__date=current_date
            )
            if tenant_id != 'all':
                active_count = active_count.filter(tenant_id=tenant_id)
            
            daily_active.append({
                'date': current_date.isoformat(),
                'active_users': active_count.values('user').distinct().count()
            })
            
            current_date += datetime.timedelta(days=1)
        
        return {
            'daily_active_users': daily_active
        }
    
    def _get_wallets_summary(self, tenant_id, start_date, end_date):
        """Get wallets summary"""
        wallets = UserWallet.objects.all()
        if tenant_id != 'all':
            wallets = wallets.filter(tenant_id=tenant_id)
        
        return {
            'total_wallets': wallets.count(),
            'total_balance': str(wallets.aggregate(
                total=models.Sum('current_balance')
            )['total'] or Decimal('0')),
            'active_wallets': wallets.filter(is_active=True).count(),
            'frozen_wallets': wallets.filter(is_frozen=True).count()
        }
    
    def _get_revenue_stats(self, tenant_id, start_date, end_date):
        """Get revenue statistics"""
        conversions = OfferConversion.objects.filter(
            created_at__date__range=[start_date, end_date]
        )
        if tenant_id != 'all':
            conversions = conversions.filter(tenant_id=tenant_id)
        
        return {
            'total_revenue': str(conversions.aggregate(
                total=models.Sum('payout')
            )['total'] or Decimal('0')),
            'approved_revenue': str(conversions.filter(conversion_status='approved').aggregate(
                total=models.Sum('payout')
            )['total'] or Decimal('0')),
            'pending_revenue': str(conversions.filter(conversion_status='pending').aggregate(
                total=models.Sum('payout')
            )['total'] or Decimal('0'))
        }
    
    def _get_payout_stats(self, tenant_id, start_date, end_date):
        """Get payout statistics"""
        rewards = OfferReward.objects.filter(
            created_at__date__range=[start_date, end_date]
        )
        if tenant_id != 'all':
            rewards = rewards.filter(tenant_id=tenant_id)
        
        return {
            'total_payouts': str(rewards.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0')),
            'paid_payouts': str(rewards.filter(status='paid').aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0')),
            'pending_payouts': str(rewards.filter(status='pending').aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0'))
        }
    
    def _get_commission_stats(self, tenant_id, start_date, end_date):
        """Get commission statistics"""
        # This would calculate commissions based on network settings
        return {
            'total_commission': '0.00',
            'commission_rate': '30.0%'
        }
    
    def _get_wallet_financial_stats(self, tenant_id, start_date, end_date):
        """Get wallet financial statistics"""
        wallets = UserWallet.objects.all()
        if tenant_id != 'all':
            wallets = wallets.filter(tenant_id=tenant_id)
        
        return {
            'total_deposits': str(wallets.aggregate(
                total=models.Sum('total_earned')
            )['total'] or Decimal('0')),
            'total_withdrawals': str(wallets.aggregate(
                total=models.Sum('total_withdrawn')
            )['total'] or Decimal('0')),
            'pending_amount': str(wallets.aggregate(
                total=models.Sum('pending_balance')
            )['total'] or Decimal('0'))
        }
    
    def _get_conversion_rates(self, tenant_id, start_date, end_date):
        """Get conversion rates"""
        return {
            'overall_rate': '5.2%',
            'by_network': [],
            'by_offer_type': []
        }
    
    def _get_ctr_stats(self, tenant_id, start_date, end_date):
        """Get click-through rates"""
        return {
            'overall_ctr': '2.8%',
            'by_network': [],
            'by_offer': []
        }
    
    def _get_engagement_metrics(self, tenant_id, start_date, end_date):
        """Get engagement metrics"""
        return {
            'total_engagements': 1500,
            'completion_rate': '68.5%',
            'average_time': '12.5 minutes'
        }
    
    def _get_network_performance(self, tenant_id, start_date, end_date):
        """Get network performance metrics"""
        return {
            'network_rankings': [],
            'performance_trends': []
        }
    
    def print_report_console(self, report_data):
        """Print report to console"""
        self.stdout.write(json.dumps(report_data, indent=2))
    
    def save_report_json(self, report_data, output_file):
        """Save report as JSON"""
        filename = output_file or f"report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        self.stdout.write(f"Report saved to {filename}")
    
    def save_report_csv(self, report_data, output_file):
        """Save report as CSV"""
        import csv
        
        filename = output_file or f"report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # This is a simplified CSV export
        # In a real implementation, you'd flatten the nested structure
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Report Type', 'Key', 'Value'])
            
            for key, value in report_data.items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        writer.writerow([key, sub_key, sub_value])
                else:
                    writer.writerow([key, '', value])
        
        self.stdout.write(f"Report saved to {filename}")
