# api/cms/services/SurveyService.py
"""Legacy SurveyService — delegates to the modern services_new layer."""
from api.cms.models_new.profile_surveys import SurveyTemplate, SurveyCompletion


class SurveyService:
    """Thin wrapper around SurveyTemplate / SurveyCompletion for legacy callers."""

    @staticmethod
    def get_active_surveys(user=None, limit=20):
        qs = SurveyTemplate.objects.filter(status='active').order_by('-created_at')[:limit]
        return list(qs)

    @staticmethod
    def get_completions(user, limit=50):
        return SurveyCompletion.objects.filter(user=user).order_by('-started_at')[:limit]

    @staticmethod
    def get_available_surveys(user=None, limit=None):
        """Return all surveys from both legacy Survey and SurveyTemplate models."""
        results = list(SurveyTemplate.objects.filter(status='active').order_by('-created_at'))
        try:
            from api.cms.models_new.survey import Survey as _LegacySurvey
            if _LegacySurvey:
                legacy = list(_LegacySurvey.objects.filter(is_active=True).order_by('-id'))
                # De-duplicate by pk if same model
                existing_pks = {getattr(r, 'pk', None) for r in results}
                results += [s for s in legacy if getattr(s, 'pk', None) not in existing_pks]
        except Exception:
            pass
        return results[:limit] if limit else results

    @staticmethod
    def search(query: str, limit: int = 20):
        """Full-text survey search."""
        return SurveyTemplate.objects.filter(
            status='active', title__icontains=query
        ).order_by('-created_at')[:limit]

    @staticmethod
    def complete_survey(user, survey_id, responses=None, quality_score=None):
        """Mark a survey as completed and trigger reward processing."""
        from api.cms.models_new.profile_surveys import SurveyTemplate, SurveyCompletion
        from decimal import Decimal
        try:
            survey = SurveyTemplate.objects.get(pk=survey_id)
            completion, created = SurveyCompletion.objects.get_or_create(
                user=user, survey=survey,
                defaults={'status': 'completed', 'quality_score': Decimal(str(quality_score or 0))}
            )
            if not created:
                completion.status = 'completed'
                if quality_score is not None:
                    completion.quality_score = Decimal(str(quality_score))
                completion.save(update_fields=['status', 'quality_score'])
            return completion
        except SurveyTemplate.DoesNotExist:
            return None
