from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/viewsets/MenuViewSet.py
"""
MenuViewSet: CRUD + reorder for menus and menu items.
"""
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny

logger = logging.getLogger(__name__)


class MenuViewSet(viewsets.ModelViewSet):
    """
    ViewSet for navigation menu management.

    Endpoints:
        GET    /api/cms/menus/                    - List menus (admin)
        POST   /api/cms/menus/                    - Create menu (admin)
        GET    /api/cms/menus/{id}/               - Menu detail
        PUT    /api/cms/menus/{id}/               - Update menu (admin)
        DELETE /api/cms/menus/{id}/               - Delete menu (admin)
        GET    /api/cms/menus/{id}/tree/          - Get menu tree (public)
        POST   /api/cms/menus/{id}/reorder/       - Reorder items (admin)
        GET    /api/cms/menus/by_location/{loc}/  - Get menu by location (public)
    """
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'location']

    def get_permissions(self):
        if self.action in ('tree', 'by_location', 'retrieve', 'list'):
            return [AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        from api.cms.models_new.menu import Menu
        return Menu.objects.all().prefetch_related('items')

    def get_serializer_class(self):
        from api.cms.serializers import MenuSerializer
        return MenuSerializer

    def create(self, request, *args, **kwargs):
        from api.cms.services_new.MenuService import MenuService
        menu = MenuService.create_menu(
            name=request.data.get('name', ''),
            location=request.data.get('location', 'header'),
            description=request.data.get('description', ''),
        )
        if menu:
            return Response(self.get_serializer(menu).data, status=status.HTTP_201_CREATED)
        return Response({'error': 'Menu creation failed'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def tree(self, request, pk=None):
        """Get full nested menu tree."""
        from api.cms.services_new.MenuService import MenuService
        menu = self.get_object()
        user = request.user if request.user.is_authenticated else None
        tree = MenuService.build_menu_tree(menu, user=user)
        return Response(tree)

    @action(detail=True, methods=['post'])
    def reorder(self, request, pk=None):
        """Reorder menu items. body: [{id, sort_order}]"""
        from api.cms.services_new.MenuService import MenuService
        order_data = request.data.get('order', [])
        success = MenuService.reorder_items(order_data)
        if success:
            return Response({'reordered': len(order_data)})
        return Response({'error': 'Reorder failed'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny], url_path='by_location/(?P<location>[^/.]+)')
    def by_location(self, request, location=None):
        """Get menu tree by location."""
        from api.cms.services_new.MenuService import MenuService
        menu = MenuService.get_menu(location=location)
        if not menu:
            return Response({'error': 'Menu not found'}, status=status.HTTP_404_NOT_FOUND)
        user = request.user if request.user.is_authenticated else None
        tree = MenuService.build_menu_tree(menu, user=user)
        return Response({'location': location, 'tree': tree})

    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        """Add item to menu."""
        from api.cms.services_new.MenuService import MenuService
        menu = self.get_object()
        item = MenuService.create_menu_item(
            menu=menu,
            label=request.data.get('label', ''),
            url=request.data.get('url', ''),
            sort_order=request.data.get('sort_order', 0),
            icon=request.data.get('icon', ''),
            open_in_new_tab=request.data.get('open_in_new_tab', False),
        )
        if item:
            return Response({'id': item.id, 'label': item.label, 'url': item.url}, status=status.HTTP_201_CREATED)
        return Response({'error': 'Item creation failed'}, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# LandingSectionViewSet
# ─────────────────────────────────────────────

class LandingSectionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for landing page sections with drag-drop reorder.
    """
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'section_type']
    ordering_fields = ['sort_order', 'created_at']
    ordering = ['sort_order']

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'for_page'):
            return [AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        from api.cms.models_new.menu import LandingSection
        return LandingSection.objects.filter(is_active=True).order_by('sort_order')

    def get_serializer_class(self):
        from api.cms.serializers import LandingSectionSerializer
        return LandingSectionSerializer

    @action(detail=False, methods=['post'])
    def bulk_reorder(self, request):
        """Bulk reorder sections. body: [{id, sort_order}]"""
        from api.cms.models_new.menu import LandingSection
        order_data = request.data.get('order', [])
        LandingSection.bulk_reorder(order_data)
        return Response({'reordered': len(order_data)})

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def for_page(self, request):
        """Get sections for a specific page."""
        from api.cms.models_new.menu import LandingSection
        page_slug = request.query_params.get('slug', '')
        sections = LandingSection.get_for_page(page_slug=page_slug)
        return Response(self.get_serializer(sections, many=True).data)


# ─────────────────────────────────────────────
# SEOConfigViewSet
# ─────────────────────────────────────────────

class SEOConfigViewSet(viewsets.ModelViewSet):
    """ViewSet for global SEO configuration."""
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        from api.cms.models_new.seo import SEOConfig
        return SEOConfig.objects.all()

    def get_serializer_class(self):
        from api.cms.serializers import SEOConfigSerializer
        return SEOConfigSerializer

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def active(self, request):
        """Get active SEO config."""
        from api.cms.services_new.SEOService import SEOService
        config = SEOService.get_seo_config()
        if config:
            return Response(self.get_serializer(config).data)
        return Response({})

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def audit(self, request):
        """Run SEO audit."""
        from api.cms.services_new.SEOService import SEOService
        return Response(SEOService.audit_blog_seo())

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def statistics(self, request):
        """Get SEO statistics."""
        from api.cms.services_new.SEOService import SEOService
        return Response(SEOService.get_seo_statistics())


# ─────────────────────────────────────────────
# SitemapViewSet
# ─────────────────────────────────────────────

class SitemapViewSet(viewsets.ModelViewSet):
    """ViewSet for sitemap entries."""
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['url', 'source_type']

    def get_queryset(self):
        from api.cms.models_new.seo import Sitemap
        return Sitemap.objects.filter(is_active=True).order_by('-priority')

    def get_serializer_class(self):
        from api.cms.serializers import SitemapSerializer
        return SitemapSerializer

    @action(detail=False, methods=['post'])
    def regenerate(self, request):
        """Regenerate sitemap from all published content."""
        from api.cms.services_new.SEOService import SEOService
        count = SEOService.regenerate_sitemap()
        return Response({'generated': count})

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def download(self, request):
        """Download sitemap.xml."""
        from api.cms.services_new.SEOService import SEOService
        from django.http import HttpResponse
        xml = SEOService.get_sitemap_xml()
        return HttpResponse(xml, content_type='application/xml')


# ─────────────────────────────────────────────
# Redirect301ViewSet
# ─────────────────────────────────────────────

class Redirect301ViewSet(viewsets.ModelViewSet):
    """ViewSet for 301 redirect management."""
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['from_url', 'to_url', 'notes']
    ordering_fields = ['hit_count', 'created_at']
    ordering = ['-hit_count']

    def get_queryset(self):
        from api.cms.models_new.seo import Redirect301
        return Redirect301.objects.all()

    def get_serializer_class(self):
        from api.cms.serializers import Redirect301Serializer
        return Redirect301Serializer

    def create(self, request, *args, **kwargs):
        from api.cms.services_new.RedirectService import RedirectService
        redirect = RedirectService.create(
            from_url=request.data.get('from_url', ''),
            to_url=request.data.get('to_url', ''),
            redirect_type=int(request.data.get('redirect_type', 301)),
            user=request.user,
            notes=request.data.get('notes', ''),
        )
        if redirect:
            return Response(self.get_serializer(redirect).data, status=status.HTTP_201_CREATED)
        return Response({'error': 'Creation failed'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def bulk_import(self, request):
        """Bulk import from CSV."""
        from api.cms.services_new.RedirectService import RedirectService
        csv_content = request.data.get('csv', '')
        if not csv_content:
            return Response({'error': 'CSV content required'}, status=status.HTTP_400_BAD_REQUEST)
        created, errors = RedirectService.bulk_import_csv(csv_content, user=request.user)
        return Response({'created': created, 'errors': errors})

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        from api.cms.services_new.RedirectService import RedirectService
        return Response(RedirectService.get_statistics())

    @action(detail=False, methods=['post'])
    def cleanup(self, request):
        """Cleanup unused redirects."""
        from api.cms.services_new.RedirectService import RedirectService
        days = int(request.data.get('days', 90))
        count = RedirectService.cleanup_unused(days=days)
        return Response({'deleted': count})


# ─────────────────────────────────────────────
# RobotsConfigViewSet
# ─────────────────────────────────────────────

class RobotsConfigViewSet(viewsets.ModelViewSet):
    """ViewSet for robots.txt configuration."""
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        from api.cms.models_new.seo import RobotsConfig
        return RobotsConfig.objects.all()

    def get_serializer_class(self):
        from api.cms.serializers import RobotsConfigSerializer
        return RobotsConfigSerializer

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def preview(self, request):
        """Preview robots.txt content."""
        from api.cms.services_new.SEOService import SEOService
        from django.http import HttpResponse
        content = SEOService.get_robots_txt()
        return HttpResponse(content, content_type='text/plain')


# ─────────────────────────────────────────────
# CMSSearchViewSet
# ─────────────────────────────────────────────

class CMSSearchViewSet(viewsets.ViewSet):
    """
    Full-text search ViewSet across all CMS content types.
    """
    permission_classes = [AllowAny]

    def list(self, request):
        """
        Search across all content types.
        GET /api/cms/search/?q=query&types=page,blog&language=en&limit=20&offset=0
        """
        from api.cms.services_new.ContentSearchService import ContentSearchService
        query = request.query_params.get('q', '').strip()
        types_raw = request.query_params.get('types', '')
        content_types = [t.strip() for t in types_raw.split(',') if t.strip()] if types_raw else None
        language = request.query_params.get('language', 'en')
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))
        user = request.user if request.user.is_authenticated else None

        result = ContentSearchService.search(
            query=query,
            content_types=content_types,
            language=language,
            limit=limit,
            offset=offset,
            user=user,
        )
        return Response(result)

    @action(detail=False, methods=['get'])
    def suggest(self, request):
        """Get search suggestions."""
        from api.cms.services_new.ContentSearchService import ContentSearchService
        query = request.query_params.get('q', '')
        suggestions = ContentSearchService.suggest(query)
        return Response({'suggestions': suggestions})


# ─────────────────────────────────────────────
# PublicCMSViewSet
# ─────────────────────────────────────────────

class PublicCMSViewSet(viewsets.ViewSet):
    """
    Unauthenticated public content fetch endpoints.
    All endpoints are public and cached.
    """
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def home(self, request):
        """Get homepage data: featured content, banners, popups, menus."""
        from api.cms.services_new.BlogService import BlogService
        from api.cms.services_new.MenuService import MenuService
        from api.cms.models import Banner, ContentPage
        from django.utils import timezone as tz

        lang = request.query_params.get('language', 'en')
        data = {
            'featured_posts': [],
            'popular_posts': [],
            'header_menu': None,
            'footer_menu': None,
        }

        # Featured blog posts
        try:
            posts = BlogService.get_featured_posts(limit=6, language=lang)
            data['featured_posts'] = [{
                'id': p.id, 'title': p.title, 'slug': p.slug,
                'excerpt': p.excerpt, 'published_at': p.published_at,
            } for p in posts]
        except Exception:
            pass

        # Popular posts
        try:
            popular = BlogService.get_popular_posts(days=30, limit=5)
            data['popular_posts'] = [{
                'id': p.id, 'title': p.title, 'slug': p.slug,
                'views_count': p.views_count,
            } for p in popular]
        except Exception:
            pass

        # Menus
        try:
            header_menu = MenuService.get_menu(location='header')
            if header_menu:
                data['header_menu'] = MenuService.build_menu_tree(header_menu)
        except Exception:
            pass

        try:
            footer_menu = MenuService.get_menu(location='footer')
            if footer_menu:
                data['footer_menu'] = MenuService.build_menu_tree(footer_menu)
        except Exception:
            pass

        return Response(data)

    @action(detail=False, methods=['get'], url_path='page/(?P<slug>[^/.]+)')
    def page(self, request, slug=None):
        """Get a public CMS page by slug."""
        from api.cms.models import ContentPage
        try:
            page = ContentPage.objects.get(slug=slug, status='published', is_active=True)
            page.increment_view_count()
            return Response({
                'id': page.id,
                'title': page.title,
                'content': page.content,
                'excerpt': page.excerpt,
                'meta_title': page.meta_title,
                'meta_description': page.meta_description,
                'published_date': page.published_date,
                'view_count': page.view_count,
            })
        except ContentPage.DoesNotExist:
            return Response({'error': 'Page not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'], url_path='blog/(?P<slug>[^/.]+)')
    def blog_post(self, request, slug=None):
        """Get a public blog post by slug."""
        from api.cms.models_new.blog import BlogPost
        try:
            post = BlogPost.objects.select_related('author', 'category').prefetch_related('tags').get(
                slug=slug, status='published', is_active=True
            )
            post.increment_views()
            return Response({
                'id': post.id,
                'title': post.title,
                'body': post.body,
                'excerpt': post.excerpt,
                'author': post.author.username if post.author else None,
                'category': {'name': post.category.name, 'slug': post.category.slug} if post.category else None,
                'tags': [{'name': t.name, 'slug': t.slug} for t in post.tags.all()],
                'published_at': post.published_at,
                'reading_time': post.reading_time_minutes,
                'views_count': post.views_count,
            })
        except BlogPost.DoesNotExist:
            return Response({'error': 'Post not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'])
    def config(self, request):
        """Get public site config (SEO, analytics IDs)."""
        from api.cms.services_new.SEOService import SEOService
        config = SEOService.get_seo_config()
        if not config:
            return Response({})
        return Response({
            'site_name': config.site_name,
            'default_title': config.default_title,
            'google_analytics_id': config.google_analytics_id,
            'google_tag_manager_id': config.google_tag_manager_id,
            'twitter_site': config.twitter_site,
            'facebook_app_id': config.facebook_app_id,
            'og_image': config.get_og_image_url(),
        })
