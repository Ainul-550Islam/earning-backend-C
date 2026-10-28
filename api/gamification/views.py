"""
Gamification Views — Django views for gamification module.
Enhanced with integration system monitoring, audit logging, and security checks.

This module provides Django views for HTML pages, health-check endpoints,
and other non-ViewSet views for the gamification module.
"""

from __future__ import annotations

import logging
import hashlib
import json
from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.generic import TemplateView, View
from django.views.decorators.http import require_http_methods
from django.contrib.auth.mixins import LoginRequiredMixin

from api.gamification.models import ContestCycle, UserAchievement, LeaderboardSnapshot
from api.gamification.services import (
    ContestService as ContestCycleService,
)
try:
    from api.gamification.services import AchievementService
except ImportError:
    AchievementService = None
try:
    from api.gamification.services import LeaderboardService
except ImportError:
    LeaderboardService = None
from api.gamification.mixins import GamificationContextMixin, CacheMixin

# Import integration system components
from api.gamification.INTEGRATION_SYSTEM.integ_audit_logs import audit_logger
from api.gamification.INTEGRATION_SYSTEM.performance_monitor import performance_monitor
from api.gamification.INTEGRATION_SYSTEM.health_check import health_manager
from api.gamification.INTEGRATION_SYSTEM.auth_bridge import auth_bridge

User = get_user_model()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Template Views
# ---------------------------------------------------------------------------

class GamificationDashboardView(LoginRequiredMixin, GamificationContextMixin, TemplateView):
    """Main gamification dashboard view. Enhanced with integration system monitoring."""
    
    template_name = "gamification/dashboard.html"
    
    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Get context data for the dashboard with integration system monitoring."""
        start_time = timezone.now()
        context = super().get_context_data(**kwargs)
        
        # Add integration context
        integration_context = getattr(self.request, 'integration_context', {})
        context['integration_context'] = integration_context
        
        try:
            # Log dashboard view access
            audit_logger.log_audit(
                action=audit_logger.AuditAction.READ,
                description=f"User accessed gamification dashboard: {self.request.user.username}",
                resource_type=audit_logger.ResourceType.INTEGRATION,
                user_id=str(self.request.user.id),
                details={
                    "request_id": integration_context.get("request_id"),
                    "ip_address": integration_context.get("ip_address"),
                    "user_agent": integration_context.get("user_agent"),
                    "vpn_detected": integration_context.get("vpn_detected", False)
                }
            )
            
            # Add gamification context
            gamification_context = self.get_gamification_context()
            context.update(gamification_context)
            
            # Get active contest with health check
            try:
                active_contest = ContestCycle.objects.get_current()
                if active_contest:
                    context['active_contest'] = active_contest
                    
                    # Get health status for active contest
                    health_status = health_manager.check_resource_health(
                        resource_type="contest_cycle",
                        resource_id=str(active_contest.id)
                    )
                    context['contest_health'] = health_status.to_dict() if health_status else None
                    
                    # Get leaderboard for active contest
                    leaderboard_service = LeaderboardService()
                    leaderboard = leaderboard_service.get_leaderboard_for_cycle(
                        active_contest.id, limit=10
                    )
                    context['leaderboard'] = leaderboard[:10]
                    
                    # Record metrics
                    performance_monitor.record_metric("dashboard_active_contest_loaded", 1.0)
                    performance_monitor.record_metric("dashboard_leaderboard_entries", len(leaderboard))
                    
            except Exception as e:
                logger.error(f"Error getting active contest: {e}")
                context['active_contest'] = None
                context['leaderboard'] = []
                context['contest_health'] = None
                
                # Log error
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.ERROR,
                    description=f"Failed to load active contest in dashboard: {e}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    user_id=str(self.request.user.id),
                    error=str(e)
                )
            
            # Get recent achievements with verification
            try:
                recent_achievements = UserAchievement.objects.filter(
                    user=self.request.user,
                    is_awarded=True
                ).order_by('-awarded_at')[:5]
                
                # Verify checksums for achievements
                verified_achievements = []
                for achievement in recent_achievements:
                    is_valid = achievement.verify_checksum()
                    verified_achievements.append({
                        'achievement': achievement,
                        'checksum_valid': is_valid
                    })
                
                context['recent_achievements'] = verified_achievements
                performance_monitor.record_metric("dashboard_achievements_loaded", len(recent_achievements))
                
            except Exception as e:
                logger.error(f"Error getting recent achievements: {e}")
                context['recent_achievements'] = []
                
                # Log error
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.ERROR,
                    description=f"Failed to load recent achievements in dashboard: {e}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    user_id=str(self.request.user.id),
                    error=str(e)
                )
            
            # Add user authentication context
            if self.request.user.is_authenticated:
                try:
                    auth_context = auth_bridge.get_user_context(str(self.request.user.id))
                    context['user_auth_context'] = auth_context.to_dict() if auth_context else None
                except Exception as e:
                    logger.warning(f"Failed to get user auth context: {e}")
                    context['user_auth_context'] = None
            
        except Exception as exc:
            logger.error(f"Dashboard view error: {exc}")
            audit_logger.log_audit(
                action=audit_logger.AuditAction.ERROR,
                description=f"Dashboard view failed: {exc}",
                resource_type=audit_logger.ResourceType.INTEGRATION,
                user_id=str(self.request.user.id),
                error=str(exc)
            )
        
        # Calculate and record view duration
        view_duration = (timezone.now() - start_time).total_seconds()
        performance_monitor.record_metric("dashboard_view_duration", view_duration)
        
        # Add view metadata
        context['view_metadata'] = {
            'duration': view_duration,
            'timestamp': timezone.now().isoformat(),
            'request_id': integration_context.get('request_id')
        }
        
        return context


class LeaderboardView(LoginRequiredMixin, GamificationContextMixin, TemplateView):
    """Leaderboard page view."""
    
    template_name = "gamification/leaderboard.html"
    
    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Get context data for the leaderboard."""
        context = super().get_context_data(**kwargs)
        
        # Add gamification context
        gamification_context = self.get_gamification_context()
        context.update(gamification_context)
        
        # Get contest cycles
        contests = ContestCycle.objects.filter(
            status__in=['ACTIVE', 'COMPLETED']
        ).order_by('-created_at')
        context['contests'] = contests
        
        # Get selected contest
        contest_id = self.request.GET.get('contest')
        selected_contest = None
        
        if contest_id:
            try:
                selected_contest = ContestCycle.objects.get(id=contest_id)
            except ContestCycle.DoesNotExist:
                pass
        else:
            # Default to active contest
            selected_contest = ContestCycle.objects.get_current()
        
        context['selected_contest'] = selected_contest
        
        # Get leaderboard data
        if selected_contest:
            leaderboard_service = LeaderboardService()
            leaderboard = leaderboard_service.get_leaderboard_for_cycle(
                selected_contest.id
            )
            context['leaderboard'] = leaderboard
            
            # Get user's rank
            user_rank = leaderboard_service.get_user_rank(
                self.request.user.id, selected_contest.id
            )
            context['user_rank'] = user_rank
        else:
            context['leaderboard'] = []
            context['user_rank'] = None
        
        return context


class AchievementsView(LoginRequiredMixin, GamificationContextMixin, TemplateView):
    """Achievements page view."""
    
    template_name = "gamification/achievements.html"
    
    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Get context data for achievements."""
        context = super().get_context_data(**kwargs)
        
        # Add gamification context
        gamification_context = self.get_gamification_context()
        context.update(gamification_context)
        
        # Get user achievements
        achievements = UserAchievement.objects.filter(
            user=self.request.user,
            is_awarded=True
        ).order_by('-awarded_at')
        context['achievements'] = achievements
        
        # Get achievement statistics
        achievement_service = AchievementService()
        stats = achievement_service.get_user_achievement_stats(self.request.user.id)
        context['achievement_stats'] = stats
        
        return context


class ChallengesView(LoginRequiredMixin, GamificationContextMixin, TemplateView):
    """Daily challenges page view."""
    
    template_name = "gamification/challenges.html"
    
    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Get context data for challenges."""
        context = super().get_context_data(**kwargs)
        
        # Add gamification context
        gamification_context = self.get_gamification_context()
        context.update(gamification_context)
        
        # Get today's challenges
        from api.gamification.services import ChallengeService
        challenge_service = ChallengeService()
        
        today_challenge = challenge_service.get_today_challenge()
        context['today_challenge'] = today_challenge
        
        # Get user's challenge progress
        if today_challenge:
            user_progress = challenge_service.get_user_challenge_progress(
                self.request.user.id, today_challenge.id
            )
            context['user_progress'] = user_progress
        else:
            context['user_progress'] = None
        
        # Get recent challenge history
        recent_challenges = challenge_service.get_user_challenge_history(
            self.request.user.id, limit=10
        )
        context['recent_challenges'] = recent_challenges
        
        return context


# ---------------------------------------------------------------------------
# API Views
# ---------------------------------------------------------------------------

class GamificationHealthView(View):
    """Health check endpoint for gamification module."""
    
    def get(self, request: Any) -> JsonResponse:
        """Return health status — includes INTEGRATION_SYSTEM health checks."""
        try:
            # Database connectivity
            contest_count = ContestCycle.objects.count()
            active_contest = ContestCycle.objects.get_current()

            health_data = {
                "status": "healthy",
                "timestamp": timezone.now().isoformat(),
                "database": "connected",
                "contests_count": contest_count,
                "active_contest": {
                    "id": str(active_contest.id) if active_contest else None,
                    "name": active_contest.name if active_contest else None,
                    "status": active_contest.status if active_contest else None,
                },
            }

            # INTEGRATION_SYSTEM: enriched health checks via HealthManager
            try:
                from api.gamification.INTEGRATION_SYSTEM.wiring import run_health_checks
                health_data["integration_system"] = run_health_checks()
            except Exception as integ_exc:
                health_data["integration_system"] = {"status": "skipped", "detail": str(integ_exc)}

            return JsonResponse(health_data)

        except Exception as e:
            logger.error("Health check failed: %s", e)
            return JsonResponse({
                "status": "unhealthy",
                "timestamp": timezone.now().isoformat(),
                "error": str(e),
            }, status=500)


class GamificationStatsView(LoginRequiredMixin, CacheMixin, View):
    """Get user's gamification statistics."""
    
    def get(self, request: Any) -> JsonResponse:
        """Return user statistics."""
        try:
            user_id = str(request.user.id)
            
            # Check cache first
            cache_key = f"gamification_stats:{user_id}"
            cached_data = self.get_cached_data(cache_key)
            
            if cached_data:
                return JsonResponse(cached_data)
            
            # Get statistics
            achievement_service = AchievementService()
            stats = achievement_service.get_user_achievement_stats(user_id)
            
            # Add additional stats
            stats.update({
                'user_id': user_id,
                'username': request.user.username,
                'last_updated': timezone.now().isoformat()
            })
            
            # Cache the result
            self.set_cached_data(cache_key, stats, timeout=300)  # 5 minutes
            
            return JsonResponse(stats)
            
        except Exception as e:
            logger.error(f"Error getting gamification stats: {e}")
            return JsonResponse({
                'error': 'Failed to get statistics',
                'details': str(e)
            }, status=500)


class ContestStatusView(View, CacheMixin):
    """Get current contest status."""
    
    def get(self, request: Any) -> JsonResponse:
        """Return current contest status."""
        try:
            # Check cache first
            cache_key = "current_contest_status"
            cached_data = self.get_cached_data(cache_key)
            
            if cached_data:
                return JsonResponse(cached_data)
            
            # Get current contest
            active_contest = ContestCycle.objects.get_current()
            
            if active_contest:
                contest_data = {
                    'id': str(active_contest.id),
                    'name': active_contest.name,
                    'status': active_contest.status,
                    'start_date': active_contest.start_date.isoformat(),
                    'end_date': active_contest.end_date.isoformat(),
                    'is_active': active_contest.is_active,
                    'is_expired': active_contest.is_expired,
                    'duration_days': active_contest.duration_days
                }
            else:
                contest_data = {
                    'id': None,
                    'name': None,
                    'status': 'NO_ACTIVE_CONTEST',
                    'start_date': None,
                    'end_date': None,
                    'is_active': False,
                    'is_expired': False,
                    'duration_days': None
                }
            
            # Add timestamp
            contest_data['timestamp'] = timezone.now().isoformat()
            
            # Cache the result
            self.set_cached_data(cache_key, contest_data, timeout=60)  # 1 minute
            
            return JsonResponse(contest_data)
            
        except Exception as e:
            logger.error(f"Error getting contest status: {e}")
            return JsonResponse({
                'error': 'Failed to get contest status',
                'details': str(e)
            }, status=500)


# ---------------------------------------------------------------------------
# Utility Views
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
def clear_gamification_cache(request: Any) -> JsonResponse:
    """Clear gamification cache (admin only)."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        from django.core.cache import cache
        
        # Clear specific cache keys
        cache_keys = [
            "current_contest_status",
            f"gamification_stats:{request.user.id}",
        ]
        
        cleared_count = 0
        for key in cache_keys:
            if cache.delete(key):
                cleared_count += 1
        
        return JsonResponse({
            'status': 'success',
            'cleared_keys': cleared_count,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return JsonResponse({
            'error': 'Failed to clear cache',
            'details': str(e)
        }, status=500)


def gamification_robots_txt(request: Any) -> HttpResponse:
    """Robots.txt for gamification module."""
    content = """User-agent: *
Disallow: /gamification/api/
Allow: /gamification/
"""
    return HttpResponse(content, content_type="text/plain")


# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------

def gamification_404_view(request: Any, exception: Any) -> HttpResponse:
    """Custom 404 handler for gamification module."""
    return render(request, "gamification/404.html", status=404)


def gamification_500_view(request: Any) -> HttpResponse:
    """Custom 500 handler for gamification module."""
    logger.error(f"500 error in gamification: {request.path}")
    return render(request, "gamification/500.html", status=500)


# Initialize logging
logger.info("Gamification views module initialized")
