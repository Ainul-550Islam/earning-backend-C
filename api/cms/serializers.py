from rest_framework import serializers
from .models import (
    ContentCategory, ContentPage, Banner, FAQCategory, FAQ,
    SiteSettings, ImageGallery, GalleryImage, FileManager,
    Comment, SiteAnalytics
)


class ContentCategorySerializer(serializers.ModelSerializer):
    """Serializer for ContentCategory model"""
    breadcrumbs = serializers.SerializerMethodField()
    content_count = serializers.IntegerField(source='total_content', read_only=True)
    
    class Meta:
        model = ContentCategory
        fields = [
            'id', 'name', 'slug', 'description', 'category_type',
            'icon', 'thumbnail', 'order', 'is_active', 'show_in_menu',
            'show_in_footer', 'show_in_app', 'parent', 'breadcrumbs',
            'seo_title', 'seo_description', 'seo_keywords',
            'min_reward', 'max_reward', 'reward_currency',
            'content_count', 'total_views', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_breadcrumbs(self, obj):
        return obj.get_breadcrumbs()


class ContentPageSerializer(serializers.ModelSerializer):
    """Serializer for ContentPage model"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    author_username = serializers.CharField(source='author.username', read_only=True)
    reading_time = serializers.IntegerField(read_only=True)
    is_published = serializers.BooleanField(read_only=True)
    related_content = serializers.SerializerMethodField()
    
    class Meta:
        model = ContentPage
        fields = [
            'id', 'uuid', 'title', 'slug', 'subtitle', 'category', 'category_name',
            'category_slug', 'page_type', 'tags', 'excerpt', 'content',
            'featured_image', 'thumbnail', 'author', 'author_name', 'author_username',
            'status', 'visibility', 'is_active', 'is_featured', 'is_pinned',
            'allow_comments', 'published_date', 'scheduled_date', 'expiry_date',
            'meta_title', 'meta_description', 'meta_keywords', 'canonical_url',
            'view_count', 'share_count', 'like_count', 'comment_count',
            'related_offer', 'related_task', 'min_reward', 'max_reward',
            'reward_currency', 'completion_time', 'difficulty_level',
            'requirements', 'version', 'parent_version', 'language',
            'is_translation', 'original_content', 'reading_time', 'is_published',
            'related_content', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'view_count', 'share_count', 'like_count', 'comment_count',
            'created_at', 'updated_at'
        ]
    
    def get_related_content(self, obj):
        # Get limited related content to avoid performance issues
        related = obj.get_related_content(limit=5)
        return ContentPageListSerializer(related, many=True).data


class ContentPageListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for content page lists"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    reading_time = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ContentPage
        fields = [
            'id', 'uuid', 'title', 'slug', 'excerpt', 'featured_image',
            'category_name', 'published_date', 'view_count', 'reading_time'
        ]


class BannerSerializer(serializers.ModelSerializer):
    """Serializer for Banner model"""
    click_url = serializers.CharField(source='get_click_url', read_only=True)
    is_active_now = serializers.BooleanField(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)
    performance_score = serializers.FloatField(read_only=True)
    
    class Meta:
        model = Banner
        fields = [
            'id', 'uuid', 'name', 'banner_type', 'position', 'title',
            'description', 'image', 'mobile_image', 'thumbnail', 'link_type',
            'link_url', 'internal_page', 'offer', 'task', 'is_active',
            'start_date', 'end_date', 'priority', 'max_impressions',
            'max_clicks', 'display_frequency', 'target_device',
            'target_audience', 'required_tags', 'excluded_tags',
            'min_user_level', 'impression_count', 'click_count',
            'conversion_count', 'total_revenue', 'reward_amount',
            'reward_type', 'max_rewards_per_user', 'click_through_rate',
            'conversion_rate', 'click_url', 'is_active_now', 'days_remaining',
            'performance_score', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'impression_count', 'click_count', 'conversion_count',
            'total_revenue', 'click_through_rate', 'conversion_rate',
            'created_at', 'updated_at'
        ]


class FAQCategorySerializer(serializers.ModelSerializer):
    """Serializer for FAQCategory model"""
    faq_count = serializers.IntegerField(source='total_faqs', read_only=True)
    
    class Meta:
        model = FAQCategory
        fields = [
            'id', 'name', 'slug', 'description', 'icon', 'order',
            'is_active', 'faq_type', 'faq_count', 'total_views',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class FAQSerializer(serializers.ModelSerializer):
    """Serializer for FAQ model"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    helpful_percentage = serializers.FloatField(read_only=True)
    total_feedback = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = FAQ
        fields = [
            'id', 'uuid', 'question', 'slug', 'short_answer', 'detailed_answer',
            'category', 'category_name', 'tags', 'priority', 'is_active',
            'is_featured', 'is_pinned', 'show_in_app', 'show_on_website',
            'view_count', 'helpful_count', 'not_helpful_count', 'helpful_percentage',
            'total_feedback', 'related_pages', 'related_offers', 'last_updated',
            'updated_by', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'view_count', 'helpful_count', 'not_helpful_count',
            'last_updated', 'created_at', 'updated_at'
        ]


class SiteSettingsSerializer(serializers.ModelSerializer):
    """Serializer for SiteSettings model"""
    typed_value = serializers.SerializerMethodField()
    
    class Meta:
        model = SiteSettings
        fields = [
            'id', 'uuid', 'key', 'value', 'data_type', 'description',
            'category', 'is_public', 'is_editable', 'last_modified',
            'modified_by', 'typed_value', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_typed_value(self, obj):
        return obj.get_value()


class ImageGallerySerializer(serializers.ModelSerializer):
    """Serializer for ImageGallery model"""
    image_count = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()
    
    class Meta:
        model = ImageGallery
        fields = [
            'id', 'uuid', 'title', 'slug', 'description', 'category',
            'tags', 'is_active', 'is_featured', 'image_count', 'cover_image',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_image_count(self, obj):
        return obj.images.filter(is_active=True).count()
    
    def get_cover_image(self, obj):
        cover = obj.cover_image
        if cover:
            return {
                'id': cover.id,
                'image': cover.image.url,
                'thumbnail': cover.thumbnail.url if cover.thumbnail else None,
                'title': cover.title
            }
        return None


class GalleryImageSerializer(serializers.ModelSerializer):
    """Serializer for GalleryImage model"""
    image_size_human = serializers.CharField(read_only=True)
    
    class Meta:
        model = GalleryImage
        fields = [
            'id', 'uuid', 'gallery', 'image', 'thumbnail', 'title',
            'alt_text', 'caption', 'order', 'is_active', 'view_count',
            'image_size_human', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'view_count', 'image_size_human', 'created_at', 'updated_at'
        ]


class FileManagerSerializer(serializers.ModelSerializer):
    """Serializer for FileManager model"""
    file_size_human = serializers.CharField(read_only=True)
    file_extension = serializers.CharField(read_only=True)
    
    class Meta:
        model = FileManager
        fields = [
            'id', 'uuid', 'name', 'file', 'file_type', 'file_size',
            'mime_type', 'description', 'category', 'is_public',
            'is_active', 'download_count', 'file_size_human', 'file_extension',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'file_size', 'mime_type', 'download_count',
            'file_size_human', 'file_extension', 'created_at', 'updated_at'
        ]


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for Comment model"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    content_object_title = serializers.SerializerMethodField()
    has_replies = serializers.BooleanField(read_only=True)
    replies = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'uuid', 'user', 'user_name', 'user_username',
            'comment_type', 'content_type', 'object_id',
            'content_object_title', 'comment', 'rating', 'is_approved',
            'is_edited', 'edit_reason', 'like_count', 'reply_count',
            'parent', 'is_active', 'is_flagged', 'flag_reason',
            'moderated_by', 'moderated_at', 'has_replies', 'replies',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'like_count', 'reply_count', 'moderated_at',
            'created_at', 'updated_at'
        ]
    
    def get_content_object_title(self, obj):
        try:
            content_obj = obj.content_object
            if hasattr(content_obj, 'title'):
                return content_obj.title
            elif hasattr(content_obj, 'question'):
                return content_obj.question
            elif hasattr(content_obj, 'name'):
                return obj.content_object.name
        except:
            pass
        return ''
    
    def get_replies(self, obj):
        replies = obj.get_replies()
        return CommentSerializer(replies, many=True).data


class SiteAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for SiteAnalytics model"""
    conversion_rate = serializers.FloatField(read_only=True)
    net_earnings = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    banner_ctr = serializers.FloatField(read_only=True)
    engagement_rate = serializers.FloatField(read_only=True)
    
    class Meta:
        model = SiteAnalytics
        fields = [
            'id', 'uuid', 'date', 'page_views', 'unique_visitors',
            'new_users', 'active_users', 'session_count',
            'avg_session_duration', 'bounce_rate', 'total_earnings',
            'total_withdrawals', 'offer_completions', 'task_completions',
            'content_views', 'content_shares', 'content_comments',
            'banner_impressions', 'banner_clicks', 'banner_conversions',
            'conversion_rate', 'net_earnings', 'banner_ctr', 'engagement_rate',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']