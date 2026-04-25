# api/payment_gateways/services/ReceiptGenerator.py
# Payment receipt generator — creates PDF/HTML receipts for all transactions

import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


class ReceiptGenerator:
    """
    Generates payment receipts for deposits, withdrawals, and conversions.

    Output formats:
        - HTML (for email embedding)
        - PDF (via weasyprint or xhtml2pdf, optional)
        - JSON (for API responses)

    Usage:
        gen = ReceiptGenerator()
        html = gen.generate_deposit_receipt(deposit_request)
        pdf  = gen.generate_pdf(html)  # Optional
    """

    COMPANY_INFO = {
        'name':    'Your Company Ltd.',
        'address': 'Dhaka, Bangladesh',
        'email':   'support@yourdomain.com',
        'phone':   '+880 1XXXXXXXXX',
        'website': 'https://yourdomain.com',
        'logo_url':'https://yourdomain.com/static/logo.png',
    }

    def generate_deposit_receipt(self, deposit, fmt: str = 'json') -> dict:
        """
        Generate receipt for a completed deposit.

        Args:
            deposit: DepositRequest instance
            fmt:     'json' | 'html' | 'pdf'

        Returns:
            dict with receipt data + optional html/pdf
        """
        receipt_data = {
            'receipt_type':   'DEPOSIT',
            'receipt_number': f'RCP-DEP-{deposit.id}-{int(timezone.now().timestamp())}',
            'issued_at':      timezone.now().isoformat(),
            'company':        self.COMPANY_INFO,

            # Transaction details
            'transaction': {
                'reference_id':  deposit.reference_id,
                'gateway':       deposit.gateway.upper(),
                'gateway_ref':   deposit.gateway_ref or '—',
                'date':          deposit.completed_at.strftime('%d %b %Y %I:%M %p') if deposit.completed_at else '—',
                'status':        deposit.status.upper(),
            },

            # Financial
            'financial': {
                'gross_amount':  str(deposit.amount),
                'fee':           str(deposit.fee),
                'net_amount':    str(deposit.net_amount),
                'currency':      deposit.currency,
                'fee_percent':   str(round(float(deposit.fee) / float(deposit.amount) * 100, 2)) + '%' if deposit.amount else '0%',
            },

            # User
            'user': {
                'name':  deposit.user.get_full_name() or deposit.user.username,
                'email': deposit.user.email,
                'id':    deposit.user.id,
            },

            # Footer
            'footer': {
                'message': 'Thank you for using our service.',
                'support': self.COMPANY_INFO['email'],
            }
        }

        if fmt == 'html':
            receipt_data['html'] = self._render_html(receipt_data, 'deposit')
        elif fmt == 'pdf':
            html = self._render_html(receipt_data, 'deposit')
            receipt_data['html'] = html
            receipt_data['pdf_base64'] = self._generate_pdf(html)

        return receipt_data

    def generate_withdrawal_receipt(self, payout_request, fmt: str = 'json') -> dict:
        """Generate receipt for a completed withdrawal/payout."""

        receipt_data = {
            'receipt_type':   'WITHDRAWAL',
            'receipt_number': f'RCP-WDL-{payout_request.id}-{int(timezone.now().timestamp())}',
            'issued_at':      timezone.now().isoformat(),
            'company':        self.COMPANY_INFO,

            'transaction': {
                'reference_id':   payout_request.reference_id,
                'gateway':        payout_request.payout_method.upper(),
                'gateway_ref':    payout_request.gateway_reference or '—',
                'date':           payout_request.processed_at.strftime('%d %b %Y %I:%M %p') if payout_request.processed_at else '—',
                'status':         payout_request.status.upper(),
            },

            'financial': {
                'gross_amount': str(payout_request.amount),
                'fee':          str(payout_request.fee),
                'net_amount':   str(payout_request.net_amount),
                'currency':     payout_request.currency,
            },

            'destination': {
                'method':  payout_request.payout_method,
                'account': self._mask_account(payout_request.account_number),
                'name':    payout_request.account_name or '—',
            },

            'user': {
                'name':  payout_request.user.get_full_name() or payout_request.user.username,
                'email': payout_request.user.email,
            },
        }

        if fmt == 'html':
            receipt_data['html'] = self._render_html(receipt_data, 'withdrawal')

        return receipt_data

    def generate_conversion_receipt(self, conversion, fmt: str = 'json') -> dict:
        """Generate receipt/proof for a publisher conversion."""
        receipt_data = {
            'receipt_type':   'CONVERSION',
            'receipt_number': f'RCP-CONV-{conversion.conversion_id[:8].upper()}',
            'issued_at':      timezone.now().isoformat(),

            'conversion': {
                'id':          conversion.conversion_id,
                'type':        conversion.conversion_type,
                'status':      conversion.status,
                'offer':       conversion.offer.name if conversion.offer else '—',
                'click_id':    conversion.click_id_raw,
                'date':        conversion.created_at.strftime('%d %b %Y %I:%M %p'),
            },

            'financial': {
                'payout':    str(conversion.payout),
                'cost':      str(conversion.cost),
                'revenue':   str(conversion.revenue),
                'currency':  conversion.currency,
            },

            'publisher': {
                'email': conversion.publisher.email if conversion.publisher else '—',
            },
        }

        if fmt == 'html':
            receipt_data['html'] = self._render_html(receipt_data, 'conversion')

        return receipt_data

    def generate_statement(self, user, start_date, end_date) -> dict:
        """
        Generate a monthly/period statement for a publisher.
        Lists all earnings, payouts, and bonuses.
        """
        from api.payment_gateways.models.core import GatewayTransaction
        from django.db.models import Sum, Count

        txns = GatewayTransaction.objects.filter(
            user=user,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status='completed',
        ).order_by('created_at')

        agg = txns.aggregate(
            deposits=Sum('amount', filter=__import__('django.db.models', fromlist=['Q']).Q(transaction_type='deposit')),
            withdrawals=Sum('amount', filter=__import__('django.db.models', fromlist=['Q']).Q(transaction_type='withdrawal')),
            fees=Sum('fee'),
            count=Count('id'),
        )

        transactions_list = []
        for t in txns:
            transactions_list.append({
                'date':      t.created_at.strftime('%d %b %Y'),
                'type':      t.transaction_type.upper(),
                'gateway':   t.gateway.upper(),
                'reference': t.reference_id,
                'amount':    str(t.amount),
                'fee':       str(t.fee),
                'net':       str(t.net_amount),
                'status':    t.status.upper(),
            })

        return {
            'statement_type': 'ACCOUNT_STATEMENT',
            'period':         f'{start_date} to {end_date}',
            'user':           {'name': user.get_full_name(), 'email': user.email},
            'summary': {
                'total_deposits':     str(agg['deposits'] or Decimal('0')),
                'total_withdrawals':  str(agg['withdrawals'] or Decimal('0')),
                'total_fees':         str(agg['fees'] or Decimal('0')),
                'transaction_count':  agg['count'],
                'current_balance':    str(getattr(user, 'balance', Decimal('0'))),
            },
            'transactions': transactions_list,
            'company':        self.COMPANY_INFO,
            'generated_at':   timezone.now().isoformat(),
        }

    def _render_html(self, data: dict, receipt_type: str) -> str:
        """Render receipt as styled HTML."""
        company  = data.get('company', self.COMPANY_INFO)
        txn      = data.get('transaction', data.get('conversion', {}))
        fin      = data.get('financial', {})
        user     = data.get('user', data.get('publisher', {}))
        dest     = data.get('destination', {})
        rtype    = data.get('receipt_type', receipt_type.upper())
        rnum     = data.get('receipt_number', '')

        COLORS = {
            'DEPOSIT':    '#3B6D11',
            'WITHDRAWAL': '#185FA5',
            'CONVERSION': '#534AB7',
        }
        color = COLORS.get(rtype, '#333')

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
  .header {{ background: {color}; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
  .header h1 {{ margin: 0; font-size: 22px; }}
  .header p {{ margin: 4px 0 0; opacity: .8; font-size: 13px; }}
  .body {{ border: 1px solid #ddd; border-top: none; padding: 24px; border-radius: 0 0 8px 8px; }}
  .row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 14px; }}
  .row:last-child {{ border-bottom: none; }}
  .label {{ color: #666; }}
  .value {{ font-weight: 500; }}
  .amount {{ font-size: 28px; font-weight: bold; color: {color}; margin: 16px 0; }}
  .section-title {{ font-size: 11px; font-weight: bold; color: #999; text-transform: uppercase; letter-spacing: 1px; margin: 16px 0 8px; }}
  .footer {{ text-align: center; font-size: 12px; color: #999; margin-top: 20px; }}
  .status-badge {{ background: {'#EAF3DE' if 'completed' in str(txn.get('status','')).lower() else '#FAEEDA'}; 
                   color: {'#3B6D11' if 'completed' in str(txn.get('status','')).lower() else '#854F0B'};
                   padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }}
</style>
</head>
<body>
<div class="header">
  <h1>🧾 {rtype} RECEIPT</h1>
  <p>{rnum} &nbsp;|&nbsp; {data.get("issued_at", "")[:10]}</p>
</div>
<div class="body">
  <div class="section-title">Amount</div>
  <div class="amount">{fin.get("currency", "")} {fin.get("net_amount", fin.get("payout", "0"))}</div>
  
  <div class="section-title">Transaction Details</div>
  {''.join(f'<div class="row"><span class="label">{k.replace("_"," ").title()}</span><span class="value">{v}</span></div>' for k,v in txn.items() if v and v != "—")}

  <div class="section-title">Financial Breakdown</div>
  {''.join(f'<div class="row"><span class="label">{k.replace("_"," ").title()}</span><span class="value">{v}</span></div>' for k,v in fin.items() if v)}

  {'<div class="section-title">Destination</div>' + "".join(f'<div class="row"><span class="label">{k.replace("_"," ").title()}</span><span class="value">{v}</span></div>' for k,v in dest.items() if v and v != "—") if dest else ""}

  <div class="section-title">Account</div>
  <div class="row"><span class="label">Name</span><span class="value">{user.get("name","")}</span></div>
  <div class="row"><span class="label">Email</span><span class="value">{user.get("email","")}</span></div>
</div>
<div class="footer">
  <p>{company.get("name")} &nbsp;|&nbsp; {company.get("email")} &nbsp;|&nbsp; {company.get("website")}</p>
  <p>This is an electronically generated receipt and does not require a signature.</p>
</div>
</body>
</html>'''
        return html

    def _generate_pdf(self, html: str) -> str:
        """Generate PDF from HTML using weasyprint (optional dependency)."""
        try:
            import weasyprint
            import base64
            import io
            pdf_bytes = weasyprint.HTML(string=html).write_pdf()
            return base64.b64encode(pdf_bytes).decode()
        except ImportError:
            logger.warning('weasyprint not installed. PDF generation skipped. pip install weasyprint')
            return ''
        except Exception as e:
            logger.error(f'PDF generation failed: {e}')
            return ''

    def _mask_account(self, account: str) -> str:
        if not account:
            return '—'
        if len(account) <= 4:
            return '****'
        return '*' * (len(account) - 4) + account[-4:]
