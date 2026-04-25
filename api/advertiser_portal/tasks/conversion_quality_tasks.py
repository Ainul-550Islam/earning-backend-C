"""
Conversion Quality Tasks

Daily quality score calculation for conversions
and fraud detection analysis.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg

from ..models.fraud import ConversionQualityScore
try:
    from ..services import ConversionQualityService
except ImportError:
    ConversionQualityService = None
try:
    from ..services import AdvertiserFraudService
except ImportError:
    AdvertiserFraudService = None

import logging
logger = logging.getLogger(__name__)


@shared_task(name="advertiser_portal.calculate_conversion_quality_scores")
def calculate_conversion_quality_scores():
    """
    Calculate daily quality scores for all conversions.
    
    This task runs daily to analyze conversion quality
    and calculate quality scores for fraud detection.
    """
    try:
        quality_service = ConversionQualityService()
        
        # Get yesterday's date
        yesterday = timezone.now().date() - timezone.timedelta(days=1)
        
        # Get all conversions from yesterday
        from ..models.tracking import Conversion
        yesterday_conversions = Conversion.objects.filter(
            created_at__date=yesterday
        ).select_related('advertiser', 'offer', 'campaign')
        
        scores_calculated = 0
        scores_failed = 0
        
        for conversion in yesterday_conversions:
            try:
                # Check if quality score already exists
                existing_score = ConversionQualityScore.objects.filter(
                    conversion=conversion,
                    date=yesterday
                ).first()
                
                if existing_score:
                    logger.info(f"Quality score already exists for conversion {conversion.id}")
                    continue
                
                # Calculate quality score
                quality_result = quality_service.calculate_conversion_quality(conversion)
                
                if quality_result.get('success'):
                    # Create quality score record
                    quality_score = ConversionQualityScore.objects.create(
                        advertiser=conversion.advertiser,
                        conversion=conversion,
                        date=yesterday,
                        overall_score=quality_result.get('overall_score', 0),
                        behavioral_score=quality_result.get('behavioral_score', 0),
                        timing_score=quality_result.get('timing_score', 0),
                        engagement_score=quality_result.get('engagement_score', 0),
                        technical_score=quality_result.get('technical_score', 0),
                        fraud_score=quality_result.get('fraud_score', 0),
                        is_flagged=quality_result.get('is_flagged', False),
                        flag_reason=quality_result.get('flag_reason'),
                        risk_factors=quality_result.get('risk_factors', []),
                        metadata=quality_result.get('metadata', {}),
                        created_at=timezone.now()
                    )
                    
                    scores_calculated += 1
                    logger.info(f"Quality score calculated for conversion {conversion.id}: {quality_result.get('overall_score', 0)}")
                    
                    # Send flag notification if flagged
                    if quality_result.get('is_flagged', False):
                        _send_conversion_flag_notification(conversion.advertiser, quality_score)
                else:
                    scores_failed += 1
                    logger.error(f"Failed to calculate quality score for conversion {conversion.id}: {quality_result.get('error', 'Unknown error')}")
                
            except Exception as e:
                scores_failed += 1
                logger.error(f"Error calculating quality score for conversion {conversion.id}: {e}")
                continue
        
        logger.info(f"Conversion quality score calculation completed: {scores_calculated} scores calculated, {scores_failed} failed")
        
        return {
            'date': yesterday.isoformat(),
            'conversions_checked': yesterday_conversions.count(),
            'scores_calculated': scores_calculated,
            'scores_failed': scores_failed,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in conversion quality score calculation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.analyze_fraud_patterns")
def analyze_fraud_patterns():
    """
    Analyze fraud patterns across conversions.
    
    This task runs daily to identify fraud patterns
    and update fraud detection rules.
    """
    try:
        fraud_service = AdvertiserFraudService()
        
        # Get last 7 days of quality scores
        start_date = timezone.now().date() - timezone.timedelta(days=7)
        end_date = timezone.now().date()
        
        quality_scores = ConversionQualityScore.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
            is_flagged=True
        ).select_related('advertiser', 'conversion')
        
        patterns_analyzed = 0
        new_rules_created = 0
        
        # Analyze patterns by advertiser
        advertisers = quality_scores.values('advertiser').distinct()
        
        for advertiser_data in advertisers:
            try:
                advertiser_id = advertiser_data['advertiser']
                advertiser_scores = quality_scores.filter(advertiser_id=advertiser_id)
                
                # Analyze patterns for this advertiser
                pattern_analysis = fraud_service.analyze_fraud_patterns(advertiser_scores)
                
                if pattern_analysis.get('patterns_found'):
                    patterns_analyzed += len(pattern_analysis.get('patterns_found', []))
                    
                    # Create new fraud rules if needed
                    new_rules = fraud_service.create_fraud_rules_from_patterns(
                        advertiser_id,
                        pattern_analysis.get('patterns_found', [])
                    )
                    
                    new_rules_created += len(new_rules)
                    
                    logger.info(f"Fraud patterns analyzed for advertiser {advertiser_id}: {len(pattern_analysis.get('patterns_found', []))} patterns, {len(new_rules)} rules created")
                
            except Exception as e:
                logger.error(f"Error analyzing fraud patterns for advertiser {advertiser_id}: {e}")
                continue
        
        logger.info(f"Fraud pattern analysis completed: {patterns_analyzed} patterns analyzed, {new_rules_created} rules created")
        
        return {
            'period': f"{start_date.isoformat()} to {end_date.isoformat()}",
            'advertisers_analyzed': advertisers.count(),
            'patterns_analyzed': patterns_analyzed,
            'new_rules_created': new_rules_created,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in fraud pattern analysis task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.update_fraud_models")
def update_fraud_models():
    """
    Update fraud detection models with new data.
    
    This task runs weekly to retrain fraud detection
    models with the latest conversion data.
    """
    try:
        fraud_service = AdvertiserFraudService()
        
        # Get last 30 days of quality scores for training
        start_date = timezone.now().date() - timezone.timedelta(days=30)
        
        training_data = ConversionQualityScore.objects.filter(
            date__gte=start_date
        ).select_related('advertiser', 'conversion')
        
        if training_data.count() < 100:
            logger.warning("Insufficient training data for fraud model update")
            return {
                'error': 'Insufficient training data',
                'training_samples': training_data.count(),
                'timestamp': timezone.now().isoformat()
            }
        
        # Update fraud models
        model_update_result = fraud_service.update_fraud_models(training_data)
        
        if model_update_result.get('success'):
            logger.info(f"Fraud models updated successfully: {model_update_result.get('models_updated', 0)} models updated")
            
            # Send model update notification to admins
            _send_model_update_notification(model_update_result)
        else:
            logger.error(f"Fraud model update failed: {model_update_result.get('error', 'Unknown error')}")
        
        return {
            'training_samples': training_data.count(),
            'models_updated': model_update_result.get('models_updated', 0),
            'accuracy': model_update_result.get('accuracy', 0),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in fraud model update task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.generate_quality_reports")
def generate_quality_reports():
    """
    Generate daily conversion quality reports.
    
    This task runs daily to generate quality reports
    for advertisers and system administrators.
    """
    try:
        # Get yesterday's date
        yesterday = timezone.now().date() - timezone.timedelta(days=1)
        
        # Get quality scores for yesterday
        quality_scores = ConversionQualityScore.objects.filter(
            date=yesterday
        ).select_related('advertiser')
        
        # Generate advertiser reports
        advertisers = quality_scores.values('advertiser').distinct()
        reports_generated = 0
        
        for advertiser_data in advertisers:
            try:
                advertiser_id = advertiser_data['advertiser']
                advertiser_scores = quality_scores.filter(advertiser_id=advertiser_id)
                
                # Generate quality report
                report_data = _generate_advertiser_quality_report(advertiser_scores, yesterday)
                
                # Store report
                from ..models.reporting import QualityReport
                report = QualityReport.objects.create(
                    advertiser_id=advertiser_id,
                    report_date=yesterday,
                    data=report_data,
                    generated_at=timezone.now()
                )
                
                reports_generated += 1
                logger.info(f"Quality report generated for advertiser {advertiser_id}")
                
                # Send report notification if there are issues
                if report_data.get('flagged_conversions', 0) > 0:
                    _send_quality_report_notification(advertiser_id, report)
                
            except Exception as e:
                logger.error(f"Error generating quality report for advertiser {advertiser_id}: {e}")
                continue
        
        # Generate system quality summary
        system_summary = _generate_system_quality_summary(quality_scores, yesterday)
        
        logger.info(f"Quality report generation completed: {reports_generated} reports generated")
        
        return {
            'date': yesterday.isoformat(),
            'reports_generated': reports_generated,
            'system_summary': system_summary,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in quality report generation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.cleanup_quality_scores")
def cleanup_quality_scores():
    """
    Clean up old quality score records.
    
    This task runs monthly to archive quality scores
    older than 1 year to maintain performance.
    """
    try:
        # Get quality scores older than 1 year
        cutoff_date = timezone.now().date() - timezone.timedelta(days=365)
        
        old_scores = ConversionQualityScore.objects.filter(
            date__lt=cutoff_date
        ).select_related('advertiser', 'conversion')
        
        scores_archived = 0
        
        for score in old_scores:
            try:
                # Archive quality score
                score.is_archived = True
                score.save()
                
                scores_archived += 1
                logger.info(f"Quality score archived for conversion {score.conversion_id}")
                
            except Exception as e:
                logger.error(f"Error archiving quality score {score.id}: {e}")
                continue
        
        logger.info(f"Quality score cleanup completed: {scores_archived} scores archived")
        
        return {
            'cutoff_date': cutoff_date.isoformat(),
            'scores_archived': scores_archived,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in quality score cleanup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _send_conversion_flag_notification(advertiser, quality_score):
    """Send conversion flag notification to advertiser."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': advertiser,
            'type': 'conversion_flagged',
            'title': 'Conversion Flagged for Review',
            'message': f'A conversion has been flagged for potential fraud. Quality score: {quality_score.overall_score}',
            'data': {
                'conversion_id': quality_score.conversion.id,
                'quality_score': quality_score.overall_score,
                'fraud_score': quality_score.fraud_score,
                'flag_reason': quality_score.flag_reason,
                'risk_factors': quality_score.risk_factors,
                'flagged_at': quality_score.created_at.isoformat(),
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending conversion flag notification: {e}")


def _send_model_update_notification(model_update_result):
    """Send model update notification to admins."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'type': 'fraud_model_updated',
            'title': 'Fraud Detection Models Updated',
            'message': f'Fraud detection models have been updated with {model_update_result.get("models_updated", 0)} models. Accuracy: {model_update_result.get("accuracy", 0):.2%}',
            'data': {
                'models_updated': model_update_result.get('models_updated', 0),
                'accuracy': model_update_result.get('accuracy', 0),
                'training_samples': model_update_result.get('training_samples', 0),
                'updated_at': timezone.now().isoformat(),
            }
        }
        
        notification_service.send_admin_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending model update notification: {e}")


def _generate_advertiser_quality_report(advertiser_scores, date):
    """Generate quality report for a specific advertiser."""
    try:
        total_conversions = advertiser_scores.count()
        flagged_conversions = advertiser_scores.filter(is_flagged=True).count()
        
        # Calculate average scores
        avg_scores = advertiser_scores.aggregate(
            avg_overall=Avg('overall_score'),
            avg_behavioral=Avg('behavioral_score'),
            avg_timing=Avg('timing_score'),
            avg_engagement=Avg('engagement_score'),
            avg_technical=Avg('technical_score'),
            avg_fraud=Avg('fraud_score')
        )
        
        # Get risk factors
        all_risk_factors = []
        for score in advertiser_scores:
            if score.risk_factors:
                all_risk_factors.extend(score.risk_factors)
        
        # Count risk factors
        risk_factor_counts = {}
        for factor in all_risk_factors:
            risk_factor_counts[factor] = risk_factor_counts.get(factor, 0) + 1
        
        return {
            'date': date.isoformat(),
            'total_conversions': total_conversions,
            'flagged_conversions': flagged_conversions,
            'flag_rate': (flagged_conversions / total_conversions * 100) if total_conversions > 0 else 0,
            'average_scores': {
                'overall': float(avg_scores['avg_overall'] or 0),
                'behavioral': float(avg_scores['avg_behavioral'] or 0),
                'timing': float(avg_scores['avg_timing'] or 0),
                'engagement': float(avg_scores['avg_engagement'] or 0),
                'technical': float(avg_scores['avg_technical'] or 0),
                'fraud': float(avg_scores['avg_fraud'] or 0),
            },
            'risk_factors': risk_factor_counts,
            'generated_at': timezone.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error generating advertiser quality report: {e}")
        return {}


def _generate_system_quality_summary(quality_scores, date):
    """Generate system-wide quality summary."""
    try:
        total_conversions = quality_scores.count()
        flagged_conversions = quality_scores.filter(is_flagged=True).count()
        
        # Calculate average scores
        avg_scores = quality_scores.aggregate(
            avg_overall=Avg('overall_score'),
            avg_behavioral=Avg('behavioral_score'),
            avg_timing=Avg('timing_score'),
            avg_engagement=Avg('engagement_score'),
            avg_technical=Avg('technical_score'),
            avg_fraud=Avg('fraud_score')
        )
        
        # Get top risk factors
        all_risk_factors = []
        for score in quality_scores:
            if score.risk_factors:
                all_risk_factors.extend(score.risk_factors)
        
        risk_factor_counts = {}
        for factor in all_risk_factors:
            risk_factor_counts[factor] = risk_factor_counts.get(factor, 0) + 1
        
        # Sort risk factors by count
        sorted_risk_factors = sorted(risk_factor_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            'date': date.isoformat(),
            'total_conversions': total_conversions,
            'flagged_conversions': flagged_conversions,
            'flag_rate': (flagged_conversions / total_conversions * 100) if total_conversions > 0 else 0,
            'average_scores': {
                'overall': float(avg_scores['avg_overall'] or 0),
                'behavioral': float(avg_scores['avg_behavioral'] or 0),
                'timing': float(avg_scores['avg_timing'] or 0),
                'engagement': float(avg_scores['avg_engagement'] or 0),
                'technical': float(avg_scores['avg_technical'] or 0),
                'fraud': float(avg_scores['avg_fraud'] or 0),
            },
            'top_risk_factors': sorted_risk_factors,
            'generated_at': timezone.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error generating system quality summary: {e}")
        return {}


def _send_quality_report_notification(advertiser_id, report):
    """Send quality report notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        report_data = report.data
        
        notification_data = {
            'advertiser_id': advertiser_id,
            'type': 'quality_report',
            'title': 'Daily Quality Report Available',
            'message': f'Your daily conversion quality report is available. {report_data.get("flagged_conversions", 0)} conversions flagged for review.',
            'data': {
                'report_id': report.id,
                'report_date': report.report_date.isoformat(),
                'total_conversions': report_data.get('total_conversions', 0),
                'flagged_conversions': report_data.get('flagged_conversions', 0),
                'flag_rate': report_data.get('flag_rate', 0),
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending quality report notification: {e}")
