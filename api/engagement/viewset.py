# engagement/viewset.py
"""
Base viewsets for engagement system.
Provides common viewset functionality and patterns.
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone

from .permissions import IsTenantMember, IsActiveUser, IsOwnerOrReadOnly
from .decorators import engagement_endpoint, rate_limit
from .exceptions import EngagementError
from .filters import EngagementFilterBackend


class BaseEngagementViewSet(viewsets.ModelViewSet):
    """Base viewset for engagement models."""
    
    permission_classes = [IsAuthenticated, IsActiveUser, IsTenantMember]
    filter_backends = [EngagementFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    def get_queryset(self):
        """Get queryset with tenant filtering."""
        queryset = super().get_queryset()
        
        # Filter by tenant
        if hasattr(self.request.user, 'tenant') and self.request.user.tenant:
            queryset = queryset.filter(tenant=self.request.user.tenant)
        
        # Non-admin users can only see their own data
        if not self.request.user.is_staff and hasattr(queryset.model, 'user'):
            queryset = queryset.filter(user=self.request.user)
        
        return queryset
    
    def perform_create(self, serializer):
        """Perform create with user and tenant."""
        serializer.save(
            user=self.request.user,
            tenant=getattr(self.request.user, 'tenant', None)
        )
    
    def get_serializer_context(self):
        """Get serializer context with request."""
        context = super().get_serializer_context()
        context['request'] = self.request
        context['user'] = self.request.user
        return context


class ReadOnlyEngagementViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for engagement models."""
    
    permission_classes = [IsAuthenticated, IsActiveUser, IsTenantMember]
    filter_backends = [EngagementFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    def get_queryset(self):
        """Get queryset with tenant filtering."""
        queryset = super().get_queryset()
        
        # Filter by tenant
        if hasattr(self.request.user, 'tenant') and self.request.user.tenant:
            queryset = queryset.filter(tenant=self.request.user.tenant)
        
        # Non-admin users can only see their own data
        if not self.request.user.is_staff and hasattr(queryset.model, 'user'):
            queryset = queryset.filter(user=self.request.user)
        
        return queryset


class UserEngagementViewSet(BaseEngagementViewSet):
    """User-specific engagement viewset."""
    
    permission_classes = [IsAuthenticated, IsActiveUser]
    
    def get_queryset(self):
        """Get queryset for current user only."""
        queryset = super().get_queryset()
        return queryset.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Perform create with current user."""
        serializer.save(
            user=self.request.user,
            tenant=getattr(self.request.user, 'tenant', None)
        )


class AdminEngagementViewSet(BaseEngagementViewSet):
    """Admin-only engagement viewset."""
    
    permission_classes = [IsAuthenticated, IsActiveUser]
    
    def get_queryset(self):
        """Get queryset for admin users."""
        queryset = super().get_queryset()
        
        # Admin users can see all data in their tenant
        if hasattr(self.request.user, 'tenant') and self.request.user.tenant:
            queryset = queryset.filter(tenant=self.request.user.tenant)
        
        return queryset
    
    def get_permissions(self):
        """Get permissions based on action."""
        permissions = super().get_permissions()
        
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            if not self.request.user.is_staff:
                permissions.append('rest_framework.permissions.IsAdminUser')
        
        return permissions


class SuperAdminEngagementViewSet(AdminEngagementViewSet):
    """Super admin viewset with system-wide access."""
    
    def get_queryset(self):
        """Get queryset for super admin users."""
        queryset = super().get_queryset()
        
        # Super admins can see all data
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'tenant') and self.request.user.tenant:
                queryset = queryset.filter(tenant=self.request.user.tenant)
        
        return queryset
    
    def get_permissions(self):
        """Get permissions based on action."""
        permissions = super().get_permissions()
        
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            if not self.request.user.is_superuser:
                permissions.append('rest_framework.permissions.IsSuperUser')
        
        return permissions


# ── Specialized Viewsets ─────────────────────────────────────────────────────

class CheckInViewSet(UserEngagementViewSet):
    """Check-in viewset with user-specific actions."""
    
    @action(detail=False, methods=['post'])
    @engagement_endpoint
    @rate_limit('checkin', limit=1, period=86400, scope='user')
    def today(self, request):
        """Perform today's check-in."""
        try:
            from .services.checkin_service import CheckInService
            
            result = CheckInService.process(request.user, tenant=getattr(request.user, 'tenant', None))
            
            return Response({
                'success': True,
                'data': result,
                'message': 'Check-in completed successfully'
            })
            
        except EngagementError as exc:
            return Response({
                'success': False,
                'error': exc.detail,
                'code': exc.default_code
            }, status=exc.status_code)
    
    @action(detail=False, methods=['get'])
    def streak(self, request):
        """Get current streak information."""
        try:
            from .services.checkin_service import CheckInService
            
            streak = CheckInService.get_current_streak(request.user)
            history = CheckInService.get_streak_history(request.user, days=30)
            
            return Response({
                'success': True,
                'data': {
                    'current_streak': streak,
                    'history': history
                }
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def calendar(self, request):
        """Get check-in calendar for current month."""
        try:
            from .services.checkin_service import CheckInService
            from datetime import date, timedelta
            
            today = date.today()
            start_date = today.replace(day=1)
            end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            calendar_data = CheckInService.get_calendar_data(
                request.user, 
                start_date, 
                end_date,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'data': calendar_data
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SpinWheelViewSet(UserEngagementViewSet):
    """Spin wheel viewset with user-specific actions."""
    
    @action(detail=False, methods=['post'])
    @engagement_endpoint
    @rate_limit('spin', limit=10, period=3600, scope='user')
    def spin(self, request):
        """Perform a spin."""
        try:
            from .services.spin_service import SpinService
            
            use_boost = request.data.get('use_boost', False)
            result = SpinService.spin(request.user, use_boost=use_boost)
            
            return Response({
                'success': True,
                'data': result,
                'message': 'Spin completed successfully'
            })
            
        except EngagementError as exc:
            return Response({
                'success': False,
                'error': exc.detail,
                'code': exc.default_code
            }, status=exc.status_code)
    
    @action(detail=False, methods=['get'])
    def remaining(self, request):
        """Get remaining spins for today."""
        try:
            from .services.spin_service import SpinService
            
            remaining = SpinService.get_remaining_spins(request.user)
            
            return Response({
                'success': True,
                'data': {
                    'remaining_spins': remaining
                }
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get spin history."""
        try:
            from .services.spin_service import SpinService
            
            limit = int(request.query_params.get('limit', 50))
            history = SpinService.get_spin_history(request.user, limit=limit)
            
            return Response({
                'success': True,
                'data': history
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class QuestViewSet(UserEngagementViewSet):
    """Quest viewset with user-specific actions."""
    
    @action(detail=True, methods=['post'])
    @engagement_endpoint
    def complete(self, request, pk=None):
        """Complete a quest."""
        try:
            from .services.quest_service import QuestService
            
            quest = self.get_object()
            progress = request.data.get('progress', 0)
            
            result = QuestService.complete_quest(
                request.user, 
                quest, 
                progress,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'data': result,
                'message': 'Quest completed successfully'
            })
            
        except EngagementError as exc:
            return Response({
                'success': False,
                'error': exc.detail,
                'code': exc.default_code
            }, status=exc.status_code)
    
    @action(detail=False, methods=['get'])
    def available(self, request):
        """Get available quests."""
        try:
            from .services.quest_service import QuestService
            
            quest_type = request.query_params.get('type', 'daily')
            quests = QuestService.get_available_quests(
                request.user, 
                quest_type=quest_type,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'data': quests
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def progress(self, request):
        """Get quest progress summary."""
        try:
            from .services.quest_service import QuestService
            
            progress = QuestService.get_progress_summary(
                request.user,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'data': progress
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AchievementViewSet(ReadOnlyEngagementViewSet):
    """Achievement viewset with progress tracking."""
    
    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Get achievement progress."""
        try:
            from .services.achievement_service import AchievementService
            
            achievement = self.get_object()
            progress = AchievementService.get_progress(
                request.user,
                achievement,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'data': progress
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def unlocked(self, request):
        """Get unlocked achievements."""
        try:
            from .services.achievement_service import AchievementService
            
            achievements = AchievementService.get_unlocked_achievements(
                request.user,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'data': achievements
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get achievement statistics."""
        try:
            from .services.achievement_service import AchievementService
            
            stats = AchievementService.get_stats(
                request.user,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'data': stats
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ShopViewSet(ReadOnlyEngagementViewSet):
    """Shop viewset with purchase functionality."""
    
    @action(detail=True, methods=['post'])
    @engagement_endpoint
    def purchase(self, request, pk=None):
        """Purchase an item."""
        try:
            from .services.shop_service import ShopService
            
            item = self.get_object()
            quantity = request.data.get('quantity', 1)
            
            result = ShopService.purchase(
                request.user,
                item,
                quantity,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'data': result,
                'message': 'Purchase completed successfully'
            })
            
        except EngagementError as exc:
            return Response({
                'success': False,
                'error': exc.detail,
                'code': exc.default_code
            }, status=exc.status_code)
    
    @action(detail=False, methods=['get'])
    def inventory(self, request):
        """Get user inventory."""
        try:
            from .services.shop_service import ShopService
            
            inventory = ShopService.get_inventory(
                request.user,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'data': inventory
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def balance(self, request):
        """Get user coin balance."""
        try:
            from .services.coin_service import CoinService
            
            balance = CoinService.get_balance(request.user)
            
            return Response({
                'success': True,
                'data': {
                    'balance': float(balance)
                }
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LeaderboardViewSet(ReadOnlyEngagementViewSet):
    """Leaderboard viewset with ranking information."""
    
    @action(detail=False, methods=['get'])
    def top_players(self, request):
        """Get top players."""
        try:
            from .services.leaderboard_service import LeaderboardService
            
            period = request.query_params.get('period', 'daily')
            limit = int(request.query_params.get('limit', 100))
            
            leaderboard = LeaderboardService.get_top_players(
                period=period,
                limit=limit,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'data': leaderboard
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def user_rank(self, request):
        """Get user's rank."""
        try:
            from .services.leaderboard_service import LeaderboardService
            
            period = request.query_params.get('period', 'daily')
            rank = LeaderboardService.get_user_rank(
                request.user,
                period=period,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'data': {
                    'rank': rank
                }
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def around_user(self, request):
        """Get players around user's rank."""
        try:
            from .services.leaderboard_service import LeaderboardService
            
            period = request.query_params.get('period', 'daily')
            count = int(request.query_params.get('count', 5))
            
            around_players = LeaderboardService.get_around_user(
                request.user,
                period=period,
                count=count,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'data': around_players
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Utility Viewsets ─────────────────────────────────────────────────────

class StatsViewSet(ReadOnlyEngagementViewSet):
    """Statistics viewset for analytics."""
    
    @action(detail=False, methods=['get'])
    def user_stats(self, request):
        """Get user statistics."""
        try:
            from .services.analytics_service import AnalyticsService
            
            stats = AnalyticsService.get_user_stats(
                request.user,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'data': stats
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def platform_stats(self, request):
        """Get platform statistics (admin only)."""
        if not request.user.is_staff:
            return Response({
                'success': False,
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from .services.analytics_service import AnalyticsService
            
            period = request.query_params.get('period', 'daily')
            stats = AnalyticsService.get_platform_stats(
                period=period,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'data': stats
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotificationViewSet(UserEngagementViewSet):
    """Notification viewset with user actions."""
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark notification as read."""
        try:
            from .services.notification_service import NotificationService
            
            notification = self.get_object()
            NotificationService.mark_as_read(
                request.user,
                notification.id,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'message': 'Notification marked as read'
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read."""
        try:
            from .services.notification_service import NotificationService
            
            NotificationService.mark_all_as_read(
                request.user,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'message': 'All notifications marked as read'
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get unread notifications count."""
        try:
            from .services.notification_service import NotificationService
            
            count = NotificationService.unread_count(
                request.user,
                tenant=getattr(request.user, 'tenant', None)
            )
            
            return Response({
                'success': True,
                'data': {
                    'unread_count': count
                }
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Mixin Classes ─────────────────────────────────────────────────────────

class TenantAwareMixin:
    """Mixin for tenant-aware viewsets."""
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        if hasattr(self.request.user, 'tenant') and self.request.user.tenant:
            queryset = queryset.filter(tenant=self.request.user.tenant)
        
        return queryset


class UserAwareMixin:
    """Mixin for user-aware viewsets."""
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        if not self.request.user.is_staff and hasattr(queryset.model, 'user'):
            queryset = queryset.filter(user=self.request.user)
        
        return queryset


class DateRangeMixin:
    """Mixin for date range filtering."""
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        return queryset


class StatsMixin:
    """Mixin for statistics endpoints."""
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get summary statistics."""
        try:
            queryset = self.get_queryset()
            
            stats = queryset.aggregate(
                total=Count('id'),
                avg_value=Avg('value') if hasattr(queryset.model, 'value') else 0,
                sum_value=Sum('value') if hasattr(queryset.model, 'value') else 0
            )
            
            return Response({
                'success': True,
                'data': stats
            })
            
        except Exception as exc:
            return Response({
                'success': False,
                'error': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
