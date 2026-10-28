# api/djoyalty/services/gamification/LotteryService.py
"""
LotteryService -- Raffle/lottery ticket entry and winner draw.
World reference: Smile.io sweepstakes, Voucherify raffle campaigns.

Flow:
  1. enter()       -> customer spends points to buy ticket(s)
  2. draw_winners()-> admin-triggered; picks random winners from all tickets
  3. notify_winners() -> award prizes + notify
"""
import logging
import random
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class LotteryService:

    @staticmethod
    @transaction.atomic
    def enter(customer, draw_id: int, tickets: int = 1, tenant=None) -> dict:
        """
        Enter customer into a lottery draw.
        Deducts points per ticket if draw requires it.
        Returns: {'success': True, 'tickets_issued': N, 'ticket_numbers': [...]}
        """
        try:
            from ...models.gamification import LotteryDraw, LotteryTicket
            from ...models.points import LoyaltyPoints

            try:
                draw = LotteryDraw.objects.get(id=draw_id)
            except LotteryDraw.DoesNotExist:
                return {'success': False, 'error': 'Lottery draw not found'}

            if draw.status != 'open':
                return {'success': False,
                        'error': f'Draw is not open for entry (status: {draw.status})'}

            now = timezone.now()
            if draw.entry_deadline and draw.entry_deadline < now:
                return {'success': False, 'error': 'Entry deadline has passed'}

            # Max tickets per customer
            already_entered = LotteryTicket.objects.filter(
                customer=customer, draw=draw,
            ).count()
            max_allowed = getattr(draw, 'max_tickets_per_customer', None)
            if max_allowed and (already_entered + tickets) > max_allowed:
                remaining = max_allowed - already_entered
                if remaining <= 0:
                    return {'success': False,
                            'error': f'Maximum {max_allowed} tickets per customer'}
                tickets = remaining

            # Points cost per ticket
            points_per_ticket = getattr(draw, 'points_per_ticket', Decimal('0'))
            total_cost = points_per_ticket * tickets

            if total_cost > 0:
                lp = LoyaltyPoints.objects.select_for_update().filter(
                    customer=customer
                ).first()
                if not lp or lp.balance < total_cost:
                    balance = lp.balance if lp else Decimal('0')
                    return {
                        'success': False,
                        'error': f'Insufficient points: {balance} / {total_cost} required',
                    }
                lp.debit(total_cost)

                # Ledger
                from ...models.points import PointsLedger
                from ...choices import LEDGER_DEBIT
                PointsLedger.objects.create(
                    customer=customer,
                    tenant=tenant or getattr(customer, 'tenant', None),
                    txn_type=LEDGER_DEBIT,
                    source='lottery_entry',
                    points=total_cost,
                    balance_after=lp.balance,
                    description=f'Lottery entry: {draw.name} ({tickets} ticket(s))',
                )

            # Issue tickets
            issued_tickets = []
            for i in range(tickets):
                import uuid
                ticket_number = f'T{draw_id}-{uuid.uuid4().hex[:8].upper()}'
                t = LotteryTicket.objects.create(
                    customer=customer,
                    draw=draw,
                    ticket_number=ticket_number,
                    tenant=tenant or getattr(customer, 'tenant', None),
                    points_paid=points_per_ticket,
                )
                issued_tickets.append(ticket_number)

            logger.info('LotteryService.enter: %s entered draw %s with %d ticket(s)',
                        customer.code, draw.name, tickets)

            return {
                'success': True,
                'draw_id': draw_id,
                'draw_name': draw.name,
                'tickets_issued': tickets,
                'ticket_numbers': issued_tickets,
                'total_cost': str(total_cost),
                'draw_date': draw.draw_date.isoformat() if draw.draw_date else None,
            }

        except Exception as e:
            logger.error('LotteryService.enter error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    @transaction.atomic
    def draw_winners(draw_id: int, num_winners: int = 1) -> dict:
        """
        Run the lottery draw -- randomly select winners.
        Should be called by admin or scheduled Celery task.
        Returns: {'success': True, 'winners': [{customer_id, ticket_number}, ...]}
        """
        try:
            from ...models.gamification import LotteryDraw, LotteryTicket

            try:
                draw = LotteryDraw.objects.select_for_update().get(id=draw_id)
            except LotteryDraw.DoesNotExist:
                return {'success': False, 'error': 'Draw not found'}

            if draw.status not in ('open', 'pending_draw'):
                return {'success': False,
                        'error': f'Cannot draw: status is {draw.status}'}

            # Get all eligible tickets
            tickets = list(
                LotteryTicket.objects.filter(draw=draw, is_winner=False)
                .select_related('customer')
            )
            if not tickets:
                return {'success': False, 'error': 'No tickets entered for this draw'}

            num_winners = min(num_winners, len(tickets))
            winning_tickets = random.sample(tickets, num_winners)

            winners = []
            for ticket in winning_tickets:
                ticket.is_winner = True
                ticket.won_at = timezone.now()
                ticket.save(update_fields=['is_winner', 'won_at'])

                # Award prize to winner
                prize_points = getattr(draw, 'prize_points', Decimal('0'))
                if prize_points > 0:
                    LotteryService._award_winner(ticket.customer, draw, prize_points)

                winners.append({
                    'customer_id': ticket.customer_id,
                    'customer_code': ticket.customer.code,
                    'ticket_number': ticket.ticket_number,
                    'prize_points': str(prize_points),
                })

            # Close draw
            draw.status = 'drawn'
            draw.drawn_at = timezone.now()
            draw.save(update_fields=['status', 'drawn_at'])

            logger.info('LotteryService.draw_winners: draw %s -- %d winner(s) selected',
                        draw.name, len(winners))

            return {
                'success': True,
                'draw_name': draw.name,
                'total_tickets': len(tickets),
                'num_winners': num_winners,
                'winners': winners,
            }

        except Exception as e:
            logger.error('LotteryService.draw_winners error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_customer_tickets(customer, draw_id: int) -> list:
        """Get all tickets a customer holds for a draw."""
        try:
            from ...models.gamification import LotteryTicket
            return list(
                LotteryTicket.objects.filter(
                    customer=customer, draw_id=draw_id,
                ).values('id', 'ticket_number', 'is_winner', 'won_at', 'created_at')
            )
        except Exception as e:
            logger.error('LotteryService.get_customer_tickets error: %s', e)
            return []

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _award_winner(customer, draw, prize_points: Decimal):
        """Award prize points to a lottery winner."""
        try:
            from ...services.earn.BonusEventService import BonusEventService
            BonusEventService.award_bonus(
                customer, prize_points,
                reason=f'Lottery winner: {draw.name}',
                triggered_by='lottery_win',
                tenant=getattr(customer, 'tenant', None),
            )
            # Notify
            try:
                from ...services.NotificationService import NotificationService
                NotificationService.send(
                    customer, 'badge_unlocked',
                    title='🎉 আপনি লটারি জিতেছেন!',
                    body=f'{draw.name} -- আপনি {prize_points} পয়েন্ট পেয়েছেন!',
                    icon='🏆',
                    metadata={'draw_id': draw.id, 'prize_points': str(prize_points)},
                )
            except Exception:
                pass
        except Exception as e:
            logger.error('LotteryService._award_winner error: %s', e)

    @staticmethod
    def buy_tickets(customer, draw_id: int = None, draw=None,
                    quantity: int = 1, tenant=None) -> dict:
        """
        Alias for enter() -- matches GamificationViewSet call signature.
        """
        did = draw_id or (draw.id if hasattr(draw, 'id') else None)
        if not did:
            return {'success': False, 'error': 'draw_id required'}
        return LotteryService.enter(customer=customer, draw_id=did, tickets=quantity, tenant=tenant)
