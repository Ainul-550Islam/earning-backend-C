# api/support/management/commands/assign_unassigned_tickets.py
from django.core.management.base import BaseCommand
class Command(BaseCommand):
    help = "Assign all unassigned tickets to available agents"
    def handle(self, *args, **options):
        from api.support.models import SupportTicket
        from api.support.services import ticket_service
        tickets = SupportTicket.objects.filter(assigned_to__isnull=True, status__in=["open","in_progress"])
        assigned = 0
        for ticket in tickets:
            ticket_service._auto_assign(ticket)
            if ticket.assigned_to:
                assigned += 1
        self.stdout.write(self.style.SUCCESS(f"Assigned {assigned}/{tickets.count()} tickets"))