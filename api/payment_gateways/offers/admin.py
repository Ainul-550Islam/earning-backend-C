# api/payment_gateways/offers/admin.py
from django.contrib import admin
from .models import Offer, Campaign, PublisherOfferApplication, OfferCreative

class OfferCreativeInline(admin.TabularInline):
    model  = OfferCreative
    extra  = 1

@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display   = ('name','offer_type','advertiser','status','publisher_payout','advertiser_cost',
                      'currency','category','total_clicks','total_conversions','epc','created_at')
    list_filter    = ('status','offer_type','category','currency')
    search_fields  = ('name','advertiser__email','app_id')
    readonly_fields= ('slug','total_clicks','total_conversions','total_revenue','conversion_rate','epc','created_at')
    inlines        = [OfferCreativeInline]
    actions        = ['approve_offers','pause_offers']

    @admin.action(description='Approve and activate offers')
    def approve_offers(self, request, queryset):
        queryset.update(status='active')

    @admin.action(description='Pause offers')
    def pause_offers(self, request, queryset):
        queryset.update(status='paused')

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display   = ('name','advertiser','status','total_budget','spent','currency','total_clicks','total_conversions','created_at')
    list_filter    = ('status',)
    search_fields  = ('name','advertiser__email')
    readonly_fields= ('spent','total_clicks','total_conversions','total_revenue','created_at')

@admin.register(PublisherOfferApplication)
class PublisherApplicationAdmin(admin.ModelAdmin):
    list_display   = ('publisher','offer','status','reviewed_by','created_at')
    list_filter    = ('status',)
    search_fields  = ('publisher__email','offer__name')
    actions        = ['approve_applications','reject_applications']

    @admin.action(description='Approve applications')
    def approve_applications(self, request, queryset):
        for app in queryset.filter(status='pending'):
            app.status = 'approved'
            app.reviewed_by = request.user
            app.save()
            app.offer.allowed_publishers.add(app.publisher)

    @admin.action(description='Reject applications')
    def reject_applications(self, request, queryset):
        queryset.filter(status='pending').update(status='rejected', reviewed_by=request.user)
