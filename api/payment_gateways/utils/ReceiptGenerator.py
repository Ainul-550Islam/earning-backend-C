# api/payment_gateways/utils/ReceiptGenerator.py

import io
import qrcode
from datetime import datetime
from decimal import Decimal
from django.template.loader import render_to_string
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Line
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib.colors import Color, HexColor
import segno  # For QR code generation
from ..models import GatewayTransaction, PayoutRequest


class ReceiptGenerator:
    """Professional Receipt Generator for Payment GatewayTransactions"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
        self.setup_fonts()
    
    def setup_fonts(self):
        """Setup custom fonts"""
        try:
            # Register fonts (you need to have font files in your project)
            pdfmetrics.registerFont(TTFont('DejaVu', 'DejaVuSans.ttf'))
            pdfmetrics.registerFont(TTFont('DejaVu-Bold', 'DejaVuSans-Bold.ttf'))
        except:
            # Fallback to default fonts
            pass
    
    def setup_custom_styles(self):
        """Setup custom styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='ReceiptTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1a365d'),
            spaceAfter=30,
            alignment=1  # Center
        ))
        
        # Header style
        self.styles.add(ParagraphStyle(
            name='ReceiptHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2d3748'),
            spaceAfter=12
        ))
        
        # Normal text style
        self.styles.add(ParagraphStyle(
            name='ReceiptText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#4a5568'),
            spaceAfter=6
        ))
        
        # Bold text style
        self.styles.add(ParagraphStyle(
            name='ReceiptBold',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2d3748'),
            fontName='Helvetica-Bold',
            spaceAfter=6
        ))
        
        # Highlight style
        self.styles.add(ParagraphStyle(
            name='ReceiptHighlight',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#2b6cb0'),
            fontName='Helvetica-Bold',
            spaceAfter=10
        ))
        
        # Footer style
        self.styles.add(ParagraphStyle(
            name='ReceiptFooter',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#718096'),
            alignment=1  # Center
        ))
    
    def generate_transaction_receipt(self, transaction, format='pdf'):
        """
        Generate receipt for a transaction
        
        Args:
            transaction (GatewayTransaction): GatewayTransaction object
            format (str): 'pdf' or 'html'
            
        Returns:
            bytes/str: Receipt content
        """
        if format.lower() == 'pdf':
            return self._generate_pdf_receipt(transaction)
        else:
            return self._generate_html_receipt(transaction)
    
    def _generate_pdf_receipt(self, transaction):
        """Generate PDF receipt"""
        buffer = io.BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        elements = []
        
        # 1. Header with Logo and Company Info
        elements.extend(self._generate_header())
        
        # 2. Receipt Title
        elements.append(Paragraph(
            f"PAYMENT RECEIPT #{transaction.reference_id}",
            self.styles['ReceiptTitle']
        ))
        
        # 3. Status Badge
        elements.extend(self._generate_status_badge(transaction))
        
        # 4. Transaction Details
        elements.extend(self._generate_transaction_details(transaction))
        
        # 5. User Information
        elements.extend(self._generate_user_info(transaction.user))
        
        # 6. Payment Method Details
        if transaction.payment_method:
            elements.extend(self._generate_payment_method_info(transaction.payment_method))
        
        # 7. Amount Breakdown
        elements.extend(self._generate_amount_breakdown(transaction))
        
        # 8. QR Code for Verification
        elements.extend(self._generate_qr_code(transaction))
        
        # 9. Terms and Conditions
        elements.extend(self._generate_terms_conditions())
        
        # 10. Footer
        elements.extend(self._generate_footer())
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        return buffer.getvalue()
    
    def _generate_html_receipt(self, transaction):
        """Generate HTML receipt"""
        context = {
            'transaction': transaction,
            'generated_at': timezone.now(),
            'status_colors': {
                'completed': 'success',
                'pending': 'warning',
                'failed': 'danger',
                'processing': 'info',
                'cancelled': 'secondary'
            }
        }
        
        return render_to_string('receipts/transaction_receipt.html', context)
    
    def _generate_header(self):
        """Generate receipt header"""
        elements = []
        
        # Company Logo and Info
        header_data = [
            ['Your Company Name', 'Payment Receipt'],
            ['123 Business Street', 'Official Document'],
            ['City, Country 12345', f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'],
            ['Phone: +1 234 567 8900', 'Email: payments@company.com'],
            ['Website: www.company.com', 'VAT: AB123456789']
        ]
        
        header_table = Table(header_data, colWidths=[3*inch, 3*inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a365d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _generate_status_badge(self, transaction):
        """Generate status badge"""
        elements = []
        
        status_colors = {
            'completed': colors.HexColor('#48bb78'),
            'pending': colors.HexColor('#ed8936'),
            'failed': colors.HexColor('#f56565'),
            'processing': colors.HexColor('#4299e1'),
            'cancelled': colors.HexColor('#a0aec0')
        }
        
        status_text = transaction.status.upper()
        color = status_colors.get(transaction.status, colors.HexColor('#a0aec0'))
        
        # Create a colored badge
        badge_data = [[status_text]]
        badge_table = Table(badge_data, colWidths=[2*inch])
        badge_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), color),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BORDER', (0, 0), (-1, -1), 1, color),
            ('ROUNDEDCORNERS', [10, 10, 10, 10]),
            ('LEFTPADDING', (0, 0), (-1, -1), 20),
            ('RIGHTPADDING', (0, 0), (-1, -1), 20),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(badge_table)
        elements.append(Spacer(1, 15))
        
        return elements
    
    def _generate_transaction_details(self, transaction):
        """Generate transaction details section"""
        elements = []
        
        elements.append(Paragraph("TRANSACTION DETAILS", self.styles['ReceiptHeader']))
        
        details_data = [
            ['Reference ID:', transaction.reference_id],
            ['GatewayTransaction ID:', f"TX{transaction.id:08d}"],
            ['Type:', transaction.get_transaction_type_display().upper()],
            ['Gateway:', transaction.gateway.upper()],
            ['Date:', timezone.localtime(transaction.created_at).strftime("%Y-%m-%d %H:%M:%S")],
            ['Status:', transaction.get_status_display().upper()],
        ]
        
        if transaction.completed_at:
            details_data.append([
                'Completed:', 
                timezone.localtime(transaction.completed_at).strftime("%Y-%m-%d %H:%M:%S")
            ])
        
        if transaction.gateway_reference:
            details_data.append(['Gateway Reference:', transaction.gateway_reference])
        
        details_table = Table(details_data, colWidths=[2*inch, 4*inch])
        details_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f7fafc')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#4a5568')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#2d3748')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(details_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _generate_user_info(self, user):
        """Generate user information section"""
        elements = []
        
        elements.append(Paragraph("USER INFORMATION", self.styles['ReceiptHeader']))
        
        user_data = [
            ['User ID:', f"USR{user.id:08d}"],
            ['Username:', user.username],
            ['Email:', user.email],
        ]
        
        if user.phone:
            user_data.append(['Phone:', user.phone])
        
        if hasattr(user, 'userprofile'):
            profile = user.userprofile
            if profile.full_name:
                user_data.append(['Full Name:', profile.full_name])
        
        user_table = Table(user_data, colWidths=[2*inch, 4*inch])
        user_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f7fafc')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#4a5568')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#2d3748')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(user_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _generate_payment_method_info(self, payment_method):
        """Generate payment method information"""
        elements = []
        
        elements.append(Paragraph("PAYMENT METHOD", self.styles['ReceiptHeader']))
        
        pm_data = [
            ['Gateway:', payment_method.get_gateway_display().upper()],
            ['Account Number:', payment_method.account_number],
            ['Account Name:', payment_method.account_name],
            ['Status:', 'VERIFIED' if payment_method.is_verified else 'UNVERIFIED'],
            ['Default:', 'YES' if payment_method.is_default else 'NO'],
        ]
        
        pm_table = Table(pm_data, colWidths=[2*inch, 4*inch])
        pm_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f7fafc')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#4a5568')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#2d3748')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(pm_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _generate_amount_breakdown(self, transaction):
        """Generate amount breakdown section"""
        elements = []
        
        elements.append(Paragraph("AMOUNT BREAKDOWN", self.styles['ReceiptHeader']))
        
        amount_data = [
            ['Description', 'Amount'],
            ['GatewayTransaction Amount', f"${transaction.amount:.2f}"],
            ['Processing Fee', f"${transaction.fee:.2f}"],
            ['Net Amount', f"<b>${transaction.net_amount:.2f}</b>"],
        ]
        
        amount_table = Table(amount_data, colWidths=[4*inch, 2*inch])
        amount_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2b6cb0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor('#f7fafc')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ebf8ff')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(amount_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _generate_qr_code(self, transaction):
        """Generate QR code for verification"""
        elements = []
        
        elements.append(Paragraph("VERIFICATION QR CODE", self.styles['ReceiptHeader']))
        
        # Create verification data
        verification_data = {
            'transaction_id': transaction.id,
            'reference_id': transaction.reference_id,
            'user_id': transaction.user.id,
            'amount': str(transaction.amount),
            'timestamp': timezone.now().isoformat()
        }
        
        import json
        qr_data = json.dumps(verification_data)
        
        # Generate QR code
        try:
            qr = segno.make_qr(qr_data)
            qr_buffer = io.BytesIO()
            qr.save(qr_buffer, kind='png', scale=5)
            qr_buffer.seek(0)
            
            qr_image = Image(qr_buffer, width=2*inch, height=2*inch)
            qr_image.hAlign = 'CENTER'
            elements.append(qr_image)
            
        except:
            # Fallback if QR generation fails
            elements.append(Paragraph(
                "QR Code generation failed. Use reference ID for verification.",
                self.styles['ReceiptText']
            ))
        
        elements.append(Paragraph(
            f"Scan to verify transaction #{transaction.reference_id}",
            self.styles['ReceiptFooter']
        ))
        
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _generate_terms_conditions(self):
        """Generate terms and conditions"""
        elements = []
        
        elements.append(Paragraph("TERMS & CONDITIONS", self.styles['ReceiptHeader']))
        
        terms = [
            "1. This receipt is an official document of the transaction.",
            "2. Please keep this receipt for your records.",
            "3. For any discrepancies, contact support within 7 days.",
            "4. GatewayTransaction fees are non-refundable.",
            "5. All amounts are in USD unless specified otherwise.",
        ]
        
        for term in terms:
            elements.append(Paragraph(f"• {term}", self.styles['ReceiptText']))
        
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _generate_footer(self):
        """Generate receipt footer"""
        elements = []
        
        # Add horizontal line
        drawing = Drawing(400, 1)
        drawing.add(Line(0, 0, 400, 0, strokeColor=colors.HexColor('#cbd5e0'), strokeWidth=1))
        elements.append(drawing)
        
        elements.append(Spacer(1, 10))
        
        footer_text = """
        Thank you for your business!<br/>
        For any questions or concerns, please contact our support team.<br/>
        Email: support@company.com | Phone: +1 234 567 8900<br/>
        This is a computer-generated receipt. No signature required.
        """
        
        elements.append(Paragraph(footer_text, self.styles['ReceiptFooter']))
        
        return elements
    
    def generate_payout_receipt(self, payout, format='pdf'):
        """
        Generate receipt for payout/withdrawal
        
        Args:
            payout (PayoutRequest): Payout request object
            format (str): 'pdf' or 'html'
            
        Returns:
            bytes/str: Receipt content
        """
        if format.lower() == 'pdf':
            return self._generate_payout_pdf_receipt(payout)
        else:
            return self._generate_payout_html_receipt(payout)
    
    def _generate_payout_pdf_receipt(self, payout):
        """Generate PDF receipt for payout"""
        buffer = io.BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        elements = []
        
        # Header
        elements.extend(self._generate_header())
        
        # Title
        elements.append(Paragraph(
            f"WITHDRAWAL RECEIPT #{payout.reference_id}",
            self.styles['ReceiptTitle']
        ))
        
        # Status
        elements.extend(self._generate_payout_status_badge(payout))
        
        # Payout Details
        elements.extend(self._generate_payout_details(payout))
        
        # User Info
        elements.extend(self._generate_user_info(payout.user))
        
        # Payout Method
        payout_method_data = [
            ['Payout Method:', payout.get_payout_method_display().upper()],
            ['Account Number:', payout.account_number],
            ['Account Name:', payout.account_name],
            ['Request Date:', timezone.localtime(payout.created_at).strftime("%Y-%m-%d %H:%M:%S")],
        ]
        
        if payout.processed_at:
            payout_method_data.append([
                'Processed Date:', 
                timezone.localtime(payout.processed_at).strftime("%Y-%m-%d %H:%M:%S")
            ])
        
        if payout.processed_by:
            payout_method_data.append(['Processed By:', payout.processed_by.username])
        
        if payout.admin_notes:
            payout_method_data.append(['Admin Notes:', payout.admin_notes])
        
        elements.append(Paragraph("PAYOUT DETAILS", self.styles['ReceiptHeader']))
        payout_table = Table(payout_method_data, colWidths=[2*inch, 4*inch])
        payout_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f7fafc')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(payout_table)
        
        elements.append(Spacer(1, 20))
        
        # Amount Breakdown
        amount_data = [
            ['Description', 'Amount'],
            ['Requested Amount', f"${payout.amount:.2f}"],
            ['Processing Fee', f"${payout.fee:.2f}"],
            ['Net Payout Amount', f"<b>${payout.net_amount:.2f}</b>"],
        ]
        
        elements.append(Paragraph("AMOUNT BREAKDOWN", self.styles['ReceiptHeader']))
        amount_table = Table(amount_data, colWidths=[4*inch, 2*inch])
        amount_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2b6cb0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ebf8ff')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
        ]))
        elements.append(amount_table)
        
        elements.append(Spacer(1, 20))
        
        # Terms and Footer
        elements.extend(self._generate_terms_conditions())
        elements.extend(self._generate_footer())
        
        doc.build(elements)
        buffer.seek(0)
        
        return buffer.getvalue()
    
    def _generate_payout_status_badge(self, payout):
        """Generate status badge for payout"""
        elements = []
        
        status_colors = {
            'completed': colors.HexColor('#48bb78'),
            'approved': colors.HexColor('#4299e1'),
            'processing': colors.HexColor('#ed8936'),
            'pending': colors.HexColor('#ecc94b'),
            'rejected': colors.HexColor('#f56565'),
            'cancelled': colors.HexColor('#a0aec0')
        }
        
        status_text = payout.status.upper()
        color = status_colors.get(payout.status, colors.HexColor('#a0aec0'))
        
        badge_data = [[status_text]]
        badge_table = Table(badge_data, colWidths=[2*inch])
        badge_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), color),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('ROUNDEDCORNERS', [10, 10, 10, 10]),
        ]))
        
        elements.append(badge_table)
        elements.append(Spacer(1, 15))
        
        return elements
    
    def _generate_payout_details(self, payout):
        """Generate payout details"""
        elements = []
        
        elements.append(Paragraph("PAYOUT REQUEST DETAILS", self.styles['ReceiptHeader']))
        
        details_data = [
            ['Reference ID:', payout.reference_id],
            ['Payout ID:', f"PO{payout.id:08d}"],
            ['Request Date:', timezone.localtime(payout.created_at).strftime("%Y-%m-%d %H:%M:%S")],
            ['Status:', payout.get_status_display().upper()],
        ]
        
        if payout.gateway_reference:
            details_data.append(['Gateway Reference:', payout.gateway_reference])
        
        details_table = Table(details_data, colWidths=[2*inch, 4*inch])
        details_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f7fafc')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ]))
        
        elements.append(details_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _generate_payout_html_receipt(self, payout):
        """Generate HTML receipt for payout"""
        context = {
            'payout': payout,
            'generated_at': timezone.now(),
            'status_colors': {
                'completed': 'success',
                'approved': 'primary',
                'processing': 'warning',
                'pending': 'info',
                'rejected': 'danger',
                'cancelled': 'secondary'
            }
        }
        
        return render_to_string('receipts/payout_receipt.html', context)
    
    def generate_summary_report(self, user, start_date, end_date, format='pdf'):
        """
        Generate transaction summary report
        
        Args:
            user (User): User object
            start_date (datetime): Start date
            end_date (datetime): End date
            format (str): 'pdf' or 'html'
            
        Returns:
            bytes/str: Report content
        """
        # Get transactions in date range
        GatewayTransactions = GatewayTransaction.objects.filter(
            user=user,
            created_at__range=[start_date, end_date]
        ).order_by('-created_at')
        
        # Get payouts in date range
        payouts = PayoutRequest.objects.filter(
            user=user,
            created_at__range=[start_date, end_date]
        ).order_by('-created_at')
        
        if format.lower() == 'pdf':
            return self._generate_summary_pdf_report(user, transactions, payouts, start_date, end_date)
        else:
            return self._generate_summary_html_report(user, transactions, payouts, start_date, end_date)
    
    def _generate_summary_pdf_report(self, user, transactions, payouts, start_date, end_date):
        """Generate PDF summary report"""
        buffer = io.BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        
        elements = []
        
        # Header
        elements.append(Paragraph(
            f"TRANSACTION SUMMARY REPORT",
            self.styles['ReceiptTitle']
        ))
        
        elements.append(Paragraph(
            f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            self.styles['ReceiptHeader']
        ))
        
        elements.append(Paragraph(
            f"User: {user.username} ({user.email})",
            self.styles['ReceiptText']
        ))
        
        elements.append(Spacer(1, 20))
        
        # Transaction Statistics
        deposit_total = sum(t.amount for t in transactions if t.transaction_type == 'deposit')
        withdrawal_total = sum(t.amount for t in transactions if t.transaction_type == 'withdrawal')
        fee_total = sum(t.fee for t in transactions)
        
        stats_data = [
            ['Statistic', 'Amount', 'Count'],
            ['Total Deposits', f"${deposit_total:.2f}", transactions.filter(transaction_type='deposit').count()],
            ['Total Withdrawals', f"${withdrawal_total:.2f}", transactions.filter(transaction_type='withdrawal').count()],
            ['Total Fees', f"${fee_total:.2f}", ''],
            ['Net Flow', f"${deposit_total - withdrawal_total:.2f}", ''],
            ['Successful GatewayTransactions', '', transactions.filter(status='completed').count()],
            ['Pending GatewayTransactions', '', transactions.filter(status='pending').count()],
        ]
        
        elements.append(Paragraph("SUMMARY STATISTICS", self.styles['ReceiptHeader']))
        stats_table = Table(stats_data, colWidths=[2.5*inch, 2*inch, 1.5*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2b6cb0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f7fafc')),
        ]))
        elements.append(stats_table)
        
        elements.append(Spacer(1, 30))
        
        # Recent Transactions
        if transactions.exists():
            elements.append(Paragraph("RECENT TRANSACTIONS", self.styles['ReceiptHeader']))
            
            # Show last 10 transactions
            recent_transactions = transactions[:10]
            tx_data = [['Date', 'Type', 'Gateway', 'Amount', 'Status']]
            
            for tx in recent_transactions:
                tx_data.append([
                    tx.created_at.strftime('%Y-%m-%d'),
                    tx.get_transaction_type_display(),
                    tx.gateway,
                    f"${tx.amount:.2f}",
                    tx.get_status_display()
                ])
            
            tx_table = Table(tx_data, colWidths=[1*inch, 1*inch, 1*inch, 1*inch, 1*inch])
            tx_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffffff')),
            ]))
            elements.append(tx_table)
        
        elements.append(Spacer(1, 30))
        
        # Footer
        elements.extend(self._generate_footer())
        
        doc.build(elements)
        buffer.seek(0)
        
        return buffer.getvalue()