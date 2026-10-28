# api/admin_panel/models/activity.py
"""
Activity tracking models:
  - AdminActivity  — every admin action log
  - AdminSession   — admin login session tracking
  - AdminNote      — internal notes on any object
  - AdminBookmark  — admin URL bookmarks
  - AdminSearch    — search query history
"""
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class AdminActivity(models.Model):
    """
    Detailed log of every admin action.
    Auto-populated by AdminActivityMiddleware.
    """
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('partial', 'Partial'),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='admin_activities',
        verbose_name=_('Actor'),
    )
    action = models.CharField(
        max_length=100, db_index=True,
        verbose_name=_('Action'),
        help_text=_('e.g. create, update, delete, bulk_action, toggle, login'),
    )
    model_name = models.CharField(
        max_length=100, blank=True, db_index=True,
        verbose_name=_('Model Name'),
    )
    object_id = models.CharField(
        max_length=100, blank=True, db_index=True,
        verbose_name=_('Object ID'),
    )
    object_repr = models.CharField(
        max_length=200, blank=True,
        verbose_name=_('Object Representation'),
        help_text=_('str() of the affected object at time of action'),
    )
    changes = models.JSONField(
        default=dict, blank=True,
        verbose_name=_('Changes'),
        help_text=_('Field-level diff: {field: {old, new}}'),
    )
    ip = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name=_('IP Address'),
    )
    user_agent = models.CharField(
        max_length=500, blank=True,
        verbose_name=_('User Agent'),
    )
    path = models.CharField(
        max_length=500, blank=True,
        verbose_name=_('Request Path'),
    )
    method = models.CharField(
        max_length=10, blank=True,
        verbose_name=_('HTTP Method'),
    )
    response_code = models.IntegerField(
        null=True, blank=True,
        verbose_name=_('HTTP Response Code'),
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='success',
        verbose_name=_('Status'),
    )
    extra = models.JSONField(
        default=dict, blank=True,
        verbose_name=_('Extra Data'),
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Admin Activity')
        verbose_name_plural = _('Admin Activities')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['actor', 'created_at']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['action', 'status']),
        ]

    def __str__(self):
        actor = self.actor.username if self.actor else 'Anonymous'
        return f"{actor} — {self.action} on {self.model_name} [{self.status}] @ {self.created_at:%Y-%m-%d %H:%M}"

    @classmethod
    def log(
        cls,
        actor,
        action: str,
        model_name: str = '',
        object_id: str = '',
        object_repr: str = '',
        changes: dict = None,
        ip: str = '',
        user_agent: str = '',
        path: str = '',
        method: str = '',
        response_code: int = None,
        status: str = 'success',
        extra: dict = None,
    ):
        """
        Convenience class method to log an admin activity.
        Usage:
            AdminActivity.log(
                actor=request.user,
                action='approve_withdrawal',
                model_name='Withdrawal',
                object_id=str(withdrawal.pk),
            )
        """
        try:
            return cls.objects.create(
                actor=actor,
                action=action,
                model_name=model_name,
                object_id=str(object_id) if object_id else '',
                object_repr=object_repr[:200] if object_repr else '',
                changes=changes or {},
                ip=ip or '',
                user_agent=user_agent[:500] if user_agent else '',
                path=path[:500] if path else '',
                method=method,
                response_code=response_code,
                status=status,
                extra=extra or {},
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"AdminActivity.log error: {e}")
            return None


class AdminSession(models.Model):
    """
    Tracks active admin sessions.
    Created/updated by AdminSessionMiddleware.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('logged_out', 'Logged Out'),
        ('force_logout', 'Force Logged Out'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_sessions',
        verbose_name=_('User'),
    )
    session_key = models.CharField(
        max_length=40, db_index=True,
        verbose_name=_('Session Key'),
    )
    ip = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name=_('IP Address'),
    )
    user_agent = models.CharField(
        max_length=500, blank=True,
        verbose_name=_('User Agent'),
    )
    location = models.CharField(
        max_length=200, blank=True,
        verbose_name=_('Location'),
        help_text=_('Geo-location from IP (city, country)'),
    )
    started_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Started At'),
    )
    last_seen = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Last Seen'),
    )
    ended_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_('Ended At'),
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Is Active'))
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name=_('Status'),
    )
    force_logout_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='force_logouts_issued',
        verbose_name=_('Force Logout By'),
    )
    force_logout_reason = models.CharField(
        max_length=200, blank=True,
        verbose_name=_('Force Logout Reason'),
    )

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Admin Session')
        verbose_name_plural = _('Admin Sessions')
        ordering = ['-started_at']
        unique_together = [('user', 'session_key')]
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['last_seen']),
        ]

    def __str__(self):
        status = 'active' if self.is_active else 'ended'
        return f"{self.user.username} — {self.ip} ({status}) from {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def duration_seconds(self) -> int:
        """Session duration in seconds."""
        end = self.ended_at or timezone.now()
        return int((end - self.started_at).total_seconds())

    def force_logout(self, by_user, reason: str = ''):
        """Force logout this session."""
        from django.contrib.sessions.models import Session
        self.is_active = False
        self.status = 'force_logout'
        self.ended_at = timezone.now()
        self.force_logout_by = by_user
        self.force_logout_reason = reason
        self.save()
        # Also delete Django session
        try:
            Session.objects.filter(session_key=self.session_key).delete()
        except Exception:
            pass


class AdminNote(models.Model):
    """
    Internal admin notes attached to any model object via GenericFK.
    E.g. notes on a User, Withdrawal, Report, etc.
    """
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True, blank=True,
        verbose_name=_('Content Type'),
    )
    object_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name=_('Object ID'),
    )
    content_object = GenericForeignKey('content_type', 'object_id')

    note = models.TextField(verbose_name=_('Note'))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='admin_notes',
        verbose_name=_('Created By'),
    )
    is_pinned = models.BooleanField(
        default=False,
        verbose_name=_('Pinned'),
        help_text=_('Pinned notes appear at the top'),
    )
    is_private = models.BooleanField(
        default=False,
        verbose_name=_('Private'),
        help_text=_('Private notes are only visible to the author'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Admin Note')
        verbose_name_plural = _('Admin Notes')
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        author = self.created_by.username if self.created_by else 'N/A'
        return f"Note by {author} on {self.content_type} #{self.object_id}"


class AdminBookmark(models.Model):
    """
    Admin URL bookmarks (saved links for quick access).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_bookmarks',
        verbose_name=_('User'),
    )
    url = models.CharField(max_length=500, verbose_name=_('URL'))
    title = models.CharField(max_length=200, verbose_name=_('Title'))
    icon = models.CharField(max_length=50, blank=True, verbose_name=_('Icon'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    sort_order = models.IntegerField(default=0, verbose_name=_('Sort Order'))
    is_active = models.BooleanField(default=True, verbose_name=_('Is Active'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Admin Bookmark')
        verbose_name_plural = _('Admin Bookmarks')
        ordering = ['user', 'sort_order', 'title']
        unique_together = [('user', 'url')]

    def __str__(self):
        return f"{self.user.username}: {self.title}"


class AdminSearch(models.Model):
    """
    Tracks global search queries made by admin users.
    Used for search analytics and suggestions.
    """
    query = models.CharField(max_length=500, verbose_name=_('Query'))
    model = models.CharField(
        max_length=100, blank=True,
        verbose_name=_('Model Filter'),
        help_text=_('Model scope if user filtered by model'),
    )
    result_count = models.IntegerField(
        default=0,
        verbose_name=_('Result Count'),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='admin_searches',
        verbose_name=_('User'),
    )
    ip = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name=_('IP Address'),
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Admin Search')
        verbose_name_plural = _('Admin Searches')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['query', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        user = self.user.username if self.user else 'Anonymous'
        return f"{user}: '{self.query}' ({self.result_count} results)"