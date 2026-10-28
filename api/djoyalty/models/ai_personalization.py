# api/djoyalty/models/ai_personalization.py
"""
Djoyalty AI & Personalization Models -- 2025 World-class।
AI Recommendations, Churn Prediction, Dynamic Offers,
Behavioral Scoring, Predictive Analytics।

World reference: Kognitiv Inspire AI, Antavo AI Loyalty Cloud,
Starbucks AI personalization, Ulta Beauty Ultamate Rewards।
Research: 2025 trend -- AI personalization = 35% higher redemption rates।
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..managers import ActiveManager

logger = logging.getLogger(__name__)


class CustomerAIProfile(models.Model):
    """
    AI-computed customer profile -- behavioral scoring।
    Real-time ML analysis এর results store করে।
    World: Kognitiv Pulse (95%+ churn accuracy), Starbucks AI।
    """
    customer = models.OneToOneField(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='ai_profile',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='ai_profiles',
    )

    # RFM Scores (Recency, Frequency, Monetary)
    recency_score = models.PositiveIntegerField(
        default=0, verbose_name='Recency Score (1-5)',
        help_text='5 = purchased very recently',
    )
    frequency_score = models.PositiveIntegerField(
        default=0, verbose_name='Frequency Score (1-5)',
        help_text='5 = very frequent buyer',
    )
    monetary_score = models.PositiveIntegerField(
        default=0, verbose_name='Monetary Score (1-5)',
        help_text='5 = high spender',
    )
    rfm_total = models.PositiveIntegerField(default=0, verbose_name='RFM Total (3-15)')
    rfm_segment = models.CharField(
        max_length=30,
        choices=[
            ('champion', 'Champion'),
            ('loyal', 'Loyal Customer'),
            ('potential_loyal', 'Potential Loyalist'),
            ('new', 'New Customer'),
            ('promising', 'Promising'),
            ('need_attention', 'Need Attention'),
            ('about_to_sleep', 'About to Sleep'),
            ('at_risk', 'At Risk'),
            ('cant_lose', "Can't Lose Them"),
            ('hibernating', 'Hibernating'),
            ('lost', 'Lost'),
        ],
        default='new',
        verbose_name='RFM Segment',
    )

    # Churn Prediction
    churn_probability = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0'),
        verbose_name='Churn Probability (0-1)',
        help_text='0 = loyal, 1 = about to leave',
    )
    churn_risk_level = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low Risk'),
            ('medium', 'Medium Risk'),
            ('high', 'High Risk'),
            ('critical', 'Critical -- Likely Churning'),
        ],
        default='low',
        verbose_name='Churn Risk',
    )
    days_since_last_purchase = models.PositiveIntegerField(default=0)
    days_since_last_login = models.PositiveIntegerField(default=0)

    # CLV (Customer Lifetime Value)
    predicted_clv_30d = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Predicted CLV -- 30 days',
    )
    predicted_clv_90d = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Predicted CLV -- 90 days',
    )
    predicted_clv_1y = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Predicted CLV -- 1 year',
    )
    actual_clv = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Actual CLV to Date',
    )

    # Behavioral Patterns
    preferred_category = models.CharField(max_length=100, null=True, blank=True)
    preferred_channel = models.CharField(
        max_length=20,
        choices=[('app', 'App'), ('web', 'Web'), ('in_store', 'In-Store'), ('unknown', 'Unknown')],
        default='unknown',
    )
    avg_order_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Average Order Value',
    )
    purchase_frequency_days = models.PositiveIntegerField(
        default=0, verbose_name='Avg Days Between Purchases',
    )
    best_day_of_week = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Best Purchase Day (0=Mon, 6=Sun)',
    )
    best_hour_of_day = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Best Purchase Hour (0-23)',
    )

    # Engagement Score
    engagement_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        verbose_name='Overall Engagement Score (0-100)',
    )

    # Metadata
    last_computed_at = models.DateTimeField(null=True, blank=True, verbose_name='Last AI Compute')
    model_version = models.CharField(max_length=20, default='1.0', verbose_name='AI Model Version')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Customer AI Profile'
        verbose_name_plural = 'Customer AI Profiles'
        indexes = [
            models.Index(fields=['churn_risk_level']),
            models.Index(fields=['rfm_segment']),
            models.Index(fields=['engagement_score']),
        ]

    def __str__(self):
        return f'AIProfile({self.customer.code}: RFM={self.rfm_segment}, churn={self.churn_probability})'


class PersonalizedOffer(models.Model):
    """
    AI-generated personalized offer for a specific customer।
    World: Sephora AI recommendations, Starbucks personalized promotions।
    2025 research: personalized offers = 35% higher redemption।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='personalized_offers',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='personalized_offers',
    )

    title = models.CharField(max_length=200, verbose_name='Offer Title')
    description = models.TextField(null=True, blank=True)

    offer_type = models.CharField(
        max_length=30,
        choices=[
            ('bonus_points', 'Bonus Points'),
            ('points_multiplier', 'Points Multiplier'),
            ('discount', 'Discount'),
            ('free_product', 'Free Product'),
            ('free_shipping', 'Free Shipping'),
            ('cashback', 'Cashback'),
            ('voucher', 'Voucher'),
            ('tier_accelerator', 'Tier Points Accelerator'),
            ('win_back', 'Win-Back Offer'),
            ('birthday', 'Birthday Special'),
        ],
        default='bonus_points',
        verbose_name='Offer Type',
    )

    # Offer value
    points_bonus = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )
    multiplier = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('1'),
    )
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
    )

    # AI Metadata
    ai_generated = models.BooleanField(default=True, verbose_name='AI Generated')
    confidence_score = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0'),
        verbose_name='AI Confidence (0-1)',
    )
    reason = models.CharField(
        max_length=200, null=True, blank=True,
        verbose_name='AI Reason',
        help_text='Why this offer was generated',
    )
    trigger = models.CharField(
        max_length=30,
        choices=[
            ('churn_risk', 'Churn Risk Detected'),
            ('rfm_segment', 'RFM Segment Based'),
            ('birthday', 'Upcoming Birthday'),
            ('anniversary', 'Membership Anniversary'),
            ('win_back', 'Win-Back Campaign'),
            ('behavior', 'Behavioral Pattern'),
            ('manual', 'Manual'),
        ],
        default='behavior',
        verbose_name='Offer Trigger',
    )

    # Validity
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(verbose_name='Valid Until')

    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('claimed', 'Claimed'),
            ('expired', 'Expired'),
            ('dismissed', 'Dismissed'),
        ],
        default='active',
    )
    viewed_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)

    # Linked campaign
    campaign = models.ForeignKey(
        'djoyalty.LoyaltyCampaign', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='personalized_offers',
    )

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Personalized Offer'
        verbose_name_plural = 'Personalized Offers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['valid_until', 'status']),
            models.Index(fields=['trigger']),
        ]

    def __str__(self):
        return f'PersonalizedOffer({self.customer.code}: {self.title} [{self.status}])'


class AIRecommendation(models.Model):
    """
    AI product/reward recommendation for customer।
    World: Amazon Prime recommendations, Netflix-style loyalty suggestions।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='ai_recommendations',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='ai_recommendations',
    )

    recommendation_type = models.CharField(
        max_length=30,
        choices=[
            ('reward', 'Reward to Redeem'),
            ('campaign', 'Campaign to Join'),
            ('challenge', 'Challenge to Try'),
            ('voucher', 'Voucher to Use'),
            ('tier_upgrade', 'Tier Upgrade Action'),
            ('streak', 'Start/Continue Streak'),
            ('referral', 'Refer a Friend'),
        ],
        verbose_name='Recommendation Type',
    )

    # What is recommended
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    action_url = models.CharField(max_length=500, null=True, blank=True, verbose_name='Deep Link / Action URL')

    # Linked objects (optional)
    linked_campaign_id = models.PositiveIntegerField(null=True, blank=True)
    linked_challenge_id = models.PositiveIntegerField(null=True, blank=True)
    linked_voucher_id = models.PositiveIntegerField(null=True, blank=True)

    # AI Scores
    relevance_score = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0'),
        verbose_name='Relevance Score (0-1)',
    )
    urgency_score = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0'),
        verbose_name='Urgency Score (0-1)',
    )

    # Display
    position = models.PositiveIntegerField(default=1, verbose_name='Display Position (1=top)')
    is_shown = models.BooleanField(default=False)
    is_clicked = models.BooleanField(default=False)
    shown_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)

    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'AI Recommendation'
        verbose_name_plural = 'AI Recommendations'
        ordering = ['position', '-relevance_score']
        indexes = [
            models.Index(fields=['customer', 'recommendation_type']),
            models.Index(fields=['expires_at', 'is_shown']),
        ]

    def __str__(self):
        return f'AIRec({self.customer.code}: {self.recommendation_type} -- {self.title})'


class ChurnAlert(models.Model):
    """
    AI-detected churn alert -- automatic action trigger।
    World: Kognitiv Pulse 95%+ accuracy churn detection।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='churn_alerts',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='churn_alerts',
    )

    risk_level = models.CharField(
        max_length=10,
        choices=[
            ('medium', 'Medium Risk'),
            ('high', 'High Risk'),
            ('critical', 'Critical -- Likely Churning'),
        ],
        verbose_name='Risk Level',
    )
    churn_probability = models.DecimalField(max_digits=5, decimal_places=4)
    predicted_churn_date = models.DateField(null=True, blank=True)

    # Signals that triggered the alert
    signals = models.JSONField(
        default=list,
        verbose_name='Churn Signals',
        help_text='List of behavioral signals: e.g. ["no_purchase_30d", "login_frequency_dropped"]',
    )

    # Action taken
    action_taken = models.CharField(
        max_length=30,
        choices=[
            ('none', 'No Action Yet'),
            ('offer_sent', 'Personalized Offer Sent'),
            ('notification_sent', 'Win-Back Notification Sent'),
            ('manual_review', 'Flagged for Manual Review'),
            ('resolved', 'Customer Re-engaged'),
        ],
        default='none',
    )
    offer = models.ForeignKey(
        PersonalizedOffer, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='churn_alerts',
    )

    detected_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Churn Alert'
        verbose_name_plural = 'Churn Alerts'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['customer', 'is_resolved']),
            models.Index(fields=['risk_level', 'is_resolved']),
        ]

    def __str__(self):
        return f'ChurnAlert({self.customer.code}: {self.risk_level} p={self.churn_probability})'
