"""
Advertiser Business Management

This module handles business-related operations for advertisers,
including business registration, industry classification, and business metrics.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID
import json

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from ..database_models.advertiser_model import Advertiser
from ..database_models.business_model import BusinessRegistration, BusinessMetric
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserBusinessService:
    """Service for managing advertiser business operations."""
    
    @staticmethod
    def register_business(advertiser_id: UUID, business_data: Dict[str, Any],
                           registered_by: Optional[User] = None) -> BusinessRegistration:
        """Register business for advertiser."""
        try:
            advertiser = AdvertiserBusinessService.get_advertiser(advertiser_id)
            
            # Check if business already registered
            existing_business = BusinessRegistration.objects.filter(advertiser=advertiser).first()
            if existing_business:
                raise AdvertiserValidationError(f"Business already registered: {existing_business.id}")
            
            # Validate required fields
            required_fields = ['business_name', 'registration_number', 'industry', 'legal_structure']
            for field in required_fields:
                if not business_data.get(field):
                    raise AdvertiserValidationError(f"{field} is required")
            
            with transaction.atomic():
                # Create business registration
                business_registration = BusinessRegistration.objects.create(
                    advertiser=advertiser,
                    business_name=business_data['business_name'],
                    registration_number=business_data['registration_number'],
                    tax_id=business_data.get('tax_id', ''),
                    industry=business_data['industry'],
                    sub_industry=business_data.get('sub_industry', ''),
                    legal_structure=business_data['legal_structure'],
                    business_type=business_data.get('business_type', 'private'),
                    date_of_establishment=business_data.get('date_of_establishment'),
                    registered_address=business_data.get('registered_address', ''),
                    registered_city=business_data.get('registered_city', ''),
                    registered_state=business_data.get('registered_state', ''),
                    registered_country=business_data.get('registered_country', ''),
                    registered_postal_code=business_data.get('registered_postal_code', ''),
                    business_phone=business_data.get('business_phone', ''),
                    business_email=business_data.get('business_email', ''),
                    business_website=business_data.get('business_website', ''),
                    business_description=business_data.get('business_description', ''),
                    number_of_employees=business_data.get('number_of_employees', 0),
                    annual_revenue=Decimal(str(business_data.get('annual_revenue', 0))),
                    business_license_number=business_data.get('business_license_number', ''),
                    business_license_expiry=business_data.get('business_license_expiry'),
                    vat_number=business_data.get('vat_number', ''),
                    registration_documents=business_data.get('registration_documents', []),
                    status='pending',
                    verified_at=None,
                    verified_by=None,
                    created_by=registered_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=registered_by,
                    title='Business Registration Submitted',
                    message=f'Your business registration for {business_registration.business_name} has been submitted for review.',
                    notification_type='business',
                    priority='medium',
                    channels=['in_app', 'email']
                )
                
                # Log registration
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    business_registration,
                    registered_by,
                    description=f"Registered business: {business_registration.business_name}"
                )
                
                return business_registration
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error registering business {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to register business: {str(e)}")
    
    @staticmethod
    def update_business_information(business_id: UUID, business_data: Dict[str, Any],
                                     updated_by: Optional[User] = None) -> BusinessRegistration:
        """Update business information."""
        try:
            business = AdvertiserBusinessService.get_business_registration(business_id)
            
            with transaction.atomic():
                # Track changes for audit log
                changed_fields = {}
                
                # Update fields
                for field in ['business_name', 'tax_id', 'industry', 'sub_industry',
                             'legal_structure', 'business_type', 'date_of_establishment',
                             'registered_address', 'registered_city', 'registered_state',
                             'registered_country', 'registered_postal_code',
                             'business_phone', 'business_email', 'business_website',
                             'business_description', 'number_of_employees', 'annual_revenue',
                             'business_license_number', 'business_license_expiry', 'vat_number']:
                    if field in business_data:
                        old_value = getattr(business, field)
                        new_value = business_data[field]
                        if old_value != new_value:
                            setattr(business, field, new_value)
                            changed_fields[field] = {'old': old_value, 'new': new_value}
                
                # Update registration documents if provided
                if 'registration_documents' in business_data:
                    old_documents = business.registration_documents
                    business.registration_documents = business_data['registration_documents']
                    changed_fields['registration_documents'] = {
                        'old': old_documents,
                        'new': business.registration_documents
                    }
                
                business.modified_by = updated_by
                business.save()
                
                # Log changes
                if changed_fields:
                    from ..database_models.audit_model import AuditLog
                    AuditLog.log_update(
                        business,
                        changed_fields,
                        updated_by,
                        description=f"Updated business information: {business.business_name}"
                    )
                
                return business
                
        except BusinessRegistration.DoesNotExist:
            raise AdvertiserNotFoundError(f"Business registration {business_id} not found")
        except Exception as e:
            logger.error(f"Error updating business information {business_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to update business information: {str(e)}")
    
    @staticmethod
    def verify_business_registration(business_id: UUID, verification_data: Dict[str, Any],
                                    verified_by: Optional[User] = None) -> bool:
        """Verify business registration."""
        try:
            business = AdvertiserBusinessService.get_business_registration(business_id)
            
            with transaction.atomic():
                # Update verification status
                business.status = verification_data.get('status', 'verified')
                business.verified_at = timezone.now()
                business.verified_by = verified_by
                business.verification_notes = verification_data.get('verification_notes', '')
                business.save(update_fields=['status', 'verified_at', 'verified_by', 'verification_notes'])
                
                # Update advertiser if verified
                if business.status == 'verified':
                    business.advertiser.is_verified = True
                    business.advertiser.verification_date = timezone.now()
                    business.advertiser.verified_by = verified_by
                    business.advertiser.save(update_fields=['is_verified', 'verification_date', 'verified_by'])
                
                # Send notification
                status_messages = {
                    'verified': 'Your business registration has been verified successfully.',
                    'rejected': 'Your business registration has been rejected.',
                    'needs_review': 'Your business registration needs additional review.'
                }
                
                Notification.objects.create(
                    advertiser=business.advertiser,
                    user=business.advertiser.user,
                    title='Business Registration Status Updated',
                    message=status_messages.get(business.status, 'Business registration status updated.'),
                    notification_type='business',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                # Log verification
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='verify_business',
                    object_type='BusinessRegistration',
                    object_id=str(business.id),
                    user=verified_by,
                    advertiser=business.advertiser,
                    description=f"Verified business registration: {business.business_name}"
                )
                
                return True
                
        except BusinessRegistration.DoesNotExist:
            raise AdvertiserNotFoundError(f"Business registration {business_id} not found")
        except Exception as e:
            logger.error(f"Error verifying business registration {business_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_business_registration(business_id: UUID) -> BusinessRegistration:
        """Get business registration by ID."""
        try:
            return BusinessRegistration.objects.get(id=business_id)
        except BusinessRegistration.DoesNotExist:
            raise AdvertiserNotFoundError(f"Business registration {business_id} not found")
    
    @staticmethod
    def get_business_by_advertiser(advertiser_id: UUID) -> Optional[BusinessRegistration]:
        """Get business registration by advertiser."""
        try:
            advertiser = AdvertiserBusinessService.get_advertiser(advertiser_id)
            return BusinessRegistration.objects.filter(advertiser=advertiser).first()
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting business by advertiser {advertiser_id}: {str(e)}")
            return None
    
    @staticmethod
    def get_business_metrics(advertiser_id: UUID, metric_type: str = 'all',
                            date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get business metrics for advertiser."""
        try:
            advertiser = AdvertiserBusinessService.get_advertiser(advertiser_id)
            
            # Default date range (last 30 days)
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            metrics = {}
            
            if metric_type in ['all', 'campaign_performance']:
                metrics['campaign_performance'] = AdvertiserBusinessService._get_campaign_metrics(advertiser, start_date, end_date)
            
            if metric_type in ['all', 'financial_performance']:
                metrics['financial_performance'] = AdvertiserBusinessService._get_financial_metrics(advertiser, start_date, end_date)
            
            if metric_type in ['all', 'audience_metrics']:
                metrics['audience_metrics'] = AdvertiserBusinessService._get_audience_metrics(advertiser, start_date, end_date)
            
            if metric_type in ['all', 'conversion_metrics']:
                metrics['conversion_metrics'] = AdvertiserBusinessService._get_conversion_metrics(advertiser, start_date, end_date)
            
            if metric_type in ['all', 'roi_metrics']:
                metrics['roi_metrics'] = AdvertiserBusinessService._get_roi_metrics(advertiser, start_date, end_date)
            
            return {
                'advertiser_id': str(advertiser_id),
                'business_name': advertiser.company_name,
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'metrics': metrics,
                'generated_at': timezone.now().isoformat()
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting business metrics {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get business metrics: {str(e)}")
    
    @staticmethod
    def _get_campaign_metrics(advertiser: Advertiser, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get campaign performance metrics."""
        try:
            from ..database_models.campaign_model import Campaign
            
            campaigns = Campaign.objects.filter(
                advertiser=advertiser,
                is_deleted=False,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            # Aggregate metrics
            total_campaigns = campaigns.count()
            active_campaigns = campaigns.filter(status='active').count()
            paused_campaigns = campaigns.filter(status='paused').count()
            
            total_budget = campaigns.aggregate(total=Sum('total_budget'))['total'] or Decimal('0.00')
            total_spend = campaigns.aggregate(total=Sum('current_spend'))['total'] or Decimal('0.00')
            
            total_impressions = campaigns.aggregate(total=Sum('total_impressions'))['total'] or 0
            total_clicks = campaigns.aggregate(total=Sum('total_clicks'))['total'] or 0
            total_conversions = campaigns.aggregate(total=Sum('total_conversions'))['total'] or 0
            
            # Calculate derived metrics
            ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
            cpa = (total_spend / total_conversions) if total_conversions > 0 else 0
            conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
            budget_utilization = (total_spend / total_budget * 100) if total_budget > 0 else 0
            
            return {
                'total_campaigns': total_campaigns,
                'active_campaigns': active_campaigns,
                'paused_campaigns': paused_campaigns,
                'total_budget': float(total_budget),
                'total_spend': float(total_spend),
                'budget_utilization': budget_utilization,
                'total_impressions': total_impressions,
                'total_clicks': total_clicks,
                'total_conversions': total_conversions,
                'ctr': ctr,
                'cpc': float(cpc),
                'cpa': float(cpa),
                'conversion_rate': conversion_rate
            }
            
        except Exception as e:
            logger.error(f"Error getting campaign metrics: {str(e)}")
            return {}
    
    @staticmethod
    def _get_financial_metrics(advertiser: Advertiser, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get financial performance metrics."""
        try:
            from ..database_models.billing_model import Invoice, PaymentTransaction
            
            # Get invoice data
            invoices = Invoice.objects.filter(
                advertiser=advertiser,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            total_invoiced = invoices.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
            paid_invoices = invoices.filter(status='paid')
            total_paid = paid_invoices.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
            
            # Get payment data
            payments = PaymentTransaction.objects.filter(
                advertiser=advertiser,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
                status='completed'
            )
            
            total_payments = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # Calculate financial metrics
            payment_rate = (total_paid / total_invoiced * 100) if total_invoiced > 0 else 0
            average_invoice_value = (total_invoiced / invoices.count()) if invoices.count() > 0 else 0
            
            return {
                'total_invoiced': float(total_invoiced),
                'total_paid': float(total_paid),
                'total_payments': float(total_payments),
                'payment_rate': payment_rate,
                'average_invoice_value': float(average_invoice_value),
                'outstanding_amount': float(total_invoiced - total_paid),
                'invoice_count': invoices.count(),
                'payment_count': payments.count()
            }
            
        except Exception as e:
            logger.error(f"Error getting financial metrics: {str(e)}")
            return {}
    
    @staticmethod
    def _get_audience_metrics(advertiser: Advertiser, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get audience metrics."""
        try:
            from ..database_models.impression_model import ImpressionAggregation
            from ..database_models.targeting_model import Targeting
            
            # Get unique audience reach
            impressions = ImpressionAggregation.objects.filter(
                campaign__advertiser=advertiser,
                date__gte=start_date,
                date__lte=end_date
            )
            
            total_impressions = impressions.aggregate(total=Sum('impressions'))['total'] or 0
            unique_impressions = impressions.aggregate(total=Sum('unique_impressions'))['total'] or 0
            
            # Get targeting data
            targetings = Targeting.objects.filter(
                campaign__advertiser=advertiser,
                campaign__is_deleted=False
            )
            
            # Analyze targeting breakdown
            geo_targeting_count = targetings.exclude(countries=[]).count()
            device_targeting_count = targetings.exclude(device_targeting=[]).count()
            demographic_targeting_count = targetings.exclude(genders=[]).count()
            
            return {
                'total_impressions': total_impressions,
                'unique_impressions': unique_impressions,
                'reach_efficiency': (unique_impressions / total_impressions * 100) if total_impressions > 0 else 0,
                'targeting_breakdown': {
                    'geo_targeting_campaigns': geo_targeting_count,
                    'device_targeting_campaigns': device_targeting_count,
                    'demographic_targeting_campaigns': demographic_targeting_count
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting audience metrics: {str(e)}")
            return {}
    
    @staticmethod
    def _get_conversion_metrics(advertiser: Advertiser, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get conversion metrics."""
        try:
            from ..database_models.conversion_model import ConversionAggregation
            
            conversions = ConversionAggregation.objects.filter(
                campaign__advertiser=advertiser,
                date__gte=start_date,
                date__lte=end_date
            )
            
            total_conversions = conversions.aggregate(total=Sum('conversions'))['total'] or 0
            total_revenue = conversions.aggregate(total=Sum('total_revenue'))['total'] or Decimal('0.00')
            
            # Get conversion by type
            conversion_by_type = conversions.values('conversion_type').annotate(
                count=Sum('conversions'),
                revenue=Sum('total_revenue')
            )
            
            return {
                'total_conversions': total_conversions,
                'total_revenue': float(total_revenue),
                'average_conversion_value': float(total_revenue / total_conversions) if total_conversions > 0 else 0,
                'conversion_by_type': list(conversion_by_type)
            }
            
        except Exception as e:
            logger.error(f"Error getting conversion metrics: {str(e)}")
            return {}
    
    @staticmethod
    def _get_roi_metrics(advertiser: Advertiser, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get ROI metrics."""
        try:
            from ..database_models.campaign_model import Campaign
            from ..database_models.conversion_model import ConversionAggregation
            
            # Get campaign spend
            campaigns = Campaign.objects.filter(
                advertiser=advertiser,
                is_deleted=False,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            total_spend = campaigns.aggregate(total=Sum('current_spend'))['total'] or Decimal('0.00')
            
            # Get conversion revenue
            conversions = ConversionAggregation.objects.filter(
                campaign__advertiser=advertiser,
                date__gte=start_date,
                date__lte=end_date
            )
            
            total_revenue = conversions.aggregate(total=Sum('total_revenue'))['total'] or Decimal('0.00')
            
            # Calculate ROI metrics
            roi = ((total_revenue - total_spend) / total_spend * 100) if total_spend > 0 else 0
            roas = (total_revenue / total_spend) if total_spend > 0 else 0
            
            return {
                'total_spend': float(total_spend),
                'total_revenue': float(total_revenue),
                'net_profit': float(total_revenue - total_spend),
                'roi': roi,
                'roas': roas,
                'profit_margin': ((total_revenue - total_spend) / total_revenue * 100) if total_revenue > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting ROI metrics: {str(e)}")
            return {}
    
    @staticmethod
    def update_business_profile_score(advertiser_id: UUID) -> float:
        """Update business profile score."""
        try:
            advertiser = AdvertiserBusinessService.get_advertiser(advertiser_id)
            
            score = 100.0  # Start with perfect score
            
            # Deduct points for missing business registration
            business = AdvertiserBusinessService.get_business_by_advertiser(advertiser_id)
            if not business:
                score -= 30.0
            elif business.status != 'verified':
                score -= 20.0
            
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
            advertiser.quality_score = score
            advertiser.save(update_fields=['quality_score'])
            
            return float(score)
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error updating business profile score {advertiser_id}: {str(e)}")
            return 0.0
    
    @staticmethod
    def get_business_insights(advertiser_id: UUID) -> Dict[str, Any]:
        """Get business insights and recommendations."""
        try:
            advertiser = AdvertiserBusinessService.get_advertiser(advertiser_id)
            
            # Get recent metrics
            metrics = AdvertiserBusinessService.get_business_metrics(advertiser_id, 'all')
            
            # Generate insights
            insights = []
            
            # Campaign performance insights
            campaign_metrics = metrics['metrics'].get('campaign_performance', {})
            if campaign_metrics.get('ctr', 0) < 1.0:
                insights.append({
                    'type': 'performance',
                    'category': 'campaign',
                    'severity': 'high',
                    'message': 'Low CTR detected. Consider optimizing ad creatives or targeting.',
                    'recommendation': 'Review creative performance and adjust targeting parameters.'
                })
            
            if campaign_metrics.get('budget_utilization', 0) > 90:
                insights.append({
                    'type': 'budget',
                    'category': 'campaign',
                    'severity': 'medium',
                    'message': 'High budget utilization detected.',
                    'recommendation': 'Consider increasing budget or optimizing spend efficiency.'
                })
            
            # Financial insights
            financial_metrics = metrics['metrics'].get('financial_performance', {})
            if financial_metrics.get('payment_rate', 0) < 80:
                insights.append({
                    'type': 'financial',
                    'category': 'billing',
                    'severity': 'high',
                    'message': 'Low payment rate detected.',
                    'recommendation': 'Follow up on outstanding invoices and review payment terms.'
                })
            
            # ROI insights
            roi_metrics = metrics['metrics'].get('roi_metrics', {})
            if roi_metrics.get('roi', 0) < 0:
                insights.append({
                    'type': 'performance',
                    'category': 'roi',
                    'severity': 'critical',
                    'message': 'Negative ROI detected.',
                    'recommendation': 'Pause underperforming campaigns and review bidding strategy.'
                })
            
            return {
                'advertiser_id': str(advertiser_id),
                'business_name': advertiser.company_name,
                'insights': insights,
                'insight_count': len(insights),
                'generated_at': timezone.now().isoformat()
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting business insights {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get business insights: {str(e)}")
    
    @staticmethod
    def get_industry_benchmarks(industry: str) -> Dict[str, Any]:
        """Get industry benchmarks."""
        try:
            # Mock implementation - would integrate with actual industry data
            benchmarks = {
                'technology': {
                    'average_ctr': 2.5,
                    'average_cpc': 2.50,
                    'average_cpa': 25.00,
                    'average_roi': 150.0,
                    'average_conversion_rate': 3.5
                },
                'retail': {
                    'average_ctr': 1.8,
                    'average_cpc': 1.80,
                    'average_cpa': 18.00,
                    'average_roi': 120.0,
                    'average_conversion_rate': 2.8
                },
                'finance': {
                    'average_ctr': 1.2,
                    'average_cpc': 3.20,
                    'average_cpa': 35.00,
                    'average_roi': 180.0,
                    'average_conversion_rate': 2.0
                },
                'healthcare': {
                    'average_ctr': 1.5,
                    'average_cpc': 2.80,
                    'average_cpa': 30.00,
                    'average_roi': 160.0,
                    'average_conversion_rate': 2.5
                }
            }
            
            return benchmarks.get(industry.lower(), {
                'average_ctr': 2.0,
                'average_cpc': 2.00,
                'average_cpa': 20.00,
                'average_roi': 140.0,
                'average_conversion_rate': 3.0
            })
            
        except Exception as e:
            logger.error(f"Error getting industry benchmarks {industry}: {str(e)}")
            return {}
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_business_statistics() -> Dict[str, Any]:
        """Get business registration statistics."""
        try:
            total_businesses = BusinessRegistration.objects.count()
            pending_businesses = BusinessRegistration.objects.filter(status='pending').count()
            verified_businesses = BusinessRegistration.objects.filter(status='verified').count()
            rejected_businesses = BusinessRegistration.objects.filter(status='rejected').count()
            
            # Calculate verification rate
            completed_businesses = verified_businesses + rejected_businesses
            verification_rate = (verified_businesses / completed_businesses * 100) if completed_businesses > 0 else 0
            
            # Get businesses by industry
            businesses_by_industry = BusinessRegistration.objects.values('industry').annotate(
                count=Count('id')
            )
            
            # Get businesses by legal structure
            businesses_by_structure = BusinessRegistration.objects.values('legal_structure').annotate(
                count=Count('id')
            )
            
            return {
                'total_businesses': total_businesses,
                'pending_businesses': pending_businesses,
                'verified_businesses': verified_businesses,
                'rejected_businesses': rejected_businesses,
                'verification_rate': verification_rate,
                'businesses_by_industry': list(businesses_by_industry),
                'businesses_by_structure': list(businesses_by_structure)
            }
            
        except Exception as e:
            logger.error(f"Error getting business statistics: {str(e)}")
            return {
                'total_businesses': 0,
                'pending_businesses': 0,
                'verified_businesses': 0,
                'rejected_businesses': 0,
                'verification_rate': 0,
                'businesses_by_industry': [],
                'businesses_by_structure': []
            }
