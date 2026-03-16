import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg, F, Window
from django.db.models.functions import TruncDate, RowNumber
from django.core.cache import cache
from django.core.paginator import Paginator
from django.conf import settings
import pandas as pd
from io import StringIO, BytesIO
import csv

from ..models import (
    ContentCategory, ContentPage, ContentViewLog, 
    ContentShare, Banner, FAQ
)
from api.users.models import User
from api.wallet.models import Transaction
# from api.tasks.models import TaskCompletion
# from api.offerwall.models import OfferCompletion

logger = logging.getLogger(__name__)


class ContentService:
    """Service class for content management business logic"""
    
    @staticmethod
    def get_published_content(
        category_id: Optional[int] = None,
        page_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        language: str = 'en',
        limit: int = 20,
        offset: int = 0,
        user: Optional[User] = None
    ) -> Tuple[List[ContentPage], int]:
        """
        Get published content with filtering and pagination
        
        Args:
            category_id: Filter by category ID
            page_type: Filter by page type
            tags: Filter by tags
            language: Content language
            limit: Number of items per page
            offset: Offset for pagination
            user: User object for permission filtering
            
        Returns:
            Tuple of (content_list, total_count)
        """
        try:
            query = Q(
                status='published',
                is_active=True,
                published_date__lte=timezone.now()
            )
            
            # Filter by visibility based on user authentication
            if user and user.is_authenticated:
                query &= Q(visibility__in=['public', 'authenticated'])
            else:
                query &= Q(visibility='public')
            
            # Apply additional filters
            if category_id:
                query &= Q(category_id=category_id)
            
            if page_type:
                query &= Q(page_type=page_type)
            
            if tags:
                tag_query = Q()
                for tag in tags:
                    tag_query |= Q(tags__contains=[tag])
                query &= tag_query
            
            if language:
                query &= Q(language=language)
            
            # Get total count
            total_count = ContentPage.objects.filter(query).count()
            
            # Get paginated results
            content = ContentPage.objects.filter(query)\
                .select_related('category', 'author')\
                .prefetch_related('related_pages')\
                .order_by('-published_date', '-created_at')\
                [offset:offset + limit]
            
            return list(content), total_count
            
        except Exception as e:
            logger.error(f"Error getting published content: {str(e)}")
            return [], 0
    
    @staticmethod
    def get_featured_content(
        limit: int = 10,
        language: str = 'en'
    ) -> List[ContentPage]:
        """
        Get featured content
        
        Args:
            limit: Number of items to return
            language: Content language
            
        Returns:
            List of featured content
        """
        cache_key = f'featured_content_{language}_{limit}'
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        try:
            featured = ContentPage.objects.filter(
                is_featured=True,
                status='published',
                is_active=True,
                published_date__lte=timezone.now(),
                language=language
            ).select_related('category', 'author')\
             .order_by('-published_date')\
             [:limit]
            
            cache.set(cache_key, list(featured), 1800)  # Cache for 30 minutes
            return list(featured)
            
        except Exception as e:
            logger.error(f"Error getting featured content: {str(e)}")
            return []
    
    @staticmethod
    def get_popular_content(
        days: int = 30,
        limit: int = 10,
        language: str = 'en'
    ) -> List[ContentPage]:
        """
        Get popular content based on views
        
        Args:
            days: Number of days to look back
            limit: Number of items to return
            language: Content language
            
        Returns:
            List of popular content
        """
        cache_key = f'popular_content_{language}_{days}_{limit}'
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            popular = ContentPage.objects.filter(
                status='published',
                is_active=True,
                published_date__gte=cutoff_date,
                published_date__lte=timezone.now(),
                language=language
            ).annotate(
                recent_views=Count(
                    'view_logs',
                    filter=Q(view_logs__created_at__gte=cutoff_date)
                )
            ).order_by('-recent_views', '-view_count')\
             .select_related('category', 'author')\
             [:limit]
            
            cache.set(cache_key, list(popular), 1800)  # Cache for 30 minutes
            return list(popular)
            
        except Exception as e:
            logger.error(f"Error getting popular content: {str(e)}")
            return []
    
    @staticmethod
    def get_content_by_slug(
        slug: str,
        language: str = 'en',
        user: Optional[User] = None
    ) -> Optional[ContentPage]:
        """
        Get content by slug with permission check
        
        Args:
            slug: Content slug
            language: Content language
            user: User object for permission check
            
        Returns:
            ContentPage object or None
        """
        try:
            content = ContentPage.objects.select_related(
                'category', 'author', 'related_offer', 'related_task'
            ).prefetch_related('related_pages').get(
                slug=slug,
                language=language
            )
            
            # Check permissions
            if not ContentService.can_view_content(content, user):
                return None
            
            return content
            
        except ContentPage.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting content by slug: {str(e)}")
            return None
    
    @staticmethod
    def can_view_content(content: ContentPage, user: Optional[User]) -> bool:
        """
        Check if user can view content
        
        Args:
            content: ContentPage object
            user: User object
            
        Returns:
            Boolean indicating if user can view
        """
        # Check if content is active and published
        if not content.is_active or content.status != 'published':
            return False
        
        # Check published date
        if content.published_date and content.published_date > timezone.now():
            return False
        
        # Check visibility
        if content.visibility == 'public':
            return True
        elif content.visibility == 'authenticated':
            return user and user.is_authenticated
        elif content.visibility == 'vip':
            return user and user.is_authenticated and user.is_vip
        elif content.visibility == 'admin':
            return user and user.is_authenticated and user.is_staff
        
        return False
    
    @staticmethod
    def record_content_view(
        content: ContentPage,
        user: Optional[User] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        referrer: Optional[str] = None,
        duration: int = 0
    ) -> bool:
        """
        Record a content view
        
        Args:
            content: ContentPage object
            user: User who viewed
            ip_address: Viewer's IP address
            user_agent: User agent string
            referrer: Referrer URL
            duration: View duration in seconds
            
        Returns:
            Boolean indicating success
        """
        try:
            with transaction.atomic():
                # Create view log
                view_log = ContentViewLog.objects.create(
                    content=content,
                    user=user,
                    view_duration=duration,
                    is_completed=duration >= 30,  # Mark as completed if viewed for 30+ seconds
                    ip_address=ip_address,
                    user_agent=user_agent,
                    referrer=referrer
                )
                
                # Increment view count
                ContentPage.objects.filter(id=content.id).update(
                    view_count=F('view_count') + 1
                )
                
                # Clear cache for popular content
                cache.delete_pattern('popular_content_*')
                
                return True
                
        except Exception as e:
            logger.error(f"Error recording content view: {str(e)}")
            return False
    
    @staticmethod
    def record_content_share(
        content: ContentPage,
        user: Optional[User] = None,
        platform: str = 'other',
        share_url: str = ''
    ) -> bool:
        """
        Record a content share
        
        Args:
            content: ContentPage object
            user: User who shared
            platform: Sharing platform
            share_url: Shared URL
            
        Returns:
            Boolean indicating success
        """
        try:
            with transaction.atomic():
                # Create share log
                ContentShare.objects.create(
                    content=content,
                    user=user,
                    share_platform=platform,
                    share_url=share_url
                )
                
                # Increment share count
                ContentPage.objects.filter(id=content.id).update(
                    share_count=F('share_count') + 1
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error recording content share: {str(e)}")
            return False
    
    @staticmethod
    def get_content_analytics(
        content_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get analytics for specific content
        
        Args:
            content_id: Content ID
            start_date: Start date for analytics
            end_date: End date for analytics
            
        Returns:
            Dictionary with analytics data
        """
        try:
            if not start_date:
                start_date = timezone.now() - timedelta(days=30)
            if not end_date:
                end_date = timezone.now()
            
            content = ContentPage.objects.get(id=content_id)
            
            # Get view logs in date range
            view_logs = ContentViewLog.objects.filter(
                content=content,
                created_at__range=(start_date, end_date)
            )
            
            # Calculate metrics
            total_views = view_logs.count()
            unique_views = view_logs.values('ip_address').distinct().count()
            avg_duration = view_logs.aggregate(avg=Avg('view_duration'))['avg'] or 0
            completion_rate = view_logs.filter(is_completed=True).count() / total_views if total_views > 0 else 0
            
            # Get shares
            shares = ContentShare.objects.filter(
                content=content,
                created_at__range=(start_date, end_date)
            ).count()
            
            # Get daily breakdown
            daily_stats = view_logs.annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                views=Count('id'),
                unique_views=Count('ip_address', distinct=True),
                avg_duration=Avg('view_duration'),
                shares=Count('content__shares')
            ).order_by('date')
            
            return {
                'content_id': content.id,
                'content_title': content.title,
                'period': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'overview': {
                    'total_views': total_views,
                    'unique_views': unique_views,
                    'average_duration': round(avg_duration, 2),
                    'completion_rate': round(completion_rate * 100, 2),
                    'total_shares': shares
                },
                'daily_stats': list(daily_stats)
            }
            
        except Exception as e:
            logger.error(f"Error getting content analytics: {str(e)}")
            return {}
    
    @staticmethod
    def get_user_content_interactions(user: User) -> Dict[str, Any]:
        """
        Get user's content interactions
        
        Args:
            user: User object
            
        Returns:
            Dictionary with user interactions
        """
        try:
            # Get viewed content
            viewed_content = ContentViewLog.objects.filter(
                user=user
            ).select_related('content').order_by('-created_at')[:50]
            
            # Get shared content
            shared_content = ContentShare.objects.filter(
                user=user
            ).select_related('content').order_by('-created_at')[:20]
            
            # Calculate statistics
            total_views = viewed_content.count()
            total_time = sum(log.view_duration for log in viewed_content)
            completed_content = viewed_content.filter(is_completed=True).count()
            
            return {
                'user_id': user.id,
                'statistics': {
                    'total_views': total_views,
                    'total_time_spent': total_time,
                    'average_time_per_view': total_time / total_views if total_views > 0 else 0,
                    'completion_rate': completed_content / total_views if total_views > 0 else 0,
                    'total_shares': shared_content.count()
                },
                'recently_viewed': [
                    {
                        'content_id': log.content.id,
                        'title': log.content.title,
                        'viewed_at': log.created_at,
                        'duration': log.view_duration,
                        'completed': log.is_completed
                    }
                    for log in viewed_content[:10]
                ],
                'recently_shared': [
                    {
                        'content_id': share.content.id,
                        'title': share.content.title,
                        'shared_at': share.created_at,
                        'platform': share.share_platform
                    }
                    for share in shared_content[:10]
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting user content interactions: {str(e)}")
            return {}
    
    @staticmethod
    def search_content(
        query: str,
        category_id: Optional[int] = None,
        page_type: Optional[str] = None,
        language: str = 'en',
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Search content with full-text search
        
        Args:
            query: Search query
            category_id: Filter by category
            page_type: Filter by page type
            language: Content language
            limit: Results per page
            offset: Pagination offset
            
        Returns:
            Tuple of (results, total_count)
        """
        try:
            search_query = Q(
                status='published',
                is_active=True,
                published_date__lte=timezone.now(),
                language=language
            )
            
            # Apply text search
            if query:
                text_query = Q(
                    Q(title__icontains=query) |
                    Q(subtitle__icontains=query) |
                    Q(excerpt__icontains=query) |
                    Q(content__icontains=query) |
                    Q(tags__contains=[query])
                )
                search_query &= text_query
            
            # Apply filters
            if category_id:
                search_query &= Q(category_id=category_id)
            
            if page_type:
                search_query &= Q(page_type=page_type)
            
            # Get total count
            total_count = ContentPage.objects.filter(search_query).count()
            
            # Get results
            results = ContentPage.objects.filter(search_query)\
                .select_related('category', 'author')\
                .order_by('-published_date')\
                [offset:offset + limit]
            
            # Format results with relevance score
            formatted_results = []
            for content in results:
                relevance_score = ContentService._calculate_relevance_score(content, query)
                formatted_results.append({
                    'id': content.id,
                    'title': content.title,
                    'slug': content.slug,
                    'excerpt': content.excerpt,
                    'category': content.category.name if content.category else None,
                    'published_date': content.published_date,
                    'view_count': content.view_count,
                    'relevance_score': relevance_score
                })
            
            # Sort by relevance score
            formatted_results.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            return formatted_results, total_count
            
        except Exception as e:
            logger.error(f"Error searching content: {str(e)}")
            return [], 0
    
    @staticmethod
    def _calculate_relevance_score(content: ContentPage, query: str) -> float:
        """
        Calculate relevance score for search results
        
        Args:
            content: ContentPage object
            query: Search query
            
        Returns:
            Relevance score (0-100)
        """
        if not query:
            return 0
        
        query = query.lower()
        score = 0
        
        # Check title (highest weight)
        if query in content.title.lower():
            score += 50
        elif any(word in content.title.lower() for word in query.split()):
            score += 30
        
        # Check subtitle
        if content.subtitle and query in content.subtitle.lower():
            score += 20
        
        # Check excerpt
        if content.excerpt and query in content.excerpt.lower():
            score += 15
        
        # Check content
        if query in content.content.lower():
            score += 10
        
        # Check tags
        if content.tags and any(query in tag.lower() for tag in content.tags):
            score += 25
        
        # Boost for recency
        days_old = (timezone.now() - content.published_date).days if content.published_date else 365
        if days_old <= 7:
            score += 20
        elif days_old <= 30:
            score += 10
        
        # Boost for popularity
        if content.view_count > 1000:
            score += 15
        elif content.view_count > 100:
            score += 5
        
        return min(score, 100)
    
    @staticmethod
    def create_content_version(
        original_content: ContentPage,
        new_content_data: Dict[str, Any],
        user: User
    ) -> Optional[ContentPage]:
        """
        Create a new version of content
        
        Args:
            original_content: Original ContentPage object
            new_content_data: New content data
            user: User creating the version
            
        Returns:
            New ContentPage version or None
        """
        try:
            with transaction.atomic():
                # Create new version
                new_version = ContentPage.objects.create(
                    parent_version=original_content,
                    version=original_content.version + 1,
                    
                    # Copy fields from original
                    title=original_content.title,
                    slug=original_content.slug,
                    subtitle=original_content.subtitle,
                    category=original_content.category,
                    page_type=original_content.page_type,
                    tags=original_content.tags,
                    excerpt=original_content.excerpt,
                    content=original_content.content,
                    featured_image=original_content.featured_image,
                    thumbnail=original_content.thumbnail,
                    author=original_content.author,
                    status='archived',
                    visibility=original_content.visibility,
                    is_active=original_content.is_active,
                    is_featured=original_content.is_featured,
                    is_pinned=original_content.is_pinned,
                    allow_comments=original_content.allow_comments,
                    published_date=original_content.published_date,
                    expiry_date=original_content.expiry_date,
                    meta_title=original_content.meta_title,
                    meta_description=original_content.meta_description,
                    meta_keywords=original_content.meta_keywords,
                    canonical_url=original_content.canonical_url,
                    related_offer=original_content.related_offer,
                    related_task=original_content.related_task,
                    min_reward=original_content.min_reward,
                    max_reward=original_content.max_reward,
                    reward_currency=original_content.reward_currency,
                    completion_time=original_content.completion_time,
                    difficulty_level=original_content.difficulty_level,
                    requirements=original_content.requirements,
                    language=original_content.language,
                    is_translation=original_content.is_translation,
                    original_content=original_content.original_content,
                    
                    # Copy statistics
                    view_count=original_content.view_count,
                    share_count=original_content.share_count,
                    like_count=original_content.like_count,
                    comment_count=original_content.comment_count
                )
                
                # Archive original
                original_content.status = 'archived'
                original_content.save()
                
                logger.info(f"Created new version {new_version.version} for content {original_content.id}")
                return new_version
                
        except Exception as e:
            logger.error(f"Error creating content version: {str(e)}")
            return None
    
    @staticmethod
    def bulk_update_status(
        content_ids: List[int],
        status: str,
        publish_date: Optional[datetime] = None,
        user: Optional[User] = None
    ) -> int:
        """
        Bulk update content status
        
        Args:
            content_ids: List of content IDs
            status: New status
            publish_date: Publication date (if publishing)
            user: User performing the action
            
        Returns:
            Number of updated records
        """
        try:
            with transaction.atomic():
                update_data = {'status': status}
                
                if status == 'published' and publish_date:
                    update_data['published_date'] = publish_date
                elif status == 'published':
                    update_data['published_date'] = timezone.now()
                
                updated = ContentPage.objects.filter(
                    id__in=content_ids
                ).update(**update_data)
                
                # Log the action
                if user:
                    logger.info(f"User {user.id} bulk updated {updated} content items to status {status}")
                
                # Clear cache
                cache.delete_pattern('*content*')
                
                return updated
                
        except Exception as e:
            logger.error(f"Error bulk updating content status: {str(e)}")
            return 0
    
    @staticmethod
    def bulk_assign_category(
        content_ids: List[int],
        category_id: int,
        remove_existing: bool = False
    ) -> int:
        """
        Bulk assign category to content
        
        Args:
            content_ids: List of content IDs
            category_id: Category ID to assign
            remove_existing: Remove existing categories if True
            
        Returns:
            Number of updated records
        """
        try:
            with transaction.atomic():
                if remove_existing:
                    updated = ContentPage.objects.filter(
                        id__in=content_ids
                    ).update(category_id=category_id)
                else:
                    # Only update content without category
                    updated = ContentPage.objects.filter(
                        id__in=content_ids,
                        category__isnull=True
                    ).update(category_id=category_id)
                
                # Clear cache
                cache.delete_pattern('*content*')
                
                return updated
                
        except Exception as e:
            logger.error(f"Error bulk assigning category: {str(e)}")
            return 0
    
    @staticmethod
    def import_content(
        file,
        import_type: str = 'json',
        overwrite: bool = False,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """
        Import content from file
        
        Args:
            file: File object to import
            import_type: Type of file (json, csv, excel)
            overwrite: Overwrite existing content
            user: User performing import
            
        Returns:
            Dictionary with import results
        """
        results = {
            'imported_count': 0,
            'skipped_count': 0,
            'errors': []
        }
        
        try:
            if import_type == 'json':
                data = json.load(file)
                items = data.get('content', [])
            elif import_type == 'csv':
                csv_data = StringIO(file.read().decode('utf-8'))
                reader = csv.DictReader(csv_data)
                items = list(reader)
            elif import_type == 'excel':
                df = pd.read_excel(file)
                items = df.to_dict('records')
            else:
                raise ValueError(f"Unsupported import type: {import_type}")
            
            with transaction.atomic():
                for item in items:
                    try:
                        # Extract data based on import type
                        if import_type == 'json':
                            content_data = item
                        else:
                            content_data = ContentService._map_import_data(item)
                        
                        # Check if content exists
                        slug = content_data.get('slug')
                        language = content_data.get('language', 'en')
                        
                        existing = ContentPage.objects.filter(
                            slug=slug, language=language
                        ).first()
                        
                        if existing and not overwrite:
                            results['skipped_count'] += 1
                            continue
                        
                        # Create or update content
                        if existing and overwrite:
                            for key, value in content_data.items():
                                if hasattr(existing, key):
                                    setattr(existing, key, value)
                            existing.save()
                        else:
                            content_data['author'] = user
                            ContentPage.objects.create(**content_data)
                        
                        results['imported_count'] += 1
                        
                    except Exception as e:
                        error_msg = f"Error importing item {item.get('title', 'Unknown')}: {str(e)}"
                        results['errors'].append(error_msg)
                        logger.error(error_msg)
                
                # Clear cache
                cache.delete_pattern('*content*')
                
                return results
                
        except Exception as e:
            error_msg = f"Error during content import: {str(e)}"
            results['errors'].append(error_msg)
            logger.error(error_msg)
            return results
    
    @staticmethod
    def _map_import_data(item: Dict) -> Dict:
        """
        Map imported data to ContentPage model fields
        
        Args:
            item: Imported data item
            
        Returns:
            Mapped data dictionary
        """
        mapping = {
            'Title': 'title',
            'Slug': 'slug',
            'Content': 'content',
            'Category': 'category_id',
            'Status': 'status',
            'Language': 'language',
            'Published Date': 'published_date'
        }
        
        mapped_data = {}
        for source_key, target_key in mapping.items():
            if source_key in item:
                mapped_data[target_key] = item[source_key]
        
        return mapped_data
    
    @staticmethod
    def export_content(
        content_ids: Optional[List[int]] = None,
        category_ids: Optional[List[int]] = None,
        format: str = 'json',
        include_metadata: bool = True,
        include_statistics: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Export content to specified format
        
        Args:
            content_ids: List of content IDs to export
            category_ids: List of category IDs to export
            format: Export format (json, csv, excel)
            include_metadata: Include metadata in export
            include_statistics: Include statistics in export
            
        Returns:
            List of exported content data
        """
        try:
            query = Q()
            
            if content_ids:
                query &= Q(id__in=content_ids)
            
            if category_ids:
                query &= Q(category_id__in=category_ids)
            
            content = ContentPage.objects.filter(query)\
                .select_related('category', 'author')\
                .order_by('-published_date')
            
            export_data = []
            for item in content:
                data = {
                    'id': item.id,
                    'title': item.title,
                    'slug': item.slug,
                    'content': item.content,
                    'status': item.status,
                    'published_date': item.published_date.isoformat() if item.published_date else None,
                    'category': item.category.name if item.category else None,
                    'author': item.author.username if item.author else None
                }
                
                if include_metadata:
                    data.update({
                        'excerpt': item.excerpt,
                        'meta_title': item.meta_title,
                        'meta_description': item.meta_description,
                        'meta_keywords': item.meta_keywords,
                        'language': item.language,
                        'tags': item.tags
                    })
                
                if include_statistics:
                    data.update({
                        'view_count': item.view_count,
                        'share_count': item.share_count,
                        'like_count': item.like_count
                    })
                
                export_data.append(data)
            
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting content: {str(e)}")
            return []
    
    @staticmethod
    def get_content_statistics() -> Dict[str, Any]:
        """
        Get overall content statistics
        
        Returns:
            Dictionary with statistics
        """
        cache_key = 'content_statistics'
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        try:
            # Total counts
            total_pages = ContentPage.objects.count()
            published_pages = ContentPage.objects.filter(status='published').count()
            draft_pages = ContentPage.objects.filter(status='draft').count()
            
            # View statistics
            total_views = ContentPage.objects.aggregate(total=Sum('view_count'))['total'] or 0
            average_views = ContentPage.objects.filter(view_count__gt=0)\
                .aggregate(avg=Avg('view_count'))['avg'] or 0
            
            # Recent content
            recent_content = ContentPage.objects.filter(
                status='published'
            ).order_by('-published_date')[:5]
            
            # Popular content
            popular_content = ContentPage.objects.filter(
                status='published'
            ).order_by('-view_count')[:5]
            
            # Category distribution
            category_dist = ContentCategory.objects.annotate(
                content_count=Count('pages')
            ).values('name', 'content_count').order_by('-content_count')[:10]
            
            stats = {
                'total_pages': total_pages,
                'published_pages': published_pages,
                'draft_pages': draft_pages,
                'total_views': total_views,
                'average_views': round(average_views, 2),
                'top_content': [
                    {
                        'id': c.id,
                        'title': c.title,
                        'views': c.view_count,
                        'published_date': c.published_date
                    }
                    for c in popular_content
                ],
                'recent_content': [
                    {
                        'id': c.id,
                        'title': c.title,
                        'published_date': c.published_date
                    }
                    for c in recent_content
                ],
                'category_distribution': list(category_dist)
            }
            
            cache.set(cache_key, stats, 300)  # Cache for 5 minutes
            return stats
            
        except Exception as e:
            logger.error(f"Error getting content statistics: {str(e)}")
            return {}
    
    @staticmethod
    def get_content_for_user_rewards(user: User) -> List[Dict[str, Any]]:
        """
        Get content that can earn rewards for user
        
        Args:
            user: User object
            
        Returns:
            List of content with reward information
        """
        try:
            # Get content that offers rewards
            reward_content = ContentPage.objects.filter(
                status='published',
                is_active=True,
                published_date__lte=timezone.now(),
                min_reward__gt=0
            ).exclude(
                # Exclude content user has already viewed
                view_logs__user=user,
                view_logs__is_completed=True
            ).select_related('category')\
             .order_by('-min_reward', '-published_date')[:20]
            
            result = []
            for content in reward_content:
                # Check if user meets requirements
                if ContentService._check_content_requirements(content, user):
                    result.append({
                        'id': content.id,
                        'title': content.title,
                        'excerpt': content.excerpt,
                        'min_reward': float(content.min_reward),
                        'max_reward': float(content.max_reward),
                        'currency': content.reward_currency,
                        'completion_time': content.completion_time,
                        'difficulty': content.difficulty_level,
                        'requirements': content.requirements
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting content for user rewards: {str(e)}")
            return []
    
    @staticmethod
    def _check_content_requirements(content: ContentPage, user: User) -> bool:
        """
        Check if user meets content requirements
        
        Args:
            content: ContentPage object
            user: User object
            
        Returns:
            Boolean indicating if requirements are met
        """
        if not content.requirements:
            return True
        
        requirements = content.requirements
        
        # Check user level
        min_level = requirements.get('min_level', 0)
        if user.level < min_level:
            return False
        
        # Check required tasks
        required_tasks = requirements.get('required_tasks', [])
        if required_tasks:
            completed_tasks = TaskCompletion.objects.filter(
                user=user,
                task_id__in=required_tasks,
                status='completed'
            ).values_list('task_id', flat=True)
            
            if not set(required_tasks).issubset(set(completed_tasks)):
                return False
        
        # Check required offers
        required_offers = requirements.get('required_offers', [])
        if required_offers:
            completed_offers = OfferCompletion.objects.filter(
                user=user,
                offer_id__in=required_offers,
                status='completed'
            ).values_list('offer_id', flat=True)
            
            if not set(required_offers).issubset(set(completed_offers)):
                return False
        
        # Check user tags
        required_tags = requirements.get('required_tags', [])
        if required_tags:
            user_tags = user.tags or []
            if not set(required_tags).issubset(set(user_tags)):
                return False
        
        return True
    
    @staticmethod
    def award_content_reward(
        content: ContentPage,
        user: User,
        view_duration: int
    ) -> Optional[Transaction]:
        """
        Award reward for completing content
        
        Args:
            content: ContentPage object
            user: User to award
            view_duration: Duration content was viewed
            
        Returns:
            Transaction object or None
        """
        try:
            # Check if content offers rewards
            if content.min_reward <= 0:
                return None
            
            # Check if user has already been rewarded for this content
            existing_reward = Transaction.objects.filter(
                user=user,
                transaction_type='content_reward',
                metadata__contains={'content_id': content.id}
            ).exists()
            
            if existing_reward:
                return None
            
            # Check if view was completed (30+ seconds or content completion)
            if view_duration < 30 and not content.completion_time:
                return None
            
            # Calculate reward amount
            if content.min_reward == content.max_reward:
                reward_amount = content.min_reward
            else:
                # Calculate based on view duration
                completion_percentage = min(view_duration / (content.completion_time * 60), 1.0)
                reward_amount = content.min_reward + (
                    (content.max_reward - content.min_reward) * completion_percentage
                )
            
            # Create transaction
            transaction = Transaction.objects.create(
                user=user,
                transaction_type='content_reward',
                amount=reward_amount,
                currency=content.reward_currency,
                status='completed',
                description=f"Content reward: {content.title}",
                metadata={
                    'content_id': content.id,
                    'view_duration': view_duration,
                    'completion_percentage': completion_percentage
                }
            )
            
            logger.info(f"Awarded {reward_amount} {content.reward_currency} to user {user.id} for content {content.id}")
            return transaction
            
        except Exception as e:
            logger.error(f"Error awarding content reward: {str(e)}")
            return None