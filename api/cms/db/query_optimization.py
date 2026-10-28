# cms/db/query_optimization.py
"""
Database Query Optimization Patterns

Provides utilities and patterns for eliminating N+1 queries and optimizing database access.

Patterns included:
- select_related() for ForeignKey relationships
- prefetch_related() for reverse relationships
- Annotated querysets for aggregations
- Query analysis and debugging
- Bulk operations
- Caching strategies

All patterns focus on:
1. Reducing number of queries
2. Reducing query complexity
3. Improving response time
4. Minimizing memory usage
"""

from django.db.models import (
    QuerySet, Prefetch, Q, F, Case, When, Value, CharField,
    Count, Sum, Avg, Max, Min, Q, Model, DecimalField
)
from django.db.models.expressions import Window
from django.db.models.functions import RowNumber, Rank, DenseRank
from typing import List, Dict, Any, Tuple, Optional, Type
import logging

logger = logging.getLogger('cms.db.optimization')


# ─────────────────────────────────────────────────────────────────────────────
# QUERY OPTIMIZATION MIXIN
# ─────────────────────────────────────────────────────────────────────────────

class OptimizedQuerySetMixin:
    """
    Mixin to add query optimization methods to managers
    
    Usage:
        class BlogPostManager(OptimizedQuerySetMixin, models.Manager):
            pass
        
        class BlogPost(models.Model):
            objects = BlogPostManager()
        
        # Use optimized queries
        posts = BlogPost.objects.with_author().with_comments()
    """
    
    def with_select_related(self, *fields) -> QuerySet:
        """
        Apply select_related() for ForeignKey optimization
        
        Example: queryset.with_select_related('author', 'category')
        """
        return self.select_related(*fields)
    
    def with_prefetch_related(self, *fields) -> QuerySet:
        """
        Apply prefetch_related() for reverse relationship optimization
        
        Example: queryset.with_prefetch_related('comments', 'tags')
        """
        return self.prefetch_related(*fields)
    
    def optimized(self) -> QuerySet:
        """
        Apply standard optimizations for this model
        
        Override in subclass for model-specific optimizations
        """
        return self


# ─────────────────────────────────────────────────────────────────────────────
# BLOG POST QUERY OPTIMIZATION EXAMPLES
# ─────────────────────────────────────────────────────────────────────────────

class OptimizedBlogQuerySet(QuerySet):
    """Optimized QuerySet for BlogPost"""
    
    def with_author(self):
        """Include author in single query"""
        return self.select_related('author')
    
    def with_category(self):
        """Include category in single query"""
        return self.select_related('category')
    
    def with_comments(self):
        """Include comments with prefetch"""
        comments_prefetch = Prefetch(
            'comments',
            queryset=self.model.comments.filter(is_approved=True)
        )
        return self.prefetch_related(comments_prefetch)
    
    def with_seo(self):
        """Include SEO config if exists"""
        return self.select_related('seo_config')
    
    def with_tags(self):
        """Include tags with many-to-many optimization"""
        return self.prefetch_related('tags__tag')
    
    def published(self):
        """Only published posts"""
        return self.filter(is_published=True)
    
    def featured(self):
        """Only featured posts"""
        return self.filter(is_featured=True)
    
    def optimized_list(self):
        """Optimized for list view"""
        return (
            self.with_author()
            .with_category()
            .with_seo()
            .only(
                'id', 'title', 'slug', 'excerpt', 'featured_image',
                'author_id', 'category_id', 'view_count', 'created_at'
            )
        )
    
    def optimized_detail(self):
        """Optimized for detail view"""
        return (
            self.with_author()
            .with_category()
            .with_comments()
            .with_seo()
            .with_tags()
        )
    
    def with_comment_count(self):
        """Include comment count"""
        return self.annotate(
            comment_count=Count('comments', filter=Q(comments__is_approved=True))
        )
    
    def with_engagement_stats(self):
        """Include view, like, share counts"""
        return self.annotate(
            engagement_total=F('view_count') + F('like_count') + F('share_count')
        )


# ─────────────────────────────────────────────────────────────────────────────
# WITHDRAWAL REQUEST QUERY OPTIMIZATION
# ─────────────────────────────────────────────────────────────────────────────

class OptimizedWithdrawalQuerySet(QuerySet):
    """Optimized QuerySet for WithdrawalRequest"""
    
    def with_user(self):
        """Include user details"""
        return self.select_related('user')
    
    def with_payment_info(self):
        """Include payment gateway"""
        return self.select_related('payment_gateway')
    
    def with_verification(self):
        """Include verification data"""
        return self.select_related('verification_request')
    
    def optimized_list(self):
        """Optimized for withdrawal list"""
        return (
            self.with_user()
            .with_payment_info()
            .only(
                'id', 'user_id', 'amount', 'status', 'created_at',
                'payment_gateway_id'
            )
        )
    
    def optimized_detail(self):
        """Optimized for withdrawal detail"""
        return (
            self.with_user()
            .with_payment_info()
            .with_verification()
        )
    
    def pending(self):
        """Only pending withdrawals"""
        return self.filter(status='pending')
    
    def approved(self):
        """Only approved withdrawals"""
        return self.filter(status='approved')
    
    def by_user(self, user):
        """Filter by user"""
        return self.filter(user=user).with_user()
    
    def with_status_counts(self):
        """Include status counts"""
        return self.values('status').annotate(count=Count('id'))
    
    def with_user_total(self):
        """Include total amount per user"""
        return self.values('user_id').annotate(
            total=Sum('amount'),
            count=Count('id')
        )


# ─────────────────────────────────────────────────────────────────────────────
# LEADERBOARD QUERY OPTIMIZATION
# ─────────────────────────────────────────────────────────────────────────────

class OptimizedLeaderboardQuerySet(QuerySet):
    """Optimized QuerySet for Leaderboard"""
    
    def with_user(self):
        """Include user details"""
        return self.select_related('user')
    
    def with_ranking(self):
        """Include dense rank window function"""
        return self.annotate(
            dense_rank=Window(
                expression=DenseRank(),
                order_by=F('total_points').desc()
            )
        )
    
    def top_earners(self, limit: int = 100):
        """Get top earners with ranking"""
        return (
            self.with_user()
            .filter(is_active=True)
            .with_ranking()
            .order_by('-total_points')[:limit]
        )
    
    def user_rank(self, user):
        """Get user's rank"""
        return (
            self.with_ranking()
            .filter(user=user)
            .values('dense_rank', 'total_points')
            .first()
        )
    
    def optimized_list(self):
        """Optimized for list view"""
        return (
            self.with_user()
            .only(
                'id', 'user_id', 'total_points', 'rank_position',
                'user__username', 'user__avatar'
            )
        )


# ─────────────────────────────────────────────────────────────────────────────
# SURVEY QUERY OPTIMIZATION
# ─────────────────────────────────────────────────────────────────────────────

class OptimizedSurveyQuerySet(QuerySet):
    """Optimized QuerySet for Survey"""
    
    def with_questions(self):
        """Include survey questions"""
        return self.prefetch_related('questions')
    
    def with_responses(self):
        """Include user responses"""
        return self.prefetch_related('responses')
    
    def with_completion_count(self):
        """Include completion count"""
        return self.annotate(
            completion_count=Count('responses', distinct=True)
        )
    
    def with_completion_rate(self):
        """Include estimated completion rate"""
        return self.annotate(
            estimated_rate=Case(
                When(
                    completion_count__gt=0,
                    then=F('completion_count')
                ),
                default=Value(0),
                output_field=DecimalField()
            )
        )
    
    def optimized_list(self):
        """Optimized for list view"""
        return (
            self.only('id', 'title', 'reward_amount', 'is_active')
            .with_completion_count()
        )
    
    def optimized_detail(self):
        """Optimized for detail view"""
        return (
            self.with_questions()
            .with_responses()
            .with_completion_count()
        )
    
    def active(self):
        """Only active surveys"""
        return self.filter(is_active=True)


# ─────────────────────────────────────────────────────────────────────────────
# QUERY ANALYSIS & DEBUGGING
# ─────────────────────────────────────────────────────────────────────────────

class QueryAnalyzer:
    """
    Analyze and debug database queries
    
    Usage:
        analyzer = QueryAnalyzer()
        analyzer.start()
        
        # ... execute code ...
        
        stats = analyzer.end()
        print(stats)
    """
    
    def __init__(self):
        """Initialize analyzer"""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        
        self.connection = connection
        self.context = CaptureQueriesContext(self.connection)
        self.queries = []
        self.start_time = None
    
    def start(self):
        """Start capturing queries"""
        self.context.__enter__()
        import time
        self.start_time = time.time()
    
    def end(self) -> Dict[str, Any]:
        """Stop capturing and analyze"""
        import time
        elapsed_time = time.time() - self.start_time
        
        self.context.__exit__(None, None, None)
        self.queries = self.context.captured_queries
        
        return self.get_stats(elapsed_time)
    
    def get_stats(self, elapsed_time: float) -> Dict[str, Any]:
        """Get query statistics"""
        
        # Count queries by type
        select_count = sum(1 for q in self.queries if q['sql'].strip().upper().startswith('SELECT'))
        insert_count = sum(1 for q in self.queries if q['sql'].strip().upper().startswith('INSERT'))
        update_count = sum(1 for q in self.queries if q['sql'].strip().upper().startswith('UPDATE'))
        delete_count = sum(1 for q in self.queries if q['sql'].strip().upper().startswith('DELETE'))
        
        # Get slowest queries
        slowest = sorted(
            self.queries,
            key=lambda q: float(q['time']),
            reverse=True
        )[:5]
        
        return {
            'total_queries': len(self.queries),
            'select_queries': select_count,
            'insert_queries': insert_count,
            'update_queries': update_count,
            'delete_queries': delete_count,
            'total_time': sum(float(q['time']) for q in self.queries),
            'elapsed_time': elapsed_time,
            'slowest_queries': [
                {
                    'time': q['time'],
                    'sql': q['sql'][:100] + '...' if len(q['sql']) > 100 else q['sql'],
                }
                for q in slowest
            ],
            'queries': self.queries,
        }
    
    def print_stats(self, elapsed_time: float = None):
        """Print statistics"""
        stats = self.get_stats(elapsed_time or 0)
        
        print(f"""
╔════════════════════════════════════════════════════════════╗
║                   QUERY STATISTICS                         ║
╚════════════════════════════════════════════════════════════╝

Total Queries: {stats['total_queries']}
  - SELECT: {stats['select_queries']}
  - INSERT: {stats['insert_queries']}
  - UPDATE: {stats['update_queries']}
  - DELETE: {stats['delete_queries']}

Total Query Time: {stats['total_time']:.3f}s
Elapsed Time: {stats['elapsed_time']:.3f}s

Slowest Queries:
""")
        for i, query in enumerate(stats['slowest_queries'], 1):
            print(f"{i}. {query['time']:.3f}s - {query['sql']}")


# ─────────────────────────────────────────────────────────────────────────────
# BULK OPERATION PATTERNS
# ─────────────────────────────────────────────────────────────────────────────

class BulkOperations:
    """Helper for efficient bulk operations"""
    
    @staticmethod
    def bulk_create(model_class: Type[Model], objects: List[Any],
                   batch_size: int = 1000) -> List[Any]:
        """
        Efficiently create many objects
        
        Args:
            model_class: Django model class
            objects: List of model instances
            batch_size: Batch size for creation
            
        Returns:
            Created objects
        """
        logger.info(f"Bulk creating {len(objects)} {model_class.__name__} objects")
        
        created = []
        for i in range(0, len(objects), batch_size):
            batch = objects[i:i + batch_size]
            created.extend(model_class.objects.bulk_create(batch))
        
        logger.info(f"Created {len(created)} objects")
        return created
    
    @staticmethod
    def bulk_update(objects: List[Any], fields: List[str],
                   batch_size: int = 1000) -> int:
        """
        Efficiently update many objects
        
        Args:
            objects: List of model instances
            fields: Fields to update
            batch_size: Batch size for updates
            
        Returns:
            Number of updated objects
        """
        logger.info(f"Bulk updating {len(objects)} objects")
        
        updated = 0
        for i in range(0, len(objects), batch_size):
            batch = objects[i:i + batch_size]
            updated += len(batch)
            model_class = batch[0].__class__
            model_class.objects.bulk_update(batch, fields)
        
        logger.info(f"Updated {updated} objects")
        return updated
    
    @staticmethod
    def bulk_delete(queryset: QuerySet, batch_size: int = 1000) -> int:
        """
        Efficiently delete many objects
        
        Args:
            queryset: QuerySet to delete
            batch_size: Batch size for deletion
            
        Returns:
            Number of deleted objects
        """
        logger.info(f"Bulk deleting objects")
        
        total_deleted = 0
        
        while True:
            # Get batch
            pk_list = list(queryset[:batch_size].values_list('pk', flat=True))
            
            if not pk_list:
                break
            
            # Delete batch
            deleted, _ = queryset.model.objects.filter(pk__in=pk_list).delete()
            total_deleted += deleted
        
        logger.info(f"Deleted {total_deleted} objects")
        return total_deleted


# ─────────────────────────────────────────────────────────────────────────────
# CACHING PATTERNS
# ─────────────────────────────────────────────────────────────────────────────

class CachingPatterns:
    """Common caching patterns for queries"""
    
    @staticmethod
    def cache_or_fetch(cache_key: str, fetch_callable, ttl: int = 3600):
        """
        Get from cache or fetch from database
        
        Args:
            cache_key: Cache key
            fetch_callable: Function to fetch data
            ttl: Time to live in seconds
            
        Returns:
            Cached or freshly fetched data
        """
        from django.core.cache import cache
        
        # Try cache
        data = cache.get(cache_key)
        if data is not None:
            logger.debug(f"Cache HIT: {cache_key}")
            return data
        
        # Cache miss - fetch
        logger.debug(f"Cache MISS: {cache_key}")
        data = fetch_callable()
        cache.set(cache_key, data, ttl)
        
        return data
    
    @staticmethod
    def warmup_cache(cache_key: str, fetch_callable, ttl: int = 3600):
        """Pre-populate cache"""
        from django.core.cache import cache
        
        data = fetch_callable()
        cache.set(cache_key, data, ttl)
        logger.info(f"Warmed cache: {cache_key}")


# Export public API
__all__ = [
    'OptimizedQuerySetMixin',
    'OptimizedBlogQuerySet',
    'OptimizedWithdrawalQuerySet',
    'OptimizedLeaderboardQuerySet',
    'OptimizedSurveyQuerySet',
    'QueryAnalyzer',
    'BulkOperations',
    'CachingPatterns',
]
