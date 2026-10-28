# api/cms/data_export.py
"""Data export utilities for CMS."""
from django.http import StreamingHttpResponse
from typing import Generator
import logging
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
import csv
import json
import io
import zipfile
import tempfile
import os

from api.cms.abstracts import BaseService
from api.cms.monitoring import CMSMetrics
from api.cms.caching import CMSCache

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Original Data Export (Preserved) ─────────────────────────────────────

class DataExporter:
    """Base class for CMS data exporters."""
    CHUNK_SIZE = 1000  # Process N rows at a time

    @classmethod
    def to_csv_response(cls, filename: str, rows: List[Dict],
                         fields: List[str] = None) -> HttpResponse:
        """Create a downloadable CSV HTTP response."""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        if not rows:
            return response
        fields = fields or list(rows[0].keys())
        writer = csv.DictWriter(response, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow(cls._stringify_row(row))
        return response

    @classmethod
    def to_json_response(cls, filename: str, data: Any) -> HttpResponse:
        """Create a downloadable JSON HTTP response."""
        response = HttpResponse(
            json.dumps(data, default=str, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @classmethod
    def _stringify_row(cls, row: Dict) -> Dict:
        """Convert all values to strings for CSV export."""
        result = {}
        for k, v in row.items():
            if isinstance(v, Decimal):
                result[k] = f"{v:.4f}"
            elif v is None:
                result[k] = ''
            else:
                result[k] = str(v)
        return result

    @classmethod
    def streaming_csv(cls, filename: str,
                       row_generator: Generator) -> StreamingHttpResponse:
        """Stream large CSV exports without loading into memory."""
        def _iter(headers, gen):
            yield ','.join(headers) + '\n'
            for row in gen:
                yield ','.join(str(v).replace(',', ';') for v in row) + '\n'

        response = StreamingHttpResponse(
            streaming_content=row_generator,
            content_type='text/csv'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class UserDataExporter(DataExporter):
    """GDPR-compliant user data export."""

    @classmethod
    def export_user_data(cls, user) -> Dict:
        """
        Export all data for a user (GDPR Article 20 — data portability).
        Returns complete user data package.
        """
        from api.cms.encryption import PIIProtection
        data = {
            'exported_at': timezone.now().isoformat(),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
            },
            'profile': cls._get_profile_data(user),
            'virtual_balance': cls._get_balance_data(user),
            'transactions': cls._get_transaction_history(user),
            'conversions': cls._get_conversion_history(user),
            'withdrawals': cls._get_withdrawal_history(user),
            'quiz_attempts': cls._get_quiz_history(user),
            'referrals': cls._get_referral_data(user),
        }
        return data

    @classmethod
    def _get_profile_data(cls, user) -> Dict:
        try:
            from api.cms.models_new.withdrawal import UserProfile
            p = UserProfile.objects.get(user=user)
            return {
                'level': p.level,
                'total_earned_usd': float(p.total_earned_usd),
                'total_earned_coins': float(p.total_earned_coins),
                'total_withdrawn_usd': float(p.total_withdrawn_usd),
                'total_offers_completed': p.total_offers_completed,
                'kyc_status': p.kyc_status,
            }
        except Exception:
            return {}

    @classmethod
    def _get_balance_data(cls, user) -> Dict:
        try:
            from api.cms.models_new.cpalead import UserVirtualBalance
            bal = UserVirtualBalance.objects.get(user=user)
            return {
                'balance': float(bal.balance),
                'currency': bal.currency,
                'usd_value': float(bal.currency.virtual_to_usd(bal.balance)),
            }
        except Exception:
            return {'balance': 0}

    @classmethod
    def _get_transaction_history(cls, user) -> List[Dict]:
        try:
            from api.cms.models_new.cpalead import VirtualTransaction
            txns = VirtualTransaction.objects.filter(user=user).order_by('-created_at')[:500]
            return [{
                'type': t.tx_type, 'amount': float(t.amount),
                'balance_after': float(t.balance_after),
                'description': t.description,
                'created_at': t.created_at.isoformat(),
            } for t in txns]
        except Exception:
            return []

    @classmethod
    def _get_conversion_history(cls, user) -> List[Dict]:
        try:
            from api.cms.models_new.cpalead import ConversionLog
            convs = ConversionLog.objects.filter(user=user).order_by('-created_at')[:200]
            return [{
                'lead_id': c.lead_id,
                'payout_usd': float(c.payout_usd),
                'coins_earned': float(c.virtual_amount_awarded),
                'status': c.status,
                'created_at': c.created_at.isoformat(),
            } for c in convs]
        except Exception:
            return []

    @classmethod
    def _get_withdrawal_history(cls, user) -> List[Dict]:
        try:
            from api.cms.models_new.withdrawal import WithdrawalRequest
            from api.cms.encryption import PIIProtection
            wds = WithdrawalRequest.objects.filter(user=user).order_by('-created_at')[:100]
            return [{
                'method': w.method,
                'account': PIIProtection.mask_account_id(w.account_id),
                'amount_usd': float(w.net_usd),
                'status': w.status,
                'created_at': w.created_at.isoformat(),
            } for w in wds]
        except Exception:
            return []

    @classmethod
    def _get_quiz_history(cls, user) -> List[Dict]:
        try:
            from api.cms.models_new.quiz import QuizAttempt
            attempts = QuizAttempt.objects.filter(
                user=user, is_completed=True
            ).select_related('quiz', 'result').order_by('-completed_at')[:50]
            return [{
                'quiz_title': a.quiz.title,
                'result': a.result.title if a.result else '',
                'reward_coins': float(a.reward_coins),
                'completed_at': a.completed_at.isoformat() if a.completed_at else '',
            } for a in attempts]
        except Exception:
            return []

    @classmethod
    def _get_referral_data(cls, user) -> Dict:
        try:
            from api.cms.services_new.ReferralService import ReferralService
            return ReferralService.get_referral_stats(user)
        except Exception:
            return {}


class AdminDataExporter(DataExporter):
    """Admin-level reports and exports."""

    @classmethod
    def export_conversions_csv(cls, days: int = 30) -> HttpResponse:
        """Export conversion log as CSV."""
        from api.cms.models_new.cpalead import ConversionLog
        import datetime
        cutoff = timezone.now() - datetime.timedelta(days=days)
        rows = list(
            ConversionLog.objects
            .filter(status='approved', created_at__gte=cutoff)
            .values('id', 'subid', 'lead_id', 'payout_usd',
                    'virtual_amount_awarded', 'campaign_id', 'created_at')
            .order_by('-created_at')[:10000]
        )
        filename = f"conversions_{timezone.now().strftime('%Y%m%d')}.csv"
        return cls.to_csv_response(filename, rows)

    @classmethod
    def export_withdrawals_csv(cls, days: int = 30) -> HttpResponse:
        """Export withdrawal requests as CSV."""
        from api.cms.models_new.withdrawal import WithdrawalRequest
        from api.cms.encryption import PIIProtection
        import datetime
        cutoff = timezone.now() - datetime.timedelta(days=days)
        raw_qs = WithdrawalRequest.objects.filter(
            created_at__gte=cutoff
        ).select_related('user').order_by('-created_at')[:5000]
        rows = [{
            'id': w.id,
            'username': w.user.username,
            'method': w.method,
            'account': PIIProtection.mask_account_id(w.account_id),
            'coins': float(w.requested_coins),
            'usd': float(w.net_usd),
            'status': w.status,
            'created_at': w.created_at.isoformat(),
        } for w in raw_qs]
        filename = f"withdrawals_{timezone.now().strftime('%Y%m%d')}.csv"
        return cls.to_csv_response(filename, rows)

    @classmethod
    def export_user_report(cls) -> HttpResponse:
        """Export user summary report."""
        from api.cms.models_new.withdrawal import UserProfile
        profiles = UserProfile.objects.select_related('user').all()[:10000]
        rows = [{
            'user_id': p.user_id,
            'username': p.user.username,
            'level': p.level,
            'total_earned_usd': float(p.total_earned_usd),
            'total_earned_coins': float(p.total_earned_coins),
            'offers_completed': p.total_offers_completed,
            'kyc_status': p.kyc_status,
            'is_suspended': p.is_suspended,
            'date_joined': p.user.date_joined.isoformat(),
        } for p in profiles]
        filename = f"users_{timezone.now().strftime('%Y%m%d')}.csv"
        return cls.to_csv_response(filename, rows)


# ── Enhanced Data Export Classes ─────────────────────────────────────

class BaseDataExporter(BaseService):
    """Base data exporter class with common functionality."""
    
    def __init__(self):
        """Initialize data exporter."""
        super().__init__()
        self.metrics = CMSMetrics
        self.cache = CMSCache
    
    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input data."""
        return data
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute data export."""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def export_data(self, data: List[Dict[str, Any]], format: str = 'csv') -> Union[HttpResponse, bytes]:
        """Export data in specified format."""
        if format == 'csv':
            return self._export_csv(data)
        elif format == 'json':
            return self._export_json(data)
        elif format == 'excel':
            return self._export_excel(data)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _export_csv(self, data: List[Dict[str, Any]]) -> HttpResponse:
        """Export data as CSV."""
        if not data:
            return HttpResponse("No data to export", content_type="text/plain")
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        
        writer.writeheader()
        writer.writerows(data)
        
        response = HttpResponse(
            output.getvalue(),
            content_type='text/csv'
        )
        response['Content-Disposition'] = 'attachment; filename="export.csv"'
        return response
    
    def _export_json(self, data: List[Dict[str, Any]]) -> HttpResponse:
        """Export data as JSON."""
        response = HttpResponse(
            json.dumps(data, indent=2, default=str),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="export.json"'
        return response
    
    def _export_excel(self, data: List[Dict[str, Any]]) -> HttpResponse:
        """Export data as Excel (mock implementation)."""
        # This would use a library like openpyxl or xlsxwriter
        # For now, return CSV as fallback
        return self._export_csv(data)


class UserDataExporter(BaseDataExporter):
    """Export user data."""
    
    def export_user_data(self, user_id: int, export_type: str = 'profile', format: str = 'csv') -> HttpResponse:
        """Export user data."""
        try:
            user = User.objects.get(id=user_id)
            
            if export_type == 'profile':
                data = self._get_user_profile_data(user)
            elif export_type == 'activity':
                data = self._get_user_activity_data(user)
            elif export_type == 'transactions':
                data = self._get_user_transaction_data(user)
            elif export_type == 'surveys':
                data = self._get_user_survey_data(user)
            else:
                raise ValueError(f"Unknown export type: {export_type}")
            
            # Record metrics
            self.metrics.increment(f'user_data_export_{export_type}')
            
            logger.info(f"User data exported: {user.username}, type: {export_type}")
            
            return self.export_data(data, format)
            
        except User.DoesNotExist:
            return HttpResponse("User not found", status=404)
        except Exception as e:
            logger.error(f"Error exporting user data: {e}")
            return HttpResponse("Export failed", status=500)
    
    def _get_user_profile_data(self, user) -> List[Dict[str, Any]]:
        """Get user profile data."""
        try:
            from api.cms.models_new import UserProfile
            profile = user.extended_profile
            
            return [{
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'is_active': user.is_active,
                'bio': profile.bio if profile else None,
                'country': profile.country if profile else None,
                'level': profile.level if profile else 1,
                'total_earned_usd': float(profile.total_earned_usd) if profile else 0,
                'total_offers_completed': profile.total_offers_completed if profile else 0,
                'is_verified': profile.is_verified if profile else False,
                'created_at': profile.created_at.isoformat() if profile else None,
                'updated_at': profile.updated_at.isoformat() if profile else None
            }]
        except Exception as e:
            logger.error(f"Error getting user profile data: {e}")
            return []
    
    def _get_user_activity_data(self, user) -> List[Dict[str, Any]]:
        """Get user activity data."""
        try:
            from api.cms.models_new.analytics import UserActivity
            
            activities = UserActivity.objects.filter(user=user).order_by('-activity_date')[:1000]
            
            return [
                {
                    'user_id': user.id,
                    'activity_type': activity.activity_type,
                    'activity_date': activity.activity_date.isoformat(),
                    'metadata': activity.metadata,
                    'created_at': activity.created_at.isoformat()
                }
                for activity in activities
            ]
        except Exception as e:
            logger.error(f"Error getting user activity data: {e}")
            return []
    
    def _get_user_transaction_data(self, user) -> List[Dict[str, Any]]:
        """Get user transaction data."""
        try:
            from api.cms.models_new.rewards import RewardTransaction
            
            transactions = RewardTransaction.objects.filter(user=user).order_by('-created_at')[:1000]
            
            return [
                {
                    'user_id': user.id,
                    'amount': float(transaction.amount),
                    'transaction_type': transaction.transaction_type,
                    'status': transaction.status,
                    'source': transaction.source,
                    'reference_id': transaction.reference_id,
                    'description': transaction.description,
                    'created_at': transaction.created_at.isoformat(),
                    'processed_at': transaction.processed_at.isoformat() if transaction.processed_at else None
                }
                for transaction in transactions
            ]
        except Exception as e:
            logger.error(f"Error getting user transaction data: {e}")
            return []
    
    def _get_user_survey_data(self, user) -> List[Dict[str, Any]]:
        """Get user survey data."""
        try:
            from api.cms.models_new.survey import SurveyCompletion
            
            completions = SurveyCompletion.objects.filter(user=user).order_by('-completed_at')[:1000]
            
            return [
                {
                    'user_id': user.id,
                    'survey_id': completion.survey.id,
                    'survey_title': completion.survey.title,
                    'status': completion.status,
                    'started_at': completion.started_at.isoformat(),
                    'completed_at': completion.completed_at.isoformat() if completion.completed_at else None,
                    'duration': completion.duration,
                    'created_at': completion.created_at.isoformat()
                }
                for completion in completions
            ]
        except Exception as e:
            logger.error(f"Error getting user survey data: {e}")
            return []


# ── Enhanced Data Export Manager ─────────────────────────────────────

class EnhancedDataExportManager:
    """Manager for handling data exports."""
    
    def __init__(self):
        """Initialize data export manager."""
        self.user_exporter = UserDataExporter()
        self.logger = logging.getLogger(f"{__name__}.manager")
    
    def export_user_data(self, user_id: int, export_type: str = 'profile', format: str = 'csv') -> HttpResponse:
        """Export user data."""
        return self.user_exporter.export_user_data(user_id, export_type, format)
    
    def get_export_history(self, user_id: int = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get export history."""
        try:
            # This would query actual export history from database
            # For now, return mock data
            return [
                {
                    'id': 1,
                    'export_type': 'user_profile',
                    'format': 'csv',
                    'status': 'completed',
                    'file_size': 1024,
                    'created_at': timezone.now().isoformat(),
                    'expires_at': (timezone.now() + timezone.timedelta(days=7)).isoformat()
                }
            ]
        except Exception as e:
            self.logger.error(f"Error getting export history: {e}")
            return []
    
    def get_export_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get export statistics."""
        try:
            # This would query actual export statistics from database
            # For now, return mock data
            return {
                'period_days': days,
                'total_exports': 0,
                'user_exports': 0,
                'system_exports': 0,
                'csv_exports': 0,
                'json_exports': 0,
                'excel_exports': 0,
                'total_size_mb': 0.0
            }
        except Exception as e:
            self.logger.error(f"Error getting export statistics: {e}")
            return {
                'period_days': days,
                'total_exports': 0,
                'user_exports': 0,
                'system_exports': 0,
                'csv_exports': 0,
                'json_exports': 0,
                'excel_exports': 0,
                'total_size_mb': 0.0,
                'error': str(e)
            }


# Global enhanced data export manager
enhanced_data_export_manager = EnhancedDataExportManager()
