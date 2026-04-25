# api/payment_gateways/support/models.py
# Support ticket system for publishers and advertisers

from django.db import models
from django.conf import settings
from core.models import TimeStampedModel


class SupportTicket(TimeStampedModel):
    CATEGORIES = (
        ('payment',       'Payment issue'),
        ('withdrawal',    'Withdrawal problem'),
        ('offer',         'Offer question'),
        ('tracking',      'Tracking issue'),
        ('account',       'Account problem'),
        ('technical',     'Technical support'),
        ('fraud',         'Fraud report'),
        ('other',         'Other'),
    )
    PRIORITY   = (('low','Low'),('medium','Medium'),('high','High'),('urgent','Urgent'))
    STATUS     = (('open','Open'),('in_progress','In Progress'),('resolved','Resolved'),('closed','Closed'))

    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                       related_name='support_tickets')
    ticket_number   = models.CharField(max_length=20, unique=True)
    subject         = models.CharField(max_length=300)
    category        = models.CharField(max_length=20, choices=CATEGORIES, default='other')
    priority        = models.CharField(max_length=10, choices=PRIORITY, default='medium')
    status          = models.CharField(max_length=15, choices=STATUS, default='open')
    description     = models.TextField()
    assigned_to     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, blank=True, related_name='assigned_tickets')
    resolved_at     = models.DateTimeField(null=True, blank=True)
    related_txn_ref = models.CharField(max_length=100, blank=True)
    attachment_url  = models.URLField(max_length=500, blank=True)

    class Meta:
        verbose_name = 'Support Ticket'
        ordering     = ['-created_at']
        indexes      = [models.Index(fields=['status', 'priority'])]

    def __str__(self):
        return f'[{self.ticket_number}] {self.subject} [{self.status}]'

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            import time
            self.ticket_number = f'TKT-{int(time.time()*1000) % 10000000}'
        super().save(*args, **kwargs)


class TicketMessage(TimeStampedModel):
    ticket      = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message     = models.TextField()
    is_staff    = models.BooleanField(default=False)
    attachment_url = models.URLField(max_length=500, blank=True)

    class Meta:
        verbose_name = 'Ticket Message'
        ordering     = ['created_at']

    def __str__(self):
        return f'Message on {self.ticket.ticket_number}'
