from rest_framework import serializers
from .models import (
    ContentCategory, ContentPage, Banner, FAQCategory, FAQ,
    SiteSettings, ImageGallery, GalleryImage, FileManager,
    Comment, SiteAnalytics
)
# Models from models_new — imported lazily to avoid circular imports at module load
from .models_new.profile_surveys import SurveyTemplate as Survey, SurveyCompletion
from .models_new.user_profile import UserSegment
from .models_new.survey_rewards import SurveyReward, RewardPool, RewardTransaction


def _lazy(module_path, name):
    """Generic lazy model loader — used for all models_new submodules."""
    import importlib
    try:
        m = importlib.import_module(module_path)
        return getattr(m, name)
    except (ImportError, AttributeError):
        return None


def _task(name):
    return _lazy('cms.models_new.task_management', name)

def _cpalead(name):
    return _lazy('cms.models_new.cpalead', name)

def _extras(name):
    return _lazy('cms.models_new.extras', name)

def _withdrawal(name):
    return _lazy('cms.models_new.withdrawal', name)

def _leaderboard(name):
    return _lazy('cms.models_new.leaderboard', name)

def _referral(name):
    return _lazy('cms.models_new.referral', name)

def _rtb(name):
    return _lazy('cms.models_new.rtb', name)

def _smartlink(name):
    return _lazy('cms.models_new.smartlink', name)

def _video(name):
    return _lazy('cms.models_new.video', name)

def _forms(name):
    return _lazy('cms.models_new.forms', name)

def _apikey(name):
    return _lazy('cms.models_new.api_keys', name)

def _quiz(name):
    return _lazy('cms.models_new.quiz', name)

def _siteconfig(name):
    return _lazy('cms.models_new.site_config', name)


# Eagerly resolve the direct-reference models used below
TaskSchedule        = _task('TaskSchedule')
TaskExecution       = _task('TaskExecution')
TaskQueue           = _task('TaskQueue')
TaskLock            = _task('TaskLock')
UserProfile         = _withdrawal('UserProfile')
WithdrawalRequest   = _withdrawal('WithdrawalRequest')
LeaderboardEntry    = _leaderboard('LeaderboardEntry')
ReferralCode        = _referral('ReferralCode')
RTBAdSlot           = _rtb('RTBAdSlot')
RTBConfig           = _rtb('RTBConfig')
SmartLink           = _smartlink('SmartLink')
VideoContent        = _video('VideoContent')
DynamicForm         = _forms('DynamicForm')
APIKey              = _apikey('APIKey')
UserSession         = _apikey('UserSession')
QuizTemplate        = _quiz('Quiz')
SiteConfig          = _siteconfig('SiteConfig')
LandingPage         = _lazy('cms.models_new.menu', 'LandingPage')
IntegrationAuditLog = _lazy('cms.models_new.extras', 'IntegrationAuditLog')



# ── FIX: moved inline Meta imports to module level ──────────────────────────
from api.cms.models_new.withdrawal import WithdrawalRequest as _WithdrawalRequest  # noqa
from api.cms.models_new.referral import ReferralCode as _ReferralCode  # noqa
from api.cms.models_new.leaderboard import LeaderboardEntry as _LeaderboardEntry  # noqa
from api.cms.models_new.quiz import QuizTemplate as _QuizTemplate  # noqa
from api.cms.models_new.smartlink import SmartLink as _SmartLink  # noqa
from api.cms.models_new.withdrawal import UserProfile as _UserProfile  # noqa
from api.cms.models_new.forms import DynamicForm as _DynamicForm  # noqa
from api.cms.models_new.site_config import SiteConfig as _SiteConfig  # noqa
from api.cms.models_new.video import VideoContent as _VideoContent  # noqa
from api.cms.models_new.rtb import RTBConfig as _RTBConfig  # noqa
from api.cms.models_new.rtb import RTBAdSlot as _RTBAdSlot  # noqa
from api.cms.models_new.landing_pages import LandingPage as _LandingPage  # noqa
from api.cms.models_new.comments import Comment as _NewComment  # noqa

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


class SurveySerializer(serializers.ModelSerializer):
    """Serializer for Survey model"""
    category_name = serializers.CharField(source='category', read_only=True)
    participants_count = serializers.IntegerField(source='current_participants', read_only=True)
    is_available = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = Survey
        fields = [
            'id', 'title', 'description', 'category', 'category_name',
            'reward_amount', 'estimated_time', 'is_active', 'is_featured',
            'start_date', 'end_date', 'max_participants', 'participants_count',
            'questions', 'is_available', 'time_remaining', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'current_participants', 'created_at', 'updated_at']
    
    def get_is_available(self, obj):
        from django.utils import timezone
        now = timezone.now()
        return (obj.is_active and 
                obj.start_date <= now <= obj.end_date and
                (obj.max_participants is None or obj.current_participants < obj.max_participants))
    
    def get_time_remaining(self, obj):
        from django.utils import timezone
        if obj.end_date > timezone.now():
            delta = obj.end_date - timezone.now()
            return int(delta.total_seconds() // 60)  # minutes
        return 0


class UserSegmentSerializer(serializers.ModelSerializer):
    """Serializer for UserSegment model"""
    user_count = serializers.SerializerMethodField()
    criteria_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = UserSegment
        fields = [
            'id', 'name', 'description', 'criteria', 'is_active',
            'user_count', 'criteria_summary', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_user_count(self, obj):
        # This would require implementing a method to count users matching criteria
        # For now, return placeholder
        return 0
    
    def get_criteria_summary(self, obj):
        """Human-readable summary of segmentation criteria"""
        criteria = obj.criteria or {}
        summaries = []
        
        if criteria.get('country'):
            summaries.append(f"Country: {criteria['country']}")
        if criteria.get('level_min'):
            summaries.append(f"Min Level: {criteria['level_min']}")
        if criteria.get('level_max'):
            summaries.append(f"Max Level: {criteria['level_max']}")
        if criteria.get('registration_date_from'):
            summaries.append(f"Registered after: {criteria['registration_date_from']}")
        
        return '; '.join(summaries) if summaries else 'All users'


class SurveyCompletionSerializer(serializers.ModelSerializer):
    """Serializer for SurveyCompletion model"""
    survey_title = serializers.CharField(source='survey.title', read_only=True)
    survey_reward = serializers.DecimalField(
        source='survey.reward_amount', read_only=True, max_digits=10, decimal_places=2
    )
    username = serializers.CharField(source='user.username', read_only=True)
    completion_time = serializers.SerializerMethodField()
    
    class Meta:
        model = SurveyCompletion
        fields = [
            'id', 'user', 'username', 'survey', 'survey_title', 'survey_reward',
            'answers', 'status', 'started_at', 'completed_at', 'duration',
            'completion_time', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_completion_time(self, obj):
        if obj.completed_at and obj.started_at:
            delta = obj.completed_at - obj.started_at
            return int(delta.total_seconds() // 60)  # minutes
        return None


class TaskScheduleSerializer(serializers.ModelSerializer):
    """Serializer for TaskSchedule model"""
    next_run = serializers.SerializerMethodField()
    last_run = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskSchedule
        fields = [
            'id', 'name', 'description', 'task_type', 'schedule_type',
            'schedule_config', 'is_active', 'max_retries', 'timeout_seconds',
            'next_run', 'last_run', 'success_rate', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_next_run(self, obj):
        # This would calculate next run based on schedule_config
        # For now, return placeholder
        return None
    
    def get_last_run(self, obj):
        # This would get last execution from TaskExecution
        # For now, return placeholder
        return None
    
    def get_success_rate(self, obj):
        # This would calculate from TaskExecution records
        # For now, return placeholder
        return 100.0


class TaskExecutionSerializer(serializers.ModelSerializer):
    """Serializer for TaskExecution model"""
    task_name = serializers.CharField(source='task.name', read_only=True)
    duration_formatted = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskExecution
        fields = [
            'id', 'task', 'task_name', 'status', 'status_display',
            'scheduled_at', 'started_at', 'completed_at', 'duration',
            'duration_formatted', 'result', 'error_message', 'retry_count',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_duration_formatted(self, obj):
        if obj.duration:
            hours = obj.duration // 3600
            minutes = (obj.duration % 3600) // 60
            seconds = obj.duration % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return None
    
    def get_status_display(self, obj):
        return obj.get_status_display()


class TaskQueueSerializer(serializers.ModelSerializer):
    """Serializer for TaskQueue model"""
    status_display = serializers.SerializerMethodField()
    priority_display = serializers.SerializerMethodField()
    wait_time = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskQueue
        fields = [
            'id', 'task_name', 'task_data', 'priority', 'priority_display',
            'status', 'status_display', 'max_retries', 'retry_count',
            'scheduled_at', 'processed_at', 'worker_id', 'wait_time',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_status_display(self, obj):
        return obj.get_status_display()
    
    def get_priority_display(self, obj):
        return f"Priority {obj.priority}" if obj.priority else "Normal"
    
    def get_wait_time(self, obj):
        if obj.scheduled_at and obj.processed_at:
            delta = obj.processed_at - obj.scheduled_at
            return int(delta.total_seconds() // 60)  # minutes
        return None


class TaskLockSerializer(serializers.ModelSerializer):
    """Serializer for TaskLock model"""
    is_expired = serializers.SerializerMethodField()
    lock_duration = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskLock
        fields = [
            'id', 'task_name', 'lock_key', 'locked_by', 'locked_at',
            'expires_at', 'is_active', 'is_expired', 'lock_duration',
            'created_at'
        ]
        read_only_fields = ['id', 'locked_at', 'created_at']
    
    def get_is_expired(self, obj):
        from django.utils import timezone
        return timezone.now() > obj.expires_at
    
    def get_lock_duration(self, obj):
        from django.utils import timezone
        if obj.expires_at:
            delta = obj.expires_at - obj.locked_at
            return int(delta.total_seconds() // 60)  # minutes
        return None


class RewardPoolSerializer(serializers.ModelSerializer):
    """Serializer for RewardPool model"""
    remaining_budget_calculated = serializers.SerializerMethodField()
    utilization_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = RewardPool
        fields = [
            'id', 'name', 'description', 'total_budget', 'allocated_amount',
            'paid_amount', 'remaining_budget', 'remaining_budget_calculated',
            'currency', 'auto_refill', 'refill_amount', 'refill_threshold',
            'is_active', 'utilization_percentage', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_remaining_budget_calculated(self, obj):
        return obj.total_budget - obj.allocated_amount
    
    def get_utilization_percentage(self, obj):
        if obj.total_budget > 0:
            return round((obj.allocated_amount / obj.total_budget) * 100, 2)
        return 0.0


class SurveyRewardSerializer(serializers.ModelSerializer):
    """Serializer for SurveyReward model"""
    survey_title = serializers.CharField(source='survey.title', read_only=True)
    total_reward_amount = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = SurveyReward
        fields = [
            'id', 'survey', 'survey_title', 'name', 'description', 'reward_type',
            'base_amount', 'bonus_amount', 'bonus_criteria', 'currency',
            'max_rewards_per_user', 'status', 'status_display',
            'total_paid', 'times_paid', 'total_reward_amount',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_total_reward_amount(self, obj):
        return obj.base_amount + obj.bonus_amount
    
    def get_status_display(self, obj):
        return obj.get_status_display()


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

# ═══════════════════════════════════════════════════════════════════
# NEW CMS SERIALIZERS — Blog, Media, Popup, Menu, SEO
# All model imports at module level (Django-safe)
# ═══════════════════════════════════════════════════════════════════

# Lazy model loader — avoids circular import at module level
def _blog(name):   return _lazy('cms.models_new.blog',   name)
def _media(name):  return _lazy('cms.models_new.media',  name)
def _popup(name):  return _lazy('cms.models_new.popup',  name)
def _menu(name):   return _lazy('cms.models_new.menu',   name)
def _seo(name):    return _lazy('cms.models_new.seo',    name)


# ── Blog Serializers ──────────────────────────────────────────────

class BlogCategorySerializer(serializers.ModelSerializer):
    has_children = serializers.SerializerMethodField()
    level = serializers.SerializerMethodField()
    breadcrumbs = serializers.SerializerMethodField()

    class Meta:
        model = None  # set in __init_subclass__ via swappable_dependency pattern
        fields = [
            'id', 'uuid', 'name', 'slug', 'description', 'icon',
            'parent', 'sort_order', 'is_active', 'thumbnail',
            'seo_title', 'seo_description',
            'post_count', 'total_views',
            'has_children', 'level', 'breadcrumbs',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'post_count', 'total_views', 'created_at', 'updated_at']

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def __class_getitem__(cls, item):
        return cls

    @classmethod
    def _get_model(cls):
        return _blog('BlogCategory')

    def get_has_children(self, obj):
        return obj.has_children

    def get_level(self, obj):
        return obj.level

    def get_breadcrumbs(self, obj):
        return obj.get_breadcrumbs()


# Patch Meta.model at runtime
BlogCategorySerializer.Meta.model = _blog('BlogCategory')


class BlogTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = ['id', 'uuid', 'name', 'slug', 'usage_count', 'is_active', 'created_at']
        read_only_fields = ['uuid', 'usage_count', 'created_at']

BlogTagSerializer.Meta.model = _blog('BlogTag')


class BlogSEOSerializer(serializers.ModelSerializer):
    robots_directive = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'post',
            'meta_title', 'meta_description', 'meta_keywords',
            'og_image', 'og_title', 'og_description',
            'twitter_title', 'twitter_description', 'twitter_card',
            'canonical_url', 'no_index', 'no_follow',
            'structured_data', 'robots_directive',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

    def get_robots_directive(self, obj):
        return obj.get_robots_directive()

BlogSEOSerializer.Meta.model = _blog('BlogSEO')


class BlogCommentSerializer(serializers.ModelSerializer):
    author_display = serializers.SerializerMethodField()
    has_replies = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'post', 'user', 'parent',
            'content', 'is_approved', 'approved_by', 'approved_at',
            'is_active', 'is_flagged', 'flag_reason',
            'like_count', 'reply_count',
            'guest_name', 'guest_email',
            'author_display', 'has_replies',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'is_approved', 'approved_by', 'approved_at',
            'like_count', 'reply_count', 'created_at', 'updated_at'
        ]

    def get_author_display(self, obj):
        return obj.user.username if obj.user else (obj.guest_name or 'Anonymous')

    def get_has_replies(self, obj):
        return obj.has_replies

BlogCommentSerializer.Meta.model = _blog('BlogComment')


class BlogPostListSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    reading_time = serializers.IntegerField(source='reading_time_minutes', read_only=True)
    tag_names = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'title', 'slug', 'excerpt',
            'featured_image', 'thumbnail',
            'author_username', 'category_name', 'category_slug',
            'status', 'is_featured', 'published_at',
            'views_count', 'like_count', 'comment_count',
            'reading_time', 'tag_names', 'language',
        ]

    def get_tag_names(self, obj):
        return [{'name': t.name, 'slug': t.slug} for t in obj.tags.all()]

BlogPostListSerializer.Meta.model = _blog('BlogPost')


class BlogPostSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    author_name = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    reading_time = serializers.IntegerField(source='reading_time_minutes', read_only=True)
    is_published = serializers.BooleanField(read_only=True)
    tag_names = serializers.SerializerMethodField()
    seo_data = serializers.SerializerMethodField()
    related_posts = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'title', 'slug', 'body', 'excerpt',
            'featured_image', 'thumbnail',
            'author', 'author_username', 'author_name',
            'category', 'category_name', 'category_slug',
            'tags',
            'status', 'is_active', 'is_featured', 'is_pinned', 'allow_comments',
            'published_at', 'scheduled_at',
            'views_count', 'share_count', 'like_count', 'comment_count',
            'language', 'version',
            'is_published', 'reading_time',
            'tag_names', 'seo_data', 'related_posts',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'views_count', 'share_count', 'like_count',
            'comment_count', 'version', 'created_at', 'updated_at'
        ]

    def get_author_name(self, obj):
        if obj.author:
            return obj.author.get_full_name() or obj.author.username
        return ''

    def get_tag_names(self, obj):
        return [{'id': t.id, 'name': t.name, 'slug': t.slug} for t in obj.tags.all()]

    def get_seo_data(self, obj):
        try:
            return BlogSEOSerializer(obj.seo).data
        except Exception:
            return None

    def get_related_posts(self, obj):
        try:
            related = obj.get_related_posts(limit=4)
            return BlogPostListSerializer(related, many=True).data
        except Exception:
            return []

BlogPostSerializer.Meta.model = _blog('BlogPost')


# ── Media Serializers ─────────────────────────────────────────────

class MediaTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = ['id', 'name', 'is_active', 'created_at']
        read_only_fields = ['created_at']

MediaTagSerializer.Meta.model = _media('MediaTag')


class MediaFolderSerializer(serializers.ModelSerializer):
    total_size_human = serializers.SerializerMethodField()
    breadcrumbs = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'name', 'parent', 'path',
            'description', 'is_active', 'is_public',
            'created_by', 'file_count', 'total_size',
            'total_size_human', 'breadcrumbs',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'path', 'file_count', 'total_size', 'created_at', 'updated_at']

    def get_total_size_human(self, obj):
        size = obj.total_size or 0
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def get_breadcrumbs(self, obj):
        return obj.breadcrumbs

MediaFolderSerializer.Meta.model = _media('MediaFolder')


class MediaVariantSerializer(serializers.ModelSerializer):
    file_url = serializers.CharField(read_only=True)
    size_human = serializers.CharField(read_only=True)

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'variant_type', 'file_path', 'cdn_url',
            'width', 'height', 'size_bytes', 'mime_type',
            'is_active', 'generated_at', 'file_url', 'size_human'
        ]
        read_only_fields = ['uuid', 'generated_at']

MediaVariantSerializer.Meta.model = _media('MediaVariant')


class MediaFileListSerializer(serializers.ModelSerializer):
    size_human = serializers.CharField(read_only=True)
    file_url = serializers.CharField(read_only=True)
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'filename', 'file_type', 'mime_type',
            'size_bytes', 'size_human', 'file_url', 'thumbnail_url',
            'title', 'alt_text', 'is_public', 'is_active',
            'width', 'height', 'created_at'
        ]

    def get_thumbnail_url(self, obj):
        return obj.get_thumbnail_url()

MediaFileListSerializer.Meta.model = _media('MediaFile')


class MediaFileSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)
    folder_name = serializers.CharField(source='folder.name', read_only=True)
    folder_path = serializers.CharField(source='folder.path', read_only=True)
    size_human = serializers.CharField(read_only=True)
    file_url = serializers.CharField(read_only=True)
    is_image = serializers.BooleanField(read_only=True)
    is_video = serializers.BooleanField(read_only=True)
    extension = serializers.CharField(read_only=True)
    tag_names = serializers.SerializerMethodField()
    variants = MediaVariantSerializer(many=True, read_only=True)
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'file', 'filename', 'file_type', 'mime_type',
            'size_bytes', 'size_human', 'file_url', 'thumbnail_url',
            'folder', 'folder_name', 'folder_path',
            'title', 'alt_text', 'description', 'caption',
            'width', 'height',
            'cdn_url', 'cdn_pushed_at',
            'is_active', 'is_public',
            'uploaded_by', 'uploaded_by_username',
            'download_count', 'view_count', 'usage_count',
            'is_image', 'is_video', 'extension',
            'tag_names', 'variants',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'filename', 'file_type', 'mime_type', 'size_bytes',
            'cdn_pushed_at', 'download_count', 'view_count', 'usage_count',
            'created_at', 'updated_at'
        ]

    def get_tag_names(self, obj):
        return [{'id': t.id, 'name': t.name} for t in obj.tags.all()]

    def get_thumbnail_url(self, obj):
        return obj.get_thumbnail_url()

MediaFileSerializer.Meta.model = _media('MediaFile')


# ── Popup Serializers ─────────────────────────────────────────────

class PopupRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'popup', 'trigger_type', 'conditions',
            'is_active', 'priority', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

PopupRuleSerializer.Meta.model = _popup('PopupRule')


class PopupStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'popup', 'date',
            'views', 'clicks', 'dismissals', 'conversions',
            'unique_users', 'conversion_rate'
        ]
        read_only_fields = ['uuid']

PopupStatSerializer.Meta.model = _popup('PopupStat')


class PopupABTestSerializer(serializers.ModelSerializer):
    variant_a_conversion_rate = serializers.SerializerMethodField()
    variant_b_conversion_rate = serializers.SerializerMethodField()
    has_sufficient_data = serializers.BooleanField(read_only=True)

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'popup', 'name', 'status',
            'variant_a', 'variant_a_name',
            'variant_b', 'variant_b_name',
            'split_pct', 'winner', 'winner_determined_at', 'ended_at',
            'variant_a_views', 'variant_a_conversions', 'variant_a_conversion_rate',
            'variant_b_views', 'variant_b_conversions', 'variant_b_conversion_rate',
            'min_sample_size', 'confidence_level', 'has_sufficient_data',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'variant_a_views', 'variant_a_conversions',
            'variant_b_views', 'variant_b_conversions',
            'winner_determined_at', 'created_at', 'updated_at'
        ]

    def get_variant_a_conversion_rate(self, obj):
        return obj.variant_a_conversion_rate

    def get_variant_b_conversion_rate(self, obj):
        return obj.variant_b_conversion_rate

PopupABTestSerializer.Meta.model = _popup('PopupABTest')


class PopupSerializer(serializers.ModelSerializer):
    click_through_rate = serializers.SerializerMethodField()
    conversion_rate = serializers.SerializerMethodField()
    dismissal_rate = serializers.SerializerMethodField()
    popup_is_active_now = serializers.SerializerMethodField()
    rules = PopupRuleSerializer(many=True, read_only=True)

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'name', 'popup_type', 'status', 'position',
            'title', 'body', 'cta_text', 'cta_url',
            'cta_secondary_text', 'cta_secondary_url',
            'image', 'background_color', 'text_color',
            'custom_css', 'custom_html',
            'start_date', 'end_date',
            'is_active', 'target_pages', 'exclude_pages', 'target_audience',
            'show_to_logged_in', 'show_to_anonymous', 'min_user_level',
            'animation', 'overlay', 'close_on_overlay', 'show_close_button',
            'auto_close_seconds', 'delay_seconds', 'cookie_days', 'max_shows_per_user',
            'total_views', 'total_clicks', 'total_dismissals', 'total_conversions',
            'priority',
            'click_through_rate', 'conversion_rate', 'dismissal_rate',
            'popup_is_active_now', 'rules',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'total_views', 'total_clicks',
            'total_dismissals', 'total_conversions',
            'created_at', 'updated_at'
        ]

    def get_click_through_rate(self, obj):
        return obj.click_through_rate

    def get_conversion_rate(self, obj):
        return obj.conversion_rate

    def get_dismissal_rate(self, obj):
        return obj.dismissal_rate

    def get_popup_is_active_now(self, obj):
        return obj.is_active_now()

PopupSerializer.Meta.model = _popup('Popup')


# ── Menu Serializers ──────────────────────────────────────────────

class MenuVisibilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = ['id', 'uuid', 'menu_item', 'show_for', 'role_name', 'is_active']
        read_only_fields = ['uuid']

MenuVisibilitySerializer.Meta.model = _menu('MenuVisibility')


class MenuItemSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    depth = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'menu', 'parent', 'label', 'url', 'link_type',
            'icon', 'sort_order', 'is_active', 'is_featured',
            'open_in_new_tab', 'css_class', 'rel',
            'has_mega_menu', 'mega_menu_content',
            'click_count', 'depth', 'children',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'click_count', 'created_at', 'updated_at']

    def get_children(self, obj):
        children = obj.children.filter(is_active=True).order_by('sort_order')
        return MenuItemSerializer(children, many=True).data

    def get_depth(self, obj):
        return obj.depth

MenuItemSerializer.Meta.model = _menu('MenuItem')


class MenuSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'name', 'slug', 'location',
            'description', 'is_active', 'is_locked',
            'cache_version', 'items',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'cache_version', 'created_at', 'updated_at']

    def get_items(self, obj):
        top_items = obj.items.filter(parent__isnull=True, is_active=True).order_by('sort_order')
        return MenuItemSerializer(top_items, many=True).data

MenuSerializer.Meta.model = _menu('Menu')


class LandingSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'name', 'section_type', 'content',
            'sort_order', 'is_active', 'page_slug', 'show_for',
            'background_color', 'css_class', 'custom_css',
            'view_count', 'click_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'view_count', 'click_count', 'created_at', 'updated_at']

LandingSectionSerializer.Meta.model = _menu('LandingSection')


# ── SEO Serializers ───────────────────────────────────────────────

class SEOConfigSerializer(serializers.ModelSerializer):
    og_image_url = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'site_name', 'default_title', 'title_separator',
            'default_description', 'default_keywords',
            'og_image', 'og_image_url', 'og_type',
            'twitter_card', 'twitter_site', 'twitter_creator',
            'google_analytics_id', 'google_tag_manager_id',
            'google_search_console', 'bing_webmaster',
            'facebook_app_id', 'canonical_base_url',
            'enable_breadcrumbs', 'enable_json_ld', 'json_ld_org_data',
            'noindex_site', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

    def get_og_image_url(self, obj):
        return obj.get_og_image_url()

SEOConfigSerializer.Meta.model = _seo('SEOConfig')


class SitemapSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'url', 'changefreq', 'priority',
            'last_modified', 'is_active',
            'source_type', 'source_id',
            'is_auto_generated', 'last_crawled', 'crawl_status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'is_auto_generated', 'last_crawled', 'crawl_status',
                           'created_at', 'updated_at']

SitemapSerializer.Meta.model = _seo('Sitemap')


class Redirect301Serializer(serializers.ModelSerializer):
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'from_url', 'to_url', 'redirect_type',
            'is_active', 'hit_count', 'last_hit', 'notes',
            'created_by', 'expires_at', 'is_expired',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'hit_count', 'last_hit', 'created_at', 'updated_at']

    def get_is_expired(self, obj):
        return obj.is_expired()

Redirect301Serializer.Meta.model = _seo('Redirect301')


class RobotsConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'name', 'is_active',
            'allow_rules', 'disallow_rules', 'sitemap_url',
            'crawl_delay', 'per_bot_rules', 'custom_content',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

RobotsConfigSerializer.Meta.model = _seo('RobotsConfig')


# ═══════════════════════════════════════════════════════════════════
# EXTRA CPAlead CMS Serializers
# ═══════════════════════════════════════════════════════════════════

def _extras(name):
    import importlib
    m = importlib.import_module('api.cms.models_new.extras')
    return getattr(m, name)


class AnnouncementSerializer(serializers.ModelSerializer):
    is_active_now = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'title', 'message', 'announcement_type',
            'icon', 'link_url', 'link_text', 'is_active', 'is_pinned',
            'is_dismissible', 'show_to_logged_in', 'show_to_anonymous',
            'start_date', 'end_date', 'priority',
            'view_count', 'dismiss_count', 'is_active_now',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'view_count', 'dismiss_count', 'created_at', 'updated_at']

    def get_is_active_now(self, obj):
        return obj.is_active_now()

AnnouncementSerializer.Meta.model = _extras('Announcement')


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'notification_type', 'title', 'message',
            'icon', 'image', 'action_url', 'action_text',
            'is_read', 'read_at', 'is_active',
            'reward_amount', 'reward_currency',
            'source_type', 'source_id', 'metadata',
            'created_at',
        ]
        read_only_fields = ['uuid', 'is_read', 'read_at', 'created_at']

NotificationSerializer.Meta.model = _extras('Notification')


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'name', 'notification_type',
            'title_template', 'message_template', 'icon',
            'is_active', 'variables', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

NotificationTemplateSerializer.Meta.model = _extras('NotificationTemplate')


class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'name', 'email_type', 'subject',
            'html_body', 'text_body', 'from_name', 'from_email',
            'reply_to', 'is_active', 'variables',
            'send_count', 'last_sent', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'send_count', 'last_sent', 'created_at', 'updated_at']

EmailTemplateSerializer.Meta.model = _extras('EmailTemplate')


class TestimonialSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    author_username = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'user', 'author_name', 'author_location',
            'author_avatar', 'content', 'rating',
            'earning_amount', 'earning_period',
            'is_active', 'is_featured', 'is_verified',
            'sort_order', 'category',
            'display_name', 'author_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

    def get_author_username(self, obj):
        return obj.user.username if obj.user else ''

TestimonialSerializer.Meta.model = _extras('Testimonial')


class SocialLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'platform', 'name', 'url', 'icon_class',
            'is_active', 'sort_order', 'location', 'open_in_new_tab',
            'follower_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

SocialLinkSerializer.Meta.model = _extras('SocialLink')


class PopupDismissalSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'popup', 'user', 'session_key',
            'dismissed_at', 'show_count', 'expires_at'
        ]
        read_only_fields = ['uuid', 'dismissed_at']

PopupDismissalSerializer.Meta.model = _extras('PopupDismissal')


class UserContentInteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'interaction_type', 'content_type',
            'content_id', 'metadata', 'created_at'
        ]
        read_only_fields = ['uuid', 'created_at']

UserContentInteractionSerializer.Meta.model = _extras('UserContentInteraction')


class ContentRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'content_type', 'content_id',
            'rating', 'review', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

ContentRatingSerializer.Meta.model = _extras('ContentRating')


class CPALeadConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'name', 'is_active',
            'publisher_id', 'campaign_id', 'website_id',
            'default_reward_per_click', 'default_reward_per_view',
            'default_reward_per_offer', 'reward_currency',
            'daily_click_limit_per_user', 'daily_earning_cap_per_user',
            'min_withdrawal', 'postback_url',
            'enable_fraud_detection',
            'min_time_between_clicks_seconds', 'max_clicks_per_ip_per_hour',
            'total_rewards_paid', 'total_clicks_tracked', 'total_offers_completed',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'total_rewards_paid', 'total_clicks_tracked',
            'total_offers_completed', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'api_key': {'write_only': True},
            'postback_secret': {'write_only': True},
        }

CPALeadConfigSerializer.Meta.model = _extras('CPALeadConfig')


class SiteLayoutConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = [
            'id', 'uuid', 'name', 'section_type', 'config',
            'is_active', 'is_default', 'theme',
            'custom_css', 'custom_js',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

SiteLayoutConfigSerializer.Meta.model = _extras('SiteLayoutConfig')


# ═══════════════════════════════════════════════════════════════════
# CPAlead Core Model Serializers
# ═══════════════════════════════════════════════════════════════════

def _cpalead(name):
    import importlib
    return getattr(importlib.import_module('api.cms.models_new.cpalead'), name)


class VirtualCurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = ['id', 'uuid', 'name', 'symbol', 'usd_ratio',
                  'daily_earn_cap', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']

VirtualCurrencySerializer.Meta.model = _cpalead('VirtualCurrency')


class UserVirtualBalanceSerializer(serializers.ModelSerializer):
    currency_name   = serializers.CharField(source='currency.name', read_only=True)
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)
    usd_equivalent  = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = ['id', 'balance', 'total_earned', 'total_spent',
                  'today_earned', 'last_earn_date',
                  'currency_name', 'currency_symbol', 'usd_equivalent',
                  'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def get_usd_equivalent(self, obj):
        try:
            return float(obj.currency.virtual_to_usd(obj.balance))
        except Exception:
            return 0.0

UserVirtualBalanceSerializer.Meta.model = _cpalead('UserVirtualBalance')


class VirtualTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = ['id', 'uuid', 'tx_type', 'amount', 'balance_after',
                  'usd_equivalent', 'description', 'source_type', 'source_id',
                  'cpalead_lead_id', 'cpalead_campaign_id', 'created_at']
        read_only_fields = ['uuid', 'created_at']

VirtualTransactionSerializer.Meta.model = _cpalead('VirtualTransaction')


class OfferWallConfigSerializer(serializers.ModelSerializer):
    currency_name = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = ['id', 'uuid', 'name', 'offerwall_title', 'header_title',
                  'publisher_id', 'background_color', 'button_color', 'text_color',
                  'target_countries', 'target_devices', 'show_offer_types',
                  'is_active', 'total_views', 'total_completions',
                  'currency_name', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'total_views', 'total_completions', 'created_at', 'updated_at']
        extra_kwargs = {'website_id': {'write_only': True}}

    def get_currency_name(self, obj):
        return obj.currency if obj.currency else 'Coins'

OfferWallConfigSerializer.Meta.model = _cpalead('OfferWallConfig')


class ContentLockerSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = ['id', 'uuid', 'name', 'locker_type', 'title', 'description',
                  'preview_content', 'unlock_mode', 'zero_hours_mode',
                  'blur_preview', 'blur_amount', 'overlay_opacity',
                  'reward_user_on_unlock', 'reward_virtual_amount',
                  'is_active', 'total_views', 'total_unlocks', 'conversion_rate',
                  'related_page_slug', 'related_blog_slug',
                  'created_at', 'updated_at']
        read_only_fields = ['uuid', 'total_views', 'total_unlocks', 'conversion_rate', 'created_at', 'updated_at']
        extra_kwargs = {'locked_content': {'write_only': True}}  # Never expose locked content in list

ContentLockerSerializer.Meta.model = _cpalead('ContentLocker')


class ClickLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = ['id', 'uuid', 'click_id', 'offer_id', 'click_source',
                  'device_type', 'country_code', 'has_converted',
                  'converted_at', 'payout_usd', 'is_fraud', 'created_at']
        read_only_fields = ['uuid', 'created_at']

ClickLogSerializer.Meta.model = _cpalead('ClickLog')


class ConversionLogSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = ['id', 'uuid', 'subid', 'lead_id', 'payout_usd', 'campaign_id',
                  'virtual_amount_awarded', 'usd_amount_awarded', 'status',
                  'rejection_reason', 'ip_address', 'created_at', 'processed_at',
                  'username']
        read_only_fields = ['uuid', 'created_at', 'processed_at']
        extra_kwargs = {'raw_postback_data': {'write_only': True}}

    def get_username(self, obj):
        return obj.user.username if obj.user else ''

ConversionLogSerializer.Meta.model = _cpalead('ConversionLog')


class OfferCacheSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = ['id', 'offer_id', 'offer_type', 'title', 'description',
                  'payout_usd', 'payout_virtual', 'icon_url',
                  'is_featured', 'is_quiz', 'category',
                  'estimated_time_minutes', 'countries', 'devices', 'fetched_at']

OfferCacheSerializer.Meta.model = _cpalead('OfferCache')


class IntegrationAuditLogSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()

    class Meta:
        try:
            from api.cms.INTEGRATION_SYSTEM.integ_audit_logs import IntegrationAuditLog
        except ImportError:
            pass
        model = IntegrationAuditLog
        fields = ['id', 'action', 'source', 'ip_address', 'success',
                  'message', 'event_id', 'lead_id', 'amount',
                  'duration_ms', 'created_at', 'username']
        read_only_fields = fields

    def get_username(self, obj):
        return obj.user.username if obj.user else ''


# ═══════════════════════════════════════════════════════════════════
# Professional Serializers — with validate_ methods
# ═══════════════════════════════════════════════════════════════════

class WithdrawalRequestSerializer(serializers.ModelSerializer):
    username      = serializers.CharField(source='user.username', read_only=True)
    method_display = serializers.CharField(source='get_method_display', read_only=True)

    class Meta:
        model = _WithdrawalRequest
        fields = ['id', 'uuid', 'method', 'method_display', 'account_id',
                  'requested_coins', 'requested_usd', 'fee_usd', 'net_usd',
                  'status', 'reject_reason', 'transaction_id',
                  'created_at', 'approved_at', 'paid_at', 'username']
        read_only_fields = ['uuid', 'fee_usd', 'net_usd', 'status', 'created_at',
                            'approved_at', 'paid_at', 'reject_reason', 'transaction_id']
        extra_kwargs = {'account_id': {'write_only': True}}

    def validate_requested_coins(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value

    def validate_method(self, value):
        allowed = ['paypal', 'payoneer', 'usdt', 'bitcoin', 'wire', 'ach', 'bank']
        if value not in allowed:
            raise serializers.ValidationError(f"Invalid method. Choose: {', '.join(allowed)}")
        return value


class ReferralCodeSerializer(serializers.ModelSerializer):
    stats = serializers.SerializerMethodField()

    class Meta:
        model = _ReferralCode
        fields = ['id', 'code', 'is_active', 'total_referrals',
                  'total_bonus_usd', 'total_bonus_coins', 'stats', 'created_at']
        read_only_fields = ['code', 'total_referrals', 'total_bonus_usd',
                            'total_bonus_coins', 'created_at']

    def get_stats(self, obj):
        return {
            'referral_link': f"/join?ref={obj.code}",
            'bonus_rate_pct': 5.0,
            'active_months': 6,
        }


class LeaderboardEntrySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = _LeaderboardEntry
        fields = ['rank', 'username', 'avatar_url', 'score', 'score_usd',
                  'score_coins', 'offers_count', 'category']
        read_only_fields = fields

    def get_avatar_url(self, obj):
        try:
            return obj.user.profile.avatar_url or ''
        except Exception:
            return ''


class QuizTemplateSerializer(serializers.ModelSerializer):
    question_count  = serializers.SerializerMethodField()
    completion_rate = serializers.SerializerMethodField()

    class Meta:
        model = _QuizTemplate
        fields = ['id', 'uuid', 'title', 'slug', 'description', 'quiz_type',
                  'thumbnail', 'payout_usd', 'is_featured', 'is_active',
                  'total_attempts', 'total_completions', 'question_count',
                  'completion_rate', 'created_at']
        read_only_fields = ['uuid', 'total_attempts', 'total_completions', 'created_at']

    def get_question_count(self, obj):
        return obj.questions.count()

    def get_completion_rate(self, obj):
        return obj.completion_rate

    def validate_payout_usd(self, value):
        if value < 0:
            raise serializers.ValidationError("Payout cannot be negative")
        if value > 100:
            raise serializers.ValidationError("Payout too high (max $100)")
        return value


class SmartLinkSerializer(serializers.ModelSerializer):
    conversion_rate = serializers.SerializerMethodField()
    rule_count = serializers.SerializerMethodField()

    class Meta:
        model = _SmartLink
        fields = ['id', 'uuid', 'name', 'slug', 'rotation_mode', 'is_active',
                  'total_clicks', 'total_conversions', 'conversion_rate',
                  'rule_count', 'created_at']
        read_only_fields = ['uuid', 'total_clicks', 'total_conversions', 'created_at']

    def get_conversion_rate(self, obj):
        if not obj.total_clicks:
            return 0.0
        return round(obj.total_conversions / obj.total_clicks * 100, 1)

    def get_rule_count(self, obj):
        return obj.routing_rules.filter(is_active=True).count()


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    coins_balance = serializers.SerializerMethodField()
    streak_days   = serializers.SerializerMethodField()
    leaderboard_rank = serializers.SerializerMethodField()

    class Meta:
        model = _UserProfile
        fields = ['id', 'username', 'email', 'display_name', 'avatar_url', 'bio',
                  'level', 'total_earned_usd', 'total_earned_coins',
                  'total_withdrawn_usd', 'total_offers_completed',
                  'kyc_status', 'is_suspended', 'show_on_leaderboard',
                  'coins_balance', 'streak_days', 'leaderboard_rank',
                  'preferred_currency', 'country', 'created_at']
        read_only_fields = ['level', 'total_earned_usd', 'total_earned_coins',
                            'total_withdrawn_usd', 'total_offers_completed',
                            'kyc_status', 'is_suspended', 'created_at']

    def get_coins_balance(self, obj):
        try:
            return float(obj.user.virtual_balance.balance)
        except Exception:
            return 0.0

    def get_streak_days(self, obj):
        try:
            return obj.user.earning_streak.current_streak
        except Exception:
            return 0

    def get_leaderboard_rank(self, obj):
        try:
            from api.cms.services_new.LeaderboardService import LeaderboardService
            rank_data = LeaderboardService.get_user_rank(obj.user, 'weekly', 'earnings')
            return rank_data.get('rank', 0)
        except Exception:
            return 0

    def validate_display_name(self, value):
        if len(value) < 2:
            raise serializers.ValidationError("Display name must be at least 2 characters")
        if len(value) > 50:
            raise serializers.ValidationError("Display name cannot exceed 50 characters")
        import re
        if not re.match(r'^[\w\s\.\-\_]+$', value):
            raise serializers.ValidationError("Display name contains invalid characters")
        return value.strip()


class DynamicFormSerializer(serializers.ModelSerializer):
    fields_count = serializers.SerializerMethodField()

    class Meta:
        model = _DynamicForm
        fields = ['id', 'uuid', 'name', 'slug', 'title', 'description',
                  'submit_text', 'success_message', 'is_active',
                  'reward_on_submit', 'reward_coins', 'total_submissions',
                  'fields_count', 'created_at']
        read_only_fields = ['uuid', 'total_submissions', 'created_at']

    def get_fields_count(self, obj):
        return obj.fields.filter(is_visible=True).count()

    def validate_slug(self, value):
        import re
        if not re.match(r'^[a-z0-9\-]+$', value):
            raise serializers.ValidationError("Slug must contain only lowercase letters, numbers, and hyphens")
        return value


class SiteConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = _SiteConfig
        fields = ['id', 'site_name', 'site_tagline', 'site_domain',
                  'logo_url', 'favicon_url', 'primary_color', 'secondary_color',
                  'maintenance_mode', 'maintenance_message',
                  'registration_enabled', 'referral_enabled',
                  'leaderboard_enabled', 'quiz_enabled', 'offerwall_enabled',
                  'min_withdrawal_coins', 'min_withdrawal_usd',
                  'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'maintenance_allowed_ips': {'write_only': True},
            'custom_js': {'write_only': True},
        }

    def validate_primary_color(self, value):
        import re
        if not re.match(r'^#[0-9a-fA-F]{3,6}$', value):
            raise serializers.ValidationError("Invalid hex color format (e.g. #007bff)")
        return value


# ═══════════════════════════════════════════════════════════════════
# NEW MODEL SERIALIZERS — Video, RTB, Analytics, Search, FeatureFlags
# ═══════════════════════════════════════════════════════════════════

class VideoContentSerializer(serializers.ModelSerializer):
    """Serializer for AI video content."""
    ctr = serializers.SerializerMethodField()
    conversion_rate = serializers.SerializerMethodField()
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    style_display = serializers.CharField(source='get_video_style_display', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = _VideoContent
        fields = [
            'id', 'uuid', 'title', 'slug', 'topic', 'platform', 'platform_display',
            'video_style', 'style_display', 'status', 'ai_generated', 'ai_credits_used',
            'script', 'thumbnail_url', 'video_url', 'duration_sec',
            'tracking_url', 'views_count', 'clicks_count', 'conversions',
            'revenue_usd', 'ctr', 'conversion_rate',
            'publish_at', 'published_at', 'created_by_username', 'created_at', 'updated_at',
        ]
        read_only_fields = ['uuid', 'ai_credits_used', 'views_count',
                            'clicks_count', 'conversions', 'revenue_usd', 'created_at']

    def get_ctr(self, obj):
        return obj.ctr

    def get_conversion_rate(self, obj):
        return obj.conversion_rate

    def validate_platform(self, value):
        allowed = ['youtube_shorts', 'tiktok', 'instagram_reel', 'generic']
        if value not in allowed:
            raise serializers.ValidationError(f"Platform must be one of: {', '.join(allowed)}")
        return value

    def validate_topic(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Topic must be at least 3 characters")
        if len(value) > 300:
            raise serializers.ValidationError("Topic too long (max 300 chars)")
        return value.strip()


class RTBConfigSerializer(serializers.ModelSerializer):
    """Serializer for RTB publisher configuration."""
    ad_slot_count = serializers.SerializerMethodField()
    fill_rate = serializers.SerializerMethodField()

    class Meta:
        model = _RTBConfig
        fields = [
            'id', 'uuid', 'name', 'publisher_id', 'is_active',
            'floor_price_cpc_usd', 'floor_price_cpa_usd', 'floor_price_cpi_usd',
            'preferred_countries', 'preferred_categories', 'blocked_categories',
            'preferred_devices', 'auction_timeout_ms', 'max_ads_per_page',
            'enable_header_bidding', 'total_impressions', 'total_clicks',
            'total_revenue_usd', 'avg_ecpm', 'ad_slot_count', 'fill_rate',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['uuid', 'total_impressions', 'total_clicks',
                            'total_revenue_usd', 'avg_ecpm', 'created_at']

    def get_ad_slot_count(self, obj):
        return obj.ad_slots.filter(is_active=True).count()

    def get_fill_rate(self, obj):
        from api.cms.models_new.rtb import RTBBidLog
        from django.db.models import Count, Q
        stats = RTBBidLog.objects.filter(ad_slot__rtb_config=obj).aggregate(
            total=Count('id'), filled=Count('id', filter=Q(was_filled=True))
        )
        if stats['total']:
            return round(stats['filled'] / stats['total'] * 100, 2)
        return 0.0

    def validate_auction_timeout_ms(self, value):
        if value < 50 or value > 5000:
            raise serializers.ValidationError("Timeout must be between 50ms and 5000ms")
        return value


class RTBAdSlotSerializer(serializers.ModelSerializer):
    """Serializer for RTB ad slots."""
    ctr = serializers.SerializerMethodField()
    ecpm = serializers.SerializerMethodField()
    slot_type_display = serializers.CharField(source='get_slot_type_display', read_only=True)

    class Meta:
        model = _RTBAdSlot
        fields = [
            'id', 'uuid', 'name', 'slot_type', 'slot_type_display',
            'page_location', 'floor_price_usd', 'is_active',
            'impressions', 'clicks', 'revenue_usd', 'ctr', 'ecpm', 'created_at',
        ]
        read_only_fields = ['uuid', 'impressions', 'clicks', 'revenue_usd', 'created_at']

    def get_ctr(self, obj):
        return obj.ctr

    def get_ecpm(self, obj):
        return obj.ecpm


class SearchResultSerializer(serializers.Serializer):
    """Serializer for search results."""
    id = serializers.IntegerField()
    title = serializers.CharField()
    url = serializers.CharField()
    content_type = serializers.CharField()
    excerpt = serializers.CharField()
    score = serializers.FloatField()
    thumbnail = serializers.CharField(allow_blank=True)
    published_at = serializers.CharField(allow_null=True)

    def to_representation(self, instance):
        if hasattr(instance, 'to_dict'):
            return instance.to_dict()
        return super().to_representation(instance)


class FeatureFlagSerializer(serializers.Serializer):
    """Serializer for feature flags."""
    flag_name = serializers.CharField()
    is_enabled = serializers.BooleanField()
    description = serializers.CharField(allow_blank=True, default='')

    class Meta:
        fields = ['flag_name', 'is_enabled', 'description']


class AnalyticsDashboardSerializer(serializers.Serializer):
    """Serializer for analytics dashboard data."""
    generated_at = serializers.CharField()
    period_days = serializers.IntegerField()
    revenue = serializers.DictField()
    users = serializers.DictField()
    offerwall = serializers.DictField()
    withdrawals = serializers.DictField()
    content = serializers.DictField()

    class Meta:
        fields = ['generated_at', 'period_days', 'revenue', 'users',
                  'offerwall', 'withdrawals', 'content']


class RTBStatsSerializer(serializers.Serializer):
    """Serializer for RTB publisher stats."""
    period_days = serializers.IntegerField()
    config_name = serializers.CharField()
    total_slots = serializers.IntegerField()
    bid_requests = serializers.IntegerField()
    filled_bids = serializers.IntegerField()
    fill_rate_pct = serializers.FloatField()
    total_revenue_usd = serializers.FloatField()
    avg_response_ms = serializers.FloatField()
    total_impressions = serializers.IntegerField()
    ecpm = serializers.FloatField()
    slots = serializers.ListField(child=serializers.DictField())


class ComplianceReportSerializer(serializers.Serializer):
    """GDPR compliance report serializer."""
    compliant = serializers.BooleanField()
    issues = serializers.ListField(child=serializers.DictField())
    period_days = serializers.IntegerField(required=False)
    generated_at = serializers.DateTimeField(required=False)


class UserDataExportSerializer(serializers.Serializer):
    """GDPR data export serializer."""
    exported_at = serializers.CharField()
    user = serializers.DictField()
    profile = serializers.DictField()
    virtual_balance = serializers.DictField()
    transactions = serializers.ListField(child=serializers.DictField())
    conversions = serializers.ListField(child=serializers.DictField())
    withdrawals = serializers.ListField(child=serializers.DictField())
    quiz_attempts = serializers.ListField(child=serializers.DictField())
    referrals = serializers.DictField()


class BackgroundJobSerializer(serializers.Serializer):
    """Serializer for background job results."""
    job = serializers.CharField(required=False)
    total = serializers.IntegerField(required=False)
    processed = serializers.IntegerField(required=False)
    failed = serializers.IntegerField(required=False, default=0)
    dry_run = serializers.BooleanField(required=False, default=False)
    results = serializers.DictField(required=False)
    errors = serializers.ListField(child=serializers.CharField(), required=False)


# ═══════════════════════════════════════════════════════════════════
# FINAL SERIALIZERS — Comments, APIKey, UserSession, LandingPage, Currency
# ═══════════════════════════════════════════════════════════════════

class NewCommentSerializer(serializers.ModelSerializer):
    """Serializer for api.cms.models_new.comments.Comment (blog/new comment system).
    Renamed from CommentSerializer to avoid shadowing cms.Comment serializer above.
    """
    author_display = serializers.CharField(read_only=True)
    reply_count    = serializers.SerializerMethodField()
    replies        = serializers.SerializerMethodField()

    class Meta:
        model = _NewComment
        fields = ['id', 'uuid', 'content_type', 'object_id', 'author_display',
                  'body', 'status', 'likes', 'dislikes', 'is_pinned',
                  'reply_count', 'replies', 'created_at']
        read_only_fields = ['uuid', 'likes', 'dislikes', 'status', 'created_at']

    def get_reply_count(self, obj):
        return obj.replies.filter(status='approved').count()

    def get_replies(self, obj):
        # Only return top-level reply list (not recursive to avoid deep nesting)
        if obj.parent_id:
            return []
        replies = obj.replies.filter(status='approved').order_by('created_at')[:5]
        return [{
            'id': r.id, 'author': r.author_display,
            'body': r.body, 'likes': r.likes,
            'created_at': r.created_at.isoformat(),
        } for r in replies]

    def validate_body(self, value):
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Comment too short")
        if len(value) > 2000:
            raise serializers.ValidationError("Comment too long (max 2000 chars)")
        return value.strip()


from api.cms.models_new.api_keys import APIKey as _APIKey  # noqa


class APIKeySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = _APIKey
        fields = ['id', 'uuid', 'name', 'key_prefix', 'scope', 'is_active',
                  'request_count', 'last_used_at', 'expires_at',
                  'username', 'created_at']
        read_only_fields = ['uuid', 'key_prefix', 'request_count', 'last_used_at', 'created_at']
        extra_kwargs = {'key_hash': {'write_only': True}}

    def validate_scope(self, value):
        allowed = ['read', 'write', 'admin', 'postback', 'analytics', 'publisher']
        if value not in allowed:
            raise serializers.ValidationError(f"Invalid scope. Choose: {', '.join(allowed)}")
        return value


from api.cms.models_new.sessions import UserSession as _UserSession  # noqa


class UserSessionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = _UserSession
        fields = ['id', 'uuid', 'ip_address', 'device_type', 'country',
                  'is_active', 'last_activity', 'created_at', 'revoked_at', 'username']
        read_only_fields = fields


class LandingPageSerializer(serializers.ModelSerializer):
    conversion_rate = serializers.SerializerMethodField()
    ctr = serializers.SerializerMethodField()

    class Meta:
        model = _LandingPage
        fields = ['id', 'uuid', 'name', 'slug', 'niche', 'headline',
                  'sub_headline', 'description', 'cta_text', 'thumbnail',
                  'background_color', 'accent_color', 'is_active', 'is_featured',
                  'views', 'clicks', 'conversions', 'conversion_rate', 'ctr',
                  'created_at', 'updated_at']
        read_only_fields = ['uuid', 'views', 'clicks', 'conversions', 'created_at']

    def get_conversion_rate(self, obj):
        return obj.conversion_rate

    def get_ctr(self, obj):
        return obj.ctr

    def validate_background_color(self, value):
        import re
        if not re.match(r'^#[0-9a-fA-F]{3,6}$', value):
            raise serializers.ValidationError("Invalid hex color")
        return value

    def validate_slug(self, value):
        import re
        if not re.match(r'^[a-z0-9\-]+$', value):
            raise serializers.ValidationError("Slug must be lowercase with hyphens only")
        return value


class CurrencyRateSerializer(serializers.Serializer):
    code   = serializers.CharField()
    symbol = serializers.CharField()
    rate   = serializers.FloatField()


class CurrencyConvertSerializer(serializers.Serializer):
    usd       = serializers.FloatField()
    currency  = serializers.CharField()
    amount    = serializers.FloatField()
    formatted = serializers.CharField()


class FastPayStatusSerializer(serializers.Serializer):
    eligible              = serializers.BooleanField()
    balance_coins         = serializers.FloatField()
    min_coins_required    = serializers.FloatField()
    has_payout_method     = serializers.BooleanField()
    reason                = serializers.CharField(allow_blank=True)


class MCPToolSerializer(serializers.Serializer):
    name        = serializers.CharField()
    description = serializers.CharField()
    inputSchema = serializers.DictField()


class TwoFactorStatusSerializer(serializers.Serializer):
    enabled  = serializers.BooleanField()
    username = serializers.CharField()
