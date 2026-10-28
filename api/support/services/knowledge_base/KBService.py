# api/support/services/knowledge_base/KBService.py  — WORLD #1
import logging
from django.utils import timezone
from django.utils.text import slugify
logger = logging.getLogger(__name__)

class KBService:
    def create_article(self, data: dict, author) -> object:
        from api.support.models import KBArticle
        title = data.get('title','')
        slug  = data.get('slug') or slugify(title)
        if KBArticle.objects.filter(slug=slug).exists():
            import uuid as _uuid
            slug = f"{slug}-{str(_uuid.uuid4())[:6]}"
        return KBArticle.objects.create(
            title   = title,
            slug    = slug,
            body    = data.get('body',''),
            summary = data.get('summary',''),
            category_id = data.get('category_id'),
            author  = author,
            status  = data.get('status','draft'),
            is_public = data.get('is_public', True),
            tags    = data.get('tags', []),
            tenant  = getattr(author, 'tenant', None),
        )

    def publish(self, article_id: int) -> object:
        from api.support.models import KBArticle
        article = KBArticle.objects.get(id=article_id)
        article.status = 'published'
        article.save(update_fields=['status'])
        return article

    def unpublish(self, article_id: int) -> object:
        from api.support.models import KBArticle
        article = KBArticle.objects.get(id=article_id)
        article.status = 'draft'
        article.save(update_fields=['status'])
        return article

    def increment_view(self, article_id: int) -> None:
        from api.support.models import KBArticle
        KBArticle.objects.filter(id=article_id).update(views_count=KBArticle.objects.get(id=article_id).views_count + 1)

kb_service = KBService()