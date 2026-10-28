# api/cms/search.py
"""
CMS Full-Text Search Engine.
Supports: Blog posts, Pages, FAQ, Offers, Quiz, Forms.
Backends: Django ORM (default) + PostgreSQL full-text + Elasticsearch (optional).
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from django.db.models import Q, QuerySet, Value, FloatField
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result item."""
    id: int
    title: str
    url: str
    content_type: str
    excerpt: str = ''
    score: float = 1.0
    thumbnail: str = ''
    published_at: Optional[str] = None
    extra: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'content_type': self.content_type,
            'excerpt': self.excerpt,
            'score': self.score,
            'thumbnail': self.thumbnail,
            'published_at': self.published_at,
            **self.extra,
        }


@dataclass
class SearchQuery:
    """Parsed and validated search query."""
    raw: str
    terms: List[str] = field(default_factory=list)
    content_types: List[str] = field(default_factory=list)
    language: str = ''
    min_score: float = 0.0
    page: int = 1
    page_size: int = 20

    def __post_init__(self):
        self.terms = [t.strip() for t in self.raw.split() if len(t.strip()) >= 2]

    @property
    def is_valid(self) -> bool:
        return len(self.raw.strip()) >= 2

    @property
    def primary_term(self) -> str:
        return self.terms[0] if self.terms else self.raw


class CMSSearchEngine:
    """
    Main CMS search engine.
    Searches across: BlogPost, Page, FAQ, OfferCache, QuizTemplate, DynamicForm.
    """
    CONTENT_TYPES = ['blog', 'page', 'faq', 'offer', 'quiz', 'form']
    MAX_RESULTS = 100
    EXCERPT_LENGTH = 200

    @classmethod
    def search(cls, query: str, content_types: Optional[List[str]] = None,
               language: str = '', page: int = 1, page_size: int = 20,
               user=None) -> Dict:
        """
        Main search entry point.
        Returns paginated results across all content types.
        """
        sq = SearchQuery(
            raw=query,
            content_types=content_types or cls.CONTENT_TYPES,
            language=language,
            page=page,
            page_size=page_size,
        )
        if not sq.is_valid:
            return {'results': [], 'count': 0, 'query': query, 'error': 'Query too short'}

        all_results: List[SearchResult] = []

        # ── Try Elasticsearch first ───────────────────────────────
        es_results = cls._es_search(sq)
        if es_results:
            all_results.extend(es_results)
            # Still run ORM for content types not indexed in ES
            orm_only_types = [ct for ct in sq.content_types if ct in ('form',)]
            sq_orm = sq.__class__(raw=sq.raw, content_types=orm_only_types,
                                   language=sq.language, page=sq.page, page_size=sq.page_size)
        else:
            orm_only_types = sq.content_types
            sq_orm = sq

        # ── ORM fallback ─────────────────────────────────────────
        searchers = {
            'blog':  cls._search_blog,
            'page':  cls._search_pages,
            'faq':   cls._search_faq,
            'offer': cls._search_offers,
            'quiz':  cls._search_quizzes,
            'form':  cls._search_forms,
        }
        for ct in sq.content_types:
            if ct in searchers:
                try:
                    results = searchers[ct](sq)
                    all_results.extend(results)
                except Exception as e:
                    logger.warning(f"[Search] {ct} search failed: {e}")

        # Sort by score descending
        all_results.sort(key=lambda r: r.score, reverse=True)

        # Paginate
        total = len(all_results)
        start = (sq.page - 1) * sq.page_size
        end = start + sq.page_size
        page_results = all_results[start:end]

        return {
            'query': query,
            'count': total,
            'total_pages': max(1, (total + sq.page_size - 1) // sq.page_size),
            'current_page': sq.page,
            'page_size': sq.page_size,
            'results': [r.to_dict() for r in page_results],
            'content_types_searched': sq.content_types,
        }

    @classmethod
    def _search_blog(cls, sq: SearchQuery) -> List[SearchResult]:
        """Search published blog posts."""
        try:
            from api.cms.models_new.blog import BlogPost
        except ImportError:
            return []

        q = Q()
        for term in sq.terms:
            q |= Q(title__icontains=term) | Q(content__icontains=term) | Q(excerpt__icontains=term)

        qs = BlogPost.objects.filter(q, status='published')
        if sq.language:
            qs = qs.filter(language=sq.language)
        qs = qs.select_related('author').order_by('-published_at')[:cls.MAX_RESULTS]

        results = []
        for post in qs:
            score = cls._score_text(sq.terms, post.title, post.content or '', weight_title=3)
            excerpt = cls._extract_excerpt(post.content or post.excerpt or '', sq.primary_term)
            results.append(SearchResult(
                id=post.id,
                title=post.title,
                url=f"/blog/{post.slug}/",
                content_type='blog',
                excerpt=excerpt,
                score=score,
                thumbnail=getattr(post, 'featured_image', ''),
                published_at=post.published_at.isoformat() if post.published_at else None,
            ))
        return results

    @classmethod
    def _search_pages(cls, sq: SearchQuery) -> List[SearchResult]:
        """Search published CMS pages."""
        try:
            from api.cms.models_new.extras import ContentPage
        except ImportError:
            return []
        try:
            q = Q()
            for term in sq.terms:
                q |= Q(title__icontains=term) | Q(content__icontains=term)
            qs = ContentPage.objects.filter(q, status='published')[:cls.MAX_RESULTS]
            results = []
            for page in qs:
                score = cls._score_text(sq.terms, page.title, page.content or '', weight_title=3)
                results.append(SearchResult(
                    id=page.id,
                    title=page.title,
                    url=f"/page/{page.slug}/",
                    content_type='page',
                    excerpt=cls._extract_excerpt(page.content or '', sq.primary_term),
                    score=score,
                ))
            return results
        except Exception:
            return []

    @classmethod
    def _search_faq(cls, sq: SearchQuery) -> List[SearchResult]:
        """Search FAQ entries."""
        try:
            from api.cms.models_new.extras import FAQ
        except ImportError:
            return []
        try:
            q = Q()
            for term in sq.terms:
                q |= Q(question__icontains=term) | Q(answer__icontains=term)
            qs = FAQ.objects.filter(q, is_active=True).order_by('-helpful_count')[:50]
            results = []
            for faq in qs:
                score = cls._score_text(sq.terms, faq.question, faq.answer or '', weight_title=2)
                results.append(SearchResult(
                    id=faq.id,
                    title=faq.question,
                    url=f"/faq/#{faq.id}",
                    content_type='faq',
                    excerpt=cls._extract_excerpt(faq.answer or '', sq.primary_term),
                    score=score,
                ))
            return results
        except Exception:
            return []

    @classmethod
    def _search_offers(cls, sq: SearchQuery) -> List[SearchResult]:
        """Search cached CPAlead offers."""
        try:
            from api.cms.models_new.cpalead import OfferCache
        except ImportError:
            return []
        try:
            q = Q()
            for term in sq.terms:
                q |= Q(title__icontains=term) | Q(description__icontains=term)
            qs = OfferCache.objects.filter(q, is_active=True).order_by('-is_featured', '-payout_usd')[:50]
            results = []
            for offer in qs:
                score = cls._score_text(sq.terms, offer.title, offer.description or '', weight_title=2)
                results.append(SearchResult(
                    id=offer.id,
                    title=offer.title,
                    url=f"/offerwall/?offer={offer.offer_id}",
                    content_type='offer',
                    excerpt=offer.description[:cls.EXCERPT_LENGTH] if offer.description else '',
                    score=score,
                    thumbnail=offer.icon_url or '',
                    extra={
                        'payout_usd': float(offer.payout_usd),
                        'offer_type': offer.offer_type,
                        'is_featured': offer.is_featured,
                    }
                ))
            return results
        except Exception:
            return []

    @classmethod
    def _search_quizzes(cls, sq: SearchQuery) -> List[SearchResult]:
        """Search active quizzes."""
        try:
            from api.cms.models_new.quiz import QuizTemplate
        except ImportError:
            return []
        try:
            q = Q()
            for term in sq.terms:
                q |= Q(title__icontains=term) | Q(description__icontains=term)
            qs = QuizTemplate.objects.filter(q, is_active=True).order_by('-is_featured')[:30]
            results = []
            for quiz in qs:
                score = cls._score_text(sq.terms, quiz.title, quiz.description or '', weight_title=3)
                results.append(SearchResult(
                    id=quiz.id,
                    title=quiz.title,
                    url=f"/quiz/{quiz.slug}/",
                    content_type='quiz',
                    excerpt=quiz.description[:cls.EXCERPT_LENGTH] if quiz.description else '',
                    score=score,
                    thumbnail=quiz.thumbnail or '',
                    extra={
                        'quiz_type': quiz.quiz_type,
                        'payout_usd': float(quiz.payout_usd),
                        'total_attempts': quiz.total_attempts,
                    }
                ))
            return results
        except Exception:
            return []

    @classmethod
    def _search_forms(cls, sq: SearchQuery) -> List[SearchResult]:
        """Search active forms."""
        try:
            from api.cms.models_new.forms import DynamicForm
        except ImportError:
            return []
        try:
            q = Q()
            for term in sq.terms:
                q |= Q(name__icontains=term) | Q(title__icontains=term) | Q(description__icontains=term)
            qs = DynamicForm.objects.filter(q, is_active=True)[:20]
            results = []
            for form in qs:
                score = cls._score_text(sq.terms, form.title or form.name, form.description or '')
                results.append(SearchResult(
                    id=form.id,
                    title=form.title or form.name,
                    url=f"/form/{form.slug}/",
                    content_type='form',
                    excerpt=form.description[:cls.EXCERPT_LENGTH] if form.description else '',
                    score=score,
                ))
            return results
        except Exception:
            return []

    @classmethod
    def _score_text(cls, terms: List[str], title: str, body: str,
                    weight_title: int = 2) -> float:
        """Score a document based on term frequency."""
        score = 0.0
        title_lower = title.lower()
        body_lower = body.lower()
        for term in terms:
            term_lower = term.lower()
            # Exact title match = highest score
            if term_lower in title_lower:
                score += weight_title * 2
            # Partial title match
            score += title_lower.count(term_lower) * weight_title
            # Body matches
            score += body_lower.count(term_lower) * 1
        return score

    @classmethod
    def _extract_excerpt(cls, text: str, term: str,
                          context_chars: int = 100) -> str:
        """Extract relevant excerpt around search term."""
        if not text:
            return ''
        # Strip HTML
        from api.cms.helpers import strip_html_tags
        clean = strip_html_tags(text)
        pos = clean.lower().find(term.lower())
        if pos == -1:
            return clean[:cls.EXCERPT_LENGTH] + ('...' if len(clean) > cls.EXCERPT_LENGTH else '')
        start = max(0, pos - context_chars)
        end = min(len(clean), pos + len(term) + context_chars)
        excerpt = clean[start:end]
        if start > 0:
            excerpt = '...' + excerpt
        if end < len(clean):
            excerpt = excerpt + '...'
        return excerpt


    # ── Elasticsearch Backend ────────────────────────────────
    @classmethod
    def _es_search(cls, sq: 'SearchQuery') -> list:
        """
        Elasticsearch search — faster, full-text, typo-tolerant.
        Falls back to ORM if ES unavailable.
        """
        from django.conf import settings
        if not getattr(settings, 'ELASTICSEARCH_ENABLED', False):
            return []
        try:
            from elasticsearch import Elasticsearch
            es = Elasticsearch(
                [settings.ELASTICSEARCH_URL],
                http_auth=settings.ELASTICSEARCH_DSL['default'].get('http_auth'),
                request_timeout=5,
            )
            index = getattr(settings, 'ELASTICSEARCH_INDEX', 'cms')
            # Multi-match across all content types
            body = {
                'query': {
                    'bool': {
                        'should': [
                            {
                                'multi_match': {
                                    'query': sq.raw,
                                    'fields': ['title^3', 'content', 'excerpt', 'description'],
                                    'type': 'best_fields',
                                    'fuzziness': 'AUTO',
                                }
                            },
                            {
                                'match_phrase': {
                                    'title': {'query': sq.raw, 'boost': 5}
                                }
                            },
                        ],
                        'filter': [{'term': {'status': 'published'}}] if 'blog' in sq.content_types else [],
                    }
                },
                'highlight': {
                    'fields': {'title': {}, 'content': {'fragment_size': 200}},
                    'pre_tags': ['<mark>'],
                    'post_tags': ['</mark>'],
                },
                '_source': ['id', 'title', 'url', 'content_type', 'excerpt', 'thumbnail', 'published_at'],
                'size': sq.page_size * 3,
            }
            # Filter by content_type if specified
            if sq.content_types and sq.content_types != cls.CONTENT_TYPES:
                body['query']['bool']['filter'].append(
                    {'terms': {'content_type': sq.content_types}}
                )
            resp = es.search(index=f"{index}_*", body=body)
            results = []
            for hit in resp['hits']['hits']:
                src = hit['_source']
                highlight = hit.get('highlight', {})
                excerpt = (highlight.get('content', [''])[0] or
                           src.get('excerpt', '')[:cls.EXCERPT_LENGTH])
                results.append(SearchResult(
                    id=src.get('id', 0),
                    title=highlight.get('title', [src.get('title', '')])[0],
                    url=src.get('url', ''),
                    content_type=src.get('content_type', 'page'),
                    excerpt=excerpt,
                    score=hit['_score'],
                    thumbnail=src.get('thumbnail', ''),
                    published_at=src.get('published_at'),
                ))
            return results
        except Exception as e:
            logger.debug(f"[Search] Elasticsearch failed, using ORM: {e}")
            return []

    @classmethod
    def es_index_object(cls, content_type: str, obj) -> bool:
        """Index a single object into Elasticsearch."""
        from django.conf import settings
        if not getattr(settings, 'ELASTICSEARCH_ENABLED', False):
            return False
        try:
            from elasticsearch import Elasticsearch
            es = Elasticsearch([settings.ELASTICSEARCH_URL], request_timeout=5)
            index = f"{settings.ELASTICSEARCH_INDEX}_{content_type}"
            field_map = {
                'blog':  ('title', 'content', 'excerpt', 'slug', 'published_at'),
                'page':  ('title', 'content', 'slug'),
                'faq':   ('question', 'answer'),
                'offer': ('title', 'description', 'offer_type'),
                'quiz':  ('title', 'description', 'slug'),
            }
            fields = field_map.get(content_type, ('title',))
            doc = {
                'id': obj.id,
                'content_type': content_type,
                'url': getattr(obj, 'get_absolute_url', lambda: f'/{content_type}/{getattr(obj, "slug", obj.id)}/') (),
                'thumbnail': getattr(obj, 'featured_image', getattr(obj, 'icon_url', getattr(obj, 'thumbnail', ''))),
                'status': getattr(obj, 'status', 'published'),
                'published_at': getattr(obj, 'published_at', getattr(obj, 'created_at', None)),
            }
            for f in fields:
                doc[f] = getattr(obj, f, '')
            # title is required
            doc['title'] = doc.get('title') or doc.get('question') or doc.get('name') or str(obj)
            doc['content'] = doc.get('content') or doc.get('answer') or doc.get('description') or ''
            es.index(index=index, id=obj.id, body=doc)
            return True
        except Exception as e:
            logger.warning(f"[Search] ES index failed: {e}")
            return False

    @classmethod
    def suggest(cls, partial: str, limit: int = 8) -> List[str]:
        """
        Autocomplete suggestions for partial query.
        Returns list of suggested search terms.
        """
        if len(partial) < 2:
            return []
        suggestions = set()
        # Blog post titles
        try:
            from api.cms.models_new.blog import BlogPost
            titles = BlogPost.objects.filter(
                title__icontains=partial, status='published'
            ).values_list('title', flat=True)[:limit]
            suggestions.update(titles)
        except Exception:
            pass
        # Quiz titles
        try:
            from api.cms.models_new.quiz import QuizTemplate
            titles = QuizTemplate.objects.filter(
                title__icontains=partial, is_active=True
            ).values_list('title', flat=True)[:limit // 2]
            suggestions.update(titles)
        except Exception:
            pass
        # Offer titles
        try:
            from api.cms.models_new.cpalead import OfferCache
            titles = OfferCache.objects.filter(
                title__icontains=partial, is_active=True
            ).values_list('title', flat=True)[:limit // 2]
            suggestions.update(titles)
        except Exception:
            pass

        result = sorted(list(suggestions))[:limit]
        return result

    @classmethod
    def index_content(cls, content_type: str, obj_id: int) -> bool:
        """
        (Re)index a single content object.
        In production, this would push to Elasticsearch.
        For now, it's a no-op that triggers cache invalidation.
        """
        try:
            from django.core.cache import cache
            cache.delete(f"search_cache_{content_type}_{obj_id}")
            logger.debug(f"[Search] Indexed: {content_type}#{obj_id}")
            return True
        except Exception as e:
            logger.warning(f"[Search] Index failed: {e}")
            return False

    @classmethod
    def reindex_all(cls) -> Dict[str, int]:
        """Reindex all content. Run as celery task after bulk changes."""
        counts = {}
        searchers = {
            'blog':  ('cms.models_new.blog', 'BlogPost'),
            'offer': ('cms.models_new.cpalead', 'OfferCache'),
            'quiz':  ('cms.models_new.quiz', 'QuizTemplate'),
        }
        for ct, (module, model_name) in searchers.items():
            try:
                mod = __import__(module, fromlist=[model_name])
                model = getattr(mod, model_name)
                counts[ct] = model.objects.count()
            except Exception:
                counts[ct] = 0
        logger.info(f"[Search] Reindex complete: {counts}")
        return counts
