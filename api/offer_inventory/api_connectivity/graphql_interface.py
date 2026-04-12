# api/offer_inventory/api_connectivity/graphql_interface.py
"""
GraphQL Interface — Offer Inventory GraphQL schema definitions.
Uses graphene-django for schema generation.
Provides flexible querying for frontend and mobile clients.
"""
import logging

logger = logging.getLogger(__name__)

# GraphQL schema definition (requires: pip install graphene-django)
GRAPHQL_AVAILABLE = False
try:
    import graphene
    from graphene_django import DjangoObjectType
    GRAPHQL_AVAILABLE = True
except ImportError:
    logger.warning('graphene-django not installed. GraphQL interface disabled.')


def get_schema():
    """Build and return the GraphQL schema if graphene is available."""
    if not GRAPHQL_AVAILABLE:
        return None

    from api.offer_inventory.models import (
        Offer, OfferNetwork, OfferCategory, Conversion,
        Click, UserProfile, WithdrawalRequest, DailyStat,
    )

    class OfferNetworkType(DjangoObjectType):
        class Meta:
            model  = OfferNetwork
            fields = ('id', 'name', 'slug', 'status', 'priority', 'revenue_share_pct')

    class OfferCategoryType(DjangoObjectType):
        class Meta:
            model  = OfferCategory
            fields = ('id', 'name', 'slug', 'icon_url', 'is_active')

    class OfferType(DjangoObjectType):
        is_available = graphene.Boolean()

        class Meta:
            model  = Offer
            fields = (
                'id', 'title', 'description', 'image_url', 'offer_url',
                'status', 'reward_type', 'reward_amount', 'payout_amount',
                'estimated_time', 'difficulty', 'is_featured',
                'conversion_rate', 'total_completions',
                'starts_at', 'expires_at',
            )

        def resolve_is_available(self, info):
            return self.is_available

    class ConversionType(DjangoObjectType):
        class Meta:
            model  = Conversion
            fields = (
                'id', 'payout_amount', 'reward_amount',
                'country_code', 'postback_sent', 'created_at',
            )

    class DailyStatType(DjangoObjectType):
        class Meta:
            model  = DailyStat
            fields = (
                'date', 'total_clicks', 'unique_clicks',
                'total_conversions', 'approved_conversions',
                'total_revenue', 'user_payouts', 'platform_profit',
                'new_users', 'active_users', 'cvr',
            )

    class OfferQuery(graphene.ObjectType):
        """GraphQL Query root for offer inventory."""
        offers = graphene.List(
            OfferType,
            status=graphene.String(),
            category=graphene.String(),
            limit=graphene.Int(default_value=20),
        )
        offer      = graphene.Field(OfferType, id=graphene.UUID(required=True))
        networks   = graphene.List(OfferNetworkType)
        categories = graphene.List(OfferCategoryType)
        daily_stats = graphene.List(DailyStatType, days=graphene.Int(default_value=7))

        def resolve_offers(self, info, status='active', category=None, limit=20):
            qs = Offer.objects.filter(status=status)
            if category:
                qs = qs.filter(category__slug=category)
            return qs[:limit]

        def resolve_offer(self, info, id):
            try:
                return Offer.objects.get(id=id)
            except Offer.DoesNotExist:
                return None

        def resolve_networks(self, info):
            return OfferNetwork.objects.filter(status='active')

        def resolve_categories(self, info):
            return OfferCategory.objects.filter(is_active=True)

        def resolve_daily_stats(self, info, days=7):
            from datetime import timedelta
            from django.utils import timezone
            since = timezone.now().date() - timedelta(days=days)
            return DailyStat.objects.filter(date__gte=since).order_by('-date')

    schema = graphene.Schema(query=OfferQuery)
    return schema


# Django URL configuration for GraphQL endpoint
def get_graphql_view():
    """Return GraphQL view for URL configuration."""
    if not GRAPHQL_AVAILABLE:
        return None
    try:
        from graphene_django.views import GraphQLView
        schema = get_schema()
        return GraphQLView.as_view(graphiql=True, schema=schema)
    except Exception as e:
        logger.error(f'GraphQL view creation failed: {e}')
        return None
