# kyc/enums.py  ── WORLD #1
from enum import Enum, IntEnum, unique


@unique
class KYCStatusEnum(str, Enum):
    NOT_SUBMITTED = 'not_submitted'
    PENDING       = 'pending'
    VERIFIED      = 'verified'
    REJECTED      = 'rejected'
    EXPIRED       = 'expired'
    UNDER_REVIEW  = 'under_review'
    SUBMITTED     = 'submitted'

    @property
    def is_final(self):    return self in (self.VERIFIED, self.REJECTED, self.EXPIRED)
    @property
    def is_active(self):   return self in (self.PENDING, self.UNDER_REVIEW, self.SUBMITTED)
    @property
    def can_submit(self):  return self in (self.NOT_SUBMITTED, self.REJECTED, self.EXPIRED)

    @classmethod
    def from_legacy(cls, v: str):
        return {'submitted': cls.SUBMITTED, 'under_review': cls.UNDER_REVIEW,
                'approved': cls.VERIFIED, 'rejected': cls.REJECTED, 'pending': cls.PENDING}.get(v, cls.NOT_SUBMITTED)


@unique
class DocumentTypeEnum(str, Enum):
    NID               = 'nid'
    PASSPORT          = 'passport'
    DRIVING_LICENSE   = 'driving_license'
    BIRTH_CERTIFICATE = 'birth_certificate'
    VOTER_ID          = 'voter_id'

    @property
    def requires_back_image(self): return self in (self.NID, self.DRIVING_LICENSE)


@unique
class PaymentMethodEnum(str, Enum):
    BKASH  = 'bkash'
    NAGAD  = 'nagad'
    ROCKET = 'rocket'
    UPAY   = 'upay'
    BANK   = 'bank'

    @property
    def is_mfs(self): return self in (self.BKASH, self.NAGAD, self.ROCKET, self.UPAY)


@unique
class FaceLivenessEnum(str, Enum):
    PENDING = 'pending'
    SUCCESS = 'success'
    FAILURE = 'failure'
    SKIPPED = 'skipped'

    @property
    def is_passed(self): return self == self.SUCCESS


@unique
class RiskLevelEnum(str, Enum):
    LOW      = 'low'
    MEDIUM   = 'medium'
    HIGH     = 'high'
    CRITICAL = 'critical'

    @classmethod
    def from_score(cls, score: int):
        if score <= 30:   return cls.LOW
        elif score <= 60: return cls.MEDIUM
        elif score <= 80: return cls.HIGH
        return cls.CRITICAL

    @property
    def color(self):
        return {'low':'#4CAF50','medium':'#FF9800','high':'#F44336','critical':'#B71C1C'}.get(self, '#9E9E9E')

    @property
    def requires_manual_review(self): return self in (self.HIGH, self.CRITICAL)


@unique
class LogActionEnum(str, Enum):
    SUBMITTED       = 'submitted'
    APPROVED        = 'approved'
    REJECTED        = 'rejected'
    RESET           = 'reset'
    EDITED          = 'edited'
    NOTE_ADDED      = 'note_added'
    PHONE_VERIFIED  = 'phone_verified'
    FACE_VERIFIED   = 'face_verified'
    OCR_EXTRACTED   = 'ocr_extracted'
    EXPIRED         = 'expired'
    DUPLICATE_FOUND = 'duplicate_found'
    RISK_SCORED     = 'risk_scored'
    BULK_ACTION     = 'bulk_action'
    EXPORTED        = 'exported'
    WEBHOOK_SENT    = 'webhook_sent'
    STATUS_CHANGED  = 'status_changed'
    DELETED         = 'deleted'
    FRAUD_CHECKED   = 'fraud_checked'


@unique
class ExportFormatEnum(str, Enum):
    CSV   = 'csv'
    EXCEL = 'excel'
    PDF   = 'pdf'
    JSON  = 'json'

    @property
    def content_type(self):
        return {'csv':'text/csv','excel':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'pdf':'application/pdf','json':'application/json'}.get(self.value,'application/octet-stream')

    @property
    def file_extension(self):
        return {'csv':'.csv','excel':'.xlsx','pdf':'.pdf','json':'.json'}.get(self.value,'')


@unique
class ProgressStageEnum(IntEnum):
    NOT_STARTED     = 0
    SUBMITTED       = 10
    DOCUMENTS_READY = 25
    OCR_COMPLETE    = 40
    FRAUD_CHECK_MIN = 60
    FRAUD_CHECK_MAX = 75
    ADMIN_REVIEWING = 85
    VERIFIED        = 100


@unique
class OCRProviderEnum(str, Enum):
    GOOGLE_VISION   = 'google_vision'
    AWS_TEXTRACT    = 'aws_textract'
    AZURE_COGNITIVE = 'azure_cognitive'
    TESSERACT       = 'tesseract'

    @property
    def is_cloud(self): return self != self.TESSERACT


@unique
class WebhookEventEnum(str, Enum):
    KYC_SUBMITTED       = 'kyc.submitted'
    KYC_VERIFIED        = 'kyc.verified'
    KYC_REJECTED        = 'kyc.rejected'
    KYC_EXPIRED         = 'kyc.expired'
    KYC_DUPLICATE_FOUND = 'kyc.duplicate_found'
    KYC_RISK_HIGH       = 'kyc.risk.high'
    KYC_FRAUD_DETECTED  = 'kyc.fraud.detected'


@unique
class BulkActionEnum(str, Enum):
    VERIFY  = 'verified'
    REJECT  = 'rejected'
    PENDING = 'pending'
    RESET   = 'reset'
    EXPORT  = 'export'
    DELETE  = 'delete'

    @property
    def requires_reason(self): return self == self.REJECT
    @property
    def is_destructive(self):  return self in (self.REJECT, self.DELETE)
