# kyc/kyb/models.py  ── WORLD #1
"""
KYB = Know Your Business.
Sumsub/Jumio এর enterprise feature — business entity verification.
Bangladesh: RJSC (trade license, MOA, shareholder info).
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class BusinessVerification(models.Model):
    """Business/Company KYC (KYB) verification."""
    STATUS_CHOICES = [
        ('not_submitted','Not Submitted'), ('pending','Pending'),
        ('verified','Verified'), ('rejected','Rejected'), ('expired','Expired'),
    ]
    ENTITY_TYPES = [
        ('sole_proprietorship','Sole Proprietorship'),
        ('partnership',        'Partnership'),
        ('private_limited',    'Private Limited Company'),
        ('public_limited',     'Public Limited Company'),
        ('ngo',                'NGO / Non-Profit'),
        ('government',         'Government Entity'),
        ('other',              'Other'),
    ]
    # Linked user (business owner/admin)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='business_verifications', null=True, blank=True)
    tenant          = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)

    # Business Info
    business_name   = models.CharField(max_length=300, db_index=True, null=True, blank=True)
    entity_type     = models.CharField(max_length=25, choices=ENTITY_TYPES, null=True, blank=True)
    trade_license_no = models.CharField(max_length=100, blank=True, db_index=True, null=True)
    tin_number      = models.CharField(max_length=50, blank=True, help_text="Tax Identification Number", null=True)
    bin_number      = models.CharField(max_length=50, blank=True, help_text="Business Identification Number", null=True)
    registration_no = models.CharField(max_length=100, blank=True, help_text="RJSC / Company Registration", null=True)
    incorporation_date = models.DateField(null=True, blank=True)
    country_of_incorporation = models.CharField(max_length=100, default='Bangladesh', null=True, blank=True)
    registered_address = models.TextField(blank=True)
    operating_address  = models.TextField(blank=True)
    website         = models.URLField(null=True, blank=True)
    phone           = models.CharField(max_length=20, null=True, blank=True)
    email           = models.EmailField(blank=True)

    # Status
    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default='not_submitted', db_index=True, null=True, blank=True)
    risk_score      = models.IntegerField(default=0)
    risk_level      = models.CharField(max_length=10, default='low', null=True, blank=True)

    # Documents
    trade_license_doc   = models.FileField(upload_to='kyb/trade_license/', null=True, blank=True)
    incorporation_doc   = models.FileField(upload_to='kyb/incorporation/', null=True, blank=True)
    moa_doc             = models.FileField(upload_to='kyb/moa/', null=True, blank=True, help_text="Memorandum of Association")
    tin_doc             = models.FileField(upload_to='kyb/tin/', null=True, blank=True)
    bank_statement      = models.FileField(upload_to='kyb/bank/', null=True, blank=True)

    # Review
    reviewed_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='kyb_reviews')
    reviewed_at     = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    admin_notes     = models.TextField(blank=True)
    verified_at     = models.DateTimeField(null=True, blank=True)
    expires_at      = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyb_business_verifications'
        verbose_name = 'Business Verification (KYB)'
        ordering = ['-created_at']

    def __str__(self):
        return f"KYB[{self.entity_type}] {self.business_name} - {self.status}"

    def approve(self, reviewed_by=None):
        import datetime
        self.status = 'verified'; self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now(); self.verified_at = timezone.now()
        self.expires_at = timezone.now() + datetime.timedelta(days=365)
        self.save()

    def reject(self, reason='', reviewed_by=None):
        self.status = 'rejected'; self.rejection_reason = reason
        self.reviewed_by = reviewed_by; self.reviewed_at = timezone.now(); self.save()


class UBODeclaration(models.Model):
    """
    UBO = Ultimate Beneficial Owner.
    FATF requirement — who ultimately controls the business (>25% ownership).
    Bangladesh BB Circular + AMLD6 requirement.
    """
    business     = models.ForeignKey(BusinessVerification, on_delete=models.CASCADE, related_name='ubo_declarations', null=True, blank=True)
    full_name    = models.CharField(max_length=200, null=True, blank=True)
    nationality  = models.CharField(max_length=100, default='Bangladesh', null=True, blank=True)
    dob          = models.DateField(null=True, blank=True)
    nid_number   = models.CharField(max_length=50, null=True, blank=True)
    passport_no  = models.CharField(max_length=50, null=True, blank=True)
    ownership_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_politically_exposed = models.BooleanField(default=False)
    address      = models.TextField(blank=True)
    id_document  = models.FileField(upload_to='kyb/ubo/', null=True, blank=True)
    is_verified  = models.BooleanField(default=False)
    verified_at  = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyb_ubo_declarations'
        verbose_name = 'UBO Declaration'

    def __str__(self):
        return f"UBO {self.full_name} {self.ownership_percentage}% of {self.business.business_name}"


class BusinessDirector(models.Model):
    """Company directors/officers for KYB."""
    business     = models.ForeignKey(BusinessVerification, on_delete=models.CASCADE, related_name='directors', null=True, blank=True)
    full_name    = models.CharField(max_length=200, null=True, blank=True)
    designation  = models.CharField(max_length=100, null=True, blank=True)
    nationality  = models.CharField(max_length=100, default='Bangladesh', null=True, blank=True)
    nid_number   = models.CharField(max_length=50, null=True, blank=True)
    id_document  = models.FileField(upload_to='kyb/directors/', null=True, blank=True)
    is_verified  = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyb_directors'
        verbose_name = 'Business Director'

    def __str__(self):
        return f"{self.designation}: {self.full_name} @ {self.business.business_name}"
