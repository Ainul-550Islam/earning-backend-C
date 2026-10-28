"""
SmartLink Report Export ViewSet
Streaming CSV and JSON export for clicks, conversions, and performance data.
Previously missing: only management command existed, no API endpoint.
"""
import csv
import json
import io
import logging
from datetime import date, timedelta

from django.http import StreamingHttpResponse, HttpResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger('smartlink.viewsets.export')


class Echo:
    """Streaming CSV writer helper — writes to response rather than a buffer."""
    def write(self, value):
        return value


class ReportExportView(APIView):
    """
    Report export endpoint. Returns CSV or JSON download.

    GET /api/smartlink/reports/export/clicks/
        ?slug=abc          (optional — all slugs if omitted)
        &date_from=YYYY-MM-DD
        &date_to=YYYY-MM-DD
        &format=csv|json   (default: csv)
        &include_fraud=0|1 (default: 0)

    GET /api/smartlink/reports/export/conversions/
        ?slug=abc&date_from=…&date_to=…&format=csv|json

    GET /api/smartlink/reports/export/performance/
        ?date_from=…&date_to=…&format=csv|json
    """
    permission_classes = [IsAuthenticated]

    CLICK_FIELDS = [
        'id', 'smartlink__slug', 'ip', 'country', 'device_type',
        'os_type', 'browser', 'is_unique', 'is_converted', 'is_fraud',
        'is_bot', 'payout', 'created_at',
    ]
    CONVERSION_FIELDS = [
        'id', 'smartlink__slug', 'offer_id', 'ip', 'country',
        'device_type', 'payout', 'created_at',
    ]

    def _parse_dates(self, request) -> tuple:
        try:
            date_from = date.fromisoformat(
                request.query_params.get('date_from', str(date.today() - timedelta(days=30)))
            )
            date_to = date.fromisoformat(
                request.query_params.get('date_to', str(date.today()))
            )
        except ValueError:
            date_from = date.today() - timedelta(days=30)
            date_to = date.today()
        return date_from, date_to

    def _base_click_qs(self, request):
        from api.smartlink.models import Click, SmartLink
        user = request.user
        if user.is_staff:
            qs = Click.objects.all()
        else:
            qs = Click.objects.filter(smartlink__publisher=user)

        slug = request.query_params.get('slug', '').strip()
        if slug:
            qs = qs.filter(smartlink__slug=slug)

        date_from, date_to = self._parse_dates(request)
        qs = qs.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)

        if not int(request.query_params.get('include_fraud', 0)):
            qs = qs.filter(is_fraud=False, is_bot=False)

        return qs.order_by('created_at').values(*self.CLICK_FIELDS)

    def get(self, request, export_type: str = 'clicks'):
        fmt = request.query_params.get('format', 'csv').lower()
        slug_label = request.query_params.get('slug', 'all')
        filename = f"smartlink_{export_type}_{slug_label}.{fmt}"

        if export_type == 'clicks':
            return self._export_clicks(request, fmt, filename)
        elif export_type == 'conversions':
            return self._export_conversions(request, fmt, filename)
        elif export_type == 'performance':
            return self._export_performance(request, fmt, filename)
        return Response({'detail': f"Unknown export type '{export_type}'."}, status=400)

    def _export_clicks(self, request, fmt: str, filename: str):
        qs = self._base_click_qs(request)

        if fmt == 'json':
            data = list(qs[:100_000])
            for row in data:
                if row.get('created_at'):
                    row['created_at'] = str(row['created_at'])
            return HttpResponse(
                json.dumps(data, default=str),
                content_type='application/json',
                headers={'Content-Disposition': f'attachment; filename="{filename}"'},
            )

        # CSV streaming
        echo = Echo()
        writer = csv.DictWriter(echo, fieldnames=self.CLICK_FIELDS)

        def rows():
            yield writer.writeheader()
            for row in qs.iterator(chunk_size=1000):
                yield writer.writerow(row)

        response = StreamingHttpResponse(rows(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    def _export_conversions(self, request, fmt: str, filename: str):
        from api.smartlink.models import Click
        user = request.user
        if user.is_staff:
            qs = Click.objects.filter(is_converted=True)
        else:
            qs = Click.objects.filter(smartlink__publisher=user, is_converted=True)

        slug = request.query_params.get('slug', '').strip()
        if slug:
            qs = qs.filter(smartlink__slug=slug)

        date_from, date_to = self._parse_dates(request)
        qs = qs.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
        qs = qs.order_by('created_at').values(*self.CONVERSION_FIELDS)

        if fmt == 'json':
            data = list(qs[:50_000])
            for row in data:
                if row.get('created_at'):
                    row['created_at'] = str(row['created_at'])
            return HttpResponse(
                json.dumps(data, default=str),
                content_type='application/json',
                headers={'Content-Disposition': f'attachment; filename="{filename}"'},
            )

        echo = Echo()
        writer = csv.DictWriter(echo, fieldnames=self.CONVERSION_FIELDS)

        def rows():
            yield writer.writeheader()
            for row in qs.iterator(chunk_size=500):
                yield writer.writerow(row)

        response = StreamingHttpResponse(rows(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    def _export_performance(self, request, fmt: str, filename: str):
        from ..reports.PublisherReportService import PublisherReportService
        date_from, date_to = self._parse_dates(request)
        report_svc = PublisherReportService()
        data = report_svc.performance_report(
            publisher_id=request.user.pk,
            params={'date_from': str(date_from), 'date_to': str(date_to)},
        )
        rows = data.get('rows', [])

        if fmt == 'json':
            return HttpResponse(
                json.dumps(rows, default=str),
                content_type='application/json',
                headers={'Content-Disposition': f'attachment; filename="{filename}"'},
            )

        if not rows:
            return HttpResponse(
                'No data for the selected period.',
                content_type='text/plain',
            )

        echo = Echo()
        fields = list(rows[0].keys()) if rows else []
        writer = csv.DictWriter(echo, fieldnames=fields)

        def gen():
            yield writer.writeheader()
            for row in rows:
                yield writer.writerow(row)

        response = StreamingHttpResponse(gen(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
