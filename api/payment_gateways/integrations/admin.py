# api/payment_gateways/integrations/admin.py
from django.contrib import admin
from .models import AdvertiserTrackerIntegration

@admin.register(AdvertiserTrackerIntegration)
class TrackerIntegrationAdmin(admin.ModelAdmin):
    list_display   = ('advertiser','tracker','app_id','offer','is_active','created_at')
    list_filter    = ('tracker','is_active')
    search_fields  = ('advertiser__email','app_id')
    readonly_fields= ('created_at','updated_at')
