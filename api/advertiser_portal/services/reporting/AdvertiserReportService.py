"""
Advertiser Report Service

Service for generating advertiser reports,
including performance, financial, and custom reports.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.reporting import AdvertiserReport, CampaignReport, PublisherBreakdown, GeoBreakdown, CreativePerformance
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class AdvertiserReportService:
    """
    Service for generating advertiser reports.
    
    Handles performance reports, financial reports,
    and custom report generation.
    """
    
    def __init__(self):
        self.logger = logger
    
    def generate_advertiser_report(self, advertiser, report_type: str, period: str, start_date, end_date, filters: Dict[str, Any] = None) -> AdvertiserReport:
        """
        Generate advertiser report.
        
        Args:
            advertiser: Advertiser instance
            report_type: Type of report
            period: Reporting period
            start_date: Report start date
            end_date: Report end date
            filters: Optional filters
            
        Returns:
            AdvertiserReport: Generated report instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Validate report parameters
                self._validate_report_parameters(report_type, period, start_date, end_date)
                
                # Generate report data
                report_data = self._generate_report_data(advertiser, report_type, period, start_date, end_date, filters)
                
                # Create report record
                report = AdvertiserReport.objects.create(
                    advertiser=advertiser,
                    report_type=report_type,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                    data=report_data,
                    status='completed',
                    file_path=None,  # Would be generated if needed
                    generated_at=timezone.now(),
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                )
                
                # Send notification
                self._send_report_generated_notification(advertiser, report)
                
                self.logger.info(f"Generated advertiser report: {report_type} for {advertiser.company_name}")
                return report
                
        except Exception as e:
            self.logger.error(f"Error generating advertiser report: {e}")
            raise ValidationError(f"Failed to generate advertiser report: {str(e)}")
    
    def generate_campaign_report(self, campaign, report_type: str, period: str, start_date, end_date) -> CampaignReport:
        """
        Generate campaign report.
        
        Args:
            campaign: Campaign instance
            report_type: Type of report
            period: Reporting period
            start_date: Report start date
            end_date: Report end date
            
        Returns:
            CampaignReport: Generated report instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Validate report parameters
                self._validate_report_parameters(report_type, period, start_date, end_date)
                
                # Generate campaign report data
                report_data = self._generate_campaign_report_data(campaign, report_type, period, start_date, end_date)
                
                # Create campaign report record
                report = CampaignReport.objects.create(
                    campaign=campaign,
                    date=end_date,  # Daily report
                    report_type=report_type,
                    period=period,
                    impressions=report_data.get('impressions', 0),
                    clicks=report_data.get('clicks', 0),
                    conversions=report_data.get('conversions', 0),
                    spend_amount=report_data.get('spend_amount', 0.00),
                    ctr=report_data.get('ctr', 0.00),
                    conversion_rate=report_data.get('conversion_rate', 0.00),
                    cpa=report_data.get('cpa', 0.00),
                    cpc=report_data.get('cpc', 0.00),
                    data=report_data,
                    generated_at=timezone.now(),
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                )
                
                self.logger.info(f"Generated campaign report: {report_type} for {campaign.name}")
                return report
                
        except Exception as e:
            self.logger.error(f"Error generating campaign report: {e}")
            raise ValidationError(f"Failed to generate campaign report: {str(e)}")
    
    def get_performance_report(self, advertiser, start_date, end_date, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get performance report data.
        
        Args:
            advertiser: Advertiser instance
            start_date: Report start date
            end_date: Report end date
            filters: Optional filters
            
        Returns:
            Dict[str, Any]: Performance report data
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Get campaign reports for the period
            campaign_reports = CampaignReport.objects.filter(
                campaign__advertiser=advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).select_related('campaign')
            
            # Aggregate performance data
            performance_data = campaign_reports.aggregate(
                total_impressions=models.Sum('impressions'),
                total_clicks=models.Sum('clicks'),
                total_conversions=models.Sum('conversions'),
                total_spend=models.Sum('spend_amount'),
                avg_ctr=models.Avg('ctr'),
                avg_conversion_rate=models.Avg('conversion_rate'),
                avg_cpa=models.Avg('cpa'),
                avg_cpc=models.Avg('cpc'),
                campaign_count=models.Count('campaign', distinct=True),
            )
            
            # Fill missing values
            for key, value in performance_data.items():
                if value is None:
                    performance_data[key] = 0
            
            # Calculate derived metrics
            total_impressions = performance_data['total_impressions']
            total_clicks = performance_data['total_clicks']
            total_conversions = performance_data['total_conversions']
            total_spend = performance_data['total_spend']
            
            calculated_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            calculated_cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
            calculated_cpa = (total_spend / total_conversions) if total_conversions > 0 else 0
            
            # Get daily breakdown
            daily_data = {}
            current_date = start_date
            while current_date <= end_date:
                day_reports = campaign_reports.filter(date=current_date)
                day_data = day_reports.aggregate(
                    impressions=models.Sum('impressions'),
                    clicks=models.Sum('clicks'),
                    conversions=models.Sum('conversions'),
                    spend=models.Sum('spend_amount')
                )
                
                daily_data[current_date.isoformat()] = {
                    'impressions': day_data['impressions'] or 0,
                    'clicks': day_data['clicks'] or 0,
                    'conversions': day_data['conversions'] or 0,
                    'spend': float(day_data['spend'] or 0),
                }
                
                current_date += timezone.timedelta(days=1)
            
            return {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': (end_date - start_date).days + 1,
                },
                'summary': {
                    'total_impressions': total_impressions,
                    'total_clicks': total_clicks,
                    'total_conversions': total_conversions,
                    'total_spend': float(total_spend),
                    'campaign_count': performance_data['campaign_count'],
                    'ctr': float(calculated_ctr),
                    'cpc': float(calculated_cpc),
                    'cpa': float(calculated_cpa),
                    'conversion_rate': float((total_conversions / total_clicks * 100) if total_clicks > 0 else 0),
                },
                'daily_breakdown': daily_data,
                'top_campaigns': self._get_top_campaigns(advertiser, start_date, end_date),
                'generated_at': timezone.now().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting performance report: {e}")
            raise ValidationError(f"Failed to get performance report: {str(e)}")
    
    def get_financial_report(self, advertiser, start_date, end_date) -> Dict[str, Any]:
        """
        Get financial report data.
        
        Args:
            advertiser: Advertiser instance
            start_date: Report start date
            end_date: Report end date
            
        Returns:
            Dict[str, Any]: Financial report data
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            from ...models.billing import AdvertiserTransaction, AdvertiserDeposit, AdvertiserInvoice
            
            # Get transaction data
            transactions = AdvertiserTransaction.objects.filter(
                wallet__advertiser=advertiser,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            ).select_related('wallet')
            
            # Get deposit data
            deposits = AdvertiserDeposit.objects.filter(
                advertiser=advertiser,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
                status='completed'
            )
            
            # Get invoice data
            invoices = AdvertiserInvoice.objects.filter(
                advertiser=advertiser,
                start_date__gte=start_date,
                end_date__lte=end_date
            )
            
            # Aggregate financial data
            spend_data = transactions.filter(transaction_type='spend').aggregate(
                total_spend=models.Sum('amount'),
                spend_count=models.Count('id')
            )
            
            deposit_data = deposits.aggregate(
                total_deposits=models.Sum('net_amount'),
                deposit_count=models.Count('id'),
                total_fees=models.Sum('processing_fee')
            )
            
            invoice_data = invoices.aggregate(
                total_invoiced=models.Sum('total_amount'),
                invoice_count=models.Count('id'),
                paid_amount=models.Sum(models.Case(
                    When(status='paid', then=models.F('total_amount')),
                    default=0,
                ))
            )
            
            # Fill missing values
            for key, value in {**spend_data, **deposit_data, **invoice_data}.items():
                if value is None:
                    if key in spend_data:
                        spend_data[key] = 0
                    elif key in deposit_data:
                        deposit_data[key] = 0
                    elif key in invoice_data:
                        invoice_data[key] = 0
            
            # Calculate net flow
            total_spend = spend_data['total_spend']
            total_deposits = deposit_data['total_deposits']
            net_flow = total_deposits - total_spend
            
            return {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': (end_date - start_date).days + 1,
                },
                'spending': {
                    'total_spend': float(total_spend),
                    'spend_count': spend_data['spend_count'],
                    'avg_spend_per_transaction': float(total_spend / spend_data['spend_count']) if spend_data['spend_count'] > 0 else 0,
                },
                'deposits': {
                    'total_deposits': float(total_deposits),
                    'deposit_count': deposit_data['deposit_count'],
                    'total_fees': float(deposit_data['total_fees']),
                    'net_deposits': float(total_deposits - deposit_data['total_fees']),
                },
                'invoices': {
                    'total_invoiced': float(invoice_data['total_invoiced']),
                    'invoice_count': invoice_data['invoice_count'],
                    'paid_amount': float(invoice_data['paid_amount']),
                    'outstanding_amount': float(invoice_data['total_invoiced'] - invoice_data['paid_amount']),
                },
                'summary': {
                    'net_flow': float(net_flow),
                    'current_balance': float(self._get_current_balance(advertiser)),
                    'roi': float((total_deposits - total_spend) / total_spend * 100) if total_spend > 0 else 0,
                },
                'daily_breakdown': self._get_financial_daily_breakdown(advertiser, start_date, end_date),
                'generated_at': timezone.now().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting financial report: {e}")
            raise ValidationError(f"Failed to get financial report: {str(e)}")
    
    def get_report_history(self, advertiser, report_type: str = None, limit: int = 50) -> List[AdvertiserReport]:
        """
        Get report history for advertiser.
        
        Args:
            advertiser: Advertiser instance
            report_type: Optional report type filter
            limit: Maximum number of records
            
        Returns:
            List[AdvertiserReport]: Report history
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            queryset = AdvertiserReport.objects.filter(advertiser=advertiser).order_by('-generated_at')
            
            if report_type:
                queryset = queryset.filter(report_type=report_type)
            
            return list(queryset[:limit])
            
        except Exception as e:
            self.logger.error(f"Error getting report history: {e}")
            raise ValidationError(f"Failed to get report history: {str(e)}")
    
    def schedule_report(self, advertiser, report_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Schedule recurring report.
        
        Args:
            advertiser: Advertiser instance
            report_config: Report configuration
            
        Returns:
            Dict[str, Any]: Scheduling result
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Validate report configuration
                self._validate_report_config(report_config)
                
                # Store scheduled report in metadata
                metadata = advertiser.profile.metadata or {}
                
                if 'scheduled_reports' not in metadata:
                    metadata['scheduled_reports'] = []
                
                scheduled_report = {
                    'id': f"schedule_{timezone.now().timestamp()}",
                    'name': report_config.get('name', 'Unnamed Report'),
                    'report_type': report_config.get('report_type'),
                    'frequency': report_config.get('frequency', 'daily'),
                    'recipients': report_config.get('recipients', []),
                    'format': report_config.get('format', 'pdf'),
                    'filters': report_config.get('filters', {}),
                    'created_at': timezone.now().isoformat(),
                    'is_active': True,
                    'next_run': self._calculate_next_run(report_config.get('frequency')),
                    'last_run': None,
                }
                
                metadata['scheduled_reports'].append(scheduled_report)
                advertiser.profile.metadata = metadata
                advertiser.profile.save()
                
                # Send notification
                self._send_report_scheduled_notification(advertiser, scheduled_report)
                
                self.logger.info(f"Scheduled report: {scheduled_report['name']} for {advertiser.company_name}")
                
                return scheduled_report
                
        except Exception as e:
            self.logger.error(f"Error scheduling report: {e}")
            raise ValidationError(f"Failed to schedule report: {str(e)}")
    
    def _validate_report_parameters(self, report_type: str, period: str, start_date, end_date):
        """Validate report parameters."""
        valid_types = ['performance', 'financial', 'campaign', 'creative', 'geo', 'publisher']
        if report_type not in valid_types:
            raise ValidationError(f"Invalid report type: {report_type}")
        
        valid_periods = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'custom']
        if period not in valid_periods:
            raise ValidationError(f"Invalid period: {period}")
        
        if start_date >= end_date:
            raise ValidationError("Start date must be before end date")
        
        if end_date > timezone.now().date():
            raise ValidationError("End date cannot be in the future")
    
    def _generate_report_data(self, advertiser, report_type: str, period: str, start_date, end_date, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate report data based on type."""
        if report_type == 'performance':
            return self.get_performance_report(advertiser, start_date, end_date, filters)
        elif report_type == 'financial':
            return self.get_financial_report(advertiser, start_date, end_date)
        else:
            return {'message': f'Report type {report_type} not implemented yet'}
    
    def _generate_campaign_report_data(self, campaign, report_type: str, period: str, start_date, end_date) -> Dict[str, Any]:
        """Generate campaign report data."""
        # This would implement campaign-specific report generation
        return {
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'report_type': report_type,
            'period': period,
            'impressions': 0,
            'clicks': 0,
            'conversions': 0,
            'spend_amount': 0.00,
            'ctr': 0.00,
            'conversion_rate': 0.00,
            'cpa': 0.00,
            'cpc': 0.00,
        }
    
    def _get_top_campaigns(self, advertiser, start_date, end_date, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top performing campaigns."""
        try:
            campaign_reports = CampaignReport.objects.filter(
                campaign__advertiser=advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).values('campaign__id', 'campaign__name').annotate(
                total_impressions=models.Sum('impressions'),
                total_clicks=models.Sum('clicks'),
                total_conversions=models.Sum('conversions'),
                total_spend=models.Sum('spend_amount')
            ).order_by('-total_spend')[:limit]
            
            top_campaigns = []
            for campaign_data in campaign_reports:
                total_impressions = campaign_data['total_impressions'] or 0
                total_clicks = campaign_data['total_clicks'] or 0
                total_conversions = campaign_data['total_conversions'] or 0
                total_spend = campaign_data['total_spend'] or 0
                
                top_campaigns.append({
                    'campaign_id': campaign_data['campaign__id'],
                    'campaign_name': campaign_data['campaign__name'],
                    'impressions': total_impressions,
                    'clicks': total_clicks,
                    'conversions': total_conversions,
                    'spend': float(total_spend),
                    'ctr': float((total_clicks / total_impressions * 100) if total_impressions > 0 else 0),
                    'cpa': float((total_spend / total_conversions) if total_conversions > 0 else 0),
                })
            
            return top_campaigns
            
        except Exception as e:
            self.logger.error(f"Error getting top campaigns: {e}")
            return []
    
    def _get_current_balance(self, advertiser) -> float:
        """Get current wallet balance."""
        try:
            from ...models.billing import AdvertiserWallet
            wallet = AdvertiserWallet.objects.get(advertiser=advertiser)
            return float(wallet.balance)
        except AdvertiserWallet.DoesNotExist:
            return 0.00
    
    def _get_financial_daily_breakdown(self, advertiser, start_date, end_date) -> Dict[str, Any]:
        """Get daily financial breakdown."""
        try:
            from ...models.billing import AdvertiserTransaction, AdvertiserDeposit
            
            daily_data = {}
            current_date = start_date
            
            while current_date <= end_date:
                # Get daily spend
                daily_spend = AdvertiserTransaction.objects.filter(
                    wallet__advertiser=advertiser,
                    created_at__date=current_date,
                    transaction_type='spend'
                ).aggregate(total=models.Sum('amount'))['total'] or 0
                
                # Get daily deposits
                daily_deposits = AdvertiserDeposit.objects.filter(
                    advertiser=advertiser,
                    created_at__date=current_date,
                    status='completed'
                ).aggregate(total=models.Sum('net_amount'))['total'] or 0
                
                daily_data[current_date.isoformat()] = {
                    'spend': float(daily_spend),
                    'deposits': float(daily_deposits),
                    'net_flow': float(daily_deposits - daily_spend),
                }
                
                current_date += timezone.timedelta(days=1)
            
            return daily_data
            
        except Exception as e:
            self.logger.error(f"Error getting financial daily breakdown: {e}")
            return {}
    
    def _validate_report_config(self, config: Dict[str, Any]):
        """Validate report configuration."""
        required_fields = ['name', 'report_type', 'frequency', 'recipients']
        
        for field in required_fields:
            if field not in config:
                raise ValidationError(f"Missing required field: {field}")
        
        valid_frequencies = ['daily', 'weekly', 'monthly', 'quarterly']
        if config['frequency'] not in valid_frequencies:
            raise ValidationError(f"Invalid frequency: {config['frequency']}")
    
    def _calculate_next_run(self, frequency: str) -> str:
        """Calculate next run time for scheduled report."""
        now = timezone.now()
        
        if frequency == 'daily':
            next_run = now + timezone.timedelta(days=1)
            next_run = next_run.replace(hour=9, minute=0, second=0, microsecond=0)
        elif frequency == 'weekly':
            next_run = now + timezone.timedelta(weeks=1)
            next_run = next_run.replace(hour=9, minute=0, second=0, microsecond=0)
        elif frequency == 'monthly':
            next_run = now + timezone.timedelta(days=30)
            next_run = next_run.replace(hour=9, minute=0, second=0, microsecond=0)
        else:
            next_run = now + timezone.timedelta(days=1)
        
        return next_run.isoformat()
    
    def _send_report_generated_notification(self, advertiser, report: AdvertiserReport):
        """Send report generated notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='report_created',
            title=_('Report Generated'),
            message=_(
                'Your {report_type} report for {period} has been generated successfully.'
            ).format(
                report_type=report.get_report_type_display(),
                period=report.get_period_display()
            ),
            priority='medium',
            action_url=f'/advertiser/reports/{report.id}/',
            action_text=_('View Report')
        )
    
    def _send_report_scheduled_notification(self, advertiser, scheduled_report: Dict[str, Any]):
        """Send report scheduled notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='report_created',
            title=_('Report Scheduled'),
            message=_(
                'Your report "{name}" has been scheduled to run {frequency}.'
            ).format(
                name=scheduled_report['name'],
                frequency=scheduled_report['frequency']
            ),
            priority='low',
            action_url='/advertiser/reports/scheduled/',
            action_text=_('Manage Reports')
        )
