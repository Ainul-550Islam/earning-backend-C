from django.db.models import Sum
# api/referral/services/AdvancedReferralService.py
# World-class features: QR codes, email invites, social share, geo rates,
# sub-ID tracking, double-sided bonus, recurring commission, payout prefs
# ============================================================

import logging
import secrets
import hashlib
from decimal import Decimal
from datetime import timedelta
from typing import Optional, Dict, List
from django.db import transaction
from django.utils import timezone
from django.conf import settings as django_settings
from api.referral.models.advanced import ReferralQRCode
from api.referral.models.advanced import ReferralSubID
from api.referral.models.advanced import ReferralEmailInvitation
from api.referral.models.advanced import ReferralCommissionExpiry
from api.referral.models.advanced import RecurringCommissionLog

logger = logging.getLogger(__name__)

FRONTEND_URL = getattr(django_settings, 'FRONTEND_URL', 'https://yourplatform.com')
SITE_NAME    = getattr(django_settings, 'SITE_NAME', 'EarnPlatform')


# ── QR Code Service ────────────────────────────────────────────────────────────

class QRCodeService:
    """
    World #1 feature: QR codes for referral links.
    Starbucks, Airbnb, ReferralRock all use QR codes.
    """

    @staticmethod
    def get_or_create(referral_code_obj) -> 'ReferralQRCode':
        from api.referral.models import ReferralQRCode
        qr, created = ReferralQRCode.objects.get_or_create(
            referral_code=referral_code_obj
        )
        if created or not qr.qr_image_data:
            qr.generate_qr(base_url=FRONTEND_URL)
        return qr

    @staticmethod
    def regenerate(qr_code_obj, fg_color='#000000', bg_color='#FFFFFF') -> str:
        qr_code_obj.foreground_color = fg_color
        qr_code_obj.background_color = bg_color
        qr_code_obj.save(update_fields=['foreground_color', 'background_color'])
        return qr_code_obj.generate_qr(base_url=FRONTEND_URL)

    @staticmethod
    def record_scan(qr_code_obj) -> None:
        from django.db.models import F, Sum, F
        from api.referral.models import ReferralQRCode
        ReferralQRCode.objects.filter(id=qr_code_obj.id).update(
            scan_count=F('scan_count') + 1,
            last_scanned=timezone.now(),
        )


# ── Sub-ID Tracking Service ────────────────────────────────────────────────────

class SubIDService:
    """
    PartnerStack-style sub-ID tracking.
    Track which YouTube video / TikTok / blog post drove each referral.

    Usage:
        SubIDService.record_click(
            code=code_obj,
            sub1='youtube', sub2='tutorial_video', sub3='june_2024',
            ip=request_ip, user_agent=request.META['HTTP_USER_AGENT'],
        )
    """

    @staticmethod
    @transaction.atomic
    def record_click(
        code, ip: str = '', user_agent: str = '',
        referrer_url: str = '', landed_url: str = '',
        sub1: str = '', sub2: str = '', sub3: str = '',
        sub4: str = '', sub5: str = '',
    ) -> 'ReferralSubID':
        from api.referral.models import ReferralSubID
        return ReferralSubID.objects.create(
            code=code,
            sub1=sub1[:100], sub2=sub2[:100], sub3=sub3[:100],
            sub4=sub4[:100], sub5=sub5[:100],
            click_ip=ip or None,
            user_agent=user_agent[:500],
            referrer_url=referrer_url[:2000],
            landed_url=landed_url[:2000],
        )

    @staticmethod
    def mark_converted(sub_id_obj, referred_user) -> None:
        from django.db.models import F
        sub_id_obj.converted = True
        sub_id_obj.conversion_time = timezone.now()
        sub_id_obj.referred_user = referred_user
        sub_id_obj.save(update_fields=['converted', 'conversion_time', 'referred_user'])

    @staticmethod
    def get_performance_by_sub1(code) -> List[Dict]:
        """Which sub1 value drove the most conversions?"""
        from api.referral.models import ReferralSubID
        from django.db.models import Count, Sum
        return list(
            ReferralSubID.objects.filter(code=code)
            .values('sub1')
            .annotate(
                clicks=Count('id'),
                conversions=Sum('converted'),
            )
            .order_by('-conversions', '-clicks')
        )


# ── Geo Commission Service ─────────────────────────────────────────────────────

class GeoCommissionService:
    """
    Get commission rate based on user's country.
    Falls back to ReferralSettings default if no geo rule exists.
    """

    @staticmethod
    def get_rate_for_user(
        user, level: int = 1, role: str = 'referred'
    ) -> Decimal:
        """
        Get commission rate considering user's geo.
        role: 'referrer' or 'referred'
        """
        from api.referral.models import GeoCommissionRate, ReferralSettings

        country = GeoCommissionService._get_user_country(user)
        if country:
            try:
                rate = GeoCommissionRate.objects.get(
                    country_code=country,
                    applies_to__in=[role, 'both'],
                    is_active=True,
                )
                field_map = {1: 'level1_rate', 2: 'level2_rate', 3: 'level3_rate'}
                return getattr(rate, field_map.get(level, 'level1_rate'))
            except GeoCommissionRate.DoesNotExist:
                pass

        # Fallback to settings
        s = ReferralSettings.objects.first()
        if s:
            return s.get_rate_for_level(level)
        return Decimal('10.00')

    @staticmethod
    def _get_user_country(user) -> Optional[str]:
        """Try to get user's country code from profile."""
        try:
            return (
                getattr(user, 'country', None)
                or getattr(user, 'country_code', None)
                or getattr(getattr(user, 'profile', None), 'country', None)
                or ''
            )
        except Exception:
            return None

    @staticmethod
    def setup_default_geo_rates(tenant=None) -> int:
        """Seed common geo rates (US pays more, developing markets less)."""
        from api.referral.models import GeoCommissionRate
        default_rates = [
            {'country_code': 'US', 'country_name': 'United States',
             'level1_rate': 15, 'level2_rate': 7, 'level3_rate': 3},
            {'country_code': 'GB', 'country_name': 'United Kingdom',
             'level1_rate': 12, 'level2_rate': 6, 'level3_rate': 2},
            {'country_code': 'CA', 'country_name': 'Canada',
             'level1_rate': 12, 'level2_rate': 6, 'level3_rate': 2},
            {'country_code': 'AU', 'country_name': 'Australia',
             'level1_rate': 12, 'level2_rate': 6, 'level3_rate': 2},
            {'country_code': 'IN', 'country_name': 'India',
             'level1_rate': 8, 'level2_rate': 4, 'level3_rate': 1},
            {'country_code': 'BD', 'country_name': 'Bangladesh',
             'level1_rate': 8, 'level2_rate': 4, 'level3_rate': 1},
            {'country_code': 'PK', 'country_name': 'Pakistan',
             'level1_rate': 7, 'level2_rate': 3, 'level3_rate': 1},
        ]
        created = 0
        for rate_data in default_rates:
            _, was_created = GeoCommissionRate.objects.get_or_create(
                country_code=rate_data['country_code'],
                applies_to='referred',
                tenant=tenant,
                defaults={
                    'country_name': rate_data['country_name'],
                    'level1_rate': rate_data['level1_rate'],
                    'level2_rate': rate_data['level2_rate'],
                    'level3_rate': rate_data['level3_rate'],
                }
            )
            if was_created:
                created += 1
        return created


# ── Double-Sided Bonus Service ────────────────────────────────────────────────

class DoubleSidedBonusService:
    """
    Give BOTH referrer AND referred user a welcome bonus.
    World best practice: Dropbox, Airbnb, PayPal.
    2x higher conversion rates than single-sided programs.
    """

    @staticmethod
    @transaction.atomic
    def award_both_bonuses(
        referrer,
        referred_user,
        config=None,
    ) -> Dict:
        from api.referral.models import DoubleSidedBonusConfig
        from api.referral.INTEGRATION_SYSTEM.integ_adapter import WalletAdapter

        if config is None:
            config = DoubleSidedBonusConfig.objects.filter(is_active=True).first()

        if not config:
            # Fallback to ReferralSettings
            from api.referral.models import ReferralSettings
            s = ReferralSettings.objects.first()
            if s:
                referrer_amount = s.referrer_signup_bonus
                referred_amount = s.direct_signup_bonus
            else:
                return {'success': False, 'reason': 'no_config'}
        else:
            referrer_amount = config.referrer_bonus
            referred_amount = config.referred_bonus

        result = {'referrer_bonus': 0, 'referred_bonus': 0, 'success': True}

        # Credit referrer
        if referrer_amount > 0:
            try:
                WalletAdapter.credit_bonus(
                    user=referrer,
                    amount=referrer_amount,
                    description=f'Referral signup bonus — you referred {referred_user.username}',
                )
                result['referrer_bonus'] = float(referrer_amount)
                logger.info(
                    f'[DoubleSided] Referrer bonus: {referrer.username} ৳{referrer_amount}'
                )
            except Exception as e:
                logger.error(f'[DoubleSided] Referrer bonus failed: {e}')

        # Credit referred user (THE MISSING FEATURE)
        if referred_amount > 0:
            try:
                WalletAdapter.credit_bonus(
                    user=referred_user,
                    amount=referred_amount,
                    description=f'Welcome bonus — you were invited by {referrer.username}',
                )
                result['referred_bonus'] = float(referred_amount)
                logger.info(
                    f'[DoubleSided] Referred user bonus: {referred_user.username} ৳{referred_amount}'
                )
            except Exception as e:
                logger.error(f'[DoubleSided] Referred user bonus failed: {e}')

        return result


# ── Email Invitation Service ──────────────────────────────────────────────────

class EmailInvitationService:
    """
    Send referral email invitations.
    World #1 feature: Dropbox doubled users with email invites.
    """

    MAX_DAILY_INVITES = 20
    INVITE_EXPIRY_DAYS = 30

    @staticmethod
    @transaction.atomic
    def send_invitation(
        referrer,
        invited_email: str,
        invited_name: str = '',
        personal_message: str = '',
        referral_code=None,
    ) -> Dict:
        from api.referral.models import ReferralEmailInvitation

        # Daily limit check
        today = timezone.now().date()
        today_count = ReferralEmailInvitation.objects.filter(
            referrer=referrer,
            created_at__date=today,
        ).count()
        if today_count >= EmailInvitationService.MAX_DAILY_INVITES:
            return {
                'success': False,
                'reason': f'Daily limit of {EmailInvitationService.MAX_DAILY_INVITES} invites reached',
            }

        # Duplicate check
        existing = ReferralEmailInvitation.objects.filter(
            referrer=referrer, invited_email=invited_email.lower()
        ).first()
        if existing and existing.status not in ('expired', 'bounced'):
            return {'success': False, 'reason': 'Already invited this email', 'id': existing.id}

        # Get or create primary referral code
        if not referral_code:
            from api.referral.models import ReferralCode
            referral_code = ReferralCode.objects.filter(
                user=referrer, is_primary=True, is_active=True
            ).first()

        # Create invitation
        token = secrets.token_urlsafe(32)
        invite = ReferralEmailInvitation.objects.create(
            referrer=referrer,
            invited_email=invited_email.lower(),
            invited_name=invited_name,
            referral_code=referral_code,
            personal_message=personal_message[:500],
            tracking_token=token,
            expires_at=timezone.now() + timedelta(days=EmailInvitationService.INVITE_EXPIRY_DAYS),
        )

        # Send email
        sent = EmailInvitationService._send_email(invite)
        if sent:
            invite.status = 'sent'
            invite.sent_at = timezone.now()
            invite.save(update_fields=['status', 'sent_at'])

        return {
            'success': True,
            'invitation_id': invite.id,
            'email': invited_email,
            'sent': sent,
        }

    @staticmethod
    def _send_email(invite) -> bool:
        """Send invitation email using project's notification system."""
        try:
            from api.notifications.services import NotificationService

            code = invite.referral_code.code if invite.referral_code else ''
            signup_url = f"{FRONTEND_URL.rstrip('/')}/register?ref={code}&token={invite.tracking_token}"

            ns = NotificationService()
            ns.create_notification(
                user=invite.referrer,  # Log as referrer's notification
                title=f'{invite.referrer.username} invited you to {SITE_NAME}',
                message=(
                    f'{invite.referrer.username} thinks you\'d love {SITE_NAME}. '
                    f'{invite.personal_message}\n\n'
                    f'Sign up here: {signup_url}'
                ),
                notification_type='referral_invitation',
                priority='medium',
                channel='email',
            )
            return True
        except Exception as e:
            logger.warning(f'[EmailInvite] Send failed: {e}')
            # Fallback: Django email
            try:
                from django.core.mail import send_mail
                code = invite.referral_code.code if invite.referral_code else ''
                signup_url = f"{FRONTEND_URL.rstrip('/')}/register?ref={code}"
                send_mail(
                    subject=f'{invite.referrer.username} invited you to {SITE_NAME}',
                    message=(
                        f'Hi {invite.invited_name or "there"},\n\n'
                        f'{invite.referrer.username} invited you to join {SITE_NAME}.\n'
                        f'{invite.personal_message}\n\n'
                        f'Sign up here: {signup_url}\n\n'
                        f'This invitation expires in {EmailInvitationService.INVITE_EXPIRY_DAYS} days.'
                    ),
                    from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                    recipient_list=[invite.invited_email],
                    fail_silently=True,
                )
                return True
            except Exception:
                return False

    @staticmethod
    def track_open(token: str) -> bool:
        from api.referral.models import ReferralEmailInvitation
        from django.db.models import F
        updated = ReferralEmailInvitation.objects.filter(
            tracking_token=token,
            status__in=['sent', 'opened'],
        ).update(
            status='opened',
            opened_at=timezone.now(),
            open_count=F('open_count') + 1,
        )
        return updated > 0

    @staticmethod
    def track_click(token: str) -> Optional['ReferralEmailInvitation']:
        from api.referral.models import ReferralEmailInvitation
        from django.db.models import F
        ReferralEmailInvitation.objects.filter(
            tracking_token=token
        ).update(
            status='clicked',
            clicked_at=timezone.now(),
            click_count=F('click_count') + 1,
        )
        return ReferralEmailInvitation.objects.filter(
            tracking_token=token
        ).first()

    @staticmethod
    def bulk_send(referrer, emails: List[str], message: str = '') -> Dict:
        """Send invitations to multiple emails at once."""
        results = {'sent': 0, 'failed': 0, 'errors': []}
        for email in emails[:EmailInvitationService.MAX_DAILY_INVITES]:
            r = EmailInvitationService.send_invitation(
                referrer=referrer,
                invited_email=email,
                personal_message=message,
            )
            if r['success']:
                results['sent'] += 1
            else:
                results['failed'] += 1
                results['errors'].append({'email': email, 'reason': r.get('reason', '')})
        return results


# ── Social Share Service ──────────────────────────────────────────────────────

class SocialShareService:
    """
    Generate social share URLs and track shares.
    World #1 feature: ReferralRock shows which platform drives most referrals.
    """

    @staticmethod
    def get_share_urls(referral_code_obj) -> Dict[str, str]:
        """Get pre-filled share URLs for all platforms."""
        code = referral_code_obj.code
        referral_url = f"{FRONTEND_URL.rstrip('/')}/go/{code}/"
        message = f"Join me on {SITE_NAME} and earn rewards! Use my referral code: {code}"
        encoded_url = referral_url.replace('/', '%2F').replace(':', '%3A')
        encoded_msg = message.replace(' ', '%20').replace('!', '%21')

        return {
            'whatsapp': f"https://wa.me/?text={encoded_msg}%20{encoded_url}",
            'telegram': f"https://t.me/share/url?url={encoded_url}&text={encoded_msg}",
            'facebook': f"https://www.facebook.com/sharer/sharer.php?u={encoded_url}",
            'twitter': f"https://twitter.com/intent/tweet?text={encoded_msg}&url={encoded_url}",
            'linkedin': f"https://www.linkedin.com/sharing/share-offsite/?url={encoded_url}",
            'copy_link': referral_url,
            'sms': f"sms:?body={encoded_msg}%20{encoded_url}",
        }

    @staticmethod
    def record_share(referral_code_obj, platform: str) -> None:
        from api.referral.models import ReferralSocialShare
        from django.db.models import F
        ReferralSocialShare.objects.update_or_create(
            referral_code=referral_code_obj,
            platform=platform,
            defaults={},
        )
        ReferralSocialShare.objects.filter(
            referral_code=referral_code_obj, platform=platform
        ).update(share_count=F('share_count') + 1)

    @staticmethod
    def get_best_platform(referral_code_obj) -> Optional[str]:
        """Which platform drove the most conversions for this code?"""
        from api.referral.models import ReferralSocialShare
        best = ReferralSocialShare.objects.filter(
            referral_code=referral_code_obj
        ).order_by('-convert_count', '-click_count').first()
        return best.platform if best else None


# ── Commission Expiry Service ─────────────────────────────────────────────────

class CommissionExpiryService:
    """
    CPAlead-style: 5% commission for first 6 months only.
    After expiry, commission rate drops or stops.
    """

    @staticmethod
    def setup_expiry_for_referral(referral_obj, rule=None) -> 'ReferralCommissionExpiry':
        from api.referral.models import ReferralCommissionExpiry, CommissionExpiryRule

        if not rule:
            rule = CommissionExpiryRule.objects.filter(is_active=True).first()

        expiry_date = None
        if rule:
            if rule.expiry_months:
                expiry_date = referral_obj.created_at + timedelta(
                    days=rule.expiry_months * 30
                )
            elif rule.expiry_days:
                expiry_date = referral_obj.created_at + timedelta(days=rule.expiry_days)

        expiry, _ = ReferralCommissionExpiry.objects.get_or_create(
            referral=referral_obj,
            defaults={
                'rule': rule,
                'expires_at': expiry_date,
                'earning_cap': rule.expiry_earnings if rule else None,
            }
        )
        return expiry

    @staticmethod
    def check_and_expire_old() -> Dict:
        """Run daily — expire commissions past their window."""
        from api.referral.models import ReferralCommissionExpiry
        now = timezone.now()
        expired = ReferralCommissionExpiry.objects.filter(
            is_expired=False,
            expires_at__lt=now,
        )
        count = expired.count()
        expired.update(is_expired=True, expired_at=now)
        logger.info(f'[CommissionExpiry] Expired {count} commissions')
        return {'expired': count}

    @staticmethod
    def is_commission_allowed(referral_obj) -> bool:
        """Check if commission is still valid for this referral."""
        try:
            expiry = referral_obj.commission_expiry
            return expiry.is_commission_active()
        except Exception:
            return True  # No expiry rule = lifetime


# ── Recurring Commission Service ─────────────────────────────────────────────

class RecurringCommissionService:
    """
    Monthly recurring commissions — fire every month user is active.
    Better than one-time only: incentivizes referring ACTIVE users.
    """

    @staticmethod
    def setup_recurring(referrer, referred_user, level: int = 1, rate: Decimal = None) -> 'RecurringCommissionLog':
        from api.referral.models import RecurringCommissionLog, ReferralSettings

        if rate is None:
            s = ReferralSettings.objects.first()
            rate = s.get_rate_for_level(level) if s else Decimal('5.00')

        recurring, _ = RecurringCommissionLog.objects.get_or_create(
            referrer=referrer,
            referred_user=referred_user,
            level=level,
            defaults={
                'commission_rate': rate,
                'next_commission_at': timezone.now() + timedelta(days=30),
            }
        )
        return recurring

    @staticmethod
    def process_due_recurring() -> Dict:
        """Run monthly — pay all due recurring commissions."""
        from api.referral.models import RecurringCommissionLog
        from api.referral.INTEGRATION_SYSTEM.integ_adapter import WalletAdapter
        from django.db.models import F

        due = RecurringCommissionLog.objects.filter(
            status='active',
            next_commission_at__lte=timezone.now(),
        ).select_related('referrer', 'referred_user')

        paid = 0
        errors = 0

        for rec in due:
            # Check limits
            if rec.max_payments and rec.payment_count >= rec.max_payments:
                rec.status = 'expired'
                rec.save(update_fields=['status'])
                continue
            if rec.expires_at and timezone.now() > rec.expires_at:
                rec.status = 'expired'
                rec.save(update_fields=['status'])
                continue

            # Get referred user's last month earnings
            from api.referral.models import ReferralEarning
            last_month_start = timezone.now() - timedelta(days=30)
            earnings_sum = ReferralEarning.objects.filter(
                referred_user=rec.referred_user,
                created_at__gte=last_month_start,
            ).aggregate(t=Sum('source_amount'))['t'] or Decimal('0')

            if earnings_sum <= 0:
                # No activity — skip this month
                rec.next_commission_at = timezone.now() + timedelta(days=30)
                rec.save(update_fields=['next_commission_at'])
                continue

            commission = (earnings_sum * rec.commission_rate / 100).quantize(Decimal('0.01'))

            try:
                WalletAdapter.credit_bonus(
                    user=rec.referrer,
                    amount=commission,
                    description=f'Monthly L{rec.level} recurring commission from {rec.referred_user.username}',
                )
                RecurringCommissionLog.objects.filter(id=rec.id).update(
                    total_paid=F('total_paid') + commission,
                    payment_count=F('payment_count') + 1,
                    last_paid_at=timezone.now(),
                    next_commission_at=timezone.now() + timedelta(days=30),
                )
                paid += 1
            except Exception as e:
                errors += 1
                logger.error(f'[Recurring] Payment failed for {rec.id}: {e}')

        return {'paid': paid, 'errors': errors}