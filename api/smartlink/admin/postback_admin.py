from django.contrib import admin
from ..models.postback_log import PostbackLog


@admin.register(PostbackLog)
class PostbackLogAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'event', 'click_id', 'offer_id',
        'payout', 'currency', 'transaction_id',
        'is_duplicate', 'is_attributed', 'ip', 'created_at',
    ]
    list_filter  = ['event', 'is_duplicate', 'is_attributed', 'currency', 'created_at']
    search_fields = ['click_id', 'offer_id', 'transaction_id', 'ip', 'sub1']
    readonly_fields = [
        'click_id', 'offer_id', 'event', 'payout', 'currency',
        'transaction_id', 'sub1', 'adv_sub1', 'ip',
        'is_duplicate', 'is_attributed', 'raw_params', 'created_at',
    ]
    date_hierarchy  = 'created_at'
    ordering        = ['-created_at']
    list_per_page   = 100

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
