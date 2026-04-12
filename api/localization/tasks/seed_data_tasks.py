# tasks/seed_data_tasks.py
"""Celery tasks for seeding initial data"""
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(name='localization.seed_data_tasks.seed_all_data')
    def seed_all_data():
        """Full system seed — languages, countries, currencies, timezones, translation keys"""
        try:
            from django.core.management import call_command
            results = {}
            for cmd in ['seed_languages', 'seed_countries', 'seed_currencies',
                       'seed_timezones', 'seed_translation_keys']:
                try:
                    call_command(cmd)
                    results[cmd] = 'success'
                    logger.info(f"Seeded: {cmd}")
                except Exception as e:
                    results[cmd] = f'failed: {e}'
                    logger.error(f"Seed {cmd} failed: {e}")
            return {'success': True, 'results': results}
        except Exception as e:
            logger.error(f"seed_all_data failed: {e}")
            return {'success': False, 'error': str(e)}

    @shared_task(name='localization.seed_data_tasks.seed_translation_keys_task')
    def seed_translation_keys_task():
        """CPAlead translation keys seed করে"""
        try:
            from django.core.management import call_command
            call_command('seed_translation_keys')
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @shared_task(name='localization.seed_data_tasks.seed_plural_rules')
    def seed_plural_rules():
        """All active languages-এর CLDR plural rules DB-তে save করে"""
        try:
            from ..models.core import Language
            from ..utils.plural import get_plural_forms_for_locale, get_cldr_info
            updated = 0
            for lang in Language.objects.filter(is_active=True):
                try:
                    forms = get_plural_forms_for_locale(lang.code)
                    lang.plural_forms = len(forms)
                    lang.save(update_fields=['plural_forms'])
                    updated += 1
                except Exception:
                    pass
            logger.info(f"Plural rules seeded for {updated} languages")
            return {'success': True, 'updated': updated}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @shared_task(name='localization.seed_data_tasks.seed_number_formats')
    def seed_number_formats():
        """Core language number formats seed করে"""
        try:
            from ..models.core import Language
            from ..models.settings import NumberFormat
            FORMAT_DATA = {
                'en': {'decimal_symbol': '.', 'grouping_symbol': ',', 'grouping_size': 3},
                'bn': {'decimal_symbol': '.', 'grouping_symbol': ',', 'grouping_size': 3,
                       'secondary_grouping': 2, 'native_digits': '০১২৩৪৫৬৭৮৯'},
                'hi': {'decimal_symbol': '.', 'grouping_symbol': ',', 'grouping_size': 3,
                       'secondary_grouping': 2, 'native_digits': '०१२३४५६७८९'},
                'ar': {'decimal_symbol': '.', 'grouping_symbol': ',', 'grouping_size': 3,
                       'native_digits': '٠١٢٣٤٥٦٧٨٩', 'number_system': 'arab'},
                'de': {'decimal_symbol': ',', 'grouping_symbol': '.', 'grouping_size': 3},
                'fr': {'decimal_symbol': ',', 'grouping_symbol': ' ', 'grouping_size': 3},
                'zh': {'decimal_symbol': '.', 'grouping_symbol': ',', 'grouping_size': 3},
            }
            created = 0
            for lang_code, fmt_data in FORMAT_DATA.items():
                lang = Language.objects.filter(code=lang_code).first()
                if lang:
                    _, was_created = NumberFormat.objects.get_or_create(
                        language=lang, country=None, defaults=fmt_data
                    )
                    if was_created:
                        created += 1
            return {'success': True, 'created': created}
        except Exception as e:
            return {'success': False, 'error': str(e)}

except ImportError:
    logger.warning("Celery not installed — seed tasks disabled")
