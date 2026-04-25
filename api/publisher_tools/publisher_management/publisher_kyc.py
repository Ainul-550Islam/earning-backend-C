# api/publisher_tools/publisher_management/publisher_kyc.py
"""
Publisher KYC (Know Your Customer) — সম্পূর্ণ KYC verification system।
পাবলিশারের পরিচয় যাচাই ও document verification।
"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel


class PublisherKYC(TimeStampedModel):
    """
    Publisher-এর KYC (Know Your Customer) রেকর্ড।
    ব্যক্তিগত তথ্য ও পরিচয় যাচাইয়ের সম্পূর্ণ প্রক্রিয়া এখানে।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_publisherkyc_tenant', db_index=True,
    )

    KYC_STATUS_CHOICES = [
        ('not_started', _('Not Started')),
        ('in_progress', _('In Progress')),
        ('submitted',   _('Submitted — Pending Review')),
        ('approved',    _('Approved')),
        ('rejected',    _('Rejected')),
        ('expired',     _('Expired — Re-submission Required')),
        ('on_hold',     _('On Hold — Additional Info Needed')),
    ]

    KYC_TYPE_CHOICES = [
        ('individual', _('Individual Person')),
        ('business',   _('Business / Company')),
    ]

    DOCUMENT_TYPE_CHOICES = [
        # Individual
        ('national_id',       _('National ID Card')),
        ('passport',          _('Passport')),
        ('driving_license',   _('Driving License')),
        ('birth_certificate', _('Birth Certificate')),
        # Business
        ('trade_license',     _('Trade License')),
        ('tin_certificate',   _('TIN Certificate')),
        ('incorporation',     _('Certificate of Incorporation')),
        ('vat_certificate',   _('VAT Registration Certificate')),
        ('bank_statement',    _('Bank Statement')),
        ('utility_bill',      _('Utility Bill (Address Proof)')),
    ]

    RISK_LEVEL_CHOICES = [
        ('low',      _('Low Risk')),
        ('medium',   _('Medium Risk')),
        ('high',     _('High Risk')),
        ('critical', _('Critical — Requires Manual Review')),
    ]

    # ── Core Reference ────────────────────────────────────────────────────────
    publisher = models.OneToOneField(
        'publisher_tools.Publisher',
        on_delete=models.CASCADE,
        related_name='kyc',
        verbose_name=_("Publisher"),
    )
    kyc_type = models.CharField(
        max_length=20,
        choices=KYC_TYPE_CHOICES,
        default='individual',
        verbose_name=_("KYC Type"),
        db_index=True,
    )

    # ── Personal Information ──────────────────────────────────────────────────
    full_legal_name = models.CharField(
        max_length=300,
        verbose_name=_("Full Legal Name"),
        help_text=_("NID / Passport-এ যেভাবে আছে সেভাবে লিখুন"),
    )
    date_of_birth = models.DateField(
        null=True, blank=True,
        verbose_name=_("Date of Birth"),
    )
    nationality = models.CharField(
        max_length=100,
        default='Bangladeshi',
        verbose_name=_("Nationality"),
    )
    gender = models.CharField(
        max_length=10,
        choices=[('male', _('Male')), ('female', _('Female')), ('other', _('Other'))],
        blank=True,
        verbose_name=_("Gender"),
    )

    # ── Contact & Address ─────────────────────────────────────────────────────
    permanent_address = models.TextField(
        verbose_name=_("Permanent Address"),
    )
    current_address = models.TextField(
        blank=True,
        verbose_name=_("Current Address"),
        help_text=_("Permanent address থেকে আলাদা হলে লিখুন"),
    )
    city = models.CharField(max_length=100, verbose_name=_("City"))
    state_province = models.CharField(max_length=100, blank=True, verbose_name=_("State / Division"))
    postal_code = models.CharField(max_length=20, blank=True, verbose_name=_("Postal Code"))
    country = models.CharField(max_length=100, default='Bangladesh', verbose_name=_("Country"))

    # ── Identity Documents ────────────────────────────────────────────────────
    primary_document_type = models.CharField(
        max_length=30,
        choices=DOCUMENT_TYPE_CHOICES,
        verbose_name=_("Primary ID Type"),
    )
    primary_document_number = models.CharField(
        max_length=100,
        verbose_name=_("Primary Document Number"),
        help_text=_("NID number, Passport number, etc."),
    )
    primary_document_expiry = models.DateField(
        null=True, blank=True,
        verbose_name=_("Primary Document Expiry"),
    )
    primary_document_front = models.ImageField(
        upload_to='kyc/documents/primary/front/',
        null=True, blank=True,
        verbose_name=_("Primary Document Front"),
    )
    primary_document_back = models.ImageField(
        upload_to='kyc/documents/primary/back/',
        null=True, blank=True,
        verbose_name=_("Primary Document Back"),
    )

    # ── Secondary Document ────────────────────────────────────────────────────
    secondary_document_type = models.CharField(
        max_length=30,
        choices=DOCUMENT_TYPE_CHOICES,
        blank=True,
        verbose_name=_("Secondary Document Type"),
    )
    secondary_document_number = models.CharField(
        max_length=100, blank=True,
        verbose_name=_("Secondary Document Number"),
    )
    secondary_document_file = models.ImageField(
        upload_to='kyc/documents/secondary/',
        null=True, blank=True,
        verbose_name=_("Secondary Document"),
    )

    # ── Selfie / Liveness ─────────────────────────────────────────────────────
    selfie_photo = models.ImageField(
        upload_to='kyc/selfies/',
        null=True, blank=True,
        verbose_name=_("Selfie with ID"),
        help_text=_("ID card বুকের সামনে ধরে তোলা ছবি"),
    )
    liveness_check_passed = models.BooleanField(
        default=False,
        verbose_name=_("Liveness Check Passed"),
    )
    liveness_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Liveness Score (%)"),
    )

    # ── Business Information (if business KYC) ────────────────────────────────
    business_name = models.CharField(
        max_length=300, blank=True,
        verbose_name=_("Business / Company Name"),
    )
    business_registration_number = models.CharField(
        max_length=100, blank=True,
        verbose_name=_("Business Registration Number"),
    )
    tin_number = models.CharField(
        max_length=50, blank=True,
        verbose_name=_("TIN Number"),
    )
    vat_number = models.CharField(
        max_length=50, blank=True,
        verbose_name=_("VAT Number"),
    )
    trade_license_number = models.CharField(
        max_length=100, blank=True,
        verbose_name=_("Trade License Number"),
    )
    trade_license_expiry = models.DateField(
        null=True, blank=True,
        verbose_name=_("Trade License Expiry"),
    )
    trade_license_document = models.ImageField(
        upload_to='kyc/documents/trade_license/',
        null=True, blank=True,
        verbose_name=_("Trade License Document"),
    )

    # ── Tax Information ───────────────────────────────────────────────────────
    tax_country = models.CharField(
        max_length=100, default='Bangladesh',
        verbose_name=_("Tax Residency Country"),
    )
    is_tax_exempt = models.BooleanField(
        default=False,
        verbose_name=_("Tax Exempt"),
    )
    tax_form_type = models.CharField(
        max_length=20, blank=True,
        choices=[('W-9', 'W-9 (US Person)'), ('W-8BEN', 'W-8BEN (Non-US)'), ('other', 'Other')],
        verbose_name=_("Tax Form Type"),
    )

    # ── KYC Status & Review ───────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=KYC_STATUS_CHOICES,
        default='not_started',
        verbose_name=_("KYC Status"),
        db_index=True,
    )
    risk_level = models.CharField(
        max_length=10,
        choices=RISK_LEVEL_CHOICES,
        default='low',
        verbose_name=_("Risk Level"),
        db_index=True,
    )
    risk_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Risk Score (0-100)"),
    )

    # ── Review Details ────────────────────────────────────────────────────────
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Submitted At"))
    reviewed_at  = models.DateTimeField(null=True, blank=True, verbose_name=_("Reviewed At"))
    approved_at  = models.DateTimeField(null=True, blank=True, verbose_name=_("Approved At"))
    expires_at   = models.DateTimeField(null=True, blank=True, verbose_name=_("KYC Expires At"))
    reviewed_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_kyc_reviewed_by',
        verbose_name=_("Reviewed By"),
    )
    rejection_reason    = models.TextField(blank=True, verbose_name=_("Rejection Reason"))
    additional_info_request = models.TextField(blank=True, verbose_name=_("Additional Info Requested"))
    reviewer_notes      = models.TextField(blank=True, verbose_name=_("Reviewer Internal Notes"))

    # ── AML / Compliance ──────────────────────────────────────────────────────
    pep_check_passed = models.BooleanField(
        default=False,
        verbose_name=_("PEP Check Passed"),
        help_text=_("Politically Exposed Person check"),
    )
    sanctions_check_passed = models.BooleanField(
        default=False,
        verbose_name=_("Sanctions Check Passed"),
    )
    adverse_media_check = models.BooleanField(
        default=False,
        verbose_name=_("Adverse Media Check Passed"),
    )
    aml_check_result = models.JSONField(
        default=dict, blank=True,
        verbose_name=_("AML Check Result"),
    )

    # ── Verification Attempts ─────────────────────────────────────────────────
    submission_count = models.IntegerField(
        default=0,
        verbose_name=_("Submission Count"),
    )
    max_submissions = models.IntegerField(
        default=3,
        verbose_name=_("Max Allowed Submissions"),
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_publisher_kyc'
        verbose_name = _('Publisher KYC')
        verbose_name_plural = _('Publisher KYC Records')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher'], name='idx_publisher_1618'),
            models.Index(fields=['status'], name='idx_status_1619'),
            models.Index(fields=['risk_level'], name='idx_risk_level_1620'),
            models.Index(fields=['submitted_at'], name='idx_submitted_at_1621'),
        ]

    def __str__(self):
        return f"KYC: {self.publisher.publisher_id} — {self.status}"

    @property
    def is_approved(self):
        return self.status == 'approved'

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    @property
    def can_submit(self):
        return self.submission_count < self.max_submissions and self.status not in ('approved',)

    @property
    def completion_percentage(self):
        """KYC form কতটুকু fill হয়েছে সেটা calculate করে"""
        required_fields = [
            self.full_legal_name, self.date_of_birth, self.nationality,
            self.permanent_address, self.city, self.country,
            self.primary_document_type, self.primary_document_number,
            self.primary_document_front,
        ]
        filled = sum(1 for f in required_fields if f)
        return int((filled / len(required_fields)) * 100)

    def submit_for_review(self):
        """KYC review-এর জন্য submit করে"""
        if not self.can_submit:
            raise ValueError(f"Cannot submit: max submissions ({self.max_submissions}) reached or already approved.")
        if self.completion_percentage < 80:
            raise ValueError(f"KYC form is only {self.completion_percentage}% complete. Fill all required fields.")
        self.status = 'submitted'
        self.submitted_at = timezone.now()
        self.submission_count += 1
        self.save()

    def approve(self, reviewed_by=None, notes: str = ''):
        """KYC approve করে"""
        self.status = 'approved'
        self.reviewed_at = timezone.now()
        self.approved_at = timezone.now()
        self.reviewed_by = reviewed_by
        self.reviewer_notes = notes
        # KYC expires after 2 years
        from datetime import timedelta
        self.expires_at = timezone.now() + timedelta(days=730)
        self.save()

        # Update publisher KYC status
        self.publisher.is_kyc_verified = True
        self.publisher.kyc_verified_at = timezone.now()
        self.publisher.save(update_fields=['is_kyc_verified', 'kyc_verified_at', 'updated_at'])

    def reject(self, reason: str, reviewed_by=None):
        """KYC reject করে"""
        self.status = 'rejected'
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewed_by
        self.rejection_reason = reason
        self.save()

    def request_additional_info(self, info_request: str, reviewed_by=None):
        """Additional information request করে"""
        self.status = 'on_hold'
        self.additional_info_request = info_request
        self.reviewed_by = reviewed_by
        self.save()

    def calculate_risk_score(self) -> int:
        """
        Risk score calculate করে।
        AML checks, PEP status, country risk সব মিলিয়ে।
        """
        score = 0

        # High-risk countries
        high_risk_countries = ['North Korea', 'Iran', 'Syria', 'Myanmar']
        if self.country in high_risk_countries:
            score += 50

        # PEP
        if not self.pep_check_passed:
            score += 30

        # Sanctions
        if not self.sanctions_check_passed:
            score += 40

        # Missing documents
        if not self.primary_document_front:
            score += 15

        # Expired documents
        if self.primary_document_expiry and self.primary_document_expiry < timezone.now().date():
            score += 20

        self.risk_score = min(100, score)
        if self.risk_score >= 70:
            self.risk_level = 'critical'
        elif self.risk_score >= 50:
            self.risk_level = 'high'
        elif self.risk_score >= 30:
            self.risk_level = 'medium'
        else:
            self.risk_level = 'low'

        self.save(update_fields=['risk_score', 'risk_level', 'updated_at'])
        return self.risk_score


class KYCDocument(TimeStampedModel):
    """
    KYC-এর জন্য upload করা documents।
    প্রতিটি document আলাদাভাবে track হয়।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_kycdocument_tenant', db_index=True,
    )

    VERIFICATION_STATUS_CHOICES = [
        ('pending',  _('Pending Verification')),
        ('verified', _('Verified')),
        ('rejected', _('Rejected')),
        ('unclear',  _('Image Unclear — Re-upload Required')),
    ]

    kyc = models.ForeignKey(
        PublisherKYC,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name=_("KYC Record"),
    )
    document_type = models.CharField(
        max_length=30,
        choices=PublisherKYC.DOCUMENT_TYPE_CHOICES,
        verbose_name=_("Document Type"),
        db_index=True,
    )
    document_number = models.CharField(
        max_length=100, blank=True,
        verbose_name=_("Document Number"),
    )
    document_file = models.ImageField(
        upload_to='kyc/documents/uploads/',
        verbose_name=_("Document File"),
    )
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.IntegerField(default=0, verbose_name=_("File Size (bytes)"))
    file_type = models.CharField(max_length=50, blank=True, verbose_name=_("File Type"))

    issue_date  = models.DateField(null=True, blank=True, verbose_name=_("Issue Date"))
    expiry_date = models.DateField(null=True, blank=True, verbose_name=_("Expiry Date"))
    issuing_authority = models.CharField(max_length=200, blank=True, verbose_name=_("Issuing Authority"))
    issuing_country   = models.CharField(max_length=100, blank=True, verbose_name=_("Issuing Country"))

    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default='pending',
        verbose_name=_("Verification Status"),
        db_index=True,
    )
    rejection_reason = models.TextField(blank=True, verbose_name=_("Rejection Reason"))
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_kycdoc_verified_by',
    )
    ocr_extracted_data = models.JSONField(
        default=dict, blank=True,
        verbose_name=_("OCR Extracted Data"),
        help_text=_("Automated text extraction result"),
    )

    class Meta:
        db_table = 'publisher_tools_kyc_documents'
        verbose_name = _('KYC Document')
        verbose_name_plural = _('KYC Documents')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['kyc', 'document_type'], name='idx_kyc_document_type_1622'),
            models.Index(fields=['verification_status'], name='idx_verification_status_1623'),
        ]

    def __str__(self):
        return f"{self.kyc.publisher.publisher_id} — {self.document_type} [{self.verification_status}]"

    @property
    def is_expired(self):
        if self.expiry_date:
            return self.expiry_date < timezone.now().date()
        return False

    def verify(self, verified_by=None):
        self.verification_status = 'verified'
        self.verified_at = timezone.now()
        self.verified_by = verified_by
        self.save()

    def reject_document(self, reason: str, verified_by=None):
        self.verification_status = 'rejected'
        self.rejection_reason = reason
        self.verified_by = verified_by
        self.save()
