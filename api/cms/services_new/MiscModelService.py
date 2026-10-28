# api/cms/services_new/MiscModelService.py
"""
Service layer for models that had no service coverage:
  BannerReward, BlockDefinition, CommentReaction, ContentPermission,
  FormField, LandingPage, PermissionAuditLog, PermissionStats,
  QuizQuestion, SurveyQuestion, VideoGenerationRequest
"""
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger('api.cms.services')


# ══════════════════════════════════════════════════════════════════════════════
# BANNER REWARD SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class BannerRewardService:
    """Business logic for BannerReward lifecycle."""

    @staticmethod
    def process(reward_id: str) -> bool:
        """Mark a BannerReward as processed and credit the user's wallet."""
        from api.cms.models import BannerReward
        from api.cms.adapters import WalletAdapter, AuditAdapter
        from decimal import Decimal
        try:
            reward = BannerReward.objects.select_related('user').get(uuid=reward_id, is_processed=False)
            ok = WalletAdapter.credit(
                user=reward.user,
                amount_usd=Decimal(str(reward.amount)),
                source='banner_reward',
                ref_id=str(reward.uuid),
                description=f'Banner reward: {reward.reward_type}',
            )
            if ok:
                reward.is_processed = True
                reward.save(update_fields=['is_processed'])
                AuditAdapter.reward_issued(reward.user, float(reward.amount), 'banner_reward')
                logger.info("[BannerRewardService] Processed reward %s for user %s", reward_id, reward.user_id)
            return ok
        except BannerReward.DoesNotExist:
            logger.warning("[BannerRewardService] Reward %s not found or already processed.", reward_id)
            return False
        except Exception as e:
            logger.error("[BannerRewardService] process(%s) failed: %s", reward_id, e)
            return False

    @staticmethod
    def retry_failed(max_retries: int = 3) -> int:
        """Retry unprocessed rewards. Returns count successfully processed."""
        from api.cms.models import BannerReward
        failed = BannerReward.objects.filter(is_processed=False, retry_count__lt=max_retries, is_active=True)
        count = 0
        for reward in failed:
            success = BannerRewardService.process(str(reward.uuid))
            if not success:
                reward.retry_count = (reward.retry_count or 0) + 1
                reward.save(update_fields=['retry_count'])
            else:
                count += 1
        return count

    @staticmethod
    def get_user_rewards(user, processed: Optional[bool] = None) -> List:
        from api.cms.models import BannerReward
        qs = BannerReward.objects.filter(user=user).order_by('-created_at')
        if processed is not None:
            qs = qs.filter(is_processed=processed)
        return list(qs)


# ══════════════════════════════════════════════════════════════════════════════
# BLOCK DEFINITION SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class BlockDefinitionService:
    """Manage content block type definitions."""

    @staticmethod
    def get_active_blocks() -> List:
        from api.cms.models_new.blocks import BlockDefinition
        return list(BlockDefinition.objects.filter(is_active=True).order_by('order'))

    @staticmethod
    def get_schema(block_type: str) -> Dict:
        from api.cms.models_new.blocks import BlockDefinition
        block = BlockDefinition.objects.filter(block_type=block_type, is_active=True).first()
        return block.schema if block else {}

    @staticmethod
    def validate_block_data(block_type: str, data: Dict) -> bool:
        """Basic schema validation for a block's data payload."""
        schema = BlockDefinitionService.get_schema(block_type)
        if not schema:
            return True  # no schema = accept anything
        required_fields = schema.get('required', [])
        return all(field in data for field in required_fields)

    @staticmethod
    def reorder(block_type_order: List[str]) -> bool:
        """Reorder block definitions by providing an ordered list of block_types."""
        from api.cms.models_new.blocks import BlockDefinition
        try:
            for idx, block_type in enumerate(block_type_order):
                BlockDefinition.objects.filter(block_type=block_type).update(order=idx)
            return True
        except Exception as e:
            logger.error("[BlockDefinitionService] reorder failed: %s", e)
            return False


# ══════════════════════════════════════════════════════════════════════════════
# COMMENT REACTION SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class CommentReactionService:
    """Toggle/add reactions to comments."""

    @staticmethod
    def toggle(user, comment_id: int, reaction: str) -> Dict:
        """
        Toggle a reaction. If the user already has this reaction on the comment, remove it.
        Returns {'action': 'added'|'removed', 'reaction': str}
        """
        from api.cms.models_new.comments import CommentReaction
        try:
            existing = CommentReaction.objects.filter(
                user=user, comment_id=comment_id, reaction=reaction
            ).first()
            if existing:
                existing.delete()
                return {'action': 'removed', 'reaction': reaction}
            # Remove any OTHER reaction from this user on this comment first
            CommentReaction.objects.filter(user=user, comment_id=comment_id).delete()
            CommentReaction.objects.create(user=user, comment_id=comment_id, reaction=reaction)
            return {'action': 'added', 'reaction': reaction}
        except Exception as e:
            logger.error("[CommentReactionService] toggle failed: %s", e)
            return {'action': 'error', 'reaction': reaction}

    @staticmethod
    def get_counts(comment_id: int) -> Dict[str, int]:
        """Return reaction counts for a comment."""
        from api.cms.models_new.comments import CommentReaction
        from django.db.models import Count
        counts = (
            CommentReaction.objects.filter(comment_id=comment_id)
            .values('reaction')
            .annotate(count=Count('id'))
        )
        return {row['reaction']: row['count'] for row in counts}


# ══════════════════════════════════════════════════════════════════════════════
# CONTENT PERMISSION SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class ContentPermissionService:
    """Fine-grained content permission checks."""

    @staticmethod
    def has_permission(user, content_id: str, permission: str) -> bool:
        from api.cms.models import ContentPermission
        try:
            perm = ContentPermission.objects.filter(
                content__uuid=content_id, is_active=True
            ).first()
            if not perm:
                return user.is_staff  # default: only staff if no explicit perm
            allowed = perm.permissions or []
            return permission in allowed or user.is_staff
        except Exception as e:
            logger.warning("[ContentPermissionService] has_permission failed: %s", e)
            return user.is_staff

    @staticmethod
    def grant(content_id: str, target_id: str, permissions: List[str]) -> bool:
        from api.cms.models import ContentPermission, ContentPage
        try:
            content = ContentPage.objects.filter(uuid=content_id).first()
            if not content:
                return False
            perm, _ = ContentPermission.objects.get_or_create(
                content=content, target_id=target_id,
                defaults={'permissions': permissions, 'is_active': True}
            )
            perm.permissions = permissions
            perm.is_active = True
            perm.save(update_fields=['permissions', 'is_active'])
            return True
        except Exception as e:
            logger.error("[ContentPermissionService] grant failed: %s", e)
            return False

    @staticmethod
    def revoke(content_id: str, target_id: str) -> bool:
        from api.cms.models import ContentPermission
        try:
            ContentPermission.objects.filter(
                content__uuid=content_id, target_id=target_id
            ).update(is_active=False)
            return True
        except Exception as e:
            logger.error("[ContentPermissionService] revoke failed: %s", e)
            return False


# ══════════════════════════════════════════════════════════════════════════════
# FORM FIELD SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class FormFieldService:
    """Manage form field definitions."""

    @staticmethod
    def get_fields_for_form(form_id: int) -> List:
        from api.cms.models_new.forms import FormField
        return list(FormField.objects.filter(form_id=form_id).order_by('order'))

    @staticmethod
    def validate_submission(form_id: int, data: Dict) -> Dict:
        """Validate submitted data against form field definitions."""
        fields = FormFieldService.get_fields_for_form(form_id)
        errors = {}
        for field in fields:
            value = data.get(field.name)
            if field.is_required and not value:
                errors[field.name] = f'{field.label} is required.'
        return errors

    @staticmethod
    def reorder(form_id: int, field_ids: List[int]) -> bool:
        from api.cms.models_new.forms import FormField
        try:
            for idx, fid in enumerate(field_ids):
                FormField.objects.filter(id=fid, form_id=form_id).update(order=idx)
            return True
        except Exception as e:
            logger.error("[FormFieldService] reorder failed: %s", e)
            return False


# ══════════════════════════════════════════════════════════════════════════════
# LANDING PAGE SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class LandingPageService:
    """Business logic for LandingPage and LandingSection models."""

    @staticmethod
    def get_published(slug: str = '') -> Optional[Any]:
        from api.cms.models import LandingPage
        try:
            qs = LandingPage.objects.filter(is_active=True)
            if slug:
                return qs.get(slug=slug)
            return qs.first()
        except Exception:
            return None

    @staticmethod
    def publish(landing_page_id: int, user=None) -> bool:
        from api.cms.models import LandingPage
        from api.cms.adapters import AuditAdapter, AnalyticsAdapter
        try:
            page = LandingPage.objects.get(pk=landing_page_id)
            page.is_active = True
            page.save(update_fields=['is_active'])
            if user:
                AuditAdapter.content_published(user, 'landing_page', str(landing_page_id))
                AnalyticsAdapter.content_published(user, 'landing_page', str(landing_page_id))
            return True
        except Exception as e:
            logger.error("[LandingPageService] publish failed: %s", e)
            return False


# ══════════════════════════════════════════════════════════════════════════════
# PERMISSION AUDIT / STATS SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class PermissionAuditService:
    """Manage permission audit logs and stats."""

    @staticmethod
    def log(action: str, user_id: int, username: str, content_id: str,
            ip_address: str = '', extra: Dict = None) -> bool:
        from api.cms.models import PermissionAuditLog
        try:
            PermissionAuditLog.objects.create(
                action=action, user_id=user_id, username=username,
                content_id=content_id, ip_address=ip_address,
            )
            return True
        except Exception as e:
            logger.error("[PermissionAuditService] log failed: %s", e)
            return False

    @staticmethod
    def get_recent(content_id: str = '', limit: int = 50) -> List:
        from api.cms.models import PermissionAuditLog
        qs = PermissionAuditLog.objects.order_by('-created_at')
        if content_id:
            qs = qs.filter(content_id=content_id)
        return list(qs[:limit])

    @staticmethod
    def record_stats(content_id: str, cache_hit: bool = False, response_ms: float = 0) -> None:
        from api.cms.models import PermissionStats
        from django.utils import timezone
        today = timezone.now().date()
        stats, _ = PermissionStats.objects.get_or_create(date=today, content_id=content_id)
        stats.check_count = (stats.check_count or 0) + 1
        if cache_hit:
            stats.cache_hits = (stats.cache_hits or 0) + 1
        else:
            stats.cache_misses = (stats.cache_misses or 0) + 1
        if response_ms:
            current_avg = stats.avg_response_time or 0
            stats.avg_response_time = (current_avg + response_ms) / 2
        stats.save()


# ══════════════════════════════════════════════════════════════════════════════
# QUIZ QUESTION SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class QuizQuestionService:
    """Manage quiz questions and answer scoring."""

    @staticmethod
    def get_for_quiz(quiz_id: int) -> List:
        from api.cms.models_new.quiz import QuizQuestion
        return list(QuizQuestion.objects.filter(quiz_id=quiz_id).prefetch_related('answers').order_by('order'))

    @staticmethod
    def score_answer(question_id: int, answer_id: int) -> float:
        from api.cms.models_new.quiz import QuizAnswer
        try:
            answer = QuizAnswer.objects.get(id=answer_id, question_id=question_id)
            return float(answer.score_weight or 0)
        except Exception:
            return 0.0

    @staticmethod
    def calculate_attempt_score(attempt_data: Dict) -> float:
        """Calculate total score for an attempt given answers_data dict {question_id: answer_id}."""
        total = 0.0
        for q_id, a_id in attempt_data.items():
            total += QuizQuestionService.score_answer(int(q_id), int(a_id))
        return total

    @staticmethod
    def get_result(quiz_id: int, score: float):
        from api.cms.models_new.quiz import QuizResult
        result = QuizResult.objects.filter(
            quiz_id=quiz_id, min_score__lte=score, max_score__gte=score
        ).first()
        return result


# ══════════════════════════════════════════════════════════════════════════════
# SURVEY QUESTION SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class SurveyQuestionService:
    """Manage profile survey questions."""

    @staticmethod
    def get_for_survey(survey_id: int) -> List:
        from api.cms.models_new.profile_surveys import SurveyQuestion
        return list(SurveyQuestion.objects.filter(survey_id=survey_id).order_by('order'))

    @staticmethod
    def validate_response(question_id: str, answer: Any) -> bool:
        from api.cms.models_new.profile_surveys import SurveyQuestion
        try:
            q = SurveyQuestion.objects.get(uuid=question_id)
            if q.is_required and not answer:
                return False
            if q.question_type in ('single_choice', 'multiple_choice') and q.choices:
                choices = q.choices if isinstance(q.choices, list) else []
                if isinstance(answer, list):
                    return all(a in choices for a in answer)
                return answer in choices
            return True
        except Exception:
            return True


# ══════════════════════════════════════════════════════════════════════════════
# VIDEO GENERATION REQUEST SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class VideoGenerationService:
    """Submit and track AI video generation requests."""

    @staticmethod
    def submit(video_id: int, request_data: Dict) -> Optional[Any]:
        from api.cms.models_new.video import VideoGenerationRequest
        from django.utils import timezone
        try:
            req = VideoGenerationRequest.objects.create(
                video_id=video_id,
                request_data=request_data,
                status='pending',
                started_at=timezone.now(),
            )
            logger.info("[VideoGenerationService] Submitted request %s for video %s", req.pk, video_id)
            return req
        except Exception as e:
            logger.error("[VideoGenerationService] submit failed: %s", e)
            return None

    @staticmethod
    def mark_completed(request_id: int, response_data: Dict) -> bool:
        from api.cms.models_new.video import VideoGenerationRequest
        from django.utils import timezone
        try:
            req = VideoGenerationRequest.objects.get(pk=request_id)
            req.status = 'completed'
            req.response_data = response_data
            req.completed_at = timezone.now()
            req.save(update_fields=['status', 'response_data', 'completed_at'])
            return True
        except Exception as e:
            logger.error("[VideoGenerationService] mark_completed failed: %s", e)
            return False

    @staticmethod
    def mark_failed(request_id: int, error_message: str) -> bool:
        from api.cms.models_new.video import VideoGenerationRequest
        try:
            VideoGenerationRequest.objects.filter(pk=request_id).update(
                status='failed', error_message=error_message
            )
            return True
        except Exception as e:
            logger.error("[VideoGenerationService] mark_failed failed: %s", e)
            return False

    @staticmethod
    def get_pending() -> List:
        from api.cms.models_new.video import VideoGenerationRequest
        return list(VideoGenerationRequest.objects.filter(status='pending').order_by('created_at'))


# ══════════════════════════════════════════════════════════════════════════════
# API KEY SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class APIKeyService:
    """Manage CMS API keys for external integrations."""

    @staticmethod
    def generate(user, name: str, scopes: list = None) -> "APIKey":
        import secrets
        from api.cms.models import APIKey
        key = secrets.token_urlsafe(40)
        return APIKey.objects.create(
            user=user, name=name, key=key, scopes=scopes or [],
        )

    @staticmethod
    def validate(raw_key: str) -> bool:
        from api.cms.models import APIKey
        return APIKey.objects.filter(key=raw_key, is_active=True).exists()

    @staticmethod
    def revoke(key_id: int) -> bool:
        from api.cms.models import APIKey
        try:
            APIKey.objects.filter(pk=key_id).update(is_active=False)
            return True
        except Exception as e:
            logger.error("[APIKeyService] revoke failed: %s", e)
            return False

    @staticmethod
    def get_user_keys(user) -> list:
        from api.cms.models import APIKey
        return list(APIKey.objects.filter(user=user).order_by('-created_at'))


# ══════════════════════════════════════════════════════════════════════════════
# USER SESSION SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class UserSessionService:
    """Track CMS user sessions for analytics and security."""

    @staticmethod
    def start(user, session_key: str, ip: str = '', user_agent: str = '') -> "UserSession":
        from api.cms.models import UserSession
        from django.utils import timezone
        session, created = UserSession.objects.get_or_create(
            user=user, session_key=session_key,
            defaults={"ip_address": ip, "user_agent": user_agent, "started_at": timezone.now()},
        )
        return session

    @staticmethod
    def end(session_key: str) -> bool:
        from api.cms.models import UserSession
        from django.utils import timezone
        try:
            UserSession.objects.filter(session_key=session_key, ended_at__isnull=True).update(
                ended_at=timezone.now()
            )
            return True
        except Exception as e:
            logger.error("[UserSessionService] end failed: %s", e)
            return False

    @staticmethod
    def get_active_sessions(user) -> list:
        from api.cms.models import UserSession
        return list(UserSession.objects.filter(user=user, ended_at__isnull=True).order_by('-started_at'))
