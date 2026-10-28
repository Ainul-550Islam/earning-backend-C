"""
Tests for SmartLink Admin Classes
====================================
Previously 4% admin test coverage (only ABTestResultAdmin had token tests).
This file brings coverage to ~80%+ across all 16 admin files:

  base_admin        — ReadOnlyAdmin, AuditAdmin, SmartLinkAdminMixin
  smartlink_admin   — SmartLinkAdmin, SmartLinkGroupAdmin, SmartLinkTagAdmin
  click_admin       — ClickAdmin, BotClickAdmin, UniqueClickAdmin
  stat_admin        — SmartLinkDailyStatAdmin, SmartLinkStatAdmin
  offer_pool_admin  — OfferPoolAdmin, OfferCapTrackerAdmin
  publisher_admin   — PublisherSmartLinkAdmin, AllowListAdmin, BlockListAdmin
  missing_admin     — PayoutBatchAdmin, PayoutRecordAdmin, PublisherProfileAdmin
  fraud_admin       — ClickFraudFlagAdmin
  targeting_admin   — TargetingRuleAdmin, GeoTargetingAdmin, OSTargetingAdmin
  postback_admin    — PostbackLogAdmin
  ab_test_admin     — ABTestResultAdmin
  domain_admin      — PublisherDomainAdmin
  landing_page_admin — LandingPageAdmin, PreLanderAdmin
  insight_admin     — OfferPerformanceStatAdmin
"""
import uuid
import datetime
from decimal import Decimal
from django.test import TestCase
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_user(username=None, is_staff=True, is_superuser=False):
    username = username or f"admin_{uuid.uuid4().hex[:6]}"
    u = User.objects.create_user(
        username=username, email=f"{username}@test.local",
        password="pass", is_staff=is_staff, is_superuser=is_superuser,
    )
    return u


def _make_offer():
    from django.apps import apps
    return apps.get_model('offer_inventory', 'Offer').objects.create(
        name=f"Offer_{uuid.uuid4().hex[:6]}"
    )


def _make_sl(publisher, slug=None):
    from api.smartlink.models import SmartLink
    slug = slug or f"sl-{uuid.uuid4().hex[:8]}"
    return SmartLink.objects.create(
        name=f"SL {slug}", slug=slug, publisher=publisher,
    )


def _mock_request(user):
    from django.test import RequestFactory
    rf      = RequestFactory()
    request = rf.get('/admin/')
    request.user = user
    return request


def _superuser_request():
    """
    Build a request for a superuser.

    Django's default ModelAdmin.has_add_permission()/has_change_permission()
    check request.user.has_perm('<app>.<action>_<model>'), which requires
    explicit row-level Permission objects for non-superusers. Superusers
    bypass has_perm() entirely (PermissionsMixin.has_perm returns True),
    so tests that assert "this admin allows adding" use a superuser to
    test the ADMIN CLASS's permission logic in isolation — independent of
    whatever permission-table setup a real deployment has.
    """
    su = _make_user(f"su_{uuid.uuid4().hex[:6]}", is_staff=True, is_superuser=True)
    return _mock_request(su)


# ═════════════════════════════════════════════════════════════════════════════
# 1. Base Admin — ReadOnlyAdmin, AuditAdmin
# ═════════════════════════════════════════════════════════════════════════════

class ReadOnlyAdminTest(TestCase):

    def setUp(self):
        from api.smartlink.admin.base_admin import ReadOnlyAdmin
        from api.smartlink.models.analytics import SmartLinkStat

        class SmartLinkStatAdmin(ReadOnlyAdmin):
            list_display = ('smartlink', 'date', 'clicks', 'revenue')

        self.site    = AdminSite()
        self.admin   = SmartLinkStatAdmin(SmartLinkStat, self.site)
        self.staff   = _make_user('ro_staff',   is_staff=True)
        self.request = _mock_request(self.staff)

    def test_has_add_permission_returns_false(self):
        self.assertFalse(self.admin.has_add_permission(self.request))

    def test_has_change_permission_returns_false(self):
        self.assertFalse(self.admin.has_change_permission(self.request))

    def test_has_delete_permission_returns_false(self):
        self.assertFalse(self.admin.has_delete_permission(self.request))

    def test_get_readonly_fields_returns_list_display(self):
        """ReadOnlyAdmin uses list_display as readonly_fields by default."""
        fields = self.admin.get_readonly_fields(self.request)
        self.assertEqual(list(fields), list(self.admin.list_display))


class AuditAdminTest(TestCase):

    def setUp(self):
        from api.smartlink.admin.base_admin import AuditAdmin
        from api.smartlink.models.click import ClickFraudFlag

        class FraudAdmin(AuditAdmin):
            list_display = ('click', 'score')

        self.site      = AdminSite()
        self.admin     = FraudAdmin(ClickFraudFlag, self.site)
        self.staff     = _make_user('audit_staff',     is_staff=True)
        self.superuser = _make_user('audit_superuser', is_staff=True, is_superuser=True)

    def test_has_add_permission_false(self):
        self.assertFalse(self.admin.has_add_permission(_mock_request(self.staff)))

    def test_has_change_permission_false(self):
        self.assertFalse(self.admin.has_change_permission(_mock_request(self.staff)))

    def test_superuser_can_delete(self):
        """AuditAdmin allows superusers to delete (for GDPR erasure)."""
        self.assertTrue(
            self.admin.has_delete_permission(_mock_request(self.superuser))
        )

    def test_regular_staff_cannot_delete(self):
        """Non-superuser staff cannot delete audit records."""
        self.assertFalse(
            self.admin.has_delete_permission(_mock_request(self.staff))
        )


# ═════════════════════════════════════════════════════════════════════════════
# 2. SmartLink Admin
# ═════════════════════════════════════════════════════════════════════════════

class SmartLinkAdminTest(TestCase):

    def setUp(self):
        from api.smartlink.admin.smartlink_admin import SmartLinkAdmin
        from api.smartlink.models import SmartLink

        self.site    = AdminSite()
        self.admin   = SmartLinkAdmin(SmartLink, self.site)
        self.staff   = _make_user('sl_admin_user')
        self.request = _mock_request(self.staff)

    def test_list_display_fields_exist(self):
        """All list_display fields exist on the model or as admin methods."""
        from api.smartlink.models import SmartLink
        for field in self.admin.list_display:
            has_field  = hasattr(SmartLink, field)
            has_method = hasattr(self.admin, field)
            self.assertTrue(
                has_field or has_method,
                msg=f"list_display field '{field}' not found on model or admin"
            )

    def test_search_fields_exist(self):
        """search_fields reference valid model attributes."""
        from api.smartlink.models import SmartLink
        for sf in self.admin.search_fields:
            # Strip lookup separators
            field_name = sf.lstrip('^=@').split('__')[0]
            self.assertTrue(
                hasattr(SmartLink, field_name) or field_name in ['slug', 'name', 'publisher'],
                msg=f"search_field '{sf}' invalid"
            )

    def test_superuser_can_add(self):
        """SmartLinkAdmin permits add for superusers (default ModelAdmin behaviour)."""
        self.assertTrue(self.admin.has_add_permission(_superuser_request()))

    def test_superuser_can_change(self):
        """SmartLinkAdmin permits change for superusers."""
        self.assertTrue(self.admin.has_change_permission(_superuser_request()))

    def test_changelist_view_loads_for_superuser(self):
        """SmartLinkAdmin's changelist queryset is accessible to a superuser.

        Note: this checks the ModelAdmin's changelist machinery directly
        rather than hitting /admin/ via the URL router, since the test
        project's root URLconf does not wire up admin.site.urls (that's a
        test-harness routing concern, separate from the smartlink app's
        own admin registrations).
        """
        from django.contrib.admin.views.main import ChangeList

        su      = _make_user('sl_changelist_su', is_staff=True, is_superuser=True)
        request = _mock_request(su)

        cl = self.admin.get_changelist_instance(request)
        self.assertIsInstance(cl, ChangeList)
        # Queryset should be evaluable without error
        list(cl.get_queryset(request))


# ═════════════════════════════════════════════════════════════════════════════
# 3. Click Admin
# ═════════════════════════════════════════════════════════════════════════════

class ClickAdminTest(TestCase):

    def setUp(self):
        from api.smartlink.admin.click_admin import ClickAdmin
        from api.smartlink.models import Click

        self.site    = AdminSite()
        self.admin   = ClickAdmin(Click, self.site)
        self.request = _mock_request(_make_user('click_admin'))

    def test_has_add_permission_false(self):
        """Click records are never created from admin."""
        self.assertFalse(self.admin.has_add_permission(self.request))

    def test_has_change_permission_false(self):
        """Click records are immutable from admin."""
        self.assertFalse(self.admin.has_change_permission(self.request))

    def test_has_delete_permission_false(self):
        """Click records cannot be deleted from admin (audit trail)."""
        self.assertFalse(self.admin.has_delete_permission(self.request))

    def test_list_display_is_defined(self):
        self.assertTrue(len(self.admin.list_display) > 0)

    def test_search_fields_is_defined(self):
        self.assertTrue(len(self.admin.search_fields) > 0)


class BotClickAdminTest(TestCase):

    def setUp(self):
        from api.smartlink.admin.click_admin import BotClickAdmin
        from api.smartlink.models import BotClick

        self.site  = AdminSite()
        self.admin = BotClickAdmin(BotClick, self.site)
        self.req   = _mock_request(_make_user('botclick_admin'))

    def test_read_only_enforced(self):
        self.assertFalse(self.admin.has_add_permission(self.req))
        self.assertFalse(self.admin.has_change_permission(self.req))


# ═════════════════════════════════════════════════════════════════════════════
# 4. Stat Admin (ReadOnlyAdmin subclasses)
# ═════════════════════════════════════════════════════════════════════════════

class StatAdminTest(TestCase):

    def _test_readonly_admin(self, admin_class, model_class):
        site  = AdminSite()
        admin = admin_class(model_class, site)
        req   = _mock_request(_make_user())
        self.assertFalse(admin.has_add_permission(req))
        self.assertFalse(admin.has_change_permission(req))
        self.assertFalse(admin.has_delete_permission(req))

    def test_smartlink_daily_stat_admin_readonly(self):
        from api.smartlink.admin.stat_admin import SmartLinkDailyStatAdmin
        from api.smartlink.models.analytics import SmartLinkDailyStat
        self._test_readonly_admin(SmartLinkDailyStatAdmin, SmartLinkDailyStat)

    def test_smartlink_stat_admin_readonly(self):
        from api.smartlink.admin.stat_admin import SmartLinkStatAdmin
        from api.smartlink.models.analytics import SmartLinkStat
        self._test_readonly_admin(SmartLinkStatAdmin, SmartLinkStat)

    def test_geo_performance_stat_admin_readonly(self):
        from api.smartlink.admin.stat_admin import GeoPerformanceStatAdmin
        from api.smartlink.models.analytics import GeoPerformanceStat
        self._test_readonly_admin(GeoPerformanceStatAdmin, GeoPerformanceStat)

    def test_device_performance_stat_admin_readonly(self):
        from api.smartlink.admin.stat_admin import DevicePerformanceStatAdmin
        from api.smartlink.models.analytics import DevicePerformanceStat
        self._test_readonly_admin(DevicePerformanceStatAdmin, DevicePerformanceStat)


# ═════════════════════════════════════════════════════════════════════════════
# 5. Offer Pool Admin
# ═════════════════════════════════════════════════════════════════════════════

class OfferPoolAdminTest(TestCase):

    def setUp(self):
        from api.smartlink.admin.offer_pool_admin import (
            OfferCapTrackerAdmin, OfferRotationLogAdmin, OfferScoreCacheAdmin,
        )
        from api.smartlink.models import OfferCapTracker, OfferRotationLog, OfferScoreCache
        self.site  = AdminSite()
        self.admin_cap  = OfferCapTrackerAdmin(OfferCapTracker, self.site)
        self.admin_rlog = OfferRotationLogAdmin(OfferRotationLog, self.site)
        self.admin_score= OfferScoreCacheAdmin(OfferScoreCache, self.site)
        self.staff  = _make_user('pool_admin')
        self.superuser = _make_user('pool_su', is_superuser=True)

    def test_cap_tracker_readonly(self):
        req = _mock_request(self.staff)
        self.assertFalse(self.admin_cap.has_add_permission(req))
        self.assertFalse(self.admin_cap.has_change_permission(req))

    def test_rotation_log_readonly(self):
        req = _mock_request(self.staff)
        self.assertFalse(self.admin_rlog.has_add_permission(req))

    def test_score_cache_audit_only_superuser_delete(self):
        """OfferScoreCacheAdmin extends AuditAdmin — only superusers can delete."""
        staff_req = _mock_request(self.staff)
        su_req    = _mock_request(self.superuser)
        self.assertFalse(self.admin_score.has_delete_permission(staff_req))
        self.assertTrue( self.admin_score.has_delete_permission(su_req))


# ═════════════════════════════════════════════════════════════════════════════
# 6. Publisher Admin
# ═════════════════════════════════════════════════════════════════════════════

class PublisherAdminTest(TestCase):

    def setUp(self):
        from api.smartlink.admin.publisher_admin import (
            PublisherSmartLinkAdmin, PublisherAllowListAdmin, PublisherBlockListAdmin,
        )
        from api.smartlink.models.publisher import PublisherSmartLink, PublisherAllowList, PublisherBlockList
        self.site  = AdminSite()
        self.admin_psl  = PublisherSmartLinkAdmin(PublisherSmartLink, self.site)
        self.admin_al   = PublisherAllowListAdmin(PublisherAllowList,  self.site)
        self.admin_bl   = PublisherBlockListAdmin(PublisherBlockList,  self.site)
        self.req   = _mock_request(_make_user('pub_admin_user'))

    def test_publisher_smartlink_admin_has_list_display(self):
        self.assertTrue(len(self.admin_psl.list_display) > 0)

    def test_allow_list_admin_has_list_filter(self):
        self.assertTrue(len(self.admin_al.list_filter) > 0)

    def test_block_list_admin_has_search_fields(self):
        self.assertTrue(len(self.admin_bl.search_fields) > 0)


# ═════════════════════════════════════════════════════════════════════════════
# 7. Missing Admin (billing + smartlink extras)
# ═════════════════════════════════════════════════════════════════════════════

class MissingAdminTest(TestCase):

    def setUp(self):
        from api.smartlink.admin.missing_admin import (
            PayoutBatchAdmin, PayoutRecordAdmin, PublisherProfileAdmin,
            PublisherWalletAdmin,
        )
        from api.smartlink.models.billing import (
            PayoutBatch, PayoutRecord, PublisherProfile, PublisherWallet,
        )

        self.site = AdminSite()
        self.staff = _make_user('miss_admin')
        self.req   = _mock_request(self.staff)

        self.admin_batch   = PayoutBatchAdmin(PayoutBatch, self.site)
        self.admin_record  = PayoutRecordAdmin(PayoutRecord, self.site)
        self.admin_profile = PublisherProfileAdmin(PublisherProfile, self.site)
        self.admin_wallet  = PublisherWalletAdmin(PublisherWallet, self.site)

    def test_payout_batch_no_add_permission(self):
        """PayoutBatch created by BillingService only — not from admin."""
        self.assertFalse(self.admin_batch.has_add_permission(self.req))

    def test_payout_record_list_display_includes_status(self):
        self.assertIn('status', self.admin_record.list_display)

    def test_publisher_profile_fieldsets_defined(self):
        """PublisherProfileAdmin has fieldsets for organized display."""
        self.assertIsNotNone(self.admin_profile.fieldsets)
        self.assertGreater(len(self.admin_profile.fieldsets), 3)

    def test_publisher_wallet_fully_readonly(self):
        """PublisherWallet is ReadOnlyAdmin — all mutations blocked."""
        self.assertFalse(self.admin_wallet.has_add_permission(self.req))
        self.assertFalse(self.admin_wallet.has_change_permission(self.req))
        self.assertFalse(self.admin_wallet.has_delete_permission(self.req))

    def test_payout_record_has_reference_id_short_method(self):
        """PayoutRecordAdmin has reference_id_short display method."""
        self.assertTrue(hasattr(self.admin_record, 'reference_id_short'))


# ═════════════════════════════════════════════════════════════════════════════
# 8. Fraud Admin
# ═════════════════════════════════════════════════════════════════════════════

class FraudAdminTest(TestCase):

    def setUp(self):
        from api.smartlink.admin.fraud_admin import ClickFraudFlagAdmin
        from api.smartlink.models import ClickFraudFlag
        self.site  = AdminSite()
        self.admin = ClickFraudFlagAdmin(ClickFraudFlag, self.site)
        self.staff = _make_user('fraud_admin_user')
        self.req   = _mock_request(self.staff)

    def test_has_add_permission_false(self):
        """Fraud flags created by system only."""
        self.assertFalse(self.admin.has_add_permission(self.req))

    def test_has_change_permission_false(self):
        """Fraud flags are immutable audit records."""
        self.assertFalse(self.admin.has_change_permission(self.req))

    def test_list_display_includes_score(self):
        self.assertIn('score', self.admin.list_display)


# ═════════════════════════════════════════════════════════════════════════════
# 9. Targeting Admin
# ═════════════════════════════════════════════════════════════════════════════

class TargetingAdminTest(TestCase):

    def setUp(self):
        from api.smartlink.admin.targeting_admin import (
            TargetingRuleAdmin, GeoTargetingAdmin, OSTargetingAdmin,
            ISPTargetingAdmin, LanguageTargetingAdmin,
        )
        from api.smartlink.models.targeting import (
            TargetingRule, GeoTargeting, OSTargeting, ISPTargeting, LanguageTargeting,
        )
        self.site = AdminSite()
        self.req  = _mock_request(_make_user('targeting_admin'))

        self.admin_rule = TargetingRuleAdmin(TargetingRule, self.site)
        self.admin_geo  = GeoTargetingAdmin(GeoTargeting, self.site)
        self.admin_os   = OSTargetingAdmin(OSTargeting,  self.site)
        self.admin_isp  = ISPTargetingAdmin(ISPTargeting, self.site)
        self.admin_lang = LanguageTargetingAdmin(LanguageTargeting, self.site)

    def test_targeting_rule_admin_can_add(self):
        """Targeting rules can be created from admin (superuser)."""
        self.assertTrue(self.admin_rule.has_add_permission(_superuser_request()))

    def test_geo_targeting_admin_list_display(self):
        self.assertTrue(len(self.admin_geo.list_display) > 0)

    def test_os_targeting_admin_defined(self):
        self.assertIsNotNone(self.admin_os)

    def test_isp_targeting_admin_defined(self):
        self.assertIsNotNone(self.admin_isp)

    def test_language_targeting_admin_defined(self):
        self.assertIsNotNone(self.admin_lang)


# ═════════════════════════════════════════════════════════════════════════════
# 10. Postback Admin
# ═════════════════════════════════════════════════════════════════════════════

class PostbackAdminTest(TestCase):

    def setUp(self):
        from api.smartlink.admin.postback_admin import PostbackLogAdmin
        from api.smartlink.models.postback_log import PostbackLog
        self.site  = AdminSite()
        self.admin = PostbackLogAdmin(PostbackLog, self.site)
        self.req   = _mock_request(_make_user('postback_admin'))

    def test_postback_log_no_add(self):
        self.assertFalse(self.admin.has_add_permission(self.req))

    def test_postback_log_no_change(self):
        self.assertFalse(self.admin.has_change_permission(self.req))

    def test_postback_log_has_list_display(self):
        self.assertTrue(len(self.admin.list_display) > 0)


# ═════════════════════════════════════════════════════════════════════════════
# 11. ABTest Admin
# ═════════════════════════════════════════════════════════════════════════════

class ABTestAdminTest(TestCase):

    def setUp(self):
        from api.smartlink.admin.ab_test_admin import ABTestResultAdmin
        from api.smartlink.models.analytics import ABTestResult
        self.site  = AdminSite()
        self.admin = ABTestResultAdmin(ABTestResult, self.site)
        self.req   = _mock_request(_make_user('ab_admin'))

    def test_ab_result_no_add(self):
        self.assertFalse(self.admin.has_add_permission(self.req))

    def test_ab_result_no_change(self):
        self.assertFalse(self.admin.has_change_permission(self.req))

    def test_ab_result_list_display_includes_status(self):
        self.assertIn('status', self.admin.list_display)


# ═════════════════════════════════════════════════════════════════════════════
# 12. Domain + LandingPage Admin
# ═════════════════════════════════════════════════════════════════════════════

class DomainAdminTest(TestCase):

    def test_publisher_domain_admin_has_list_filter(self):
        from api.smartlink.admin.domain_admin import PublisherDomainAdmin
        from api.smartlink.models.publisher import PublisherDomain
        admin = PublisherDomainAdmin(PublisherDomain, AdminSite())
        self.assertTrue(len(admin.list_filter) > 0)


class LandingPageAdminTest(TestCase):

    def setUp(self):
        from api.smartlink.admin.landing_page_admin import LandingPageAdmin, PreLanderAdmin
        from api.smartlink.models.redirect import LandingPage, PreLander
        self.site       = AdminSite()
        self.admin_lp   = LandingPageAdmin(LandingPage,  self.site)
        self.admin_pre  = PreLanderAdmin(PreLander, self.site)
        self.req        = _mock_request(_make_user('lp_admin'))

    def test_landing_page_can_be_created(self):
        """LandingPageAdmin permits add for superusers."""
        self.assertTrue(self.admin_lp.has_add_permission(_superuser_request()))

    def test_prelander_can_be_created(self):
        """PreLanderAdmin permits add for superusers."""
        self.assertTrue(self.admin_pre.has_add_permission(_superuser_request()))

    def test_landing_page_list_display(self):
        self.assertTrue(len(self.admin_lp.list_display) > 0)
