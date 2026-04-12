# api/publisher_tools/payment_settlement/invoice_generator.py
"""
Invoice Generator — PDF invoice generation utilities।
Publisher-কে professional invoice পাঠানোর জন্য।
"""
from decimal import Decimal
from datetime import date
from typing import Dict

from django.utils import timezone


def build_invoice_data(invoice) -> Dict:
    """
    Invoice PDF generate করার জন্য সব data collect করে।
    """
    publisher = invoice.publisher

    return {
        'invoice_number':  invoice.invoice_number,
        'invoice_date':    invoice.issued_at.date() if invoice.issued_at else timezone.now().date(),
        'due_date':        invoice.due_date,
        'invoice_type':    invoice.get_invoice_type_display(),
        'period': {
            'start': invoice.period_start,
            'end':   invoice.period_end,
        },

        'publisher': {
            'publisher_id':   publisher.publisher_id,
            'display_name':   publisher.display_name,
            'business_type':  publisher.get_business_type_display(),
            'contact_email':  publisher.contact_email,
            'contact_phone':  publisher.contact_phone,
            'country':        publisher.country,
            'city':           publisher.city,
            'address':        publisher.address,
        },

        'financial': {
            'gross_revenue':      float(invoice.gross_revenue),
            'publisher_share':    float(invoice.publisher_share),
            'ivt_deduction':      float(invoice.ivt_deduction),
            'adjustment':         float(invoice.adjustment),
            'processing_fee':     float(invoice.processing_fee),
            'withholding_tax':    float(invoice.withholding_tax),
            'net_payable':        float(invoice.net_payable),
            'currency':           invoice.currency,
        },

        'traffic': {
            'total_impressions': invoice.total_impressions,
            'total_clicks':      invoice.total_clicks,
            'total_ad_requests': invoice.total_ad_requests,
        },

        'payment': {
            'method':    invoice.payout_threshold.get_payment_method_display() if invoice.payout_threshold else 'N/A',
            'reference': invoice.payment_reference,
            'status':    invoice.get_status_display(),
        },

        'status':           invoice.status,
        'admin_notes':      invoice.admin_notes,
        'publisher_notes':  invoice.publisher_notes,
    }


def generate_invoice_html(invoice) -> str:
    """
    Invoice-এর HTML representation generate করে।
    Production-এ WeasyPrint দিয়ে PDF convert করা হবে।
    """
    data = build_invoice_data(invoice)
    pub  = data['publisher']
    fin  = data['financial']
    traffic = data['traffic']

    # Format period
    period_str = f"{data['period']['start']} to {data['period']['end']}"

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
body {{ font-family: Arial, sans-serif; font-size: 12px; color: #333; margin: 40px; }}
.header {{ display: flex; justify-content: space-between; margin-bottom: 30px; }}
.company {{ font-size: 20px; font-weight: bold; color: #1e40af; }}
.invoice-title {{ font-size: 24px; font-weight: bold; color: #333; text-align: right; }}
.invoice-number {{ color: #6b7280; font-size: 14px; }}
.section {{ margin: 20px 0; }}
.section-title {{ font-weight: bold; border-bottom: 2px solid #e5e7eb; padding-bottom: 5px; margin-bottom: 10px; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ background: #f3f4f6; padding: 8px; text-align: left; font-weight: bold; }}
td {{ padding: 8px; border-bottom: 1px solid #e5e7eb; }}
.amount {{ text-align: right; }}
.total-row {{ font-weight: bold; background: #f0f9ff; }}
.net-payable {{ font-size: 16px; color: #22c55e; }}
.status-paid {{ color: #22c55e; font-weight: bold; }}
.status-pending {{ color: #f59e0b; font-weight: bold; }}
.footer {{ margin-top: 40px; text-align: center; color: #9ca3af; font-size: 10px; }}
</style>
</head>
<body>

<div class="header">
  <div>
    <div class="company">📡 Publisher Tools Platform</div>
    <div>publisher-tools.io</div>
    <div>support@publisher-tools.io</div>
  </div>
  <div>
    <div class="invoice-title">INVOICE</div>
    <div class="invoice-number">{data['invoice_number']}</div>
    <div>Date: {data['invoice_date']}</div>
    <div>Due: {data['due_date'] or 'N/A'}</div>
  </div>
</div>

<div class="section">
  <div class="section-title">Publisher Information</div>
  <table>
    <tr><td><strong>Publisher ID:</strong></td><td>{pub['publisher_id']}</td></tr>
    <tr><td><strong>Name:</strong></td><td>{pub['display_name']}</td></tr>
    <tr><td><strong>Business Type:</strong></td><td>{pub['business_type']}</td></tr>
    <tr><td><strong>Email:</strong></td><td>{pub['contact_email']}</td></tr>
    <tr><td><strong>Country:</strong></td><td>{pub['country']}</td></tr>
  </table>
</div>

<div class="section">
  <div class="section-title">Invoice Period: {period_str}</div>
  <table>
    <thead>
      <tr>
        <th>Description</th>
        <th>Impressions</th>
        <th>Clicks</th>
        <th class="amount">Amount (USD)</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Gross Ad Revenue</td>
        <td>{traffic['total_impressions']:,}</td>
        <td>{traffic['total_clicks']:,}</td>
        <td class="amount">${fin['gross_revenue']:,.4f}</td>
      </tr>
      <tr>
        <td>Publisher Revenue Share</td>
        <td colspan="2"></td>
        <td class="amount">${fin['publisher_share']:,.4f}</td>
      </tr>
    </tbody>
  </table>
</div>

<div class="section">
  <div class="section-title">Deductions & Fees</div>
  <table>
    <tbody>
      <tr>
        <td>IVT / Invalid Traffic Deduction</td>
        <td class="amount" style="color:#ef4444">-${fin['ivt_deduction']:,.4f}</td>
      </tr>
      <tr>
        <td>Adjustment</td>
        <td class="amount">${fin['adjustment']:,.4f}</td>
      </tr>
      <tr>
        <td>Processing Fee</td>
        <td class="amount" style="color:#ef4444">-${fin['processing_fee']:,.4f}</td>
      </tr>
      <tr>
        <td>Withholding Tax</td>
        <td class="amount" style="color:#ef4444">-${fin['withholding_tax']:,.4f}</td>
      </tr>
    </tbody>
    <tfoot>
      <tr class="total-row">
        <td><strong>NET PAYABLE</strong></td>
        <td class="amount net-payable"><strong>${fin['net_payable']:,.4f} {fin['currency']}</strong></td>
      </tr>
    </tfoot>
  </table>
</div>

<div class="section">
  <div class="section-title">Payment Status</div>
  <table>
    <tr>
      <td><strong>Status:</strong></td>
      <td class="{'status-paid' if data['status'] == 'paid' else 'status-pending'}">{data['payment']['status']}</td>
    </tr>
    <tr><td><strong>Method:</strong></td><td>{data['payment']['method']}</td></tr>
    <tr><td><strong>Reference:</strong></td><td>{data['payment']['reference'] or 'Pending'}</td></tr>
  </table>
</div>

{f'<div class="section"><div class="section-title">Notes</div><p>{data["admin_notes"]}</p></div>' if data.get('admin_notes') else ''}

<div class="footer">
  <p>This is an automatically generated invoice. For questions, contact publisher-support@publisher-tools.io</p>
  <p>Publisher Tools Platform | Invoice #{data['invoice_number']} | Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
</div>

</body>
</html>"""

    return html


def calculate_invoice_summary(
    gross_revenue: Decimal,
    revenue_share_pct: Decimal,
    ivt_deduction: Decimal = Decimal('0'),
    processing_fee_flat: Decimal = Decimal('0'),
    processing_fee_pct: Decimal = Decimal('0'),
    withholding_tax_pct: Decimal = Decimal('0'),
    adjustment: Decimal = Decimal('0'),
) -> Dict:
    """
    Invoice-এর সব amounts calculate করে।
    Preview বা validation-এর জন্য।
    """
    from ..utils import (
        calculate_publisher_revenue, calculate_processing_fee,
        calculate_withholding_tax, calculate_net_payable
    )

    publisher_share = calculate_publisher_revenue(gross_revenue, revenue_share_pct, ivt_deduction)
    processing_fee  = calculate_processing_fee(publisher_share, processing_fee_flat, processing_fee_pct)
    withholding_tax = calculate_withholding_tax(publisher_share, withholding_tax_pct)
    net_payable     = calculate_net_payable(
        publisher_share, Decimal('0'), adjustment, processing_fee, withholding_tax
    )

    return {
        'gross_revenue':    float(gross_revenue),
        'publisher_share':  float(publisher_share),
        'ivt_deduction':    float(ivt_deduction),
        'adjustment':       float(adjustment),
        'processing_fee':   float(processing_fee),
        'withholding_tax':  float(withholding_tax),
        'net_payable':      float(net_payable),
        'effective_rate':   float(publisher_share / gross_revenue * 100) if gross_revenue > 0 else 0,
    }
