# api/cms/adapters/platform_extras.py
"""
Adapters for remaining platform systems:
  api.backup, api.promotions, api.inventory,
  api.smartlink (external), api.admin_panel
"""
import logging
from typing import Optional, Dict, Any, List

from .base import BaseAdapter

logger = logging.getLogger('api.cms.adapters')


# ══════════════════════════════════════════════════════════════════════════════
# BACKUP ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class BackupAdapter(BaseAdapter):
    """CMS → api.backup — backup/restore CMS data."""

    _system_name = 'api.backup'

    @classmethod
    def _check_available(cls):
        import api.backup  # noqa

    @classmethod
    def create_backup(cls, scope: str = 'cms', label: str = '') -> Optional[str]:
        """
        Trigger a backup of CMS data.
        Returns backup_id on success, None on failure.
        scope: 'cms' | 'cms_media' | 'cms_full'
        """
        try:
            from api.backup.services import BackupService
            backup = BackupService.create(scope=scope, label=label or f'cms_{scope}')
            return str(backup.pk) if backup else None
        except ImportError:
            return cls._unavailable('create_backup', None)
        except Exception as e:
            logger.warning("[CMS→Backup] create_backup failed: %s", e)
            return None

    @classmethod
    def get_backup_status(cls, backup_id: str) -> str:
        """Return backup status: 'pending'|'running'|'completed'|'failed'|'unknown'."""
        try:
            from api.backup.models import BackupRecord
            record = BackupRecord.objects.filter(pk=backup_id).first()
            return getattr(record, 'status', 'unknown') if record else 'unknown'
        except (ImportError, Exception):
            return 'unknown'

    @classmethod
    def list_backups(cls, scope: str = 'cms', limit: int = 20) -> List[Dict]:
        """List recent CMS backups."""
        try:
            from api.backup.models import BackupRecord
            records = BackupRecord.objects.filter(scope=scope).order_by('-created_at')[:limit]
            return [
                {
                    'id': str(r.pk),
                    'label': r.label,
                    'status': r.status,
                    'size_bytes': getattr(r, 'size_bytes', 0),
                    'created_at': r.created_at.isoformat(),
                }
                for r in records
            ]
        except (ImportError, Exception):
            return []

    @classmethod
    def restore(cls, backup_id: str, dry_run: bool = True) -> Dict:
        """
        Restore from a backup.
        Always runs dry_run=True first unless explicitly set to False.
        Returns {'success': bool, 'message': str}
        """
        try:
            from api.backup.services import BackupService
            result = BackupService.restore(backup_id=backup_id, dry_run=dry_run)
            return result or {'success': False, 'message': 'no result'}
        except ImportError:
            return {'success': False, 'message': 'backup system unavailable'}
        except Exception as e:
            logger.error("[CMS→Backup] restore(%s) failed: %s", backup_id, e)
            return {'success': False, 'message': str(e)}

    @classmethod
    def schedule_auto_backup(cls, cron_expression: str = '0 2 * * *') -> bool:
        """Schedule automatic daily CMS backups."""
        try:
            from api.backup.services import BackupService
            BackupService.schedule(scope='cms', cron=cron_expression)
            return True
        except (ImportError, Exception):
            return False


# ══════════════════════════════════════════════════════════════════════════════
# PROMOTIONS ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class PromotionsAdapter(BaseAdapter):
    """CMS → api.promotions — promo codes, discount campaigns, bonus events."""

    _system_name = 'api.promotions'

    @classmethod
    def _check_available(cls):
        import api.promotions  # noqa

    @classmethod
    def get_active_promotions(cls, user=None, placement: str = '') -> List[Dict]:
        """
        Fetch promotions active right now, optionally for a specific CMS placement.
        Returns list of promo dicts for CMS banner/popup rendering.
        """
        try:
            from api.promotions.services import PromotionsService
            return PromotionsService.get_active(user=user, placement=placement) or []
        except ImportError:
            return cls._unavailable('get_active_promotions', [])
        except Exception as e:
            logger.debug("[CMS→Promotions] get_active_promotions failed: %s", e)
            return []

    @classmethod
    def validate_promo_code(cls, code: str, user=None) -> Dict:
        """
        Validate a promo code.
        Returns {'valid': bool, 'discount_pct': float, 'bonus_coins': int, 'reason': str}
        """
        try:
            from api.promotions.services import PromotionsService
            result = PromotionsService.validate_code(code=code, user=user)
            return result or {'valid': False, 'reason': 'invalid_code'}
        except ImportError:
            return {'valid': False, 'reason': 'promotions_unavailable'}
        except Exception as e:
            logger.warning("[CMS→Promotions] validate_promo_code failed: %s", e)
            return {'valid': False, 'reason': 'error'}

    @classmethod
    def apply_promo_code(cls, code: str, user, order_amount: float = 0) -> Dict:
        """
        Apply a promo code for a user.
        Returns {'applied': bool, 'discount': float, 'bonus_coins': int}
        """
        try:
            from api.promotions.services import PromotionsService
            return PromotionsService.apply_code(code=code, user=user, amount=order_amount) or {'applied': False}
        except ImportError:
            return {'applied': False, 'reason': 'promotions_unavailable'}
        except Exception as e:
            logger.warning("[CMS→Promotions] apply_promo_code failed: %s", e)
            return {'applied': False, 'reason': str(e)}

    @classmethod
    def get_bonus_event(cls) -> Optional[Dict]:
        """
        Return the currently running bonus event (double coins, etc.)
        for CMS banner display.
        """
        try:
            from api.promotions.models import BonusEvent
            from django.utils import timezone
            now = timezone.now()
            event = BonusEvent.objects.filter(
                start_at__lte=now, end_at__gte=now, is_active=True
            ).first()
            if event:
                return {
                    'name': event.name,
                    'description': event.description,
                    'multiplier': getattr(event, 'multiplier', 1),
                    'end_at': event.end_at.isoformat(),
                    'banner_image': getattr(event, 'banner_image_url', ''),
                }
            return None
        except (ImportError, Exception):
            return None

    @classmethod
    def record_promo_impression(cls, promo_id: str, user=None, placement: str = '') -> bool:
        """Track that a user saw a promotion (for campaign analytics)."""
        try:
            from api.promotions.services import PromotionsService
            PromotionsService.record_impression(promo_id=promo_id, user=user, placement=placement)
            return True
        except (ImportError, Exception):
            return False


# ══════════════════════════════════════════════════════════════════════════════
# INVENTORY ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class InventoryAdapter(BaseAdapter):
    """CMS → api.inventory — physical/virtual inventory management."""

    _system_name = 'api.inventory'

    @classmethod
    def _check_available(cls):
        import api.inventory  # noqa

    @classmethod
    def get_item(cls, item_id: str) -> Optional[Dict]:
        """Fetch a single inventory item (for CMS product/reward display)."""
        try:
            from api.inventory.services import InventoryService
            return InventoryService.get_item(item_id=item_id)
        except (ImportError, Exception):
            return None

    @classmethod
    def get_items(cls, category: str = '', in_stock_only: bool = True, limit: int = 50) -> List[Dict]:
        """Fetch inventory items for CMS marketplace/reward catalog widgets."""
        try:
            from api.inventory.services import InventoryService
            return InventoryService.list_items(
                category=category,
                in_stock_only=in_stock_only,
                limit=limit,
            ) or []
        except (ImportError, Exception):
            return []

    @classmethod
    def check_stock(cls, item_id: str, quantity: int = 1) -> bool:
        """Check if an item has sufficient stock."""
        try:
            from api.inventory.services import InventoryService
            return InventoryService.check_stock(item_id=item_id, quantity=quantity)
        except ImportError:
            return True  # assume in stock if unavailable
        except Exception:
            return False

    @classmethod
    def reserve(cls, item_id: str, quantity: int, user=None, ref_id: str = '') -> bool:
        """Reserve inventory (e.g., before processing a reward redemption)."""
        try:
            from api.inventory.services import InventoryService
            return InventoryService.reserve(item_id=item_id, quantity=quantity, user=user, ref_id=ref_id)
        except (ImportError, Exception):
            return False

    @classmethod
    def release_reservation(cls, ref_id: str) -> bool:
        """Release a previously reserved quantity."""
        try:
            from api.inventory.services import InventoryService
            InventoryService.release_reservation(ref_id=ref_id)
            return True
        except (ImportError, Exception):
            return False

    @classmethod
    def get_categories(cls) -> List[Dict]:
        """Fetch inventory categories for CMS filter UI."""
        try:
            from api.inventory.models import InventoryCategory
            return list(
                InventoryCategory.objects.filter(is_active=True).values('slug', 'name', 'icon_url')
            )
        except (ImportError, Exception):
            return []


# ══════════════════════════════════════════════════════════════════════════════
# EXTERNAL SMARTLINK ADAPTER  (api.smartlink — NOT the CMS's own SmartLink model)
# ══════════════════════════════════════════════════════════════════════════════

class ExternalSmartLinkAdapter(BaseAdapter):
    """
    CMS → api.smartlink (the PLATFORM-LEVEL smartlink routing system).

    Note: CMS also has its OWN SmartLink model for CMS-level content routing.
    This adapter speaks to the EXTERNAL platform smartlink system only.
    """

    _system_name = 'api.smartlink'

    @classmethod
    def _check_available(cls):
        import api.smartlink  # noqa

    @classmethod
    def resolve(cls, slug: str, user=None, context: Optional[Dict] = None) -> Optional[str]:
        """
        Resolve a smartlink slug to a destination URL.
        The platform router handles geo, device, and A/B logic.
        """
        try:
            from api.smartlink.services import SmartLinkService
            return SmartLinkService.resolve(slug=slug, user=user, context=context or {})
        except ImportError:
            return None
        except Exception as e:
            logger.debug("[CMS→SmartLink] resolve(%s) failed: %s", slug, e)
            return None

    @classmethod
    def get_platform_links(cls, tag: str = '', limit: int = 20) -> List[Dict]:
        """Fetch platform-level smartlinks for embedding in CMS pages."""
        try:
            from api.smartlink.models import SmartLink as PlatformSmartLink
            qs = PlatformSmartLink.objects.filter(is_active=True)
            if tag:
                qs = qs.filter(tags__contains=tag)
            return list(qs.values('slug', 'name', 'description', 'total_clicks')[:limit])
        except (ImportError, Exception):
            return []

    @classmethod
    def record_click(cls, slug: str, user=None, ip: str = '') -> bool:
        """Record a click on a platform smartlink from a CMS page."""
        try:
            from api.smartlink.services import SmartLinkService
            SmartLinkService.record_click(slug=slug, user=user, ip=ip)
            return True
        except (ImportError, Exception):
            return False


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN PANEL ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class AdminPanelAdapter(BaseAdapter):
    """
    CMS → api.admin_panel interface.

    CMS uses this to register its models in the platform admin panel,
    and to get admin-only configuration values.
    """

    _system_name = 'api.admin_panel'

    @classmethod
    def _check_available(cls):
        import api.admin_panel  # noqa

    @classmethod
    def get_admin_config(cls, key: str, default=None):
        """Fetch a platform admin configuration value."""
        try:
            from api.admin_panel.models import AdminConfig
            config = AdminConfig.objects.filter(key=key).first()
            return config.value if config else default
        except (ImportError, Exception):
            return default

    @classmethod
    def register_cms_section(cls) -> bool:
        """
        Register the CMS section in the platform admin panel sidebar.
        Called from CMSAppConfig.ready() if admin_panel is available.
        """
        try:
            from api.admin_panel.registry import AdminRegistry
            AdminRegistry.register_section(
                section_id='cms',
                title='Content Management',
                icon='newspaper',
                order=5,
                urls_namespace='admin:api_cms_',
            )
            return True
        except (ImportError, Exception):
            return False

    @classmethod
    def get_platform_stats(cls) -> Dict:
        """Fetch high-level platform stats for the CMS dashboard header."""
        try:
            from api.admin_panel.services import AdminDashboardService
            return AdminDashboardService.get_summary() or {}
        except (ImportError, Exception):
            return {}

    @classmethod
    def log_admin_action(cls, user, action: str, target: str, detail: str = '') -> bool:
        """Log an admin action taken through CMS to the platform audit trail."""
        try:
            from api.admin_panel.services import AdminAuditService
            AdminAuditService.log(user=user, action=action, target=target, detail=detail)
            return True
        except (ImportError, Exception):
            return False
