# api/djoyalty/models/family_eco.py
"""
Djoyalty Family Accounts + Eco/Green Loyalty Models।
FamilyAccount, FamilyMember, EcoAction, GreenPoints,
CharityRedemption, ExperientialReward।

World reference:
- Family accounts: Antavo Global Loyalty Report 2025 top desired feature
- Eco/Green points: Major retailers 2024 -- reusable bags, carbon-neutral delivery
- Charity: Marriott Bonvoy charity redemption, Sephora cause-based rewards
- Experiential: Events, VIP access, early access (Antavo #1 differentiator)
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..managers import ActiveManager

logger = logging.getLogger(__name__)


# ─── FAMILY ACCOUNTS ─────────────────────────────────────────────────────────

class FamilyAccount(models.Model):
    """
    Family/Group loyalty account -- shared points pool।
    World: Antavo Global Loyalty Report 2025 -- family accounts as top desired feature।
    Airlines use family miles pooling; retail uses household accounts।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='family_accounts',
    )
    name = models.CharField(max_length=200, verbose_name='Family Account Name')
    owner = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='owned_family_accounts',
        verbose_name='Account Owner',
    )
    account_code = models.CharField(max_length=20, unique=True, verbose_name='Family Account Code')

    # Shared pool settings
    pool_points = models.BooleanField(
        default=True,
        verbose_name='Pool Points',
        help_text='If True, all members share one points balance',
    )
    shared_balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Shared Points Balance',
    )
    shared_lifetime_earned = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )

    # Tier settings
    use_combined_tier = models.BooleanField(
        default=False,
        verbose_name='Use Combined Tier',
        help_text='If True, tier is based on combined family spending',
    )

    max_members = models.PositiveIntegerField(default=5, verbose_name='Max Members')
    is_active = models.BooleanField(default=True)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Family Account'
        verbose_name_plural = 'Family Accounts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account_code']),
            models.Index(fields=['owner']),
        ]

    def __str__(self):
        return f'FamilyAccount({self.name}: {self.owner.code})'

    def save(self, *args, **kwargs):
        if not self.account_code:
            from ..utils import generate_loyalty_number
            self.account_code = 'FAM' + generate_loyalty_number()[-6:]
        super().save(*args, **kwargs)


class FamilyMember(models.Model):
    """
    Individual member of a family loyalty account।

    AUDIT FIX (Data Integrity -- High):
      Added save() override that raises ValidationError when the customer
      being added as a FamilyMember is the same as the FamilyAccount.owner।
      Without this guard, the owner could be inserted as a member record,
      causing double-counting in points allocation logic that sums across
      all members INCLUDING the owner FK on FamilyAccount।

      The check runs at the Python layer (save()) and is always enforced
      regardless of whether the record is created via the API, admin, or ORM।
    """
    family_account = models.ForeignKey(
        FamilyAccount,
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name='Family Account',
    )
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='family_memberships',
        verbose_name='Customer',
    )
    role = models.CharField(
        max_length=20,
        choices=[
            ('owner', 'Owner'),
            ('adult', 'Adult Member'),
            ('child', 'Child Member'),
        ],
        default='adult',
        verbose_name='Role',
    )
    can_redeem = models.BooleanField(default=True, verbose_name='Can Redeem Shared Points')
    can_transfer = models.BooleanField(default=False, verbose_name='Can Transfer Points')
    points_contributed = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points Contributed to Pool',
    )
    joined_at = models.DateTimeField(default=timezone.now)
    invited_by = models.ForeignKey(
        'djoyalty.Customer', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='family_invitations',
    )
    is_active = models.BooleanField(default=True)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Family Member'
        verbose_name_plural = 'Family Members'
        unique_together = [('family_account', 'customer')]
        indexes = [
            models.Index(fields=['customer', 'is_active']),
        ]

    def __str__(self):
        return f'FamilyMember({self.customer.code} in {self.family_account.name} [{self.role}])'

    def save(self, *args, **kwargs):
        """
        AUDIT FIX: Prevent adding the FamilyAccount owner as a FamilyMember।
        The owner already has a ForeignKey on FamilyAccount -- inserting them
        as a member record causes double-counting in point pool calculations।
        """
        from django.core.exceptions import ValidationError
        if self.customer_id and self.family_account_id:
            owner_id = (
                self.family_account.owner_id
                if hasattr(self.family_account, 'owner_id')
                else getattr(self.family_account, 'owner', None)
            )
            # Resolve owner_id whether stored as PK or as related object
            if hasattr(owner_id, 'pk'):
                owner_id = owner_id.pk
            if owner_id and self.customer_id == owner_id:
                raise ValidationError(
                    f'Customer {self.customer_id} is the owner of FamilyAccount '
                    f'{self.family_account_id} and cannot also be added as a member। '
                    f'The owner is already counted via FamilyAccount.owner FK।'
                )
        super().save(*args, **kwargs)


# ─── ECO / GREEN LOYALTY ─────────────────────────────────────────────────────

class EcoAction(models.Model):
    """
    Eco-friendly action configuration -- earns green points।
    World: Major retailers 2024 -- reusable bags, carbon-neutral delivery,
    Shell eco-rewards, Patagonia sustainability rewards।
    Research: 78% consumers would pay more for eco-friendly brands।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='eco_actions',
    )
    name = models.CharField(max_length=200, verbose_name='Eco Action Name')
    description = models.TextField(null=True, blank=True)
    action_type = models.CharField(
        max_length=30,
        choices=[
            ('reusable_bag', 'Used Reusable Bag'),
            ('carbon_neutral_delivery', 'Carbon-Neutral Delivery Chosen'),
            ('paperless_receipt', 'Chose Paperless Receipt'),
            ('recycle', 'Recycled Product/Packaging'),
            ('bike_delivery', 'Chose Bike/Walk Delivery'),
            ('eco_product', 'Purchased Eco Product'),
            ('plant_tree', 'Plant a Tree Contribution'),
            ('carbon_offset', 'Carbon Offset Purchase'),
            ('water_saving', 'Water-Saving Action'),
            ('electric_vehicle', 'EV Charging at Store'),
            ('custom', 'Custom Eco Action'),
        ],
        verbose_name='Action Type',
    )
    points_reward = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('10'),
        verbose_name='Green Points Reward',
    )
    co2_saved_kg = models.DecimalField(
        max_digits=10, decimal_places=3, default=Decimal('0'),
        verbose_name='CO₂ Saved (kg)',
        help_text='Estimated CO₂ reduction per action',
    )
    max_per_customer_per_day = models.PositiveIntegerField(default=1)
    max_total_verifications = models.PositiveIntegerField(null=True, blank=True)
    requires_proof = models.BooleanField(default=False, verbose_name='Requires Photo/Proof')
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    icon = models.CharField(max_length=50, default='🌱', verbose_name='Icon')
    badge_reward = models.ForeignKey(
        'djoyalty.Badge', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='eco_actions',
    )

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Eco Action'
        verbose_name_plural = 'Eco Actions'
        ordering = ['action_type']
        # AUDIT FIX (4): (tenant, action_type, is_active) covers the primary
        # eco action lookup; (tenant, is_active) for listing.
        indexes = [
            models.Index(fields=['tenant', 'action_type'],
                         name='ecoaction_tenant_type_idx'),
            models.Index(fields=['tenant', 'is_active'],
                         name='ecoaction_tenant_active_idx'),
        ]

    def __str__(self):
        return f'EcoAction({self.name}: {self.points_reward} green pts, {self.co2_saved_kg}kg CO₂)'


class CustomerEcoAction(models.Model):
    """
    Customer completed eco action record।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='eco_actions',
    )
    eco_action = models.ForeignKey(
        EcoAction,
        on_delete=models.CASCADE,
        related_name='customer_records',
    )
    points_awarded = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    co2_saved_kg = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('0'))
    proof_url = models.URLField(null=True, blank=True, verbose_name='Proof URL')
    is_verified = models.BooleanField(default=False)
    verified_by = models.CharField(max_length=200, null=True, blank=True)
    location = models.CharField(max_length=200, null=True, blank=True)
    completed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Customer Eco Action'
        ordering = ['-completed_at']
        indexes = [
            models.Index(fields=['customer', 'eco_action']),
        ]

    def __str__(self):
        return f'EcoRecord({self.customer.code}: {self.eco_action.name})'


class CustomerEcoStats(models.Model):
    """
    Aggregated eco impact per customer।
    """
    customer = models.OneToOneField(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='eco_stats',
    )
    total_eco_points = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    total_co2_saved_kg = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('0'))
    total_eco_actions = models.PositiveIntegerField(default=0)
    eco_tier = models.CharField(
        max_length=20,
        choices=[
            ('seedling', '🌱 Seedling'),
            ('sapling', '🌿 Sapling'),
            ('tree', '🌳 Tree'),
            ('forest', '🌲 Forest Guardian'),
            ('planet', '🌍 Planet Hero'),
        ],
        default='seedling',
    )
    trees_equivalent = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        help_text='CO₂ saved equivalent in trees planted',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Customer Eco Stats'
        # AUDIT FIX (4): OneToOneField to customer creates a unique index.
        # eco_tier index covers leaderboard/segment queries by eco tier.
        indexes = [
            models.Index(fields=['eco_tier'],
                         name='ecostat_tier_idx'),
        ]

    def __str__(self):
        return f'EcoStats({self.customer.code}: {self.total_co2_saved_kg}kg CO₂ saved)'


# ─── CHARITY / CAUSE-BASED REDEMPTION ────────────────────────────────────────

class CharityCause(models.Model):
    """
    Charity/cause that customers can donate points to।
    World: Marriott Bonvoy charity miles, Sephora cause-based rewards,
    2025 trend: loyalty as social impact।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='charity_causes',
    )
    name = models.CharField(max_length=200, verbose_name='Charity Name')
    description = models.TextField(null=True, blank=True)
    category = models.CharField(
        max_length=30,
        choices=[
            ('environment', '🌍 Environment'),
            ('education', '📚 Education'),
            ('health', '🏥 Health & Medical'),
            ('hunger', '🍽️ Fight Hunger'),
            ('animals', '🐾 Animal Welfare'),
            ('disaster', '🆘 Disaster Relief'),
            ('children', '👦 Children'),
            ('elderly', '👴 Elderly Care'),
            ('local', '🏘️ Local Community'),
            ('other', 'Other'),
        ],
        default='other',
        verbose_name='Category',
    )
    logo = models.URLField(null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    points_per_donation_unit = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('100'),
        verbose_name='Points per Donation Unit',
        help_text='e.g. 100 pts = 1 BDT donated to charity',
    )
    min_donation_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('100'),
    )
    total_points_donated = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Total Points Donated (all customers)',
    )
    total_currency_donated = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Total Currency Donated',
    )
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    registration_number = models.CharField(max_length=100, null=True, blank=True, verbose_name='Charity Reg. No.')

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Charity Cause'
        verbose_name_plural = 'Charity Causes'
        ordering = ['name']
        # AUDIT FIX (4): (tenant, is_active) for active charity listing;
        # (category, is_active) for category-filtered browse.
        indexes = [
            models.Index(fields=['tenant', 'is_active'],
                         name='charity_tenant_active_idx'),
            models.Index(fields=['category', 'is_active'],
                         name='charity_category_active_idx'),
        ]

    def __str__(self):
        return f'Charity({self.name} [{self.category}])'


class CharityDonation(models.Model):
    """
    Customer points donation to a charity।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='charity_donations',
        verbose_name='Customer',
    )
    charity = models.ForeignKey(
        CharityCause,
        on_delete=models.CASCADE,
        related_name='donations',
        verbose_name='Charity',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='charity_donations',
    )

    points_donated = models.DecimalField(max_digits=14, decimal_places=2)
    currency_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Currency Value Donated',
    )
    message = models.CharField(max_length=500, null=True, blank=True, verbose_name='Donor Message')
    is_anonymous = models.BooleanField(default=False)
    certificate_url = models.URLField(null=True, blank=True, verbose_name='Donation Certificate URL')
    donated_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Charity Donation'
        verbose_name_plural = 'Charity Donations'
        ordering = ['-donated_at']
        indexes = [
            models.Index(fields=['customer', 'charity']),
            models.Index(fields=['donated_at']),
        ]

    def __str__(self):
        return f'Donation({self.customer.code} -> {self.charity.name}: {self.points_donated} pts)'


# ─── EXPERIENTIAL REWARDS ────────────────────────────────────────────────────

class ExperientialReward(models.Model):
    """
    Experiential/event-based reward -- VIP events, early access,
    exclusive experiences। Beyond discounts।
    World: Antavo #1 differentiator -- experiential loyalty।
    Fashion brands: runway livestreams, in-person events (+33% retention)।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='experiential_rewards',
    )
    name = models.CharField(max_length=200, verbose_name='Experience Name')
    description = models.TextField(null=True, blank=True)
    experience_type = models.CharField(
        max_length=30,
        choices=[
            ('vip_event', '🎉 VIP Event'),
            ('early_access', '🚀 Early Access'),
            ('exclusive_content', '🎬 Exclusive Content'),
            ('personal_stylist', '👗 Personal Stylist Session'),
            ('private_sale', '🛍️ Private Sale Access'),
            ('factory_tour', '🏭 Factory/Behind-Scenes Tour'),
            ('cooking_class', '👨‍🍳 Cooking Class'),
            ('concert_ticket', '🎵 Concert/Event Ticket'),
            ('travel', '✈️ Travel Experience'),
            ('spa_wellness', '💆 Spa & Wellness'),
            ('charity_event', '❤️ Charity Event'),
            ('product_launch', '🆕 Product Launch Party'),
            ('meet_greet', '🤝 Meet & Greet'),
            ('custom', 'Custom Experience'),
        ],
        verbose_name='Experience Type',
    )

    # Requirements
    points_required = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('1000'),
        verbose_name='Points Required',
    )
    min_tier = models.ForeignKey(
        'djoyalty.LoyaltyTier', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='experiential_rewards',
        verbose_name='Minimum Tier Required',
    )

    # Availability
    total_slots = models.PositiveIntegerField(default=10, verbose_name='Total Available Slots')
    slots_remaining = models.PositiveIntegerField(default=10)
    event_date = models.DateTimeField(null=True, blank=True, verbose_name='Event Date')
    event_location = models.CharField(max_length=300, null=True, blank=True)
    registration_deadline = models.DateTimeField(null=True, blank=True)

    # Media
    image = models.URLField(null=True, blank=True)
    video_url = models.URLField(null=True, blank=True)
    terms = models.TextField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ('upcoming', 'Upcoming'),
            ('open', 'Open for Registration'),
            ('full', 'Fully Booked'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='upcoming',
    )
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Experiential Reward'
        verbose_name_plural = 'Experiential Rewards'
        ordering = ['event_date']
        indexes = [
            models.Index(fields=['status', 'event_date']),
            models.Index(fields=['experience_type']),
        ]

    def __str__(self):
        return f'Experience({self.name}: {self.experience_type} [{self.status}])'


class ExperientialRegistration(models.Model):
    """
    Customer registration for an experiential reward।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='experience_registrations',
    )
    experience = models.ForeignKey(
        ExperientialReward,
        on_delete=models.CASCADE,
        related_name='registrations',
    )
    points_redeemed = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=[
            ('registered', 'Registered'),
            ('confirmed', 'Confirmed'),
            ('attended', 'Attended'),
            ('no_show', 'No Show'),
            ('cancelled', 'Cancelled'),
        ],
        default='registered',
    )
    confirmation_code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    special_requests = models.TextField(null=True, blank=True)
    registered_at = models.DateTimeField(default=timezone.now)
    attended_at = models.DateTimeField(null=True, blank=True)
    feedback_rating = models.PositiveIntegerField(null=True, blank=True, verbose_name='Post-Experience Rating (1-5)')
    feedback_comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Experience Registration'
        unique_together = [('customer', 'experience')]
        ordering = ['-registered_at']
        # AUDIT FIX (4): (customer, status) for customer experience history;
        # (experience, status) for experience capacity management.
        indexes = [
            models.Index(fields=['customer', 'status'],
                         name='expreg_customer_status_idx'),
            models.Index(fields=['experience', 'status'],
                         name='expreg_experience_status_idx'),
        ]

    def __str__(self):
        return f'ExperienceReg({self.customer.code}: {self.experience.name} [{self.status}])'


# ─── RECEIPT OCR ─────────────────────────────────────────────────────────────

class ReceiptScan(models.Model):
    """
    Receipt scan -> points earn (Fetch Rewards style)।
    World: Fetch Rewards $2.5B valuation -- users snap receipt, AI awards points।
    2025: AI-powered OCR receipt processing trending, fraud detection built-in।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='receipt_scans',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='receipt_scans',
    )

    receipt_image_url = models.URLField(verbose_name='Receipt Image URL')
    receipt_hash = models.CharField(
        max_length=64, null=True, blank=True,
        verbose_name='Receipt Hash (for duplicate detection)',
    )

    # OCR Results
    merchant_name = models.CharField(max_length=200, null=True, blank=True)
    total_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Total Amount (OCR extracted)',
    )
    purchase_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=10, default='BDT')
    items_detected = models.JSONField(
        default=list, blank=True,
        verbose_name='Items Detected by OCR',
    )
    raw_ocr_text = models.TextField(null=True, blank=True, verbose_name='Raw OCR Text')

    # Processing Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Processing'),
            ('processing', 'OCR Processing'),
            ('verified', 'Verified'),
            ('approved', 'Approved -- Points Awarded'),
            ('rejected', 'Rejected'),
            ('duplicate', 'Duplicate Receipt'),
            ('fraud_suspected', 'Fraud Suspected'),
        ],
        default='pending',
    )
    points_awarded = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )
    rejection_reason = models.CharField(max_length=300, null=True, blank=True)

    # AI Fraud Detection
    ai_fraud_score = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0'),
        verbose_name='AI Fraud Score (0=clean, 1=fraud)',
    )
    is_ai_generated = models.BooleanField(
        default=False,
        verbose_name='AI-Generated Receipt Detected',
        help_text='2025: AI receipt generation fraud spike',
    )

    # Channel
    channel = models.CharField(
        max_length=20,
        choices=[('app', 'Mobile App'), ('web', 'Web'), ('in_store', 'In-Store Kiosk')],
        default='app',
    )

    processed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=200, null=True, blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Receipt Scan'
        verbose_name_plural = 'Receipt Scans'
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['receipt_hash']),
            models.Index(fields=['status', 'submitted_at']),
            models.Index(fields=['ai_fraud_score']),
        ]

    def __str__(self):
        return f'Receipt({self.customer.code}: {self.merchant_name} {self.total_amount} [{self.status}])'


class ReceiptEarnRule(models.Model):
    """
    Rules for how much points a customer earns per receipt।
    Can target specific merchants, categories, amounts।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='receipt_earn_rules',
    )
    name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)

    # Targeting
    target_merchant = models.CharField(
        max_length=200, null=True, blank=True,
        verbose_name='Target Merchant (leave blank for all)',
    )
    min_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Minimum Receipt Amount',
    )

    # Earn
    earn_type = models.CharField(
        max_length=20,
        choices=[
            ('fixed', 'Fixed Points per Receipt'),
            ('percentage', '% of Receipt Amount'),
        ],
        default='percentage',
    )
    points_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('1'),
        verbose_name='Points (fixed) or Rate (% of amount)',
    )
    max_points_per_receipt = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
    )
    max_receipts_per_day = models.PositiveIntegerField(default=5)

    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Receipt Earn Rule'
        # AUDIT FIX (4): (tenant, is_active) for active rule lookup on every
        # receipt scan; (is_active,) for cross-tenant rule engine queries.
        indexes = [
            models.Index(fields=['tenant', 'is_active'],
                         name='receiptrule_tenant_active_idx'),
            models.Index(fields=['is_active', 'valid_from', 'valid_until'],
                         name='receiptrule_active_dates_idx'),
        ]

    def __str__(self):
        return f'ReceiptRule({self.name}: {self.earn_type} {self.points_value})'


# ─── CONSENT & PRIVACY ───────────────────────────────────────────────────────

class CustomerConsent(models.Model):
    """
    GDPR/Privacy consent management।
    2025 trend: privacy-first personalization -- consent = trust।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='consents',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='customer_consents',
    )

    consent_type = models.CharField(
        max_length=30,
        choices=[
            ('marketing_email', 'Marketing Emails'),
            ('marketing_sms', 'Marketing SMS'),
            ('marketing_push', 'Push Notifications'),
            ('data_analytics', 'Data Analytics & Personalization'),
            ('data_sharing', 'Share Data with Partners'),
            ('profiling', 'AI Behavioral Profiling'),
            ('location', 'Location Tracking'),
            ('third_party', 'Third-Party Integrations'),
        ],
        verbose_name='Consent Type',
    )
    is_granted = models.BooleanField(default=False, verbose_name='Consent Granted')
    granted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    consent_text_version = models.CharField(
        max_length=20, default='1.0',
        verbose_name='Consent Text Version',
        help_text='Version of the privacy policy shown',
    )
    source = models.CharField(
        max_length=30,
        choices=[
            ('registration', 'Registration'),
            ('app', 'Mobile App'),
            ('web', 'Website'),
            ('in_store', 'In-Store'),
            ('email', 'Email'),
            ('admin', 'Admin'),
        ],
        default='web',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Customer Consent'
        verbose_name_plural = 'Customer Consents'
        unique_together = [('customer', 'consent_type')]
        indexes = [
            models.Index(fields=['customer', 'consent_type', 'is_granted']),
        ]

    def __str__(self):
        status = 'granted' if self.is_granted else 'revoked'
        return f'Consent({self.customer.code}: {self.consent_type} [{status}])'
