"""
Tests for B2B Components
Covers: white_label, reseller, trial_management,
        tenant_lifecycle (onboarding, offboarding, BYOK, SSO, support tickets),
        backup_sdk
"""

import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, Mock
from django.test import TestCase


# ─────────────────────────────────────────────────────────
# WHITE LABEL
# ─────────────────────────────────────────────────────────

class BrandThemeTest(TestCase):
    def test_theme_to_css_vars(self):
        from api.backup.white_label import BrandTheme
        theme = BrandTheme(primary_color="#FF5733")
        css = theme.to_css_vars()
        self.assertIn("--brand-primary: #FF5733", css)
        self.assertIn(":root", css)

    def test_theme_defaults(self):
        from api.backup.white_label import BrandTheme
        theme = BrandTheme()
        self.assertEqual(theme.primary_color, "#1A73E8")
        self.assertEqual(theme.font_family, "Inter, sans-serif")


class WhiteLabelConfigTest(TestCase):
    def _make_config(self, tenant_id="t-001"):
        from api.backup.white_label import WhiteLabelConfig
        return WhiteLabelConfig(
            tenant_id=tenant_id,
            brand_name="Acme Backup",
            custom_domain="backup.acme.com",
            support_email="support@acme.com",
        )

    def test_config_validates_ok(self):
        config = self._make_config()
        self.assertTrue(config.validate())

    def test_empty_brand_name_fails(self):
        from api.backup.white_label import WhiteLabelConfig
        config = WhiteLabelConfig(tenant_id="t-002", brand_name="")
        with self.assertRaises(ValueError):
            config.validate()

    def test_invalid_domain_fails(self):
        from api.backup.white_label import WhiteLabelConfig
        config = WhiteLabelConfig(
            tenant_id="t-003", brand_name="X", custom_domain="not a domain!!"
        )
        with self.assertRaises(ValueError):
            config.validate()

    def test_email_defaults_from_brand(self):
        config = self._make_config()
        self.assertIn("Acme", config.email_from_name)

    def test_to_dict(self):
        config = self._make_config()
        d = config.to_dict()
        self.assertIn("brand_name", d)
        self.assertEqual(d["brand_name"], "Acme Backup")

    def test_hide_powered_by(self):
        from api.backup.white_label import WhiteLabelConfig
        config = WhiteLabelConfig(tenant_id="t-004", brand_name="OEM Corp",
                                  hide_powered_by=True)
        self.assertTrue(config.hide_powered_by)


class WhiteLabelRegistryTest(TestCase):
    def _make_registry_and_config(self):
        from api.backup.white_label import WhiteLabelRegistry, WhiteLabelConfig
        registry = WhiteLabelRegistry()
        config = WhiteLabelConfig(tenant_id="t-001", brand_name="Acme",
                                  custom_domain="backup.acme.com")
        return registry, config

    def test_register_and_get(self):
        registry, config = self._make_registry_and_config()
        registry.register(config)
        self.assertIsNotNone(registry.get("t-001"))
        self.assertEqual(registry.get("t-001").brand_name, "Acme")

    def test_get_by_domain(self):
        registry, config = self._make_registry_and_config()
        registry.register(config)
        found = registry.get_by_domain("backup.acme.com")
        self.assertIsNotNone(found)

    def test_update_config(self):
        registry, config = self._make_registry_and_config()
        registry.register(config)
        registry.update("t-001", {"support_email": "new@acme.com"})
        self.assertEqual(registry.get("t-001").support_email, "new@acme.com")

    def test_delete_config(self):
        registry, config = self._make_registry_and_config()
        registry.register(config)
        self.assertTrue(registry.delete("t-001"))
        self.assertIsNone(registry.get("t-001"))

    def test_list_all(self):
        from api.backup.white_label import WhiteLabelRegistry, WhiteLabelConfig
        registry = WhiteLabelRegistry()
        for i in range(3):
            registry.register(WhiteLabelConfig(f"t-{i}", f"Brand {i}"))
        self.assertEqual(len(registry.list_all()), 3)


class EmailTemplateRendererTest(TestCase):
    def _make_config(self):
        from api.backup.white_label import WhiteLabelConfig
        return WhiteLabelConfig(
            tenant_id="t-001", brand_name="Acme",
            support_email="support@acme.com",
            logo_url="https://acme.com/logo.png",
        )

    def test_render_email(self):
        from api.backup.white_label import EmailTemplateRenderer
        renderer = EmailTemplateRenderer()
        result = renderer.render(self._make_config(), "<p>Test body</p>", "Test subject")
        self.assertIn("html", result)
        self.assertIn("Acme", result["html"])
        self.assertIn("Test body", result["html"])

    def test_backup_completed_email(self):
        from api.backup.white_label import EmailTemplateRenderer
        renderer = EmailTemplateRenderer()
        result = renderer.backup_completed_email(self._make_config(), "prod_backup", "1.2 GB")
        self.assertIn("completed", result["html"].lower())
        self.assertIn("1.2 GB", result["html"])

    def test_backup_failed_email(self):
        from api.backup.white_label import EmailTemplateRenderer
        renderer = EmailTemplateRenderer()
        result = renderer.backup_failed_email(self._make_config(), "prod_backup", "Disk full")
        self.assertIn("failed", result["html"].lower())

    def test_hide_powered_by(self):
        from api.backup.white_label import WhiteLabelConfig, EmailTemplateRenderer
        config = WhiteLabelConfig("t-oem", "OEM Corp", hide_powered_by=True)
        renderer = EmailTemplateRenderer()
        result = renderer.render(config, "<p>body</p>")
        self.assertNotIn("Powered by BackupSystem", result["html"])

    def test_logo_in_email(self):
        from api.backup.white_label import EmailTemplateRenderer
        renderer = EmailTemplateRenderer()
        result = renderer.render(self._make_config(), "<p>body</p>")
        self.assertIn("logo.png", result["html"])


# ─────────────────────────────────────────────────────────
# RESELLER / MSP
# ─────────────────────────────────────────────────────────

class ResellerProfileTest(TestCase):
    def _make_reseller(self, rid="r-001", tier=None):
        from api.backup.reseller import ResellerProfile, PartnerTier
        return ResellerProfile(
            reseller_id=rid,
            company_name="ACME MSP",
            tier=tier or PartnerTier.MSP,
            contact_email="admin@acmemsp.com",
        )

    def test_is_active(self):
        from api.backup.reseller import ResellerStatus
        r = self._make_reseller()
        self.assertTrue(r.is_active)
        r.status = ResellerStatus.SUSPENDED
        self.assertFalse(r.is_active)

    def test_to_dict(self):
        r = self._make_reseller()
        d = r.to_dict()
        self.assertIn("reseller_id", d)
        self.assertIn("commission_pct", d)


class ResellerHierarchyTest(TestCase):
    def setUp(self):
        from api.backup.reseller import ResellerHierarchyManager, ResellerProfile, PartnerTier
        self.mgr = ResellerHierarchyManager()
        self.distributor = ResellerProfile("dist-001", "Big Dist", PartnerTier.DISTRIBUTOR)
        self.reseller = ResellerProfile("res-001", "Reseller A", PartnerTier.RESELLER,
                                         parent_id="dist-001")
        self.msp = ResellerProfile("msp-001", "ACME MSP", PartnerTier.MSP,
                                    parent_id="res-001")
        self.mgr.register_reseller(self.distributor)
        self.mgr.register_reseller(self.reseller)
        self.mgr.register_reseller(self.msp)

    def test_register_reseller(self):
        self.assertIsNotNone(self.mgr.get_reseller("dist-001"))

    def test_unknown_parent_raises(self):
        from api.backup.reseller import ResellerProfile, PartnerTier
        orphan = ResellerProfile("r-999", "Orphan", PartnerTier.RESELLER,
                                  parent_id="nonexistent")
        with self.assertRaises(LookupError):
            self.mgr.register_reseller(orphan)

    def test_get_children(self):
        children = self.mgr.get_children("dist-001")
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].reseller_id, "res-001")

    def test_get_ancestors(self):
        ancestors = self.mgr.get_ancestors("msp-001")
        ancestor_ids = [a.reseller_id for a in ancestors]
        self.assertIn("res-001", ancestor_ids)
        self.assertIn("dist-001", ancestor_ids)

    def test_get_full_subtree(self):
        subtree = self.mgr.get_full_subtree("dist-001")
        ids = [r.reseller_id for r in subtree]
        self.assertIn("res-001", ids)
        self.assertIn("msp-001", ids)

    def test_provision_tenant(self):
        from api.backup.reseller import SubTenant
        tenant = SubTenant("cust-001", "msp-001", "Customer A", "admin@custA.com")
        self.mgr.provision_tenant(tenant)
        tenants = self.mgr.get_tenants("msp-001")
        self.assertEqual(len(tenants), 1)

    def test_max_tenants_enforced(self):
        from api.backup.reseller import SubTenant, ResellerProfile, PartnerTier
        small_msp = ResellerProfile("msp-small", "Tiny MSP", PartnerTier.MSP,
                                     parent_id="dist-001", max_tenants=2)
        self.mgr.register_reseller(small_msp)
        for i in range(2):
            self.mgr.provision_tenant(
                SubTenant(f"c-{i}", "msp-small", f"Cust{i}", f"a{i}@c.com")
            )
        with self.assertRaises(RuntimeError):
            self.mgr.provision_tenant(
                SubTenant("c-overflow", "msp-small", "Extra", "x@c.com")
            )

    def test_suspend_reseller(self):
        from api.backup.reseller import SubTenant
        self.mgr.provision_tenant(SubTenant("c-001", "msp-001", "C1", "a@b.com"))
        count = self.mgr.suspend_reseller("msp-001")
        self.assertGreater(count, 0)

    def test_usage_summary(self):
        from api.backup.reseller import SubTenant
        self.mgr.provision_tenant(SubTenant("c-001", "msp-001", "C1", "a@b.com",
                                             storage_quota_gb=100))
        summary = self.mgr.usage_summary("msp-001")
        self.assertEqual(summary.reseller_id, "msp-001")
        self.assertGreater(summary.total_storage_gb, 0)
        self.assertGreater(summary.commission_estimate, 0)

    def test_commission_report(self):
        report = self.mgr.commission_report()
        self.assertIsInstance(report, list)

    def test_get_all_tenants_in_subtree(self):
        from api.backup.reseller import SubTenant
        self.mgr.provision_tenant(SubTenant("c-001", "msp-001", "C1", "a@b.com"))
        self.mgr.provision_tenant(SubTenant("c-002", "res-001", "C2", "b@b.com"))
        all_tenants = self.mgr.get_all_tenants_in_subtree("dist-001")
        ids = [t.tenant_id for t in all_tenants]
        self.assertIn("c-001", ids)
        self.assertIn("c-002", ids)


# ─────────────────────────────────────────────────────────
# TRIAL MANAGEMENT
# ─────────────────────────────────────────────────────────

class PlanLimitsTest(TestCase):
    def test_plan_tiers_defined(self):
        from api.backup.trial_management import PLAN_LIMITS, PlanTier
        for tier in [PlanTier.FREE, PlanTier.TRIAL, PlanTier.STARTER,
                     PlanTier.BUSINESS, PlanTier.ENTERPRISE]:
            self.assertIn(tier, PLAN_LIMITS)

    def test_enterprise_is_unlimited(self):
        from api.backup.trial_management import PLAN_LIMITS, PlanTier
        ent = PLAN_LIMITS[PlanTier.ENTERPRISE]
        self.assertGreater(ent.storage_gb, 10000)
        self.assertGreater(ent.backup_jobs, 1000)

    def test_free_is_most_restrictive(self):
        from api.backup.trial_management import PLAN_LIMITS, PlanTier
        free = PLAN_LIMITS[PlanTier.FREE]
        business = PLAN_LIMITS[PlanTier.BUSINESS]
        self.assertLess(free.storage_gb, business.storage_gb)
        self.assertLess(free.backup_jobs, business.backup_jobs)

    def test_to_dict(self):
        from api.backup.trial_management import PLAN_LIMITS, PlanTier
        d = PLAN_LIMITS[PlanTier.STARTER].to_dict()
        self.assertIn("storage_gb", d)
        self.assertIn("support_tier", d)


class TrialManagerTest(TestCase):
    def setUp(self):
        from api.backup.trial_management import TrialManager
        self.mgr = TrialManager()

    def test_start_trial(self):
        from api.backup.trial_management import TrialStatus, PlanTier
        sub = self.mgr.start_trial("t-001", trial_days=14)
        self.assertEqual(sub.plan.value, PlanTier.TRIAL.value)
        self.assertEqual(sub.trial_status, TrialStatus.ACTIVE)
        self.assertTrue(sub.is_trial_active)
        self.assertEqual(sub.trial_days_remaining, 14)

    def test_start_free(self):
        from api.backup.trial_management import PlanTier
        sub = self.mgr.start_free("t-002")
        self.assertEqual(sub.plan, PlanTier.FREE)

    def test_upgrade_from_trial(self):
        from api.backup.trial_management import PlanTier, TrialStatus
        self.mgr.start_trial("t-003", trial_days=14)
        sub = self.mgr.upgrade("t-003", PlanTier.BUSINESS)
        self.assertEqual(sub.plan, PlanTier.BUSINESS)
        self.assertEqual(sub.trial_status, TrialStatus.CONVERTED)

    def test_check_limit_within(self):
        self.mgr.start_trial("t-004")
        result = self.mgr.check_limit("t-004", "storage_gb", 10)
        self.assertTrue(result["allowed"])

    def test_check_limit_exceeded(self):
        self.mgr.start_free("t-005")
        result = self.mgr.check_limit("t-005", "storage_gb", 100)  # FREE=5GB
        self.assertFalse(result["allowed"])

    def test_trial_expiry(self):
        sub = self.mgr.start_trial("t-006", trial_days=0)
        sub.trial_started_at = datetime.utcnow() - timedelta(days=1)
        expired = self.mgr.expire_trials()
        self.assertIn("t-006", expired)

    def test_expiring_soon(self):
        sub = self.mgr.start_trial("t-007", trial_days=2)
        soon = self.mgr.list_trials_expiring_soon(days=3)
        self.assertTrue(any(s.tenant_id == "t-007" for s in soon))

    def test_subscription_to_dict(self):
        sub = self.mgr.start_trial("t-008")
        d = sub.to_dict()
        self.assertIn("plan", d)
        self.assertIn("limits", d)
        self.assertIn("is_trial_active", d)


# ─────────────────────────────────────────────────────────
# TENANT ONBOARDING
# ─────────────────────────────────────────────────────────

class TenantOnboardingTest(TestCase):
    def setUp(self):
        from api.backup.tenant_lifecycle import TenantOnboardingService
        self.svc = TenantOnboardingService()

    def test_invite_tenant(self):
        from api.backup.tenant_lifecycle import OnboardingStatus
        checklist = self.svc.invite_tenant("t-001", "admin@company.com")
        self.assertIsNotNone(checklist)
        self.assertEqual(self.svc.get_status("t-001"), OnboardingStatus.INVITED)

    def test_mark_steps(self):
        self.svc.invite_tenant("t-002", "admin@company.com")
        for step in ["admin_user_created", "storage_configured",
                     "first_backup_run", "notification_configured",
                     "billing_configured"]:
            self.svc.mark_step("t-002", step)
        checklist = self.svc.get_checklist("t-002")
        self.assertTrue(checklist.is_complete)
        self.assertEqual(checklist.completion_pct, 100.0)

    def test_completion_pct_partial(self):
        self.svc.invite_tenant("t-003", "a@b.com")
        self.svc.mark_step("t-003", "admin_user_created")
        checklist = self.svc.get_checklist("t-003")
        self.assertGreater(checklist.completion_pct, 0)
        self.assertLess(checklist.completion_pct, 100)

    def test_list_incomplete(self):
        self.svc.invite_tenant("t-004", "a@b.com")
        incomplete = self.svc.list_incomplete()
        self.assertTrue(any(c.tenant_id == "t-004" for c in incomplete))

    def test_activated_at_set_on_completion(self):
        self.svc.invite_tenant("t-005", "a@b.com")
        for step in ["admin_user_created", "storage_configured",
                     "first_backup_run", "notification_configured",
                     "billing_configured"]:
            self.svc.mark_step("t-005", step)
        checklist = self.svc.get_checklist("t-005")
        self.assertIsNotNone(checklist.activated_at)

    def test_checklist_to_dict(self):
        checklist = self.svc.invite_tenant("t-006", "a@b.com")
        d = checklist.to_dict()
        self.assertIn("completion_pct", d)
        self.assertIn("steps", d)


# ─────────────────────────────────────────────────────────
# TENANT OFFBOARDING
# ─────────────────────────────────────────────────────────

class TenantOffboardingTest(TestCase):
    def setUp(self):
        from api.backup.tenant_lifecycle import TenantOffboardingService
        self.svc = TenantOffboardingService()

    def _make_request(self, tenant_id="t-001", grace_days=30):
        from api.backup.tenant_lifecycle import OffboardingRequest, OffboardingReason
        return OffboardingRequest(
            tenant_id=tenant_id,
            reason=OffboardingReason.CHURNED,
            requested_by="admin@example.com",
            purge_after_days=grace_days,
        )

    def test_initiate_offboarding(self):
        req = self._make_request()
        result = self.svc.initiate(req)
        self.assertIsNotNone(result.scheduled_purge_at)

    def test_grace_period_blocks_purge(self):
        req = self._make_request(grace_days=30)
        self.svc.initiate(req)
        with self.assertRaises(RuntimeError):
            self.svc.purge_tenant_data("t-001")

    def test_purge_after_grace_period(self):
        req = self._make_request("t-002", grace_days=0)
        req.scheduled_purge_at = datetime.utcnow() - timedelta(seconds=1)
        self.svc.initiate(req)
        result = self.svc.purge_tenant_data("t-002")
        self.assertEqual(result["tenant_id"], "t-002")
        self.assertIn("purged", result)

    def test_cancel_offboarding(self):
        req = self._make_request("t-003")
        self.svc.initiate(req)
        self.assertTrue(self.svc.cancel_offboarding("t-003"))
        self.assertIsNone(self.svc.get_request("t-003"))

    def test_due_for_purge(self):
        req = self._make_request("t-004", grace_days=0)
        req.scheduled_purge_at = datetime.utcnow() - timedelta(hours=1)
        self.svc.initiate(req)
        due = self.svc.due_for_purge()
        self.assertTrue(any(r.tenant_id == "t-004" for r in due))

    def test_export_tenant_data(self):
        result = self.svc.export_tenant_data("t-005", "/exports/t-005/")
        self.assertEqual(result["status"], "queued")


# ─────────────────────────────────────────────────────────
# BYOK
# ─────────────────────────────────────────────────────────

class BYOKTest(TestCase):
    def _make_key(self, tenant_id="t-001"):
        from api.backup.tenant_lifecycle import CustomerEncryptionKey
        return CustomerEncryptionKey(
            tenant_id=tenant_id,
            key_id="key-001",
            key_alias="prod-key",
            provider="aws_kms",
            key_arn="arn:aws:kms:us-east-1:123456789:key/abc-def",
            rotation_days=90,
        )

    def test_register_and_get_key(self):
        from api.backup.tenant_lifecycle import BYOKManager
        mgr = BYOKManager()
        mgr.register_key(self._make_key())
        key = mgr.get_key("t-001")
        self.assertIsNotNone(key)
        self.assertEqual(key.provider, "aws_kms")

    def test_rotate_key(self):
        from api.backup.tenant_lifecycle import BYOKManager
        mgr = BYOKManager()
        mgr.register_key(self._make_key())
        result = mgr.rotate_key("t-001", "arn:aws:kms:us-east-1:123:key/new-key")
        self.assertTrue(result)
        self.assertIsNotNone(mgr.get_key("t-001").rotated_at)

    def test_revoke_key(self):
        from api.backup.tenant_lifecycle import BYOKManager
        mgr = BYOKManager()
        mgr.register_key(self._make_key())
        self.assertTrue(mgr.revoke_key("t-001"))
        self.assertFalse(mgr.get_key("t-001").is_active)

    def test_encrypt_decrypt(self):
        from api.backup.tenant_lifecycle import BYOKManager
        mgr = BYOKManager()
        mgr.register_key(self._make_key("t-enc"))
        data = b"sensitive backup content"
        encrypted = mgr.encrypt_with_tenant_key("t-enc", data)
        decrypted = mgr.decrypt_with_tenant_key("t-enc", encrypted)
        self.assertEqual(decrypted, data)

    def test_encrypt_fails_without_key(self):
        from api.backup.tenant_lifecycle import BYOKManager
        mgr = BYOKManager()
        with self.assertRaises(PermissionError):
            mgr.encrypt_with_tenant_key("no-tenant", b"data")

    def test_needs_rotation_flag(self):
        from api.backup.tenant_lifecycle import CustomerEncryptionKey
        key = CustomerEncryptionKey(
            tenant_id="t-old", key_id="k-old", key_alias="old",
            provider="gcp_kms", key_arn="gcp://key/old",
            rotation_days=1,
            created_at=datetime.utcnow() - timedelta(days=5),
        )
        self.assertTrue(key.needs_rotation)

    def test_keys_needing_rotation(self):
        from api.backup.tenant_lifecycle import BYOKManager, CustomerEncryptionKey
        mgr = BYOKManager()
        stale = CustomerEncryptionKey(
            tenant_id="t-stale", key_id="k-stale", key_alias="stale",
            provider="aws_kms", key_arn="arn:stale",
            rotation_days=1,
            created_at=datetime.utcnow() - timedelta(days=10),
        )
        mgr.register_key(stale)
        due = mgr.keys_needing_rotation()
        self.assertEqual(len(due), 1)


# ─────────────────────────────────────────────────────────
# SSO
# ─────────────────────────────────────────────────────────

class SSOManagerTest(TestCase):
    def _make_saml_config(self, tenant_id="t-sso"):
        from api.backup.tenant_lifecycle import SSOConfig, SSOProtocol
        return SSOConfig(
            tenant_id=tenant_id,
            protocol=SSOProtocol.SAML2,
            provider_name="Okta",
            entity_id="https://okta.example.com/app/backup",
            sso_url="https://okta.example.com/sso/saml",
            x509_cert="MIIC...certificate...",
        )

    def _make_oidc_config(self, tenant_id="t-oidc"):
        from api.backup.tenant_lifecycle import SSOConfig, SSOProtocol
        return SSOConfig(
            tenant_id=tenant_id,
            protocol=SSOProtocol.OIDC,
            provider_name="Azure AD",
            client_id="client-abc-123",
            client_secret="secret-xyz",
            sso_url="https://login.microsoftonline.com/tenant/oauth2/v2.0/authorize",
            discovery_url="https://login.microsoftonline.com/tenant/.well-known/openid-configuration",
        )

    def test_configure_saml(self):
        from api.backup.tenant_lifecycle import SSOManager
        mgr = SSOManager()
        mgr.configure(self._make_saml_config())
        self.assertIsNotNone(mgr.get("t-sso"))

    def test_configure_oidc(self):
        from api.backup.tenant_lifecycle import SSOManager
        mgr = SSOManager()
        mgr.configure(self._make_oidc_config())
        self.assertIsNotNone(mgr.get("t-oidc"))

    def test_invalid_saml_config_raises(self):
        from api.backup.tenant_lifecycle import SSOConfig, SSOProtocol, SSOManager
        config = SSOConfig(tenant_id="t-bad", protocol=SSOProtocol.SAML2,
                           provider_name="Okta")  # missing required fields
        mgr = SSOManager()
        with self.assertRaises(ValueError):
            mgr.configure(config)

    def test_disable_sso(self):
        from api.backup.tenant_lifecycle import SSOManager
        mgr = SSOManager()
        mgr.configure(self._make_saml_config("t-dis"))
        self.assertTrue(mgr.disable("t-dis"))
        self.assertFalse(mgr.get("t-dis").enabled)

    def test_initiate_saml_flow(self):
        from api.backup.tenant_lifecycle import SSOManager
        mgr = SSOManager()
        mgr.configure(self._make_saml_config())
        flow = mgr.initiate_saml_flow("t-sso")
        self.assertIn("redirect_url", flow)
        self.assertIn("state", flow)
        self.assertIn("okta", flow["redirect_url"])

    def test_initiate_oidc_flow(self):
        from api.backup.tenant_lifecycle import SSOManager
        mgr = SSOManager()
        mgr.configure(self._make_oidc_config())
        flow = mgr.initiate_oidc_flow("t-oidc", "https://app.com/callback")
        self.assertIn("redirect_url", flow)
        self.assertIn("client_id=client-abc-123", flow["redirect_url"])

    def test_process_saml_response(self):
        from api.backup.tenant_lifecycle import SSOManager
        mgr = SSOManager()
        mgr.configure(self._make_saml_config())
        result = mgr.process_saml_response("t-sso", "mock-saml-response-base64")
        self.assertIn("email", result)
        self.assertIn("auto_provision", result)

    def test_list_configs(self):
        from api.backup.tenant_lifecycle import SSOManager
        mgr = SSOManager()
        mgr.configure(self._make_saml_config("t-a"))
        mgr.configure(self._make_oidc_config("t-b"))
        self.assertEqual(len(mgr.list_configs()), 2)

    def test_sso_config_to_dict(self):
        config = self._make_saml_config()
        d = config.to_dict()
        self.assertIn("protocol", d)
        self.assertIn("provider_name", d)
        self.assertNotIn("client_secret", d)  # secret not exposed


# ─────────────────────────────────────────────────────────
# SUPPORT TICKETS
# ─────────────────────────────────────────────────────────

class SupportTicketTest(TestCase):
    def _make_ticket(self, ticket_id="tkt-001"):
        from api.backup.tenant_lifecycle import SupportTicket, SupportTicketPriority
        return SupportTicket(
            ticket_id=ticket_id,
            tenant_id="t-001",
            subject="Backup failed — storage full",
            description="S3 bucket is at 100% capacity",
            priority=SupportTicketPriority.HIGH,
            created_by="admin@company.com",
        )

    def test_create_ticket_internal(self):
        from api.backup.tenant_lifecycle import SupportTicketService
        svc = SupportTicketService(provider="internal")
        ticket = svc.create_ticket(self._make_ticket())
        self.assertEqual(ticket.status, "open")

    def test_resolve_ticket(self):
        from api.backup.tenant_lifecycle import SupportTicketService
        svc = SupportTicketService()
        svc.create_ticket(self._make_ticket("tkt-002"))
        self.assertTrue(svc.resolve_ticket("tkt-002"))
        ticket = svc.get_ticket("tkt-002")
        self.assertEqual(ticket.status, "resolved")
        self.assertIsNotNone(ticket.resolved_at)

    def test_list_tenant_tickets(self):
        from api.backup.tenant_lifecycle import SupportTicketService, SupportTicket, SupportTicketPriority
        svc = SupportTicketService()
        for i in range(3):
            t = SupportTicket(f"tkt-{i}", "t-list", f"Subject {i}",
                              "desc", SupportTicketPriority.LOW, "a@b.com")
            svc.create_ticket(t)
        tickets = svc.list_tenant_tickets("t-list")
        self.assertEqual(len(tickets), 3)

    def test_priority_enum(self):
        from api.backup.tenant_lifecycle import SupportTicketPriority
        for p in ["low","medium","high","critical"]:
            self.assertIn(p, [v.value for v in SupportTicketPriority])

    def test_ticket_to_dict(self):
        ticket = self._make_ticket()
        d = ticket.to_dict()
        self.assertIn("ticket_id", d)
        self.assertIn("priority", d)

    @patch("backup.tenant_lifecycle.requests.post")
    def test_zendesk_integration(self, mock_post):
        from api.backup.tenant_lifecycle import SupportTicketService
        mock_post.return_value = MagicMock(
            json=lambda: {"ticket": {"id": 12345}},
        )
        mock_post.return_value.raise_for_status = Mock()
        svc = SupportTicketService(
            provider="zendesk",
            api_key="test-token",
            base_url="https://company.zendesk.com",
        )
        ticket = self._make_ticket("tkt-zd")
        result = svc.create_ticket(ticket)
        self.assertEqual(result.external_id, "12345")


# ─────────────────────────────────────────────────────────
# BACKUP SDK
# ─────────────────────────────────────────────────────────

class BackupSDKTest(TestCase):
    def _make_client(self):
        from api.backup.backup_sdk import BackupClient
        return BackupClient(api_key="bk_test_key_12345",
                            base_url="https://api.test.backupsystem.io")

    def test_client_importable(self):
        from api.backup.backup_sdk import BackupClient
        self.assertTrue(callable(BackupClient))

    def test_client_init(self):
        client = self._make_client()
        self.assertEqual(client.api_key, "bk_test_key_12345")
        self.assertIsNotNone(client.backups)
        self.assertIsNotNone(client.schedules)
        self.assertIsNotNone(client.storage)
        self.assertIsNotNone(client.reports)
        self.assertIsNotNone(client.webhooks)

    def test_backup_object_from_dict(self):
        from api.backup.backup_sdk import BackupObject
        d = {"id": "bk-001", "name": "prod_backup", "status": "completed",
             "size_bytes": 1024*1024, "created_at": "2026-01-01T00:00:00Z",
             "storage_type": "s3"}
        obj = BackupObject.from_dict(d)
        self.assertEqual(obj.id, "bk-001")
        self.assertEqual(obj.status, "completed")

    def test_backup_object_to_dict(self):
        from api.backup.backup_sdk import BackupObject
        obj = BackupObject(id="bk-1", name="test", status="completed",
                           size_bytes=1024, created_at="2026-01-01",
                           storage_type="s3")
        d = obj.to_dict()
        self.assertIn("id", d)
        self.assertIn("status", d)

    @patch("backup.backup_sdk.requests.Session.request")
    def test_list_backups(self, mock_request):
        mock_request.return_value = MagicMock(
            status_code=200, ok=True, content=b"{}",
            json=lambda: {"results": [
                {"id": "bk-1", "name": "b1", "status": "completed",
                 "size_bytes": 100, "created_at": "2026-01-01", "storage_type": "s3"},
            ]},
        )
        client = self._make_client()
        backups = client.backups.list()
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].id, "bk-1")

    @patch("backup.backup_sdk.requests.Session.request")
    def test_create_backup(self, mock_request):
        mock_request.return_value = MagicMock(
            status_code=201, ok=True, content=b"{}",
            json=lambda: {"id": "bk-new", "name": "prod", "status": "pending",
                          "size_bytes": None, "created_at": "2026-05-19", "storage_type": "s3"},
        )
        client = self._make_client()
        backup = client.backups.create(name="prod", storage_type="s3")
        self.assertEqual(backup.id, "bk-new")
        self.assertEqual(backup.status, "pending")

    @patch("backup.backup_sdk.requests.Session.request")
    def test_401_raises_auth_error(self, mock_request):
        from api.backup.backup_sdk import AuthError
        mock_request.return_value = MagicMock(status_code=401, ok=False)
        client = self._make_client()
        with self.assertRaises(AuthError):
            client.backups.list()

    @patch("backup.backup_sdk.requests.Session.request")
    def test_429_raises_rate_limit_error(self, mock_request):
        from api.backup.backup_sdk import RateLimitError
        mock_request.return_value = MagicMock(
            status_code=429, ok=False,
            headers={"Retry-After": "30"},
        )
        client = self._make_client()
        with self.assertRaises(RateLimitError):
            client.backups.list()

    @patch("backup.backup_sdk.requests.Session.request")
    def test_restore_backup(self, mock_request):
        mock_request.return_value = MagicMock(
            status_code=200, ok=True, content=b"{}",
            json=lambda: {"status": "initiated", "backup_id": "bk-001"},
        )
        client = self._make_client()
        result = client.backups.restore("bk-001", target_database="prod_restored")
        self.assertEqual(result["status"], "initiated")

    @patch("backup.backup_sdk.requests.Session.request")
    def test_list_schedules(self, mock_request):
        mock_request.return_value = MagicMock(
            status_code=200, ok=True, content=b"{}",
            json=lambda: {"results": [
                {"id": "sch-1", "name": "Daily", "cron_expression": "0 0 * * *",
                 "is_active": True, "next_run_at": None},
            ]},
        )
        client = self._make_client()
        schedules = client.schedules.list()
        self.assertEqual(len(schedules), 1)
        self.assertEqual(schedules[0].cron_expression, "0 0 * * *")

    def test_sdk_exceptions_hierarchy(self):
        from api.backup.backup_sdk import BackupSDKError, AuthError, RateLimitError, NotFoundError
        self.assertTrue(issubclass(AuthError, BackupSDKError))
        self.assertTrue(issubclass(RateLimitError, BackupSDKError))
        self.assertTrue(issubclass(NotFoundError, BackupSDKError))

    def test_schedule_object_from_dict(self):
        from api.backup.backup_sdk import ScheduleObject
        d = {"id": "sch-1", "name": "Weekly", "cron_expression": "0 0 * * 0",
             "is_active": True, "next_run_at": "2026-05-26T00:00:00Z"}
        obj = ScheduleObject.from_dict(d)
        self.assertEqual(obj.name, "Weekly")
        self.assertTrue(obj.is_active)
