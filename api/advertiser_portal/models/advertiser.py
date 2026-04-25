"""
Advertiser Models for Advertiser Portal

This module contains models for managing advertisers,
their profiles, verification, and agreements.
"""

import logging
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

User = get_user_model()


class Advertiser(models.Model):
    """
    Model for managing advertiser accounts.
    
    Stores advertiser information including company details,
    verification status, and account management.
    """
    
    # Core fields
    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='advertiser_profile',
        verbose_name=_('User'),
        help_text=_('User account associated with this advertiser')
    )
    
    company_name = models.CharField(
        _('Company Name'),
        max_length=200,
        db_index=True,
        help_text=_('Legal company name')
    )
    
    website = models.URLField(
        _('Website'),
        max_length=500,
        help_text=_('Company website URL')
    )
    
    business_type = models.CharField(
        _('Business Type'),
        max_length=50,
        choices=[
            ('individual', _('Individual')),
            ('small_business', _('Small Business')),
            ('medium_business', _('Medium Business')),
            ('enterprise', _('Enterprise')),
            ('agency', _('Agency')),
            ('network', _('Network')),
        ],
        default='small_business',
        db_index=True,
        help_text=_('Type of business entity')
    )
    
    # Account status
    verification_status = models.CharField(
        _('Verification Status'),
        max_length=20,
        choices=[
            ('pending', _('Pending')),
            ('in_review', _('In Review')),
            ('verified', _('Verified')),
            ('rejected', _('Rejected')),
            ('suspended', _('Suspended')),
        ],
        default='pending',
        db_index=True,
        help_text=_('Current verification status')
    )
    
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        db_index=True,
        help_text=_('Whether this advertiser account is active')
    )
    
    is_approved = models.BooleanField(
        _('Is Approved'),
        default=False,
        db_index=True,
        help_text=_('Whether this advertiser has been approved')
    )
    
    # Account management
    account_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_advertisers',
        verbose_name=_('Account Manager'),
        help_text=_('Account manager assigned to this advertiser')
    )
    
    # Business details
    business_email = models.EmailField(
        _('Business Email'),
        help_text=_('Primary business contact email')
    )
    
    business_phone = models.CharField(
        _('Business Phone'),
        max_length=20,
        null=True,
        blank=True,
        help_text=_('Business contact phone number')
    )
    
    business_address = models.TextField(
        _('Business Address'),
        null=True,
        blank=True,
        help_text=_('Full business address')
    )
    
    # Tax and legal
    tax_id = models.CharField(
        _('Tax ID'),
        max_length=50,
        null=True,
        blank=True,
        help_text=_('Tax identification number')
    )
    
    registration_number = models.CharField(
        _('Registration Number'),
        max_length=50,
        null=True,
        blank=True,
        help_text=_('Business registration number')
    )
    
    # Financial information
    billing_currency = models.CharField(
        _('Billing Currency'),
        max_length=3,
        default='USD',
        help_text=_('Currency for billing (3-letter code)')
    )
    
    payment_method = models.CharField(
        _('Payment Method'),
        max_length=50,
        choices=[
            ('credit_card', _('Credit Card')),
            ('bank_transfer', _('Bank Transfer')),
            ('paypal', _('PayPal')),
            ('wire', _('Wire Transfer')),
            ('crypto', _('Cryptocurrency')),
        ],
        default='credit_card',
        help_text=_('Preferred payment method')
    )
    
    credit_limit = models.DecimalField(
        _('Credit Limit'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Credit limit for this advertiser')
    )
    
    # Communication preferences
    email_notifications = models.BooleanField(
        _('Email Notifications'),
        default=True,
        help_text=_('Whether to send email notifications')
    )
    
    sms_notifications = models.BooleanField(
        _('SMS Notifications'),
        default=False,
        help_text=_('Whether to send SMS notifications')
    )
    
    # API access
    api_key = models.CharField(
        _('API Key'),
        max_length=255,
        unique=True,
        help_text=_('API key for programmatic access')
    )
    
    api_secret = models.CharField(
        _('API Secret'),
        max_length=255,
        help_text=_('API secret for authentication')
    )
    
    api_permissions = models.JSONField(
        _('API Permissions'),
        default=list,
        blank=True,
        help_text=_('List of API permissions granted')
    )
    
    # Settings
    timezone = models.CharField(
        _('Timezone'),
        max_length=50,
        default='UTC',
        help_text=_('Advertiser timezone')
    )
    
    language = models.CharField(
        _('Language'),
        max_length=10,
        default='en',
        help_text=_('Preferred language code')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        db_index=True,
        help_text=_('When this advertiser account was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this advertiser account was last updated')
    )
    
    last_login_at = models.DateTimeField(
        _('Last Login At'),
        null=True,
        blank=True,
        help_text=_('Last login timestamp')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_advertiser'
        verbose_name = _('Advertiser')
        verbose_name_plural = _('Advertisers')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active'], name='idx_user_is_active_378'),
            models.Index(fields=['verification_status', 'is_active'], name='idx_verification_status_is_65a'),
            models.Index(fields=['business_type', 'is_active'], name='idx_business_type_is_activ_563'),
            models.Index(fields=['created_at'], name='idx_created_at_381'),
            models.Index(fields=['company_name'], name='idx_company_name_382'),
        ]
    
    def __str__(self):
        return f"{self.company_name} ({self.user.username})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate API key uniqueness
        if self.api_key and Advertiser.objects.filter(api_key=self.api_key).exclude(id=self.id).exists():
            raise ValidationError(_('API key must be unique'))
        
        # Validate credit limit
        if self.credit_limit < 0:
            raise ValidationError(_('Credit limit cannot be negative'))
    
    @property
    def is_verified(self) -> bool:
        """Check if advertiser is verified."""
        return self.verification_status == 'verified'
    
    @property
    def can_create_campaigns(self) -> bool:
        """Check if advertiser can create campaigns."""
        return self.is_active and self.is_approved and self.is_verified
    
    @property
    def account_status_display(self) -> str:
        """Get human-readable account status."""
        status_map = {
            'pending': _('Pending Verification'),
            'in_review': _('Under Review'),
            'verified': _('Verified'),
            'rejected': _('Rejected'),
            'suspended': _('Suspended'),
        }
        return status_map.get(self.verification_status, _('Unknown'))
    
    def get_active_campaigns(self):
        """Get all active campaigns for this advertiser."""
        return self.campaigns.filter(
            is_active=True,
            start_date__lte=timezone.now(),
            end_date__gte=timezone.now()
        )
    
    def get_total_spend(self, days: int = 30) -> float:
        """Get total spend in last N days."""
        from .campaign import CampaignSpend
        
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        total_spend = CampaignSpend.objects.filter(
            campaign__advertiser=self,
            date__gte=cutoff_date
        ).aggregate(
            total=models.Sum('spend_amount')
        )['total'] or 0
        
        return float(total_spend)
    
    def get_current_balance(self) -> float:
        """Get current account balance."""
        from .billing import AdvertiserWallet
        
        wallet = AdvertiserWallet.objects.filter(advertiser=self).first()
        return float(wallet.balance) if wallet else 0.0


class AdvertiserProfile(models.Model):
    """
    Extended profile information for advertisers.
    
    Stores detailed profile data including address,
    contact information, and company details.
    """
    
    # Core relationship
    advertiser = models.OneToOneField(
        Advertiser,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this profile belongs to')
    )
    
    # Address information
    address_line_1 = models.CharField(
        _('Address Line 1'),
        max_length=255,
        help_text=_('Street address line 1')
    )
    
    address_line_2 = models.CharField(
        _('Address Line 2'),
        max_length=255,
        null=True,
        blank=True,
        help_text=_('Street address line 2')
    )
    
    city = models.CharField(
        _('City'),
        max_length=100,
        help_text=_('City name')
    )
    
    state = models.CharField(
        _('State/Province'),
        max_length=100,
        help_text=_('State or province name')
    )
    
    postal_code = models.CharField(
        _('Postal Code'),
        max_length=20,
        help_text=_('Postal or ZIP code')
    )
    
    country = models.CharField(
        _('Country'),
        max_length=2,
        help_text=_('Country code (ISO 3166-1 alpha-2)')
    )
    
    # Contact information
    contact_name = models.CharField(
        _('Contact Name'),
        max_length=100,
        help_text=_('Primary contact person name')
    )
    
    contact_title = models.CharField(
        _('Contact Title'),
        max_length=100,
        null=True,
        blank=True,
        help_text=_('Contact person job title')
    )
    
    contact_phone = models.CharField(
        _('Contact Phone'),
        max_length=20,
        help_text=_('Contact person phone number')
    )
    
    contact_email = models.EmailField(
        _('Contact Email'),
        help_text=_('Contact person email address')
    )
    
    # Company details
    industry = models.CharField(
        _('Industry'),
        max_length=100,
        help_text=_('Industry category')
    )
    
    company_size = models.CharField(
        _('Company Size'),
        max_length=50,
        choices=[
            ('1-10', _('1-10 employees')),
            ('11-50', _('11-50 employees')),
            ('51-200', _('51-200 employees')),
            ('201-500', _('201-500 employees')),
            ('501-1000', _('501-1000 employees')),
            ('1000+', _('1000+ employees')),
        ],
        null=True,
        blank=True,
        help_text=_('Number of employees')
    )
    
    annual_revenue = models.CharField(
        _('Annual Revenue'),
        max_length=50,
        choices=[
            ('<100k', _('< $100K')),
            ('100k-500k', _('$100K - $500K')),
            ('500k-1m', _('$500K - $1M')),
            ('1m-5m', _('$1M - $5M')),
            ('5m-10m', _('$5M - $10M')),
            ('10m-50m', _('$10M - $50M')),
            ('50m+', _('> $50M')),
        ],
        null=True,
        blank=True,
        help_text=_('Annual revenue range')
    )
    
    # Marketing information
    website_traffic = models.CharField(
        _('Website Traffic'),
        max_length=50,
        choices=[
            ('<1k', _('< 1K monthly')),
            ('1k-10k', _('1K - 10K monthly')),
            ('10k-100k', _('10K - 100K monthly')),
            ('100k-1m', _('100K - 1M monthly')),
            ('1m+', _('> 1M monthly')),
        ],
        null=True,
        blank=True,
        help_text=_('Monthly website traffic')
    )
    
    target_audience = models.JSONField(
        _('Target Audience'),
        default=list,
        blank=True,
        help_text=_('Target audience demographics')
    )
    
    # Brand information
    brand_description = models.TextField(
        _('Brand Description'),
        null=True,
        blank=True,
        help_text=_('Description of brand and products/services')
    )
    
    logo = models.ImageField(
        _('Logo'),
        upload_to='advertiser_logos/',
        null=True,
        blank=True,
        help_text=_('Company logo image')
    )
    
    brand_colors = models.JSONField(
        _('Brand Colors'),
        default=list,
        blank=True,
        help_text=_('Primary brand colors (hex codes)')
    )
    
    # Social media
    facebook_url = models.URLField(
        _('Facebook URL'),
        null=True,
        blank=True,
        help_text=_('Facebook page URL')
    )
    
    twitter_url = models.URLField(
        _('Twitter URL'),
        null=True,
        blank=True,
        help_text=_('Twitter profile URL')
    )
    
    linkedin_url = models.URLField(
        _('LinkedIn URL'),
        null=True,
        blank=True,
        help_text=_('LinkedIn company page URL')
    )
    
    # Preferences
    preferred_campaign_types = models.JSONField(
        _('Preferred Campaign Types'),
        default=list,
        blank=True,
        help_text=_('Preferred campaign objectives')
    )
    
    budget_range_min = models.DecimalField(
        _('Minimum Budget'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Minimum campaign budget')
    )
    
    budget_range_max = models.DecimalField(
        _('Maximum Budget'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Maximum campaign budget')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this profile was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this profile was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_advertiser_profile'
        verbose_name = _('Advertiser Profile')
        verbose_name_plural = _('Advertiser Profiles')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser'], name='idx_advertiser_383'),
            models.Index(fields=['country'], name='idx_country_384'),
            models.Index(fields=['industry'], name='idx_industry_385'),
            models.Index(fields=['created_at'], name='idx_created_at_386'),
        ]
    
    def __str__(self):
        return f"Profile: {self.advertiser.company_name}"
    
    @property
    def full_address(self) -> str:
        """Get formatted full address."""
        parts = [self.address_line_1]
        
        if self.address_line_2:
            parts.append(self.address_line_2)
        
        parts.extend([self.city, self.state, self.postal_code, self.country])
        
        return ', '.join(filter(None, parts))
    
    @property
    def primary_contact(self) -> str:
        """Get primary contact information."""
        if self.contact_name:
            return f"{self.contact_name} ({self.contact_email})"
        return f"{self.advertiser.business_email}"
    
    def get_completion_percentage(self) -> float:
        """Calculate profile completion percentage."""
        required_fields = [
            'address_line_1', 'city', 'state', 'postal_code', 'country',
            'contact_name', 'contact_phone', 'contact_email',
            'industry', 'brand_description'
        ]
        
        completed = sum(1 for field in required_fields if getattr(self, field))
        
        return (completed / len(required_fields)) * 100


class AdvertiserVerification(models.Model):
    """
    Model for tracking advertiser verification process.
    
    Stores verification documents, status, and review history.
    """
    
    # Core relationship
    advertiser = models.ForeignKey(
        Advertiser,
        on_delete=models.CASCADE,
        related_name='verifications',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser being verified')
    )
    
    # Verification details
    document_type = models.CharField(
        _('Document Type'),
        max_length=50,
        choices=[
            ('business_license', _('Business License')),
            ('tax_certificate', _('Tax Certificate')),
            ('id_document', _('ID Document')),
            ('bank_statement', _('Bank Statement')),
            ('proof_of_address', _('Proof of Address')),
            ('company_registration', _('Company Registration')),
            ('other', _('Other')),
        ],
        help_text=_('Type of verification document')
    )
    
    document_file = models.FileField(
        _('Document File'),
        upload_to='verification_documents/',
        help_text=_('Uploaded verification document')
    )
    
    document_number = models.CharField(
        _('Document Number'),
        max_length=100,
        null=True,
        blank=True,
        help_text=_('Document identification number')
    )
    
    # Verification status
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=[
            ('pending', _('Pending')),
            ('in_review', _('In Review')),
            ('approved', _('Approved')),
            ('rejected', _('Rejected')),
            ('expired', _('Expired')),
        ],
        default='pending',
        db_index=True,
        help_text=_('Current verification status')
    )
    
    rejection_reason = models.TextField(
        _('Rejection Reason'),
        null=True,
        blank=True,
        help_text=_('Reason for rejection if applicable')
    )
    
    # Review information
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_verifications',
        verbose_name=_('Reviewed By'),
        help_text=_('User who reviewed this verification')
    )
    
    review_notes = models.TextField(
        _('Review Notes'),
        null=True,
        blank=True,
        help_text=_('Notes from review process')
    )
    
    # Expiration
    expires_at = models.DateTimeField(
        _('Expires At'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('When this verification expires')
    )
    
    # Metadata
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional verification metadata')
    )
    
    # Timestamps
    submitted_at = models.DateTimeField(
        _('Submitted At'),
        auto_now_add=True,
        db_index=True,
        help_text=_('When verification was submitted')
    )
    
    reviewed_at = models.DateTimeField(
        _('Reviewed At'),
        null=True,
        blank=True,
        help_text=_('When verification was reviewed')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When verification was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_advertiser_verification'
        verbose_name = _('Advertiser Verification')
        verbose_name_plural = _('Advertiser Verifications')
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['advertiser', 'status'], name='idx_advertiser_status_387'),
            models.Index(fields=['document_type', 'status'], name='idx_document_type_status_388'),
            models.Index(fields=['submitted_at'], name='idx_submitted_at_389'),
            models.Index(fields=['expires_at'], name='idx_expires_at_390'),
        ]
    
    def __str__(self):
        return f"Verification: {self.advertiser.company_name} - {self.document_type}"
    
    @property
    def is_expired(self) -> bool:
        """Check if verification is expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def is_approved(self) -> bool:
        """Check if verification is approved."""
        return self.status == 'approved'
    
    @property
    def needs_review(self) -> bool:
        """Check if verification needs review."""
        return self.status in ['pending', 'in_review']
    
    def get_file_size_display(self) -> str:
        """Get human-readable file size."""
        if self.document_file:
            size = self.document_file.size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        return "N/A"


class AdvertiserAgreement(models.Model):
    """
    Model for managing advertiser agreements.
    
    Stores terms of service, privacy policy, and
    other legal agreements.
    """
    
    # Core relationship
    advertiser = models.ForeignKey(
        Advertiser,
        on_delete=models.CASCADE,
        related_name='agreements',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this agreement belongs to')
    )
    
    # Agreement details
    agreement_type = models.CharField(
        _('Agreement Type'),
        max_length=50,
        choices=[
            ('terms_of_service', _('Terms of Service')),
            ('privacy_policy', _('Privacy Policy')),
            ('advertiser_agreement', _('Advertiser Agreement')),
            ('payment_terms', _('Payment Terms')),
            ('data_processing', _('Data Processing Agreement')),
            ('compliance', _('Compliance Agreement')),
        ],
        help_text=_('Type of agreement')
    )
    
    terms_version = models.CharField(
        _('Terms Version'),
        max_length=20,
        help_text=_('Version of terms and conditions')
    )
    
    agreement_text = models.TextField(
        _('Agreement Text'),
        help_text=_('Full text of the agreement')
    )
    
    # Signature information
    signed_at = models.DateTimeField(
        _('Signed At'),
        auto_now_add=True,
        db_index=True,
        help_text=_('When agreement was signed')
    )
    
    ip_address = models.GenericIPAddressField(
        _('IP Address'),
        help_text=_('IP address of user when signing')
    )
    
    user_agent = models.TextField(
        _('User Agent'),
        help_text=_('User agent string when signing')
    )
    
    # Status
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        help_text=_('Whether this agreement is currently active')
    )
    
    expires_at = models.DateTimeField(
        _('Expires At'),
        null=True,
        blank=True,
        help_text=_('When this agreement expires')
    )
    
    # Metadata
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional agreement metadata')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this agreement was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this agreement was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_advertiser_agreement'
        verbose_name = _('Advertiser Agreement')
        verbose_name_plural = _('Advertiser Agreements')
        ordering = ['-signed_at']
        indexes = [
            models.Index(fields=['advertiser', 'agreement_type'], name='idx_advertiser_agreement_t_0bb'),
            models.Index(fields=['agreement_type', 'is_active'], name='idx_agreement_type_is_acti_798'),
            models.Index(fields=['signed_at'], name='idx_signed_at_393'),
            models.Index(fields=['expires_at'], name='idx_expires_at_394'),
        ]
        unique_together = [
            ['advertiser', 'agreement_type', 'terms_version'],
        ]
    
    def __str__(self):
        return f"Agreement: {self.advertiser.company_name} - {self.agreement_type}"
    
    @property
    def is_expired(self) -> bool:
        """Check if agreement is expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def is_current(self) -> bool:
        """Check if this is the current active agreement."""
        return self.is_active and not self.is_expired
    
    def get_display_name(self) -> str:
        """Get human-readable agreement name."""
        type_names = {
            'terms_of_service': _('Terms of Service'),
            'privacy_policy': _('Privacy Policy'),
            'advertiser_agreement': _('Advertiser Agreement'),
            'payment_terms': _('Payment Terms'),
            'data_processing': _('Data Processing Agreement'),
            'compliance': _('Compliance Agreement'),
        }
        return type_names.get(self.agreement_type, self.agreement_type)


# Signal handlers for advertiser models
        app_label = 'advertiser_portal_v2'
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=Advertiser)
def advertiser_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for advertisers."""
    if created:
        logger.info(f"New advertiser created: {instance.company_name}")
        
        # Send welcome notification
        from .notification import AdvertiserNotification
        AdvertiserNotification.objects.create(
            advertiser=instance,
            type='welcome',
            title=_('Welcome to Advertiser Portal'),
            message=_('Your advertiser account has been created successfully.'),
        )

@receiver(post_save, sender=AdvertiserVerification)
def verification_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for verifications."""
    if created:
        logger.info(f"New verification submitted: {instance.advertiser.company_name} - {instance.document_type}")
        
        # Notify account manager
        if instance.advertiser.account_manager:
            from .notification import AdvertiserNotification
            AdvertiserNotification.objects.create(
                advertiser=instance.advertiser,
                type='verification_submitted',
                title=_('New Verification Submitted'),
                message=f'Verification document submitted: {instance.document_type}',
            )

@receiver(post_save, sender=AdvertiserAgreement)
def agreement_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for agreements."""
    if created:
        logger.info(f"New agreement signed: {instance.advertiser.company_name} - {instance.agreement_type}")
        
        # Update advertiser verification status if terms of service signed
        if instance.agreement_type == 'terms_of_service':
            instance.advertiser.verification_status = 'in_review'
            instance.advertiser.save()
