"""
Custom Manager and QuerySet classes for Offer Routing Models

This module provides optimized QuerySet methods and custom managers
for all core models to enforce business logic at the ORM level.
"""

from django.db import models
from django.utils import timezone
from django.db.models import Q, Count, Avg, F


# ─────────────────────────────────────────────────────────────────────────────
# QUERYSETS
# ─────────────────────────────────────────────────────────────────────────────

class OfferRouteQuerySet(models.QuerySet):
    """Optimized QuerySet for OfferRoute model."""
    
    def active(self):
        """Return only active routes."""
        return self.filter(is_active=True)
    
    def by_tenant(self, tenant):
        """Filter routes by tenant."""
        return self.filter(tenant=tenant)
    
    def by_priority(self, priority):
        """Filter routes by priority."""
        return self.filter(priority=priority)
    
    def with_conditions(self):
        """Prefetch related conditions to avoid N+1 queries."""
        return self.prefetch_related('conditions', 'actions')
    
    def with_stats(self):
        """Annotate with decision counts."""
        return self.annotate(
            total_decisions=Count('routing_decisions_offer', distinct=True),
            avg_response_time=Avg('routing_decisions_offer__response_time_ms')
        )
    
    def sorted_by_priority(self):
        """Order by priority (highest first)."""
        return self.order_by('-priority', 'name')


class RouteConditionQuerySet(models.QuerySet):
    """Optimized QuerySet for RouteCondition model."""
    
    def by_route(self, route):
        """Filter conditions by route."""
        return self.filter(route=route)
    
    def active_only(self):
        """Return only active conditions."""
        return self.filter(is_active=True)
    
    def by_type(self, condition_type):
        """Filter by condition type (AND, OR, NOT)."""
        return self.filter(condition_type=condition_type)


class RouteActionQuerySet(models.QuerySet):
    """Optimized QuerySet for RouteAction model."""
    
    def by_route(self, route):
        """Filter actions by route."""
        return self.filter(route=route)
    
    def by_type(self, action_type):
        """Filter by action type."""
        return self.filter(action_type=action_type)
    
    def active_only(self):
        """Return only active actions."""
        return self.filter(is_active=True)


class OfferScoreQuerySet(models.QuerySet):
    """Optimized QuerySet for OfferScore model."""
    
    def top_scores(self, limit=10):
        """Get top-ranked scores."""
        return self.order_by('-score')[:limit]
    
    def by_user_and_offer(self, user, offer):
        """Get score for specific user-offer pair."""
        return self.filter(user=user, offer=offer).first()
    
    def expired(self):
        """Get expired scores."""
        return self.filter(expires_at__lt=timezone.now())
    
    def recent(self, days=7):
        """Get scores from the last N days."""
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(created_at__gte=cutoff)


class UserOfferCapQuerySet(models.QuerySet):
    """Optimized QuerySet for UserOfferCap model."""
    
    def exhausted(self):
        """Get caps where remaining shows = 0."""
        return self.filter(shown_today__gte=F('max_shows_per_day'))
    
    def available(self):
        """Get caps with remaining shows."""
        return self.exclude(shown_today__gte=F('max_shows_per_day'))
    
    def by_user_and_offer(self, user, offer):
        """Get cap for specific user-offer pair."""
        return self.filter(user=user, offer=offer).first()
    
    def reset_required(self):
        """Get caps requiring a daily reset."""
        today = timezone.now().date()
        return self.filter(last_reset_date__lt=today)


class RoutingDecisionLogQuerySet(models.QuerySet):
    """Optimized QuerySet for RoutingDecisionLog model."""
    
    def recent(self, hours=24):
        """Get decisions from last N hours."""
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff)
    
    def successful(self):
        """Get successful routing decisions."""
        return self.filter(success=True)
    
    def by_user(self, user):
        """Get decisions for a specific user."""
        return self.filter(user=user)
    
    def by_route(self, route):
        """Get decisions for a specific route."""
        return self.filter(route=route)
    
    def by_reason(self, reason):
        """Filter by decision reason."""
        return self.filter(reason=reason)
    
    def with_performance_stats(self):
        """Annotate with performance metrics."""
        return self.annotate(
            avg_response_time=Avg('response_time_ms'),
            cache_hit_count=Count('id', filter=Q(cache_hit=True))
        )


class RoutingInsightQuerySet(models.QuerySet):
    """Optimized QuerySet for RoutingInsight model."""
    
    def actionable(self):
        """Get only actionable insights."""
        return self.filter(is_actionable=True)
    
    def critical(self):
        """Get critical severity insights."""
        return self.filter(severity='critical')
    
    def recent(self, days=7):
        """Get recent insights."""
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(created_at__gte=cutoff)


class OfferRoutingCapQuerySet(models.QuerySet):
    """Optimized QuerySet for OfferRoutingCap model."""
    
    def by_offer(self, offer):
        """Filter caps by offer."""
        return self.filter(offer=offer)
    
    def by_cap_type(self, cap_type):
        """Filter by cap type (daily, hourly, etc)."""
        return self.filter(cap_type=cap_type)
    
    def exhausted(self):
        """Get caps where current_count >= cap_value."""
        return self.filter(current_count__gte=F('cap_value'))


class RoutingABTestQuerySet(models.QuerySet):
    """Optimized QuerySet for RoutingABTest model."""
    
    def active(self):
        """Get only active tests."""
        return self.filter(is_active=True)
    
    def completed(self):
        """Get completed tests."""
        return self.filter(status='completed')
    
    def running(self):
        """Get currently running tests."""
        return self.filter(status='running')
    
    def by_tenant(self, tenant):
        """Filter tests by tenant."""
        return self.filter(tenant=tenant)
    
    def recent(self, days=30):
        """Get recent tests."""
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(created_at__gte=cutoff)


class ABTestAssignmentQuerySet(models.QuerySet):
    """Optimized QuerySet for ABTestAssignment model."""
    
    def for_test(self, test):
        """Get all assignments for a test."""
        return self.filter(test=test)
    
    def for_user(self, user):
        """Get all test assignments for a user."""
        return self.filter(user=user)
    
    def by_variant(self, variant):
        """Filter by variant (A, B, C, etc)."""
        return self.filter(variant=variant)


class NetworkPerformanceCacheQuerySet(models.QuerySet):
    """Optimized QuerySet for NetworkPerformanceCache model."""
    
    def active(self):
        """Get non-expired cache entries."""
        return self.filter(expires_at__gt=timezone.now())
    
    def expired(self):
        """Get expired cache entries."""
        return self.filter(expires_at__lte=timezone.now())
    
    def by_region(self, region):
        """Filter by geographic region."""
        return self.filter(region=region)


# ─────────────────────────────────────────────────────────────────────────────
# MANAGERS
# ─────────────────────────────────────────────────────────────────────────────

class OfferRouteManager(models.Manager):
    """Manager for OfferRoute model."""
    
    def get_queryset(self):
        """Override to return custom QuerySet."""
        return OfferRouteQuerySet(self.model, using=self._db)
    
    def active(self):
        """Return only active routes."""
        return self.get_queryset().active()
    
    def by_tenant(self, tenant):
        """Filter routes by tenant."""
        return self.get_queryset().by_tenant(tenant)
    
    def active_routes(self):
        """Get active routes ordered by priority."""
        return self.active().sorted_by_priority()
    
    def with_stats(self):
        """Get routes with decision statistics."""
        return self.get_queryset().with_stats()


class RouteConditionManager(models.Manager):
    """Manager for RouteCondition model."""
    
    def get_queryset(self):
        return RouteConditionQuerySet(self.model, using=self._db)
    
    def active(self):
        """Get only active conditions."""
        return self.get_queryset().active_only()


class RouteActionManager(models.Manager):
    """Manager for RouteAction model."""
    
    def get_queryset(self):
        return RouteActionQuerySet(self.model, using=self._db)
    
    def active(self):
        """Get only active actions."""
        return self.get_queryset().active_only()


class OfferScoreManager(models.Manager):
    """Manager for OfferScore model."""
    
    def get_queryset(self):
        return OfferScoreQuerySet(self.model, using=self._db)
    
    def top_scores(self, limit=10):
        """Get top-ranked scores."""
        return self.get_queryset().top_scores(limit)
    
    def recent_scores(self, days=7):
        """Get recent scores."""
        return self.get_queryset().recent(days)


class UserOfferCapManager(models.Manager):
    """Manager for UserOfferCap model."""
    
    def get_queryset(self):
        return UserOfferCapQuerySet(self.model, using=self._db)
    
    def exhausted(self):
        """Get exhausted caps."""
        return self.get_queryset().exhausted()
    
    def available(self):
        """Get available caps."""
        return self.get_queryset().available()


class RoutingDecisionLogManager(models.Manager):
    """Manager for RoutingDecisionLog model."""
    
    def get_queryset(self):
        return RoutingDecisionLogQuerySet(self.model, using=self._db)
    
    def recent(self, hours=24):
        """Get recent decisions."""
        return self.get_queryset().recent(hours)
    
    def successful(self):
        """Get successful decisions."""
        return self.get_queryset().successful()
    
    def by_user(self, user):
        """Get decisions for user."""
        return self.get_queryset().by_user(user)


class RoutingInsightManager(models.Manager):
    """Manager for RoutingInsight model."""
    
    def get_queryset(self):
        return RoutingInsightQuerySet(self.model, using=self._db)
    
    def actionable(self):
        """Get actionable insights."""
        return self.get_queryset().actionable()
    
    def critical(self):
        """Get critical insights."""
        return self.get_queryset().critical()


class OfferRoutingCapManager(models.Manager):
    """Manager for OfferRoutingCap model."""
    
    def get_queryset(self):
        return OfferRoutingCapQuerySet(self.model, using=self._db)
    
    def by_offer(self, offer):
        """Get caps for offer."""
        return self.get_queryset().by_offer(offer)


class RoutingABTestManager(models.Manager):
    """Manager for RoutingABTest model."""
    
    def get_queryset(self):
        return RoutingABTestQuerySet(self.model, using=self._db)
    
    def active(self):
        """Get active tests."""
        return self.get_queryset().active()
    
    def running(self):
        """Get running tests."""
        return self.get_queryset().running()
    
    def by_tenant(self, tenant):
        """Get tests for tenant."""
        return self.get_queryset().by_tenant(tenant)


class ABTestAssignmentManager(models.Manager):
    """Manager for ABTestAssignment model."""
    
    def get_queryset(self):
        return ABTestAssignmentQuerySet(self.model, using=self._db)


class NetworkPerformanceCacheManager(models.Manager):
    """Manager for NetworkPerformanceCache model."""
    
    def get_queryset(self):
        return NetworkPerformanceCacheQuerySet(self.model, using=self._db)
    
    def active(self):
        """Get active cache entries."""
        return self.get_queryset().active()
    
    def expired(self):
        """Get expired entries."""
        return self.get_queryset().expired()
