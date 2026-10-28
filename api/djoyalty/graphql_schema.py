# api/djoyalty/graphql_schema.py
"""
AUDIT FIX (v2) -- FLOATING FILE DOCUMENTED।

This file defines a complete Graphene GraphQL schema for djoyalty।
It is NOT currently wired into urls.py or apps.py।

Status: Future feature -- wire into urls.py when graphql endpoint needed।

To activate:
  1. pip install graphene-django
  2. Add to INSTALLED_APPS: 'graphene_django'
  3. Add to urls.py:
       from graphene_django.views import GraphQLView
       from .graphql_schema import schema
       path('graphql/', GraphQLView.as_view(graphiql=True, schema=schema)),
  4. Add to settings: GRAPHENE = {'SCHEMA': 'api.djoyalty.graphql_schema.schema'}
"""
import logging

logger = logging.getLogger(__name__)

try:
    import graphene
    from graphene_django import DjangoObjectType
    GRAPHENE_AVAILABLE = True
except ImportError:
    GRAPHENE_AVAILABLE = False
    logger.debug('graphql_schema: graphene-django not installed. pip install graphene-django')


def build_schema():
    """Build and return the Djoyalty GraphQL schema (if graphene available)."""
    if not GRAPHENE_AVAILABLE:
        logger.warning('graphql_schema: graphene-django not installed, schema not built.')
        return None

    from .models.core import Customer, Txn
    from .models.points import LoyaltyPoints, PointsLedger
    from .models.tiers import LoyaltyTier, UserTier
    from .models.engagement import Badge, UserBadge
    from .models.notifications import NotificationCenter

    class CustomerType(DjangoObjectType):
        class Meta:
            model = Customer
            fields = ('id', 'code', 'email', 'phone', 'firstname', 'lastname',
                      'is_active', 'created_at')

    class LoyaltyPointsType(DjangoObjectType):
        class Meta:
            model = LoyaltyPoints
            fields = ('id', 'balance', 'lifetime_earned', 'lifetime_redeemed')

    class LoyaltyTierType(DjangoObjectType):
        class Meta:
            model = LoyaltyTier
            fields = ('id', 'name', 'rank', 'min_points', 'multiplier', 'color', 'icon')

    class UserTierType(DjangoObjectType):
        class Meta:
            model = UserTier
            fields = ('id', 'tier', 'is_current', 'joined_at')

    class PointsLedgerType(DjangoObjectType):
        class Meta:
            model = PointsLedger
            fields = ('id', 'txn_type', 'source', 'points', 'balance_after',
                      'description', 'created_at')

    class BadgeType(DjangoObjectType):
        class Meta:
            model = Badge
            fields = ('id', 'name', 'description', 'icon', 'badge_type')

    class NotificationType(DjangoObjectType):
        class Meta:
            model = NotificationCenter
            fields = ('id', 'title', 'body', 'icon', 'notification_type',
                      'is_read', 'created_at')

    class LoyaltyProfileType(graphene.ObjectType):
        customer_id = graphene.Int()
        code = graphene.String()
        balance = graphene.Float()
        tier = graphene.String()
        tier_rank = graphene.Int()
        lifetime_earned = graphene.Float()
        streak_days = graphene.Int()
        badges_count = graphene.Int()
        unread_notifications = graphene.Int()

    class Query(graphene.ObjectType):

        # Customer queries
        customer = graphene.Field(CustomerType, id=graphene.Int(), code=graphene.String())
        customers = graphene.List(CustomerType, limit=graphene.Int(default_value=20))

        # Loyalty profile
        loyalty_profile = graphene.Field(LoyaltyProfileType, customer_id=graphene.Int(required=True))

        # Points
        points = graphene.Field(LoyaltyPointsType, customer_id=graphene.Int(required=True))
        points_history = graphene.List(PointsLedgerType,
                                        customer_id=graphene.Int(required=True),
                                        limit=graphene.Int(default_value=20))

        # Tiers
        tiers = graphene.List(LoyaltyTierType)
        customer_tier = graphene.Field(UserTierType, customer_id=graphene.Int(required=True))

        # Badges
        badges = graphene.List(BadgeType)
        customer_badges = graphene.List(BadgeType, customer_id=graphene.Int(required=True))

        # Notifications
        notifications = graphene.List(NotificationType,
                                       customer_id=graphene.Int(required=True),
                                       unread_only=graphene.Boolean(default_value=False))

        def resolve_customer(self, info, id=None, code=None):
            if id:
                return Customer.objects.filter(id=id).first()
            if code:
                return Customer.objects.filter(code=code.upper()).first()
            return None

        def resolve_customers(self, info, limit=20):
            return Customer.objects.filter(is_active=True).order_by('-created_at')[:limit]

        def resolve_loyalty_profile(self, info, customer_id):
            from .selectors import get_customer_loyalty_summary
            customer = Customer.objects.filter(id=customer_id).first()
            if not customer:
                return None
            summary = get_customer_loyalty_summary(customer)
            return LoyaltyProfileType(
                customer_id=customer.id,
                code=summary['code'],
                balance=float(summary['balance']),
                tier=summary['tier'],
                tier_rank=summary['tier_rank'],
                lifetime_earned=float(summary['lifetime_earned']),
                streak_days=summary['streak_days'],
                badges_count=summary['badges_count'],
                unread_notifications=summary['unread_notifications'],
            )

        def resolve_points(self, info, customer_id):
            return LoyaltyPoints.objects.filter(customer_id=customer_id).first()

        def resolve_points_history(self, info, customer_id, limit=20):
            return PointsLedger.objects.filter(
                customer_id=customer_id, is_reversed=False
            ).order_by('-created_at')[:limit]

        def resolve_tiers(self, info):
            return LoyaltyTier.objects.filter(is_active=True).order_by('rank')

        def resolve_customer_tier(self, info, customer_id):
            return UserTier.objects.filter(
                customer_id=customer_id, is_current=True
            ).select_related('tier').first()

        def resolve_badges(self, info):
            return Badge.objects.filter(is_active=True)

        def resolve_customer_badges(self, info, customer_id):
            ubs = UserBadge.objects.filter(
                customer_id=customer_id
            ).select_related('badge')
            return [ub.badge for ub in ubs]

        def resolve_notifications(self, info, customer_id, unread_only=False):
            qs = NotificationCenter.objects.filter(customer_id=customer_id)
            if unread_only:
                qs = qs.filter(is_read=False)
            return qs.order_by('-created_at')[:20]

    class EarnPointsMutation(graphene.Mutation):
        class Arguments:
            customer_id = graphene.Int(required=True)
            amount = graphene.Float(required=True)
            source = graphene.String(default_value='purchase')
            reference_id = graphene.String()

        success = graphene.Boolean()
        points_earned = graphene.Float()
        new_balance = graphene.Float()
        error = graphene.String()

        def mutate(self, info, customer_id, amount, source='purchase', reference_id=''):
            from .use_cases import EarnPointsUseCase, EarnPointsInput
            from decimal import Decimal
            result = EarnPointsUseCase().execute(EarnPointsInput(
                customer_id=customer_id,
                amount=Decimal(str(amount)),
                source=source,
                reference_id=reference_id,
            ))
            return EarnPointsMutation(
                success=result.success,
                points_earned=float(result.points_earned),
                new_balance=float(result.new_balance),
                error=result.error,
            )

    class Mutation(graphene.ObjectType):
        earn_points = EarnPointsMutation.Field()

    return graphene.Schema(query=Query, mutation=Mutation)


# Build schema at import time (if graphene available)
schema = build_schema()
