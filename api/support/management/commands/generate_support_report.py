# api/support/management/commands/generate_support_report.py
from django.core.management.base import BaseCommand
class Command(BaseCommand):
    help = "Generate support report for a period"
    def add_arguments(self, p):
        p.add_argument("--days", type=int, default=30)
        p.add_argument("--type", choices=["tickets","agents","csat","sla"], default="tickets")
    def handle(self, *args, **options):
        days  = options["days"]
        rtype = options["type"]
        if rtype == "tickets":
            from api.support.reports.ticket_report import ticket_report
            data = ticket_report.generate(days=days)
            summary = data.get("summary", {})
            self.stdout.write(f"Tickets: {summary.get("total",0)} total, {summary.get("resolved",0)} resolved")
        elif rtype == "agents":
            from api.support.reports.agent_report import agent_report
            data = agent_report.generate(days=days)
            for a in data[:5]:
                self.stdout.write(f"  {a["username"]}: {a["resolved"]} resolved, CSAT {a["csat_score"]}")
        elif rtype == "csat":
            from api.support.reports.csat_report import csat_report
            data = csat_report.generate(days=days)
            self.stdout.write(f"CSAT: {data.get("avg_score",0)}/5.0, NPS: {data.get("nps_score",0)}")
        elif rtype == "sla":
            from api.support.reports.sla_report import sla_report
            data = sla_report.generate(days=days)
            self.stdout.write(f"SLA Compliance: {data.get("compliance_rate",0)}%")
        self.stdout.write(self.style.SUCCESS("Report generated"))