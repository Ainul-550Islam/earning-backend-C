# kyc/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone

class KYC(models.Model):
    """KYC verification for users"""
    
    STATUS_CHOICES = [
        ('not_submitted', 'Not Submitted'),
        ('pending', 'Pending Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]
    
    DOCUMENT_TYPES = [
        ('nid', 'National ID'),
        ('passport', 'Passport'),
        ('driving_license', 'Driving License'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # v1 - Basic KYC
    full_name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=20)
    payment_number = models.CharField(max_length=20, help_text="bKash/Nagad number")
    payment_method = models.CharField(max_length=20, default='bkash')
    
    # Address
    address_line = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Bangladesh')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_submitted')
    
    # v1 - Name verification
    is_name_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    is_payment_verified = models.BooleanField(default=False)
    
    # v2 - Document verification
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, blank=True)
    document_number = models.CharField(max_length=50, blank=True)
    document_front = models.ImageField(upload_to='kyc/documents/', null=True, blank=True)
    document_back = models.ImageField(upload_to='kyc/documents/', null=True, blank=True)
    
    # v2 - Selfie verification
    selfie_photo = models.ImageField(upload_to='kyc/selfies/', null=True, blank=True)
    is_face_verified = models.BooleanField(default=False)
    
    # v2 - OCR extracted data
    extracted_name = models.CharField(max_length=200, blank=True)
    extracted_dob = models.DateField(null=True, blank=True)
    extracted_nid = models.CharField(max_length=50, blank=True)
    ocr_confidence = models.FloatField(default=0.0)
    
    # Admin review
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kyc_reviews'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    
    # Duplicate detection (v2)
    is_duplicate = models.BooleanField(default=False)
    duplicate_of = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicates'
    )
    
    # Risk scoring (v2)
    risk_score = models.IntegerField(default=0, help_text="0-100")
    risk_factors = models.JSONField(default=list, blank=True)
    
    # Expiry (v2)
    verified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'kyc'
        verbose_name = 'KYC'
        verbose_name_plural = 'KYC Records'
    
    def __str__(self):
        return f"{self.user.username} - {self.get_status_display()}"
    
    def submit_for_review(self):
        """Submit KYC for admin review"""
        if self.status == 'not_submitted':
            self.status = 'pending'
            self.save()
    
    def approve(self, reviewed_by=None):
        """Approve KYC"""
        self.status = 'verified'
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.verified_at = timezone.now()
        
        # Set expiry (1 year from now)
        from datetime import timedelta
        self.expires_at = timezone.now() + timedelta(days=365)
        
        self.save()
        
        # Update user verification status
        user = self.user
        user.is_verified = True  # Add this field to User model
        user.save()
    
    def reject(self, reason='', reviewed_by=None):
        """Reject KYC"""
        self.status = 'rejected'
        self.rejection_reason = reason
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.save()
    
    def calculate_risk_score(self):
        """Calculate KYC risk score"""
        score = 0
        factors = []
        
        # Check name match
        if self.extracted_name and self.full_name:
            from difflib import SequenceMatcher
            similarity = SequenceMatcher(None, 
                self.extracted_name.lower(), 
                self.full_name.lower()
            ).ratio()
            
            if similarity < 0.8:
                score += 30
                factors.append('Name mismatch')
        
        # Check age
        if self.date_of_birth:
            from datetime import date
            age = (date.today() - self.date_of_birth).days / 365.25
            if age < 18:
                score += 50
                factors.append('Under 18')
        
        # Check duplicate
        if self.is_duplicate:
            score += 40
            factors.append('Duplicate KYC')
        
        # Check OCR confidence
        if self.ocr_confidence < 0.7:
            score += 20
            factors.append('Low OCR confidence')
        
        self.risk_score = min(score, 100)
        self.risk_factors = factors
        self.save()
        
        return self.risk_score


class KYCVerificationLog(models.Model):
    """Log all KYC verification attempts"""
    kyc = models.ForeignKey(KYC, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=50)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    details = models.TextField()
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']


# kyc/services.py
class KYCService:
    """KYC processing services"""
    
    @staticmethod
    def check_duplicate_kyc(kyc):
        """Check for duplicate KYC submissions"""
        # Check by document number
        if kyc.document_number:
            duplicates = KYC.objects.filter(
                document_number=kyc.document_number,
                status='verified'
            ).exclude(id=kyc.id)
            
            if duplicates.exists():
                kyc.is_duplicate = True
                kyc.duplicate_of = duplicates.first()
                kyc.save()
                return True
        
        # Check by phone number
        if kyc.phone_number:
            duplicates = KYC.objects.filter(
                phone_number=kyc.phone_number,
                status='verified'
            ).exclude(id=kyc.id)
            
            if duplicates.exists():
                kyc.is_duplicate = True
                kyc.duplicate_of = duplicates.first()
                kyc.save()
                return True
        
        return False
    
    @staticmethod
    def verify_phone_otp(kyc, otp_code):
        """Verify phone number with OTP"""
        # Implement OTP verification
        # For now, simple mock
        kyc.is_phone_verified = True
        kyc.save()
        
        KYCVerificationLog.objects.create(
            kyc=kyc,
            action='phone_verified',
            details='Phone number verified via OTP'
        )
        
        return True
    
    @staticmethod
    def extract_nid_data(image_path):
        """Extract data from NID using OCR (v2)"""
        # This would integrate with OCR service like:
        # - Google Cloud Vision API
        # - AWS Textract
        # - Tesseract OCR
        
        # Mock implementation
        extracted_data = {
            'name': '',
            'nid_number': '',
            'date_of_birth': None,
            'confidence': 0.0
        }
        
        return extracted_data
    
    @staticmethod
    def verify_face_match(selfie_path, document_path):
        """Verify face match between selfie and ID (v2)"""
        # This would integrate with:
        # - AWS Rekognition
        # - Azure Face API
        # - Face++ API
        
        # Mock implementation
        confidence = 0.0
        
        return confidence > 0.8