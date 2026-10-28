"""
api/support/multilang/bangla_processor.py
FILE 59/70 — Bengali NLP Preprocessor

Bengali text preprocessing for better AI classification।
Normalization + keyword extraction + transliteration।
"""
import re
import logging
logger = logging.getLogger(__name__)

# Bengali → English transliteration map (common support keywords)
BN_KEYWORD_MAP = {
    'টাকা':          'money',
    'পেমেন্ট':       'payment',
    'বিকাশ':         'bkash',
    'নগদ':           'nagad',
    'উইথড্র':        'withdraw',
    'কয়েন':          'coins',
    'ব্যালেন্স':     'balance',
    'একাউন্ট':       'account',
    'লগইন':          'login',
    'পাসওয়ার্ড':    'password',
    'সাসপেন্ড':      'suspended',
    'ব্লক':           'blocked',
    'হ্যাক':          'hacked',
    'ফ্রড':           'fraud',
    'রিফান্ড':        'refund',
    'ভেরিফিকেশন':   'verification',
    'কেওয়াইসি':      'kyc',
    'রেফারেল':       'referral',
    'অফার':          'offer',
    'টাস্ক':          'task',
    'পাইনি':         'not received',
    'হচ্ছে না':      'not working',
    'সমস্যা':        'problem',
    'সাহায্য':       'help',
    'জরুরি':         'urgent',
    'দ্রুত':         'fast',
    'আজকে':          'today',
    'কাল':           'yesterday',
}

BN_STOP_WORDS = {
    'আমি','আমার','আমাকে','আমাদের','তুমি','তোমার','সে','তার',
    'এটা','এই','ওই','ওটা','যে','যা','কি','কিন্তু','এবং',
    'অথবা','তবে','হয়','হয়েছে','করেছি','করছি','করব',
    'না','নেই','আছে','ছিল','থেকে','জন্য','দিয়ে','নিয়ে',
}


class BanglaProcessor:
    """Bengali text NLP preprocessing"""

    def normalize(self, text: str) -> str:
        """Bengali text normalize করো"""
        if not text:
            return text

        # Unicode normalization
        import unicodedata
        text = unicodedata.normalize('NFC', text)

        # Remove zero-width characters
        text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)

        # Normalize ৷ (Bengali danda) to period
        text = text.replace('।', '.').replace('৷', '.')

        # Normalize repeated characters
        text = re.sub(r'([!?।.]{2,})', r'\1'[0], text)

        return text.strip()

    def extract_keywords(self, text: str) -> list:
        """Bengali text থেকে meaningful keywords extract করো"""
        text     = self.normalize(text)
        words    = re.findall(r'[\u0980-\u09FF]+', text)
        keywords = [w for w in words if w not in BN_STOP_WORDS and len(w) > 2]
        return keywords[:20]

    def to_english_keywords(self, text: str) -> list:
        """Bengali keywords → English equivalents"""
        english = []
        for bn_kw, en_kw in BN_KEYWORD_MAP.items():
            if bn_kw in text:
                english.append(en_kw)

        # Also keep English words from mixed text
        en_words = re.findall(r'[a-zA-Z]{3,}', text.lower())
        english.extend(en_words)

        return list(set(english))

    def detect_category_from_bengali(self, text: str) -> str:
        """Bengali text থেকে support category detect করো"""
        en_keywords = self.to_english_keywords(text)
        combined    = ' '.join(en_keywords).lower()

        if any(w in combined for w in ['payment','bkash','nagad','money','transaction']):
            return 'payment'
        if any(w in combined for w in ['withdraw','cashout','redeem']):
            return 'withdrawal'
        if any(w in combined for w in ['coins','balance','reward']):
            return 'coins'
        if any(w in combined for w in ['hacked','fraud','scam']):
            return 'fraud'
        if any(w in combined for w in ['account','login','suspended','blocked']):
            return 'account'
        if any(w in combined for w in ['kyc','verification']):
            return 'kyc'
        if any(w in combined for w in ['referral','commission']):
            return 'referral'
        if any(w in combined for w in ['offer','task','survey']):
            return 'offer'

        # Direct Bengali pattern matching
        urgent_patterns = ['জরুরি','এখনই','দ্রুত','আজকেই']
        if any(p in text for p in urgent_patterns):
            return 'other'  # Mark as other but flag urgent

        return 'other'

    def is_urgent_bengali(self, text: str) -> bool:
        urgent_words = ['জরুরি','জরুরী','এখনই','এখনি','দ্রুত','আজকেই','সাথে সাথে','হ্যাক','ফ্রড','চুরি']
        return any(w in text for w in urgent_words)

    def get_sentiment_words_bn(self) -> dict:
        return {
            'angry': ['রাগ','রাগান্বিত','বিরক্ত','ক্ষুব্ধ','ঘৃণা'],
            'frustrated': ['হতাশ','অপেক্ষা','কোনো সাড়া নেই','উত্তর দিচ্ছে না'],
            'positive': ['ধন্যবাদ','চমৎকার','ভালো','সন্তুষ্ট','খুশি'],
            'threatening': ['মামলা','অভিযোগ','পুলিশ','আইন','মিডিয়া'],
        }

    def segment_sentences(self, text: str) -> list:
        """Bengali text sentence segmentation"""
        text      = self.normalize(text)
        sentences = re.split(r'[.।!?\n]+', text)
        return [s.strip() for s in sentences if s.strip()]

    def has_bengali(self, text: str) -> bool:
        return bool(re.search(r'[\u0980-\u09FF]', text))

    def has_english(self, text: str) -> bool:
        return bool(re.search(r'[a-zA-Z]{3,}', text))

    def is_mixed(self, text: str) -> bool:
        return self.has_bengali(text) and self.has_english(text)

    def preprocess_for_ai(self, text: str) -> str:
        """AI classifier-এর জন্য text preprocess করো"""
        normalized = self.normalize(text)
        en_keywords= self.to_english_keywords(normalized)

        if en_keywords:
            return f"{normalized} [keywords: {' '.join(en_keywords)}]"
        return normalized


bangla_processor = BanglaProcessor()