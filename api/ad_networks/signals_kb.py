"""
api/ad_networks/signals_kb.py
Knowledge base signals for ad networks module
SaaS-ready with tenant support
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional

from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
from django.dispatch import Signal, receiver
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction

from .models import (
    AdNetwork, Offer, OfferCategory, UserOfferEngagement,
    OfferConversion, OfferReward, UserWallet, OfferClick,
    OfferTag, OfferTagging, NetworkHealthCheck
)
from .choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus
)
from .constants import FRAUD_SCORE_THRESHOLD, CACHE_TIMEOUTS
from .helpers import get_cache_key

logger = logging.getLogger(__name__)
User = get_user_model()


# ==================== CUSTOM SIGNALS ====================

# Knowledge base signals
kb_article_created = Signal()
kb_article_updated = Signal()
kb_article_deleted = Signal()
kb_article_viewed = Signal()

kb_category_created = Signal()
kb_category_updated = Signal()
kb_category_deleted = Signal()

kb_search_performed = Signal()
kb_feedback_submitted = Signal()

kb_helpful_vote = Signal()
kb_not_helpful_vote = Signal()

kb_related_articles_requested = Signal()
kb_popular_articles_updated = Signal()


# ==================== KNOWLEDGE BASE MODELS ====================

class KBArticle:
    """Knowledge Base Article (for signal handling)"""
    
    def __init__(self, id: int = None, title: str = '', content: str = '',
                 category_id: int = None, tenant_id: str = 'default',
                 view_count: int = 0, helpful_count: int = 0,
                 not_helpful_count: int = 0, is_published: bool = True,
                 created_at: datetime = None, updated_at: datetime = None):
        self.id = id
        self.title = title
        self.content = content
        self.category_id = category_id
        self.tenant_id = tenant_id
        self.view_count = view_count
        self.helpful_count = helpful_count
        self.not_helpful_count = not_helpful_count
        self.is_published = is_published
        self.created_at = created_at or timezone.now()
        self.updated_at = updated_at or timezone.now()


class KBCategory:
    """Knowledge Base Category (for signal handling)"""
    
    def __init__(self, id: int = None, name: str = '', description: str = '',
                 tenant_id: str = 'default', parent_id: int = None,
                 article_count: int = 0, is_active: bool = True,
                 created_at: datetime = None, updated_at: datetime = None):
        self.id = id
        self.name = name
        self.description = description
        self.tenant_id = tenant_id
        self.parent_id = parent_id
        self.article_count = article_count
        self.is_active = is_active
        self.created_at = created_at or timezone.now()
        self.updated_at = updated_at or timezone.now()


class KBSearchLog:
    """Knowledge Base Search Log (for signal handling)"""
    
    def __init__(self, id: int = None, query: str = '', user_id: int = None,
                 tenant_id: str = 'default', results_count: int = 0,
                 clicked_article_id: int = None, created_at: datetime = None):
        self.id = id
        self.query = query
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.results_count = results_count
        self.clicked_article_id = clicked_article_id
        self.created_at = created_at or timezone.now()


class KBFeedback:
    """Knowledge Base Feedback (for signal handling)"""
    
    def __init__(self, id: int = None, article_id: int = None, user_id: int = None,
                 tenant_id: str = 'default', feedback_type: str = '',
                 rating: int = None, comment: str = '', is_helpful: bool = None,
                 created_at: datetime = None):
        self.id = id
        self.article_id = article_id
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.feedback_type = feedback_type
        self.rating = rating
        self.comment = comment
        self.is_helpful = is_helpful
        self.created_at = created_at or timezone.now()


# ==================== KNOWLEDGE BASE SIGNAL RECEIVERS ====================

@receiver(kb_article_created)
def handle_kb_article_created(sender, instance: KBArticle, **kwargs):
    """
    Handle knowledge base article creation
    """
    try:
        logger.info(f"KB article created: {instance.title} (ID: {instance.id})")
        
        # Update category article count
        if instance.category_id:
            update_category_article_count(instance.category_id, instance.tenant_id)
        
        # Invalidate cache
        invalidate_kb_cache(instance.tenant_id)
        
        # Send notification to admins
        notify_admins_new_kb_article(instance)
        
    except Exception as e:
        logger.error(f"Error handling KB article creation: {str(e)}")


@receiver(kb_article_updated)
def handle_kb_article_updated(sender, instance: KBArticle, **kwargs):
    """
    Handle knowledge base article update
    """
    try:
        logger.info(f"KB article updated: {instance.title} (ID: {instance.id})")
        
        # Invalidate cache
        invalidate_kb_cache(instance.tenant_id)
        
        # Update search index
        update_kb_search_index(instance)
        
        # Log update for analytics
        log_kb_article_update(instance)
        
    except Exception as e:
        logger.error(f"Error handling KB article update: {str(e)}")


@receiver(kb_article_deleted)
def handle_kb_article_deleted(sender, instance: KBArticle, **kwargs):
    """
    Handle knowledge base article deletion
    """
    try:
        logger.info(f"KB article deleted: {instance.title} (ID: {instance.id})")
        
        # Update category article count
        if instance.category_id:
            update_category_article_count(instance.category_id, instance.tenant_id)
        
        # Invalidate cache
        invalidate_kb_cache(instance.tenant_id)
        
        # Remove from search index
        remove_from_kb_search_index(instance.id)
        
        # Log deletion for analytics
        log_kb_article_deletion(instance)
        
    except Exception as e:
        logger.error(f"Error handling KB article deletion: {str(e)}")


@receiver(kb_article_viewed)
def handle_kb_article_viewed(sender, instance: KBArticle, user_id: int = None, **kwargs):
    """
    Handle knowledge base article view
    """
    try:
        logger.info(f"KB article viewed: {instance.title} (ID: {instance.id})")
        
        # Update view count
        update_article_view_count(instance.id, instance.tenant_id)
        
        # Log user activity
        if user_id:
            log_user_kb_activity(user_id, 'view', instance.id)
        
        # Update popular articles cache
        update_popular_articles_cache(instance.tenant_id)
        
    except Exception as e:
        logger.error(f"Error handling KB article view: {str(e)}")


@receiver(kb_category_created)
def handle_kb_category_created(sender, instance: KBCategory, **kwargs):
    """
    Handle knowledge base category creation
    """
    try:
        logger.info(f"KB category created: {instance.name} (ID: {instance.id})")
        
        # Invalidate cache
        invalidate_kb_cache(instance.tenant_id)
        
        # Update category hierarchy cache
        update_category_hierarchy_cache(instance.tenant_id)
        
    except Exception as e:
        logger.error(f"Error handling KB category creation: {str(e)}")


@receiver(kb_category_updated)
def handle_kb_category_updated(sender, instance: KBCategory, **kwargs):
    """
    Handle knowledge base category update
    """
    try:
        logger.info(f"KB category updated: {instance.name} (ID: {instance.id})")
        
        # Invalidate cache
        invalidate_kb_cache(instance.tenant_id)
        
        # Update category hierarchy cache
        update_category_hierarchy_cache(instance.tenant_id)
        
    except Exception as e:
        logger.error(f"Error handling KB category update: {str(e)}")


@receiver(kb_category_deleted)
def handle_kb_category_deleted(sender, instance: KBCategory, **kwargs):
    """
    Handle knowledge base category deletion
    """
    try:
        logger.info(f"KB category deleted: {instance.name} (ID: {instance.id})")
        
        # Invalidate cache
        invalidate_kb_cache(instance.tenant_id)
        
        # Update category hierarchy cache
        update_category_hierarchy_cache(instance.tenant_id)
        
    except Exception as e:
        logger.error(f"Error handling KB category deletion: {str(e)}")


@receiver(kb_search_performed)
def handle_kb_search_performed(sender, query: str, results_count: int,
                              user_id: int = None, tenant_id: str = 'default', **kwargs):
    """
    Handle knowledge base search
    """
    try:
        logger.info(f"KB search performed: '{query}' ({results_count} results)")
        
        # Log search for analytics
        log_kb_search(query, results_count, user_id, tenant_id)
        
        # Update search suggestions
        update_search_suggestions(query, tenant_id)
        
        # Update popular searches cache
        update_popular_searches_cache(tenant_id)
        
    except Exception as e:
        logger.error(f"Error handling KB search: {str(e)}")


@receiver(kb_feedback_submitted)
def handle_kb_feedback_submitted(sender, instance: KBFeedback, **kwargs):
    """
    Handle knowledge base feedback submission
    """
    try:
        logger.info(f"KB feedback submitted: Article ID {instance.article_id}, Type: {instance.feedback_type}")
        
        # Update article feedback counts
        update_article_feedback_counts(instance.article_id, instance.tenant_id)
        
        # Invalidate article cache
        invalidate_article_cache(instance.article_id, instance.tenant_id)
        
        # Send notification to content team
        notify_content_team_feedback(instance)
        
    except Exception as e:
        logger.error(f"Error handling KB feedback submission: {str(e)}")


@receiver(kb_helpful_vote)
def handle_kb_helpful_vote(sender, article_id: int, user_id: int, tenant_id: str = 'default', **kwargs):
    """
    Handle helpful vote on KB article
    """
    try:
        logger.info(f"KB helpful vote: Article ID {article_id}, User ID {user_id}")
        
        # Update helpful count
        increment_article_helpful_count(article_id, tenant_id)
        
        # Update article quality score
        update_article_quality_score(article_id, tenant_id)
        
        # Log user activity
        log_user_kb_activity(user_id, 'helpful_vote', article_id)
        
    except Exception as e:
        logger.error(f"Error handling KB helpful vote: {str(e)}")


@receiver(kb_not_helpful_vote)
def handle_kb_not_helpful_vote(sender, article_id: int, user_id: int, tenant_id: str = 'default', **kwargs):
    """
    Handle not helpful vote on KB article
    """
    try:
        logger.info(f"KB not helpful vote: Article ID {article_id}, User ID {user_id}")
        
        # Update not helpful count
        increment_article_not_helpful_count(article_id, tenant_id)
        
        # Update article quality score
        update_article_quality_score(article_id, tenant_id)
        
        # Log user activity
        log_user_kb_activity(user_id, 'not_helpful_vote', article_id)
        
        # Flag for content review if many not helpful votes
        check_article_for_review(article_id, tenant_id)
        
    except Exception as e:
        logger.error(f"Error handling KB not helpful vote: {str(e)}")


@receiver(kb_related_articles_requested)
def handle_kb_related_articles_requested(sender, article_id: int, tenant_id: str = 'default', **kwargs):
    """
    Handle request for related articles
    """
    try:
        logger.info(f"Related articles requested: Article ID {article_id}")
        
        # Cache related articles
        cache_related_articles(article_id, tenant_id)
        
        # Log analytics
        log_related_articles_request(article_id, tenant_id)
        
    except Exception as e:
        logger.error(f"Error handling related articles request: {str(e)}")


@receiver(kb_popular_articles_updated)
def handle_kb_popular_articles_updated(sender, tenant_id: str = 'default', **kwargs):
    """
    Handle popular articles cache update
    """
    try:
        logger.info(f"Popular articles cache updated: Tenant {tenant_id}")
        
        # Update popular articles cache
        update_popular_articles_cache(tenant_id)
        
    except Exception as e:
        logger.error(f"Error handling popular articles update: {str(e)}")


# ==================== KNOWLEDGE BASE HELPER FUNCTIONS ====================

def update_category_article_count(category_id: int, tenant_id: str):
    """Update article count for category"""
    try:
        # This would typically update the database
        # For now, just log the action
        logger.debug(f"Updating article count for category {category_id}")
    except Exception as e:
        logger.error(f"Error updating category article count: {str(e)}")


def invalidate_kb_cache(tenant_id: str):
    """Invalidate knowledge base cache"""
    try:
        # Clear all KB-related cache keys
        patterns = [
            f"kb_*_{tenant_id}",
            f"kb_article_*_{tenant_id}",
            f"kb_category_*_{tenant_id}",
            f"kb_search_*_{tenant_id}",
        ]
        
        for pattern in patterns:
            # This would use cache.delete_pattern in production
            logger.debug(f"Invalidating cache pattern: {pattern}")
            
    except Exception as e:
        logger.error(f"Error invalidating KB cache: {str(e)}")


def notify_admins_new_kb_article(article: KBArticle):
    """Notify admins about new KB article"""
    try:
        # This would send notifications to admins
        logger.info(f"Notifying admins about new KB article: {article.title}")
    except Exception as e:
        logger.error(f"Error notifying admins: {str(e)}")


def update_kb_search_index(article: KBArticle):
    """Update search index for KB article"""
    try:
        # This would update Elasticsearch or similar
        logger.debug(f"Updating search index for article {article.id}")
    except Exception as e:
        logger.error(f"Error updating search index: {str(e)}")


def log_kb_article_update(article: KBArticle):
    """Log KB article update for analytics"""
    try:
        # This would log to analytics database
        logger.debug(f"Logging KB article update: {article.id}")
    except Exception as e:
        logger.error(f"Error logging article update: {str(e)}")


def remove_from_kb_search_index(article_id: int):
    """Remove KB article from search index"""
    try:
        # This would remove from Elasticsearch or similar
        logger.debug(f"Removing article {article_id} from search index")
    except Exception as e:
        logger.error(f"Error removing from search index: {str(e)}")


def log_kb_article_deletion(article: KBArticle):
    """Log KB article deletion for analytics"""
    try:
        # This would log to analytics database
        logger.debug(f"Logging KB article deletion: {article.id}")
    except Exception as e:
        logger.error(f"Error logging article deletion: {str(e)}")


def update_article_view_count(article_id: int, tenant_id: str):
    """Update view count for article"""
    try:
        cache_key = get_cache_key('kb_article_views', article_id, tenant_id)
        current_views = cache.get(cache_key, 0)
        cache.set(cache_key, current_views + 1, timeout=3600)
    except Exception as e:
        logger.error(f"Error updating view count: {str(e)}")


def log_user_kb_activity(user_id: int, activity_type: str, article_id: int):
    """Log user KB activity"""
    try:
        # This would log to user activity database
        logger.debug(f"Logging user KB activity: User {user_id}, {activity_type}, Article {article_id}")
    except Exception as e:
        logger.error(f"Error logging user activity: {str(e)}")


def update_popular_articles_cache(tenant_id: str):
    """Update popular articles cache"""
    try:
        cache_key = get_cache_key('kb_popular_articles', tenant_id)
        # This would fetch popular articles from database
        cache.set(cache_key, [], timeout=1800)
    except Exception as e:
        logger.error(f"Error updating popular articles cache: {str(e)}")


def update_category_hierarchy_cache(tenant_id: str):
    """Update category hierarchy cache"""
    try:
        cache_key = get_cache_key('kb_category_hierarchy', tenant_id)
        # This would fetch category hierarchy from database
        cache.set(cache_key, [], timeout=3600)
    except Exception as e:
        logger.error(f"Error updating category hierarchy cache: {str(e)}")


def log_kb_search(query: str, results_count: int, user_id: int, tenant_id: str):
    """Log KB search for analytics"""
    try:
        # This would log to analytics database
        logger.debug(f"Logging KB search: '{query}', {results_count} results, User {user_id}")
    except Exception as e:
        logger.error(f"Error logging KB search: {str(e)}")


def update_search_suggestions(query: str, tenant_id: str):
    """Update search suggestions"""
    try:
        cache_key = get_cache_key('kb_search_suggestions', tenant_id)
        # This would update suggestions based on query
        logger.debug(f"Updating search suggestions for: '{query}'")
    except Exception as e:
        logger.error(f"Error updating search suggestions: {str(e)}")


def update_popular_searches_cache(tenant_id: str):
    """Update popular searches cache"""
    try:
        cache_key = get_cache_key('kb_popular_searches', tenant_id)
        # This would fetch popular searches from database
        cache.set(cache_key, [], timeout=1800)
    except Exception as e:
        logger.error(f"Error updating popular searches cache: {str(e)}")


def update_article_feedback_counts(article_id: int, tenant_id: str):
    """Update feedback counts for article"""
    try:
        # This would update database counts
        logger.debug(f"Updating feedback counts for article {article_id}")
    except Exception as e:
        logger.error(f"Error updating feedback counts: {str(e)}")


def invalidate_article_cache(article_id: int, tenant_id: str):
    """Invalidate specific article cache"""
    try:
        cache_keys = [
            get_cache_key('kb_article', article_id, tenant_id),
            get_cache_key('kb_article_views', article_id, tenant_id),
            get_cache_key('kb_article_feedback', article_id, tenant_id),
        ]
        
        for key in cache_keys:
            cache.delete(key)
            
    except Exception as e:
        logger.error(f"Error invalidating article cache: {str(e)}")


def notify_content_team_feedback(feedback: KBFeedback):
    """Notify content team about feedback"""
    try:
        # This would send notifications to content team
        logger.info(f"Notifying content team about feedback: Article {feedback.article_id}")
    except Exception as e:
        logger.error(f"Error notifying content team: {str(e)}")


def increment_article_helpful_count(article_id: int, tenant_id: str):
    """Increment helpful count for article"""
    try:
        cache_key = get_cache_key('kb_article_helpful', article_id, tenant_id)
        current_count = cache.get(cache_key, 0)
        cache.set(cache_key, current_count + 1, timeout=3600)
    except Exception as e:
        logger.error(f"Error incrementing helpful count: {str(e)}")


def increment_article_not_helpful_count(article_id: int, tenant_id: str):
    """Increment not helpful count for article"""
    try:
        cache_key = get_cache_key('kb_article_not_helpful', article_id, tenant_id)
        current_count = cache.get(cache_key, 0)
        cache.set(cache_key, current_count + 1, timeout=3600)
    except Exception as e:
        logger.error(f"Error incrementing not helpful count: {str(e)}")


def update_article_quality_score(article_id: int, tenant_id: str):
    """Update quality score for article"""
    try:
        helpful_key = get_cache_key('kb_article_helpful', article_id, tenant_id)
        not_helpful_key = get_cache_key('kb_article_not_helpful', article_id, tenant_id)
        
        helpful_count = cache.get(helpful_key, 0)
        not_helpful_count = cache.get(not_helpful_key, 0)
        
        total_votes = helpful_count + not_helpful_count
        if total_votes > 0:
            quality_score = (helpful_count / total_votes) * 100
            score_key = get_cache_key('kb_article_quality', article_id, tenant_id)
            cache.set(score_key, quality_score, timeout=3600)
            
    except Exception as e:
        logger.error(f"Error updating quality score: {str(e)}")


def check_article_for_review(article_id: int, tenant_id: str):
    """Check if article needs review based on feedback"""
    try:
        not_helpful_key = get_cache_key('kb_article_not_helpful', article_id, tenant_id)
        not_helpful_count = cache.get(not_helpful_key, 0)
        
        # Flag for review if more than 10 not helpful votes
        if not_helpful_count >= 10:
            logger.warning(f"Article {article_id} flagged for review due to {not_helpful_count} not helpful votes")
            # This would create a review task or notification
            
    except Exception as e:
        logger.error(f"Error checking article for review: {str(e)}")


def cache_related_articles(article_id: int, tenant_id: str):
    """Cache related articles for an article"""
    try:
        cache_key = get_cache_key('kb_related_articles', article_id, tenant_id)
        # This would find related articles and cache them
        cache.set(cache_key, [], timeout=1800)
    except Exception as e:
        logger.error(f"Error caching related articles: {str(e)}")


def log_related_articles_request(article_id: int, tenant_id: str):
    """Log related articles request for analytics"""
    try:
        # This would log to analytics database
        logger.debug(f"Logging related articles request: Article {article_id}")
    except Exception as e:
        logger.error(f"Error logging related articles request: {str(e)}")


# ==================== KNOWLEDGE BASE UTILITIES ====================

class KBSignalUtils:
    """Utilities for KB signal handling"""
    
    @staticmethod
    def trigger_article_viewed(article_id: int, user_id: int = None, tenant_id: str = 'default'):
        """Trigger article viewed signal"""
        # Create mock article instance
        article = KBArticle(id=article_id, tenant_id=tenant_id)
        kb_article_viewed.send(sender=KBArticle, instance=article, user_id=user_id)
    
    @staticmethod
    def trigger_search_performed(query: str, results_count: int, user_id: int = None, tenant_id: str = 'default'):
        """Trigger search performed signal"""
        kb_search_performed.send(
            sender=KBSearchLog,
            query=query,
            results_count=results_count,
            user_id=user_id,
            tenant_id=tenant_id
        )
    
    @staticmethod
    def trigger_helpful_vote(article_id: int, user_id: int, tenant_id: str = 'default'):
        """Trigger helpful vote signal"""
        kb_helpful_vote.send(
            sender=KBArticle,
            article_id=article_id,
            user_id=user_id,
            tenant_id=tenant_id
        )
    
    @staticmethod
    def trigger_not_helpful_vote(article_id: int, user_id: int, tenant_id: str = 'default'):
        """Trigger not helpful vote signal"""
        kb_not_helpful_vote.send(
            sender=KBArticle,
            article_id=article_id,
            user_id=user_id,
            tenant_id=tenant_id
        )


# ==================== EXPORTS ====================

__all__ = [
    # Signals
    'kb_article_created',
    'kb_article_updated',
    'kb_article_deleted',
    'kb_article_viewed',
    'kb_category_created',
    'kb_category_updated',
    'kb_category_deleted',
    'kb_search_performed',
    'kb_feedback_submitted',
    'kb_helpful_vote',
    'kb_not_helpful_vote',
    'kb_related_articles_requested',
    'kb_popular_articles_updated',
    
    # Models
    'KBArticle',
    'KBCategory',
    'KBSearchLog',
    'KBFeedback',
    
    # Utilities
    'KBSignalUtils',
]
