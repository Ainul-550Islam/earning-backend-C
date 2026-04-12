# tasks/seed_tasks.py
"""Celery task: seed countries/currencies/timezones from ISO data"""
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(name='localization.seed_tasks.seed_all')
    def seed_all():
        """Countries, currencies, timezones seed করে"""
        results = {}
        try:
            from .seed_languages import seed_languages_task
            results['languages'] = seed_languages_task()
        except Exception as e:
            results['languages'] = {'error': str(e)}
        logger.info(f"Seed completed: {results}")
        return {'success': True, 'results': results}

    @shared_task(name='localization.seed_tasks.seed_languages_task')
    def seed_languages_task():
        """50+ languages seed করে"""
        try:
            from ..models.core import Language
            languages = [
                {'code': 'en', 'name': 'English', 'name_native': 'English', 'is_default': True, 'flag_emoji': '🇺🇸'},
                {'code': 'bn', 'name': 'Bengali', 'name_native': 'বাংলা', 'is_rtl': False, 'flag_emoji': '🇧🇩'},
                {'code': 'hi', 'name': 'Hindi', 'name_native': 'हिन्दी', 'flag_emoji': '🇮🇳'},
                {'code': 'ar', 'name': 'Arabic', 'name_native': 'العربية', 'is_rtl': True, 'flag_emoji': '🇸🇦'},
                {'code': 'es', 'name': 'Spanish', 'name_native': 'Español', 'flag_emoji': '🇪🇸'},
                {'code': 'fr', 'name': 'French', 'name_native': 'Français', 'flag_emoji': '🇫🇷'},
                {'code': 'de', 'name': 'German', 'name_native': 'Deutsch', 'flag_emoji': '🇩🇪'},
                {'code': 'zh', 'name': 'Chinese', 'name_native': '中文', 'flag_emoji': '🇨🇳'},
                {'code': 'ja', 'name': 'Japanese', 'name_native': '日本語', 'flag_emoji': '🇯🇵'},
                {'code': 'ko', 'name': 'Korean', 'name_native': '한국어', 'flag_emoji': '🇰🇷'},
                {'code': 'pt', 'name': 'Portuguese', 'name_native': 'Português', 'flag_emoji': '🇵🇹'},
                {'code': 'ru', 'name': 'Russian', 'name_native': 'Русский', 'flag_emoji': '🇷🇺'},
                {'code': 'tr', 'name': 'Turkish', 'name_native': 'Türkçe', 'flag_emoji': '🇹🇷'},
                {'code': 'vi', 'name': 'Vietnamese', 'name_native': 'Tiếng Việt', 'flag_emoji': '🇻🇳'},
                {'code': 'id', 'name': 'Indonesian', 'name_native': 'Bahasa Indonesia', 'flag_emoji': '🇮🇩'},
                {'code': 'ms', 'name': 'Malay', 'name_native': 'Bahasa Melayu', 'flag_emoji': '🇲🇾'},
                {'code': 'ur', 'name': 'Urdu', 'name_native': 'اردو', 'is_rtl': True, 'flag_emoji': '🇵🇰'},
                {'code': 'fa', 'name': 'Persian', 'name_native': 'فارسی', 'is_rtl': True, 'flag_emoji': '🇮🇷'},
                {'code': 'ta', 'name': 'Tamil', 'name_native': 'தமிழ்', 'flag_emoji': '🇮🇳'},
                {'code': 'ne', 'name': 'Nepali', 'name_native': 'नेपाली', 'flag_emoji': '🇳🇵'},
                {'code': 'si', 'name': 'Sinhala', 'name_native': 'සිංහල', 'flag_emoji': '🇱🇰'},
            ]
            created = 0
            for lang_data in languages:
                _, was_created = Language.objects.get_or_create(
                    code=lang_data['code'],
                    defaults=lang_data
                )
                if was_created:
                    created += 1
            return {'created': created, 'total': len(languages)}
        except Exception as e:
            logger.error(f"seed_languages_task failed: {e}")
            return {'error': str(e)}

except ImportError:
    pass
