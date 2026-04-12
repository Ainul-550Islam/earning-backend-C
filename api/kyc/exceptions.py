# kyc/exceptions.py  ── WORLD #1
from rest_framework.exceptions import APIException
from rest_framework import status as http_status


class KYCBaseException(APIException):
    status_code    = http_status.HTTP_400_BAD_REQUEST
    default_detail = 'KYC operation failed.'
    error_code     = 'KYC_000'

    def __init__(self, detail=None, error_code=None, extra=None):
        super().__init__(detail=detail or self.default_detail)
        if error_code: self.error_code = error_code
        self.extra = extra or {}

    def to_dict(self):
        return {'error': self.default_detail, 'error_code': self.error_code,
                'detail': str(self.detail), **self.extra}


class KYCNotFoundException(KYCBaseException):
    status_code = http_status.HTTP_404_NOT_FOUND
    default_detail = 'KYC record not found.'
    error_code = 'KYC_001'


class KYCSubmissionNotFoundException(KYCBaseException):
    status_code = http_status.HTTP_404_NOT_FOUND
    default_detail = 'KYC submission not found.'
    error_code = 'KYC_001'


class KYCAlreadyVerifiedException(KYCBaseException):
    default_detail = 'KYC is already verified.'
    error_code = 'KYC_002'


class KYCAlreadySubmittedException(KYCBaseException):
    default_detail = 'KYC submission already exists.'
    error_code = 'KYC_003'


class KYCInvalidStatusTransitionException(KYCBaseException):
    default_detail = 'Invalid KYC status transition.'
    error_code = 'KYC_004'

    def __init__(self, from_status: str, to_status: str):
        super().__init__(detail=f"Cannot transition from '{from_status}' to '{to_status}'.",
                         extra={'from_status': from_status, 'to_status': to_status})


class KYCDeleteNotAllowedException(KYCBaseException):
    default_detail = 'Verified KYC cannot be deleted.'
    error_code = 'KYC_011'


class KYCFinalizedError(KYCBaseException):
    default_detail = 'KYC is already finalized.'
    error_code = 'KYC_004'


class KYCValidationException(KYCBaseException):
    default_detail = 'KYC validation failed.'
    error_code = 'KYC_VAL_000'


class KYCDocumentInvalidException(KYCValidationException):
    default_detail = 'Invalid document type or number.'
    error_code = 'KYC_006'

    def __init__(self, field: str = None, reason: str = None):
        super().__init__(detail=reason or self.default_detail,
                         extra={'field': field, 'reason': reason})


class KYCAgeRestrictionException(KYCValidationException):
    default_detail = 'User must be at least 18 years old.'
    error_code = 'KYC_013'


class KYCRejectionReasonRequiredException(KYCValidationException):
    default_detail = 'Rejection reason is required.'
    error_code = 'KYC_012'


class KYCImageException(KYCBaseException):
    default_detail = 'Image processing failed.'
    error_code = 'KYC_IMG_000'


class KYCImageTooSmallException(KYCImageException):
    default_detail = 'Image resolution is too low. Minimum 400×300 pixels required.'
    error_code = 'KYC_007'

    def __init__(self, width: int = 0, height: int = 0):
        super().__init__(detail=f'Image too small ({width}×{height}px). Minimum 400×300 required.',
                         extra={'width': width, 'height': height})


class KYCImageTooLargeException(KYCImageException):
    default_detail = 'Image file too large. Max 5MB.'
    error_code = 'KYC_008'

    def __init__(self, size_mb: float = 0):
        super().__init__(detail=f'Image {size_mb:.1f}MB exceeds 5MB limit.', extra={'size_mb': size_mb})


class KYCImageTypeInvalidException(KYCImageException):
    default_detail = 'Invalid image type. Allowed: JPEG, PNG, WebP.'
    error_code = 'KYC_IMG_003'


class KYCImageBlurryException(KYCImageException):
    default_detail = 'Image is too blurry.'
    error_code = 'KYC_IMG_004'


class KYCDuplicateDetectedException(KYCBaseException):
    status_code = http_status.HTTP_409_CONFLICT
    default_detail = 'Duplicate KYC detected.'
    error_code = 'KYC_005'


class KYCFaceException(KYCBaseException):
    default_detail = 'Face verification failed.'
    error_code = 'KYC_FACE_000'


class KYCFaceMismatchException(KYCFaceException):
    default_detail = 'Face does not match ID document.'
    error_code = 'KYC_009'

    def __init__(self, confidence: float = 0):
        super().__init__(detail=f'Face match confidence {confidence:.2f} below 0.80.',
                         extra={'confidence': confidence})


class KYCFaceNotDetectedException(KYCFaceException):
    default_detail = 'No face detected in image.'
    error_code = 'KYC_FACE_002'


class KYCFaceLivenessFailedException(KYCFaceException):
    default_detail = 'Liveness check failed.'
    error_code = 'KYC_FACE_003'


class KYCMultipleFacesException(KYCFaceException):
    default_detail = 'Multiple faces detected in selfie.'
    error_code = 'KYC_FACE_004'


class KYCOCRException(KYCBaseException):
    status_code = http_status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = 'OCR processing failed.'
    error_code = 'KYC_501'


class KYCOCRLowConfidenceException(KYCOCRException):
    default_detail = 'OCR confidence too low. Upload a clearer document.'
    error_code = 'KYC_OCR_002'


class KYCOCRProviderException(KYCOCRException):
    status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'OCR service temporarily unavailable.'
    error_code = 'KYC_OCR_003'


class KYCRateLimitException(KYCBaseException):
    status_code = http_status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Too many KYC attempts. Please try again later.'
    error_code = 'KYC_010'


class KYCStorageException(KYCBaseException):
    status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'File storage service unavailable.'
    error_code = 'KYC_503'


class KYCWebhookException(KYCBaseException):
    status_code = http_status.HTTP_502_BAD_GATEWAY
    default_detail = 'Webhook delivery failed.'
    error_code = 'KYC_504'


class KYCPermissionException(KYCBaseException):
    status_code = http_status.HTTP_403_FORBIDDEN
    default_detail = 'You do not have permission for this KYC operation.'
    error_code = 'KYC_PERM_001'


class KYCFraudSuspectedException(KYCBaseException):
    status_code = http_status.HTTP_403_FORBIDDEN
    default_detail = 'Suspicious activity detected. KYC flagged for review.'
    error_code = 'KYC_SEC_001'

    def __init__(self, risk_score: int = 0, factors: list = None):
        super().__init__(extra={'risk_score': risk_score, 'risk_factors': factors or []})


class KYCBlacklistedNumberException(KYCBaseException):
    status_code = http_status.HTTP_403_FORBIDDEN
    default_detail = 'The provided number is blacklisted.'
    error_code = 'KYC_SEC_002'
