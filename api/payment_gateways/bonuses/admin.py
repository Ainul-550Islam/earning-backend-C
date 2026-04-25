# api/payment_gateways/bonuses/admin.py
from django.contrib import admin
from .models import PerformanceTier, PublisherBonus

@admin.register(PerformanceTier)
class PerformanceTierAdmin(admin.ModelAdmin):
    list_display   = ('name','min_monthly_earnings','bonus_percent','min_payout_threshold','priority_support','exclusive_offers','sort_order')
    ordering       = ('sort_order',)

@admin.register(PublisherBonus)
class PublisherBonusAdmin(admin.ModelAdmin):
    list_display   = ('publisher','bonus_type','amount','currency','status','period','paid_at','created_at')
    list_filter    = ('bonus_type','status','currency')
    search_fields  = ('publisher__email','period')
    readonly_fields= ('created_at','paid_at')
    actions        = ['mark_paid']

    @admin.action(description='Mark selected bonuses as paid')
    def mark_paid(self, request, queryset):
        from django.utils import timezone
        queryset.filter(status='pending').update(status='paid', paid_at=timezone.now())
