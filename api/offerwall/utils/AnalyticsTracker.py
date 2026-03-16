"""
Analytics tracking utility for offers
"""
import logging
from django.utils import timezone
from django.db.models import Avg, Sum, Count, F
from datetime import timedelta
from ..constants import *

logger = logging.getLogger(__name__)


class AnalyticsTracker:
    """Track and analyze offer performance"""
    
    def __init__(self, offer=None, user=None):
        self.offer = offer
        self.user = user
    
    def track_offer_view(self, request_data):
        """
        Track offer view event
        
        Args:
            request_data: Dictionary with request information
        
        Returns:
            bool: Success status
        """
        try:
            from api.analytics.models import AnalyticsEvent
            
            AnalyticsEvent.objects.create(
                event_type=EVENT_OFFER_VIEW,
                user=self.user,
                ip_address=request_data.get('ip_address'),
                user_agent=request_data.get('user_agent'),
                device_type=request_data.get('device_type'),
                browser=request_data.get('browser'),
                os=request_data.get('os'),
                country=request_data.get('country'),
                metadata={
                    'offer_id': str(self.offer.id) if self.offer else None,
                    'offer_title': self.offer.title if self.offer else None,
                    'offer_type': self.offer.offer_type if self.offer else None,
                    'payout': float(self.offer.payout) if self.offer else None,
                }
            )
            
            # Increment offer view count
            if self.offer:
                self.offer.view_count = F('view_count') + 1
                self.offer.save(update_fields=['view_count'])
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to track offer view: {e}")
            return False
    
    def track_offer_click(self, click_data):
        """
        Track offer click event
        
        Args:
            click_data: Dictionary with click information
        
        Returns:
            OfferClick instance or None
        """
        try:
            from ..models import OfferClick
            from api.analytics.models import AnalyticsEvent
            import uuid
            
            # Create click record
            click = OfferClick.objects.create(
                offer=self.offer,
                user=self.user,
                click_id=str(uuid.uuid4()),
                ip_address=click_data.get('ip_address'),
                user_agent=click_data.get('user_agent', ''),
                device_type=click_data.get('device_type', ''),
                device_model=click_data.get('device_model', ''),
                os=click_data.get('os', ''),
                os_version=click_data.get('os_version', ''),
                browser=click_data.get('browser', ''),
                country=click_data.get('country', ''),
                city=click_data.get('city', ''),
                referrer_url=click_data.get('referrer_url', ''),
                session_id=click_data.get('session_id', ''),
                tracking_params=click_data.get('tracking_params', {})
            )
            
            # Track analytics event
            AnalyticsEvent.objects.create(
                event_type=EVENT_OFFER_CLICK,
                user=self.user,
                ip_address=click_data.get('ip_address'),
                user_agent=click_data.get('user_agent'),
                device_type=click_data.get('device_type'),
                metadata={
                    'offer_id': str(self.offer.id),
                    'offer_title': self.offer.title,
                    'click_id': click.click_id,
                    'payout': float(self.offer.payout),
                }
            )
            
            # Increment offer click count
            self.offer.click_count = F('click_count') + 1
            self.offer.save(update_fields=['click_count'])
            
            logger.info(f"Tracked click: {click.click_id} for offer {self.offer.id}")
            
            return click
        
        except Exception as e:
            logger.error(f"Failed to track offer click: {e}")
            return None
    
    def track_offer_conversion(self, conversion_data):
        """
        Track offer conversion event
        
        Args:
            conversion_data: Dictionary with conversion information
        
        Returns:
            bool: Success status
        """
        try:
            from api.analytics.models import AnalyticsEvent
            
            AnalyticsEvent.objects.create(
                event_type=EVENT_OFFER_CONVERSION,
                user=self.user,
                value=conversion_data.get('reward_amount'),
                metadata={
                    'offer_id': str(self.offer.id) if self.offer else None,
                    'offer_title': self.offer.title if self.offer else None,
                    'conversion_id': conversion_data.get('conversion_id'),
                    'payout': conversion_data.get('payout_amount'),
                    'reward': conversion_data.get('reward_amount'),
                    'status': conversion_data.get('status', 'pending'),
                }
            )
            
            # Increment conversion count
            if self.offer:
                self.offer.conversion_count = F('conversion_count') + 1
                
                # Update completion rate
                if self.offer.click_count > 0:
                    rate = (self.offer.conversion_count / self.offer.click_count) * 100
                    self.offer.completion_rate = rate
                
                self.offer.save(update_fields=['conversion_count', 'completion_rate'])
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to track conversion: {e}")
            return False
    
    def get_offer_performance_stats(self, period='all'):
        """
        Get performance statistics for offer
        
        Args:
            period: Time period ('day', 'week', 'month', 'all')
        
        Returns:
            dict: Performance statistics
        """
        if not self.offer:
            return {}
        
        from ..models import OfferClick, OfferConversion
        
        # Determine time filter
        if period == 'day':
            time_filter = timezone.now() - timedelta(days=1)
        elif period == 'week':
            time_filter = timezone.now() - timedelta(weeks=1)
        elif period == 'month':
            time_filter = timezone.now() - timedelta(days=30)
        else:
            time_filter = None
        
        # Base querysets
        clicks_qs = OfferClick.objects.filter(offer=self.offer)
        conversions_qs = OfferConversion.objects.filter(offer=self.offer)
        
        if time_filter:
            clicks_qs = clicks_qs.filter(clicked_at__gte=time_filter)
            conversions_qs = conversions_qs.filter(converted_at__gte=time_filter)
        
        # Calculate stats
        total_clicks = clicks_qs.count()
        total_conversions = conversions_qs.filter(status=CONVERSION_APPROVED).count()
        pending_conversions = conversions_qs.filter(status=CONVERSION_PENDING).count()
        
        conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
        
        total_revenue = conversions_qs.filter(
            status=CONVERSION_APPROVED
        ).aggregate(
            total=Sum('payout_amount')
        )['total'] or 0
        
        total_payout = conversions_qs.filter(
            status=CONVERSION_APPROVED
        ).aggregate(
            total=Sum('reward_amount')
        )['total'] or 0
        
        # Device breakdown
        device_breakdown = clicks_qs.values('device_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Country breakdown
        country_breakdown = clicks_qs.exclude(country='').values('country').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return {
            'period': period,
            'views': self.offer.view_count,
            'clicks': total_clicks,
            'conversions': total_conversions,
            'pending_conversions': pending_conversions,
            'conversion_rate': round(conversion_rate, 2),
            'ctr': round((total_clicks / self.offer.view_count * 100) if self.offer.view_count > 0 else 0, 2),
            'total_revenue': float(total_revenue),
            'total_payout': float(total_payout),
            'profit': float(total_revenue - total_payout),
            'device_breakdown': list(device_breakdown),
            'country_breakdown': list(country_breakdown),
            'quality_score': self.offer.quality_score,
        }
    
    def get_user_offer_stats(self):
        """
        Get user's offer completion statistics
        
        Returns:
            dict: User statistics
        """
        if not self.user:
            return {}
        
        from ..models import OfferConversion, OfferClick
        
        conversions = OfferConversion.objects.filter(user=self.user)
        
        total_completions = conversions.filter(status=CONVERSION_APPROVED).count()
        pending = conversions.filter(status=CONVERSION_PENDING).count()
        rejected = conversions.filter(status=CONVERSION_REJECTED).count()
        
        total_earned = conversions.filter(status=CONVERSION_APPROVED).aggregate(
            total=Sum('reward_amount')
        )['total'] or 0
        
        pending_earnings = conversions.filter(status=CONVERSION_PENDING).aggregate(
            total=Sum('reward_amount')
        )['total'] or 0
        
        # Favorite category
        favorite_category = conversions.filter(
            status=CONVERSION_APPROVED
        ).values('offer__category__name').annotate(
            count=Count('id')
        ).order_by('-count').first()
        
        # Most completed offer type
        top_offer_type = conversions.filter(
            status=CONVERSION_APPROVED
        ).values('offer__offer_type').annotate(
            count=Count('id')
        ).order_by('-count').first()
        
        # Recent activity
        recent_completions = conversions.filter(
            converted_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        return {
            'total_completions': total_completions,
            'pending_conversions': pending,
            'rejected_conversions': rejected,
            'total_earned': float(total_earned),
            'pending_earnings': float(pending_earnings),
            'favorite_category': favorite_category['offer__category__name'] if favorite_category else 'N/A',
            'most_completed_offer_type': top_offer_type['offer__offer_type'] if top_offer_type else 'N/A',
            'recent_completions_30d': recent_completions,
            'success_rate': round((total_completions / (total_completions + rejected) * 100) if (total_completions + rejected) > 0 else 0, 2),
        }
    
    def get_provider_performance(self, provider):
        """
        Get performance stats for provider
        
        Args:
            provider: OfferProvider instance
        
        Returns:
            dict: Provider statistics
        """
        from ..models import Offer, OfferConversion
        
        offers = Offer.objects.filter(provider=provider)
        
        total_offers = offers.count()
        active_offers = offers.filter(status=STATUS_ACTIVE).count()
        
        total_views = offers.aggregate(total=Sum('view_count'))['total'] or 0
        total_clicks = offers.aggregate(total=Sum('click_count'))['total'] or 0
        total_conversions = offers.aggregate(total=Sum('conversion_count'))['total'] or 0
        
        conversions = OfferConversion.objects.filter(offer__provider=provider)
        
        total_revenue = conversions.filter(status=CONVERSION_APPROVED).aggregate(
            total=Sum('payout_amount')
        )['total'] or 0
        
        total_payout = conversions.filter(status=CONVERSION_APPROVED).aggregate(
            total=Sum('reward_amount')
        )['total'] or 0
        
        avg_completion_rate = offers.aggregate(avg=Avg('completion_rate'))['avg'] or 0
        avg_quality_score = offers.aggregate(avg=Avg('quality_score'))['avg'] or 0
        
        return {
            'provider_name': provider.name,
            'total_offers': total_offers,
            'active_offers': active_offers,
            'total_views': total_views,
            'total_clicks': total_clicks,
            'total_conversions': total_conversions,
            'conversion_rate': round((total_conversions / total_clicks * 100) if total_clicks > 0 else 0, 2),
            'ctr': round((total_clicks / total_views * 100) if total_views > 0 else 0, 2),
            'total_revenue': float(total_revenue),
            'total_payout': float(total_payout),
            'profit': float(total_revenue - total_payout),
            'avg_completion_rate': round(avg_completion_rate, 2),
            'avg_quality_score': round(avg_quality_score, 2),
        }
    
    def get_trending_offers(self, limit=10):
        """
        Get trending offers based on recent activity
        
        Args:
            limit: Number of offers to return
        
        Returns:
            QuerySet: Trending offers
        """
        from ..models import Offer
        from django.db.models import F, Q
        
        # Calculate trending score based on recent activity
        recent_time = timezone.now() - timedelta(days=7)
        
        trending_offers = Offer.objects.filter(
            status=STATUS_ACTIVE,
            created_at__lte=timezone.now() - timedelta(days=1)  # At least 1 day old
        ).annotate(
            trending_score=(
                F('conversion_count') * 3 +  # Weight conversions more
                F('click_count') * 2 +
                F('view_count')
            ) / (
                (timezone.now() - F('created_at')).total_seconds() / 86400 + 1  # Days since creation
            )
        ).order_by('-trending_score')[:limit]
        
        return trending_offers
    
    def update_offer_analytics(self):
        """
        Update offer's analytics data
        
        Returns:
            bool: Success status
        """
        if not self.offer:
            return False
        
        try:
            from ..models import OfferConversion
            
            # Update revenue
            total_revenue = OfferConversion.objects.filter(
                offer=self.offer,
                status=CONVERSION_APPROVED
            ).aggregate(total=Sum('payout_amount'))['total'] or 0
            
            total_payout = OfferConversion.objects.filter(
                offer=self.offer,
                status=CONVERSION_APPROVED
            ).aggregate(total=Sum('reward_amount'))['total'] or 0
            
            self.offer.total_revenue = total_revenue
            self.offer.total_payout = total_payout
            
            # Update completion rate
            if self.offer.click_count > 0:
                self.offer.completion_rate = (
                    self.offer.conversion_count / self.offer.click_count
                ) * 100
            
            # Calculate and update quality score
            self.offer.calculate_quality_score()
            
            self.offer.save()
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to update offer analytics: {e}")
            return False
    
    @staticmethod
    def generate_performance_report(start_date, end_date):
        """
        Generate comprehensive performance report
        
        Args:
            start_date: Start date for report
            end_date: End date for report
        
        Returns:
            dict: Performance report
        """
        from ..models import Offer, OfferClick, OfferConversion
        
        offers = Offer.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        clicks = OfferClick.objects.filter(
            clicked_at__gte=start_date,
            clicked_at__lte=end_date
        )
        
        conversions = OfferConversion.objects.filter(
            converted_at__gte=start_date,
            converted_at__lte=end_date
        )
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
            },
            'offers': {
                'total': offers.count(),
                'active': offers.filter(status=STATUS_ACTIVE).count(),
                'featured': offers.filter(is_featured=True).count(),
            },
            'engagement': {
                'total_clicks': clicks.count(),
                'unique_users': clicks.values('user').distinct().count(),
                'total_conversions': conversions.filter(status=CONVERSION_APPROVED).count(),
            },
            'revenue': {
                'total': float(conversions.filter(status=CONVERSION_APPROVED).aggregate(
                    total=Sum('payout_amount')
                )['total'] or 0),
                'payouts': float(conversions.filter(status=CONVERSION_APPROVED).aggregate(
                    total=Sum('reward_amount')
                )['total'] or 0),
            }
        }