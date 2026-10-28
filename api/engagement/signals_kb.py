# engagement/signals_kb.py
"""
Knowledge base signals for engagement system.
Provides signals for knowledge base and documentation updates.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


# ── Knowledge Base Signals ─────────────────────────────────────────────────────

@receiver(post_save)
def kb_content_updated(sender, instance, created, **kwargs):
    """
    Signal handler for knowledge base content updates.
    """
    # Only process if this looks like KB content
    if hasattr(instance, 'title') and hasattr(instance, 'content'):
        try:
            # Invalidate KB cache
            from django.core.cache import cache
            
            cache_key_pattern = f"kb_content_{sender.__name__}_*"
            cache.delete_pattern(cache_key_pattern)
            
            # Log the update
            action = "created" if created else "updated"
            logger.info(f"KB content {action}: {sender.__name__} - {instance.title}")
            
            # Trigger KB update webhook if available
            _trigger_kb_webhook(instance, action)
            
        except Exception as exc:
            logger.error(f"Failed to handle KB content update: {exc}")


@receiver(post_delete)
def kb_content_deleted(sender, instance, **kwargs):
    """
    Signal handler for knowledge base content deletion.
    """
    # Only process if this looks like KB content
    if hasattr(instance, 'title') and hasattr(instance, 'content'):
        try:
            # Invalidate KB cache
            from django.core.cache import cache
            
            cache_key_pattern = f"kb_content_{sender.__name__}_*"
            cache.delete_pattern(cache_key_pattern)
            
            # Log the deletion
            logger.info(f"KB content deleted: {sender.__name__} - {instance.title}")
            
            # Trigger KB deletion webhook if available
            _trigger_kb_webhook(instance, "deleted")
            
        except Exception as exc:
            logger.error(f"Failed to handle KB content deletion: {exc}")


def _trigger_kb_webhook(instance, action):
    """
    Trigger webhook for KB content changes.
    """
    try:
        from .services.webhook_service import WebhookService
        
        webhook_data = {
            'action': action,
            'model': instance.__class__.__name__,
            'id': instance.id,
            'title': getattr(instance, 'title', ''),
            'content_preview': getattr(instance, 'content', '')[:200] + '...' if hasattr(instance, 'content') and len(instance.content) > 200 else getattr(instance, 'content', ''),
            'updated_at': timezone.now().isoformat(),
        }
        
        WebhookService.dispatch('kb_content_updated', webhook_data)
        
    except Exception as exc:
        logger.error(f"Failed to trigger KB webhook: {exc}")


# ── Documentation Signals ───────────────────────────────────────────────────

@receiver(post_save)
def documentation_updated(sender, instance, created, **kwargs):
    """
    Signal handler for documentation updates.
    """
    # Only process if this looks like documentation
    if hasattr(instance, 'slug') and hasattr(instance, 'body'):
        try:
            # Invalidate documentation cache
            from django.core.cache import cache
            
            cache_key_pattern = f"doc_content_{sender.__name__}_*"
            cache.delete_pattern(cache_key_pattern)
            
            # Update search index
            _update_search_index(instance, created)
            
            # Log the update
            action = "created" if created else "updated"
            logger.info(f"Documentation {action}: {sender.__name__} - {instance.slug}")
            
        except Exception as exc:
            logger.error(f"Failed to handle documentation update: {exc}")


def _update_search_index(instance, created):
    """
    Update search index for documentation.
    """
    try:
        from .search import search_index_manager
        
        # Create or update search index entry
        search_data = {
            'title': getattr(instance, 'title', getattr(instance, 'slug', '')),
            'content': getattr(instance, 'body', getattr(instance, 'content', '')),
            'url': f"/docs/{getattr(instance, 'slug', instance.id)}/",
            'updated_at': timezone.now(),
        }
        
        # This would integrate with your search backend
        # For now, it's a placeholder
        logger.debug(f"Search index updated for {instance.__class__.__name__}: {search_data['title']}")
        
    except Exception as exc:
        logger.error(f"Failed to update search index: {exc}")


# ── Help System Signals ─────────────────────────────────────────────────────

@receiver(post_save)
def help_article_updated(sender, instance, created, **kwargs):
    """
    Signal handler for help article updates.
    """
    # Only process if this looks like a help article
    if hasattr(instance, 'question') and hasattr(instance, 'answer'):
        try:
            # Invalidate help cache
            from django.core.cache import cache
            
            cache_key_pattern = f"help_article_{sender.__name__}_*"
            cache.delete_pattern(cache_key_pattern)
            
            # Update help search index
            _update_help_search_index(instance, created)
            
            # Log the update
            action = "created" if created else "updated"
            logger.info(f"Help article {action}: {sender.__name__} - {instance.question[:50]}...")
            
        except Exception as exc:
            logger.error(f"Failed to handle help article update: {exc}")


def _update_help_search_index(instance, created):
    """
    Update search index for help articles.
    """
    try:
        from .search import search_index_manager
        
        # Create or update search index entry
        search_data = {
            'title': getattr(instance, 'question', ''),
            'content': getattr(instance, 'answer', ''),
            'url': f"/help/article/{getattr(instance, 'slug', instance.id)}/",
            'category': getattr(instance, 'category', ''),
            'updated_at': timezone.now(),
        }
        
        # This would integrate with your search backend
        logger.debug(f"Help search index updated for {instance.__class__.__name__}: {search_data['title']}")
        
    except Exception as exc:
        logger.error(f"Failed to update help search index: {exc}")


# ── FAQ Signals ─────────────────────────────────────────────────────────────

@receiver(post_save)
def faq_updated(sender, instance, created, **kwargs):
    """
    Signal handler for FAQ updates.
    """
    # Only process if this looks like an FAQ
    if hasattr(instance, 'question') and hasattr(instance, 'answer'):
        try:
            # Invalidate FAQ cache
            from django.core.cache import cache
            
            cache_key_pattern = f"faq_{sender.__name__}_*"
            cache.delete_pattern(cache_key_pattern)
            
            # Update FAQ search index
            _update_faq_search_index(instance, created)
            
            # Log the update
            action = "created" if created else "updated"
            logger.info(f"FAQ {action}: {sender.__name__} - {instance.question[:50]}...")
            
        except Exception as exc:
            logger.error(f"Failed to handle FAQ update: {exc}")


def _update_faq_search_index(instance, created):
    """
    Update search index for FAQs.
    """
    try:
        from .search import search_index_manager
        
        # Create or update search index entry
        search_data = {
            'title': getattr(instance, 'question', ''),
            'content': getattr(instance, 'answer', ''),
            'url': f"/faq/{getattr(instance, 'slug', instance.id)}/",
            'category': getattr(instance, 'category', ''),
            'priority': getattr(instance, 'priority', 0),
            'updated_at': timezone.now(),
        }
        
        # This would integrate with your search backend
        logger.debug(f"FAQ search index updated for {instance.__class__.__name__}: {search_data['title']}")
        
    except Exception as exc:
        logger.error(f"Failed to update FAQ search index: {exc}")


# ── Tutorial Signals ─────────────────────────────────────────────────────

@receiver(post_save)
def tutorial_updated(sender, instance, created, **kwargs):
    """
    Signal handler for tutorial updates.
    """
    # Only process if this looks like a tutorial
    if hasattr(instance, 'title') and hasattr(instance, 'steps'):
        try:
            # Invalidate tutorial cache
            from django.core.cache import cache
            
            cache_key_pattern = f"tutorial_{sender.__name__}_*"
            cache.delete_pattern(cache_key_pattern)
            
            # Update tutorial search index
            _update_tutorial_search_index(instance, created)
            
            # Log the update
            action = "created" if created else "updated"
            logger.info(f"Tutorial {action}: {sender.__name__} - {instance.title}")
            
        except Exception as exc:
            logger.error(f"Failed to handle tutorial update: {exc}")


def _update_tutorial_search_index(instance, created):
    """
    Update search index for tutorials.
    """
    try:
        from .search import search_index_manager
        
        # Create or update search index entry
        search_data = {
            'title': getattr(instance, 'title', ''),
            'content': getattr(instance, 'description', ''),
            'url': f"/tutorials/{getattr(instance, 'slug', instance.id)}/",
            'difficulty': getattr(instance, 'difficulty', 'beginner'),
            'estimated_time': getattr(instance, 'estimated_time', 0),
            'updated_at': timezone.now(),
        }
        
        # This would integrate with your search backend
        logger.debug(f"Tutorial search index updated for {instance.__class__.__name__}: {search_data['title']}")
        
    except Exception as exc:
        logger.error(f"Failed to update tutorial search index: {exc}")


# ── Version Control Signals ─────────────────────────────────────────────────

@receiver(post_save)
def version_updated(sender, instance, created, **kwargs):
    """
    Signal handler for version updates.
    """
    # Only process if this looks like version information
    if hasattr(instance, 'version') and hasattr(instance, 'release_notes'):
        try:
            # Invalidate version cache
            from django.core.cache import cache
            
            cache.delete('latest_version')
            cache.delete('version_history')
            
            # Log the update
            action = "created" if created else "updated"
            logger.info(f"Version {action}: {sender.__name__} - {instance.version}")
            
            # Trigger version update notification
            _notify_version_update(instance, action)
            
        except Exception as exc:
            logger.error(f"Failed to handle version update: {exc}")


def _notify_version_update(instance, action):
    """
    Notify users about version updates.
    """
    try:
        from .services.notification_service import NotificationService
        
        # Get all active users
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        active_users = User.objects.filter(is_active=True)
        
        # Send notification to all users
        for user in active_users:
            NotificationService.send(
                user,
                "version_update",
                title=f"New Version Available: {instance.version}",
                body=f"Version {instance.version} has been {action}. Check release notes for details.",
                data={
                    'version': instance.version,
                    'action': action,
                    'release_notes': getattr(instance, 'release_notes', ''),
                }
            )
        
        logger.info(f"Version update notification sent to {active_users.count()} users")
        
    except Exception as exc:
        logger.error(f"Failed to send version update notification: {exc}")


# ── Analytics Signals ─────────────────────────────────────────────────────

@receiver(post_save)
def kb_analytics_updated(sender, instance, created, **kwargs):
    """
    Signal handler for knowledge base analytics.
    """
    # Only process if this looks like KB content
    if hasattr(instance, 'title') and hasattr(instance, 'content'):
        try:
            # Record analytics event
            from .services.analytics_service import AnalyticsService
            
            action = 'kb_created' if created else 'kb_updated'
            
            # This would record to analytics system
            # For now, it's a placeholder
            logger.debug(f"KB analytics event: {action} - {instance.title}")
            
        except Exception as exc:
            logger.error(f"Failed to record KB analytics: {exc}")


# ── Cache Management Signals ─────────────────────────────────────────────────

@receiver(post_save)
def kb_cache_invalidated(sender, instance, created, **kwargs):
    """
    Signal handler for cache invalidation.
    """
    # Only process if this looks like KB content
    if hasattr(instance, 'title') and hasattr(instance, 'content'):
        try:
            # Invalidate related caches
            from django.core.cache import cache
            
            # Invalidate search results cache
            cache.delete_pattern('search_results_*')
            
            # Invalidate popular content cache
            cache.delete('popular_kb_content')
            
            # Invalidate recent updates cache
            cache.delete('recent_kb_updates')
            
            logger.debug(f"KB cache invalidated for {sender.__name__}: {instance.title}")
            
        except Exception as exc:
            logger.error(f"Failed to invalidate KB cache: {exc}")


# ── Search Index Signals ─────────────────────────────────────────────────────

@receiver(post_save)
def search_index_updated(sender, instance, created, **kwargs):
    """
    Signal handler for search index updates.
    """
    # Only process if this looks like searchable content
    if hasattr(instance, 'title') or hasattr(instance, 'name'):
        try:
            # Update search index
            from .search import search_index_manager
            
            # Determine index name based on model
            index_name = f"{sender.__name__.lower()}_index"
            
            # Create index if it doesn't exist
            if index_name not in search_index_manager.indices:
                fields = []
                if hasattr(instance, 'title'):
                    fields.append('title')
                if hasattr(instance, 'name'):
                    fields.append('name')
                if hasattr(instance, 'content'):
                    fields.append('content')
                if hasattr(instance, 'body'):
                    fields.append('body')
                if hasattr(instance, 'description'):
                    fields.append('description')
                
                search_index_manager.create_index(index_name, sender, fields)
            
            # Update the index
            search_index_manager.update_index(index_name)
            
            logger.debug(f"Search index updated for {sender.__name__}: {getattr(instance, 'title', getattr(instance, 'name', ''))}")
            
        except Exception as exc:
            logger.error(f"Failed to update search index: {exc}")


# ── Notification Signals ─────────────────────────────────────────────────────

@receiver(post_save)
def kb_notification_sent(sender, instance, created, **kwargs):
    """
    Signal handler for KB-related notifications.
    """
    # Only process if this looks like KB content
    if hasattr(instance, 'title') and hasattr(instance, 'content'):
        try:
            # Send notification for new KB content
            if created and hasattr(instance, 'notify_users') and instance.notify_users:
                from .services.notification_service import NotificationService
                
                # Get users who should be notified
                from django.contrib.auth import get_user_model
                User = get_user_model()
                
                # This would get users based on preferences
                # For now, it's a placeholder
                logger.debug(f"KB notification would be sent for: {instance.title}")
            
        except Exception as exc:
            logger.error(f"Failed to send KB notification: {exc}")


# ── Integration Signals ─────────────────────────────────────────────────────

@receiver(post_save)
def external_system_synced(sender, instance, created, **kwargs):
    """
    Signal handler for external system synchronization.
    """
    # Only process if this looks like KB content
    if hasattr(instance, 'title') and hasattr(instance, 'content'):
        try:
            # Sync with external systems
            _sync_with_external_systems(instance, created)
            
        except Exception as exc:
            logger.error(f"Failed to sync with external systems: {exc}")


def _sync_with_external_systems(instance, created):
    """
    Sync KB content with external systems.
    """
    try:
        # This would integrate with external systems like:
        # - Help desk systems
        # - Documentation platforms
        # - Knowledge base services
        # - Search engines
        
        action = 'created' if created else 'updated'
        
        sync_data = {
            'action': action,
            'model': instance.__class__.__name__,
            'id': instance.id,
            'title': getattr(instance, 'title', ''),
            'content': getattr(instance, 'content', ''),
            'url': f"/kb/{getattr(instance, 'slug', instance.id)}/",
            'updated_at': timezone.now().isoformat(),
        }
        
        # This would send data to external systems
        logger.debug(f"External sync data prepared: {sync_data}")
        
    except Exception as exc:
        logger.error(f"Failed to prepare external sync data: {exc}")


# ── Utility Functions ─────────────────────────────────────────────────────

def is_kb_content(sender):
    """
    Check if sender is a KB content model.
    """
    kb_fields = ['title', 'content', 'body', 'question', 'answer', 'description']
    
    # Check if model has KB-like fields
    for field in kb_fields:
        if hasattr(sender, field):
            return True
    
    return False


def get_kb_cache_key(sender, instance):
    """
    Generate cache key for KB content.
    """
    return f"kb_{sender.__name__.lower()}_{instance.id}"


def invalidate_kb_cache(sender, instance):
    """
    Invalidate cache for KB content.
    """
    try:
        from django.core.cache import cache
        
        cache_key = get_kb_cache_key(sender, instance)
        cache.delete(cache_key)
        
        # Also invalidate related caches
        cache.delete_pattern(f"kb_{sender.__name__.lower()}_*")
        cache.delete_pattern("search_results_*")
        cache.delete("popular_kb_content")
        cache.delete("recent_kb_updates")
        
        logger.debug(f"KB cache invalidated for {sender.__name__}: {getattr(instance, 'title', instance.id)}")
        
    except Exception as exc:
        logger.error(f"Failed to invalidate KB cache: {exc}")


def update_search_index_for_kb(sender, instance):
    """
    Update search index for KB content.
    """
    try:
        from .search import search_index_manager
        
        # Determine index name
        index_name = f"{sender.__name__.lower()}_index"
        
        # Determine searchable fields
        fields = []
        if hasattr(instance, 'title'):
            fields.append('title')
        if hasattr(instance, 'name'):
            fields.append('name')
        if hasattr(instance, 'content'):
            fields.append('content')
        if hasattr(instance, 'body'):
            fields.append('body')
        if hasattr(instance, 'question'):
            fields.append('question')
        if hasattr(instance, 'answer'):
            fields.append('answer')
        if hasattr(instance, 'description'):
            fields.append('description')
        
        # Create index if it doesn't exist
        if index_name not in search_index_manager.indices:
            search_index_manager.create_index(index_name, sender, fields)
        
        # Update the index
        search_index_manager.update_index(index_name)
        
        logger.debug(f"Search index updated for KB content: {sender.__name__}")
        
    except Exception as exc:
        logger.error(f"Failed to update search index for KB content: {exc}")


def trigger_kb_webhook(instance, action):
    """
    Trigger webhook for KB content changes.
    """
    try:
        from .services.webhook_service import WebhookService
        
        webhook_data = {
            'action': action,
            'model': instance.__class__.__name__,
            'id': instance.id,
            'title': getattr(instance, 'title', getattr(instance, 'question', '')),
            'content_preview': getattr(instance, 'content', getattr(instance, 'body', getattr(instance, 'answer', '')))[:200] + '...' if hasattr(instance, 'content') and len(getattr(instance, 'content', '')) > 200 else getattr(instance, 'content', getattr(instance, 'body', getattr(instance, 'answer', ''))),
            'url': f"/kb/{getattr(instance, 'slug', instance.id)}/",
            'updated_at': timezone.now().isoformat(),
        }
        
        WebhookService.dispatch('kb_content_updated', webhook_data)
        
        logger.debug(f"KB webhook triggered: {action} - {webhook_data['title']}")
        
    except Exception as exc:
        logger.error(f"Failed to trigger KB webhook: {exc}")


# ── Signal Registration ─────────────────────────────────────────────────────

def register_kb_signals():
    """
    Register all KB-related signals.
    """
    try:
        # This function can be called to ensure all KB signals are registered
        logger.info("KB signals registered successfully")
        
    except Exception as exc:
        logger.error(f"Failed to register KB signals: {exc}")


# Auto-register signals on module import
try:
    register_kb_signals()
except Exception:
    # Silently ignore if signals can't be registered during import
    pass
