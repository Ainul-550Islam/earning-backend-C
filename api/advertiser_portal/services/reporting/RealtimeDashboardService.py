"""
Realtime Dashboard Service

Service for providing live metrics for advertiser dashboards,
including real-time performance data and analytics.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Count, Avg, Q

from ...models.campaign import AdCampaign
from ...models.offer import AdvertiserOffer
from ...models.billing import AdvertiserWallet
from ...models.reporting import CampaignReport

User = get_user_model()
logger = logging.getLogger(__name__)


class RealtimeDashboardService:
    """
    Service for providing real-time dashboard data.
    
    Handles live metrics, performance monitoring,
    and dashboard analytics.
    """
    
    def __init__(self):
        self.logger = logger
    
    def get_dashboard_overview(self, advertiser) -> Dict[str, Any]:
        """
        Get comprehensive dashboard overview for advertiser.
        
        Args:
            advertiser: Advertiser instance
            
        Returns:
            Dict[str, Any]: Dashboard overview data
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            now = timezone.now()
            today = now.date()
            
            # Get basic counts
            active_campaigns = AdCampaign.objects.filter(
                advertiser=advertiser,
                status='active'
            ).count()
            
            total_campaigns = AdCampaign.objects.filter(advertiser=advertiser).count()
            active_offers = AdvertiserOffer.objects.filter(
                advertiser=advertiser,
                status='active'
            ).count()
            
            total_offers = AdvertiserOffer.objects.filter(advertiser=advertiser).count()
            
            # Get today's performance
            today_performance = self._get_today_performance(advertiser, today)
            
            # Get wallet information
            wallet_info = self._get_wallet_info(advertiser)
            
            # Get recent activity
            recent_activity = self._get_recent_activity(advertiser)
            
            # Get performance trends
            performance_trends = self._get_performance_trends(advertiser, days=7)
            
            return {
                'overview': {
                    'active_campaigns': active_campaigns,
                    'total_campaigns': total_campaigns,
                    'active_offers': active_offers,
                    'total_offers': total_offers,
                    'campaign_health': self._calculate_campaign_health(advertiser),
                },
                'today_performance': today_performance,
                'wallet': wallet_info,
                'recent_activity': recent_activity,
                'performance_trends': performance_trends,
                'alerts': self._get_dashboard_alerts(advertiser),
                'generated_at': now.isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting dashboard overview: {e}")
            raise ValidationError(f"Failed to get dashboard overview: {str(e)}")
    
    def get_live_metrics(self, advertiser, time_range: str = '24h') -> Dict[str, Any]:
        """
        Get live performance metrics.
        
        Args:
            advertiser: Advertiser instance
            time_range: Time range ('1h', '24h', '7d', '30d')
            
        Returns:
            Dict[str, Any]: Live metrics data
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            now = timezone.now()
            
            # Calculate time range
            if time_range == '1h':
                start_time = now - timezone.timedelta(hours=1)
            elif time_range == '24h':
                start_time = now - timezone.timedelta(hours=24)
            elif time_range == '7d':
                start_time = now - timezone.timedelta(days=7)
            elif time_range == '30d':
                start_time = now - timezone.timedelta(days=30)
            else:
                start_time = now - timezone.timedelta(hours=24)
            
            # Get campaign performance in time range
            campaign_reports = CampaignReport.objects.filter(
                campaign__advertiser=advertiser,
                date__gte=start_time.date(),
                date__lte=now.date()
            ).select_related('campaign')
            
            # Aggregate metrics
            metrics = campaign_reports.aggregate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_spend=Sum('spend_amount'),
                avg_ctr=Avg('ctr'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_cpa=Avg('cpa'),
                avg_cpc=Avg('cpc'),
            )
            
            # Fill missing values
            for key, value in metrics.items():
                if value is None:
                    metrics[key] = 0
            
            # Calculate derived metrics
            total_impressions = metrics['total_impressions']
            total_clicks = metrics['total_clicks']
            total_conversions = metrics['total_conversions']
            total_spend = metrics['total_spend']
            
            calculated_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            calculated_cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
            calculated_cpa = (total_spend / total_conversions) if total_conversions > 0 else 0
            
            # Get hourly breakdown for 24h view
            hourly_data = {}
            if time_range == '24h':
                hourly_data = self._get_hourly_metrics(advertiser, start_time, now)
            
            return {
                'time_range': time_range,
                'period': {
                    'start_time': start_time.isoformat(),
                    'end_time': now.isoformat(),
                },
                'metrics': {
                    'impressions': total_impressions,
                    'clicks': total_clicks,
                    'conversions': total_conversions,
                    'spend': float(total_spend),
                    'ctr': float(calculated_ctr),
                    'cpc': float(calculated_cpc),
                    'cpa': float(calculated_cpa),
                    'conversion_rate': float((total_conversions / total_clicks * 100) if total_clicks > 0 else 0),
                },
                'hourly_data': hourly_data,
                'top_campaigns': self._get_top_campaigns_live(advertiser, start_time, now),
                'real_time_indicators': self._get_real_time_indicators(advertiser),
                'generated_at': now.isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting live metrics: {e}")
            raise ValidationError(f"Failed to get live metrics: {str(e)}")
    
    def get_campaign_performance_chart(self, campaign, days: int = 30) -> Dict[str, Any]:
        """
        Get campaign performance chart data.
        
        Args:
            campaign: Campaign instance
            days: Number of days to include
            
        Returns:
            Dict[str, Any]: Chart data
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            end_date = timezone.now().date()
            start_date = end_date - timezone.timedelta(days=days-1)
            
            # Get daily performance data
            daily_reports = CampaignReport.objects.filter(
                campaign=campaign,
                date__gte=start_date,
                date__lte=end_date
            ).order_by('date')
            
            # Prepare chart data
            chart_data = {
                'labels': [],
                'datasets': {
                    'impressions': [],
                    'clicks': [],
                    'conversions': [],
                    'spend': [],
                    'ctr': [],
                    'cpa': [],
                }
            }
            
            for report in daily_reports:
                chart_data['labels'].append(report.date.strftime('%m/%d'))
                chart_data['datasets']['impressions'].append(report.impressions)
                chart_data['datasets']['clicks'].append(report.clicks)
                chart_data['datasets']['conversions'].append(report.conversions)
                chart_data['datasets']['spend'].append(float(report.spend_amount))
                chart_data['datasets']['ctr'].append(float(report.ctr))
                chart_data['datasets']['cpa'].append(float(report.cpa))
            
            # Fill missing dates with zeros
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime('%m/%d')
                if date_str not in chart_data['labels']:
                    chart_data['labels'].append(date_str)
                    for dataset in chart_data['datasets'].values():
                        dataset.append(0)
                current_date += timezone.timedelta(days=1)
            
            return {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'chart_data': chart_data,
                'summary': self._get_campaign_summary(campaign, start_date, end_date),
                'generated_at': timezone.now().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting campaign performance chart: {e}")
            raise ValidationError(f"Failed to get campaign performance chart: {str(e)}")
    
    def get_real_time_alerts(self, advertiser) -> List[Dict[str, Any]]:
        """
        Get real-time alerts for advertiser.
        
        Args:
            advertiser: Advertiser instance
            
        Returns:
            List[Dict[str, Any]]: Real-time alerts
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            alerts = []
            
            # Check wallet balance alerts
            wallet_alerts = self._check_wallet_alerts(advertiser)
            alerts.extend(wallet_alerts)
            
            # Check campaign performance alerts
            campaign_alerts = self._check_campaign_alerts(advertiser)
            alerts.extend(campaign_alerts)
            
            # Check budget alerts
            budget_alerts = self._check_budget_alerts(advertiser)
            alerts.extend(budget_alerts)
            
            # Sort by severity and timestamp
            alerts.sort(key=lambda x: (x['severity'] != 'high', x['timestamp']), reverse=True)
            
            return alerts[:20]  # Limit to 20 most recent alerts
            
        except Exception as e:
            self.logger.error(f"Error getting real-time alerts: {e}")
            raise ValidationError(f"Failed to get real-time alerts: {str(e)}")
    
    def get_performance_comparison(self, advertiser, comparison_period: str = 'previous_period') -> Dict[str, Any]:
        """
        Get performance comparison data.
        
        Args:
            advertiser: Advertiser instance
            comparison_period: Comparison period type
            
        Returns:
            Dict[str, Any]: Performance comparison data
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            now = timezone.now()
            
            # Calculate current and comparison periods
            if comparison_period == 'previous_period':
                current_end = now.date()
                current_start = current_end - timezone.timedelta(days=6)  # Last 7 days
                comparison_end = current_start - timezone.timedelta(days=1)
                comparison_start = comparison_end - timezone.timedelta(days=6)
            elif comparison_period == 'previous_month':
                current_end = now.date()
                current_start = current_end - timezone.timedelta(days=29)
                comparison_end = current_start - timezone.timedelta(days=1)
                comparison_start = comparison_end - timezone.timedelta(days=29)
            else:
                current_end = now.date()
                current_start = current_end - timezone.timedelta(days=6)
                comparison_end = current_start - timezone.timedelta(days=1)
                comparison_start = comparison_end - timezone.timedelta(days=6)
            
            # Get current period performance
            current_performance = self._get_period_performance(advertiser, current_start, current_end)
            
            # Get comparison period performance
            comparison_performance = self._get_period_performance(advertiser, comparison_start, comparison_end)
            
            # Calculate changes
            changes = self._calculate_performance_changes(current_performance, comparison_performance)
            
            return {
                'current_period': {
                    'start_date': current_start.isoformat(),
                    'end_date': current_end.isoformat(),
                    'performance': current_performance,
                },
                'comparison_period': {
                    'start_date': comparison_start.isoformat(),
                    'end_date': comparison_end.isoformat(),
                    'performance': comparison_performance,
                },
                'changes': changes,
                'comparison_type': comparison_period,
                'generated_at': now.isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting performance comparison: {e}")
            raise ValidationError(f"Failed to get performance comparison: {str(e)}")
    
    def _get_today_performance(self, advertiser, today) -> Dict[str, Any]:
        """Get today's performance data."""
        try:
            today_reports = CampaignReport.objects.filter(
                campaign__advertiser=advertiser,
                date=today
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_spend=Sum('spend_amount')
            )
            
            for key, value in today_reports.items():
                if value is None:
                    today_reports[key] = 0
            
            total_clicks = today_reports['total_clicks']
            total_conversions = today_reports['total_conversions']
            total_spend = today_reports['total_spend']
            
            return {
                'impressions': today_reports['total_impressions'],
                'clicks': total_clicks,
                'conversions': total_conversions,
                'spend': float(total_spend),
                'ctr': float((total_clicks / today_reports['total_impressions'] * 100) if today_reports['total_impressions'] > 0 else 0),
                'cpa': float((total_spend / total_conversions) if total_conversions > 0 else 0),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting today's performance: {e}")
            return {
                'impressions': 0,
                'clicks': 0,
                'conversions': 0,
                'spend': 0.0,
                'ctr': 0.0,
                'cpa': 0.0,
            }
    
    def _get_wallet_info(self, advertiser) -> Dict[str, Any]:
        """Get wallet information."""
        try:
            wallet = AdvertiserWallet.objects.get(advertiser=advertiser)
            
            return {
                'balance': float(wallet.balance),
                'credit_limit': float(wallet.credit_limit),
                'available_balance': float(wallet.available_balance),
                'auto_refill_enabled': wallet.auto_refill_enabled,
                'auto_refill_threshold': float(wallet.auto_refill_threshold),
            }
            
        except AdvertiserWallet.DoesNotExist:
            return {
                'balance': 0.0,
                'credit_limit': 0.0,
                'available_balance': 0.0,
                'auto_refill_enabled': False,
                'auto_refill_threshold': 0.0,
            }
    
    def _get_recent_activity(self, advertiser, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent activity for advertiser."""
        try:
            activities = []
            
            # Recent campaigns
            recent_campaigns = AdCampaign.objects.filter(
                advertiser=advertiser
            ).order_by('-created_at')[:5]
            
            for campaign in recent_campaigns:
                activities.append({
                    'type': 'campaign_created',
                    'title': f'Campaign "{campaign.name}" created',
                    'timestamp': campaign.created_at.isoformat(),
                    'status': campaign.status,
                })
            
            # Recent deposits
            from ...models.billing import AdvertiserDeposit
            recent_deposits = AdvertiserDeposit.objects.filter(
                advertiser=advertiser,
                status='completed'
            ).order_by('-created_at')[:5]
            
            for deposit in recent_deposits:
                activities.append({
                    'type': 'deposit',
                    'title': f'Deposit of ${float(deposit.net_amount):.2f} received',
                    'timestamp': deposit.created_at.isoformat(),
                    'amount': float(deposit.net_amount),
                })
            
            # Sort by timestamp
            activities.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return activities[:limit]
            
        except Exception as e:
            self.logger.error(f"Error getting recent activity: {e}")
            return []
    
    def _get_performance_trends(self, advertiser, days: int) -> Dict[str, Any]:
        """Get performance trends."""
        try:
            end_date = timezone.now().date()
            start_date = end_date - timezone.timedelta(days=days-1)
            
            # Get daily performance
            daily_reports = CampaignReport.objects.filter(
                campaign__advertiser=advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).values('date').annotate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_spend=Sum('spend_amount')
            ).order_by('date')
            
            # Calculate trends
            if len(daily_reports) >= 2:
                recent_avg = daily_reports[len(daily_reports)//2:].aggregate(
                    avg_spend=Avg('total_spend'),
                    avg_conversions=Avg('total_conversions')
                )
                
                older_avg = daily_reports[:len(daily_reports)//2].aggregate(
                    avg_spend=Avg('total_spend'),
                    avg_conversions=Avg('total_conversions')
                )
                
                spend_trend = 'up' if recent_avg['avg_spend'] > older_avg['avg_spend'] else 'down'
                conversion_trend = 'up' if recent_avg['avg_conversions'] > older_avg['avg_conversions'] else 'down'
            else:
                spend_trend = 'stable'
                conversion_trend = 'stable'
            
            return {
                'spend_trend': spend_trend,
                'conversion_trend': conversion_trend,
                'data_points': len(daily_reports),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting performance trends: {e}")
            return {
                'spend_trend': 'stable',
                'conversion_trend': 'stable',
                'data_points': 0,
            }
    
    def _calculate_campaign_health(self, advertiser) -> Dict[str, Any]:
        """Calculate overall campaign health."""
        try:
            campaigns = AdCampaign.objects.filter(advertiser=advertiser)
            
            total_campaigns = campaigns.count()
            active_campaigns = campaigns.filter(status='active').count()
            paused_campaigns = campaigns.filter(status='paused').count()
            
            if total_campaigns == 0:
                return {
                    'score': 0,
                    'status': 'no_campaigns',
                    'active_percentage': 0,
                }
            
            active_percentage = (active_campaigns / total_campaigns) * 100
            
            if active_percentage >= 80:
                status = 'excellent'
                score = 90
            elif active_percentage >= 60:
                status = 'good'
                score = 70
            elif active_percentage >= 40:
                status = 'fair'
                score = 50
            else:
                status = 'poor'
                score = 30
            
            return {
                'score': score,
                'status': status,
                'active_percentage': active_percentage,
                'total_campaigns': total_campaigns,
                'active_campaigns': active_campaigns,
                'paused_campaigns': paused_campaigns,
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating campaign health: {e}")
            return {
                'score': 0,
                'status': 'error',
                'active_percentage': 0,
            }
    
    def _get_dashboard_alerts(self, advertiser) -> List[Dict[str, Any]]:
        """Get dashboard alerts."""
        return self.get_real_time_alerts(advertiser)[:5]  # Top 5 alerts
    
    def _get_hourly_metrics(self, advertiser, start_time, end_time) -> Dict[str, Any]:
        """Get hourly metrics breakdown."""
        hourly_data = {}
        
        current_hour = start_time.replace(minute=0, second=0, microsecond=0)
        
        while current_hour < end_time:
            # This would implement hourly aggregation
            # For now, return empty data
            hourly_data[current_hour.strftime('%H:00')] = {
                'impressions': 0,
                'clicks': 0,
                'conversions': 0,
                'spend': 0.0,
            }
            
            current_hour += timezone.timedelta(hours=1)
        
        return hourly_data
    
    def _get_top_campaigns_live(self, advertiser, start_time, end_time, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top performing campaigns in time range."""
        try:
            campaign_reports = CampaignReport.objects.filter(
                campaign__advertiser=advertiser,
                date__gte=start_time.date(),
                date__lte=end_time.date()
            ).values('campaign__id', 'campaign__name').annotate(
                total_spend=Sum('spend_amount'),
                total_conversions=Sum('conversions')
            ).order_by('-total_spend')[:limit]
            
            top_campaigns = []
            for campaign_data in campaign_reports:
                total_spend = campaign_data['total_spend'] or 0
                total_conversions = campaign_data['total_conversions'] or 0
                
                top_campaigns.append({
                    'campaign_id': campaign_data['campaign__id'],
                    'campaign_name': campaign_data['campaign__name'],
                    'spend': float(total_spend),
                    'conversions': total_conversions,
                    'cpa': float((total_spend / total_conversions) if total_conversions > 0 else 0),
                })
            
            return top_campaigns
            
        except Exception as e:
            self.logger.error(f"Error getting top campaigns live: {e}")
            return []
    
    def _get_real_time_indicators(self, advertiser) -> Dict[str, Any]:
        """Get real-time performance indicators."""
        try:
            # This would implement real-time indicators
            return {
                'current_cpm': 2.50,
                'current_ctr': 1.25,
                'active_visitors': 145,
                'conversion_rate_today': 2.8,
                'avg_response_time': 0.85,
                'server_uptime': 99.9,
            }
            
        except Exception as e:
            self.logger.error(f"Error getting real-time indicators: {e}")
            return {}
    
    def _get_campaign_summary(self, campaign, start_date, end_date) -> Dict[str, Any]:
        """Get campaign summary for period."""
        try:
            reports = CampaignReport.objects.filter(
                campaign=campaign,
                date__gte=start_date,
                date__lte=end_date
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_spend=Sum('spend_amount'),
                avg_ctr=Avg('ctr'),
                avg_cpa=Avg('cpa')
            )
            
            for key, value in reports.items():
                if value is None:
                    reports[key] = 0
            
            return {
                'total_impressions': reports['total_impressions'],
                'total_clicks': reports['total_clicks'],
                'total_conversions': reports['total_conversions'],
                'total_spend': float(reports['total_spend']),
                'avg_ctr': float(reports['avg_ctr']),
                'avg_cpa': float(reports['avg_cpa']),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting campaign summary: {e}")
            return {}
    
    def _check_wallet_alerts(self, advertiser) -> List[Dict[str, Any]]:
        """Check wallet-related alerts."""
        alerts = []
        
        try:
            wallet = AdvertiserWallet.objects.get(advertiser=advertiser)
            
            if wallet.balance <= wallet.auto_refill_threshold and wallet.auto_refill_enabled:
                alerts.append({
                    'type': 'wallet_low',
                    'severity': 'high',
                    'title': 'Wallet Balance Low',
                    'message': f'Balance (${wallet.balance:.2f}) is below auto-refill threshold (${wallet.auto_refill_threshold:.2f})',
                    'timestamp': timezone.now().isoformat(),
                })
            elif wallet.balance <= 50:
                alerts.append({
                    'type': 'wallet_critical',
                    'severity': 'critical',
                    'title': 'Critical Wallet Balance',
                    'message': f'Wallet balance is critically low (${wallet.balance:.2f})',
                    'timestamp': timezone.now().isoformat(),
                })
                
        except AdvertiserWallet.DoesNotExist:
            pass
        
        return alerts
    
    def _check_campaign_alerts(self, advertiser) -> List[Dict[str, Any]]:
        """Check campaign-related alerts."""
        alerts = []
        
        # Check for campaigns with no recent activity
        inactive_campaigns = AdCampaign.objects.filter(
            advertiser=advertiser,
            status='active',
            created_at__lt=timezone.now() - timezone.timedelta(days=7)
        ).count()
        
        if inactive_campaigns > 0:
            alerts.append({
                'type': 'inactive_campaigns',
                'severity': 'medium',
                'title': 'Inactive Campaigns',
                'message': f'{inactive_campaigns} campaigns have been inactive for over 7 days',
                'timestamp': timezone.now().isoformat(),
            })
        
        return alerts
    
    def _check_budget_alerts(self, advertiser) -> List[Dict[str, Any]]:
        """Check budget-related alerts."""
        alerts = []
        
        # This would implement budget checking logic
        # For now, return empty list
        return alerts
    
    def _get_period_performance(self, advertiser, start_date, end_date) -> Dict[str, Any]:
        """Get performance for a specific period."""
        try:
            reports = CampaignReport.objects.filter(
                campaign__advertiser=advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_spend=Sum('spend_amount')
            )
            
            for key, value in reports.items():
                if value is None:
                    reports[key] = 0
            
            return {
                'impressions': reports['total_impressions'],
                'clicks': reports['total_clicks'],
                'conversions': reports['total_conversions'],
                'spend': float(reports['total_spend']),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting period performance: {e}")
            return {
                'impressions': 0,
                'clicks': 0,
                'conversions': 0,
                'spend': 0.0,
            }
    
    def _calculate_performance_changes(self, current: Dict[str, Any], comparison: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate performance changes between periods."""
        changes = {}
        
        for metric in ['impressions', 'clicks', 'conversions', 'spend']:
            current_value = current.get(metric, 0)
            comparison_value = comparison.get(metric, 0)
            
            if comparison_value == 0:
                change_percentage = 100 if current_value > 0 else 0
            else:
                change_percentage = ((current_value - comparison_value) / comparison_value) * 100
            
            changes[metric] = {
                'current': current_value,
                'comparison': comparison_value,
                'change': current_value - comparison_value,
                'change_percentage': change_percentage,
                'trend': 'up' if change_percentage > 0 else 'down' if change_percentage < 0 else 'stable',
            }
        
        return changes
