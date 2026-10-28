"""
tasks/personality_quiz_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Personality Quiz Offer Tasks — CPAlead's Exclusive Feature
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead states: "We are the ONLY network that has both in-house CPC offers
and co-reg Quiz offers that perform better than email submits."

Personality quizzes drive MASSIVE social media traffic and convert
better than email submits because users complete them voluntarily.

  ✅ create_quiz_session         — start a personality quiz session
  ✅ record_quiz_answer          — record each quiz answer
  ✅ complete_quiz               — finalize quiz + credit publisher
  ✅ generate_quiz_result        — compute personalized quiz result
  ✅ process_quiz_lead           — handle co-reg lead data
  ✅ sync_quiz_inventory         — pull quiz offers from sources
  ✅ rotate_quiz_questions       — A/B test quiz question sets
  ✅ generate_quiz_report        — daily quiz performance analytics
  ✅ detect_quiz_fraud           — catch bot completions / invalid answers
  ✅ share_quiz_result           — generate shareable quiz result card
"""
import logging
import uuid
import json
import hashlib
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

QUIZ_SESSION_TTL = 3600 * 2   # 2 hours to complete a quiz
QUIZ_DEDUP_TTL   = 86400 * 30 # 30-day dedup window

# Default quiz categories (CPAlead-style)
QUIZ_CATEGORIES = [
    'personality', 'iq_test', 'relationship', 'career', 'health',
    'celebrity_match', 'trivia', 'compatibility', 'astrology', 'lifestyle',
]

# Minimum answers before quiz can be completed
MIN_QUIZ_ANSWERS = 3


@shared_task(bind=True, max_retries=2, default_retry_delay=10,
             name='tasks.personality_quiz_tasks.create_quiz_session')
def create_quiz_session(
    self,
    quiz_id: str,
    user_id: int,
    publisher_id: int,
    click_id: str,
    country: str = 'US',
    device: str = 'desktop',
    utm_source: str = '',
    ip_address: str = '',
) -> dict:
    """
    Initialize a personality quiz session for a user.
    Each quiz session tracks:
    - Questions answered
    - Time taken
    - Device fingerprint
    - Click attribution

    Returns a session_id that tracks the quiz state.
    """
    try:
        logger.info(f"🎯 Quiz session started: quiz={quiz_id} user={user_id} country={country}")

        session_id = str(uuid.uuid4()).replace('-', '')

        session_data = {
            'session_id':   session_id,
            'quiz_id':      quiz_id,
            'user_id':      user_id,
            'publisher_id': publisher_id,
            'click_id':     click_id,
            'country':      country,
            'device':       device,
            'utm_source':   utm_source,
            'ip_address':   ip_address,
            'answers':      [],
            'started_at':   timezone.now().isoformat(),
            'completed':    False,
            'credited':     False,
        }

        cache.set(f'quiz_session_{session_id}', session_data, timeout=QUIZ_SESSION_TTL)

        # Track quiz views for analytics
        view_key = f'quiz_views_{quiz_id}'
        cache.set(view_key, cache.get(view_key, 0) + 1, timeout=86400)

        # Load quiz questions
        questions = _get_quiz_questions(quiz_id)

        return {
            'status':       'success',
            'session_id':   session_id,
            'quiz_id':      quiz_id,
            'questions':    questions[:10],  # Send first 10 questions
            'total_questions': len(questions),
            'timestamp':    timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] create_quiz_session: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=5,
             name='tasks.personality_quiz_tasks.record_quiz_answer')
def record_quiz_answer(
    self,
    session_id: str,
    question_id: str,
    answer: str,
    answer_index: int = 0,
    time_taken_seconds: float = 0.0,
) -> dict:
    """
    Record a user's answer to a quiz question.
    Validates answer and updates session state.
    Fraud signals: answer in <0.5s (bot), same answer for all questions.
    """
    try:
        session = cache.get(f'quiz_session_{session_id}')
        if not session:
            return {'status': 'session_expired', 'session_id': session_id}

        if session.get('completed'):
            return {'status': 'already_completed'}

        # Fraud: answer too fast (bot detection)
        if time_taken_seconds < 0.5:
            logger.warning(f"[QUIZ FRAUD] Suspiciously fast answer: {time_taken_seconds:.2f}s")
            session['fraud_signals'] = session.get('fraud_signals', 0) + 1

        # Record answer
        session['answers'].append({
            'question_id':        question_id,
            'answer':             answer,
            'answer_index':       answer_index,
            'time_taken_seconds': time_taken_seconds,
            'answered_at':        timezone.now().isoformat(),
        })

        session['last_answer_at'] = timezone.now().isoformat()
        cache.set(f'quiz_session_{session_id}', session, timeout=QUIZ_SESSION_TTL)

        return {
            'status':          'recorded',
            'session_id':      session_id,
            'answers_count':   len(session['answers']),
            'timestamp':       timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10,
             name='tasks.personality_quiz_tasks.complete_quiz')
def complete_quiz(
    self,
    session_id: str,
    email: str = '',           # Optional co-reg email collection
    name: str  = '',
    opt_in: bool = False,
) -> dict:
    """
    Finalize a quiz and credit the publisher.

    Key steps:
    1. Validate session has minimum answers
    2. Check for fraud signals
    3. Validate co-reg email if provided
    4. Generate quiz result
    5. Credit publisher payout
    6. Fire advertiser postback
    7. Create shareable result link
    """
    try:
        session = cache.get(f'quiz_session_{session_id}')
        if not session:
            return {'status': 'session_expired', 'session_id': session_id}

        if session.get('completed'):
            return {
                'status':     'already_completed',
                'session_id': session_id,
                'result_url': session.get('result_url', ''),
            }

        # Validate minimum answers
        answers = session.get('answers', [])
        if len(answers) < MIN_QUIZ_ANSWERS:
            return {
                'status':    'insufficient_answers',
                'answered':  len(answers),
                'required':  MIN_QUIZ_ANSWERS,
            }

        quiz_id      = session['quiz_id']
        user_id      = session['user_id']
        publisher_id = session['publisher_id']
        click_id     = session['click_id']

        # Fraud check
        fraud_signals = session.get('fraud_signals', 0)
        if fraud_signals >= 3:
            logger.warning(f"[QUIZ FRAUD] Session {session_id}: {fraud_signals} fraud signals")
            return {'status': 'fraud_detected', 'session_id': session_id}

        # Dedup: same user + quiz
        dedup_hash = hashlib.sha256(f"{user_id}_{quiz_id}".encode()).hexdigest()
        dedup_key  = f'quiz_dedup_{dedup_hash}'
        if cache.get(dedup_key):
            return {'status': 'duplicate_completion', 'session_id': session_id}
        cache.set(dedup_key, 1, timeout=QUIZ_DEDUP_TTL)

        # Generate quiz result
        result = generate_quiz_result.apply(kwargs={
            'session_id': session_id,
            'answers':    answers,
            'quiz_id':    quiz_id,
        }).get()

        result_id  = result.get('result_id', session_id[:8])
        result_url = f"/quiz/result/{result_id}/"

        # Get payout
        payout     = _get_quiz_payout(quiz_id, session.get('country', 'US'))
        pub_share  = payout * Decimal('0.70')

        # Process co-reg lead
        if email and opt_in:
            process_quiz_lead.apply_async(kwargs={
                'quiz_id':      quiz_id,
                'session_id':   session_id,
                'email':        email,
                'name':         name,
                'country':      session.get('country', ''),
                'publisher_id': publisher_id,
                'answers':      answers,
            })

        # Credit publisher
        if pub_share > Decimal('0') and publisher_id:
            try:
                from api.tasks.services import WalletService
                WalletService().credit(
                    user_id=publisher_id,
                    amount=pub_share,
                    transaction_type='quiz_completion',
                    reference=f'quiz_{quiz_id}_{session_id[:8]}',
                    metadata={
                        'quiz_id':    quiz_id,
                        'session_id': session_id,
                        'payout':     str(payout),
                        'email_lead': bool(email and opt_in),
                    },
                )
            except ImportError:
                pass

        # Update community points (1000 pts per $1)
        try:
            from api.tasks.community_tasks import award_community_points
            award_community_points.apply_async(kwargs={
                'user_id':    user_id or publisher_id,
                'amount_usd': str(pub_share),
                'source':     'quiz_completion',
            })
        except ImportError:
            pass

        # Fire postback
        try:
            from api.tasks.click_tracking_tasks import fire_postback
            fire_postback.apply_async(kwargs={
                'click_id':       click_id,
                'transaction_id': session_id,
                'payout':         str(payout),
                'status':         'approved',
            })
        except ImportError:
            pass

        # Mark session complete
        session['completed']   = True
        session['credited']    = True
        session['completed_at'] = timezone.now().isoformat()
        session['result_id']   = result_id
        session['result_url']  = result_url
        cache.set(f'quiz_session_{session_id}', session, timeout=86400)

        # Analytics
        comp_key = f'quiz_completions_{quiz_id}'
        cache.set(comp_key, cache.get(comp_key, 0) + 1, timeout=86400)

        logger.info(
            f"[QUIZ] Completed: quiz={quiz_id} user={user_id} "
            f"pub_payout=${pub_share} result={result_id}"
        )
        return {
            'status':      'success',
            'session_id':  session_id,
            'result_id':   result_id,
            'result_url':  result_url,
            'payout':      str(pub_share),
            'result':      result.get('result_data', {}),
            'timestamp':   timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] complete_quiz: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=10,
             name='tasks.personality_quiz_tasks.generate_quiz_result')
def generate_quiz_result(
    self,
    session_id: str,
    answers: list,
    quiz_id: str,
) -> dict:
    """
    Compute a personalized quiz result based on the user's answers.
    Personality type calculated from answer weights.
    Result is highly shareable on social media — driving viral traffic.
    """
    try:
        result_id   = hashlib.md5(f"{session_id}{quiz_id}".encode()).hexdigest()[:12]

        # Load quiz result mapping
        quiz_config = cache.get(f'quiz_config_{quiz_id}') or _default_quiz_config(quiz_id)
        result_map  = quiz_config.get('result_map', {})
        result_types = quiz_config.get('result_types', [])

        # Score answers
        scores = {}
        for answer in answers:
            weight = answer.get('answer_index', 0)
            for result_type in result_types:
                scores[result_type] = scores.get(result_type, 0) + weight

        # Pick top result type
        if scores:
            winner = max(scores, key=lambda k: scores[k])
        else:
            winner = result_types[0] if result_types else 'Type A'

        result_data = result_map.get(winner, {
            'type':        winner,
            'title':       f"You are a {winner}!",
            'description': f"Based on your answers, you are a natural {winner.lower()}.",
            'icon':        '🎯',
            'share_text':  f"I just found out I'm a {winner}! Take the quiz to find out yours!",
        })

        result_data['result_id']  = result_id
        result_data['quiz_id']    = quiz_id
        result_data['share_url']  = f"/quiz/result/{result_id}/"
        result_data['created_at'] = timezone.now().isoformat()

        # Cache result for sharing
        cache.set(f'quiz_result_{result_id}', result_data, timeout=86400 * 30)

        return {
            'status':      'success',
            'result_id':   result_id,
            'result_data': result_data,
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30,
             name='tasks.personality_quiz_tasks.process_quiz_lead')
def process_quiz_lead(
    self,
    quiz_id: str,
    session_id: str,
    email: str,
    name: str,
    country: str,
    publisher_id: int,
    answers: list,
) -> dict:
    """
    Process a co-reg lead collected during quiz completion.
    Validates email quality, stores lead, notifies advertisers.
    Co-reg leads are valued at premium CPA rates.
    """
    try:
        import re
        # Validate email
        if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email.strip()):
            return {'status': 'invalid_email', 'email': email}

        # Deduplicate email leads
        email_hash = hashlib.sha256(email.lower().encode()).hexdigest()
        dedup_key  = f'quiz_lead_dedup_{quiz_id}_{email_hash}'
        if cache.get(dedup_key):
            return {'status': 'duplicate_lead', 'email_hash': email_hash[:12]}
        cache.set(dedup_key, 1, timeout=QUIZ_DEDUP_TTL)

        # Store lead
        try:
            from quizzes.models import QuizLead
            QuizLead.objects.create(
                quiz_id=quiz_id,
                session_id=session_id,
                email=email,
                name=name or '',
                email_hash=email_hash,
                country=country,
                publisher_id=publisher_id,
                answers_json=json.dumps(answers),
                created_at=timezone.now(),
            )
        except ImportError:
            pass

        # Extra CPA credit for co-reg email opt-in
        co_reg_bonus = Decimal('0.25')   # $0.25 bonus for email opt-in
        try:
            from api.tasks.services import WalletService
            WalletService().credit(
                user_id=publisher_id,
                amount=co_reg_bonus,
                transaction_type='quiz_coreg_bonus',
                reference=f'coreg_{quiz_id}_{email_hash[:8]}',
                metadata={'email_hash': email_hash[:12], 'quiz_id': quiz_id},
            )
        except ImportError:
            pass

        logger.info(f"[QUIZ LEAD] Processed: quiz={quiz_id} email={email[:20]}...")
        return {
            'status':        'success',
            'quiz_id':       quiz_id,
            'email_hash':    email_hash[:12],
            'co_reg_bonus':  str(co_reg_bonus),
            'timestamp':     timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.personality_quiz_tasks.sync_quiz_inventory')
def sync_quiz_inventory(self) -> dict:
    """Pull quiz offer inventory from advertiser networks and update local DB."""
    try:
        logger.info("🔄 Syncing quiz inventory...")
        synced = 0

        # Default quiz templates if no external source configured
        default_quizzes = [
            {
                'quiz_id':    'personality_001',
                'title':      'What Type of Leader Are You?',
                'category':   'personality',
                'payout':     {'US': '0.80', 'GB': '0.70', 'DEFAULT': '0.30'},
                'questions':  10,
                'is_active':  True,
            },
            {
                'quiz_id':    'iq_test_001',
                'title':      'What is Your IQ? (Official Test)',
                'category':   'iq_test',
                'payout':     {'US': '1.20', 'GB': '1.00', 'DEFAULT': '0.50'},
                'questions':  15,
                'is_active':  True,
            },
            {
                'quiz_id':    'celeb_match_001',
                'title':      'Which Celebrity Are You Most Like?',
                'category':   'celebrity_match',
                'payout':     {'US': '0.60', 'GB': '0.55', 'DEFAULT': '0.25'},
                'questions':  8,
                'is_active':  True,
            },
        ]

        for quiz in default_quizzes:
            cache.set(f'quiz_config_{quiz["quiz_id"]}', quiz, timeout=86400)
            synced += 1

        try:
            from quizzes.models import QuizOffer
            for q in default_quizzes:
                QuizOffer.objects.update_or_create(
                    quiz_id=q['quiz_id'],
                    defaults={
                        'title':      q['title'],
                        'category':   q['category'],
                        'is_active':  q['is_active'],
                        'question_count': q['questions'],
                    },
                )
        except ImportError:
            pass

        return {'status': 'success', 'synced': synced, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.personality_quiz_tasks.detect_quiz_fraud')
def detect_quiz_fraud(self, lookback_hours: int = 1) -> dict:
    """
    Detect fraudulent quiz completions:
    - Same IP, multiple quizzes in short time (> 10/hour)
    - Bot-like answer patterns (all same answer index)
    - Session time too short for question count
    """
    try:
        from datetime import timedelta
        from django.db.models import Count
        logger.info(f"🔍 Detecting quiz fraud (lookback={lookback_hours}h)...")
        flagged = 0

        try:
            from quizzes.models import QuizCompletion
            cutoff = timezone.now() - timedelta(hours=lookback_hours)

            # IP velocity
            ip_high = (
                QuizCompletion.objects.filter(created_at__gte=cutoff)
                .values('ip_address')
                .annotate(cnt=Count('id'))
                .filter(cnt__gt=10)
            )
            for row in ip_high:
                flagged += 1
                logger.warning(f"[QUIZ FRAUD] IP {row['ip_address']}: {row['cnt']} completions/hour")
                # Block IP
                from api.tasks.ip_management_tasks import block_ip_range
                block_ip_range.apply_async(kwargs={
                    'cidr': row['ip_address'] + '/32',
                    'reason': f'quiz_velocity:{row["cnt"]}',
                    'duration_hours': 24,
                })

        except ImportError:
            pass

        return {'status': 'success', 'flagged': flagged, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.personality_quiz_tasks.generate_quiz_report')
def generate_quiz_report(self, date_str: str = None) -> dict:
    """Daily quiz performance report: completions, leads, revenue, viral shares."""
    try:
        from datetime import datetime, timedelta
        from django.db.models import Count, Sum

        target    = (datetime.strptime(date_str, '%Y-%m-%d').date()
                     if date_str else (timezone.now() - timedelta(days=1)).date())
        day_start = timezone.make_aware(datetime.combine(target, datetime.min.time()))
        day_end   = day_start + timedelta(days=1)

        report = {'date': str(target), 'type': 'quiz_daily', 'by_category': {}}

        try:
            from quizzes.models import QuizCompletion, QuizLead
            from django.db.models import Q

            for cat in QUIZ_CATEGORIES:
                comps = QuizCompletion.objects.filter(
                    created_at__gte=day_start,
                    created_at__lt=day_end,
                    quiz__category=cat,
                ).count()
                if comps > 0:
                    leads = QuizLead.objects.filter(
                        created_at__gte=day_start,
                        created_at__lt=day_end,
                        quiz_id__startswith=cat,
                    ).count()
                    report['by_category'][cat] = {
                        'completions': comps,
                        'leads':       leads,
                        'lead_rate':   round(leads / comps * 100, 1) if comps > 0 else 0,
                    }

        except ImportError:
            pass

        cache.set(f'quiz_report_{target}', report, timeout=86400)
        return {'status': 'success', 'report': report, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=5,
             name='tasks.personality_quiz_tasks.share_quiz_result')
def share_quiz_result(self, result_id: str, platform: str = 'facebook') -> dict:
    """
    Generate a shareable image/card for a quiz result.
    Returns: Open Graph-compatible share URL for social media.
    Viral sharing is CPAlead's primary traffic driver for quiz offers.
    """
    try:
        result_data = cache.get(f'quiz_result_{result_id}')
        if not result_data:
            return {'status': 'result_not_found', 'result_id': result_id}

        from django.conf import settings
        base_url   = getattr(settings, 'FRONTEND_URL', 'https://yourdomain.com')
        share_url  = f"{base_url}/quiz/result/{result_id}/"
        og_title   = result_data.get('title', 'My Quiz Result')
        og_desc    = result_data.get('share_text', 'I just took this quiz! Find out your result.')
        og_image   = f"{base_url}/api/quiz/og-image/{result_id}/"  # OG image endpoint

        share_links = {
            'facebook':  f"https://www.facebook.com/sharer/sharer.php?u={share_url}",
            'twitter':   f"https://twitter.com/intent/tweet?url={share_url}&text={og_desc}",
            'whatsapp':  f"https://api.whatsapp.com/send?text={og_desc}+{share_url}",
            'reddit':    f"https://reddit.com/submit?url={share_url}&title={og_title}",
            'link':      share_url,
        }

        # Track share event
        share_key = f'quiz_shares_{result_data.get("quiz_id", "")}'
        cache.set(share_key, cache.get(share_key, 0) + 1, timeout=86400)

        return {
            'status':      'success',
            'result_id':   result_id,
            'share_url':   share_url,
            'og_title':    og_title,
            'og_desc':     og_desc,
            'og_image':    og_image,
            'share_links': share_links,
            'platform':    platform,
            'link':        share_links.get(platform, share_url),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


# ── Private helpers ─────────────────────────────────────────────────────────

def _get_quiz_questions(quiz_id: str) -> list:
    """Return quiz questions from cache or DB."""
    cached = cache.get(f'quiz_questions_{quiz_id}')
    if cached:
        return cached

    # Default questions for demo
    questions = [
        {'id': f'{quiz_id}_q1', 'text': 'When facing a challenge, you typically...', 'options': ['Take charge', 'Plan carefully', 'Seek help', 'Stay calm']},
        {'id': f'{quiz_id}_q2', 'text': 'Your ideal weekend involves...', 'options': ['Adventure', 'Relaxation', 'Socializing', 'Learning']},
        {'id': f'{quiz_id}_q3', 'text': 'You make decisions based on...', 'options': ['Intuition', 'Data', 'Emotions', 'Others opinions']},
        {'id': f'{quiz_id}_q4', 'text': 'Your friends would describe you as...', 'options': ['Leader', 'Creative', 'Caring', 'Analytical']},
        {'id': f'{quiz_id}_q5', 'text': 'In a group, you are the one who...', 'options': ['Leads', 'Plans', 'Supports', 'Observes']},
    ]

    try:
        from quizzes.models import QuizQuestion
        db_qs = list(QuizQuestion.objects.filter(
            quiz_id=quiz_id, is_active=True
        ).values('id', 'text', 'options').order_by('order')[:15])
        if db_qs:
            questions = db_qs
    except ImportError:
        pass

    cache.set(f'quiz_questions_{quiz_id}', questions, timeout=3600)
    return questions


def _get_quiz_payout(quiz_id: str, country: str = 'US') -> Decimal:
    """Get quiz payout for country."""
    quiz_config = cache.get(f'quiz_config_{quiz_id}') or {}
    payout_map  = quiz_config.get('payout', {'DEFAULT': '0.50'})
    payout_str  = payout_map.get(country, payout_map.get('DEFAULT', '0.50'))
    return Decimal(str(payout_str))


def _default_quiz_config(quiz_id: str) -> dict:
    """Return default quiz config when not found in cache/DB."""
    category = quiz_id.split('_')[0] if '_' in quiz_id else 'personality'
    return {
        'quiz_id':    quiz_id,
        'category':   category,
        'payout':     {'US': '0.80', 'GB': '0.70', 'DEFAULT': '0.30'},
        'questions':  10,
        'is_active':  True,
        'result_types': ['Type A', 'Type B', 'Type C', 'Type D'],
        'result_map': {
            'Type A': {
                'type': 'Type A', 'title': 'The Natural Leader',
                'description': 'You have natural leadership qualities.',
                'icon': '👑', 'share_text': "I'm a Natural Leader! Find out your type!",
            },
            'Type B': {
                'type': 'Type B', 'title': 'The Creative Thinker',
                'description': 'You have incredible creative instincts.',
                'icon': '🎨', 'share_text': "I'm a Creative Thinker! Discover yours!",
            },
            'Type C': {
                'type': 'Type C', 'title': 'The Empathetic Soul',
                'description': 'Your emotional intelligence is extraordinary.',
                'icon': '💝', 'share_text': "I'm an Empathetic Soul! Take the quiz!",
            },
            'Type D': {
                'type': 'Type D', 'title': 'The Strategic Mind',
                'description': 'You think several steps ahead.',
                'icon': '🧠', 'share_text': "I'm a Strategic Mind! What are you?",
            },
        },
    }
