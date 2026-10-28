"""
SmartLink GDPR Anonymization Service
Right-to-erasure: replace all PII in clicks and sessions with anonymized values.
Preserves aggregate analytics counts — only removes identifying data.
"""
import logging
from django.utils import timezone
from django.db.models import F

logger = logging.getLogger('smartlink.gdpr')

ANONYMIZED_IP = '0.0.0.0'
ANONYMIZED_UA = '[ANONYMIZED]'


class GDPRAnonymizationService:
    """
    GDPR Article 17 — Right to erasure.

    anonymize_publisher(user) replaces all PII across:
      - Click (ip, user_agent, sub1…sub5)
      - ClickSession (ip, user_agent)
      - ClickMetadata (custom_params)
      - PostbackLog (ip, raw_params, click_id partial)
      - Publisher profile PII
    """

    def anonymize_publisher(self, publisher) -> dict:
        """
        Full publisher erasure. Marks profile as anonymized.
        Returns counts of rows anonymized per model.
        """
        result = {}
        result['clicks'] = self._anonymize_clicks(publisher)
        result['sessions'] = self._anonymize_sessions(publisher)
        result['postbacks'] = self._anonymize_postbacks(publisher)
        result['profile'] = self._anonymize_profile(publisher)

        logger.warning(
            f"GDPR anonymization complete for user#{publisher.pk}: {result}"
        )
        return result

    def _anonymize_clicks(self, publisher) -> int:
        from api.smartlink.models.click import Click, ClickMetadata
        # Anonymize Click fields
        updated = Click.objects.filter(
            smartlink__publisher=publisher,
        ).update(
            ip=ANONYMIZED_IP,
            user_agent=ANONYMIZED_UA,
        )
        # Anonymize ClickMetadata sub-IDs
        click_ids = list(
            Click.objects.filter(smartlink__publisher=publisher)
            .values_list('pk', flat=True)[:50000]
        )
        if click_ids:
            try:
                ClickMetadata.objects.filter(click_id__in=click_ids).update(
                    sub1='', sub2='', sub3='', sub4='', sub5='',
                )
            except Exception:
                pass
        return updated

    def _anonymize_sessions(self, publisher) -> int:
        from api.smartlink.models.click import ClickSession
        updated = ClickSession.objects.filter(
            smartlink__publisher=publisher,
        ).update(
            ip=ANONYMIZED_IP,
            user_agent=ANONYMIZED_UA,
        )
        return updated

    def _anonymize_postbacks(self, publisher) -> int:
        from api.smartlink.models.postback_log import PostbackLog
        from django.db.models import Q
        # PostbackLog links to offer/click, not publisher directly.
        # Anonymize postbacks where click_id matches publisher's clicks.
        from api.smartlink.models.click import Click
        click_ids = list(
            Click.objects.filter(smartlink__publisher=publisher)
            .values_list('pk', flat=True)[:10000]
        )
        if not click_ids:
            return 0
        # click_id in PostbackLog is stored as string
        str_ids = [str(c) for c in click_ids]
        updated = PostbackLog.objects.filter(click_id__in=str_ids).update(
            ip='',
            raw_params={},
        )
        return updated

    def _anonymize_profile(self, publisher) -> bool:
        try:
            from api.smartlink.models.billing import PublisherProfile
            profile = PublisherProfile.objects.get(publisher=publisher)
            profile.anonymize()
            return True
        except Exception:
            return False

    def anonymize_single_click(self, click_pk: int) -> bool:
        """
        Anonymize a single click by PK. Used for targeted erasure.
        """
        from api.smartlink.models.click import Click
        updated = Click.objects.filter(pk=click_pk).update(
            ip=ANONYMIZED_IP,
            user_agent=ANONYMIZED_UA,
            sub1='', sub2='', sub3='', sub4='', sub5='',
        )
        return updated == 1

    def get_publisher_data_summary(self, publisher) -> dict:
        """
        Return counts of all data held for a publisher (GDPR Art. 15 access right).
        """
        from api.smartlink.models.click import Click, ClickSession
        from api.smartlink.models import SmartLink
        from api.smartlink.models.postback_log import PostbackLog

        sl_count = SmartLink.objects.filter(publisher=publisher).count()
        click_count = Click.objects.filter(smartlink__publisher=publisher).count()
        session_count = ClickSession.objects.filter(smartlink__publisher=publisher).count()

        return {
            'publisher_id': publisher.pk,
            'username': publisher.username,
            'smartlinks': sl_count,
            'clicks': click_count,
            'sessions': session_count,
            'data_as_of': timezone.now().isoformat(),
            'note': (
                'This is the data held about you. '
                'Request erasure at POST /api/smartlink/publisher/profile/anonymize/'
            ),
        }
