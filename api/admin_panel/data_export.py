# api/admin_panel/data_export.py
"""
Admin Panel Data Export Engine.
Exports platform data to CSV, Excel, JSON for admin download.
Calls other apps' models — never stores data itself.
Supports: user data, transaction history, offer performance,
fraud logs, audit trail, compliance reports, custom queries.
"""
from __future__ import annotations
import csv
import io
import json
import logging
from typing import Any, Dict, List, Optional
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AdminDataExporter:
    """Central data export engine for admin_panel."""

    SUPPORTED_FORMATS = ['csv', 'json', 'xlsx']
    MAX_ROWS = 100_000

    # ── User data export ─────────────────────────────────────────────────

    @classmethod
    def export_users(cls, filters: Dict = None, fmt: str = 'csv', limit: int = 10000) -> str:
        """Export user list."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        qs = User.objects.all()
        if filters:
            qs = qs.filter(**filters)
        data = list(qs.values(
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'is_staff', 'date_joined', 'last_login'
        )[:limit])
        return cls._serialize(data, fmt, 'users')

    @classmethod
    def export_user_data(cls, user_id: Any) -> Dict:
        """Export all data for a single user (GDPR data subject access)."""
        data = {'user_id': user_id, 'exported_at': timezone.now().isoformat()}
        # User profile
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(pk=user_id)
            data['profile'] = {
                'username': user.username, 'email': user.email,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
            }
        except Exception:
            pass
        # Wallet
        try:
            from api.wallet.models import Wallet, WalletTransaction
            wallet = Wallet.objects.get(user_id=user_id)
            data['wallet'] = {'balance': float(wallet.current_balance), 'is_locked': wallet.is_locked}
            data['transactions'] = list(
                WalletTransaction.objects.filter(wallet=wallet)
                .values('amount', 'transaction_type', 'description', 'status', 'created_at')[:100]
            )
        except Exception:
            pass
        # Payouts
        try:
            from api.payout_queue.models import PayoutItem
            data['payouts'] = list(
                PayoutItem.objects.filter(user_id=user_id)
                .values('amount', 'status', 'gateway', 'created_at')[:100]
            )
        except Exception:
            pass
        # Activity
        try:
            from api.admin_panel.models.activity import AdminActivity
            data['admin_actions'] = list(
                AdminActivity.objects.filter(actor_id=user_id)
                .values('action', 'model_name', 'status', 'created_at')[:50]
            )
        except Exception:
            pass
        return data

    # ── Transaction exports ──────────────────────────────────────────────

    @classmethod
    def export_transactions(cls, filters: Dict = None, fmt: str = 'csv', limit: int = 50000) -> str:
        try:
            from api.wallet.models import WalletTransaction
            qs = WalletTransaction.objects.select_related('wallet__user').all()
            if filters:
                qs = qs.filter(**filters)
            data = list(qs.values(
                'id', 'wallet__user__username', 'amount', 'transaction_type',
                'status', 'description', 'reference', 'created_at'
            )[:limit])
            return cls._serialize(data, fmt, 'transactions')
        except Exception as e:
            return cls._serialize([], fmt, 'transactions')

    @classmethod
    def export_payouts(cls, filters: Dict = None, fmt: str = 'csv', limit: int = 10000) -> str:
        try:
            from api.payout_queue.models import PayoutItem
            qs = PayoutItem.objects.select_related('user').all()
            if filters:
                qs = qs.filter(**filters)
            data = list(qs.values(
                'id', 'user__username', 'amount', 'status',
                'gateway', 'gateway_reference', 'created_at'
            )[:limit])
            return cls._serialize(data, fmt, 'payouts')
        except Exception:
            return ''

    # ── Fraud exports ────────────────────────────────────────────────────

    @classmethod
    def export_fraud_logs(cls, filters: Dict = None, fmt: str = 'csv', limit: int = 20000) -> str:
        try:
            from api.fraud_detection.models import FraudAttempt
            qs = FraudAttempt.objects.all()
            if filters:
                qs = qs.filter(**filters)
            data = list(qs.values(
                'id', 'user_id', 'ip_address', 'attempt_type', 'fraud_score', 'created_at'
            )[:limit])
            return cls._serialize(data, fmt, 'fraud_logs')
        except Exception:
            return ''

    # ── Audit log export ─────────────────────────────────────────────────

    @classmethod
    def export_audit_log(cls, filters: Dict = None, fmt: str = 'csv', limit: int = 50000) -> str:
        try:
            from api.admin_panel.models.activity import AdminActivity
            qs = AdminActivity.objects.select_related('actor').all()
            if filters:
                qs = qs.filter(**filters)
            data = list(qs.values(
                'id', 'actor__username', 'action', 'model_name', 'object_id',
                'status', 'ip', 'method', 'path', 'created_at'
            )[:limit])
            return cls._serialize(data, fmt, 'audit_log')
        except Exception:
            return ''

    # ── Offer performance export ─────────────────────────────────────────

    @classmethod
    def export_offer_performance(cls, days: int = 30, fmt: str = 'csv') -> str:
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.promotions.models import TaskSubmission
            from django.db.models import Count, Sum
            data = list(
                TaskSubmission.objects.filter(created_at__gte=cutoff)
                .values('campaign_id', 'campaign__title', 'status')
                .annotate(count=Count('id'), total_payout=Sum('reward_amount'))
                .order_by('-total_payout')
            )
            return cls._serialize(data, fmt, 'offer_performance')
        except Exception:
            return ''

    # ── DataExport model processing ──────────────────────────────────────

    @classmethod
    def process_export(cls, export_id: int) -> bool:
        """Process a DataExport model record."""
        try:
            from api.admin_panel.models.reports import DataExport
            export = DataExport.objects.get(pk=export_id)
            export.status = 'processing'
            export.save(update_fields=['status'])

            # Map model_name to export method
            method_map = {
                'auth.User':        cls.export_users,
                'wallet.Wallet':    cls.export_transactions,
                'payout_queue.PayoutItem': cls.export_payouts,
                'fraud.FraudAttempt': cls.export_fraud_logs,
                'admin.AdminActivity': cls.export_audit_log,
            }
            export_fn = method_map.get(export.model_name, cls.export_users)
            content = export_fn(fmt=export.format)

            # Save to file
            import os
            from django.conf import settings
            filename = f"admin_export_{export_id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.{export.format}"
            path = os.path.join(settings.MEDIA_ROOT, 'admin_exports', filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            mode = 'wb' if isinstance(content, bytes) else 'w'
            with open(path, mode) as f:
                f.write(content)

            export.file_path = path
            export.file_size_bytes = os.path.getsize(path)
            export.status = 'ready'
            export.completed_at = timezone.now()
            export.save()
            return True
        except Exception as e:
            logger.error(f"[DataExport.process] {export_id}: {e}")
            try:
                from api.admin_panel.models.reports import DataExport
                DataExport.objects.filter(pk=export_id).update(status='failed', error_message=str(e)[:500])
            except Exception:
                pass
            return False

    # ── Serialization ────────────────────────────────────────────────────

    @classmethod
    def _serialize(cls, data: List[Dict], fmt: str, name: str) -> str:
        if fmt == 'json':
            return json.dumps(data, ensure_ascii=False, default=str, indent=2)
        elif fmt == 'xlsx':
            return cls._to_xlsx(data, name)
        else:
            return cls._to_csv(data)

    @staticmethod
    def _to_csv(data: List[Dict]) -> str:
        if not data:
            return ''
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(data[0].keys()), extrasaction='ignore')
        writer.writeheader()
        for row in data:
            writer.writerow({k: str(v) if v is not None else '' for k, v in row.items()})
        return output.getvalue()

    @staticmethod
    def _to_xlsx(data: List[Dict], sheet_name: str = 'Export') -> bytes:
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = sheet_name[:31]
            if data:
                headers = list(data[0].keys())
                ws.append(headers)
                for row in data:
                    ws.append([str(row.get(h, '')) for h in headers])
            buf = io.BytesIO()
            wb.save(buf)
            return buf.getvalue()
        except ImportError:
            return b''