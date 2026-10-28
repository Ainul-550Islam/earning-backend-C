# api/cms/signals_kb.py
"""
CMS Knowledge Base signals (KB = Knowledge Base / Blog / Content).
Fired on content events: publish, update, delete, view, comment, FAQ, search, rating.

FIX (audit): connect_kb_receivers() previously connected only 2 out of 15+
signals (kb_post_published and kb_search_performed).  All remaining signals
now have receivers:
  - kb_post_updated      → re-index + cache invalidate
  - kb_post_archived     → remove from search index
  - kb_post_viewed       → analytics view counter
  - kb_comment_created   → notify post author
  - kb_comment_approved  → notify commenter
  - kb_comment_rejected  → notify commenter
  - kb_faq_helpful       → track helpfulness metric
  - kb_faq_created       → index new FAQ
  - kb_search_no_results → track zero-result queries
  - kb_content_rated     → update average rating cache
  - kb_content_bookmarked→ track bookmarks metric
  - kb_announcement_read → mark announcement as read in cache
  - kb_page_published    → re-index page + cache invalidate
  - kb_page_unpublished  → remove from index + cache invalidate
"""
from django.dispatch import Signal

# ── Blog / Content ────────────────────────────────────────────────
kb_post_published    = Signal()  # post, author
kb_post_updated      = Signal()  # post, author, changed_fields
kb_post_archived     = Signal()  # post
kb_post_viewed       = Signal()  # post, user, ip

# ── Comment signals ───────────────────────────────────────────────
kb_comment_created   = Signal()  # post, comment, user
kb_comment_approved  = Signal()  # comment, moderator
kb_comment_rejected  = Signal()  # comment, moderator, reason

# ── FAQ signals ───────────────────────────────────────────────────
kb_faq_helpful       = Signal()  # faq, user, helpful=True/False
kb_faq_created       = Signal()  # faq, author

# ── Search signals ────────────────────────────────────────────────
kb_search_performed  = Signal()  # query, results_count, user
kb_search_no_results = Signal()  # query, user

# ── Content rating ────────────────────────────────────────────────
kb_content_rated     = Signal()   # content_type, object_id, user, stars
kb_content_bookmarked = Signal()  # content_type, object_id, user

# ── Announcement signals ──────────────────────────────────────────
kb_announcement_read = Signal()  # announcement, user

# ── Page signals ──────────────────────────────────────────────────
kb_page_published    = Signal()  # page, author
kb_page_unpublished  = Signal()  # page


def connect_kb_receivers():
    """
    Connect all Knowledge Base signal receivers.
    Called once from CMSConfig.ready() after base receivers are wired.
    Each handler is wrapped in try/except so a failure in one handler
    never crashes the whole signal dispatch chain.
    """
    import logging
    logger = logging.getLogger(__name__)

    # ──────────────────────────────────────────────────────────────
    # Blog / Content receivers
    # ──────────────────────────────────────────────────────────────

    def on_post_published(sender, post, author, **kwargs):
        """Re-index post in search + invalidate blog cache when published."""
        try:
            from api.cms.search import CMSSearchEngine
            CMSSearchEngine.index_content('blog', post.id)
        except Exception as e:
            logger.debug(f"[KB Signal] post_published — search index failed: {e}")

        try:
            from api.cms.caching import CacheInvalidationService
            CacheInvalidationService.on_blog_post_update(post.id)
        except Exception as e:
            logger.debug(f"[KB Signal] post_published — cache invalidation failed: {e}")

        try:
            from api.cms.monitoring import CMSMetrics
            CMSMetrics.increment('blog_posts_published')
        except Exception:
            pass

    def on_post_updated(sender, post, author, changed_fields=None, **kwargs):
        """Re-index + invalidate cache on blog post update."""
        try:
            from api.cms.search import CMSSearchEngine
            CMSSearchEngine.index_content('blog', post.id)
        except Exception as e:
            logger.debug(f"[KB Signal] post_updated — search index failed: {e}")

        try:
            from api.cms.caching import CacheInvalidationService
            CacheInvalidationService.on_blog_post_update(post.id)
        except Exception as e:
            logger.debug(f"[KB Signal] post_updated — cache invalidation failed: {e}")

    def on_post_archived(sender, post, **kwargs):
        """Remove archived post from search index."""
        try:
            from api.cms.search import CMSSearchEngine
            CMSSearchEngine.deindex_content('blog', post.id)
        except Exception as e:
            logger.debug(f"[KB Signal] post_archived — deindex failed: {e}")

        try:
            from api.cms.caching import CacheInvalidationService
            CacheInvalidationService.on_blog_post_update(post.id)
        except Exception:
            pass

    def on_post_viewed(sender, post, user=None, ip='', **kwargs):
        """Increment view counter for analytics."""
        try:
            from api.cms.monitoring import CMSMetrics
            CMSMetrics.increment('blog_post_views')
        except Exception:
            pass

        try:
            # Async increment to avoid DB write on every page view
            from api.cms.tasks.blog_analytics_tasks import collect_blog_analytics
            collect_blog_analytics.apply_async(
                kwargs={'post_id': post.id, 'user_id': getattr(user, 'id', None), 'ip': ip},
                countdown=5,
            )
        except Exception:
            # Task queue unavailable — increment synchronously as fallback
            try:
                post.__class__.objects.filter(pk=post.pk).update(
                    view_count=__import__('django.db.models', fromlist=['F']).F('view_count') + 1
                )
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────
    # Comment receivers
    # ──────────────────────────────────────────────────────────────

    def on_comment_created(sender, post, comment, user, **kwargs):
        """Notify post author when a new comment is created."""
        try:
            from api.cms.adapters import NotificationAdapter
            if hasattr(post, 'author') and post.author and post.author != user:
                NotificationAdapter.notify(
                    user=post.author,
                    title='নতুন মন্তব্য',
                    body=(
                        f"{getattr(user, 'username', 'একজন ব্যবহারকারী')} "
                        f"আপনার পোস্টে মন্তব্য করেছেন।"
                    ),
                    notif_type='comment',
                    object_id=getattr(post, 'pk', None),
                )
        except Exception as e:
            logger.debug(f"[KB Signal] comment_created — notify failed: {e}")

        try:
            from api.cms.monitoring import CMSMetrics
            CMSMetrics.increment('comments_created')
        except Exception:
            pass

    def on_comment_approved(sender, comment, moderator, **kwargs):
        """Notify the commenter that their comment was approved."""
        try:
            from api.cms.adapters import NotificationAdapter
            commenter = getattr(comment, 'author', None) or getattr(comment, 'user', None)
            if commenter and commenter != moderator:
                NotificationAdapter.notify(
                    user=commenter,
                    title='মন্তব্য অনুমোদিত',
                    body='আপনার মন্তব্য অনুমোদন করা হয়েছে।',
                    notif_type='comment_approved',
                    object_id=getattr(comment, 'pk', None),
                )
        except Exception as e:
            logger.debug(f"[KB Signal] comment_approved — notify failed: {e}")

    def on_comment_rejected(sender, comment, moderator, reason='', **kwargs):
        """Notify the commenter that their comment was rejected with reason."""
        try:
            from api.cms.adapters import NotificationAdapter
            commenter = getattr(comment, 'author', None) or getattr(comment, 'user', None)
            if commenter:
                NotificationAdapter.notify(
                    user=commenter,
                    title='মন্তব্য প্রত্যাখ্যাত',
                    body=f"আপনার মন্তব্য প্রত্যাখ্যাত হয়েছে।{' কারণ: ' + reason if reason else ''}",
                    notif_type='comment_rejected',
                    object_id=getattr(comment, 'pk', None),
                )
        except Exception as e:
            logger.debug(f"[KB Signal] comment_rejected — notify failed: {e}")

    # ──────────────────────────────────────────────────────────────
    # FAQ receivers
    # ──────────────────────────────────────────────────────────────

    def on_faq_helpful(sender, faq, user, helpful=True, **kwargs):
        """Track FAQ helpfulness metric and update FAQ score."""
        try:
            from api.cms.monitoring import CMSMetrics
            metric_key = 'faq_helpful' if helpful else 'faq_not_helpful'
            CMSMetrics.increment(metric_key)
        except Exception:
            pass

        try:
            # Update the FAQ helpfulness score asynchronously
            from django.core.cache import cache
            cache_key = f'faq_helpful_{faq.pk}'
            current = cache.get(cache_key, {'helpful': 0, 'not_helpful': 0})
            if helpful:
                current['helpful'] += 1
            else:
                current['not_helpful'] += 1
            cache.set(cache_key, current, timeout=86400)  # 24h
        except Exception as e:
            logger.debug(f"[KB Signal] faq_helpful — cache update failed: {e}")

    def on_faq_created(sender, faq, author, **kwargs):
        """Index newly created FAQ in search."""
        try:
            from api.cms.search import CMSSearchEngine
            CMSSearchEngine.index_content('faq', faq.id)
        except Exception as e:
            logger.debug(f"[KB Signal] faq_created — search index failed: {e}")

    # ──────────────────────────────────────────────────────────────
    # Search receivers
    # ──────────────────────────────────────────────────────────────

    def on_search_performed(sender, query, results_count, user=None, **kwargs):
        """Track search analytics — total queries and zero-result rate."""
        try:
            from api.cms.monitoring import CMSMetrics
            CMSMetrics.increment('search_queries')
            if results_count == 0:
                CMSMetrics.increment('search_no_results')
        except Exception:
            pass

    def on_search_no_results(sender, query, user=None, **kwargs):
        """
        Log zero-result searches for later analysis / content gap identification.
        Stored in cache sorted set; a periodic task aggregates into DB.
        """
        try:
            from api.cms.monitoring import CMSMetrics
            CMSMetrics.increment('search_no_results')
        except Exception:
            pass

        try:
            from django.core.cache import cache
            # Keep a rolling list of the last 500 no-result queries for editorial review
            no_result_queries = cache.get('kb_no_result_queries', [])
            no_result_queries.append({'query': query, 'user_id': getattr(user, 'id', None)})
            if len(no_result_queries) > 500:
                no_result_queries = no_result_queries[-500:]
            cache.set('kb_no_result_queries', no_result_queries, timeout=604800)  # 7 days
        except Exception as e:
            logger.debug(f"[KB Signal] search_no_results — cache log failed: {e}")

    # ──────────────────────────────────────────────────────────────
    # Content rating receivers
    # ──────────────────────────────────────────────────────────────

    def on_content_rated(sender, content_type, object_id, user, stars, **kwargs):
        """Invalidate rating cache so next request recomputes the average."""
        try:
            from django.core.cache import cache
            cache_key = f'content_rating_{content_type}_{object_id}'
            cache.delete(cache_key)
        except Exception as e:
            logger.debug(f"[KB Signal] content_rated — cache delete failed: {e}")

        try:
            from api.cms.monitoring import CMSMetrics
            CMSMetrics.increment('content_ratings')
        except Exception:
            pass

    def on_content_bookmarked(sender, content_type, object_id, user, **kwargs):
        """Track bookmark analytics."""
        try:
            from api.cms.monitoring import CMSMetrics
            CMSMetrics.increment('content_bookmarks')
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────
    # Announcement receivers
    # ──────────────────────────────────────────────────────────────

    def on_announcement_read(sender, announcement, user, **kwargs):
        """
        Mark announcement as read for this user.
        Uses a cache set per announcement to avoid DB writes on every read event.
        """
        try:
            from django.core.cache import cache
            # Store per-user read status in a cache set
            read_key = f'announcement_read_{announcement.pk}'
            readers = cache.get(read_key, set())
            readers.add(getattr(user, 'id', None))
            cache.set(read_key, readers, timeout=604800)  # 7 days
        except Exception as e:
            logger.debug(f"[KB Signal] announcement_read — cache update failed: {e}")

    # ──────────────────────────────────────────────────────────────
    # Page receivers
    # ──────────────────────────────────────────────────────────────

    def on_page_published(sender, page, author, **kwargs):
        """Re-index page in search and invalidate page cache."""
        try:
            from api.cms.search import CMSSearchEngine
            CMSSearchEngine.index_content('page', page.id)
        except Exception as e:
            logger.debug(f"[KB Signal] page_published — search index failed: {e}")

        try:
            from api.cms.caching import CacheInvalidationService
            CacheInvalidationService.on_page_update(page.id)
        except Exception as e:
            logger.debug(f"[KB Signal] page_published — cache invalidation failed: {e}")

        try:
            from api.cms.monitoring import CMSMetrics
            CMSMetrics.increment('pages_published')
        except Exception:
            pass

    def on_page_unpublished(sender, page, **kwargs):
        """Remove unpublished page from search index and invalidate cache."""
        try:
            from api.cms.search import CMSSearchEngine
            CMSSearchEngine.deindex_content('page', page.id)
        except Exception as e:
            logger.debug(f"[KB Signal] page_unpublished — deindex failed: {e}")

        try:
            from api.cms.caching import CacheInvalidationService
            CacheInvalidationService.on_page_update(page.id)
        except Exception as e:
            logger.debug(f"[KB Signal] page_unpublished — cache invalidation failed: {e}")

    # ──────────────────────────────────────────────────────────────
    # Connect all signals
    # ──────────────────────────────────────────────────────────────

    # Blog / Content
    kb_post_published.connect(on_post_published,     dispatch_uid='kb_post_published_indexer')
    kb_post_updated.connect(on_post_updated,          dispatch_uid='kb_post_updated_indexer')
    kb_post_archived.connect(on_post_archived,        dispatch_uid='kb_post_archived_deindexer')
    kb_post_viewed.connect(on_post_viewed,            dispatch_uid='kb_post_viewed_counter')

    # Comments
    kb_comment_created.connect(on_comment_created,   dispatch_uid='kb_comment_created_notifier')
    kb_comment_approved.connect(on_comment_approved, dispatch_uid='kb_comment_approved_notifier')
    kb_comment_rejected.connect(on_comment_rejected, dispatch_uid='kb_comment_rejected_notifier')

    # FAQs
    kb_faq_helpful.connect(on_faq_helpful,            dispatch_uid='kb_faq_helpful_tracker')
    kb_faq_created.connect(on_faq_created,            dispatch_uid='kb_faq_created_indexer')

    # Search
    kb_search_performed.connect(on_search_performed,  dispatch_uid='kb_search_tracker')
    kb_search_no_results.connect(on_search_no_results, dispatch_uid='kb_search_no_results_logger')

    # Content rating
    kb_content_rated.connect(on_content_rated,        dispatch_uid='kb_content_rated_cache_buster')
    kb_content_bookmarked.connect(on_content_bookmarked, dispatch_uid='kb_content_bookmarked_tracker')

    # Announcements
    kb_announcement_read.connect(on_announcement_read, dispatch_uid='kb_announcement_read_marker')

    # Pages
    kb_page_published.connect(on_page_published,      dispatch_uid='kb_page_published_indexer')
    kb_page_unpublished.connect(on_page_unpublished,  dispatch_uid='kb_page_unpublished_deindexer')

    logger.debug("[KB Signals] All 16 receivers connected successfully.")
