# cms/serializers_new/BlogAndSEOSerializer.py
"""
Blog and BlogSEO Serializers

Complete serializers for blog posts and SEO configuration with comprehensive validation.

Includes:
- BlogCategorySerializer
- BlogPostSerializer (list and detailed views)
- BlogCommentSerializer
- BlogSEOSerializer (with full validation)
- BlogTagSerializer
- BlogAuthorSerializer
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
import json
import logging

logger = logging.getLogger('cms.serializers.blog')


# ─────────────────────────────────────────────────────────────────────────────
# HELPER VALIDATORS
# ─────────────────────────────────────────────────────────────────────────────

def validate_meta_title_length(value):
    """Validate meta title is 30-60 characters"""
    if value and (len(value) < 30 or len(value) > 60):
        raise serializers.ValidationError(
            f"Meta title must be 30-60 characters. Current: {len(value)}"
        )


def validate_meta_description_length(value):
    """Validate meta description is 120-160 characters"""
    if value and (len(value) < 120 or len(value) > 160):
        raise serializers.ValidationError(
            f"Meta description must be 120-160 characters. Current: {len(value)}"
        )


def validate_schema_json(value):
    """Validate schema.org JSON structure"""
    if value:
        try:
            if isinstance(value, str):
                json.loads(value)
            elif isinstance(value, dict):
                # Already a dict, check for required fields
                if '@context' not in value:
                    raise serializers.ValidationError("Schema must include @context")
                if '@type' not in value:
                    raise serializers.ValidationError("Schema must include @type")
        except json.JSONDecodeError as e:
            raise serializers.ValidationError(f"Invalid JSON schema: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY SERIALIZER
# ─────────────────────────────────────────────────────────────────────────────

class BlogCategorySerializer(serializers.ModelSerializer):
    """
    Blog Category Serializer
    
    Serializes blog categories with optional post count annotation.
    """
    
    post_count = serializers.SerializerMethodField()
    
    class Meta:
        from api.cms.models_new.blog import BlogCategory
        model = BlogCategory
        fields = [
            'id', 'name', 'slug', 'description',
            'parent', 'icon', 'color',
            'is_published', 'is_active',
            'position', 'post_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'post_count']
    
    def get_post_count(self, obj):
        """Return number of published posts in category"""
        return obj.posts.filter(is_published=True).count()
    
    def validate_name(self, value):
        """Validate category name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Category name cannot be empty")
        return value.strip()
    
    def validate(self, data):
        """Cross-field validation"""
        # Check for self-referencing
        if 'parent' in data and data['parent']:
            if self.instance and data['parent'].id == self.instance.id:
                raise serializers.ValidationError("A category cannot be its own parent")
        
        return data


# ─────────────────────────────────────────────────────────────────────────────
# BLOG TAG SERIALIZER
# ─────────────────────────────────────────────────────────────────────────────

class BlogTagSerializer(serializers.ModelSerializer):
    """Blog Tag Serializer"""
    
    class Meta:
        from api.cms.models_new.blog import BlogTag
        model = BlogTag
        fields = ['id', 'name', 'slug']
        read_only_fields = ['id', 'slug']
    
    def validate_name(self, value):
        """Validate tag name"""
        if not value or len(value) < 2:
            raise serializers.ValidationError("Tag name must be at least 2 characters")
        return value


# ─────────────────────────────────────────────────────────────────────────────
# BLOG COMMENT SERIALIZER
# ─────────────────────────────────────────────────────────────────────────────

class BlogCommentSerializer(serializers.ModelSerializer):
    """
    Blog Comment Serializer
    
    Handles comment creation with optional user/guest identification.
    """
    
    author_name = serializers.SerializerMethodField()
    author_email = serializers.SerializerMethodField()
    
    class Meta:
        from api.cms.models_new.blog import BlogComment
        model = BlogComment
        fields = [
            'id', 'post', 'user', 'guest_name', 'guest_email',
            'author_name', 'author_email',
            'content', 'is_approved', 'is_spam',
            'parent', 'helpful_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'is_approved', 'is_spam', 'helpful_count',
            'created_at', 'updated_at', 'author_name', 'author_email'
        ]
    
    def get_author_name(self, obj):
        """Get author name from user or guest_name"""
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        return obj.guest_name or 'Anonymous'
    
    def get_author_email(self, obj):
        """Get author email"""
        if obj.user:
            return obj.user.email
        return obj.guest_email
    
    def validate_content(self, value):
        """Validate comment content"""
        if not value or len(value.strip()) < 5:
            raise serializers.ValidationError("Comment must be at least 5 characters")
        if len(value) > 5000:
            raise serializers.ValidationError("Comment cannot exceed 5000 characters")
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        # Must have either user or guest_name
        if not data.get('user') and not data.get('guest_name'):
            raise serializers.ValidationError(
                "Comment must have either a registered user or guest name"
            )
        
        # Guest comments need email
        if data.get('guest_name') and not data.get('guest_email'):
            raise serializers.ValidationError(
                "Guest comments must include an email address"
            )
        
        return data


# ─────────────────────────────────────────────────────────────────────────────
# BLOG POST SERIALIZERS
# ─────────────────────────────────────────────────────────────────────────────

class BlogPostListSerializer(serializers.ModelSerializer):
    """
    Blog Post List Serializer (lightweight for listings)
    
    Returns minimal fields for blog listing pages.
    """
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    author_name = serializers.CharField(
        source='author.get_full_name',
        read_only=True
    )
    comment_count = serializers.SerializerMethodField()
    
    class Meta:
        from api.cms.models_new.blog import BlogPost
        model = BlogPost
        fields = [
            'id', 'title', 'slug', 'category', 'category_name',
            'author', 'author_name', 'excerpt',
            'featured_image', 'featured_image_alt',
            'is_published', 'is_featured',
            'published_at',
            'view_count', 'like_count', 'share_count',
            'comment_count',
            'created_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'published_at',
            'view_count', 'like_count', 'share_count'
        ]
    
    def get_comment_count(self, obj):
        """Return approved comment count"""
        return obj.comments.filter(is_approved=True).count()


class BlogPostDetailSerializer(serializers.ModelSerializer):
    """
    Blog Post Detail Serializer (full details)
    
    Returns all fields for blog detail pages, including comments and SEO.
    """
    
    category = BlogCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=None,
        source='category',
        write_only=True,
        help_text="Category ID"
    )
    author = serializers.StringRelatedField(read_only=True)
    author_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='author',
        write_only=True,
        required=False,
        allow_null=True
    )
    comments = BlogCommentSerializer(many=True, read_only=True)
    tags = BlogTagSerializer(many=True, read_only=True)
    seo_config = serializers.SerializerMethodField()
    
    class Meta:
        from api.cms.models_new.blog import BlogPost
        model = BlogPost
        fields = [
            'id', 'title', 'slug', 'category', 'category_id',
            'author', 'author_id',
            'excerpt', 'content',
            'featured_image', 'featured_image_alt',
            'is_published', 'is_featured', 'is_active',
            'published_at',
            'view_count', 'like_count', 'share_count',
            'comments', 'tags',
            'seo_config',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'published_at',
            'view_count', 'like_count', 'share_count'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow category_id to query all categories
        self.fields['category_id'].queryset = self._get_category_queryset()
    
    def _get_category_queryset(self):
        """Get category queryset"""
        from api.cms.models_new.blog import BlogCategory
        return BlogCategory.objects.all()
    
    def get_seo_config(self, obj):
        """Return SEO config if exists"""
        try:
            seo = obj.seo_config
            return {
                'id': seo.id,
                'meta_title': seo.meta_title,
                'meta_description': seo.meta_description,
                'primary_keyword': seo.primary_keyword,
                'schema_type': seo.schema_type,
            }
        except:
            return None
    
    def validate_title(self, value):
        """Validate title"""
        if not value or len(value.strip()) < 5:
            raise serializers.ValidationError("Title must be at least 5 characters")
        if len(value) > 500:
            raise serializers.ValidationError("Title cannot exceed 500 characters")
        return value.strip()
    
    def validate_excerpt(self, value):
        """Validate excerpt"""
        if value and len(value) > 500:
            raise serializers.ValidationError("Excerpt cannot exceed 500 characters")
        return value
    
    def validate_content(self, value):
        """Validate content"""
        if not value or len(value.strip()) < 20:
            raise serializers.ValidationError("Content must be at least 20 characters")
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        # Published posts need published_at
        if data.get('is_published') and not self.instance:
            # New post being published
            if 'published_at' not in data:
                data['published_at'] = timezone.now()
        
        return data


class BlogPostCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Blog Post Create/Update Serializer
    
    Used for creating and updating blog posts.
    """
    
    class Meta:
        from api.cms.models_new.blog import BlogPost
        model = BlogPost
        fields = [
            'title', 'slug', 'category', 'author',
            'excerpt', 'content',
            'featured_image', 'featured_image_alt',
            'is_published', 'is_featured', 'is_active',
        ]
    
    def validate_category(self, value):
        """Validate category exists and is active"""
        if not value.is_active:
            raise serializers.ValidationError("Cannot post to inactive category")
        return value


# ─────────────────────────────────────────────────────────────────────────────
# BLOG SEO SERIALIZER
# ─────────────────────────────────────────────────────────────────────────────

class BlogSEOSerializer(serializers.ModelSerializer):
    """
    Blog SEO Serializer with comprehensive validation
    
    Validates:
    - Meta title length (30-60 chars)
    - Meta description length (120-160 chars)
    - Schema.org JSON structure
    - Keyword format
    """
    
    blog_post_title = serializers.CharField(
        source='blog_post.title',
        read_only=True
    )
    created_by_username = serializers.CharField(
        source='created_by.username',
        read_only=True,
        required=False
    )
    modified_by_username = serializers.CharField(
        source='modified_by.username',
        read_only=True,
        required=False
    )
    
    class Meta:
        from api.cms.models_new.blog import BlogSEO
        model = BlogSEO
        fields = [
            'id', 'blog_post', 'blog_post_title',
            'meta_title', 'meta_description',
            'primary_keyword', 'secondary_keywords',
            'schema_type', 'schema_json',
            'og_title', 'og_description', 'og_image',
            'is_featured', 'canonical_url',
            'created_by', 'created_by_username',
            'modified_by', 'modified_by_username',
            'created_at', 'modified_at'
        ]
        read_only_fields = [
            'id', 'created_by', 'modified_by',
            'created_at', 'modified_at',
            'created_by_username', 'modified_by_username'
        ]
    
    def validate_meta_title(self, value):
        """Validate meta title"""
        if value:
            if len(value) < 30:
                raise serializers.ValidationError(
                    f"Meta title too short ({len(value)} chars). "
                    "Aim for 30-60 characters."
                )
            if len(value) > 60:
                raise serializers.ValidationError(
                    f"Meta title too long ({len(value)} chars). "
                    "Maximum 60 characters to avoid truncation."
                )
        return value
    
    def validate_meta_description(self, value):
        """Validate meta description"""
        if value:
            if len(value) < 120:
                raise serializers.ValidationError(
                    f"Meta description too short ({len(value)} chars). "
                    "Aim for 120-160 characters."
                )
            if len(value) > 160:
                raise serializers.ValidationError(
                    f"Meta description too long ({len(value)} chars). "
                    "Maximum 160 characters."
                )
        return value
    
    def validate_schema_type(self, value):
        """Validate schema type"""
        valid_types = ['BlogPosting', 'NewsArticle', 'ScholarlyArticle', 'HowTo']
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid schema type. Must be one of: {', '.join(valid_types)}"
            )
        return value
    
    def validate_schema_json(self, value):
        """Validate schema.org JSON"""
        if value:
            validate_schema_json(value)
        return value
    
    def validate_primary_keyword(self, value):
        """Validate primary keyword"""
        if value:
            if len(value.split()) > 5:
                raise serializers.ValidationError(
                    "Primary keyword should be 1-5 words"
                )
        return value
    
    def validate_canonical_url(self, value):
        """Validate canonical URL"""
        if value:
            if not value.startswith('http'):
                raise serializers.ValidationError(
                    "Canonical URL must be a full URL starting with http/https"
                )
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        blog_post = data.get('blog_post')
        
        # Ensure blog post exists
        if blog_post:
            try:
                from api.cms.models_new.blog import BlogPost
                BlogPost.objects.get(pk=blog_post.id)
            except:
                raise serializers.ValidationError(
                    {'blog_post': 'Blog post not found'}
                )
        
        return data


class BlogSEODetailedSerializer(BlogSEOSerializer):
    """
    Blog SEO Detailed Serializer
    
    Extended version with full blog post details.
    """
    
    blog_post = BlogPostListSerializer(read_only=True)
    
    class Meta(BlogSEOSerializer.Meta):
        fields = BlogSEOSerializer.Meta.fields + ['blog_post']
        read_only_fields = BlogSEOSerializer.Meta.read_only_fields + ['blog_post']


# ─────────────────────────────────────────────────────────────────────────────
# AUTHOR SERIALIZER
# ─────────────────────────────────────────────────────────────────────────────

class BlogAuthorSerializer(serializers.ModelSerializer):
    """Blog Author Profile Serializer"""
    
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    post_count = serializers.SerializerMethodField()
    
    class Meta:
        from api.cms.models_new.blog import BlogAuthor
        model = BlogAuthor
        fields = [
            'id', 'user', 'username', 'email',
            'bio', 'avatar',
            'website', 'social_twitter', 'social_linkedin',
            'is_active', 'post_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'username', 'email',
            'created_at', 'updated_at'
        ]
    
    def get_post_count(self, obj):
        """Return number of published posts by author"""
        return obj.user.blog_posts.filter(is_published=True).count()
