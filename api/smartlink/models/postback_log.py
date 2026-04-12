"""
PostbackLog Model
Audit trail for every S2S postback received.
Used for dispute resolution and conversion verification.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class PostbackLog(models.Model):
    """
    Full audit log of every S2S postback received.
    Immutable — records are never updated, only created.
    """
    click_id       = models.CharField(max_length=50, blank=True, db_index=True)
    offer_id       = models.CharField(max_length=20, blank=True, db_index=True)
    event          = models.CharField(max_length=20, default='lead', db_index=True)
    payout         = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    currency       = models.CharField(max_length=3, default='USD')
    transaction_id = models.CharField(max_length=255, blank=True, db_index=True)
    sub1           = models.CharField(max_length=255, blank=True)
    adv_sub1       = models.CharField(max_length=255, blank=True)
    ip             = models.GenericIPAddressField(blank=True, null=True)
    is_duplicate   = models.BooleanField(default=False)
    is_attributed  = models.BooleanField(default=False)
    raw_params     = models.JSONField(default=dict, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table   = 'sl_postback_log'
        verbose_name = _('Postback Log')
        ordering   = ['-created_at']
        indexes    = [
            models.Index(fields=['offer_id', 'created_at'], name='pb_offer_ts_idx'),
            models.Index(fields=['click_id'],                name='pb_click_idx'),
            models.Index(fields=['transaction_id'],          name='pb_txn_idx'),
        ]

    def __str__(self):
        return f"Postback: click={self.click_id} offer={self.offer_id} ${self.payout} [{self.event}]"
