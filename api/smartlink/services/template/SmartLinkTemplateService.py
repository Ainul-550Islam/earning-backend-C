"""
SmartLink Template Service
Create SmartLinks from templates with one click.
"""
import logging
from django.db import transaction

logger = logging.getLogger('smartlink.template')


class SmartLinkTemplateService:
    """Manage and apply SmartLink configuration templates."""

    def create_template_from_smartlink(self, smartlink, publisher, name: str,
                                        is_public: bool = False) -> object:
        """Save a SmartLink's full config as a reusable template."""
        from ...models.extensions.smartlink_schedule import SmartLinkTemplate

        config = self._extract_config(smartlink)
        template = SmartLinkTemplate.objects.create(
            publisher=publisher,
            name=name,
            description=f"Template from SmartLink [{smartlink.slug}]",
            is_public=is_public,
            config=config,
        )
        logger.info(f"Template created: '{name}' from [{smartlink.slug}]")
        return template

    @transaction.atomic
    def create_smartlink_from_template(self, template, publisher,
                                        override: dict = None) -> object:
        """Create a new SmartLink from a template."""
        from ...services.core.SmartLinkBuilderService import SmartLinkBuilderService

        config = dict(template.config)
        if override:
            config.update(override)

        # Remove slug — generate new one
        config.pop('slug', None)

        builder = SmartLinkBuilderService()
        sl = builder.build(publisher, config)

        # Increment template use count
        from ...models.extensions.smartlink_schedule import SmartLinkTemplate
        SmartLinkTemplate.objects.filter(pk=template.pk).update(
            use_count=template.use_count + 1
        )

        logger.info(f"SmartLink [{sl.slug}] created from template '{template.name}'")
        return sl

    def get_public_templates(self, category: str = None) -> list:
        """Get all public templates available to all publishers."""
        from ...models.extensions.smartlink_schedule import SmartLinkTemplate
        qs = SmartLinkTemplate.objects.filter(is_public=True).order_by('-use_count')
        if category:
            qs = qs.filter(config__type=category)
        return list(qs.values(
            'id', 'name', 'description', 'use_count',
            'config', 'created_at'
        ))

    def _extract_config(self, smartlink) -> dict:
        """Extract full SmartLink config for template storage."""
        config = {
            'name':            smartlink.name,
            'type':            smartlink.type,
            'redirect_type':   smartlink.redirect_type,
            'rotation_method': smartlink.rotation_method,
            'enable_ab_test':  smartlink.enable_ab_test,
            'enable_fraud_filter': smartlink.enable_fraud_filter,
            'enable_bot_filter':   smartlink.enable_bot_filter,
            'enable_unique_click': smartlink.enable_unique_click,
        }

        # Extract targeting
        try:
            rule = smartlink.targeting_rule
            targeting = {'logic': rule.logic}
            try:
                geo = rule.geo_targeting
                targeting['geo'] = {'mode': geo.mode, 'countries': geo.countries,
                                     'regions': geo.regions, 'cities': geo.cities}
            except Exception:
                pass
            try:
                dev = rule.device_targeting
                targeting['device'] = {'mode': dev.mode, 'device_types': dev.device_types}
            except Exception:
                pass
            try:
                t = rule.time_targeting
                targeting['time'] = {
                    'days_of_week': t.days_of_week,
                    'start_hour': t.start_hour,
                    'end_hour': t.end_hour,
                }
            except Exception:
                pass
            config['targeting'] = targeting
        except Exception:
            pass

        # Extract fallback
        try:
            config['fallback_url'] = smartlink.fallback.url
        except Exception:
            pass

        return config
