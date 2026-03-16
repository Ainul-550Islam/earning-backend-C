import logging
import json
import math
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any, Union
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg, F, Window, Value, Case, When
from django.db.models.functions import (
    TruncDate, TruncHour, RowNumber, Coalesce,
    Concat, Substr, Length
)
from django.core.cache import cache
from django.conf import settings
from django.core.paginator import Paginator
import re
from collections import defaultdict
import jieba  # For Chinese text segmentation
from nltk.tokenize import word_tokenize  # For English text segmentation
from nltk.corpus import stopwords
import nltk

# Download NLTK data if not present
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

from ..models import FAQ, FAQCategory, FAQFeedback, ContentPage
from api.users.models import User
# from core.utils import get_client_ip, normalize_text
# from search.models import SearchIndex

logger = logging.getLogger(__name__)


class FAQService:
    """Service class for FAQ management business logic"""
    
    @staticmethod
    def get_faqs_by_category(
        category: Optional[FAQCategory] = None,
        category_slug: Optional[str] = None,
        faq_type: Optional[str] = None,
        language: str = 'en',
        limit: int = 20,
        offset: int = 0,
        user: Optional[User] = None
    ) -> Tuple[List[FAQ], int]:
        """
        Get FAQs by category or type
        
        Args:
            category: FAQCategory object
            category_slug: Category slug for lookup
            faq_type: Type of FAQs (e.g., 'general', 'earning')
            language: Language code
            limit: Number of items per page
            offset: Pagination offset
            user: User for permission filtering
            
        Returns:
            Tuple of (faq_list, total_count)
        """
        try:
            query = Q(is_active=True)
            
            # Filter by category
            if category:
                query &= Q(category=category)
            elif category_slug:
                query &= Q(category__slug=category_slug, category__is_active=True)
            
            # Filter by FAQ type
            if faq_type:
                query &= Q(category__faq_type=faq_type)
            
            # Filter by language (if FAQ has language field)
            # Assuming FAQ model has language field or uses category language
            
            # Get total count
            total_count = FAQ.objects.filter(query).count()
            
            # Get paginated results
            faqs = FAQ.objects.filter(query)\
                .select_related('category', 'updated_by')\
                .prefetch_related('related_pages')\
                .order_by('-priority', '-is_featured', 'question')\
                [offset:offset + limit]
            
            return list(faqs), total_count
            
        except Exception as e:
            logger.error(f"Error getting FAQs by category: {str(e)}")
            return [], 0
    
    @staticmethod
    def get_featured_faqs(
        limit: int = 10,
        language: str = 'en'
    ) -> List[FAQ]:
        """
        Get featured FAQs
        
        Args:
            limit: Number of items to return
            language: Language code
            
        Returns:
            List of featured FAQs
        """
        cache_key = f'featured_faqs_{language}_{limit}'
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        try:
            featured = FAQ.objects.filter(
                is_featured=True,
                is_active=True
            ).select_related('category')\
             .order_by('-priority', 'question')\
             [:limit]
            
            cache.set(cache_key, list(featured), 1800)  # Cache for 30 minutes
            return list(featured)
            
        except Exception as e:
            logger.error(f"Error getting featured FAQs: {str(e)}")
            return []
    
    @staticmethod
    def get_popular_faqs(
        days: int = 30,
        limit: int = 10,
        min_views: int = 10
    ) -> List[FAQ]:
        """
        Get popular FAQs based on views
        
        Args:
            days: Number of days to look back
            limit: Number of items to return
            min_views: Minimum views required
            
        Returns:
            List of popular FAQs
        """
        cache_key = f'popular_faqs_{days}_{limit}_{min_views}'
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            popular = FAQ.objects.filter(
                is_active=True,
                view_count__gte=min_views
            ).annotate(
                recent_views=Count(
                    Case(
                        When(
                            view_logs__created_at__gte=cutoff_date,
                            then=1
                        )
                    )
                ),
                helpfulness_score=Case(
                    When(
                        helpful_count=0,
                        then=0.0
                    ),
                    default=(
                        F('helpful_count') * 1.0 /
                        (F('helpful_count') + F('not_helpful_count'))
                    ),
                    output_field=models.FloatField()
                )
            ).order_by('-recent_views', '-helpfulness_score')\
             .select_related('category')\
             [:limit]
            
            cache.set(cache_key, list(popular), 1800)  # Cache for 30 minutes
            return list(popular)
            
        except Exception as e:
            logger.error(f"Error getting popular FAQs: {str(e)}")
            return []
    
    @staticmethod
    def get_most_helpful_faqs(
        min_feedback: int = 5,
        limit: int = 10
    ) -> List[FAQ]:
        """
        Get most helpful FAQs
        
        Args:
            min_feedback: Minimum feedback count required
            limit: Number of items to return
            
        Returns:
            List of most helpful FAQs
        """
        cache_key = f'helpful_faqs_{min_feedback}_{limit}'
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        try:
            helpful = FAQ.objects.filter(
                is_active=True,
                helpful_count__gte=min_feedback
            ).annotate(
                total_feedback=F('helpful_count') + F('not_helpful_count'),
                helpfulness_percentage=Case(
                    When(
                        total_feedback=0,
                        then=0.0
                    ),
                    default=(
                        F('helpful_count') * 100.0 / F('total_feedback')
                    ),
                    output_field=models.FloatField()
                )
            ).filter(
                total_feedback__gte=min_feedback
            ).order_by('-helpfulness_percentage', '-total_feedback')\
             .select_related('category')\
             [:limit]
            
            cache.set(cache_key, list(helpful), 1800)  # Cache for 30 minutes
            return list(helpful)
            
        except Exception as e:
            logger.error(f"Error getting helpful FAQs: {str(e)}")
            return []
    
    @staticmethod
    def get_faq_by_slug(
        slug: str,
        language: str = 'en',
        increment_view: bool = True
    ) -> Optional[FAQ]:
        """
        Get FAQ by slug
        
        Args:
            slug: FAQ slug
            language: Language code
            increment_view: Whether to increment view count
            
        Returns:
            FAQ object or None
        """
        try:
            faq = FAQ.objects.select_related(
                'category', 'updated_by'
            ).prefetch_related('related_pages').get(
                slug=slug
                # Add language filter if FAQ has language field
            )
            
            if increment_view:
                faq.increment_view_count()
            
            return faq
            
        except FAQ.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting FAQ by slug: {str(e)}")
            return None
    
    @staticmethod
    def record_feedback(
        faq: FAQ,
        user: Optional[User] = None,
        is_helpful: bool = True,
        feedback_text: str = '',
        request = None
    ) -> Dict[str, Any]:
        """
        Record FAQ feedback
        
        Args:
            faq: FAQ object
            user: User providing feedback
            is_helpful: Whether FAQ was helpful
            feedback_text: Additional feedback text
            request: Django request object
            
        Returns:
            Dictionary with feedback results
        """
        try:
            # Get client info
            ip_address = None
            user_agent = ''
            
            if request:
                ip_address = get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            with transaction.atomic():
                # Create feedback record
                feedback = FAQFeedback.objects.create(
                    faq=faq,
                    user=user,
                    is_helpful=is_helpful,
                    feedback_text=feedback_text,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                # Update FAQ statistics
                if is_helpful:
                    FAQ.objects.filter(id=faq.id).update(
                        helpful_count=F('helpful_count') + 1
                    )
                else:
                    FAQ.objects.filter(id=faq.id).update(
                        not_helpful_count=F('not_helpful_count') + 1
                    )
                
                # Refresh FAQ instance
                faq.refresh_from_db()
                
                # Update search index relevance
                FAQService._update_faq_relevance_score(faq)
                
                logger.debug(f"Recorded feedback for FAQ {faq.id}: helpful={is_helpful}")
                
                return {
                    'success': True,
                    'feedback_id': feedback.id,
                    'helpful_count': faq.helpful_count,
                    'not_helpful_count': faq.not_helpful_count,
                    'helpfulness_score': FAQService._calculate_helpfulness_score(faq)
                }
                
        except Exception as e:
            logger.error(f"Error recording FAQ feedback: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _calculate_helpfulness_score(faq: FAQ) -> float:
        """
        Calculate helpfulness score for FAQ
        
        Args:
            faq: FAQ object
            
        Returns:
            Helpfulness score (0-100)
        """
        total = faq.helpful_count + faq.not_helpful_count
        if total == 0:
            return 0
        return round((faq.helpful_count / total) * 100, 1)
    
    @staticmethod
    def _update_faq_relevance_score(faq: FAQ) -> None:
        """
        Update FAQ relevance score based on feedback
        
        Args:
            faq: FAQ object
        """
        try:
            # Calculate relevance score based on various factors
            helpfulness_score = FAQService._calculate_helpfulness_score(faq)
            view_score = min(faq.view_count / 1000, 10)  # Cap at 10 points
            feedback_score = min((faq.helpful_count + faq.not_helpful_count) / 50, 5)  # Cap at 5 points
            
            relevance_score = (
                helpfulness_score * 0.6 +  # 60% weight to helpfulness
                view_score * 0.3 +        # 30% weight to views
                feedback_score * 0.1       # 10% weight to feedback volume
            )
            
            # Update FAQ (assuming we add a relevance_score field)
            # FAQ.objects.filter(id=faq.id).update(relevance_score=relevance_score)
            
        except Exception as e:
            logger.error(f"Error updating FAQ relevance score: {str(e)}")
    
    @staticmethod
    def search_faqs(
        query: str,
        category_id: Optional[int] = None,
        faq_type: Optional[str] = None,
        language: str = 'en',
        limit: int = 20,
        offset: int = 0,
        use_semantic_search: bool = True
    ) -> Tuple[List[Dict[str, Any]], int, Dict[str, Any]]:
        """
        Search FAQs with advanced search capabilities
        
        Args:
            query: Search query
            category_id: Filter by category ID
            faq_type: Filter by FAQ type
            language: Language code
            limit: Results per page
            offset: Pagination offset
            use_semantic_search: Whether to use semantic search
            
        Returns:
            Tuple of (results, total_count, search_metadata)
        """
        try:
            # Clean and normalize query
            clean_query = FAQService._clean_search_query(query)
            
            if not clean_query or len(clean_query) < 2:
                return [], 0, {'query': query, 'cleaned_query': clean_query}
            
            # Start building query
            search_query = Q(is_active=True)
            
            # Apply category filter
            if category_id:
                search_query &= Q(category_id=category_id)
            
            # Apply FAQ type filter
            if faq_type:
                search_query &= Q(category__faq_type=faq_type)
            
            # Text search
            if use_semantic_search:
                results = FAQService._semantic_search(
                    clean_query, search_query, language, limit, offset
                )
                total_count = len(results)
                
                # Format results
                formatted_results = []
                for faq, score in results:
                    formatted_results.append({
                        'id': faq.id,
                        'question': faq.question,
                        'slug': faq.slug,
                        'short_answer': faq.short_answer,
                        'category': faq.category.name if faq.category else None,
                        'view_count': faq.view_count,
                        'helpfulness_score': FAQService._calculate_helpfulness_score(faq),
                        'relevance_score': score,
                        'matched_terms': FAQService._extract_matched_terms(faq, clean_query)
                    })
                
                # Sort by relevance score
                formatted_results.sort(key=lambda x: x['relevance_score'], reverse=True)
                
            else:
                # Simple text search
                text_query = (
                    Q(question__icontains=clean_query) |
                    Q(short_answer__icontains=clean_query) |
                    Q(detailed_answer__icontains=clean_query) |
                    Q(tags__contains=[clean_query])
                )
                
                search_query &= text_query
                
                # Get total count
                total_count = FAQ.objects.filter(search_query).count()
                
                # Get results
                faqs = FAQ.objects.filter(search_query)\
                    .select_related('category')\
                    .order_by('-priority', '-helpful_count')\
                    [offset:offset + limit]
                
                # Format results
                formatted_results = []
                for faq in faqs:
                    relevance_score = FAQService._calculate_text_relevance_score(faq, clean_query)
                    formatted_results.append({
                        'id': faq.id,
                        'question': faq.question,
                        'slug': faq.slug,
                        'short_answer': faq.short_answer,
                        'category': faq.category.name if faq.category else None,
                        'view_count': faq.view_count,
                        'helpfulness_score': FAQService._calculate_helpfulness_score(faq),
                        'relevance_score': relevance_score,
                        'matched_terms': FAQService._extract_matched_terms(faq, clean_query)
                    })
                
                # Sort by relevance score
                formatted_results.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            search_metadata = {
                'query': query,
                'cleaned_query': clean_query,
                'results_count': len(formatted_results),
                'total_count': total_count,
                'search_type': 'semantic' if use_semantic_search else 'text'
            }
            
            return formatted_results, total_count, search_metadata
            
        except Exception as e:
            logger.error(f"Error searching FAQs: {str(e)}")
            return [], 0, {'error': str(e)}
    
    @staticmethod
    def _clean_search_query(query: str) -> str:
        """
        Clean and normalize search query
        
        Args:
            query: Raw search query
            
        Returns:
            Cleaned query string
        """
        try:
            # Remove extra whitespace
            query = ' '.join(query.strip().split())
            
            # Convert to lowercase
            query = query.lower()
            
            # Remove special characters (keep letters, numbers, spaces)
            query = re.sub(r'[^\w\s]', ' ', query)
            
            # Remove stopwords for English queries
            if FAQService._is_english(query):
                stop_words = set(stopwords.words('english'))
                words = query.split()
                filtered_words = [word for word in words if word not in stop_words]
                query = ' '.join(filtered_words)
            
            return query
            
        except Exception as e:
            logger.error(f"Error cleaning search query: {str(e)}")
            return query
    
    @staticmethod
    def _is_english(text: str) -> bool:
        """
        Check if text is primarily English
        
        Args:
            text: Text to check
            
        Returns:
            Boolean indicating if text is English
        """
        try:
            # Simple check: if most characters are ASCII, assume English
            ascii_chars = sum(1 for char in text if ord(char) < 128)
            return ascii_chars / len(text) > 0.7 if text else False
        except:
            return False
    
    @staticmethod
    def _semantic_search(
        query: str,
        base_query: Q,
        language: str,
        limit: int,
        offset: int
    ) -> List[Tuple[FAQ, float]]:
        """
        Perform semantic search on FAQs
        
        Args:
            query: Search query
            base_query: Base filter query
            language: Language code
            limit: Results limit
            offset: Pagination offset
            
        Returns:
            List of (FAQ, relevance_score) tuples
        """
        try:
            # Get all eligible FAQs
            faqs = FAQ.objects.filter(base_query)\
                .select_related('category')\
                .prefetch_related('related_pages')
            
            results = []
            
            # Tokenize query
            if language == 'zh':
                query_tokens = list(jieba.cut(query))
            else:
                query_tokens = word_tokenize(query)
            
            for faq in faqs:
                # Calculate relevance score
                score = FAQService._calculate_semantic_relevance_score(
                    faq, query, query_tokens, language
                )
                
                if score > 0.1:  # Only include if somewhat relevant
                    results.append((faq, score))
            
            # Sort by score
            results.sort(key=lambda x: x[1], reverse=True)
            
            # Apply pagination
            paginated_results = results[offset:offset + limit]
            
            return paginated_results
            
        except Exception as e:
            logger.error(f"Error in semantic search: {str(e)}")
            return []
    
    @staticmethod
    def _calculate_semantic_relevance_score(
        faq: FAQ,
        query: str,
        query_tokens: List[str],
        language: str
    ) -> float:
        """
        Calculate semantic relevance score for FAQ
        
        Args:
            faq: FAQ object
            query: Search query
            query_tokens: Tokenized query
            language: Language code
            
        Returns:
            Relevance score (0-1)
        """
        score = 0
        
        try:
            # Combine text fields for analysis
            combined_text = f"{faq.question} {faq.short_answer} {faq.detailed_answer}"
            combined_text = combined_text.lower()
            
            # Exact match in question (highest weight)
            if query.lower() in faq.question.lower():
                score += 0.4
            
            # Exact match in short answer
            if query.lower() in faq.short_answer.lower():
                score += 0.2
            
            # Exact match in detailed answer
            if query.lower() in faq.detailed_answer.lower():
                score += 0.1
            
            # Token matching
            if language == 'zh':
                # Chinese token matching
                faq_tokens = list(jieba.cut(combined_text))
            else:
                # English token matching
                faq_tokens = word_tokenize(combined_text)
            
            # Calculate token overlap
            query_set = set(query_tokens)
            faq_set = set(faq_tokens)
            
            if query_set and faq_set:
                overlap = len(query_set.intersection(faq_set))
                jaccard_similarity = overlap / len(query_set.union(faq_set))
                score += jaccard_similarity * 0.3
            
            # Boost for FAQ tags
            if faq.tags and any(token in faq.tags for token in query_tokens):
                score += 0.1
            
            # Boost for helpful FAQs
            helpfulness_score = FAQService._calculate_helpfulness_score(faq) / 100
            score += helpfulness_score * 0.05
            
            # Boost for popular FAQs
            view_boost = min(faq.view_count / 1000, 0.05)
            score += view_boost
            
            # Normalize score to 0-1 range
            score = min(score, 1.0)
            
            return score
            
        except Exception as e:
            logger.error(f"Error calculating semantic relevance: {str(e)}")
            return 0
    
    @staticmethod
    def _calculate_text_relevance_score(faq: FAQ, query: str) -> float:
        """
        Calculate text-based relevance score
        
        Args:
            faq: FAQ object
            query: Search query
            
        Returns:
            Relevance score (0-100)
        """
        score = 0
        query = query.lower()
        
        try:
            # Check question (highest weight)
            if query in faq.question.lower():
                score += 50
            elif any(word in faq.question.lower() for word in query.split()):
                score += 30
            
            # Check short answer
            if query in faq.short_answer.lower():
                score += 20
            elif any(word in faq.short_answer.lower() for word in query.split()):
                score += 15
            
            # Check detailed answer
            if query in faq.detailed_answer.lower():
                score += 10
            
            # Check tags
            if faq.tags and any(query in tag.lower() for tag in faq.tags):
                score += 25
            
            # Boost for helpfulness
            helpfulness = FAQService._calculate_helpfulness_score(faq)
            score += helpfulness * 0.5
            
            # Boost for popularity
            if faq.view_count > 1000:
                score += 15
            elif faq.view_count > 100:
                score += 5
            
            return min(score, 100)
            
        except Exception as e:
            logger.error(f"Error calculating text relevance: {str(e)}")
            return 0
    
    @staticmethod
    def _extract_matched_terms(faq: FAQ, query: str) -> List[str]:
        """
        Extract which terms from query matched in FAQ
        
        Args:
            faq: FAQ object
            query: Search query
            
        Returns:
            List of matched terms
        """
        try:
            query_terms = set(query.lower().split())
            matched_terms = set()
            
            # Check in question
            question_lower = faq.question.lower()
            for term in query_terms:
                if term in question_lower:
                    matched_terms.add(term)
            
            # Check in short answer
            short_answer_lower = faq.short_answer.lower()
            for term in query_terms:
                if term in short_answer_lower:
                    matched_terms.add(term)
            
            # Check in tags
            if faq.tags:
                for term in query_terms:
                    if any(term in tag.lower() for tag in faq.tags):
                        matched_terms.add(term)
            
            return list(matched_terms)
            
        except Exception as e:
            logger.error(f"Error extracting matched terms: {str(e)}")
            return []
    
    @staticmethod
    def get_related_faqs(
        faq: FAQ,
        limit: int = 5
    ) -> List[FAQ]:
        """
        Get related FAQs
        
        Args:
            faq: FAQ object
            limit: Number of related FAQs to return
            
        Returns:
            List of related FAQs
        """
        try:
            related = FAQ.objects.filter(
                is_active=True
            ).exclude(id=faq.id)
            
            # Start with same category
            if faq.category:
                related = related.filter(category=faq.category)
            
            # Filter by shared tags
            if faq.tags:
                tag_query = Q()
                for tag in faq.tags:
                    tag_query |= Q(tags__contains=[tag])
                related = related.filter(tag_query)
            
            # Order by relevance
            related = related.annotate(
                relevance=Case(
                    When(category=faq.category, then=Value(2)),
                    default=Value(1),
                    output_field=models.IntegerField()
                )
            ).order_by('-relevance', '-priority', '-helpful_count')\
             .select_related('category')\
             [:limit]
            
            return list(related)
            
        except Exception as e:
            logger.error(f"Error getting related FAQs: {str(e)}")
            return []
    
    @staticmethod
    def get_categories_with_counts() -> List[Dict[str, Any]]:
        """
        Get all FAQ categories with FAQ counts
        
        Returns:
            List of categories with counts
        """
        cache_key = 'faq_categories_with_counts'
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        try:
            categories = FAQCategory.objects.filter(is_active=True)\
                .annotate(
                    faq_count=Count('faqs', filter=Q(faqs__is_active=True)),
                    total_views=Sum('faqs__view_count'),
                    average_helpfulness=Avg(
                        Case(
                            When(
                                faqs__helpful_count=0,
                                then=0.0
                            ),
                            default=(
                                F('faqs__helpful_count') * 100.0 /
                                (F('faqs__helpful_count') + F('faqs__not_helpful_count'))
                            ),
                            output_field=models.FloatField()
                        )
                    )
                )\
                .order_by('order', 'name')
            
            result = []
            for category in categories:
                result.append({
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug,
                    'icon': category.icon,
                    'order': category.order,
                    'faq_type': category.faq_type,
                    'faq_count': category.faq_count,
                    'total_views': category.total_views or 0,
                    'average_helpfulness': round(category.average_helpfulness or 0, 1)
                })
            
            cache.set(cache_key, result, 3600)  # Cache for 1 hour
            return result
            
        except Exception as e:
            logger.error(f"Error getting categories with counts: {str(e)}")
            return []
    
    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """
        Get overall FAQ statistics
        
        Returns:
            Dictionary with FAQ statistics
        """
        cache_key = 'faq_statistics'
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        try:
            # Overall counts
            total_faqs = FAQ.objects.count()
            active_faqs = FAQ.objects.filter(is_active=True).count()
            featured_faqs = FAQ.objects.filter(is_featured=True, is_active=True).count()
            
            # View statistics
            total_views = FAQ.objects.aggregate(total=Sum('view_count'))['total'] or 0
            average_views = FAQ.objects.filter(view_count__gt=0)\
                .aggregate(avg=Avg('view_count'))['avg'] or 0
            
            # Feedback statistics
            total_helpful = FAQ.objects.aggregate(total=Sum('helpful_count'))['total'] or 0
            total_not_helpful = FAQ.objects.aggregate(total=Sum('not_helpful_count'))['total'] or 0
            total_feedback = total_helpful + total_not_helpful
            
            # Category distribution
            category_dist = FAQCategory.objects.annotate(
                faq_count=Count('faqs', filter=Q(faqs__is_active=True))
            ).filter(faq_count__gt=0)\
             .values('name', 'faq_type', 'faq_count')\
             .order_by('-faq_count')
            
            # Most viewed FAQs
            most_viewed = FAQ.objects.filter(is_active=True)\
                .order_by('-view_count')\
                .select_related('category')\
                .values('id', 'question', 'view_count', 'category__name')[:5]
            
            # Most helpful FAQs
            most_helpful = FAQ.objects.filter(
                is_active=True,
                helpful_count__gt=0
            ).annotate(
                helpfulness_percentage=Case(
                    When(
                        helpful_count=0,
                        then=0.0
                    ),
                    default=(
                        F('helpful_count') * 100.0 /
                        (F('helpful_count') + F('not_helpful_count'))
                    ),
                    output_field=models.FloatField()
                )
            ).order_by('-helpfulness_percentage')\
             .select_related('category')\
             .values('id', 'question', 'helpfulness_percentage', 'category__name')[:5]
            
            # Recent feedback
            recent_feedback = FAQFeedback.objects\
                .select_related('faq', 'user')\
                .order_by('-created_at')\
                .values(
                    'faq__question',
                    'is_helpful',
                    'feedback_text',
                    'user__username',
                    'created_at'
                )[:10]
            
            stats = {
                'summary': {
                    'total_faqs': total_faqs,
                    'active_faqs': active_faqs,
                    'featured_faqs': featured_faqs,
                    'total_views': total_views,
                    'average_views': round(average_views, 2),
                    'total_feedback': total_feedback,
                    'helpful_feedback': total_helpful,
                    'not_helpful_feedback': total_not_helpful,
                    'overall_helpfulness': round(
                        (total_helpful / total_feedback * 100) if total_feedback > 0 else 0, 1
                    )
                },
                'category_distribution': list(category_dist),
                'most_viewed': list(most_viewed),
                'most_helpful': list(most_helpful),
                'recent_feedback': list(recent_feedback),
                'generated_at': timezone.now().isoformat()
            }
            
            cache.set(cache_key, stats, 300)  # Cache for 5 minutes
            return stats
            
        except Exception as e:
            logger.error(f"Error getting FAQ statistics: {str(e)}")
            return {}
    
    @staticmethod
    def get_user_faq_interactions(user: User) -> Dict[str, Any]:
        """
        Get user's FAQ interactions
        
        Args:
            user: User object
            
        Returns:
            Dictionary with user interactions
        """
        try:
            # Get viewed FAQs
            viewed_faqs = FAQ.objects.filter(
                view_logs__user=user
            ).annotate(
                last_viewed=Max('view_logs__created_at'),
                view_count_user=Count('view_logs')
            ).order_by('-last_viewed')[:20]
            
            # Get feedback provided
            feedback_given = FAQFeedback.objects.filter(user=user)\
                .select_related('faq')\
                .order_by('-created_at')[:10]
            
            # Get recently searched FAQs
            # This would require a search log model
            
            # Calculate statistics
            total_views = sum(faq.view_count_user for faq in viewed_faqs)
            helpful_feedback = feedback_given.filter(is_helpful=True).count()
            not_helpful_feedback = feedback_given.filter(is_helpful=False).count()
            
            return {
                'user_id': user.id,
                'statistics': {
                    'total_views': total_views,
                    'unique_faqs_viewed': len(viewed_faqs),
                    'feedback_given': len(feedback_given),
                    'helpful_feedback': helpful_feedback,
                    'not_helpful_feedback': not_helpful_feedback
                },
                'recently_viewed': [
                    {
                        'faq_id': faq.id,
                        'question': faq.question,
                        'last_viewed': faq.last_viewed,
                        'view_count': faq.view_count_user
                    }
                    for faq in viewed_faqs[:5]
                ],
                'recent_feedback': [
                    {
                        'faq_id': feedback.faq_id,
                        'question': feedback.faq.question,
                        'is_helpful': feedback.is_helpful,
                        'feedback_text': feedback.feedback_text,
                        'given_at': feedback.created_at
                    }
                    for feedback in feedback_given[:5]
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting user FAQ interactions: {str(e)}")
            return {}
    
    @staticmethod
    def suggest_faq_improvements(faq: FAQ) -> List[Dict[str, Any]]:
        """
        Suggest improvements for FAQ
        
        Args:
            faq: FAQ object
            
        Returns:
            List of improvement suggestions
        """
        suggestions = []
        
        try:
            # Check question length
            question_length = len(faq.question)
            if question_length < 10:
                suggestions.append({
                    'type': 'question_too_short',
                    'message': 'FAQ question is too short. Consider making it more descriptive.',
                    'severity': 'high',
                    'current_value': question_length,
                    'recommended_min': 10
                })
            elif question_length > 200:
                suggestions.append({
                    'type': 'question_too_long',
                    'message': 'FAQ question is too long. Consider making it more concise.',
                    'severity': 'medium',
                    'current_value': question_length,
                    'recommended_max': 200
                })
            
            # Check answer completeness
            answer_length = len(faq.detailed_answer)
            if answer_length < 50:
                suggestions.append({
                    'type': 'answer_too_short',
                    'message': 'FAQ answer is too brief. Consider providing more details.',
                    'severity': 'high',
                    'current_value': answer_length,
                    'recommended_min': 50
                })
            
            # Check for tags
            if not faq.tags or len(faq.tags) < 2:
                suggestions.append({
                    'type': 'insufficient_tags',
                    'message': 'FAQ has few or no tags. Add relevant tags to improve discoverability.',
                    'severity': 'medium',
                    'current_tags': faq.tags or [],
                    'recommended_min': 3
                })
            
            # Check helpfulness score
            helpfulness = FAQService._calculate_helpfulness_score(faq)
            if helpfulness < 60 and faq.helpful_count + faq.not_helpful_count > 10:
                suggestions.append({
                    'type': 'low_helpfulness',
                    'message': f'FAQ has low helpfulness score ({helpfulness}%). Consider improving the content.',
                    'severity': 'medium',
                    'current_score': helpfulness,
                    'recommended_min': 60
                })
            
            # Check view count
            if faq.view_count > 1000 and helpfulness < 50:
                suggestions.append({
                    'type': 'high_views_low_helpfulness',
                    'message': 'FAQ is frequently viewed but has low helpfulness. Consider revising the content.',
                    'severity': 'high',
                    'views': faq.view_count,
                    'helpfulness': helpfulness
                })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error suggesting FAQ improvements: {str(e)}")
            return []
    
    @staticmethod
    def generate_faq_report(
        faq_ids: Optional[List[int]] = None,
        category_ids: Optional[List[int]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate FAQ report
        
        Args:
            faq_ids: List of FAQ IDs to include
            category_ids: List of category IDs to include
            start_date: Report start date
            end_date: Report end date
            
        Returns:
            Dictionary with report data
        """
        try:
            if not start_date:
                start_date = timezone.now() - timedelta(days=30)
            if not end_date:
                end_date = timezone.now()
            
            # Build query
            query = Q()
            
            if faq_ids:
                query &= Q(id__in=faq_ids)
            
            if category_ids:
                query &= Q(category_id__in=category_ids)
            
            # Get FAQs
            faqs = FAQ.objects.filter(query)\
                .select_related('category')\
                .prefetch_related('related_pages')
            
            report_data = {
                'report_type': 'faq_performance',
                'period': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'faqs_count': faqs.count(),
                'generated_at': timezone.now(),
                'data': []
            }
            
            for faq in faqs:
                # Get feedback in period
                feedback = FAQFeedback.objects.filter(
                    faq=faq,
                    created_at__range=(start_date, end_date)
                )
                
                helpful_feedback = feedback.filter(is_helpful=True).count()
                not_helpful_feedback = feedback.filter(is_helpful=False).count()
                total_feedback = helpful_feedback + not_helpful_feedback
                
                faq_data = {
                    'faq_id': faq.id,
                    'question': faq.question,
                    'category': faq.category.name if faq.category else None,
                    'status': 'active' if faq.is_active else 'inactive',
                    'is_featured': faq.is_featured,
                    'total_views': faq.view_count,
                    'total_feedback': faq.helpful_count + faq.not_helpful_count,
                    'helpfulness_score': FAQService._calculate_helpfulness_score(faq),
                    'period_stats': {
                        'views': FAQService._get_faq_views_in_period(faq, start_date, end_date),
                        'feedback': total_feedback,
                        'helpful_feedback': helpful_feedback,
                        'not_helpful_feedback': not_helpful_feedback
                    }
                }
                
                report_data['data'].append(faq_data)
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating FAQ report: {str(e)}")
            return {}
    
    @staticmethod
    def _get_faq_views_in_period(
        faq: FAQ,
        start_date: datetime,
        end_date: datetime
    ) -> int:
        """
        Get FAQ views in specific period
        
        Args:
            faq: FAQ object
            start_date: Start date
            end_date: End date
            
        Returns:
            Number of views in period
        """
        # This would require a view log model for FAQs
        # For now, return 0 or approximate based on total views
        return 0
    
    @staticmethod
    def auto_suggest_tags(faq: FAQ) -> List[str]:
        """
        Automatically suggest tags for FAQ
        
        Args:
            faq: FAQ object
            
        Returns:
            List of suggested tags
        """
        try:
            # Combine text for analysis
            text = f"{faq.question} {faq.short_answer} {faq.detailed_answer}"
            text = text.lower()
            
            # Extract words (simple approach)
            words = re.findall(r'\b[a-z]{3,}\b', text)
            
            # Remove stopwords
            stop_words = set(stopwords.words('english'))
            filtered_words = [word for word in words if word not in stop_words]
            
            # Count word frequency
            word_freq = defaultdict(int)
            for word in filtered_words:
                word_freq[word] += 1
            
            # Get most frequent words
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            
            # Extract top words as tags
            tags = [word for word, freq in sorted_words[:10] if freq > 1]
            
            return tags[:5]  # Return top 5 tags
            
        except Exception as e:
            logger.error(f"Error auto-suggesting tags: {str(e)}")
            return []
    
    @staticmethod
    def cleanup_inactive_faqs(days_inactive: int = 365) -> Tuple[int, int]:
        """
        Archive or delete inactive FAQs
        
        Args:
            days_inactive: Days of inactivity threshold
            
        Returns:
            Tuple of (archived_count, deleted_count)
        """
        try:
            cutoff_date = timezone.now() - timedelta(days=days_inactive)
            
            # Find FAQs with no views or feedback in the period
            inactive_faqs = FAQ.objects.filter(
                is_active=True,
                view_count=0,
                helpful_count=0,
                not_helpful_count=0,
                created_at__lt=cutoff_date
            )
            
            archived_count = 0
            deleted_count = 0
            
            for faq in inactive_faqs:
                # Archive instead of delete to preserve data
                faq.is_active = False
                faq.status = 'archived'
                faq.save()
                archived_count += 1
            
            logger.info(f"Archived {archived_count} inactive FAQs")
            return archived_count, deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up inactive FAQs: {str(e)}")
            return 0, 0