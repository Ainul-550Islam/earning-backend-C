from django.contrib.sitemaps import Sitemap
from django.utils import timezone
from django.urls import reverse
from .models import ContentPage, FAQ, ContentCategory


class ContentPageSitemap(Sitemap):
    """Sitemap for content pages"""
    changefreq = "weekly"
    priority = 0.8
    
    def items(self):
        """Get all published content pages"""
        return ContentPage.objects.filter(
            status='published',
            is_active=True,
            published_date__lte=timezone.now()
        ).order_by('-published_date')
    
    def lastmod(self, obj):
        """Last modification date"""
        return obj.updated_at
    
    def location(self, obj):
        """URL for the content page"""
        return obj.get_absolute_url()
    
    def protocol(self):
        """Protocol to use (http/https)"""
        return 'https'


class FAQSitemap(Sitemap):
    """Sitemap for FAQs"""
    changefreq = "monthly"
    priority = 0.6
    
    def items(self):
        """Get all active FAQs"""
        return FAQ.objects.filter(
            is_active=True,
            show_on_website=True
        ).order_by('-priority')
    
    def lastmod(self, obj):
        """Last modification date"""
        return obj.last_updated
    
    def location(self, obj):
        """URL for the FAQ"""
        return obj.get_absolute_url()
    
    def protocol(self):
        """Protocol to use"""
        return 'https'


class ContentCategorySitemap(Sitemap):
    """Sitemap for content categories"""
    changefreq = "monthly"
    priority = 0.7
    
    def items(self):
        """Get all active categories"""
        return ContentCategory.objects.filter(
            is_active=True,
            show_in_menu=True  # শুধুমাত্র menu-তে show করার categories
        ).order_by('order')
    
    def lastmod(self, obj):
        """Last modification date"""
        return obj.updated_at
    
    def location(self, obj):
        """URL for the category"""
        return obj.get_absolute_url()
    
    def protocol(self):
        """Protocol to use"""
        return 'https'