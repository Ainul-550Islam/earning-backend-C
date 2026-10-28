# cms/models_new/blog.py
"""
Blog Models — Complete CMS Blog Management System

Models:
- BlogCategory: Blog post categories with hierarchy
- BlogPost: Individual blog posts with content, metadata
- BlogComment: Comments on blog posts with moderation
- BlogSEO: SEO metadata for blog posts (meta tags, schema)
- BlogAuthor: Author information and statistics
- BlogTag: Tags for organizing blog posts
- BlogPostTag: Many-to-many relationship between posts and tags

This module includes:
- Complete field definitions with validation
- Custom managers with frequently used querysets
- Model validators for business rules
- Signal-compatible save/delete methods
- Comprehensive indexing for performance
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator, URLValidator
from django.utils.text import slugify
from django.utils import timezone

User = get_user_model()
from django.core.exceptions import ValidationError
import json
import logging

logger = logging.getLogger('cms.models.blog')


class BlogCategoryQuerySet(models.QuerySet):
    """Custom QuerySet for BlogCategory"""
    
    def published(self):
        """Only published categories"""
        return self.filter(is_published=True)
    
    def active(self):
        """Only active categories"""
        return self.filter(is_active=True)
    
    def with_post_count(self):
        """Annotate with post count"""
        return self.annotate(
            post_count=models.Count('blogpost', filter=models.Q(blogpost__is_published=True))
        )
    
    def ordered_by_posts(self):
        """Order by number of posts"""
        return self.with_post_count().order_by('-post_count')


class BlogCategoryManager(models.Manager):
    """Custom manager for BlogCategory"""
    
    def get_queryset(self):
        return BlogCategoryQuerySet(self.model, using=self._db)
    
    def published(self):
        return self.get_queryset().published()
    
    def active(self):
        return self.get_queryset().active()
    
    def with_post_count(self):
        return self.get_queryset().with_post_count()


class BlogCategory(models.Model):
    """
    Blog Post Categories
    
    Organizes blog posts into categories with optional hierarchy.
    Supports nested categories via parent field.
    """
    
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Category name (e.g., 'Technology', 'Reviews')"
    )
    slug = models.SlugField(
        unique=True,
        help_text="URL-friendly slug"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Category description for listing pages"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text="Parent category for hierarchy (optional)"
    )
    icon = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Font Awesome icon class (e.g., 'fa-laptop')"
    )
    color = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        help_text="Hex color code for category (e.g., '#FF5733')"
    )
    is_published = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Published categories appear in listings"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Inactive categories are hidden"
    )
    position = models.PositiveIntegerField(
        default=0,
        help_text="Display order in listings"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    objects = BlogCategoryManager()
    
    class Meta:
        app_label = 'cms'
        db_table = 'cms_blog_category'
        verbose_name = 'Blog Category'
        verbose_name_plural = 'Blog Categories'
        ordering = ['position', 'name']
        indexes = [
            models.Index(fields=['is_published', 'is_active']),
            models.Index(fields=['position', '-created_at']),
            models.Index(fields=['parent', 'position']),
        ]
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """Validate category"""
        if self.parent == self:
            raise ValidationError("A category cannot be its own parent")
    
    def save(self, *args, **kwargs):
        """
        Save category with slug generation
        
        - Auto-generate slug from name if not provided
        - Ensure slug is unique
        """
        if not self.slug:
            self.slug = slugify(self.name)
        
        # Ensure unique slug
        base_slug = self.slug
        counter = 1
        while BlogCategory.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
            self.slug = f"{base_slug}-{counter}"
            counter += 1
        
        self.full_clean()
        super().save(*args, **kwargs)


class BlogPostQuerySet(models.QuerySet):
    """Custom QuerySet for BlogPost"""
    
    def published(self):
        """Only published posts"""
        return self.filter(is_published=True)
    
    def active(self):
        """Only active posts"""
        return self.filter(is_active=True)
    
    def by_author(self, author):
        """Posts by specific author"""
        return self.filter(author=author)
    
    def by_category(self, category):
        """Posts in specific category"""
        return self.filter(category=category)
    
    def recent(self, days=30):
        """Posts from last N days"""
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)
    
    def with_comments(self):
        """Only posts with comments"""
        return self.annotate(
            comment_count=models.Count('comments')
        ).filter(comment_count__gt=0)
    
    def popular(self, min_views=100):
        """Posts with minimum view count"""
        return self.filter(view_count__gte=min_views)
    
    def featured(self):
        """Featured posts"""
        return self.filter(is_featured=True)


class BlogPostManager(models.Manager):
    """Custom manager for BlogPost"""
    
    def get_queryset(self):
        return BlogPostQuerySet(self.model, using=self._db)
    
    def published(self):
        return self.get_queryset().published()
    
    def active(self):
        return self.get_queryset().active()
    
    def recent(self, days=30):
        return self.get_queryset().recent(days)
    
    def featured(self):
        return self.get_queryset().featured()


class BlogPost(models.Model):
    """
    Blog Posts — Individual Articles
    
    Core blog post model with rich content, metadata, and engagement tracking.
    """
    
    title = models.CharField(
        max_length=500,
        help_text="Blog post title"
    )
    slug = models.SlugField(
        max_length=500,
        help_text="URL-friendly slug"
    )
    category = models.ForeignKey(
        BlogCategory,
        on_delete=models.PROTECT,
        related_name='posts',
        help_text="Blog post category"
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blog_posts',
        help_text="Post author"
    )
    excerpt = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Short excerpt for listings (max 500 chars)"
    )
    content = models.TextField(
        help_text="Blog post main content (HTML supported)"
    )
    featured_image = models.ImageField(
        upload_to='blog/featured/',
        null=True,
        blank=True,
        help_text="Featured image for post"
    )
    featured_image_alt = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Alt text for featured image (SEO)"
    )
    
    # Publishing
    is_published = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Published posts are visible to public"
    )
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Featured posts appear in homepage"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Inactive posts are hidden"
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When post was published"
    )
    
    # Engagement
    view_count = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text="Number of views"
    )
    like_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of likes"
    )
    share_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of shares"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    objects = BlogPostManager()
    
    class Meta:
        app_label = 'cms'
        db_table = 'cms_blog_post'
        verbose_name = 'Blog Post'
        verbose_name_plural = 'Blog Posts'
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['slug', 'category']),
            models.Index(fields=['is_published', '-published_at']),
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['is_featured', '-published_at']),
            models.Index(fields=['-view_count']),
        ]
        unique_together = [
            ('slug', 'category'),  # Slug unique per category
        ]
    
    def __str__(self):
        return self.title
    
    def clean(self):
        """Validate blog post"""
        if self.is_published and not self.published_at:
            raise ValidationError("Published posts must have a published_at date")
    
    def save(self, *args, **kwargs):
        """
        Save blog post with slug generation and publishing logic
        
        - Auto-generate slug from title if not provided
        - Set published_at when publishing
        - Ensure slug is unique per category
        """
        if not self.slug:
            self.slug = slugify(self.title)
        
        # Ensure unique slug per category
        base_slug = self.slug
        counter = 1
        while BlogPost.objects.filter(
            slug=self.slug,
            category=self.category
        ).exclude(pk=self.pk).exists():
            self.slug = f"{base_slug}-{counter}"
            counter += 1
        
        # Auto-set published_at
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        elif not self.is_published:
            self.published_at = None
        
        # Validate before saving
        self.full_clean()
        super().save(*args, **kwargs)
    
    def increment_views(self):
        """Increment view count"""
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def increment_likes(self):
        """Increment like count"""
        self.like_count += 1
        self.save(update_fields=['like_count'])
    
    def increment_shares(self):
        """Increment share count"""
        self.share_count += 1
        self.save(update_fields=['share_count'])


class BlogComment(models.Model):
    """
    Blog Post Comments
    
    Comments on blog posts with moderation support.
    """
    
    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name='cms_blog_comments',
        help_text="Post being commented on"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blog_comments',
        help_text="Comment author"
    )
    guest_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Name if comment by guest (non-registered user)"
    )
    guest_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email if comment by guest"
    )
    content = models.TextField(
        help_text="Comment text"
    )
    
    # Moderation
    is_approved = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Approved comments appear on site"
    )
    is_spam = models.BooleanField(
        default=False,
        help_text="Mark as spam"
    )
    
    # Parent comment (for nested comments)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        help_text="Parent comment (for nested comments)"
    )
    
    # Engagement
    helpful_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of 'helpful' votes"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        app_label = 'cms'
        db_table = 'cms_blog_comment'
        verbose_name = 'Blog Comment'
        verbose_name_plural = 'Blog Comments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['post', 'is_approved']),
            models.Index(fields=['is_spam']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        author = self.user or self.guest_name or 'Anonymous'
        return f"Comment by {author} on {self.post.title}"
    
    def clean(self):
        """Validate comment"""
        if self.user and (self.guest_name or self.guest_email):
            raise ValidationError("Use either registered user or guest name, not both")


class BlogSEO(models.Model):
    """
    Blog Post SEO Configuration
    
    Stores SEO metadata: meta tags, schema.org data, keywords, etc.
    One-to-one relationship with BlogPost.
    """
    
    blog_post = models.OneToOneField(
        BlogPost,
        on_delete=models.CASCADE,
        related_name='cms_blog_seo_config',
        help_text="Blog post"
    )
    
    # Meta Tags
    meta_title = models.CharField(
        max_length=60,
        blank=True,
        null=True,
        help_text="Meta title for search engines (30-60 chars recommended)"
    )
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        null=True,
        help_text="Meta description for search engines (120-160 chars)"
    )
    
    # Keywords
    primary_keyword = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Primary SEO keyword/phrase"
    )
    secondary_keywords = models.TextField(
        blank=True,
        null=True,
        help_text="Secondary keywords (comma-separated)"
    )
    
    # Schema.org
    schema_type = models.CharField(
        max_length=50,
        default='BlogPosting',
        choices=[
            ('BlogPosting', 'Blog Post'),
            ('NewsArticle', 'News Article'),
            ('ScholarlyArticle', 'Scholarly Article'),
            ('HowTo', 'How-To Guide'),
        ],
        help_text="Type of schema.org data"
    )
    schema_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Full schema.org JSON-LD data"
    )
    
    # Open Graph
    og_title = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="OG title for social sharing"
    )
    og_description = models.CharField(
        max_length=160,
        blank=True,
        null=True,
        help_text="OG description for social sharing"
    )
    og_image = models.URLField(
        blank=True,
        null=True,
        help_text="OG image URL for social sharing"
    )
    
    # Other
    is_featured = models.BooleanField(
        default=False,
        help_text="Featured in SEO recommendations"
    )
    canonical_url = models.URLField(
        blank=True,
        null=True,
        help_text="Canonical URL if different from post URL"
    )
    
    # Tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_blog_seos',
        help_text="User who created SEO config"
    )
    modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_blog_seos',
        help_text="User who last modified SEO config"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    modified_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        app_label = 'cms'
        db_table = 'cms_blog_seo'
        verbose_name = 'Blog SEO'
        verbose_name_plural = 'Blog SEOs'
        ordering = ['-modified_at']
    
    def __str__(self):
        return f"SEO: {self.blog_post.title}"


class BlogTag(models.Model):
    """
    Blog Tags
    
    Tags for organizing and categorizing blog posts.
    """
    
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Tag name"
    )
    slug = models.SlugField(
        unique=True,
        help_text="URL-friendly slug"
    )
    
    class Meta:
        app_label = 'cms'
        db_table = 'cms_blog_tag'
        verbose_name = 'Blog Tag'
        verbose_name_plural = 'Blog Tags'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Auto-generate slug"""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class BlogPostTag(models.Model):
    """
    Many-to-Many relationship between BlogPost and BlogTag
    """
    
    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name='tags'
    )
    tag = models.ForeignKey(
        BlogTag,
        on_delete=models.CASCADE,
        related_name='posts'
    )
    
    class Meta:
        app_label = 'cms'
        db_table = 'cms_blog_post_tag'
        unique_together = [('post', 'tag')]
        verbose_name = 'Blog Post Tag'
        verbose_name_plural = 'Blog Post Tags'
    
    def __str__(self):
        return f"{self.post.title} - {self.tag.name}"


class BlogAuthor(models.Model):
    """
    Blog Author Profile
    
    Extended information about blog post authors.
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='blog_author_profile',
        help_text="Django user"
    )
    bio = models.TextField(
        blank=True,
        null=True,
        help_text="Author biography"
    )
    avatar = models.ImageField(
        upload_to='blog/authors/',
        null=True,
        blank=True,
        help_text="Author profile picture"
    )
    website = models.URLField(
        blank=True,
        null=True,
        help_text="Author's personal website"
    )
    social_twitter = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Twitter handle"
    )
    social_linkedin = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="LinkedIn profile"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Active authors can publish posts"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        app_label = 'cms'
        db_table = 'cms_blog_author'
        verbose_name = 'Blog Author'
        verbose_name_plural = 'Blog Authors'
    
    def __str__(self):
        return self.user.get_full_name() or self.user.username
