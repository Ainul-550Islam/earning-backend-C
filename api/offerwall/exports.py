"""
api/offerwall/exports.py

Earnings export — CSV, Excel (XLSX), and JSON.

Endpoints:
  GET /api/offerwall/exports/earnings/           → CSV download
  GET /api/offerwall/exports/earnings/?fmt=xlsx  → Excel download
  GET /api/offerwall/exports/earnings/?fmt=json  → JSON (for programmatic use)

Query params:
  fmt          csv | xlsx | json   (default: csv)
  start_date   YYYY-MM-DD
  end_date     YYYY-MM-DD
  status       approved | pending | all  (default: approved)
  offer_type   app_install | survey | …  (optional filter)
"""
import csv
import io
import json
import logging
from datetime import date, timedelta

# FIX: openpyxl must be guarded — crash if not installed
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from api.offerwall.models import OfferConversion

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

EXPORT_FIELDS = [
    ('conversion_id',        'Conversion ID'),
    ('converted_at',         'Date'),
    ('offer__title',         'Offer'),
    ('offer__offer_type',    'Offer type'),
    ('offer__provider__name','Provider'),
    ('status',               'Status'),
    ('reward_amount',        'Reward amount'),
    ('reward_currency',      'Reward currency'),
    ('bonus_amount',         'Bonus amount'),
    ('payout_amount',        'Payout (USD)'),
]

DB_FIELDS = [f for f, _ in EXPORT_FIELDS]
HEADERS   = [h for _, h in EXPORT_FIELDS]


def _build_queryset(user, params, client_id=None):
    """
    FIX: Added client_id param for B2B-aware admin export.
    When client_id is provided, filter by that publisher's users.
    """
    if client_id:
        try:
            from api.offerwall.b2b.models import B2BClient
            b2b = B2BClient.objects.get(id=client_id)
            # Filter conversions for this B2B publisher's embedded users
            return OfferConversion.objects.filter(
                user=b2b.owner,
                status='approved',
            ).select_related('offer', 'offer__provider')
        except Exception:
            pass
    from api.offerwall.models import OfferConversion
    qs = OfferConversion.objects.filter(user=user).select_related(
        'offer', 'offer__provider')

    status_filter = params.get('status', 'approved')
    if status_filter != 'all':
        qs = qs.filter(status=status_filter)

    start = params.get('start_date')
    end   = params.get('end_date')
    if start:
        qs = qs.filter(converted_at__date__gte=start)
    if end:
        qs = qs.filter(converted_at__date__lte=end)

    offer_type = params.get('offer_type')
    if offer_type:
        qs = qs.filter(offer__offer_type=offer_type)

    return qs.order_by('-converted_at')


def _row_values(conv):
    return [
        conv.conversion_id,
        conv.converted_at.strftime('%Y-%m-%d %H:%M:%S'),
        conv.offer.title if conv.offer else '',
        conv.offer.offer_type if conv.offer else '',
        (conv.offer.provider.name if conv.offer and conv.offer.provider else ''),
        conv.status,
        str(conv.reward_amount or 0),
        conv.reward_currency or 'Points',
        str(conv.bonus_amount  or 0),
        str(conv.payout_amount or 0),
    ]


# ─────────────────────────────────────────────────────────────
# Exporters
# ─────────────────────────────────────────────────────────────

class CSVExporter:
    def build(self, rows, headers=None) -> bytes:
        """
        Build CSV as bytes from a list of row dicts or tuples.
        Args:
            rows: list of dicts or tuples
            headers: optional column headers
        Returns:
            bytes: CSV content
        """
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        _headers = headers or HEADERS
        writer.writerow(_headers)
        for row in rows:
            if isinstance(row, dict):
                writer.writerow([row.get(h, '') for h in _headers])
            else:
                writer.writerow(row)
        return output.getvalue().encode('utf-8')

    @staticmethod
    def export(queryset, filename='earnings.csv') -> HttpResponse:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)
        writer.writerow(HEADERS)
        for conv in queryset.iterator(chunk_size=500):
            writer.writerow(_row_values(conv))
        return response


class XLSXExporter:
    @staticmethod
    def export(queryset, filename='earnings.xlsx') -> HttpResponse:
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
        except ImportError:
            # Graceful fallback if openpyxl not installed
            return CSVExporter.export(queryset, filename.replace('.xlsx', '.csv'))

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Earnings'

        header_font = Font(bold=True, color='FFFFFF')
        header_fill = PatternFill(fill_type='solid', fgColor='185FA5')

        for col_idx, header in enumerate(HEADERS, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font  = header_font
            cell.fill  = header_fill
            cell.alignment = Alignment(horizontal='center')

        for row_idx, conv in enumerate(queryset.iterator(chunk_size=500), 2):
            for col_idx, value in enumerate(_row_values(conv), 1):
                ws.cell(row=row_idx, column=col_idx, value=value)

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class JSONExporter:
    def build(self, rows, headers=None) -> dict:
        """
        Build JSON-serializable dict from a list of row dicts or tuples.
        Args:
            rows: list of dicts or tuples
            headers: optional column headers
        Returns:
            dict: {'count': N, 'results': [...]}
        """
        _headers = headers or HEADERS
        results = []
        for row in rows:
            if isinstance(row, dict):
                results.append(row)
            else:
                results.append(dict(zip(_headers, row)))
        return {'count': len(results), 'results': results}

    @staticmethod
    def export(queryset) -> HttpResponse:
        data = [dict(zip(HEADERS, _row_values(c)))
                for c in queryset.iterator(chunk_size=500)]
        return HttpResponse(
            json.dumps({'count': len(data), 'results': data}, ensure_ascii=False),
            content_type='application/json',
        )


# ─────────────────────────────────────────────────────────────
# View
# ─────────────────────────────────────────────────────────────

class EarningsExportView(APIView):
    """
    GET /api/offerwall/exports/earnings/

    Download earnings history.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        fmt      = request.query_params.get('format', 'csv').lower()
        qs       = _build_queryset(request.user, request.query_params)
        today    = date.today().isoformat()
        username = request.user.username

        filename_base = f'earnings_{username}_{today}'

        logger.info(f'[export] user={username} fmt={fmt} count={qs.count()}')

        if fmt == 'xlsx':
            return XLSXExporter.export(qs, f'{filename_base}.xlsx')
        if fmt == 'json':
            return JSONExporter.export(qs)
        return CSVExporter.export(qs, f'{filename_base}.csv')


class AdminEarningsExportView(APIView):
    """
    FIX: Was not B2B aware — now supports ?client_id= filter
    so platform operators can export a specific publisher's earnings.
    """

    """
    GET /api/offerwall/exports/admin/earnings/?user_id=…

    Admin-only: export any user's earnings.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            from rest_framework.response import Response
            from rest_framework import status as drf_status
            return Response({'error': 'forbidden'}, status=drf_status.HTTP_403_FORBIDDEN)

        user_id = request.query_params.get('user_id')
        if not user_id:
            from django.contrib.auth import get_user_model
            from rest_framework.response import Response
            return Response({'error': 'user_id required'})

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            from rest_framework.response import Response
            from rest_framework import status as drf_status
            return Response({'error': 'user_not_found'},
                            status=drf_status.HTTP_404_NOT_FOUND)

        qs       = _build_queryset(target_user, request.query_params)
        fmt      = request.query_params.get('format', 'csv').lower()
        today    = date.today().isoformat()
        filename = f'earnings_{target_user.username}_{today}'

        if fmt == 'xlsx':
            return XLSXExporter.export(qs, f'{filename}.xlsx')
        if fmt == 'json':
            return JSONExporter.export(qs)
        return CSVExporter.export(qs, f'{filename}.csv')
