import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg, F, Window, Value
from django.db.models.functions import TruncDate, TruncHour, RowNumber
from django.core.cache import cache
from django.conf import settings
import random
from collections import defaultdict

from ..models import (
    Banner, BannerImpression, BannerClick, BannerReward,
    ContentPage
)
from api.users.models import User, UserProfile
from api.wallet.models import Transaction
# from api.tasks.models import Task
# from api.offerwall.models import Offer
# from core.utils import get_client_ip

logger = logging.getLogger(__name__)


class BannerService:
    """Service class for banner management business logic"""
    
    @staticmethod
    def get_active_banners(
        user: Optional[User] = None,
        device: str = 'desktop',
        position: Optional[str] = None,
        limit: int = 10,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Banner]:
        """
        Get active banners for specific user, device, and position
        
        Args:
            user: User requesting banners (for targeting)
            device: Device type ('desktop', 'mobile', 'tablet')
            position: Banner position (e.g., 'top', 'sidebar')
            limit: Maximum number of banners to return
            context: Additional context for targeting
            
        Returns:
            List of active banners
        """
        try:
            now = timezone.now()
            
            # Build base query
            query = Q(
                is_active=True,
                start_date__lte=now
            ) & (
                Q(end_date__isnull=True) | Q(end_date__gte=now)
            )
            
            # Filter by device
            query &= Q(target_device='all') | Q(target_device=device)
            
            # Filter by position if specified
            if position:
                query &= Q(position=position)
            
            # Get all eligible banners
            eligible_banners = Banner.objects.filter(query)\
                .select_related('internal_page', 'offer', 'task')\
                .order_by('-priority', '-created_at')
            
            # Apply targeting rules
            filtered_banners = []
            for banner in eligible_banners:
                if BannerService._check_banner_targeting(banner, user, context):
                    filtered_banners.append(banner)
                
                if len(filtered_banners) >= limit:
                    break
            
            # Apply display frequency and rotation
            banners = BannerService._apply_display_rules(filtered_banners, user, limit)
            
            return banners
            
        except Exception as e:
            logger.error(f"Error getting active banners: {str(e)}")
            return []
    
    @staticmethod
    def _check_banner_targeting(
        banner: Banner,
        user: Optional[User],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if banner should be shown to user based on targeting rules
        
        Args:
            banner: Banner object
            user: User to check targeting for
            context: Additional context
            
        Returns:
            Boolean indicating if banner should be shown
        """
        try:
            # Check user level
            if banner.min_user_level > 0:
                if not user or user.level < banner.min_user_level:
                    return False
            
            # Check required tags
            if banner.required_tags:
                user_tags = user.tags if user and hasattr(user, 'tags') else []
                if not set(banner.required_tags).issubset(set(user_tags)):
                    return False
            
            # Check excluded tags
            if banner.excluded_tags:
                user_tags = user.tags if user and hasattr(user, 'tags') else []
                if set(banner.excluded_tags).intersection(set(user_tags)):
                    return False
            
            # Check target audience rules
            if banner.target_audience:
                if not BannerService._check_audience_rules(banner.target_audience, user, context):
                    return False
            
            # Check impression limits
            if banner.max_impressions > 0 and banner.impression_count >= banner.max_impressions:
                return False
            
            # Check click limits
            if banner.max_clicks > 0 and banner.click_count >= banner.max_clicks:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking banner targeting: {str(e)}")
            return False
    
    @staticmethod
    def _check_audience_rules(
        audience_rules: Dict[str, Any],
        user: Optional[User],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check advanced audience targeting rules
        
        Args:
            audience_rules: Audience targeting rules dictionary
            user: User to check
            context: Additional context
            
        Returns:
            Boolean indicating if user matches audience
        """
        if not audience_rules or not user:
            return True
        
        try:
            # Check country
            if 'countries' in audience_rules:
                user_country = user.country if hasattr(user, 'country') else None
                if user_country and user_country not in audience_rules['countries']:
                    return False
            
            # Check language
            if 'languages' in audience_rules:
                user_language = user.language if hasattr(user, 'language') else 'en'
                if user_language not in audience_rules['languages']:
                    return False
            
            # Check user registration date
            if 'min_registration_days' in audience_rules:
                if user.date_joined:
                    days_registered = (timezone.now() - user.date_joined).days
                    if days_registered < audience_rules['min_registration_days']:
                        return False
            
            # Check user activity
            if 'min_total_earnings' in audience_rules:
                total_earnings = getattr(user, 'total_earnings', 0)
                if total_earnings < audience_rules['min_total_earnings']:
                    return False
            
            # Check completion rates
            if 'min_completion_rate' in audience_rules:
                completion_rate = getattr(user, 'completion_rate', 0)
                if completion_rate < audience_rules['min_completion_rate']:
                    return False
            
            # Check device context
            if context and 'device' in context:
                if 'devices' in audience_rules and context['device'] not in audience_rules['devices']:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking audience rules: {str(e)}")
            return True
    
    @staticmethod
    def _apply_display_rules(
        banners: List[Banner],
        user: Optional[User],
        limit: int
    ) -> List[Banner]:
        """
        Apply display frequency and rotation rules
        
        Args:
            banners: List of eligible banners
            user: User for frequency tracking
            limit: Maximum banners to return
            
        Returns:
            Filtered and sorted banners
        """
        if not banners:
            return []
        
        try:
            # Calculate weights for each banner
            weighted_banners = []
            for banner in banners:
                weight = banner.priority
                
                # Reduce weight for frequently shown banners
                if user:
                    user_impressions = BannerImpression.objects.filter(
                        banner=banner,
                        user=user,
                        created_at__gte=timezone.now() - timedelta(hours=24)
                    ).count()
                    
                    if user_impressions > 0:
                        weight = max(1, weight // (user_impressions + 1))
                
                # Apply display frequency
                if banner.display_frequency > 1:
                    total_impressions = banner.impression_count
                    if total_impressions % banner.display_frequency != 0:
                        weight = max(1, weight // 2)
                
                weighted_banners.append((banner, weight))
            
            # Sort by weight (higher weight first)
            weighted_banners.sort(key=lambda x: x[1], reverse=True)
            
            # Select banners using weighted random selection
            selected_banners = []
            total_weight = sum(weight for _, weight in weighted_banners)
            
            for _ in range(min(limit, len(weighted_banners))):
                if not weighted_banners:
                    break
                
                # Weighted random selection
                r = random.uniform(0, total_weight)
                current = 0
                for i, (banner, weight) in enumerate(weighted_banners):
                    current += weight
                    if r <= current:
                        selected_banners.append(banner)
                        total_weight -= weight
                        weighted_banners.pop(i)
                        break
            
            return selected_banners
            
        except Exception as e:
            logger.error(f"Error applying display rules: {str(e)}")
            return banners[:limit]
    
    @staticmethod
    def record_impression(
        banner: Banner,
        user: Optional[User] = None,
        request = None,
        impression_type: str = 'view'
    ) -> bool:
        """
        Record a banner impression
        
        Args:
            banner: Banner object
            user: User who saw the banner
            request: Django request object
            impression_type: Type of impression
            
        Returns:
            Boolean indicating success
        """
        try:
            with transaction.atomic():
                # Get client info from request
                ip_address = None
                user_agent = ''
                referrer = ''
                session_id = ''
                
                if request:
                    ip_address = get_client_ip(request)
                    user_agent = request.META.get('HTTP_USER_AGENT', '')
                    referrer = request.META.get('HTTP_REFERER', '')
                    session_id = request.session.session_key if hasattr(request, 'session') else ''
                
                # Create impression record
                impression = BannerImpression.objects.create(
                    banner=banner,
                    user=user,
                    impression_type=impression_type,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    referrer=referrer,
                    session_id=session_id
                )
                
                # Update banner impression count
                Banner.objects.filter(id=banner.id).update(
                    impression_count=F('impression_count') + 1
                )
                
                # Clear cache
                cache.delete_pattern(f'banner_stats_{banner.id}_*')
                
                logger.debug(f"Recorded impression for banner {banner.id}")
                return True
                
        except Exception as e:
            logger.error(f"Error recording banner impression: {str(e)}")
            return False
    
    @staticmethod
    def record_click(
        banner: Banner,
        user: Optional[User] = None,
        request = None,
        click_type: str = 'user'
    ) -> Dict[str, Any]:
        """
        Record a banner click and return redirect info
        
        Args:
            banner: Banner object
            user: User who clicked
            request: Django request object
            click_type: Type of click
            
        Returns:
            Dictionary with redirect URL and metadata
        """
        try:
            with transaction.atomic():
                # Get client info
                ip_address = None
                user_agent = ''
                
                if request:
                    ip_address = get_client_ip(request)
                    user_agent = request.META.get('HTTP_USER_AGENT', '')
                
                # Create click record
                click = BannerClick.objects.create(
                    banner=banner,
                    user=user,
                    click_type=click_type,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                # Update banner click count
                Banner.objects.filter(id=banner.id).update(
                    click_count=F('click_count') + 1
                )
                
                # Award reward if applicable
                reward_awarded = False
                if banner.reward_amount > 0 and user:
                    reward_awarded = BannerService._award_banner_reward(banner, user, click)
                
                # Get redirect URL
                redirect_url = BannerService._get_banner_redirect_url(banner)
                
                # Clear cache
                cache.delete_pattern(f'banner_stats_{banner.id}_*')
                
                logger.info(f"Recorded click for banner {banner.id} by user {user.id if user else 'anonymous'}")
                
                return {
                    'success': True,
                    'redirect_url': redirect_url,
                    'reward_awarded': reward_awarded,
                    'click_id': click.id
                }
                
        except Exception as e:
            logger.error(f"Error recording banner click: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _award_banner_reward(
        banner: Banner,
        user: User,
        click: BannerClick
    ) -> bool:
        """
        Award reward for banner click
        
        Args:
            banner: Banner object
            user: User to award
            click: Click record
            
        Returns:
            Boolean indicating if reward was awarded
        """
        try:
            # Check if user has reached max rewards for this banner
            user_reward_count = BannerReward.objects.filter(
                banner=banner,
                user=user
            ).count()
            
            if user_reward_count >= banner.max_rewards_per_user:
                logger.info(f"User {user.id} has reached max rewards for banner {banner.id}")
                return False
            
            # Check reward type conditions
            if banner.reward_type == 'conversion':
                # For conversion rewards, we need conversion tracking
                # This would be implemented based on specific conversion events
                logger.debug(f"Conversion reward for banner {banner.id} requires conversion tracking")
                return False
            
            # Create reward record
            reward = BannerReward.objects.create(
                banner=banner,
                user=user,
                amount=banner.reward_amount,
                reward_type=banner.reward_type
            )
            
            # Create transaction
            transaction = Transaction.objects.create(
                user=user,
                transaction_type='banner_reward',
                amount=banner.reward_amount,
                currency='USD',  # Default currency, could be configurable
                status='completed',
                description=f"Banner click reward: {banner.name}",
                metadata={
                    'banner_id': banner.id,
                    'click_id': click.id,
                    'reward_id': reward.id,
                    'reward_type': banner.reward_type
                }
            )
            
            # Link transaction to reward
            reward.transaction = transaction
            reward.save()
            
            # Update banner revenue if applicable
            if banner.reward_type == 'click':
                Banner.objects.filter(id=banner.id).update(
                    conversion_count=F('conversion_count') + 1,
                    total_revenue=F('total_revenue') + banner.reward_amount
                )
            
            logger.info(f"Awarded {banner.reward_amount} to user {user.id} for banner {banner.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error awarding banner reward: {str(e)}")
            return False
    
    @staticmethod
    def _get_banner_redirect_url(banner: Banner) -> str:
        """
        Get redirect URL for banner based on link type
        
        Args:
            banner: Banner object
            
        Returns:
            Redirect URL string
        """
        try:
            if banner.link_type == 'external':
                return banner.link_url
            
            elif banner.link_type == 'internal':
                if banner.internal_page:
                    return banner.internal_page.get_absolute_url()
                return '#'
            
            elif banner.link_type == 'offer':
                if banner.offer:
                    # Assuming offer has a get_absolute_url method
                    return f"/offers/{banner.offer.id}/"
                return '#'
            
            elif banner.link_type == 'task':
                if banner.task:
                    return f"/tasks/{banner.task.id}/"
                return '#'
            
            elif banner.link_type == 'category':
                if banner.category:
                    return f"/category/{banner.category.slug}/"
                return '#'
            
            elif banner.link_type == 'wallet':
                return "/wallet/"
            
            elif banner.link_type == 'profile':
                return "/profile/"
            
            else:
                return '#'
                
        except Exception as e:
            logger.error(f"Error getting banner redirect URL: {str(e)}")
            return '#'
    
    @staticmethod
    def get_banner_statistics(
        banner: Banner,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get detailed statistics for a banner
        
        Args:
            banner: Banner object
            start_date: Start date for statistics
            end_date: End date for statistics
            
        Returns:
            Dictionary with banner statistics
        """
        cache_key = f'banner_stats_{banner.id}_{start_date}_{end_date}'
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        try:
            if not start_date:
                start_date = banner.start_date
            if not end_date:
                end_date = timezone.now()
            
            # Get impressions
            impressions = BannerImpression.objects.filter(
                banner=banner,
                created_at__range=(start_date, end_date)
            )
            
            # Get clicks
            clicks = BannerClick.objects.filter(
                banner=banner,
                created_at__range=(start_date, end_date)
            )
            
            # Calculate metrics
            total_impressions = impressions.count()
            total_clicks = clicks.count()
            
            # Click-through rate
            ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            
            # Conversion metrics
            conversions = clicks.filter(conversion_value__gt=0).count()
            conversion_rate = (conversions / total_clicks * 100) if total_clicks > 0 else 0
            total_revenue = clicks.aggregate(total=Sum('conversion_value'))['total'] or 0
            
            # User engagement
            unique_users = impressions.values('user').distinct().count()
            returning_users = impressions.values('user').annotate(
                count=Count('id')
            ).filter(count__gt=1).count()
            
            # Device breakdown
            device_breakdown = impressions.values('user_agent').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            # Hourly breakdown
            hourly_stats = impressions.annotate(
                hour=TruncHour('created_at')
            ).values('hour').annotate(
                impressions=Count('id'),
                clicks=Count('banner__clicks')
            ).order_by('hour')
            
            # Daily trends
            daily_stats = impressions.annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                impressions=Count('id'),
                clicks=Count('banner__clicks'),
                ctr=Count('banner__clicks') * 100.0 / Count('id')
            ).order_by('date')
            
            stats = {
                'banner_id': banner.id,
                'banner_name': banner.name,
                'period': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'overview': {
                    'total_impressions': total_impressions,
                    'total_clicks': total_clicks,
                    'click_through_rate': round(ctr, 2),
                    'conversions': conversions,
                    'conversion_rate': round(conversion_rate, 2),
                    'total_revenue': float(total_revenue),
                    'unique_users': unique_users,
                    'returning_users': returning_users
                },
                'performance_metrics': {
                    'impression_count': banner.impression_count,
                    'click_count': banner.click_count,
                    'conversion_count': banner.conversion_count,
                    'total_revenue': float(banner.total_revenue),
                    'max_impressions': banner.max_impressions,
                    'max_clicks': banner.max_clicks,
                    'remaining_impressions': max(0, banner.max_impressions - banner.impression_count) if banner.max_impressions > 0 else 'unlimited',
                    'remaining_clicks': max(0, banner.max_clicks - banner.click_count) if banner.max_clicks > 0 else 'unlimited'
                },
                'breakdowns': {
                    'hourly': list(hourly_stats),
                    'daily': list(daily_stats),
                    'devices': list(device_breakdown)
                }
            }
            
            cache.set(cache_key, stats, 300)  # Cache for 5 minutes
            return stats
            
        except Exception as e:
            logger.error(f"Error getting banner statistics: {str(e)}")
            return {}
    
    @staticmethod
    def get_analytics(
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        banner_type: Optional[str] = None,
        position: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get analytics for multiple banners
        
        Args:
            start_date: Start date for analytics
            end_date: End date for analytics
            banner_type: Filter by banner type
            position: Filter by position
            
        Returns:
            List of analytics data for banners
        """
        try:
            if not start_date:
                start_date = timezone.now() - timedelta(days=30)
            if not end_date:
                end_date = timezone.now()
            
            # Build query
            query = Q(
                impressions__created_at__range=(start_date, end_date)
            )
            
            if banner_type:
                query &= Q(banner_type=banner_type)
            
            if position:
                query &= Q(position=position)
            
            # Get banners with aggregated data
            banners = Banner.objects.filter(query)\
                .annotate(
                    total_impressions=Count('impressions'),
                    total_clicks=Count('clicks'),
                    total_conversions=Count('clicks', filter=Q(clicks__conversion_value__gt=0)),
                    total_revenue=Sum('clicks__conversion_value')
                )\
                .select_related('internal_page', 'offer', 'task')\
                .order_by('-total_impressions')
            
            analytics_data = []
            for banner in banners:
                if banner.total_impressions == 0:
                    continue
                
                ctr = (banner.total_clicks / banner.total_impressions * 100) if banner.total_impressions > 0 else 0
                conversion_rate = (banner.total_conversions / banner.total_clicks * 100) if banner.total_clicks > 0 else 0
                
                analytics_data.append({
                    'banner': {
                        'id': banner.id,
                        'name': banner.name,
                        'type': banner.banner_type,
                        'position': banner.position,
                        'is_active': banner.is_active_now()
                    },
                    'date': start_date.date(),
                    'impressions': banner.total_impressions,
                    'clicks': banner.total_clicks,
                    'conversions': banner.total_conversions,
                    'revenue': float(banner.total_revenue or 0),
                    'ctr': round(ctr, 2),
                    'conversion_rate': round(conversion_rate, 2)
                })
            
            return analytics_data
            
        except Exception as e:
            logger.error(f"Error getting banner analytics: {str(e)}")
            return []
    
    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """
        Get overall banner statistics
        
        Returns:
            Dictionary with banner statistics
        """
        cache_key = 'banner_statistics_overall'
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        try:
            now = timezone.now()
            thirty_days_ago = now - timedelta(days=30)
            
            # Overall counts
            total_banners = Banner.objects.count()
            active_banners = Banner.objects.filter(is_active=True).count()
            expired_banners = Banner.objects.filter(
                end_date__lt=now, is_active=True
            ).count()
            
            # Performance metrics
            total_impressions = Banner.objects.aggregate(
                total=Sum('impression_count')
            )['total'] or 0
            
            total_clicks = Banner.objects.aggregate(
                total=Sum('click_count')
            )['total'] or 0
            
            total_revenue = Banner.objects.aggregate(
                total=Sum('total_revenue')
            )['total'] or 0
            
            # Recent performance (last 30 days)
            recent_impressions = BannerImpression.objects.filter(
                created_at__gte=thirty_days_ago
            ).count()
            
            recent_clicks = BannerClick.objects.filter(
                created_at__gte=thirty_days_ago
            ).count()
            
            # Top performing banners
            top_banners = Banner.objects.filter(
                impression_count__gt=0
            ).order_by('-impression_count')[:5]
            
            # Banner type distribution
            type_distribution = Banner.objects.values('banner_type')\
                .annotate(
                    count=Count('id'),
                    total_impressions=Sum('impression_count'),
                    total_clicks=Sum('click_count')
                )\
                .order_by('-total_impressions')
            
            # Position performance
            position_performance = Banner.objects.values('position')\
                .annotate(
                    count=Count('id'),
                    avg_ctr=Avg(
                        models.ExpressionWrapper(
                            models.F('click_count') * 100.0 / models.F('impression_count'),
                            output_field=models.FloatField()
                        )
                    ),
                    total_revenue=Sum('total_revenue')
                )\
                .order_by('-total_revenue')
            
            stats = {
                'summary': {
                    'total_banners': total_banners,
                    'active_banners': active_banners,
                    'expired_banners': expired_banners,
                    'total_impressions': total_impressions,
                    'total_clicks': total_clicks,
                    'total_revenue': float(total_revenue),
                    'overall_ctr': round((total_clicks / total_impressions * 100) if total_impressions > 0 else 0, 2),
                    'recent_impressions': recent_impressions,
                    'recent_clicks': recent_clicks
                },
                'top_performing': [
                    {
                        'id': banner.id,
                        'name': banner.name,
                        'impressions': banner.impression_count,
                        'clicks': banner.click_count,
                        'ctr': round((banner.click_count / banner.impression_count * 100) if banner.impression_count > 0 else 0, 2),
                        'revenue': float(banner.total_revenue)
                    }
                    for banner in top_banners
                ],
                'type_distribution': list(type_distribution),
                'position_performance': list(position_performance),
                'current_active': BannerService._get_current_active_banners()
            }
            
            cache.set(cache_key, stats, 300)  # Cache for 5 minutes
            return stats
            
        except Exception as e:
            logger.error(f"Error getting banner statistics: {str(e)}")
            return {}
    
    @staticmethod
    def _get_current_active_banners() -> List[Dict[str, Any]]:
        """
        Get currently active banners with their status
        
        Returns:
            List of active banners with status
        """
        try:
            now = timezone.now()
            active_banners = []
            
            banners = Banner.objects.filter(is_active=True)\
                .select_related('internal_page', 'offer', 'task')\
                .order_by('-priority')
            
            for banner in banners:
                status = BannerService._get_banner_status(banner, now)
                active_banners.append({
                    'id': banner.id,
                    'name': banner.name,
                    'type': banner.banner_type,
                    'position': banner.position,
                    'status': status,
                    'impressions': banner.impression_count,
                    'clicks': banner.click_count,
                    'remaining_impressions': max(0, banner.max_impressions - banner.impression_count) if banner.max_impressions > 0 else 'unlimited',
                    'remaining_clicks': max(0, banner.max_clicks - banner.click_count) if banner.max_clicks > 0 else 'unlimited',
                    'end_date': banner.end_date
                })
            
            return active_banners
            
        except Exception as e:
            logger.error(f"Error getting current active banners: {str(e)}")
            return []
    
    @staticmethod
    def _get_banner_status(banner: Banner, now: datetime) -> str:
        """
        Get current status of banner
        
        Args:
            banner: Banner object
            now: Current datetime
            
        Returns:
            Status string
        """
        if not banner.is_active:
            return 'inactive'
        
        if now < banner.start_date:
            return 'scheduled'
        
        if banner.end_date and now > banner.end_date:
            return 'expired'
        
        if banner.max_impressions > 0 and banner.impression_count >= banner.max_impressions:
            return 'impressions_limit_reached'
        
        if banner.max_clicks > 0 and banner.click_count >= banner.max_clicks:
            return 'clicks_limit_reached'
        
        return 'active'
    
    @staticmethod
    def generate_banner_report(
        banner_ids: Optional[List[int]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        report_type: str = 'performance'
    ) -> Dict[str, Any]:
        """
        Generate detailed banner report
        
        Args:
            banner_ids: List of banner IDs to include
            start_date: Report start date
            end_date: Report end date
            report_type: Type of report ('performance', 'financial', 'audience')
            
        Returns:
            Dictionary with report data
        """
        try:
            if not start_date:
                start_date = timezone.now() - timedelta(days=30)
            if not end_date:
                end_date = timezone.now()
            
            # Get banners
            if banner_ids:
                banners = Banner.objects.filter(id__in=banner_ids)
            else:
                banners = Banner.objects.filter(
                    created_at__range=(start_date, end_date)
                )
            
            report_data = {
                'report_type': report_type,
                'period': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'banners_count': banners.count(),
                'generated_at': timezone.now(),
                'data': []
            }
            
            for banner in banners.select_related('internal_page', 'offer', 'task'):
                banner_data = {
                    'banner_id': banner.id,
                    'banner_name': banner.name,
                    'banner_type': banner.banner_type,
                    'position': banner.position,
                    'status': banner.is_active_now()
                }
                
                if report_type == 'performance':
                    stats = BannerService.get_banner_statistics(banner, start_date, end_date)
                    banner_data.update(stats['overview'])
                
                elif report_type == 'financial':
                    clicks = BannerClick.objects.filter(
                        banner=banner,
                        created_at__range=(start_date, end_date)
                    )
                    
                    total_revenue = clicks.aggregate(
                        total=Sum('conversion_value')
                    )['total'] or 0
                    
                    banner_data.update({
                        'total_revenue': float(total_revenue),
                        'click_count': clicks.count(),
                        'average_revenue_per_click': float(total_revenue / clicks.count()) if clicks.count() > 0 else 0
                    })
                
                elif report_type == 'audience':
                    impressions = BannerImpression.objects.filter(
                        banner=banner,
                        created_at__range=(start_date, end_date)
                    )
                    
                    # Audience demographics
                    unique_users = impressions.values('user').distinct().count()
                    user_countries = impressions.values('user__country')\
                        .annotate(count=Count('id'))\
                        .order_by('-count')[:10]
                    
                    banner_data.update({
                        'unique_users': unique_users,
                        'top_countries': list(user_countries)
                    })
                
                report_data['data'].append(banner_data)
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating banner report: {str(e)}")
            return {}
    
    @staticmethod
    def create_banner_from_template(
        template_name: str,
        data: Dict[str, Any],
        user: User
    ) -> Optional[Banner]:
        """
        Create banner from template
        
        Args:
            template_name: Template to use
            data: Banner data
            user: User creating banner
            
        Returns:
            Created Banner object or None
        """
        try:
            templates = {
                'hero_banner': {
                    'banner_type': 'hero',
                    'position': 'top',
                    'priority': 10,
                    'display_frequency': 1
                },
                'sidebar_ad': {
                    'banner_type': 'sidebar',
                    'position': 'right',
                    'priority': 5,
                    'display_frequency': 3
                },
                'popup_offer': {
                    'banner_type': 'popup',
                    'position': 'center',
                    'priority': 8,
                    'display_frequency': 5
                },
                'notification': {
                    'banner_type': 'notification',
                    'position': 'bottom',
                    'priority': 7,
                    'display_frequency': 2
                }
            }
            
            if template_name not in templates:
                raise ValueError(f"Unknown template: {template_name}")
            
            template = templates[template_name]
            
            # Merge template with provided data
            banner_data = {**template, **data}
            
            # Set default values
            if 'start_date' not in banner_data:
                banner_data['start_date'] = timezone.now()
            
            if 'is_active' not in banner_data:
                banner_data['is_active'] = True
            
            # Create banner
            banner = Banner.objects.create(**banner_data)
            
            logger.info(f"Created banner {banner.id} from template {template_name} by user {user.id}")
            return banner
            
        except Exception as e:
            logger.error(f"Error creating banner from template: {str(e)}")
            return None
    
    @staticmethod
    def deactivate_expired_banners() -> Tuple[int, int]:
        """
        Deactivate banners that have expired
        
        Returns:
            Tuple of (deactivated_count, total_expired)
        """
        try:
            now = timezone.now()
            
            # Find expired banners
            expired_banners = Banner.objects.filter(
                is_active=True,
                end_date__lt=now
            )
            
            total_expired = expired_banners.count()
            deactivated_count = expired_banners.update(is_active=False)
            
            if deactivated_count > 0:
                logger.info(f"Deactivated {deactivated_count} expired banners")
            
            return deactivated_count, total_expired
            
        except Exception as e:
            logger.error(f"Error deactivating expired banners: {str(e)}")
            return 0, 0
    
    @staticmethod
    def cleanup_old_logs(days: int = 90) -> Tuple[int, int]:
        """
        Clean up old banner logs
        
        Args:
            days: Delete logs older than this many days
            
        Returns:
            Tuple of (impressions_deleted, clicks_deleted)
        """
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Delete old impressions
            impressions_deleted, _ = BannerImpression.objects.filter(
                created_at__lt=cutoff_date
            ).delete()
            
            # Delete old clicks
            clicks_deleted, _ = BannerClick.objects.filter(
                created_at__lt=cutoff_date
            ).delete()
            
            # Delete old rewards
            rewards_deleted, _ = BannerReward.objects.filter(
                created_at__lt=cutoff_date
            ).delete()
            
            logger.info(f"Cleaned up {impressions_deleted} impressions, {clicks_deleted} clicks, {rewards_deleted} rewards older than {days} days")
            return impressions_deleted, clicks_deleted
            
        except Exception as e:
            logger.error(f"Error cleaning up old banner logs: {str(e)}")
            return 0, 0