from django.db.models import Count, Sum, Avg, F, Q, Max, Min
from django.db.models.functions import TruncDate, TruncHour, TruncMonth
from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
import logging
from ..models import AnalyticsEvent, OfferPerformanceAnalytics
from .DataCollector import DataCollector

logger = logging.getLogger(__name__)

class OfferPerformanceCollector(DataCollector):
    """
    Collector for offer performance analytics
    """
    
    def __init__(self):
        super().__init__(cache_timeout=600)  # 10 minutes cache
    
    def collect_offer_performance(
        self,
        offer_id: int = None,
        start_date: datetime = None,
        end_date: datetime = None,
        period: str = 'daily'
    ) -> List[Dict]:
        """
        Collect offer performance metrics
        
        Args:
            offer_id: Specific offer ID or all offers
            start_date: Start date
            end_date: End date
            period: Aggregation period
        
        Returns:
            Offer performance data
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        # Build filters for offer events
        filters = {
            'event_time__gte': start_date,
            'event_time__lte': end_date,
            'event_type__in': ['offer_viewed', 'offer_completed']
        }
        
        if offer_id:
            filters['metadata__offer_id'] = offer_id
        
        events = AnalyticsEvent.objects.filter(**filters)
        
        # Group by period
        trunc_map = {
            'hourly': TruncHour('event_time'),
            'daily': TruncDate('event_time'),
            'weekly': TruncDate('event_time'),  # Would need custom week
            'monthly': TruncMonth('event_time')
        }
        
        trunc_func = trunc_map.get(period, TruncDate('event_time'))
        
        # Aggregate by period and offer
        performance_data = events.annotate(
            period=trunc_func,
            offer_id=F('metadata__offer_id'),
            offer_name=F('metadata__offer_name')
        ).values(
            'period', 'offer_id', 'offer_name'
        ).annotate(
            # View metrics
            impressions=Count('id', filter=Q(event_type='offer_viewed')),
            unique_views=Count('user_id', distinct=True, filter=Q(event_type='offer_viewed')),
            clicks=Count('id', filter=Q(
                event_type='offer_viewed',
                metadata__clicked=True
            )),
            
            # Completion metrics
            completions=Count('id', filter=Q(event_type='offer_completed')),
            unique_completions=Count('user_id', distinct=True, filter=Q(event_type='offer_completed')),
            
            # Revenue metrics
            revenue_generated=Sum('value', filter=Q(event_type='offer_completed')),
            
            # Device breakdown
            mobile_views=Count('id', filter=Q(
                event_type='offer_viewed',
                device_type='mobile'
            )),
            desktop_views=Count('id', filter=Q(
                event_type='offer_viewed',
                device_type='desktop'
            )),
            tablet_views=Count('id', filter=Q(
                event_type='offer_viewed',
                device_type='tablet'
            ))
        ).order_by('period', 'offer_id')
        
        # Calculate derived metrics
        for data in performance_data:
            # Click-through rate
            if data['impressions'] > 0:
                data['ctr'] = (data['clicks'] / data['impressions']) * 100
            else:
                data['ctr'] = 0.0
            
            # Conversion rate
            if data['unique_views'] > 0:
                data['conversion_rate'] = (data['unique_completions'] / data['unique_views']) * 100
            else:
                data['conversion_rate'] = 0.0
            
            # Cost per completion (simplified)
            if data['completions'] > 0:
                # Assume average cost per completion
                data['cost_per_completion'] = Decimal('0.50')
                data['roi'] = ((data['revenue_generated'] or Decimal('0')) - 
                             (data['cost_per_completion'] * data['completions'])) / \
                            (data['cost_per_completion'] * data['completions']) * 100
            else:
                data['cost_per_completion'] = Decimal('0')
                data['roi'] = 0.0
        
        return list(performance_data)
    
    def collect_top_performing_offers(
        self,
        metric: str = 'revenue',
        limit: int = 10,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> List[Dict]:
        """
        Collect top performing offers by metric
        
        Args:
            metric: Ranking metric
            limit: Number of offers to return
            start_date: Start date
            end_date: End date
        
        Returns:
            Top performing offers
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        # Get offer completion events
        completion_events = AnalyticsEvent.objects.filter(
            event_type='offer_completed',
            event_time__gte=start_date,
            event_time__lte=end_date
        )
        
        # Aggregate by offer
        offer_performance = completion_events.values(
            'metadata__offer_id',
            'metadata__offer_name',
            'metadata__offer_category'
        ).annotate(
            completions=Count('id'),
            unique_users=Count('user_id', distinct=True),
            total_revenue=Sum('value'),
            avg_completion_time=Avg('duration'),
            avg_rating=Avg('metadata__rating')
        ).order_by(f'-{self._get_metric_field(metric)}')[:limit]
        
        # Format results
        top_offers = []
        for offer in offer_performance:
            # Calculate additional metrics
            view_events = AnalyticsEvent.objects.filter(
                event_type='offer_viewed',
                metadata__offer_id=offer['metadata__offer_id'],
                event_time__gte=start_date,
                event_time__lte=end_date
            ).aggregate(
                views=Count('id'),
                unique_views=Count('user_id', distinct=True)
            )
            
            if view_events['views'] > 0:
                conversion_rate = (offer['completions'] / view_events['views']) * 100
            else:
                conversion_rate = 0.0
            
            top_offers.append({
                'offer_id': offer['metadata__offer_id'],
                'offer_name': offer['metadata__offer_name'],
                'category': offer['metadata__offer_category'],
                'completions': offer['completions'],
                'unique_users': offer['unique_users'],
                'views': view_events['views'],
                'unique_views': view_events['unique_views'],
                'conversion_rate': conversion_rate,
                'revenue': offer['total_revenue'] or Decimal('0'),
                'avg_completion_time': offer['avg_completion_time'],
                'avg_rating': offer['avg_rating']
            })
        
        return top_offers
    
    def collect_offer_funnel(
        self,
        offer_id: int,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict:
        """
        Collect conversion funnel for an offer
        
        Args:
            offer_id: Offer ID
            start_date: Start date
            end_date: End date
        
        Returns:
            Offer conversion funnel
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        # Get all events for this offer
        events = AnalyticsEvent.objects.filter(
            metadata__offer_id=offer_id,
            event_time__gte=start_date,
            event_time__lte=end_date
        )
        
        # Count by event type
        event_counts = events.values('event_type').annotate(
            count=Count('id'),
            unique_users=Count('user_id', distinct=True)
        )
        
        # Build funnel stages
        funnel_stages = {
            'impression': 0,
            'click': 0,
            'start': 0,
            'completion': 0
        }
        
        for event in event_counts:
            event_type = event['event_type']
            if event_type == 'offer_viewed':
                funnel_stages['impression'] = event['count']
            elif event_type == 'offer_clicked':
                funnel_stages['click'] = event['count']
            elif event_type == 'offer_started':
                funnel_stages['start'] = event['count']
            elif event_type == 'offer_completed':
                funnel_stages['completion'] = event['count']
        
        # Calculate conversion rates
        conversion_rates = {}
        
        if funnel_stages['impression'] > 0:
            conversion_rates['impression_to_click'] = \
                (funnel_stages['click'] / funnel_stages['impression']) * 100
            conversion_rates['impression_to_completion'] = \
                (funnel_stages['completion'] / funnel_stages['impression']) * 100
        
        if funnel_stages['click'] > 0:
            conversion_rates['click_to_start'] = \
                (funnel_stages['start'] / funnel_stages['click']) * 100
            conversion_rates['click_to_completion'] = \
                (funnel_stages['completion'] / funnel_stages['click']) * 100
        
        if funnel_stages['start'] > 0:
            conversion_rates['start_to_completion'] = \
                (funnel_stages['completion'] / funnel_stages['start']) * 100
        
        # Calculate drop-off points
        drop_offs = []
        
        stages = [
            ('impression', 'click'),
            ('click', 'start'),
            ('start', 'completion')
        ]
        
        for from_stage, to_stage in stages:
            from_count = funnel_stages[from_stage]
            to_count = funnel_stages[to_stage]
            
            if from_count > 0:
                drop_off = from_count - to_count
                drop_off_rate = (drop_off / from_count) * 100
                
                drop_offs.append({
                    'from': from_stage,
                    'to': to_stage,
                    'drop_off_count': drop_off,
                    'drop_off_rate': drop_off_rate,
                    'retention_rate': 100 - drop_off_rate
                })
        
        return {
            'offer_id': offer_id,
            'period': {
                'start': start_date,
                'end': end_date
            },
            'funnel_stages': funnel_stages,
            'conversion_rates': conversion_rates,
            'drop_offs': drop_offs,
            'total_impressions': funnel_stages['impression'],
            'total_completions': funnel_stages['completion'],
            'overall_conversion_rate': conversion_rates.get('impression_to_completion', 0)
        }
    
    def collect_offer_comparison(
        self,
        offer_ids: List[int],
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict:
        """
        Compare multiple offers
        
        Args:
            offer_ids: List of offer IDs to compare
            start_date: Start date
            end_date: End date
        
        Returns:
            Offer comparison data
        """
        if not offer_ids:
            return {}
        
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        comparison_data = {
            'period': {'start': start_date, 'end': end_date},
            'offers': [],
            'metrics_summary': {}
        }
        
        # Collect data for each offer
        for offer_id in offer_ids:
            offer_performance = self.collect_offer_performance(
                offer_id=offer_id,
                start_date=start_date,
                end_date=end_date,
                period='daily'
            )
            
            if not offer_performance:
                continue
            
            # Aggregate daily data
            total_impressions = sum(d['impressions'] for d in offer_performance)
            total_clicks = sum(d['clicks'] for d in offer_performance)
            total_completions = sum(d['completions'] for d in offer_performance)
            total_revenue = sum(d['revenue_generated'] or Decimal('0') for d in offer_performance)
            
            # Get offer details
            offer_event = AnalyticsEvent.objects.filter(
                metadata__offer_id=offer_id
            ).first()
            
            if offer_event:
                offer_name = offer_event.metadata.get('offer_name', f'Offer {offer_id}')
                offer_category = offer_event.metadata.get('offer_category', 'Unknown')
            else:
                offer_name = f'Offer {offer_id}'
                offer_category = 'Unknown'
            
            # Calculate metrics
            ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            conversion_rate = (total_completions / total_impressions * 100) if total_impressions > 0 else 0
            revenue_per_completion = total_revenue / total_completions if total_completions > 0 else Decimal('0')
            
            comparison_data['offers'].append({
                'offer_id': offer_id,
                'offer_name': offer_name,
                'category': offer_category,
                'impressions': total_impressions,
                'clicks': total_clicks,
                'completions': total_completions,
                'revenue': total_revenue,
                'ctr': ctr,
                'conversion_rate': conversion_rate,
                'revenue_per_completion': revenue_per_completion
            })
        
        # Calculate summary metrics
        if comparison_data['offers']:
            offers = comparison_data['offers']
            
            comparison_data['metrics_summary'] = {
                'total_impressions': sum(o['impressions'] for o in offers),
                'total_completions': sum(o['completions'] for o in offers),
                'total_revenue': sum(o['revenue'] for o in offers),
                'avg_ctr': sum(o['ctr'] for o in offers) / len(offers),
                'avg_conversion_rate': sum(o['conversion_rate'] for o in offers) / len(offers),
                'best_performing': max(offers, key=lambda x: x['revenue']),
                'highest_conversion': max(offers, key=lambda x: x['conversion_rate'])
            }
        
        return comparison_data
    
    def collect_offer_insights(
        self,
        offer_id: int = None,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict:
        """
        Collect insights for offer performance
        
        Args:
            offer_id: Specific offer ID or all offers
            start_date: Start date
            end_date: End date
        
        Returns:
            Offer performance insights
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        # Get performance data
        if offer_id:
            performance_data = self.collect_offer_performance(
                offer_id=offer_id,
                start_date=start_date,
                end_date=end_date,
                period='daily'
            )
        else:
            performance_data = self.collect_offer_performance(
                start_date=start_date,
                end_date=end_date,
                period='daily'
            )
        
        if not performance_data:
            return {'insights': [], 'recommendations': []}
        
        # Analyze for insights
        insights = []
        
        # 1. Trend analysis
        if len(performance_data) >= 7:
            recent_performance = performance_data[-7:]
            previous_performance = performance_data[-14:-7] if len(performance_data) >= 14 else []
            
            if recent_performance and previous_performance:
                recent_completions = sum(d['completions'] for d in recent_performance)
                previous_completions = sum(d['completions'] for d in previous_performance)
                
                if previous_completions > 0:
                    trend = ((recent_completions - previous_completions) / previous_completions) * 100
                    
                    if trend > 20:
                        insights.append({
                            'type': 'positive_trend',
                            'message': f'Offer completions increased by {trend:.1f}% compared to previous week',
                            'severity': 'info'
                        })
                    elif trend < -20:
                        insights.append({
                            'type': 'negative_trend',
                            'message': f'Offer completions decreased by {abs(trend):.1f}% compared to previous week',
                            'severity': 'warning'
                        })
        
        # 2. Conversion rate analysis
        for data in performance_data[-3:]:  # Last 3 periods
            if data['impressions'] > 100 and data['conversion_rate'] < 5:
                insights.append({
                    'type': 'low_conversion',
                    'message': f'Low conversion rate ({data["conversion_rate"]:.1f}%) on {data["period"].date()}',
                    'severity': 'warning'
                })
            elif data['impressions'] > 100 and data['conversion_rate'] > 20:
                insights.append({
                    'type': 'high_conversion',
                    'message': f'High conversion rate ({data["conversion_rate"]:.1f}%) on {data["period"].date()}',
                    'severity': 'info'
                })
        
        # 3. ROI analysis
        for data in performance_data:
            if data['roi'] < 0:
                insights.append({
                    'type': 'negative_roi',
                    'message': f'Negative ROI ({data["roi"]:.1f}%) detected',
                    'severity': 'critical'
                })
                break
        
        # Generate recommendations based on insights
        recommendations = self._generate_recommendations(insights, performance_data)
        
        return {
            'insights': insights,
            'recommendations': recommendations,
            'performance_summary': {
                'total_periods': len(performance_data),
                'total_impressions': sum(d['impressions'] for d in performance_data),
                'total_completions': sum(d['completions'] for d in performance_data),
                'avg_conversion_rate': sum(d['conversion_rate'] for d in performance_data) / len(performance_data) if performance_data else 0,
                'total_revenue': sum(d['revenue_generated'] or Decimal('0') for d in performance_data)
            }
        }
    
    # Helper methods
    def _get_metric_field(self, metric: str) -> str:
        """Map metric name to field name"""
        metric_map = {
            'revenue': 'total_revenue',
            'completions': 'completions',
            'conversion': 'conversion_rate',
            'roi': 'roi',
            'ctr': 'ctr'
        }
        return metric_map.get(metric, 'total_revenue')
    
    def _generate_recommendations(
        self,
        insights: List[Dict],
        performance_data: List[Dict]
    ) -> List[Dict]:
        """Generate recommendations based on insights"""
        recommendations = []
        
        insight_types = [insight['type'] for insight in insights]
        
        # Low conversion recommendation
        if 'low_conversion' in insight_types:
            recommendations.append({
                'title': 'Improve Offer Conversion',
                'description': 'Consider optimizing the offer description, adding incentives, or targeting different user segments.',
                'priority': 'high',
                'actions': [
                    'A/B test different offer descriptions',
                    'Add completion bonus',
                    'Target users with higher engagement scores'
                ]
            })
        
        # Negative ROI recommendation
        if 'negative_roi' in insight_types:
            recommendations.append({
                'title': 'Address Negative ROI',
                'description': 'The offer is currently losing money. Consider reducing payouts or improving conversion rates.',
                'priority': 'critical',
                'actions': [
                    'Reduce offer payout amount',
                    'Improve targeting to reduce wasted impressions',
                    'Consider pausing the offer temporarily'
                ]
            })
        
        # Positive trend recommendation
        if 'positive_trend' in insight_types:
            recommendations.append({
                'title': 'Capitalize on Positive Trend',
                'description': 'The offer is performing well. Consider increasing its visibility.',
                'priority': 'medium',
                'actions': [
                    'Feature the offer on the homepage',
                    'Send targeted notifications to interested users',
                    'Increase daily impression limits'
                ]
            })
        
        # Check for device-specific opportunities
        if performance_data:
            last_period = performance_data[-1]
            if last_period.get('mobile_views', 0) > last_period.get('desktop_views', 0) * 2:
                recommendations.append({
                    'title': 'Mobile-First Optimization',
                    'description': 'Most views are coming from mobile devices. Ensure the offer is optimized for mobile.',
                    'priority': 'medium',
                    'actions': [
                        'Test mobile-specific layouts',
                        'Ensure fast loading on mobile networks',
                        'Simplify mobile completion process'
                    ]
                })
        
        return recommendations