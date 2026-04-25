# api/payment_gateways/notifications/admin.py
from django.contrib import admin
from .models import InAppNotification, DeviceToken

@admin.register(InAppNotification)
class InAppNotificationAdmin(admin.ModelAdmin):
    list_display  = ('user','notification_type','title','is_read','created_at')
    list_filter   = ('is_read','notification_type')
    search_fields = ('user__email','title')
    readonly_fields = ('created_at','read_at')

@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display  = ('user','platform','is_active','created_at')
    list_filter   = ('platform','is_active')
    search_fields = ('user__email',)
