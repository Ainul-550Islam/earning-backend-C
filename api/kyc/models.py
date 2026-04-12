# kyc/models.py  ── WORLD #1 COMPLETE — 23 Model Classes
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 1 ─ KYC  (original — unchanged)
# ══════════════════════════════════════════════════════════════════════════════
class KYC(models.Model):
    """KYC verification for users"""
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant', db_index=True,
    )
    STATUS_CHOICES = [
        ('not_submitted', 'Not Submitted'), ('pending', 'Pending Review'),
        ('verified', 'Verified'),           ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]
    DOCUMENT_TYPES = [
        ('nid', 'National ID'), ('passport', 'Passport'),
        ('driving_license', 'Driving License'),
    ]
    user             = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    full_name        = models.CharField(max_length=200, null=True, blank=True)
    date_of_birth    = models.DateField(null=True, blank=True)
    phone_number     = models.CharField(max_length=20, null=True, blank=True)
    payment_number   = models.CharField(max_length=20, help_text="bKash/Nagad number", null=True, blank=True)
    payment_method   = models.CharField(max_length=20, default='bkash', null=True, blank=True)
    address_line     = models.TextField(blank=True)
    city             = models.CharField(max_length=100, null=True, blank=True)
    country          = models.CharField(max_length=100, default='Bangladesh', null=True, blank=True)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_submitted', null=True, blank=True)
    is_name_verified    = models.BooleanField(default=False)
    is_phone_verified   = models.BooleanField(default=False)
    is_payment_verified = models.BooleanField(default=False)
    document_type    = models.CharField(max_length=20, choices=DOCUMENT_TYPES, null=True, blank=True)
    document_number  = models.CharField(max_length=50, null=True, blank=True)
    document_front   = models.ImageField(upload_to='kyc/documents/', null=True, blank=True)
    document_back    = models.ImageField(upload_to='kyc/documents/', null=True, blank=True)
    selfie_photo     = models.ImageField(upload_to='kyc/selfies/', null=True, blank=True)
    is_face_verified    = models.BooleanField(default=False)
    extracted_name   = models.CharField(max_length=200, null=True, blank=True)
    extracted_dob    = models.DateField(null=True, blank=True)
    extracted_nid    = models.CharField(max_length=50, null=True, blank=True)
    ocr_confidence   = models.FloatField(default=0.0)
    reviewed_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='kyc_kyc_reviewed_by'
    )
    reviewed_at      = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    admin_notes      = models.TextField(blank=True)
    is_duplicate     = models.BooleanField(default=False)
    duplicate_of     = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant'
    )
    risk_score       = models.IntegerField(default=0, help_text="0-100")
    risk_factors     = models.JSONField(default=list, blank=True)
    verified_at      = models.DateTimeField(null=True, blank=True)
    expires_at       = models.DateTimeField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc'
        verbose_name = 'KYC'
        verbose_name_plural = 'KYC Records'

    def __str__(self): return f"{self.user.username} - {self.get_status_display()}"

    def submit_for_review(self):
        if self.status == 'not_submitted':
            self.status = 'pending'; self.save()

    def approve(self, reviewed_by=None):
        from datetime import timedelta
        self.status = 'verified'; self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now(); self.verified_at = timezone.now()
        self.expires_at = timezone.now() + timedelta(days=365); self.save()
        user = self.user
        if hasattr(user, 'is_verified'):
            user.is_verified = True; user.save()

    def reject(self, reason='', reviewed_by=None):
        self.status = 'rejected'; self.rejection_reason = reason
        self.reviewed_by = reviewed_by; self.reviewed_at = timezone.now(); self.save()

    def calculate_risk_score(self):
        score = 0; factors = []
        if self.extracted_name and self.full_name:
            from difflib import SequenceMatcher
            sim = SequenceMatcher(None, self.extracted_name.lower(), self.full_name.lower()).ratio()
            if sim < 0.8: score += 30; factors.append('Name mismatch')
        if self.date_of_birth:
            from datetime import date
            age = (date.today() - self.date_of_birth).days / 365.25
            if age < 18: score += 50; factors.append('Under 18')
        if self.is_duplicate: score += 40; factors.append('Duplicate KYC')
        if self.ocr_confidence < 0.7: score += 20; factors.append('Low OCR confidence')
        self.risk_score = min(score, 100); self.risk_factors = factors; self.save()
        return self.risk_score


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 2 ─ KYCSubmission  (original — unchanged)
# ══════════════════════════════════════════════════════════════════════════════
class KYCSubmission(models.Model):
    class StatusChoices(models.TextChoices):
        SUBMITTED      = "submitted",      "Submitted"
        PENDING_REVIEW = "pending",        "Pending Review"
        VERIFIED       = "verified",       "Verified"
        REJECTED       = "rejected",       "Rejected"

    class DocumentTypeChoices(models.TextChoices):
        NID             = "nid",             "NID"
        PASSPORT        = "passport",        "Passport"
        DRIVING_LICENSE = "driving_license", "Driving License"

    class FaceLivenessChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILURE = "failure", "Failure"

    user                    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kyc_submissions", null=True, blank=True)
    status                  = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.SUBMITTED, db_index=True, null=True, blank=True)
    verification_progress   = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)], db_index=True)
    document_type           = models.CharField(max_length=30, choices=DocumentTypeChoices.choices, db_index=True, null=True, blank=True)
    document_number         = models.CharField(max_length=50, db_index=True, null=True, blank=True)
    nid_front               = models.ImageField(upload_to="kyc/nid/front/")
    nid_back                = models.ImageField(upload_to="kyc/nid/back/")
    selfie_with_note        = models.ImageField(upload_to="kyc/selfie/")
    image_clarity_score     = models.FloatField(default=0.0)
    document_matching_score = models.FloatField(default=0.0)
    face_liveness_check     = models.CharField(max_length=20, choices=FaceLivenessChoices.choices, default=FaceLivenessChoices.PENDING, db_index=True, null=True, blank=True)
    rejection_reason        = models.TextField(blank=True, default="")
    created_at              = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at              = models.DateTimeField(auto_now=True)
    submitted_at            = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "kyc_submissions"
        verbose_name = "KYC Submission"
        verbose_name_plural = "KYC Submissions"
        indexes = [models.Index(fields=["user", "created_at"]), models.Index(fields=["user", "status"])]

    def __str__(self): return f"KYCSubmission(user={self.user_id}, status={self.status}, progress={self.verification_progress}%)"

    def set_submitted(self):
        self.status = self.StatusChoices.SUBMITTED; self.verification_progress = 10
        self.face_liveness_check = self.FaceLivenessChoices.PENDING
        self.image_clarity_score = 0.0; self.document_matching_score = 0.0
        self.rejection_reason = self.rejection_reason or ""; self.submitted_at = timezone.now(); self.save()

    def set_fraud_check_results(self, *, clarity, matching, liveness, progress):
        self.image_clarity_score = float(clarity); self.document_matching_score = float(matching)
        self.face_liveness_check = liveness; self.verification_progress = int(progress)
        self.status = self.StatusChoices.PENDING_REVIEW; self.save()

    def set_verified(self):
        self.status = self.StatusChoices.VERIFIED; self.verification_progress = 100
        self.save(update_fields=["status", "verification_progress", "updated_at"])

    def set_rejected(self, reason=""):
        self.status = self.StatusChoices.REJECTED; self.rejection_reason = reason or ""
        self.save(update_fields=["status", "rejection_reason", "updated_at"])

    def _sync_to_legacy_users_kyc(self):
        try:
            from api.users.models import KYCVerification
        except Exception:
            return
        status_map = {
            self.StatusChoices.SUBMITTED: "submitted", self.StatusChoices.PENDING_REVIEW: "under_review",
            self.StatusChoices.VERIFIED: "approved",   self.StatusChoices.REJECTED: "rejected",
        }
        legacy_status = status_map.get(self.status, "pending")
        kyc_obj = KYCVerification.objects.filter(user=self.user).first()
        if not kyc_obj and not self.nid_front: return
        if not kyc_obj:
            kyc_obj = KYCVerification(user=self.user, verification_status=legacy_status,
                document_type=self.document_type, document_number=self.document_number,
                front_image=self.nid_front, back_image=self.nid_back if self.nid_back else None,
                selfie_with_id_note=self.selfie_with_note if self.selfie_with_note else None)
            if self.submitted_at: kyc_obj.submitted_at = self.submitted_at
            if self.status == self.StatusChoices.REJECTED: kyc_obj.rejection_reason = self.rejection_reason or ""
            kyc_obj.save(); return
        kyc_obj.verification_status = legacy_status; kyc_obj.document_type = self.document_type
        kyc_obj.document_number = self.document_number
        if self.nid_front: kyc_obj.front_image = self.nid_front
        if self.nid_back: kyc_obj.back_image = self.nid_back
        if self.selfie_with_note: kyc_obj.selfie_with_id_note = self.selfie_with_note
        if self.submitted_at: kyc_obj.submitted_at = self.submitted_at
        if self.status == self.StatusChoices.REJECTED: kyc_obj.rejection_reason = self.rejection_reason or ""
        kyc_obj.save()

    def save(self, *args, **kwargs):
        prev_status = None
        if self.pk:
            try: prev_status = KYCSubmission.objects.only("status").get(pk=self.pk).status
            except Exception: prev_status = None
        super().save(*args, **kwargs)
        if prev_status is None or prev_status != self.status:
            self._sync_to_legacy_users_kyc()


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 3 ─ KYCVerificationLog  (original — unchanged)
# ══════════════════════════════════════════════════════════════════════════════
class KYCVerificationLog(models.Model):
    """Log all KYC verification attempts"""
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant', db_index=True,
    )
    kyc          = models.ForeignKey(KYC, on_delete=models.CASCADE, related_name='%(app_label)s_%(class)s_tenant')
    action       = models.CharField(max_length=50, null=True, blank=True)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    details      = models.TextField()
    metadata     = models.JSONField(default=dict)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta: ordering = ['-created_at']


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 4 ─ KYCBlacklist  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCBlacklist(models.Model):
    """
    Blacklisted phone numbers, document numbers, IPs.
    যেকোনো KYC submit এর আগে এই list check হবে।
    """
    TYPE_CHOICES = [
        ('phone',    'Phone Number'),
        ('document', 'Document Number'),
        ('ip',       'IP Address'),
        ('email',    'Email'),
        ('nid',      'NID Number'),
    ]
    type         = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True, null=True, blank=True)
    value        = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    reason       = models.TextField(blank=True)
    is_active    = models.BooleanField(default=True, db_index=True)
    added_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    tenant       = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    expires_at   = models.DateTimeField(null=True, blank=True, help_text="Null = permanent")

    class Meta:
        db_table = 'kyc_blacklist'
        verbose_name = 'KYC Blacklist Entry'
        verbose_name_plural = 'KYC Blacklist'
        unique_together = [('type', 'value')]
        indexes = [models.Index(fields=['type', 'value', 'is_active'])]

    def __str__(self): return f"[{self.type.upper()}] {self.value}"

    @classmethod
    def is_blacklisted(cls, btype: str, value: str) -> bool:
        now = timezone.now()
        return cls.objects.filter(
            type=btype, value=value, is_active=True
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        ).exists()


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 5 ─ KYCRiskProfile  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCRiskProfile(models.Model):
    """
    Detailed risk scoring profile per KYC.
    Auto-computed — admin শুধু দেখতে পারবে।
    """
    RISK_LEVEL_CHOICES = [
        ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical'),
    ]
    kyc                    = models.OneToOneField(KYC, on_delete=models.CASCADE, related_name='risk_profile', null=True, blank=True)
    risk_level             = models.CharField(max_length=10, choices=RISK_LEVEL_CHOICES, default='low', db_index=True, null=True, blank=True)
    overall_score          = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    name_match_score       = models.FloatField(default=0.0)
    face_match_score       = models.FloatField(default=0.0)
    document_clarity_score = models.FloatField(default=0.0)
    ocr_confidence_score   = models.FloatField(default=0.0)
    duplicate_flag         = models.BooleanField(default=False)
    age_flag               = models.BooleanField(default=False)
    blacklist_flag         = models.BooleanField(default=False)
    vpn_flag               = models.BooleanField(default=False)
    multiple_attempts_flag = models.BooleanField(default=False)
    factors                = models.JSONField(default=list)
    computed_at            = models.DateTimeField(auto_now=True)
    requires_manual_review = models.BooleanField(default=False, db_index=True)
    notes                  = models.TextField(blank=True)

    class Meta:
        db_table = 'kyc_risk_profiles'
        verbose_name = 'KYC Risk Profile'

    def __str__(self): return f"Risk[{self.risk_level.upper()}:{self.overall_score}] - {self.kyc}"

    def compute(self):
        """Compute and save risk profile"""
        score = 0; factors = []
        if self.name_match_score < 0.8:     score += 30; factors.append('name_mismatch')
        if self.face_match_score < 0.8:     score += 35; factors.append('face_mismatch')
        if self.document_clarity_score < 40: score += 20; factors.append('low_clarity')
        if self.ocr_confidence_score < 0.7: score += 20; factors.append('low_ocr')
        if self.duplicate_flag:             score += 40; factors.append('duplicate')
        if self.age_flag:                   score += 50; factors.append('age_under_18')
        if self.blacklist_flag:             score += 60; factors.append('blacklisted')
        if self.vpn_flag:                   score += 25; factors.append('vpn_detected')
        if self.multiple_attempts_flag:     score += 15; factors.append('multiple_attempts')
        self.overall_score = min(score, 100)
        self.factors = factors
        if self.overall_score <= 30:   self.risk_level = 'low'
        elif self.overall_score <= 60: self.risk_level = 'medium'
        elif self.overall_score <= 80: self.risk_level = 'high'
        else:                          self.risk_level = 'critical'
        self.requires_manual_review = self.overall_score > 60
        self.save()
        return self.overall_score


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 6 ─ KYCOCRResult  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCOCRResult(models.Model):
    """OCR extraction results — document থেকে automatically extract করা data"""
    kyc              = models.ForeignKey(KYC, on_delete=models.CASCADE, related_name='ocr_results', null=True, blank=True)
    provider         = models.CharField(max_length=50, default='tesseract', null=True, blank=True)
    document_side    = models.CharField(max_length=10, choices=[('front','Front'),('back','Back')], default='front')
    raw_text         = models.TextField(blank=True)
    extracted_name   = models.CharField(max_length=200, null=True, blank=True)
    extracted_dob    = models.CharField(max_length=30, null=True, blank=True)
    extracted_nid    = models.CharField(max_length=50, null=True, blank=True)
    extracted_address = models.TextField(blank=True)
    extracted_father_name = models.CharField(max_length=200, null=True, blank=True)
    extracted_mother_name = models.CharField(max_length=200, null=True, blank=True)
    confidence       = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    language         = models.CharField(max_length=10, default='eng', null=True, blank=True)
    processing_time_ms = models.IntegerField(default=0)
    error            = models.TextField(blank=True)
    is_successful    = models.BooleanField(default=False)
    raw_response     = models.JSONField(default=dict, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_ocr_results'
        verbose_name = 'OCR Result'
        ordering = ['-created_at']

    def __str__(self): return f"OCR[{self.provider}] {self.kyc} - conf:{self.confidence:.2f}"


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 7 ─ KYCFaceMatchResult  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCFaceMatchResult(models.Model):
    """Face matching result between selfie and ID document"""
    kyc              = models.ForeignKey(KYC, on_delete=models.CASCADE, related_name='face_match_results', null=True, blank=True)
    provider         = models.CharField(max_length=50, default='deepface', null=True, blank=True)
    match_confidence = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    liveness_score   = models.FloatField(default=0.0)
    is_matched       = models.BooleanField(default=False)
    is_liveness_pass = models.BooleanField(default=False)
    face_detected_selfie = models.BooleanField(default=False)
    face_detected_doc    = models.BooleanField(default=False)
    multiple_faces   = models.BooleanField(default=False)
    spoofing_detected = models.BooleanField(default=False)
    processing_time_ms = models.IntegerField(default=0)
    error            = models.TextField(blank=True)
    raw_response     = models.JSONField(default=dict, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_face_match_results'
        verbose_name = 'Face Match Result'
        ordering = ['-created_at']

    def __str__(self): return f"Face[{self.provider}] matched={self.is_matched} conf={self.match_confidence:.2f}"


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 8 ─ KYCWebhookEndpoint  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCWebhookEndpoint(models.Model):
    """Webhook endpoints — KYC event এ external system notify করা"""
    tenant      = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='kyc_webhooks', null=True, blank=True)
    name        = models.CharField(max_length=100, null=True, blank=True)
    url         = models.URLField(max_length=500, null=True, blank=True)
    secret_key  = models.CharField(max_length=256, blank=True, help_text="HMAC signing key", null=True)
    events      = models.JSONField(default=list, help_text="List of events e.g. ['kyc.verified','kyc.rejected']")
    is_active   = models.BooleanField(default=True, db_index=True)
    timeout_sec = models.IntegerField(default=10)
    retry_count = models.IntegerField(default=3)
    headers     = models.JSONField(default=dict, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_webhook_endpoints'
        verbose_name = 'Webhook Endpoint'

    def __str__(self): return f"{self.name} → {self.url}"


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 9 ─ KYCWebhookDeliveryLog  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCWebhookDeliveryLog(models.Model):
    """Every webhook delivery attempt log"""
    endpoint      = models.ForeignKey(KYCWebhookEndpoint, on_delete=models.CASCADE, related_name='delivery_logs', null=True, blank=True)
    event         = models.CharField(max_length=100, null=True, blank=True)
    payload       = models.JSONField(default=dict)
    response_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    is_success    = models.BooleanField(default=False, db_index=True)
    attempt_count = models.IntegerField(default=1)
    duration_ms   = models.IntegerField(default=0)
    error         = models.TextField(blank=True)
    sent_at       = models.DateTimeField(auto_now_add=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'kyc_webhook_delivery_logs'
        verbose_name = 'Webhook Delivery Log'
        ordering = ['-sent_at']

    def __str__(self): return f"Webhook[{self.event}] → {self.response_code} ({'OK' if self.is_success else 'FAIL'})"


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 10 ─ KYCExportJob  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCExportJob(models.Model):
    """Track KYC data export jobs (CSV/Excel/PDF)"""
    FORMAT_CHOICES = [('csv','CSV'),('excel','Excel'),('pdf','PDF'),('json','JSON')]
    STATUS_CHOICES = [('pending','Pending'),('processing','Processing'),('done','Done'),('failed','Failed')]

    requested_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    tenant        = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    format        = models.CharField(max_length=10, choices=FORMAT_CHOICES, null=True, blank=True)
    filters       = models.JSONField(default=dict, blank=True, help_text="Applied filters snapshot")
    status        = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending', db_index=True, null=True, blank=True)
    file          = models.FileField(upload_to='kyc/exports/', null=True, blank=True)
    row_count     = models.IntegerField(default=0)
    error         = models.TextField(blank=True)
    started_at    = models.DateTimeField(null=True, blank=True)
    completed_at  = models.DateTimeField(null=True, blank=True)
    expires_at    = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_export_jobs'
        verbose_name = 'Export Job'
        ordering = ['-created_at']

    def __str__(self): return f"Export[{self.format.upper()}] by {self.requested_by} - {self.status}"


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 11 ─ KYCBulkActionLog  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCBulkActionLog(models.Model):
    """Audit log for all bulk admin actions"""
    ACTION_CHOICES = [
        ('verified','Verified'), ('rejected','Rejected'), ('pending','Pending'),
        ('reset','Reset'), ('export','Export'), ('delete','Delete'),
    ]
    performed_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    tenant         = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    action         = models.CharField(max_length=20, choices=ACTION_CHOICES, null=True, blank=True)
    kyc_ids        = models.JSONField(default=list)
    total_affected = models.IntegerField(default=0)
    success_count  = models.IntegerField(default=0)
    failure_count  = models.IntegerField(default=0)
    reason         = models.TextField(blank=True)
    errors         = models.JSONField(default=list, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_bulk_action_logs'
        verbose_name = 'Bulk Action Log'
        ordering = ['-created_at']

    def __str__(self): return f"Bulk[{self.action}] {self.success_count}/{self.total_affected} by {self.performed_by}"


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 12 ─ KYCAdminNote  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCAdminNote(models.Model):
    """Structured admin notes per KYC (instead of free-text admin_notes field)"""
    NOTE_TYPE_CHOICES = [
        ('general','General'), ('warning','Warning'), ('fraud_alert','Fraud Alert'),
        ('follow_up','Follow Up'), ('approved','Approval Note'), ('rejection','Rejection Note'),
    ]
    kyc          = models.ForeignKey(KYC, on_delete=models.CASCADE, related_name='admin_note_list', null=True, blank=True)
    author       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    note_type    = models.CharField(max_length=20, choices=NOTE_TYPE_CHOICES, default='general', null=True, blank=True)
    content      = models.TextField()
    is_internal  = models.BooleanField(default=True, help_text="User দেখতে পাবে না")
    is_pinned    = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_admin_notes'
        verbose_name = 'Admin Note'
        ordering = ['-is_pinned', '-created_at']

    def __str__(self): return f"[{self.note_type}] {self.content[:50]}"


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 13 ─ KYCRejectionTemplate  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCRejectionTemplate(models.Model):
    """Pre-defined rejection reason templates for admin quick select"""
    tenant      = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    title       = models.CharField(max_length=100, null=True, blank=True)
    body        = models.TextField()
    category    = models.CharField(max_length=50, null=True, blank=True)
    is_active   = models.BooleanField(default=True)
    usage_count = models.IntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_rejection_templates'
        verbose_name = 'Rejection Template'
        ordering = ['-usage_count', 'title']

    def __str__(self): return self.title


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 14 ─ KYCAnalyticsSnapshot  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCAnalyticsSnapshot(models.Model):
    """Daily/hourly analytics snapshots for dashboard charts"""
    PERIOD_CHOICES = [('hourly','Hourly'), ('daily','Daily'), ('weekly','Weekly'), ('monthly','Monthly')]

    tenant          = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    period          = models.CharField(max_length=10, choices=PERIOD_CHOICES, db_index=True, null=True, blank=True)
    period_start    = models.DateTimeField(db_index=True)
    period_end      = models.DateTimeField()
    total_submitted = models.IntegerField(default=0)
    total_verified  = models.IntegerField(default=0)
    total_rejected  = models.IntegerField(default=0)
    total_pending   = models.IntegerField(default=0)
    total_expired   = models.IntegerField(default=0)
    avg_risk_score  = models.FloatField(default=0.0)
    high_risk_count = models.IntegerField(default=0)
    duplicate_count = models.IntegerField(default=0)
    avg_processing_hours = models.FloatField(default=0.0)
    verification_rate = models.FloatField(default=0.0, help_text="verified/total %")
    rejection_rate  = models.FloatField(default=0.0)
    snapshot_data   = models.JSONField(default=dict, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_analytics_snapshots'
        verbose_name = 'Analytics Snapshot'
        unique_together = [('tenant', 'period', 'period_start')]
        ordering = ['-period_start']

    def __str__(self): return f"Analytics[{self.period}] {self.period_start.date()} — verified:{self.total_verified}"


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 15 ─ KYCIPTracker  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCIPTracker(models.Model):
    """Track IPs used for KYC submissions — fraud detection"""
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kyc_ip_logs', null=True, blank=True)
    kyc         = models.ForeignKey(KYC, on_delete=models.SET_NULL, null=True, blank=True, related_name='ip_logs')
    ip_address  = models.GenericIPAddressField(db_index=True)
    action      = models.CharField(max_length=50, null=True, blank=True)
    user_agent  = models.TextField(blank=True)
    country     = models.CharField(max_length=100, null=True, blank=True)
    city        = models.CharField(max_length=100, null=True, blank=True)
    is_vpn      = models.BooleanField(default=False, db_index=True)
    is_proxy    = models.BooleanField(default=False)
    is_tor      = models.BooleanField(default=False)
    risk_score  = models.IntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'kyc_ip_tracker'
        verbose_name = 'IP Tracker Entry'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['ip_address', 'created_at'])]

    def __str__(self): return f"IP[{self.ip_address}] {self.action} - {self.user}"


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 16 ─ KYCDeviceFingerprint  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCDeviceFingerprint(models.Model):
    """Device fingerprint for detecting multiple accounts from same device"""
    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kyc_devices', null=True, blank=True)
    fingerprint   = models.CharField(max_length=512, db_index=True, null=True, blank=True)
    device_type   = models.CharField(max_length=50, null=True, blank=True)
    os            = models.CharField(max_length=100, null=True, blank=True)
    browser       = models.CharField(max_length=100, null=True, blank=True)
    screen_res    = models.CharField(max_length=20, null=True, blank=True)
    timezone      = models.CharField(max_length=100, null=True, blank=True)
    language      = models.CharField(max_length=20, null=True, blank=True)
    canvas_hash   = models.CharField(max_length=64, null=True, blank=True)
    webgl_hash    = models.CharField(max_length=64, null=True, blank=True)
    is_suspicious = models.BooleanField(default=False, db_index=True)
    seen_count    = models.IntegerField(default=1)
    first_seen    = models.DateTimeField(auto_now_add=True)
    last_seen     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_device_fingerprints'
        verbose_name = 'Device Fingerprint'
        unique_together = [('user', 'fingerprint')]

    def __str__(self): return f"Device[{self.device_type}] {self.user} - seen:{self.seen_count}x"


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 17 ─ KYCVerificationStep  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCVerificationStep(models.Model):
    """Step-by-step verification progress tracking"""
    STEP_CHOICES = [
        ('personal_info',  'Personal Info'),
        ('document_upload','Document Upload'),
        ('ocr_check',      'OCR Check'),
        ('face_check',     'Face Check'),
        ('fraud_check',    'Fraud Check'),
        ('admin_review',   'Admin Review'),
        ('final',          'Final Decision'),
    ]
    STEP_STATUS = [
        ('pending',  'Pending'), ('in_progress', 'In Progress'),
        ('done',     'Done'),    ('failed',       'Failed'), ('skipped','Skipped'),
    ]
    kyc           = models.ForeignKey(KYC, on_delete=models.CASCADE, related_name='verification_steps', null=True, blank=True)
    step          = models.CharField(max_length=30, choices=STEP_CHOICES, null=True, blank=True)
    status        = models.CharField(max_length=15, choices=STEP_STATUS, default='pending', null=True, blank=True)
    started_at    = models.DateTimeField(null=True, blank=True)
    completed_at  = models.DateTimeField(null=True, blank=True)
    duration_ms   = models.IntegerField(default=0)
    result        = models.JSONField(default=dict, blank=True)
    error         = models.TextField(blank=True)
    retry_count   = models.IntegerField(default=0)
    order         = models.IntegerField(default=0)

    class Meta:
        db_table = 'kyc_verification_steps'
        verbose_name = 'Verification Step'
        ordering = ['order']
        unique_together = [('kyc', 'step')]

    def __str__(self): return f"Step[{self.step}:{self.status}] - {self.kyc}"

    def mark_done(self, result: dict = None):
        self.status = 'done'; self.completed_at = timezone.now()
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)
        if result: self.result = result
        self.save()

    def mark_failed(self, error: str = ''):
        self.status = 'failed'; self.completed_at = timezone.now(); self.error = error; self.save()


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 18 ─ KYCOTPLog  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCOTPLog(models.Model):
    """OTP send/verify logs for phone verification"""
    PURPOSE_CHOICES = [
        ('phone_verify', 'Phone Verification'),
        ('resubmit',     'Resubmit Verification'),
        ('admin_action', 'Admin Action OTP'),
    ]
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kyc_otp_logs', null=True, blank=True)
    kyc          = models.ForeignKey(KYC, on_delete=models.SET_NULL, null=True, blank=True)
    phone        = models.CharField(max_length=20, null=True, blank=True)
    purpose      = models.CharField(max_length=20, choices=PURPOSE_CHOICES, null=True, blank=True)
    otp_hash     = models.CharField(max_length=128, help_text="Hashed OTP — never store plain", null=True, blank=True)
    is_used      = models.BooleanField(default=False)
    is_verified  = models.BooleanField(default=False)
    attempt_count = models.IntegerField(default=0)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    sent_at      = models.DateTimeField(auto_now_add=True)
    verified_at  = models.DateTimeField(null=True, blank=True)
    expires_at   = models.DateTimeField()

    class Meta:
        db_table = 'kyc_otp_logs'
        verbose_name = 'OTP Log'
        ordering = ['-sent_at']

    def __str__(self): return f"OTP[{self.purpose}] {self.phone} - {'✓' if self.is_verified else '✗'}"

    @property
    def is_expired(self): return timezone.now() > self.expires_at

    @property
    def is_valid(self): return not self.is_expired and not self.is_used and self.attempt_count < 3


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 19 ─ KYCTenantConfig  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCTenantConfig(models.Model):
    """Per-tenant KYC configuration — World #1 multi-tenant support"""
    tenant                  = models.OneToOneField('tenants.Tenant', on_delete=models.CASCADE, related_name='kyc_config', null=True, blank=True)
    kyc_required            = models.BooleanField(default=True)
    allowed_document_types  = models.JSONField(default=list, help_text="Empty = all allowed")
    min_age                 = models.IntegerField(default=18)
    auto_approve_threshold  = models.IntegerField(default=0, help_text="Risk score ≤ this → auto approve. 0=disabled")
    auto_reject_threshold   = models.IntegerField(default=90, help_text="Risk score ≥ this → auto reject")
    kyc_expiry_days         = models.IntegerField(default=365)
    require_selfie          = models.BooleanField(default=True)
    require_face_match      = models.BooleanField(default=True)
    require_ocr             = models.BooleanField(default=True)
    require_phone_verify    = models.BooleanField(default=True)
    max_submissions_per_user = models.IntegerField(default=5)
    submission_cooldown_hours = models.IntegerField(default=24)
    notification_enabled    = models.BooleanField(default=True)
    webhook_enabled         = models.BooleanField(default=True)
    custom_rejection_messages = models.JSONField(default=dict, blank=True)
    extra_config            = models.JSONField(default=dict, blank=True)
    created_at              = models.DateTimeField(auto_now_add=True)
    updated_at              = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_tenant_configs'
        verbose_name = 'KYC Tenant Config'

    def __str__(self): return f"Config[{self.tenant}] kyc_required={self.kyc_required}"

    @classmethod
    def for_tenant(cls, tenant):
        obj, _ = cls.objects.get_or_create(tenant=tenant)
        return obj


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 20 ─ KYCAuditTrail  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCAuditTrail(models.Model):
    """
    Comprehensive immutable audit trail — World #1 compliance.
    একবার create হলে কখনো delete/update করা যাবে না।
    """
    ENTITY_CHOICES = [
        ('kyc',            'KYC'),
        ('kyc_submission', 'KYC Submission'),
        ('blacklist',      'Blacklist'),
        ('config',         'Tenant Config'),
        ('webhook',        'Webhook'),
        ('export',         'Export'),
        ('bulk_action',    'Bulk Action'),
    ]
    tenant        = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    actor         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    actor_ip      = models.GenericIPAddressField(null=True, blank=True)
    actor_agent   = models.TextField(blank=True)
    entity_type   = models.CharField(max_length=30, choices=ENTITY_CHOICES, db_index=True, null=True, blank=True)
    entity_id     = models.CharField(max_length=50, db_index=True, null=True, blank=True)
    action        = models.CharField(max_length=100, db_index=True, null=True, blank=True)
    before_state  = models.JSONField(default=dict, blank=True)
    after_state   = models.JSONField(default=dict, blank=True)
    diff          = models.JSONField(default=dict, blank=True)
    description   = models.TextField(blank=True)
    severity      = models.CharField(max_length=10, choices=[('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')], default='low')
    session_id    = models.CharField(max_length=100, null=True, blank=True)
    request_id    = models.CharField(max_length=100, null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'kyc_audit_trail'
        verbose_name = 'Audit Trail'
        verbose_name_plural = 'Audit Trail'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['actor', 'created_at']),
            models.Index(fields=['tenant', 'created_at']),
        ]

    def __str__(self): return f"Audit[{self.entity_type}:{self.entity_id}] {self.action} by {self.actor}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("Audit trail entries are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Audit trail entries cannot be deleted.")

    @classmethod
    def log(cls, *, entity_type, entity_id, action, actor=None, tenant=None,
            before=None, after=None, description='', severity='low',
            actor_ip=None, request_id='', session_id='', actor_agent=''):
        diff = {}
        if before and after:
            for key in set(list(before.keys()) + list(after.keys())):
                if before.get(key) != after.get(key):
                    diff[key] = {'before': before.get(key), 'after': after.get(key)}
        return cls.objects.create(
            tenant=tenant, actor=actor, actor_ip=actor_ip, actor_agent=actor_agent,
            entity_type=entity_type, entity_id=str(entity_id), action=action,
            before_state=before or {}, after_state=after or {}, diff=diff,
            description=description, severity=severity,
            request_id=request_id, session_id=session_id,
        )


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 21 ─ KYCDuplicateGroup  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCDuplicateGroup(models.Model):
    """Groups duplicate KYC records together for admin review"""
    MATCH_TYPE_CHOICES = [
        ('document','Document Number'), ('phone','Phone Number'),
        ('face','Face Match'), ('name_dob','Name + DOB'),
    ]
    match_type     = models.CharField(max_length=20, choices=MATCH_TYPE_CHOICES, null=True, blank=True)
    match_value    = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    kyc_records    = models.ManyToManyField(KYC, related_name='duplicate_groups')
    primary_kyc    = models.ForeignKey(KYC, on_delete=models.SET_NULL, null=True, blank=True, related_name='primary_duplicate_group')
    is_resolved    = models.BooleanField(default=False, db_index=True)
    resolution_note = models.TextField(blank=True)
    resolved_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    resolved_at    = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_duplicate_groups'
        verbose_name = 'Duplicate Group'

    def __str__(self): return f"DupGroup[{self.match_type}:{self.match_value}] resolved={self.is_resolved}"


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 22 ─ KYCNotificationLog  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCNotificationLog(models.Model):
    """Log all KYC-related notifications sent"""
    CHANNEL_CHOICES = [
        ('push','Push'), ('sms','SMS'), ('email','Email'), ('in_app','In-App'),
    ]
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kyc_notifications', null=True, blank=True)
    kyc         = models.ForeignKey(KYC, on_delete=models.SET_NULL, null=True, blank=True)
    channel     = models.CharField(max_length=10, choices=CHANNEL_CHOICES, null=True, blank=True)
    event_type  = models.CharField(max_length=50, null=True, blank=True)
    title       = models.CharField(max_length=200, null=True, blank=True)
    message     = models.TextField()
    is_sent     = models.BooleanField(default=False, db_index=True)
    is_read     = models.BooleanField(default=False)
    error       = models.TextField(blank=True)
    sent_at     = models.DateTimeField(null=True, blank=True)
    read_at     = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_notification_logs'
        verbose_name = 'Notification Log'
        ordering = ['-created_at']

    def __str__(self): return f"Notif[{self.channel}:{self.event_type}] {self.user} - {'sent' if self.is_sent else 'failed'}"


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 23 ─ KYCFeatureFlag  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
class KYCFeatureFlag(models.Model):
    """Runtime feature flags for KYC system — deploy without restart"""
    tenant      = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    key         = models.CharField(max_length=100, db_index=True, null=True, blank=True)
    is_enabled  = models.BooleanField(default=False, db_index=True)
    value       = models.JSONField(default=dict, blank=True, help_text="Optional config value")
    description = models.TextField(blank=True)
    updated_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_feature_flags'
        verbose_name = 'Feature Flag'
        unique_together = [('tenant', 'key')]

    def __str__(self): return f"Flag[{self.key}]={'ON' if self.is_enabled else 'OFF'}"

    @classmethod
    def is_on(cls, key: str, tenant=None) -> bool:
        try:
            return cls.objects.get(key=key, tenant=tenant).is_enabled
        except cls.DoesNotExist:
            return False

    @classmethod
    def get_value(cls, key: str, tenant=None, default=None):
        try:
            obj = cls.objects.get(key=key, tenant=tenant)
            return obj.value if obj.is_enabled else default
        except cls.DoesNotExist:
            return default
