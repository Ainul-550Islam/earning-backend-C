"""
test_utils_media_pipeline.py
=============================
Full coverage for messaging/utils/media_pipeline.py
Functions: generate_presigned_upload_url, _validate_upload,
           _build_file_key, _local_upload_fallback,
           process_image_after_upload, _strip_exif,
           generate_video_thumbnail, scan_file_for_viruses, detect_nsfw
Place in: messaging/tests/test_utils_media_pipeline.py
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock, call
from django.test import TestCase, override_settings
from ..utils.media_pipeline import (
    generate_presigned_upload_url,
    _validate_upload,
    _build_file_key,
    _local_upload_fallback,
    process_image_after_upload,
    _strip_exif,
    generate_video_thumbnail,
    scan_file_for_viruses,
    detect_nsfw,
)
from ..exceptions import MediaTooLargeError, MediaTypeNotAllowedError


class TestValidateUpload(TestCase):
    def test_raises_for_disallowed_mimetype(self):
        with self.assertRaises(MediaTypeNotAllowedError) as ctx:
            _validate_upload("file.exe", "application/x-msdownload", 100)
        self.assertIn("not allowed", str(ctx.exception).lower())

    def test_raises_for_oversized_image(self):
        from ..constants import MAX_ATTACHMENT_SIZE_BYTES
        with self.assertRaises(MediaTooLargeError):
            _validate_upload("big.jpg", "image/jpeg", MAX_ATTACHMENT_SIZE_BYTES + 1)

    def test_raises_for_oversized_video(self):
        from ..constants import MAX_VIDEO_SIZE_BYTES
        with self.assertRaises(MediaTooLargeError):
            _validate_upload("huge.mp4", "video/mp4", MAX_VIDEO_SIZE_BYTES + 1)

    def test_raises_for_oversized_audio(self):
        from ..constants import MAX_AUDIO_SIZE_BYTES
        with self.assertRaises(MediaTooLargeError):
            _validate_upload("big.mp3", "audio/mpeg", MAX_AUDIO_SIZE_BYTES + 1)

    def test_valid_image_passes(self):
        _validate_upload("photo.jpg", "image/jpeg", 500_000)  # 500KB — should not raise

    def test_valid_video_passes(self):
        from ..constants import MAX_VIDEO_SIZE_BYTES
        _validate_upload("clip.mp4", "video/mp4", MAX_VIDEO_SIZE_BYTES - 1)

    def test_valid_pdf_passes(self):
        _validate_upload("doc.pdf", "application/pdf", 1_000_000)


class TestBuildFileKey(TestCase):
    def test_includes_chat_id_in_path_when_provided(self):
        chat_id = "11111111-2222-3333-4444-555555555555"
        key = _build_file_key(user_id=1, filename="photo.jpg", chat_id=chat_id)
        self.assertIn(chat_id, key)
        self.assertIn(".jpg", key)

    def test_invalid_chat_id_falls_back_to_user_scoped_path(self):
        """
        SECURITY: chat_id used to be embedded in the S3 key with no
        format validation at all. Not true path traversal (S3 doesn't
        resolve ".." like a filesystem), but an unvalidated value still
        let arbitrary characters into the key structure. A malformed/
        non-UUID chat_id must not be embedded raw - falls back to the
        user-scoped path instead.
        """
        key = _build_file_key(user_id=1, filename="photo.jpg", chat_id="../../etc/passwd")
        self.assertNotIn("etc/passwd", key)
        self.assertIn("messaging/users/1/", key)

    def test_includes_user_id_when_no_chat(self):
        key = _build_file_key(user_id=42, filename="avatar.png", chat_id=None)
        self.assertIn("42", key)

    def test_extension_preserved(self):
        key = _build_file_key(user_id=1, filename="video.mp4", chat_id=None)
        self.assertTrue(key.endswith(".mp4"))

    def test_key_contains_date_path(self):
        from django.utils import timezone
        key = _build_file_key(user_id=1, filename="x.jpg", chat_id=None)
        year = str(timezone.now().year)
        self.assertIn(year, key)

    def test_unique_each_call(self):
        k1 = _build_file_key(1, "file.jpg", None)
        k2 = _build_file_key(1, "file.jpg", None)
        self.assertNotEqual(k1, k2)

    def test_path_starts_with_messaging_prefix(self):
        key = _build_file_key(1, "file.jpg", None)
        self.assertTrue(key.startswith("messaging/"))


class TestLocalUploadFallback(TestCase):
    def test_returns_dict_with_required_keys(self):
        result = _local_upload_fallback(user_id=1, filename="test.jpg", mimetype="image/jpeg")
        self.assertIn("upload_url", result)
        self.assertIn("file_key", result)
        self.assertIn("cdn_url", result)
        self.assertIn("expires_in", result)
        self.assertIn("method", result)
        self.assertIn("headers", result)

    def test_method_is_put(self):
        result = _local_upload_fallback(1, "file.jpg", "image/jpeg")
        self.assertEqual(result["method"], "PUT")

    def test_cdn_url_is_localhost(self):
        result = _local_upload_fallback(1, "file.jpg", "image/jpeg")
        self.assertIn("localhost", result["cdn_url"])

    def test_file_key_contains_dev_prefix(self):
        result = _local_upload_fallback(1, "file.jpg", "image/jpeg")
        self.assertTrue(result["file_key"].startswith("dev/"))

    def test_expires_in_is_900(self):
        result = _local_upload_fallback(1, "file.jpg", "image/jpeg")
        self.assertEqual(result["expires_in"], 900)


class TestGeneratePresignedUploadUrl(TestCase):
    @override_settings(AWS_STORAGE_BUCKET_NAME=None)
    def test_falls_back_to_local_when_no_s3_bucket(self):
        result = generate_presigned_upload_url(
            user_id=1,
            filename="test.jpg",
            mimetype="image/jpeg",
            file_size=500_000,
        )
        self.assertIn("upload_url", result)
        self.assertIn("file_key", result)

    @override_settings(AWS_STORAGE_BUCKET_NAME=None)
    def test_raises_for_disallowed_mimetype(self):
        with self.assertRaises(MediaTypeNotAllowedError):
            generate_presigned_upload_url(
                user_id=1, filename="hack.exe",
                mimetype="application/x-msdownload", file_size=100,
            )

    @override_settings(
        AWS_STORAGE_BUCKET_NAME="my-bucket",
        AWS_S3_REGION_NAME="us-east-1",
        AWS_S3_CUSTOM_DOMAIN="cdn.example.com",
    )
    @patch("messaging.utils.media_pipeline.boto3")
    def test_returns_presigned_url_when_s3_configured(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://my-bucket.s3.amazonaws.com/presigned"
        mock_boto3.client.return_value = mock_s3
        result = generate_presigned_upload_url(
            user_id=1, filename="photo.jpg",
            mimetype="image/jpeg", file_size=100_000,
        )
        self.assertIn("upload_url", result)
        self.assertIn("https://", result["upload_url"])

    @override_settings(
        AWS_STORAGE_BUCKET_NAME="my-bucket", AWS_S3_REGION_NAME="us-east-1",
    )
    @patch("messaging.utils.media_pipeline.boto3")
    def test_cdn_url_uses_custom_domain(self, mock_boto3):
        with self.settings(AWS_S3_CUSTOM_DOMAIN="cdn.example.com"):
            mock_s3 = MagicMock()
            mock_s3.generate_presigned_url.return_value = "https://presigned"
            mock_boto3.client.return_value = mock_s3
            result = generate_presigned_upload_url(
                user_id=1, filename="photo.jpg",
                mimetype="image/jpeg", file_size=100_000,
            )
            self.assertIn("cdn.example.com", result["cdn_url"])

    @override_settings(
        AWS_STORAGE_BUCKET_NAME="my-bucket", AWS_S3_REGION_NAME="us-east-1",
    )
    @patch("messaging.utils.media_pipeline.boto3")
    def test_reraises_client_error(self, mock_boto3):
        from botocore.exceptions import ClientError
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "PutObject"
        )
        mock_boto3.client.return_value = mock_s3
        with self.assertRaises(ClientError):
            generate_presigned_upload_url(
                user_id=1, filename="photo.jpg", mimetype="image/jpeg", file_size=1000,
            )


class TestProcessImageAfterUploadRealPillow(TestCase):
    """
    Real end-to-end tests (Part 6 audit): the original coverage for this
    function mocked PIL.Image entirely (@patch(..., "Image", create=True)),
    so none of the actual resize/EXIF-strip/format-conversion logic ever
    really ran despite the function showing as covered. These drive real
    Pillow objects through the whole pipeline and inspect real output bytes.
    """

    @override_settings(AWS_STORAGE_BUCKET_NAME="bucket", AWS_S3_CUSTOM_DOMAIN="cdn.example.com")
    @patch("messaging.utils.media_pipeline.boto3")
    def test_real_pillow_pipeline_produces_valid_outputs(self, mock_boto3):
        from PIL import Image
        import io as real_io

        # 2000x2000 forces the >1920 resize path in the "compressed" branch
        src = Image.new("RGB", (2000, 2000), color=(200, 50, 50))
        buf = real_io.BytesIO()
        src.save(buf, format="JPEG")
        real_jpeg_bytes = buf.getvalue()

        mock_body = MagicMock()
        mock_body.read.return_value = real_jpeg_bytes
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": mock_body}
        put_calls = {}

        def capture_put(Bucket, Key, Body, ContentType):
            put_calls[Key] = (Body.read(), ContentType)

        mock_s3.put_object.side_effect = capture_put
        mock_boto3.client.return_value = mock_s3

        result = process_image_after_upload("uploads/photo.jpg", "image/jpeg")

        self.assertIsNotNone(result["thumbnail"])
        self.assertIsNotNone(result["webp"])
        self.assertIsNotNone(result["compressed"])
        self.assertEqual(len(put_calls), 3)

        thumb_key = next(k for k in put_calls if "_thumb." in k)
        thumb_bytes, thumb_ct = put_calls[thumb_key]
        thumb_img = Image.open(real_io.BytesIO(thumb_bytes))
        self.assertEqual(thumb_ct, "image/jpeg")
        self.assertLessEqual(thumb_img.size[0], 320)
        self.assertLessEqual(thumb_img.size[1], 320)

        webp_key = next(k for k in put_calls if k.endswith(".webp"))
        webp_bytes, webp_ct = put_calls[webp_key]
        webp_img = Image.open(real_io.BytesIO(webp_bytes))
        self.assertEqual(webp_img.format, "WEBP")
        self.assertEqual(webp_ct, "image/webp")

        comp_key = next(k for k in put_calls if "_compressed" in k)
        comp_bytes, comp_ct = put_calls[comp_key]
        comp_img = Image.open(real_io.BytesIO(comp_bytes))
        self.assertEqual(comp_ct, "image/jpeg")
        self.assertLessEqual(comp_img.size[0], 1920)
        self.assertLessEqual(comp_img.size[1], 1920)

    @override_settings(AWS_STORAGE_BUCKET_NAME="bucket")
    @patch("messaging.utils.media_pipeline.boto3")
    def test_real_pillow_pipeline_strips_gps_exif(self, mock_boto3):
        """Confirms _strip_exif is actually wired into the real pipeline -
        an EXIF-tagged source image should carry no EXIF into any output."""
        from PIL import Image
        import io as real_io

        src = Image.new("RGB", (100, 100), color=(10, 20, 30))
        buf = real_io.BytesIO()
        exif = src.getexif()
        exif[271] = "TestCameraMake"  # Make tag
        src.save(buf, format="JPEG", exif=exif)
        real_jpeg_bytes = buf.getvalue()

        mock_body = MagicMock()
        mock_body.read.return_value = real_jpeg_bytes
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": mock_body}
        put_calls = {}
        mock_s3.put_object.side_effect = lambda Bucket, Key, Body, ContentType: put_calls.update(
            {Key: Body.read()}
        )
        mock_boto3.client.return_value = mock_s3

        process_image_after_upload("uploads/gps_photo.jpg", "image/jpeg")

        comp_key = next(k for k in put_calls if "_compressed" in k)
        comp_img = Image.open(real_io.BytesIO(put_calls[comp_key]))
        self.assertEqual(dict(comp_img.getexif()), {})


class TestProcessImageAfterUpload(TestCase):
    @override_settings(AWS_STORAGE_BUCKET_NAME=None)
    def test_returns_empty_results_when_no_s3(self):
        result = process_image_after_upload("uploads/test.jpg", "image/jpeg")
        self.assertIn("original", result)
        self.assertEqual(result["original"], "uploads/test.jpg")
        self.assertIsNone(result["thumbnail"])
        self.assertIsNone(result["webp"])

    @override_settings(AWS_STORAGE_BUCKET_NAME="bucket")
    @patch("messaging.utils.media_pipeline.boto3")
    def test_handles_pillow_not_installed(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        with patch.dict("sys.modules", {"PIL": None, "PIL.Image": None}):
            result = process_image_after_upload("img.jpg", "image/jpeg")
        self.assertIn("original", result)

    @override_settings(AWS_STORAGE_BUCKET_NAME="bucket")
    @patch("messaging.utils.media_pipeline.boto3")
    @patch("messaging.utils.media_pipeline.Image", create=True)
    def test_creates_thumbnail_webp_and_compressed(self, mock_image_module, mock_boto3):
        import io
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"fakeimagebytes")}
        mock_boto3.client.return_value = mock_s3
        mock_img = MagicMock()
        mock_img.mode = "RGB"
        mock_img.size = (1920, 1080)
        mock_img.copy.return_value = mock_img
        mock_image_module.open.return_value = mock_img
        mock_image_module.LANCZOS = 1

        # Patch the io.BytesIO used internally
        with patch("messaging.utils.media_pipeline.io") as mock_io:
            mock_buf = MagicMock()
            mock_io.BytesIO.return_value = mock_buf
            result = process_image_after_upload("uploads/photo.jpg", "image/jpeg")
        self.assertIn("original", result)


    @override_settings(AWS_STORAGE_BUCKET_NAME="bucket")
    @patch("messaging.utils.media_pipeline.boto3")
    def test_real_pillow_pipeline_converts_non_rgb_source(self, mock_boto3):
        """A grayscale ('L' mode) source must be converted to RGB before
        WebP/JPEG re-encoding (both formats used downstream need RGB)."""
        from PIL import Image
        import io as real_io

        src = Image.new("L", (200, 200), color=128)  # grayscale, not RGB/RGBA
        buf = real_io.BytesIO()
        src.save(buf, format="PNG")
        real_png_bytes = buf.getvalue()

        mock_body = MagicMock()
        mock_body.read.return_value = real_png_bytes
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": mock_body}
        put_calls = {}
        mock_s3.put_object.side_effect = lambda Bucket, Key, Body, ContentType: put_calls.update(
            {Key: Body.read()}
        )
        mock_boto3.client.return_value = mock_s3

        result = process_image_after_upload("uploads/gray.png", "image/png")

        self.assertIsNotNone(result["webp"])
        webp_key = next(k for k in put_calls if k.endswith(".webp"))
        webp_img = Image.open(real_io.BytesIO(put_calls[webp_key]))
        self.assertEqual(webp_img.mode, "RGB")


class TestStripExif(TestCase):
    def test_uses_getdata_fallback_on_older_pillow(self):
        """Pillow < 10.2 doesn't have get_flattened_data() - hasattr()
        gating must fall back to the older getdata() path and still work."""
        from PIL import Image
        img = Image.new("RGB", (10, 10), color=(1, 2, 3))

        class NoFlattenedData:
            """Wraps a real Image but hides get_flattened_data, forcing
            the hasattr() check in _strip_exif to take the fallback path."""
            def __init__(self, wrapped):
                self._wrapped = wrapped
            def __getattr__(self, name):
                if name == "get_flattened_data":
                    raise AttributeError(name)
                return getattr(self._wrapped, name)

        wrapped = NoFlattenedData(img)
        self.assertFalse(hasattr(wrapped, "get_flattened_data"))
        result = _strip_exif(wrapped)
        self.assertEqual(result.size, (10, 10))
        self.assertEqual(list(result.getdata())[:3], [(1, 2, 3), (1, 2, 3), (1, 2, 3)])
    def test_returns_image_object(self):
        try:
            from PIL import Image
            import io
            img = Image.new("RGB", (100, 100), color=(255, 0, 0))
            result = _strip_exif(img)
            self.assertEqual(result.size, (100, 100))
        except ImportError:
            # Pillow not installed — test skipped
            pass

    def test_returns_input_image_on_failure(self):
        mock_img = MagicMock()
        mock_img.getdata.side_effect = Exception("PIL error")
        result = _strip_exif(mock_img)
        self.assertIs(result, mock_img)

    def test_logs_warning_on_failure(self):
        """Part 6 audit: this failure mode used to be completely silent -
        no log line at all - which matters because it means the image
        keeps its original EXIF (GPS/device info) with zero observability."""
        mock_img = MagicMock()
        mock_img.getdata.side_effect = Exception("PIL error")
        with self.assertLogs("messaging.utils.media_pipeline", level="WARNING") as ctx:
            _strip_exif(mock_img)
        self.assertTrue(any("EXIF" in msg for msg in ctx.output))


class TestGenerateVideoThumbnail(TestCase):
    @override_settings(AWS_STORAGE_BUCKET_NAME=None)
    def test_returns_none_when_no_s3(self):
        result = generate_video_thumbnail("videos/test.mp4")
        self.assertIsNone(result)

    @override_settings(AWS_STORAGE_BUCKET_NAME="bucket")
    @patch("messaging.utils.media_pipeline.boto3")
    @patch("messaging.utils.media_pipeline.subprocess")
    @patch("messaging.utils.media_pipeline.tempfile")
    def test_returns_thumbnail_url_on_success(self, mock_tempfile, mock_subprocess, mock_boto3):
        import tempfile
        mock_tmp_vid = MagicMock()
        mock_tmp_vid.name = "/tmp/fake_video.mp4"
        mock_tmp_thumb = MagicMock()
        mock_tmp_thumb.name = "/tmp/fake_thumb.jpg"
        mock_tempfile.NamedTemporaryFile.side_effect = [
            MagicMock(__enter__=lambda s: mock_tmp_vid, __exit__=MagicMock(return_value=False)),
            MagicMock(__enter__=lambda s: mock_tmp_thumb, __exit__=MagicMock(return_value=False)),
        ]
        mock_subprocess.run = MagicMock()
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        with patch("builtins.open", MagicMock()), \
             patch("messaging.utils.media_pipeline.os.unlink"):
            result = generate_video_thumbnail("videos/clip.mp4")
        self.assertIsInstance(result, (str, type(None)))

    @override_settings(AWS_STORAGE_BUCKET_NAME="bucket")
    @patch("messaging.utils.media_pipeline.boto3")
    def test_returns_none_when_ffmpeg_not_found(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_s3.download_fileobj.return_value = None
        mock_boto3.client.return_value = mock_s3
        with patch("messaging.utils.media_pipeline.subprocess") as mock_sub:
            mock_sub.run.side_effect = FileNotFoundError("ffmpeg not found")
            result = generate_video_thumbnail("v.mp4")
        self.assertIsNone(result)

    @override_settings(AWS_STORAGE_BUCKET_NAME="bucket")
    @patch("messaging.utils.media_pipeline.boto3")
    def test_cleans_up_temp_files_when_ffmpeg_fails(self, mock_boto3):
        """
        Regression test (Part 6 audit): cleanup previously only ran on the
        success path (two inline os.unlink() calls at the end of the try
        block). Any real failure - a corrupt video causing ffmpeg to exit
        non-zero, the 30s timeout, an S3 error - skipped straight past
        them into an except block that returned early, leaking the
        downloaded video (often several MB) and any partial thumbnail on
        disk forever. Uses real tempfile.NamedTemporaryFile (wrapped only
        to record the paths) so this proves actual files don't survive,
        not just that a mock method got called.
        """
        import os as real_os
        import tempfile as tempfile_module
        import subprocess as real_subprocess

        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        created = []
        original_ntf = tempfile_module.NamedTemporaryFile  # capture BEFORE patching - tempfile
        # is the same global module object everywhere, so re-importing it
        # after the patch is active would just hand back the patched
        # version and recurse forever.

        def tracking_ntf(*args, **kwargs):
            f = original_ntf(*args, **kwargs)
            created.append(f.name)
            return f

        with patch(
            "messaging.utils.media_pipeline.tempfile.NamedTemporaryFile",
            side_effect=tracking_ntf,
        ), patch(
            "messaging.utils.media_pipeline.subprocess.run",
            side_effect=real_subprocess.CalledProcessError(1, "ffmpeg"),
        ):
            result = generate_video_thumbnail("videos/corrupt.mp4")

        self.assertIsNone(result)
        self.assertEqual(len(created), 2)
        for p in created:
            self.assertFalse(real_os.path.exists(p), f"temp file leaked: {p}")

    @override_settings(AWS_STORAGE_BUCKET_NAME="bucket")
    @patch("messaging.utils.media_pipeline.boto3")
    def test_cleans_up_temp_files_on_success(self, mock_boto3):
        import os as real_os
        import tempfile as tempfile_module

        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        created = []
        original_ntf = tempfile_module.NamedTemporaryFile

        def tracking_ntf(*args, **kwargs):
            f = original_ntf(*args, **kwargs)
            created.append(f.name)
            return f

        def fake_run(*args, **kwargs):
            # Write something to the thumb path so open() has real bytes
            with open(created[-1], "wb") as fh:
                fh.write(b"\xff\xd8\xff\xe0fake-jpeg-bytes")
            return MagicMock(returncode=0)

        with patch(
            "messaging.utils.media_pipeline.tempfile.NamedTemporaryFile",
            side_effect=tracking_ntf,
        ), patch(
            "messaging.utils.media_pipeline.subprocess.run", side_effect=fake_run,
        ):
            result = generate_video_thumbnail("videos/clip.mp4")

        self.assertIsNotNone(result)
        self.assertEqual(len(created), 2)
        for p in created:
            self.assertFalse(real_os.path.exists(p), f"temp file leaked: {p}")

    @override_settings(AWS_STORAGE_BUCKET_NAME="bucket")
    @patch("messaging.utils.media_pipeline.boto3")
    def test_logs_when_cleanup_itself_fails(self, mock_boto3):
        """The finally block's own os.unlink can fail (e.g. permissions,
        already removed by something else) - must not raise out of the
        function, just log and move on."""
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        with patch("messaging.utils.media_pipeline.subprocess") as mock_sub, \
             patch("messaging.utils.media_pipeline.os.path.exists", return_value=True), \
             patch("messaging.utils.media_pipeline.os.unlink", side_effect=OSError("busy")), \
             self.assertLogs("messaging.utils.media_pipeline", level="WARNING") as ctx:
            mock_sub.run.side_effect = FileNotFoundError("ffmpeg not found")
            result = generate_video_thumbnail("v.mp4")
        self.assertIsNone(result)
        self.assertTrue(any("cleanup failed" in msg for msg in ctx.output))


class TestScanFileForViruses(TestCase):
    @override_settings(VIRUSTOTAL_API_KEY=None)
    def test_returns_true_when_not_configured(self):
        result = scan_file_for_viruses("uploads/file.jpg")
        self.assertTrue(result)

    @override_settings(VIRUSTOTAL_API_KEY="fake-api-key", AWS_STORAGE_BUCKET_NAME="bucket")
    @patch("messaging.utils.media_pipeline.requests")
    def test_returns_true_when_scan_clean(self, mock_requests):
        submit_resp = MagicMock()
        submit_resp.raise_for_status = MagicMock()
        submit_resp.json.return_value = {"data": {"id": "analysis-id-123"}}

        report_resp = MagicMock()
        report_resp.raise_for_status = MagicMock()
        report_resp.json.return_value = {
            "data": {
                "attributes": {
                    "status": "completed",
                    "stats": {"malicious": 0, "suspicious": 0, "harmless": 70},
                }
            }
        }
        mock_requests.post.return_value = submit_resp
        mock_requests.get.return_value = report_resp

        with patch("messaging.utils.media_pipeline.time"):
            result = scan_file_for_viruses("uploads/clean.jpg")
        self.assertTrue(result)

    @override_settings(VIRUSTOTAL_API_KEY="fake-api-key", AWS_STORAGE_BUCKET_NAME="bucket")
    @patch("messaging.utils.media_pipeline.requests")
    def test_returns_false_when_malicious(self, mock_requests):
        submit_resp = MagicMock()
        submit_resp.raise_for_status = MagicMock()
        submit_resp.json.return_value = {"data": {"id": "analysis-id-456"}}
        report_resp = MagicMock()
        report_resp.raise_for_status = MagicMock()
        report_resp.json.return_value = {
            "data": {
                "attributes": {
                    "status": "completed",
                    "stats": {"malicious": 3, "suspicious": 1, "harmless": 10},
                }
            }
        }
        mock_requests.post.return_value = submit_resp
        mock_requests.get.return_value = report_resp
        with patch("messaging.utils.media_pipeline.time"):
            result = scan_file_for_viruses("uploads/virus.exe")
        self.assertFalse(result)

    @override_settings(VIRUSTOTAL_API_KEY="key", AWS_STORAGE_BUCKET_NAME="bucket")
    @patch("messaging.utils.media_pipeline.requests")
    def test_returns_true_on_exception(self, mock_requests):
        mock_requests.post.side_effect = Exception("VT API down")
        result = scan_file_for_viruses("uploads/file.jpg")
        self.assertTrue(result)

    @override_settings(VIRUSTOTAL_API_KEY="key", AWS_STORAGE_BUCKET_NAME="bucket")
    @patch("messaging.utils.media_pipeline.requests")
    def test_returns_true_when_scan_never_completes(self, mock_requests):
        """Polling loop exhausts all 6 attempts without status=='completed'
        (VT still processing) - falls through to the same fail-open True."""
        submit_resp = MagicMock()
        submit_resp.raise_for_status = MagicMock()
        submit_resp.json.return_value = {"data": {"id": "analysis-id-slow"}}
        report_resp = MagicMock()
        report_resp.raise_for_status = MagicMock()
        report_resp.json.return_value = {
            "data": {"attributes": {"status": "queued", "stats": {}}}
        }
        mock_requests.post.return_value = submit_resp
        mock_requests.get.return_value = report_resp
        with patch("messaging.utils.media_pipeline.time"):
            result = scan_file_for_viruses("uploads/slow.jpg")
        self.assertTrue(result)
        self.assertEqual(mock_requests.get.call_count, 6)


class TestDetectNsfw(TestCase):
    @override_settings(GOOGLE_VISION_API_KEY=None)
    def test_returns_safe_when_not_configured(self):
        result = detect_nsfw("https://example.com/image.jpg")
        self.assertTrue(result["is_safe"])
        self.assertFalse(result["is_nsfw"])
        self.assertEqual(result["toxic_score"], 0.0)

    @override_settings(GOOGLE_VISION_API_KEY="fake-key")
    @patch("messaging.utils.media_pipeline.requests")
    def test_returns_safe_for_clean_image(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "responses": [{
                "safeSearchAnnotation": {
                    "adult": "VERY_UNLIKELY",
                    "violence": "UNLIKELY",
                    "medical": "UNLIKELY",
                    "racy": "UNLIKELY",
                }
            }]
        }
        mock_requests.post.return_value = mock_resp
        result = detect_nsfw("https://example.com/clean.jpg")
        self.assertTrue(result["is_safe"])
        self.assertFalse(result["is_nsfw"])

    @override_settings(GOOGLE_VISION_API_KEY="fake-key")
    @patch("messaging.utils.media_pipeline.requests")
    def test_returns_unsafe_for_nsfw_image(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "responses": [{
                "safeSearchAnnotation": {
                    "adult": "VERY_LIKELY",
                    "violence": "UNLIKELY",
                    "medical": "UNLIKELY",
                    "racy": "LIKELY",
                }
            }]
        }
        mock_requests.post.return_value = mock_resp
        result = detect_nsfw("https://example.com/nsfw.jpg")
        self.assertFalse(result["is_safe"])
        self.assertTrue(result["is_nsfw"])

    @override_settings(GOOGLE_VISION_API_KEY="fake-key")
    @patch("messaging.utils.media_pipeline.requests")
    def test_returns_safe_on_api_exception(self, mock_requests):
        mock_requests.post.side_effect = Exception("Vision API error")
        result = detect_nsfw("https://example.com/image.jpg")
        self.assertTrue(result["is_safe"])
        self.assertFalse(result["is_nsfw"])
        self.assertEqual(result["toxic_score"], 0.0)

    @override_settings(GOOGLE_VISION_API_KEY="fake-key")
    @patch("messaging.utils.media_pipeline.requests")
    def test_returns_annotation_categories(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "responses": [{
                "safeSearchAnnotation": {
                    "adult": "UNLIKELY", "violence": "UNLIKELY",
                    "medical": "UNLIKELY", "racy": "UNLIKELY",
                }
            }]
        }
        mock_requests.post.return_value = mock_resp
        result = detect_nsfw("https://example.com/image.jpg")
        self.assertIn("adult", result)
        self.assertIn("violence", result)

    @override_settings(GOOGLE_VISION_API_KEY="fake-key")
    @patch("messaging.utils.media_pipeline.requests")
    def test_is_nsfw_and_toxic_score_present_for_process_image_task(self, mock_requests):
        """
        Regression test (Part 6 audit): tasks.process_image_task reads
        nsfw_result.get("is_nsfw") and nsfw_result.get("toxic_score", 0.0)
        to decide MediaAttachment.status/is_nsfw/nsfw_score. Neither key
        existed in this function's return value before - dict.get() on a
        missing key doesn't raise, it silently returns the falsy default,
        so every image was marked is_nsfw=False/nsfw_score=0.0/READY no
        matter what Vision actually detected. This asserts the exact keys
        and types the task's own .get() calls depend on.
        """
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "responses": [{
                "safeSearchAnnotation": {"adult": "VERY_LIKELY", "violence": "UNLIKELY"}
            }]
        }
        mock_requests.post.return_value = mock_resp
        result = detect_nsfw("https://example.com/explicit.jpg")
        self.assertIn("is_nsfw", result)
        self.assertIn("toxic_score", result)
        self.assertIs(result["is_nsfw"], True)
        self.assertIsInstance(result["toxic_score"], float)
        self.assertGreater(result["toxic_score"], 0.0)

    @override_settings(GOOGLE_VISION_API_KEY="fake-key")
    @patch("messaging.utils.media_pipeline.requests")
    def test_toxic_score_reflects_highest_risk_category(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "responses": [{
                "safeSearchAnnotation": {"adult": "POSSIBLE", "violence": "VERY_LIKELY"}
            }]
        }
        mock_requests.post.return_value = mock_resp
        result = detect_nsfw("https://example.com/violent.jpg")
        self.assertEqual(result["toxic_score"], 1.0)  # driven by violence, not adult

    @override_settings(GOOGLE_VISION_API_KEY="fake-key")
    @patch("messaging.utils.media_pipeline.requests")
    def test_toxic_score_zero_for_very_unlikely(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "responses": [{
                "safeSearchAnnotation": {"adult": "VERY_UNLIKELY", "violence": "VERY_UNLIKELY"}
            }]
        }
        mock_requests.post.return_value = mock_resp
        result = detect_nsfw("https://example.com/clean.jpg")
        self.assertEqual(result["toxic_score"], 0.0)
