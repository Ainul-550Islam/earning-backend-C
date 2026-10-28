# api/cms/services/ContentSearchService.py
"""
ContentSearchService: Full-text search across pages, blogs, FAQs, and banners.
"""
import logging
from typing import List, Dict, Optional, Tuple, Any

from django.db.models import Q, F, Value, FloatField
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ContentSearchService:
    """Full-text search service across all CMS content types."""

    SEARCHABLE_TYPES = ['page', 'blog', 'faq', 'banner', 'category']

    @staticmethod
    def search(
        query: str,
        content_types: Optional[List[str]] = None,
        language: str = 'en',
        limit: int = 20,
        offset: int = 0,
        user=None
    ) -> Dict[str, Any]:
        """
        Full-text search across CMS content.

        Args:
            query: Search query string
            content_types: List of types to search (page, blog, faq, banner, category)
            language: Language filter
            limit: Max results per type
            offset: Pagination offset
            user: Requesting user

        Returns:
            Dict with 'results', 'total', 'by_type' breakdown
        """
        if not query or len(query.strip()) < 2:
            return {'results': [], 'total': 0, 'by_type': {}, 'query': query}

        clean_query = query.strip()
        types_to_search = content_types or ContentSearchService.SEARCHABLE_TYPES

        all_results = []
        by_type = {}

        if 'page' in types_to_search:
            page_results = ContentSearchService._search_pages(clean_query, language, limit, user)
            all_results.extend(page_results)
            by_type['page'] = len(page_results)

        if 'blog' in types_to_search:
            blog_results = ContentSearchService._search_blogs(clean_query, language, limit, user)
            all_results.extend(blog_results)
            by_type['blog'] = len(blog_results)

        if 'faq' in types_to_search:
            faq_results = ContentSearchService._search_faqs(clean_query, limit)
            all_results.extend(faq_results)
            by_type['faq'] = len(faq_results)

        if 'category' in types_to_search:
            cat_results = ContentSearchService._search_categories(clean_query, limit)
            all_results.extend(cat_results)
            by_type['category'] = len(cat_results)

        # Sort by relevance
        all_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

        total = len(all_results)
        paginated = all_results[offset:offset + limit]

        return {
            'query': clean_query,
            'results': paginated,
            'total': total,
            'by_type': by_type,
        }

    @staticmethod
    def _search_pages(query: str, language: str, limit: int, user=None) -> List[Dict]:
        """Search CMS content pages."""
        from api.cms.models import ContentPage
        results = []
        try:
            q = Q(status='published', is_active=True, language=language) & (
                Q(title__icontains=query) |
                Q(excerpt__icontains=query) |
                Q(content__icontains=query) |
                Q(meta_keywords__icontains=query)
            )
            if not (user and user.is_staff):
                if user and user.is_authenticated:
                    q &= Q(visibility__in=['public', 'authenticated'])
                else:
                    q &= Q(visibility='public')

            pages = ContentPage.objects.filter(q).select_related('category')[:limit]
            for page in pages:
                score = ContentSearchService._score(page.title, page.excerpt or '', query)
                results.append({
                    'id': page.id,
                    'type': 'page',
                    'title': page.title,
                    'excerpt': page.excerpt[:200] if page.excerpt else '',
                    'url': page.get_absolute_url(),
                    'published_date': page.published_date,
                    'category': page.category.name if page.category else None,
                    'relevance_score': score,
                })
        except Exception as e:
            logger.error(f"Error searching pages: {e}")
        return results

    @staticmethod
    def _search_blogs(query: str, language: str, limit: int, user=None) -> List[Dict]:
        """Search blog posts."""
        results = []
        try:
            from api.cms.models_new.blog import BlogPost
            q = Q(status='published', is_active=True, language=language) & (
                Q(title__icontains=query) |
                Q(excerpt__icontains=query) |
                Q(body__icontains=query)
            )
            posts = BlogPost.objects.filter(q).select_related('category', 'author')[:limit]
            for post in posts:
                score = ContentSearchService._score(post.title, post.excerpt or '', query)
                results.append({
                    'id': post.id,
                    'type': 'blog',
                    'title': post.title,
                    'excerpt': post.excerpt[:200] if post.excerpt else '',
                    'url': post.get_absolute_url(),
                    'published_date': post.published_at,
                    'author': post.author.username if post.author else None,
                    'category': post.category.name if post.category else None,
                    'relevance_score': score,
                })
        except Exception as e:
            logger.error(f"Error searching blogs: {e}")
        return results

    @staticmethod
    def _search_faqs(query: str, limit: int) -> List[Dict]:
        """Search FAQs."""
        from api.cms.models import FAQ
        results = []
        try:
            q = Q(is_active=True) & (
                Q(question__icontains=query) |
                Q(short_answer__icontains=query) |
                Q(detailed_answer__icontains=query)
            )
            faqs = FAQ.objects.filter(q).select_related('category')[:limit]
            for faq in faqs:
                score = ContentSearchService._score(faq.question, faq.short_answer or '', query)
                results.append({
                    'id': faq.id,
                    'type': 'faq',
                    'title': faq.question,
                    'excerpt': faq.short_answer[:200] if faq.short_answer else '',
                    'url': faq.get_absolute_url(),
                    'category': faq.category.name if faq.category else None,
                    'relevance_score': score,
                })
        except Exception as e:
            logger.error(f"Error searching FAQs: {e}")
        return results

    @staticmethod
    def _search_categories(query: str, limit: int) -> List[Dict]:
        """Search content categories."""
        from api.cms.models import ContentCategory
        results = []
        try:
            cats = ContentCategory.objects.filter(
                is_active=True,
                name__icontains=query
            )[:limit]
            for cat in cats:
                results.append({
                    'id': cat.id,
                    'type': 'category',
                    'title': cat.name,
                    'excerpt': cat.description[:200] if cat.description else '',
                    'url': cat.get_absolute_url(),
                    'relevance_score': ContentSearchService._score(cat.name, cat.description or '', query),
                })
        except Exception as e:
            logger.error(f"Error searching categories: {e}")
        return results

    @staticmethod
    def _score(title: str, excerpt: str, query: str) -> float:
        """Simple relevance scoring."""
        score = 0.0
        q = query.lower()
        if q in title.lower():
            score += 50.0
        elif any(word in title.lower() for word in q.split()):
            score += 25.0
        if q in excerpt.lower():
            score += 15.0
        return score

    @staticmethod
    def suggest(query: str, limit: int = 5) -> List[str]:
        """Get search suggestions."""
        if not query or len(query) < 2:
            return []
        from api.cms.models import ContentPage, FAQ
        suggestions = set()
        try:
            titles = ContentPage.objects.filter(
                title__icontains=query, status='published', is_active=True
            ).values_list('title', flat=True)[:limit]
            suggestions.update(titles)
            faq_questions = FAQ.objects.filter(
                question__icontains=query, is_active=True
            ).values_list('question', flat=True)[:limit]
            suggestions.update(faq_questions)
        except Exception as e:
            logger.warning(f"Error generating suggestions: {e}")
        return list(suggestions)[:limit]
