# kyc/video_kyc/models.py  ── WORLD #1
"""
Video KYC (vKYC).
Live video call with agent + AI assistance.
Required by: Bangladesh Bank for digital banking accounts (BB Circular 2022).
Technology: WebRTC (peer-to-peer video) + Django Channels (WebSocket).

Providers: Jumio, IDnow VideoIdent, custom WebRTC.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
import secrets


class VideoKYCSession(models.Model):
    """Live video KYC session."""
    STATUS = [
        ('scheduled',  'Scheduled'),
        ('waiting',    'Waiting for Agent'),
        ('in_progress','In Progress'),
        ('completed',  'Completed'),
        ('cancelled',  'Cancelled'),
        ('timeout',    'Timed Out'),
        ('failed',     'Failed'),
    ]
    OUTCOME = [
        ('approved',         'Approved — Verified'),
        ('rejected',         'Rejected — Failed verification'),
        ('inconclusive',     'Inconclusive — Retry needed'),
        ('technical_failure','Technical failure'),
        ('pending',          'Pending review'),
    ]

    user             = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='video_kyc_sessions', null=True, blank=True)
    kyc              = models.ForeignKey('kyc.KYC', on_delete=models.SET_NULL, null=True, blank=True, related_name='video_sessions')
    tenant           = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    agent            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_video_sessions')

    # Session identifiers
    session_token    = models.CharField(max_length=64, unique=True, default=secrets.token_hex, null=True, blank=True)
    room_id          = models.CharField(max_length=100, blank=True, db_index=True, null=True)

    # Status
    status           = models.CharField(max_length=20, choices=STATUS, default='scheduled', db_index=True, null=True, blank=True)
    outcome          = models.CharField(max_length=25, choices=OUTCOME, null=True, blank=True)

    # Timing
    scheduled_at     = models.DateTimeField(null=True, blank=True)
    started_at       = models.DateTimeField(null=True, blank=True)
    ended_at         = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)

    # AI assistance flags
    face_verified_during_call = models.BooleanField(default=False)
    document_captured         = models.BooleanField(default=False)
    liveness_confirmed        = models.BooleanField(default=False)

    # Recording (for compliance)
    recording_url    = models.URLField(null=True, blank=True)
    recording_key    = models.CharField(max_length=200, blank=True, help_text="Encrypted storage key", null=True)

    # Agent notes
    agent_notes      = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)

    # Quality metrics
    video_quality_score  = models.FloatField(default=0.0)
    audio_quality_score  = models.FloatField(default=0.0)
    connection_quality   = models.CharField(max_length=10, null=True, blank=True)

    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_video_sessions'
        verbose_name = 'Video KYC Session'
        ordering = ['-created_at']

    def __str__(self):
        return f"VideoKYC[{self.status}] {self.user} - {self.outcome or 'pending'}"

    def start(self, agent=None):
        self.status     = 'in_progress'
        self.started_at = timezone.now()
        if agent: self.agent = agent
        self.save()

    def complete(self, outcome: str, agent_notes: str = ''):
        self.status      = 'completed'
        self.outcome     = outcome
        self.ended_at    = timezone.now()
        self.agent_notes = agent_notes
        if self.started_at:
            self.duration_seconds = int((self.ended_at - self.started_at).total_seconds())

        # Update KYC if approved
        if outcome == 'approved' and self.kyc:
            self.kyc.approve(reviewed_by=self.agent)
            self.face_verified_during_call = True

        self.save()

    def cancel(self, reason: str = ''):
        self.status = 'cancelled'
        self.rejection_reason = reason
        self.ended_at = timezone.now()
        self.save()

    @property
    def join_url(self):
        """Frontend URL to join the video session."""
        base = getattr(settings, 'FRONTEND_URL', 'https://app.yourdomain.com')
        return f"{base}/kyc/video/{self.session_token}"

    @property
    def agent_url(self):
        """Agent dashboard URL."""
        base = getattr(settings, 'ADMIN_URL', 'https://admin.yourdomain.com')
        return f"{base}/kyc/video/agent/{self.session_token}"


class VideoKYCQueue(models.Model):
    """Queue for pending video KYC sessions waiting for an agent."""
    session      = models.OneToOneField(VideoKYCSession, on_delete=models.CASCADE, related_name='queue_entry', null=True, blank=True)
    priority     = models.IntegerField(default=0, db_index=True, help_text="Higher = served first")
    wait_reason  = models.CharField(max_length=100, null=True, blank=True)
    assigned_to  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_at  = models.DateTimeField(null=True, blank=True)
    entered_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_video_queue'
        verbose_name = 'Video KYC Queue'
        ordering = ['-priority', 'entered_at']

    def __str__(self):
        return f"Queue[priority={self.priority}] {self.session.user}"
