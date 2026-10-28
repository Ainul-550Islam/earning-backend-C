# api/cms/services_new/VideoContentService.py
"""Video Content Service — CPAlead AI video integration. CMS owns this."""
import logging
from typing import Dict, Any, Optional, List
from django.utils import timezone

logger = logging.getLogger(__name__)


class VideoContentService:

    @staticmethod
    def create_video(topic: str, platform: str = 'youtube_shorts',
                      style: str = 'story', user=None,
                      smartlink_id: int = None,
                      use_ai: bool = True) -> Dict[str, Any]:
        """Create video content, optionally generating script with AI."""
        from api.cms.models_new.video import VideoContent
        import re
        slug = re.sub(r'[^a-z0-9\-]', '-', topic.lower())[:80]
        base = slug; i = 1
        while VideoContent.objects.filter(slug=slug).exists():
            slug = f"{base}-{i}"; i += 1

        video = VideoContent.objects.create(
            title=f"{style.replace('_',' ').title()}: {topic}",
            slug=slug,
            topic=topic,
            platform=platform,
            video_style=style,
            status='draft',
            ai_generated=use_ai,
            created_by=user,
        )

        if smartlink_id:
            from api.cms.models_new.smartlink import SmartLink
            try:
                sl = SmartLink.objects.get(id=smartlink_id, is_active=True)
                video.cpalead_smartlink = sl
                video.save(update_fields=['cpalead_smartlink'])
            except SmartLink.DoesNotExist:
                pass

        if use_ai:
            script = VideoContentService._generate_script(topic, platform, style)
            if script:
                video.script = script
                video.status = 'ready'
                video.ai_credits_used = 1
                video.save(update_fields=['script', 'status', 'ai_credits_used'])

        return {
            'id': video.id,
            'uuid': str(video.uuid),
            'title': video.title,
            'platform': video.platform,
            'status': video.status,
            'script': video.script,
        }

    @staticmethod
    def _generate_script(topic: str, platform: str, style: str) -> Optional[str]:
        """Generate video script using AI."""
        try:
            from api.cms.openai import CMSAIService
            client = CMSAIService._get_client()
            if not client:
                return VideoContentService._fallback_script(topic, platform, style)

            duration = {'youtube_shorts': 60, 'tiktok': 30, 'instagram_reel': 30}.get(platform, 60)
            prompt = (
                f"Write a {duration}-second {style} video script about: '{topic}'\n"
                f"Platform: {platform}\n"
                f"Format: Hook (5s) → Main content → CTA to check link in bio.\n"
                f"Keep it engaging, punchy, and viral-ready. Max 200 words."
            )
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"[VideoContent] AI script generation failed: {e}")
            return VideoContentService._fallback_script(topic, platform, style)

    @staticmethod
    def _fallback_script(topic: str, platform: str, style: str) -> str:
        return (
            f"🔥 {topic} — You won't believe this!\n\n"
            f"[Hook: Start with surprising fact about {topic}]\n\n"
            f"[Main: Share {style} content about {topic}]\n\n"
            f"💰 Want to earn from this? Check the link in my bio!\n"
            f"Complete a quick offer and get rewarded instantly! 🎯"
        )

    @staticmethod
    def list_videos(user=None, platform: str = None, status: str = None,
                     limit: int = 20) -> List[Dict]:
        from api.cms.models_new.video import VideoContent
        qs = VideoContent.objects.all()
        if user:
            qs = qs.filter(created_by=user)
        if platform:
            qs = qs.filter(platform=platform)
        if status:
            qs = qs.filter(status=status)
        return [{
            'id': v.id, 'uuid': str(v.uuid), 'title': v.title,
            'platform': v.platform, 'status': v.status,
            'ctr': v.ctr, 'conversions': v.conversions,
            'revenue_usd': float(v.revenue_usd),
            'views_count': v.views_count,
            'created_at': v.created_at.isoformat(),
        } for v in qs.order_by('-created_at')[:limit]]

    @staticmethod
    def publish_video(video_id: int, video_url: str = '',
                       thumbnail_url: str = '') -> Dict:
        from api.cms.models_new.video import VideoContent
        try:
            video = VideoContent.objects.get(id=video_id)
            video.status = 'published'
            video.published_at = timezone.now()
            if video_url:
                video.video_url = video_url
            if thumbnail_url:
                video.thumbnail_url = thumbnail_url
            video.save(update_fields=['status', 'published_at', 'video_url',
                                       'thumbnail_url', 'updated_at'])
            return {'success': True, 'status': 'published'}
        except VideoContent.DoesNotExist:
            return {'success': False, 'error': 'Video not found'}

    @staticmethod
    def get_analytics(video_id: int) -> Dict:
        from api.cms.models_new.video import VideoContent
        try:
            v = VideoContent.objects.get(id=video_id)
            return {
                'views': v.views_count, 'clicks': v.clicks_count,
                'conversions': v.conversions, 'ctr': v.ctr,
                'conversion_rate': v.conversion_rate,
                'revenue_usd': float(v.revenue_usd),
                'platform': v.platform, 'status': v.status,
            }
        except VideoContent.DoesNotExist:
            return {}
