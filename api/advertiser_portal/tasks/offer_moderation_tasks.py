"""
Offer Moderation Tasks

Queue new offers for review and
automated content moderation.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q

from ..models.offer import AdvertiserOffer
try:
    from ..services import OfferModerationService
except ImportError:
    OfferModerationService = None
try:
    from ..services import OfferPublishService
except ImportError:
    OfferPublishService = None

import logging
logger = logging.getLogger(__name__)


@shared_task(name="advertiser_portal.queue_new_offers_for_review")
def queue_new_offers_for_review():
    """
    Queue new offers for moderation review.
    
    This task runs every 10 minutes to check for
    new offers and queue them for moderation.
    """
    try:
        moderation_service = OfferModerationService()
        
        # Get offers pending moderation
        pending_offers = AdvertiserOffer.objects.filter(
            status='pending_review'
        ).select_related('advertiser', 'advertiser__profile')
        
        offers_queued = 0
        offers_failed = 0
        
        for offer in pending_offers:
            try:
                # Check if offer is already queued
                if offer.moderation_queued_at:
                    logger.info(f"Offer {offer.id} already queued for moderation")
                    continue
                
                # Queue offer for moderation
                queue_result = moderation_service.queue_offer_for_moderation(offer)
                
                if queue_result.get('success'):
                    offers_queued += 1
                    logger.info(f"Offer {offer.id} queued for moderation")
                    
                    # Send queued notification
                    _send_offer_queued_notification(offer)
                else:
                    offers_failed += 1
                    logger.error(f"Failed to queue offer {offer.id} for moderation: {queue_result.get('error', 'Unknown error')}")
                
            except Exception as e:
                offers_failed += 1
                logger.error(f"Error queuing offer {offer.id} for moderation: {e}")
                continue
        
        logger.info(f"Offer moderation queue completed: {offers_queued} offers queued, {offers_failed} failed")
        
        return {
            'offers_checked': pending_offers.count(),
            'offers_queued': offers_queued,
            'offers_failed': offers_failed,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in offer moderation queue task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.perform_automated_moderation")
def perform_automated_moderation():
    """
    Perform automated content moderation on queued offers.
    
    This task runs every 5 minutes to perform automated
    moderation checks on queued offers.
    """
    try:
        moderation_service = OfferModerationService()
        
        # Get offers queued for automated moderation
        queued_offers = AdvertiserOffer.objects.filter(
            status='pending_review',
            moderation_queued_at__isnull=False,
            moderation_status='pending'
        ).select_related('advertiser')
        
        offers_processed = 0
        offers_approved = 0
        offers_rejected = 0
        offers_flagged = 0
        
        for offer in queued_offers:
            try:
                # Perform automated moderation
                moderation_result = moderation_service.perform_automated_moderation(offer)
                
                if moderation_result.get('success'):
                    offers_processed += 1
                    
                    # Update offer moderation status
                    offer.moderation_status = moderation_result.get('status', 'pending')
                    offer.moderation_score = moderation_result.get('score', 0)
                    offer.moderation_issues = moderation_result.get('issues', [])
                    offer.moderation_completed_at = timezone.now()
                    offer.save()
                    
                    # Handle moderation results
                    if moderation_result.get('status') == 'approved':
                        offers_approved += 1
                        logger.info(f"Offer {offer.id} automatically approved")
                        
                        # Approve offer
                        _approve_offer(offer)
                        
                    elif moderation_result.get('status') == 'rejected':
                        offers_rejected += 1
                        logger.info(f"Offer {offer.id} automatically rejected: {moderation_result.get('reason', 'Unknown reason')}")
                        
                        # Reject offer
                        _reject_offer(offer, moderation_result.get('reason', 'Automated rejection'))
                        
                    elif moderation_result.get('status') == 'flagged':
                        offers_flagged += 1
                        logger.warning(f"Offer {offer.id} flagged for manual review: {moderation_result.get('issues', [])}")
                        
                        # Send flag notification
                        _send_offer_flagged_notification(offer, moderation_result)
                else:
                    logger.error(f"Automated moderation failed for offer {offer.id}: {moderation_result.get('error', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"Error performing automated moderation for offer {offer.id}: {e}")
                continue
        
        logger.info(f"Automated moderation completed: {offers_processed} processed, {offers_approved} approved, {offers_rejected} rejected, {offers_flagged} flagged")
        
        return {
            'offers_processed': offers_processed,
            'offers_approved': offers_approved,
            'offers_rejected': offers_rejected,
            'offers_flagged': offers_flagged,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in automated moderation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.update_moderation_rules")
def update_moderation_rules():
    """
    Update moderation rules based on new patterns.
    
    This task runs daily to update moderation rules
    based on recent moderation patterns.
    """
    try:
        moderation_service = OfferModerationService()
        
        # Get recent moderation results (last 24 hours)
        start_time = timezone.now() - timezone.timedelta(hours=24)
        
        recent_moderations = AdvertiserOffer.objects.filter(
            moderation_completed_at__gte=start_time
        ).select_related('advertiser')
        
        rules_updated = 0
        new_rules_created = 0
        
        # Analyze moderation patterns
        pattern_analysis = moderation_service.analyze_moderation_patterns(recent_moderations)
        
        if pattern_analysis.get('patterns_found'):
            # Update existing rules
            updated_rules = moderation_service.update_moderation_rules_from_patterns(
                pattern_analysis.get('patterns_found', [])
            )
            rules_updated += len(updated_rules)
            
            # Create new rules if needed
            new_rules = moderation_service.create_moderation_rules_from_patterns(
                pattern_analysis.get('patterns_found', [])
            )
            new_rules_created += len(new_rules)
            
            logger.info(f"Moderation rules updated: {len(updated_rules)} updated, {len(new_rules)} created")
        
        logger.info(f"Moderation rule update completed: {rules_updated} rules updated, {new_rules_created} rules created")
        
        return {
            'moderations_analyzed': recent_moderations.count(),
            'rules_updated': rules_updated,
            'new_rules_created': new_rules_created,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in moderation rule update task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.publish_approved_offers")
def publish_approved_offers():
    """
    Publish offers that have been approved.
    
    This task runs every 5 minutes to publish
    offers that have been approved.
    """
    try:
        publish_service = OfferPublishService()
        
        # Get approved but unpublished offers
        approved_offers = AdvertiserOffer.objects.filter(
            status='approved',
            is_published=False
        ).select_related('advertiser')
        
        offers_published = 0
        offers_failed = 0
        
        for offer in approved_offers:
            try:
                # Publish offer
                publish_result = publish_service.publish_offer(offer)
                
                if publish_result.get('success'):
                    offers_published += 1
                    logger.info(f"Offer {offer.id} published successfully")
                    
                    # Send publish notification
                    _send_offer_published_notification(offer)
                else:
                    offers_failed += 1
                    logger.error(f"Failed to publish offer {offer.id}: {publish_result.get('error', 'Unknown error')}")
                
            except Exception as e:
                offers_failed += 1
                logger.error(f"Error publishing offer {offer.id}: {e}")
                continue
        
        logger.info(f"Offer publishing completed: {offers_published} published, {offers_failed} failed")
        
        return {
            'offers_checked': approved_offers.count(),
            'offers_published': offers_published,
            'offers_failed': offers_failed,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in offer publishing task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.check_offer_compliance")
def check_offer_compliance():
    """
    Check compliance of published offers.
    
    This task runs daily to check if published offers
    still comply with platform policies.
    """
    try:
        moderation_service = OfferModerationService()
        
        # Get all published offers
        published_offers = AdvertiserOffer.objects.filter(
            status='approved',
            is_published=True
        ).select_related('advertiser')
        
        offers_checked = 0
        offers_flagged = 0
        
        for offer in published_offers:
            try:
                # Check compliance
                compliance_result = moderation_service.check_offer_compliance(offer)
                
                if not compliance_result.get('compliant', True):
                    # Flag offer for compliance issues
                    offer.status = 'flagged'
                    offer.compliance_issues = compliance_result.get('issues', [])
                    offer.flagged_at = timezone.now()
                    offer.save()
                    
                    offers_flagged += 1
                    logger.warning(f"Offer {offer.id} flagged for compliance: {compliance_result.get('issues', [])}")
                    
                    # Send compliance notification
                    _send_compliance_notification(offer, compliance_result.get('issues', []))
                else:
                    # Mark as compliant
                    offer.last_compliance_check = timezone.now()
                    offer.save()
                
                offers_checked += 1
                
            except Exception as e:
                logger.error(f"Error checking compliance for offer {offer.id}: {e}")
                continue
        
        logger.info(f"Offer compliance check completed: {offers_checked} checked, {offers_flagged} flagged")
        
        return {
            'offers_checked': offers_checked,
            'offers_flagged': offers_flagged,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in offer compliance check task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.generate_moderation_reports")
def generate_moderation_reports():
    """
    Generate moderation reports for administrators.
    
    This task runs daily to generate moderation
    reports and statistics.
    """
    try:
        # Get yesterday's date
        yesterday = timezone.now().date() - timezone.timedelta(days=1)
        
        # Get moderation statistics for yesterday
        from datetime import datetime, time
        start_time = timezone.make_aware(datetime.combine(yesterday, time.min))
        end_time = timezone.make_aware(datetime.combine(yesterday, time.max))
        
        # Get offers moderated yesterday
        moderated_offers = AdvertiserOffer.objects.filter(
            moderation_completed_at__range=[start_time, end_time]
        ).select_related('advertiser')
        
        # Calculate statistics
        total_moderated = moderated_offers.count()
        auto_approved = moderated_offers.filter(moderation_status='approved').count()
        auto_rejected = moderated_offers.filter(moderation_status='rejected').count()
        flagged_for_review = moderated_offers.filter(moderation_status='flagged').count()
        
        # Generate report data
        report_data = {
            'date': yesterday.isoformat(),
            'total_moderated': total_moderated,
            'auto_approved': auto_approved,
            'auto_rejected': auto_rejected,
            'flagged_for_review': flagged_for_review,
            'auto_approval_rate': (auto_approved / total_moderated * 100) if total_moderated > 0 else 0,
            'auto_rejection_rate': (auto_rejected / total_moderated * 100) if total_moderated > 0 else 0,
            'flag_rate': (flagged_for_review / total_moderated * 100) if total_moderated > 0 else 0,
            'generated_at': timezone.now().isoformat(),
        }
        
        # Store report
        from ..models.reporting import ModerationReport
        report = ModerationReport.objects.create(
            report_date=yesterday,
            data=report_data,
            generated_at=timezone.now()
        )
        
        # Send admin notification if high flag rate
        if report_data['flag_rate'] > 20:  # More than 20% flag rate
            _send_high_flag_rate_notification(report_data)
        
        logger.info(f"Moderation report generated for {yesterday}: {total_moderated} offers moderated")
        
        return report_data
        
    except Exception as e:
        logger.error(f"Error in moderation report generation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _approve_offer(offer):
    """Approve an offer."""
    try:
        offer.status = 'approved'
        offer.approved_at = timezone.now()
        offer.save()
        
        # Send approval notification
        _send_offer_approval_notification(offer)
        
    except Exception as e:
        logger.error(f"Error approving offer {offer.id}: {e}")
        raise


def _reject_offer(offer, reason):
    """Reject an offer."""
    try:
        offer.status = 'rejected'
        offer.rejected_at = timezone.now()
        offer.rejection_reason = reason
        offer.save()
        
        # Send rejection notification
        _send_offer_rejection_notification(offer, reason)
        
    except Exception as e:
        logger.error(f"Error rejecting offer {offer.id}: {e}")
        raise


def _send_offer_queued_notification(offer):
    """Send offer queued notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': offer.advertiser,
            'type': 'offer_queued',
            'title': 'Offer Queued for Review',
            'message': f'Your offer "{offer.name}" has been queued for moderation review.',
            'data': {
                'offer_id': offer.id,
                'offer_name': offer.name,
                'queued_at': offer.moderation_queued_at.isoformat() if offer.moderation_queued_at else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending offer queued notification: {e}")


def _send_offer_approval_notification(offer):
    """Send offer approval notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': offer.advertiser,
            'type': 'offer_approved',
            'title': 'Offer Approved',
            'message': f'Your offer "{offer.name}" has been approved and will be published shortly.',
            'data': {
                'offer_id': offer.id,
                'offer_name': offer.name,
                'approved_at': offer.approved_at.isoformat() if offer.approved_at else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending offer approval notification: {e}")


def _send_offer_rejection_notification(offer, reason):
    """Send offer rejection notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': offer.advertiser,
            'type': 'offer_rejected',
            'title': 'Offer Rejected',
            'message': f'Your offer "{offer.name}" has been rejected: {reason}',
            'data': {
                'offer_id': offer.id,
                'offer_name': offer.name,
                'rejection_reason': reason,
                'rejected_at': offer.rejected_at.isoformat() if offer.rejected_at else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending offer rejection notification: {e}")


def _send_offer_flagged_notification(offer, moderation_result):
    """Send offer flagged notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': offer.advertiser,
            'type': 'offer_flagged',
            'title': 'Offer Flagged for Review',
            'message': f'Your offer "{offer.name}" has been flagged for manual review: {", ".join(moderation_result.get("issues", []))}',
            'data': {
                'offer_id': offer.id,
                'offer_name': offer.name,
                'issues': moderation_result.get('issues', []),
                'moderation_score': moderation_result.get('score', 0),
                'flagged_at': timezone.now().isoformat(),
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending offer flagged notification: {e}")


def _send_offer_published_notification(offer):
    """Send offer published notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': offer.advertiser,
            'type': 'offer_published',
            'title': 'Offer Published',
            'message': f'Your offer "{offer.name}" has been published and is now live.',
            'data': {
                'offer_id': offer.id,
                'offer_name': offer.name,
                'published_at': timezone.now().isoformat(),
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending offer published notification: {e}")


def _send_compliance_notification(offer, issues):
    """Send compliance notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': offer.advertiser,
            'type': 'offer_compliance_issue',
            'title': 'Offer Compliance Issue',
            'message': f'Your offer "{offer.name}" has compliance issues: {", ".join(issues)}',
            'data': {
                'offer_id': offer.id,
                'offer_name': offer.name,
                'compliance_issues': issues,
                'flagged_at': offer.flagged_at.isoformat() if offer.flagged_at else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending compliance notification: {e}")


def _send_high_flag_rate_notification(report_data):
    """Send high flag rate notification to admins."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'type': 'high_flag_rate',
            'title': 'High Offer Flag Rate Alert',
            'message': f'High offer flag rate detected: {report_data["flag_rate"]:.1f}% of offers flagged for manual review',
            'data': {
                'date': report_data['date'],
                'total_moderated': report_data['total_moderated'],
                'flagged_for_review': report_data['flagged_for_review'],
                'flag_rate': report_data['flag_rate'],
            }
        }
        
        notification_service.send_admin_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending high flag rate notification: {e}")
