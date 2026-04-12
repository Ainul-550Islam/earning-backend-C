# kyc/liveness/models.py  ── WORLD #1
"""
Liveness Detection + Deepfake Detection.
2025 must-have: Deepfake attempts every 5 minutes globally (Sumsub data).
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class LivenessCheck(models.Model):
    """
    Active + Passive liveness check results.
    Active: Blink, turn head, smile on command.
    Passive: AI analyzes single photo for liveness signals.
    """
    CHECK_TYPE = [
        ('passive',      'Passive Liveness (Single Photo)'),
        ('active_blink', 'Active — Blink Detection'),
        ('active_turn',  'Active — Head Turn'),
        ('active_smile', 'Active — Smile Detection'),
        ('video',        'Video Liveness (Full Session)'),
    ]
    RESULT = [
        ('pending', 'Pending'),
        ('live',    'Live — Passed'),
        ('spoof',   'Spoof — Failed'),
        ('error',   'Error'),
    ]
    PROVIDER_CHOICES = [
        ('facetec',     'FaceTec 3D'),
        ('iproov',      'iProov'),
        ('jumio',       'Jumio Liveness'),
        ('onfido',      'Onfido Motion'),
        ('aws_rekognition', 'AWS Rekognition'),
        ('deepface',    'DeepFace (Local)'),
        ('mock',        'Mock'),
    ]

    kyc              = models.ForeignKey('kyc.KYC', on_delete=models.CASCADE, related_name='liveness_checks', null=True, blank=True)
    user             = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    check_type       = models.CharField(max_length=20, choices=CHECK_TYPE, default='passive', null=True, blank=True)
    provider         = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='mock', null=True, blank=True)
    result           = models.CharField(max_length=10, choices=RESULT, default='pending', db_index=True, null=True, blank=True)

    # Scores
    liveness_score   = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    confidence       = models.FloatField(default=0.0)

    # Deepfake / Spoof signals
    is_deepfake      = models.BooleanField(default=False, db_index=True)
    is_print_attack  = models.BooleanField(default=False, help_text="Printed photo presented")
    is_screen_attack = models.BooleanField(default=False, help_text="Phone/monitor displayed")
    is_mask_attack   = models.BooleanField(default=False, help_text="3D mask used")
    is_injection_attack = models.BooleanField(default=False, help_text="Virtual camera injection")

    # Media integrity
    media_integrity_score = models.FloatField(default=0.0, help_text="Image/video tampering score")
    texture_score    = models.FloatField(default=0.0)
    depth_score      = models.FloatField(default=0.0, help_text="3D depth cue score")

    # Session data
    session_id       = models.CharField(max_length=100, null=True, blank=True)
    attempts         = models.IntegerField(default=1)
    processing_time_ms = models.IntegerField(default=0)
    error            = models.TextField(blank=True)
    raw_response     = models.JSONField(default=dict, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_liveness_checks'
        verbose_name = 'Liveness Check'
        ordering = ['-created_at']

    def __str__(self):
        return f"Liveness[{self.check_type}:{self.result}] score={self.liveness_score:.2f}"

    @property
    def is_spoof_detected(self):
        return any([self.is_deepfake, self.is_print_attack, self.is_screen_attack,
                    self.is_mask_attack, self.is_injection_attack])

    @property
    def passed(self):
        return self.result == 'live' and not self.is_spoof_detected


class DeepfakeDetectionLog(models.Model):
    """Detailed deepfake detection log — AI model outputs."""
    kyc              = models.ForeignKey('kyc.KYC', on_delete=models.CASCADE, related_name='deepfake_logs', null=True, blank=True)
    liveness_check   = models.ForeignKey(LivenessCheck, on_delete=models.CASCADE, related_name='deepfake_logs', null=True, blank=True)
    model_used       = models.CharField(max_length=100, null=True, blank=True)
    deepfake_probability = models.FloatField(default=0.0)
    is_synthetic     = models.BooleanField(default=False)
    artifacts_detected = models.JSONField(default=list, blank=True, help_text="GAN artifacts, blending boundaries etc.")
    frame_analysis   = models.JSONField(default=list, blank=True, help_text="Per-frame analysis for video")
    raw_output       = models.JSONField(default=dict, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_deepfake_logs'
        verbose_name = 'Deepfake Detection Log'
        ordering = ['-created_at']

    def __str__(self):
        return f"Deepfake[prob={self.deepfake_probability:.2f}] synthetic={self.is_synthetic}"
