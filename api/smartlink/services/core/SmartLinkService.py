import logging
from django.db import transaction
from django.utils import timezone
from ...models import SmartLink, SmartLinkGroup, SmartLinkTag, SmartLinkTagging
from ...exceptions import SlugConflict, SlugReserved, PublisherLimitExceeded
from ...constants import SLUG_RESERVED_WORDS, MAX_SMARTLINKS_PER_PUBLISHER
from .SlugGeneratorService import SlugGeneratorService

logger = logging.getLogger('smartlink.service')


class SmartLinkService:
    """
    Core CRUD service for SmartLinks.
    Handles creation, updating, archiving, and validation.
    """

    def __init__(self):
        self.slug_service = SlugGeneratorService()

    @transaction.atomic
    def create(self, publisher, data: dict) -> SmartLink:
        """
        Create a new SmartLink with all associated config.
        Validates publisher limits, slug uniqueness, and reserved words.
        """
        # Check publisher limit
        count = SmartLink.objects.filter(publisher=publisher, is_archived=False).count()
        if count >= MAX_SMARTLINKS_PER_PUBLISHER:
            raise PublisherLimitExceeded(
                f"Publisher has reached the maximum of {MAX_SMARTLINKS_PER_PUBLISHER} SmartLinks."
            )

        # Resolve slug
        slug = data.get('slug')
        if slug:
            self._validate_slug_available(slug)
        else:
            slug = self.slug_service.generate_unique()

        # Create SmartLink
        smartlink = SmartLink.objects.create(
            publisher=publisher,
            slug=slug,
            name=data.get('name', f'SmartLink {slug}'),
            description=data.get('description', ''),
            type=data.get('type', 'general'),
            redirect_type=data.get('redirect_type', '302'),
            rotation_method=data.get('rotation_method', 'weighted'),
            is_active=data.get('is_active', True),
            enable_ab_test=data.get('enable_ab_test', False),
            enable_fraud_filter=data.get('enable_fraud_filter', True),
            enable_bot_filter=data.get('enable_bot_filter', True),
            enable_unique_click=data.get('enable_unique_click', True),
            notes=data.get('notes', ''),
        )

        # Assign group if provided
        group_id = data.get('group_id')
        if group_id:
            try:
                group = SmartLinkGroup.objects.get(pk=group_id, publisher=publisher)
                smartlink.group = group
                smartlink.save(update_fields=['group'])
            except SmartLinkGroup.DoesNotExist:
                pass

        # Assign tags
        tag_names = data.get('tags', [])
        if tag_names:
            self._apply_tags(smartlink, tag_names)

        logger.info(f"SmartLink created: [{slug}] by publisher#{publisher.pk}")
        return smartlink

    @transaction.atomic
    def update(self, smartlink: SmartLink, data: dict, publisher=None) -> SmartLink:
        """Update SmartLink fields. Slug changes are validated for uniqueness."""
        new_slug = data.get('slug')
        if new_slug and new_slug != smartlink.slug:
            self._validate_slug_available(new_slug)
            smartlink.slug = new_slug

        updatable_fields = [
            'name', 'description', 'type', 'redirect_type', 'rotation_method',
            'is_active', 'enable_ab_test', 'enable_fraud_filter',
            'enable_bot_filter', 'enable_unique_click', 'notes',
        ]
        changed = []
        for field in updatable_fields:
            if field in data:
                setattr(smartlink, field, data[field])
                changed.append(field)

        if changed:
            smartlink.save(update_fields=changed + ['updated_at'])

        # Update tags if provided
        if 'tags' in data:
            self._apply_tags(smartlink, data['tags'])

        logger.info(f"SmartLink updated: [{smartlink.slug}] fields={changed}")
        return smartlink

    def archive(self, smartlink: SmartLink) -> SmartLink:
        """Soft-delete: archive the SmartLink."""
        smartlink.is_active = False
        smartlink.is_archived = True
        smartlink.save(update_fields=['is_active', 'is_archived', 'updated_at'])
        logger.info(f"SmartLink archived: [{smartlink.slug}]")
        return smartlink

    def restore(self, smartlink: SmartLink) -> SmartLink:
        """Restore an archived SmartLink."""
        smartlink.is_archived = False
        smartlink.is_active = True
        smartlink.save(update_fields=['is_active', 'is_archived', 'updated_at'])
        logger.info(f"SmartLink restored: [{smartlink.slug}]")
        return smartlink

    def duplicate(self, smartlink: SmartLink, publisher=None) -> SmartLink:
        """Duplicate a SmartLink with a new slug."""
        new_slug = self.slug_service.generate_unique()
        target_publisher = publisher or smartlink.publisher
        data = {
            'name': f"Copy of {smartlink.name}",
            'description': smartlink.description,
            'type': smartlink.type,
            'redirect_type': smartlink.redirect_type,
            'rotation_method': smartlink.rotation_method,
            'enable_fraud_filter': smartlink.enable_fraud_filter,
            'enable_bot_filter': smartlink.enable_bot_filter,
            'enable_unique_click': smartlink.enable_unique_click,
        }
        return self.create(target_publisher, {**data, 'slug': new_slug})

    def get_for_publisher(self, publisher, filters: dict = None):
        """Return queryset of SmartLinks for a publisher."""
        qs = SmartLink.objects.filter(
            publisher=publisher,
            is_archived=False,
        ).select_related('group').prefetch_related('tags')

        if filters:
            if filters.get('is_active') is not None:
                qs = qs.filter(is_active=filters['is_active'])
            if filters.get('group_id'):
                qs = qs.filter(group_id=filters['group_id'])
            if filters.get('type'):
                qs = qs.filter(type=filters['type'])
            if filters.get('search'):
                from django.db.models import Q
                q = filters['search']
                qs = qs.filter(Q(slug__icontains=q) | Q(name__icontains=q))

        return qs.order_by('-created_at')

    def update_click_timestamp(self, smartlink: SmartLink):
        """Update last_click_at field (called on each redirect)."""
        SmartLink.objects.filter(pk=smartlink.pk).update(last_click_at=timezone.now())

    # ──────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────

    def _validate_slug_available(self, slug: str):
        if slug.lower() in SLUG_RESERVED_WORDS:
            raise SlugReserved(f'"{slug}" is reserved.')
        if SmartLink.objects.filter(slug=slug).exists():
            raise SlugConflict(f'Slug "{slug}" is already in use.')

    def _apply_tags(self, smartlink: SmartLink, tag_names: list):
        """Set tags on a SmartLink (replaces existing tags)."""
        SmartLinkTagging.objects.filter(smartlink=smartlink).delete()
        for name in tag_names:
            tag, _ = SmartLinkTag.objects.get_or_create(name=name.strip().lower())
            SmartLinkTagging.objects.get_or_create(smartlink=smartlink, tag=tag)
