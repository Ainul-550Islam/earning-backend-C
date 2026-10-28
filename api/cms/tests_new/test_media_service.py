# api/cms/tests_new/test_media_service.py
"""
Tests for MediaService and MediaVariantService.
"""
import io
from django.test import TestCase
from decimal import Decimal
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import patch, MagicMock, call
try:
    from api.cms.models_new.profile_surveys import (
        SurveyTemplate as Survey, SurveyCompletion, SurveyCategory, SurveyQuestion
    )
    from api.cms.models_new.survey_rewards import (
        SurveyReward, RewardTransaction as Transaction, RewardPool
    )
    from api.cms.models_new.seo import SEOConfig as SEOModel, Redirect301
    from api.cms.models_new.user_profile import UserProfile, UserSegment
    from api.cms.models_new.task_management import TaskSchedule, TaskExecution
    from api.cms.models_new.cpalead import (
        VirtualCurrency, UserVirtualBalance, ConversionLog, ClickLog, ContentLocker
    )
except Exception:
    pass
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock

User = get_user_model()


def make_user(username='mediauser'):
    return User.objects.create_user(username=username, password='pass123')


def make_test_image(name='test.jpg', size=(100, 100)):
    """Create a minimal JPEG for testing."""
    try:
        from PIL import Image
        import io as _io
        img = Image.new('RGB', size, color='red')
        buf = _io.BytesIO()
        img.save(buf, format='JPEG')
        buf.seek(0)
        return SimpleUploadedFile(name, buf.read(), content_type='image/jpeg')
    except ImportError:
        # Fallback: create a minimal binary
        return SimpleUploadedFile(name, b'\xff\xd8\xff\xe0' + b'\x00' * 20, content_type='image/jpeg')


class TestMediaServiceUpload(TestCase):
    """Test MediaService file upload functionality."""

    def setUp(self):
        self.user = make_user()

    def test_upload_image_file(self):
        """Should upload an image file successfully."""
        from api.cms.services_new.MediaService import MediaService
        file = make_test_image('upload_test.jpg')
        media = MediaService.upload_file(
            file=file,
            uploaded_by=self.user,
            title='Test Upload',
            is_public=True,
            auto_generate_variants=False,
        )
        self.assertIsNotNone(media)
        self.assertEqual(media.title, 'Test Upload')
        self.assertEqual(media.uploaded_by, self.user)
        self.assertEqual(media.file_type, 'image')
        self.assertTrue(media.is_active)

    def test_upload_sets_filename(self):
        """Upload should extract and store filename."""
        from api.cms.services_new.MediaService import MediaService
        file = make_test_image('myfile.jpg')
        media = MediaService.upload_file(file=file, uploaded_by=self.user, auto_generate_variants=False)
        self.assertIsNotNone(media)
        self.assertIn('myfile', media.filename)

    def test_upload_sets_mime_type(self):
        """Upload should auto-detect MIME type."""
        from api.cms.services_new.MediaService import MediaService
        file = make_test_image('mime_test.jpg')
        media = MediaService.upload_file(file=file, uploaded_by=self.user, auto_generate_variants=False)
        self.assertIsNotNone(media)
        self.assertEqual(media.mime_type, 'image/jpeg')

    def test_upload_to_folder(self):
        """Should assign file to folder."""
        from api.cms.services_new.MediaService import MediaService
        folder = MediaService.create_folder(name='Test Folder', created_by=self.user)
        file = make_test_image('folder_test.jpg')
        media = MediaService.upload_file(
            file=file, uploaded_by=self.user, folder=folder, auto_generate_variants=False
        )
        self.assertEqual(media.folder, folder)

    def test_upload_with_tags(self):
        """Should assign tags to uploaded file."""
        from api.cms.services_new.MediaService import MediaService
        tag = MediaService.get_or_create_tag('nature')
        file = make_test_image('tagged.jpg')
        media = MediaService.upload_file(
            file=file, uploaded_by=self.user, tags=[tag], auto_generate_variants=False
        )
        self.assertIn(tag, media.tags.all())

    def test_upload_multiple_files(self):
        """Should upload multiple files at once."""
        from api.cms.services_new.MediaService import MediaService
        files = [make_test_image(f'multi_{i}.jpg') for i in range(3)]
        uploaded, errors = MediaService.upload_multiple_files(
            files=files, uploaded_by=self.user
        )
        self.assertEqual(len(uploaded), 3)
        self.assertEqual(len(errors), 0)


class TestMediaServiceFileListing(TestCase):
    """Test MediaService file listing and filtering."""

    def setUp(self):
        self.user = make_user()
        from api.cms.services_new.MediaService import MediaService
        for i in range(5):
            MediaService.upload_file(
                make_test_image(f'list_{i}.jpg'),
                uploaded_by=self.user,
                title=f'File {i}',
                auto_generate_variants=False,
            )

    def test_list_files_returns_all(self):
        """Should return all active files."""
        from api.cms.services_new.MediaService import MediaService
        files, total = MediaService.list_files(limit=10)
        self.assertGreaterEqual(total, 5)

    def test_list_files_by_type(self):
        """Should filter files by type."""
        from api.cms.services_new.MediaService import MediaService
        files, total = MediaService.list_files(file_type='image', limit=10)
        for f in files:
            self.assertEqual(f.file_type, 'image')

    def test_list_files_search(self):
        """Should search files by title."""
        from api.cms.services_new.MediaService import MediaService
        files, total = MediaService.list_files(search='File 0', limit=10)
        self.assertGreaterEqual(total, 1)

    def test_list_files_pagination(self):
        """Should paginate results."""
        from api.cms.services_new.MediaService import MediaService
        files1, total = MediaService.list_files(limit=2, offset=0)
        files2, _ = MediaService.list_files(limit=2, offset=2)
        ids1 = [f.id for f in files1]
        ids2 = [f.id for f in files2]
        self.assertEqual(len(files1), 2)
        # Pages should not overlap
        for fid in ids2:
            self.assertNotIn(fid, ids1)


class TestMediaServiceMetadata(TestCase):
    """Test metadata update functionality."""

    def setUp(self):
        self.user = make_user()
        from api.cms.services_new.MediaService import MediaService
        self.media = MediaService.upload_file(
            make_test_image('meta_test.jpg'), uploaded_by=self.user, auto_generate_variants=False
        )

    def test_update_title(self):
        """Should update file title."""
        from api.cms.services_new.MediaService import MediaService
        MediaService.update_file_metadata(self.media, {'title': 'New Title'})
        self.media.refresh_from_db()
        self.assertEqual(self.media.title, 'New Title')

    def test_update_alt_text(self):
        """Should update alt text."""
        from api.cms.services_new.MediaService import MediaService
        MediaService.update_file_metadata(self.media, {'alt_text': 'Image description'})
        self.media.refresh_from_db()
        self.assertEqual(self.media.alt_text, 'Image description')

    def test_update_is_public(self):
        """Should update is_public flag."""
        from api.cms.services_new.MediaService import MediaService
        MediaService.update_file_metadata(self.media, {'is_public': False})
        self.media.refresh_from_db()
        self.assertFalse(self.media.is_public)


class TestMediaServiceDelete(TestCase):
    """Test file deletion."""

    def setUp(self):
        self.user = make_user()
        from api.cms.services_new.MediaService import MediaService
        self.media = MediaService.upload_file(
            make_test_image('del_test.jpg'), uploaded_by=self.user, auto_generate_variants=False
        )

    def test_soft_delete(self):
        """Soft delete should deactivate file, not remove from DB."""
        from api.cms.services_new.MediaService import MediaService
        from api.cms.models_new.media import MediaFile
        file_id = self.media.id
        MediaService.delete_file(self.media, hard_delete=False)
        self.assertFalse(MediaFile.objects.get(id=file_id).is_active)

    def test_hard_delete(self):
        """Hard delete should remove file from DB."""
        from api.cms.services_new.MediaService import MediaService
        from api.cms.models_new.media import MediaFile
        file_id = self.media.id
        MediaService.delete_file(self.media, hard_delete=True)
        self.assertFalse(MediaFile.objects.filter(id=file_id).exists())


class TestMediaFolder(TestCase):
    """Test folder creation and tree."""

    def setUp(self):
        self.user = make_user()

    def test_create_folder(self):
        """Should create a media folder."""
        from api.cms.services_new.MediaService import MediaService
        folder = MediaService.create_folder(name='Photos', created_by=self.user)
        self.assertIsNotNone(folder)
        self.assertEqual(folder.name, 'Photos')

    def test_create_nested_folder(self):
        """Should create nested folders."""
        from api.cms.services_new.MediaService import MediaService
        parent = MediaService.create_folder(name='Root', created_by=self.user)
        child = MediaService.create_folder(name='Sub', parent=parent, created_by=self.user)
        self.assertEqual(child.parent, parent)

    def test_folder_path_auto_generated(self):
        """Folder path should be auto-generated."""
        from api.cms.services_new.MediaService import MediaService
        parent = MediaService.create_folder(name='Parent', created_by=self.user)
        child = MediaService.create_folder(name='Child', parent=parent, created_by=self.user)
        self.assertIn('Parent', child.path)
        self.assertIn('Child', child.path)

    def test_get_folder_tree(self):
        """Should return folder tree structure."""
        from api.cms.services_new.MediaService import MediaService
        MediaService.create_folder(name='TreeRoot', created_by=self.user)
        tree = MediaService.get_folder_tree()
        self.assertIsInstance(tree, list)


class TestMediaServiceStatistics(TestCase):
    """Test storage statistics."""

    def setUp(self):
        self.user = make_user()

    def test_get_storage_statistics(self):
        """Should return storage stats dict."""
        from api.cms.services_new.MediaService import MediaService
        stats = MediaService.get_storage_statistics()
        self.assertIn('total_files', stats)
        self.assertIn('total_size_bytes', stats)
        self.assertIn('by_type', stats)


class TestMediaVariantService(TestCase):
    """Test MediaVariantService variant generation."""

    def setUp(self):
        self.user = make_user()
        from api.cms.services_new.MediaService import MediaService
        self.media = MediaService.upload_file(
            make_test_image('variant_test.jpg'), uploaded_by=self.user, auto_generate_variants=False
        )

    @patch('cms.services_new.MediaVariantService.MediaVariantService._resize_image')
    def test_generate_all_variants(self, mock_resize):
        """Should attempt to generate all variant types."""
        from api.cms.services_new.MediaVariantService import MediaVariantService
        mock_resize.return_value = ('path/to/file.webp', 150, 150, 1024)
        results = MediaVariantService.generate_all_variants(self.media)
        self.assertIsInstance(results, dict)
        self.assertIn('thumb', results)
        self.assertIn('medium', results)
        self.assertIn('large', results)

    def test_generate_variant_non_image_skipped(self):
        """Non-image files should not generate variants."""
        from api.cms.services_new.MediaService import MediaService
        from api.cms.services_new.MediaVariantService import MediaVariantService
        from api.cms.models_new.media import MediaFile
        # Manually set file_type to document
        MediaFile.objects.filter(id=self.media.id).update(file_type='document')
        self.media.refresh_from_db()
        results = MediaVariantService.generate_all_variants(self.media)
        self.assertEqual(len(results), 0)

    def test_delete_variants(self):
        """Should delete all variants for a file."""
        from api.cms.services_new.MediaVariantService import MediaVariantService
        from api.cms.models_new.media import MediaVariant
        MediaVariant.objects.create(
            file=self.media,
            variant_type='thumb',
            file_path='path/thumb.webp',
        )
        deleted = MediaVariantService.delete_variants(self.media)
        self.assertGreaterEqual(deleted, 1)
        self.assertFalse(MediaVariant.objects.filter(file=self.media).exists())
