# engagement/services/auction_service.py
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .coin_service import CoinService
from .notification_service import NotificationService
from ..models.auction import Auction, AuctionBid, AuctionWatchlist
from ..exceptions import EngagementError

logger = logging.getLogger(__name__)


class AuctionError(EngagementError):
    default_detail = "Auction error."
    default_code   = "auction_error"


class AuctionService:

    @classmethod
    @transaction.atomic
    def place_bid(cls, user, auction_id: int, amount: Decimal, tenant=None) -> dict:
        """
        Place a bid. Escrows coins immediately.
        Refunds previous highest bidder automatically.
        """
        auction = Auction.objects.select_for_update().get(pk=auction_id)

        if not auction.is_live:
            raise AuctionError("Auction is not currently active.")

        min_bid = max(auction.starting_bid, auction.current_bid + auction.bid_increment)
        if amount < min_bid:
            raise AuctionError(f"Minimum bid is {min_bid} coins.")

        # Deduct coins (escrow)
        CoinService.deduct(user, amount, source="auction_bid", ref_id=str(auction_id))

        # Refund previous highest bidder
        prev_winner = AuctionBid.objects.filter(
            auction=auction, is_winning=True
        ).select_for_update().first()
        if prev_winner and prev_winner.user != user:
            CoinService.add(prev_winner.user, prev_winner.coins_held,
                            source="auction_outbid_refund", ref_id=str(auction_id))
            prev_winner.is_winning     = False
            prev_winner.coins_returned = True
            prev_winner.save(update_fields=["is_winning", "coins_returned"])
            # Notify outbid user
            NotificationService.send(
                prev_winner.user, "reward",
                title="You've been outbid!",
                body=f"Someone placed a higher bid on '{auction.title}'. Your coins have been refunded.",
                data={"auction_id": auction_id, "refunded": float(prev_winner.coins_held)},
                tenant=tenant,
            )

        # Create new bid
        bid = AuctionBid.objects.create(
            user=user,
            tenant=tenant or getattr(user, "tenant", None),
            auction=auction,
            amount=amount,
            is_winning=True,
            coins_held=amount,
        )

        # Update auction state
        auction.current_bid = amount
        auction.total_bids  += 1
        auction.save(update_fields=["current_bid", "total_bids"])

        logger.info("AuctionService: user=%s bid=%s on auction=%s", user.pk, amount, auction_id)
        return {
            "success":    True,
            "amount":     float(amount),
            "is_winning": True,
            "auction_id": auction_id,
        }

    @classmethod
    @transaction.atomic
    def close_auction(cls, auction_id: int, tenant=None) -> dict:
        """
        Close a finished auction. Award item to winner, refund losers.
        Called by Celery task.
        """
        auction = Auction.objects.select_for_update().get(pk=auction_id)
        if auction.status in ("completed", "cancelled"):
            return {"already_closed": True}

        auction.status = "ended"
        winning_bid    = AuctionBid.objects.filter(auction=auction, is_winning=True).first()

        if winning_bid:
            auction.winner = winning_bid.user
            # Grant item to winner
            if auction.item_slug:
                from ..models.shop import ShopItem
                from .shop_service import ShopService
                try:
                    item = ShopItem.objects.filter(slug=auction.item_slug).first()
                    if item:
                        from ..models.shop import UserInventory
                        inv, _ = UserInventory.objects.get_or_create(
                            user=winning_bid.user, item=item,
                            defaults={"tenant": tenant},
                        )
                        inv.quantity += auction.item_quantity
                        inv.save(update_fields=["quantity"])
                except Exception as exc:
                    logger.error("AuctionService: item grant failed: %s", exc)

            NotificationService.send(
                winning_bid.user, "reward",
                title=f"You won the auction: {auction.title}!",
                body=f"Congratulations! Your winning bid was {winning_bid.amount} coins.",
                data={"auction_id": auction_id, "won_amount": float(winning_bid.amount)},
                tenant=tenant,
            )

        auction.status = "completed"
        auction.save(update_fields=["status", "winner"])
        logger.info("AuctionService: closed auction=%s winner=%s", auction_id, getattr(winning_bid, "user_id", None))
        return {"closed": True, "winner_id": getattr(winning_bid, "user_id", None)}

    @classmethod
    def watch(cls, user, auction_id: int, tenant=None) -> dict:
        auction = Auction.objects.get(pk=auction_id)
        obj, created = AuctionWatchlist.objects.get_or_create(
            user=user, auction=auction,
            defaults={"tenant": tenant or getattr(user, "tenant", None)},
        )
        if not created:
            obj.delete()
            return {"watching": False}
        return {"watching": True}
