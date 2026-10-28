# api/cms/serializers_new/ContentAndFormSerializer.py
"""
Serializers for DynamicForm, Block, Comment, and Payout models
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models_new.forms import DynamicForm, FormField, FormSubmission
from ..models_new.blocks import BlockDefinition, ContentBlock
from ..models_new.comments import CommentReaction  # Comment renamed to ContentComment
from ..models_new.withdrawal import PayoutMethod

User = get_user_model()


# ── Forms ─────────────────────────────────────────────────────────────────────

class FormFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormField
        fields = [
            'id', 'form', 'label', 'field_type', 'name', 'placeholder',
            'help_text', 'default_value', 'choices', 'is_required', 'order',
        ]
        read_only_fields = ['id']

    def validate_name(self, value):
        import re
        if not re.match(r'^[a-z][a-z0-9_]*$', value):
            raise serializers.ValidationError(
                "Field name must start with a letter and contain only lowercase letters, numbers, and underscores."
            )
        return value


class FormSubmissionSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = FormSubmission
        fields = [
            'uuid', 'form', 'user', 'user_display', 'session_key',
            'data', 'ip_address', 'user_agent', 'reward_given',
        ]
        read_only_fields = ['uuid', 'reward_given']
        extra_kwargs = {'ip_address': {'write_only': True}, 'user_agent': {'write_only': True}}


class DynamicFormSerializer(serializers.ModelSerializer):
    fields_list = FormFieldSerializer(many=True, read_only=True, source='fields')

    class Meta:
        model = DynamicForm
        fields = [
            'uuid', 'name', 'slug', 'description', 'title',
            'submit_text', 'success_message', 'redirect_url', 'fields_list',
        ]
        read_only_fields = ['uuid']


# ── Blocks ────────────────────────────────────────────────────────────────────

class BlockDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlockDefinition
        fields = ['id', 'block_type', 'label', 'icon', 'schema', 'is_active', 'order']
        read_only_fields = ['id']


class ContentBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentBlock
        fields = [
            'uuid', 'parent_type', 'parent_id', 'block_type',
            'order', 'data', 'css_class', 'is_visible',
        ]
        read_only_fields = ['uuid']


# ── Comment Reaction ──────────────────────────────────────────────────────────

class CommentReactionSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = CommentReaction
        fields = ['id', 'comment', 'user', 'user_display', 'reaction', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_reaction(self, value):
        valid = ['like', 'love', 'haha', 'wow', 'sad', 'angry']
        if value not in valid:
            raise serializers.ValidationError(f"reaction must be one of: {', '.join(valid)}")
        return value


# ── Payout Method ─────────────────────────────────────────────────────────────

class PayoutMethodSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = PayoutMethod
        fields = [
            'id', 'user', 'user_display', 'method', 'account_id',
            'account_name', 'is_default', 'is_verified', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'is_verified', 'created_at', 'updated_at']
        extra_kwargs = {'account_id': {'write_only': True}}


# ─────────────────────────────────────────────────────────────────────────────
# PART 7 ADDITIONS — missing serializers for new ViewSets
# ─────────────────────────────────────────────────────────────────────────────

from rest_framework import serializers as _s


class ContentCommentSerializer(_s.ModelSerializer):
    author_display = _s.StringRelatedField(source='author', read_only=True)

    class Meta:
        from api.cms.models_new.comments import ContentComment
        model = ContentComment
        fields = [
            'id', 'author', 'author_display', 'content_type', 'object_id',
            'body', 'parent', 'is_approved', 'is_spam',
            'approved_at', 'created_at',
        ]
        read_only_fields = ['id', 'approved_at', 'created_at']


class AnnouncementSerializer(_s.ModelSerializer):
    class Meta:
        from api.cms.models_new.extras import Announcement
        model = Announcement
        fields = [
            'id', 'title', 'content', 'announcement_type', 'target_audience',
            'is_active', 'priority', 'start_date', 'end_date', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class NotificationTemplateSerializer(_s.ModelSerializer):
    class Meta:
        from api.cms.models_new.extras import NotificationTemplate
        model = NotificationTemplate
        fields = [
            'id', 'name', 'template_type', 'channel', 'subject',
            'body', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TestimonialSerializer(_s.ModelSerializer):
    class Meta:
        from api.cms.models_new.extras import Testimonial
        model = Testimonial
        fields = [
            'id', 'author_name', 'company', 'content', 'rating',
            'avatar', 'is_featured', 'is_approved', 'display_order', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class SocialLinkSerializer(_s.ModelSerializer):
    class Meta:
        from api.cms.models_new.extras import SocialLink
        model = SocialLink
        fields = ['id', 'platform', 'url', 'icon', 'is_active', 'display_order']
        read_only_fields = ['id']


class UserContentInteractionSerializer(_s.ModelSerializer):
    user_display = _s.StringRelatedField(source='user', read_only=True)

    class Meta:
        from api.cms.models_new.extras import UserContentInteraction
        model = UserContentInteraction
        fields = [
            'id', 'user', 'user_display', 'interaction_type',
            'content_type', 'object_id', 'created_at',
        ]
        read_only_fields = ['id', 'user', 'created_at']


class LandingPageSerializer(_s.ModelSerializer):
    created_by_display = _s.StringRelatedField(source='created_by', read_only=True)

    class Meta:
        from api.cms.models_new.landing_pages import LandingPage
        model = LandingPage
        fields = [
            'id', 'title', 'slug', 'template_type', 'content', 'meta_description',
            'is_published', 'published_at', 'created_by', 'created_by_display',
            'view_count', 'conversion_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'published_at', 'view_count', 'conversion_count', 'created_at', 'updated_at']


class MediaFolderSerializer(_s.ModelSerializer):
    created_by_display = _s.StringRelatedField(source='created_by', read_only=True)

    class Meta:
        from api.cms.models_new.media import MediaFolder
        model = MediaFolder
        fields = ['id', 'name', 'parent', 'description', 'is_public', 'created_by', 'created_by_display', 'created_at']
        read_only_fields = ['id', 'created_at']


class MediaTagSerializer(_s.ModelSerializer):
    class Meta:
        from api.cms.models_new.media import MediaTag
        model = MediaTag
        fields = ['id', 'name', 'slug']
        read_only_fields = ['id']


class MediaFileSerializer(_s.ModelSerializer):
    uploaded_by_display = _s.StringRelatedField(source='uploaded_by', read_only=True)

    class Meta:
        from api.cms.models_new.media import MediaFile
        model = MediaFile
        fields = [
            'id', 'name', 'file', 'file_type', 'file_size', 'mime_type',
            'folder', 'alt_text', 'description', 'is_public',
            'uploaded_by', 'uploaded_by_display', 'created_at',
        ]
        read_only_fields = ['id', 'file_size', 'mime_type', 'uploaded_by', 'created_at']


class MediaVariantSerializer(_s.ModelSerializer):
    class Meta:
        from api.cms.models_new.media import MediaVariant
        model = MediaVariant
        fields = ['id', 'media_file', 'variant_type', 'format', 'width', 'height', 'file_size', 'url', 'created_at']
        read_only_fields = ['id', 'created_at']


class PopupSerializer(_s.ModelSerializer):
    created_by_display = _s.StringRelatedField(source='created_by', read_only=True)

    class Meta:
        from api.cms.models_new.popup import Popup
        model = Popup
        fields = [
            'id', 'name', 'title', 'content', 'popup_type', 'trigger_type',
            'is_active', 'priority', 'display_count', 'published_at',
            'created_by', 'created_by_display', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'display_count', 'published_at', 'created_at', 'updated_at']


class PopupRuleSerializer(_s.ModelSerializer):
    class Meta:
        from api.cms.models_new.popup import PopupRule
        model = PopupRule
        fields = ['id', 'popup', 'rule_type', 'rule_value', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class PopupStatSerializer(_s.ModelSerializer):
    class Meta:
        from api.cms.models_new.popup import PopupStat
        model = PopupStat
        fields = ['id', 'popup', 'date', 'impressions', 'clicks', 'conversions']
        read_only_fields = ['id']


class VideoContentSerializer(_s.ModelSerializer):
    created_by_display = _s.StringRelatedField(source='created_by', read_only=True)

    class Meta:
        from api.cms.models_new.video import VideoContent
        model = VideoContent
        fields = [
            'id', 'title', 'description', 'video_type', 'video_url', 'thumbnail',
            'duration_seconds', 'is_published', 'published_at', 'view_count',
            'created_by', 'created_by_display', 'created_at',
        ]
        read_only_fields = ['id', 'view_count', 'published_at', 'created_at']


class VideoGenerationRequestSerializer(_s.ModelSerializer):
    requested_by_display = _s.StringRelatedField(source='requested_by', read_only=True)

    class Meta:
        from api.cms.models_new.video import VideoGenerationRequest
        model = VideoGenerationRequest
        fields = [
            'id', 'requested_by', 'requested_by_display', 'prompt',
            'duration_seconds', 'status', 'progress', 'result_url',
            'error_message', 'created_at', 'completed_at',
        ]
        read_only_fields = ['id', 'requested_by', 'status', 'progress', 'result_url', 'created_at', 'completed_at']
