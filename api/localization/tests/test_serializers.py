# tests/test_serializers.py
from django.test import TestCase
from .factories import make_language, make_country, make_currency


class LanguageSerializerTest(TestCase):
    def test_language_serializer(self):
        lang = make_language(code='te-ser', name='Serializer Test', is_default=False)
        from localization.serializers.language import LanguageSerializer
        serializer = LanguageSerializer(lang)
        data = serializer.data
        self.assertEqual(data['code'], 'te-ser')
        self.assertIn('name', data)


class CountrySerializerTest(TestCase):
    def test_country_serializer(self):
        country = make_country(code='TS', name='Ser Country', phone_code='+111')
        from localization.serializers.country import CountrySerializer
        serializer = CountrySerializer(country)
        data = serializer.data
        self.assertEqual(data['code'], 'TS')
