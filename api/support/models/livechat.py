# api/support/models/livechat.py  — WORLD #1
"""Live chat session, message, attachment, rating, queue, transcript models."""
from django.db import models
from django.conf import settings
import uuid


class ChatSession(models.Model):
    """Live chat session between user and agent."""
    STATUS_CHOICES = [('waiting','Waiting'),('active','Active'),('ended','Ended')]
    session_id     = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    tenant         = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    user           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_sessions')
    agent          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_managed_chats')
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting', db_index=True)
    queue_position = models.IntegerField(default=0)
    started_at     = models.DateTimeField(auto_now_add=True)
    ended_at       = models.DateTimeField(null=True, blank=True)
    department     = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        app_label = 'support'
        ordering  = ['-started_at']
        db_table  = 'support_chat_session'

    def __str__(self):
        return f'Chat {str(self.session_id)[:8]} — {self.user.username}'


class ChatMessage(models.Model):
    """Message within a live chat session."""
    MSG_TYPES = [('text','Text'),('image','Image'),('file','File'),('system','System')]
    session    = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    sender     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    content    = models.TextField()
    message_type = models.CharField(max_length=20, choices=MSG_TYPES, default='text')
    is_read    = models.BooleanField(default=False)
    read_at    = models.DateTimeField(null=True, blank=True)
    is_agent   = models.BooleanField(default=False)
    is_bot     = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        ordering  = ['created_at']
        db_table  = 'support_chat_message'


class ChatAttachment(models.Model):
    """File attachment in a chat message."""
    message    = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='attachments')
    file       = models.FileField(upload_to='chat_attachments/')
    filename   = models.CharField(max_length=255)
    mime_type  = models.CharField(max_length=100, blank=True, default='')
    size_bytes = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        db_table  = 'support_chat_attachment'


class ChatRating(models.Model):
    """Rating submitted after chat ends."""
    session    = models.OneToOneField(ChatSession, on_delete=models.CASCADE, related_name='chat_rating')
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    score      = models.IntegerField(help_text='1-5')
    comment    = models.TextField(blank=True, default='')
    rated_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        db_table  = 'support_chat_rating'


class ChatQueue(models.Model):
    """Tracks users waiting in chat queue."""
    user             = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    department       = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
    joined_at        = models.DateTimeField(auto_now_add=True)
    estimated_wait_minutes = models.IntegerField(default=0)
    position         = models.IntegerField(default=0)
    session          = models.ForeignKey(ChatSession, on_delete=models.SET_NULL, null=True, blank=True)
    is_active        = models.BooleanField(default=True)

    class Meta:
        app_label = 'support'
        ordering  = ['position']
        db_table  = 'support_chat_queue'


class ChatTranscript(models.Model):
    """Generated chat transcript."""
    session      = models.OneToOneField(ChatSession, on_delete=models.CASCADE, related_name='transcript')
    content_html = models.TextField(blank=True, default='')
    content_text = models.TextField(blank=True, default='')
    generated_at = models.DateTimeField(auto_now_add=True)
    emailed_at   = models.DateTimeField(null=True, blank=True)
    email_sent_to = models.EmailField(blank=True, default='')

    class Meta:
        app_label = 'support'
        db_table  = 'support_chat_transcript'