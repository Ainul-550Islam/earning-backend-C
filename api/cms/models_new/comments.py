# api/cms/models_new/comments.py
"""Comment / Discussion system — threaded comments on blog posts and content."""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class ContentComment(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('spam',     'Spam'),
    ]
    uuid        = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    # Parent content
    content_type = models.CharField(max_length=30, db_index=True,
                                     help_text="blog_post, page, quiz, etc.")
    object_id    = models.PositiveIntegerField(db_index=True)
    # Threading
    parent      = models.ForeignKey('self', on_delete=models.CASCADE,
                                    null=True, blank=True, related_name='replies')
    depth       = models.PositiveSmallIntegerField(default=0)
    # Author
    user        = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='comments')
    author_name  = models.CharField(max_length=100, blank=True)
    author_email = models.EmailField(blank=True)
    # Content
    body        = models.TextField(max_length=2000)
    status      = models.CharField(max_length=15, choices=STATUS_CHOICES,
                                   default='approved', db_index=True)
    # Reactions
    likes       = models.PositiveIntegerField(default=0)
    dislikes    = models.PositiveIntegerField(default=0)
    is_pinned   = models.BooleanField(default=False)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Comment"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id', 'status']),
            models.Index(fields=['parent', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        author = self.user.username if self.user else self.author_name or 'Anonymous'
        return f"Comment by {author} on {self.content_type}#{self.object_id}"

    @property
    def author_display(self):
        if self.user:
            return self.user.username
        return self.author_name or 'Anonymous'

    @property
    def is_reply(self):
        return self.parent_id is not None

    def get_replies(self):
        return ContentComment.objects.filter(parent=self, status='approved').order_by('created_at')


class CommentReaction(models.Model):
    """User reactions on comments (like/dislike)."""
    REACTION_TYPES = [('like', 'Like'), ('dislike', 'Dislike')]
    comment  = models.ForeignKey(ContentComment, on_delete=models.CASCADE, related_name='reactions')
    user     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reaction = models.CharField(max_length=10, choices=REACTION_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "cms"
        unique_together = [['comment', 'user']]
        verbose_name = "Comment Reaction"

    def __str__(self):
        return f"{self.user.username} {self.reaction}d comment #{self.comment_id}"


# Backward-compat alias — use ContentComment in new code
Comment = ContentComment
