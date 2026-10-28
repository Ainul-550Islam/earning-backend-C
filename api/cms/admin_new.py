# cms/admin_new.py
"""
Admin registrations for new CMS models.

v11 additions (appended at the bottom of the existing file):
  - offerwall.Offer, offerwall.OfferClick, offerwall.OfferConversion
  - api_finance.Wallet, api_finance.Transaction,
    api_finance.PayoutRequest, api_finance.ReconciliationLog
  - cms.models_new.ab_testing: ABTest, ABTestVariant,
    ABTestParticipant, ABTestResult
  - cms.models_new.realtime_offers: RealTimeOfferUpdate,
    UserOfferSubscription, OfferUpdateQueue

Import this file in admin.py:
    from .admin_new import *
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _


# ─────────────────────────────────────────────────────────────────────
# Existing registrations (Blog, Media, Popup, Menu, Landing, SEO) are
# preserved exactly as they were in the previous version of admin_new.py.
# ─────────────────────────────────────────────────────────────────────

try:
    from api.cms.models_new.blog import BlogCategory, BlogTag, BlogPost, BlogComment, BlogSEO

    @admin.register(BlogCategory)
    class BlogCategoryAdmin(admin.ModelAdmin):
        list_display = ['name', 'slug', 'parent', 'sort_order', 'post_count', 'is_active']
        list_filter = ['is_active', 'parent']
        search_fields = ['name', 'slug']
        prepopulated_fields = {'slug': ('name',)}
        ordering = ['sort_order', 'name']

    @admin.register(BlogTag)
    class BlogTagAdmin(admin.ModelAdmin):
        list_display = ['name', 'slug', 'usage_count', 'is_active']
        search_fields = ['name', 'slug']
        prepopulated_fields = {'slug': ('name',)}
        ordering = ['-usage_count']

    class BlogSEOInline(admin.StackedInline):
        model = BlogSEO
        extra = 0
        fields = ['meta_title', 'meta_description', 'meta_keywords',
                  'og_image', 'canonical_url', 'no_index', 'no_follow']

    @admin.register(BlogPost)
    class BlogPostAdmin(admin.ModelAdmin):
        list_display = ['title', 'author', 'category', 'status',
                        'is_featured', 'views_count', 'published_at']
        list_filter = ['status', 'is_featured', 'language', 'category']
        search_fields = ['title', 'excerpt', 'body']
        prepopulated_fields = {'slug': ('title',)}
        raw_id_fields = ['author', 'category']
        filter_horizontal = ['tags']
        ordering = ['-published_at']
        inlines = [BlogSEOInline]
        actions = ['publish_posts', 'archive_posts']

        def publish_posts(self, request, queryset):
            count = 0
            for post in queryset:
                post.publish()
                count += 1
            self.message_user(request, f"{count} posts published.")
        publish_posts.short_description = "Publish selected posts"

        def archive_posts(self, request, queryset):
            count = queryset.update(status='archived', is_active=False)
            self.message_user(request, f"{count} posts archived.")
        archive_posts.short_description = "Archive selected posts"

    @admin.register(BlogComment)
    class BlogCommentAdmin(admin.ModelAdmin):
        list_display = ['post', 'user', 'guest_name', 'is_approved', 'is_flagged', 'created_at']
        list_filter = ['is_approved', 'is_flagged', 'is_active']
        search_fields = ['content', 'guest_name', 'guest_email']
        raw_id_fields = ['post', 'user', 'approved_by']
        actions = ['approve_comments']

        def approve_comments(self, request, queryset):
            for comment in queryset:
                comment.approve(moderator=request.user)
            self.message_user(request, f"{queryset.count()} comments approved.")
        approve_comments.short_description = "Approve selected comments"

except ImportError:
    pass


try:
    from api.cms.models_new.media import MediaFile, MediaFolder, MediaVariant, MediaTag, MediaUsage

    @admin.register(MediaFolder)
    class MediaFolderAdmin(admin.ModelAdmin):
        list_display = ['name', 'parent', 'file_count', 'total_size', 'is_system', 'created_at']
        list_filter = ['is_system']
        search_fields = ['name']
        raw_id_fields = ['parent', 'created_by']

    @admin.register(MediaFile)
    class MediaFileAdmin(admin.ModelAdmin):
        list_display = ['name', 'folder', 'file_type', 'file_size', 'is_public', 'upload_status', 'uploaded_at']
        list_filter = ['file_type', 'is_public', 'upload_status']
        search_fields = ['name', 'original_filename', 'alt_text']
        raw_id_fields = ['folder', 'uploaded_by']
        readonly_fields = ['file_size', 'dimensions', 'cdn_url', 'uploaded_at']

    @admin.register(MediaTag)
    class MediaTagAdmin(admin.ModelAdmin):
        list_display = ['name', 'slug', 'usage_count']
        search_fields = ['name', 'slug']

except ImportError:
    pass


try:
    from api.cms.models_new.popup import Popup, PopupRule, PopupStat, PopupABTest

    @admin.register(Popup)
    class PopupAdmin(admin.ModelAdmin):
        list_display = ['name', 'popup_type', 'status', 'trigger_type',
                        'total_displays', 'total_conversions', 'starts_at', 'ends_at']
        list_filter = ['status', 'popup_type', 'trigger_type', 'language']
        search_fields = ['name', 'title']
        ordering = ['-created_at']
        readonly_fields = ['total_displays', 'total_conversions', 'unique_users', 'revenue_generated']

    @admin.register(PopupRule)
    class PopupRuleAdmin(admin.ModelAdmin):
        list_display = ['popup', 'rule_type', 'is_active', 'priority']
        list_filter = ['rule_type', 'is_active']
        raw_id_fields = ['popup']

    @admin.register(PopupStat)
    class PopupStatAdmin(admin.ModelAdmin):
        list_display = ['popup', 'date', 'displays', 'conversions', 'revenue']
        list_filter = ['popup', 'date']
        readonly_fields = ['popup', 'date', 'displays', 'conversions', 'revenue']

        def has_add_permission(self, request):
            return False

except ImportError:
    pass


try:
    from api.cms.models_new.menu import Menu, MenuItem, MenuVisibility
    from api.cms.models_new.landing_pages import LandingSection

    @admin.register(Menu)
    class MenuAdmin(admin.ModelAdmin):
        list_display = ['name', 'slug', 'location', 'language', 'is_active', 'item_count']
        list_filter = ['is_active', 'location', 'language']
        search_fields = ['name', 'slug']
        prepopulated_fields = {'slug': ('name',)}

    @admin.register(MenuItem)
    class MenuItemAdmin(admin.ModelAdmin):
        list_display = ['label', 'menu', 'parent', 'item_type', 'sort_order', 'is_visible']
        list_filter = ['menu', 'item_type', 'is_visible']
        search_fields = ['label', 'url']
        raw_id_fields = ['menu', 'parent']
        ordering = ['menu', 'sort_order']

    @admin.register(LandingSection)
    class LandingSectionAdmin(admin.ModelAdmin):
        list_display = ['name', 'section_type', 'sort_order', 'page_slug', 'show_for', 'is_active', 'view_count']
        list_filter = ['section_type', 'is_active', 'show_for']
        search_fields = ['name', 'page_slug']
        ordering = ['sort_order']
        readonly_fields = ['view_count', 'click_count']

except ImportError:
    pass


try:
    from api.cms.models_new.seo import SEOConfig, Sitemap, Redirect301, RobotsConfig

    @admin.register(SEOConfig)
    class SEOConfigAdmin(admin.ModelAdmin):
        list_display = ['site_name', 'default_title', 'google_analytics_id', 'is_active']
        list_filter = ['is_active']
        fieldsets = (
            ('Basic', {'fields': ('site_name', 'default_title', 'title_separator',
                                  'default_description', 'default_keywords', 'is_active')}),
            ('Open Graph', {'fields': ('og_image', 'og_type')}),
            ('Twitter', {'fields': ('twitter_card', 'twitter_site', 'twitter_creator')}),
            ('Analytics', {'fields': ('google_analytics_id', 'google_tag_manager_id',
                                      'google_search_console', 'bing_webmaster', 'facebook_app_id')}),
            ('Advanced', {'fields': ('canonical_base_url', 'enable_breadcrumbs',
                                     'enable_json_ld', 'json_ld_org_data', 'noindex_site')}),
        )

    @admin.register(Sitemap)
    class SitemapAdmin(admin.ModelAdmin):
        list_display = ['url', 'changefreq', 'priority', 'last_modified', 'source_type', 'is_active']
        list_filter = ['changefreq', 'is_active', 'source_type', 'is_auto_generated']
        search_fields = ['url', 'source_type']
        ordering = ['-priority', 'url']
        readonly_fields = ['is_auto_generated', 'last_crawled', 'crawl_status']
        actions = ['deactivate_entries']

        def deactivate_entries(self, request, queryset):
            queryset.update(is_active=False)
            self.message_user(request, f"Deactivated {queryset.count()} entries.")
        deactivate_entries.short_description = "Deactivate selected entries"

    @admin.register(Redirect301)
    class Redirect301Admin(admin.ModelAdmin):
        list_display = ['from_url', 'to_url', 'redirect_type', 'hit_count', 'last_hit', 'is_active', 'expires_at']
        list_filter = ['redirect_type', 'is_active']
        search_fields = ['from_url', 'to_url', 'notes']
        ordering = ['-hit_count']
        readonly_fields = ['hit_count', 'last_hit']
        actions = ['deactivate_redirects']

        def deactivate_redirects(self, request, queryset):
            queryset.update(is_active=False)
            self.message_user(request, f"Deactivated {queryset.count()} redirects.")
        deactivate_redirects.short_description = "Deactivate selected redirects"

    @admin.register(RobotsConfig)
    class RobotsConfigAdmin(admin.ModelAdmin):
        list_display = ['name', 'is_active', 'crawl_delay', 'sitemap_url']
        list_filter = ['is_active']
        search_fields = ['name']
        fieldsets = (
            ('Basic', {'fields': ('name', 'is_active', 'sitemap_url', 'crawl_delay')}),
            ('Rules', {'fields': ('allow_rules', 'disallow_rules')}),
            ('Per-Bot Rules', {'fields': ('per_bot_rules',)}),
            ('Custom', {'fields': ('custom_content',)}),
        )

except ImportError:
    pass


try:
    try:
        from api.cms.INTEGRATION_SYSTEM.integ_audit_logs import IntegrationAuditLog
    except ImportError:
        pass

    @admin.register(IntegrationAuditLog)
    class IntegrationAuditLogAdmin(admin.ModelAdmin):
        list_display = ['action', 'source', 'user', 'ip_address', 'success', 'amount', 'duration_ms', 'created_at']
        list_filter = ['action', 'success', 'source']
        search_fields = ['lead_id', 'event_id', 'ip_address', 'message']
        readonly_fields = ['action', 'source', 'user', 'ip_address', 'success', 'message',
                           'data', 'event_id', 'lead_id', 'amount', 'duration_ms', 'created_at']
        ordering = ['-created_at']

        def has_add_permission(self, request):
            return False

        def has_delete_permission(self, request, obj=None):
            return request.user.is_superuser

except Exception:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# NEW v11 REGISTRATIONS — Offerwall App
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from offerwall.models import Offer, OfferClick, OfferConversion

    class OfferClickInline(admin.TabularInline):
        model = OfferClick
        extra = 0
        max_num = 10
        fields = ['user', 'ip_address', 'country', 'device_type', 'subid', 'clicked_at']
        readonly_fields = ['user', 'ip_address', 'country', 'device_type', 'subid', 'clicked_at']
        can_delete = False

        def has_add_permission(self, request, obj=None):
            return False

    class OfferConversionInline(admin.TabularInline):
        model = OfferConversion
        extra = 0
        max_num = 10
        fields = ['user', 'lead_id', 'payout_usd', 'virtual_awarded', 'status', 'fraud_score', 'converted_at']
        readonly_fields = ['user', 'lead_id', 'payout_usd', 'virtual_awarded', 'fraud_score', 'converted_at']
        can_delete = False

        def has_add_permission(self, request, obj=None):
            return False

    @admin.register(Offer)
    class OfferAdmin(admin.ModelAdmin):
        list_display = [
            'title', 'source', 'status', 'is_featured',
            'payout_usd', 'virtual_payout', 'target_device',
            'total_clicks', 'total_conversions', 'conversion_rate_display',
            'created_at', 'expires_at',
        ]
        list_filter = ['status', 'source', 'is_featured', 'target_device']
        search_fields = ['title', 'description', 'external_id']
        readonly_fields = [
            'id', 'total_clicks', 'total_conversions', 'total_paid_usd',
            'created_at', 'updated_at',
        ]
        ordering = ['-is_featured', '-payout_usd']
        inlines = [OfferClickInline, OfferConversionInline]
        actions = ['activate_offers', 'pause_offers', 'expire_offers']

        fieldsets = (
            ('Identity', {
                'fields': ('id', 'title', 'description', 'source', 'external_id')
            }),
            ('Payout', {
                'fields': ('payout_usd', 'virtual_payout', 'revenue_share')
            }),
            ('Status & Targeting', {
                'fields': ('status', 'is_featured', 'target_device',
                           'target_countries', 'min_user_level')
            }),
            ('Media', {
                'fields': ('image_url', 'click_url')
            }),
            ('Analytics (read-only)', {
                'fields': ('total_clicks', 'total_conversions', 'total_paid_usd'),
                'classes': ('collapse',),
            }),
            ('Timestamps', {
                'fields': ('created_at', 'updated_at', 'expires_at'),
                'classes': ('collapse',),
            }),
        )

        def conversion_rate_display(self, obj):
            rate = obj.conversion_rate
            colour = 'green' if rate >= 10 else 'orange' if rate >= 3 else 'red'
            return format_html(
                '<span style="color:{}; font-weight:bold;">{:.1f}%</span>',
                colour, rate
            )
        conversion_rate_display.short_description = 'Conv. Rate'
        conversion_rate_display.admin_order_field = 'total_conversions'

        def activate_offers(self, request, queryset):
            count = queryset.update(status='active')
            self.message_user(request, f"{count} offer(s) activated.")
        activate_offers.short_description = "Activate selected offers"

        def pause_offers(self, request, queryset):
            count = queryset.update(status='paused')
            self.message_user(request, f"{count} offer(s) paused.")
        pause_offers.short_description = "Pause selected offers"

        def expire_offers(self, request, queryset):
            count = queryset.update(status='expired')
            self.message_user(request, f"{count} offer(s) expired.")
        expire_offers.short_description = "Mark selected as expired"

    @admin.register(OfferClick)
    class OfferClickAdmin(admin.ModelAdmin):
        list_display = [
            'offer', 'user', 'country', 'device_type',
            'subid', 'ip_address', 'clicked_at',
        ]
        list_filter = ['device_type', 'country', 'clicked_at']
        search_fields = ['subid', 'ip_address', 'offer__title', 'user__username']
        readonly_fields = [
            'id', 'offer', 'user', 'ip_address', 'user_agent',
            'country', 'device_type', 'subid', 'clicked_at',
        ]
        ordering = ['-clicked_at']
        raw_id_fields = ['offer', 'user']
        date_hierarchy = 'clicked_at'

        def has_add_permission(self, request):
            return False  # Clicks are created programmatically only

    @admin.register(OfferConversion)
    class OfferConversionAdmin(admin.ModelAdmin):
        list_display = [
            'lead_id', 'offer', 'user', 'payout_usd',
            'virtual_awarded', 'status', 'fraud_score_badge',
            'converted_at',
        ]
        list_filter = ['status', 'converted_at']
        search_fields = ['lead_id', 'offer__title', 'user__username', 'ip_address']
        readonly_fields = [
            'id', 'lead_id', 'offer', 'click', 'user',
            'ip_address', 'postback_raw',
            'approved_at', 'rejected_at', 'converted_at',
        ]
        ordering = ['-converted_at']
        raw_id_fields = ['offer', 'click', 'user']
        date_hierarchy = 'converted_at'
        actions = ['approve_conversions', 'reject_conversions']

        fieldsets = (
            ('Attribution', {
                'fields': ('id', 'offer', 'click', 'user', 'lead_id')
            }),
            ('Amounts', {
                'fields': ('payout_usd', 'virtual_awarded')
            }),
            ('Status & Fraud', {
                'fields': ('status', 'fraud_score', 'fraud_reasons')
            }),
            ('Raw Data', {
                'fields': ('ip_address', 'postback_raw'),
                'classes': ('collapse',),
            }),
            ('Timestamps', {
                'fields': ('converted_at', 'approved_at', 'rejected_at'),
                'classes': ('collapse',),
            }),
        )

        def fraud_score_badge(self, obj):
            score = obj.fraud_score
            colour = 'red' if score > 70 else 'orange' if score > 30 else 'green'
            return format_html(
                '<span style="color:{}; font-weight:bold;">{}</span>',
                colour, score
            )
        fraud_score_badge.short_description = 'Fraud'
        fraud_score_badge.admin_order_field = 'fraud_score'

        def approve_conversions(self, request, queryset):
            from django.utils import timezone
            count = queryset.filter(status='pending').update(
                status='approved', approved_at=timezone.now()
            )
            self.message_user(request, f"{count} conversion(s) approved.")
        approve_conversions.short_description = "Approve selected conversions"

        def reject_conversions(self, request, queryset):
            from django.utils import timezone
            count = queryset.filter(status='pending').update(
                status='rejected', rejected_at=timezone.now()
            )
            self.message_user(request, f"{count} conversion(s) rejected.")
        reject_conversions.short_description = "Reject selected conversions"

        def has_add_permission(self, request):
            return False  # Conversions are created via postback only

except ImportError:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# NEW v11 REGISTRATIONS — api_finance App
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from api_finance.models import Wallet, Transaction, PayoutRequest, ReconciliationLog

    class TransactionInline(admin.TabularInline):
        model = Transaction
        extra = 0
        max_num = 15
        fields = ['transaction_type', 'source', 'amount_usd', 'status', 'description', 'created_at']
        readonly_fields = ['transaction_type', 'source', 'amount_usd', 'status', 'description', 'created_at']
        can_delete = False
        ordering = ['-created_at']

        def has_add_permission(self, request, obj=None):
            return False

    @admin.register(Wallet)
    class WalletAdmin(admin.ModelAdmin):
        list_display = [
            'user', 'balance_usd_display', 'balance_virtual',
            'total_earned_usd', 'total_paid_usd',
            'lock_status', 'created_at',
        ]
        list_filter = ['is_locked', 'created_at']
        search_fields = ['user__username', 'user__email', 'locked_reason']
        readonly_fields = [
            'id', 'user', 'total_earned_usd', 'total_paid_usd',
            'created_at', 'updated_at',
        ]
        ordering = ['-balance_usd']
        raw_id_fields = ['user']
        inlines = [TransactionInline]
        actions = ['lock_wallets', 'unlock_wallets']

        fieldsets = (
            ('User', {'fields': ('id', 'user')}),
            ('Balances', {'fields': ('balance_usd', 'balance_virtual',
                                     'total_earned_usd', 'total_paid_usd')}),
            ('Lock Status', {'fields': ('is_locked', 'locked_reason')}),
            ('Timestamps', {'fields': ('created_at', 'updated_at'),
                            'classes': ('collapse',)}),
        )

        def balance_usd_display(self, obj):
            colour = 'green' if obj.balance_usd > 0 else 'grey'
            return format_html(
                '<span style="color:{};">${}</span>', colour, obj.balance_usd
            )
        balance_usd_display.short_description = 'Balance (USD)'
        balance_usd_display.admin_order_field = 'balance_usd'

        def lock_status(self, obj):
            if obj.is_locked:
                return format_html('<span style="color:red; font-weight:bold;">🔒 LOCKED</span>')
            return format_html('<span style="color:green;">✓ Active</span>')
        lock_status.short_description = 'Status'
        lock_status.admin_order_field = 'is_locked'

        def lock_wallets(self, request, queryset):
            count = queryset.update(is_locked=True, locked_reason='Locked via admin action')
            self.message_user(request, f"{count} wallet(s) locked.")
        lock_wallets.short_description = "Lock selected wallets"

        def unlock_wallets(self, request, queryset):
            count = queryset.update(is_locked=False, locked_reason='')
            self.message_user(request, f"{count} wallet(s) unlocked.")
        unlock_wallets.short_description = "Unlock selected wallets"

    @admin.register(Transaction)
    class TransactionAdmin(admin.ModelAdmin):
        list_display = [
            'id_short', 'user', 'transaction_type', 'source',
            'amount_usd', 'fee_usd', 'net_usd',
            'status', 'created_at',
        ]
        list_filter = ['transaction_type', 'source', 'status', 'created_at']
        search_fields = ['id', 'user__username', 'reference_id', 'description']
        readonly_fields = [
            'id', 'wallet', 'user', 'reference_id',
            'balance_before', 'balance_after', 'net_usd',
            'created_at', 'completed_at',
        ]
        ordering = ['-created_at']
        raw_id_fields = ['wallet', 'user']
        date_hierarchy = 'created_at'

        fieldsets = (
            ('Identity', {'fields': ('id', 'wallet', 'user', 'reference_id')}),
            ('Amounts', {'fields': ('amount', 'amount_usd', 'amount_virtual',
                                    'currency', 'fee_usd', 'net_usd')}),
            ('Classification', {'fields': ('transaction_type', 'source', 'status')}),
            ('Balance Snapshot', {'fields': ('balance_before', 'balance_after'),
                                   'classes': ('collapse',)}),
            ('Metadata', {'fields': ('description', 'metadata', 'ip_address'),
                          'classes': ('collapse',)}),
            ('Timestamps', {'fields': ('created_at', 'completed_at'),
                            'classes': ('collapse',)}),
        )

        def id_short(self, obj):
            return str(obj.id)[:8] + '…'
        id_short.short_description = 'ID'

        def has_add_permission(self, request):
            return False  # Transactions created via service layer only

        def has_delete_permission(self, request, obj=None):
            return request.user.is_superuser  # Immutable audit trail

    @admin.register(PayoutRequest)
    class PayoutRequestAdmin(admin.ModelAdmin):
        list_display = [
            'id_short', 'user', 'amount_requested', 'fee',
            'amount_net', 'method', 'status_badge',
            'fraud_score_display', 'created_at',
        ]
        list_filter = ['status', 'method', 'created_at']
        search_fields = ['id', 'user__username', 'destination', 'external_ref']
        readonly_fields = [
            'id', 'user', 'transaction', 'amount_net',
            'created_at', 'processed_at',
        ]
        ordering = ['-created_at']
        raw_id_fields = ['user', 'transaction']
        date_hierarchy = 'created_at'
        actions = ['approve_requests', 'reject_requests', 'mark_paid']

        fieldsets = (
            ('Identity', {'fields': ('id', 'user', 'transaction')}),
            ('Amounts', {'fields': ('amount_requested', 'fee', 'amount_net')}),
            ('Payment', {'fields': ('method', 'destination', 'external_ref')}),
            ('Status & Fraud', {'fields': ('status', 'fraud_score',
                                           'rejection_reason', 'admin_notes')}),
            ('Timestamps', {'fields': ('created_at', 'processed_at'),
                            'classes': ('collapse',)}),
        )

        def id_short(self, obj):
            return str(obj.id)[:8] + '…'
        id_short.short_description = 'ID'

        def status_badge(self, obj):
            colours = {
                'pending':  'orange',
                'approved': 'blue',
                'paid':     'green',
                'rejected': 'red',
                'failed':   'darkred',
            }
            colour = colours.get(obj.status, 'grey')
            return format_html(
                '<span style="color:{}; font-weight:bold;">{}</span>',
                colour, obj.get_status_display()
            )
        status_badge.short_description = 'Status'
        status_badge.admin_order_field = 'status'

        def fraud_score_display(self, obj):
            score = obj.fraud_score
            colour = 'red' if score > 70 else 'orange' if score > 30 else 'green'
            return format_html(
                '<span style="color:{};">{}</span>', colour, score
            )
        fraud_score_display.short_description = 'Fraud Score'
        fraud_score_display.admin_order_field = 'fraud_score'

        def approve_requests(self, request, queryset):
            from django.utils import timezone
            count = queryset.filter(status='pending').update(
                status='approved', processed_at=timezone.now()
            )
            self.message_user(request, f"{count} payout request(s) approved.")
        approve_requests.short_description = "Approve selected payout requests"

        def reject_requests(self, request, queryset):
            from django.utils import timezone
            count = queryset.filter(status='pending').update(
                status='rejected',
                rejection_reason='Rejected via admin action',
                processed_at=timezone.now()
            )
            self.message_user(request, f"{count} payout request(s) rejected.")
        reject_requests.short_description = "Reject selected payout requests"

        def mark_paid(self, request, queryset):
            from django.utils import timezone
            count = queryset.filter(status='approved').update(
                status='paid', processed_at=timezone.now()
            )
            self.message_user(request, f"{count} payout request(s) marked as paid.")
        mark_paid.short_description = "Mark selected as Paid"

    @admin.register(ReconciliationLog)
    class ReconciliationLogAdmin(admin.ModelAdmin):
        list_display = [
            'date', 'total_credited', 'total_debited',
            'total_payouts', 'transaction_count', 'payout_count',
            'discrepancy_usd', 'balanced_badge', 'run_by', 'created_at',
        ]
        list_filter = ['is_balanced', 'date']
        search_fields = ['date', 'notes']
        readonly_fields = [
            'id', 'date',
            'total_credited', 'total_debited', 'total_fees', 'total_payouts',
            'transaction_count', 'payout_count',
            'discrepancy_usd', 'is_balanced',
            'run_by', 'created_at',
        ]
        ordering = ['-date']
        raw_id_fields = ['run_by']

        def balanced_badge(self, obj):
            if obj.is_balanced:
                return format_html('<span style="color:green; font-weight:bold;">✓ Balanced</span>')
            return format_html(
                '<span style="color:red; font-weight:bold;">✗ Gap: ${}</span>',
                obj.discrepancy_usd
            )
        balanced_badge.short_description = 'Balance'
        balanced_badge.admin_order_field = 'is_balanced'

        def has_add_permission(self, request):
            return False  # Generated automatically by reconciliation task

        def has_delete_permission(self, request, obj=None):
            return request.user.is_superuser  # Immutable audit record

except ImportError:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# NEW v11 REGISTRATIONS — cms.models_new.ab_testing
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from api.cms.models_new.ab_testing import (
        ABTest, ABTestVariant, ABTestParticipant, ABTestResult
    )

    class ABTestVariantInline(admin.TabularInline):
        model = ABTestVariant
        extra = 1
        max_num = 6
        fields = ['name', 'is_control', 'traffic_split', 'is_active',
                  'offer_id', 'payout_multiplier']
        readonly_fields = []

    class ABTestResultInline(admin.TabularInline):
        model = ABTestResult
        extra = 0
        fields = [
            'variant', 'total_participants', 'conversions',
            'conversion_rate', 'total_value',
            'is_statistically_significant', 'is_winner', 'calculated_at',
        ]
        readonly_fields = fields
        can_delete = False

        def has_add_permission(self, request, obj=None):
            return False

    @admin.register(ABTest)
    class ABTestAdmin(admin.ModelAdmin):
        list_display = [
            'name', 'test_type', 'status', 'target_percentage',
            'start_time', 'end_time',
            'participant_count', 'confidence_level', 'created_at',
        ]
        list_filter = ['status', 'test_type', 'start_time']
        search_fields = ['name', 'description', 'uuid']
        readonly_fields = ['uuid', 'created_at', 'updated_at']
        ordering = ['-created_at']
        inlines = [ABTestVariantInline, ABTestResultInline]
        actions = ['start_tests', 'pause_tests', 'complete_tests']

        fieldsets = (
            ('Identity', {'fields': ('uuid', 'name', 'description', 'test_type', 'status')}),
            ('Targeting', {
                'fields': ('target_percentage', 'target_countries',
                           'target_devices', 'min_age', 'max_age')
            }),
            ('Schedule', {'fields': ('start_time', 'end_time', 'min_duration_hours')}),
            ('Statistics', {
                'fields': ('confidence_level', 'min_sample_size',
                           'primary_metric', 'secondary_metrics')
            }),
            ('Timestamps', {'fields': ('created_at', 'updated_at'),
                            'classes': ('collapse',)}),
        )

        def participant_count(self, obj):
            return obj.participants.count()
        participant_count.short_description = 'Participants'

        def start_tests(self, request, queryset):
            from django.utils import timezone
            count = queryset.filter(status='draft').update(
                status='running', start_time=timezone.now()
            )
            self.message_user(request, f"{count} test(s) started.")
        start_tests.short_description = "Start selected tests"

        def pause_tests(self, request, queryset):
            count = queryset.filter(status='running').update(status='paused')
            self.message_user(request, f"{count} test(s) paused.")
        pause_tests.short_description = "Pause selected tests"

        def complete_tests(self, request, queryset):
            count = queryset.filter(status__in=['running', 'paused']).update(status='completed')
            self.message_user(request, f"{count} test(s) marked completed.")
        complete_tests.short_description = "Mark selected as completed"

    @admin.register(ABTestVariant)
    class ABTestVariantAdmin(admin.ModelAdmin):
        list_display = [
            'name', 'test', 'is_control', 'traffic_split',
            'is_active', 'offer_id', 'payout_multiplier',
        ]
        list_filter = ['is_control', 'is_active', 'test__status']
        search_fields = ['name', 'uuid', 'offer_id', 'test__name']
        readonly_fields = ['uuid', 'created_at', 'updated_at']
        raw_id_fields = ['test']
        ordering = ['test', 'traffic_split']

    @admin.register(ABTestParticipant)
    class ABTestParticipantAdmin(admin.ModelAdmin):
        list_display = [
            'user', 'test', 'variant', 'has_converted',
            'conversion_value', 'assigned_at', 'converted_at',
        ]
        list_filter = ['has_converted', 'test__status', 'assigned_at']
        search_fields = ['user__username', 'uuid', 'test__name']
        readonly_fields = [
            'uuid', 'test', 'variant', 'user',
            'assigned_at', 'first_seen_at', 'last_seen_at',
            'has_converted', 'converted_at', 'conversion_value',
            'clicks', 'page_views', 'time_spent_seconds',
        ]
        raw_id_fields = ['test', 'variant', 'user']
        ordering = ['-assigned_at']

        def has_add_permission(self, request):
            return False  # Participants are assigned automatically

    @admin.register(ABTestResult)
    class ABTestResultAdmin(admin.ModelAdmin):
        list_display = [
            'test', 'variant', 'total_participants', 'conversions',
            'conversion_rate', 'total_value',
            'is_statistically_significant', 'is_winner', 'calculated_at',
        ]
        list_filter = ['is_winner', 'is_statistically_significant']
        search_fields = ['test__name', 'uuid']
        readonly_fields = [
            'uuid', 'test', 'variant',
            'total_participants', 'active_participants',
            'conversions', 'conversion_rate',
            'total_value', 'avg_value_per_conversion', 'avg_value_per_participant',
            'total_clicks', 'total_page_views', 'avg_time_spent',
            'confidence_interval_lower', 'confidence_interval_upper',
            'p_value', 'is_statistically_significant',
            'improvement_percentage', 'is_winner', 'calculated_at',
        ]
        ordering = ['-calculated_at']

        def has_add_permission(self, request):
            return False  # Computed automatically

        def has_delete_permission(self, request, obj=None):
            return request.user.is_superuser

except ImportError:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# NEW v11 REGISTRATIONS — cms.models_new.realtime_offers
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from api.cms.models_new.realtime_offers import (
        RealTimeOfferUpdate, UserOfferSubscription, OfferUpdateQueue
    )

    @admin.register(RealTimeOfferUpdate)
    class RealTimeOfferUpdateAdmin(admin.ModelAdmin):
        list_display = [
            'offer_id', 'update_type', 'priority', 'is_active',
            'created_at', 'processed_at', 'expires_at',
        ]
        list_filter = ['update_type', 'is_active', 'created_at']
        search_fields = ['offer_id', 'uuid']
        readonly_fields = ['uuid', 'created_at', 'processed_at']
        ordering = ['-priority', '-created_at']
        actions = ['deactivate_updates', 'activate_updates']

        fieldsets = (
            ('Identity', {'fields': ('uuid', 'offer_id', 'update_type', 'priority', 'is_active')}),
            ('Data', {'fields': ('old_data', 'new_data')}),
            ('Targeting', {'fields': ('countries', 'devices', 'min_age', 'max_age')}),
            ('Timestamps', {'fields': ('created_at', 'processed_at', 'expires_at'),
                            'classes': ('collapse',)}),
        )

        def deactivate_updates(self, request, queryset):
            count = queryset.update(is_active=False)
            self.message_user(request, f"{count} update(s) deactivated.")
        deactivate_updates.short_description = "Deactivate selected updates"

        def activate_updates(self, request, queryset):
            count = queryset.update(is_active=True)
            self.message_user(request, f"{count} update(s) activated.")
        activate_updates.short_description = "Activate selected updates"

    @admin.register(UserOfferSubscription)
    class UserOfferSubscriptionAdmin(admin.ModelAdmin):
        list_display = [
            'user', 'is_active',
            'subscribe_new_offers', 'subscribe_updated_offers',
            'min_payout', 'max_payout',
            'notification_sound', 'notification_desktop',
            'updated_at',
        ]
        list_filter = ['is_active', 'subscribe_new_offers', 'notification_desktop']
        search_fields = ['user__username', 'user__email']
        readonly_fields = ['created_at', 'updated_at']
        raw_id_fields = ['user']
        ordering = ['-updated_at']

        fieldsets = (
            ('User', {'fields': ('user', 'is_active')}),
            ('Subscription Types', {
                'fields': ('subscribe_new_offers', 'subscribe_updated_offers',
                           'subscribe_expired_offers', 'subscribe_payout_changes')
            }),
            ('Filters', {
                'fields': ('min_payout', 'max_payout',
                           'preferred_countries', 'preferred_categories')
            }),
            ('Notification Channels', {
                'fields': ('notification_sound', 'notification_desktop', 'notification_email')
            }),
            ('Timestamps', {'fields': ('created_at', 'updated_at'),
                            'classes': ('collapse',)}),
        )

    @admin.register(OfferUpdateQueue)
    class OfferUpdateQueueAdmin(admin.ModelAdmin):
        list_display = ['uuid', 'status', 'created_at', 'processed_at', 'error_message']
        list_filter = ['status', 'created_at']
        search_fields = ['uuid']
        readonly_fields = ['uuid', 'batch_data', 'created_at', 'processed_at', 'error_message']
        ordering = ['-created_at']
        actions = ['retry_failed']

        def retry_failed(self, request, queryset):
            count = queryset.filter(status='failed').update(status='pending')
            self.message_user(request, f"{count} queue item(s) reset to pending.")
        retry_failed.short_description = "Retry selected failed items"

        def has_add_permission(self, request):
            return False  # Items are queued programmatically

except ImportError:
    pass
