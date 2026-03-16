# api/promotions/ai/nlp_analyzer.py
# NLP Analyzer — Text Proof Analysis, Sentiment, Language Detection
# Survey response, comment proof, text task verify করে
# =============================================================================

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger('ai.nlp_analyzer')


@dataclass
class NLPAnalysisResult:
    text:              str
    language:          str
    language_confidence: float
    sentiment:         str          # positive, negative, neutral
    sentiment_score:   float        # -1.0 to 1.0
    is_meaningful:     bool         # Not gibberish/random text
    word_count:        int
    unique_words:      int
    readability_score: float        # 0.0 - 1.0
    topics:            list
    keywords:          list
    is_spam:           bool
    spam_score:        float
    toxicity_score:    float        # 0.0 - 1.0
    flags:             list         = field(default_factory=list)


@dataclass
class TextProofVerification:
    is_valid:          bool
    confidence:        float
    language_match:    bool         # Expected language match হয়েছে কিনা
    min_length_met:    bool
    quality_score:     float
    issues:            list
    recommendation:    str


class NLPAnalyzer:
    """
    Natural Language Processing — Text proof analysis।

    Features:
    1. Language detection
    2. Sentiment analysis
    3. Spam/gibberish detection
    4. Toxicity detection
    5. Keyword extraction
    6. Survey response quality check
    """

    # Spam indicators
    SPAM_PATTERNS = [
        r'\b(click here|buy now|free money|make money fast|earn \$\d+)\b',
        r'(.)\1{4,}',                    # aaaaa repeated chars
        r'\b\w{1}\s\w{1}\s\w{1}\s\w{1}', # a b c d random single chars
    ]

    def analyze(self, text: str, expected_language: str = None) -> NLPAnalysisResult:
        """Text analyze করে।"""
        if not text or not text.strip():
            return self._empty_result()

        text = text.strip()

        # Language detection
        lang, lang_conf = self._detect_language(text)

        # Basic stats
        words        = text.split()
        word_count   = len(words)
        unique_words = len(set(w.lower() for w in words))

        # Spam detection
        spam_score = self._calculate_spam_score(text)

        # Meaningfulness
        is_meaningful = self._is_meaningful(text, word_count, unique_words)

        # Sentiment
        sentiment, sent_score = self._analyze_sentiment(text)

        # Toxicity
        toxicity = self._detect_toxicity(text)

        # Readability
        readability = self._calculate_readability(text, word_count)

        # Keywords
        keywords = self._extract_keywords(text)

        # Topics
        topics = self._extract_topics(text)

        flags = []
        if spam_score > 0.7:  flags.append('spam')
        if not is_meaningful: flags.append('gibberish')
        if toxicity > 0.7:    flags.append('toxic')
        if word_count < 5:    flags.append('too_short')

        return NLPAnalysisResult(
            text=text[:1000], language=lang, language_confidence=lang_conf,
            sentiment=sentiment, sentiment_score=sent_score,
            is_meaningful=is_meaningful, word_count=word_count,
            unique_words=unique_words, readability_score=readability,
            topics=topics, keywords=keywords,
            is_spam=spam_score > 0.7, spam_score=round(spam_score, 3),
            toxicity_score=round(toxicity, 3), flags=flags,
        )

    def verify_text_proof(
        self,
        text: str,
        min_words: int = 20,
        expected_language: str = None,
        required_topics: list = None,
    ) -> TextProofVerification:
        """Text proof (survey response, comment) verify করে।"""
        analysis = self.analyze(text, expected_language)
        issues   = []

        # Length check
        min_met = analysis.word_count >= min_words
        if not min_met:
            issues.append(f'too_short:{analysis.word_count}_words_min_{min_words}')

        # Language match
        lang_match = True
        if expected_language and analysis.language != expected_language:
            lang_match = False
            issues.append(f'language_mismatch:{analysis.language}_vs_{expected_language}')

        # Quality check
        quality = analysis.readability_score
        if analysis.is_spam:
            quality *= 0.2; issues.append('spam_detected')
        if not analysis.is_meaningful:
            quality *= 0.1; issues.append('gibberish_detected')
        if analysis.toxicity_score > 0.7:
            quality *= 0.3; issues.append('toxic_content')

        # Topic match
        if required_topics:
            for topic in required_topics:
                if topic.lower() not in ' '.join(analysis.keywords).lower():
                    issues.append(f'missing_topic:{topic}')

        # Overall confidence
        confidence = quality
        if min_met:      confidence += 0.20
        if lang_match:   confidence += 0.10
        if not issues:   confidence += 0.20
        confidence = min(1.0, confidence)

        return TextProofVerification(
            is_valid        = confidence >= 0.50 and min_met and lang_match,
            confidence      = round(confidence, 3),
            language_match  = lang_match,
            min_length_met  = min_met,
            quality_score   = round(quality, 3),
            issues          = issues,
            recommendation  = 'approve' if confidence >= 0.7 else
                              'manual_review' if confidence >= 0.4 else 'reject',
        )

    # ── NLP Methods ───────────────────────────────────────────────────────────

    def _detect_language(self, text: str) -> tuple[str, float]:
        """Language detect করে।"""
        for lib_fn in [self._langdetect, self._langid_detect, self._simple_detect]:
            try:
                result = lib_fn(text)
                if result:
                    return result
            except Exception:
                continue
        return 'unknown', 0.0

    def _langdetect(self, text: str) -> Optional[tuple]:
        from langdetect import detect, detect_langs
        langs = detect_langs(text)
        if langs:
            return langs[0].lang, round(langs[0].prob, 3)
        return None

    def _langid_detect(self, text: str) -> Optional[tuple]:
        import langid
        lang, score = langid.classify(text)
        return lang, min(1.0, abs(score) / 10)

    def _simple_detect(self, text: str) -> tuple[str, float]:
        """Unicode block দিয়ে simple language detection।"""
        # Bengali characters range
        bengali = sum(1 for c in text if '\u0980' <= c <= '\u09FF')
        latin   = sum(1 for c in text if c.isascii() and c.isalpha())
        arabic  = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
        total   = max(len(text), 1)

        if bengali / total > 0.3: return 'bn', 0.7
        if arabic / total > 0.3:  return 'ar', 0.7
        if latin / total > 0.5:   return 'en', 0.6
        return 'unknown', 0.3

    def _analyze_sentiment(self, text: str) -> tuple[str, float]:
        """Sentiment analysis।"""
        try:
            from transformers import pipeline
            if not hasattr(self, '_sentiment_pipeline'):
                self._sentiment_pipeline = pipeline(
                    'sentiment-analysis',
                    model='distilbert-base-uncased-finetuned-sst-2-english',
                    truncation=True,
                )
            result = self._sentiment_pipeline(text[:512])[0]
            score  = result['score'] if result['label'] == 'POSITIVE' else -result['score']
            label  = 'positive' if score > 0.1 else 'negative' if score < -0.1 else 'neutral'
            return label, round(score, 3)
        except Exception:
            return self._simple_sentiment(text)

    def _simple_sentiment(self, text: str) -> tuple[str, float]:
        """Rule-based simple sentiment।"""
        pos_words = {'good', 'great', 'excellent', 'amazing', 'love', 'nice', 'best', 'happy'}
        neg_words = {'bad', 'terrible', 'awful', 'hate', 'worst', 'poor', 'horrible'}
        words     = set(text.lower().split())
        pos_count = len(words & pos_words)
        neg_count = len(words & neg_words)
        if pos_count > neg_count:   return 'positive', 0.6
        if neg_count > pos_count:   return 'negative', -0.6
        return 'neutral', 0.0

    def _calculate_spam_score(self, text: str) -> float:
        score = 0.0
        text_lower = text.lower()
        for pattern in self.SPAM_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                score += 0.3
        # Repetitive text check
        words = text.split()
        if len(words) > 3:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.3:
                score += 0.4
        return min(1.0, score)

    def _is_meaningful(self, text: str, word_count: int, unique_words: int) -> bool:
        if word_count < 3:
            return False
        if unique_words / max(word_count, 1) < 0.2:
            return False  # Too repetitive
        # Check if mostly random characters
        alpha_ratio = sum(1 for c in text if c.isalpha()) / max(len(text), 1)
        return alpha_ratio > 0.5

    def _detect_toxicity(self, text: str) -> float:
        """Toxic language detection।"""
        toxic_patterns = [
            r'\b(kill|murder|rape|bomb|terrorist)\b',
            r'\b(fuck|shit|ass|bitch|damn)\b',   # profanity
        ]
        score = 0.0
        for pattern in toxic_patterns:
            if re.search(pattern, text.lower()):
                score += 0.35
        return min(1.0, score)

    def _calculate_readability(self, text: str, word_count: int) -> float:
        """Simplified readability score।"""
        if word_count < 5:
            return 0.1
        sentences    = len(re.split(r'[.!?]+', text))
        avg_sent_len = word_count / max(sentences, 1)
        # Too long or too short sentences = lower readability
        if 5 <= avg_sent_len <= 25:
            score = 0.8
        elif avg_sent_len < 3:
            score = 0.3
        else:
            score = 0.5
        # Diversity bonus
        unique_ratio = len(set(text.lower().split())) / max(word_count, 1)
        score       += unique_ratio * 0.2
        return min(1.0, round(score, 3))

    def _extract_keywords(self, text: str, top_n: int = 10) -> list:
        """Simple keyword extraction — stop words remove করে।"""
        stop_words = {
            'the', 'is', 'in', 'it', 'of', 'and', 'a', 'to', 'was', 'for',
            'on', 'are', 'with', 'as', 'at', 'be', 'by', 'this', 'an', 'or',
            'that', 'have', 'from', 'not', 'but', 'what', 'all', 'were',
        }
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        from collections import Counter
        freq = Counter(w for w in words if w not in stop_words)
        return [word for word, _ in freq.most_common(top_n)]

    def _extract_topics(self, text: str) -> list:
        """Simple topic extraction — keyword matching।"""
        topic_keywords = {
            'social_media':   ['youtube', 'facebook', 'instagram', 'tiktok', 'twitter'],
            'technology':     ['app', 'software', 'mobile', 'android', 'ios', 'install'],
            'finance':        ['money', 'payment', 'earn', 'reward', 'cash'],
            'entertainment':  ['video', 'music', 'movie', 'game', 'watch'],
        }
        text_lower = text.lower()
        return [
            topic for topic, keywords in topic_keywords.items()
            if any(kw in text_lower for kw in keywords)
        ]

    def _empty_result(self) -> NLPAnalysisResult:
        return NLPAnalysisResult(
            text='', language='unknown', language_confidence=0.0,
            sentiment='neutral', sentiment_score=0.0,
            is_meaningful=False, word_count=0, unique_words=0,
            readability_score=0.0, topics=[], keywords=[],
            is_spam=False, spam_score=0.0, toxicity_score=0.0,
        )