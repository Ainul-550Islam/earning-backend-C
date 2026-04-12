from django.test import TestCase
from .factories import SmartLinkFactory, UserFactory
from ..services.core.SmartLinkService import SmartLinkService
from ..exceptions import SlugConflict, SlugReserved, PublisherLimitExceeded


class SmartLinkServiceTest(TestCase):
    def setUp(self):
        self.service = SmartLinkService()
        self.publisher = UserFactory()

    def test_create_with_auto_slug(self):
        sl = self.service.create(self.publisher, {'name': 'Test Link'})
        self.assertIsNotNone(sl.slug)
        self.assertTrue(sl.is_active)
        self.assertEqual(sl.publisher, self.publisher)

    def test_create_with_custom_slug(self):
        sl = self.service.create(self.publisher, {'name': 'Test', 'slug': 'mycustomslug'})
        self.assertEqual(sl.slug, 'mycustomslug')

    def test_create_duplicate_slug_raises(self):
        self.service.create(self.publisher, {'name': 'First', 'slug': 'uniqueslug01'})
        with self.assertRaises(SlugConflict):
            self.service.create(self.publisher, {'name': 'Second', 'slug': 'uniqueslug01'})

    def test_create_reserved_slug_raises(self):
        with self.assertRaises(SlugReserved):
            self.service.create(self.publisher, {'name': 'Admin', 'slug': 'admin'})

    def test_update_name(self):
        sl = SmartLinkFactory(publisher=self.publisher)
        updated = self.service.update(sl, {'name': 'Updated Name'})
        self.assertEqual(updated.name, 'Updated Name')

    def test_archive_sets_flags(self):
        sl = SmartLinkFactory(publisher=self.publisher)
        archived = self.service.archive(sl)
        self.assertFalse(archived.is_active)
        self.assertTrue(archived.is_archived)

    def test_restore_from_archive(self):
        sl = SmartLinkFactory(publisher=self.publisher, is_active=False, is_archived=True)
        restored = self.service.restore(sl)
        self.assertTrue(restored.is_active)
        self.assertFalse(restored.is_archived)

    def test_duplicate_creates_new_slug(self):
        sl = SmartLinkFactory(publisher=self.publisher)
        clone = self.service.duplicate(sl)
        self.assertNotEqual(clone.slug, sl.slug)
        self.assertEqual(clone.publisher, self.publisher)

    def test_get_for_publisher_filters_correctly(self):
        other = UserFactory()
        sl1 = SmartLinkFactory(publisher=self.publisher)
        sl2 = SmartLinkFactory(publisher=other)
        result = list(self.service.get_for_publisher(self.publisher))
        self.assertIn(sl1, result)
        self.assertNotIn(sl2, result)
