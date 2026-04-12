import re
from typing import Dict, List, Optional, Tuple
import logging
from collections import Counter
from langdetect import detect, detect_langs, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException
import pycld2 as cld2
from lingua import Language, LanguageDetectorBuilder

logger = logging.getLogger(__name__)


class LanguageDetector:
    """
    Advanced language detection service
    Combines multiple detection methods for accuracy
    """
    
    def __init__(self):
        # Initialize detectors
        self._initialize_langdetect()
        self.lingua_detector = self._initialize_lingua()
        
        # Language mapping
        self.language_mapping = {
            'en': 'English',
            'bn': 'Bengali',
            'hi': 'Hindi',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'pt': 'Portuguese',
            'ru': 'Russian',
            'ar': 'Arabic',
            'ja': 'Japanese',
            'zh': 'Chinese',
            'ko': 'Korean',
            'it': 'Italian',
            'nl': 'Dutch',
            'pl': 'Polish',
            'tr': 'Turkish',
            'vi': 'Vietnamese',
            'th': 'Thai',
            'id': 'Indonesian',
            'ms': 'Malay',
            'fa': 'Persian',
            'ur': 'Urdu',
            'he': 'Hebrew',
            'el': 'Greek',
            'sv': 'Swedish',
            'da': 'Danish',
            'fi': 'Finnish',
            'no': 'Norwegian',
            'cs': 'Czech',
            'hu': 'Hungarian',
            'ro': 'Romanian',
            'sk': 'Slovak',
            'hr': 'Croatian',
            'bg': 'Bulgarian',
            'uk': 'Ukrainian',
            'sr': 'Serbian',
            'sl': 'Slovenian',
            'et': 'Estonian',
            'lv': 'Latvian',
            'lt': 'Lithuanian',
        }
        
        # Language scripts
        self.scripts = {
            'en': 'Latin',
            'bn': 'Bengali',
            'hi': 'Devanagari',
            'ar': 'Arabic',
            'ja': 'Japanese',
            'zh': 'Chinese',
            'ko': 'Korean',
            'ru': 'Cyrillic',
            'el': 'Greek',
            'he': 'Hebrew',
            'th': 'Thai',
        }
        
        # Common words for quick detection
        self.common_words = {
            'en': {'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'I'},
            'es': {'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'ser', 'se'},
            'fr': {'le', 'de', 'un', 'à', 'être', 'et', 'en', 'avoir', 'que', 'pour'},
            'de': {'der', 'die', 'das', 'und', 'in', 'den', 'von', 'zu', 'das', 'mit'},
            'it': {'il', 'la', 'di', 'che', 'e', 'a', 'in', 'con', 'per', 'una'},
            'pt': {'o', 'a', 'de', 'do', 'da', 'em', 'um', 'para', 'com', 'não'},
            'ru': {'и', 'в', 'не', 'на', 'я', 'быть', 'с', 'что', 'а', 'это'},
            'ja': {'の', 'に', 'は', 'を', 'た', 'が', 'で', 'て', 'と', 'し'},
            'zh': {'的', '一', '是', '在', '不', '了', '有', '和', '人', '这'},
            'ko': {'이', '에', '는', '을', '의', '가', '으로', '한', '하고', '에서'},
            'ar': {'في', 'من', 'على', 'أن', 'ما', 'إن', 'لا', 'هذا', 'كان', 'إذا'},
            'hi': {'के', 'में', 'है', 'की', 'से', 'को', 'यह', 'इस', 'कि', 'जो'},
            'bn': {'এবং', 'এর', 'যে', 'কি', 'হয়', 'একটি', 'তিনি', 'সব', 'আর', 'হবে'},
        }
    
    def _initialize_langdetect(self):
        """Initialize langdetect with seed for consistency"""
        try:
            DetectorFactory.seed = 42
        except Exception:
            pass
    
    def _initialize_lingua(self):
        """Initialize Lingua detector with common languages"""
        try:
            languages = [
                Language.ENGLISH,
                Language.SPANISH,
                Language.FRENCH,
                Language.GERMAN,
                Language.ITALIAN,
                Language.PORTUGUESE,
                Language.RUSSIAN,
                Language.CHINESE,
                Language.JAPANESE,
                Language.KOREAN,
                Language.ARABIC,
                Language.HINDI,
                Language.BENGALI,
                Language.TURKISH,
                Language.VIETNAMESE,
                Language.THAI,
                Language.INDONESIAN,
            ]
            
            return LanguageDetectorBuilder.from_languages(*languages).build()
        except Exception as e:
            logger.error(f"Failed to initialize Lingua detector: {e}")
            return None
    
    def detect_language(
        self, 
        text: str, 
        confidence_threshold: float = 0.5
    ) -> Dict:
        """
        Detect language of text with high accuracy
        
        Args:
            text: Text to analyze
            confidence_threshold: Minimum confidence score (0.0 to 1.0)
        
        Returns:
            Dictionary with detection results
        """
        if not text or len(text.strip()) < 3:
            return {
                'language': 'unknown',
                'confidence': 0.0,
                'is_reliable': False,
                'error': 'Text too short'
            }
        
        # Clean text
        cleaned_text = self._clean_text(text)
        
        # Use multiple detection methods
        results = []
        
        # Method 1: langdetect
        langdetect_result = self._detect_with_langdetect(cleaned_text)
        if langdetect_result:
            results.append(langdetect_result)
        
        # Method 2: pycld2
        cld2_result = self._detect_with_cld2(cleaned_text)
        if cld2_result:
            results.append(cld2_result)
        
        # Method 3: Lingua
        lingua_result = self._detect_with_lingua(cleaned_text)
        if lingua_result:
            results.append(lingua_result)
        
        # Method 4: Word frequency
        word_freq_result = self._detect_with_word_frequency(cleaned_text)
        if word_freq_result:
            results.append(word_freq_result)
        
        # Method 5: Script detection
        script_result = self._detect_with_script(cleaned_text)
        if script_result:
            results.append(script_result)
        
        # Combine results
        final_result = self._combine_results(results, confidence_threshold)
        
        # Add metadata
        final_result.update({
            'text_length': len(text),
            'character_count': len(text),
            'word_count': len(text.split()),
            'methods_used': len([r for r in results if r]),
            'detection_methods': self._get_method_names(results)
        })
        
        return final_result
    
    def detect_multiple(self, texts: List[str]) -> List[Dict]:
        """
        Detect languages for multiple texts
        """
        return [self.detect_language(text) for text in texts]
    
    def get_language_name(self, language_code: str) -> str:
        """
        Get language name from code
        """
        return self.language_mapping.get(language_code, language_code)
    
    def get_script(self, language_code: str) -> str:
        """
        Get script for language
        """
        return self.scripts.get(language_code, 'Unknown')
    
    def _clean_text(self, text: str) -> str:
        """Clean text for language detection"""
        # Remove URLs
        text = re.sub(r'https?://\S+|www\.\S+', '', text)
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+\.\S+', '', text)
        
        # Remove special characters but keep language-specific ones
        text = re.sub(r'[^\w\s\u0600-\u06FF\u0980-\u09FF\u0900-\u097F\u0A00-\u0A7F\u0A80-\u0AFF\u0B00-\u0B7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F\u0D80-\u0DFF\u0E00-\u0E7F\u0E80-\u0EFF\u0F00-\u0FFF\u1000-\u109F\u1780-\u17FF\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]', ' ', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    def _detect_with_langdetect(self, text: str) -> Optional[Dict]:
        """Detect language using langdetect"""
        try:
            # Get all possible languages with probabilities
            languages = detect_langs(text)
            
            if languages:
                primary = languages[0]
                alternatives = [
                    {
                        'language': lang.lang,
                        'confidence': lang.prob,
                        'name': self.get_language_name(lang.lang)
                    }
                    for lang in languages[1:] if lang.prob > 0.1
                ]
                
                return {
                    'language': primary.lang,
                    'confidence': primary.prob,
                    'method': 'langdetect',
                    'alternative_languages': alternatives,
                    'is_reliable': primary.prob > 0.9
                }
        except LangDetectException as e:
            logger.debug(f"langdetect error: {e}")
        except Exception as e:
            logger.error(f"langdetect unexpected error: {e}")
        
        return None
    
    def _detect_with_cld2(self, text: str) -> Optional[Dict]:
        """Detect language using pycld2"""
        try:
            is_reliable, text_bytes_found, details = cld2.detect(text)
            
            if details:
                primary = details[0]
                alternatives = [
                    {
                        'language': lang[1].lower(),
                        'confidence': lang[2] / 100.0,
                        'name': self.get_language_name(lang[1].lower())
                    }
                    for lang in details[1:] if lang[2] > 10
                ]
                
                return {
                    'language': primary[1].lower(),
                    'confidence': primary[2] / 100.0,
                    'method': 'cld2',
                    'alternative_languages': alternatives,
                    'is_reliable': is_reliable and primary[2] > 80
                }
        except Exception as e:
            logger.error(f"cld2 error: {e}")
        
        return None
    
    def _detect_with_lingua(self, text: str) -> Optional[Dict]:
        """Detect language using Lingua"""
        if not self.lingua_detector or len(text) < 10:
            return None
        
        try:
            confidence_values = self.lingua_detector.compute_language_confidence_values(text)
            
            if confidence_values:
                primary = confidence_values[0]
                alternatives = [
                    {
                        'language': lang[0].iso_code_639_1.name.lower(),
                        'confidence': lang[1].value,
                        'name': lang[0].name
                    }
                    for lang in confidence_values[1:] if lang[1].value > 0.1
                ]
                
                return {
                    'language': primary[0].iso_code_639_1.name.lower(),
                    'confidence': primary[1].value,
                    'method': 'lingua',
                    'alternative_languages': alternatives,
                    'is_reliable': primary[1].value > 0.8
                }
        except Exception as e:
            logger.error(f"Lingua error: {e}")
        
        return None
    
    def _detect_with_word_frequency(self, text: str) -> Optional[Dict]:
        """Detect language using word frequency analysis"""
        words = text.lower().split()
        if len(words) < 3:
            return None
        
        scores = {}
        
        for lang_code, common_words in self.common_words.items():
            matches = sum(1 for word in words if word in common_words)
            if matches > 0:
                score = matches / len(words)
                scores[lang_code] = score
        
        if scores:
            best_lang = max(scores.items(), key=lambda x: x[1])
            
            return {
                'language': best_lang[0],
                'confidence': best_lang[1],
                'method': 'word_frequency',
                'is_reliable': best_lang[1] > 0.3 and len(words) > 5
            }
        
        return None
    
    def _detect_with_script(self, text: str) -> Optional[Dict]:
        """Detect language based on script/character usage"""
        if not text:
            return None
        
        # Check for specific scripts
        scripts = {
            'arabic': r'[\u0600-\u06FF]',
            'bengali': r'[\u0980-\u09FF]',
            'devanagari': r'[\u0900-\u097F]',
            'chinese': r'[\u4E00-\u9FFF]',
            'japanese': r'[\u3040-\u309F\u30A0-\u30FF]',
            'korean': r'[\uAC00-\uD7AF]',
            'cyrillic': r'[\u0400-\u04FF]',
            'greek': r'[\u0370-\u03FF]',
            'hebrew': r'[\u0590-\u05FF]',
            'thai': r'[\u0E00-\u0E7F]',
        }
        
        script_counts = {}
        total_chars = len([c for c in text if c.isalpha()])
        
        if total_chars == 0:
            return None
        
        for script_name, pattern in scripts.items():
            count = len(re.findall(pattern, text))
            if count > 0:
                script_counts[script_name] = count / total_chars
        
        if script_counts:
            # Map script to language
            script_to_lang = {
                'arabic': 'ar',
                'bengali': 'bn',
                'devanagari': 'hi',
                'chinese': 'zh',
                'japanese': 'ja',
                'korean': 'ko',
                'cyrillic': 'ru',  # Could be multiple languages
                'greek': 'el',
                'hebrew': 'he',
                'thai': 'th',
            }
            
            best_script = max(script_counts.items(), key=lambda x: x[1])
            lang_code = script_to_lang.get(best_script[0])
            
            if lang_code:
                return {
                    'language': lang_code,
                    'confidence': best_script[1],
                    'method': 'script_detection',
                    'detected_script': best_script[0],
                    'is_reliable': best_script[1] > 0.7
                }
        
        return None
    
    def _combine_results(
        self, 
        results: List[Dict], 
        confidence_threshold: float
    ) -> Dict:
        """
        Combine results from multiple detection methods
        """
        if not results:
            return {
                'language': 'unknown',
                'confidence': 0.0,
                'is_reliable': False,
                'error': 'No detection methods succeeded'
            }
        
        # Count votes for each language
        votes = Counter()
        weighted_scores = {}
        
        for result in results:
            lang = result['language']
            confidence = result['confidence']
            method_weight = self._get_method_weight(result['method'])
            
            votes[lang] += 1
            if lang not in weighted_scores:
                weighted_scores[lang] = 0
            weighted_scores[lang] += confidence * method_weight
        
        # Find language with highest votes
        if votes:
            # Get languages with most votes
            max_votes = max(votes.values())
            candidates = [lang for lang, count in votes.items() if count == max_votes]
            
            # If tie, use weighted scores
            if len(candidates) > 1:
                best_lang = max(candidates, key=lambda x: weighted_scores.get(x, 0))
            else:
                best_lang = candidates[0]
            
            # Calculate combined confidence
            lang_results = [r for r in results if r['language'] == best_lang]
            avg_confidence = sum(r['confidence'] for r in lang_results) / len(lang_results)
            
            # Adjust confidence based on number of agreeing methods
            agreement_boost = min(0.2, (max_votes - 1) * 0.1)
            final_confidence = min(1.0, avg_confidence + agreement_boost)
            
            # Get alternative languages
            alternatives = []
            for result in results:
                if (result['language'] != best_lang and 
                    result.get('alternative_languages')):
                    alternatives.extend(result['alternative_languages'])
            
            # Deduplicate alternatives
            seen = set()
            unique_alternatives = []
            for alt in alternatives:
                key = (alt['language'], alt['name'])
                if key not in seen:
                    seen.add(key)
                    unique_alternatives.append(alt)
            
            # Sort alternatives by confidence
            unique_alternatives.sort(key=lambda x: x['confidence'], reverse=True)
            
            return {
                'language': best_lang,
                'confidence': final_confidence,
                'is_reliable': final_confidence > confidence_threshold,
                'language_name': self.get_language_name(best_lang),
                'alternative_languages': unique_alternatives[:3],
                'method_breakdown': [
                    {
                        'method': r['method'],
                        'language': r['language'],
                        'confidence': r['confidence'],
                        'is_reliable': r.get('is_reliable', False)
                    }
                    for r in results
                ]
            }
        
        # Fallback to first result
        first_result = results[0]
        return {
            'language': first_result['language'],
            'confidence': first_result['confidence'],
            'is_reliable': first_result.get('is_reliable', False),
            'language_name': self.get_language_name(first_result['language']),
            'alternative_languages': first_result.get('alternative_languages', []),
            'method_breakdown': [{
                'method': first_result['method'],
                'language': first_result['language'],
                'confidence': first_result['confidence'],
                'is_reliable': first_result.get('is_reliable', False)
            }]
        }
    
    def _get_method_weight(self, method: str) -> float:
        """Get weight for detection method"""
        weights = {
            'cld2': 1.2,      # Very reliable
            'lingua': 1.1,    # Good for short texts
            'langdetect': 1.0, # Standard
            'word_frequency': 0.8, # Good for longer texts
            'script_detection': 0.9, # Good for non-Latin scripts
        }
        return weights.get(method, 0.5)
    
    def _get_method_names(self, results: List[Dict]) -> List[str]:
        """Get names of methods used"""
        return [r['method'] for r in results if r]
    
    def is_valid_language(self, language_code: str) -> bool:
        """
        Check if language code is valid
        """
        return language_code in self.language_mapping
    
    def get_supported_languages(self) -> List[Dict]:
        """
        Get list of supported languages
        """
        return [
            {
                'code': code,
                'name': name,
                'script': self.get_script(code)
            }
            for code, name in self.language_mapping.items()
        ]
    
    def detect_language_batch(
        self, 
        texts: List[str], 
        batch_size: int = 100
    ) -> List[Dict]:
        """
        Detect languages for batch of texts
        """
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = self.detect_multiple(batch)
            results.extend(batch_results)
        
        return results
    
    def get_language_statistics(self, texts: List[str]) -> Dict:
        """
        Get language distribution statistics
        """
        detections = self.detect_language_batch(texts)
        
        language_counts = Counter()
        confidence_sum = {}
        reliable_count = 0
        
        for detection in detections:
            lang = detection['language']
            language_counts[lang] += 1
            
            if lang not in confidence_sum:
                confidence_sum[lang] = 0
            confidence_sum[lang] += detection['confidence']
            
            if detection.get('is_reliable'):
                reliable_count += 1
        
        total = len(detections)
        
        return {
            'total_texts': total,
            'reliable_detections': reliable_count,
            'reliability_rate': reliable_count / total if total > 0 else 0,
            'language_distribution': [
                {
                    'language': lang,
                    'name': self.get_language_name(lang),
                    'count': count,
                    'percentage': count / total * 100 if total > 0 else 0,
                    'average_confidence': confidence_sum[lang] / count if count > 0 else 0
                }
                for lang, count in language_counts.most_common()
            ],
            'top_language': language_counts.most_common(1)[0] if language_counts else None
        }