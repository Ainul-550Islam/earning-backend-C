"""
SmartLink — Invoice PDF Generation Service
==========================================
Generates professional invoice PDFs for PayoutRecord instances.
Uses reportlab (pure-Python, no system dependencies) — no weasyprint needed.

Install:
    pip install reportlab

Usage:
    from api.smartlink.services.billing.InvoicePDFService import InvoicePDFService
    pdf_bytes = InvoicePDFService().generate(payout_record)

The generated PDF is returned as raw bytes so it can be:
  - Streamed directly via HttpResponse
  - Saved to Django storage / S3
  - Attached to an email

Endpoint wired in BusinessViewSets.PayoutViewSet:
    GET /api/smartlink/payouts/{id}/invoice-pdf/
"""
import io
import logging
from decimal import Decimal
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger('smartlink.billing.invoice')

# ── Colour palette ─────────────────────────────────────────────────────────────
_BRAND_PRIMARY   = (0.09, 0.46, 0.82)   # #1775D1 — blue header
_BRAND_SECONDARY = (0.95, 0.97, 1.00)   # #F2F7FF — light blue row fill
_TEXT_DARK       = (0.13, 0.13, 0.13)   # #222222
_TEXT_MID        = (0.40, 0.40, 0.40)   # #666666
_WHITE           = (1.00, 1.00, 1.00)
_BORDER          = (0.82, 0.88, 0.95)   # #D2E0F4 — table border


class InvoicePDFService:
    """
    Generates a fully formatted payout invoice PDF for a PayoutRecord.

    All layout uses reportlab's canvas + platypus (no external HTML renderer).
    No third-party fonts required — Helvetica family used throughout.
    """

    # Page margins (points, 1pt = 1/72 inch)
    _MARGIN_LEFT   = 50
    _MARGIN_RIGHT  = 50
    _MARGIN_TOP    = 50
    _MARGIN_BOTTOM = 50

    def generate(self, payout_record) -> bytes:
        """
        Generate a PDF invoice for a PayoutRecord.

        Args:
            payout_record: smartlink.models.billing.PayoutRecord instance.

        Returns:
            PDF file as raw bytes.

        Raises:
            ImportError if reportlab is not installed.
            Exception on any rendering error (caller should catch).
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                HRFlowable,
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        except ImportError:
            raise ImportError(
                "reportlab is required for PDF generation. "
                "Install it with: pip install reportlab"
            )

        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=self._MARGIN_LEFT,
            rightMargin=self._MARGIN_RIGHT,
            topMargin=self._MARGIN_TOP,
            bottomMargin=self._MARGIN_BOTTOM,
            title=f"Invoice — SmartLink Payout #{str(payout_record.reference_id)[:8].upper()}",
            author="SmartLink Platform",
        )

        styles     = getSampleStyleSheet()
        page_width = A4[0] - self._MARGIN_LEFT - self._MARGIN_RIGHT

        # ── Custom styles ──────────────────────────────────────────────────────
        h1 = ParagraphStyle(
            'SL_H1',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=22,
            textColor=colors.Color(*_WHITE),
            spaceAfter=4,
        )
        h2 = ParagraphStyle(
            'SL_H2',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=11,
            textColor=colors.Color(*_TEXT_DARK),
            spaceAfter=2,
        )
        body = ParagraphStyle(
            'SL_Body',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            textColor=colors.Color(*_TEXT_DARK),
            leading=13,
        )
        body_mid = ParagraphStyle(
            'SL_BodyMid',
            parent=body,
            textColor=colors.Color(*_TEXT_MID),
        )
        body_right = ParagraphStyle(
            'SL_BodyRight',
            parent=body,
            alignment=TA_RIGHT,
        )
        label = ParagraphStyle(
            'SL_Label',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=colors.Color(*_TEXT_MID),
            spaceAfter=1,
        )
        total_style = ParagraphStyle(
            'SL_Total',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=13,
            textColor=colors.Color(*_BRAND_PRIMARY),
            alignment=TA_RIGHT,
        )
        status_style = ParagraphStyle(
            'SL_Status',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=colors.Color(*_WHITE),
            alignment=TA_CENTER,
        )

        # ── Helper: colour from RGB tuple ─────────────────────────────────────
        def c(rgb):
            return colors.Color(*rgb)

        # ── Gather data ───────────────────────────────────────────────────────
        publisher    = payout_record.publisher
        profile      = getattr(publisher, 'publisher_profile', None)
        ref_short    = str(payout_record.reference_id).replace('-', '').upper()[:12]
        invoice_num  = f"SL-{ref_short}"
        generated_at = timezone.now().strftime('%d %B %Y')
        period_from  = payout_record.period_from.strftime('%d %b %Y')
        period_to    = payout_record.period_to.strftime('%d %b %Y')
        paid_at_str  = (
            payout_record.paid_at.strftime('%d %b %Y %H:%M UTC')
            if payout_record.paid_at else 'Pending'
        )

        company_name = ''
        country_code = ''
        tax_id       = ''
        if profile:
            company_name = profile.company_name or ''
            country_code = profile.country_code or ''
            tax_id       = profile.tax_id or ''

        platform_name    = getattr(settings, 'SMARTLINK_PLATFORM_NAME',    'SmartLink Platform')
        platform_email   = getattr(settings, 'SMARTLINK_PLATFORM_EMAIL',   'billing@smartlink.io')
        platform_address = getattr(settings, 'SMARTLINK_PLATFORM_ADDRESS', '')
        platform_website = getattr(settings, 'SMARTLINK_PLATFORM_WEBSITE', 'https://smartlink.io')

        # ── Status badge colour ───────────────────────────────────────────────
        _status_colours = {
            'paid':       (0.13, 0.70, 0.37),   # green
            'processing': (0.95, 0.61, 0.07),   # amber
            'approved':   (0.09, 0.46, 0.82),   # blue
            'failed':     (0.86, 0.21, 0.27),   # red
            'rejected':   (0.86, 0.21, 0.27),
            'on_hold':    (0.60, 0.60, 0.60),
            'calculated': (0.45, 0.55, 0.65),
        }
        status_rgb = _status_colours.get(
            payout_record.status, (0.45, 0.55, 0.65)
        )

        # ── Build story ───────────────────────────────────────────────────────
        story = []

        # ── 1. Header banner ──────────────────────────────────────────────────
        header_data = [[
            Paragraph(platform_name, h1),
            Paragraph(f'PAYOUT INVOICE<br/>{invoice_num}', ParagraphStyle(
                'SL_InvNum',
                parent=h1,
                alignment=TA_RIGHT,
                fontSize=14,
            )),
        ]]
        header_table = Table(header_data, colWidths=[page_width * 0.6, page_width * 0.4])
        header_table.setStyle(TableStyle([
            ('BACKGROUND',  (0, 0), (-1, -1), c(_BRAND_PRIMARY)),
            ('TEXTCOLOR',   (0, 0), (-1, -1), c(_WHITE)),
            ('TOPPADDING',  (0, 0), (-1, -1), 14),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 14),
            ('LEFTPADDING', (0, 0), (-1, -1), 16),
            ('RIGHTPADDING', (0, 0), (-1, -1), 16),
            ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
            ('ROUNDEDCORNERS', [6]),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 14))

        # ── 2. Meta row: Generated / Period / Status ──────────────────────────
        status_badge_data = [[
            Paragraph(payout_record.status.upper(), status_style),
        ]]
        badge_table = Table(
            status_badge_data,
            colWidths=[80],
        )
        badge_table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, -1), c(status_rgb)),
            ('ROUNDEDCORNERS', [4]),
            ('TOPPADDING',   (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
        ]))

        meta_data = [[
            [Paragraph('GENERATED', label), Paragraph(generated_at, body)],
            [Paragraph('PERIOD', label),    Paragraph(f'{period_from} – {period_to}', body)],
            [Paragraph('STATUS', label),    badge_table],
        ]]
        meta_table = Table(
            meta_data,
            colWidths=[page_width / 3, page_width / 3, page_width / 3],
        )
        meta_table.setStyle(TableStyle([
            ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND',   (0, 0), (-1, -1), c(_BRAND_SECONDARY)),
            ('TOPPADDING',   (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 10),
            ('LEFTPADDING',  (0, 0), (-1, -1), 14),
            ('RIGHTPADDING', (0, 0), (-1, -1), 14),
            ('BOX',          (0, 0), (-1, -1), 0.5, c(_BORDER)),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 18))

        # ── 3. FROM / TO ──────────────────────────────────────────────────────
        from_lines = [
            Paragraph('FROM', label),
            Paragraph(f'<b>{platform_name}</b>', body),
        ]
        if platform_address:
            from_lines.append(Paragraph(platform_address, body_mid))
        from_lines.append(Paragraph(platform_email, body_mid))
        from_lines.append(Paragraph(platform_website, body_mid))

        to_lines = [
            Paragraph('TO (PUBLISHER)', label),
            Paragraph(f'<b>{publisher.get_full_name() or publisher.username}</b>', body),
        ]
        if company_name:
            to_lines.append(Paragraph(company_name, body_mid))
        to_lines.append(Paragraph(publisher.email, body_mid))
        if country_code:
            to_lines.append(Paragraph(f'Country: {country_code}', body_mid))
        if tax_id:
            to_lines.append(Paragraph(f'Tax ID: {tax_id}', body_mid))

        addresses_data = [[from_lines, to_lines]]
        addresses_table = Table(
            addresses_data,
            colWidths=[page_width * 0.5, page_width * 0.5],
        )
        addresses_table.setStyle(TableStyle([
            ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',(0, 0), (-1, -1), 20),
        ]))
        story.append(addresses_table)
        story.append(Spacer(1, 18))
        story.append(HRFlowable(width=page_width, thickness=0.5,
                                color=c(_BORDER), spaceAfter=14))

        # ── 4. Line items table ───────────────────────────────────────────────
        li_header = [
            Paragraph('<b>Description</b>', body),
            Paragraph('<b>Details</b>',     body),
            Paragraph('<b>Amount (USD)</b>', ParagraphStyle(
                'RH', parent=body, fontName='Helvetica-Bold', alignment=TA_RIGHT
            )),
        ]

        def _fmt(val) -> str:
            try:
                return f"${Decimal(str(val)):,.4f}"
            except Exception:
                return str(val)

        line_items = [
            li_header,
            [
                Paragraph('Publisher Earnings', body),
                Paragraph(f'Period: {period_from} – {period_to}', body_mid),
                Paragraph(_fmt(payout_record.gross_amount), body_right),
            ],
        ]

        if payout_record.total_clicks:
            line_items.append([
                Paragraph('Traffic Volume', body),
                Paragraph(
                    f'{payout_record.total_clicks:,} clicks / '
                    f'{payout_record.total_conversions:,} conversions',
                    body_mid
                ),
                Paragraph('—', body_right),
            ])

        if payout_record.scrub_amount and payout_record.scrub_amount > 0:
            line_items.append([
                Paragraph('Quality Adjustment (scrub)', body),
                Paragraph(
                    f'Scrub rate: {float(payout_record.scrub_rate or 0):.1%}'
                    + (f'<br/><font size="8" color="grey">{payout_record.scrub_reason}</font>'
                       if payout_record.scrub_reason else ''),
                    body_mid,
                ),
                Paragraph(f'−{_fmt(payout_record.scrub_amount)}', body_right),
            ])

        if payout_record.fraud_rate and payout_record.fraud_rate > 0:
            line_items.append([
                Paragraph('Fraud Rate (FYI)', body),
                Paragraph(f'{float(payout_record.fraud_rate):.1%}', body_mid),
                Paragraph('—', body_right),
            ])

        if payout_record.fx_rate and payout_record.currency != 'USD':
            line_items.append([
                Paragraph('FX Conversion', body),
                Paragraph(
                    f'1 USD = {payout_record.fx_rate} {payout_record.currency}',
                    body_mid,
                ),
                Paragraph(_fmt(payout_record.local_amount) + f' {payout_record.currency}',
                          body_right),
            ])

        col_widths = [page_width * 0.40, page_width * 0.35, page_width * 0.25]
        li_table = Table(line_items, colWidths=col_widths, repeatRows=1)

        row_fills = []
        for i in range(1, len(line_items)):
            bg = _BRAND_SECONDARY if i % 2 == 0 else _WHITE
            row_fills.append(('BACKGROUND', (0, i), (-1, i), c(bg)))

        li_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND',   (0, 0), (-1, 0), c(_BRAND_PRIMARY)),
            ('TEXTCOLOR',    (0, 0), (-1, 0), c(_WHITE)),
            ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1, 0), 9),
            ('TOPPADDING',   (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING',(0, 0), (-1, 0), 8),
            # Body rows
            ('FONTNAME',     (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE',     (0, 1), (-1, -1), 9),
            ('TOPPADDING',   (0, 1), (-1, -1), 7),
            ('BOTTOMPADDING',(0, 1), (-1, -1), 7),
            ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN',        (2, 0), (2, -1),  'RIGHT'),
            ('GRID',         (0, 0), (-1, -1), 0.4, c(_BORDER)),
            *row_fills,
        ]))
        story.append(li_table)
        story.append(Spacer(1, 0))

        # ── 5. Total box ──────────────────────────────────────────────────────
        total_data = [[
            Paragraph('NET PAYOUT', ParagraphStyle(
                'TL', parent=label, alignment=TA_RIGHT, spaceAfter=0
            )),
            Paragraph(
                f'{payout_record.currency} {_fmt(payout_record.net_amount)}',
                total_style,
            ),
        ]]
        total_table = Table(total_data, colWidths=[page_width * 0.75, page_width * 0.25])
        total_table.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), c(_BRAND_SECONDARY)),
            ('TOPPADDING',    (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING',   (0, 0), (-1, -1), 14),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 14),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX',           (0, 0), (-1, -1), 1.0, c(_BRAND_PRIMARY)),
        ]))
        story.append(total_table)
        story.append(Spacer(1, 18))

        # ── 6. Payment details ────────────────────────────────────────────────
        story.append(Paragraph('PAYMENT DETAILS', label))
        story.append(Spacer(1, 4))

        payment_rows = [
            ['Payment Method',  payout_record.get_payment_method_display()],
            ['Payment Address', payout_record.payment_address or '—'],
            ['Paid At',         paid_at_str],
        ]
        if payout_record.transaction_ref:
            payment_rows.append(['Transaction Reference', payout_record.transaction_ref])

        pmt_table = Table(
            payment_rows,
            colWidths=[page_width * 0.30, page_width * 0.70],
        )
        pmt_table.setStyle(TableStyle([
            ('FONTNAME',     (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME',     (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE',     (0, 0), (-1, -1), 9),
            ('TEXTCOLOR',    (0, 0), (0, -1), c(_TEXT_MID)),
            ('TEXTCOLOR',    (1, 0), (1, -1), c(_TEXT_DARK)),
            ('TOPPADDING',   (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
            ('LEFTPADDING',  (0, 0), (-1, -1), 0),
            ('LINEBELOW',    (0, 0), (-1, -2), 0.3, c(_BORDER)),
        ]))
        story.append(pmt_table)
        story.append(Spacer(1, 18))
        story.append(HRFlowable(width=page_width, thickness=0.5,
                                color=c(_BORDER), spaceBefore=4, spaceAfter=8))

        # ── 7. Reference & footer ─────────────────────────────────────────────
        story.append(Paragraph(
            f'Reference: <b>{str(payout_record.reference_id)}</b>',
            body_mid,
        ))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            'This document is an automated payout confirmation generated by the '
            f'{platform_name} platform. For queries contact {platform_email}.',
            ParagraphStyle('Footer', parent=body_mid, fontSize=7.5, leading=11),
        ))

        # ── 8. Build PDF ──────────────────────────────────────────────────────
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(
            f"Invoice PDF generated: payout#{payout_record.pk} "
            f"ref={payout_record.reference_id} "
            f"size={len(pdf_bytes)} bytes"
        )
        return pdf_bytes
