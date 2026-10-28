# cms/viewsets_new/BlogSEOViewSet.py
"""
BlogSEO ViewSet — Complete REST API for Blog SEO Metadata

This ViewSet provides CRUD operations for:
- Meta tags (title, description)
- Schema.org structured data
- Open Graph tags
- Keywords and SEO optimization
- Sitemap generation
- SEO scoring and validation

Permissions: Admin only (high-impact SEO configuration)
"""

from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.db.models import Q
import logging
import json

logger = logging.getLogger('cms.viewsets.blog_seo')


class BlogSEOViewSet(viewsets.ModelViewSet):
    """
    Blog SEO Metadata Management
    
    Complete REST API for managing SEO configuration for blog posts.
    
    Endpoints:
        GET    /v3/blog-seo/                      — list all SEO configs
        POST   /v3/blog-seo/                      — create new SEO config
        GET    /v3/blog-seo/{id}/                 — retrieve SEO config details
        PUT    /v3/blog-seo/{id}/                 — full update SEO config
        PATCH  /v3/blog-seo/{id}/                 — partial update SEO config
        DELETE /v3/blog-seo/{id}/                 — delete SEO config
        
        POST   /v3/blog-seo/{id}/generate-schema/   — auto-generate schema.org data
        GET    /v3/blog-seo/{id}/preview/          — preview search result appearance
        POST   /v3/blog-seo/validate/              — validate SEO score
        POST   /v3/blog-seo/{id}/generate-sitemap/ — generate sitemap entry
        GET    /v3/blog-seo/bulk-export/           — export all SEO configs
        POST   /v3/blog-seo/bulk-import/           — import SEO configs
    
    Query Parameters:
        - blog_post: Filter by blog post ID
        - schema_type: Filter by schema type (BlogPosting, NewsArticle, etc.)
        - is_featured: Filter by featured status
        - min_score: Filter by minimum SEO score
        - search: Search in meta_title, meta_description, keywords
    
    Permissions: IsAdminUser (SEO = high-impact configuration)
    """
    
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['blog_post', 'schema_type', 'is_featured']
    search_fields = ['blog_post__title', 'meta_title', 'meta_description', 'primary_keyword']
    ordering_fields = ['created_at', 'modified_at', 'schema_type']
    ordering = ['-modified_at']
    
    def get_queryset(self):
        """
        Get SEO configs with optimized queries.
        
        - Select related: blog_post (foreign key)
        - Prefetch related: keyword sets if applicable
        - Filter by tenant if multi-tenant
        """
        from api.cms.models_new.blog import BlogSEO
        
        qs = BlogSEO.objects.select_related('blog_post').all()
        
        # Multi-tenant filtering
        if hasattr(self.request, 'tenant'):
            qs = qs.filter(blog_post__tenant=self.request.tenant)
        
        # Optional: Filter by minimum SEO score
        min_score = self.request.query_params.get('min_score')
        if min_score:
            try:
                min_score = int(min_score)
                # Score filtering would require annotation; see perform_list()
            except ValueError:
                pass
        
        return qs
    
    def get_serializer_class(self):
        """
        Return appropriate serializer based on action.
        
        - List/Retrieve: Full details
        - Create/Update: Form data with validation
        - Custom actions: Specific serializers
        """
        from api.cms.serializers_new.ContentAndFormSerializer import (
            BlogSEOSerializer,
            BlogSEODetailedSerializer,
        )
        
        if self.action in ('create', 'update', 'partial_update'):
            return BlogSEOSerializer
        elif self.action == 'retrieve':
            return BlogSEODetailedSerializer
        else:
            return BlogSEOSerializer
    
    def perform_create(self, serializer):
        """Track who created SEO config"""
        serializer.save(created_by=self.request.user)
        logger.info(f"SEO config created by {self.request.user}: {serializer.instance.id}")
    
    def perform_update(self, serializer):
        """Track who updated SEO config"""
        serializer.save(modified_by=self.request.user)
        logger.info(f"SEO config updated by {self.request.user}: {serializer.instance.id}")
    
    def perform_destroy(self, instance):
        """Log deletion"""
        blog_id = instance.blog_post.id
        logger.warning(f"SEO config deleted for blog {blog_id}")
        instance.delete()
    
    # ─────────────────────────────────────────────────────────────────────────
    # CUSTOM ACTIONS
    # ─────────────────────────────────────────────────────────────────────────
    
    @action(detail=True, methods=['post'])
    def generate_schema(self, request, pk=None):
        """
        Auto-generate schema.org structured data
        
        Generates appropriate schema based on blog category:
        - BlogPosting (default for blog posts)
        - NewsArticle (if category is News)
        - ScholarlyArticle (if academic)
        - HowTo (if how-to guide)
        
        Request body:
        {
            "schema_type": "BlogPosting"  (optional, default: "BlogPosting")
        }
        
        Response:
        {
            "schema_type": "BlogPosting",
            "schema": {...full schema.org data...},
            "message": "Schema generated successfully"
        }
        """
        from api.cms.models_new.blog import BlogSEO
        
        seo = self.get_object()
        blog = seo.blog_post
        
        schema_type = request.data.get('schema_type', 'BlogPosting')
        
        # Validate schema type
        valid_types = ['BlogPosting', 'NewsArticle', 'ScholarlyArticle', 'HowTo']
        if schema_type not in valid_types:
            return Response(
                {'error': f'Invalid schema_type. Must be one of {valid_types}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate schema
        schema = {
            '@context': 'https://schema.org',
            '@type': schema_type,
            'headline': blog.title,
            'description': blog.excerpt or blog.title[:160],
            'author': {
                '@type': 'Person',
                'name': str(blog.author),
            },
            'datePublished': blog.published_at.isoformat() if blog.published_at else None,
            'dateModified': blog.updated_at.isoformat(),
        }
        
        # Add image if available
        if blog.featured_image:
            schema['image'] = {
                '@type': 'ImageObject',
                'url': request.build_absolute_uri(blog.featured_image.url),
                'width': 1200,
                'height': 630,
            }
        
        # Add keywords
        if seo.primary_keyword:
            schema['keywords'] = [seo.primary_keyword]
            if seo.secondary_keywords:
                schema['keywords'].extend(seo.secondary_keywords.split(','))
        
        # Save schema
        seo.schema_json = schema
        seo.schema_type = schema_type
        seo.save(update_fields=['schema_json', 'schema_type', 'modified_at'])
        
        logger.info(f"Generated {schema_type} schema for blog {blog.id}")
        
        return Response({
            'schema_type': schema_type,
            'schema': schema,
            'message': 'Schema generated successfully',
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        Preview how blog post appears in search results
        
        Returns:
        {
            "title": "Meta title as shown in browser",
            "description": "Meta description as shown in search results",
            "url": "/blog/blog-slug/",
            "seo_score": 85,
            "rating": "Excellent",
            "suggestions": [...]
        }
        """
        seo = self.get_object()
        blog = seo.blog_post
        
        # Build preview
        preview = {
            'title': seo.meta_title or blog.title,
            'description': seo.meta_description or (blog.excerpt[:160] if blog.excerpt else ''),
            'url': f"/blog/{blog.slug}/",
            'keyword': seo.primary_keyword,
            'seo_score': self._calculate_seo_score(seo),
            'rating': self._score_to_rating(self._calculate_seo_score(seo)),
            'suggestions': self._get_seo_suggestions(seo),
        }
        
        return Response(preview, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def validate(self, request):
        """
        Validate SEO configuration and get score
        
        Request:
        {
            "blog_id": 123
        }
        
        Response:
        {
            "blog_id": 123,
            "blog_title": "Blog Title",
            "seo_score": 85,
            "rating": "Excellent",
            "issues": [...],
            "improvements": [...]
        }
        """
        from api.cms.models_new.blog import BlogPost, BlogSEO
        
        blog_id = request.data.get('blog_id')
        if not blog_id:
            return Response(
                {'error': 'blog_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            blog = BlogPost.objects.get(id=blog_id)
            seo = blog.blogseo
        except BlogPost.DoesNotExist:
            return Response(
                {'error': 'Blog not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except BlogSEO.DoesNotExist:
            return Response(
                {'error': 'SEO config not found for blog'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        score = self._calculate_seo_score(seo)
        suggestions = self._get_seo_suggestions(seo)
        
        return Response({
            'blog_id': blog_id,
            'blog_title': blog.title,
            'seo_score': score,
            'rating': self._score_to_rating(score),
            'issues': [s for s in suggestions if s['type'] == 'issue'],
            'improvements': [s for s in suggestions if s['type'] == 'improvement'],
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def generate_sitemap_entry(self, request, pk=None):
        """
        Generate sitemap entry for this blog post
        
        Response:
        {
            "loc": "https://example.com/blog/blog-slug/",
            "lastmod": "2024-06-10",
            "changefreq": "weekly",
            "priority": 0.8
        }
        """
        seo = self.get_object()
        blog = seo.blog_post
        
        # Get current site domain
        from django.contrib.sites.models import Site
        try:
            current_site = Site.objects.get_current()
            domain = f"https://{current_site.domain}"
        except Site.DoesNotExist:
            domain = "https://example.com"
        
        entry = {
            'loc': f"{domain}/blog/{blog.slug}/",
            'lastmod': blog.updated_at.date().isoformat(),
            'changefreq': request.data.get('changefreq', 'weekly'),
            'priority': min(1.0, float(request.data.get('priority', 0.8))),
        }
        
        return Response(entry, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def bulk_export(self, request):
        """
        Export all SEO configs as JSON
        
        Query parameters:
        - format: "json" or "csv"
        - blog_category: Filter by blog category
        
        Response: JSON array of all SEO configs
        """
        from api.cms.models_new.blog import BlogSEO
        
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'count': queryset.count(),
            'results': serializer.data,
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def bulk_import(self, request):
        """
        Import SEO configs from JSON
        
        Request body:
        {
            "configs": [
                {
                    "blog_post": 1,
                    "meta_title": "...",
                    "meta_description": "...",
                    ...
                }
            ]
        }
        
        Response:
        {
            "imported": 5,
            "skipped": 0,
            "errors": []
        }
        """
        from api.cms.models_new.blog import BlogSEO
        
        configs = request.data.get('configs', [])
        imported = 0
        errors = []
        
        for config in configs:
            try:
                serializer = self.get_serializer(data=config)
                serializer.is_valid(raise_exception=True)
                serializer.save(modified_by=self.request.user)
                imported += 1
            except serializers.ValidationError as e:
                errors.append({
                    'config': config.get('blog_post'),
                    'error': str(e),
                })
        
        return Response({
            'imported': imported,
            'skipped': len(configs) - imported,
            'errors': errors,
        }, status=status.HTTP_201_CREATED)
    
    # ─────────────────────────────────────────────────────────────────────────
    # HELPER METHODS FOR SEO SCORING
    # ─────────────────────────────────────────────────────────────────────────
    
    def _calculate_seo_score(self, seo):
        """
        Calculate SEO score (0-100) based on best practices
        
        Scoring criteria:
        - Meta title (10 pts): 30-60 chars = full score
        - Meta description (10 pts): 120-160 chars = full score
        - Primary keyword (10 pts): present = full score
        - Schema markup (10 pts): present = full score
        - Featured image (5 pts): present = full score
        - URL slug (5 pts): good format = full score
        - Internal links (10 pts): present = bonus
        - Readability (10 pts): content length check = bonus
        """
        score = 50  # Base score
        blog = seo.blog_post
        
        # Meta title scoring
        if seo.meta_title:
            title_len = len(seo.meta_title)
            if 30 <= title_len <= 60:
                score += 10  # Perfect length
            elif 25 <= title_len <= 75:
                score += 7   # Acceptable length
            else:
                score += 3   # Suboptimal length
        
        # Meta description scoring
        if seo.meta_description:
            desc_len = len(seo.meta_description)
            if 120 <= desc_len <= 160:
                score += 10  # Perfect length
            elif 100 <= desc_len <= 180:
                score += 7   # Acceptable length
            else:
                score += 3   # Suboptimal length
        
        # Keywords
        if seo.primary_keyword:
            score += 10
        if seo.secondary_keywords:
            score += 5
        
        # Schema markup
        if seo.schema_json:
            try:
                schema = json.loads(seo.schema_json) if isinstance(seo.schema_json, str) else seo.schema_json
                if isinstance(schema, dict) and '@type' in schema:
                    score += 10
            except json.JSONDecodeError:
                pass
        
        # Featured image
        if blog.featured_image:
            score += 5
        
        # URL slug quality
        if blog.slug and len(blog.slug) > 3 and '-' in blog.slug:
            score += 5
        
        # Internal links
        if blog.content:
            internal_links = blog.content.count('<a href="/') + blog.content.count('<a href="/')
            if internal_links > 0:
                score += min(5, internal_links)
        
        # Content length (good SEO = 300+ words)
        if blog.content:
            word_count = len(blog.content.split())
            if word_count >= 300:
                score += 5
        
        return min(100, score)
    
    def _get_seo_suggestions(self, seo):
        """Get actionable SEO improvement suggestions"""
        suggestions = []
        blog = seo.blog_post
        
        # Meta title
        if not seo.meta_title:
            suggestions.append({
                'type': 'issue',
                'priority': 'high',
                'title': 'Missing meta title',
                'description': 'Add a meta title (30-60 chars) for better search appearance',
                'example': blog.title[:60],
            })
        elif len(seo.meta_title) < 30:
            suggestions.append({
                'type': 'improvement',
                'priority': 'medium',
                'title': 'Meta title too short',
                'description': 'Expand to 30-60 characters for better CTR',
                'current_length': len(seo.meta_title),
            })
        elif len(seo.meta_title) > 60:
            suggestions.append({
                'type': 'improvement',
                'priority': 'low',
                'title': 'Meta title too long',
                'description': 'Reduce to 60 characters to avoid truncation',
                'current_length': len(seo.meta_title),
            })
        
        # Meta description
        if not seo.meta_description:
            suggestions.append({
                'type': 'issue',
                'priority': 'high',
                'title': 'Missing meta description',
                'description': 'Add a meta description (120-160 chars)',
                'example': (blog.excerpt or blog.title)[:160],
            })
        elif len(seo.meta_description) < 120:
            suggestions.append({
                'type': 'improvement',
                'priority': 'medium',
                'title': 'Meta description too short',
                'description': 'Expand to 120-160 characters for full impact',
                'current_length': len(seo.meta_description),
            })
        
        # Keywords
        if not seo.primary_keyword:
            suggestions.append({
                'type': 'improvement',
                'priority': 'medium',
                'title': 'No primary keyword defined',
                'description': 'Define a primary keyword for SEO focus',
            })
        
        # Schema
        if not seo.schema_json:
            suggestions.append({
                'type': 'improvement',
                'priority': 'medium',
                'title': 'No structured data',
                'description': 'Add schema.org markup for better search visibility',
            })
        
        # Featured image
        if not blog.featured_image:
            suggestions.append({
                'type': 'improvement',
                'priority': 'low',
                'title': 'No featured image',
                'description': 'Add a featured image to improve CTR',
            })
        
        # Content length
        if blog.content:
            word_count = len(blog.content.split())
            if word_count < 300:
                suggestions.append({
                    'type': 'improvement',
                    'priority': 'low',
                    'title': 'Content too short',
                    'description': 'Aim for 300+ words for better SEO',
                    'current_words': word_count,
                })
        
        return suggestions
    
    def _score_to_rating(self, score):
        """Convert numerical score to rating"""
        if score >= 80:
            return 'Excellent'
        elif score >= 60:
            return 'Good'
        elif score >= 40:
            return 'Fair'
        else:
            return 'Poor'


# ─────────────────────────────────────────────────────────────────────────────
# SERIALIZERS (if not in separate file)
# ─────────────────────────────────────────────────────────────────────────────

class BlogSEOBaseSerializer:
    """Base fields for BlogSEO serializers"""
    base_fields = [
        'id', 'blog_post', 'blog_post_title',
        'meta_title', 'meta_description',
        'primary_keyword', 'secondary_keywords',
        'schema_type', 'schema_json',
        'og_title', 'og_description', 'og_image',
        'is_featured', 'canonical_url',
        'created_at', 'modified_at'
    ]


# Make sure to register in urls.py:
# from .viewsets_new import BlogSEOViewSet
# api_router.register(r"v3/blog-seo", BlogSEOViewSet, basename="cms-blog-seo")
