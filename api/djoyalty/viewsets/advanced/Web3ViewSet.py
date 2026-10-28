# djoyalty/viewsets/advanced/Web3ViewSet.py
"""
Web3 / DAO Governance ViewSet -- exposes web3_loyalty.py and dao_governance.py।
Web3: NFT badges, wallet linking, on-chain point mirroring।
DAO: Community governance proposals, voting, execution।
Previously: both fully built, zero API routes।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers as drf_serializers
from ...serializers.AnalyticsSerializer import (
    CustomerWalletSerializer, NFTBadgeSerializer,
    LinkWalletInputSerializer, DAOProposalSerializer,
    DAOCreateProposalInputSerializer, DAOVoteInputSerializer,
)
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet


# ─── Web3 ViewSet ──────────────────────────────────────────────────────────────

class Web3ViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    GET  /web3/status/                    -- web3 feature enabled?
    GET  /web3/my-wallet/                 -- customer's linked wallet
    POST /web3/link-wallet/               -- link MetaMask/wallet address
    GET  /web3/my-nfts/                   -- customer's NFT badges
    POST /web3/mint-badge/                -- mint badge as NFT (admin)
    POST /web3/mirror-balance/            -- mirror points balance on-chain
    """
    permission_classes = [IsAuthenticated]

    def _get_customer(self, request):
        c = getattr(request, 'loyalty_customer', None)
        if c:
            return c
        cid = request.query_params.get('customer_id') or request.data.get('customer_id')
        if cid:
            from ...models.core import Customer
            return Customer.objects.filter(pk=cid).first()
        return None

    @action(detail=False, methods=['get'], url_path='status')
    def status(self, request):
        try:
            from ...web3_loyalty import Web3LoyaltyService
            return Response({
                'enabled': Web3LoyaltyService.is_enabled(),
                'config': Web3LoyaltyService.get_web3_config() if Web3LoyaltyService.is_enabled() else {},
            })
        except Exception as e:
            return Response({'enabled': False, 'error': str(e)})

    @action(detail=False, methods=['get'], url_path='my-nfts')
    def my_nfts(self, request):
        customer = self._get_customer(request)
        if not customer:
            return Response({'nfts': []})
        try:
            from ...web3_loyalty import Web3LoyaltyService
            nfts = Web3LoyaltyService.get_customer_nft_badges(customer)
            return Response({'nfts': nfts})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='link-wallet')
    def link_wallet(self, request):
        customer = self._get_customer(request)
        if not customer:
            return self.not_found('Customer not found')
        wallet_address = request.data.get('wallet_address', '')
        wallet_type    = request.data.get('wallet_type', 'metamask')
        signature      = request.data.get('signature', '')
        if not wallet_address:
            return self.err('wallet_address required')
        try:
            from ...web3_loyalty import Web3LoyaltyService
            # Verify ownership if signature provided
            if signature:
                verified = Web3LoyaltyService.verify_wallet_ownership(
                    customer=customer,
                    wallet_address=wallet_address,
                    signature=signature,
                )
                if not verified:
                    return self.err('Wallet ownership verification failed')
            wallet = Web3LoyaltyService.link_wallet(
                customer=customer,
                wallet_address=wallet_address,
                wallet_type=wallet_type,
            )
            return Response({
                'status': 'linked',
                'wallet_id': wallet.id,
                'address': wallet.wallet_address,
                'type': wallet_type,
            }, status=201)
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['post'], url_path='mint-badge',
            permission_classes=[IsLoyaltyAdmin])
    def mint_badge(self, request):
        customer_id = request.data.get('customer_id')
        badge_id    = request.data.get('badge_id')
        if not customer_id or not badge_id:
            return self.err('customer_id and badge_id required')
        try:
            from ...models.core import Customer
            from ...models.engagement import Badge
            from ...web3_loyalty import Web3LoyaltyService
            from django.shortcuts import get_object_or_404
            customer = get_object_or_404(Customer, pk=customer_id)
            badge    = get_object_or_404(Badge, pk=badge_id)
            nft = Web3LoyaltyService.mint_badge_nft(customer=customer, badge=badge)
            return Response({
                'status': 'minted',
                'nft_id': nft.id,
                'token_id': nft.token_id,
            }, status=201)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


# ─── DAO Governance ViewSet ────────────────────────────────────────────────────

class DAOGovernanceViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    GET  /dao/proposals/                -- list active proposals
    GET  /dao/proposals/{id}/           -- proposal detail + votes
    POST /dao/proposals/create/         -- create proposal (admin)
    POST /dao/proposals/{id}/vote/      -- cast vote
    GET  /dao/proposals/{id}/results/   -- voting results
    POST /dao/proposals/{id}/execute/   -- execute passed proposal (admin)
    GET  /dao/config/                   -- governance config (tier weights etc.)
    """
    permission_classes = [IsAuthenticated]

    def _get_customer(self, request):
        c = getattr(request, 'loyalty_customer', None)
        if c:
            return c
        cid = request.query_params.get('customer_id') or request.data.get('customer_id')
        if cid:
            from ...models.core import Customer
            return Customer.objects.filter(pk=cid).first()
        return None

    @action(detail=False, methods=['get'], url_path='proposals')
    def proposals(self, request):
        from ...dao_governance import GovernanceProposal
        qs = GovernanceProposal.objects.filter(
            status__in=['active', 'passed', 'executed']
        ).order_by('-created_at')[:50]
        data = [{
            'id': p.id,
            'proposal_id': p.proposal_id(),
            'title': p.title,
            'status': p.status,
            'is_active': p.is_active(),
            'total_votes': p.total_votes(),
            'for_percentage': str(p.for_percentage()),
            'quorum_reached': p.quorum_reached(),
            'time_remaining': p.time_remaining(),
        } for p in qs]
        return Response({'proposals': data})

    @action(detail=False, methods=['get'],
            url_path='proposals/(?P<proposal_id>[0-9]+)')
    def proposal_detail(self, request, proposal_id=None):
        from django.shortcuts import get_object_or_404
        from ...dao_governance import GovernanceProposal
        p = get_object_or_404(GovernanceProposal, pk=proposal_id)
        return Response({
            'id': p.id,
            'proposal_id': p.proposal_id(),
            'title': p.title,
            'description': p.description,
            'status': p.status,
            'is_active': p.is_active(),
            'total_votes': p.total_votes(),
            'total_voting_power': str(p.total_voting_power()),
            'for_percentage': str(p.for_percentage()),
            'quorum_reached': p.quorum_reached(),
            'time_remaining': p.time_remaining(),
            'voting_ends_at': str(p.voting_ends_at) if p.voting_ends_at else None,
        })

    @action(detail=False, methods=['post'],
            url_path='proposals/(?P<proposal_id>[0-9]+)/vote')
    def vote(self, request, proposal_id=None):
        customer = self._get_customer(request)
        if not customer:
            return self.not_found('Customer not found')
        from django.shortcuts import get_object_or_404
        from ...dao_governance import GovernanceProposal, GovernanceVote
        p = get_object_or_404(GovernanceProposal, pk=proposal_id)
        if not p.is_active():
            return self.err('Proposal is not active for voting')
        vote_choice = request.data.get('vote')  # 'for' | 'against' | 'abstain'
        if vote_choice not in ('for', 'against', 'abstain'):
            return self.err("vote must be 'for', 'against', or 'abstain'")
        # Check not already voted
        if GovernanceVote.objects.filter(proposal=p, voter=customer).exists():
            return self.err('Already voted on this proposal')
        try:
            # Compute voting power based on tier
            from ...dao_governance import GovernanceConfig
            config  = GovernanceConfig.objects.first()
            vp      = 1  # default
            if config and hasattr(customer, 'user_tier') and customer.user_tier.first():
                tier_rank = customer.user_tier.first().tier.rank if customer.user_tier.first().tier else 1
                vp = config.get_tier_weight(tier_rank)

            v = GovernanceVote.objects.create(
                proposal=p, voter=customer,
                vote=vote_choice, voting_power=vp,
            )
            return Response({
                'status': 'voted',
                'vote': vote_choice,
                'voting_power': vp,
            }, status=201)
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['post'], url_path='proposals/create',
            permission_classes=[IsLoyaltyAdmin])
    def create_proposal(self, request):
        title        = request.data.get('title', '')
        description  = request.data.get('description', '')
        voting_days  = int(request.data.get('voting_days', 7))
        if not title:
            return self.err('title required')
        try:
            from ...dao_governance import GovernanceProposal
            from django.utils import timezone
            from datetime import timedelta
            p = GovernanceProposal.objects.create(
                title=title,
                description=description,
                status='active',
                created_by=request.data.get('created_by', str(request.user)),
                voting_ends_at=timezone.now() + timedelta(days=voting_days),
            )
            return Response({
                'status': 'created',
                'proposal_id': p.proposal_id(),
                'id': p.id,
            }, status=201)
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['get'], url_path='config')
    def governance_config(self, request):
        from ...dao_governance import GovernanceConfig
        config = GovernanceConfig.objects.first()
        if not config:
            return Response({'config': None, 'message': 'No governance config found'})
        return Response({
            'quorum_percent': str(config.quorum_percent),
            'voting_period_days': config.voting_period_days,
            'tier_weights': {
                'rank_1': config.get_tier_weight(1),
                'rank_2': config.get_tier_weight(2),
                'rank_3': config.get_tier_weight(3),
                'rank_4': config.get_tier_weight(4),
            },
        })
