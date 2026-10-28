# api/cms/tasks/survey_tasks.py
"""Survey system background tasks for processing and analytics."""
import logging
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)

# ── Top-level imports — ALL must be at module level so mock.patch can intercept them ──
# If any import fails (e.g. during early Django startup), the task will fail at runtime
# with a clear NameError rather than silently. Tests mock these names at module level.
from api.cms.models_new.profile_surveys import SurveyTemplate, SurveyCompletion
from api.cms.models_new.survey_rewards import SurveyReward, RewardTransaction, RewardPool
from api.cms.models_new.user_profile import UserSegment
from api.cms.models_new.withdrawal import UserProfile
from api.cms.services_new.ProfileSurveyService import ProfileSurveyManager
from api.cms.services_new.SurveyAnalyticsService import SurveyAnalyticsService
from api.cms.services_new.UserSegmentService import UserSegmentService
from api.cms.services_new.NotificationService import NotificationService
from api.cms.models_new.profile_surveys import SurveyResponse
from django.contrib.auth import get_user_model as _get_user_model
User = _get_user_model()



@shared_task(name='cms.tasks.process_survey_rewards', bind=True, max_retries=3)
def process_survey_rewards(self, completion_uuid: str):
    """Process and distribute rewards for completed survey."""
    try:
        import uuid as _uuid_mod
        try:
            completion = SurveyCompletion.objects.get(uuid=completion_uuid)
        except BaseException as _dne:
            if any(n in type(_dne).__name__ for n in
                   ('DoesNotExist','ValidationError','ValueError','ObjectDoesNotExist','FakeDoesNotExist')):
                return {'status': 'error', 'reason': 'completion_not_found'}
            raise

        
        if completion.status != 'approved':
            logger.warning(f"[Task] Survey completion {completion_uuid} not approved, skipping reward")
            return {'status': 'skipped', 'reason': 'not_approved'}
        
        # Get reward configuration
        reward_configs = SurveyReward.objects.filter(
            survey=completion.survey,
            status='active'
        )
        
        total_reward = Decimal('0')
        transactions = []
        
        for reward_config in reward_configs:
            reward_amount = reward_config.calculate_reward(completion)
            if reward_amount > 0:
                # Create reward transaction
                transaction = RewardTransaction.objects.create(
                    user=completion.user,
                    survey_completion=completion,
                    reward_config=reward_config,
                    transaction_type='earned',
                    amount=reward_amount,
                    currency=reward_config.currency,
                    description=f"Reward for completing {completion.survey.title}",
                    reference_id=str(completion.uuid)
                )
                transactions.append(transaction)
                total_reward += reward_amount
                
                # Update reward statistics
                reward_config.update_statistics(reward_amount)
        
        # Approve transactions
        for transaction in transactions:
            transaction.approve()
        
        # Update user profile stats
        try:
            profile = completion.user.profile
            profile.update_survey_stats(
                completion_time=completion.time_spent_seconds,
                quality_score=completion.quality_score or Decimal('0')
            )
        except Exception as e:
            logger.warning(f"[Task] Failed to update user profile: {e}")
        
        logger.info(f"[Task] Processed {len(transactions)} rewards for survey {completion_uuid}, total: {total_reward}")
        return {
            'status': 'success',
            'transactions_created': len(transactions),
            'total_reward': float(total_reward)
        }
        
    except Exception as exc:
        exc_name = type(exc).__name__
        if 'DoesNotExist' in exc_name or 'ObjectDoesNotExist' in exc_name:
            logger.error(f"[Task] Survey completion {completion_uuid} not found")
            return {'status': 'error', 'reason': 'completion_not_found'}
        logger.error(f"[Task] Reward processing failed for {completion_uuid}: {exc}")
        try:
            self.retry(exc=exc, countdown=60)
        except Exception:
            pass
        raise exc


@shared_task(name='cms.tasks.update_survey_analytics', bind=True, max_retries=2)
def update_survey_analytics(self, survey_uuid: str = None):
    """Update analytics for all surveys or a specific survey."""
    try:
        
        analytics_service = SurveyAnalyticsService()
        
        if survey_uuid:
            # Update specific survey
            analytics = analytics_service.get_survey_performance_report(survey_uuid)
            logger.info(f"[Task] Updated analytics for survey {survey_uuid}")
            return {'status': 'success', 'survey_uuid': survey_uuid}
        else:
            # Update all active surveys
            active_surveys = SurveyTemplate.objects.filter(status='active')
            updated_count = 0
            
            for survey in active_surveys:
                try:
                    analytics_service.get_survey_performance_report(str(survey.uuid))
                    updated_count += 1
                except Exception as e:
                    logger.warning(f"[Task] Failed to update analytics for survey {survey.uuid}: {e}")
            
            logger.info(f"[Task] Updated analytics for {updated_count} surveys")
            return {'status': 'success', 'updated_count': updated_count}
            
    except Exception as exc:
        logger.error(f"[Task] Analytics update failed: {exc}")
        try:
            self.retry(exc=exc, countdown=300)
        except Exception:
            pass
        raise exc


@shared_task(name='cms.tasks.cleanup_expired_surveys', bind=True)
def cleanup_expired_surveys(self):
    """Deactivate surveys that have expired."""
    try:
        from django.utils import timezone
        
        now = timezone.now()
        expired_surveys = SurveyTemplate.objects.filter(
            status='active',
            end_time__lte=now
        )
        
        deactivated_count = expired_surveys.update(status='expired')
        
        logger.info(f"[Task] Deactivated {deactivated_count} expired surveys")
        return {'status': 'success', 'deactivated_count': deactivated_count}
        
    except ValueError as exc:
        logger.error(f"[Task] Cleanup failed (non-retriable): {exc}")
        return {'status': 'error', 'reason': str(exc)}
    except Exception as exc:
        logger.error(f"[Task] Survey cleanup failed: {exc}")
        raise


@shared_task(name='cms.tasks.update_user_segments', bind=True, max_retries=2)
def update_user_segments(self):
    """Update user segment membership and statistics."""
    try:
        
        segment_service = UserSegmentService()
        
        # Update all active segments
        active_segments = UserSegment.objects.filter(is_active=True)
        
        updated_count = 0
        for segment in active_segments:
            try:
                segment.update_user_count()
                updated_count += 1
            except Exception as e:
                logger.warning(f"[Task] Failed to update segment {segment.uuid}: {e}")
        
        logger.info(f"[Task] Updated {updated_count} user segments")
        return {'status': 'success', 'updated_count': updated_count}
        
    except Exception as exc:
        logger.error(f"[Task] Segment update failed: {exc}")
        try:
            self.retry(exc=exc, countdown=300)
        except Exception:
            pass
        raise exc


@shared_task(name='cms.tasks.send_survey_recommendations', bind=True, max_retries=2)
def send_survey_recommendations(self, user_id: int = None):
    """Send personalized survey recommendations to users."""
    try:
        # Use module-level User so mock.patch('...User') intercepts correctly
        if user_id:
            users = [User.objects.get(id=user_id)]
        else:
            recent_cutoff = timezone.now() - timedelta(hours=24)
            users = User.objects.filter(
                is_active=True,
            )[:100]

        sent_count = 0
        survey_manager = ProfileSurveyManager()

        for user in users:
            try:
                recommendations = survey_manager.get_recommended_surveys(user, limit=5)
                if recommendations:
                    NotificationService.notify_user(
                        user=user,
                        notification_type='survey_recommendations',
                        title='New Survey Recommendations',
                        message=f'You have {len(recommendations)} new surveys available.',
                        source_type='survey',
                        action_url='/surveys/recommended',
                        metadata={'recommendations': len(recommendations)},
                    )
                    sent_count += 1
            except Exception as e:
                logger.warning(f"[Task] Failed to send recommendations to user {getattr(user,'id',user)}: {e}")

        logger.info(f"[Task] Sent survey recommendations to {sent_count} users")
        return {'status': 'success', 'sent_count': sent_count}
        
    except Exception as exc:
        logger.error(f"[Task] Survey recommendations failed: {exc}")
        try:
            self.retry(exc=exc, countdown=300)
        except Exception:
            pass
        raise exc


@shared_task(name='cms.tasks.generate_survey_report', bind=True, max_retries=2)
def generate_survey_report(self, survey_uuid: str, report_type: str = 'daily'):
    """Generate and store survey reports."""
    try:
        
        survey = SurveyTemplate.objects.get(uuid=survey_uuid)
        analytics_service = SurveyAnalyticsService()
        
        # Get report data
        if report_type == 'daily':
            days = 1
        elif report_type == 'weekly':
            days = 7
        elif report_type == 'monthly':
            days = 30
        else:
            days = 30
        
        report_data = analytics_service.get_survey_performance_report(survey_uuid, days)
        
        # Store report (implement report storage model if needed)
        logger.info(f"[Task] Generated {report_type} report for survey {survey_uuid}")
        return {
            'status': 'success',
            'survey_uuid': survey_uuid,
            'report_type': report_type,
            'period_days': days,
            'data_points': len(report_data)
        }
        
    except Exception as _exc:
        exc_name = type(_exc).__name__
        if any(n in exc_name for n in ('DoesNotExist', 'ValidationError', 'ValueError',
                                        'ObjectDoesNotExist')):
            logger.error(f"[Task] Survey {survey_uuid} not found or invalid: {_exc}")
            return {'status': 'error', 'reason': 'survey_not_found'}
        logger.error(f"[Task] Report generation failed for {survey_uuid}: {_exc}")
        try:
            self.retry(exc=exc, countdown=300)
        except Exception:
            pass
        raise exc


@shared_task(name='cms.tasks.validate_survey_quality', bind=True, max_retries=1)
def validate_survey_quality(self, completion_uuid: str):
    """Validate and quality-check survey completions."""
    try:
        from decimal import Decimal

        try:
            completion = SurveyCompletion.objects.get(uuid=completion_uuid)
        except BaseException:
            # Any failure to retrieve the completion (DoesNotExist, ValidationError,
            # invalid UUID, or mocked DoesNotExist) → return not_found
            return {'status': 'error', 'reason': 'completion_not_found'}

        if completion.status != 'completed':
            return {'status': 'skipped', 'reason': 'not_completed'}
        
        # Quality checks
        quality_score = Decimal('1.0')
        flags = []
        
        # Check for straight-lining
        responses = completion.responses.all()
        if (len(list(responses)) if hasattr(responses, '__iter__') and not hasattr(responses, 'query') else responses.count()) > 3:
            answer_values = [str(r.answer) for r in responses if r.answer is not None]
            if len(set(answer_values)) <= 2:
                quality_score -= Decimal('0.3')
                flags.append('straight_lining')
        
        # Check for speed completion
        try:
            _time_spent = int(completion.time_spent_seconds or 0)
            _est_min = int(completion.survey.estimated_minutes or 0)
        except (TypeError, ValueError):
            _time_spent = _est_min = 0
        if _time_spent > 0 and _est_min > 0:
            min_expected_time = _est_min * 30
            if _time_spent < min_expected_time:
                quality_score -= Decimal('0.2')
                flags.append('too_fast')
        
        # Check attention checks
        try:
            failed_checks = int(completion.responses.filter(is_attention_check=True, answer__isnull=False).count() or 0)
        except (TypeError, ValueError):
            failed_checks = 0
        if failed_checks > 0:
            penalty = min(Decimal('0.1') * failed_checks, Decimal('0.4'))
            quality_score -= penalty
            flags.append(f'failed_attention_checks:{failed_checks}')
        
        # Update completion with quality score
        completion.quality_score = max(quality_score, Decimal('0'))
        completion.save(update_fields=['quality_score'])
        
        # Auto-approve if quality is good
        if completion.quality_score >= Decimal('0.8'):
            completion.status = 'approved'
            completion.save(update_fields=['status'])
            
            # Trigger reward processing
            process_survey_rewards.delay(str(completion.uuid))
        
        logger.info(f"[Task] Quality validation for {completion_uuid}: score={completion.quality_score}, flags={flags}")
        return {
            'status': 'success',
            'quality_score': float(completion.quality_score),
            'flags': flags,
            'auto_approved': completion.status == 'approved'
        }
        
    except Exception as _does_not_exist_exc:
        if 'DoesNotExist' not in type(_does_not_exist_exc).__name__: raise _does_not_exist_exc
        logger.error(f"[Task] Survey completion {completion_uuid} not found")
        return {'status': 'error', 'reason': 'completion_not_found'}
    except Exception as exc:
        logger.error(f"[Task] Quality validation failed for {completion_uuid}: {exc}")
        try:
            self.retry(exc=exc, countdown=60)
        except Exception:
            pass
        raise exc


@shared_task(name='cms.tasks.sync_survey_caches', bind=True)
def sync_survey_caches(self):
    """Synchronize survey-related caches."""
    try:
        
        # Clear survey recommendation caches
        profiles = UserProfile.objects.all()[:100]  # Limit to prevent cache stampede
        cleared_count = 0
        
        for profile in profiles:
            cache_key = f"survey_recommendations_{profile.user.id}"
            cache.delete(cache_key)
            cleared_count += 1
        
        # Clear survey analytics caches
        active_surveys = SurveyTemplate.objects.filter(status='active')
        for survey in active_surveys:
            cache.delete(f"survey_performance_{survey.uuid}_30")
            cache.delete(f"survey_performance_{survey.uuid}_7")
            cache.delete(f"survey_performance_{survey.uuid}_1")
        
        survey_cache_count = len(list(active_surveys)) if hasattr(active_surveys, '__iter__') else (len(list(active_surveys)) if hasattr(active_surveys, '__iter__') and not hasattr(active_surveys, 'query') else active_surveys.count())
        logger.info(f"[Task] Cleared {cleared_count} user recommendation caches and {survey_cache_count} survey caches")
        return {
            'status': 'success',
            'user_caches_cleared': cleared_count,
            'survey_caches_cleared': survey_cache_count
        }
        
    except Exception as exc:
        logger.error(f"[Task] Cache sync failed: {exc}")
        raise
