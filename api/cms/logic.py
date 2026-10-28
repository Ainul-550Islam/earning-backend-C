# api/cms/logic.py
"""Pure business logic functions — no Django/DB dependencies, fully testable."""
import logging
from decimal import Decimal
from typing import Optional, Tuple, Dict, Any, List

logger = logging.getLogger(__name__)


# ── Original Logic Functions ─────────────────────────────────────

def calculate_referral_bonus(original_amount: Decimal,
                              rate: Decimal = Decimal('0.05')) -> Decimal:
    """Calculate 5% referral bonus."""
    return (original_amount * rate).quantize(Decimal('0.0001'))


def calculate_coins_from_usd(usd: Decimal, ratio: Decimal) -> Decimal:
    """Convert USD to virtual coins using ratio."""
    return (usd * ratio).quantize(Decimal('1'))


def calculate_usd_from_coins(coins: Decimal, ratio: Decimal) -> Decimal:
    if ratio == 0:
        return Decimal('0')
    return (coins / ratio).quantize(Decimal('0.0001'))


def calculate_withdrawal_fee(amount_usd: Decimal,
                              fee_rate: Decimal = Decimal('0.02')) -> Tuple[Decimal, Decimal]:
    """Returns (fee, net_amount)."""
    fee = (amount_usd * fee_rate).quantize(Decimal('0.0001'))
    net = (amount_usd - fee).quantize(Decimal('0.0001'))
    return fee, net


def calculate_streak_multiplier(streak_days: int,
                                  max_multiplier: float = 2.0,
                                  per_day: float = 0.033) -> Decimal:
    multiplier = 1.0 + (streak_days * per_day)
    return Decimal(str(min(max_multiplier, multiplier))).quantize(Decimal('0.01'))


def calculate_user_level(total_earned_usd: float) -> int:
    thresholds = [(1000, 7), (500, 6), (200, 5), (100, 4), (50, 3), (10, 2)]
    for threshold, level in thresholds:
        if total_earned_usd >= threshold:
            return level
    return 1


def is_high_value_payout(amount_usd: Decimal, threshold: Decimal = Decimal('10')) -> bool:
    return amount_usd >= threshold


# ── Survey Logic ─────────────────────────────────────────────

def calculate_survey_quality(responses: List[Dict[str, Any]], survey_data: Dict[str, Any]) -> float:
    """Calculate quality score for survey responses."""
    base_score = 0.7
    
    # Time-based quality factor
    time_factor = _calculate_time_factor(responses, survey_data)
    
    # Consistency factor
    consistency_factor = _calculate_consistency_factor(responses)
    
    # Completeness factor
    completeness_factor = _calculate_completeness_factor(responses, survey_data)
    
    # Answer quality factor
    answer_quality_factor = _calculate_answer_quality_factor(responses, survey_data)
    
    # Weighted combination
    final_score = (
        base_score * 0.2 +
        time_factor * 0.25 +
        consistency_factor * 0.25 +
        completeness_factor * 0.15 +
        answer_quality_factor * 0.15
    )
    
    return min(max(final_score, 0.0), 1.0)


def _calculate_time_factor(responses: List[Dict[str, Any]], survey_data: Dict[str, Any]) -> float:
    """Calculate time-based quality factor."""
    if not responses:
        return 0.0
    
    # Get completion time from first response timestamp
    completion_time = responses[0].get('completion_time')
    if not completion_time:
        return 0.5  # Neutral score if no time data
    
    # Compare with expected time
    expected_minutes = survey_data.get('estimated_minutes', 10)
    # This would need actual time calculation in real implementation
    actual_seconds = 600  # Placeholder
    
    if actual_seconds < expected_minutes * 30:  # Too fast
        return 0.3
    elif actual_seconds < expected_minutes * 60:  # Reasonable
        return 0.9
    elif actual_seconds < expected_minutes * 120:  # Slow but acceptable
        return 0.7
    else:  # Too slow
        return 0.5


def _calculate_consistency_factor(responses: List[Dict[str, Any]]) -> float:
    """Calculate response consistency factor."""
    if not responses:
        return 0.0
    
    # Check for consistent answer patterns
    consistency_score = 0.8
    
    # Flag potential random responses
    answer_lengths = [len(str(r.get('answer', ''))) for r in responses]
    if answer_lengths:
        avg_length = sum(answer_lengths) / len(answer_lengths)
        # Penalize very short answers
        short_answers = sum(1 for length in answer_lengths if length < 3)
        if short_answers / len(answer_lengths) > 0.5:
            consistency_score -= 0.3
    
    # Check for duplicate answers
    answers = [str(r.get('answer', '')) for r in responses]
    unique_answers = len(set(answers))
    if unique_answers < len(answers) * 0.7:  # Many duplicates
        consistency_score -= 0.2
    
    return max(consistency_score, 0.0)


def _calculate_completeness_factor(responses: List[Dict[str, Any]], survey_data: Dict[str, Any]) -> float:
    """Calculate response completeness factor."""
    if not responses:
        return 0.0
    
    # Get required questions
    required_count = survey_data.get('required_questions_count', 5)
    
    # Count answered required questions
    answered_required = 0
    for response in responses:
        answer = response.get('answer')
        if answer and str(answer).strip():
            answered_required += 1
    
    return answered_required / required_count if required_count > 0 else 1.0


def _calculate_answer_quality_factor(responses: List[Dict[str, Any]], survey_data: Dict[str, Any]) -> float:
    """Calculate answer quality factor."""
    if not responses:
        return 0.0
    
    quality_score = 0.8
    
    for response in responses:
        answer = str(response.get('answer', '')).strip()
        
        # Penalize empty or very short answers
        if len(answer) < 2:
            quality_score -= 0.1
        
        # Check for obviously invalid answers
        if answer.lower() in ['n/a', 'none', 'xxx', 'test']:
            quality_score -= 0.2
    
    return max(quality_score, 0.0)


def calculate_survey_recommendation_score(user_data: Dict[str, Any], survey_data: Dict[str, Any]) -> float:
    """Calculate recommendation score for a survey for a specific user."""
    score = 0.0
    
    # Category preference
    user_categories = user_data.get('preferred_categories', [])
    survey_category = survey_data.get('category')
    if survey_category in user_categories:
        score += 0.3
    
    # Difficulty matching
    user_avg_quality = user_data.get('average_quality_score', 0.7)
    survey_difficulty = survey_data.get('difficulty', 'medium')
    
    if user_avg_quality >= 0.8 and survey_difficulty == 'hard':
        score += 0.2
    elif user_avg_quality >= 0.6 and survey_difficulty == 'medium':
        score += 0.2
    elif user_avg_quality < 0.6 and survey_difficulty == 'easy':
        score += 0.2
    
    # Reward amount
    max_reward = survey_data.get('max_reward', 0)
    if max_reward > 5.0:
        score += 0.1
    
    # Time preference
    user_avg_time = user_data.get('average_completion_time', 600)  # seconds
    survey_time = survey_data.get('estimated_minutes', 10) * 60
    
    if abs(user_avg_time - survey_time) < 300:  # Within 5 minutes
        score += 0.1
    
    return min(score, 1.0)


# ── Reward Logic ─────────────────────────────────────────────

def calculate_survey_reward(survey_data: Dict[str, Any], quality_score: float, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate reward for survey completion."""
    base_reward = Decimal(str(survey_data.get('min_reward', 1.0)))
    max_reward = Decimal(str(survey_data.get('max_reward', 5.0)))
    
    # Quality bonus
    quality_multiplier = Decimal('1.0')
    if quality_score >= 0.9:
        quality_multiplier = Decimal('1.2')  # 20% bonus
    elif quality_score >= 0.8:
        quality_multiplier = Decimal('1.1')  # 10% bonus
    elif quality_score < 0.5:
        quality_multiplier = Decimal('0.8')  # 20% penalty
    
    # Difficulty bonus
    difficulty_multiplier = Decimal('1.0')
    survey_difficulty = survey_data.get('difficulty', 'medium')
    if survey_difficulty == 'hard':
        difficulty_multiplier = Decimal('1.3')
    elif survey_difficulty == 'medium':
        difficulty_multiplier = Decimal('1.15')
    
    # User loyalty bonus
    loyalty_multiplier = Decimal(str(_calculate_loyalty_multiplier(user_data)))
    
    # Calculate final reward
    final_reward = base_reward * quality_multiplier * difficulty_multiplier * loyalty_multiplier
    final_reward = min(final_reward, max_reward)
    
    return {
        'base_reward': base_reward,
        'quality_multiplier': quality_multiplier,
        'difficulty_multiplier': difficulty_multiplier,
        'loyalty_multiplier': loyalty_multiplier,
        'final_reward': final_reward,
        'bonus_amount': final_reward - base_reward
    }


def _calculate_loyalty_multiplier(user_data: Dict[str, Any]) -> float:
    """Calculate loyalty multiplier based on user's history."""
    # Get user's completion count
    completion_count = user_data.get('survey_completions_count', 0)
    
    if completion_count >= 100:
        return 1.2  # 20% bonus
    elif completion_count >= 50:
        return 1.15  # 15% bonus
    elif completion_count >= 25:
        return 1.1  # 10% bonus
    elif completion_count >= 10:
        return 1.05  # 5% bonus
    else:
        return 1.0


def calculate_pool_utilization(pool_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate reward pool utilization metrics."""
    total_allocated = Decimal(str(pool_data.get('total_allocated', 1000)))
    current_balance = Decimal(str(pool_data.get('current_balance', 500)))
    utilized_amount = total_allocated - current_balance
    
    utilization_percentage = float((utilized_amount / total_allocated * 100) if total_allocated > 0 else 0)
    
    return {
        'total_allocated': total_allocated,
        'current_balance': current_balance,
        'utilized_amount': utilized_amount,
        'utilization_percentage': utilization_percentage,
        'is_low': utilization_percentage > 80,
        'is_critical': utilization_percentage > 95
    }


def should_refill_pool(pool_data: Dict[str, Any], threshold: float = 80.0) -> bool:
    """Determine if pool should be refilled."""
    utilization = calculate_pool_utilization(pool_data)
    return utilization['utilization_percentage'] >= threshold and pool_data.get('auto_refill', False)


# ── Task Management Logic ─────────────────────────────────────

def calculate_task_priority(task_data: Dict[str, Any], context: Dict[str, Any] = None) -> int:
    """Calculate priority score for a task."""
    base_priority = 50
    
    # Task type priority
    type_priority = {
        'cleanup': 30,
        'analytics': 40,
        'notification': 60,
        'report': 50,
        'backup': 20
    }
    
    task_type = task_data.get('task_type', 'cleanup')
    base_priority += type_priority.get(task_type, 50)
    
    # Urgency factor
    next_run_time = task_data.get('next_run_time')
    if next_run_time:
        # This would need actual time calculation in real implementation
        time_until_run = 3600  # Placeholder: 1 hour
        
        if time_until_run < 300:  # Less than 5 minutes
            base_priority += 30
        elif time_until_run < 3600:  # Less than 1 hour
            base_priority += 20
        elif time_until_run < 86400:  # Less than 1 day
            base_priority += 10
    
    # Failure rate factor
    recent_failures = task_data.get('recent_failure_count', 0)
    if recent_failures > 3:
        base_priority -= 20  # Lower priority for frequently failing tasks
    
    return max(base_priority, 1)


def should_retry_task(task_data: Dict[str, Any], execution_data: Dict[str, Any]) -> bool:
    """Determine if a failed task should be retried."""
    # Check retry count
    max_retries = task_data.get('max_retries', 3)
    retry_count = execution_data.get('retry_count', 0)
    
    if retry_count >= max_retries:
        return False
    
    # Check failure type
    error_message = execution_data.get('error_message', '').lower()
    
    # Don't retry certain types of errors
    non_retryable_errors = [
        'permission denied',
        'authentication failed',
        'invalid configuration',
        'not found'
    ]
    
    for error in non_retryable_errors:
        if error in error_message:
            return False
    
    return True


def calculate_retry_delay(execution_data: Dict[str, Any]) -> int:
    """Calculate delay before next retry using exponential backoff."""
    base_delay = 60  # 1 minute
    max_delay = 3600  # 1 hour
    retry_count = execution_data.get('retry_count', 0)
    
    # Exponential backoff with jitter
    import random
    delay = base_delay * (2 ** retry_count)
    delay = min(delay, max_delay)
    
    # Add jitter to prevent thundering herd
    jitter = random.uniform(0.8, 1.2)
    delay = int(delay * jitter)
    
    return delay


# ── User Profile Logic ─────────────────────────────────────

def calculate_profile_completeness(profile_data: Dict[str, Any]) -> float:
    """Calculate profile completeness percentage."""
    required_fields = ['first_name', 'last_name', 'email']
    optional_fields = ['phone_number', 'date_of_birth', 'address']
    
    completeness = 0.0
    
    # Required fields (60% weight)
    required_filled = 0
    for field in required_fields:
        if profile_data.get(field):
            required_filled += 1
    
    completeness += (required_filled / len(required_fields)) * 60
    
    # Optional fields (40% weight)
    optional_filled = 0
    for field in optional_fields:
        if profile_data.get(field):
            optional_filled += 1
    
    completeness += (optional_filled / len(optional_fields)) * 40
    
    return min(completeness, 100.0)


def calculate_participation_score(user_data: Dict[str, Any]) -> float:
    """Calculate user participation score."""
    # Survey participation (40% weight)
    completed_surveys = user_data.get('completed_surveys_count', 0)
    survey_score = min(completed_surveys * 2, 40)
    
    # Quality score (30% weight)
    avg_quality = user_data.get('average_quality_score', 0.7)
    quality_score = avg_quality * 30
    
    # Activity recency (20% weight)
    days_since_last_activity = user_data.get('days_since_last_activity', 30)
    recency_score = max(0, 20 - days_since_last_activity)
    
    # Profile completeness (10% weight)
    profile_completeness = user_data.get('profile_completeness', 50)
    profile_score = profile_completeness / 10
    
    total_score = survey_score + quality_score + recency_score + profile_score
    return min(total_score, 100.0)


def determine_user_segments(user_data: Dict[str, Any]) -> List[str]:
    """Determine appropriate user segments based on profile and behavior."""
    segments = []
    
    # Demographic segments
    profile_data = user_data.get('profile', {})
    
    # Age-based segments
    date_of_birth = profile_data.get('date_of_birth')
    if date_of_birth:
        # This would need actual age calculation in real implementation
        age = 25  # Placeholder
        if age < 18:
            segments.append('under_18')
        elif age < 25:
            segments.append('18_24')
        elif age < 35:
            segments.append('25_34')
        elif age < 50:
            segments.append('35_49')
        else:
            segments.append('50_plus')
    
    # Location-based segments (if available)
    if profile_data.get('address'):
        segments.append('has_address')
    
    # Behavioral segments
    completed_surveys = user_data.get('completed_surveys_count', 0)
    
    if completed_surveys == 0:
        segments.append('new_user')
    elif completed_surveys < 5:
        segments.append('beginner')
    elif completed_surveys < 25:
        segments.append('intermediate')
    else:
        segments.append('expert')
    
    # Quality-based segments
    avg_quality = user_data.get('average_quality_score', 0.7)
    
    if avg_quality >= 0.9:
        segments.append('high_quality')
    elif avg_quality >= 0.7:
        segments.append('good_quality')
    
    # Activity-based segments
    days_since_last_activity = user_data.get('days_since_last_activity', 30)
    
    if days_since_last_activity > 30:
        segments.append('inactive')
    elif days_since_last_activity > 7:
        segments.append('dormant')
    else:
        segments.append('active')
    
    return segments


# ── Analytics Logic ─────────────────────────────────────

def calculate_survey_analytics(analytics_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate survey analytics from raw data."""
    total_completed = analytics_data.get('total_completed', 0)
    total_started = analytics_data.get('total_started', 0)
    avg_quality = analytics_data.get('avg_quality', 0.7)
    total_rewards = analytics_data.get('total_rewards', 0)
    
    # Completion rate
    completion_rate = (total_completed / total_started * 100) if total_started > 0 else 0
    
    return {
        'total_completed': total_completed,
        'total_started': total_started,
        'completion_rate': completion_rate,
        'avg_quality': avg_quality,
        'total_rewards': total_rewards,
        'avg_reward_per_completion': (total_rewards / total_completed) if total_completed > 0 else 0
    }


def calculate_user_analytics(analytics_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate user analytics from raw data."""
    new_registrations = analytics_data.get('new_registrations', 0)
    active_users = analytics_data.get('active_users', 0)
    previous_active = analytics_data.get('previous_active_users', 0)
    
    # User retention
    retention_rate = (active_users / previous_active * 100) if previous_active > 0 else 0
    
    return {
        'new_registrations': new_registrations,
        'active_users': active_users,
        'previous_active_users': previous_active,
        'retention_rate': retention_rate,
        'growth_rate': ((active_users - previous_active) / previous_active * 100) if previous_active > 0 else 0
    }


def calculate_reward_analytics(analytics_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate reward analytics from raw data."""
    total_earned = analytics_data.get('total_earned', 0)
    total_paid = analytics_data.get('total_paid', 0)
    pending_payouts = analytics_data.get('pending_payouts', 0)
    
    return {
        'total_earned': total_earned,
        'total_paid': total_paid,
        'pending_payouts': pending_payouts,
        'net_balance': total_earned - total_paid,
        'payout_rate': (total_paid / total_earned * 100) if total_earned > 0 else 0
    }


# ── Validation Logic ─────────────────────────────────────

def validate_survey_responses(responses: List[Dict[str, Any]], survey_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate survey responses against survey requirements."""
    errors = []
    warnings = []
    
    # Check required questions
    required_count = survey_data.get('required_questions_count', 0)
    answered_count = sum(1 for r in responses if r.get('answer'))
    
    if answered_count < required_count:
        errors.append(f"Missing {required_count - answered_count} required answers")
    
    # Validate answer formats
    for response in responses:
        answer = response.get('answer')
        question_type = response.get('question_type', 'text')
        
        if question_type == 'email' and answer:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, str(answer)):
                errors.append(f"Invalid email format: {answer}")
        
        elif question_type == 'number' and answer:
            try:
                float(answer)
            except (ValueError, TypeError):
                errors.append(f"Invalid number format: {answer}")
        
        elif question_type == 'text' and answer:
            if len(str(answer).strip()) < 3:
                warnings.append(f"Very short answer provided")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'completion_percentage': (answered_count / required_count * 100) if required_count > 0 else 100
    }


def validate_profile_data(profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate user profile data."""
    errors = []
    warnings = []
    
    # Email validation
    email = profile_data.get('email', '').strip()
    if email:
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            errors.append("Invalid email format")
    
    # Phone validation
    phone = profile_data.get('phone_number', '').strip()
    if phone:
        # Remove common formatting characters
        clean_phone = re.sub(r'[-\s\(\)]', '', phone)
        if not clean_phone.isdigit() or len(clean_phone) < 10:
            errors.append("Invalid phone number format")
    
    # Date of birth validation
    dob = profile_data.get('date_of_birth')
    if dob:
        # This would need actual date validation in real implementation
        age = 25  # Placeholder
        if age < 13:
            errors.append("User must be at least 13 years old")
        elif age > 120:
            warnings.append("Unusual age - please verify date of birth")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }


def get_postback_response(success: bool) -> str:
    """CPAlead expects '1' on success, '0' on failure."""
    return '1' if success else '0'


def sanitize_subid(subid: str) -> str:
    import re
    return re.sub(r'[^a-zA-Z0-9_\-]', '', str(subid))[:100]


def build_offerwall_embed_url(publisher_id: str, website_id: str,
                               subid: str, currency_name: str = 'Coins') -> str:
    return (
        f"https://cdn.cpalead.com/offerwall/v2/offerwall.min.js"
        f"?pub={publisher_id}&website={website_id}&subid={subid}"
        f"&currency={currency_name}"
    )


def detect_device_type(user_agent: str) -> str:
    ua = (user_agent or '').lower()
    if any(k in ua for k in ['ipad', 'tablet', 'kindle']):
        return 'tablet'
    if any(k in ua for k in ['mobile', 'android', 'iphone', 'ipod']):
        return 'mobile'
    return 'desktop'


def paginate_list(items: list, page: int = 1, page_size: int = 20) -> dict:
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        'count': total,
        'total_pages': max(1, (total + page_size - 1) // page_size),
        'current_page': page,
        'results': items[start:end],
    }
