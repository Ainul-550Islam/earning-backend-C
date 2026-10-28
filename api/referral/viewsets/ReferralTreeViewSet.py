# api/referral/viewsets/ReferralTreeViewSet.py
# Referral tree: my tree, depth, earnings per level, downline
# ============================================================

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)


class ReferralTreeViewSet(APIView):
    """
    GET /api/referral/tree/
    User এর complete referral tree।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.services.ReferralTreeService import ReferralTreeService

        tree_data = ReferralTreeService.get_tree_data(request.user)
        return Response({'success': True, 'tree': tree_data})


class ReferralDownlineView(APIView):
    """
    GET /api/referral/tree/downline/?level=1
    User এর downline members।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.services.ReferralTreeService import ReferralTreeService

        level = request.query_params.get('level')
        max_results = min(200, int(request.query_params.get('limit', 50)))

        if level:
            try:
                level = int(level)
                if level not in [1, 2, 3]:
                    return Response({'error': 'level must be 1, 2, or 3'}, status=400)
            except ValueError:
                return Response({'error': 'Invalid level'}, status=400)
        else:
            level = None

        downline = ReferralTreeService.get_downline(
            user=request.user,
            level=level,
            max_results=max_results,
        )

        return Response({
            'success': True,
            'level': level,
            'downline': downline,
            'total': len(downline),
        })


class ReferralUplineView(APIView):
    """
    GET /api/referral/tree/upline/
    User কে কে refer করেছে (ancestors)।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.services.ReferralTreeService import ReferralTreeService

        upline = ReferralTreeService.get_upline(request.user)
        return Response({'success': True, 'upline': upline})


class TreeEarningsByLevelView(APIView):
    """
    GET /api/referral/tree/earnings-by-level/
    Level অনুযায়ী earnings breakdown।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.models import ReferralTree

        try:
            tree = ReferralTree.objects.get(root_user=request.user)
        except ReferralTree.DoesNotExist:
            return Response({
                'success': True,
                'breakdown': {
                    'level1': {'count': 0, 'earned': 0},
                    'level2': {'count': 0, 'earned': 0},
                    'level3': {'count': 0, 'earned': 0},
                    'total': 0,
                }
            })

        return Response({
            'success': True,
            'breakdown': {
                'level1': {
                    'count': tree.level1_count,
                    'earned': float(tree.level1_earned),
                },
                'level2': {
                    'count': tree.level2_count,
                    'earned': float(tree.level2_earned),
                },
                'level3': {
                    'count': tree.level3_count,
                    'earned': float(tree.level3_earned),
                },
                'total': float(tree.total_earned),
                'total_members': tree.total_members,
                'last_updated': (
                    tree.last_rebuilt_at.isoformat()
                    if tree.last_rebuilt_at else None
                ),
            }
        })