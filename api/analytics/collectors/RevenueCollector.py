from django.db.models import Count, Sum, Avg, F, Q, Max, Min
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
import logging
from ..models import AnalyticsEvent, RevenueAnalytics
from .DataCollector import DataCollector

logger = logging.getLogger(__name__)

class RevenueCollector(DataCollector):
    """
    Collector for revenue analytics data
    """
    
    def __init__(self):
        super().__init__(cache_timeout=300)  # 5 minutes cache
    
    def calculate_daily_revenue(self, date: datetime = None) -> Dict:
        """
        Calculate daily revenue
        
        Args:
            date: Specific date or today
        
        Returns:
            Daily revenue metrics
        """
        if not date:
            date = timezone.now().date()
        
        tomorrow = date + timedelta(days=1)
        
        # Get revenue events for the day
        revenue_events = AnalyticsEvent.objects.filter(
            event_time__gte=date,
            event_time__lt=tomorrow,
            value__gt=0
        )
        
        # Calculate by source
        revenue_by_source = {}
        total_revenue = Decimal('0')
        
        for event in revenue_events:
            source = self._get_revenue_source(event.event_type)
            amount = event.value or Decimal('0')
            
            if source in revenue_by_source:
                revenue_by_source[source] += amount
            else:
                revenue_by_source[source] = amount
            
            total_revenue += amount
        
        # Calculate costs (simplified - would come from actual cost data)
        cost_total = total_revenue * Decimal('0.3')  # Assuming 30% cost
        
        # Get user metrics
        active_users = AnalyticsEvent.objects.filter(
            event_time__gte=date,
            event_time__lt=tomorrow,
            event_type='user_login'
        ).values('user_id').distinct().count()
        
        paying_users = revenue_events.values('user_id').distinct().count()
        
        # Calculate ARPU/ARPPU
        arpu = total_revenue / active_users if active_users > 0 else Decimal('0')
        arppu = total_revenue / paying_users if paying_users > 0 else Decimal('0')
        
        # Withdrawals
        withdrawals = AnalyticsEvent.objects.filter(
            event_time__gte=date,
            event_time__lt=tomorrow,
            event_type='withdrawal_processed',
            value__lt=0  # Negative value for withdrawals
        ).aggregate(
            total=Sum('value'),
            count=Count('id')
        )
        
        return {
            'date': date,
            'revenue_total': total_revenue,
            'revenue_by_source': revenue_by_source,
            'cost_total': cost_total,
            'gross_profit': total_revenue - cost_total,
            'active_users': active_users,
            'paying_users': paying_users,
            'conversion_rate': (paying_users / active_users * 100) if active_users > 0 else 0,
            'arpu': arpu,
            'arppu': arppu,
            'total_withdrawals': abs(withdrawals['total'] or Decimal('0')),
            'withdrawal_requests': withdrawals['count'] or 0
        }
    
    def calculate_weekly_revenue(self, week_start: datetime = None) -> Dict:
        """
        Calculate weekly revenue
        
        Args:
            week_start: Start of week or current week
        
        Returns:
            Weekly revenue metrics
        """
        if not week_start:
            # Get start of current week (Monday)
            today = timezone.now().date()
            week_start = today - timedelta(days=today.weekday())
        
        week_end = week_start + timedelta(days=7)
        
        # Calculate daily revenue for each day of the week
        daily_revenues = []
        current_day = week_start
        
        while current_day < week_end:
            daily_revenue = self.calculate_daily_revenue(current_day)
            daily_revenues.append(daily_revenue)
            current_day += timedelta(days=1)
        
        # Aggregate weekly metrics
        weekly_total = sum(d['revenue_total'] for d in daily_revenues)
        weekly_cost = sum(d['cost_total'] for d in daily_revenues)
        weekly_users = sum(d['active_users'] for d in daily_revenues)
        weekly_paying = sum(d['paying_users'] for d in daily_revenues)
        
        return {
            'week_start': week_start,
            'week_end': week_end - timedelta(days=1),
            'revenue_total': weekly_total,
            'cost_total': weekly_cost,
            'gross_profit': weekly_total - weekly_cost,
            'profit_margin': ((weekly_total - weekly_cost) / weekly_total * 100) if weekly_total > 0 else 0,
            'active_users': weekly_users,
            'paying_users': weekly_paying,
            'conversion_rate': (weekly_paying / weekly_users * 100) if weekly_users > 0 else 0,
            'arpu': weekly_total / weekly_users if weekly_users > 0 else Decimal('0'),
            'arppu': weekly_total / weekly_paying if weekly_paying > 0 else Decimal('0'),
            'daily_breakdown': daily_revenues
        }
    
    def calculate_monthly_revenue(self, month: datetime = None) -> Dict:
        """
        Calculate monthly revenue
        
        Args:
            month: Month to calculate or current month
        
        Returns:
            Monthly revenue metrics
        """
        if not month:
            month = timezone.now().replace(day=1)
        
        # Calculate start and end of month
        if month.month == 12:
            next_month = month.replace(year=month.year + 1, month=1)
        else:
            next_month = month.replace(month=month.month + 1)
        
        month_end = next_month - timedelta(days=1)
        
        # Get all revenue events for the month
        revenue_events = AnalyticsEvent.objects.filter(
            event_time__gte=month,
            event_time__lt=next_month,
            value__gt=0
        )
        
        # Calculate revenue by source
        revenue_by_source = {}
        total_revenue = Decimal('0')
        
        for event in revenue_events:
            source = self._get_revenue_source(event.event_type)
            amount = event.value or Decimal('0')
            
            if source in revenue_by_source:
                revenue_by_source[source] += amount
            else:
                revenue_by_source[source] = amount
            
            total_revenue += amount
        
        # Calculate costs (more detailed for monthly)
        cost_breakdown = self._calculate_monthly_costs(month, next_month)
        cost_total = sum(cost_breakdown.values())
        
        # User metrics
        active_users = AnalyticsEvent.objects.filter(
            event_time__gte=month,
            event_time__lt=next_month,
            event_type='user_login'
        ).values('user_id').distinct().count()
        
        paying_users = revenue_events.values('user_id').distinct().count()
        
        # Withdrawals
        withdrawals = AnalyticsEvent.objects.filter(
            event_time__gte=month,
            event_time__lt=next_month,
            event_type='withdrawal_processed',
            value__lt=0
        ).aggregate(
            total=Sum('value'),
            count=Count('id')
        )
        
        # Platform fees and taxes
        platform_fee = total_revenue * Decimal('0.1')  # 10% platform fee
        tax_deducted = total_revenue * Decimal('0.15')  # 15% tax
        
        return {
            'month': month,
            'revenue_total': total_revenue,
            'revenue_by_source': revenue_by_source,
            'cost_total': cost_total,
            'cost_breakdown': cost_breakdown,
            'gross_profit': total_revenue - cost_total,
            'net_profit': total_revenue - cost_total - platform_fee - tax_deducted,
            'profit_margin': ((total_revenue - cost_total) / total_revenue * 100) if total_revenue > 0 else 0,
            'active_users': active_users,
            'paying_users': paying_users,
            'conversion_rate': (paying_users / active_users * 100) if active_users > 0 else 0,
            'arpu': total_revenue / active_users if active_users > 0 else Decimal('0'),
            'arppu': total_revenue / paying_users if paying_users > 0 else Decimal('0'),
            'total_withdrawals': abs(withdrawals['total'] or Decimal('0')),
            'withdrawal_requests': withdrawals['count'] or 0,
            'platform_fee_earned': platform_fee,
            'tax_deducted': tax_deducted
        }
    
    def calculate_revenue_trends(self, days: int = 30) -> Dict:
        """
        Calculate revenue trends
        
        Args:
            days: Number of days to analyze
        
        Returns:
            Revenue trends and forecasts
        """
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get daily revenue for the period
        daily_revenues = []
        current_date = start_date
        
        while current_date <= end_date:
            daily_rev = self.calculate_daily_revenue(current_date.date())
            daily_revenues.append({
                'date': current_date.date(),
                'revenue': daily_rev['revenue_total']
            })
            current_date += timedelta(days=1)
        
        # Calculate trends
        if len(daily_revenues) >= 2:
            # Daily growth rate
            daily_growth = []
            for i in range(1, len(daily_revenues)):
                prev = daily_revenues[i-1]['revenue']
                curr = daily_revenues[i]['revenue']
                
                if prev > 0:
                    growth = ((curr - prev) / prev) * 100
                elif curr > 0:
                    growth = 100.0
                else:
                    growth = 0.0
                
                daily_growth.append(growth)
            
            avg_daily_growth = sum(daily_growth) / len(daily_growth) if daily_growth else 0
            
            # Weekly patterns
            weekday_revenue = {i: [] for i in range(7)}  # 0=Monday, 6=Sunday
            
            for rev in daily_revenues:
                weekday = rev['date'].weekday()
                weekday_revenue[weekday].append(rev['revenue'])
            
            avg_weekday_revenue = {
                day: sum(revs) / len(revs) if revs else 0
                for day, revs in weekday_revenue.items()
            }
            
            # Best performing day
            best_day = max(avg_weekday_revenue.items(), key=lambda x: x[1])[0]
            best_day_name = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][best_day]
            
            # Forecast next 7 days
            forecast = self._forecast_revenue(daily_revenues, periods=7)
            
        else:
            avg_daily_growth = 0
            avg_weekday_revenue = {}
            best_day_name = 'Unknown'
            forecast = []
        
        return {
            'period_days': days,
            'total_revenue': sum(r['revenue'] for r in daily_revenues),
            'avg_daily_revenue': sum(r['revenue'] for r in daily_revenues) / len(daily_revenues) if daily_revenues else 0,
            'avg_daily_growth': avg_daily_growth,
            'best_performing_day': best_day_name,
            'weekday_patterns': avg_weekday_revenue,
            'forecast_next_7_days': forecast,
            'daily_data': daily_revenues
        }
    
    def get_revenue_by_source_breakdown(
        self,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict:
        """
        Get revenue breakdown by source
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            Revenue breakdown by source
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        revenue_events = AnalyticsEvent.objects.filter(
            event_time__gte=start_date,
            event_time__lte=end_date,
            value__gt=0
        )
        
        # Group by source
        source_revenue = {}
        
        for event in revenue_events:
            source = self._get_revenue_source(event.event_type)
            amount = event.value or Decimal('0')
            
            if source in source_revenue:
                source_revenue[source] += amount
            else:
                source_revenue[source] = amount
        
        # Calculate percentages
        total_revenue = sum(source_revenue.values())
        
        if total_revenue > 0:
            source_percentages = {
                source: (amount / total_revenue * 100)
                for source, amount in source_revenue.items()
            }
        else:
            source_percentages = {}
        
        return {
            'total_revenue': total_revenue,
            'by_source': source_revenue,
            'percentages': source_percentages,
            'top_source': max(source_revenue.items(), key=lambda x: x[1])[0] if source_revenue else None
        }
    
    def get_revenue_today(self) -> Decimal:
        """Get revenue for today"""
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        revenue = AnalyticsEvent.objects.filter(
            event_time__gte=today,
            event_time__lt=tomorrow,
            value__gt=0
        ).aggregate(total=Sum('value'))['total'] or Decimal('0')
        
        return revenue
    
    def get_revenue_this_month(self) -> Decimal:
        """Get revenue for this month"""
        today = timezone.now()
        month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        
        revenue = AnalyticsEvent.objects.filter(
            event_time__gte=month_start,
            event_time__lt=next_month,
            value__gt=0
        ).aggregate(total=Sum('value'))['total'] or Decimal('0')
        
        return revenue
    
    def get_withdrawals_processed_today(self) -> int:
        """Get number of withdrawals processed today"""
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        return AnalyticsEvent.objects.filter(
            event_type='withdrawal_processed',
            event_time__gte=today,
            event_time__lt=tomorrow
        ).count()
    
    def get_revenue_trend(self, days: int = 30) -> float:
        """Get revenue trend percentage"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        previous_start_date = start_date - timedelta(days=days)
        
        # Current period revenue
        current_revenue = AnalyticsEvent.objects.filter(
            value__gt=0,
            event_time__gte=start_date,
            event_time__lt=end_date
        ).aggregate(total=Sum('value'))['total'] or Decimal('0')
        
        # Previous period revenue
        previous_revenue = AnalyticsEvent.objects.filter(
            value__gt=0,
            event_time__gte=previous_start_date,
            event_time__lt=start_date
        ).aggregate(total=Sum('value'))['total'] or Decimal('0')
        
        if previous_revenue > 0:
            return float(((current_revenue - previous_revenue) / previous_revenue) * 100)
        elif current_revenue > 0:
            return 100.0
        else:
            return 0.0
    
    # Helper methods
    def _get_revenue_source(self, event_type: str) -> str:
        """Map event type to revenue source"""
        source_map = {
            'task_completed': 'task_completion',
            'offer_completed': 'offer_completion',
            'referral_joined': 'referral_commission',
            'subscription_payment': 'subscription',
            'ad_impression': 'ads',
            'sponsorship': 'sponsorship'
        }
        
        return source_map.get(event_type, 'other')
    
    def _calculate_monthly_costs(
        self,
        month_start: datetime,
        month_end: datetime
    ) -> Dict[str, Decimal]:
        """
        Calculate monthly costs breakdown
        
        Args:
            month_start: Start of month
            month_end: End of month
        
        Returns:
            Cost breakdown by category
        """
        # This is a simplified version
        # In production, you would integrate with accounting system
        
        # Get total payout to users
        user_payouts = AnalyticsEvent.objects.filter(
            event_type='withdrawal_processed',
            event_time__gte=month_start,
            event_time__lt=month_end,
            value__lt=0
        ).aggregate(total=Sum('value'))['total'] or Decimal('0')
        
        user_payouts = abs(user_payouts)
        
        # Estimate other costs (these would come from actual cost data)
        costs = {
            'user_payouts': user_payouts,
            'server_hosting': Decimal('5000'),  # Monthly server costs
            'employee_salaries': Decimal('20000'),  # Monthly salaries
            'marketing': Decimal('10000'),  # Monthly marketing spend
            'payment_processing': Decimal('2000'),  # Payment gateway fees
            'third_party_services': Decimal('3000'),  # Other services
            'office_rent': Decimal('5000'),  # Office costs
            'miscellaneous': Decimal('2000')  # Other expenses
        }
        
        return costs
    
    def _forecast_revenue(
        self,
        historical_data: List[Dict],
        periods: int = 7
    ) -> List[Dict]:
        """
        Forecast future revenue using simple moving average
        
        Args:
            historical_data: Historical revenue data
            periods: Number of periods to forecast
        
        Returns:
            Forecasted revenue
        """
        if not historical_data or len(historical_data) < 7:
            return []
        
        # Use last 7 days average for forecast
        recent_data = historical_data[-7:]
        avg_revenue = sum(d['revenue'] for d in recent_data) / 7
        
        # Generate forecast
        forecast = []
        last_date = historical_data[-1]['date']
        
        for i in range(1, periods + 1):
            forecast_date = last_date + timedelta(days=i)
            forecast.append({
                'date': forecast_date,
                'revenue': avg_revenue,
                'confidence': max(0, 100 - (i * 10))  # Decreasing confidence
            })
        
        return forecast