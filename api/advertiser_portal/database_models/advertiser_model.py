"""
Advertiser Database Model

This module contains the Advertiser model and related models
for managing advertiser accounts and profiles.
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.utils import timezone
from django.core.validators import EmailValidator, URLValidator
from django.db.models import Q, Sum, Count, Avg

from api.advertiser_portal.models_base import (
    AdvertiserPortalBaseModel, StatusModel, AuditModel,
    APIKeyModel, BudgetModel, GeoModel, TrackingModel, ConfigurationModel,
)
from ..enums import *
from ..utils import *
from ..validators import *


User = get_user_model()


class Advertiser(AdvertiserPortalBaseModel, StatusModel, AuditModel, APIKeyModel):
    """
    Main advertiser model representing advertising clients.
    
    This model stores all advertiser information including company details,
    contact information, verification status, and account settings.
    """
    
    # Basic Information
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='advertiser',
        help_text="Associated user account"
    )
    company_name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Legal company name"
    )
    trade_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Trade name or DBA (Doing Business As)"
    )
    industry = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Industry category"
    )
    sub_industry = models.CharField(
        max_length=100,
        blank=True,
        help_text="Sub-industry category"
    )
    
    # Contact Information
    contact_email = models.EmailField(
        db_index=True,
        help_text="Primary contact email"
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Primary contact phone number"
    )
    contact_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Primary contact person name"
    )
    contact_title = models.CharField(
        max_length=100,
        blank=True,
        help_text="Primary contact person title"
    )
    
    # Business Information
    website = models.URLField(
        blank=True,
        help_text="Company website URL"
    )
    description = models.TextField(
        blank=True,
        help_text="Company description"
    )
    company_size = models.CharField(
        max_length=50,
        choices=[
            ('1-10', '1-10 employees'),
            ('11-50', '11-50 employees'),
            ('51-200', '51-200 employees'),
            ('201-500', '201-500 employees'),
            ('501-1000', '501-1000 employees'),
            ('1000+', '1000+ employees')
        ],
        default='1-10',
        help_text="Company size"
    )
    annual_revenue = models.CharField(
        max_length=50,
        choices=[
            ('<1M', 'Less than $1M'),
            ('1M-10M', '$1M - $10M'),
            ('10M-50M', '$10M - $50M'),
            ('50M-100M', '$50M - $100M'),
            ('100M-500M', '$100M - $500M'),
            ('500M+', 'More than $500M')
        ],
        blank=True,
        help_text="Annual revenue range"
    )
    
    # Address Information
    billing_address = models.TextField(
        blank=True,
        help_text="Billing address"
    )
    billing_city = models.CharField(
        max_length=100,
        blank=True,
        help_text="Billing city"
    )
    billing_state = models.CharField(
        max_length=100,
        blank=True,
        help_text="Billing state/province"
    )
    billing_country = models.CharField(
        max_length=2,
        blank=True,
        help_text="Billing country code (ISO 3166-1 alpha-2)"
    )
    billing_postal_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="Billing postal code"
    )
    
    # Verification and Compliance
    is_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether advertiser account is verified"
    )
    verification_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when account was verified"
    )
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_advertisers',
        help_text="Admin who verified the account"
    )
    verification_documents = models.JSONField(
        default=list,
        blank=True,
        help_text="List of verification document URLs"
    )
    compliance_score = models.IntegerField(
        default=0,
        help_text="Compliance score (0-100)"
    )
    
    # Account Settings
    account_type = models.CharField(
        max_length=20,
        choices=[
            ('individual', 'Individual'),
            ('business', 'Business'),
            ('enterprise', 'Enterprise'),
            ('agency', 'Agency')
        ],
        default='business',
        help_text="Account type"
    )
    account_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_advertisers',
        help_text="Assigned account manager"
    )
    timezone = models.CharField(
        max_length=50,
        default='UTC',
        help_text="Advertiser timezone"
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Default currency code"
    )
    language = models.CharField(
        max_length=5,
        default='en',
        help_text="Preferred language code"
    )
    
    # Financial Information
    credit_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Credit limit for post-paid billing"
    )
    account_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Current account balance"
    )
    auto_charge_enabled = models.BooleanField(
        default=False,
        help_text="Whether automatic charging is enabled"
    )
    billing_cycle = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('annually', 'Annually')
        ],
        default='monthly',
        help_text="Billing cycle"
    )
    
    # Performance Metrics
    total_spend = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Total amount spent historically"
    )
    total_campaigns = models.IntegerField(
        default=0,
        help_text="Total number of campaigns created"
    )
    active_campaigns = models.IntegerField(
        default=0,
        help_text="Number of currently active campaigns"
    )
    quality_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Advertiser quality score (0-100)"
    )
    
    # Settings and Preferences
    notification_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Notification preferences"
    )
    api_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="API access settings"
    )
    integration_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Third-party integration settings"
    )
    
    class Meta:
        db_table = 'advertisers'
        verbose_name = 'Advertiser'
        verbose_name_plural = 'Advertisers'
        indexes = [
            models.Index(fields=['company_name'], name='idx_company_name_060'),
            models.Index(fields=['industry'], name='idx_industry_061'),
            models.Index(fields=['status'], name='idx_status_062'),
            models.Index(fields=['is_verified'], name='idx_is_verified_063'),
            models.Index(fields=['created_at'], name='idx_created_at_064'),
            models.Index(fields=['user'], name='idx_user_065'),
        ]
    
    def __str__(self) -> str:
        return f"{self.company_name} ({self.id})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate email format
        if self.contact_email:
            validator = EmailValidator()
            validator(self.contact_email)
        
        # Validate URL format
        if self.website:
            validator = URLValidator()
            validator(self.website)
        
        # Validate phone format
        if self.contact_phone:
            if not re.match(r'^\+?1?\d{9,15}$', self.contact_phone.replace('-', '').replace(' ', '')):
                raise ValidationError("Invalid phone number format")
        
        # Validate country code
        if self.billing_country and len(self.billing_country) != 2:
            raise ValidationError("Country code must be 2 characters")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Generate API key if not set
        if not self.api_key:
            self.api_key = self.generate_api_key()
        
        # Update quality score
        self.quality_score = self.calculate_quality_score()
        
        # Set verification date if verified and not set
        if self.is_verified and not self.verification_date:
            self.verification_date = timezone.now()
        
        super().save(*args, **kwargs)
    
    def generate_api_key(self) -> str:
        """Generate a unique API key."""
        import secrets
        prefix = "adv_"
        unique_id = secrets.token_urlsafe(32)
        return f"{prefix}{unique_id}"
    
    def calculate_quality_score(self) -> Decimal:
        """Calculate advertiser quality score."""
        score = 0
        
        # Verification score (30 points)
        if self.is_verified:
            score += 30
        
        # Account age score (20 points)
        days_active = (timezone.now() - self.created_at).days
        score += min(days_active / 365 * 20, 20)
        
        # Spend consistency score (25 points)
        if self.total_spend > 0:
            score += min(float(self.total_spend) / 10000 * 25, 25)
        
        # Campaign performance score (25 points)
        if self.active_campaigns > 0:
            avg_performance = self.get_average_campaign_performance()
            score += min(avg_performance * 25, 25)
        
        return Decimal(str(min(score, 100)))
    
    def get_average_campaign_performance(self) -> float:
        """Get average campaign performance score."""
        campaigns = Campaign.objects.filter(
            advertiser=self,
            is_deleted=False
        )
        
        if not campaigns.exists():
            return 0.0
        
        # Simple performance calculation based on status and activity
        active_count = campaigns.filter(status='active').count()
        total_count = campaigns.count()
        
        return (active_count / total_count) if total_count > 0 else 0.0
    
    def get_active_campaigns(self) -> QuerySet['Campaign']:
        """Get all active campaigns."""
        return Campaign.objects.filter(
            advertiser=self,
            status='active',
            is_deleted=False
        )
    
    def get_total_budget_remaining(self) -> Decimal:
        """Get total remaining budget across all campaigns."""
        campaigns = self.get_active_campaigns()
        total_remaining = sum(
            campaign.remaining_budget for campaign in campaigns
        )
        return Decimal(str(total_remaining))
    
    def get_monthly_spend(self, year: int, month: int) -> Decimal:
        """Get total spend for a specific month."""
        from django.db.models import Sum
        
        start_date = timezone.datetime(year, month, 1).date()
        if month == 12:
            end_date = timezone.datetime(year + 1, 1, 1).date()
        else:
            end_date = timezone.datetime(year, month + 1, 1).date()
        
        return Campaign.objects.filter(
            advertiser=self,
            created_at__date__gte=start_date,
            created_at__date__lt=end_date,
            is_deleted=False
        ).aggregate(total=Sum('current_spend'))['total'] or Decimal('0')
    
    def can_create_campaign(self) -> bool:
        """Check if advertiser can create new campaigns."""
        max_campaigns = {
            'individual': 5,
            'business': 50,
            'enterprise': 500,
            'agency': 1000
        }
        
        max_allowed = max_campaigns.get(self.account_type, 50)
        current_count = Campaign.objects.filter(
            advertiser=self,
            is_deleted=False
        ).count()
        
        return current_count < max_allowed
    
    def get_billing_profile(self) -> Optional['BillingProfile']:
        """Get billing profile for this advertiser."""
        try:
            return self.billing_profile
        except BillingProfile.DoesNotExist:
            return None
    
    def get_primary_payment_method(self) -> Optional['PaymentMethod']:
        """Get primary payment method."""
        return PaymentMethod.objects.filter(
            advertiser=self,
            is_default=True,
            is_active=True
        ).first()
    
    def add_credit(self, amount: Decimal, credit_type: str = 'payment', description: str = '') -> bool:
        """Add credit to advertiser account."""
        try:
            with transaction.atomic():
                AdvertiserCredit.objects.create(
                    advertiser=self,
                    amount=amount,
                    credit_type=credit_type,
                    description=description
                )
                
                self.account_balance += amount
                self.save(update_fields=['account_balance'])
                
                return True
        except Exception as e:
            logger.error(f"Failed to add credit for advertiser {self.id}: {str(e)}")
            return False
    
    def deduct_credit(self, amount: Decimal, description: str = '') -> bool:
        """Deduct credit from advertiser account."""
        try:
            with transaction.atomic():
                if self.account_balance < amount:
                    return False
                
                AdvertiserCredit.objects.create(
                    advertiser=self,
                    amount=-amount,
                    credit_type='spend',
                    description=description
                )
                
                self.account_balance -= amount
                self.save(update_fields=['account_balance'])
                
                return True
        except Exception as e:
            logger.error(f"Failed to deduct credit for advertiser {self.id}: {str(e)}")
            return False
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for this advertiser."""
        campaigns = Campaign.objects.filter(
            advertiser=self,
            is_deleted=False
        )
        
        # Aggregate metrics
        metrics = campaigns.aggregate(
            total_budget=Sum('total_budget'),
            current_spend=Sum('current_spend'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            avg_ctr=Avg('ctr'),
            avg_cpc=Avg('cpc'),
            avg_conversion_rate=Avg('conversion_rate')
        )
        
        # Calculate derived metrics
        total_budget = metrics['total_budget'] or Decimal('0')
        current_spend = metrics['current_spend'] or Decimal('0')
        total_impressions = metrics['total_impressions'] or 0
        total_clicks = metrics['total_clicks'] or 0
        total_conversions = metrics['total_conversions'] or 0
        
        ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        cpc = (current_spend / total_clicks) if total_clicks > 0 else 0
        conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
        
        return {
            'total_campaigns': campaigns.count(),
            'active_campaigns': campaigns.filter(status='active').count(),
            'total_budget': float(total_budget),
            'current_spend': float(current_spend),
            'remaining_budget': float(total_budget - current_spend),
            'budget_utilization': float((current_spend / total_budget * 100) if total_budget > 0 else 0),
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'total_conversions': total_conversions,
            'ctr': round(ctr, 2),
            'cpc': round(cpc, 2),
            'conversion_rate': round(conversion_rate, 2),
            'quality_score': float(self.quality_score)
        }
    
    def update_performance_metrics(self) -> None:
        """Update performance metrics for this advertiser."""
        campaigns = Campaign.objects.filter(
            advertiser=self,
            is_deleted=False
        )
        
        # Update counts
        self.total_campaigns = campaigns.count()
        self.active_campaigns = campaigns.filter(status='active').count()
        
        # Update total spend
        total_spend = campaigns.aggregate(total=Sum('current_spend'))['total'] or Decimal('0')
        self.total_spend = total_spend
        
        # Update quality score
        self.quality_score = self.calculate_quality_score()
        
        self.save(update_fields=[
            'total_campaigns',
            'active_campaigns', 
            'total_spend',
            'quality_score'
        ])


class AdvertiserVerification(AdvertiserPortalBaseModel):
    """
    Model for tracking advertiser verification processes.
    """
    
    advertiser = models.ForeignKey(
        Advertiser,
        on_delete=models.CASCADE,
        related_name='advertiser_verifications'
    )
    verification_type = models.CharField(
        max_length=50,
        choices=[
            ('business', 'Business Verification'),
            ('identity', 'Identity Verification'),
            ('payment', 'Payment Method Verification'),
            ('compliance', 'Compliance Review')
        ],
        help_text="Type of verification"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('in_review', 'In Review'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('requires_action', 'Requires Action')
        ],
        default='pending',
        help_text="Verification status"
    )
    submitted_documents = models.JSONField(
        default=list,
        blank=True,
        help_text="List of submitted document URLs"
    )
    verification_notes = models.TextField(
        blank=True,
        help_text="Notes from verification process"
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_verifications'
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Verification expiration date"
    )
    
    class Meta:
        db_table = 'advertiser_verifications'
        verbose_name = 'Advertiser Verification'
        verbose_name_plural = 'Advertiser Verifications'
        indexes = [
            models.Index(fields=['advertiser', 'verification_type'], name='idx_advertiser_verificatio_11f'),
            models.Index(fields=['status'], name='idx_status_067'),
            models.Index(fields=['created_at'], name='idx_created_at_068'),
        ]
    
    def __str__(self) -> str:
        return f"{self.advertiser.company_name} - {self.verification_type}"


class AdvertiserCredit(AdvertiserPortalBaseModel):
    """
    Model for tracking advertiser credit transactions.
    """
    
    advertiser = models.ForeignKey(
        Advertiser,
        on_delete=models.CASCADE,
        related_name='credit_transactions'
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Credit amount (positive for credit, negative for debit)"
    )
    credit_type = models.CharField(
        max_length=50,
        choices=[
            ('payment', 'Payment'),
            ('refund', 'Refund'),
            ('bonus', 'Bonus Credit'),
            ('penalty', 'Penalty'),
            ('adjustment', 'Adjustment'),
            ('spend', 'Campaign Spend')
        ],
        help_text="Type of credit transaction"
    )
    description = models.TextField(
        blank=True,
        help_text="Transaction description"
    )
    reference_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reference ID (e.g., invoice number, transaction ID)"
    )
    balance_after = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Account balance after this transaction"
    )
    
    class Meta:
        db_table = 'advertiser_credits'
        verbose_name = 'Advertiser Credit'
        verbose_name_plural = 'Advertiser Credits'
        indexes = [
            models.Index(fields=['advertiser', 'created_at'], name='idx_advertiser_created_at_069'),
            models.Index(fields=['credit_type'], name='idx_credit_type_070'),
            models.Index(fields=['reference_id'], name='idx_reference_id_071'),
        ]
    
    def __str__(self) -> str:
        return f"{self.advertiser.company_name} - {self.credit_type} - ${self.amount}"
