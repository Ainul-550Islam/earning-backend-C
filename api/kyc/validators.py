# kyc/validators.py  ── WORLD #1
import re
import os
import logging
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def validate_nid_number(value: str) -> str:
    if not value: raise ValidationError(_('NID number is required.'))
    cleaned = re.sub(r'[\s\-]', '', str(value))
    if not cleaned.isdigit():
        raise ValidationError(_('NID number must contain digits only.'))
    if len(cleaned) not in [10, 13, 17]:
        raise ValidationError(_('NID must be 10, 13, or 17 digits.'))
    return cleaned


def validate_passport_number(value: str) -> str:
    if not value: raise ValidationError(_('Passport number is required.'))
    cleaned = str(value).strip().upper()
    if not re.match(r'^[A-Z]{1,2}\d{7,8}$', cleaned):
        raise ValidationError(_('Invalid passport number. Format: A1234567'))
    return cleaned


def validate_driving_license_number(value: str) -> str:
    if not value: raise ValidationError(_('License number is required.'))
    cleaned = str(value).strip().upper()
    if not 7 <= len(cleaned) <= 15:
        raise ValidationError(_('License number must be 7-15 characters.'))
    if not re.match(r'^[A-Z0-9\-]+$', cleaned):
        raise ValidationError(_('License number: only letters, digits, hyphens.'))
    return cleaned


def validate_document_number(doc_type: str, doc_number: str) -> str:
    validators = {
        'nid':             validate_nid_number,
        'passport':        validate_passport_number,
        'driving_license': validate_driving_license_number,
    }
    validator = validators.get(doc_type)
    if not validator:
        if not doc_number or len(str(doc_number).strip()) < 5:
            raise ValidationError(_('Document number must be at least 5 characters.'))
        return str(doc_number).strip()
    return validator(doc_number)


def validate_bd_phone_number(value: str) -> str:
    if not value: raise ValidationError(_('Phone number is required.'))
    cleaned = re.sub(r'[\s\-\(\)]', '', str(value))
    if not re.match(r'^(?:\+?880|0)?1[3-9]\d{8}$', cleaned):
        raise ValidationError(_('Invalid Bangladesh phone number. Format: 01XXXXXXXXX'))
    if cleaned.startswith('+880'):  cleaned = '0' + cleaned[4:]
    elif cleaned.startswith('880'): cleaned = '0' + cleaned[3:]
    return cleaned


def validate_payment_number(value: str, payment_method: str = None) -> str:
    return validate_bd_phone_number(value)


def validate_image_size(image) -> None:
    max_bytes = 5 * 1024 * 1024
    size = getattr(image, 'size', 0)
    if not size and hasattr(image, 'file'):
        image.file.seek(0, 2); size = image.file.tell(); image.file.seek(0)
    if size > max_bytes:
        raise ValidationError(_(f'Image {size/(1024*1024):.1f}MB exceeds 5MB limit.'))


def validate_image_type(image) -> None:
    allowed       = ['image/jpeg','image/jpg','image/png','image/webp','image/heic','image/heif']
    allowed_exts  = ['.jpg','.jpeg','.png','.webp','.heic','.heif']
    content_type  = getattr(image, 'content_type', None)
    if content_type and content_type not in allowed:
        raise ValidationError(_(f'Invalid image type "{content_type}".'))
    ext = os.path.splitext(getattr(image, 'name', '') or '')[1].lower()
    if ext and ext not in allowed_exts:
        raise ValidationError(_(f'Invalid file extension "{ext}".'))


def validate_image_dimensions(image) -> None:
    try:
        from PIL import Image
        if hasattr(image, 'seek'): image.seek(0)
        img = Image.open(image)
        w, h = img.size
        if w < 400 or h < 300:
            raise ValidationError(_(f'Image {w}×{h}px too small. Minimum 400×300.'))
        if hasattr(image, 'seek'): image.seek(0)
    except ValidationError: raise
    except Exception as e: logger.warning(f'Dimension check skipped: {e}')


def validate_kyc_image(image) -> None:
    validate_image_size(image)
    validate_image_type(image)
    validate_image_dimensions(image)


def validate_date_of_birth(value) -> None:
    from datetime import date
    if value is None: return
    today = date.today()
    if value >= today:           raise ValidationError(_('Date of birth must be in the past.'))
    if value.year < 1900:        raise ValidationError(_('DOB cannot be before 1900.'))
    age = (today - value).days / 365.25
    if age < 18:   raise ValidationError(_(f'Must be at least 18. Current age: {int(age)}.'))
    if age > 120:  raise ValidationError(_('Invalid DOB. Age cannot exceed 120.'))


def validate_full_name(value: str) -> str:
    if not value: raise ValidationError(_('Full name is required.'))
    cleaned = str(value).strip()
    if len(cleaned) < 3:  raise ValidationError(_('Full name must be at least 3 characters.'))
    if len(cleaned) > 200: raise ValidationError(_('Full name cannot exceed 200 characters.'))
    if not re.match(r"^[\u0980-\u09FFa-zA-Z\s\-\'\.]+$", cleaned):
        raise ValidationError(_('Full name: only letters, spaces, hyphens, apostrophes.'))
    return cleaned


def validate_risk_score(value: int) -> None:
    if not (0 <= int(value) <= 100):
        raise ValidationError(_(f'Risk score must be 0-100. Got: {value}'))


def check_name_similarity(name1: str, name2: str, threshold: float = 0.80) -> tuple:
    if not name1 or not name2: return False, 0.0
    from difflib import SequenceMatcher
    ratio = SequenceMatcher(None, name1.strip().lower(), name2.strip().lower()).ratio()
    return ratio >= threshold, round(ratio, 4)


class BDPhoneValidator:
    message = _('Enter a valid Bangladesh phone number (01XXXXXXXXX).')
    code    = 'invalid_phone'

    def __call__(self, value):
        try:   validate_bd_phone_number(value)
        except ValidationError: raise ValidationError(self.message, code=self.code)


class KYCImageValidator:
    def __call__(self, value):
        try:   validate_kyc_image(value)
        except ValidationError as e: raise ValidationError(str(e))
