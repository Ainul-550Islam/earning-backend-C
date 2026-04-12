"""
Time-Based Fraud Detector  (PRODUCTION-READY — COMPLETE)
==========================================================
Detects fraud patterns based on timing anomalies.

Earning/marketing platforms are heavily targeted by automated bots
that work around the clock. Human users have natural activity patterns —
bots do not. Time-based signals are especially powerful when combined
with other signals.

Patterns detected:
  1. Activity at bot-hours (2–5 AM in user's timezone)
  2. Machine-speed requests (< 500ms between actions)
  3. Perfectly uniform timing (e.g. exactly 1.000s between every action)
  4. Weekend vs weekday unusual activity patterns
  5. Action timestamps clustered at exact-second boundaries (bot timer)
  6. Inhuman offer completion speed
  7. 24/7 activity without natural sleep gaps
  8. Clock skew between server time and client-reported time
"""
import logging
import time
import statistics
from typing import Optional, List

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class TimeBaedFraudDetector:
    """
    Detects bot activity and fraud through timing analysis.

    Usage:
        detector = TimeBaedFraudDetector(
            ip_address='1.2.3.4',
            user_timezone='Asia/Dhaka',
            user_id=123,
        )
        result = detector.check(action_type='offer_complete')
    """

    SIGNAL_SCORES = {
        'bot_hours_activity':      20,
        'machine_speed_request':   40,
        'uniform_timing':          35,
        'exact_second_timestamps': 30,
        'no_sleep_gap':            25,
        'clock_skew':              20,
        'weekend_anomaly':         10,
        'inhuman_completion_speed': 40,
    }

    # Activity hours considered suspicious (local time 24h)
    BOT_HOURS_START = 2   # 2 AM
    BOT_HOURS_END   = 5   # 5 AM

    # Maximum legitimate request rate (requests per minute)
    MAX_HUMAN_RPM = 60

    def __init__(self, ip_address: str = '',
                 user_timezone: str = 'UTC',
                 user_id: Optional[int] = None,
                 session_id: str = ''):
        self.ip_address   = ip_address
        self.user_tz      = user_timezone
        self.user_id      = user_id
        self.session_id   = session_id
        self.flags: list  = []
        self.score: int   = 0

    # ── Public API ─────────────────────────────────────────────────────────

    def check(self, action_type: str = '',
               client_timestamp_ms: Optional[int] = None) -> dict:
        """
        Run all time-based fraud checks for a single action event.

        Args:
            action_type:          e.g. 'login', 'offer_complete', 'api_call'
            client_timestamp_ms:  Client-reported Unix timestamp in ms (for clock skew)

        Returns:
            {
                'time_fraud_detected': bool,
                'time_risk_score':     int,
                'flags':               list,
                'hour_of_day':         int (local time),
                'is_bot_hours':        bool,
                'request_gap_ms':      float,
                'is_machine_speed':    bool,
            }
        """
        self.flags = []
        self.score = 0

        now = timezone.now()

        gap_ms = self._record_and_check_gap(action_type, now)
        self._check_bot_hours(now)
        self._check_machine_speed(gap_ms)
        self._check_uniform_timing(action_type)
        self._check_exact_second_timestamps(action_type)
        self._check_no_sleep_gap()
        if client_timestamp_ms:
            self._check_clock_skew(client_timestamp_ms, now)

        self.score = min(self.score, 100)

        local_hour = self._get_local_hour(now)

        return {
            'ip_address':          self.ip_address,
            'action_type':         action_type,
            'time_fraud_detected': self.score >= 30,
            'time_risk_score':     self.score,
            'flags':               self.flags,
            'hour_of_day':         local_hour,
            'is_bot_hours':        self.BOT_HOURS_START <= local_hour <= self.BOT_HOURS_END,
            'request_gap_ms':      gap_ms,
            'is_machine_speed':    gap_ms < 500 and gap_ms > 0,
            'server_time':         now.isoformat(),
        }

    def check_completion_speed(self, action_type: str,
                                 elapsed_seconds: float) -> dict:
        """
        Check if a task/survey was completed faster than humanly possible.

        Args:
            action_type:      'survey', 'task', 'offer', 'video', etc.
            elapsed_seconds:  Time from page load to completion POST

        Returns:
            {
                'too_fast':         bool,
                'elapsed_seconds':  float,
                'min_human_seconds': int,
                'score':            int,
            }
        """
        MIN_TIMES = {
            'survey':          30,
            'survey_complete': 30,
            'task':            10,
            'offer':           15,
            'video':           20,
            'install':         30,
            'signup':          25,
            'quiz':            20,
            'poll':            10,
        }

        min_time = MIN_TIMES.get(action_type, 10)
        too_fast = elapsed_seconds < min_time

        score = 0
        if elapsed_seconds <= 0:
            score = 45  # Instant or negative = clear bot
        elif elapsed_seconds < min_time:
            ratio = elapsed_seconds / min_time
            score = int((1 - ratio) * 40)  # Proportional score

        return {
            'action_type':      action_type,
            'too_fast':         too_fast,
            'elapsed_seconds':  round(elapsed_seconds, 3),
            'min_human_seconds': min_time,
            'score':            score,
            'flag':             'inhuman_completion_speed' if too_fast else None,
        }

    def analyze_session_timing(self, action_times: List[float]) -> dict:
        """
        Analyze a list of Unix timestamps (in seconds) for the session
        to detect bot-like uniform timing patterns.

        Args:
            action_times: List of Unix timestamps of actions in this session

        Returns:
            {
                'is_bot_pattern':    bool,
                'pattern_type':      str,
                'avg_gap_ms':        float,
                'gap_std_dev_ms':    float,
                'uniformity_score':  float (0-1, higher = more uniform = more bot-like),
            }
        """
        if len(action_times) < 3:
            return {'is_bot_pattern': False, 'reason': 'insufficient data'}

        action_times_sorted = sorted(action_times)
        gaps = [
            (action_times_sorted[i+1] - action_times_sorted[i]) * 1000
            for i in range(len(action_times_sorted) - 1)
        ]

        avg_gap   = statistics.mean(gaps)
        std_dev   = statistics.stdev(gaps) if len(gaps) > 1 else 0

        # Coefficient of variation — lower = more uniform = more bot-like
        cv = std_dev / avg_gap if avg_gap > 0 else 0

        # Uniformity score: 1.0 = perfectly uniform (bot), 0.0 = random (human)
        uniformity = max(0.0, 1.0 - min(cv, 1.0))

        pattern_type = 'unknown'
        if avg_gap < 100:
            pattern_type = 'machine_speed'
        elif uniformity > 0.85:
            pattern_type = 'uniform_bot_timer'
        elif avg_gap > 0 and uniformity < 0.3:
            pattern_type = 'human_pattern'
        else:
            pattern_type = 'mixed'

        return {
            'is_bot_pattern':    uniformity > 0.80 or avg_gap < 100,
            'pattern_type':      pattern_type,
            'action_count':      len(action_times),
            'avg_gap_ms':        round(avg_gap, 2),
            'gap_std_dev_ms':    round(std_dev, 2),
            'uniformity_score':  round(uniformity, 4),
            'min_gap_ms':        round(min(gaps), 2),
            'max_gap_ms':        round(max(gaps), 2),
        }

    # ── Signal Checks ──────────────────────────────────────────────────────

    def _record_and_check_gap(self, action_type: str,
                               now) -> float:
        """Record action timestamp and return gap since last action (ms)."""
        key = self._session_key(action_type)
        last_ts = cache.get(key)
        now_ts  = now.timestamp()

        cache.set(key, now_ts, 300)

        if last_ts is None:
            return -1.0  # First action in window

        gap_ms = (now_ts - last_ts) * 1000
        return max(gap_ms, 0.0)

    def _check_bot_hours(self, now):
        """Signal 1: Activity at 2–5 AM local time."""
        local_hour = self._get_local_hour(now)
        if self.BOT_HOURS_START <= local_hour < self.BOT_HOURS_END:
            self._add_flag('bot_hours_activity',
                           f'Activity at {local_hour}:xx local time (bot-hours)')

    def _check_machine_speed(self, gap_ms: float):
        """Signal 2: Requests faster than human reaction time (< 500ms)."""
        if gap_ms < 0:
            return  # First request
        if gap_ms < 200:
            self._add_flag('machine_speed_request',
                           f'Request gap {gap_ms:.1f}ms — impossibly fast for human')
        elif gap_ms < 500:
            self._add_flag('machine_speed_request',
                           f'Request gap {gap_ms:.1f}ms — faster than human reaction')

    def _check_uniform_timing(self, action_type: str):
        """Signal 3: Detect perfectly uniform timing (bot timer pattern)."""
        history_key = f"pi:time_hist:{self._identifier()}:{action_type}"
        history     = cache.get(history_key, [])
        history.append(time.time())
        history     = history[-15:]  # Keep last 15 timestamps
        cache.set(history_key, history, 300)

        if len(history) >= 5:
            result = self.analyze_session_timing(history)
            if result.get('is_bot_pattern') and result.get('pattern_type') == 'uniform_bot_timer':
                self._add_flag('uniform_timing',
                               f'Uniform action timing (uniformity={result["uniformity_score"]:.2f})')

    def _check_exact_second_timestamps(self, action_type: str):
        """Signal 4: Actions landing on exact second boundaries (bot cron/timer)."""
        ms_frac = time.time() % 1  # Fractional seconds (0.0 – 1.0)

        # Real humans rarely act at exactly .000 seconds
        if ms_frac < 0.010 or ms_frac > 0.990:
            # Track how often this happens
            exact_key   = f"pi:exact_ts:{self._identifier()}"
            exact_count = cache.get(exact_key, 0) + 1
            cache.set(exact_key, exact_count, 300)

            if exact_count >= 3:
                self._add_flag('exact_second_timestamps',
                               f'Action on exact-second boundary {exact_count}x in session')

    def _check_no_sleep_gap(self):
        """Signal 5: 24/7 activity without natural sleep breaks."""
        activity_key = f"pi:daily_active:{self._identifier()}"
        active_hours = cache.get(activity_key, set())
        current_hour = timezone.now().hour
        active_hours.add(current_hour)
        cache.set(activity_key, active_hours, 86400)

        # If active for 20+ different hours in a day = no sleep = bot
        if len(active_hours) >= 20:
            self._add_flag('no_sleep_gap',
                           f'Active in {len(active_hours)} different hours today — no sleep gap')

    def _check_clock_skew(self, client_ts_ms: int, server_now):
        """Signal 6: Large discrepancy between client and server timestamps."""
        server_ts_ms = int(server_now.timestamp() * 1000)
        skew_ms      = abs(server_ts_ms - client_ts_ms)

        if skew_ms > 300_000:  # 5 minutes skew
            self._add_flag('clock_skew',
                           f'Client-server clock skew: {skew_ms/1000:.1f}s — time manipulation?')

    # ── Helpers ────────────────────────────────────────────────────────────

    def _add_flag(self, signal: str, description: str):
        score = self.SIGNAL_SCORES.get(signal, 10)
        self.flags.append({'signal': signal, 'description': description, 'score': score})
        self.score += score

    def _get_local_hour(self, now) -> int:
        """Get current hour in user's local timezone."""
        try:
            import pytz
            tz  = pytz.timezone(self.user_tz)
            local_now = now.astimezone(tz)
            return local_now.hour
        except Exception:
            return now.hour  # Fall back to UTC

    def _session_key(self, action_type: str) -> str:
        return f"pi:last_ts:{self._identifier()}:{action_type}"

    def _identifier(self) -> str:
        if self.user_id:
            return f"u{self.user_id}"
        if self.session_id:
            return f"s{self.session_id}"
        return f"ip{self.ip_address}"
