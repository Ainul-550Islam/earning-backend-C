# tests/factories.py
"""Test factories using factory_boy or simple helpers"""
from django.utils import timezone


def make_language(code='en', name='English', is_default=True, **kwargs):
    from localization.models.core import Language
    obj, _ = Language.objects.get_or_create(code=code, defaults={
        'name': name, 'is_default': is_default, 'is_active': True,
        'flag_emoji': '🇺🇸', 'locale_code': f'{code}_US', **kwargs
    })
    return obj


def make_country(code='BD', name='Bangladesh', phone_code='+880', **kwargs):
    from localization.models.core import Country
    obj, _ = Country.objects.get_or_create(code=code, defaults={
        'name': name, 'phone_code': phone_code, 'is_active': True,
        'flag_emoji': '🇧🇩', **kwargs
    })
    return obj


def make_currency(code='USD', name='US Dollar', symbol='$', **kwargs):
    from localization.models.core import Currency
    obj, _ = Currency.objects.get_or_create(code=code, defaults={
        'name': name, 'symbol': symbol, 'is_active': True,
        'exchange_rate': 1.0, **kwargs
    })
    return obj


def make_translation_key(key='test.key', category='test', **kwargs):
    from localization.models.core import TranslationKey
    obj, _ = TranslationKey.objects.get_or_create(key=key, defaults={
        'description': 'Test key', 'category': category, **kwargs
    })
    return obj


def make_translation(key=None, language=None, value='Test value', **kwargs):
    from localization.models.core import Translation
    if key is None:
        key = make_translation_key()
    if language is None:
        language = make_language()
    obj, _ = Translation.objects.get_or_create(key=key, language=language, defaults={
        'value': value, 'is_approved': True, **kwargs
    })
    return obj
