# api/wallet/models/statement.py
from django.db import models
from django.conf import settings
from django.utils import timezone


class AccountStatement(models.Model):
    """Monthly/yearly wallet account statement."""
    PERIODS=[("monthly","Monthly"),("quarterly","Quarterly"),("yearly","Yearly"),("custom","Custom")]
    STATUS=[("generating","Generating"),("ready","Ready"),("failed","Failed")]

    tenant          = models.ForeignKey("tenants.Tenant",on_delete=models.SET_NULL,null=True,blank=True,related_name="wallet_statement_tenant",db_index=True)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="wallet_statements")
    wallet          = models.ForeignKey("wallet.Wallet",on_delete=models.CASCADE,related_name="statements")
    period          = models.CharField(max_length=12,choices=PERIODS,default="monthly")
    period_start    = models.DateField(db_index=True)
    period_end      = models.DateField()
    status          = models.CharField(max_length=12,choices=STATUS,default="generating")
    opening_balance = models.DecimalField(max_digits=20,decimal_places=8,default=0)
    closing_balance = models.DecimalField(max_digits=20,decimal_places=8,default=0)
    total_credits   = models.DecimalField(max_digits=20,decimal_places=8,default=0)
    total_debits    = models.DecimalField(max_digits=20,decimal_places=8,default=0)
    total_fees      = models.DecimalField(max_digits=20,decimal_places=8,default=0)
    txn_count       = models.PositiveIntegerField(default=0)
    pdf_file        = models.CharField(max_length=500,blank=True)
    csv_file        = models.CharField(max_length=500,blank=True)
    generated_at    = models.DateTimeField(null=True,blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label="wallet"; db_table="wallet_account_statement"; ordering=["-period_start"]
        unique_together=[("wallet","period","period_start")]

    def __str__(self): return f"{self.user.username}|{self.period}|{self.period_start}"


class StatementLine(models.Model):
    """Individual transaction line in a statement."""
    statement  = models.ForeignKey(AccountStatement,on_delete=models.CASCADE,related_name="lines")
    txn_id     = models.CharField(max_length=100,blank=True)
    date       = models.DateField()
    description= models.TextField()
    txn_type   = models.CharField(max_length=30)
    credit     = models.DecimalField(max_digits=20,decimal_places=8,default=0)
    debit      = models.DecimalField(max_digits=20,decimal_places=8,default=0)
    balance    = models.DecimalField(max_digits=20,decimal_places=8,default=0)
    reference  = models.CharField(max_length=100,blank=True)

    class Meta:
        app_label="wallet"; db_table="wallet_statement_line"; ordering=["date","id"]
