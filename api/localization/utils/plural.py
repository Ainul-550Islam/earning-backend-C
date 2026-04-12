# utils/plural.py
"""
CLDR Plural Rules for 15 supported languages.
Based on CLDR v43 specification.
https://www.unicode.org/cldr/charts/43/supplemental/language_plural_rules.html

Forms: zero, one, two, few, many, other
"""
from typing import Callable, Dict


# ── CLDR plural rule functions per language ────────────────────────

def _plural_en(n: float) -> str:
    """English: one (n=1) → other"""
    i = int(n)
    if i == 1 and n == 1:
        return 'one'
    return 'other'


def _plural_bn(n: float) -> str:
    """Bengali: one (n=0,1) → other"""
    if n == 0 or n == 1:
        return 'one'
    return 'other'


def _plural_hi(n: float) -> str:
    """Hindi: same as Bengali"""
    return _plural_bn(n)


def _plural_ar(n: float) -> str:
    """
    Arabic — 6 forms (most complex).
    zero: n=0
    one: n=1
    two: n=2
    few: n % 100 in 3..10
    many: n % 100 in 11..99
    other: everything else
    """
    n100 = int(n) % 100
    if n == 0:
        return 'zero'
    if n == 1:
        return 'one'
    if n == 2:
        return 'two'
    if 3 <= n100 <= 10:
        return 'few'
    if 11 <= n100 <= 99:
        return 'many'
    return 'other'


def _plural_ur(n: float) -> str:
    """Urdu — same as English"""
    return _plural_en(n)


def _plural_fa(n: float) -> str:
    """Persian — one (n=0,1) → other"""
    return _plural_bn(n)


def _plural_he(n: float) -> str:
    """
    Hebrew — 4 forms.
    one: n=1
    two: n=2
    many: n is not 0 and n % 10 = 0
    other: everything else
    """
    if n == 1:
        return 'one'
    if n == 2:
        return 'two'
    if n != 0 and int(n) % 10 == 0:
        return 'many'
    return 'other'


def _plural_es(n: float) -> str:
    """Spanish — one (n=1) → other"""
    return _plural_en(n)


def _plural_fr(n: float) -> str:
    """
    French — one (n=0,1) → other.
    (French treats 0 as singular)
    """
    if n == 0 or n == 1:
        return 'one'
    return 'other'


def _plural_de(n: float) -> str:
    """German — one (n=1) → other"""
    return _plural_en(n)


def _plural_zh(n: float) -> str:
    """Chinese — other only (no plural distinction)"""
    return 'other'


def _plural_ja(n: float) -> str:
    """Japanese — other only"""
    return 'other'


def _plural_ko(n: float) -> str:
    """Korean — other only"""
    return 'other'


def _plural_id(n: float) -> str:
    """Indonesian — other only"""
    return 'other'


def _plural_ms(n: float) -> str:
    """Malay — other only"""
    return 'other'


def _plural_ta(n: float) -> str:
    """Tamil — one (n=1) → other"""
    return _plural_en(n)


def _plural_te(n: float) -> str:
    """Telugu — one (n=1) → other"""
    return _plural_en(n)


def _plural_ml(n: float) -> str:
    """Malayalam — one (n=1) → other"""
    return _plural_en(n)


def _plural_ne(n: float) -> str:
    """Nepali — one (n=1) → other"""
    return _plural_en(n)


def _plural_si(n: float) -> str:
    """
    Sinhala — 2 forms.
    one: n=0 or n=1
    other: everything else
    """
    return _plural_bn(n)


def _plural_tr(n: float) -> str:
    """Turkish — one (n=1) → other"""
    return _plural_en(n)


def _plural_ru(n: float) -> str:
    """
    Russian — 3 forms.
    one: n % 10 = 1 and n % 100 ≠ 11
    few: n % 10 in 2..4 and n % 100 not in 12..14
    many: n % 10 = 0, or n % 10 in 5..9, or n % 100 in 11..14
    """
    n10 = int(n) % 10
    n100 = int(n) % 100
    if n10 == 1 and n100 != 11:
        return 'one'
    if 2 <= n10 <= 4 and not (12 <= n100 <= 14):
        return 'few'
    return 'many'


def _plural_pl(n: float) -> str:
    """
    Polish — 4 forms.
    one: n=1
    few: n % 10 in 2..4 and n % 100 not in 12..14
    many: n % 10 in 0,1 or 5..9 or n % 100 in 11..14
    other: everything else
    """
    n10 = int(n) % 10
    n100 = int(n) % 100
    if n == 1:
        return 'one'
    if 2 <= n10 <= 4 and not (12 <= n100 <= 14):
        return 'few'
    if n10 in (0, 1) or 5 <= n10 <= 9 or 11 <= n100 <= 14:
        return 'many'
    return 'other'


def _plural_pt(n: float) -> str:
    """Portuguese — one (n=0,1) → other"""
    return _plural_fr(n)


def _plural_vi(n: float) -> str:
    """Vietnamese — other only"""
    return 'other'


def _plural_my(n: float) -> str:
    """Burmese — other only"""
    return 'other'


def _plural_km(n: float) -> str:
    """Khmer — other only"""
    return 'other'


def _plural_th(n: float) -> str:
    """Thai — other only"""
    return 'other'


def _plural_sw(n: float) -> str:
    """Swahili — one (n=1) → other"""
    return _plural_en(n)


def _plural_am(n: float) -> str:
    """Amharic — one (n=0,1) → other"""
    return _plural_bn(n)


def _plural_uk(n: float) -> str:
    """Ukrainian — same rules as Russian"""
    return _plural_ru(n)


# ── Lookup table ────────────────────────────────────────────────────
PLURAL_RULES: Dict[str, Callable[[float], str]] = {
    # Tier 1 — CPAlead primary languages
    'en': _plural_en,
    'bn': _plural_bn,
    'hi': _plural_hi,
    'ar': _plural_ar,
    'ur': _plural_ur,
    'es': _plural_es,
    'fr': _plural_fr,
    'de': _plural_de,
    'zh': _plural_zh,
    'id': _plural_id,
    'ms': _plural_ms,
    'ta': _plural_ta,
    'ne': _plural_ne,
    'tr': _plural_tr,
    'si': _plural_si,
    # Additional commonly used
    'fa': _plural_fa,
    'he': _plural_he,
    'ja': _plural_ja,
    'ko': _plural_ko,
    'ru': _plural_ru,
    'pl': _plural_pl,
    'pt': _plural_pt,
    'vi': _plural_vi,
    'my': _plural_my,
    'km': _plural_km,
    'th': _plural_th,
    'te': _plural_te,
    'ml': _plural_ml,
    'sw': _plural_sw,
    'am': _plural_am,
    'uk': _plural_uk,
    # Variants — map to base
    'zh-hans': _plural_zh,
    'zh-hant': _plural_zh,
    'pt-br': _plural_pt,
    'es-419': _plural_es,
    'en-us': _plural_en,
    'en-gb': _plural_en,
    'bn-bd': _plural_bn,
    'bn-in': _plural_bn,
}

# Available plural forms per language
PLURAL_FORMS: Dict[str, list] = {
    'ar': ['zero', 'one', 'two', 'few', 'many', 'other'],
    'he': ['one', 'two', 'many', 'other'],
    'ru': ['one', 'few', 'many'],
    'uk': ['one', 'few', 'many'],
    'pl': ['one', 'few', 'many', 'other'],
    'default': ['one', 'other'],
    'cjk': ['other'],  # Chinese, Japanese, Korean, etc.
}


def get_plural_form(n: float, locale: str) -> str:
    """
    CLDR plural category for number n in locale.
    Returns: 'zero' | 'one' | 'two' | 'few' | 'many' | 'other'
    """
    # Normalize locale
    lang = locale.lower().split('-')[0].split('_')[0]

    # Try exact match, then base language
    rule_fn = PLURAL_RULES.get(locale.lower()) or PLURAL_RULES.get(lang)

    if rule_fn:
        return rule_fn(n)

    # Default: English rules
    return _plural_en(n)


def get_plural_forms_for_locale(locale: str) -> list:
    """What plural forms does a locale support?"""
    lang = locale.lower().split('-')[0]
    if lang in ('zh', 'ja', 'ko', 'id', 'ms', 'vi', 'my', 'km', 'th'):
        return ['other']
    if lang == 'ar':
        return PLURAL_FORMS['ar']
    if lang in ('ru', 'uk'):
        return PLURAL_FORMS['ru']
    if lang == 'he':
        return PLURAL_FORMS['he']
    if lang == 'pl':
        return PLURAL_FORMS['pl']
    return PLURAL_FORMS['default']


def get_cldr_info(locale: str) -> dict:
    """Locale-র plural info return করে — useful for translation UI"""
    forms = get_plural_forms_for_locale(locale)
    examples = {}
    for form in forms:
        for n in range(0, 20):
            if get_plural_form(n, locale) == form:
                examples.setdefault(form, []).append(n)
                if len(examples[form]) >= 3:
                    break
    return {
        'locale': locale,
        'forms': forms,
        'form_count': len(forms),
        'examples': examples,
    }
