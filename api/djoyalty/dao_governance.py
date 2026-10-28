# api/djoyalty/dao_governance.py
"""
Djoyalty DAO Governance -- Decentralized Autonomous Organization style
customer voting on loyalty program rules।

2025/2026 trend: Customers vote on:
  - Earn rule changes (should purchase earn 2x or 3x points?)
  - New reward catalog items (what rewards should we add?)
  - Tier thresholds (should Gold require 1000 or 1500 points?)
  - Campaign approval (vote for next month's bonus campaign)
  - Point expiry policy (should points expire in 6 months or 12?)
  - Charity partners (which charity to donate to?)

Reference:
  - Lacoste UNDW3 NFT voting rights
  - Reddit Community Points governance
  - Decentraland DAO (DCL)
  - Curve Finance veCRV voting model

Philosophy: Customers who hold more points / higher tiers get more
voting power (like veCRV model). This increases engagement because
customers are incentivized to stay active to keep voting rights.

"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


# ─── Choice Constants ─────────────────────────────────────────────────────────

PROPOSAL_STATUS_DRAFT     = 'draft'
PROPOSAL_STATUS_ACTIVE    = 'active'
PROPOSAL_STATUS_PASSED    = 'passed'
PROPOSAL_STATUS_REJECTED  = 'rejected'
PROPOSAL_STATUS_EXECUTED  = 'executed'
PROPOSAL_STATUS_CANCELLED = 'cancelled'
PROPOSAL_STATUS_EXPIRED   = 'expired'

PROPOSAL_STATUS_CHOICES = [
    (PROPOSAL_STATUS_DRAFT,     'Draft -- not yet published'),
    (PROPOSAL_STATUS_ACTIVE,    'Active -- voting in progress'),
    (PROPOSAL_STATUS_PASSED,    'Passed -- approved by members'),
    (PROPOSAL_STATUS_REJECTED,  'Rejected -- not approved'),
    (PROPOSAL_STATUS_EXECUTED,  'Executed -- changes applied'),
    (PROPOSAL_STATUS_CANCELLED, 'Cancelled -- withdrawn'),
    (PROPOSAL_STATUS_EXPIRED,   'Expired -- voting period ended'),
]

PROPOSAL_TYPE_EARN_RULE        = 'earn_rule'
PROPOSAL_TYPE_TIER_THRESHOLD   = 'tier_threshold'
PROPOSAL_TYPE_CATALOG_ITEM     = 'catalog_item'
PROPOSAL_TYPE_CAMPAIGN         = 'campaign'
PROPOSAL_TYPE_EXPIRY_POLICY    = 'expiry_policy'
PROPOSAL_TYPE_CHARITY_PARTNER  = 'charity_partner'
PROPOSAL_TYPE_CASHOUT_RATE     = 'cashout_rate'
PROPOSAL_TYPE_CUSTOM           = 'custom'

PROPOSAL_TYPE_CHOICES = [
    (PROPOSAL_TYPE_EARN_RULE,       'Earn Rule Change'),
    (PROPOSAL_TYPE_TIER_THRESHOLD,  'Tier Threshold Change'),
    (PROPOSAL_TYPE_CATALOG_ITEM,    'New Catalog Item'),
    (PROPOSAL_TYPE_CAMPAIGN,        'Campaign Approval'),
    (PROPOSAL_TYPE_EXPIRY_POLICY,   'Points Expiry Policy'),
    (PROPOSAL_TYPE_CHARITY_PARTNER, 'Charity Partner'),
    (PROPOSAL_TYPE_CASHOUT_RATE,    'Cashout Rate Change'),
    (PROPOSAL_TYPE_CUSTOM,          'Custom Proposal'),
]

VOTE_FOR     = 'for'
VOTE_AGAINST = 'against'
VOTE_ABSTAIN = 'abstain'

VOTE_CHOICES = [
    (VOTE_FOR,     'For -- I support this'),
    (VOTE_AGAINST, 'Against -- I oppose this'),
    (VOTE_ABSTAIN, 'Abstain -- no opinion'),
]

QUORUM_TYPE_PERCENTAGE = 'percentage'  # % of eligible voters must vote
QUORUM_TYPE_ABSOLUTE   = 'absolute'   # absolute number must vote


# ─── Models ──────────────────────────────────────────────────────────────────

class GovernanceConfig(models.Model):
    """
    Per-tenant DAO governance configuration।
    Controls voting power formula, quorum, vote duration।
    """
    tenant = models.OneToOneField(
        'djoyalty.Tenant',
        on_delete=models.CASCADE,
        related_name='governance_config',
    )

    # Voting power formula
    voting_power_formula = models.CharField(
        max_length=20,
        choices=[
            ('equal',          'Equal -- 1 vote per member'),
            ('points_balance', 'Points Balance -- more points = more votes'),
            ('tier_based',     'Tier Based -- higher tier = more votes'),
            ('hybrid',         'Hybrid -- tier weight × sqrt(balance)'),
        ],
        default='hybrid',
    )

    # Minimum requirements to vote
    min_tier_rank_to_vote = models.PositiveIntegerField(
        default=0,
        help_text='Minimum tier rank required to vote (0=all tiers)',
    )
    min_points_to_vote = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        help_text='Minimum points balance required to vote',
    )
    min_account_age_days = models.PositiveIntegerField(
        default=30,
        help_text='Minimum account age in days to participate',
    )

    # Proposal creation requirements
    min_points_to_propose = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('1000'),
        help_text='Minimum points balance to create a proposal',
    )
    min_tier_rank_to_propose = models.PositiveIntegerField(
        default=2,
        help_text='Minimum tier rank required to create proposals',
    )

    # Voting period
    default_voting_days = models.PositiveIntegerField(
        default=7,
        help_text='Default voting period in days',
    )
    min_voting_days = models.PositiveIntegerField(default=3)
    max_voting_days = models.PositiveIntegerField(default=30)

    # Quorum
    quorum_type = models.CharField(
        max_length=15,
        choices=[
            (QUORUM_TYPE_PERCENTAGE, 'Percentage of eligible voters'),
            (QUORUM_TYPE_ABSOLUTE,   'Absolute vote count'),
        ],
        default=QUORUM_TYPE_PERCENTAGE,
    )
    quorum_threshold = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10'),
        help_text='Quorum: 10 = 10% of eligible voters must participate',
    )

    # Passing threshold
    passing_threshold_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('51'),
        help_text='Percentage of FOR votes (out of FOR + AGAINST) needed to pass',
    )

    # Auto-execution
    auto_execute = models.BooleanField(
        default=False,
        help_text='Automatically apply changes when proposal passes',
    )

    # Tier voting weights (used in hybrid/tier_based formula)
    tier_vote_weights = models.JSONField(
        default=dict,
        help_text='Dict of tier_rank -> vote_weight, e.g. {1: 1, 2: 2, 3: 5, 4: 10, 5: 20}',
    )

    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Governance Config'

    def get_tier_weight(self, tier_rank: int) -> int:
        """Get vote weight for a tier rank। Default: rank itself."""
        weights = self.tier_vote_weights or {}
        return weights.get(str(tier_rank), tier_rank or 1)

    def __str__(self):
        return f'GovernanceConfig({self.tenant.name if self.tenant else "global"})'


class GovernanceProposal(models.Model):
    """
    A governance proposal that members can vote on।
    Created by eligible members, voted on by the community।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='governance_proposals',
    )
    proposer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.SET_NULL, null=True,
        related_name='proposed_proposals',
    )

    # Proposal identity
    proposal_number = models.PositiveIntegerField(
        help_text='Sequential proposal number, e.g. GIP-001',
    )
    title = models.CharField(max_length=200)
    summary = models.TextField(help_text='Short summary -- shown in voting list')
    description = models.TextField(help_text='Full description with rationale')
    proposal_type = models.CharField(
        max_length=30, choices=PROPOSAL_TYPE_CHOICES,
        default=PROPOSAL_TYPE_CUSTOM,
    )

    # The actual change being proposed
    # Stored as structured JSON so it can be auto-executed
    proposed_changes = models.JSONField(
        default=dict,
        help_text='Structured changes to apply if proposal passes. '
                  'Format depends on proposal_type. '
                  'earn_rule: {rule_id: int, new_earn_value: str} '
                  'tier_threshold: {tier_id: int, new_min_points: str} '
                  'catalog_item: {name: str, points_cost: str, reward_type: str} '
                  'expiry_policy: {expiry_days: int} '
                  'charity_partner: {cause_id: int, allocation_pct: str}',
    )
    current_state = models.JSONField(
        default=dict,
        help_text='Current state before changes (for display and rollback)',
    )

    # Status & timing
    status = models.CharField(
        max_length=20, choices=PROPOSAL_STATUS_CHOICES,
        default=PROPOSAL_STATUS_DRAFT, db_index=True,
    )
    voting_start = models.DateTimeField(null=True, blank=True)
    voting_end = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # Vote tallies (updated in real-time)
    votes_for = models.PositiveIntegerField(default=0)
    votes_against = models.PositiveIntegerField(default=0)
    votes_abstain = models.PositiveIntegerField(default=0)
    total_voting_power_for = models.DecimalField(
        max_digits=20, decimal_places=4, default=Decimal('0'),
    )
    total_voting_power_against = models.DecimalField(
        max_digits=20, decimal_places=4, default=Decimal('0'),
    )
    total_voting_power_abstain = models.DecimalField(
        max_digits=20, decimal_places=4, default=Decimal('0'),
    )
    unique_voters = models.PositiveIntegerField(default=0)
    eligible_voters_at_start = models.PositiveIntegerField(
        default=0,
        help_text='Number of eligible voters when proposal was published',
    )

    # Metadata
    discussion_url = models.URLField(
        null=True, blank=True,
        help_text='Link to discussion thread (forum/Discord)',
    )
    tags = models.JSONField(default=list)
    view_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Governance Proposal'
        verbose_name_plural = 'Governance Proposals'
        ordering = ['-created_at']
        unique_together = [('tenant', 'proposal_number')]
        indexes = [
            models.Index(fields=['status', 'voting_end']),
            models.Index(fields=['tenant', 'status']),
        ]

    @property
    def proposal_id(self) -> str:
        """Human-readable ID like GIP-001."""
        return f'GIP-{self.proposal_number:03d}'

    @property
    def is_active(self) -> bool:
        return (
            self.status == PROPOSAL_STATUS_ACTIVE and
            self.voting_end is not None and
            timezone.now() < self.voting_end
        )

    @property
    def total_votes(self) -> int:
        return self.votes_for + self.votes_against + self.votes_abstain

    @property
    def total_voting_power(self) -> Decimal:
        return (
            self.total_voting_power_for +
            self.total_voting_power_against +
            self.total_voting_power_abstain
        )

    @property
    def for_percentage(self) -> Decimal:
        """% of FOR votes out of FOR + AGAINST (not counting abstain)।"""
        decisive = self.total_voting_power_for + self.total_voting_power_against
        if decisive == 0:
            return Decimal('0')
        return (self.total_voting_power_for / decisive * 100).quantize(Decimal('0.01'))

    @property
    def quorum_reached(self) -> bool:
        """Check if quorum threshold is met."""
        if self.eligible_voters_at_start == 0:
            return False
        pct = self.unique_voters / self.eligible_voters_at_start * 100
        return Decimal(str(pct)) >= Decimal('10')  # 10% default

    @property
    def time_remaining(self) -> str:
        """Human-readable time remaining for voting."""
        if not self.voting_end:
            return 'Not started'
        now = timezone.now()
        if now > self.voting_end:
            return 'Ended'
        delta = self.voting_end - now
        days = delta.days
        hours = delta.seconds // 3600
        if days > 0:
            return f'{days}d {hours}h remaining'
        return f'{hours}h {(delta.seconds % 3600) // 60}m remaining'

    def __str__(self):
        return f'Proposal({self.proposal_id}: {self.title} [{self.status}])'


class GovernanceVote(models.Model):
    """
    A single vote cast by a customer on a proposal।
    One vote per customer per proposal (enforced by unique_together)।
    Voting power is recorded at time of voting।
    """
    proposal = models.ForeignKey(
        GovernanceProposal, on_delete=models.CASCADE,
        related_name='votes',
    )
    voter = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='governance_votes',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='governance_votes',
    )

    vote = models.CharField(max_length=10, choices=VOTE_CHOICES)

    # Voting power at time of casting vote (snapshot -- immutable)
    voting_power = models.DecimalField(
        max_digits=20, decimal_places=4, default=Decimal('1'),
    )
    points_balance_at_vote = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )
    tier_rank_at_vote = models.PositiveIntegerField(default=0)

    # Optional reasoning
    comment = models.TextField(
        null=True, blank=True,
        help_text='Voter can leave a comment explaining their vote',
    )

    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Governance Vote'
        unique_together = [('proposal', 'voter')]
        ordering = ['-voted_at']
        indexes = [
            models.Index(fields=['proposal', 'vote']),
        ]

    def __str__(self):
        return f'Vote({self.voter.code}: {self.vote} on {self.proposal.proposal_id})'


class GovernanceExecution(models.Model):
    """
    Record of a proposal being executed (changes applied)।
    Tracks what changed, who executed, and any errors।
    """
    proposal = models.OneToOneField(
        GovernanceProposal, on_delete=models.CASCADE,
        related_name='execution',
    )
    executed_by = models.ForeignKey(
        'djoyalty.Customer', null=True, blank=True,
        on_delete=models.SET_NULL,
        help_text='Admin who executed, null if auto-executed',
    )

    success = models.BooleanField(default=False)
    changes_applied = models.JSONField(default=dict)
    error_message = models.TextField(null=True, blank=True)
    execution_log = models.TextField(null=True, blank=True)

    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Governance Execution'

    def __str__(self):
        return f'Execution({self.proposal.proposal_id}: {"✅" if self.success else "❌"})'


# ─── Voting Power Calculator ──────────────────────────────────────────────────

class VotingPowerCalculator:
    """
    Calculate a customer's voting power based on governance config।

    Formulas:
    - equal:          1 vote per member
    - points_balance: voting_power = log10(balance + 1) × 10
    - tier_based:     voting_power = tier_weight (from config)
    - hybrid:         voting_power = tier_weight × sqrt(balance / 100)

    Hybrid model is recommended:
      - Ensures long-term engaged customers (high tier) have more influence
      - But also rewards active point-earners (high balance)
      - sqrt prevents extreme concentration of power in whales
    """

    import math as _math

    @classmethod
    def calculate(cls, customer, config: GovernanceConfig) -> Decimal:
        """Calculate voting power for a customer given governance config।"""
        from .selectors import get_points_balance, get_current_tier
        import math

        formula = config.voting_power_formula
        balance = float(get_points_balance(customer))
        tier = get_current_tier(customer)
        tier_rank = tier.rank if tier else 0

        if formula == 'equal':
            return Decimal('1')

        elif formula == 'points_balance':
            # Log scale prevents whales from dominating
            power = math.log10(max(balance, 1) + 1) * 10
            return Decimal(str(round(power, 4)))

        elif formula == 'tier_based':
            weight = config.get_tier_weight(tier_rank)
            return Decimal(str(weight))

        elif formula == 'hybrid':
            # tier_weight × sqrt(balance / 1000 + 1)
            tier_weight = config.get_tier_weight(tier_rank)
            balance_factor = math.sqrt(max(balance, 0) / 1000 + 1)
            power = tier_weight * balance_factor
            return Decimal(str(round(power, 4)))

        return Decimal('1')

    @classmethod
    def is_eligible_to_vote(cls, customer, config: GovernanceConfig) -> tuple:
        """
        Check if a customer is eligible to vote।
        Returns: (eligible: bool, reason: str)
        """
        from .selectors import get_points_balance, get_current_tier
        from .helpers import days_since

        if not customer.is_active:
            return False, 'Account is not active.'

        # Account age check
        account_age = days_since(customer.created_at)
        if account_age < config.min_account_age_days:
            return False, (
                f'Account must be at least {config.min_account_age_days} days old '
                f'(yours is {account_age} days).'
            )

        # Minimum points check
        if config.min_points_to_vote > 0:
            balance = get_points_balance(customer)
            if balance < config.min_points_to_vote:
                return False, (
                    f'Minimum {config.min_points_to_vote} points required to vote '
                    f'(your balance: {balance}).'
                )

        # Minimum tier check
        if config.min_tier_rank_to_vote > 0:
            tier = get_current_tier(customer)
            tier_rank = tier.rank if tier else 0
            if tier_rank < config.min_tier_rank_to_vote:
                return False, (
                    f'Minimum tier rank {config.min_tier_rank_to_vote} required '
                    f'(your rank: {tier_rank}).'
                )

        return True, ''

    @classmethod
    def is_eligible_to_propose(cls, customer, config: GovernanceConfig) -> tuple:
        """Check if customer can create proposals."""
        from .selectors import get_points_balance, get_current_tier

        eligible, reason = cls.is_eligible_to_vote(customer, config)
        if not eligible:
            return False, reason

        # Higher requirements for proposing
        if config.min_points_to_propose > 0:
            balance = get_points_balance(customer)
            if balance < config.min_points_to_propose:
                return False, (
                    f'Minimum {config.min_points_to_propose} points required to propose '
                    f'(your balance: {balance}).'
                )

        if config.min_tier_rank_to_propose > 0:
            tier = get_current_tier(customer)
            tier_rank = tier.rank if tier else 0
            if tier_rank < config.min_tier_rank_to_propose:
                return False, (
                    f'Minimum tier rank {config.min_tier_rank_to_propose} required '
                    f'to create proposals (your rank: {tier_rank}).'
                )

        return True, ''


# ─── Governance Service ───────────────────────────────────────────────────────

class GovernanceService:
    """
    Core DAO governance service।
    Manages the full lifecycle: create -> publish -> vote -> tally -> execute।

    Usage:
        # Create a proposal
        proposal = GovernanceService.create_proposal(
            proposer=customer,
            title='Double points for eco purchases',
            description='I propose we give 2x points for...',
            proposal_type='earn_rule',
            proposed_changes={'rule_name': 'eco_purchase', 'new_multiplier': '2'},
        )

        # Publish (start voting)
        GovernanceService.publish_proposal(proposal, voting_days=7)

        # Cast a vote
        GovernanceService.cast_vote(proposal, voter=customer, vote='for', comment='Great idea!')

        # Get results
        results = GovernanceService.get_results(proposal)

        # Execute if passed
        GovernanceService.execute_proposal(proposal)
    """

    @staticmethod
    def get_or_create_config(tenant=None) -> GovernanceConfig:
        """Get governance config for tenant, create default if not exists."""
        config, created = GovernanceConfig.objects.get_or_create(
            tenant=tenant,
            defaults={
                'voting_power_formula': 'hybrid',
                'default_voting_days': 7,
                'quorum_threshold': Decimal('10'),
                'passing_threshold_pct': Decimal('51'),
                'min_points_to_vote': Decimal('0'),
                'min_account_age_days': 30,
                'min_points_to_propose': Decimal('1000'),
                'min_tier_rank_to_propose': 2,
                'tier_vote_weights': {
                    '0': 1, '1': 1, '2': 2, '3': 5, '4': 10, '5': 20,
                },
                'is_enabled': True,
            },
        )
        if created:
            logger.info('GovernanceService: created default config for tenant %s', tenant)
        return config

    @staticmethod
    def get_next_proposal_number(tenant=None) -> int:
        """Get next sequential proposal number for tenant."""
        last = GovernanceProposal.objects.filter(
            tenant=tenant
        ).order_by('-proposal_number').first()
        return (last.proposal_number + 1) if last else 1

    @staticmethod
    @transaction.atomic
    def create_proposal(proposer, title: str, description: str,
                         proposal_type: str = PROPOSAL_TYPE_CUSTOM,
                         proposed_changes: dict = None,
                         current_state: dict = None,
                         summary: str = '',
                         discussion_url: str = '',
                         tags: list = None,
                         tenant=None) -> GovernanceProposal:
        """
        Create a new governance proposal in DRAFT state।
        Validates proposer is eligible।
        """
        config = GovernanceService.get_or_create_config(tenant)

        if not config.is_enabled:
            raise ValueError('Governance is not enabled for this tenant.')

        # Check proposer eligibility
        eligible, reason = VotingPowerCalculator.is_eligible_to_propose(proposer, config)
        if not eligible:
            raise PermissionError(f'Not eligible to create proposals: {reason}')

        proposal_number = GovernanceService.get_next_proposal_number(tenant)

        proposal = GovernanceProposal.objects.create(
            tenant=tenant or proposer.tenant,
            proposer=proposer,
            proposal_number=proposal_number,
            title=title,
            summary=summary or title,
            description=description,
            proposal_type=proposal_type,
            proposed_changes=proposed_changes or {},
            current_state=current_state or {},
            status=PROPOSAL_STATUS_DRAFT,
            discussion_url=discussion_url,
            tags=tags or [],
        )

        # Audit log
        try:
            from .models.audit import AdminAuditLog
            AdminAuditLog.log(
                action='governance_proposal_created',
                category='campaign',
                customer=proposer,
                new_value={
                    'proposal_id': proposal.proposal_id,
                    'title': title,
                    'type': proposal_type,
                },
                description=f'Governance proposal {proposal.proposal_id} created',
            )
        except Exception:
            pass

        logger.info('GovernanceService: proposal %s created by %s',
                    proposal.proposal_id, proposer.code)
        return proposal

    @staticmethod
    @transaction.atomic
    def publish_proposal(proposal: GovernanceProposal,
                          voting_days: int = None) -> GovernanceProposal:
        """
        Publish a draft proposal -- start the voting period।
        Counts eligible voters at this moment (for quorum calculation)।
        """
        if proposal.status != PROPOSAL_STATUS_DRAFT:
            raise ValueError(f'Can only publish DRAFT proposals (current: {proposal.status})')

        config = GovernanceService.get_or_create_config(proposal.tenant)
        days = voting_days or config.default_voting_days
        days = max(config.min_voting_days, min(config.max_voting_days, days))

        now = timezone.now()
        proposal.status = PROPOSAL_STATUS_ACTIVE
        proposal.voting_start = now
        proposal.voting_end = now + timedelta(days=days)
        proposal.published_at = now

        # Count eligible voters
        proposal.eligible_voters_at_start = GovernanceService._count_eligible_voters(
            config, proposal.tenant
        )

        proposal.save()

        # Notify all eligible customers
        try:
            GovernanceService._notify_voters_about_proposal(proposal, config)
        except Exception as e:
            logger.debug('GovernanceService.publish_proposal notification error: %s', e)

        logger.info('GovernanceService: proposal %s published -- voting until %s (%d eligible voters)',
                    proposal.proposal_id, proposal.voting_end.date(), proposal.eligible_voters_at_start)
        return proposal

    @staticmethod
    def _count_eligible_voters(config: GovernanceConfig, tenant=None) -> int:
        """Count customers eligible to vote."""
        from .models.core import Customer
        from django.utils import timezone
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=config.min_account_age_days)
        qs = Customer.objects.filter(is_active=True, created_at__lte=cutoff)
        if tenant:
            qs = qs.filter(tenant=tenant)

        if config.min_tier_rank_to_vote > 0:
            qs = qs.filter(
                user_tiers__tier__rank__gte=config.min_tier_rank_to_vote,
                user_tiers__is_current=True,
            )

        if config.min_points_to_vote > 0:
            qs = qs.filter(loyalty_points__balance__gte=config.min_points_to_vote)

        return qs.distinct().count()

    @staticmethod
    def _notify_voters_about_proposal(proposal: GovernanceProposal,
                                       config: GovernanceConfig):
        """Send notification to all eligible voters about new proposal."""
        from .models.core import Customer
        from .services.NotificationService import NotificationService
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=config.min_account_age_days)
        customers = Customer.objects.filter(
            is_active=True, created_at__lte=cutoff,
        )
        if proposal.tenant:
            customers = customers.filter(tenant=proposal.tenant)

        sent = 0
        for customer in customers.iterator(chunk_size=100):
            try:
                NotificationService.send(
                    customer, 'campaign_active',
                    title=f'🗳️ Vote Now: {proposal.title[:50]}',
                    body=(
                        f'Governance Proposal {proposal.proposal_id} is open for voting। '
                        f'Voting ends: {proposal.voting_end.strftime("%b %d")}। '
                        f'Your vote matters!'
                    ),
                    icon='🗳️',
                    action_url=f'/governance/{proposal.id}/',
                    metadata={
                        'proposal_id': proposal.id,
                        'proposal_ref': proposal.proposal_id,
                    },
                )
                sent += 1
            except Exception:
                pass

        logger.info('GovernanceService: notified %d voters about %s',
                    sent, proposal.proposal_id)

    @staticmethod
    @transaction.atomic
    def cast_vote(proposal: GovernanceProposal, voter, vote: str,
                   comment: str = '') -> GovernanceVote:
        """
        Cast a vote on a proposal।
        Validates eligibility, calculates voting power, records vote।
        Updates proposal tallies atomically।
        """
        # Validate proposal is active
        if not proposal.is_active:
            raise ValueError(
                f'Proposal {proposal.proposal_id} is not currently accepting votes '
                f'(status: {proposal.status}).'
            )

        # Validate vote value
        valid_votes = [VOTE_FOR, VOTE_AGAINST, VOTE_ABSTAIN]
        if vote not in valid_votes:
            raise ValueError(f'Vote must be one of: {valid_votes}')

        config = GovernanceService.get_or_create_config(proposal.tenant)

        # Check eligibility
        eligible, reason = VotingPowerCalculator.is_eligible_to_vote(voter, config)
        if not eligible:
            raise PermissionError(f'Not eligible to vote: {reason}')

        # Check not already voted
        if GovernanceVote.objects.filter(proposal=proposal, voter=voter).exists():
            raise ValueError(f'You have already voted on {proposal.proposal_id}.')

        # Calculate voting power
        voting_power = VotingPowerCalculator.calculate(voter, config)

        # Get voter's current state for snapshot
        from .selectors import get_points_balance, get_current_tier
        balance = get_points_balance(voter)
        tier = get_current_tier(voter)
        tier_rank = tier.rank if tier else 0

        # Create vote record
        vote_record = GovernanceVote.objects.create(
            proposal=proposal,
            voter=voter,
            tenant=proposal.tenant,
            vote=vote,
            voting_power=voting_power,
            points_balance_at_vote=balance,
            tier_rank_at_vote=tier_rank,
            comment=comment[:500] if comment else '',
        )

        # Update proposal tallies atomically
        update_fields = {}
        if vote == VOTE_FOR:
            update_fields = {
                'votes_for': models.F('votes_for') + 1,
                'total_voting_power_for': models.F('total_voting_power_for') + voting_power,
            }
        elif vote == VOTE_AGAINST:
            update_fields = {
                'votes_against': models.F('votes_against') + 1,
                'total_voting_power_against': models.F('total_voting_power_against') + voting_power,
            }
        else:  # abstain
            update_fields = {
                'votes_abstain': models.F('votes_abstain') + 1,
                'total_voting_power_abstain': models.F('total_voting_power_abstain') + voting_power,
            }
        update_fields['unique_voters'] = models.F('unique_voters') + 1

        GovernanceProposal.objects.filter(id=proposal.id).update(**update_fields)

        # Refresh proposal from DB
        proposal.refresh_from_db()

        logger.info('GovernanceService: %s voted %s on %s (power: %s)',
                    voter.code, vote, proposal.proposal_id, voting_power)

        # Notify voter of successful vote
        try:
            from .services.NotificationService import NotificationService
            emoji = {'for': '✅', 'against': '❌', 'abstain': '🤝'}.get(vote, '🗳️')
            NotificationService.send(
                voter, 'campaign_active',
                title=f'{emoji} Vote Recorded!',
                body=f'আপনার ভোট "{vote.title()}" {proposal.proposal_id} তে নথিভুক্ত হয়েছে। Power: {voting_power}',
                icon=emoji,
                metadata={'proposal_id': proposal.id, 'vote': vote},
            )
        except Exception:
            pass

        return vote_record

    @staticmethod
    def change_vote(proposal: GovernanceProposal, voter,
                     new_vote: str) -> GovernanceVote:
        """
        Change an existing vote (allowed while voting is active)।
        Adjusts tally accordingly।
        """
        if not proposal.is_active:
            raise ValueError('Cannot change vote -- voting period has ended.')

        existing_vote = GovernanceVote.objects.filter(
            proposal=proposal, voter=voter
        ).first()

        if not existing_vote:
            raise ValueError('No existing vote to change.')

        old_vote = existing_vote.vote
        old_power = existing_vote.voting_power

        if old_vote == new_vote:
            return existing_vote  # No change needed

        # Reverse old vote and apply new vote in one atomic update
        with transaction.atomic():
            # Decrement old vote tally
            decrement = {}
            if old_vote == VOTE_FOR:
                decrement = {
                    'votes_for': models.F('votes_for') - 1,
                    'total_voting_power_for': models.F('total_voting_power_for') - old_power,
                }
            elif old_vote == VOTE_AGAINST:
                decrement = {
                    'votes_against': models.F('votes_against') - 1,
                    'total_voting_power_against': models.F('total_voting_power_against') - old_power,
                }
            else:
                decrement = {
                    'votes_abstain': models.F('votes_abstain') - 1,
                    'total_voting_power_abstain': models.F('total_voting_power_abstain') - old_power,
                }
            GovernanceProposal.objects.filter(id=proposal.id).update(**decrement)

            # Update vote record
            existing_vote.vote = new_vote
            existing_vote.save(update_fields=['vote'])

            # Increment new vote tally
            increment = {}
            if new_vote == VOTE_FOR:
                increment = {
                    'votes_for': models.F('votes_for') + 1,
                    'total_voting_power_for': models.F('total_voting_power_for') + old_power,
                }
            elif new_vote == VOTE_AGAINST:
                increment = {
                    'votes_against': models.F('votes_against') - 1,
                    'total_voting_power_against': models.F('total_voting_power_against') - old_power,
                }
            else:
                increment = {
                    'votes_abstain': models.F('votes_abstain') + 1,
                    'total_voting_power_abstain': models.F('total_voting_power_abstain') + old_power,
                }
            GovernanceProposal.objects.filter(id=proposal.id).update(**increment)

        logger.info('GovernanceService: %s changed vote from %s to %s on %s',
                    voter.code, old_vote, new_vote, proposal.proposal_id)
        return existing_vote

    @staticmethod
    def get_results(proposal: GovernanceProposal) -> dict:
        """
        Get full voting results for a proposal।
        Returns comprehensive breakdown with percentages and quorum status।
        """
        proposal.refresh_from_db()
        config = GovernanceService.get_or_create_config(proposal.tenant)

        total_power = proposal.total_voting_power
        decisive_power = proposal.total_voting_power_for + proposal.total_voting_power_against

        # Calculate percentages
        for_pct = (
            float(proposal.total_voting_power_for) / float(decisive_power) * 100
            if decisive_power > 0 else 0
        )
        against_pct = (
            float(proposal.total_voting_power_against) / float(decisive_power) * 100
            if decisive_power > 0 else 0
        )

        # Check quorum
        eligible = proposal.eligible_voters_at_start
        quorum_met = (
            eligible > 0 and
            (proposal.unique_voters / eligible * 100) >= float(config.quorum_threshold)
        )

        # Determine outcome
        passing_threshold = float(config.passing_threshold_pct)
        would_pass = quorum_met and for_pct >= passing_threshold

        return {
            'proposal_id': proposal.proposal_id,
            'title': proposal.title,
            'status': proposal.status,
            'voting_power': {
                'for': str(proposal.total_voting_power_for),
                'against': str(proposal.total_voting_power_against),
                'abstain': str(proposal.total_voting_power_abstain),
                'total': str(total_power),
            },
            'vote_counts': {
                'for': proposal.votes_for,
                'against': proposal.votes_against,
                'abstain': proposal.votes_abstain,
                'total': proposal.total_votes,
            },
            'percentages': {
                'for': f'{for_pct:.1f}%',
                'against': f'{against_pct:.1f}%',
            },
            'quorum': {
                'met': quorum_met,
                'threshold': f'{config.quorum_threshold}%',
                'unique_voters': proposal.unique_voters,
                'eligible_voters': eligible,
                'participation': f'{proposal.unique_voters / max(eligible, 1) * 100:.1f}%',
            },
            'outcome': {
                'would_pass': would_pass,
                'passing_threshold': f'{passing_threshold}%',
                'needs_more_votes': not quorum_met,
            },
            'timing': {
                'voting_end': proposal.voting_end.isoformat() if proposal.voting_end else None,
                'time_remaining': proposal.time_remaining,
            },
        }

    @staticmethod
    @transaction.atomic
    def finalize_proposal(proposal: GovernanceProposal) -> GovernanceProposal:
        """
        Finalize a proposal after voting period ends।
        Determines passed/rejected/expired status।
        Called by scheduled task (finalize_expired_proposals)।
        """
        if proposal.status != PROPOSAL_STATUS_ACTIVE:
            return proposal

        now = timezone.now()
        if proposal.voting_end and now < proposal.voting_end:
            return proposal  # Still active

        config = GovernanceService.get_or_create_config(proposal.tenant)
        results = GovernanceService.get_results(proposal)

        if not results['quorum']['met']:
            proposal.status = PROPOSAL_STATUS_EXPIRED
            logger.info('GovernanceService: %s EXPIRED -- quorum not met', proposal.proposal_id)
        elif results['outcome']['would_pass']:
            proposal.status = PROPOSAL_STATUS_PASSED
            logger.info('GovernanceService: %s PASSED (%s for)',
                        proposal.proposal_id, results['percentages']['for'])
            # Auto-execute if configured
            if config.auto_execute:
                GovernanceService.execute_proposal(proposal)
        else:
            proposal.status = PROPOSAL_STATUS_REJECTED
            logger.info('GovernanceService: %s REJECTED (%s for)',
                        proposal.proposal_id, results['percentages']['for'])

        proposal.save(update_fields=['status'])

        # Notify proposer of outcome
        try:
            from .services.NotificationService import NotificationService
            if proposal.proposer:
                emoji = {'passed': '🎉', 'rejected': '😔', 'expired': '⏰'}.get(
                    proposal.status, '📋'
                )
                NotificationService.send(
                    proposal.proposer, 'campaign_active',
                    title=f'{emoji} Proposal {proposal.status.title()}!',
                    body=(
                        f'Your proposal "{proposal.title}" has {proposal.status}। '
                        f'For: {results["percentages"]["for"]}, '
                        f'Voters: {results["vote_counts"]["total"]}'
                    ),
                    priority='high',
                )
        except Exception:
            pass

        return proposal

    @staticmethod
    @transaction.atomic
    def execute_proposal(proposal: GovernanceProposal,
                          executed_by=None) -> GovernanceExecution:
        """
        Execute a passed proposal -- apply the proposed changes।
        This is where governance becomes reality:
        changes are applied to the actual loyalty system।
        """
        if proposal.status != PROPOSAL_STATUS_PASSED:
            raise ValueError(
                f'Can only execute PASSED proposals (current: {proposal.status})'
            )

        execution_log = []
        changes_applied = {}
        success = False

        try:
            proposed = proposal.proposed_changes
            ptype = proposal.proposal_type

            if ptype == PROPOSAL_TYPE_EARN_RULE:
                result = GovernanceExecutor.apply_earn_rule_change(proposed)
                changes_applied = result
                execution_log.append(f'Earn rule updated: {result}')

            elif ptype == PROPOSAL_TYPE_TIER_THRESHOLD:
                result = GovernanceExecutor.apply_tier_threshold_change(proposed)
                changes_applied = result
                execution_log.append(f'Tier threshold updated: {result}')

            elif ptype == PROPOSAL_TYPE_CATALOG_ITEM:
                result = GovernanceExecutor.apply_catalog_item(proposed, proposal.tenant)
                changes_applied = result
                execution_log.append(f'Catalog item added: {result}')

            elif ptype == PROPOSAL_TYPE_EXPIRY_POLICY:
                result = GovernanceExecutor.apply_expiry_policy(proposed, proposal.tenant)
                changes_applied = result
                execution_log.append(f'Expiry policy updated: {result}')

            elif ptype == PROPOSAL_TYPE_CHARITY_PARTNER:
                result = GovernanceExecutor.apply_charity_partner(proposed)
                changes_applied = result
                execution_log.append(f'Charity partner updated: {result}')

            elif ptype == PROPOSAL_TYPE_CASHOUT_RATE:
                result = GovernanceExecutor.apply_cashout_rate_change(proposed, proposal.tenant)
                changes_applied = result
                execution_log.append(f'Cashout rate updated: {result}')

            elif ptype == PROPOSAL_TYPE_CUSTOM:
                # Custom proposals require manual execution
                changes_applied = {'note': 'Custom proposal -- manual implementation required'}
                execution_log.append('Custom proposal: notify admins to implement manually')

            success = True
            proposal.status = PROPOSAL_STATUS_EXECUTED
            proposal.executed_at = timezone.now()
            proposal.save(update_fields=['status', 'executed_at'])

            logger.info('GovernanceService: executed %s successfully', proposal.proposal_id)

        except Exception as e:
            error_msg = str(e)
            execution_log.append(f'ERROR: {error_msg}')
            logger.error('GovernanceService.execute_proposal error for %s: %s',
                         proposal.proposal_id, e)

        # Create execution record
        execution = GovernanceExecution.objects.create(
            proposal=proposal,
            executed_by=executed_by,
            success=success,
            changes_applied=changes_applied,
            error_message=None if success else execution_log[-1],
            execution_log='\n'.join(execution_log),
        )

        # Notify community of execution
        try:
            from .services.NotificationService import NotificationService
            if proposal.proposer:
                emoji = '✅' if success else '❌'
                NotificationService.send(
                    proposal.proposer, 'campaign_active',
                    title=f'{emoji} Proposal Executed!',
                    body=f'"{proposal.title}" has been implemented! The community spoke.',
                    priority='high',
                )
        except Exception:
            pass

        return execution

    @staticmethod
    def cancel_proposal(proposal: GovernanceProposal, cancelled_by=None,
                         reason: str = '') -> GovernanceProposal:
        """Cancel an active or draft proposal."""
        if proposal.status in (PROPOSAL_STATUS_EXECUTED, PROPOSAL_STATUS_CANCELLED):
            raise ValueError(f'Cannot cancel proposal in {proposal.status} status.')

        proposal.status = PROPOSAL_STATUS_CANCELLED
        proposal.cancelled_at = timezone.now()
        proposal.save(update_fields=['status', 'cancelled_at'])

        logger.info('GovernanceService: proposal %s cancelled -- %s',
                    proposal.proposal_id, reason)
        return proposal

    @staticmethod
    def get_active_proposals(tenant=None) -> list:
        """Get all currently active proposals."""
        qs = GovernanceProposal.objects.filter(
            status=PROPOSAL_STATUS_ACTIVE,
            voting_end__gt=timezone.now(),
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.order_by('voting_end'))

    @staticmethod
    def get_proposal_feed(tenant=None, limit: int = 20) -> list:
        """Get recent proposals for the governance feed (all statuses)."""
        qs = GovernanceProposal.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.order_by('-created_at')[:limit])

    @staticmethod
    def get_customer_voting_history(customer, limit: int = 20) -> list:
        """Get customer's voting history."""
        return list(
            GovernanceVote.objects.filter(customer=customer)
            .select_related('proposal')
            .order_by('-voted_at')[:limit]
        )

    @staticmethod
    def get_customer_governance_stats(customer) -> dict:
        """Get governance participation stats for a customer."""
        from .selectors import get_current_tier
        config = GovernanceService.get_or_create_config(customer.tenant)

        voting_power = VotingPowerCalculator.calculate(customer, config)
        eligible_to_vote, vote_reason = VotingPowerCalculator.is_eligible_to_vote(
            customer, config
        )
        eligible_to_propose, propose_reason = VotingPowerCalculator.is_eligible_to_propose(
            customer, config
        )

        total_votes = GovernanceVote.objects.filter(customer=customer).count()
        votes_for = GovernanceVote.objects.filter(customer=customer, vote=VOTE_FOR).count()
        proposals_created = GovernanceProposal.objects.filter(proposer=customer).count()

        return {
            'voting_power': str(voting_power),
            'power_formula': config.voting_power_formula,
            'eligible_to_vote': eligible_to_vote,
            'vote_eligibility_reason': vote_reason if not eligible_to_vote else 'Eligible',
            'eligible_to_propose': eligible_to_propose,
            'propose_eligibility_reason': propose_reason if not eligible_to_propose else 'Eligible',
            'total_votes_cast': total_votes,
            'votes_for': votes_for,
            'votes_against': total_votes - votes_for,
            'proposals_created': proposals_created,
            'active_proposals': len(GovernanceService.get_active_proposals(customer.tenant)),
        }


# ─── Governance Executor ──────────────────────────────────────────────────────

class GovernanceExecutor:
    """
    Applies approved governance changes to the loyalty system।
    Called by GovernanceService.execute_proposal()।
    Each method validates, applies, and returns a dict of what changed।
    """

    @staticmethod
    def apply_earn_rule_change(proposed: dict) -> dict:
        """
        Apply an earn rule change proposed by governance।
        proposed: {
          'rule_id': int,           # ID of rule to change
          'field': str,             # 'earn_value', 'multiplier', 'is_active'
          'new_value': str,         # New value as string
          'rule_name': str,         # Optional: for new rules
        }
        """
        from .models.earn_rules import EarnRule

        rule_id = proposed.get('rule_id')
        field = proposed.get('field', 'earn_value')
        new_value = proposed.get('new_value')

        if not rule_id or not new_value:
            raise ValueError('earn_rule change requires rule_id and new_value')

        rule = EarnRule.objects.get(id=rule_id)
        old_value = str(getattr(rule, field, ''))

        if field == 'earn_value':
            rule.earn_value = Decimal(new_value)
        elif field == 'multiplier':
            rule.multiplier = Decimal(new_value)
        elif field == 'is_active':
            rule.is_active = new_value.lower() in ('true', '1', 'yes')
        elif field == 'name':
            rule.name = new_value

        rule.save(update_fields=[field, 'updated_at'])

        logger.info('GovernanceExecutor: earn rule #%d %s changed %s -> %s',
                    rule_id, rule.name, old_value, new_value)
        return {
            'rule_id': rule_id,
            'rule_name': rule.name,
            'field': field,
            'old_value': old_value,
            'new_value': new_value,
        }

    @staticmethod
    def apply_tier_threshold_change(proposed: dict) -> dict:
        """
        Change tier minimum points threshold।
        proposed: {
          'tier_id': int,
          'new_min_points': str,
        }
        """
        from .models.tiers import LoyaltyTier

        tier_id = proposed.get('tier_id')
        new_min = proposed.get('new_min_points')

        if not tier_id or not new_min:
            raise ValueError('tier_threshold change requires tier_id and new_min_points')

        tier = LoyaltyTier.objects.get(id=tier_id)
        old_min = str(tier.min_points)
        tier.min_points = Decimal(new_min)
        tier.save(update_fields=['min_points', 'updated_at'])

        logger.info('GovernanceExecutor: tier %s min_points changed %s -> %s',
                    tier.name, old_min, new_min)
        return {
            'tier_id': tier_id,
            'tier_name': tier.name,
            'old_min_points': old_min,
            'new_min_points': new_min,
        }

    @staticmethod
    def apply_catalog_item(proposed: dict, tenant=None) -> dict:
        """
        Add a new catalog item voted in by community।
        proposed: {
          'name': str,
          'description': str,
          'reward_type': str,
          'points_cost': str,
          'cash_value': str,
        }
        """
        from .models.catalog import RewardCatalogItem

        name = proposed.get('name')
        if not name:
            raise ValueError('catalog_item requires name')

        item = RewardCatalogItem.objects.create(
            name=name,
            description=proposed.get('description', ''),
            reward_type=proposed.get('reward_type', 'voucher'),
            points_cost=Decimal(proposed.get('points_cost', '500')),
            cash_value=Decimal(proposed.get('cash_value', '50')),
            is_active=True,
            tenant=tenant,
        )

        logger.info('GovernanceExecutor: catalog item "%s" added by governance', name)
        return {'item_id': item.id, 'item_name': item.name, 'points_cost': str(item.points_cost)}

    @staticmethod
    def apply_expiry_policy(proposed: dict, tenant=None) -> dict:
        """
        Change points expiry policy।
        proposed: {'expiry_days': int}
        """
        from .models.audit import SystemConfig

        expiry_days = proposed.get('expiry_days')
        if not expiry_days:
            raise ValueError('expiry_policy requires expiry_days')

        SystemConfig.objects.update_or_create(
            key='points.expiry_days',
            tenant=tenant,
            defaults={
                'value': str(expiry_days),
                'value_type': 'integer',
                'description': f'Points expiry: {expiry_days} days (set by governance)',
            },
        )

        logger.info('GovernanceExecutor: expiry policy set to %s days by governance', expiry_days)
        return {'expiry_days': expiry_days}

    @staticmethod
    def apply_charity_partner(proposed: dict) -> dict:
        """
        Update charity donation allocation।
        proposed: {'cause_id': int, 'allocation_pct': str}
        """
        from .models.family_eco import CharityCause

        cause_id = proposed.get('cause_id')
        allocation = proposed.get('allocation_pct', '10')

        if cause_id:
            cause = CharityCause.objects.filter(id=cause_id).first()
            if cause:
                cause.is_featured = True
                cause.save(update_fields=['is_featured'])
                logger.info('GovernanceExecutor: charity %s featured by governance', cause.name)
                return {'cause_id': cause_id, 'cause_name': cause.name, 'allocation_pct': allocation}

        return {'note': 'Charity partner updated -- manual configuration may be required'}

    @staticmethod
    def apply_cashout_rate_change(proposed: dict, tenant=None) -> dict:
        """
        Change cashout rate (points per BDT)।
        proposed: {'method': str, 'new_rate': str}
        """
        from .models.cashout import CashoutRate

        method = proposed.get('method', 'mobile_wallet')
        new_rate = proposed.get('new_rate')

        if not new_rate:
            raise ValueError('cashout_rate requires new_rate')

        rate, created = CashoutRate.objects.get_or_create(
            cashout_method=method,
            tenant=tenant,
            defaults={
                'points_per_unit': Decimal(new_rate),
                'currency': 'BDT',
                'is_active': True,
            },
        )
        if not created:
            old_rate = str(rate.points_per_unit)
            rate.points_per_unit = Decimal(new_rate)
            rate.save(update_fields=['points_per_unit'])
            logger.info('GovernanceExecutor: cashout rate %s changed to %s by governance',
                        method, new_rate)
            return {'method': method, 'old_rate': old_rate, 'new_rate': new_rate}

        return {'method': method, 'new_rate': new_rate, 'created': True}


# ─── Scheduled Tasks Helpers ──────────────────────────────────────────────────

def finalize_expired_proposals(tenant=None) -> dict:
    """
    Finalize all proposals whose voting period has ended।
    Call from Celery task daily।
    """
    expired = GovernanceProposal.objects.filter(
        status=PROPOSAL_STATUS_ACTIVE,
        voting_end__lte=timezone.now(),
    )
    if tenant:
        expired = expired.filter(tenant=tenant)

    finalized = {'passed': 0, 'rejected': 0, 'expired': 0, 'errors': 0}

    for proposal in expired:
        try:
            result = GovernanceService.finalize_proposal(proposal)
            finalized[result.status] = finalized.get(result.status, 0) + 1
        except Exception as e:
            finalized['errors'] += 1
            logger.error('finalize_expired_proposals error for %s: %s',
                         proposal.proposal_id, e)

    logger.info('finalize_expired_proposals: %s', finalized)
    return finalized
