# api/djoyalty/services/EcoLoyaltyService.py
"""
EcoLoyaltyService -- eco/green points + charity donation service।
from django.db.models import Q
World: Shell eco-rewards, major retailers green points 2024-2025।
"""
from django.db.models import Q
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class EcoLoyaltyService:

    @staticmethod
    @transaction.atomic
    def record_eco_action(customer, action_type: str, proof_url: str = None,
                           location: str = None, tenant=None):
        """
        Customer eco action record করো + green points award করো।
        """
        from ..models.family_eco import EcoAction, CustomerEcoAction, CustomerEcoStats
        from ..models.points import LoyaltyPoints, PointsLedger
        from ..choices import LEDGER_CREDIT

        action_config = EcoAction.objects.filter(
            action_type=action_type, is_active=True
        ).filter(
            Q(tenant=tenant or customer.tenant) | Q(tenant__isnull=True)
        ).first()

        if not action_config:
            raise ValueError(f'No active eco action config for type: {action_type}')

        # Daily limit check
        today = timezone.now().date()
        today_count = CustomerEcoAction.objects.filter(
            customer=customer,
            eco_action=action_config,
            completed_at__date=today,
        ).count()
        if today_count >= action_config.max_per_customer_per_day:
            raise ValueError(f'Daily eco action limit reached for {action_type}')

        # Award points
        lp, _ = LoyaltyPoints.objects.get_or_create(
            customer=customer,
            defaults={'tenant': tenant or customer.tenant, 'balance': Decimal('0')},
        )
        lp.credit(action_config.points_reward)

        PointsLedger.objects.create(
            customer=customer,
            tenant=tenant or customer.tenant,
            txn_type=LEDGER_CREDIT,
            source='bonus',
            points=action_config.points_reward,
            balance_after=lp.balance,
            description=f'Eco action: {action_config.name}',
        )

        # Record eco action
        eco_record = CustomerEcoAction.objects.create(
            customer=customer,
            eco_action=action_config,
            points_awarded=action_config.points_reward,
            co2_saved_kg=action_config.co2_saved_kg,
            proof_url=proof_url,
            is_verified=not action_config.requires_proof,
            location=location,
        )

        # Update eco stats
        stats, _ = CustomerEcoStats.objects.get_or_create(customer=customer)
        stats.total_eco_points += action_config.points_reward
        stats.total_co2_saved_kg += action_config.co2_saved_kg
        stats.total_eco_actions += 1
        stats.trees_equivalent = stats.total_co2_saved_kg / Decimal('21.77')  # avg tree absorbs 21.77kg CO2/year
        stats.eco_tier = EcoLoyaltyService._compute_eco_tier(stats.total_co2_saved_kg)
        stats.save()

        # Award badge if configured
        if action_config.badge_reward:
            from ..services.engagement.BadgeService import BadgeService
            BadgeService.check_and_award(customer, 'manual', tenant=tenant)

        logger.info('EcoLoyaltyService: %s eco action recorded for %s (+%s pts, %s kg CO₂)',
                    action_type, customer.code, action_config.points_reward, action_config.co2_saved_kg)
        return eco_record

    @staticmethod
    def _compute_eco_tier(co2_saved_kg: Decimal) -> str:
        if co2_saved_kg >= 1000:
            return 'planet'
        elif co2_saved_kg >= 200:
            return 'forest'
        elif co2_saved_kg >= 50:
            return 'tree'
        elif co2_saved_kg >= 10:
            return 'sapling'
        return 'seedling'

    @staticmethod
    @transaction.atomic
    def donate_to_charity(customer, charity_id: int, points_to_donate: Decimal, tenant=None):
        """
        Customer এর points charity-তে donate করো।
        """
        from ..models.family_eco import CharityCause, CharityDonation
        from ..models.points import LoyaltyPoints, PointsLedger
        from ..exceptions import InsufficientPointsError
        from ..choices import LEDGER_DEBIT

        charity = CharityCause.objects.get(id=charity_id, is_active=True)

        if points_to_donate < charity.min_donation_points:
            raise ValueError(f'Minimum donation is {charity.min_donation_points} points')

        lp = customer.loyalty_points.first()
        if not lp or lp.balance < points_to_donate:
            raise InsufficientPointsError(
                available=lp.balance if lp else 0,
                required=points_to_donate,
            )

        # Deduct points
        lp.debit(points_to_donate)

        # Calculate currency value
        currency_value = (points_to_donate / charity.points_per_donation_unit).quantize(Decimal('0.01'))

        PointsLedger.objects.create(
            customer=customer,
            tenant=tenant or customer.tenant,
            txn_type=LEDGER_DEBIT,
            source='redemption',
            points=points_to_donate,
            balance_after=lp.balance,
            description=f'Charity donation: {charity.name}',
        )

        # Record donation
        donation = CharityDonation.objects.create(
            customer=customer,
            charity=charity,
            tenant=tenant or customer.tenant,
            points_donated=points_to_donate,
            currency_value=currency_value,
        )

        # Update charity totals
        charity.total_points_donated += points_to_donate
        charity.total_currency_donated += currency_value
        charity.save(update_fields=['total_points_donated', 'total_currency_donated'])

        logger.info('EcoLoyaltyService: %s donated %s pts to %s',
                    customer.code, points_to_donate, charity.name)
        return donation

    @staticmethod
    def get_customer_eco_summary(customer) -> dict:
        """Customer এর eco impact summary।"""
        from ..models.family_eco import CustomerEcoStats
        stats = CustomerEcoStats.objects.filter(customer=customer).first()
        if not stats:
            return {
                'total_eco_points': '0',
                'total_co2_saved_kg': '0',
                'total_eco_actions': 0,
                'eco_tier': 'seedling',
                'trees_equivalent': '0',
            }
        return {
            'total_eco_points': str(stats.total_eco_points),
            'total_co2_saved_kg': str(stats.total_co2_saved_kg),
            'total_eco_actions': stats.total_eco_actions,
            'eco_tier': stats.eco_tier,
            'trees_equivalent': str(stats.trees_equivalent),
        }



    @staticmethod
    def log_action(customer, action_type: str, proof_url: str = None,
                   quantity: float = 1.0, metadata: dict = None, tenant=None) -> dict:
        """Alias for record_eco_action() -- matches EcoFamilyViewSet call signature."""
        return EcoLoyaltyService.record_eco_action(
            customer=customer,
            action_type=action_type,
            proof_url=proof_url or '',
            quantity=quantity,
            metadata=metadata,
            tenant=tenant,
        )
