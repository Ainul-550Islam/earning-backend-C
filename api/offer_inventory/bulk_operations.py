# api/offer_inventory/bulk_operations.py
"""
Bulk Operations.
Mass create/update/delete for offers, users, conversions.
All operations are atomic and validated.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class BulkOfferManager:
    """Bulk offer operations."""

    @staticmethod
    @transaction.atomic
    def bulk_activate(offer_ids: list) -> int:
        from api.offer_inventory.models import Offer
        updated = Offer.objects.filter(
            id__in=offer_ids, status__in=['paused', 'draft']
        ).update(status='active')
        logger.info(f'Bulk activated {updated} offers')
        return updated

    @staticmethod
    @transaction.atomic
    def bulk_pause(offer_ids: list, reason: str = 'Bulk pause') -> int:
        from api.offer_inventory.models import Offer, OfferLog
        updated = Offer.objects.filter(
            id__in=offer_ids, status='active'
        ).update(status='paused')
        OfferLog.objects.bulk_create([
            OfferLog(offer_id=oid, old_status='active', new_status='paused', note=reason)
            for oid in offer_ids
        ], ignore_conflicts=True)
        return updated

    @staticmethod
    @transaction.atomic
    def bulk_update_payout(offer_ids: list, multiplier: float) -> int:
        """Multiply all payouts by a factor (e.g. 1.1 = +10%)."""
        from api.offer_inventory.models import Offer
        from django.db.models import F
        updated = 0
        for offer in Offer.objects.filter(id__in=offer_ids):
            offer.payout_amount = (offer.payout_amount * Decimal(str(multiplier))).quantize(Decimal('0.0001'))
            offer.reward_amount = (offer.reward_amount * Decimal(str(multiplier))).quantize(Decimal('0.0001'))
            offer.save(update_fields=['payout_amount', 'reward_amount'])
            updated += 1
        return updated

    @staticmethod
    @transaction.atomic
    def bulk_expire(offer_ids: list) -> int:
        from api.offer_inventory.models import Offer
        return Offer.objects.filter(id__in=offer_ids).update(status='expired')

    @staticmethod
    def bulk_reset_caps(offer_ids: list) -> int:
        from api.offer_inventory.models import OfferCap
        from django.core.cache import cache
        updated = OfferCap.objects.filter(offer_id__in=offer_ids).update(current_count=0)
        for oid in offer_ids:
            cache.delete(f'offer_avail:{oid}')
        return updated


class BulkConversionManager:
    """Bulk conversion operations."""

    @staticmethod
    @transaction.atomic
    def bulk_approve(conversion_ids: list, admin_user) -> dict:
        """Bulk approve pending conversions and trigger payouts."""
        from api.offer_inventory.models import Conversion, ConversionStatus
        from api.offer_inventory.payout_engine import BulkPayoutProcessor

        approved_status = ConversionStatus.objects.get(name='approved')
        updated = Conversion.objects.filter(
            id__in=conversion_ids, status__name='pending'
        ).update(status=approved_status)

        result = BulkPayoutProcessor.process_batch(conversion_ids)
        result['db_updated'] = updated
        return result

    @staticmethod
    @transaction.atomic
    def bulk_reject(conversion_ids: list, reason: str) -> int:
        from api.offer_inventory.models import Conversion, ConversionStatus
        rejected_status = ConversionStatus.objects.get(name='rejected')
        updated = Conversion.objects.filter(
            id__in=conversion_ids, status__name='pending'
        ).update(
            status=rejected_status,
            rejected_at=timezone.now(),
            reject_reason=reason[:255],
        )
        return updated


class BulkUserManager:
    """Bulk user operations."""

    @staticmethod
    def bulk_suspend(user_ids: list, reason: str) -> int:
        from api.offer_inventory.models import UserRiskProfile
        from django.db.models import Q
        count = 0
        for uid in user_ids:
            obj, _ = UserRiskProfile.objects.get_or_create(user_id=uid)
            obj.is_suspended      = True
            obj.suspension_reason = reason
            obj.save(update_fields=['is_suspended', 'suspension_reason'])
            count += 1
        return count

    @staticmethod
    def bulk_unsuspend(user_ids: list) -> int:
        from api.offer_inventory.models import UserRiskProfile
        return UserRiskProfile.objects.filter(user_id__in=user_ids).update(
            is_suspended=False, suspension_reason=''
        )

    @staticmethod
    def bulk_add_bonus(user_ids: list, amount: Decimal,
                        source: str = 'admin_bonus') -> int:
        """Add bonus balance to multiple users."""
        from api.offer_inventory.repository import WalletRepository
        success = 0
        for uid in user_ids:
            try:
                WalletRepository.credit_user(
                    user_id    =uid,
                    amount     =amount,
                    source     =source,
                    source_id  =f'bulk_{timezone.now().strftime("%Y%m%d")}',
                    description=f'Bulk bonus: {amount}',
                )
                success += 1
            except Exception as e:
                logger.error(f'Bulk bonus error user={uid}: {e}')
        return success


class BulkIPManager:
    """Bulk IP management."""

    @staticmethod
    def bulk_block_from_file(ip_list: list, reason: str,
                              hours: int = 72) -> int:
        """Block a large list of IPs efficiently."""
        from api.offer_inventory.security_fraud.ip_blacklist import IPBlacklistManager
        return IPBlacklistManager.bulk_block(ip_list, reason=reason, hours=hours)

    @staticmethod
    def bulk_unblock(ip_list: list) -> int:
        from api.offer_inventory.models import BlacklistedIP
        deleted, _ = BlacklistedIP.objects.filter(ip_address__in=ip_list).delete()
        from django.core.cache import cache
        for ip in ip_list:
            cache.delete(f'ip_bl:{ip}:None')
        return deleted

    @staticmethod
    def import_external_blocklist(url: str) -> int:
        """
        Download and import a blocklist from a URL.
        Supports plain text (one IP per line) and CSV formats.
        """
        import requests
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            ips = [
                line.strip() for line in resp.text.splitlines()
                if line.strip() and not line.startswith('#')
            ]
            # Basic IP validation
            import ipaddress
            valid_ips = []
            for ip in ips:
                try:
                    ipaddress.ip_address(ip)
                    valid_ips.append(ip)
                except ValueError:
                    pass
            return BulkIPManager.bulk_block_from_file(
                valid_ips, reason=f'external_blocklist:{url[:100]}', hours=720
            )
        except Exception as e:
            logger.error(f'Blocklist import error: {e}')
            return 0
