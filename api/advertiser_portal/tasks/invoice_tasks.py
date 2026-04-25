"""
Invoice Tasks

Monthly invoice generation for advertisers
and automated billing processes.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from datetime import timedelta, date
from calendar import monthrange

from ..models.billing import AdvertiserInvoice, AdvertiserWallet
from ..models.campaign import AdCampaign
try:
    from ..services import AdvertiserBillingService
except ImportError:
    AdvertiserBillingService = None

import logging
logger = logging.getLogger(__name__)


@shared_task(name="advertiser_portal.generate_monthly_invoices")
def generate_monthly_invoices():
    """
    Generate monthly invoices for all active advertisers.
    
    This task runs on the 1st of each month to generate
    invoices for the previous month's billing period.
    """
    try:
        billing_service = AdvertiserBillingService()
        
        # Get previous month
        today = timezone.now().date()
        if today.month == 1:
            previous_month = 12
            previous_year = today.year - 1
        else:
            previous_month = today.month - 1
            previous_year = today.year
        
        # Get start and end dates for previous month
        start_date = date(previous_year, previous_month, 1)
        _, last_day = monthrange(previous_year, previous_month)
        end_date = date(previous_year, previous_month, last_day)
        
        # Get all active advertisers
        from ..models.advertiser import Advertiser
        active_advertisers = Advertiser.objects.filter(
            status='active'
        ).select_related('profile', 'wallet')
        
        invoices_generated = 0
        invoices_failed = 0
        total_amount = 0
        
        for advertiser in active_advertisers:
            try:
                # Check if invoice already exists for this period
                existing_invoice = AdvertiserInvoice.objects.filter(
                    advertiser=advertiser,
                    period=f"{previous_year}-{previous_month:02d}",
                    start_date=start_date,
                    end_date=end_date
                ).first()
                
                if existing_invoice:
                    logger.info(f"Invoice already exists for advertiser {advertiser.id} for period {previous_year}-{previous_month:02d}")
                    continue
                
                # Calculate billing data for the period
                billing_data = billing_service.calculate_monthly_billing(
                    advertiser,
                    start_date,
                    end_date
                )
                
                if billing_data.get('total_amount', 0) > 0:
                    # Generate invoice number
                    invoice_number = _generate_invoice_number(advertiser, previous_year, previous_month)
                    
                    # Create invoice
                    invoice = AdvertiserInvoice.objects.create(
                        advertiser=advertiser,
                        invoice_number=invoice_number,
                        period=f"{previous_year}-{previous_month:02d}",
                        start_date=start_date,
                        end_date=end_date,
                        subtotal=billing_data.get('subtotal', 0),
                        tax_amount=billing_data.get('tax_amount', 0),
                        fee_amount=billing_data.get('fee_amount', 0),
                        total_amount=billing_data.get('total_amount', 0),
                        currency=billing_data.get('currency', 'USD'),
                        status='draft',
                        created_at=timezone.now()
                    )
                    
                    # Add line items
                    for item in billing_data.get('line_items', []):
                        invoice.line_items.create(
                            item_type=item.get('type'),
                            description=item.get('description'),
                            quantity=item.get('quantity', 1),
                            unit_price=item.get('unit_price', 0),
                            total_price=item.get('total_price', 0),
                            metadata=item.get('metadata', {})
                        )
                    
                    # Generate PDF
                    _generate_invoice_pdf(invoice)
                    
                    # Update status to sent
                    invoice.status = 'sent'
                    invoice.sent_at = timezone.now()
                    invoice.save()
                    
                    invoices_generated += 1
                    total_amount += billing_data.get('total_amount', 0)
                    
                    logger.info(f"Invoice generated for advertiser {advertiser.id}: {invoice_number} - ${billing_data.get('total_amount', 0):.2f}")
                    
                    # Send invoice notification
                    _send_invoice_notification(advertiser, invoice)
                else:
                    logger.info(f"No billing activity for advertiser {advertiser.id} in period {previous_year}-{previous_month:02d}")
                
            except Exception as e:
                invoices_failed += 1
                logger.error(f"Error generating invoice for advertiser {advertiser.id}: {e}")
                continue
        
        logger.info(f"Monthly invoice generation completed: {invoices_generated} invoices generated, {invoices_failed} failed, total: ${total_amount:.2f}")
        
        return {
            'period': f"{previous_year}-{previous_month:02d}",
            'advertisers_checked': active_advertisers.count(),
            'invoices_generated': invoices_generated,
            'invoices_failed': invoices_failed,
            'total_amount': total_amount,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in monthly invoice generation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.send_invoice_reminders")
def send_invoice_reminders():
    """
    Send invoice reminders for overdue invoices.
    
    This task runs daily to check for overdue invoices
    and send reminder notifications.
    """
    try:
        # Get overdue invoices
        today = timezone.now().date()
        overdue_invoices = AdvertiserInvoice.objects.filter(
            status__in=['sent', 'overdue'],
            due_date__lt=today
        ).select_related('advertiser')
        
        reminders_sent = 0
        
        for invoice in overdue_invoices:
            try:
                # Calculate days overdue
                days_overdue = (today - invoice.due_date).days
                
                # Determine reminder type
                if days_overdue <= 7:
                    reminder_type = 'first_reminder'
                    subject = 'Invoice Payment Reminder'
                elif days_overdue <= 14:
                    reminder_type = 'second_reminder'
                    subject = 'Invoice Overdue Notice'
                else:
                    reminder_type = 'final_notice'
                    subject = 'Final Invoice Notice - Immediate Action Required'
                
                # Send reminder notification
                _send_invoice_reminder_notification(invoice, reminder_type, days_overdue)
                
                # Update invoice status if very overdue
                if days_overdue > 30:
                    invoice.status = 'overdue'
                    invoice.save()
                
                reminders_sent += 1
                logger.info(f"Invoice reminder sent for invoice {invoice.invoice_number}: {days_overdue} days overdue")
                
            except Exception as e:
                logger.error(f"Error sending reminder for invoice {invoice.id}: {e}")
                continue
        
        logger.info(f"Invoice reminders completed: {reminders_sent} reminders sent")
        
        return {
            'date': today.isoformat(),
            'overdue_invoices': overdue_invoices.count(),
            'reminders_sent': reminders_sent,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in invoice reminder task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.update_invoice_statuses")
def update_invoice_statuses():
    """
    Update invoice statuses based on payments.
    
    This task runs daily to check for payments
    and update invoice statuses accordingly.
    """
    try:
        # Get sent invoices
        sent_invoices = AdvertiserInvoice.objects.filter(
            status='sent'
        ).select_related('advertiser')
        
        invoices_updated = 0
        
        for invoice in sent_invoices:
            try:
                # Check if payment has been received
                # This would integrate with actual payment processing
                payment_status = _check_invoice_payment_status(invoice)
                
                if payment_status.get('paid'):
                    # Update invoice status
                    invoice.status = 'paid'
                    invoice.paid_at = timezone.now()
                    invoice.save()
                    
                    invoices_updated += 1
                    logger.info(f"Invoice {invoice.invoice_number} marked as paid")
                    
                    # Send payment confirmation
                    _send_payment_confirmation_notification(invoice)
                
            except Exception as e:
                logger.error(f"Error updating status for invoice {invoice.id}: {e}")
                continue
        
        logger.info(f"Invoice status update completed: {invoices_updated} invoices updated")
        
        return {
            'invoices_checked': sent_invoices.count(),
            'invoices_updated': invoices_updated,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in invoice status update task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.generate_invoice_summaries")
def generate_invoice_summaries():
    """
    Generate monthly invoice summaries for reporting.
    
    This task runs monthly to generate summary reports
    of all invoices generated.
    """
    try:
        # Get previous month
        today = timezone.now().date()
        if today.month == 1:
            previous_month = 12
            previous_year = today.year - 1
        else:
            previous_month = today.month - 1
            previous_year = today.year
        
        # Get invoices for previous month
        invoices = AdvertiserInvoice.objects.filter(
            period=f"{previous_year}-{previous_month:02d}"
        ).select_related('advertiser')
        
        # Generate summary statistics
        summary = {
            'period': f"{previous_year}-{previous_month:02d}",
            'total_invoices': invoices.count(),
            'total_amount': float(invoices.aggregate(total=Sum('total_amount'))['total'] or 0),
            'paid_invoices': invoices.filter(status='paid').count(),
            'overdue_invoices': invoices.filter(status='overdue').count(),
            'pending_invoices': invoices.filter(status='sent').count(),
            'average_amount': float(invoices.aggregate(avg=Avg('total_amount'))['avg'] or 0),
            'generated_at': timezone.now().isoformat(),
        }
        
        # Calculate collection rate
        if summary['total_invoices'] > 0:
            summary['collection_rate'] = (summary['paid_invoices'] / summary['total_invoices'] * 100)
        else:
            summary['collection_rate'] = 0
        
        # Store summary
        _store_invoice_summary(summary)
        
        logger.info(f"Invoice summary generated for {previous_year}-{previous_month:02d}: {summary['total_invoices']} invoices, ${summary['total_amount']:.2f}")
        
        return summary
        
    except Exception as e:
        logger.error(f"Error in invoice summary generation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.archive_old_invoices")
def archive_old_invoices():
    """
    Archive old invoices to maintain performance.
    
    This task runs quarterly to archive invoices
    older than 2 years.
    """
    try:
        # Get invoices older than 2 years
        cutoff_date = timezone.now().date() - timezone.timedelta(days=730)
        
        old_invoices = AdvertiserInvoice.objects.filter(
            created_at__date__lt=cutoff_date
        ).select_related('advertiser')
        
        invoices_archived = 0
        
        for invoice in old_invoices:
            try:
                # Archive invoice
                invoice.is_archived = True
                invoice.save()
                
                invoices_archived += 1
                logger.info(f"Invoice {invoice.invoice_number} archived")
                
            except Exception as e:
                logger.error(f"Error archiving invoice {invoice.id}: {e}")
                continue
        
        logger.info(f"Invoice archival completed: {invoices_archived} invoices archived")
        
        return {
            'cutoff_date': cutoff_date.isoformat(),
            'invoices_archived': invoices_archived,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in invoice archival task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _generate_invoice_number(advertiser, year, month):
    """Generate unique invoice number."""
    try:
        # Format: ADV-{advertiser_id}-{YYYYMM}-{sequence}
        advertiser_id = str(advertiser.id).zfill(6)
        date_str = f"{year}{month:02d}"
        
        # Get sequence number for this advertiser and month
        count = AdvertiserInvoice.objects.filter(
            advertiser=advertiser,
            period=f"{year}-{month:02d}"
        ).count()
        
        sequence = str(count + 1).zfill(3)
        
        return f"ADV-{advertiser_id}-{date_str}-{sequence}"
        
    except Exception as e:
        logger.error(f"Error generating invoice number: {e}")
        return f"ADV-{advertiser.id}-{year}{month:02d}-001"


def _generate_invoice_pdf(invoice):
    """Generate PDF for invoice."""
    try:
        # This would implement actual PDF generation
        # For now, just log the action
        logger.info(f"Generating PDF for invoice {invoice.invoice_number}")
        
        # Create placeholder file path
        invoice.file_path = f"invoices/{invoice.advertiser.id}/{invoice.invoice_number}.pdf"
        invoice.save()
        
    except Exception as e:
        logger.error(f"Error generating invoice PDF: {e}")
        raise


def _send_invoice_notification(advertiser, invoice):
    """Send invoice notification to advertiser."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': advertiser,
            'type': 'invoice_generated',
            'title': 'New Invoice Generated',
            'message': f'Your invoice {invoice.invoice_number} for {invoice.period} is now available.',
            'data': {
                'invoice_id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'period': invoice.period,
                'total_amount': float(invoice.total_amount),
                'due_date': invoice.due_date.isoformat(),
                'file_path': invoice.file_path.name if invoice.file_path else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending invoice notification: {e}")


def _send_invoice_reminder_notification(invoice, reminder_type, days_overdue):
    """Send invoice reminder notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        subject_map = {
            'first_reminder': 'Invoice Payment Reminder',
            'second_reminder': 'Invoice Overdue Notice',
            'final_notice': 'Final Invoice Notice - Immediate Action Required'
        }
        
        notification_data = {
            'advertiser': invoice.advertiser,
            'type': 'invoice_reminder',
            'title': subject_map.get(reminder_type, 'Invoice Reminder'),
            'message': f'Your invoice {invoice.invoice_number} is {days_overdue} days overdue. Amount due: ${invoice.total_amount:.2f}',
            'data': {
                'invoice_id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'days_overdue': days_overdue,
                'total_amount': float(invoice.total_amount),
                'due_date': invoice.due_date.isoformat(),
                'reminder_type': reminder_type,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending invoice reminder notification: {e}")


def _send_payment_confirmation_notification(invoice):
    """Send payment confirmation notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': invoice.advertiser,
            'type': 'payment_confirmation',
            'title': 'Payment Confirmation',
            'message': f'Payment received for invoice {invoice.invoice_number}. Amount: ${invoice.total_amount:.2f}',
            'data': {
                'invoice_id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'amount_paid': float(invoice.total_amount),
                'paid_at': invoice.paid_at.isoformat() if invoice.paid_at else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending payment confirmation notification: {e}")


def _check_invoice_payment_status(invoice):
    """Check if invoice has been paid."""
    try:
        # This would integrate with actual payment processing system
        # For now, return unpaid status
        return {
            'paid': False,
            'amount_paid': 0,
            'payment_date': None,
            'payment_method': None,
        }
        
    except Exception as e:
        logger.error(f"Error checking invoice payment status: {e}")
        return {'paid': False}


def _store_invoice_summary(summary):
    """Store invoice summary for reporting."""
    try:
        # This would implement actual storage of summary data
        # For example, save to a statistics table or cache
        logger.info(f"Storing invoice summary for {summary['period']}: {summary}")
        
    except Exception as e:
        logger.error(f"Error storing invoice summary: {e}")
