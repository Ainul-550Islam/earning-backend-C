# api/wallet/models/config.py
from django.db import models
from django.utils import timezone


class WalletConfigModel(models.Model):
    """Runtime configuration key-value store."""
    tenant      = models.ForeignKey("tenants.Tenant",on_delete=models.SET_NULL,null=True,blank=True,related_name="wallet_config_tenant",db_index=True)
    key         = models.CharField(max_length=100,unique=True,db_index=True)
    value       = models.TextField()
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    updated_by  = models.CharField(max_length=100,blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label="wallet"; db_table="wallet_config"; ordering=["key"]

    def __str__(self): return f"{self.key}={self.value[:50]}"


class GatewayConfig(models.Model):
    """Per-gateway configuration."""
    GATEWAYS=[("bkash","bKash"),("nagad","Nagad"),("rocket","Rocket"),
              ("usdt_trc20","USDT TRC-20"),("usdt_erc20","USDT ERC-20"),
              ("paypal","PayPal"),("stripe","Stripe"),("sslcommerz","SSLCommerz")]
    tenant         = models.ForeignKey("tenants.Tenant",on_delete=models.SET_NULL,null=True,blank=True,related_name="wallet_gwconfig_tenant",db_index=True)
    gateway        = models.CharField(max_length=20,choices=GATEWAYS,unique=True)
    is_enabled     = models.BooleanField(default=True)
    min_amount     = models.DecimalField(max_digits=14,decimal_places=2,default=50)
    max_amount     = models.DecimalField(max_digits=14,decimal_places=2,default=100000)
    fee_percent    = models.DecimalField(max_digits=5,decimal_places=2,default=2)
    flat_fee       = models.DecimalField(max_digits=8,decimal_places=2,default=0)
    processing_time_hours = models.PositiveIntegerField(default=24)
    config         = models.JSONField(default=dict,blank=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        app_label="wallet"; db_table="wallet_gateway_config"

    def __str__(self): return f"{self.gateway}|enabled={self.is_enabled}"
