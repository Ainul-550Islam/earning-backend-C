# =============================================================================
# api/offer_inventory/models.py এর UserReferral, ReferralCommission, CommissionTier
# এই তিনটি class কে REPLACE করুন নিচের stub দিয়ে।
# "এক মালিক — api.referral"
#
# আপনার offer_inventory/models.py তে এই তিনটি class খুঁজে replace করুন:
# =============================================================================

# ── api/offer_inventory/models.py এ class গুলো replace করুন ──────────────

"""
# ── UserReferral (DEPRECATED — use api.referral.Referral) ──────────────────
class UserReferral(models.Model):
    \"\"\"
    DEPRECATED: এই model টি আর use করবেন না।
    api.referral.models.Referral ব্যবহার করুন।
    Backward compat এর জন্য রাখা হয়েছে — নতুন code লিখবেন না।
    \"\"\"
    class Meta:
        # Django managed=False করা হলে migration তৈরি হবে না
        # কিন্তু backward compat এর জন্য DB তে থাকবে
        app_label = 'offer_inventory'
        db_table = 'offer_inventory_userreferral'

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='offer_referrals_made', null=True, blank=True
    )
    referred = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='offer_referral_received', null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def get_canonical_referral(self):
        \"\"\"api.referral.Referral থেকে data আনো।\"\"\"
        try:
            from api.referral.models import Referral
            return Referral.objects.filter(
                referred_user=self.referred
            ).select_related('referrer').first()
        except Exception:
            return None


# ── ReferralCommission (DEPRECATED — use api.referral.CommissionLog) ────────
class ReferralCommission(models.Model):
    \"\"\"
    DEPRECATED: api.referral.models.CommissionLog ব্যবহার করুন।
    Backward compat এর জন্য রাখা হয়েছে।
    \"\"\"
    class Meta:
        app_label = 'offer_inventory'
        db_table = 'offer_inventory_referralcommission'

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='offer_commissions_received', null=True, blank=True
    )
    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='offer_commissions_triggered', null=True, blank=True
    )
    amount = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)


# ── CommissionTier (DEPRECATED — use api.referral.CommissionRule) ────────────
class CommissionTier(models.Model):
    \"\"\"
    DEPRECATED: api.referral.models.CommissionRule ব্যবহার করুন।
    \"\"\"
    class Meta:
        app_label = 'offer_inventory'
        db_table = 'offer_inventory_commissiontier'

    name = models.CharField(max_length=100, default='')
    min_referrals = models.IntegerField(default=0)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    is_active = models.BooleanField(default=True)
\"\"\"
"""