from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework.routers import DefaultRouter
from django.contrib.sitemaps.views import sitemap
from .sitemaps import ContentPageSitemap, FAQSitemap, ContentCategorySitemap
from .views import ContentAPIView, BannerAPIView, FAQAPIView

from . import views

app_name = 'api.cms'

# Sitemaps
sitemaps = {
    'content': ContentPageSitemap,
    'faq': FAQSitemap,
    'category': ContentCategorySitemap,
}

urlpatterns = [
    # Dashboard and Home
    path('', ContentAPIView.as_view(), name='cms-api'),
    path('', views.DashboardView.as_view(), name='dashboard'),
    # path('analytics/', views.AnalyticsDashboardView.as_view(), name='analytics_dashboard'),
    path('', ContentAPIView.as_view(), name='cms-overview'),
    path('banners/', BannerAPIView.as_view(), name='cms-banners'),
    path('faqs/', FAQAPIView.as_view(), name='cms-faqs'),
    
    # Content Categories
    path('categories/', views.ContentCategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.ContentCategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/', views.ContentCategoryDetailView.as_view(), name='category_detail'),
    path('categories/<int:pk>/update/', views.ContentCategoryUpdateView.as_view(), name='category_update'),
    path('categories/<int:pk>/delete/', views.ContentCategoryDeleteView.as_view(), name='category_delete'),
    
    # Content Pages
    path('content/', views.ContentPageListView.as_view(), name='content_list'),
    path('content/create/', views.ContentPageCreateView.as_view(), name='content_create'),
    path('content/<slug:slug>/', views.ContentPageDetailView.as_view(), name='content_detail'),
    path('content/<slug:slug>/update/', views.ContentPageUpdateView.as_view(), name='content_update'),
    path('content/<slug:slug>/delete/', views.ContentPageDeleteView.as_view(), name='content_delete'),
    path('content/<int:pk>/preview/', views.ContentPagePreviewView.as_view(), name='content_preview'),
    
    # Banners
    path('banners/', views.BannerListView.as_view(), name='banner_list'),
    path('banners/create/', views.BannerCreateView.as_view(), name='banner_create'),
    path('banners/<int:pk>/', views.BannerDetailView.as_view(), name='banner_detail'),
    path('banners/<int:pk>/update/', views.BannerUpdateView.as_view(), name='banner_update'),
    path('banners/<int:pk>/delete/', views.BannerDeleteView.as_view(), name='banner_delete'),
    path('api/banners/<int:banner_id>/click/', views.record_banner_click, name='banner_click'),
    
    # FAQs
    path('faqs/', views.FAQListView.as_view(), name='faq_list'),
    path('faqs/categories/', views.FAQCategoryListView.as_view(), name='faq_category_list'),
    path('faqs/<slug:slug>/', views.FAQDetailView.as_view(), name='faq_detail'),
    path('api/faqs/<int:faq_id>/feedback/', views.record_faq_feedback, name='faq_feedback'),
    
    # File Management
    # path('files/', views.FileManagerListView.as_view(), name='file_list'),
    path('galleries/', views.ImageGalleryListView.as_view(), name='gallery_list'),
    path('galleries/<slug:slug>/', views.ImageGalleryDetailView.as_view(), name='gallery_detail'),
    
    # Comments
    path('comments/create/', views.CommentCreateView.as_view(), name='comment_create'),
    path('api/comments/<int:comment_id>/like/', views.toggle_comment_like, name='comment_like'),
    
    # Search
    path('search/', views.site_search, name='search'),
    
    # API Endpoints
    path('api/content/', views.ContentAPIView.as_view(), name='api_content'),
    path('api/banners/', views.BannerAPIView.as_view(), name='api_banners'),
    path('api/faqs/', views.FAQAPIView.as_view(), name='api_faqs'),
    path('banners/<int:banner_id>/click/', views.record_banner_click, name='api_banner_click'),
    path('faqs/<int:faq_id>/feedback/', views.record_faq_feedback, name='api_faq_feedback'),
    path('content/<int:content_id>/share/', views.increment_content_share, name='api_content_share'),
    path('comments/<int:comment_id>/like/', views.toggle_comment_like, name='api_comment_like'),
    path('bulk-content-actions/', views.bulk_content_actions, name='api_bulk_actions'),
    
    # Utility
    path('api/content/<int:content_id>/share/', views.increment_content_share, name='content_share'),
    path('api/bulk-content-actions/', views.bulk_content_actions, name='bulk_content_actions'),
    
    # RSS Feeds
    path('feeds/latest/', views.LatestContentFeed(), name='content_feed'),
    path('feeds/latest/atom/', views.AtomLatestContentFeed(), name='content_feed_atom'),
    
    # Sitemap
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    
    # Redirects for old URLs
    path('blog/', RedirectView.as_view(pattern_name='cms:content_list', query_string=True)),
    path('news/', RedirectView.as_view(pattern_name='cms:content_list', query_string=True, permanent=True)),


]
# ═══════════════════════════════════════════════════
#  DRF API VIEWSETS ROUTER
# ═══════════════════════════════════════════════════
from rest_framework.routers import DefaultRouter
from .views import (
    SiteSettingsViewSet, ContentPermissionViewSet,
    ContentCategoryViewSet, ContentPageViewSet, BannerViewSet,
    FAQCategoryViewSet, FAQViewSet, ImageGalleryViewSet,
    GalleryImageViewSet, FileManagerViewSet, CommentViewSet,
    SiteAnalyticsViewSet,
)
api_router = DefaultRouter()
api_router.register(r"categories", ContentCategoryViewSet, basename="cms-category")
api_router.register(r"pages", ContentPageViewSet, basename="cms-page")
api_router.register(r"banners", BannerViewSet, basename="cms-banner")
api_router.register(r"faq-categories", FAQCategoryViewSet, basename="cms-faqcat")
api_router.register(r"faqs", FAQViewSet, basename="cms-faq")
api_router.register(r"galleries", ImageGalleryViewSet, basename="cms-gallery")
api_router.register(r"gallery-images", GalleryImageViewSet, basename="cms-gallery-image")
api_router.register(r"files", FileManagerViewSet, basename="cms-file")
api_router.register(r"comments", CommentViewSet, basename="cms-comment")
api_router.register(r"analytics", SiteAnalyticsViewSet, basename="cms-analytics")
api_router.register(r"settings", SiteSettingsViewSet, basename="cms-settings")
api_router.register(r"permissions", ContentPermissionViewSet, basename="cms-permission")
from django.urls import include
urlpatterns += [path("", include(api_router.urls))]
