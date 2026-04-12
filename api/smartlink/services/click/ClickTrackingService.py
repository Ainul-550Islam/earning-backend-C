import logging
from django.utils import timezone
from ...models import Click, ClickMetadata, ClickSession
from ...choices import DeviceType, OSType, BrowserType
from .ClickDeduplicationService import ClickDeduplicationService
from .SubIDParserService import SubIDParserService

logger = logging.getLogger('smartlink.click_tracking')


class ClickTrackingService:
    """
    Record a click to the database after redirect.
    Called asynchronously via Celery task to not block the redirect response.
    """

    def __init__(self):
        self.dedup_service = ClickDeduplicationService()
        self.sub_id_parser = SubIDParserService()

    def record(self, smartlink_id: int, offer_id: int, context: dict) -> Click:
        """
        Create a Click record with all associated metadata.

        Args:
            smartlink_id: SmartLink PK
            offer_id: Offer PK (can be None for fallback clicks)
            context: full request context dict

        Returns:
            Click instance
        """
        from ...models import SmartLink
        try:
            smartlink = SmartLink.objects.get(pk=smartlink_id)
        except SmartLink.DoesNotExist:
            logger.error(f"ClickTrackingService: SmartLink#{smartlink_id} not found")
            return None

        ip = context.get('ip', '0.0.0.0')
        user_agent = context.get('user_agent', '')
        country = context.get('country', '')
        device_type = context.get('device_type', DeviceType.UNKNOWN)
        os_type = context.get('os', OSType.UNKNOWN)
        browser = context.get('browser', BrowserType.OTHER)

        # Check for duplicate
        is_unique = True
        if smartlink.enable_unique_click and offer_id:
            is_unique = not self.dedup_service.is_duplicate(
                ip=ip,
                user_agent=user_agent,
                offer_id=offer_id,
                smartlink_id=smartlink_id,
            )

        # Get or create session
        session = self._get_or_create_session(smartlink, ip, user_agent, country, device_type)

        # Create Click record
        click = Click.objects.create(
            smartlink=smartlink,
            offer_id=offer_id,
            session=session,
            ip=ip,
            country=country,
            region=context.get('region', ''),
            city=context.get('city', ''),
            user_agent=user_agent,
            device_type=device_type,
            os=os_type,
            browser=browser,
            is_unique=is_unique,
            is_fraud=context.get('is_fraud', False),
            is_bot=context.get('is_bot', False),
            fraud_score=context.get('fraud_score', 0),
            referrer=context.get('referrer', ''),
        )

        # Create metadata (sub params)
        sub_ids = self.sub_id_parser.parse(context)
        ClickMetadata.objects.create(
            click=click,
            sub1=sub_ids.get('sub1', ''),
            sub2=sub_ids.get('sub2', ''),
            sub3=sub_ids.get('sub3', ''),
            sub4=sub_ids.get('sub4', ''),
            sub5=sub_ids.get('sub5', ''),
            custom_params=sub_ids.get('custom', {}),
            referrer=context.get('referrer', ''),
            offer_url_final=context.get('final_url', ''),
        )

        # Record unique click dedup entry
        if is_unique and offer_id:
            self.dedup_service.mark_seen(
                ip=ip,
                user_agent=user_agent,
                offer_id=offer_id,
                smartlink_id=smartlink_id,
                click=click,
            )

        # Update SmartLink counters
        smartlink.increment_clicks(unique=is_unique)

        # Update session click count
        if session:
            ClickSession.objects.filter(pk=session.pk).update(
                click_count=session.click_count + 1,
                last_seen=timezone.now(),
            )

        logger.debug(
            f"Click recorded: sl={smartlink.slug} offer={offer_id} "
            f"country={country} device={device_type} unique={is_unique}"
        )
        return click

    def _get_or_create_session(self, smartlink, ip, user_agent, country, device_type):
        """Get existing session or create a new one for this visitor."""
        try:
            session, created = ClickSession.objects.get_or_create(
                smartlink=smartlink,
                ip=ip,
                defaults={
                    'user_agent': user_agent,
                    'country': country,
                    'device_type': device_type,
                    'click_count': 0,
                }
            )
            return session
        except Exception as e:
            logger.warning(f"Session create error: {e}")
            return None
