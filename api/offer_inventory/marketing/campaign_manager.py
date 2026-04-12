# api/offer_inventory/marketing/campaign_manager.py
"""
Marketing Campaign Manager.
Create, schedule, and track marketing campaigns targeting
offer inventory users. Supports email, push, SMS, and in-app.
"""
import logging
import uuid
from decimal import Decimal
from datetime import timedelta
from django.db import models, transaction
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ── Campaign Model-like dataclass (uses existing Notification + EmailLog) ─────

class MarketingCampaignService:
    """
    Marketing campaign lifecycle:
    Create → Schedule → Execute → Track → Report
    """

    # ── Audience building ──────────────────────────────────────────

    @staticmethod
    def build_audience(criteria: dict) -> list:
        """
        Build a targeted user audience from criteria.
        criteria = {
            'min_earnings': 100,       # minimum lifetime earnings
            'country': 'BD',           # country filter
            'last_active_days': 30,    # active within N days
            'loyalty_level': 'Gold',   # loyalty tier
            'no_offer_days': 7,        # didn't do offer in N days
            'has_kyc': True,
            'segment_id': 'uuid',      # from UserSegment
        }
        Returns list of user IDs.
        """
        from django.contrib.auth import get_user_model
        from api.offer_inventory.models import (
            UserProfile, UserKYC, ChurnRecord, UserSegment
        )
        from django.db.models import Q
        from api.wallet.models import Wallet

        User = get_user_model()
        qs   = User.objects.filter(is_active=True)

        min_earnings = criteria.get('min_earnings')
        if min_earnings is not None:
            qs = qs.filter(
                wallet_wallet_user__total_earned__gte=Decimal(str(min_earnings))
            )

        country = criteria.get('country')
        if country:
            qs = qs.filter(
                offer_clicks__country_code=country
            ).distinct()

        last_active = criteria.get('last_active_days')
        if last_active:
            since = timezone.now() - timedelta(days=last_active)
            qs    = qs.filter(last_login__gte=since)

        has_kyc = criteria.get('has_kyc')
        if has_kyc is True:
            qs = qs.filter(kyc_profile__status='approved')
        elif has_kyc is False:
            qs = qs.exclude(kyc_profile__status='approved')

        no_offer_days = criteria.get('no_offer_days')
        if no_offer_days:
            since = timezone.now() - timedelta(days=no_offer_days)
            qs    = qs.exclude(conversions__created_at__gte=since)

        return list(qs.values_list('id', flat=True).distinct()[:50000])

    # ── In-app notification campaign ───────────────────────────────

    @staticmethod
    @transaction.atomic
    def send_in_app_campaign(title: str, body: str, user_ids: list,
                              notif_type: str = 'offer',
                              action_url: str = '') -> dict:
        """Send in-app notifications to a user segment."""
        from api.offer_inventory.models import Notification

        batch_size = 500
        total      = 0
        for i in range(0, len(user_ids), batch_size):
            batch = user_ids[i:i + batch_size]
            objs  = [
                Notification(
                    user_id   =uid,
                    notif_type=notif_type,
                    title     =title,
                    body      =body,
                    action_url=action_url,
                )
                for uid in batch
            ]
            Notification.objects.bulk_create(objs, batch_size=batch_size)
            total += len(batch)

        logger.info(f'In-app campaign sent: "{title}" → {total} users')
        return {'sent': total, 'title': title}

    # ── Email campaign ─────────────────────────────────────────────

    @staticmethod
    def send_email_campaign(subject: str, template: str,
                             user_ids: list, context: dict = None) -> dict:
        """
        Queue email campaign for all users.
        Uses EmailLog for tracking.
        """
        from api.offer_inventory.models import EmailLog
        from django.contrib.auth import get_user_model
        User = get_user_model()

        users = User.objects.filter(id__in=user_ids).only('email', 'id')
        logs  = []
        for user in users:
            if not user.email:
                continue
            logs.append(EmailLog(
                recipient=user.email,
                subject  =subject,
                template =template,
                status   ='queued',
            ))

        EmailLog.objects.bulk_create(logs, batch_size=500)
        total = len(logs)

        # Queue actual email sending
        from api.offer_inventory.tasks import send_email_batch
        send_email_batch.delay(subject, template, user_ids, context or {})

        logger.info(f'Email campaign queued: "{subject}" → {total} recipients')
        return {'queued': total}

    # ── Push notification campaign ─────────────────────────────────

    @staticmethod
    def send_push_campaign(title: str, body: str,
                            user_ids: list, icon_url: str = '',
                            click_url: str = '') -> dict:
        """Send browser push notifications to subscribed users."""
        from api.offer_inventory.models import PushSubscription

        subscriptions = PushSubscription.objects.filter(
            user_id__in=user_ids, is_active=True
        ).select_related('user')

        sent = 0
        for sub in subscriptions:
            try:
                success = MarketingCampaignService._send_web_push(
                    endpoint =sub.endpoint,
                    p256dh   =sub.p256dh_key,
                    auth     =sub.auth_key,
                    title    =title,
                    body     =body,
                    icon     =icon_url,
                    url      =click_url,
                )
                if success:
                    sent += 1
            except Exception as e:
                logger.debug(f'Push send error {sub.user_id}: {e}')

        logger.info(f'Push campaign: "{title}" → {sent}/{subscriptions.count()} sent')
        return {'sent': sent, 'total_subscriptions': subscriptions.count()}

    @staticmethod
    def _send_web_push(endpoint: str, p256dh: str, auth: str,
                        title: str, body: str, icon: str = '',
                        url: str = '') -> bool:
        """Fire a Web Push notification."""
        try:
            from pywebpush import webpush, WebPushException
            import json
            from django.conf import settings
            payload = json.dumps({
                'title': title, 'body': body, 'icon': icon, 'url': url
            })
            webpush(
                subscription_info={'endpoint': endpoint, 'keys': {'p256dh': p256dh, 'auth': auth}},
                data=payload,
                vapid_private_key=getattr(settings, 'VAPID_PRIVATE_KEY', ''),
                vapid_claims={'sub': f'mailto:{getattr(settings, "VAPID_EMAIL", "admin@platform.com")}'},
            )
            return True
        except Exception:
            return False

    # ── Reactivation campaign ──────────────────────────────────────

    @staticmethod
    def run_reactivation_campaign(inactive_days: int = 14,
                                   bonus_amount: Decimal = Decimal('5')) -> dict:
        """
        Auto reactivation: find inactive users → send offer + bonus.
        """
        # Find churned users
        from api.offer_inventory.models import ChurnRecord
        since  = timezone.now() - timedelta(days=inactive_days)
        churn  = ChurnRecord.objects.filter(
            last_active__lt=since,
            is_churned=True,
            reactivation_sent=False,
        ).values_list('user_id', flat=True)[:5000]

        user_ids = list(churn)
        if not user_ids:
            return {'sent': 0, 'bonus_given': 0}

        # Send in-app
        MarketingCampaignService.send_in_app_campaign(
            title     ='আমরা আপনাকে মিস করছি! 🎁',
            body      =f'ফিরে আসুন এবং {bonus_amount} টাকা বোনাস পান!',
            user_ids  =user_ids,
            notif_type='offer',
            action_url='/offers',
        )

        # Give bonus
        given = 0
        from api.offer_inventory.repository import WalletRepository
        for uid in user_ids:
            try:
                WalletRepository.credit_user(
                    user_id    =uid,
                    amount     =bonus_amount,
                    source     ='reactivation_bonus',
                    source_id  =f'react_{timezone.now().strftime("%Y%m%d")}',
                    description='ফিরে আসার বোনাস',
                )
                given += 1
            except Exception:
                pass

        # Mark sent
        ChurnRecord.objects.filter(user_id__in=user_ids).update(
            reactivation_sent=True
        )

        logger.info(f'Reactivation campaign: {len(user_ids)} targeted, {given} bonus given')
        return {'targeted': len(user_ids), 'bonus_given': given}
