from api.cms.models_new.blog import BlogPost, BlogCategory
# api/cms/services/BlogService.py
"""
BlogService: Full CRUD, slug generation, SEO auto-fill, publishing workflow,
draft management, analytics, and bulk operations.
"""
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any

from django.db import transaction
from django.db.models import Q, F, Count, Sum, Avg
from django.utils import timezone
from django.utils.text import slugify
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class BlogService:
    """Service class for blog management business logic."""

    # ────────────────────────────────────────────────────
    # CRUD OPERATIONS
    # ────────────────────────────────────────────────────

    @staticmethod
    def create_post(
        title: str,
        body: str,
        author,
        category=None,
        tags: Optional[List] = None,
        status: str = 'draft',
        excerpt: str = '',
        language: str = 'en',
        featured_image=None,
        auto_seo: bool = True,
        **kwargs
    ) -> Optional[Any]:
        """
        Create a new blog post with optional SEO auto-fill.

        Args:
            title: Post title
            body: Post body (rich text)
            author: Author user object
            category: BlogCategory object
            tags: List of BlogTag objects
            status: Initial status (draft, published, etc.)
            excerpt: Short excerpt
            language: Language code
            featured_image: Image file or ProcessedImageField
            auto_seo: Auto-create SEO metadata
            **kwargs: Additional model fields

        Returns:
            Created BlogPost object or None on failure
        """
        try:
            from api.cms.models_new.blog import BlogPost, BlogSEO

            with transaction.atomic():
                slug = BlogService._generate_unique_slug(title)

                post = BlogPost.objects.create(
                    title=title,
                    slug=slug,
                    body=body,
                    author=author,
                    category=category,
                    status=status,
                    excerpt=excerpt,
                    language=language,
                    featured_image=featured_image,
                    **kwargs
                )

                # Assign tags
                if tags:
                    post.tags.set(tags)
                    for tag in tags:
                        tag.increment_usage()

                # Auto-fill SEO
                if auto_seo:
                    BlogService._auto_fill_seo(post)

                # Update category post count
                if category:
                    from api.cms.models_new.blog import BlogCategory
                    BlogCategory.objects.filter(id=category.id).update(
                        post_count=F('post_count') + 1
                    )

                logger.info(f"Created blog post '{post.title}' (id={post.id})")
                return post

        except Exception as e:
            logger.error(f"Error creating blog post: {e}", exc_info=True)
            return None

    @staticmethod
    def update_post(post, data: Dict[str, Any], auto_seo: bool = False) -> bool:
        """
        Update an existing blog post.

        Args:
            post: BlogPost instance
            data: Dictionary of fields to update
            auto_seo: Re-run auto SEO fill

        Returns:
            True on success, False on failure
        """
        try:
            with transaction.atomic():
                old_category = post.category

                # Extract tags separately (M2M)
                tags = data.pop('tags', None)

                for field, value in data.items():
                    if hasattr(post, field):
                        setattr(post, field, value)

                # Regenerate slug if title changed
                if 'title' in data:
                    new_slug = BlogService._generate_unique_slug(data['title'], exclude_id=post.id)
                    post.slug = new_slug

                post.save()

                # Update tags
                if tags is not None:
                    # Decrement old tags
                    for tag in post.tags.all():
                        tag.decrement_usage()
                    post.tags.set(tags)
                    for tag in tags:
                        tag.increment_usage()

                # Update category counts if changed
                if 'category' in data and old_category != post.category:
                    from api.cms.models_new.blog import BlogCategory
                    if old_category:
                        BlogCategory.objects.filter(id=old_category.id).update(
                            post_count=F('post_count') - 1
                        )
                    if post.category:
                        BlogCategory.objects.filter(id=post.category.id).update(
                            post_count=F('post_count') + 1
                        )

                if auto_seo:
                    BlogService._auto_fill_seo(post)

                logger.info(f"Updated blog post '{post.title}' (id={post.id})")
                return True

        except Exception as e:
            logger.error(f"Error updating blog post {post.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def delete_post(post, soft: bool = True) -> bool:
        """
        Delete or soft-delete a blog post.

        Args:
            post: BlogPost instance
            soft: If True, archive instead of hard delete

        Returns:
            True on success
        """
        try:
            with transaction.atomic():
                if soft:
                    post.status = 'archived'
                    post.is_active = False
                    post.save(update_fields=['status', 'is_active'])
                    logger.info(f"Soft deleted blog post {post.id}")
                else:
                    post.delete()
                    logger.info(f"Hard deleted blog post {post.id}")
                return True
        except Exception as e:
            logger.error(f"Error deleting blog post: {e}", exc_info=True)
            return False

    @staticmethod
    def get_post(slug: str, increment_view: bool = True, user=None):
        """
        Get blog post by slug with optional view tracking.

        Returns:
            BlogPost or None
        """
        try:
            from api.cms.models_new.blog import BlogPost
            post = BlogPost.objects.select_related(
                'author', 'category'
            ).prefetch_related('tags', 'seo').get(slug=slug)

            # Check visibility
            if not BlogService._can_view(post, user):
                return None

            if increment_view:
                post.increment_views()

            return post
        except Exception:
            return None

    @staticmethod
    def _can_view(post, user=None) -> bool:
        """Check if user can view the post."""
        if not post.is_active:
            return False
        if post.status == 'published':
            return True
        if user and user.is_staff:
            return True
        if user and post.author == user:
            return True
        return False

    # ────────────────────────────────────────────────────
    # PUBLISHING WORKFLOW
    # ────────────────────────────────────────────────────

    @staticmethod
    def publish_post(post, publish_date: Optional[datetime] = None) -> bool:
        """
        Publish a blog post.

        Args:
            post: BlogPost instance
            publish_date: Optional backdated publish date

        Returns:
            True on success
        """
        try:
            with transaction.atomic():
                post.status = 'published'
                post.published_at = publish_date or timezone.now()
                post.save(update_fields=['status', 'published_at'])
                # Ensure SEO exists
                BlogService._auto_fill_seo(post)
                # Update category count
                if post.category:
                    from api.cms.models_new.blog import BlogCategory
                    BlogCategory.objects.filter(id=post.category.id).update(
                        post_count=Count('blog_posts', filter=Q(blog_posts__status='published'))
                    )
                logger.info(f"Published blog post '{post.title}' (id={post.id})")
                cache.delete(f'blog_post_{post.slug}')
                cache.delete('blog_featured_posts')
                return True
        except Exception as e:
            logger.error(f"Error publishing blog post {post.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def schedule_post(post, scheduled_at: datetime) -> bool:
        """Schedule a post for future publishing."""
        try:
            if scheduled_at <= timezone.now():
                raise ValueError("Scheduled date must be in the future.")
            post.status = 'scheduled'
            post.scheduled_at = scheduled_at
            post.save(update_fields=['status', 'scheduled_at'])
            logger.info(f"Scheduled post {post.id} for {scheduled_at}")
            return True
        except Exception as e:
            logger.error(f"Error scheduling post {post.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def unpublish_post(post) -> bool:
        """Revert published post to draft."""
        try:
            post.status = 'draft'
            post.save(update_fields=['status'])
            cache.delete(f'blog_post_{post.slug}')
            return True
        except Exception as e:
            logger.error(f"Error unpublishing post {post.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def bulk_publish(post_ids: List[int], user=None) -> int:
        """Bulk publish multiple posts."""
        from api.cms.models_new.blog import BlogPost
        return BlogPost.bulk_publish(post_ids, user=user)

    # ────────────────────────────────────────────────────
    # SLUG GENERATION
    # ────────────────────────────────────────────────────

    @staticmethod
    def _generate_unique_slug(title: str, exclude_id: Optional[int] = None) -> str:
        """
        Generate a unique slug from title.
        Appends numeric suffix if slug already exists.

        Returns:
            Unique slug string
        """
        from api.cms.models_new.blog import BlogPost
        base_slug = slugify(title)[:250]
        if not base_slug:
            base_slug = 'post'
        slug = base_slug
        counter = 1
        while True:
            qs = BlogPost.objects.filter(slug=slug)
            if exclude_id:
                qs = qs.exclude(id=exclude_id)
            if not qs.exists():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    # ────────────────────────────────────────────────────
    # SEO AUTO-FILL
    # ────────────────────────────────────────────────────

    @staticmethod
    def _auto_fill_seo(post) -> None:
        """Auto-create or update SEO metadata for a post."""
        try:
            from api.cms.models_new.blog import BlogSEO
            seo, _ = BlogSEO.objects.get_or_create(post=post)
            seo.auto_fill_from_post()
        except Exception as e:
            logger.warning(f"SEO auto-fill failed for post {post.id}: {e}")

    @staticmethod
    def update_seo(post, seo_data: Dict[str, Any]) -> bool:
        """Update SEO metadata for a post."""
        try:
            from api.cms.models_new.blog import BlogSEO
            seo, _ = BlogSEO.objects.get_or_create(post=post)
            for key, value in seo_data.items():
                if hasattr(seo, key):
                    setattr(seo, key, value)
            seo.save()
            return True
        except Exception as e:
            logger.error(f"Error updating SEO for post {post.id}: {e}", exc_info=True)
            return False

    # ────────────────────────────────────────────────────
    # LISTING & FILTERING
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_published_posts(
        category_id: Optional[int] = None,
        tag_slug: Optional[str] = None,
        author_id: Optional[int] = None,
        language: str = 'en',
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        user=None
    ) -> Tuple[List, int]:
        """
        Get published posts with filtering and pagination.

        Returns:
            Tuple (posts_list, total_count)
        """
        from api.cms.models_new.blog import BlogPost
        try:
            q = Q(status='published', is_active=True, published_at__lte=timezone.now())
            if language:
                q &= Q(language=language)
            if category_id:
                q &= Q(category_id=category_id)
            if tag_slug:
                q &= Q(tags__slug=tag_slug)
            if author_id:
                q &= Q(author_id=author_id)
            if search:
                q &= (
                    Q(title__icontains=search) |
                    Q(excerpt__icontains=search) |
                    Q(body__icontains=search)
                )

            total = BlogPost.objects.filter(q).count()
            posts = (
                BlogPost.objects.filter(q)
                .select_related('author', 'category')
                .prefetch_related('tags')
                .order_by('-published_at')[offset:offset + limit]
            )
            return list(posts), total
        except Exception as e:
            logger.error(f"Error listing published posts: {e}", exc_info=True)
            return [], 0

    @staticmethod
    def get_featured_posts(limit: int = 6, language: str = 'en') -> List:
        """Get featured published posts."""
        from api.cms.models_new.blog import BlogPost
        cache_key = f'blog_featured_{language}_{limit}'
        result = cache.get(cache_key)
        if result is None:
            result = list(
                BlogPost.objects.filter(
                    status='published', is_active=True,
                    is_featured=True, language=language,
                    published_at__lte=timezone.now()
                ).select_related('author', 'category')
                .prefetch_related('tags')
                .order_by('-published_at')[:limit]
            )
            cache.set(cache_key, result, 1800)
        return result

    @staticmethod
    def get_popular_posts(days: int = 30, limit: int = 10) -> List:
        """Get popular posts by view count."""
        from api.cms.models_new.blog import BlogPost
        cutoff = timezone.now() - timedelta(days=days)
        return list(
            BlogPost.objects.filter(
                status='published', is_active=True,
                published_at__gte=cutoff
            ).order_by('-views_count')
            .select_related('author', 'category')[:limit]
        )

    # ────────────────────────────────────────────────────
    # COMMENTS
    # ────────────────────────────────────────────────────

    @staticmethod
    def add_comment(post, content: str, user=None, parent=None, guest_name='', guest_email='', ip='') -> Optional[Any]:
        """Add a comment to a post."""
        try:
            from api.cms.models_new.blog import BlogComment
            if not post.allow_comments:
                return None
            comment = BlogComment.objects.create(
                post=post,
                user=user,
                parent=parent,
                content=content,
                guest_name=guest_name,
                guest_email=guest_email,
                ip_address=ip,
                is_approved=False  # Requires moderation by default
            )
            return comment
        except Exception as e:
            logger.error(f"Error adding comment to post {post.id}: {e}", exc_info=True)
            return None

    @staticmethod
    def approve_comment(comment, moderator=None) -> bool:
        """Approve a blog comment."""
        try:
            comment.approve(moderator=moderator)
            return True
        except Exception as e:
            logger.error(f"Error approving comment {comment.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def get_post_comments(post, approved_only: bool = True) -> List:
        """Get top-level comments for a post."""
        from api.cms.models_new.blog import BlogComment
        qs = BlogComment.objects.filter(
            post=post, parent__isnull=True, is_active=True
        ).select_related('user')
        if approved_only:
            qs = qs.filter(is_approved=True)
        return list(qs.order_by('-created_at'))

    # ────────────────────────────────────────────────────
    # ANALYTICS
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_post_analytics(post_id: int, days: int = 30) -> Dict[str, Any]:
        """Get analytics for a specific post."""
        from api.cms.models_new.blog import BlogPost
        try:
            post = BlogPost.objects.get(id=post_id)
            return {
                'post_id': post.id,
                'title': post.title,
                'status': post.status,
                'views_count': post.views_count,
                'share_count': post.share_count,
                'like_count': post.like_count,
                'comment_count': post.comment_count,
                'reading_time': post.reading_time_minutes,
                'published_at': post.published_at,
            }
        except Exception as e:
            logger.error(f"Error getting analytics for post {post_id}: {e}")
            return {}

    @staticmethod
    def get_blog_statistics() -> Dict[str, Any]:
        """Get overall blog statistics."""
        from api.cms.models_new.blog import BlogPost, BlogComment
        cache_key = 'blog_statistics_overall'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            total_posts = BlogPost.objects.count()
            published_posts = BlogPost.objects.filter(status='published', is_active=True).count()
            draft_posts = BlogPost.objects.filter(status='draft').count()
            total_views = BlogPost.objects.aggregate(t=Sum('views_count'))['t'] or 0
            total_comments = BlogPost.objects.aggregate(t=Sum('comment_count'))['t'] or 0
            top_posts = list(
                BlogPost.objects.filter(status='published', is_active=True)
                .order_by('-views_count')[:5]
                .values('id', 'title', 'views_count', 'published_at')
            )
            stats = {
                'total_posts': total_posts,
                'published_posts': published_posts,
                'draft_posts': draft_posts,
                'total_views': total_views,
                'total_comments': total_comments,
                'top_posts': top_posts,
                'generated_at': timezone.now().isoformat(),
            }
            cache.set(cache_key, stats, 300)
            return stats
        except Exception as e:
            logger.error(f"Error getting blog statistics: {e}", exc_info=True)
            return {}

    # ────────────────────────────────────────────────────
    # SCHEDULED PUBLISHING
    # ────────────────────────────────────────────────────

    @staticmethod
    def publish_scheduled_posts() -> int:
        """Publish all scheduled posts whose time has come."""
        from api.cms.models_new.blog import BlogPost
        now = timezone.now()
        posts = BlogPost.objects.filter(
            status='scheduled',
            scheduled_at__lte=now,
            is_active=True
        )
        count = 0
        for post in posts:
            try:
                post.status = 'published'
                post.published_at = post.scheduled_at
                post.save(update_fields=['status', 'published_at'])
                count += 1
            except Exception as e:
                logger.error(f"Error publishing scheduled post {post.id}: {e}")
        logger.info(f"Published {count} scheduled posts")
        return count

    # ────────────────────────────────────────────────────
    # CATEGORY MANAGEMENT
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_categories_with_post_counts() -> List[Dict]:
        """Get all blog categories with post counts."""
        from api.cms.models_new.blog import BlogCategory
        cache_key = 'blog_categories_counts'
        result = cache.get(cache_key)
        if result is None:
            categories = (
                BlogCategory.objects.filter(is_active=True)
                .annotate(published_count=Count(
                    'blog_posts',
                    filter=Q(blog_posts__status='published', blog_posts__is_active=True)
                ))
                .order_by('sort_order', 'name')
            )
            result = [
                {
                    'id': cat.id,
                    'name': cat.name,
                    'slug': cat.slug,
                    'icon': cat.icon,
                    'post_count': cat.published_count,
                    'parent_id': cat.parent_id,
                }
                for cat in categories
            ]
            cache.set(cache_key, result, 1800)
        return result

    @staticmethod
    def create_category(name: str, parent=None, **kwargs) -> Optional[Any]:
        """Create a new blog category."""
        from api.cms.models_new.blog import BlogCategory
        try:
            slug = slugify(name)
            counter = 1
            base_slug = slug
            while BlogCategory.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            cat = BlogCategory.objects.create(name=name, slug=slug, parent=parent, **kwargs)
            return cat
        except Exception as e:
            logger.error(f"Error creating blog category: {e}", exc_info=True)
            return None

    # ────────────────────────────────────────────────────
    # TAG MANAGEMENT
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_or_create_tag(name: str) -> Any:
        """Get or create a blog tag."""
        from api.cms.models_new.blog import BlogTag
        slug = slugify(name)
        tag, _ = BlogTag.objects.get_or_create(slug=slug, defaults={'name': name})
        return tag

    @staticmethod
    def get_popular_tags(limit: int = 20) -> List:
        """Get popular tags by usage count."""
        from api.cms.models_new.blog import BlogTag
        return list(BlogTag.objects.filter(is_active=True).order_by('-usage_count')[:limit])

    @staticmethod
    def clean_unused_tags() -> int:
        """Remove tags with zero usage."""
        from api.cms.models_new.blog import BlogTag
        deleted, _ = BlogTag.objects.filter(usage_count=0).delete()
        logger.info(f"Deleted {deleted} unused blog tags")
        return deleted
