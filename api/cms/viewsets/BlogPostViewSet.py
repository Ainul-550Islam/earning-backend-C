from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/viewsets/BlogPostViewSet.py
"""
BlogPostViewSet: Full CRUD + publish + preview + analytics for blog posts.
"""
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from django.db.models import Q, F
from django.core.cache import cache

logger = logging.getLogger(__name__)


class BlogPostViewSet(viewsets.ModelViewSet):
    """
    ViewSet for BlogPost CRUD, publishing workflow, and preview.

    Endpoints:
        GET    /api/cms/blog/                    - List published posts
        POST   /api/cms/blog/                    - Create post (auth)
        GET    /api/cms/blog/{slug}/             - Retrieve post detail
        PUT    /api/cms/blog/{slug}/             - Update post (auth)
        PATCH  /api/cms/blog/{slug}/             - Partial update (auth)
        DELETE /api/cms/blog/{slug}/             - Delete post (admin)
        POST   /api/cms/blog/{id}/publish/       - Publish post
        POST   /api/cms/blog/{id}/unpublish/     - Unpublish post
        POST   /api/cms/blog/{id}/schedule/      - Schedule post
        GET    /api/cms/blog/{id}/preview/       - Preview (draft)
        POST   /api/cms/blog/bulk_publish/       - Bulk publish
        GET    /api/cms/blog/statistics/         - Blog statistics
        GET    /api/cms/blog/featured/           - Featured posts
        GET    /api/cms/blog/popular/            - Popular posts
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'excerpt', 'body']
    ordering_fields = ['published_at', 'views_count', 'like_count', 'created_at']
    ordering = ['-published_at']
    lookup_field = 'slug'

    def get_queryset(self):
        from api.cms.models_new.blog import BlogPost
        user = self.request.user
        qs = BlogPost.objects.select_related('author', 'category').prefetch_related('tags', 'seo')
        if user.is_staff:
            return qs.all()
        return qs.filter(status='published', is_active=True, published_at__lte=timezone.now())

    def get_serializer_class(self):
        from api.cms.serializers import BlogPostSerializer
        return BlogPostSerializer

    def list(self, request, *args, **kwargs):
        """List blog posts with optional filters."""
        qs = self.get_queryset()
        # Category filter
        cat = request.query_params.get('category')
        if cat:
            qs = qs.filter(category__slug=cat)
        # Tag filter
        tag = request.query_params.get('tag')
        if tag:
            qs = qs.filter(tags__slug=tag)
        # Language filter
        lang = request.query_params.get('language', 'en')
        qs = qs.filter(language=lang)
        # Featured
        featured = request.query_params.get('featured')
        if featured == 'true':
            qs = qs.filter(is_featured=True)

        qs = self.filter_queryset(qs)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """Get blog post and increment view count."""
        instance = self.get_object()
        instance.increment_views()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """Create a new blog post."""
        from api.cms.services_new.BlogService import BlogService
        data = request.data.copy()
        tags = data.pop('tags', [])
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        post = BlogService.create_post(
            author=request.user,
            tags=tags,
            **serializer.validated_data
        )
        if post:
            out = self.get_serializer(post)
            return Response(out.data, status=status.HTTP_201_CREATED)
        return Response({'error': 'Failed to create post'}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        """Update a blog post."""
        from api.cms.services_new.BlogService import BlogService
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        success = BlogService.update_post(instance, dict(serializer.validated_data))
        if success:
            return Response(self.get_serializer(instance).data)
        return Response({'error': 'Update failed'}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """Soft-delete a blog post."""
        from api.cms.services_new.BlogService import BlogService
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        instance = self.get_object()
        BlogService.delete_post(instance, soft=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def publish(self, request, slug=None):
        """Publish a blog post."""
        from api.cms.services_new.BlogService import BlogService
        post = self.get_object()
        if not request.user.is_staff and post.author != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        publish_date = request.data.get('publish_date')
        success = BlogService.publish_post(post, publish_date=publish_date)
        if success:
            return Response({'status': 'published', 'published_at': post.published_at})
        return Response({'error': 'Publish failed'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def unpublish(self, request, slug=None):
        """Unpublish a blog post (revert to draft)."""
        from api.cms.services_new.BlogService import BlogService
        post = self.get_object()
        if not request.user.is_staff and post.author != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        success = BlogService.unpublish_post(post)
        if success:
            return Response({'status': 'draft'})
        return Response({'error': 'Unpublish failed'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def schedule(self, request, slug=None):
        """Schedule a post for future publishing."""
        from api.cms.services_new.BlogService import BlogService
        post = self.get_object()
        scheduled_at = request.data.get('scheduled_at')
        if not scheduled_at:
            return Response({'error': 'scheduled_at is required'}, status=status.HTTP_400_BAD_REQUEST)
        from django.utils.dateparse import parse_datetime
        dt = parse_datetime(scheduled_at)
        if not dt:
            return Response({'error': 'Invalid date format'}, status=status.HTTP_400_BAD_REQUEST)
        success = BlogService.schedule_post(post, scheduled_at=dt)
        if success:
            return Response({'status': 'scheduled', 'scheduled_at': dt})
        return Response({'error': 'Schedule failed'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def preview(self, request, slug=None):
        """Preview a blog post (includes drafts for author/staff)."""
        from api.cms.models_new.blog import BlogPost
        try:
            post = BlogPost.objects.select_related('author', 'category').prefetch_related('tags').get(slug=slug)
            if not request.user.is_staff and post.author != request.user:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            serializer = self.get_serializer(post)
            return Response({**serializer.data, 'preview': True})
        except BlogPost.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def bulk_publish(self, request):
        """Bulk publish multiple posts."""
        from api.cms.services_new.BlogService import BlogService
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
        count = BlogService.bulk_publish(ids, user=request.user)
        return Response({'published': count})

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get blog statistics."""
        from api.cms.services_new.BlogService import BlogService
        return Response(BlogService.get_blog_statistics())

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured blog posts."""
        from api.cms.services_new.BlogService import BlogService
        lang = request.query_params.get('language', 'en')
        limit = int(request.query_params.get('limit', 6))
        posts = BlogService.get_featured_posts(limit=limit, language=lang)
        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get popular blog posts."""
        from api.cms.services_new.BlogService import BlogService
        days = int(request.query_params.get('days', 30))
        limit = int(request.query_params.get('limit', 10))
        posts = BlogService.get_popular_posts(days=days, limit=limit)
        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def analytics(self, request, slug=None):
        """Get analytics for a specific post."""
        from api.cms.services_new.BlogService import BlogService
        post = self.get_object()
        return Response(BlogService.get_post_analytics(post.id))

    @action(detail=True, methods=['get'])
    def comments(self, request, slug=None):
        """Get comments for a post."""
        from api.cms.services_new.BlogService import BlogService
        post = self.get_object()
        approved_only = not request.user.is_staff
        comments = BlogService.get_post_comments(post, approved_only=approved_only)
        return Response([{
            'id': c.id,
            'content': c.content,
            'user': c.user.username if c.user else c.guest_name,
            'is_approved': c.is_approved,
            'created_at': c.created_at,
            'like_count': c.like_count,
            'reply_count': c.reply_count,
        } for c in comments])

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticatedOrReadOnly])
    def add_comment(self, request, slug=None):
        """Add a comment to a post."""
        from api.cms.services_new.BlogService import BlogService
        post = self.get_object()
        content = request.data.get('content', '').strip()
        if not content:
            return Response({'error': 'Content is required'}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user if request.user.is_authenticated else None
        comment = BlogService.add_comment(
            post=post,
            content=content,
            user=user,
            guest_name=request.data.get('guest_name', ''),
            guest_email=request.data.get('guest_email', ''),
            ip=request.META.get('REMOTE_ADDR'),
        )
        if comment:
            return Response({
                'id': comment.id,
                'content': comment.content,
                'is_approved': comment.is_approved,
                'created_at': comment.created_at,
            }, status=status.HTTP_201_CREATED)
        return Response({'error': 'Could not add comment'}, status=status.HTTP_400_BAD_REQUEST)


class BlogCategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for BlogCategory CRUD.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['sort_order', 'name', 'post_count']

    def get_queryset(self):
        from api.cms.models_new.blog import BlogCategory
        return BlogCategory.objects.filter(is_active=True).order_by('sort_order', 'name')

    def get_serializer_class(self):
        from api.cms.serializers import BlogCategorySerializer
        return BlogCategorySerializer

    @action(detail=False, methods=['get'])
    def with_counts(self, request):
        """Get categories with post counts."""
        from api.cms.services_new.BlogService import BlogService
        return Response(BlogService.get_categories_with_post_counts())

    @action(detail=True, methods=['get'])
    def posts(self, request, slug=None):
        """Get posts for a specific category."""
        from api.cms.services_new.BlogService import BlogService
        lang = request.query_params.get('language', 'en')
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))
        category = self.get_object()
        posts, total = BlogService.get_published_posts(
            category_id=category.id, language=lang, limit=limit, offset=offset
        )
        from api.cms.serializers import BlogPostSerializer
        return Response({
            'count': total,
            'results': BlogPostSerializer(posts, many=True).data,
        })
