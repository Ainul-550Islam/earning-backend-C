# api/offer_inventory/compliance_legal/disclaimer_manager.py
"""Disclaimer Manager — Platform risk disclosures and legal notices."""
import logging

logger = logging.getLogger(__name__)

DISCLAIMERS = {
    'earnings': {
        'en': 'Earnings are not guaranteed. Past performance does not indicate future results.',
        'bn': 'আয়ের কোনো গ্যারান্টি নেই। পূর্ববর্তী ফলাফল ভবিষ্যতের ফলাফল নির্দেশ করে না।',
    },
    'tax': {
        'en': 'Users are responsible for their own tax obligations. Consult a tax professional.',
        'bn': 'ব্যবহারকারীরা তাদের নিজস্ব কর দায়িত্বের জন্য দায়ী।',
    },
    'age': {
        'en': 'This platform is for users 18 years and older only.',
        'bn': 'এই প্ল্যাটফর্ম শুধুমাত্র ১৮ বছর বা তার বেশি বয়সীদের জন্য।',
    },
    'country': {
        'en': 'Availability varies by country. Some offers may not be available in your region.',
        'bn': 'প্রাপ্যতা দেশ অনুযায়ী পরিবর্তিত হয়।',
    },
    'withdrawal': {
        'en': 'Withdrawal processing may take 1–5 business days.',
        'bn': 'উইথড্রয়াল প্রসেস করতে ১–৫ কার্যদিবস সময় লাগতে পারে।',
    },
    'kyc': {
        'en': 'KYC verification is required for withdrawals above ৳500.',
        'bn': '৳৫০০-এর বেশি উইথড্রয়ালের জন্য KYC যাচাই প্রয়োজন।',
    },
}


class DisclaimerManager:
    """Platform disclaimer and legal notice management."""

    @classmethod
    def get(cls, key: str, language: str = 'en') -> str:
        """Get disclaimer text for a given type and language."""
        disclaimer = DISCLAIMERS.get(key, {})
        return disclaimer.get(language) or disclaimer.get('en', '')

    @classmethod
    def get_all(cls, language: str = 'en') -> dict:
        """Get all disclaimers for a language."""
        return {k: cls.get(k, language) for k in DISCLAIMERS}

    @classmethod
    def get_offer_disclaimer(cls, offer, language: str = 'bn') -> str:
        """Get composite disclaimer for an offer."""
        parts = [cls.get('earnings', language), cls.get('country', language)]
        return ' '.join(p for p in parts if p)

    @classmethod
    def get_withdrawal_disclaimer(cls, amount, language: str = 'bn') -> str:
        """Get withdrawal-specific disclaimer."""
        base = cls.get('withdrawal', language)
        if float(amount) >= 500:
            base += ' ' + cls.get('kyc', language)
        return base

    @classmethod
    def get_all_keys(cls) -> list:
        return list(DISCLAIMERS.keys())
