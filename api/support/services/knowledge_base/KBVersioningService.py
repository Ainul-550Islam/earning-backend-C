# api/support/services/knowledge_base/KBVersioningService.py  — WORLD #1
import logging
logger = logging.getLogger(__name__)

class KBVersioningService:
    def save_version(self, article, changed_by=None, summary: str = '') -> object:
        from api.support.models import KBArticleVersion
        last = KBArticleVersion.objects.filter(article=article).order_by('-version_number').first()
        version_number = (last.version_number + 1) if last else 1
        return KBArticleVersion.objects.create(
            article=article, version_number=version_number,
            body_snapshot=article.body, changed_by=changed_by, diff_summary=summary,
        )

    def get_history(self, article_id: int) -> list:
        from api.support.models import KBArticleVersion
        versions = KBArticleVersion.objects.filter(article_id=article_id).order_by('-version_number')
        return [{'version': v.version_number, 'changed_by': v.changed_by.username if v.changed_by else '', 'diff': v.diff_summary, 'at': v.changed_at} for v in versions]

    def restore(self, article_id: int, version_number: int, by=None) -> object:
        from api.support.models import KBArticle, KBArticleVersion
        version = KBArticleVersion.objects.get(article_id=article_id, version_number=version_number)
        article = version.article
        self.save_version(article, changed_by=by, summary=f'Restored to v{version_number}')
        article.body = version.body_snapshot
        article.save(update_fields=['body'])
        return article

kb_versioning_service = KBVersioningService()