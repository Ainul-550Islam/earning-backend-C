# api/cms/models_new/quiz.py
"""
Personality Quiz Builder — CMS owns this.
CPAlead personality quiz: "Which NBA Star Are You?" etc.
Users answer → get result → publisher earns.
Rule: এক কাজের জন্য একটাই মালিক।
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class QuizTemplate(models.Model):
    """A personality quiz (CPAlead co-reg quiz style)."""
    QUIZ_TYPES = [
        ('personality', 'Personality Quiz'),
        ('trivia',      'Trivia / Knowledge Quiz'),
        ('survey',      'Survey'),
        ('poll',        'Quick Poll'),
    ]
    uuid        = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title       = models.CharField(max_length=300)
    slug        = models.SlugField(max_length=300, unique=True)
    description = models.TextField(blank=True)
    quiz_type   = models.CharField(max_length=20, choices=QUIZ_TYPES, default='personality')
    thumbnail   = models.URLField(blank=True)
    # CPAlead integration
    cpalead_offer_id = models.CharField(max_length=100, blank=True,
                                         help_text="CPAlead offer_id for this quiz")
    payout_usd  = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    # Display
    is_active   = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False)
    show_results_immediately = models.BooleanField(default=True)
    # Stats
    total_attempts   = models.PositiveIntegerField(default=0)
    total_completions = models.PositiveIntegerField(default=0)
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Quiz Template"
        ordering = ['-is_featured', '-created_at']

    def __str__(self):
        return self.title

    @property
    def completion_rate(self):
        if not self.total_attempts:
            return 0
        return round(self.total_completions / self.total_attempts * 100, 1)


class QuizQuestion(models.Model):
    """A single question in a quiz."""
    QUESTION_TYPES = [
        ('single',   'Single Choice'),
        ('multiple', 'Multiple Choice'),
        ('text',     'Text Input'),
        ('scale',    'Rating Scale (1-5)'),
    ]
    quiz        = models.ForeignKey(QuizTemplate, on_delete=models.CASCADE,
                                    related_name='questions')
    text        = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='single')
    order       = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    image_url   = models.URLField(blank=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Quiz Question"
        ordering = ['order']
        unique_together = [['quiz', 'order']]

    def __str__(self):
        return f"Q{self.order}: {self.text[:60]}"


class QuizAnswer(models.Model):
    """Answer choice for a quiz question."""
    question    = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE,
                                    related_name='answers')
    text        = models.CharField(max_length=500)
    # Personality scoring: maps to personality result
    personality_tag = models.CharField(max_length=50, blank=True)
    score_weight    = models.IntegerField(default=1)
    image_url       = models.URLField(blank=True)
    order           = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "cms"
        verbose_name = "Quiz Answer"
        ordering = ['order']

    def __str__(self):
        return f"{self.text[:50]}"


class QuizResult(models.Model):
    """Personality result shown after completing quiz."""
    quiz        = models.ForeignKey(QuizTemplate, on_delete=models.CASCADE,
                                    related_name='results')
    title       = models.CharField(max_length=200)
    description = models.TextField()
    image_url   = models.URLField(blank=True)
    personality_tag = models.CharField(max_length=50, blank=True,
                                        help_text="Match tag from answers")
    share_text  = models.TextField(blank=True, help_text="Social share text")
    min_score   = models.IntegerField(default=0)
    max_score   = models.IntegerField(default=100)

    class Meta:
        app_label = "cms"
        verbose_name = "Quiz Result"

    def __str__(self):
        return f"{self.quiz.title} → {self.title}"


class QuizAttempt(models.Model):
    """A user's quiz session."""
    uuid        = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    quiz        = models.ForeignKey(QuizTemplate, on_delete=models.CASCADE,
                                    related_name='attempts')
    user        = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='quiz_attempts')
    session_key = models.CharField(max_length=100, blank=True)
    result      = models.ForeignKey(QuizResult, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='attempts')
    answers_data    = models.JSONField(default=dict)  # {question_id: answer_id}
    total_score     = models.IntegerField(default=0)
    is_completed    = models.BooleanField(default=False, db_index=True)
    completed_at    = models.DateTimeField(null=True, blank=True)
    # CPAlead tracking
    cpalead_lead_id = models.CharField(max_length=200, blank=True)
    reward_earned   = models.BooleanField(default=False)
    reward_coins    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Quiz Attempt"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['quiz', 'is_completed', 'created_at']),
            models.Index(fields=['user', 'quiz']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        return f"{self.quiz.title} by {self.user or self.session_key}"

    def complete(self, result: QuizResult, total_score: int):
        self.result = result
        self.total_score = total_score
        self.is_completed = True
        self.completed_at = timezone.now()
        self.save(update_fields=['result', 'total_score', 'is_completed', 'completed_at'])
        # Update quiz stats
        QuizTemplate.objects.filter(pk=self.quiz_id).update(
            total_completions=models.F('total_completions') + 1
        )
