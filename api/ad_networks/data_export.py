"""
api/ad_networks/data_export.py
Data export functionality for ad networks module
SaaS-ready with tenant support
"""

import logging
import csv
import json
import zipfile
import io
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, BinaryIO
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Sum, Avg, F
from django.http import HttpResponse
from django.core.cache import cache

from .models import (
    AdNetwork, Offer, OfferCategory, UserOfferEngagement,
    OfferConversion, OfferReward, UserWallet, OfferClick,
    OfferTag, OfferTagging, NetworkAPILog
)
from .choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus
)
from .constants import CACHE_TIMEOUTS
from .helpers import get_cache_key

logger = logging.getLogger(__name__)
User = get_user_model()


# ==================== EXPORT FORMATS ====================

class ExportFormat:
    """Supported export formats"""
    
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"
    PDF = "pdf"
    XML = "xml"
    ZIP = "zip"


# ==================== EXPORT TYPES ====================

class ExportType:
    """Export types"""
    
    OFFERS = "offers"
    USERS = "users"
    CONVERSIONS = "conversions"
    REWARDS = "rewards"
    ANALYTICS = "analytics"
    TRANSACTIONS = "transactions"
    REPORTS = "reports"


# ==================== BASE EXPORT MANAGER ====================

class BaseExportManager:
    """Base export manager"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.cache_timeout = CACHE_TIMEOUTS.get('export', 1800)  # 30 minutes
    
    def _get_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key"""
        return get_cache_key(self.__class__.__name__, self.tenant_id, *args, **kwargs)
    
    def _get_from_cache(self, key: str) -> Any:
        """Get data from cache"""
        return cache.get(key)
    
    def _set_cache(self, key: str, data: Any, timeout: int = None) -> None:
        """Set data in cache"""
        timeout = timeout or self.cache_timeout
        cache.set(key, data, timeout)
    
    def _serialize_datetime(self, dt: datetime) -> str:
        """Serialize datetime for export"""
        if dt is None:
            return ''
        return dt.isoformat()
    
    def _serialize_decimal(self, value: Decimal) -> Union[str, float]:
        """Serialize decimal for export"""
        if value is None:
            return 0
        return float(value)
    
    def _generate_filename(self, export_type: str, format_type: str, 
                          start_date: datetime = None, end_date: datetime = None) -> str:
        """Generate filename for export"""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        
        if start_date and end_date:
            date_range = f"_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"
        else:
            date_range = ''
        
        return f"{export_type}{date_range}_{timestamp}.{format_type}"


# ==================== OFFER EXPORT MANAGER ====================

class OfferExportManager(BaseExportManager):
    """Export manager for offers"""
    
    def export_offers(self, format_type: str = ExportFormat.CSV, 
                      filters: Dict[str, Any] = None,
                      start_date: datetime = None, end_date: datetime = None) -> Union[HttpResponse, bytes]:
        """Export offers data"""
        try:
            # Get offers queryset
            queryset = self._get_offers_queryset(filters, start_date, end_date)
            
            # Prepare data
            data = self._prepare_offers_data(queryset)
            
            # Export in specified format
            if format_type == ExportFormat.CSV:
                return self._export_csv(data, 'offers', start_date, end_date)
            elif format_type == ExportFormat.JSON:
                return self._export_json(data, 'offers', start_date, end_date)
            elif format_type == ExportFormat.EXCEL:
                return self._export_excel(data, 'offers', start_date, end_date)
            else:
                raise ValueError(f"Unsupported export format: {format_type}")
                
        except Exception as e:
            logger.error(f"Error exporting offers: {str(e)}")
            raise
    
    def _get_offers_queryset(self, filters: Dict[str, Any] = None,
                           start_date: datetime = None, end_date: datetime = None):
        """Get offers queryset"""
        queryset = Offer.objects.filter(tenant_id=self.tenant_id)
        
        # Apply date range filter
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Apply filters
        if filters:
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            if 'category_id' in filters:
                queryset = queryset.filter(category_id=filters['category_id'])
            if 'is_featured' in filters:
                queryset = queryset.filter(is_featured=filters['is_featured'])
            if 'is_hot' in filters:
                queryset = queryset.filter(is_hot=filters['is_hot'])
        
        return queryset.select_related('category').prefetch_related('tags')
    
    def _prepare_offers_data(self, queryset) -> List[Dict[str, Any]]:
        """Prepare offers data for export"""
        data = []
        
        for offer in queryset:
            offer_data = {
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'reward_amount': self._serialize_decimal(offer.reward_amount),
                'reward_currency': offer.reward_currency,
                'category': offer.category.name if offer.category else '',
                'platforms': ', '.join(offer.platforms),
                'device_type': offer.device_type,
                'difficulty': offer.difficulty,
                'estimated_time': offer.estimated_time,
                'steps_required': offer.steps_required,
                'countries': ', '.join(offer.countries),
                'min_age': offer.min_age,
                'max_age': offer.max_age,
                'is_featured': offer.is_featured,
                'is_hot': offer.is_hot,
                'is_new': offer.is_new,
                'tags': ', '.join([tag.name for tag in offer.tags.all()]),
                'requirements': offer.requirements,
                'terms_url': offer.terms_url,
                'privacy_url': offer.privacy_url,
                'click_url': offer.click_url,
                'preview_url': offer.preview_url,
                'status': offer.status,
                'created_at': self._serialize_datetime(offer.created_at),
                'updated_at': self._serialize_datetime(offer.updated_at),
                'expires_at': self._serialize_datetime(offer.expires_at),
                'performance_score': offer.performance_score,
                'total_conversions': offer.total_conversions,
                'conversion_rate': offer.conversion_rate,
            }
            data.append(offer_data)
        
        return data
    
    def _export_csv(self, data: List[Dict[str, Any]], export_type: str,
                   start_date: datetime = None, end_date: datetime = None) -> HttpResponse:
        """Export data as CSV"""
        if not data:
            return HttpResponse('No data to export', content_type='text/plain')
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        
        for row in data:
            writer.writerow(row)
        
        # Create response
        filename = self._generate_filename(export_type, ExportFormat.CSV, start_date, end_date)
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    
    def _export_json(self, data: List[Dict[str, Any]], export_type: str,
                    start_date: datetime = None, end_date: datetime = None) -> HttpResponse:
        """Export data as JSON"""
        json_data = {
            'export_type': export_type,
            'tenant_id': self.tenant_id,
            'export_date': timezone.now().isoformat(),
            'date_range': {
                'start': self._serialize_datetime(start_date),
                'end': self._serialize_datetime(end_date),
            },
            'total_records': len(data),
            'data': data,
        }
        
        filename = self._generate_filename(export_type, ExportFormat.JSON, start_date, end_date)
        response = HttpResponse(
            json.dumps(json_data, indent=2, default=str),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    
    def _export_excel(self, data: List[Dict[str, Any]], export_type: str,
                     start_date: datetime = None, end_date: datetime = None) -> HttpResponse:
        """Export data as Excel"""
        try:
            import pandas as pd
            
            if not data:
                return HttpResponse('No data to export', content_type='text/plain')
            
            # Create DataFrame
            df = pd.DataFrame(data)
            
            # Create Excel file in memory
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Offers', index=False)
                
                # Add metadata sheet
                metadata = {
                    'Export Type': export_type,
                    'Tenant ID': self.tenant_id,
                    'Export Date': timezone.now().isoformat(),
                    'Start Date': self._serialize_datetime(start_date),
                    'End Date': self._serialize_datetime(end_date),
                    'Total Records': len(data),
                }
                
                metadata_df = pd.DataFrame(list(metadata.items()), columns=['Property', 'Value'])
                metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
            
            # Create response
            filename = self._generate_filename(export_type, ExportFormat.EXCEL, start_date, end_date)
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except ImportError:
            logger.error("pandas not available for Excel export")
            return HttpResponse('Excel export not available', content_type='text/plain')
        except Exception as e:
            logger.error(f"Error creating Excel export: {str(e)}")
            raise


# ==================== USER EXPORT MANAGER ====================

class UserExportManager(BaseExportManager):
    """Export manager for user data"""
    
    def export_users(self, format_type: str = ExportFormat.CSV,
                    filters: Dict[str, Any] = None,
                    start_date: datetime = None, end_date: datetime = None) -> Union[HttpResponse, bytes]:
        """Export users data"""
        try:
            # Get users queryset
            queryset = self._get_users_queryset(filters, start_date, end_date)
            
            # Prepare data
            data = self._prepare_users_data(queryset)
            
            # Export in specified format
            if format_type == ExportFormat.CSV:
                return self._export_csv(data, 'users', start_date, end_date)
            elif format_type == ExportFormat.JSON:
                return self._export_json(data, 'users', start_date, end_date)
            elif format_type == ExportFormat.EXCEL:
                return self._export_excel(data, 'users', start_date, end_date)
            else:
                raise ValueError(f"Unsupported export format: {format_type}")
                
        except Exception as e:
            logger.error(f"Error exporting users: {str(e)}")
            raise
    
    def _get_users_queryset(self, filters: Dict[str, Any] = None,
                          start_date: datetime = None, end_date: datetime = None):
        """Get users queryset"""
        queryset = User.objects.all()
        
        # Apply date range filter
        if start_date:
            queryset = queryset.filter(date_joined__gte=start_date)
        if end_date:
            queryset = queryset.filter(date_joined__lte=end_date)
        
        # Apply filters
        if filters:
            if 'is_active' in filters:
                queryset = queryset.filter(is_active=filters['is_active'])
            if 'is_staff' in filters:
                queryset = queryset.filter(is_staff=filters['is_staff'])
        
        return queryset
    
    def _prepare_users_data(self, queryset) -> List[Dict[str, Any]]:
        """Prepare users data for export"""
        data = []
        
        for user in queryset:
            # Get user statistics
            user_stats = self._get_user_stats(user.id)
            
            user_data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'date_joined': self._serialize_datetime(user.date_joined),
                'last_login': self._serialize_datetime(user.last_login),
                'total_engagements': user_stats['total_engagements'],
                'total_conversions': user_stats['total_conversions'],
                'total_rewards': user_stats['total_rewards'],
                'total_earned': self._serialize_decimal(user_stats['total_earned']),
                'wallet_balance': self._serialize_decimal(user_stats['wallet_balance']),
            }
            data.append(user_data)
        
        return data
    
    def _get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user statistics"""
        stats = {
            'total_engagements': 0,
            'total_conversions': 0,
            'total_rewards': 0,
            'total_earned': 0,
            'wallet_balance': 0,
        }
        
        try:
            # Get engagements count
            stats['total_engagements'] = UserOfferEngagement.objects.filter(
                user_id=user_id,
                tenant_id=self.tenant_id
            ).count()
            
            # Get conversions count
            conversions = OfferConversion.objects.filter(
                engagement__user_id=user_id,
                tenant_id=self.tenant_id,
                status=ConversionStatus.APPROVED
            )
            stats['total_conversions'] = conversions.count()
            
            # Get rewards count and total earned
            rewards = OfferReward.objects.filter(
                user_id=user_id,
                tenant_id=self.tenant_id,
                status=RewardStatus.APPROVED
            )
            stats['total_rewards'] = rewards.count()
            stats['total_earned'] = rewards.aggregate(
                total=Sum('amount')
            )['total'] or 0
            
            # Get wallet balance
            try:
                wallet = UserWallet.objects.get(user_id=user_id, tenant_id=self.tenant_id)
                stats['wallet_balance'] = wallet.current_balance
            except UserWallet.DoesNotExist:
                pass
                
        except Exception as e:
            logger.error(f"Error getting user stats for {user_id}: {str(e)}")
        
        return stats


# ==================== CONVERSION EXPORT MANAGER ====================

class ConversionExportManager(BaseExportManager):
    """Export manager for conversions"""
    
    def export_conversions(self, format_type: str = ExportFormat.CSV,
                          filters: Dict[str, Any] = None,
                          start_date: datetime = None, end_date: datetime = None) -> Union[HttpResponse, bytes]:
        """Export conversions data"""
        try:
            # Get conversions queryset
            queryset = self._get_conversions_queryset(filters, start_date, end_date)
            
            # Prepare data
            data = self._prepare_conversions_data(queryset)
            
            # Export in specified format
            if format_type == ExportFormat.CSV:
                return self._export_csv(data, 'conversions', start_date, end_date)
            elif format_type == ExportFormat.JSON:
                return self._export_json(data, 'conversions', start_date, end_date)
            elif format_type == ExportFormat.EXCEL:
                return self._export_excel(data, 'conversions', start_date, end_date)
            else:
                raise ValueError(f"Unsupported export format: {format_type}")
                
        except Exception as e:
            logger.error(f"Error exporting conversions: {str(e)}")
            raise
    
    def _get_conversions_queryset(self, filters: Dict[str, Any] = None,
                                start_date: datetime = None, end_date: datetime = None):
        """Get conversions queryset"""
        queryset = OfferConversion.objects.filter(tenant_id=self.tenant_id)
        
        # Apply date range filter
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Apply filters
        if filters:
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            if 'is_fraud' in filters:
                queryset = queryset.filter(is_fraud=filters['is_fraud'])
        
        return queryset.select_related('engagement__user', 'engagement__offer')
    
    def _prepare_conversions_data(self, queryset) -> List[Dict[str, Any]]:
        """Prepare conversions data for export"""
        data = []
        
        for conversion in queryset:
            conversion_data = {
                'id': conversion.id,
                'user_id': conversion.engagement.user.id,
                'username': conversion.engagement.user.username,
                'user_email': conversion.engagement.user.email,
                'offer_id': conversion.engagement.offer.id,
                'offer_title': conversion.engagement.offer.title,
                'status': conversion.status,
                'payout': self._serialize_decimal(conversion.payout),
                'currency': conversion.currency,
                'fraud_score': conversion.fraud_score,
                'is_fraud': conversion.is_fraud,
                'created_at': self._serialize_datetime(conversion.created_at),
                'approved_at': self._serialize_datetime(conversion.approved_at),
                'rejection_reason': conversion.rejection_reason,
                'engagement_id': conversion.engagement.id,
                'engagement_status': conversion.engagement.status,
                'engagement_started_at': self._serialize_datetime(conversion.engagement.started_at),
                'engagement_completed_at': self._serialize_datetime(conversion.engagement.completed_at),
            }
            data.append(conversion_data)
        
        return data


# ==================== ANALYTICS EXPORT MANAGER ====================

class AnalyticsExportManager(BaseExportManager):
    """Export manager for analytics data"""
    
    def export_analytics(self, report_type: str = 'revenue',
                        period: str = '30d',
                        format_type: str = ExportFormat.CSV) -> Union[HttpResponse, bytes]:
        """Export analytics data"""
        try:
            # Get analytics data
            data = self._get_analytics_data(report_type, period)
            
            # Export in specified format
            if format_type == ExportFormat.CSV:
                return self._export_csv(data, f'analytics_{report_type}', None, None)
            elif format_type == ExportFormat.JSON:
                return self._export_json(data, f'analytics_{report_type}', None, None)
            elif format_type == ExportFormat.EXCEL:
                return self._export_excel(data, f'analytics_{report_type}', None, None)
            else:
                raise ValueError(f"Unsupported export format: {format_type}")
                
        except Exception as e:
            logger.error(f"Error exporting analytics: {str(e)}")
            raise
    
    def _get_analytics_data(self, report_type: str, period: str) -> List[Dict[str, Any]]:
        """Get analytics data"""
        try:
            from .analytics import RevenueAnalytics, OfferAnalytics, UserAnalytics
            
            # Calculate date range
            if period == '7d':
                start_date = timezone.now() - timedelta(days=7)
            elif period == '30d':
                start_date = timezone.now() - timedelta(days=30)
            elif period == '90d':
                start_date = timezone.now() - timedelta(days=90)
            else:
                start_date = timezone.now() - timedelta(days=30)
            
            end_date = timezone.now()
            
            if report_type == 'revenue':
                analytics = RevenueAnalytics(self.tenant_id)
                data = analytics.get_revenue_analytics('custom', start_date, end_date)
                
                # Convert daily revenue to flat list
                daily_revenue = data.get('daily_revenue', [])
                return daily_revenue
                
            elif report_type == 'offers':
                analytics = OfferAnalytics(self.tenant_id)
                top_offers = analytics.get_top_performing_offers('custom', 100, start_date, end_date)
                return top_offers
                
            elif report_type == 'users':
                analytics = UserAnalytics(self.tenant_id)
                top_users = analytics.get_top_users('custom', 'revenue', 100, start_date, end_date)
                return top_users
                
            else:
                raise ValueError(f"Unsupported report type: {report_type}")
                
        except Exception as e:
            logger.error(f"Error getting analytics data: {str(e)}")
            raise


# ==================== COMPREHENSIVE EXPORT MANAGER ====================

class ComprehensiveExportManager(BaseExportManager):
    """Comprehensive export manager"""
    
    def __init__(self, tenant_id: str = 'default'):
        super().__init__(tenant_id)
        self.offer_exporter = OfferExportManager(tenant_id)
        self.user_exporter = UserExportManager(tenant_id)
        self.conversion_exporter = ConversionExportManager(tenant_id)
        self.analytics_exporter = AnalyticsExportManager(tenant_id)
    
    def export_all_data(self, format_type: str = ExportFormat.ZIP,
                       start_date: datetime = None, end_date: datetime = None) -> HttpResponse:
        """Export all data as ZIP"""
        try:
            # Create ZIP file in memory
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Export offers
                offers_response = self.offer_exporter.export_offers(
                    ExportFormat.CSV, None, start_date, end_date
                )
                zip_file.writestr('offers.csv', offers_response.content)
                
                # Export users
                users_response = self.user_exporter.export_users(
                    ExportFormat.CSV, None, start_date, end_date
                )
                zip_file.writestr('users.csv', users_response.content)
                
                # Export conversions
                conversions_response = self.conversion_exporter.export_conversions(
                    ExportFormat.CSV, None, start_date, end_date
                )
                zip_file.writestr('conversions.csv', conversions_response.content)
                
                # Export analytics
                analytics_response = self.analytics_exporter.export_analytics(
                    'revenue', '30d', ExportFormat.CSV
                )
                zip_file.writestr('analytics_revenue.csv', analytics_response.content)
                
                # Add metadata
                metadata = {
                    'tenant_id': self.tenant_id,
                    'export_date': timezone.now().isoformat(),
                    'date_range': {
                        'start': self._serialize_datetime(start_date),
                        'end': self._serialize_datetime(end_date),
                    },
                    'files': [
                        'offers.csv',
                        'users.csv',
                        'conversions.csv',
                        'analytics_revenue.csv',
                    ]
                }
                
                zip_file.writestr('metadata.json', json.dumps(metadata, indent=2))
            
            # Create response
            zip_buffer.seek(0)
            filename = self._generate_filename('all_data', ExportFormat.ZIP, start_date, end_date)
            response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except Exception as e:
            logger.error(f"Error creating comprehensive export: {str(e)}")
            raise
    
    def _export_csv(self, data: List[Dict[str, Any]], export_type: str,
                   start_date: datetime = None, end_date: datetime = None) -> bytes:
        """Export data as CSV bytes"""
        if not data:
            return b'No data to export'
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        
        for row in data:
            writer.writerow(row)
        
        return output.getvalue().encode('utf-8')
    
    def _export_json(self, data: List[Dict[str, Any]], export_type: str,
                    start_date: datetime = None, end_date: datetime = None) -> bytes:
        """Export data as JSON bytes"""
        json_data = {
            'export_type': export_type,
            'tenant_id': self.tenant_id,
            'export_date': timezone.now().isoformat(),
            'date_range': {
                'start': self._serialize_datetime(start_date),
                'end': self._serialize_datetime(end_date),
            },
            'total_records': len(data),
            'data': data,
        }
        
        return json.dumps(json_data, indent=2, default=str).encode('utf-8')


# ==================== EXPORT SCHEDULER ====================

class ExportScheduler:
    """Schedule and manage exports"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.export_manager = ComprehensiveExportManager(tenant_id)
    
    def schedule_daily_export(self, export_type: str = 'all') -> str:
        """Schedule daily export"""
        # This would typically integrate with a task queue
        # For now, return a placeholder
        export_id = f"daily_{export_type}_{timezone.now().strftime('%Y%m%d')}"
        
        logger.info(f"Scheduled daily export: {export_id}")
        return export_id
    
    def create_export_task(self, export_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create export task"""
        try:
            export_type = export_config.get('type', 'all')
            format_type = export_config.get('format', ExportFormat.ZIP)
            start_date = export_config.get('start_date')
            end_date = export_config.get('end_date')
            
            # Generate export
            if export_type == 'all':
                response = self.export_manager.export_all_data(format_type, start_date, end_date)
            elif export_type == 'offers':
                response = self.export_manager.offer_exporter.export_offers(format_type, export_config.get('filters'), start_date, end_date)
            elif export_type == 'users':
                response = self.export_manager.user_exporter.export_users(format_type, export_config.get('filters'), start_date, end_date)
            elif export_type == 'conversions':
                response = self.export_manager.conversion_exporter.export_conversions(format_type, export_config.get('filters'), start_date, end_date)
            else:
                raise ValueError(f"Unsupported export type: {export_type}")
            
            return {
                'success': True,
                'export_id': str(uuid.uuid4()),
                'filename': response.get('Content-Disposition', '').split('filename=')[-1].strip('"'),
                'size': len(response.content),
                'created_at': timezone.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error creating export task: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'created_at': timezone.now().isoformat(),
            }


# ==================== EXPORT PERMISSIONS ====================

class ExportPermissions:
    """Export permissions management"""
    
    @staticmethod
    def can_export_data(user, export_type: str, tenant_id: str) -> bool:
        """Check if user can export data"""
        # Admin can export anything
        if user.is_staff:
            return True
        
        # Check tenant ownership
        if hasattr(user, 'tenant_id') and user.tenant_id != tenant_id:
            return False
        
        # Check export type permissions
        if export_type in ['offers', 'conversions']:
            return True  # Basic users can export offers and conversions
        elif export_type in ['users', 'analytics']:
            return user.is_staff  # Only staff can export users and analytics
        
        return False
    
    @staticmethod
    def get_export_limits(user) -> Dict[str, Any]:
        """Get export limits for user"""
        if user.is_staff:
            return {
                'max_records': 1000000,
                'max_file_size_mb': 100,
                'formats': ['csv', 'json', 'excel', 'zip'],
            }
        else:
            return {
                'max_records': 10000,
                'max_file_size_mb': 10,
                'formats': ['csv', 'json'],
            }


# ==================== EXPORTS ====================

__all__ = [
    # Formats and types
    'ExportFormat',
    'ExportType',
    
    # Managers
    'BaseExportManager',
    'OfferExportManager',
    'UserExportManager',
    'ConversionExportManager',
    'AnalyticsExportManager',
    'ComprehensiveExportManager',
    
    # Scheduler and permissions
    'ExportScheduler',
    'ExportPermissions',
]
