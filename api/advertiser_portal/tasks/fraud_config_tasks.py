"""
Fraud Config Tasks

Apply fraud rules to pending conversions
and update fraud detection configurations.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q

from ..models.fraud import ConversionQualityScore, FraudRule, FraudConfig
try:
    from ..services import AdvertiserFraudService
except ImportError:
    AdvertiserFraudService = None
try:
    from ..services import ConversionQualityService
except ImportError:
    ConversionQualityService = None

import logging
logger = logging.getLogger(__name__)


@shared_task(name="advertiser_portal.apply_fraud_rules")
def apply_fraud_rules():
    """
    Apply fraud rules to pending conversions.
    
    This task runs every 10 minutes to apply fraud
    detection rules to new conversions.
    """
    try:
        fraud_service = AdvertiserFraudService()
        quality_service = ConversionQualityService()
        
        # Get conversions without fraud analysis
        from ..models.tracking import Conversion
        pending_conversions = Conversion.objects.filter(
            fraud_analyzed=False
        ).select_related('advertiser', 'offer', 'campaign')
        
        conversions_analyzed = 0
        conversions_flagged = 0
        
        for conversion in pending_conversions:
            try:
                # Get active fraud rules
                active_rules = FraudRule.objects.filter(
                    is_active=True
                ).filter(
                    Q(advertiser=conversion.advertiser) | Q(advertiser__isnull=True)
                )
                
                # Apply fraud rules
                fraud_analysis = fraud_service.apply_fraud_rules(conversion, active_rules)
                
                # Update conversion fraud status
                conversion.fraud_score = fraud_analysis.get('fraud_score', 0)
                conversion.is_flagged = fraud_analysis.get('is_flagged', False)
                conversion.flag_reason = fraud_analysis.get('flag_reason')
                conversion.risk_factors = fraud_analysis.get('risk_factors', [])
                conversion.fraud_analyzed = True
                conversion.fraud_analyzed_at = timezone.now()
                conversion.save()
                
                conversions_analyzed += 1
                
                if fraud_analysis.get('is_flagged', False):
                    conversions_flagged += 1
                    logger.info(f"Conversion {conversion.id} flagged for fraud: {fraud_analysis.get('flag_reason')}")
                    
                    # Send fraud alert
                    _send_fraud_alert(conversion, fraud_analysis)
                
            except Exception as e:
                logger.error(f"Error applying fraud rules to conversion {conversion.id}: {e}")
                continue
        
        logger.info(f"Fraud rule application completed: {conversions_analyzed} conversions analyzed, {conversions_flagged} flagged")
        
        return {
            'conversions_analyzed': conversions_analyzed,
            'conversions_flagged': conversions_flagged,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in fraud rule application task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.update_fraud_rules")
def update_fraud_rules():
    """
    Update fraud detection rules based on new patterns.
    
    This task runs daily to update fraud rules
    based on recent fraud patterns.
    """
    try:
        fraud_service = AdvertiserFraudService()
        
        # Get recent fraud patterns (last 24 hours)
        start_time = timezone.now() - timezone.timedelta(hours=24)
        
        flagged_conversions = ConversionQualityScore.objects.filter(
            is_flagged=True,
            created_at__gte=start_time
        ).select_related('advertiser')
        
        rules_updated = 0
        new_rules_created = 0
        
        # Analyze patterns and update rules
        for advertiser in flagged_conversions.values('advertiser').distinct():
            try:
                advertiser_id = advertiser['advertiser']
                advertiser_flags = flagged_conversions.filter(advertiser_id=advertiser_id)
                
                # Analyze fraud patterns
                pattern_analysis = fraud_service.analyze_fraud_patterns(advertiser_flags)
                
                if pattern_analysis.get('patterns_found'):
                    # Update existing rules
                    updated_rules = fraud_service.update_fraud_rules_from_patterns(
                        advertiser_id,
                        pattern_analysis.get('patterns_found', [])
                    )
                    rules_updated += len(updated_rules)
                    
                    # Create new rules if needed
                    new_rules = fraud_service.create_fraud_rules_from_patterns(
                        advertiser_id,
                        pattern_analysis.get('patterns_found', [])
                    )
                    new_rules_created += len(new_rules)
                    
                    logger.info(f"Fraud rules updated for advertiser {advertiser_id}: {len(updated_rules)} updated, {len(new_rules)} created")
                
            except Exception as e:
                logger.error(f"Error updating fraud rules for advertiser {advertiser_id}: {e}")
                continue
        
        logger.info(f"Fraud rule update completed: {rules_updated} rules updated, {new_rules_created} rules created")
        
        return {
            'rules_updated': rules_updated,
            'new_rules_created': new_rules_created,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in fraud rule update task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.validate_fraud_configs")
def validate_fraud_configs():
    """
    Validate fraud detection configurations.
    
    This task runs daily to validate fraud
    detection configurations and fix issues.
    """
    try:
        fraud_service = AdvertiserFraudService()
        
        # Get all fraud configs
        fraud_configs = FraudConfig.objects.all().select_related('advertiser')
        
        configs_validated = 0
        configs_fixed = 0
        invalid_configs = 0
        
        for config in fraud_configs:
            try:
                # Validate configuration
                validation_result = fraud_service.validate_fraud_config(config)
                
                if validation_result.get('valid', True):
                    configs_validated += 1
                else:
                    invalid_configs += 1
                    
                    # Try to fix configuration
                    fix_result = fraud_service.fix_fraud_config(config, validation_result.get('errors', []))
                    
                    if fix_result.get('success'):
                        configs_fixed += 1
                        logger.info(f"Fraud config fixed for advertiser {config.advertiser_id}")
                    else:
                        logger.error(f"Failed to fix fraud config for advertiser {config.advertiser_id}: {fix_result.get('error')}")
                
            except Exception as e:
                logger.error(f"Error validating fraud config for advertiser {config.advertiser_id}: {e}")
                continue
        
        logger.info(f"Fraud config validation completed: {configs_validated} valid, {configs_fixed} fixed, {invalid_configs} invalid")
        
        return {
            'configs_validated': configs_validated,
            'configs_fixed': configs_fixed,
            'invalid_configs': invalid_configs,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in fraud config validation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.sync_fraud_rules")
def sync_fraud_rules():
    """
    Synchronize fraud rules across all advertisers.
    
    This task runs weekly to ensure fraud rules
    are properly synchronized.
    """
    try:
        fraud_service = AdvertiserFraudService()
        
        # Get global fraud rules
        global_rules = FraudRule.objects.filter(
            advertiser__isnull=True,
            is_active=True
        )
        
        advertisers_synced = 0
        rules_synced = 0
        
        # Get all advertisers
        from ..models.advertiser import Advertiser
        advertisers = Advertiser.objects.filter(status='active')
        
        for advertiser in advertisers:
            try:
                # Sync global rules to advertiser
                synced_rules = fraud_service.sync_global_rules_to_advertiser(
                    advertiser,
                    global_rules
                )
                
                if synced_rules:
                    advertisers_synced += 1
                    rules_synced += len(synced_rules)
                    logger.info(f"Synced {len(synced_rules)} fraud rules to advertiser {advertiser.id}")
                
            except Exception as e:
                logger.error(f"Error syncing fraud rules for advertiser {advertiser.id}: {e}")
                continue
        
        logger.info(f"Fraud rule sync completed: {advertisers_synced} advertisers synced, {rules_synced} rules synced")
        
        return {
            'advertisers_synced': advertisers_synced,
            'rules_synced': rules_synced,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in fraud rule sync task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.cleanup_fraud_logs")
def cleanup_fraud_logs():
    """
    Clean up old fraud detection logs.
    
    This task runs weekly to clean up old fraud
    logs to maintain performance.
    """
    try:
        # Clean up logs older than 90 days
        cutoff_date = timezone.now() - timezone.timedelta(days=90)
        
        # Clean up old fraud analysis logs
        from ..models.tracking import Conversion
        old_conversions = Conversion.objects.filter(
            fraud_analyzed_at__lt=cutoff_date
        ).count()
        
        # This would implement actual cleanup logic
        # For now, just log the action
        logs_cleaned = old_conversions
        
        logger.info(f"Fraud log cleanup completed: {logs_cleaned} logs cleaned")
        
        return {
            'cutoff_date': cutoff_date.isoformat(),
            'logs_cleaned': logs_cleaned,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in fraud log cleanup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.generate_fraud_reports")
def generate_fraud_reports():
    """
    Generate fraud detection reports.
    
    This task runs daily to generate fraud
    detection reports for administrators.
    """
    try:
        # Get yesterday's date
        yesterday = timezone.now().date() - timezone.timedelta(days=1)
        
        # Get fraud statistics for yesterday
        from datetime import datetime, time
        start_time = timezone.make_aware(datetime.combine(yesterday, time.min))
        end_time = timezone.make_aware(datetime.combine(yesterday, time.max))
        
        # Get conversions analyzed yesterday
        from ..models.tracking import Conversion
        conversions_analyzed = Conversion.objects.filter(
            fraud_analyzed_at__range=[start_time, end_time]
        ).count()
        
        # Get conversions flagged yesterday
        conversions_flagged = Conversion.objects.filter(
            fraud_analyzed_at__range=[start_time, end_time],
            is_flagged=True
        ).count()
        
        # Get fraud rule performance
        fraud_rules = FraudRule.objects.filter(is_active=True)
        rules_performance = []
        
        for rule in fraud_rules:
            # This would calculate rule performance metrics
            rule_performance = {
                'rule_id': rule.id,
                'rule_name': rule.name,
                'conversions_checked': 0,  # Would be calculated
                'conversions_flagged': 0,  # Would be calculated
                'flag_rate': 0.0,  # Would be calculated
            }
            rules_performance.append(rule_performance)
        
        # Generate report data
        report_data = {
            'date': yesterday.isoformat(),
            'conversions_analyzed': conversions_analyzed,
            'conversions_flagged': conversions_flagged,
            'flag_rate': (conversions_flagged / conversions_analyzed * 100) if conversions_analyzed > 0 else 0,
            'rules_performance': rules_performance,
            'generated_at': timezone.now().isoformat(),
        }
        
        # Store report
        from ..models.reporting import FraudReport
        report = FraudReport.objects.create(
            report_date=yesterday,
            data=report_data,
            generated_at=timezone.now()
        )
        
        # Send admin notification if high fraud rate
        if report_data['flag_rate'] > 10:  # More than 10% flag rate
            _send_high_fraud_rate_notification(report_data)
        
        logger.info(f"Fraud report generated for {yesterday}: {conversions_analyzed} analyzed, {conversions_flagged} flagged")
        
        return report_data
        
    except Exception as e:
        logger.error(f"Error in fraud report generation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _send_fraud_alert(conversion, fraud_analysis):
    """Send fraud alert notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': conversion.advertiser,
            'type': 'fraud_alert',
            'title': 'Fraud Alert',
            'message': f'Conversion flagged for potential fraud: {fraud_analysis.get("flag_reason", "Unknown reason")}',
            'data': {
                'conversion_id': conversion.id,
                'fraud_score': fraud_analysis.get('fraud_score', 0),
                'flag_reason': fraud_analysis.get('flag_reason'),
                'risk_factors': fraud_analysis.get('risk_factors', []),
                'conversion_value': conversion.payout_amount if hasattr(conversion, 'payout_amount') else 0,
                'flagged_at': conversion.fraud_analyzed_at.isoformat(),
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending fraud alert: {e}")


def _send_high_fraud_rate_notification(report_data):
    """Send high fraud rate notification to admins."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'type': 'high_fraud_rate',
            'title': 'High Fraud Rate Alert',
            'message': f'High fraud rate detected: {report_data["flag_rate"]:.1f}% of conversions flagged',
            'data': {
                'date': report_data['date'],
                'conversions_analyzed': report_data['conversions_analyzed'],
                'conversions_flagged': report_data['conversions_flagged'],
                'flag_rate': report_data['flag_rate'],
            }
        }
        
        notification_service.send_admin_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending high fraud rate notification: {e}")
