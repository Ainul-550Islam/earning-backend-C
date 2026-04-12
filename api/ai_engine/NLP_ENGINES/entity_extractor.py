"""
api/ai_engine/NLP_ENGINES/entity_extractor.py
==============================================
Entity Extractor — text থেকে named entities extract করো।
Users, amounts, dates, phone numbers, emails, IDs।
Support ticket ও feedback processing এ ব্যবহার।
"""
import re, logging
from typing import List, Dict
logger = logging.getLogger(__name__)

class EntityExtractor:
    PATTERNS = {
        'email':     r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
        'phone':     r"(\+?88)?01[3-9]\d{8}",
        'amount':    r"(?:৳|BDT|USD|\$|৳\s?)\s?[\d,]+(?:\.\d{1,2})?",
        'user_id':   r"\bUSER\d{6}\b",
        'order_id':  r"\bORD-[A-Z0-9]+\b",
        'txn_id':    r"\bTXN-[A-Z0-9]+\b",
        'date':      r"\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b",
        'url':       r"https?://[^\s]+",
        'ip':        r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        'nid':       r"\b(?:\d{10}|\d{13}|\d{17})\b",
    }
    def extract(self, text: str) -> List[Dict]:
        entities = []
        for etype, pattern in self.PATTERNS.items():
            for m in re.finditer(pattern, text, re.IGNORECASE):
                entities.append({'type': etype, 'value': m.group().strip(), 'start': m.start(), 'end': m.end()})
        return entities

    def extract_by_type(self, text: str, entity_type: str) -> List[str]:
        pattern = self.PATTERNS.get(entity_type)
        if not pattern: return []
        return [m.group().strip() for m in re.finditer(pattern, text, re.IGNORECASE)]

    def extract_financial_entities(self, text: str) -> dict:
        amounts  = self.extract_by_type(text, 'amount')
        txn_ids  = self.extract_by_type(text, 'txn_id')
        user_ids = self.extract_by_type(text, 'user_id')
        return {'amounts': amounts, 'transaction_ids': txn_ids, 'user_ids': user_ids,
                'has_financial_entity': bool(amounts or txn_ids)}

    def anonymize(self, text: str, mask: str = "***") -> str:
        result = text
        for etype in ['email', 'phone', 'nid', 'ip']:
            pattern = self.PATTERNS.get(etype, '')
            if pattern:
                result = re.sub(pattern, f"[{etype.upper()}_REDACTED]", result, flags=re.IGNORECASE)
        return result

    def extract_support_entities(self, ticket_text: str) -> dict:
        entities  = self.extract(ticket_text)
        by_type   = {}
        for e in entities:
            by_type.setdefault(e['type'], []).append(e['value'])
        return {
            'all_entities':   entities,
            'by_type':        by_type,
            'entity_count':   len(entities),
            'has_user_id':    bool(by_type.get('user_id')),
            'has_amount':     bool(by_type.get('amount')),
            'has_txn_id':     bool(by_type.get('txn_id')),
        }


class KeywordExtractor:
    STOPWORDS = {
        'the','a','an','is','it','in','on','at','to','for','of','and','or','but',
        'not','are','was','were','be','been','have','has','do','does','did',
        'এটা','এই','সে','তার','কিন্তু','যে','এবং','বা','না','হয়','ছিল',
    }
    def extract(self, text: str, top_n: int = 10) -> List[str]:
        words = re.findall(r"[a-zA-Z\u0980-\u09FF]{3,}", text.lower())
        freq  = {}
        for w in words:
            if w not in self.STOPWORDS:
                freq[w] = freq.get(w, 0) + 1
        return sorted(freq, key=freq.get, reverse=True)[:top_n]

    def extract_with_scores(self, text: str, top_n: int = 10) -> List[Dict]:
        words = re.findall(r"[a-zA-Z\u0980-\u09FF]{3,}", text.lower())
        freq  = {}
        for w in words:
            if w not in self.STOPWORDS:
                freq[w] = freq.get(w, 0) + 1
        total = sum(freq.values()) or 1
        return [
            {'keyword': w, 'count': c, 'score': round(c/total, 4)}
            for w, c in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:top_n]
        ]
