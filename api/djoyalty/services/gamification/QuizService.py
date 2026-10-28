# api/djoyalty/services/gamification/QuizService.py
"""
QuizService -- Quiz attempt grading and points reward.
World reference: Starbucks Rewards quiz challenges, Voucherify quiz campaigns.

Flow:
  1. get_quiz()    -> fetch quiz + questions for customer
  2. submit()      -> grade answers, award points if passing score met
  3. get_history() -> customer's past attempts
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class QuizService:

    @staticmethod
    def get_quiz(quiz_id: int, customer=None) -> dict:
        """
        Get quiz details. If customer given, includes attempt history.
        Returns: {'quiz': {...}, 'questions': [...], 'attempts_used': N}
        """
        try:
            from ...models.gamification import QuizReward, CustomerQuizAttempt

            try:
                quiz = QuizReward.objects.get(id=quiz_id, is_active=True)
            except QuizReward.DoesNotExist:
                return {'success': False, 'error': 'Quiz not found or inactive'}

            # Check validity window
            now = timezone.now()
            if quiz.valid_from and quiz.valid_from > now:
                return {'success': False, 'error': 'Quiz not yet available'}
            if quiz.valid_until and quiz.valid_until < now:
                return {'success': False, 'error': 'Quiz has ended'}

            attempts_used = 0
            already_passed = False
            if customer:
                attempts_used = CustomerQuizAttempt.objects.filter(
                    customer=customer, quiz=quiz,
                ).count()
                already_passed = CustomerQuizAttempt.objects.filter(
                    customer=customer, quiz=quiz, passed=True,
                ).exists()

            return {
                'success': True,
                'quiz': {
                    'id': quiz.id,
                    'name': quiz.name,
                    'description': getattr(quiz, 'description', ''),
                    'points_reward': str(quiz.points_reward),
                    'passing_score': getattr(quiz, 'passing_score', 70),
                    'max_attempts': getattr(quiz, 'max_attempts', 3),
                    'time_limit_minutes': getattr(quiz, 'time_limit_minutes', None),
                },
                'questions': QuizService._get_questions(quiz),
                'attempts_used': attempts_used,
                'already_passed': already_passed,
                'can_attempt': (
                    not already_passed and
                    attempts_used < getattr(quiz, 'max_attempts', 3)
                ),
            }

        except Exception as e:
            logger.error('QuizService.get_quiz error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    @transaction.atomic
    def submit(customer, quiz_id: int, answers: dict, tenant=None) -> dict:
        """
        Grade a quiz attempt.
        answers = {'question_id': 'chosen_answer', ...}
        Returns: {'success': True, 'score': 80, 'passed': True, 'points_awarded': 100}
        """
        try:
            from ...models.gamification import QuizReward, CustomerQuizAttempt

            try:
                quiz = QuizReward.objects.get(id=quiz_id, is_active=True)
            except QuizReward.DoesNotExist:
                return {'success': False, 'error': 'Quiz not found'}

            # Max attempts check
            max_attempts = getattr(quiz, 'max_attempts', 3)
            attempts_used = CustomerQuizAttempt.objects.filter(
                customer=customer, quiz=quiz,
            ).count()
            if attempts_used >= max_attempts:
                return {'success': False, 'error': f'Maximum {max_attempts} attempts reached'}

            # Already passed -> no more attempts
            already_passed = CustomerQuizAttempt.objects.filter(
                customer=customer, quiz=quiz, passed=True,
            ).exists()
            if already_passed:
                return {'success': False, 'error': 'Quiz already passed'}

            # Grade answers
            score, correct_count, total_questions = QuizService._grade(quiz, answers)
            passing_score = getattr(quiz, 'passing_score', 70)
            passed = score >= passing_score
            points_awarded = Decimal('0')

            if passed:
                points_awarded = quiz.points_reward or Decimal('0')
                if points_awarded > 0:
                    from ...services.earn.BonusEventService import BonusEventService
                    BonusEventService.award_bonus(
                        customer, points_awarded,
                        reason=f'Quiz passed: {quiz.name}',
                        triggered_by='quiz',
                        tenant=tenant,
                    )

            # Record attempt
            attempt = CustomerQuizAttempt.objects.create(
                customer=customer,
                quiz=quiz,
                tenant=tenant or getattr(customer, 'tenant', None),
                score=score,
                passed=passed,
                answers_given=answers,
                points_awarded=points_awarded,
                attempted_at=timezone.now(),
            )

            logger.info('QuizService.submit: %s quiz %s -> score=%s passed=%s',
                        customer.code, quiz.name, score, passed)

            return {
                'success': True,
                'attempt_id': attempt.id,
                'score': score,
                'passing_score': passing_score,
                'passed': passed,
                'correct_count': correct_count,
                'total_questions': total_questions,
                'points_awarded': str(points_awarded),
                'attempts_remaining': max(0, max_attempts - attempts_used - 1),
            }

        except Exception as e:
            logger.error('QuizService.submit error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_history(customer, quiz_id: int = None) -> list:
        """Get customer's quiz attempt history."""
        try:
            from ...models.gamification import CustomerQuizAttempt
            qs = CustomerQuizAttempt.objects.filter(customer=customer)
            if quiz_id:
                qs = qs.filter(quiz_id=quiz_id)
            return list(qs.order_by('-attempted_at').values(
                'id', 'quiz_id', 'quiz__name', 'score',
                'passed', 'points_awarded', 'attempted_at',
            ))
        except Exception as e:
            logger.error('QuizService.get_history error: %s', e)
            return []

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _get_questions(quiz) -> list:
        """
        Get questions for a quiz.
        Looks for a JSONField 'questions' on QuizReward model.
        Format: [{'id': 1, 'question': '...', 'options': [...], 'correct': 'A'}, ...]
        The 'correct' field is STRIPPED before returning to customer.
        """
        try:
            raw = getattr(quiz, 'questions', None) or []
            # Strip correct answers from response
            return [
                {k: v for k, v in q.items() if k != 'correct'}
                for q in raw
            ]
        except Exception:
            return []

    @staticmethod
    def _grade(quiz, answers: dict) -> tuple:
        """
        Grade answers against quiz correct answers.
        Returns: (score_percent, correct_count, total_questions)
        """
        try:
            questions = getattr(quiz, 'questions', None) or []
            if not questions:
                return 100, 0, 0

            correct_count = 0
            for q in questions:
                q_id = str(q.get('id', ''))
                correct = str(q.get('correct', ''))
                given = str(answers.get(q_id, answers.get(int(q_id) if q_id.isdigit() else q_id, '')))
                if given and correct and given.strip().upper() == correct.strip().upper():
                    correct_count += 1

            total = len(questions)
            score = round((correct_count / total) * 100) if total > 0 else 0
            return score, correct_count, total
        except Exception as e:
            logger.error('QuizService._grade error: %s', e)
            return 0, 0, 0
