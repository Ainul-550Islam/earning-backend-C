# api/users/services/UserEnhancedService.py
# ============================================================
# User System নতুন features:
# 1. Profile Completion Score
# 2. Daily Streak System
# 3. Tier Benefit Enforcement
# 4. Social Login (Facebook, Google)
# ============================================================

from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from datetime import timedelta, date
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# 1. PROFILE COMPLETION SCORE
# ──────────────────────────────────────────────────────────────

class ProfileCompletionService:
    """
    Profile কতটা complete হয়েছে calculate করো।
    বেশি complete → বেশি features unlock।
    """

    FIELDS = {
        'email':            {'weight': 15, 'label': 'Email'},
        'phone':            {'weight': 10, 'label': 'Phone Number'},
        'avatar':           {'weight': 5,  'label': 'Profile Picture'},
        'country':          {'weight': 5,  'label': 'Country'},
        'bio':              {'weight': 5,  'label': 'Bio'},
        'date_of_birth':    {'weight': 5,  'label': 'Date of Birth'},
        'kyc_verified':     {'weight': 30, 'label': 'KYC Verification'},
        'phone_verified':   {'weight': 10, 'label': 'Phone Verified'},
        'email_verified':   {'weight': 10, 'label': 'Email Verified'},
        '2fa_enabled':      {'weight': 5,  'label': '2FA Security'},
    }

    # Score threshold → feature unlock
    UNLOCK_THRESHOLDS = {
        30:  'basic_withdraw',       # Minimum withdrawal unlock
        50:  'offer_wall',           # Offerwall access
        70:  'higher_offers',        # Higher payout offers
        90:  'vip_support',          # Priority support
        100: 'max_daily_limit',      # Maximum daily earning limit
    }

    @classmethod
    def calculate(cls, user) -> dict:
        """User এর profile completion % calculate করো"""
        score = 0
        completed = []
        missing = []

        # User fields check
        if user.email:
            score += cls.FIELDS['email']['weight']
            completed.append('email')
        else:
            missing.append(cls.FIELDS['email'])

        if user.phone:
            score += cls.FIELDS['phone']['weight']
            completed.append('phone')
        else:
            missing.append(cls.FIELDS['phone'])

        if user.avatar:
            score += cls.FIELDS['avatar']['weight']
            completed.append('avatar')
        else:
            missing.append(cls.FIELDS['avatar'])

        if user.country:
            score += cls.FIELDS['country']['weight']
            completed.append('country')
        else:
            missing.append(cls.FIELDS['country'])

        # Profile fields
        try:
            from api.users.models import UserProfile
            profile = UserProfile.objects.filter(user=user).first()
            if profile:
                if profile.bio:
                    score += cls.FIELDS['bio']['weight']
                    completed.append('bio')
                else:
                    missing.append(cls.FIELDS['bio'])

                if profile.date_of_birth:
                    score += cls.FIELDS['date_of_birth']['weight']
                    completed.append('date_of_birth')
                else:
                    missing.append(cls.FIELDS['date_of_birth'])

                if profile.phone_verified:
                    score += cls.FIELDS['phone_verified']['weight']
                    completed.append('phone_verified')
                else:
                    missing.append(cls.FIELDS['phone_verified'])

                if profile.email_verified:
                    score += cls.FIELDS['email_verified']['weight']
                    completed.append('email_verified')
                else:
                    missing.append(cls.FIELDS['email_verified'])
        except Exception:
            pass

        # KYC check
        try:
            from api.users.models import KYCVerification
            kyc = KYCVerification.objects.filter(user=user, verification_status='approved').first()
            if kyc:
                score += cls.FIELDS['kyc_verified']['weight']
                completed.append('kyc_verified')
            else:
                missing.append(cls.FIELDS['kyc_verified'])
        except Exception:
            missing.append(cls.FIELDS['kyc_verified'])

        # 2FA check
        try:
            from api.users.models import SecuritySettings
            sec = SecuritySettings.objects.filter(user=user, two_factor_enabled=True).first()
            if sec:
                score += cls.FIELDS['2fa_enabled']['weight']
                completed.append('2fa_enabled')
            else:
                missing.append(cls.FIELDS['2fa_enabled'])
        except Exception:
            missing.append(cls.FIELDS['2fa_enabled'])

        # Unlocked features
        unlocked = [feature for threshold, feature in cls.UNLOCK_THRESHOLDS.items() if score >= threshold]

        return {
            'score': score,
            'percentage': score,
            'completed': completed,
            'missing': missing[:3],  # Top 3 যা complete করলে score বাড়বে
            'unlocked_features': unlocked,
            'next_unlock': cls._get_next_unlock(score),
        }

    @classmethod
    def _get_next_unlock(cls, current_score: int) -> dict:
        for threshold, feature in cls.UNLOCK_THRESHOLDS.items():
            if current_score < threshold:
                return {
                    'feature': feature,
                    'required_score': threshold,
                    'points_needed': threshold - current_score,
                }
        return {}

    @classmethod
    def can_access_feature(cls, user, feature: str) -> bool:
        """User নির্দিষ্ট feature access করতে পারবে কিনা"""
        data = cls.calculate(user)
        return feature in data['unlocked_features']


# ──────────────────────────────────────────────────────────────
# 2. DAILY STREAK SYSTEM
# ──────────────────────────────────────────────────────────────

class StreakService:
    """
    প্রতিদিন login করলে streak বাড়ে।
    Streak bonus: 7 days → extra 10%, 30 days → extra 25%
    """

    STREAK_REWARDS = {
        3:  Decimal('5.00'),    # 3 days → ৳5 bonus
        7:  Decimal('15.00'),   # 7 days → ৳15 bonus
        14: Decimal('30.00'),   # 14 days → ৳30 bonus
        30: Decimal('100.00'),  # 30 days → ৳100 bonus
        60: Decimal('250.00'),  # 60 days → ৳250 bonus
    }

    @classmethod
    @transaction.atomic
    def record_daily_login(cls, user) -> dict:
        """
        User login করলে call করো।
        Streak update করো এবং milestone bonus দাও।
        """
        try:
            from api.users.models import UserStatistics
            stats, _ = UserStatistics.objects.select_for_update().get_or_create(user=user)

            today = date.today()
            yesterday = today - timedelta(days=1)
            last_active = stats.last_active_date

            if last_active == today:
                # আজকে already logged in
                return {
                    'streak': stats.current_streak,
                    'already_checked_in': True,
                    'bonus': None,
                }

            if last_active == yesterday:
                # Consecutive day → streak বাড়াও
                stats.current_streak += 1
            else:
                # Streak broken
                stats.current_streak = 1

            stats.last_active_date = today
            stats.days_active += 1

            if stats.current_streak > stats.longest_streak:
                stats.longest_streak = stats.current_streak

            stats.save(update_fields=['current_streak', 'longest_streak', 'last_active_date', 'days_active'])

            # Milestone bonus check
            bonus_result = cls._check_milestone_bonus(user, stats.current_streak)

            return {
                'streak': stats.current_streak,
                'longest_streak': stats.longest_streak,
                'already_checked_in': False,
                'bonus': bonus_result,
                'message': cls._streak_message(stats.current_streak),
            }

        except Exception as e:
            logger.error(f"Streak record error for user {user.id}: {e}")
            return {'streak': 0, 'error': str(e)}

    @classmethod
    def _check_milestone_bonus(cls, user, current_streak: int) -> dict:
        """Milestone এ bonus দাও"""
        if current_streak not in cls.STREAK_REWARDS:
            return None

        bonus_amount = cls.STREAK_REWARDS[current_streak]

        try:
            from api.wallet.services import WalletService
            from api.wallet.models import Wallet

            wallet, _ = Wallet.objects.get_or_create(user=user)
            WalletService.add_earnings(
                wallet=wallet,
                amount=bonus_amount,
                description=f"🔥 {current_streak} দিনের streak bonus!",
                source_type='streak_bonus',
                source_id=str(current_streak),
            )
            logger.info(f"Streak bonus given: user={user.id}, streak={current_streak}, bonus={bonus_amount}")
            return {
                'milestone': current_streak,
                'amount': float(bonus_amount),
                'message': f"🎉 {current_streak} দিনের streak! ৳{bonus_amount} bonus পেয়েছেন!",
            }
        except Exception as e:
            logger.error(f"Streak bonus error: {e}")
            return None

    @classmethod
    def _streak_message(cls, streak: int) -> str:
        if streak == 1:
            return "Welcome back! Streak শুরু হয়েছে 🔥"
        if streak < 7:
            return f"{streak} দিনের streak! চালিয়ে যান!"
        if streak < 30:
            return f"দারুণ! {streak} দিনের streak! 🔥🔥"
        return f"অবিশ্বাস্য! {streak} দিনের streak! 🏆"

    @classmethod
    def get_streak_info(cls, user) -> dict:
        """Streak dashboard info"""
        try:
            from api.users.models import UserStatistics
            stats = UserStatistics.objects.filter(user=user).first()
            if not stats:
                return {'current_streak': 0, 'longest_streak': 0}

            next_milestone = None
            for days in sorted(cls.STREAK_REWARDS.keys()):
                if stats.current_streak < days:
                    next_milestone = {
                        'days': days,
                        'reward': float(cls.STREAK_REWARDS[days]),
                        'days_remaining': days - stats.current_streak,
                    }
                    break

            return {
                'current_streak': stats.current_streak,
                'longest_streak': stats.longest_streak,
                'last_active': str(stats.last_active_date) if stats.last_active_date else None,
                'next_milestone': next_milestone,
                'all_milestones': {k: float(v) for k, v in cls.STREAK_REWARDS.items()},
            }
        except Exception as e:
            logger.error(f"Streak info error: {e}")
            return {'current_streak': 0}


# ──────────────────────────────────────────────────────────────
# 3. TIER BENEFIT ENFORCEMENT
# ──────────────────────────────────────────────────────────────

class TierService:
    """
    User tier (FREE/BRONZE/SILVER/GOLD/PLATINUM) অনুযায়ী
    benefits enforce করো।
    """

    TIER_CONFIG = {
        'FREE':     {'reward_multiplier': 1.0,  'daily_limit': 200,   'withdrawal_fee': 2.0,  'min_withdrawal': 100},
        'BRONZE':   {'reward_multiplier': 1.05, 'daily_limit': 300,   'withdrawal_fee': 1.5,  'min_withdrawal': 80},
        'SILVER':   {'reward_multiplier': 1.10, 'daily_limit': 500,   'withdrawal_fee': 1.0,  'min_withdrawal': 50},
        'GOLD':     {'reward_multiplier': 1.15, 'daily_limit': 1000,  'withdrawal_fee': 0.5,  'min_withdrawal': 30},
        'PLATINUM': {'reward_multiplier': 1.20, 'daily_limit': 5000,  'withdrawal_fee': 0.0,  'min_withdrawal': 10},
    }

    TIER_REQUIREMENTS = {
        'BRONZE':   {'total_earned': 500,   'days_active': 7},
        'SILVER':   {'total_earned': 2000,  'days_active': 30},
        'GOLD':     {'total_earned': 10000, 'days_active': 90},
        'PLATINUM': {'total_earned': 50000, 'days_active': 180},
    }

    @classmethod
    def get_tier_config(cls, user) -> dict:
        tier = getattr(user, 'tier', 'FREE')
        return cls.TIER_CONFIG.get(tier, cls.TIER_CONFIG['FREE'])

    @classmethod
    @transaction.atomic
    def check_and_upgrade_tier(cls, user) -> dict:
        """
        User এর earning দেখে tier upgrade করো।
        Task complete হলে বা daily check এ call করো।
        """
        try:
            from api.users.models import UserStatistics
            stats = UserStatistics.objects.filter(user=user).first()
            if not stats:
                return {'upgraded': False}

            current_tier = getattr(user, 'tier', 'FREE')
            tier_order = ['FREE', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM']
            current_idx = tier_order.index(current_tier)

            new_tier = current_tier
            for tier in reversed(tier_order[1:]):  # PLATINUM থেকে শুরু
                req = cls.TIER_REQUIREMENTS.get(tier, {})
                if (float(stats.total_earned) >= req.get('total_earned', 0) and
                        stats.days_active >= req.get('days_active', 0)):
                    new_tier = tier
                    break

            if new_tier != current_tier and tier_order.index(new_tier) > current_idx:
                user.tier = new_tier
                user.save(update_fields=['tier'])

                # Upgrade bonus দাও
                upgrade_bonus = {'BRONZE': 50, 'SILVER': 200, 'GOLD': 500, 'PLATINUM': 2000}
                bonus = upgrade_bonus.get(new_tier, 0)
                if bonus:
                    from api.wallet.services import WalletService
                    from api.wallet.models import Wallet
                    wallet, _ = Wallet.objects.get_or_create(user=user)
                    WalletService.add_earnings(
                        wallet=wallet,
                        amount=Decimal(str(bonus)),
                        description=f"🎊 {new_tier} tier upgrade bonus!",
                        source_type='tier_upgrade',
                    )

                logger.info(f"Tier upgraded: user={user.id} {current_tier} → {new_tier}")
                return {
                    'upgraded': True,
                    'old_tier': current_tier,
                    'new_tier': new_tier,
                    'bonus': bonus,
                    'message': f"🎉 Congratulations! {new_tier} tier এ upgrade হয়েছেন!",
                }

            return {'upgraded': False, 'current_tier': current_tier}

        except Exception as e:
            logger.error(f"Tier upgrade check error: {e}")
            return {'upgraded': False}

    @classmethod
    def get_tier_progress(cls, user) -> dict:
        """পরের tier এ কতটুকু বাকি"""
        try:
            from api.users.models import UserStatistics
            stats = UserStatistics.objects.filter(user=user).first()
            current_tier = getattr(user, 'tier', 'FREE')
            config = cls.get_tier_config(user)

            tier_order = ['FREE', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM']
            current_idx = tier_order.index(current_tier)

            next_tier = tier_order[current_idx + 1] if current_idx < 4 else None
            next_req = cls.TIER_REQUIREMENTS.get(next_tier, {}) if next_tier else {}

            total_earned = float(stats.total_earned) if stats else 0
            days_active = stats.days_active if stats else 0

            return {
                'current_tier': current_tier,
                'next_tier': next_tier,
                'benefits': config,
                'progress': {
                    'earning': {
                        'current': total_earned,
                        'required': next_req.get('total_earned', 0),
                        'percentage': min(100, (total_earned / next_req['total_earned'] * 100)) if next_req.get('total_earned') else 100,
                    },
                    'days': {
                        'current': days_active,
                        'required': next_req.get('days_active', 0),
                        'percentage': min(100, (days_active / next_req['days_active'] * 100)) if next_req.get('days_active') else 100,
                    }
                } if next_tier else None,
            }
        except Exception as e:
            logger.error(f"Tier progress error: {e}")
            return {'current_tier': 'FREE'}


# ──────────────────────────────────────────────────────────────
# 4. SOCIAL LOGIN HANDLER
# ──────────────────────────────────────────────────────────────

class SocialLoginService:
    """
    Facebook + Google OAuth handler।
    Frontend থেকে access_token আসবে, এখানে verify হবে।

    pip install requests
    settings.py:
      FACEBOOK_APP_ID = 'your_app_id'
      FACEBOOK_APP_SECRET = 'your_secret'
    """

    @staticmethod
    def verify_google_token(id_token: str) -> dict:
        """
        Google ID token verify করো।
        Frontend → Google Sign-In → id_token → এখানে পাঠাও।
        """
        import requests
        try:
            resp = requests.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}",
                timeout=10
            )
            data = resp.json()

            if 'error' in data or resp.status_code != 200:
                return {'valid': False, 'error': data.get('error', 'Invalid token')}

            return {
                'valid': True,
                'email': data.get('email'),
                'name': data.get('name'),
                'picture': data.get('picture'),
                'google_id': data.get('sub'),
                'email_verified': data.get('email_verified') == 'true',
            }
        except Exception as e:
            logger.error(f"Google token verify error: {e}")
            return {'valid': False, 'error': str(e)}

    @staticmethod
    def verify_facebook_token(access_token: str) -> dict:
        """
        Facebook access token verify করো।
        Frontend → Facebook Login → access_token → এখানে পাঠাও।
        """
        import requests
        from django.conf import settings as django_settings

        app_id = getattr(django_settings, 'FACEBOOK_APP_ID', '')
        app_secret = getattr(django_settings, 'FACEBOOK_APP_SECRET', '')

        try:
            # Token verify করো
            verify_resp = requests.get(
                f"https://graph.facebook.com/debug_token?input_token={access_token}&access_token={app_id}|{app_secret}",
                timeout=10
            )
            verify_data = verify_resp.json().get('data', {})

            if not verify_data.get('is_valid'):
                return {'valid': False, 'error': 'Invalid Facebook token'}

            # User info পাও
            user_resp = requests.get(
                f"https://graph.facebook.com/me?fields=id,name,email,picture&access_token={access_token}",
                timeout=10
            )
            user_data = user_resp.json()

            if 'error' in user_data:
                return {'valid': False, 'error': user_data['error'].get('message')}

            return {
                'valid': True,
                'email': user_data.get('email'),
                'name': user_data.get('name'),
                'picture': user_data.get('picture', {}).get('data', {}).get('url'),
                'facebook_id': user_data.get('id'),
            }
        except Exception as e:
            logger.error(f"Facebook token verify error: {e}")
            return {'valid': False, 'error': str(e)}

    @staticmethod
    @transaction.atomic
    def get_or_create_social_user(provider: str, social_data: dict,
                                   referral_code: str = None) -> tuple:
        """
        Social login user তৈরি বা existing user return করো।
        Returns: (user, created, tokens)
        """
        from django.contrib.auth import get_user_model
        from api.users.services.TokenService import TokenService
        User = get_user_model()

        email = social_data.get('email')
        if not email:
            raise ValueError("Email not provided by social provider")

        # Existing user খোঁজো
        user = User.objects.filter(email=email).first()
        created = False

        if not user:
            # নতুন user তৈরি করো
            import re, secrets
            base_username = re.sub(r'[^a-zA-Z0-9]', '', social_data.get('name', '').lower())[:15]
            username = base_username or 'user'

            # Unique username ensure করো
            if User.objects.filter(username=username).exists():
                username = f"{username}_{secrets.token_hex(3)}"

            user = User.objects.create_user(
                username=username,
                email=email,
                password=User.objects.make_random_password(),
                is_verified=True,
            )
            user.country = social_data.get('country', '')
            user.save()
            created = True

            # Profile picture save করো
            if social_data.get('picture'):
                try:
                    from api.users.models import UserProfile
                    profile, _ = UserProfile.objects.get_or_create(user=user)
                    profile.email_verified = True
                    profile.save()
                except Exception:
                    pass

            # Referral process করো
            if referral_code:
                try:
                    referrer = User.objects.get(referral_code=referral_code)
                    from api.referral.services import ReferralService
                    ReferralService.process_signup_with_fraud_check(user, referrer)
                except Exception:
                    pass

        tokens = TokenService.generate_tokens(user)
        return user, created, tokens