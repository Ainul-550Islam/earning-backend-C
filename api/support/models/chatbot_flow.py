"""
api/support/models/chatbot_flow.py
FILE 62/70 — Chatbot Flow Models
"""
from django.db import models
from django.conf import settings

class ChatbotFlow(models.Model):
    """Visual chatbot flow definition"""
    flow_id     = models.CharField(max_length=32, unique=True, db_index=True)
    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    nodes       = models.JSONField(default=list)
    edges       = models.JSONField(default=list)
    settings    = models.JSONField(default=dict)
    is_active   = models.BooleanField(default=False, db_index=True)
    is_default  = models.BooleanField(default=False)
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                     null=True, related_name='chatbot_flows')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'support'
        db_table  = 'support_chatbot_flow'

    def __str__(self):
        return f'{self.name} ({"active" if self.is_active else "inactive"})'

class BotConversation(models.Model):
    """Bot conversation session state"""
    SESSION_STATES = [('active','Active'),('handed_off','Handed Off'),('ended','Ended')]
    session_id    = models.CharField(max_length=64, unique=True, db_index=True)
    flow          = models.ForeignKey(ChatbotFlow, null=True, on_delete=models.SET_NULL)
    user          = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                       on_delete=models.SET_NULL, related_name='bot_conversations')
    current_node  = models.CharField(max_length=50, default='start')
    variables     = models.JSONField(default=dict)
    message_count = models.IntegerField(default=0)
    state         = models.CharField(max_length=20, choices=SESSION_STATES, default='active')
    ticket        = models.ForeignKey('SupportTicket', null=True, blank=True,
                       on_delete=models.SET_NULL, related_name='bot_conversations')
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'support'
        db_table  = 'support_bot_conversation'