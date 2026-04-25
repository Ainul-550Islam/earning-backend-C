# api/payment_gateways/smartlink/admin.py
from django.contrib import admin
from .models import SmartLink, SmartLinkRotation

@admin.register(SmartLink)
class SmartLinkAdmin(admin.ModelAdmin):
    list_display   = ('name','publisher','rotation_mode','status','total_clicks','total_conversions','total_earnings','epc','created_at')
    list_filter    = ('rotation_mode','status')
    search_fields  = ('name','publisher__email','slug')
    readonly_fields= ('slug','total_clicks','total_conversions','total_earnings','epc','url')

@admin.register(SmartLinkRotation)
class SmartLinkRotationAdmin(admin.ModelAdmin):
    list_display   = ('smart_link','offer','weight','clicks','conversions','earnings')
    list_filter    = ('is_control',)
