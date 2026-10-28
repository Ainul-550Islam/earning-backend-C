# =============================================================================
# api/wallet/services.py এর add_referral_commission METHOD PATCH
# 
# PROBLEM: hardcoded COMMISSION_RATES = {1: 0.10, 2: 0.05, 3: 0.02}
#          ReferralSettings কে সম্পূর্ণ ignore করে।
#
# FIX: নিচের code দিয়ে wallet/services.py এর add_referral_commission replace করুন।
# "এক মালিক — api.referral.models.ReferralSettings"
# =============================================================================

# wallet/services.py এর ভেতরে এই method টি replace করুন:
"""
    @staticmethod
    def add_referral_commission(wallet, amount, level: int, referred_user_id,
                                source_task_id='', source_earning_id=''):
        \"\"\"
        Referral commission add করো।
        Rates এখন api.referral.ReferralSettings থেকে আসে (hardcoded নয়)।
        \"\"\"
        from decimal import Decimal
        amount = Decimal(str(amount))

        # ── Get rate from api.referral.ReferralSettings ───────────────────
        try:
            from django.core.cache import cache
            settings_obj = cache.get('referral_settings')
            if not settings_obj:
                from api.referral.models import ReferralSettings
                settings_obj = ReferralSettings.objects.first()
                if settings_obj:
                    cache.set('referral_settings', settings_obj, timeout=300)

            if settings_obj:
                rate = settings_obj.get_rate_for_level(level) / Decimal('100')
            else:
                # Fallback only if settings don't exist yet
                fallback = {1: Decimal('0.10'), 2: Decimal('0.05'), 3: Decimal('0.02')}
                rate = fallback.get(level, Decimal('0'))
        except Exception:
            fallback = {1: Decimal('0.10'), 2: Decimal('0.05'), 3: Decimal('0.02')}
            rate = fallback.get(level, Decimal('0'))

        commission = amount * rate
        if commission <= Decimal('0'):
            return None

        return WalletService.add_earnings(
            wallet=wallet,
            amount=commission,
            description=f"Level {level} referral commission ({int(rate * 100)}%)",
            source_type='referral',
            source_id=str(referred_user_id),
            metadata={
                'referral_level': level,
                'commission_rate': str(rate),
                'source_task_id': str(source_task_id),
                'source_earning_id': str(source_earning_id),
                'referred_user_id': str(referred_user_id),
            }
        )
"""