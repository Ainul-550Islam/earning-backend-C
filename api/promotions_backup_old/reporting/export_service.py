# api/promotions/reporting/export_service.py
import csv, io, json, logging
from datetime import date
logger = logging.getLogger('reporting.export')

class ExportService:
    """Reports CSV/JSON/Excel export করে।"""

    def export_submissions_csv(self, queryset) -> bytes:
        buf = io.StringIO()
        w   = csv.writer(buf)
        w.writerow(['ID','Campaign','Worker','Status','Reward USD','Submitted At','Reviewed At'])
        for s in queryset.values('id','campaign__title','worker__username','status','reward_usd','submitted_at','reviewed_at'):
            w.writerow([s['id'],s['campaign__title'],s['worker__username'],s['status'],s['reward_usd'],s['submitted_at'],s['reviewed_at']])
        return buf.getvalue().encode('utf-8')

    def export_transactions_csv(self, queryset) -> bytes:
        buf = io.StringIO()
        w   = csv.writer(buf)
        w.writerow(['ID','User','Type','Amount USD','Currency','Status','Method','Created At'])
        for t in queryset.values('id','user__username','transaction_type','amount_usd','currency','status','payment_method','created_at'):
            w.writerow([t['id'],t['user__username'],t['transaction_type'],t['amount_usd'],t['currency'],t['status'],t['payment_method'],t['created_at']])
        return buf.getvalue().encode('utf-8')

    def export_json(self, data: list | dict, pretty: bool = False) -> bytes:
        return json.dumps(data, indent=2 if pretty else None, default=str).encode('utf-8')

    def export_excel(self, sheets: dict) -> bytes:
        """sheets = {'Sheet1': queryset_or_list}"""
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            first = True
            for sheet_name, data in sheets.items():
                ws = wb.active if first else wb.create_sheet(sheet_name)
                ws.title = sheet_name
                first    = False
                if not data: continue
                rows = list(data) if hasattr(data,'__iter__') else data
                if rows and isinstance(rows[0], dict):
                    ws.append(list(rows[0].keys()))
                    for row in rows: ws.append(list(row.values()))
            buf = io.BytesIO()
            wb.save(buf)
            return buf.getvalue()
        except ImportError:
            return b'openpyxl required: pip install openpyxl'

    def generate_filename(self, report_type: str, ext: str = 'csv') -> str:
        return f'{report_type}_{date.today()}.{ext}'
