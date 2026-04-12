# =============================================================================
# promotions/quiz_survey/quiz_manager.py
# 🟠 HIGH — Quiz/Survey Campaign System
# Co-reg Quiz: user answers questions → gets registered → publisher earns
# CPAlead: "personality quiz campaigns that outperform traditional offers"
# iMonetizeIt: Sweepstakes + Quiz = top earner for Tier1
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
import uuid, logging

logger = logging.getLogger(__name__)

QUIZ_TYPES = {
    'personality': 'Personality Quiz',
    'trivia':      'Trivia / Knowledge Quiz',
    'survey':      'Market Research Survey',
    'sweepstakes': 'Sweepstakes Entry',
    'iq':          'IQ Test',
    'interest':    'Interest Matching Quiz',
}


class QuizManager:
    """
    Create and serve quiz/survey campaigns.
    User completes quiz → system registers lead → publisher gets paid.
    """
    QUIZ_PREFIX = 'quiz:'
    SESSION_PREFIX = 'quiz_session:'

    def create_quiz_campaign(
        self,
        advertiser_id: int,
        quiz_title: str,
        quiz_type: str,
        questions: list,          # [{'q': '...', 'options': [...], 'correct': 0}]
        payout_per_completion: Decimal,
        lead_form_fields: list = None,  # ['email', 'name', 'phone', 'zip']
        min_questions_required: int = None,
        target_countries: list = None,
    ) -> dict:
        """Create a quiz campaign."""
        if quiz_type not in QUIZ_TYPES:
            return {'error': f'Invalid quiz type. Options: {", ".join(QUIZ_TYPES.keys())}'}

        if not questions:
            return {'error': 'At least 1 question required'}

        quiz_id = str(uuid.uuid4())[:16]
        quiz_data = {
            'quiz_id': quiz_id,
            'advertiser_id': advertiser_id,
            'title': quiz_title,
            'quiz_type': quiz_type,
            'type_display': QUIZ_TYPES[quiz_type],
            'questions': questions,
            'total_questions': len(questions),
            'min_questions_required': min_questions_required or len(questions),
            'lead_form_fields': lead_form_fields or ['email'],
            'payout_per_completion': str(payout_per_completion),
            'target_countries': target_countries or [],
            'status': 'active',
            'total_completions': 0,
            'created_at': timezone.now().isoformat(),
        }
        cache.set(f'{self.QUIZ_PREFIX}{quiz_id}', quiz_data, timeout=3600 * 24 * 365)

        return {
            'quiz_id': quiz_id,
            'title': quiz_title,
            'quiz_type': QUIZ_TYPES[quiz_type],
            'total_questions': len(questions),
            'payout': str(payout_per_completion),
            'embed_url': f'/api/promotions/quiz/{quiz_id}/',
            'embed_code': self._generate_quiz_embed(quiz_id, quiz_title),
            'status': 'active',
        }

    def get_quiz(self, quiz_id: str, publisher_id: int = 0) -> dict:
        """Get quiz for display (questions without correct answers)."""
        quiz = cache.get(f'{self.QUIZ_PREFIX}{quiz_id}')
        if not quiz:
            return {'error': 'Quiz not found'}

        # Return questions without correct answers
        safe_questions = []
        for i, q in enumerate(quiz['questions']):
            safe_questions.append({
                'index': i,
                'question': q.get('q', ''),
                'options': q.get('options', []),
                # NO 'correct' field exposed!
            })

        return {
            'quiz_id': quiz_id,
            'title': quiz['title'],
            'quiz_type': quiz['type_display'],
            'questions': safe_questions,
            'total_questions': quiz['total_questions'],
            'payout_display': f'${Decimal(quiz["payout_per_completion"]):.2f}',
            'lead_form_fields': quiz['lead_form_fields'],
            'cta': 'Complete Quiz — Get Results!',
            'publisher_id': publisher_id,
        }

    def start_quiz_session(self, quiz_id: str, visitor_id: str, publisher_id: int) -> dict:
        """Start a new quiz session for a visitor."""
        quiz = cache.get(f'{self.QUIZ_PREFIX}{quiz_id}')
        if not quiz:
            return {'error': 'Quiz not found'}

        session_id = str(uuid.uuid4())[:16]
        session = {
            'session_id': session_id,
            'quiz_id': quiz_id,
            'visitor_id': visitor_id,
            'publisher_id': publisher_id,
            'answers': [],
            'current_question': 0,
            'started_at': timezone.now().isoformat(),
            'completed': False,
        }
        cache.set(f'{self.SESSION_PREFIX}{session_id}', session, timeout=3600)
        return {'session_id': session_id, 'quiz_id': quiz_id, 'total_questions': quiz['total_questions']}

    def submit_answer(self, session_id: str, question_index: int, answer_index: int) -> dict:
        """Submit an answer for a question."""
        session = cache.get(f'{self.SESSION_PREFIX}{session_id}')
        if not session:
            return {'error': 'Session expired'}

        quiz = cache.get(f'{self.QUIZ_PREFIX}{session["quiz_id"]}')
        if not quiz:
            return {'error': 'Quiz not found'}

        if question_index >= len(quiz['questions']):
            return {'error': 'Invalid question index'}

        session['answers'].append({
            'question_index': question_index,
            'answer_index': answer_index,
            'answered_at': timezone.now().isoformat(),
        })
        session['current_question'] = question_index + 1
        cache.set(f'{self.SESSION_PREFIX}{session_id}', session, timeout=3600)

        is_last = question_index + 1 >= quiz['min_questions_required']
        return {
            'session_id': session_id,
            'question_index': question_index,
            'is_complete': is_last,
            'questions_remaining': max(0, quiz['total_questions'] - (question_index + 1)),
        }

    def complete_quiz(self, session_id: str, lead_data: dict) -> dict:
        """Complete quiz, collect lead, award publisher."""
        session = cache.get(f'{self.SESSION_PREFIX}{session_id}')
        if not session or session.get('completed'):
            return {'error': 'Invalid or already completed session'}

        quiz = cache.get(f'{self.QUIZ_PREFIX}{session["quiz_id"]}')
        if not quiz:
            return {'error': 'Quiz not found'}

        # Validate lead data
        required_fields = quiz.get('lead_form_fields', ['email'])
        for field in required_fields:
            if field not in lead_data or not lead_data[field]:
                return {'error': f'Required field missing: {field}'}

        # Mark completed
        session['completed'] = True
        session['completed_at'] = timezone.now().isoformat()
        session['lead_data'] = {k: v for k, v in lead_data.items() if k in required_fields}
        cache.set(f'{self.SESSION_PREFIX}{session_id}', session, timeout=3600 * 24)

        # Award publisher
        payout = Decimal(quiz['payout_per_completion'])
        self._award_quiz_payout(
            publisher_id=session['publisher_id'],
            quiz_id=session['quiz_id'],
            payout=payout,
            session_id=session_id,
        )

        # Calculate "results" (personality-style)
        result = self._calculate_result(quiz, session['answers'])

        return {
            'success': True,
            'session_id': session_id,
            'result': result,
            'payout_awarded': str(payout),
            'message': 'Quiz completed! Results ready.',
        }

    def _calculate_result(self, quiz: dict, answers: list) -> dict:
        """Generate personality result based on answers."""
        quiz_type = quiz.get('quiz_type', 'personality')
        total_answers = len(answers)
        score = sum(a.get('answer_index', 0) for a in answers)

        if quiz_type == 'personality':
            profiles = [
                {'type': 'The Innovator', 'desc': 'You love trying new things!'},
                {'type': 'The Achiever', 'desc': 'You are goal-oriented and driven!'},
                {'type': 'The Connector', 'desc': 'You value relationships above all!'},
                {'type': 'The Thinker', 'desc': 'You analyze before you act!'},
            ]
            return profiles[score % len(profiles)]
        elif quiz_type == 'trivia':
            return {
                'score': score,
                'total': total_answers,
                'percentage': round(score / max(total_answers, 1) * 100),
                'grade': 'A' if score >= total_answers * 0.9 else 'B' if score >= 0.7 else 'C',
            }
        return {'completed': True, 'answers': total_answers}

    def _award_quiz_payout(self, publisher_id: int, quiz_id: str, payout: Decimal, session_id: str):
        from api.promotions.models import PromotionTransaction
        try:
            PromotionTransaction.objects.create(
                user_id=publisher_id,
                transaction_type='reward',
                amount=payout,
                status='completed',
                notes=f'Quiz Completion — #{quiz_id[:8]}',
                metadata={'quiz_id': quiz_id, 'session_id': session_id, 'type': 'quiz'},
            )
        except Exception as e:
            logger.error(f'Quiz payout failed: {e}')

    def _generate_quiz_embed(self, quiz_id: str, title: str) -> str:
        from django.conf import settings
        base = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        return f'''<!-- Quiz Widget Embed -->
<div id="quiz-widget-{quiz_id[:8]}"></div>
<script src="{base}/static/promotions/js/quiz-sdk.js"></script>
<script>
  QuizSDK.init({{
    quizId: '{quiz_id}',
    containerId: 'quiz-widget-{quiz_id[:8]}',
    apiBase: '{base}/api/promotions/',
    theme: 'modern',
    onComplete: function(result) {{ console.log('Quiz done:', result); }}
  }});
</script>'''


@api_view(['GET'])
@permission_classes([AllowAny])
def get_quiz_view(request, quiz_id):
    """GET /api/promotions/quiz/<quiz_id>/?pub=123"""
    manager = QuizManager()
    pub_id = int(request.query_params.get('pub', 0))
    quiz = manager.get_quiz(quiz_id, publisher_id=pub_id)
    if 'error' in quiz:
        return Response(quiz, status=status.HTTP_404_NOT_FOUND)
    return Response(quiz)


@api_view(['POST'])
@permission_classes([AllowAny])
def start_quiz_session_view(request, quiz_id):
    """POST /api/promotions/quiz/<quiz_id>/start/"""
    import hashlib
    ip = request.META.get('REMOTE_ADDR', '')
    ua = request.META.get('HTTP_USER_AGENT', '')
    visitor_id = hashlib.sha256(f'{ip}:{ua}'.encode()).hexdigest()[:16]
    pub_id = int(request.data.get('publisher_id', 0))
    manager = QuizManager()
    result = manager.start_quiz_session(quiz_id, visitor_id, pub_id)
    return Response(result)


@api_view(['POST'])
@permission_classes([AllowAny])
def submit_answer_view(request, session_id):
    """POST /api/promotions/quiz/session/<session_id>/answer/"""
    manager = QuizManager()
    result = manager.submit_answer(
        session_id=session_id,
        question_index=int(request.data.get('question_index', 0)),
        answer_index=int(request.data.get('answer_index', 0)),
    )
    return Response(result)


@api_view(['POST'])
@permission_classes([AllowAny])
def complete_quiz_view(request, session_id):
    """POST /api/promotions/quiz/session/<session_id>/complete/"""
    manager = QuizManager()
    result = manager.complete_quiz(
        session_id=session_id,
        lead_data=request.data.get('lead_data', {}),
    )
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_quiz_campaign_view(request):
    """POST /api/promotions/quiz/create/"""
    manager = QuizManager()
    data = request.data
    result = manager.create_quiz_campaign(
        advertiser_id=request.user.id,
        quiz_title=data.get('title', ''),
        quiz_type=data.get('quiz_type', 'personality'),
        questions=data.get('questions', []),
        payout_per_completion=Decimal(str(data.get('payout', '0.50'))),
        lead_form_fields=data.get('lead_form_fields', ['email']),
        target_countries=data.get('target_countries', []),
    )
    return Response(result, status=status.HTTP_201_CREATED)
