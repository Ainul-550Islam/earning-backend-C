# cms/filters.py
"""
CMS FilterSets — complete per-model filtering.

Every FilterSet maps to a model and defines:
  - exact / icontains / date-range / boolean filters
  - ordering via OrderingFilter

Usage in ViewSet:
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = BlogPostFilter
"""

import django_filters
from django_filters import rest_framework as drf_filters
from django.db import models as dj_models


# ─────────────────────────────────────────────────────────────────────────────
# BLOG FILTERS
# ─────────────────────────────────────────────────────────────────────────────

class BlogPostFilter(drf_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr='icontains')
    slug = django_filters.CharFilter(lookup_expr='icontains')
    author__username = django_filters.CharFilter(lookup_expr='icontains')
    category__slug = django_filters.CharFilter(lookup_expr='exact')
    is_published = django_filters.BooleanFilter()
    is_featured = django_filters.BooleanFilter()
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    published_after = django_filters.DateTimeFilter(field_name='published_at', lookup_expr='gte')
    published_before = django_filters.DateTimeFilter(field_name='published_at', lookup_expr='lte')
    min_views = django_filters.NumberFilter(field_name='view_count', lookup_expr='gte')

    class Meta:
        from api.cms.models_new.blog import BlogPost
        model = BlogPost
        fields = ['author', 'category', 'is_published', 'is_featured']


class BlogCategoryFilter(drf_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    slug = django_filters.CharFilter(lookup_expr='icontains')
    parent = django_filters.NumberFilter()
    is_active = django_filters.BooleanFilter()

    class Meta:
        from api.cms.models_new.blog import BlogCategory
        model = BlogCategory
        fields = ['parent', 'is_active']


class BlogSEOFilter(drf_filters.FilterSet):
    meta_title = django_filters.CharFilter(lookup_expr='icontains')
    primary_keyword = django_filters.CharFilter(lookup_expr='icontains')
    min_seo_score = django_filters.NumberFilter(field_name='seo_score', lookup_expr='gte')
    has_schema = django_filters.BooleanFilter(field_name='schema_json', lookup_expr='isnull', exclude=True)

    class Meta:
        from api.cms.models_new.blog import BlogSEO
        model = BlogSEO
        fields = ['post']


# ─────────────────────────────────────────────────────────────────────────────
# SURVEY FILTERS
# ─────────────────────────────────────────────────────────────────────────────

class SurveyFilter(drf_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr='icontains')
    is_active = django_filters.BooleanFilter()
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    min_reward = django_filters.NumberFilter(field_name='reward_amount', lookup_expr='gte')
    max_reward = django_filters.NumberFilter(field_name='reward_amount', lookup_expr='lte')

    class Meta:
        from api.cms.models_new.survey import Survey
        model = Survey
        fields = ['is_active', 'created_by']


class SurveyCompletionFilter(drf_filters.FilterSet):
    user = django_filters.NumberFilter()
    survey = django_filters.NumberFilter()
    completed_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    completed_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    min_reward = django_filters.NumberFilter(field_name='reward_amount', lookup_expr='gte')

    class Meta:
        from api.cms.models_new.survey import SurveyCompletion
        model = SurveyCompletion
        fields = ['user', 'survey']


class SurveyCategoryFilter(drf_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    is_active = django_filters.BooleanFilter()

    class Meta:
        from api.cms.models_new.profile_surveys import SurveyCategory
        model = SurveyCategory
        fields = ['is_active']


# ─────────────────────────────────────────────────────────────────────────────
# LEADERBOARD FILTERS
# ─────────────────────────────────────────────────────────────────────────────

class LeaderboardEntryFilter(drf_filters.FilterSet):
    period = django_filters.NumberFilter()
    user = django_filters.NumberFilter()
    min_points = django_filters.NumberFilter(field_name='total_points', lookup_expr='gte')
    max_rank = django_filters.NumberFilter(field_name='rank_position', lookup_expr='lte')

    class Meta:
        from api.cms.models_new.leaderboard import LeaderboardEntry
        model = LeaderboardEntry
        fields = ['period', 'user']


class EarningStreakFilter(drf_filters.FilterSet):
    user = django_filters.NumberFilter()
    min_streak = django_filters.NumberFilter(field_name='current_streak', lookup_expr='gte')
    is_active = django_filters.BooleanFilter()

    class Meta:
        from api.cms.models_new.leaderboard import EarningStreak
        model = EarningStreak
        fields = ['user', 'is_active']


# ─────────────────────────────────────────────────────────────────────────────
# OFFER / CPA FILTERS
# ─────────────────────────────────────────────────────────────────────────────

class OfferFilter(drf_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr='icontains')
    is_active = django_filters.BooleanFilter()
    offer_type = django_filters.CharFilter()
    min_payout = django_filters.NumberFilter(field_name='payout_amount', lookup_expr='gte')
    max_payout = django_filters.NumberFilter(field_name='payout_amount', lookup_expr='lte')
    country = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        from api.cms.models_new.cpalead import OfferWallConfig
        model = OfferWallConfig
        fields = ['is_active']


class VirtualCurrencyFilter(drf_filters.FilterSet):
    user = django_filters.NumberFilter()
    currency_type = django_filters.CharFilter()
    min_balance = django_filters.NumberFilter(field_name='balance', lookup_expr='gte')

    class Meta:
        from api.cms.models_new.cpalead import VirtualCurrency
        model = VirtualCurrency
        fields = ['user', 'currency_type']


# ─────────────────────────────────────────────────────────────────────────────
# FINANCE FILTERS
# ─────────────────────────────────────────────────────────────────────────────

class WithdrawalRequestFilter(drf_filters.FilterSet):
    user = django_filters.NumberFilter()
    status = django_filters.CharFilter()
    payment_method = django_filters.CharFilter()
    min_amount = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    max_amount = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        from api.cms.models_new.withdrawal import WithdrawalRequest
        model = WithdrawalRequest
        fields = ['user', 'status', 'payment_method']


class PayoutMethodFilter(drf_filters.FilterSet):
    user = django_filters.NumberFilter()
    method_type = django_filters.CharFilter()
    is_verified = django_filters.BooleanFilter()
    is_default = django_filters.BooleanFilter()

    class Meta:
        from api.cms.models_new.withdrawal import PayoutMethod
        model = PayoutMethod
        fields = ['user', 'method_type', 'is_verified', 'is_default']


# ─────────────────────────────────────────────────────────────────────────────
# MEDIA FILTERS
# ─────────────────────────────────────────────────────────────────────────────

class MediaFileFilter(drf_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    file_type = django_filters.CharFilter()
    folder = django_filters.NumberFilter()
    uploaded_by = django_filters.NumberFilter()
    is_public = django_filters.BooleanFilter()
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    min_size = django_filters.NumberFilter(field_name='file_size', lookup_expr='gte')
    max_size = django_filters.NumberFilter(field_name='file_size', lookup_expr='lte')

    class Meta:
        from api.cms.models_new.media import MediaFile
        model = MediaFile
        fields = ['file_type', 'folder', 'uploaded_by', 'is_public']


# ─────────────────────────────────────────────────────────────────────────────
# POPUP FILTERS
# ─────────────────────────────────────────────────────────────────────────────

class PopupFilter(drf_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    is_active = django_filters.BooleanFilter()
    popup_type = django_filters.CharFilter()
    trigger_type = django_filters.CharFilter()
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')

    class Meta:
        from api.cms.models_new.popup import Popup
        model = Popup
        fields = ['is_active', 'popup_type', 'trigger_type']


# ─────────────────────────────────────────────────────────────────────────────
# REFERRAL FILTERS
# ─────────────────────────────────────────────────────────────────────────────

class ReferralCodeFilter(drf_filters.FilterSet):
    user = django_filters.NumberFilter()
    is_active = django_filters.BooleanFilter()
    code = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        from api.cms.models_new.referral import ReferralCode
        model = ReferralCode
        fields = ['user', 'is_active']


class ReferralEarningFilter(drf_filters.FilterSet):
    user = django_filters.NumberFilter()
    earning_type = django_filters.CharFilter()
    min_amount = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')

    class Meta:
        from api.cms.models_new.referral import ReferralEarning
        model = ReferralEarning
        fields = ['user', 'earning_type']


# ─────────────────────────────────────────────────────────────────────────────
# AB TESTING FILTERS
# ─────────────────────────────────────────────────────────────────────────────

class ABTestFilter(drf_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    status = django_filters.CharFilter()
    test_type = django_filters.CharFilter()
    is_active = django_filters.BooleanFilter()
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')

    class Meta:
        from api.cms.models_new.ab_testing import ABTest
        model = ABTest
        fields = ['status', 'test_type', 'is_active']


# ─────────────────────────────────────────────────────────────────────────────
# WORKFLOW FILTERS
# ─────────────────────────────────────────────────────────────────────────────

class WorkflowStateFilter(drf_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    workflow = django_filters.NumberFilter()
    is_initial = django_filters.BooleanFilter()
    is_final = django_filters.BooleanFilter()
    is_active = django_filters.BooleanFilter()

    class Meta:
        from api.cms.models_new.workflow import WorkflowState
        model = WorkflowState
        fields = ['workflow', 'is_initial', 'is_final', 'is_active']


# ─────────────────────────────────────────────────────────────────────────────
# SMART LINK FILTERS
# ─────────────────────────────────────────────────────────────────────────────

class SmartLinkFilter(drf_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    short_code = django_filters.CharFilter(lookup_expr='icontains')
    is_active = django_filters.BooleanFilter()
    link_type = django_filters.CharFilter()
    created_by = django_filters.NumberFilter()
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')

    class Meta:
        from api.cms.models_new.smartlink import SmartLink
        model = SmartLink
        fields = ['is_active', 'link_type', 'created_by']


# ─────────────────────────────────────────────────────────────────────────────
# VIDEO FILTERS
# ─────────────────────────────────────────────────────────────────────────────

class VideoContentFilter(drf_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr='icontains')
    is_published = django_filters.BooleanFilter()
    video_type = django_filters.CharFilter()
    created_by = django_filters.NumberFilter()
    published_after = django_filters.DateTimeFilter(field_name='published_at', lookup_expr='gte')

    class Meta:
        from api.cms.models_new.video import VideoContent
        model = VideoContent
        fields = ['is_published', 'video_type', 'created_by']


# ─────────────────────────────────────────────────────────────────────────────
# TASK MANAGEMENT FILTERS
# ─────────────────────────────────────────────────────────────────────────────

class TaskScheduleFilter(drf_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    is_active = django_filters.BooleanFilter()
    task_type = django_filters.CharFilter()
    schedule_type = django_filters.CharFilter()

    class Meta:
        from api.cms.models_new.task_management import TaskSchedule
        model = TaskSchedule
        fields = ['is_active', 'task_type', 'schedule_type']


class TaskExecutionFilter(drf_filters.FilterSet):
    schedule = django_filters.NumberFilter()
    status = django_filters.CharFilter()
    started_after = django_filters.DateTimeFilter(field_name='started_at', lookup_expr='gte')
    started_before = django_filters.DateTimeFilter(field_name='started_at', lookup_expr='lte')

    class Meta:
        from api.cms.models_new.task_management import TaskExecution
        model = TaskExecution
        fields = ['schedule', 'status']


# ─────────────────────────────────────────────────────────────────────────────
# COMMENT FILTERS
# ─────────────────────────────────────────────────────────────────────────────

class ContentCommentFilter(drf_filters.FilterSet):
    is_approved = django_filters.BooleanFilter()
    is_spam = django_filters.BooleanFilter()
    author = django_filters.NumberFilter()
    content_type = django_filters.NumberFilter()
    object_id = django_filters.NumberFilter()
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    body = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        from api.cms.models_new.comments import ContentComment
        model = ContentComment
        fields = ['is_approved', 'is_spam', 'author']


__all__ = [
    'BlogPostFilter', 'BlogCategoryFilter', 'BlogSEOFilter',
    'SurveyFilter', 'SurveyCompletionFilter', 'SurveyCategoryFilter',
    'LeaderboardEntryFilter', 'EarningStreakFilter',
    'OfferFilter', 'VirtualCurrencyFilter',
    'WithdrawalRequestFilter', 'PayoutMethodFilter',
    'MediaFileFilter', 'PopupFilter',
    'ReferralCodeFilter', 'ReferralEarningFilter',
    'ABTestFilter', 'WorkflowStateFilter',
    'SmartLinkFilter', 'VideoContentFilter',
    'TaskScheduleFilter', 'TaskExecutionFilter',
    'ContentCommentFilter',
]
