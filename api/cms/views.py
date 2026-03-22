from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.db.models import Q, F, Count, Sum, Avg, Max, Min
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from api.wallet.models import WalletTransaction as GatewayTransaction
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed
from django.contrib.sitemaps import Sitemap
from api.tenants.mixins import TenantMixin
from rest_framework.views import APIView 
from rest_framework.response import Response 
from rest_framework.permissions import IsAuthenticatedOrReadOnly 
import json
from datetime import datetime, timedelta
import logging

from .models import (
    ContentCategory, ContentPage, Banner, FAQCategory, FAQ,
    SiteSettings, ImageGallery, GalleryImage, FileManager,
    Comment, SiteAnalytics, ContentPermission
)
from .forms import (
    ContentCategoryForm, ContentPageForm, BannerForm, FAQForm,
    FAQCategoryForm, SiteSettingsForm, ImageGalleryForm,
    GalleryImageForm, FileManagerForm, CommentForm
)

logger = logging.getLogger(__name__)


# ==============================================
# Dashboard and Analytics Views
# ==============================================

class DashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Admin Dashboard View"""
    template_name = 'cms/dashboard.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get today's date
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        # Content Statistics
        content_stats = {
            'total_pages': ContentPage.objects.count(),
            'published_pages': ContentPage.objects.filter(status='published', is_active=True).count(),
            'draft_pages': ContentPage.objects.filter(status='draft').count(),
            'scheduled_pages': ContentPage.objects.filter(status='scheduled', scheduled_date__gte=timezone.now()).count(),
            'total_views': ContentPage.objects.aggregate(Sum('view_count'))['view_count__sum'] or 0,
            'total_shares': ContentPage.objects.aggregate(Sum('share_count'))['share_count__sum'] or 0,
            'total_comments': ContentPage.objects.aggregate(Sum('comment_count'))['comment_count__sum'] or 0,
        }
        
        # Category Statistics
        category_stats = ContentCategory.objects.filter(is_active=True).annotate(
            page_count=Count('pages', filter=Q(pages__is_active=True))
        ).order_by('-page_count')[:10]
        
        # Banner Statistics
        banner_stats = {
            'total_banners': Banner.objects.count(),
            'active_banners': Banner.objects.filter(is_active=True).count(),
            'total_impressions': Banner.objects.aggregate(Sum('impression_count'))['impression_count__sum'] or 0,
            'total_clicks': Banner.objects.aggregate(Sum('click_count'))['click_count__sum'] or 0,
            'total_conversions': Banner.objects.aggregate(Sum('conversion_count'))['conversion_count__sum'] or 0,
        }
        
        # FAQ Statistics
        faq_stats = {
            'total_faqs': FAQ.objects.count(),
            'active_faqs': FAQ.objects.filter(is_active=True).count(),
            'featured_faqs': FAQ.objects.filter(is_featured=True, is_active=True).count(),
            'total_faq_views': FAQ.objects.aggregate(Sum('view_count'))['view_count__sum'] or 0,
        }
        
        # Recent Activity
        recent_pages = ContentPage.objects.all().order_by('-updated_at')[:10]
        recent_banners = Banner.objects.all().order_by('-created_at')[:10]
        recent_faqs = FAQ.objects.all().order_by('-created_at')[:10]
        
        # Popular Content
        popular_content = ContentPage.objects.filter(
            is_active=True, status='published'
        ).order_by('-view_count')[:10]
        
        # Analytics data
        analytics_data = SiteAnalytics.objects.filter(
            date__gte=week_ago
        ).order_by('date')
        
        context.update({
            'content_stats': content_stats,
            'category_stats': category_stats,
            'banner_stats': banner_stats,
            'faq_stats': faq_stats,
            'recent_pages': recent_pages,
            'recent_banners': recent_banners,
            'recent_faqs': recent_faqs,
            'popular_content': popular_content,
            'analytics_data': analytics_data,
            'today': today,
            'week_ago': week_ago,
        })
        
        return context


class AnalyticsDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Detailed Analytics Dashboard"""
    template_name = 'cms/analytics_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Date range filter
        days = int(self.request.GET.get('days', 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get analytics data
        analytics = SiteAnalytics.objects.filter(
            date__range=[start_date, end_date]
        ).order_by('date')
        
        # Calculate totals
        totals = analytics.aggregate(
            total_views=Sum('page_views'),
            total_visitors=Sum('unique_visitors'),
            total_earnings=Sum('total_earnings'),
            total_conversions=Sum('offer_completions') + Sum('task_completions') + Sum('banner_conversions'),
            avg_session_duration=Avg('avg_session_duration'),
            avg_bounce_rate=Avg('bounce_rate')
        )
        
        # Popular content
        popular_content = ContentPage.objects.filter(
            status='published',
            is_active=True,
            published_date__date__range=[start_date, end_date]
        ).order_by('-view_count')[:10]
        
        # Top performing banners
        top_banners = Banner.objects.filter(
            is_active=True
        ).order_by('-click_through_rate')[:10]
        
        context.update({
            'analytics': analytics,
            'totals': totals,
            'popular_content': popular_content,
            'top_banners': top_banners,
            'start_date': start_date,
            'end_date': end_date,
            'days': days,
        })
        
        return context


# ==============================================
# Content Category Views
# ==============================================

class ContentCategoryListView(LoginRequiredMixin, ListView):
    """List all content categories"""
    model = ContentCategory
    template_name = 'cms/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = ContentCategory.objects.all()
        
        # Filtering
        category_type = self.request.GET.get('type')
        if category_type:
            queryset = queryset.filter(category_type=category_type)
        
        is_active = self.request.GET.get('is_active')
        if is_active:
            if is_active.lower() == 'true':
                queryset = queryset.filter(is_active=True)
            elif is_active.lower() == 'false':
                queryset = queryset.filter(is_active=False)
        
        # Searching
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(slug__icontains=search_query)
            )
        
        return queryset.order_by('order', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category_types'] = ContentCategory.CATEGORY_TYPES
        return context


class ContentCategoryDetailView(LoginRequiredMixin, DetailView):
    """View category details"""
    model = ContentCategory
    template_name = 'cms/category_detail.html'
    context_object_name = 'category'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = self.get_object()
        
        # Get content in this category
        content_pages = category.pages.filter(is_active=True).order_by('-published_date')
        
        # Paginate content
        paginator = Paginator(content_pages, 10)
        page = self.request.GET.get('page')
        
        try:
            content_list = paginator.page(page)
        except PageNotAnInteger:
            content_list = paginator.page(1)
        except EmptyPage:
            content_list = paginator.page(paginator.num_pages)
        
        context.update({
            'content_list': content_list,
            'child_categories': category.get_active_children(),
        })
        
        return context


class ContentCategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create new content category"""
    model = ContentCategory
    form_class = ContentCategoryForm
    template_name = 'cms/category_form.html'
    permission_required = 'cms.add_contentcategory'
    success_url = reverse_lazy('cms:category_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Category created successfully!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Category'
        return context


class ContentCategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Update existing content category"""
    model = ContentCategory
    form_class = ContentCategoryForm
    template_name = 'cms/category_form.html'
    permission_required = 'cms.change_contentcategory'
    
    def get_success_url(self):
        return reverse_lazy('cms:category_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, 'Category updated successfully!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Update Category: {self.object.name}'
        return context


class ContentCategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Delete content category"""
    model = ContentCategory
    template_name = 'cms/category_confirm_delete.html'
    permission_required = 'cms.delete_contentcategory'
    success_url = reverse_lazy('cms:category_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Category deleted successfully!')
        return super().delete(request, *args, **kwargs)


# ==============================================
# Content Page Views
# ==============================================

class ContentPageListView(ListView):
    """List content pages (public view)"""
    model = ContentPage
    template_name = 'cms/content_list.html'
    context_object_name = 'content_pages'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = ContentPage.objects.filter(
            status='published',
            is_active=True,
            published_date__lte=timezone.now()
        ).select_related('category', 'author')
        
        # Category filter
        category_slug = self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        # Page type filter
        page_type = self.request.GET.get('type')
        if page_type:
            queryset = queryset.filter(page_type=page_type)
        
        # Tag filter
        tag = self.request.GET.get('tag')
        if tag:
            queryset = queryset.filter(tags__contains=[tag])
        
        # Search
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(subtitle__icontains=search_query) |
                Q(excerpt__icontains=search_query) |
                Q(content__icontains=search_query) |
                Q(tags__contains=[search_query])
            )
        
        # Sorting
        sort_by = self.request.GET.get('sort', '-published_date')
        if sort_by in ['published_date', '-published_date', 'title', '-title', 'view_count', '-view_count']:
            queryset = queryset.order_by(sort_by)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get categories for filter
        categories = ContentCategory.objects.filter(
            is_active=True,
            show_in_menu=True
        ).order_by('order')
        
        # Get page types
        page_types = ContentPage.PAGE_TYPES
        
        # Get popular tags
        # Note: This query might need optimization for large datasets
        all_pages = ContentPage.objects.filter(
            status='published',
            is_active=True
        )
        tag_counts = {}
        for page in all_pages:
            if page.tags:
                for tag in page.tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        popular_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        
        context.update({
            'categories': categories,
            'page_types': page_types,
            'popular_tags': popular_tags,
            'current_category': self.request.GET.get('category'),
            'current_type': self.request.GET.get('type'),
            'current_tag': self.request.GET.get('tag'),
            'search_query': self.request.GET.get('q', ''),
            'sort_by': self.request.GET.get('sort', '-published_date'),
        })
        
        return context


class ContentPageDetailView(DetailView):
    """Content page detail view"""
    model = ContentPage
    template_name = 'cms/content_detail.html'
    context_object_name = 'content'
    
    def get_object(self, queryset=None):
        # Try to get by slug first, then by UUID
        slug = self.kwargs.get('slug')
        uuid = self.kwargs.get('uuid')
        
        if slug:
            obj = get_object_or_404(
                ContentPage.objects.select_related('category', 'author'),
                slug=slug,
                is_active=True,
                status='published'
            )
        elif uuid:
            obj = get_object_or_404(
                ContentPage.objects.select_related('category', 'author'),
                uuid=uuid,
                is_active=True,
                status='published'
            )
        else:
            obj = super().get_object(queryset)
        
        return obj
    
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        
        # Increment view count (async)
        content = self.get_object()
        content.increment_view_count()
        
        # Record view log
        if request.user.is_authenticated:
            from .models import ContentViewLog
            ContentViewLog.objects.create(
                content=content,
                user=request.user,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        content = self.get_object()
        
        # Get related content
        related_content = content.get_related_content()
        
        # Get comments (if allowed)
        comments = []
        if content.allow_comments:
            comments = Comment.objects.filter(
                content_type__model='contentpage',
                object_id=content.id,
                is_approved=True,
                is_active=True,
                parent__isnull=True
            ).select_related('user').order_by('-created_at')
        
        # Check permissions
        can_comment = ContentPermission.check_permission(content, self.request.user, 'comment') if self.request.user.is_authenticated else False
        
        context.update({
            'related_content': related_content,
            'comments': comments,
            'can_comment': can_comment,
            'comment_form': CommentForm() if can_comment else None,
        })
        
        return context


class ContentPageCreateView(LoginRequiredMixin, CreateView):
    """Create new content page"""
    model = ContentPage
    form_class = ContentPageForm
    template_name = 'cms/content_form.html'
    
    def form_valid(self, form):
        form.instance.author = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, 'Content created successfully!')
        return response
    
    def get_success_url(self):
        return reverse_lazy('cms:content_detail', kwargs={'slug': self.object.slug})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Content'
        return context


class ContentPageUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Update content page"""
    model = ContentPage
    form_class = ContentPageForm
    template_name = 'cms/content_form.html'
    
    def test_func(self):
        content = self.get_object()
        return self.request.user.is_staff or content.author == self.request.user
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Content updated successfully!')
        return response
    
    def get_success_url(self):
        return reverse_lazy('cms:content_detail', kwargs={'slug': self.object.slug})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Update Content: {self.object.title}'
        return context


class ContentPageDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete content page"""
    model = ContentPage
    template_name = 'cms/content_confirm_delete.html'
    
    def test_func(self):
        content = self.get_object()
        return self.request.user.is_staff
    
    def get_success_url(self):
        return reverse_lazy('cms:content_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Content deleted successfully!')
        return super().delete(request, *args, **kwargs)


class ContentPagePreviewView(LoginRequiredMixin, DetailView):
    """Preview content page (for drafts)"""
    model = ContentPage
    template_name = 'cms/content_detail.html'
    context_object_name = 'content'
    
    def get_object(self, queryset=None):
        # Allow preview of any content for staff/author
        obj = get_object_or_404(ContentPage, pk=self.kwargs.get('pk'))
        
        if not (self.request.user.is_staff or obj.author == self.request.user):
            # Only allow preview of published content for others
            if obj.status != 'published' or not obj.is_active:
                raise Http404("Content not found")
        
        return obj


# ==============================================
# Banner Views
# ==============================================

class BannerListView(LoginRequiredMixin, ListView):
    """List all banners"""
    model = Banner
    template_name = 'cms/banner_list.html'
    context_object_name = 'banners'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Banner.objects.all().select_related('internal_page', 'offer', 'task')
        
        # Filtering
        banner_type = self.request.GET.get('type')
        if banner_type:
            queryset = queryset.filter(banner_type=banner_type)
        
        position = self.request.GET.get('position')
        if position:
            queryset = queryset.filter(position=position)
        
        is_active = self.request.GET.get('is_active')
        if is_active:
            if is_active.lower() == 'true':
                queryset = queryset.filter(is_active=True)
            elif is_active.lower() == 'false':
                queryset = queryset.filter(is_active=False)
        
        # Active now filter
        active_now = self.request.GET.get('active_now')
        if active_now:
            now = timezone.now()
            if active_now.lower() == 'true':
                queryset = queryset.filter(
                    is_active=True,
                    start_date__lte=now,
                ).filter(
                    models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
                )
        
        # Search
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        return queryset.order_by('-priority', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['banner_types'] = Banner.BANNER_TYPES
        context['position_choices'] = Banner.POSITION_CHOICES
        return context


class BannerDetailView(LoginRequiredMixin, DetailView):
    """View banner details"""
    model = Banner
    template_name = 'cms/banner_detail.html'
    context_object_name = 'banner'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        banner = self.get_object()
        
        # Get impressions and clicks for last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        impressions = banner.impressions.filter(
            created_at__gte=thirty_days_ago
        ).values('created_at__date').annotate(
            count=Count('id')
        ).order_by('created_at__date')
        
        clicks = banner.clicks.filter(
            created_at__gte=thirty_days_ago
        ).values('created_at__date').annotate(
            count=Count('id')
        ).order_by('created_at__date')
        
        # Get recent impressions and clicks
        recent_impressions = banner.impressions.all().order_by('-created_at')[:10]
        recent_clicks = banner.clicks.all().order_by('-created_at')[:10]
        
        context.update({
            'impressions_data': list(impressions),
            'clicks_data': list(clicks),
            'recent_impressions': recent_impressions,
            'recent_clicks': recent_clicks,
        })
        
        return context


class BannerCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create new banner"""
    model = Banner
    form_class = BannerForm
    template_name = 'cms/banner_form.html'
    permission_required = 'cms.add_banner'
    success_url = reverse_lazy('cms:banner_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Banner created successfully!')
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Banner'
        return context


class BannerUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Update banner"""
    model = Banner
    form_class = BannerForm
    template_name = 'cms/banner_form.html'
    permission_required = 'cms.change_banner'
    
    def get_success_url(self):
        return reverse_lazy('cms:banner_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Banner updated successfully!')
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Update Banner: {self.object.name}'
        return context


class BannerDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Delete banner"""
    model = Banner
    template_name = 'cms/banner_confirm_delete.html'
    permission_required = 'cms.delete_banner'
    success_url = reverse_lazy('cms:banner_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Banner deleted successfully!')
        return super().delete(request, *args, **kwargs)


@csrf_exempt
@require_http_methods(["POST"])
def record_banner_click(request, banner_id):
    """Record banner click (API endpoint)"""
    try:
        banner = Banner.objects.get(id=banner_id, is_active=True)
        
        # Check if banner is active now
        if not banner.is_active_now():
            return JsonResponse({'success': False, 'error': 'Banner not active'})
        
        # Record click
        banner.record_click(user=request.user if request.user.is_authenticated else None)
        
        # Get redirect URL
        redirect_url = banner.get_click_url()
        
        return JsonResponse({
            'success': True,
            'redirect_url': redirect_url,
            'message': 'Click recorded successfully'
        })
    
    except Banner.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Banner not found'}, status=404)
    
    except Exception as e:
        logger.error(f"Error recording banner click: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==============================================
# FAQ Views
# ==============================================

class FAQListView(ListView):
    """List all FAQs (public view)"""
    model = FAQ
    template_name = 'cms/faq_list.html'
    context_object_name = 'faqs'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = FAQ.objects.filter(
            is_active=True,
            show_on_website=True
        ).select_related('category')
        
        # Category filter
        category_slug = self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        # FAQ type filter
        faq_type = self.request.GET.get('type')
        if faq_type and hasattr(FAQCategory, 'faq_type'):
            queryset = queryset.filter(category__faq_type=faq_type)
        
        # Search
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(question__icontains=search_query) |
                Q(short_answer__icontains=search_query) |
                Q(detailed_answer__icontains=search_query) |
                Q(tags__contains=[search_query])
            )
        
        # Featured filter
        featured = self.request.GET.get('featured')
        if featured:
            queryset = queryset.filter(is_featured=True)
        
        return queryset.order_by('-priority', '-is_featured', 'question')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get categories
        categories = FAQCategory.objects.filter(
            is_active=True,
            faqs__is_active=True
        ).distinct().order_by('order')
        
        # Get FAQ types
        faq_types = FAQCategory._meta.get_field('faq_type').choices if hasattr(FAQCategory, 'faq_type') else []
        
        # Popular FAQs
        popular_faqs = FAQ.objects.filter(
            is_active=True,
            show_on_website=True
        ).order_by('-view_count')[:10]
        
        context.update({
            'categories': categories,
            'faq_types': faq_types,
            'popular_faqs': popular_faqs,
            'current_category': self.request.GET.get('category'),
            'current_type': self.request.GET.get('type'),
            'search_query': self.request.GET.get('q', ''),
        })
        
        return context


class FAQDetailView(DetailView):
    """FAQ detail view"""
    model = FAQ
    template_name = 'cms/faq_detail.html'
    context_object_name = 'faq'
    
    def get_object(self, queryset=None):
        slug = self.kwargs.get('slug')
        obj = get_object_or_404(
            FAQ.objects.select_related('category'),
            slug=slug,
            is_active=True,
            show_on_website=True
        )
        return obj
    
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        
        # Increment view count
        faq = self.get_object()
        faq.increment_view_count()
        
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        faq = self.get_object()
        
        # Get related FAQs
        related_faqs = faq.get_related_faqs()
        
        # Get related content pages
        related_pages = faq.related_pages.filter(is_active=True, status='published')[:5]
        
        context.update({
            'related_faqs': related_faqs,
            'related_pages': related_pages,
        })
        
        return context


class FAQCategoryListView(ListView):
    """List FAQ categories"""
    model = FAQCategory
    template_name = 'cms/faq_category_list.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        return FAQCategory.objects.filter(
            is_active=True
        ).prefetch_related(
            'faqs'
        ).order_by('order')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get FAQs count per category
        for category in context['categories']:
            category.faq_count = category.faqs.filter(is_active=True).count()
        
        return context


# ==============================================
# File and Image Management Views
# ==============================================

class FileManagerListView(ListView):
    """List all files"""
    model = FileManager
    template_name = 'cms/file_list.html'
    context_object_name = 'files'
    paginate_by = 30
    
    def get_queryset(self):
        queryset = FileManager.objects.filter(is_active=True)
        
        # Filter by file type
        file_type = self.request.GET.get('type')
        if file_type:
            queryset = queryset.filter(file_type=file_type)
        
        # Filter by category
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Search
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['file_types'] = FileManager.FILE_TYPES
        context['categories'] = ContentCategory.objects.filter(is_active=True)
        return context


class ImageGalleryListView(ListView):
    """List image galleries (public view)"""
    model = ImageGallery
    template_name = 'cms/gallery_list.html'
    context_object_name = 'galleries'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = ImageGallery.objects.filter(is_active=True)
        
        # Filter by category
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Search
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(tags__contains=[search_query])
            )
        
        # Featured filter
        featured = self.request.GET.get('featured')
        if featured:
            queryset = queryset.filter(is_featured=True)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = ContentCategory.objects.filter(is_active=True)
        return context


class ImageGalleryDetailView(DetailView):
    """View image gallery details"""
    model = ImageGallery
    template_name = 'cms/gallery_detail.html'
    context_object_name = 'gallery'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        gallery = self.get_object()
        
        # Get images in this gallery
        images = gallery.images.filter(is_active=True).order_by('order')
        
        context['images'] = images
        return context


# ==============================================
# Comment Views
# ==============================================

class CommentCreateView(LoginRequiredMixin, CreateView):
    """Create new comment"""
    model = Comment
    form_class = CommentForm
    template_name = 'cms/comment_form.html'
    
    def form_valid(self, form):
        # Set user and content object
        form.instance.user = self.request.user
        
        # Get content type and object ID from request
        content_type_id = self.request.POST.get('content_type_id')
        object_id = self.request.POST.get('object_id')
        
        if content_type_id and object_id:
            from django.contrib.contenttypes.models import ContentType
            content_type = ContentType.objects.get_for_id(content_type_id)
            form.instance.content_type = content_type
            form.instance.object_id = object_id
        
        # Auto-approve for trusted users
        if hasattr(self.request.user, 'is_trusted') and self.request.user.is_trusted:
            form.instance.is_approved = True
        
        response = super().form_valid(form)
        
        # Add success message
        if form.instance.is_approved:
            messages.success(self.request, 'Comment posted successfully!')
        else:
            messages.success(self.request, 'Comment submitted for review. It will appear after approval.')
        
        return response
    
    def get_success_url(self):
        # Redirect back to the content page
        content_obj = self.object.content_object
        if hasattr(content_obj, 'get_absolute_url'):
            return content_obj.get_absolute_url()
        return '/'


@login_required
def toggle_comment_like(request, comment_id):
    """Toggle like on a comment"""
    try:
        comment = Comment.objects.get(id=comment_id, is_active=True)
        
        # Check if user already liked this comment
        like_exists = CommentLike.objects.filter(
            comment=comment,
            user=request.user
        ).exists()
        
        if like_exists:
            # Unlike
            CommentLike.objects.filter(
                comment=comment,
                user=request.user
            ).delete()
            
            # Decrement like count
            Comment.objects.filter(id=comment_id).update(
                like_count=F('like_count') - 1
            )
            liked = False
            message = 'Comment unliked'
        else:
            # Like
            CommentLike.objects.create(
                comment=comment,
                user=request.user
            )
            
            # Increment like count (handled by signal)
            liked = True
            message = 'Comment liked'
        
        return JsonResponse({
            'success': True,
            'liked': liked,
            'like_count': comment.like_count,
            'message': message
        })
    
    except Comment.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Comment not found'}, status=404)
    
    except Exception as e:
        logger.error(f"Error toggling comment like: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==============================================
# API Views
# ==============================================

class ContentAPIView(APIView):
    """Content API endpoint"""
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get(self, request):
        """Get content list"""
        content_type = request.GET.get('type', 'all')
        limit = int(request.GET.get('limit', 10))
        offset = int(request.GET.get('offset', 0))
        
        queryset = ContentPage.objects.filter(
            status='published',
            is_active=True,
            published_date__lte=timezone.now()
        )
        
        if content_type != 'all':
            queryset = queryset.filter(page_type=content_type)
        
        # Apply ordering
        sort_by = request.GET.get('sort', '-published_date')
        if sort_by in ['published_date', '-published_date', 'title', '-title', 'view_count', '-view_count']:
            queryset = queryset.order_by(sort_by)
        
        # Pagination
        total_count = queryset.count()
        content_list = queryset[offset:offset + limit]
        
        # Serialize data
        data = []
        for content in content_list:
            data.append({
                'id': content.id,
                'uuid': str(content.uuid),
                'title': content.title,
                'slug': content.slug,
                'excerpt': content.excerpt,
                'featured_image': content.featured_image.url if content.featured_image else None,
                'category': content.category.name if content.category else None,
                'category_slug': content.category.slug if content.category else None,
                'published_date': content.published_date.isoformat() if content.published_date else None,
                'view_count': content.view_count,
                'reading_time': content.reading_time,
                'url': request.build_absolute_uri(content.get_absolute_url()),
            })
        
        return Response({
            'success': True,
            'data': data,
            'total_count': total_count,
            'limit': limit,
            'offset': offset
        })


class BannerAPIView(APIView):
    """Banner API endpoint"""
    authentication_classes = []
    permission_classes = []
    
    def get(self, request):
        """Get active banners for a specific position"""
        position = request.GET.get('position', 'top')
        device = request.GET.get('device', 'all')
        
        # Get banners using manager
        banners = Banner.objects.get_for_position(position, device)[:5]
        
        data = []
        for banner in banners:
            data.append({
                'id': banner.id,
                'uuid': str(banner.uuid),
                'name': banner.name,
                'title': banner.title,
                'description': banner.description,
                'image_url': banner.image.url if banner.image else None,
                'mobile_image_url': banner.mobile_image.url if banner.mobile_image else None,
                'link_url': banner.get_click_url(),
                'link_type': banner.link_type,
                'banner_type': banner.banner_type,
                'position': banner.position,
                'reward_amount': float(banner.reward_amount) if banner.reward_amount else None,
                'reward_type': banner.reward_type,
            })
        
        return Response({
            'success': True,
            'data': data,
            'count': len(data)
        })


class FAQAPIView(APIView):
    """FAQ API endpoint"""
    authentication_classes = []
    permission_classes = []
    
    def get(self, request):
        """Get FAQs"""
        category_slug = request.GET.get('category')
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        queryset = FAQ.objects.filter(
            is_active=True,
            show_in_app=True
        ).select_related('category')
        
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        # Apply ordering
        sort_by = request.GET.get('sort', '-priority')
        if sort_by in ['priority', '-priority', 'question', '-question', 'view_count', '-view_count']:
            queryset = queryset.order_by(sort_by)
        
        # Pagination
        total_count = queryset.count()
        faq_list = queryset[offset:offset + limit]
        
        # Serialize data
        data = []
        for faq in faq_list:
            data.append({
                'id': faq.id,
                'uuid': str(faq.uuid),
                'question': faq.question,
                'short_answer': faq.short_answer,
                'slug': faq.slug,
                'category': faq.category.name if faq.category else None,
                'category_slug': faq.category.slug if faq.category else None,
                'priority': faq.priority,
                'view_count': faq.view_count,
                'helpful_percentage': faq.helpful_percentage,
                'url': request.build_absolute_uri(faq.get_absolute_url()) if request else None,
            })
        
        return Response({
            'success': True,
            'data': data,
            'total_count': total_count,
            'limit': limit,
            'offset': offset
        })


# ==============================================
# Utility Views
# ==============================================

@login_required
def increment_content_share(request, content_id):
    """Increment share count for content"""
    try:
        content = ContentPage.objects.get(id=content_id, is_active=True)
        content.increment_share_count()
        
        # Record share
        platform = request.GET.get('platform', 'other')
        ContentShare.objects.create(
            content=content,
            user=request.user if request.user.is_authenticated else None,
            share_platform=platform,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return JsonResponse({
            'success': True,
            'share_count': content.share_count,
            'message': 'Share recorded successfully'
        })
    
    except ContentPage.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Content not found'}, status=404)
    
    except Exception as e:
        logger.error(f"Error recording share: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def record_faq_feedback(request, faq_id):
    """Record FAQ helpfulness feedback"""
    try:
        faq = FAQ.objects.get(id=faq_id, is_active=True)
        
        is_helpful = request.GET.get('helpful', 'true').lower() == 'true'
        feedback_text = request.GET.get('feedback', '')
        
        faq.record_feedback(
            is_helpful=is_helpful,
            user=request.user if request.user.is_authenticated else None,
            feedback_text=feedback_text,
            request=request
        )
        
        return JsonResponse({
            'success': True,
            'helpful_count': faq.helpful_count,
            'not_helpful_count': faq.not_helpful_count,
            'helpful_percentage': faq.helpful_percentage,
            'message': 'Feedback recorded successfully'
        })
    
    except FAQ.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'FAQ not found'}, status=404)
    
    except Exception as e:
        logger.error(f"Error recording FAQ feedback: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def bulk_content_actions(request):
    """Bulk actions for content (delete, publish, etc.)"""
    try:
        data = json.loads(request.body)
        action = data.get('action')
        content_ids = data.get('content_ids', [])
        
        if not content_ids:
            return JsonResponse({'success': False, 'error': 'No content IDs provided'})
        
        if action == 'delete':
            # Soft delete content
            ContentPage.objects.filter(id__in=content_ids).update(is_active=False)
            message = f'{len(content_ids)} content items deleted'
        
        elif action == 'publish':
            # Publish content
            ContentPage.objects.filter(id__in=content_ids).update(
                status='published',
                published_date=timezone.now()
            )
            message = f'{len(content_ids)} content items published'
        
        elif action == 'draft':
            # Move to draft
            ContentPage.objects.filter(id__in=content_ids).update(status='draft')
            message = f'{len(content_ids)} content items moved to draft'
        
        elif action == 'feature':
            # Toggle featured status
            ContentPage.objects.filter(id__in=content_ids).update(
                is_featured=models.Case(
                    models.When(is_featured=True, then=models.Value(False)),
                    default=models.Value(True)
                )
            )
            message = f'{len(content_ids)} content items featured status toggled'
        
        else:
            return JsonResponse({'success': False, 'error': 'Invalid action'})
        
        return JsonResponse({
            'success': True,
            'message': message,
            'count': len(content_ids)
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    
    except Exception as e:
        logger.error(f"Error in bulk content actions: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def site_search(request):
    """Global site search"""
    query = request.GET.get('q', '')
    search_type = request.GET.get('type', 'all')
    
    results = {
        'content': [],
        'faqs': [],
        'categories': [],
        'total_results': 0
    }
    
    if query:
        # Search in content
        if search_type in ['all', 'content']:
            content_results = ContentPage.objects.filter(
                Q(title__icontains=query) |
                Q(subtitle__icontains=query) |
                Q(excerpt__icontains=query) |
                Q(content__icontains=query) |
                Q(tags__contains=[query]),
                status='published',
                is_active=True
            ).select_related('category')[:10]
            
            results['content'] = content_results
        
        # Search in FAQs
        if search_type in ['all', 'faq']:
            faq_results = FAQ.objects.filter(
                Q(question__icontains=query) |
                Q(short_answer__icontains=query) |
                Q(detailed_answer__icontains=query) |
                Q(tags__contains=[query]),
                is_active=True,
                show_on_website=True
            ).select_related('category')[:10]
            
            results['faqs'] = faq_results
        
        # Search in categories
        if search_type in ['all', 'category']:
            category_results = ContentCategory.objects.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(seo_description__icontains=query),
                is_active=True
            )[:10]
            
            results['categories'] = category_results
        
        # Calculate total results
        results['total_results'] = (
            len(results['content']) +
            len(results['faqs']) +
            len(results['categories'])
        )
    
    return render(request, 'cms/search_results.html', {
        'query': query,
        'results': results,
        'search_type': search_type
    })


# ==============================================
# RSS Feed Views
# ==============================================

class LatestContentFeed(Feed):
    """RSS feed for latest content"""
    title = "Latest Content"
    link = "/content/"
    description = "Latest published content"
    
    def items(self):
        return ContentPage.objects.filter(
            status='published',
            is_active=True,
            published_date__lte=timezone.now()
        ).order_by('-published_date')[:20]
    
    def item_title(self, item):
        return item.title
    
    def item_description(self, item):
        return item.excerpt or item.content[:500] + "..."
    
    def item_link(self, item):
        return item.get_absolute_url()
    
    def item_pubdate(self, item):
        return item.published_date
    
    def item_categories(self, item):
        return [item.get_page_type_display()]
    
    def item_author_name(self, item):
        return item.author.get_full_name() if item.author else "Admin"


class AtomLatestContentFeed(LatestContentFeed):
    """Atom feed for latest content"""
    feed_type = Atom1Feed
    subtitle = LatestContentFeed.description


# ==============================================
# Sitemap Views
# ==============================================

class ContentPageSitemap(Sitemap):
    """Sitemap for content pages"""
    changefreq = "weekly"
    priority = 0.8
    
    def items(self):
        return ContentPage.objects.filter(
            status='published',
            is_active=True,
            published_date__lte=timezone.now()
        ).order_by('-published_date')
    
    def lastmod(self, obj):
        return obj.updated_at
    
    def location(self, obj):
        return obj.get_absolute_url()


class FAQSitemap(Sitemap):
    """Sitemap for FAQs"""
    changefreq = "monthly"
    priority = 0.6
    
    def items(self):
        return FAQ.objects.filter(
            is_active=True,
            show_on_website=True
        ).order_by('-priority')
    
    def lastmod(self, obj):
        return obj.last_updated
    
    def location(self, obj):
        return obj.get_absolute_url()


class ContentCategorySitemap(Sitemap):
    """Sitemap for content categories"""
    changefreq = "monthly"
    priority = 0.7
    
    def items(self):
        return ContentCategory.objects.filter(
            is_active=True,
            show_on_website=True
        ).order_by('order')
    
    def location(self, obj):
        return obj.get_absolute_url()

# ═══════════════════════════════════════════════════════════════════
#  DRF API VIEWSETS — JWT Authentication
# ═══════════════════════════════════════════════════════════════════
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import (
    ContentCategorySerializer, ContentPageSerializer, ContentPageListSerializer,
    BannerSerializer, FAQCategorySerializer, FAQSerializer,
    SiteSettingsSerializer, ImageGallerySerializer, GalleryImageSerializer,
    FileManagerSerializer, CommentSerializer, SiteAnalyticsSerializer,
)

class ContentCategoryViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ContentCategorySerializer
    def get_queryset(self):
        qs = ContentCategory.objects.all()
        if self.request.query_params.get("is_active"):
            qs = qs.filter(is_active=True)
        return qs.order_by("order", "name")

class ContentPageViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get_serializer_class(self):
        if self.action == "list":
            return ContentPageListSerializer
        return ContentPageSerializer
    def get_queryset(self):
        qs = ContentPage.objects.select_related("category", "author").all()
        status_f = self.request.query_params.get("status")
        if status_f:
            qs = qs.filter(status=status_f)
        return qs.order_by("-created_at")
    @action(detail=False, methods=["get"])
    def published(self, request):
        qs = ContentPage.objects.filter(status="published", is_active=True)
        s = ContentPageListSerializer(qs, many=True)
        return Response({"results": s.data})
    @action(detail=False, methods=["get"])
    def featured(self, request):
        qs = ContentPage.objects.filter(is_featured=True, status="published")
        s = ContentPageListSerializer(qs, many=True)
        return Response({"results": s.data})
    @action(detail=False, methods=["get"])
    def stats(self, request):
        from django.db.models import Count
        total = ContentPage.objects.count()
        published = ContentPage.objects.filter(status="published").count()
        draft = ContentPage.objects.filter(status="draft").count()
        featured = ContentPage.objects.filter(is_featured=True).count()
        return Response({"total": total, "published": published, "draft": draft, "featured": featured})

class BannerViewSet(viewsets.ModelViewSet):
    @action(detail=False, methods=["get"])
    def stats(self, request):
        from django.db.models import Count
        total = self.get_queryset().count()
        active = self.get_queryset().filter(is_active=True).count() if hasattr(self.get_queryset().model, "is_active") else 0
        return Response({"total": total, "active": active, "inactive": total - active})

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = BannerSerializer
    def get_queryset(self):
        qs = Banner.objects.all()
        if self.request.query_params.get("is_active"):
            qs = qs.filter(is_active=True)
        return qs.order_by("-created_at")

class FAQCategoryViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = FAQCategorySerializer
    queryset = FAQCategory.objects.all().order_by("order")

class FAQViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = FAQSerializer
    def get_queryset(self):
        qs = FAQ.objects.select_related("category").all()
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(question__icontains=q)
        return qs.order_by("-priority", "order")

class ImageGalleryViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ImageGallerySerializer
    queryset = ImageGallery.objects.all().order_by("-created_at")

class GalleryImageViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = GalleryImageSerializer
    queryset = GalleryImage.objects.select_related("gallery").all().order_by("-created_at")

class FileManagerViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = FileManagerSerializer
    queryset = FileManager.objects.all().order_by("-created_at")

class CommentViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = CommentSerializer
    def get_queryset(self):
        qs = Comment.objects.select_related("user").all()
        if self.request.query_params.get("is_approved") == "false":
            qs = qs.filter(is_approved=False)
        return qs.order_by("-created_at")
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        comment = self.get_object()
        comment.is_approved = True
        comment.save()
        return Response({"success": True})
    @action(detail=True, methods=["post"])
    def flag(self, request, pk=None):
        comment = self.get_object()
        comment.is_flagged = True
        comment.save()
        return Response({"success": True})

class SiteAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = SiteAnalyticsSerializer
    def get_queryset(self):
        return SiteAnalytics.objects.all().order_by("-date")
    @action(detail=False, methods=["get"])
    def today(self, request):
        from django.utils import timezone
        today = timezone.now().date()
        obj, _ = SiteAnalytics.objects.get_or_create(date=today)
        s = SiteAnalyticsSerializer(obj)
        return Response(s.data)


# ── SiteSettings ViewSet ──────────────────────────────────────
from rest_framework import viewsets as vs2
class SiteSettingsViewSet(vs2.ModelViewSet):
    permission_classes = [__import__('rest_framework.permissions', fromlist=['IsAdminUser']).IsAdminUser]
    def get_queryset(self):
        from .models import SiteSettings
        return SiteSettings.objects.all()
    def get_serializer_class(self):
        return SiteSettingsSerializer

# ── ContentPermission ViewSet ─────────────────────────────────
class ContentPermissionViewSet(vs2.ModelViewSet):
    permission_classes = [__import__('rest_framework.permissions', fromlist=['IsAdminUser']).IsAdminUser]
    def get_queryset(self):
        from .models import ContentPermission
        return ContentPermission.objects.all()
    def get_serializer_class(self):
        from .serializers import ContentPermissionSerializer
        return ContentPermissionSerializer

    @action(detail=False, methods=['post'])
    def check(self, request):
        from .models import ContentPermission, ContentPage
        content_id = request.data.get('content_id')
        perm_type  = request.data.get('perm_type', 'read')
        try:
            content = ContentPage.objects.get(pk=content_id)
            has_perm = ContentPermission.check_permission(content, request.user, perm_type)
            return CR({'has_permission': has_perm})
        except: return CR({'has_permission': False})
