# tests/test_performance.py
"""Performance smoke tests — ensure queries are not excessive"""
from django.test import TestCase
from django.test.utils import override_settings
from .factories import make_language, make_translation_key, make_translation


class PerformanceTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='te-perf', name='Perf Test', is_default=False)
        for i in range(100):
            key = make_translation_key(key=f'perf.key.{i}', category='performance')
            make_translation(key=key, language=self.lang, value=f'Perf Value {i}')

    def test_bulk_translation_query_count(self):
        from localization.models.core import Translation
        from django.db import connection, reset_queries
        with override_settings(DEBUG=True):
            reset_queries()
            translations = list(
                Translation.objects.filter(
                    language=self.lang, is_approved=True
                ).select_related('key').only('key__key', 'value')
            )
            query_count = len(connection.queries)
        self.assertLessEqual(query_count, 5, f"Too many queries: {query_count}")
        self.assertEqual(len(translations), 100)
