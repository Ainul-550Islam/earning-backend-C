# api/wallet/models/audit.py
from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    """Immutable audit trail for all wallet admin actions."""
    ACTION_TYPES=[
        ("wallet_locked","Wallet Locked"),("wallet_unlocked","Wallet Unlocked"),
        ("balance_frozen","Balance Frozen"),("balance_unfrozen","Balance Unfrozen"),
        ("admin_credit","Admin Credit"),("admin_debit","Admin Debit"),
        ("withdrawal_approved","Withdrawal Approved"),("withdrawal_rejected","Withdrawal Rejected"),
        ("kyc_approved","KYC Approved"),("kyc_rejected","KYC Rejected"),
        ("fraud_detected","Fraud Detected"),("aml_flagged","AML Flagged"),
        ("fee_changed","Fee Changed"),("limit_changed","Limit Changed"),
        ("config_changed","Config Changed"),("manual_reconcile","Manual Reconcile"),
        ("dispute_opened","Dispute Opened"),("dispute_resolved","Dispute Resolved"),
        ("withdrawal_blocked","Withdrawal Blocked"),("withdrawal_unblocked","Withdrawal Unblocked"),
        ("security_lock","Security Lock Applied"),
    ]
    tenant          = models.ForeignKey("tenants.Tenant",on_delete=models.SET_NULL,null=True,blank=True,related_name="wallet_auditlog_tenant",db_index=True)
    action          = models.CharField(max_length=50,choices=ACTION_TYPES,db_index=True)
    performed_by    = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="wallet_audit_performed_by")
    target_type     = models.CharField(max_length=30,default="wallet",db_index=True)
    target_id       = models.BigIntegerField(null=True,blank=True,db_index=True)
    detail          = models.TextField(blank=True)
    before_state    = models.JSONField(default=dict,blank=True)
    after_state     = models.JSONField(default=dict,blank=True)
    ip_address      = models.GenericIPAddressField(null=True,blank=True)
    metadata        = models.JSONField(default=dict,blank=True)
    created_at      = models.DateTimeField(auto_now_add=True,db_index=True)

    class Meta:
        app_label="wallet"; db_table="wallet_audit_log"; ordering=["-created_at"]
        indexes=[models.Index(fields=["action","created_at"]),
                 models.Index(fields=["target_type","target_id"])]

    def __str__(self): return f"{self.action}|{self.target_type}:{self.target_id}|{self.created_at:%Y-%m-%d}"

    def save(self,*args,**kwargs):
        if self.pk: raise ValueError("AuditLog is immutable — cannot update")
        super().save(*args,**kwargs)

    def delete(self,*args,**kwargs):
        raise ValueError("AuditLog is immutable — cannot delete")
