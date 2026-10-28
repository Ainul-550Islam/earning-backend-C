# api/referral/data_export.py
# Full data export for referral module — CSV, Excel, JSON
# Used by admin export endpoint + scheduled reports
# ============================================================

import csv
import json
import logging
from decimal import Decimal
from io import StringIO, BytesIO
from typing import Any, Dict, List, Optional
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class ReferralDataExport:
    """
    Export referral data in multiple formats.
    Used by admin panel for reporting and compliance.
    """

    # ── CSV Exports ───────────────────────────────────────────────────────────

    @staticmethod
    def export_referrals_csv(
        tenant=None, from_date=None, to_date=None,
        include_suspicious: bool = False,
    ) -> str:
        """Export referral relationships to CSV string."""
        from api.referral.models import Referral

        qs = Referral.objects.select_related(
            'referrer', 'referred_user', 'tenant'
        ).order_by('-created_at')

        if tenant:
            qs = qs.filter(tenant=tenant)
        if from_date:
            qs = qs.filter(created_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(created_at__date__lte=to_date)
        if not include_suspicious:
            qs = qs.filter(is_suspicious=False)

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'id', 'referrer_username', 'referrer_email',
            'referred_username', 'referred_email',
            'level', 'signup_bonus_given', 'total_commission_earned',
            'is_suspicious', 'registration_ip', 'created_at',
        ])

        for r in qs.iterator(chunk_size=500):
            writer.writerow([
                r.id,
                r.referrer.username,
                r.referrer.email,
                r.referred_user.username,
                r.referred_user.email,
                r.level,
                r.signup_bonus_given,
                float(r.total_commission_earned),
                r.is_suspicious,
                r.registration_ip or '',
                r.created_at.isoformat(),
            ])

        return output.getvalue()

    @staticmethod
    def export_commissions_csv(
        user=None, tenant=None, status: str = None,
        from_date=None, to_date=None,
    ) -> str:
        """Export commission logs to CSV string."""
        from api.referral.models import CommissionLog

        qs = CommissionLog.objects.select_related(
            'user', 'referred_user', 'campaign'
        ).order_by('-created_at')

        if user:
            qs = qs.filter(user=user)
        if tenant:
            qs = qs.filter(tenant=tenant)
        if status:
            qs = qs.filter(status=status)
        if from_date:
            qs = qs.filter(created_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(created_at__date__lte=to_date)

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'id', 'user', 'referred_user', 'level',
            'amount', 'base_amount', 'commission_rate_pct',
            'action_type', 'status', 'campaign',
            'wallet_transaction_id', 'created_at', 'updated_at',
        ])

        for c in qs.iterator(chunk_size=500):
            writer.writerow([
                c.id,
                c.user.username,
                c.referred_user.username,
                c.level,
                float(c.amount),
                float(c.base_amount),
                float(c.commission_rate * 100),
                c.action_type,
                c.status,
                c.campaign.name if c.campaign else '',
                c.wallet_transaction_id or '',
                c.created_at.isoformat(),
                c.updated_at.isoformat(),
            ])

        return output.getvalue()

    @staticmethod
    def export_fraud_report_csv(from_date=None, to_date=None) -> str:
        """Export suspicious referrals for audit."""
        from api.referral.models import SuspiciousReferral

        qs = SuspiciousReferral.objects.select_related(
            'referral__referrer', 'referral__referred_user', 'reviewed_by'
        ).order_by('-detected_at')

        if from_date:
            qs = qs.filter(detected_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(detected_at__date__lte=to_date)

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'id', 'referral_id', 'referrer', 'referred_user',
            'fraud_score', 'status', 'flags', 'review_notes',
            'reviewed_by', 'reviewed_at', 'detected_at',
        ])

        for sr in qs.iterator(chunk_size=200):
            writer.writerow([
                sr.id,
                sr.referral_id,
                sr.referral.referrer.username,
                sr.referral.referred_user.username,
                sr.fraud_score,
                sr.status,
                json.dumps(sr.flags),
                sr.review_notes,
                sr.reviewed_by.username if sr.reviewed_by else '',
                sr.reviewed_at.isoformat() if sr.reviewed_at else '',
                sr.detected_at.isoformat(),
            ])

        return output.getvalue()

    @staticmethod
    def export_leaderboard_csv(period: str = 'weekly') -> str:
        """Export top referrers leaderboard."""
        from api.referral.models import TopReferrer

        today = timezone.now().date()
        qs = TopReferrer.objects.filter(
            period=period, date=today
        ).select_related('user').order_by('rank')

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'rank', 'username', 'email',
            'referral_count', 'commission_earned', 'rank_change', 'date',
        ])

        for entry in qs:
            writer.writerow([
                entry.rank,
                entry.user.username,
                entry.user.email,
                entry.referral_count,
                float(entry.commission_earned),
                entry.rank_change,
                str(entry.date),
            ])

        return output.getvalue()

    # ── JSON Exports ──────────────────────────────────────────────────────────

    @staticmethod
    def export_user_data_json(user) -> Dict:
        """
        GDPR Article 20 — Data portability.
        Export all referral data for a specific user.
        """
        from api.referral.models import (
            Referral, ReferralEarning, CommissionLog,
            ReferralCode, ReferralEmailInvitation,
        )

        return {
            'export_date':      timezone.now().isoformat(),
            'user':             user.username,
            'referral_codes': list(
                ReferralCode.objects.filter(user=user).values(
                    'code', 'is_primary', 'clicks', 'conversions', 'created_at',
                )
            ),
            'referrals_made': list(
                Referral.objects.filter(referrer=user).values(
                    'referred_user__username', 'level',
                    'total_commission_earned', 'created_at',
                )
            ),
            'commission_history': list(
                CommissionLog.objects.filter(user=user).values(
                    'amount', 'level', 'status', 'action_type',
                    'referred_user__username', 'created_at',
                )
            ),
            'invitations_sent': list(
                ReferralEmailInvitation.objects.filter(referrer=user).values(
                    'invited_email', 'status', 'sent_at', 'converted_at',
                )
            ),
        }

    @staticmethod
    def export_queryset_to_csv(qs) -> str:
        """
        Generic queryset to CSV export.
        Uses model field names as headers.
        """
        if not qs.exists():
            return ''

        model = qs.model
        fields = [f.name for f in model._meta.fields
                  if f.name not in ('password',)]

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(fields)

        for obj in qs.values(*fields).iterator(chunk_size=500):
            row = []
            for field in fields:
                val = obj[field]
                if isinstance(val, Decimal):
                    val = float(val)
                elif hasattr(val, 'isoformat'):
                    val = val.isoformat()
                row.append(val)
            writer.writerow(row)

        return output.getvalue()

    # ── Excel Export ──────────────────────────────────────────────────────────

    @staticmethod
    def export_to_excel(data: List[Dict], sheet_name: str = 'Referrals') -> Optional[bytes]:
        """
        Export data to Excel file (.xlsx).
        Returns bytes or None if openpyxl not installed.
        """
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = sheet_name

            if not data:
                buffer = BytesIO()
                wb.save(buffer)
                return buffer.getvalue()

            # Headers
            headers = list(data[0].keys())
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header.replace('_', ' ').title())
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
                cell.font = Font(bold=True, color='FFFFFF')
                cell.alignment = Alignment(horizontal='center')

            # Data
            for row_idx, row_data in enumerate(data, 2):
                for col_idx, key in enumerate(headers, 1):
                    val = row_data.get(key, '')
                    if isinstance(val, Decimal):
                        val = float(val)
                    ws.cell(row=row_idx, column=col_idx, value=val)

            # Auto-size columns
            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

            buffer = BytesIO()
            wb.save(buffer)
            return buffer.getvalue()

        except ImportError:
            logger.debug('[Export] openpyxl not installed — Excel export disabled')
            return None