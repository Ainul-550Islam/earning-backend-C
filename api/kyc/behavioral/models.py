# kyc/behavioral/models.py  ── WORLD #1
"""
Behavioral Biometrics.
Analyzes HOW users interact (typing speed, mouse movement, scroll patterns).
Detects: bots, account takeover, scripted submissions.

2025 standard used by: Sumsub, BioCatch, Nudata Security.
"""
from django.db import models
from django.conf import settings


class BehavioralSession(models.Model):
    """
    Captures behavioral signals during KYC submission session.
    Data collected by frontend JS SDK and sent to backend.
    """
    RISK_LEVEL = [('low','Low'),('medium','Medium'),('high','High'),('bot','Bot Detected')]

    user               = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='behavioral_sessions', null=True, blank=True)
    kyc                = models.ForeignKey('kyc.KYC', on_delete=models.SET_NULL, null=True, blank=True, related_name='behavioral_sessions')
    session_id         = models.CharField(max_length=100, unique=True, db_index=True, null=True, blank=True)
    tenant             = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)

    # Keystroke dynamics
    avg_typing_speed_wpm = models.FloatField(default=0.0)
    keystroke_intervals  = models.JSONField(default=list, blank=True, help_text="Inter-key timing (ms)")
    backspace_ratio      = models.FloatField(default=0.0, help_text="Backspace / total keys ratio")
    copy_paste_detected  = models.BooleanField(default=False)

    # Mouse / touch dynamics
    avg_mouse_speed      = models.FloatField(default=0.0)
    click_patterns       = models.JSONField(default=list, blank=True)
    scroll_pattern       = models.CharField(max_length=20, null=True, blank=True)
    touch_pressure_avg   = models.FloatField(default=0.0, help_text="Mobile touch pressure")

    # Session timing
    total_session_ms     = models.IntegerField(default=0)
    form_fill_time_ms    = models.IntegerField(default=0)
    idle_time_ms         = models.IntegerField(default=0)
    tab_switches         = models.IntegerField(default=0)
    page_focus_losses    = models.IntegerField(default=0)

    # Device signals
    device_type          = models.CharField(max_length=20, null=True, blank=True)
    user_agent           = models.TextField(blank=True)
    screen_width         = models.IntegerField(default=0)
    screen_height        = models.IntegerField(default=0)
    timezone_offset      = models.IntegerField(default=0)
    language             = models.CharField(max_length=20, null=True, blank=True)

    # Risk assessment
    risk_level           = models.CharField(max_length=10, choices=RISK_LEVEL, default='low', db_index=True, null=True, blank=True)
    bot_probability      = models.FloatField(default=0.0)
    automation_detected  = models.BooleanField(default=False, db_index=True)
    anomaly_score        = models.FloatField(default=0.0)
    anomaly_flags        = models.JSONField(default=list, blank=True)

    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_behavioral_sessions'
        verbose_name = 'Behavioral Session'
        ordering = ['-created_at']

    def __str__(self):
        return f"Behavioral[{self.risk_level}] {self.user} bot_prob={self.bot_probability:.2f}"

    def analyze(self):
        """
        Analyze collected behavioral data for anomalies.
        Rule-based heuristics — replace with ML model in production.
        """
        flags = []
        score = 0.0

        # Too fast form fill (bot indicator)
        if self.form_fill_time_ms < 5000:
            flags.append('form_fill_too_fast')
            score += 0.4

        # Copy-paste entire fields (bot indicator)
        if self.copy_paste_detected:
            flags.append('copy_paste_detected')
            score += 0.3

        # No mouse movement
        if self.avg_mouse_speed == 0 and self.device_type == 'desktop':
            flags.append('no_mouse_movement')
            score += 0.25

        # Tab switching (user looking up data or using autofill)
        if self.tab_switches > 10:
            flags.append('excessive_tab_switching')
            score += 0.15

        # Uniform typing speed (bots type at constant speed)
        if self.keystroke_intervals:
            variance = self._variance(self.keystroke_intervals)
            if variance < 50:   # Very uniform
                flags.append('uniform_typing_speed')
                score += 0.3

        self.anomaly_score  = min(score, 1.0)
        self.anomaly_flags  = flags
        self.bot_probability = self.anomaly_score
        self.automation_detected = score > 0.6

        if self.bot_probability > 0.8:    self.risk_level = 'bot'
        elif self.bot_probability > 0.5:  self.risk_level = 'high'
        elif self.bot_probability > 0.25: self.risk_level = 'medium'
        else:                             self.risk_level = 'low'

        self.save()
        return self.risk_level

    @staticmethod
    def _variance(values: list) -> float:
        if not values or len(values) < 2: return 999.0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)
