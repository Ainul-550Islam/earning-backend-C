"""
api/ai_engine/NLP_ENGINES/keyword_extractor.py
===============================================
Keyword Extractor — TF-IDF, RAKE, YAKE based।
Offer descriptions, user reviews, support tickets থেকে keywords।
SEO, tagging, search optimization।
"""
import re, logging, math
from typing import List, Dict, Optional
logger = logging.getLogger(__name__)

class KeywordExtractor:
    """Multi-method keyword extraction engine।"""

    STOP_WORDS = {
        'en': {'a','an','the','is','are','was','were','be','been','being','have','has',
               'had','do','does','did','will','would','could','should','may','might',
               'shall','must','can','to','of','in','for','on','with','at','by','from',
               'up','about','into','through','during','before','after','above','below',
               'this','that','these','those','it','its','i','you','he','she','we','they',
               'and','but','or','so','yet','both','either','neither','not','no'},
        'bn': {'এই','সেই','কিন্তু','এবং','তবে','বা','যে','তা','আমি','তুমি','সে','আমরা'},
    }

    def extract(self, text: str, method: str = 'tfidf',
                top_n: int = 10, language: str = 'en') -> List[Dict]:
        """Keywords extract করো।"""
        if not text or not text.strip():
            return []

        if method == 'rake':
            return self._rake_extract(text, top_n, language)
        elif method == 'frequency':
            return self._frequency_extract(text, top_n, language)
        return self._tfidf_extract(text, top_n, language)

    def _tfidf_extract(self, text: str, top_n: int, lang: str) -> List[Dict]:
        """Simplified TF-IDF keyword extraction।"""
        words = re.findall(r'\b[a-zA-Z\u0980-\u09FF]{3,}\b', text.lower())
        stop  = self.STOP_WORDS.get(lang, self.STOP_WORDS['en'])
        words = [w for w in words if w not in stop]

        tf: Dict[str, int] = {}
        for w in words:
            tf[w] = tf.get(w, 0) + 1

        total = len(words) or 1
        scored = []
        for word, count in tf.items():
            tf_score  = count / total
            idf_score = math.log(total / (count + 1)) + 1
            scored.append({
                'keyword': word,
                'score':   round(tf_score * idf_score, 6),
                'count':   count,
                'method':  'tfidf',
            })
        return sorted(scored, key=lambda x: x['score'], reverse=True)[:top_n]

    def _rake_extract(self, text: str, top_n: int, lang: str) -> List[Dict]:
        """RAKE (Rapid Automatic Keyword Extraction)।"""
        stop = self.STOP_WORDS.get(lang, self.STOP_WORDS['en'])
        stop_pattern = r'\b(?:' + '|'.join(re.escape(w) for w in stop) + r')\b'
        phrases = re.split(stop_pattern, text.lower(), flags=re.IGNORECASE)
        phrases = [p.strip() for p in phrases if p.strip() and len(p.strip()) > 2]

        word_freq: Dict[str, int] = {}
        word_deg: Dict[str, int]  = {}
        for phrase in phrases:
            words = phrase.split()
            for w in words:
                word_freq[w] = word_freq.get(w, 0) + 1
                word_deg[w]  = word_deg.get(w, 0) + len(words) - 1

        scored = []
        for phrase in phrases[:top_n * 2]:
            words = phrase.split()
            if not words:
                continue
            score = sum((word_deg.get(w, 0) + word_freq.get(w, 0)) / max(word_freq.get(w, 1), 1)
                        for w in words)
            scored.append({'keyword': phrase, 'score': round(score, 4), 'method': 'rake'})

        seen = set()
        unique = []
        for item in sorted(scored, key=lambda x: x['score'], reverse=True):
            if item['keyword'] not in seen:
                seen.add(item['keyword'])
                unique.append(item)
        return unique[:top_n]

    def _frequency_extract(self, text: str, top_n: int, lang: str) -> List[Dict]:
        """Simple frequency-based extraction।"""
        words = re.findall(r'\b[a-zA-Z\u0980-\u09FF]{3,}\b', text.lower())
        stop  = self.STOP_WORDS.get(lang, self.STOP_WORDS['en'])
        words = [w for w in words if w not in stop]
        freq: Dict[str, int] = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        total = len(words) or 1
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [{'keyword': w, 'score': round(c/total, 6), 'count': c, 'method': 'frequency'}
                for w, c in sorted_words[:top_n]]

    def extract_hashtags(self, text: str) -> List[str]:
        """Hashtags extract করো।"""
        return re.findall(r'#\w+', text)

    def extract_phrases(self, text: str, n_gram: int = 2) -> List[Dict]:
        """N-gram phrases extract করো।"""
        words = re.findall(r'\b[a-zA-Z\u0980-\u09FF]{2,}\b', text.lower())
        phrases: Dict[str, int] = {}
        for i in range(len(words) - n_gram + 1):
            phrase = ' '.join(words[i:i+n_gram])
            phrases[phrase] = phrases.get(phrase, 0) + 1
        sorted_phrases = sorted(phrases.items(), key=lambda x: x[1], reverse=True)[:20]
        return [{'phrase': p, 'count': c} for p, c in sorted_phrases]

    def bulk_extract(self, texts: List[str], top_n: int = 5) -> List[Dict]:
        """Multiple texts থেকে keyword extract।"""
        results = []
        for i, text in enumerate(texts):
            keywords = self.extract(text, top_n=top_n)
            results.append({'text_index': i, 'keywords': keywords})
        return results
