# api/cms/services_new/QuizService.py
"""Quiz Builder Service — CMS owns this. CPAlead personality quizzes."""
import logging
from typing import Dict, Any, List, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class QuizService:

    @staticmethod
    def get_quiz(slug: str) -> Optional[Any]:
        from api.cms.models_new.quiz import QuizTemplate
        try:
            return QuizTemplate.objects.get(slug=slug, is_active=True)
        except QuizTemplate.DoesNotExist:
            return None

    @staticmethod
    def start_attempt(quiz_id: int, user=None, session_key: str = '',
                       ip: str = '') -> Dict:
        from api.cms.models_new.quiz import QuizTemplate, QuizAttempt
        try:
            quiz = QuizTemplate.objects.prefetch_related(
                'questions__answers'
            ).get(id=quiz_id, is_active=True)
        except QuizTemplate.DoesNotExist:
            return {'error': 'Quiz not found'}

        attempt = QuizAttempt.objects.create(
            quiz=quiz, user=user, session_key=session_key, ip_address=ip or None
        )
        QuizTemplate.objects.filter(pk=quiz_id).update(
            total_attempts=__import__('django.db.models', fromlist=['F']).F('total_attempts') + 1
        )
        questions = [{
            'id': q.id, 'text': q.text, 'type': q.question_type,
            'order': q.order, 'is_required': q.is_required,
            'image_url': q.image_url,
            'answers': [
                {'id': a.id, 'text': a.text, 'image_url': a.image_url, 'order': a.order}
                for a in q.answers.all()
            ]
        } for q in quiz.questions.all()]
        return {
            'attempt_id': attempt.id,
            'attempt_uuid': str(attempt.uuid),
            'quiz_title': quiz.title,
            'quiz_type': quiz.quiz_type,
            'questions': questions,
        }

    @staticmethod
    def submit_answers(attempt_id: int, answers: Dict[str, Any]) -> Dict:
        """Submit quiz answers, calculate result, award reward."""
        from api.cms.models_new.quiz import QuizAttempt, QuizAnswer, QuizResult
        try:
            attempt = QuizAttempt.objects.select_related('quiz').get(
                id=attempt_id, is_completed=False
            )
        except QuizAttempt.DoesNotExist:
            return {'error': 'Attempt not found or already completed'}

        attempt.answers_data = answers

        # Calculate personality score
        total_score = 0
        personality_tags = {}
        for question_id, answer_id in answers.items():
            try:
                answer = QuizAnswer.objects.get(id=int(answer_id))
                total_score += answer.score_weight
                tag = answer.personality_tag
                if tag:
                    personality_tags[tag] = personality_tags.get(tag, 0) + 1
            except (QuizAnswer.DoesNotExist, ValueError):
                pass

        # Find best result
        dominant_tag = max(personality_tags, key=personality_tags.get) if personality_tags else ''
        result = QuizResult.objects.filter(
            quiz=attempt.quiz,
            personality_tag=dominant_tag,
        ).first() or QuizResult.objects.filter(
            quiz=attempt.quiz,
            min_score__lte=total_score,
            max_score__gte=total_score,
        ).first()

        if result:
            attempt.complete(result, total_score)
        else:
            attempt.total_score = total_score
            attempt.is_completed = True
            attempt.completed_at = timezone.now()
            attempt.save(update_fields=['total_score', 'is_completed', 'completed_at', 'answers_data'])

        # Award coins for completing quiz
        reward_coins = 0
        if attempt.quiz.payout_usd > 0 and (attempt.user or attempt.session_key):
            try:
                from api.cms.models_new.cpalead import VirtualCurrency
                from api.cms.services_new.CPALeadService import VirtualCurrencyService
                vc = VirtualCurrency.get_active()
                if vc and attempt.user:
                    reward_coins = float(vc.usd_to_virtual(attempt.quiz.payout_usd))
                    VirtualCurrencyService.award_coins(
                        user=attempt.user,
                        amount=vc.usd_to_virtual(attempt.quiz.payout_usd),
                        reason=f"Quiz completed: {attempt.quiz.title}",
                        tx_type='earn_quiz',
                    )
                    QuizAttempt.objects.filter(pk=attempt.pk).update(
                        reward_earned=True, reward_coins=reward_coins
                    )
            except Exception as e:
                logger.warning(f"QuizService reward failed: {e}")

        return {
            'completed': True,
            'total_score': total_score,
            'result': {
                'title': result.title if result else 'Result',
                'description': result.description if result else '',
                'image_url': result.image_url if result else '',
                'share_text': result.share_text if result else '',
            } if result else None,
            'reward_coins': reward_coins,
        }

    @staticmethod
    def list_quizzes(active_only: bool = True, limit: int = 20) -> List[Dict]:
        from api.cms.models_new.quiz import QuizTemplate
        qs = QuizTemplate.objects.all()
        if active_only:
            qs = qs.filter(is_active=True)
        qs = qs.order_by('-is_featured', '-created_at')[:limit]
        return [{
            'id': q.id, 'title': q.title, 'slug': q.slug,
            'quiz_type': q.quiz_type, 'thumbnail': q.thumbnail,
            'total_attempts': q.total_attempts,
            'completion_rate': q.completion_rate,
            'payout_usd': float(q.payout_usd),
        } for q in qs]
