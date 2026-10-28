"""
api/support/models/audit.py
TicketAuditLog, restored from the shadowed legacy api/support/models.py
"""
from django.db import models
from django.conf import settings


class TicketAuditLog(models.Model):
    ticket     = models.ForeignKey('support.SupportTicket', on_delete=models.CASCADE, related_name='audit_logs')
    actor      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action     = models.CharField(max_length=100)
    field      = models.CharField(max_length=100, blank=True, default='')
    old_value  = models.TextField(blank=True, default='')
    new_value  = models.TextField(blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'support_ticket_audit_log'
