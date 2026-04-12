# kyc/constants.py  ── WORLD #1
class KYCStatus:
    NOT_SUBMITTED = 'not_submitted'; PENDING = 'pending'; VERIFIED = 'verified'
    REJECTED = 'rejected'; EXPIRED = 'expired'; UNDER_REVIEW = 'under_review'; SUBMITTED = 'submitted'
    FINAL = [VERIFIED, REJECTED, EXPIRED]; ACTIVE = [PENDING, UNDER_REVIEW, SUBMITTED]
    CHOICES = [(NOT_SUBMITTED,'Not Submitted'),(PENDING,'Pending Review'),(VERIFIED,'Verified'),
               (REJECTED,'Rejected'),(EXPIRED,'Expired'),(UNDER_REVIEW,'Under Review'),(SUBMITTED,'Submitted')]

class DocumentType:
    NID = 'nid'; PASSPORT = 'passport'; DRIVING_LICENSE = 'driving_license'
    ALL = [NID, PASSPORT, DRIVING_LICENSE]
    CHOICES = [(NID,'National ID'),(PASSPORT,'Passport'),(DRIVING_LICENSE,'Driving License')]

class PaymentMethod:
    BKASH = 'bkash'; NAGAD = 'nagad'; ROCKET = 'rocket'; UPAY = 'upay'; BANK = 'bank'
    CHOICES = [(BKASH,'bKash'),(NAGAD,'Nagad'),(ROCKET,'Rocket'),(UPAY,'Upay'),(BANK,'Bank')]

class RiskLevel:
    LOW = 'low'; MEDIUM = 'medium'; HIGH = 'high'; CRITICAL = 'critical'
    THRESHOLDS = {'low':(0,30),'medium':(31,60),'high':(61,80),'critical':(81,100)}
    @classmethod
    def from_score(cls, score):
        for level,(lo,hi) in cls.THRESHOLDS.items():
            if lo <= score <= hi: return level
        return cls.CRITICAL

class LogAction:
    SUBMITTED='submitted'; APPROVED='approved'; REJECTED='rejected'; RESET='reset'
    EDITED='edited'; NOTE_ADDED='note_added'; PHONE_VERIFIED='phone_verified'
    FACE_VERIFIED='face_verified'; OCR_EXTRACTED='ocr_extracted'; EXPIRED='expired'
    DUPLICATE_FOUND='duplicate_found'; RISK_SCORED='risk_scored'; BULK_ACTION='bulk_action'
    EXPORTED='exported'; WEBHOOK_SENT='webhook_sent'; STATUS_CHANGED='status_changed'; DELETED='deleted'

class UploadConfig:
    MAX_IMAGE_SIZE = 5*1024*1024; MAX_DOCUMENT_SIZE = 10*1024*1024
    ALLOWED_IMAGE_TYPES = ['image/jpeg','image/jpg','image/png','image/webp','image/heic']
    NID_FRONT_PATH = 'kyc/nid/front/'; NID_BACK_PATH = 'kyc/nid/back/'; SELFIE_PATH = 'kyc/selfie/'
    MIN_IMAGE_WIDTH = 400; MIN_IMAGE_HEIGHT = 300; MIN_CLARITY_SCORE = 30.0

class CacheKeys:
    KYC_STATUS = 'kyc:status:{user_id}'; KYC_ADMIN_STATS = 'kyc:admin:stats'
    KYC_RISK_SCORE = 'kyc:risk:{kyc_id}'; KYC_USER_VERIFIED = 'kyc:verified:{user_id}'
    TTL_STATUS = 300; TTL_ADMIN_STATS = 120; TTL_RISK_SCORE = 3600; TTL_VERIFIED = 21600

class ThrottleRates:
    KYC_SUBMIT = '5/hour'; KYC_FRAUD_CHECK = '10/hour'; KYC_STATUS = '60/minute'; KYC_ADMIN = '1000/hour'

class ExpiryConfig:
    KYC_VALIDITY_DAYS = 365; WARNING_BEFORE_EXPIRY_DAYS = 30; PENDING_TIMEOUT_HOURS = 72

class NotificationTemplates:
    KYC_SUBMITTED    = {'title':'KYC Submitted ✅','message':'আপনার KYC submitted হয়েছে।','type':'kyc_submitted'}
    KYC_VERIFIED     = {'title':'KYC Verified 🎉','message':'আপনার KYC verified হয়েছে!','type':'kyc_verified'}
    KYC_REJECTED     = {'title':'KYC Rejected ❌','message':'KYC reject হয়েছে। কারণ: {reason}','type':'kyc_rejected'}
    KYC_EXPIRING_SOON= {'title':'KYC Expiring ⚠️','message':'{days} দিনে expire হবে।','type':'kyc_expiring'}
    KYC_EXPIRED      = {'title':'KYC Expired ⌛','message':'আপনার KYC expired।','type':'kyc_expired'}

class WebhookEvents:
    KYC_SUBMITTED='kyc.submitted'; KYC_VERIFIED='kyc.verified'; KYC_REJECTED='kyc.rejected'
    KYC_EXPIRED='kyc.expired'; KYC_DUPLICATE_FOUND='kyc.duplicate_found'; KYC_FRAUD_DETECTED='kyc.fraud.detected'

class ErrorCode:
    KYC_NOT_FOUND='KYC_001'; KYC_ALREADY_VERIFIED='KYC_002'; KYC_DUPLICATE_DETECTED='KYC_005'
    KYC_DOCUMENT_INVALID='KYC_006'; KYC_IMAGE_TOO_SMALL='KYC_007'; KYC_IMAGE_TOO_LARGE='KYC_008'
    KYC_FACE_MISMATCH='KYC_009'; KYC_RATE_LIMITED='KYC_010'; KYC_OCR_FAILED='KYC_501'

class CountryConfig:
    DEFAULT_COUNTRY='Bangladesh'; DEFAULT_COUNTRY_CODE='BD'; DEFAULT_PHONE_PREFIX='+880'
    PHONE_PATTERNS = {'BD': r'^(?:\+?880|0)?1[3-9]\d{8}$'}

class ExportFormat:
    CSV='csv'; EXCEL='excel'; PDF='pdf'; JSON='json'
    ALL=[CSV,EXCEL,PDF,JSON]; CHOICES=[(f,f.upper()) for f in ALL]
