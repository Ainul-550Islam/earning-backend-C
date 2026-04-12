"""
Advertiser Profile Management

This module handles advertiser profile creation, management, and profile-related operations.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.core.mail import send_mail
from django.conf import settings

from ..database_models.advertiser_model import Advertiser, AdvertiserVerification, AdvertiserCredit
from ..database_models.user_model import AdvertiserUser
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserProfileService:
    """Service for managing advertiser profiles."""
    
    @staticmethod
    def create_advertiser_profile(data: Dict[str, Any], created_by: Optional[User] = None) -> Advertiser:
        """Create a new advertiser profile."""
        try:
            with transaction.atomic():
                # Validate required fields
                required_fields = ['company_name', 'contact_email', 'industry']
                for field in required_fields:
                    if not data.get(field):
                        raise AdvertiserValidationError(f"{field} is required")
                
                # Validate email format
                validate_email(data['contact_email'])
                
                # Check for duplicate email
                if Advertiser.objects.filter(contact_email=data['contact_email']).exists():
                    raise AdvertiserValidationError("Advertiser with this email already exists")
                
                # Check for duplicate company name
                if Advertiser.objects.filter(company_name=data['company_name']).exists():
                    raise AdvertiserValidationError("Advertiser with this company name already exists")
                
                # Create advertiser
                advertiser = Advertiser.objects.create(
                    company_name=data['company_name'],
                    trade_name=data.get('trade_name', ''),
                    industry=data.get('industry', 'other'),
                    sub_industry=data.get('sub_industry', ''),
                    contact_email=data['contact_email'],
                    contact_phone=data.get('contact_phone', ''),
                    contact_name=data.get('contact_name', ''),
                    contact_title=data.get('contact_title', ''),
                    website=data.get('website', ''),
                    description=data.get('description', ''),
                    company_size=data.get('company_size', 'small'),
                    annual_revenue=data.get('annual_revenue'),
                    billing_address=data.get('billing_address', ''),
                    billing_city=data.get('billing_city', ''),
                    billing_state=data.get('billing_state', ''),
                    billing_country=data.get('billing_country', ''),
                    billing_postal_code=data.get('billing_postal_code', ''),
                    is_verified=False,
                    verification_date=None,
                    verified_by=None,
                    verification_documents=data.get('verification_documents', []),
                    compliance_score=0,
                    account_type=data.get('account_type', 'individual'),
                    account_manager=data.get('account_manager'),
                    timezone=data.get('timezone', 'UTC'),
                    currency=data.get('currency', 'USD'),
                    language=data.get('language', 'en'),
                    credit_limit=Decimal(str(data.get('credit_limit', 1000.00))),
                    account_balance=Decimal('0.00'),
                    auto_charge_enabled=data.get('auto_charge_enabled', False),
                    billing_cycle=data.get('billing_cycle', 'monthly'),
                    total_spend=Decimal('0.00'),
                    total_campaigns=0,
                    active_campaigns=0,
                    quality_score=0,
                    created_by=created_by
                )
                
                # Generate API key
                advertiser.generate_api_key()
                
                # Create initial credit record
                AdvertiserCredit.objects.create(
                    advertiser=advertiser,
                    credit_type='initial',
                    amount=Decimal(str(data.get('initial_credit', 0))),
                    description='Initial credit allocation',
                    balance_after=advertiser.account_balance
                )
                
                # Send welcome notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=created_by,
                    title='Advertiser Profile Created',
                    message=f'Your advertiser profile for {advertiser.company_name} has been created successfully.',
                    notification_type='system',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    advertiser,
                    created_by,
                    description=f"Created advertiser profile: {advertiser.company_name}"
                )
                
                return advertiser
                
        except Exception as e:
            logger.error(f"Error creating advertiser profile: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create advertiser profile: {str(e)}")
    
    @staticmethod
    def update_advertiser_profile(advertiser_id: UUID, data: Dict[str, Any],
                                   updated_by: Optional[User] = None) -> Advertiser:
        """Update advertiser profile."""
        try:
            advertiser = AdvertiserProfileService.get_advertiser_profile(advertiser_id)
            
            with transaction.atomic():
                # Track changes for audit log
                changed_fields = {}
                
                # Update basic fields
                for field in ['trade_name', 'industry', 'sub_industry', 'contact_phone',
                             'contact_name', 'contact_title', 'website', 'description',
                             'company_size', 'annual_revenue', 'billing_address',
                             'billing_city', 'billing_state', 'billing_country',
                             'billing_postal_code', 'account_type', 'account_manager',
                             'timezone', 'currency', 'language']:
                    if field in data:
                        old_value = getattr(advertiser, field)
                        new_value = data[field]
                        if old_value != new_value:
                            setattr(advertiser, field, new_value)
                            changed_fields[field] = {'old': old_value, 'new': new_value}
                
                # Update credit limit
                if 'credit_limit' in data:
                    old_limit = advertiser.credit_limit
                    new_limit = Decimal(str(data['credit_limit']))
                    if old_limit != new_limit:
                        advertiser.credit_limit = new_limit
                        changed_fields['credit_limit'] = {'old': old_limit, 'new': new_limit}
                
                # Update auto-charge settings
                if 'auto_charge_enabled' in data:
                    old_auto_charge = advertiser.auto_charge_enabled
                    new_auto_charge = data['auto_charge_enabled']
                    if old_auto_charge != new_auto_charge:
                        advertiser.auto_charge_enabled = new_auto_charge
                        changed_fields['auto_charge_enabled'] = {'old': old_auto_charge, 'new': new_auto_charge}
                
                advertiser.modified_by = updated_by
                advertiser.save()
                
                # Log changes
                if changed_fields:
                    from ..database_models.audit_model import AuditLog
                    AuditLog.log_update(
                        advertiser,
                        changed_fields,
                        updated_by,
                        description=f"Updated advertiser profile: {advertiser.company_name}"
                    )
                
                return advertiser
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser profile {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error updating advertiser profile {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to update advertiser profile: {str(e)}")
    
    @staticmethod
    def get_advertiser_profile(advertiser_id: UUID) -> Advertiser:
        """Get advertiser profile by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser profile {advertiser_id} not found")
    
    @staticmethod
    def list_advertiser_profiles(filters: Optional[Dict[str, Any]] = None,
                                   page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """List advertiser profiles with filtering and pagination."""
        try:
            queryset = Advertiser.objects.filter(is_deleted=False)
            
            # Apply filters
            if filters:
                if 'status' in filters:
                    if filters['status'] == 'active':
                        queryset = queryset.filter(is_verified=True)
                    elif filters['status'] == 'pending':
                        queryset = queryset.filter(is_verified=False)
                    elif filters['status'] == 'inactive':
                        queryset = queryset.filter(is_deleted=True)
                
                if 'industry' in filters:
                    queryset = queryset.filter(industry=filters['industry'])
                
                if 'account_type' in filters:
                    queryset = queryset.filter(account_type=filters['account_type'])
                
                if 'company_size' in filters:
                    queryset = queryset.filter(company_size=filters['company_size'])
                
                if 'search' in filters:
                    search = filters['search']
                    queryset = queryset.filter(
                        Q(company_name__icontains=search) |
                        Q(trade_name__icontains=search) |
                        Q(contact_email__icontains=search) |
                        Q(contact_name__icontains=search)
                    )
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            advertisers = queryset[offset:offset + page_size]
            
            return {
                'advertisers': advertisers,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"Error listing advertiser profiles: {str(e)}")
            raise AdvertiserServiceError(f"Failed to list advertiser profiles: {str(e)}")
    
    @staticmethod
    def delete_advertiser_profile(advertiser_id: UUID, deleted_by: Optional[User] = None) -> bool:
        """Delete advertiser profile (soft delete)."""
        try:
            advertiser = AdvertiserProfileService.get_advertiser_profile(advertiser_id)
            
            with transaction.atomic():
                # Log deletion
                from ..database_models.audit_model import AuditLog
                AuditLog.log_deletion(
                    advertiser,
                    deleted_by,
                    description=f"Deleted advertiser profile: {advertiser.company_name}"
                )
                
                # Soft delete
                advertiser.soft_delete()
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=deleted_by,
                    title='Advertiser Profile Deleted',
                    message=f'Your advertiser profile for {advertiser.company_name} has been deleted.',
                    notification_type='system',
                    priority='high',
                    channels=['in_app']
                )
                
                return True
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser profile {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error deleting advertiser profile {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to delete advertiser profile: {str(e)}")
    
    @staticmethod
    def get_advertiser_summary(advertiser_id: UUID) -> Dict[str, Any]:
        """Get comprehensive advertiser summary."""
        try:
            advertiser = AdvertiserProfileService.get_advertiser_profile(advertiser_id)
            
            # Get campaign statistics
            from ..database_models.campaign_model import Campaign
            campaigns = Campaign.objects.filter(advertiser=advertiser, is_deleted=False)
            
            # Get spend statistics
            total_spend = campaigns.aggregate(
                total=Sum('current_spend')
            )['total'] or Decimal('0.00')
            
            # Get credit information
            credit_available = advertiser.credit_available
            credit_utilization = ((advertiser.credit_limit - credit_available) / advertiser.credit_limit * 100) if advertiser.credit_limit > 0 else 0
            
            # Get recent activity
            from ..database_models.user_model import UserActivityLog
            recent_activity = UserActivityLog.objects.filter(
                user__advertiser=advertiser
            ).order_by('-created_at')[:10]
            
            return {
                'profile': {
                    'id': str(advertiser.id),
                    'company_name': advertiser.company_name,
                    'trade_name': advertiser.trade_name,
                    'industry': advertiser.industry,
                    'contact_email': advertiser.contact_email,
                    'contact_phone': advertiser.contact_phone,
                    'website': advertiser.website,
                    'is_verified': advertiser.is_verified,
                    'verification_date': advertiser.verification_date.isoformat() if advertiser.verification_date else None,
                    'account_type': advertiser.account_type,
                    'status': 'verified' if advertiser.is_verified else 'pending',
                    'created_at': advertiser.created_at.isoformat()
                },
                'statistics': {
                    'total_campaigns': campaigns.count(),
                    'active_campaigns': campaigns.filter(status='active').count(),
                    'total_spend': float(total_spend),
                    'credit_limit': float(advertiser.credit_limit),
                    'credit_available': float(credit_available),
                    'credit_utilization': float(credit_utilization),
                    'quality_score': float(advertiser.quality_score)
                },
                'billing': {
                    'account_balance': float(advertiser.account_balance),
                    'auto_charge_enabled': advertiser.auto_charge_enabled,
                    'billing_cycle': advertiser.billing_cycle,
                    'currency': advertiser.currency
                },
                'recent_activity': [
                    {
                        'id': str(activity.id),
                        'activity_type': activity.activity_type,
                        'description': activity.description,
                        'created_at': activity.created_at.isoformat()
                    }
                    for activity in recent_activity
                ]
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser profile {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting advertiser summary {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get advertiser summary: {str(e)}")
    
    @staticmethod
    def regenerate_api_key(advertiser_id: UUID, regenerated_by: Optional[User] = None) -> str:
        """Regenerate API key for advertiser."""
        try:
            advertiser = AdvertiserProfileService.get_advertiser_profile(advertiser_id)
            
            with transaction.atomic():
                old_api_key = advertiser.api_key
                advertiser.generate_api_key()
                advertiser.save(update_fields=['api_key'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=regenerated_by,
                    title='API Key Regenerated',
                    message='Your API key has been regenerated successfully.',
                    notification_type='security',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                # Log regeneration
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='regenerate_api_key',
                    object_type='Advertiser',
                    object_id=str(advertiser.id),
                    user=regenerated_by,
                    advertiser=advertiser,
                    description=f"Regenerated API key for: {advertiser.company_name}"
                )
                
                return advertiser.api_key
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser profile {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error regenerating API key {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to regenerate API key: {str(e)}")
    
    @staticmethod
    def update_compliance_score(advertiser_id: UUID) -> float:
        """Update advertiser compliance score."""
        try:
            advertiser = AdvertiserProfileService.get_advertiser_profile(advertiser_id)
            
            # Calculate compliance score based on various factors
            score = 100.0  # Start with perfect score
            
            # Deduct points for missing verification
            if not advertiser.is_verified:
                score -= 30.0
            
            # Deduct points for incomplete profile
            if not advertiser.trade_name:
                score -= 5.0
            if not advertiser.website:
                score -= 10.0
            if not advertiser.description:
                score -= 5.0
            if not advertiser.contact_phone:
                score -= 5.0
            
            # Deduct points for low activity
            from ..database_models.campaign_model import Campaign
            campaign_count = Campaign.objects.filter(advertiser=advertiser, is_deleted=False).count()
            if campaign_count == 0:
                score -= 20.0
            elif campaign_count < 3:
                score -= 10.0
            
            # Deduct points for low spend
            if advertiser.total_spend < 100:
                score -= 10.0
            
            # Ensure score doesn't go below 0
            score = max(0, score)
            
            # Update advertiser score
            advertiser.compliance_score = score
            advertiser.save(update_fields=['compliance_score'])
            
            return float(score)
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser profile {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error updating compliance score {advertiser_id}: {str(e)}")
            return 0.0
    
    @staticmethod
    def get_advertiser_performance_metrics(advertiser_id: UUID, 
                                           date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get advertiser performance metrics."""
        try:
            advertiser = AdvertiserProfileService.get_advertiser_profile(advertiser_id)
            
            # Default date range (last 30 days)
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Get campaign performance data
            from ..database_models.campaign_model import Campaign
            campaigns = Campaign.objects.filter(
                advertiser=advertiser,
                is_deleted=False,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            # Aggregate metrics
            total_impressions = campaigns.aggregate(
                total=Sum('total_impressions')
            )['total'] or 0
            
            total_clicks = campaigns.aggregate(
                total=Sum('total_clicks')
            )['total'] or 0
            
            total_conversions = campaigns.aggregate(
                total=Sum('total_conversions')
            )['total'] or 0
            
            total_spend = campaigns.aggregate(
                total=Sum('current_spend')
            )['total'] or Decimal('0.00')
            
            # Calculate derived metrics
            ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
            cpa = (total_spend / total_conversions) if total_conversions > 0 else 0
            conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
            
            return {
                'advertiser_id': str(advertiser_id),
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'metrics': {
                    'total_impressions': total_impressions,
                    'total_clicks': total_clicks,
                    'total_conversions': total_conversions,
                    'total_spend': float(total_spend),
                    'ctr': ctr,
                    'cpc': float(cpc),
                    'cpa': float(cpa),
                    'conversion_rate': conversion_rate
                },
                'campaigns': {
                    'total': campaigns.count(),
                    'active': campaigns.filter(status='active').count(),
                    'paused': campaigns.filter(status='paused').count()
                }
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser profile {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting performance metrics {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get performance metrics: {str(e)}")
    
    @staticmethod
    def export_advertiser_data(advertiser_id: UUID, format_type: str = 'json') -> Dict[str, Any]:
        """Export advertiser data."""
        try:
            advertiser = AdvertiserProfileService.get_advertiser_profile(advertiser_id)
            
            # Get comprehensive data
            summary = AdvertiserProfileService.get_advertiser_summary(advertiser_id)
            
            # Get campaign data
            from ..database_models.campaign_model import Campaign
            campaigns = Campaign.objects.filter(advertiser=advertiser, is_deleted=False)
            
            campaign_data = [
                {
                    'id': str(campaign.id),
                    'name': campaign.name,
                    'status': campaign.status,
                    'objective': campaign.objective,
                    'daily_budget': float(campaign.daily_budget),
                    'total_budget': float(campaign.total_budget),
                    'current_spend': float(campaign.current_spend),
                    'total_impressions': campaign.total_impressions,
                    'total_clicks': campaign.total_clicks,
                    'total_conversions': campaign.total_conversions,
                    'created_at': campaign.created_at.isoformat()
                }
                for campaign in campaigns
            ]
            
            # Get billing data
            from ..database_models.billing_model import Invoice, PaymentTransaction
            invoices = Invoice.objects.filter(advertiser=advertiser)
            transactions = PaymentTransaction.objects.filter(advertiser=advertiser)
            
            billing_data = {
                'invoices': [
                    {
                        'id': str(invoice.id),
                        'invoice_number': invoice.invoice_number,
                        'amount': float(invoice.total_amount),
                        'status': invoice.status,
                        'due_date': invoice.due_date.isoformat() if invoice.due_date else None,
                        'created_at': invoice.created_at.isoformat()
                    }
                    for invoice in invoices
                ],
                'transactions': [
                    {
                        'id': str(transaction.id),
                        'transaction_id': transaction.transaction_id,
                        'amount': float(transaction.amount),
                        'status': transaction.status,
                        'created_at': transaction.created_at.isoformat()
                    }
                    for transaction in transactions
                ]
            }
            
            export_data = {
                'advertiser': summary['profile'],
                'statistics': summary['statistics'],
                'campaigns': campaign_data,
                'billing': billing_data,
                'exported_at': timezone.now().isoformat()
            }
            
            if format_type == 'json':
                return export_data
            elif format_type == 'csv':
                # Convert to CSV format (implementation needed)
                return AdvertiserProfileService._convert_to_csv(export_data)
            else:
                raise AdvertiserValidationError(f"Unsupported format: {format_type}")
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser profile {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error exporting advertiser data {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to export advertiser data: {str(e)}")
    
    @staticmethod
    def _convert_to_csv(data: Dict[str, Any]) -> str:
        """Convert data to CSV format."""
        # This would implement CSV conversion logic
        # For now, return JSON string
        import json
        return json.dumps(data, indent=2)
