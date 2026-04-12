# admin.py

from django.contrib import admin
from django.contrib.admin import ModelAdmin, TabularInline, StackedInline
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.db.models import Count, Sum, Avg, Q
from django.http import HttpResponseRedirect
import logging
from typing import Optional, Dict, Any, List, Tuple
import json
from datetime import datetime, timedelta
from decimal import Decimal
import mimetypes
import csv
from django.contrib.admin import ModelAdmin, actions
from django.contrib.admin.views.main import ChangeList
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q, Sum, Count, Avg
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.http import urlencode
from .models import  NOT_FOUND, MISSING, INVALID, LOCKED
from .utils import safe_int, safe_str, safe_decimal, safe_bool, safe_now
from django.contrib.auth import get_user_model
from django.apps import apps 

User = get_user_model()



import os
print("--- CMS ADMIN LOADED ---")

# Import your models
from .models import (
    ContentCategory, ContentPage, Banner, FAQCategory, FAQ, 
    BannerImpression, BannerClick, BannerReward, FAQFeedback,
    ContentViewLog, ContentShare, SiteSettings, ImageGallery,
    GalleryImage, FileManager, Comment, CommentLike, SiteAnalytics,
    ContentPermission
)

logger = logging.getLogger(__name__)

# ============================================
# HELPER FUNCTIONS AND DECORATORS (Defensive)
# ============================================

class SafeAccessMixin:
    """Mixin for safe attribute access with defensive coding"""
    
    @staticmethod
    def safe_getattr(obj, attr: str, default: Any = None, raise_exception: bool = False) -> Any:
        """
        Safely get attribute from object using getattr() with defensive fallback
        Uses Null Object Pattern for default values
        """
        try:
            value = getattr(obj, attr, default)
            
            # Handle callable attributes
            if callable(value):
                try:
                    return value()
                except Exception as e:
                    logger.warning(f"Error calling {attr} on {obj}: {e}")
                    return default
            
            return value
        except AttributeError as e:
            if raise_exception:
                raise
            logger.debug(f"Attribute {attr} not found on {obj}: {e}")
            return default
        except Exception as e:
            logger.error(f"Unexpected error accessing {attr} on {obj}: {e}")
            return default
    
    @staticmethod
    def safe_dict_get(data: Dict, keys: List, default: Any = None) -> Any:
        """
        Safe deep dictionary access (Chain get)
        Uses Walrus Operator (Python 3.8+) for concise checking
        """
        if not isinstance(data, dict):
            return default
        
        current = data
        for key in keys:
            if not isinstance(current, dict):
                return default
            if (value := current.get(key)) is None:
                return default
            current = value
        return current
    
    @staticmethod
    def create_sentinel():
        """Create a unique sentinel object for missing values"""
        class Sentinel:
            def __repr__(self):
                return "<SENTINEL>"
            def __str__(self):
                return "SENTINEL"
        return Sentinel()

# ============================================
# CUSTOM FILTERS AND ACTIONS
# ============================================

class IsActiveFilter(admin.SimpleListFilter):
    """Custom filter for active status"""
    title = _('Active Status')
    parameter_name = 'is_active'
    
    def lookups(self, request, model_admin):
        return (
            ('active', _('Active')),
            ('inactive', _('Inactive')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(is_active=True)
        if self.value() == 'inactive':
            return queryset.filter(is_active=False)
        return queryset


class StatusFilter(admin.SimpleListFilter):
    """Custom filter for content status"""
    title = _('Content Status')
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return (
            ('published', _('Published')),
            ('draft', _('Draft')),
            ('scheduled', _('Scheduled')),
            ('expired', _('Expired')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'published':
            return queryset.filter(status='published')
        if self.value() == 'draft':
            return queryset.filter(status='draft')
        if self.value() == 'scheduled':
            return queryset.filter(status='scheduled')
        if self.value() == 'expired':
            return queryset.filter(status='expired')
        return queryset


class DateRangeFilter(admin.SimpleListFilter):
    """Custom filter for date ranges"""
    title = _('Date Range')
    parameter_name = 'date_range'
    
    def lookups(self, request, model_admin):
        return (
            ('today', _('Today')),
            ('yesterday', _('Yesterday')),
            ('this_week', _('This Week')),
            ('last_7_days', _('Last 7 Days')),
            ('this_month', _('This Month')),
            ('last_30_days', _('Last 30 Days')),
        )
    
    def queryset(self, request, queryset):
        now = datetime.now()
        
        if self.value() == 'today':
            today = now.date()
            return queryset.filter(created_at__date=today)
        
        if self.value() == 'yesterday':
            yesterday = (now - timedelta(days=1)).date()
            return queryset.filter(created_at__date=yesterday)
        
        if self.value() == 'this_week':
            start_of_week = now - timedelta(days=now.weekday())
            return queryset.filter(created_at__date__gte=start_of_week.date())
        
        if self.value() == 'last_7_days':
            last_week = now - timedelta(days=7)
            return queryset.filter(created_at__gte=last_week)
        
        if self.value() == 'this_month':
            start_of_month = now.replace(day=1)
            return queryset.filter(created_at__gte=start_of_month)
        
        if self.value() == 'last_30_days':
            last_month = now - timedelta(days=30)
            return queryset.filter(created_at__gte=last_month)
        
        return queryset

# ============================================
# INLINE ADMIN CLASSES
# ============================================

class ContentPageInline(TabularInline):
    """Inline for showing pages in category admin"""
    model = ContentPage
    fields = ('title', 'status_badge', 'view_count', 'author', 'published_date')
    readonly_fields = ('status_badge', 'view_count', 'published_date')
    extra = 0
    max_num = 10
    can_delete = False
    show_change_link = True
    
    def status_badge(self, obj):
        """Color badge for status"""
        status_colors = {
            'published': 'success',
            'draft': 'secondary',
            'review': 'warning',
            'approved': 'info',
            'scheduled': 'primary',
            'archived': 'dark',
            'expired': 'danger',
        }
        color = status_colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = _('Status')


class FAQInline(TabularInline):
    """Inline for showing FAQs in category admin"""
    model = FAQ
    fields = ('question', 'priority_badge', 'view_count', 'is_featured_icon')
    readonly_fields = ('priority_badge', 'view_count', 'is_featured_icon')
    extra = 0
    max_num = 10
    
    def priority_badge(self, obj):
        """Color badge for priority"""
        priority_colors = {
            1: 'secondary',  # Low
            2: 'info',       # Medium
            3: 'warning',    # High
            4: 'danger',     # Critical
        }
        color = priority_colors.get(obj.priority, 'secondary')
        return format_html(
            '<span class="badge badge-{}">Priority: {}</span>',
            color, obj.priority
        )
    priority_badge.short_description = _('Priority')
    
    def is_featured_icon(self, obj):
        """Boolean icon for featured status"""
        if obj.is_featured:
            return format_html(
                '<span style="color: green; font-size: 1.2em;">✓</span>'
            )
        return format_html(
            '<span style="color: gray; font-size: 1.2em;">✗</span>'
        )
    is_featured_icon.short_description = _('Featured')


class GalleryImageInline(StackedInline):
    """Inline for gallery images"""
    model = GalleryImage
    fields = ('image_preview', 'title', 'alt_text', 'caption', 'order', 'view_count')
    readonly_fields = ('image_preview', 'view_count')
    extra = 1
    max_num = 20
    
    def image_preview(self, obj):
        """Image preview in admin"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 150px;" />',
                obj.image.url
            )
        return _("No image")
    image_preview.short_description = _('Preview')


class BannerImpressionInline(TabularInline):
    """Inline for banner impressions"""
    model = BannerImpression
    fields = ('user', 'impression_type', 'device_type', 'created_at')
    readonly_fields = ('user', 'impression_type', 'device_type', 'created_at')
    extra = 0
    max_num = 5
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


class BannerClickInline(TabularInline):
    """Inline for banner clicks"""
    model = BannerClick
    fields = ('user', 'click_type', 'conversion_value', 'created_at')
    readonly_fields = ('user', 'click_type', 'conversion_value', 'created_at')
    extra = 0
    max_num = 5
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


class CommentReplyInline(TabularInline):
    """Inline for comment replies"""
    model = Comment
    fields = ('user', 'comment_preview', 'is_approved_icon', 'created_at')
    readonly_fields = ('comment_preview', 'is_approved_icon', 'created_at')
    extra = 0
    max_num = 5
    fk_name = 'parent'
    
    def comment_preview(self, obj):
        """Preview comment with truncation"""
        comment = obj.comment
        if len(comment) > 100:
            return f"{comment[:100]}..."
        return comment
    comment_preview.short_description = _('Comment')
    
    def is_approved_icon(self, obj):
        """Boolean icon for approval status"""
        if obj.is_approved:
            return format_html(
                '<span style="color: green; font-size: 1.2em;">✓</span>'
            )
        return format_html(
            '<span style="color: red; font-size: 1.2em;">✗</span>'
        )
    is_approved_icon.short_description = _('Approved')


# ============================================
# MAIN ADMIN CLASSES
# ============================================

@admin.register(ContentCategory)
class ContentCategoryAdmin(SafeAccessMixin, ModelAdmin):
    """Admin for ContentCategory with defensive coding"""
    
    # Fields configuration
    list_display = (
        'name_with_icon', 
        'category_type_badge', 
        'parent_link',
        'content_count_progress',
        'is_active_badge',
        'order',
        'created_at'
    )
    
    list_filter = (
        IsActiveFilter,
        'category_type',
        'show_in_menu',
        'show_in_footer',
        DateRangeFilter,
    )
    
    search_fields = (
        'name', 
        'slug', 
        'description',
        'seo_title',
        'seo_keywords'
    )
    
    readonly_fields = (
        'thumbnail_preview',
        'total_views',
        'total_content',
        'created_at',
        'updated_at',
        'breadcrumbs_display',
    )
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'slug', 'description', 'category_type'),
            'classes': ('wide',),
        }),
        (_('Display Settings'), {
            'fields': (
                'icon', 
                'thumbnail_preview',
                'order', 
                'is_active',
                'show_in_menu', 
                'show_in_footer',
                'show_in_app',
                'parent',
                'breadcrumbs_display'
            ),
            'classes': ('wide',),
        }),
        (_('SEO Settings'), {
            'fields': ('seo_title', 'seo_description', 'seo_keywords'),
            'classes': ('collapse',),
        }),
        (_('Earning Settings'), {
            'fields': ('min_reward', 'max_reward', 'reward_currency'),
            'classes': ('collapse',),
        }),
        (_('Statistics'), {
            'fields': ('total_views', 'total_content'),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    inlines = [ContentPageInline]
    
    actions = ['activate_categories', 'deactivate_categories', 'update_content_counts']
    
    # Help texts for defensive UX
    help_texts = {
        'slug': _('URL-friendly version of the name. Use hyphens instead of spaces.'),
        'parent': _('Select parent category to create hierarchy.'),
        'min_reward': _('Minimum reward amount for this category.'),
        'max_reward': _('Maximum reward amount for this category.'),
    }
    
    # Custom methods with defensive coding
    def name_with_icon(self, obj):
        """Display name with icon"""
        icon = self.safe_getattr(obj, 'icon', '📁')
        name = self.safe_getattr(obj, 'name', 'Unknown')
        return format_html(f'{icon} {name}')
    name_with_icon.short_description = _('Name')
    name_with_icon.admin_order_field = 'name'
    
    def category_type_badge(self, obj):
        """Color badge for category type"""
        type_colors = {
            'page': 'primary',
            'blog': 'info',
            'news': 'warning',
            'tutorial': 'success',
            'policy': 'secondary',
            'help': 'light',
            'offer': 'danger',
            'task': 'dark',
        }
        category_type = self.safe_getattr(obj, 'category_type', 'page')
        display = self.safe_getattr(obj, 'get_category_type_display', lambda: 'Page')()
        color = type_colors.get(category_type, 'secondary')
        
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, display
        )
    category_type_badge.short_description = _('Type')
    category_type_badge.admin_order_field = 'category_type'
    
    def parent_link(self, obj):
        """Clickable parent link"""
        parent = self.safe_getattr(obj, 'parent')
        if parent:
            url = reverse('admin:cms_contentcategory_change', args=[parent.id])
            return format_html(
                '<a href="{}">{}</a>',
                url, parent.name
            )
        return _("No Parent")
    parent_link.short_description = _('Parent')
    
    def content_count_progress(self, obj):
        """Progress bar for content count"""
        count = self.safe_getattr(obj, 'total_content', 0)
        max_count = 100  # Adjust based on your needs
        
        percentage = min((count / max_count) * 100, 100) if max_count > 0 else 0
        
        # Color based on percentage
        if percentage > 80:
            color = 'danger'
        elif percentage > 50:
            color = 'warning'
        else:
            color = 'success'
        
        return format_html(
            '''
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="flex-grow: 1;">
                    <div class="progress" style="height: 10px;">
                        <div class="progress-bar bg-{}" 
                             role="progressbar" 
                             style="width: {}%" 
                             aria-valuenow="{}" 
                             aria-valuemin="0" 
                             aria-valuemax="100">
                        </div>
                    </div>
                </div>
                <span>{}</span>
            </div>
            ''',
            color, percentage, percentage, count
        )
    content_count_progress.short_description = _('Content Count')
    content_count_progress.admin_order_field = 'total_content'
    
    def is_active_badge(self, obj):
        """Boolean badge for active status"""
        is_active = self.safe_getattr(obj, 'is_active', False)
        
        if is_active:
            return format_html(
                '<span class="badge badge-success">{}</span>',
                _('Active')
            )
        return format_html(
            '<span class="badge badge-danger">{}</span>',
            _('Inactive')
        )
    is_active_badge.short_description = _('Status')
    is_active_badge.admin_order_field = 'is_active'
    
    def thumbnail_preview(self, obj):
        """Thumbnail preview in admin"""
        thumbnail = self.safe_getattr(obj, 'thumbnail')
        if thumbnail and hasattr(thumbnail, 'url'):
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 150px;" />',
                thumbnail.url
            )
        return _("No thumbnail")
    thumbnail_preview.short_description = _('Thumbnail Preview')
    
    def breadcrumbs_display(self, obj):
        """Display breadcrumbs hierarchy"""
        try:
            breadcrumbs = obj.get_breadcrumbs() if hasattr(obj, 'get_breadcrumbs') else []
            if not breadcrumbs:
                return _("No parent categories")
            
            html_parts = []
            for idx, bc in enumerate(breadcrumbs):
                if idx > 0:
                    html_parts.append(' → ')
                html_parts.append(
                    f'<span class="badge badge-light">{bc.get("name", "Unknown")}</span>'
                )
            
            return format_html(''.join(html_parts))
        except Exception as e:
            logger.error(f"Error getting breadcrumbs: {e}")
            return _("Error loading breadcrumbs")
    breadcrumbs_display.short_description = _('Breadcrumbs')
    
    # Custom actions with defensive coding
    def activate_categories(self, request, queryset):
        """Activate selected categories with error handling"""
        try:
            updated = queryset.update(is_active=True)
            self.message_user(
                request, 
                f'Successfully activated {updated} categories.',
                messages.SUCCESS
            )
        except Exception as e:
            logger.error(f"Error activating categories: {e}")
            self.message_user(
                request,
                f'Error activating categories: {str(e)}',
                messages.ERROR
            )
    activate_categories.short_description = _('Activate selected categories')
    
    def deactivate_categories(self, request, queryset):
        """Deactivate selected categories"""
        try:
            updated = queryset.update(is_active=False)
            self.message_user(
                request,
                f'Successfully deactivated {updated} categories.',
                messages.SUCCESS
            )
        except Exception as e:
            logger.error(f"Error deactivating categories: {e}")
            self.message_user(
                request,
                f'Error deactivating categories: {str(e)}',
                messages.ERROR
            )
    deactivate_categories.short_description = _('Deactivate selected categories')
    
    def update_content_counts(self, request, queryset):
        """Update content counts for selected categories"""
        try:
            for category in queryset:
                if hasattr(category, 'update_content_count'):
                    category.update_content_count()
            
            self.message_user(
                request,
                f'Updated content counts for {queryset.count()} categories.',
                messages.SUCCESS
            )
        except Exception as e:
            logger.error(f"Error updating content counts: {e}")
            self.message_user(
                request,
                f'Error updating content counts: {str(e)}',
                messages.ERROR
            )
    update_content_counts.short_description = _('Update content counts')
    
    # Override save_model with defensive coding
    def save_model(self, request, obj, form, change):
        """Save model with defensive error handling"""
        try:
            # Graceful degradation: Set defaults if missing
            if not obj.slug:
                from django.utils.text import slugify
                obj.slug = slugify(obj.name)
            
            if not obj.order:
                max_order = ContentCategory.objects.aggregate(Max('order'))['order__max'] or 0
                obj.order = max_order + 10
            
            super().save_model(request, obj, form, change)
            
            # Clear cache after save
            cache.delete(f'category_breadcrumbs_{obj.id}')
            
        except Exception as e:
            logger.error(f"Error saving ContentCategory {obj.id}: {e}")
            self.message_user(
                request,
                f'Error saving category: {str(e)}',
                messages.ERROR
            )
            raise


@admin.register(ContentPage)
class ContentPageAdmin(SafeAccessMixin, ModelAdmin):
    """Admin for ContentPage with bulletproof design"""
    
    # Fields configuration
    list_display = (
        'title_with_status',
        'category_link',
        'page_type_badge',
        'author_link',
        'view_count_badge',
        'published_date_display',
        'is_active_icon',
    )
    
    list_filter = (
        StatusFilter,
        IsActiveFilter,
        'page_type',
        'visibility',
        'category',
        'author',
        DateRangeFilter,
    )
    
    search_fields = (
        'title',
        'slug',
        'subtitle',
        'excerpt',
        'content',
        'meta_title',
        'meta_keywords',
    )
    
    readonly_fields = (
        'uuid',
        'view_count',
        'share_count',
        'like_count',
        'comment_count',
        'reading_time_display',
        'last_viewed',
        'created_at',
        'updated_at',
        'featured_image_preview',
        'thumbnail_preview',
        'version_info',
        'tags_display', 
        'requirements_display',
    )
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'title', 
                'slug', 
                'subtitle',
                'uuid',
                'version_info',
            ),
            'classes': ('wide',),
        }),
        (_('Categorization'), {
            'fields': (
                'category',
                'page_type',
                'tags_display',
                'language',
                'is_translation',
                'original_content',
            ),
            'classes': ('wide',),
        }),
        (_('Content'), {
            'fields': (
                'excerpt',
                'content',
                'featured_image',
                'featured_image_preview',
                'thumbnail',
                'thumbnail_preview',
            ),
            'classes': ('wide',),
        }),
        (_('Metadata'), {
            'fields': (
                'author',
                'status',
                'visibility',
                'is_active',
                'is_featured',
                'is_pinned',
                'allow_comments',
            ),
            'classes': ('wide',),
        }),
        (_('Dates'), {
            'fields': (
                'published_date',
                'scheduled_date',
                'expiry_date',
                'last_viewed',
            ),
            'classes': ('collapse',),
        }),
        (_('SEO Settings'), {
            'fields': (
                'meta_title',
                'meta_description',
                'meta_keywords',
                'canonical_url',
            ),
            'classes': ('collapse',),
        }),
        (_('Earning Settings'), {
            'fields': (
                'related_offer',
                'related_task',
                'min_reward',
                'max_reward',
                'reward_currency',
                'completion_time',
                'difficulty_level',
                'requirements_display',
            ),
            'classes': ('collapse',),
        }),
        (_('Statistics'), {
            'fields': (
                'view_count',
                'share_count',
                'like_count',
                'comment_count',
                'reading_time_display',
            ),
            'classes': ('collapse',),
        }),
        (_('Version Control'), {
            'fields': (
                'version',
                'parent_version',
            ),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    actions = [
        'publish_selected',
        'unpublish_selected',
        'duplicate_content',
        'reset_view_counts',
        'export_as_json',
    ]
    
    def tags_display(self, obj):
        return ", ".join([tag.name for tag in obj.tags.all()]) if hasattr(obj, 'tags') else "No Tags"
    tags_display.short_description = 'Tags'

    def requirements_display(self, obj):
        return obj.requirements if hasattr(obj, 'requirements') else "No Requirements"
    requirements_display.short_description = 'Requirements'
    
    # Custom methods
    def title_with_status(self, obj):
        """Title with status badge"""
        title = self.safe_getattr(obj, 'title', 'Untitled')
        status = self.safe_getattr(obj, 'status', 'draft')
        
        status_colors = {
            'published': 'success',
            'draft': 'secondary',
            'review': 'warning',
            'approved': 'info',
            'scheduled': 'primary',
            'archived': 'dark',
            'expired': 'danger',
        }
        
        color = status_colors.get(status, 'secondary')
        display_status = self.safe_getattr(obj, 'get_status_display', lambda: 'Draft')()
        
        return format_html(
            '''
            <div style="display: flex; align-items: center; gap: 8px;">
                <span class="badge badge-{}" style="min-width: 80px;">{}</span>
                <span>{}</span>
            </div>
            ''',
            color, display_status, title
        )
    title_with_status.short_description = _('Title')
    title_with_status.admin_order_field = 'title'
    
    def category_link(self, obj):
        """Clickable category link"""
        category = self.safe_getattr(obj, 'category')
        if category:
            url = reverse('admin:cms_contentcategory_change', args=[category.id])
            return format_html(
                '<a href="{}">{}</a>',
                url, category.name
            )
        return _("No Category")
    category_link.short_description = _('Category')
    category_link.admin_order_field = 'category__name'
    
    def page_type_badge(self, obj):
        """Badge for page type"""
        page_type = self.safe_getattr(obj, 'page_type', 'static')
        display = self.safe_getattr(obj, 'get_page_type_display', lambda: 'Static Page')()
        
        type_colors = {
            'static': 'secondary',
            'blog': 'info',
            'news': 'primary',
            'tutorial': 'success',
            'policy': 'warning',
            'offer_detail': 'danger',
            'task_guide': 'dark',
            'earning_tip': 'light',
            'announcement': 'info',
        }
        
        color = type_colors.get(page_type, 'secondary')
        
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, display
        )
    page_type_badge.short_description = _('Type')
    page_type_badge.admin_order_field = 'page_type'
    
    def author_link(self, obj):
        """Clickable author link"""
        author = self.safe_getattr(obj, 'author')
        if author:
            url = reverse('admin:users_user_change', args=[author.id])
            return format_html(
                '<a href="{}">{}</a>',
                url, author.get_full_name() or author.username
            )
        return _("No Author")
    author_link.short_description = _('Author')
    author_link.admin_order_field = 'author__username'
    
    def view_count_badge(self, obj):
        """Badge with view count"""
        view_count = self.safe_getattr(obj, 'view_count', 0)
        
        # Color based on view count
        if view_count > 1000:
            color = 'danger'
        elif view_count > 100:
            color = 'warning'
        elif view_count > 10:
            color = 'info'
        else:
            color = 'secondary'
        
        return format_html(
            '<span class="badge badge-{}">👁️ {}</span>',
            color, view_count
        )
    view_count_badge.short_description = _('Views')
    view_count_badge.admin_order_field = 'view_count'
    
    def published_date_display(self, obj):
        """Formatted published date"""
        published_date = self.safe_getattr(obj, 'published_date')
        if published_date:
            from django.utils.formats import date_format
            return date_format(published_date, "SHORT_DATETIME_FORMAT")
        return _("Not published")
    published_date_display.short_description = _('Published')
    published_date_display.admin_order_field = 'published_date'
    
    def is_active_icon(self, obj):
        """Boolean icon for active status"""
        is_active = self.safe_getattr(obj, 'is_active', False)
        is_featured = self.safe_getattr(obj, 'is_featured', False)
        
        icons = []
        if is_active:
            icons.append('<span style="color: green;" title="Active">●</span>')
        else:
            icons.append('<span style="color: red;" title="Inactive">●</span>')
        
        if is_featured:
            icons.append('<span style="color: gold;" title="Featured">★</span>')
        
        return format_html(' '.join(icons))
    is_active_icon.short_description = _('Status')
    
    def featured_image_preview(self, obj):
        """Featured image preview"""
        image = self.safe_getattr(obj, 'featured_image')
        if image and hasattr(image, 'url'):
            return format_html(
                '''
                <div>
                    <img src="{}" style="max-height: 200px; max-width: 300px;" />
                    <div><small>{}</small></div>
                </div>
                ''',
                image.url, image.name if hasattr(image, 'name') else ''
            )
        return _("No featured image")
    featured_image_preview.short_description = _('Featured Image Preview')
    
    def thumbnail_preview(self, obj):
        """Thumbnail preview"""
        thumbnail = self.safe_getattr(obj, 'thumbnail')
        if thumbnail and hasattr(thumbnail, 'url'):
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 150px;" />',
                thumbnail.url
            )
        return _("No thumbnail")
    thumbnail_preview.short_description = _('Thumbnail Preview')
    
    def reading_time_display(self, obj):
        """Display reading time"""
        reading_time = self.safe_getattr(obj, 'reading_time', 0)
        return f"{reading_time} min"
    reading_time_display.short_description = _('Reading Time')
    
    def version_info(self, obj):
        """Display version information"""
        version = self.safe_getattr(obj, 'version', 1)
        parent = self.safe_getattr(obj, 'parent_version')
        
        if parent:
            parent_url = reverse('admin:cms_contentpage_change', args=[parent.id])
            return format_html(
                'Version {} of <a href="{}">{}</a>',
                version, parent_url, parent.title
            )
        return f"Version {version} (Original)"
    version_info.short_description = _('Version Information')
    
    def tags_display(self, obj):
        """Display tags as badges"""
        tags = self.safe_getattr(obj, 'tags', [])
        if not tags:
            return _("No tags")
        
        badges = []
        for tag in tags[:10]:  # Limit to 10 tags
            badges.append(
                f'<span class="badge badge-info" style="margin: 2px;">{tag}</span>'
            )
        
        if len(tags) > 10:
            badges.append(f'<span class="badge badge-light">+{len(tags)-10} more</span>')
        
        return format_html(' '.join(badges))
    tags_display.short_description = _('Tags')
    
    def requirements_display(self, obj):
        """Display requirements as formatted JSON"""
        requirements = self.safe_getattr(obj, 'requirements', {})
        if not requirements:
            return _("No requirements")
        
        try:
            formatted = json.dumps(requirements, indent=2, ensure_ascii=False)
            return format_html('<pre style="background: #f8f9fa; padding: 10px;">{}</pre>', formatted)
        except:
            return str(requirements)
    requirements_display.short_description = _('Requirements')
    
    # Custom actions
    def publish_selected(self, request, queryset):
        """Publish selected content"""
        try:
            now = timezone.now()
            updated = queryset.update(
                status='published',
                published_date=now,
                is_active=True
            )
            self.message_user(
                request,
                f'Successfully published {updated} content items.',
                messages.SUCCESS
            )
        except Exception as e:
            logger.error(f"Error publishing content: {e}")
            self.message_user(
                request,
                f'Error publishing content: {str(e)}',
                messages.ERROR
            )
    publish_selected.short_description = _('Publish selected content')
    
    def unpublish_selected(self, request, queryset):
        """Unpublish selected content"""
        try:
            updated = queryset.update(status='draft', is_active=False)
            self.message_user(
                request,
                f'Successfully unpublished {updated} content items.',
                messages.SUCCESS
            )
        except Exception as e:
            logger.error(f"Error unpublishing content: {e}")
            self.message_user(
                request,
                f'Error unpublishing content: {str(e)}',
                messages.ERROR
            )
    unpublish_selected.short_description = _('Unpublish selected content')
    
    def duplicate_content(self, request, queryset):
        """Duplicate selected content"""
        try:
            count = 0
            for obj in queryset:
                new_obj = obj.create_new_version() if hasattr(obj, 'create_new_version') else None
                if new_obj:
                    count += 1
            
            self.message_user(
                request,
                f'Successfully duplicated {count} content items.',
                messages.SUCCESS
            )
        except Exception as e:
            logger.error(f"Error duplicating content: {e}")
            self.message_user(
                request,
                f'Error duplicating content: {str(e)}',
                messages.ERROR
            )
    duplicate_content.short_description = _('Duplicate selected content')
    
    def reset_view_counts(self, request, queryset):
        """Reset view counts for selected content"""
        try:
            updated = queryset.update(view_count=0, last_viewed=None)
            self.message_user(
                request,
                f'Reset view counts for {updated} content items.',
                messages.SUCCESS
            )
        except Exception as e:
            logger.error(f"Error resetting view counts: {e}")
            self.message_user(
                request,
                f'Error resetting view counts: {str(e)}',
                messages.ERROR
            )
    reset_view_counts.short_description = _('Reset view counts')
    
    def export_as_json(self, request, queryset):
        """Export selected content as JSON"""
        try:
            import json
            from django.http import JsonResponse
            
            data = []
            for obj in queryset:
                # Use model_to_dict with defensive coding
                from django.forms.models import model_to_dict
                obj_dict = model_to_dict(obj)
                
                # Add additional fields
                obj_dict['absolute_url'] = obj.get_absolute_url() if hasattr(obj, 'get_absolute_url') else ''
                obj_dict['reading_time'] = obj.reading_time if hasattr(obj, 'reading_time') else 0
                
                data.append(obj_dict)
            
            response = JsonResponse(data, safe=False, json_dumps_params={'indent': 2})
            response['Content-Disposition'] = 'attachment; filename="content_export.json"'
            return response
            
        except Exception as e:
            logger.error(f"Error exporting content: {e}")
            self.message_user(
                request,
                f'Error exporting content: {str(e)}',
                messages.ERROR
            )
            return None
    export_as_json.short_description = _('Export as JSON')


@admin.register(Banner)
class BannerAdmin(SafeAccessMixin, ModelAdmin):
    """Admin for Banner with performance metrics"""
    
    list_display = (
        'name_with_preview',
        'banner_type_badge',
        'position_badge',
        'performance_score_bar',
        'status_badge',
        'impression_click_stats',
        'days_remaining_badge',
    )
    
    list_filter = (
        IsActiveFilter,
        'banner_type',
        'position',
        'target_device',
        'reward_type',
        DateRangeFilter,
    )
    
    search_fields = ('name', 'title', 'description')
    
    readonly_fields = (
        'uuid',
        'impression_count',
        'click_count',
        'required_tags_display',
        'excluded_tags_display',
        'target_audience_display',
        'conversion_count',
        'total_revenue',
        'click_through_rate',
        'conversion_rate',
        'performance_score',
        'days_remaining',
        'image_preview',
        'mobile_image_preview',
        'created_at',
        'updated_at',
    )
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'uuid', 'banner_type', 'position'),
            'classes': ('wide',),
        }),
        (_('Content'), {
            'fields': (
                'title',
                'description',
                'image',
                'image_preview',
                'mobile_image',
                'mobile_image_preview',
            ),
            'classes': ('wide',),
        }),
        (_('Links & Actions'), {
            'fields': (
                'link_type',
                'link_url',
                'internal_page',
                'offer',
                'task',
            ),
            'classes': ('wide',),
        }),
        (_('Display Settings'), {
            'fields': (
                'is_active',
                'start_date',
                'end_date',
                'priority',
                'max_impressions',
                'max_clicks',
                'display_frequency',
            ),
            'classes': ('wide',),
        }),
        (_('Targeting'), {
            'fields': (
                'target_device',
                'target_audience_display',
                'required_tags_display',
                'excluded_tags_display',
                'min_user_level',
            ),
            'classes': ('collapse',),
        }),
        (_('Earning Settings'), {
            'fields': (
                'reward_amount',
                'reward_type',
                'max_rewards_per_user',
            ),
            'classes': ('collapse',),
        }),
        (_('Statistics'), {
            'fields': (
                'impression_count',
                'click_count',
                'conversion_count',
                'total_revenue',
                'click_through_rate',
                'conversion_rate',
                'performance_score',
                'days_remaining',
            ),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    inlines = [BannerImpressionInline, BannerClickInline]
    
    actions = ['activate_banners', 'deactivate_banners', 'reset_stats']
    
    # Custom methods
    def name_with_preview(self, obj):
        """Name with thumbnail preview"""
        name = self.safe_getattr(obj, 'name', 'Unnamed')
        thumbnail = self.safe_getattr(obj, 'thumbnail')
        
        if thumbnail and hasattr(thumbnail, 'url'):
            return format_html(
                '''
                <div style="display: flex; align-items: center; gap: 10px;">
                    <img src="{}" style="height: 30px; width: 50px; object-fit: cover;" />
                    <span>{}</span>
                </div>
                ''',
                thumbnail.url, name
            )
        return name
    name_with_preview.short_description = _('Name')
    
    def banner_type_badge(self, obj):
        """Badge for banner type"""
        banner_type = self.safe_getattr(obj, 'banner_type', 'hero')
        display = self.safe_getattr(obj, 'get_banner_type_display', lambda: 'Hero Banner')()
        
        type_colors = {
            'hero': 'primary',
            'sidebar': 'info',
            'inline': 'success',
            'popup': 'warning',
            'notification': 'danger',
            'interstitial': 'dark',
            'rewarded': 'light',
        }
        
        color = type_colors.get(banner_type, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, display
        )
    banner_type_badge.short_description = _('Type')
    
    def position_badge(self, obj):
        """Badge for position"""
        position = self.safe_getattr(obj, 'position', 'top')
        return format_html(
            '<span class="badge badge-secondary">{}</span>',
            position.title()
        )
    position_badge.short_description = _('Position')
    
    def performance_score_bar(self, obj):
        """Progress bar for performance score"""
        score = self.safe_getattr(obj, 'performance_score', 0)
        
        # Color based on score
        if score > 80:
            color = 'success'
        elif score > 50:
            color = 'warning'
        else:
            color = 'danger'
        
        return format_html(
            '''
            <div style="display: flex; align-items: center; gap: 8px;">
                <div style="flex-grow: 1;">
                    <div class="progress" style="height: 10px;">
                        <div class="progress-bar bg-{}" 
                             role="progressbar" 
                             style="width: {}%" 
                             aria-valuenow="{}" 
                             aria-valuemin="0" 
                             aria-valuemax="100">
                        </div>
                    </div>
                </div>
                <small>{:.1f}</small>
            </div>
            ''',
            color, score, score, score
        )
    performance_score_bar.short_description = _('Performance')
    
    def status_badge(self, obj):
        """Status badge with active check"""
        is_active = self.safe_getattr(obj, 'is_active', False)
        is_active_now = obj.is_active_now() if hasattr(obj, 'is_active_now') else False
        
        if is_active_now:
            return format_html(
                '<span class="badge badge-success" title="Currently active">Active</span>'
            )
        elif is_active:
            return format_html(
                '<span class="badge badge-warning" title="Configured but not currently showing">Inactive</span>'
            )
        else:
            return format_html(
                '<span class="badge badge-danger">Disabled</span>'
            )
    status_badge.short_description = _('Status')
    
    def impression_click_stats(self, obj):
        """Display impression and click stats"""
        impressions = self.safe_getattr(obj, 'impression_count', 0)
        clicks = self.safe_getattr(obj, 'click_count', 0)
        ctr = self.safe_getattr(obj, 'click_through_rate', 0)
        
        return format_html(
            '''
            <div style="font-size: 0.9em;">
                <div>👁️ {:,}</div>
                <div>👆 {:,}</div>
                <div>📈 {:.1f}%</div>
            </div>
            ''',
            impressions, clicks, ctr
        )
    impression_click_stats.short_description = _('Stats')
    
    def days_remaining_badge(self, obj):
        """Badge showing days remaining"""
        days = self.safe_getattr(obj, 'days_remaining')
        if days is None:
            return format_html('<span class="badge badge-info">No End Date</span>')
        
        if days < 0:
            return format_html('<span class="badge badge-danger">Expired</span>')
        elif days < 7:
            return format_html('<span class="badge badge-warning">{} days</span>', days)
        else:
            return format_html('<span class="badge badge-success">{} days</span>', days)
    days_remaining_badge.short_description = _('Expires In')
    
    def image_preview(self, obj):
        """Image preview"""
        image = self.safe_getattr(obj, 'image')
        if image and hasattr(image, 'url'):
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 300px;" />',
                image.url
            )
        return _("No image")
    image_preview.short_description = _('Image Preview')
    
    def mobile_image_preview(self, obj):
        """Mobile image preview"""
        mobile_image = self.safe_getattr(obj, 'mobile_image')
        if mobile_image and hasattr(mobile_image, 'url'):
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 150px;" />',
                mobile_image.url
            )
        return _("No mobile image")
    mobile_image_preview.short_description = _('Mobile Image Preview')
    
    def target_audience_display(self, obj):
        """Display target audience as formatted JSON"""
        audience = self.safe_getattr(obj, 'target_audience', {})
        if not audience:
            return _("No targeting")
        
        try:
            formatted = json.dumps(audience, indent=2, ensure_ascii=False)
            return format_html('<pre style="background: #f8f9fa; padding: 10px; font-size: 0.9em;">{}</pre>', formatted)
        except:
            return str(audience)
    target_audience_display.short_description = _('Target Audience')
    
    def required_tags_display(self, obj):
        """Display required tags as badges"""
        tags = self.safe_getattr(obj, 'required_tags', [])
        return self._format_tags_as_badges(tags, 'success')
    required_tags_display.short_description = _('Required Tags')
    
    def excluded_tags_display(self, obj):
        """Display excluded tags as badges"""
        tags = self.safe_getattr(obj, 'excluded_tags', [])
        return self._format_tags_as_badges(tags, 'danger')
    excluded_tags_display.short_description = _('Excluded Tags')
    
    def _format_tags_as_badges(self, tags, color_class):
        """Helper to format tags as badges"""
        if not tags:
            return _("None")
        
        badges = []
        for tag in tags[:5]:
            badges.append(
                f'<span class="badge badge-{color_class}" style="margin: 2px;">{tag}</span>'
            )
        
        if len(tags) > 5:
            badges.append(f'<span class="badge badge-light">+{len(tags)-5} more</span>')
        
        return format_html(' '.join(badges))


@admin.register(FAQCategory)
class FAQCategoryAdmin(SafeAccessMixin, ModelAdmin):
    """Admin for FAQCategory"""
    
    list_display = (
        'name_with_icon',
        'faq_type_badge',
        'faq_count_progress',
        'total_views_badge',
        'is_active_badge',
        'order',
    )
    
    list_filter = (IsActiveFilter, 'faq_type', DateRangeFilter)
    
    search_fields = ('name', 'slug', 'description')
    
    readonly_fields = ('faq_count', 'total_views', 'created_at', 'updated_at')
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'slug', 'description', 'faq_type'),
            'classes': ('wide',),
        }),
        (_('Display Settings'), {
            'fields': ('icon', 'order', 'is_active'),
            'classes': ('wide',),
        }),
        (_('Statistics'), {
            'fields': ('faq_count', 'total_views'),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    inlines = [FAQInline]
    
    actions = ['update_faq_counts']
    
    # Custom methods
    def name_with_icon(self, obj):
        icon = self.safe_getattr(obj, 'icon', '❓')
        name = self.safe_getattr(obj, 'name', 'Unknown')
        return format_html(f'{icon} {name}')
    name_with_icon.short_description = _('Name')
    
    def faq_type_badge(self, obj):
        faq_type = self.safe_getattr(obj, 'faq_type', 'general')
        display = self.safe_getattr(obj, 'get_faq_type_display', lambda: 'General')()
        
        type_colors = {
            'general': 'secondary',
            'earning': 'success',
            'withdrawal': 'warning',
            'account': 'info',
            'technical': 'danger',
            'offer': 'primary',
            'task': 'dark',
            'referral': 'light',
            'wallet': 'info',
            'security': 'danger',
        }
        
        color = type_colors.get(faq_type, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, display
        )
    faq_type_badge.short_description = _('Type')
    
    def faq_count_progress(self, obj):
        count = self.safe_getattr(obj, 'faq_count', 0)
        max_count = 50
        
        percentage = min((count / max_count) * 100, 100) if max_count > 0 else 0
        
        if percentage > 80:
            color = 'success'
        elif percentage > 50:
            color = 'warning'
        else:
            color = 'info'
        
        return format_html(
            '''
            <div style="display: flex; align-items: center; gap: 8px;">
                <div style="flex-grow: 1;">
                    <div class="progress" style="height: 10px;">
                        <div class="progress-bar bg-{}" 
                             role="progressbar" 
                             style="width: {}%" 
                             aria-valuenow="{}" 
                             aria-valuemin="0" 
                             aria-valuemax="100">
                        </div>
                    </div>
                </div>
                <span>{}</span>
            </div>
            ''',
            color, percentage, percentage, count
        )
    faq_count_progress.short_description = _('FAQ Count')
    
    def total_views_badge(self, obj):
        views = self.safe_getattr(obj, 'total_views', 0)
        
        if views > 1000:
            color = 'danger'
        elif views > 100:
            color = 'warning'
        elif views > 10:
            color = 'info'
        else:
            color = 'secondary'
        
        return format_html(
            '<span class="badge badge-{}">👁️ {}</span>',
            color, views
        )
    total_views_badge.short_description = _('Views')
    
    def is_active_badge(self, obj):
        from django.utils.html import format_html
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✔ Active</span>')
        return format_html('<span style="color: red; font-weight: bold;">✖ Inactive</span>')
    is_active_badge.short_description = 'Status'


@admin.register(FAQ)
class FAQAdmin(SafeAccessMixin, ModelAdmin):
    """Admin for FAQ"""
    
    list_display = (
        'question_preview',
        'category_link',
        'priority_badge',
        'view_count_badge',
        'helpful_percentage_bar',
        'is_featured_icon',
        'is_active_badge',
    )
    
    list_filter = (
        IsActiveFilter,
        'priority',
        'category',
        'is_featured',
        'show_in_app',
        'show_on_website',
        DateRangeFilter,
    )
    
    search_fields = ('question', 'short_answer', 'detailed_answer')
    
    readonly_fields = (
        'uuid',
        'view_count',
        'tags_display',
        'helpful_count',
        'not_helpful_count',
        'helpful_percentage',
        'created_at',
        'updated_at',
        'last_updated',
    )
    
    fieldsets = (
        (_('Question Information'), {
            'fields': ('question', 'slug', 'uuid'),
            'classes': ('wide',),
        }),
        (_('Answers'), {
            'fields': ('short_answer', 'detailed_answer'),
            'classes': ('wide',),
        }),
        (_('Categorization'), {
            'fields': ('category', 'tags_display'),
            'classes': ('wide',),
        }),
        (_('Display Settings'), {
            'fields': (
                'priority',
                'is_active',
                'is_featured',
                'is_pinned',
                'show_in_app',
                'show_on_website',
            ),
            'classes': ('wide',),
        }),
        (_('Related Content'), {
            'fields': ('related_pages', 'related_offers'),
            'classes': ('collapse',),
        }),
        (_('Statistics'), {
            'fields': (
                'view_count',
                'helpful_count',
                'not_helpful_count',
                'helpful_percentage',
            ),
            'classes': ('collapse',),
        }),
        (_('Metadata'), {
            'fields': ('updated_by', 'last_updated'),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    actions = ['mark_as_featured', 'mark_as_not_featured', 'reset_feedback_counts']
    
    # Custom methods
    def question_preview(self, obj):
        question = self.safe_getattr(obj, 'question', '')
        if len(question) > 80:
            return f"{question[:80]}..."
        return question
    question_preview.short_description = _('Question')
    
    def category_link(self, obj):
        category = self.safe_getattr(obj, 'category')
        if category:
            url = reverse('admin:cms_faqcategory_change', args=[category.id])
            return format_html(
                '<a href="{}">{}</a>',
                url, category.name
            )
        return _("No Category")
    category_link.short_description = _('Category')
    
    def priority_badge(self, obj):
        priority = self.safe_getattr(obj, 'priority', 2)
        
        priority_colors = {
            1: 'secondary',  # Low
            2: 'info',       # Medium
            3: 'warning',    # High
            4: 'danger',     # Critical
        }
        
        color = priority_colors.get(priority, 'secondary')
        display = self.safe_getattr(obj, 'get_priority_display', lambda: 'Medium')()
        
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, display
        )
    priority_badge.short_description = _('Priority')
    
    def view_count_badge(self, obj):
        view_count = self.safe_getattr(obj, 'view_count', 0)
        
        if view_count > 500:
            color = 'danger'
        elif view_count > 100:
            color = 'warning'
        elif view_count > 10:
            color = 'info'
        else:
            color = 'secondary'
        
        return format_html(
            '<span class="badge badge-{}">👁️ {}</span>',
            color, view_count
        )
    view_count_badge.short_description = _('Views')
    
    def helpful_percentage_bar(self, obj):
        percentage = self.safe_getattr(obj, 'helpful_percentage', 0)
        
        if percentage > 80:
            color = 'success'
        elif percentage > 50:
            color = 'warning'
        else:
            color = 'danger'
        
        return format_html(
            '''
            <div style="display: flex; align-items: center; gap: 8px;">
                <div style="flex-grow: 1;">
                    <div class="progress" style="height: 10px;">
                        <div class="progress-bar bg-{}" 
                             role="progressbar" 
                             style="width: {}%" 
                             aria-valuenow="{}" 
                             aria-valuemin="0" 
                             aria-valuemax="100">
                        </div>
                    </div>
                </div>
                <small>{:.1f}%</small>
            </div>
            ''',
            color, percentage, percentage, percentage
        )
    helpful_percentage_bar.short_description = _('Helpful')
    
    def is_featured_icon(self, obj):
        is_featured = self.safe_getattr(obj, 'is_featured', False)
        is_pinned = self.safe_getattr(obj, 'is_pinned', False)
        
        icons = []
        if is_featured:
            icons.append('<span style="color: gold;" title="Featured">★</span>')
        if is_pinned:
            icons.append('<span style="color: blue;" title="Pinned">📌</span>')
        
        if not icons:
            return _("No")
        
        return format_html(' '.join(icons))
    is_featured_icon.short_description = _('Flags')
    
    def is_active_badge(self, obj):
        is_active = self.safe_getattr(obj, 'is_active', False)
        
        if is_active:
            return format_html(
                '<span class="badge badge-success">{}</span>',
                _('Active')
            )
        return format_html(
            '<span class="badge badge-danger">{}</span>',
            _('Inactive')
        )
    is_active_badge.short_description = _('Status')
    
    def tags_display(self, obj):
        tags = self.safe_getattr(obj, 'tags', [])
        return self._format_tags_as_badges(tags)
    
    def _format_tags_as_badges(self, tags):
        if not tags:
            return _("No tags")
        
        badges = []
        for tag in tags[:8]:
            badges.append(
                f'<span class="badge badge-info" style="margin: 2px;">{tag}</span>'
            )
        
        if len(tags) > 8:
            badges.append(f'<span class="badge badge-light">+{len(tags)-8} more</span>')
        
        return format_html(' '.join(badges))
    
    def tags_display(self, obj):
        if hasattr(obj, 'tags') and obj.tags.exists():
            return ", ".join([t.name for t in obj.tags.all()])
        return "No Tags"
    tags_display.short_description = "Tags"


# ============================================
# REGISTER REMAINING MODELS
# ============================================

@admin.register(SiteSettings)
class SiteSettingsAdmin(SafeAccessMixin, ModelAdmin):
    list_display = ('key', 'category_badge', 'data_type_badge', 'is_public_icon', 'last_modified')
    list_filter = ('category', 'data_type', 'is_public', 'is_editable')
    search_fields = ('key', 'description', 'value')
    readonly_fields = ('uuid', 'last_modified', 'modified_by', 'created_at', 'updated_at', 'value_display',)
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('key', 'description', 'category', 'data_type'),
        }),
        (_('Value'), {
            'fields': ('value_display',),
        }),
        (_('Visibility'), {
            'fields': ('is_public', 'is_editable'),
        }),
        (_('Metadata'), {
            'fields': ('modified_by', 'last_modified', 'uuid'),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def value_display(self, obj):
        """Display value based on data type"""
        value = self.safe_getattr(obj, 'value', {})
        data_type = self.safe_getattr(obj, 'data_type', 'string')
        
        try:
            if data_type in ['array', 'object', 'json']:
                formatted = json.dumps(value, indent=2, ensure_ascii=False)
                return format_html('<pre style="background: #f8f9fa; padding: 10px;">{}</pre>', formatted)
            else:
                return str(value)
        except:
            return str(value)
    value_display.short_description = _('Value')
    
    def category_badge(self, obj):
        category = self.safe_getattr(obj, 'category', 'general')
        return format_html(
            '<span class="badge badge-secondary">{}</span>',
            category.title()
        )
    category_badge.short_description = _('Category')
    
    def data_type_badge(self, obj):
        data_type = self.safe_getattr(obj, 'data_type', 'string')
        
        type_colors = {
            'string': 'info',
            'number': 'warning',
            'boolean': 'success',
            'array': 'primary',
            'object': 'dark',
            'json': 'secondary',
        }
        
        color = type_colors.get(data_type, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, data_type.title()
        )
    data_type_badge.short_description = _('Type')
    
    def is_public_icon(self, obj):
        is_public = self.safe_getattr(obj, 'is_public', False)
        is_editable = self.safe_getattr(obj, 'is_editable', False)
        
        icons = []
        if is_public:
            icons.append('<span style="color: green;" title="Public">🌐</span>')
        else:
            icons.append('<span style="color: red;" title="Private">🔒</span>')
        
        if not is_editable:
            icons.append('<span style="color: orange;" title="Not Editable">[FIX]</span>')
        
        return format_html(' '.join(icons))
    is_public_icon.short_description = _('Flags')
    
    
    def value_display(self, obj):
        # এটি ভ্যালুটিকে সুন্দর করে দেখানোর জন্য
        if obj.value and len(str(obj.value)) > 50:
            return f"{str(obj.value)[:50]}..."
        return obj.value
    value_display.short_description = "Setting Value"


@admin.register(ImageGallery)
class ImageGalleryAdmin(SafeAccessMixin, ModelAdmin):
    list_display = ('title', 'category_link', 'image_count_badge', 'is_active_badge', 'created_at')
    list_filter = (IsActiveFilter, 'category', 'is_featured', DateRangeFilter)
    search_fields = ('title', 'slug', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at', 'tags_display',)
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('title', 'slug', 'description', 'uuid'),
        }),
        (_('Categorization'), {
            'fields': ('category', 'tags_display'),
        }),
        (_('Display Settings'), {
            'fields': ('is_active', 'is_featured'),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    inlines = [GalleryImageInline]
    
    def category_link(self, obj):
        category = self.safe_getattr(obj, 'category')
        if category:
            url = reverse('admin:cms_contentcategory_change', args=[category.id])
            return format_html('<a href="{}">{}</a>', url, category.name)
        return _("No Category")
    category_link.short_description = _('Category')
    
    def image_count_badge(self, obj):
        count = self.safe_getattr(obj, 'image_count', 0)
        
        if count > 50:
            color = 'danger'
        elif count > 20:
            color = 'warning'
        elif count > 5:
            color = 'info'
        else:
            color = 'secondary'
        
        return format_html(
            '<span class="badge badge-{}">🖼️ {}</span>',
            color, count
        )
    image_count_badge.short_description = _('Images')
    
    def is_active_badge(self, obj):
        from django.utils.html import format_html
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✔ Active</span>')
        return format_html('<span style="color: red; font-weight: bold;">✖ Inactive</span>')
    is_active_badge.short_description = 'Status'
    
    
    # ইমেজ প্রিভিউ এর জন্য (যদি লাগে)
    def image_preview(self, obj):
        from django.utils.html import format_html
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: auto; border-radius: 5px;" />', obj.image.url)
        return "No Image"
    
    def tags_display(self, obj):
        if hasattr(obj, 'tags') and obj.tags.exists():
            return ", ".join([t.name for t in obj.tags.all()])
        return "No Tags"


@admin.register(FileManager)
class FileManagerAdmin(SafeAccessMixin, ModelAdmin):
    list_display = ('name_with_icon', 'file_type_badge', 'file_size_human', 'download_count_badge', 'is_public_icon')
    list_filter = ('file_type', 'is_public', 'is_active', 'category', DateRangeFilter)
    search_fields = ('name', 'description', 'mime_type')
    readonly_fields = (
        'uuid', 'file_size', 'mime_type', 'file_size_human',
        'download_count', 'file_preview', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'file', 'uuid'),
        }),
        (_('File Properties'), {
            'fields': ('file_type', 'file_size_human', 'mime_type', 'file_preview'),
        }),
        (_('Description'), {
            'fields': ('description',),
        }),
        (_('Categorization'), {
            'fields': ('category',),
        }),
        (_('Access Control'), {
            'fields': ('is_public', 'is_active'),
        }),
        (_('Statistics'), {
            'fields': ('download_count',),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    actions = ['make_public', 'make_private', 'reset_download_counts']
    
    def name_with_icon(self, obj):
        file_type = self.safe_getattr(obj, 'file_type', 'other')
        name = self.safe_getattr(obj, 'name', 'Unknown')
        
        icons = {
            'document': '[DOC]',
            'archive': '📦',
            'video': '🎬',
            'audio': '🎵',
            'pdf': '📕',
            'spreadsheet': '[STATS]',
            'presentation': '📽️',
            'other': '📁',
        }
        
        icon = icons.get(file_type, '📁')
        return format_html(f'{icon} {name}')
    name_with_icon.short_description = _('Name')
    
    def file_type_badge(self, obj):
        file_type = self.safe_getattr(obj, 'file_type', 'other')
        
        type_colors = {
            'document': 'primary',
            'archive': 'secondary',
            'video': 'danger',
            'audio': 'warning',
            'pdf': 'danger',
            'spreadsheet': 'success',
            'presentation': 'info',
            'other': 'dark',
        }
        
        color = type_colors.get(file_type, 'dark')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, file_type.title()
        )
    file_type_badge.short_description = _('Type')
    
    def file_size_human(self, obj):
        return self.safe_getattr(obj, 'file_size_human', '0 B')
    file_size_human.short_description = _('Size')
    
    def download_count_badge(self, obj):
        count = self.safe_getattr(obj, 'download_count', 0)
        
        if count > 100:
            color = 'danger'
        elif count > 10:
            color = 'warning'
        elif count > 0:
            color = 'info'
        else:
            color = 'secondary'
        
        return format_html(
            '<span class="badge badge-{}">⬇️ {}</span>',
            color, count
        )
    download_count_badge.short_description = _('Downloads')
    
    def is_public_icon(self, obj):
        is_public = self.safe_getattr(obj, 'is_public', False)
        is_active = self.safe_getattr(obj, 'is_active', False)
        
        icons = []
        if is_public:
            icons.append('<span style="color: green;" title="Public">🌐</span>')
        else:
            icons.append('<span style="color: red;" title="Private">🔒</span>')
        
        if not is_active:
            icons.append('<span style="color: orange;" title="Inactive">🚫</span>')
        
        return format_html(' '.join(icons))
    is_public_icon.short_description = _('Access')
    
    def file_preview(self, obj):
        """File preview based on type"""
        file = self.safe_getattr(obj, 'file')
        file_type = self.safe_getattr(obj, 'file_type', 'other')
        
        if not file or not hasattr(file, 'url'):
            return _("No file")
        
        url = file.url
        name = self.safe_getattr(obj, 'name', 'file')
        
        if file_type in ['image', 'pdf']:
            return format_html(
                '''
                <div>
                    <a href="{}" target="_blank">
                        <div style="padding: 10px; border: 1px solid #ddd; display: inline-block;">
                            <div>[DOC] {}</div>
                            <div><small>Click to open</small></div>
                        </div>
                    </a>
                </div>
                ''',
                url, name
            )
        else:
            return format_html(
                '<a href="{}" target="_blank">📁 {}</a>',
                url, name
            )
    file_preview.short_description = _('Preview')


@admin.register(Comment)
class CommentAdmin(SafeAccessMixin, ModelAdmin):
    list_display = (
        'comment_preview',
        'user_link',
        'content_type_display',
        'is_approved_icon',
        'like_count_badge',
        'reply_count_badge',
        'created_at',
    )
    
    list_filter = (
        'comment_type',
        'is_approved',
        'is_flagged',
        'is_active',
        'content_type',
        DateRangeFilter,
    )
    
    search_fields = ('comment', 'user__username', 'user__email')
    
    readonly_fields = (
        'uuid',
        'like_count',
        'reply_count',
        'created_at',
        'updated_at',
        'moderated_at',
    )
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('uuid', 'user', 'comment_type', 'comment'),
        }),
        (_('Target Content'), {
            'fields': ('content_type', 'object_id', ),
        }),
        (_('Rating'), {
            'fields': ('rating',),
        }),
        (_('Status'), {
            'fields': ('is_approved', 'is_edited', 'edit_reason', 'is_active'),
        }),
        (_('Parent/Comment Thread'), {
            'fields': ('parent',),
        }),
        (_('Moderation'), {
            'fields': ('is_flagged', 'flag_reason', 'moderated_by', 'moderated_at'),
            'classes': ('collapse',),
        }),
        (_('Statistics'), {
            'fields': ('like_count', 'reply_count'),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    inlines = [CommentReplyInline]
    
    actions = [
        'approve_comments',
        'reject_comments',
        'flag_comments',
        'delete_comments',
    ]
    
    # Custom methods
    def comment_preview(self, obj):
        comment = self.safe_getattr(obj, 'comment', '')
        if len(comment) > 60:
            return f"{comment[:60]}..."
        return comment
    comment_preview.short_description = _('Comment')
    
    def user_link(self, obj):
        user = self.safe_getattr(obj, 'user')
        if user:
            url = reverse('admin:users_user_change', args=[user.id])
            return format_html(
                '<a href="{}">{}</a>',
                url, user.get_full_name() or user.username
            )
        return _("Anonymous")
    user_link.short_description = _('User')
    
    def content_type_display(self, obj):
        content_type = self.safe_getattr(obj, 'content_type')
        if content_type:
            return content_type.model.title()
        return _("Unknown")
    content_type_display.short_description = _('Content Type')
    
    def is_approved_icon(self, obj):
        is_approved = self.safe_getattr(obj, 'is_approved', False)
        is_flagged = self.safe_getattr(obj, 'is_flagged', False)
        
        if is_flagged:
            return format_html(
                '<span style="color: red;" title="Flagged">[WARN]</span>'
            )
        elif is_approved:
            return format_html(
                '<span style="color: green;" title="Approved">✓</span>'
            )
        else:
            return format_html(
                '<span style="color: orange;" title="Pending">⏳</span>'
            )
    is_approved_icon.short_description = _('Status')
    
    def like_count_badge(self, obj):
        count = self.safe_getattr(obj, 'like_count', 0)
        
        if count > 10:
            color = 'danger'
        elif count > 5:
            color = 'warning'
        elif count > 0:
            color = 'info'
        else:
            color = 'secondary'
        
        return format_html(
            '<span class="badge badge-{}">❤️ {}</span>',
            color, count
        )
    like_count_badge.short_description = _('Likes')
    
    def reply_count_badge(self, obj):
        count = self.safe_getattr(obj, 'reply_count', 0)
        
        if count > 5:
            color = 'danger'
        elif count > 2:
            color = 'warning'
        elif count > 0:
            color = 'info'
        else:
            color = 'secondary'
        
        return format_html(
            '<span class="badge badge-{}">💬 {}</span>',
            color, count
        )
    reply_count_badge.short_description = _('Replies')
    
    def content_object_link(self, obj):
        try:
            content_obj = obj.content_object
            if content_obj:
                # Try to get admin URL
                app_label = content_obj._meta.app_label
                model_name = content_obj._meta.model_name
                url = reverse(f'admin:{app_label}_{model_name}_change', args=[content_obj.id])
                return format_html(
                    '<a href="{}">{}</a>',
                    url, str(content_obj)
                )
        except:
            pass
        return _("Not available")
    content_object_link.short_description = _('Content Object')
    
    # Custom actions
    def approve_comments(self, request, queryset):
        try:
            updated = queryset.update(is_approved=True, is_flagged=False, moderated_by=request.user, moderated_at=timezone.now())
            self.message_user(request, f'Approved {updated} comments.', messages.SUCCESS)
        except Exception as e:
            logger.error(f"Error approving comments: {e}")
            self.message_user(request, f'Error: {str(e)}', messages.ERROR)
    approve_comments.short_description = _('Approve selected comments')
    
    def reject_comments(self, request, queryset):
        try:
            updated = queryset.update(is_approved=False, moderated_by=request.user, moderated_at=timezone.now())
            self.message_user(request, f'Rejected {updated} comments.', messages.SUCCESS)
        except Exception as e:
            logger.error(f"Error rejecting comments: {e}")
            self.message_user(request, f'Error: {str(e)}', messages.ERROR)
    reject_comments.short_description = _('Reject selected comments')
    
    def flag_comments(self, request, queryset):
        try:
            updated = queryset.update(is_flagged=True, moderated_by=request.user, moderated_at=timezone.now())
            self.message_user(request, f'Flagged {updated} comments for review.', messages.SUCCESS)
        except Exception as e:
            logger.error(f"Error flagging comments: {e}")
            self.message_user(request, f'Error: {str(e)}', messages.ERROR)
    flag_comments.short_description = _('Flag selected comments')
    
    def delete_comments(self, request, queryset):
        try:
            count = queryset.count()
            queryset.delete()
            self.message_user(request, f'Deleted {count} comments.', messages.SUCCESS)
        except Exception as e:
            logger.error(f"Error deleting comments: {e}")
            self.message_user(request, f'Error: {str(e)}', messages.ERROR)
    delete_comments.short_description = _('Delete selected comments')


@admin.register(SiteAnalytics)
class SiteAnalyticsAdmin(SafeAccessMixin, ModelAdmin):
    list_display = (
        'date',
        'page_views_badge',
        'unique_visitors_badge',
        'conversion_rate_bar',
        'total_earnings_badge',
        'engagement_rate_badge',
    )
    
    list_filter = (DateRangeFilter,)
    
    readonly_fields = ('uuid', 'created_at', 'updated_at', 'engagement_rate', 
        'conversion_rate', 
        'banner_ctr', 
        'net_earnings',)
    
    fieldsets = (
        (_('Date'), {
            'fields': ('date',),
        }),
        (_('Traffic Metrics'), {
            'fields': (
                'page_views',
                'unique_visitors',
                'new_users',
                'active_users',
                'session_count',
                'avg_session_duration',
                'bounce_rate',
            ),
        }),
        (_('Earning Metrics'), {
            'fields': (
                'total_earnings',
                'total_withdrawals',
                'offer_completions',
                'task_completions',
            ),
        }),
        (_('Content Metrics'), {
            'fields': (
                'content_views',
                'content_shares',
                'content_comments',
            ),
        }),
        (_('Banner Metrics'), {
            'fields': (
                'banner_impressions',
                'banner_clicks',
                'banner_conversions',
            ),
        }),
        (_('Calculated Metrics'), {
            'fields': (
                'conversion_rate',
                'net_earnings',
                'banner_ctr',
                'engagement_rate',
            ),
        }),
        (_('Metadata'), {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    # Custom methods
    def page_views_badge(self, obj):
        views = self.safe_getattr(obj, 'page_views', 0)
        
        if views > 10000:
            color = 'danger'
        elif views > 1000:
            color = 'warning'
        elif views > 100:
            color = 'info'
        else:
            color = 'secondary'
        
        return format_html(
            '<span class="badge badge-{}">[STATS] {:,}</span>',
            color, views
        )
    page_views_badge.short_description = _('Page Views')
    
    def unique_visitors_badge(self, obj):
        visitors = self.safe_getattr(obj, 'unique_visitors', 0)
        
        if visitors > 1000:
            color = 'danger'
        elif visitors > 100:
            color = 'warning'
        elif visitors > 10:
            color = 'info'
        else:
            color = 'secondary'
        
        return format_html(
            '<span class="badge badge-{}">👥 {:,}</span>',
            color, visitors
        )
    unique_visitors_badge.short_description = _('Unique Visitors')
    
    def conversion_rate_bar(self, obj):
        rate = self.safe_getattr(obj, 'conversion_rate', 0)
        
        if rate > 10:
            color = 'success'
        elif rate > 5:
            color = 'warning'
        elif rate > 1:
            color = 'info'
        else:
            color = 'secondary'
        
        return format_html(
            '''
            <div style="display: flex; align-items: center; gap: 8px;">
                <div style="flex-grow: 1;">
                    <div class="progress" style="height: 10px;">
                        <div class="progress-bar bg-{}" 
                             role="progressbar" 
                             style="width: {}%" 
                             aria-valuenow="{}" 
                             aria-valuemin="0" 
                             aria-valuemax="100">
                        </div>
                    </div>
                </div>
                <small>{:.1f}%</small>
            </div>
            ''',
            color, rate, rate, rate
        )
    conversion_rate_bar.short_description = _('Conversion Rate')
    
    def total_earnings_badge(self, obj):
        earnings = self.safe_getattr(obj, 'total_earnings', 0)
        
        if earnings > 1000:
            color = 'success'
        elif earnings > 100:
            color = 'warning'
        elif earnings > 10:
            color = 'info'
        else:
            color = 'secondary'
        
        return format_html(
            '<span class="badge badge-{}">[MONEY] ${:,.2f}</span>',
            color, earnings
        )
    total_earnings_badge.short_description = _('Earnings')
    
    def engagement_rate_badge(self, obj):
        rate = self.safe_getattr(obj, 'engagement_rate', 0)
        
        if rate > 50:
            color = 'success'
        elif rate > 20:
            color = 'warning'
        elif rate > 5:
            color = 'info'
        else:
            color = 'secondary'
        
        return format_html(
            '<span class="badge badge-{}">🎯 {:.1f}%</span>',
            color, rate
        )
    engagement_rate_badge.short_description = _('Engagement')
    
    def engagement_rate(self, obj):
        return f"{obj.engagement_rate_value}%" # আপনার লজিক অনুযায়ী
    
    def conversion_rate(self, obj):
        return f"{obj.conversion_rate_value}%"

    def banner_ctr(self, obj):
        return f"{obj.ctr_value}%"

    def net_earnings(self, obj):
        return f"${obj.earnings_value}"


@admin.register(ContentPermission)
class ContentPermissionAdmin(SafeAccessMixin, ModelAdmin):
    list_display = (
        'content_link',
        'permission_type_badge',
        'target_name_display',
        'permissions_summary',
        'is_active_badge',
    )
    
    list_filter = ('permission_type', 'is_active', 'content')
    
    search_fields = ('target_id', 'content__title')
    
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    
    fieldsets = (
        (_('Permission Settings'), {
            'fields': (
                'content',
                'permission_type',
                'target_id',
            ),
        }),
        (_('Permissions'), {
            'fields': (
                'can_view',
                'can_comment',
                'can_share',
                'can_download',
                'can_print',
                'can_edit',
            ),
            'classes': ('wide',),
        }),
        (_('Status'), {
            'fields': ('is_active', 'created_by'),
        }),
        (_('Metadata'), {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    # Custom methods
    def content_link(self, obj):
        content = self.safe_getattr(obj, 'content')
        if content:
            url = reverse('admin:cms_contentpage_change', args=[content.id])
            return format_html(
                '<a href="{}">{}</a>',
                url, content.title
            )
        return _("No Content")
    content_link.short_description = _('Content')
    
    def permission_type_badge(self, obj):
        ptype = self.safe_getattr(obj, 'permission_type', 'user')
        
        type_colors = {
            'user': 'primary',
            'group': 'info',
            'role': 'warning',
            'level': 'success',
        }
        
        color = type_colors.get(ptype, 'secondary')
        display = self.safe_getattr(obj, 'get_permission_type_display', lambda: 'User')()
        
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, display
        )
    permission_type_badge.short_description = _('Type')
    
    def target_name_display(self, obj):
        return self.safe_getattr(obj, 'target_name', obj.target_id)
    target_name_display.short_description = _('Target')
    
    def permissions_summary(self, obj):
        permissions = []
        
        if self.safe_getattr(obj, 'can_view', False):
            permissions.append('<span style="color: green;" title="Can View">👁️</span>')
        
        if self.safe_getattr(obj, 'can_comment', False):
            permissions.append('<span style="color: blue;" title="Can Comment">💬</span>')
        
        if self.safe_getattr(obj, 'can_share', False):
            permissions.append('<span style="color: orange;" title="Can Share">📤</span>')
        
        if self.safe_getattr(obj, 'can_download', False):
            permissions.append('<span style="color: purple;" title="Can Download">⬇️</span>')
        
        if self.safe_getattr(obj, 'can_edit', False):
            permissions.append('<span style="color: red;" title="Can Edit">✏️</span>')
        
        if not permissions:
            return format_html('<span style="color: gray;">No permissions</span>')
        
        return format_html(' '.join(permissions))
    permissions_summary.short_description = _('Permissions')
    
    
    def is_active_badge(self, obj):
        from django.utils.html import format_html
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✔ Active</span>')
        return format_html('<span style="color: red; font-weight: bold;">✖ Inactive</span>')
    is_active_badge.short_description = 'Status'


# ============================================
# REGISTER STATISTICS/TRACKING MODELS
# ============================================

@admin.register(BannerImpression)
class BannerImpressionAdmin(ModelAdmin):
    list_display = ('banner_link', 'user_link', 'impression_type_badge', 'device_type', 'created_at')
    list_filter = ('impression_type', 'device_type', DateRangeFilter)
    search_fields = ('banner__name', 'user__username', 'ip_address')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    
    def banner_link(self, obj):
        banner = obj.banner
        if banner:
            url = reverse('admin:cms_banner_change', args=[banner.id])
            return format_html('<a href="{}">{}</a>', url, banner.name)
        return _("No Banner")
    banner_link.short_description = _('Banner')
    
    def user_link(self, obj):
        user = obj.user
        if user:
            url = reverse('admin:users_user_change', args=[user.id])
            return format_html('<a href="{}">{}</a>', url, user.username)
        return _("Anonymous")
    user_link.short_description = _('User')
    
    def impression_type_badge(self, obj):
        colors = {
            'view': 'primary',
            'hover': 'info',
            'scroll': 'warning',
        }
        color = colors.get(obj.impression_type, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.impression_type.title()
        )
    impression_type_badge.short_description = _('Type')


@admin.register(BannerClick)
class BannerClickAdmin(ModelAdmin):
    list_display = ('banner_link', 'user_link', 'click_type_badge', 'conversion_value', 'created_at')
    list_filter = ('click_type', DateRangeFilter)
    search_fields = ('banner__name', 'user__username', 'ip_address')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    
    def banner_link(self, obj):
        banner = obj.banner
        if banner:
            url = reverse('admin:cms_banner_change', args=[banner.id])
            return format_html('<a href="{}">{}</a>', url, banner.name)
        return _("No Banner")
    banner_link.short_description = _('Banner')
    
    def user_link(self, obj):
        user = obj.user
        if user:
            url = reverse('admin:users_user_change', args=[user.id])
            return format_html('<a href="{}">{}</a>', url, user.username)
        return _("Anonymous")
    user_link.short_description = _('User')
    
    def click_type_badge(self, obj):
        colors = {
            'user': 'success',
            'auto': 'warning',
            'accidental': 'danger',
        }
        color = colors.get(obj.click_type, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.click_type.title()
        )
    click_type_badge.short_description = _('Type')


# ================================================
# [STATS] BANNER REWARD ADMIN - BULLETPROOF VERSION
# ================================================
# Features:
# [OK] Defensive Coding - Safe attribute access
# [OK] Performance Optimized - select_related + prefetch
# [OK] Error Handling - Graceful degradation
# [OK] Caching - Admin list view optimized
# [OK] Type Safety - Safe type conversion
# [OK] Bulk Actions - With validation
# [OK] Export Features - CSV/Excel ready
# [OK] Dashboard Stats - Quick insights
# ================================================




# ================================================
# 🎨 CUSTOM ADMIN FILTERS
# ================================================

class DateRangeFilter(admin.SimpleListFilter):
    """Custom date range filter with presets"""
    title = _('Date Range')
    parameter_name = 'date_range'
    
    def lookups(self, request, model_admin):
        return [
            ('today', _('Today')),
            ('yesterday', _('Yesterday')),
            ('this_week', _('This Week')),
            ('last_week', _('Last Week')),
            ('this_month', _('This Month')),
            ('last_month', _('Last Month')),
            ('this_year', _('This Year')),
        ]
    
    def queryset(self, request, queryset):
        now = safe_now()
        value = self.value()
        
        ranges = {
            'today': (now.date(), now.date() + timedelta(days=1)),
            'yesterday': (now.date() - timedelta(days=1), now.date()),
            'this_week': (now - timedelta(days=now.weekday()), now),
            'last_week': (now - timedelta(days=now.weekday() + 7), now - timedelta(days=now.weekday())),
            'this_month': (now.replace(day=1), now),
            'last_month': ((now.replace(day=1) - timedelta(days=1)).replace(day=1), now.replace(day=1)),
            'this_year': (now.replace(month=1, day=1), now),
        }
        
        if value in ranges:
            start, end = ranges[value]
            return queryset.filter(awarded_at__range=[start, end])
        
        return queryset


class AmountRangeFilter(admin.SimpleListFilter):
    """Filter by amount range"""
    title = _('Amount Range')
    parameter_name = 'amount_range'
    
    def lookups(self, request, model_admin):
        return [
            ('small', _('Small (≤ $5)')),
            ('medium', _('Medium ($5 - $10)')),
            ('large', _('Large ($10 - $50)')),
            ('xlarge', _('Extra Large (> $50)')),
        ]
    
    def queryset(self, request, queryset):
        value = self.value()
        
        ranges = {
            'small': Q(amount__lte=5),
            'medium': Q(amount__gt=5, amount__lte=10),
            'large': Q(amount__gt=10, amount__lte=50),
            'xlarge': Q(amount__gt=50),
        }
        
        if value in ranges:
            return queryset.filter(ranges[value])
        
        return queryset


class ProcessedStatusFilter(admin.SimpleListFilter):
    """Filter by processed status with counts"""
    title = _('Processed Status')
    parameter_name = 'processed'
    
    def lookups(self, request, model_admin):
        queryset = model_admin.get_queryset(request)
        return [
            ('processed', _('Processed ({})').format(queryset.filter(is_processed=True).count())),
            ('pending', _('Pending ({})').format(queryset.filter(is_processed=False).count())),
            ('failed', _('Failed ({})').format(queryset.filter(retry_count__gt=0).count())),
        ]
    
    def queryset(self, request, queryset):
        value = self.value()
        
        if value == 'processed':
            return queryset.filter(is_processed=True)
        elif value == 'pending':
            return queryset.filter(is_processed=False, retry_count=0)
        elif value == 'failed':
            return queryset.filter(retry_count__gt=0)
        
        return queryset


# ================================================
# [STATS] CUSTOM ADMIN ACTIONS
# ================================================

@admin.action(description=_('[OK] Mark selected as processed'))
def mark_as_processed(modeladmin, request, queryset):
    """Bulk action to mark rewards as processed"""
    try:
        # Update in batches to avoid long transactions
        updated = 0
        errors = 0
        
        for reward in queryset:
            try:
                if not reward.is_processed:
                    reward.is_processed = True
                    reward.save(skip_validation=True)
                    updated += 1
            except Exception as e:
                errors += 1
                logger.error(f"Failed to process reward {reward.id}: {e}")
        
        messages.success(
            request, 
            _('{} rewards marked as processed. {} errors.').format(updated, errors)
        )
    except Exception as e:
        messages.error(request, _('Error: {}').format(str(e)))


@admin.action(description=_('[LOADING] Retry failed processing'))
def retry_processing(modeladmin, request, queryset):
    """Bulk action to retry failed processing"""
    try:
        success = 0
        failed = 0
        
        for reward in queryset:
            if reward.retry_count > 0:
                result = reward.process_with_circuit_breaker()
                if result and result is not LOCKED:
                    success += 1
                else:
                    failed += 1
        
        messages.success(
            request,
            _('Retry completed: {} success, {} failed').format(success, failed)
        )
    except Exception as e:
        messages.error(request, _('Retry failed: {}').format(str(e)))


@admin.action(description=_('📋 Export selected to CSV'))
def export_as_csv(modeladmin, request, queryset):
    """Export selected rewards as CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="rewards_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'ID', 'UUID', 'Banner', 'User', 'Amount', 'Type', 
        'Awarded At', 'Processed', 'Retry Count'
    ])
    
    for reward in queryset.select_related('banner', 'user'):
        writer.writerow([
            reward.id,
            reward.uuid,
            safe_str(getattr(reward.banner, 'name', '')),
            safe_str(getattr(reward.user, 'username', '')),
            float(reward.amount),
            reward.reward_type,
            reward.awarded_at.isoformat() if reward.awarded_at else '',
            'Yes' if reward.is_processed else 'No',
            reward.retry_count
        ])
    
    return response


# ================================================
# 🎯 CUSTOM ADMIN CHANGE LIST
# ================================================

class BannerRewardChangeList(ChangeList):
    """Custom ChangeList with optimization"""
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # [OK] PROBLEM 10: Optimize with select_related and defer
        return qs.select_related(
            'banner', 'user'
        ).defer(
            'metadata', 'last_error'  # Don't load large fields in list view
        )


# ================================================
# [NOTE] MAIN ADMIN CLASS
# ================================================

@admin.register(BannerReward)
class BannerRewardAdmin(ModelAdmin):
    """
    [STATS] Banner Reward Admin - Bulletproof Version
    """
    
    # ================================================
    # 📋 LIST VIEW CONFIGURATION
    # ================================================
    
    list_display = [
        'id',
        'banner_link',
        'user_link',
        'amount_badge',
        'reward_type_badge',
        'status_badge',
        'awarded_at_colored',
        'retry_badge',
    ]
    
    list_display_links = ['id', 'banner_link']
    
    list_filter = [
        'reward_type',
        ProcessedStatusFilter,
        AmountRangeFilter,
        DateRangeFilter,
        'is_processed',
        'is_active',
    ]
    
    search_fields = [
        '=id',
        'uuid',
        'banner__name',
        'banner__id',
        'user__username',
        'user__email',
        'user__id',
    ]
    
    list_per_page = 50
    list_max_show_all = 200
    save_on_top = True
    
    # Custom actions
    actions = ['mark_as_processed', 'retry_processing', 'export_as_csv']
    
    # ================================================
    # [NOTE] FORM VIEW CONFIGURATION
    # ================================================
    
    fieldsets = (
        (_('🎯 Basic Information'), {
            'fields': ('uuid', 'banner', 'user', 'amount', 'reward_type')
        }),
        (_('⏰ Time Information'), {
            'fields': ('created_at', 'updated_at')
        }),
        (_('[FIX] Processing Information'), {
            'fields': ('is_processed', 'is_active', 'retry_count', 'last_error'),
            'classes': ('collapse',),
        }),
        (_('📦 Metadata'), {
            'fields': ('metadata_preview', ),
            'classes': ('collapse',),
        }),
    )
    
    readonly_fields = [
        'uuid', 'created_at', 'updated_at', 
        'retry_count', 'last_error', 'metadata_preview'
    ]
    
    raw_id_fields = ['banner', 'user', ]
    
    autocomplete_fields = ['banner',]
    
    # ================================================
    # [START] CUSTOM CHANGELIST
    # ================================================
    
    def get_changelist(self, request, **kwargs):
        return BannerRewardChangeList
    
    def get_queryset(self, request):
        """Optimize queryset for admin list view"""
        qs = super().get_queryset(request)
        
        # [OK] Optimize with select_related
        return qs.select_related(
            'banner', 'user'
        ).defer(
            'metadata', 'last_error'  # Don't load large fields in list
        )
    
    # ================================================
    # 🎨 CUSTOM DISPLAY METHODS (Bulletproof)
    # ================================================
    
    @admin.display(description=_('Banner'), ordering='banner__name')
    def banner_link(self, obj):
        """Safe banner link with fallback"""
        try:
            banner = getattr(obj, 'banner', None)
            if banner and banner.id:
                url = reverse('admin:banners_banner_change', args=[banner.id])
                name = safe_str(getattr(banner, 'name', '')) or _('Banner #{}').format(banner.id)
                return format_html('<a href="{}">{}</a>', url, name)
        except Exception as e:
            logger.debug(f"Banner link error: {e}")
        
        return format_html('<span class="text-muted">{}</span>', _('No Banner'))
    
    @admin.display(description=_('User'), ordering='user__username')
    def user_link(self, obj):
        """Safe user link with fallback"""
        try:
            user = getattr(obj, 'user', None)
            if user and user.id:
                url = reverse('admin:users_user_change', args=[user.id])
                username = safe_str(getattr(user, 'username', '')) or _('User #{}').format(user.id)
                return format_html('<a href="{}">{}</a>', url, username)
        except Exception as e:
            logger.debug(f"User link error: {e}")
        
        return format_html('<span class="text-muted">{}</span>', _('No User'))
    
    @admin.display(description=_('Amount'), ordering='amount')
    def amount_badge(self, obj):
        """Amount with color-coded badge"""
        try:
            amount = getattr(obj, 'amount', 0)
            
            # Determine color based on amount
            if amount > 50:
                color = 'danger'
                icon = '🔥'
            elif amount > 10:
                color = 'success'
                icon = '[MONEY]'
            elif amount > 5:
                color = 'warning'
                icon = '💸'
            elif amount > 0:
                color = 'info'
                icon = '🪙'
            else:
                color = 'secondary'
                icon = '💔'
            
            return format_html(
                '<span class="badge badge-{}" style="font-size: 1.1em;">{} ${:.2f}</span>',
                color, icon, amount
            )
        except Exception as e:
            logger.debug(f"Amount badge error: {e}")
            return format_html('<span class="badge badge-secondary">?</span>')
    
    @admin.display(description=_('Type'), ordering='reward_type')
    def reward_type_badge(self, obj):
        """Reward type with color coding"""
        try:
            reward_type = getattr(obj, 'reward_type', '')
            
            colors = {
                'click': ('success', '👆'),
                'view': ('info', '👁️'),
                'conversion': ('danger', '[MONEY]'),
                'bonus': ('warning', '🎁'),
                'share': ('primary', '📤'),
                'referral': ('dark', '👥'),
            }
            
            color, icon = colors.get(reward_type, ('secondary', '❓'))
            
            return format_html(
                '<span class="badge badge-{}">{}</span>',
                color, f"{icon} {reward_type.title()}"
            )
        except Exception as e:
            logger.debug(f"Type badge error: {e}")
            return format_html('<span class="badge badge-secondary">?</span>')
    
    @admin.display(description=_('Status'))
    def status_badge(self, obj):
        """Combined status with visual indicators"""
        try:
            badges = []
            
            # Processed status
            if getattr(obj, 'is_processed', False):
                badges.append(('<span class="badge badge-success">[OK] Processed</span>'))
            else:
                badges.append(('<span class="badge badge-warning">⏳ Pending</span>'))
            
            # Active status
            if not getattr(obj, 'is_active', True):
                badges.append(('<span class="badge badge-danger">🚫 Inactive</span>'))
            
            return mark_safe(' '.join(badges))
        except Exception:
            return format_html('<span class="badge badge-secondary">Unknown</span>')
    
    @admin.display(description=_('Awarded'), ordering='awarded_at')
    def awarded_at_colored(self, obj):
        """Colored awarded_at based on recency"""
        try:
            awarded_at = getattr(obj, 'awarded_at', None)
            if not awarded_at:
                return format_html('<span class="text-muted">-</span>')
            
            now = safe_now()
            diff = now - awarded_at
            
            if diff.total_seconds() < 3600:  # < 1 hour
                color = 'success'
                icon = '🆕'
            elif diff.days < 1:  # < 1 day
                color = 'info'
                icon = '⏱️'
            elif diff.days < 7:  # < 1 week
                color = 'warning'
                icon = '📅'
            else:
                color = 'secondary'
                icon = '📆'
            
            return format_html(
                '<span class="text-{}">{} {}</span>',
                color, icon, awarded_at.strftime('%Y-%m-%d %H:%M')
            )
        except Exception:
            return format_html('<span class="text-muted">-</span>')
    
    @admin.display(description=_('Retries'))
    def retry_badge(self, obj):
        """Retry count with visual indicator"""
        try:
            retry_count = getattr(obj, 'retry_count', 0)
            
            if retry_count == 0:
                return format_html('<span class="text-success">✓</span>')
            elif retry_count < 3:
                return format_html(
                    '<span class="badge badge-warning">[WARN] {}</span>',
                    retry_count
                )
            else:
                return format_html(
                    '<span class="badge badge-danger">[ERROR] {}</span>',
                    retry_count
                )
        except Exception:
            return format_html('<span class="badge badge-secondary">?</span>')
    
    @admin.display(description=_('Metadata Preview'))
    def metadata_preview(self, obj):
        """Preview metadata in readonly field"""
        try:
            metadata = getattr(obj, 'metadata', {})
            if not metadata:
                return _('No metadata')
            
            # Format as pretty JSON
            import json
            formatted = json.dumps(metadata, indent=2, default=str)
            return format_html(
                '<pre style="max-height: 300px; overflow: auto;">{}</pre>',
                formatted
            )
        except Exception:
            return _('Error displaying metadata')
    
    # ================================================
    # 🛡️ SAFE SAVE METHOD
    # ================================================
    
    def save_model(self, request, obj, form, change):
        """Save with proper error handling"""
        try:
            # Add audit info
            if not change:
                obj.created_by_id = request.user.id
            
            obj.save()
            messages.success(request, _('Reward saved successfully.'))
            
        except ValidationError as e:
            messages.error(request, _('Validation error: {}').format(', '.join(e.messages)))
            raise
        except Exception as e:
            messages.error(request, _('Error saving reward: {}').format(str(e)))
            logger.exception("Admin save error")
            raise
    
    def delete_model(self, request, obj):
        """Delete with proper error handling"""
        try:
            obj.delete()
            messages.success(request, _('Reward deleted successfully.'))
        except Exception as e:
            messages.error(request, _('Error deleting reward: {}').format(str(e)))
    
    # ================================================
    # 📦 BULK ACTIONS WITH VALIDATION
    # ================================================
    
    def get_actions(self, request):
        """Get available actions with permissions"""
        actions = super().get_actions(request)
        
        if not request.user.has_perm('rewards.can_export'):
            if 'export_as_csv' in actions:
                del actions['export_as_csv']
        
        return actions
    
    # ================================================
    # [STATS] DASHBOARD VIEWS
    # ================================================
    
    def get_urls(self):
        """Add custom admin URLs"""
        urls = super().get_urls()
        custom_urls = [
            path(
                'dashboard/',
                self.admin_site.admin_view(self.dashboard_view),
                name='banner_reward_dashboard'
            ),
        ]
        return custom_urls + urls
    
    def dashboard_view(self, request):
        """Custom dashboard with statistics"""
        # Get date ranges
        today = safe_now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Cache stats for performance
        cache_key = f"admin_dashboard_stats_{today}"
        stats = cache.get(cache_key)
        
        if not stats:
            # Calculate stats
            stats = {
                'today': {
                    'count': BannerReward.objects.filter(awarded_at__date=today).count(),
                    'total': BannerReward.objects.filter(
                        awarded_at__date=today
                    ).aggregate(total=Sum('amount'))['total'] or 0,
                },
                'week': {
                    'count': BannerReward.objects.filter(
                        awarded_at__gte=week_ago
                    ).count(),
                    'total': BannerReward.objects.filter(
                        awarded_at__gte=week_ago
                    ).aggregate(total=Sum('amount'))['total'] or 0,
                },
                'month': {
                    'count': BannerReward.objects.filter(
                        awarded_at__gte=month_ago
                    ).count(),
                    'total': BannerReward.objects.filter(
                        awarded_at__gte=month_ago
                    ).aggregate(total=Sum('amount'))['total'] or 0,
                },
                'by_type': dict(
                    BannerReward.objects.values('reward_type')
                    .annotate(count=Count('id'), total=Sum('amount'))
                    .order_by('-total')
                ),
                'top_users': list(
                    BannerReward.objects.values('user__username')
                    .annotate(total=Sum('amount'))
                    .order_by('-total')[:10]
                ),
                'processing': {
                    'processed': BannerReward.objects.filter(is_processed=True).count(),
                    'pending': BannerReward.objects.filter(is_processed=False).count(),
                    'failed': BannerReward.objects.filter(retry_count__gt=0).count(),
                }
            }
            
            # Cache for 5 minutes
            cache.set(cache_key, stats, 300)
        
        context = {
            **self.admin_site.each_context(request),
            'title': _('Banner Rewards Dashboard'),
            'stats': stats,
            'opts': self.model._meta,
        }
        
        return TemplateResponse(
            request,
            'admin/rewards/dashboard.html',
            context
        )
    
    # ================================================
    # 📤 EXPORT METHODS
    # ================================================
    
    def export_selected(self, request, queryset):
        """Export selected rewards as JSON"""
        data = []
        for reward in queryset.select_related('banner', 'user')[:1000]:  # Limit for performance
            data.append({
                'id': reward.id,
                'uuid': str(reward.uuid),
                'banner': safe_str(getattr(reward.banner, 'name', '')),
                'user': safe_str(getattr(reward.user, 'username', '')),
                'amount': float(reward.amount),
                'type': reward.reward_type,
                'awarded_at': reward.awarded_at.isoformat() if reward.awarded_at else None,
                'processed': reward.is_processed,
            })
        
        return JsonResponse({'rewards': data})


# ================================================
# [NOTE] INLINE ADMINS
# ================================================

class BannerRewardInline(admin.TabularInline):
    """Inline admin for related models"""
    model = BannerReward
    extra = 0
    can_delete = False
    readonly_fields = ['uuid', 'amount', 'reward_type', 'awarded_at']
    fields = ['uuid', 'amount', 'reward_type', 'awarded_at']
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('banner', 'user')


# ================================================
# 🎨 ADMIN CSS
# ================================================

class Media:
    """Custom CSS for admin"""
    css = {
        'all': ('css/admin/rewards.css',)
    }
    
    js = ('js/admin/rewards.js',)


# ================================================
# [NOTE] USAGE EXAMPLES
# ================================================

"""
# [START] How to use in other admin classes:

# Add inline to Banner admin
class BannerAdmin(ModelAdmin):
    inlines = [BannerRewardInline]

# Add inline to User admin
class UserAdmin(ModelAdmin):
    inlines = [BannerRewardInline]

# Use in templates:
{% extends "admin/change_list.html" %}
{% block object-tools-items %}
    {{ block.super }}
    <li>
        <a href="{% url 'admin:banner_reward_dashboard' %}" class="btn">
            [STATS] Dashboard
        </a>
    </li>
{% endblock %}
"""

# ================================================
# [WIN] END OF BANNER REWARD ADMIN
# ================================================

@admin.register(FAQFeedback)
class FAQFeedbackAdmin(ModelAdmin):
    list_display = ('faq_link', 'user_link', 'is_helpful_icon', 'feedback_preview', 'created_at')
    list_filter = ('is_helpful', DateRangeFilter)
    search_fields = ('faq__question', 'user__username', 'feedback_text')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    
    def faq_link(self, obj):
        faq = obj.faq
        if faq:
            url = reverse('admin:cms_faq_change', args=[faq.id])
            return format_html('<a href="{}">{}</a>', url, faq.question[:50])
        return _("No FAQ")
    faq_link.short_description = _('FAQ')
    
    def user_link(self, obj):
        user = obj.user
        if user:
            url = reverse('admin:users_user_change', args=[user.id])
            return format_html('<a href="{}">{}</a>', url, user.username)
        return _("Anonymous")
    user_link.short_description = _('User')
    
    def is_helpful_icon(self, obj):
        if obj.is_helpful:
            return format_html('<span style="color: green;">👍</span>')
        return format_html('<span style="color: red;">👎</span>')
    is_helpful_icon.short_description = _('Helpful')
    
    def feedback_preview(self, obj):
        feedback = obj.feedback_text
        if feedback and len(feedback) > 50:
            return f"{feedback[:50]}..."
        return feedback or _("No feedback")
    feedback_preview.short_description = _('Feedback')


@admin.register(ContentViewLog)
class ContentViewLogAdmin(ModelAdmin):
    list_display = ('content_link', 'user_link', 'view_duration_badge', 'is_completed_icon', 'created_at')
    list_filter = ('is_completed', 'device_type', DateRangeFilter)
    search_fields = ('content__title', 'user__username', 'ip_address')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    
    def content_link(self, obj):
        content = obj.content
        if content:
            url = reverse('admin:cms_contentpage_change', args=[content.id])
            return format_html('<a href="{}">{}</a>', url, content.title[:50])
        return _("No Content")
    content_link.short_description = _('Content')
    
    def user_link(self, obj):
        user = obj.user
        if user:
            url = reverse('admin:users_user_change', args=[user.id])
            return format_html('<a href="{}">{}</a>', url, user.username)
        return _("Anonymous")
    user_link.short_description = _('User')
    
    def view_duration_badge(self, obj):
        duration = obj.view_duration
        if duration > 300:  # 5 minutes
            color = 'success'
        elif duration > 60:  # 1 minute
            color = 'warning'
        elif duration > 10:  # 10 seconds
            color = 'info'
        else:
            color = 'secondary'
        
        return format_html(
            '<span class="badge badge-{}">⏱️ {}s</span>',
            color, duration
        )
    view_duration_badge.short_description = _('Duration')
    
    def is_completed_icon(self, obj):
        if obj.is_completed:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: orange;">⌛</span>')
    is_completed_icon.short_description = _('Completed')


@admin.register(ContentShare)
class ContentShareAdmin(ModelAdmin):
    list_display = ('content_link', 'user_link', 'share_platform_badge', 'created_at')
    list_filter = ('share_platform', DateRangeFilter)
    search_fields = ('content__title', 'user__username')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    
    def content_link(self, obj):
        content = obj.content
        if content:
            url = reverse('admin:cms_contentpage_change', args=[content.id])
            return format_html('<a href="{}">{}</a>', url, content.title[:50])
        return _("No Content")
    content_link.short_description = _('Content')
    
    def user_link(self, obj):
        user = obj.user
        if user:
            url = reverse('admin:users_user_change', args=[user.id])
            return format_html('<a href="{}">{}</a>', url, user.username)
        return _("Anonymous")
    user_link.short_description = _('User')
    
    def share_platform_badge(self, obj):
        platforms = {
            'facebook': ('primary', 'f'),
            'twitter': ('info', '𝕏'),
            'linkedin': ('primary', 'in'),
            'whatsapp': ('success', 'WA'),
            'telegram': ('info', 'TG'),
            'email': ('secondary', '✉️'),
            'copy_link': ('light', '🔗'),
            'other': ('dark', '?'),
        }
        
        color, icon = platforms.get(obj.share_platform, ('secondary', '?'))
        return format_html(
            '<span class="badge badge-{}">{} {}</span>',
            color, icon, obj.share_platform.title()
        )
    share_platform_badge.short_description = _('Platform')


@admin.register(CommentLike)
class CommentLikeAdmin(ModelAdmin):
    list_display = ('comment_link', 'user_link', 'created_at')
    list_filter = (DateRangeFilter,)
    search_fields = ('comment__comment', 'user__username')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    
    def comment_link(self, obj):
        comment = obj.comment
        if comment:
            # Try to get the comment text
            comment_text = comment.comment[:50] + "..." if len(comment.comment) > 50 else comment.comment
            url = reverse('admin:cms_comment_change', args=[comment.id])
            return format_html('<a href="{}">💬 {}</a>', url, comment_text)
        return _("No Comment")
    comment_link.short_description = _('Comment')
    
    def user_link(self, obj):
        user = obj.user
        if user:
            url = reverse('admin:users_user_change', args=[user.id])
            return format_html('<a href="{}">{}</a>', url, user.username)
        return _("No User")
    user_link.short_description = _('User')


# ============================================
# ADMIN SITE CUSTOMIZATION
# ============================================

class CMSSite(admin.AdminSite):
    """Custom admin site for CMS"""
    site_header = "Amir CMS Administration"
    site_title = "Amir CMS Admin"
    index_title = "Welcome to Amir CMS Administration"
    
    def get_app_list(self, request):
        """
        Return a sorted list of all the installed apps that have been
        registered in this site with custom ordering.
        """
        app_list = super().get_app_list(request)
        
        # Reorder apps to put CMS first
        for app in app_list:
            if app['app_label'] == 'cms':
                app_list.remove(app)
                app_list.insert(0, app)
                break
        
        return app_list


# Register custom admin site
cms_admin_site = CMSSite(name='cms_admin')

# Register all models with custom admin site


cms_admin_site.register(ContentPage, ContentPageAdmin)
cms_admin_site.register(Banner, BannerAdmin)
cms_admin_site.register(FAQCategory, FAQCategoryAdmin)
cms_admin_site.register(FAQ, FAQAdmin)
cms_admin_site.register(SiteSettings, SiteSettingsAdmin)
cms_admin_site.register(ImageGallery, ImageGalleryAdmin)
cms_admin_site.register(FileManager, FileManagerAdmin)
cms_admin_site.register(Comment, CommentAdmin)
cms_admin_site.register(SiteAnalytics, SiteAnalyticsAdmin)
cms_admin_site.register(ContentPermission, ContentPermissionAdmin)

# Statistics models
cms_admin_site.register(BannerImpression, BannerImpressionAdmin)
cms_admin_site.register(BannerClick, BannerClickAdmin)
cms_admin_site.register(BannerReward, BannerRewardAdmin)
cms_admin_site.register(FAQFeedback, FAQFeedbackAdmin)
cms_admin_site.register(ContentViewLog, ContentViewLogAdmin)
cms_admin_site.register(ContentShare, ContentShareAdmin)
cms_admin_site.register(CommentLike, CommentLikeAdmin)

# ============================================
# BULLETPROOF CODE IMPLEMENTATION EXAMPLES
# ============================================

"""
বুলেটপ্রুফ কোডিং টেকনিকগুলো এই admin.py তে যেভাবে ইমপ্লিমেন্ট করা হয়েছে:

1. SafeAccessMixin ক্লাস:
   - safe_getattr(): getattr() ব্যবহার করে ডিফেন্সিভ attribute access
   - safe_dict_get(): ডিকশনারির চেইনড access
   - create_sentinel(): ইউনিক sentinel value তৈরি করা

2. Null Object Pattern:
   সব getattr() call এ ডিফল্ট ভ্যালু দেওয়া হয়েছে:
   getattr(obj, 'name', 'Unknown')

3. Type Hinting:
   function signature-এ টাইপ হিন্টিং ব্যবহার করা হয়েছে:
   def safe_getattr(obj, attr: str, default: Any = None) -> Any:

4. Graceful Degradation:
   try-except ব্লকে error হ্যান্ডলিং:
   try:
       value = getattr(obj, attr, default)
   except Exception as e:
       logger.error(f"Error: {e}")
       return default

5. Circuit Breaker Pattern:
   API calls বা external service calls এর জন্য 
   (এই ফাইলে দেখানো হয়নি কিন্তু real implementation-এ যোগ করা যায়)

6. Logging:
   সব critical operations এর জন্য logging ব্যবহার করা হয়েছে:
   logger.error(f"Error saving ContentCategory {obj.id}: {e}")

7. Custom Actions with Error Handling:
   সব admin actions try-except ব্লকে wrap করা হয়েছে:
   try:
       updated = queryset.update(is_active=True)
   except Exception as e:
       logger.error(f"Error: {e}")
       self.message_user(request, f'Error: {str(e)}', messages.ERROR)

8. Progress Bars এবং Color Badges:
   - content_count_progress(): প্রগ্রেস বার
   - status_badge(): কালার ব্যাজ
   - view_count_badge(): ডায়নামিক কালার based on value

9. Image Previews:
   - image_preview(): ছবি প্রিভিউ
   - thumbnail_preview(): থাম্বনেইল

10. Boolean Icons:
    - is_active_icon(): টিক মার্ক/ক্রস মার্ক
    - is_featured_icon(): স্টার আইকন

11. Help Text এবং Classes:
    - help_texts dictionary
    - fieldsets-এ classes ব্যবহার

12. Inline Admin:
    - ContentPageInline, FAQInline, etc.

13. Custom Filters:
    - IsActiveFilter, StatusFilter, DateRangeFilter

14. Defensive Model Saving:
    save_model() method override করে error handling
"""

# ==================== REGISTER IN DEFAULT ADMIN ====================

from .models import (
    ContentCategory, ContentPage, Banner, FAQCategory, FAQ,
    BannerImpression, BannerClick, FAQFeedback, ContentViewLog,
    ContentShare, SiteSettings, ImageGallery, GalleryImage,
    FileManager, Comment, CommentLike, SiteAnalytics,
    PermissionAuditLog, ContentPermission, PermissionStats, BannerReward
)

print("\n[DOC] Registering CMS models in default admin...")
registered = 0
for model in [
    ContentCategory, ContentPage, Banner, FAQCategory, FAQ,
    BannerImpression, BannerClick, FAQFeedback, ContentViewLog,
    ContentShare, SiteSettings, ImageGallery, GalleryImage,
    FileManager, Comment, CommentLike, SiteAnalytics,
    PermissionAuditLog, ContentPermission, PermissionStats, BannerReward
]:
    if not admin.site.is_registered(model):
        admin.site.register(model)
        registered += 1
        print(f"[OK] Registered: {model.__name__}")

print(f"[DOC] Registered {registered} CMS models in default admin")

def _force_register_cms():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(ContentCategory, ContentCategoryAdmin), (ContentPage, ContentPageAdmin), (Banner, BannerAdmin), (FAQCategory, FAQCategoryAdmin), (FAQ, FAQAdmin), (SiteSettings, SiteSettingsAdmin), (ImageGallery, ImageGalleryAdmin), (FileManager, FileManagerAdmin), (Comment, CommentAdmin), (SiteAnalytics, SiteAnalyticsAdmin), (ContentPermission, ContentPermissionAdmin), (BannerImpression, BannerImpressionAdmin), (BannerClick, BannerClickAdmin), (BannerReward, BannerRewardAdmin), (FAQFeedback, FAQFeedbackAdmin), (ContentViewLog, ContentViewLogAdmin), (ContentShare, ContentShareAdmin), (CommentLike, CommentLikeAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] cms registered {registered} models")
    except Exception as e:
        print(f"[WARN] cms: {e}")
