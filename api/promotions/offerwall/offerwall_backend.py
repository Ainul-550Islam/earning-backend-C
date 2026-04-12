# =============================================================================
# promotions/offerwall/offerwall_backend.py
# Offerwall Backend — Publisher-embeddable offer listing
# CPAlead's core product
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


class OfferwallBackend:
    """
    Serve optimized offer lists for publisher offerwalls.
    Filters by: GEO, Device, OS, Publisher ID, Category.
    Sorted by: EPC desc (best converting first).
    """

    def get_offers_for_wall(
        self,
        publisher_id: int,
        country: str = 'US',
        device: str = 'desktop',
        os_name: str = 'Windows',
        category: str = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """Get offers to display in publisher's offerwall."""
        from api.promotions.models import Campaign
        qs = Campaign.objects.filter(
            status='active',
            total_budget__gt=0,
        ).select_related('category', 'reward_policy')

        if category:
            qs = qs.filter(category__name=category)

        # Order by reward (proxy for EPC in simple implementation)
        qs = qs.order_by('-per_task_reward')

        total = qs.count()
        offers = qs[offset:offset + limit]

        return {
            'publisher_id': publisher_id,
            'country': country,
            'device': device,
            'total': total,
            'offset': offset,
            'limit': limit,
            'offers': [self._format_offer(o, publisher_id) for o in offers],
        }

    def _format_offer(self, campaign, publisher_id: int) -> dict:
        """Format a campaign for offerwall display."""
        return {
            'id': campaign.id,
            'title': campaign.title,
            'description': campaign.description[:200] if campaign.description else '',
            'category': campaign.category.name if campaign.category else 'other',
            'payout': str(campaign.per_task_reward),
            'payout_display': f'${campaign.per_task_reward:.2f}',
            'icon_url': getattr(campaign, 'icon_url', ''),
            'proof_type': getattr(campaign, 'default_proof_type', 'screenshot'),
            'estimated_time': '2-5 minutes',
            'cta_button': 'Complete Task',
            'tracking_url': f'/api/promotions/go/{campaign.id}/?pub={publisher_id}',
            'is_featured': float(campaign.per_task_reward) >= 5.0,
            'requires': self._get_requirements(campaign),
        }

    def _get_requirements(self, campaign) -> list:
        reqs = []
        try:
            steps = campaign.steps.all()
            for step in steps[:3]:
                reqs.append(step.instruction)
        except Exception:
            reqs = ['Complete the required action', 'Submit proof']
        return reqs or ['Complete task', 'Submit proof']

    def get_categories_with_counts(self, country: str = 'US') -> list:
        """Get available offer categories with counts."""
        from api.promotions.models import Campaign, PromotionCategory
        from django.db.models import Count
        cats = PromotionCategory.objects.filter(
            is_active=True,
        ).annotate(
            offer_count=Count('campaign', filter=Q(campaign__status='active'))
        ).order_by('-offer_count')
        return [
            {
                'name': c.name,
                'display_name': c.get_name_display(),
                'offer_count': c.offer_count,
                'icon': getattr(c, 'icon_url', ''),
            }
            for c in cats
        ]


@api_view(['GET'])
@permission_classes([AllowAny])
def offerwall_offers_view(request):
    """
    GET /api/promotions/offerwall/?pub=123&country=US&device=mobile&category=apps
    Public endpoint for publisher offerwalls.
    """
    publisher_id = request.query_params.get('pub', 0)
    wall = OfferwallBackend()
    data = wall.get_offers_for_wall(
        publisher_id=int(publisher_id) if publisher_id else 0,
        country=request.query_params.get('country', 'US'),
        device=request.query_params.get('device', 'desktop'),
        os_name=request.query_params.get('os', ''),
        category=request.query_params.get('category'),
        limit=int(request.query_params.get('limit', 20)),
        offset=int(request.query_params.get('offset', 0)),
    )
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def offerwall_categories_view(request):
    """GET /api/promotions/offerwall/categories/"""
    wall = OfferwallBackend()
    return Response({
        'categories': wall.get_categories_with_counts(
            country=request.query_params.get('country', 'US')
        )
    })
