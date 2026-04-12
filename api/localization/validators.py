# validators.py — Custom Django + DRF validators
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError as DRFValidationError
import logging

logger = logging.getLogger(__name__)


def validate_language_code(value):
    """BCP 47 language code validator: en, bn, zh-Hans, sr-Latn"""
    pattern = r'^[a-z]{2,3}(-[A-Za-z]{2,4})?(-[A-Z]{2})?$'
    if not re.match(pattern, str(value)):
        raise ValidationError(
            _('%(value)s is not a valid language code. Use formats like: en, bn, zh-Hans, sr-Latn'),
            params={'value': value},
        )


def validate_currency_code(value):
    """ISO 4217 3-letter currency code"""
    if not re.match(r'^[A-Z]{3}$', str(value)):
        raise ValidationError(
            _('%(value)s is not a valid currency code. Use 3-letter ISO codes like: USD, EUR, BDT'),
            params={'value': value},
        )


def validate_country_code(value):
    """ISO 3166-1 alpha-2 country code"""
    if not re.match(r'^[A-Z]{2}$', str(value)):
        raise ValidationError(
            _('%(value)s is not a valid country code. Use 2-letter codes like: BD, US, GB'),
            params={'value': value},
        )


def validate_translation_key(value):
    """Dot-separated translation key: namespace.category.key"""
    if not re.match(r'^[a-z0-9_]+(\.[a-z0-9_]+)*$', str(value)):
        raise ValidationError(
            _('Translation key must use lowercase letters, numbers, underscores and dots. '
              'Example: common.button.submit'),
            params={'value': value},
        )


def validate_translation_value_length(value, max_length=10000):
    """Translation value not too long"""
    if value and len(value) > max_length:
        raise ValidationError(
            _('Translation value too long (%(length)s chars). Maximum: %(max)s'),
            params={'length': len(value), 'max': max_length},
        )


def validate_placeholders_match(source, translated):
    """Ensure placeholders in source exist in translation"""
    patterns = [r'\{[^}]+\}', r'%[sdif]', r'{{[^}]+}}']
    errors = []
    for pattern in patterns:
        src_phs = set(re.findall(pattern, source or ''))
        tgt_phs = set(re.findall(pattern, translated or ''))
        missing = src_phs - tgt_phs
        extra   = tgt_phs - src_phs
        if missing:
            errors.append(f"Missing placeholders: {missing}")
        if extra:
            errors.append(f"Extra placeholders: {extra}")
    if errors:
        raise ValidationError(_('Placeholder mismatch: %(errors)s'), params={'errors': '; '.join(errors)})


def validate_html_tags_match(source, translated):
    """HTML tags must match between source and translation"""
    tags_pattern = r'</?[a-z][a-z0-9]*(?:\s[^>]*)?>|<[a-z][a-z0-9]*/>'
    src_tags = re.findall(tags_pattern, source or '', re.IGNORECASE)
    tgt_tags = re.findall(tags_pattern, translated or '', re.IGNORECASE)
    if len(src_tags) != len(tgt_tags):
        raise ValidationError(
            _('HTML tag count mismatch: source has %(src)s tags, translation has %(tgt)s'),
            params={'src': len(src_tags), 'tgt': len(tgt_tags)},
        )


def validate_not_do_not_translate(translation_key, language_code):
    """Check glossary — do-not-translate terms"""
    try:
        from .models.translation import TranslationGlossary
        dnt_terms = TranslationGlossary.objects.filter(
            is_do_not_translate=True,
            source_language__code=language_code
        ).values_list('source_term', flat=True)
        for term in dnt_terms:
            if term.lower() in (translation_key or '').lower():
                raise ValidationError(
                    _('Term "%(term)s" is marked as Do Not Translate'),
                    params={'term': term},
                )
    except Exception as e:
        if not isinstance(e, ValidationError):
            logger.error(f"DNT validation error: {e}")


def validate_timezone_name(value):
    """Valid IANA timezone name"""
    try:
        import pytz
        if value not in pytz.all_timezones:
            raise ValidationError(
                _('%(value)s is not a valid timezone. Use IANA names like: Asia/Dhaka, UTC, Europe/London'),
                params={'value': value},
            )
    except ImportError:
        pass


def validate_exchange_rate(value):
    """Exchange rate must be positive"""
    from decimal import Decimal, InvalidOperation
    try:
        rate = Decimal(str(value))
        if rate <= 0:
            raise ValidationError(_('Exchange rate must be positive'))
        if rate > Decimal('1000000'):
            raise ValidationError(_('Exchange rate seems unreasonably high'))
    except (InvalidOperation, TypeError):
        raise ValidationError(_('Invalid exchange rate value'))


def validate_import_json_structure(data):
    """Validate JSON import structure: {key: value} or {locale: {key: value}}"""
    if not isinstance(data, dict):
        raise DRFValidationError("Import data must be a JSON object (dict)")
    for k, v in data.items():
        if not isinstance(k, str):
            raise DRFValidationError(f"All keys must be strings, got: {type(k).__name__}")
        if not isinstance(v, (str, dict)):
            raise DRFValidationError(f"Values must be strings or nested dicts, got: {type(v).__name__} for key '{k}'")
    return True


def validate_phone_number(number, country_code):
    """Validate phone number against country format"""
    try:
        from .models.geo import PhoneFormat
        phone_format = PhoneFormat.objects.filter(country__code=country_code.upper()).first()
        if phone_format:
            result = phone_format.validate_number(number)
            if not result.get('valid'):
                raise ValidationError(
                    _('Invalid phone number for %(country)s'),
                    params={'country': country_code},
                )
    except Exception as e:
        if isinstance(e, ValidationError):
            raise
        logger.error(f"Phone validation error: {e}")


def validate_postal_code(postal_code, country_code):
    """Validate postal code against country format regex"""
    try:
        from .models.settings import AddressFormat
        fmt = AddressFormat.objects.filter(country__code=country_code.upper()).first()
        if fmt and fmt.postal_code_regex and postal_code:
            if not re.match(fmt.postal_code_regex, str(postal_code)):
                raise ValidationError(
                    _('Invalid postal code format for %(country)s. Example: %(example)s'),
                    params={'country': country_code, 'example': fmt.postal_code_example or ''},
                )
    except Exception as e:
        if isinstance(e, ValidationError):
            raise
        logger.error(f"Postal code validation error: {e}")
