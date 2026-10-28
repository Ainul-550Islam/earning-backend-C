"""
test_views_coverage_boost.py
=============================
Coverage for messaging/views.py (APIView-based endpoints): upload flow,
search, delivery receipts, presence, translation, unread count, device sync,
health check, and mentions.

Place in: messaging/tests/test_views_coverage_boost.py
"""
from __future__ import annotations

import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase
from rest_framework.test import APIClient

from .factories import (
    UserFactory,
    InternalChatFactory,
    ChatParticipantFactory,
    ChatMessageFactory,
)
from ..models import MediaAttachment, ChatMention, ChatMessage


def _api(user=None) -> APIClient:
    client = APIClient()
    if user:
        client.force_authenticate(user=user)
    return client


class TestMessagingExceptionHandler(TestCase):
    """
    Regression tests (Part 6 audit): settings_messaging.py's REST_FRAMEWORK
    template references "messaging.views.messaging_exception_handler" as
    EXCEPTION_HANDLER, but that function never actually existed anywhere -
    a project following the template exactly would get an ImportError the
    first time DRF needed to format an exception into a response.
    """

    def test_delegates_to_drf_default_for_recognized_exceptions(self):
        from rest_framework.exceptions import NotAuthenticated
        from ..views import messaging_exception_handler
        response = messaging_exception_handler(NotAuthenticated(), {"view": None})
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 401)

    def test_formats_messaging_error_with_to_dict_shape(self):
        from ..exceptions import ChatNotFoundError
        from ..views import messaging_exception_handler
        response = messaging_exception_handler(ChatNotFoundError("gone"), {"view": None})
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {
            "error_type": "ChatNotFoundError", "code": "chat_not_found", "detail": "gone",
        })

    def test_returns_none_and_logs_for_truly_unhandled_exception(self):
        from ..views import messaging_exception_handler
        with patch("messaging.views.logger.error") as mock_log:
            response = messaging_exception_handler(ValueError("unexpected"), {"view": "SomeView"})
        self.assertIsNone(response)
        mock_log.assert_called_once()

    def test_end_to_end_via_real_drf_dispatch(self):
        """
        Wires messaging_exception_handler up via DRF settings exactly as
        settings_messaging.py's template instructs, and hits a real view
        that raises a MessagingError with NO local try/except around it -
        proving the actual gap this fixes: previously, either the handler
        didn't exist (ImportError) or (before that) the exception would
        have fallen through DRF's default handler as a bare 500 with none
        of MessagingError's error_type/code/detail context.
        """
        from rest_framework.views import APIView
        from rest_framework.test import APIRequestFactory
        from rest_framework.settings import api_settings
        from ..exceptions import ChatAccessDeniedError

        class _RaisesMessagingError(APIView):
            authentication_classes = []
            permission_classes = []

            def get(self, request):
                raise ChatAccessDeniedError("not your chat")

        factory = APIRequestFactory()
        request = factory.get("/fake/")
        with self.settings(REST_FRAMEWORK={
            **{k: v for k, v in vars(api_settings).items() if not k.startswith("_")},
            "EXCEPTION_HANDLER": "messaging.views.messaging_exception_handler",
        }):
            response = _RaisesMessagingError.as_view()(request)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "chat_access_denied")
        self.assertEqual(response.data["detail"], "not your chat")


class TestMessageAttachmentUploadView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_missing_filename(self):
        r = _api(self.user).post("/messaging/upload/", {
            "mimetype": "image/jpeg", "file_size": 100,
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_missing_mimetype(self):
        r = _api(self.user).post("/messaging/upload/", {
            "filename": "a.jpg", "file_size": 100,
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_invalid_file_size(self):
        r = _api(self.user).post("/messaging/upload/", {
            "filename": "a.jpg", "mimetype": "image/jpeg", "file_size": "not-a-number",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_non_positive_file_size(self):
        r = _api(self.user).post("/messaging/upload/", {
            "filename": "a.jpg", "mimetype": "image/jpeg", "file_size": 0,
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_success_uses_local_fallback(self):
        r = _api(self.user).post("/messaging/upload/", {
            "filename": "photo.jpg", "mimetype": "image/jpeg", "file_size": 2048,
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIn("media_id", r.data)
        self.assertTrue(MediaAttachment.objects.filter(pk=r.data["media_id"]).exists())

    def test_file_too_large_rejected(self):
        r = _api(self.user).post("/messaging/upload/", {
            "filename": "huge.jpg", "mimetype": "image/jpeg", "file_size": 10**12,
        }, format="json")
        self.assertEqual(r.status_code, 413)

    def test_disallowed_mimetype_rejected(self):
        r = _api(self.user).post("/messaging/upload/", {
            "filename": "virus.exe", "mimetype": "application/x-msdownload", "file_size": 100,
        }, format="json")
        self.assertEqual(r.status_code, 415)

    def test_unexpected_error_returns_500(self):
        with patch(
            "messaging.utils.media_pipeline.generate_presigned_upload_url",
            side_effect=RuntimeError("boom"),
        ):
            r = _api(self.user).post("/messaging/upload/", {
                "filename": "a.jpg", "mimetype": "image/jpeg", "file_size": 100,
            }, format="json")
        self.assertEqual(r.status_code, 500)


class TestUploadConfirmView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_missing_media_id(self):
        r = _api(self.user).post("/messaging/upload/confirm/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_not_found(self):
        r = _api(self.user).post("/messaging/upload/confirm/", {
            "media_id": str(uuid.uuid4()),
        }, format="json")
        self.assertEqual(r.status_code, 404)

    def test_already_confirmed(self):
        media = MediaAttachment.objects.create(
            uploaded_by=self.user, original_filename="a.pdf", file_key="k1",
            original_url="https://x/k1", mimetype="application/pdf", file_size=10,
            status=MediaAttachment.STATUS_READY,
        )
        r = _api(self.user).post("/messaging/upload/confirm/", {
            "media_id": str(media.id),
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Already confirmed", r.data["detail"])

    def test_document_marked_ready_immediately(self):
        media = MediaAttachment.objects.create(
            uploaded_by=self.user, original_filename="a.pdf", file_key="k2",
            original_url="https://x/k2", mimetype="application/pdf", file_size=10,
            status=MediaAttachment.STATUS_PENDING,
        )
        r = _api(self.user).post("/messaging/upload/confirm/", {
            "media_id": str(media.id),
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "ready")
        media.refresh_from_db()
        self.assertEqual(media.status, MediaAttachment.STATUS_READY)

    def test_image_queues_processing_task(self):
        media = MediaAttachment.objects.create(
            uploaded_by=self.user, original_filename="a.jpg", file_key="k3",
            original_url="https://x/k3", mimetype="image/jpeg", file_size=10,
            status=MediaAttachment.STATUS_PENDING,
        )
        with patch("messaging.tasks.process_image_task.delay") as mock_delay:
            r = _api(self.user).post("/messaging/upload/confirm/", {
                "media_id": str(media.id),
            }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "processing")
        mock_delay.assert_called_once_with(str(media.id))

    def test_video_queues_processing_task(self):
        media = MediaAttachment.objects.create(
            uploaded_by=self.user, original_filename="a.mp4", file_key="k4",
            original_url="https://x/k4", mimetype="video/mp4", file_size=10,
            status=MediaAttachment.STATUS_PENDING,
        )
        with patch("messaging.tasks.process_video_task.delay") as mock_delay:
            r = _api(self.user).post("/messaging/upload/confirm/", {
                "media_id": str(media.id),
            }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "processing")
        mock_delay.assert_called_once_with(str(media.id))


class TestMediaStatusView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_missing_media_id(self):
        r = _api(self.user).get("/messaging/upload/status/")
        self.assertEqual(r.status_code, 400)

    def test_not_found(self):
        r = _api(self.user).get(f"/messaging/upload/status/?media_id={uuid.uuid4()}")
        self.assertEqual(r.status_code, 404)

    def test_success(self):
        media = MediaAttachment.objects.create(
            uploaded_by=self.user, original_filename="a.jpg", file_key="k5",
            original_url="https://x/k5", mimetype="image/jpeg", file_size=10,
            status=MediaAttachment.STATUS_READY, width=800, height=600,
        )
        r = _api(self.user).get(f"/messaging/upload/status/?media_id={media.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "ready")
        self.assertEqual(r.data["width"], 800)


class TestMessageSearchView(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_missing_query(self):
        r = _api(self.user).get("/messaging/search/")
        self.assertEqual(r.status_code, 400)

    def test_query_too_short(self):
        r = _api(self.user).get("/messaging/search/?q=a")
        self.assertEqual(r.status_code, 400)

    def test_success(self):
        with patch("messaging.utils.search_engine.search_messages") as mock_search:
            mock_search.return_value = {"results": [], "total": 0, "page": 1}
            r = _api(self.user).get("/messaging/search/?q=hello&page=1&page_size=10")
        self.assertEqual(r.status_code, 200)
        mock_search.assert_called_once()

    def test_search_error_returns_500(self):
        with patch(
            "messaging.utils.search_engine.search_messages",
            side_effect=RuntimeError("es down"),
        ):
            r = _api(self.user).get("/messaging/search/?q=hello")
        self.assertEqual(r.status_code, 500)


class TestUserSearchView(TestCase):
    def test_empty_query_returns_empty_results(self):
        user = UserFactory()
        r = _api(user).get("/messaging/users/search/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["results"], [])

    def test_finds_matching_user(self):
        user = UserFactory()
        target = UserFactory(username="alice_wonder")
        r = _api(user).get("/messaging/users/search/?q=alice")
        self.assertEqual(r.status_code, 200)
        usernames = [u["username"] for u in r.data["results"]]
        self.assertIn("alice_wonder", usernames)


class TestDeliveryStatusView(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)

    def test_missing_message_id(self):
        r = _api(self.user).get("/messaging/delivery/")
        self.assertEqual(r.status_code, 400)

    def test_not_found(self):
        r = _api(self.user).get(f"/messaging/delivery/?message_id={uuid.uuid4()}")
        self.assertEqual(r.status_code, 404)

    def test_only_sender_can_view(self):
        outsider = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=outsider)
        r = _api(outsider).get(f"/messaging/delivery/?message_id={self.msg.id}")
        self.assertEqual(r.status_code, 403)

    def test_sender_sees_receipts(self):
        r = _api(self.user).get(f"/messaging/delivery/?message_id={self.msg.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("delivery_receipts", r.data)


class TestPresenceView(TestCase):
    def test_missing_user_ids(self):
        user = UserFactory()
        r = _api(user).get("/messaging/online/")
        self.assertEqual(r.status_code, 400)

    def test_success(self):
        user = UserFactory()
        other = UserFactory()
        r = _api(user).get(f"/messaging/online/?user_ids={user.pk},{other.pk}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)


class TestTranslationView(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="Hello there")

    def test_missing_message_id(self):
        r = _api(self.user).post("/messaging/translate/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_unsupported_language(self):
        r = _api(self.user).post("/messaging/translate/", {
            "message_id": str(self.msg.id), "target_language": "klingon",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_success(self):
        r = _api(self.user).post("/messaging/translate/", {
            "message_id": str(self.msg.id), "target_language": "bn",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["target_language"], "bn")

    def test_message_not_found(self):
        r = _api(self.user).post("/messaging/translate/", {
            "message_id": str(uuid.uuid4()), "target_language": "bn",
        }, format="json")
        self.assertEqual(r.status_code, 404)

    def test_unexpected_error_returns_500(self):
        with patch("messaging.services.translate_message", side_effect=RuntimeError("boom")):
            r = _api(self.user).post("/messaging/translate/", {
                "message_id": str(self.msg.id), "target_language": "bn",
            }, format="json")
        self.assertEqual(r.status_code, 500)


class TestUnreadCountView(TestCase):
    def test_success(self):
        user = UserFactory()
        r = _api(user).get("/messaging/unread/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("unread_count", r.data)


class TestDeviceSyncView(TestCase):
    def test_success(self):
        user = UserFactory()
        r = _api(user).post("/messaging/sync/", {}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_unexpected_error_returns_500(self):
        user = UserFactory()
        with patch(
            "messaging.utils.device_sync.sync_device_on_login",
            side_effect=RuntimeError("boom"),
        ):
            r = _api(user).post("/messaging/sync/", {}, format="json")
        self.assertEqual(r.status_code, 500)


class TestHealthCheckView(TestCase):
    def test_returns_200_when_healthy(self):
        r = _api().get("/messaging/health/")
        self.assertIn(r.status_code, (200, 207))
        self.assertIn("checks", r.data)
        self.assertIn("database", r.data["checks"])
        self.assertIn("cache", r.data["checks"])

    def test_no_auth_required(self):
        # permission_classes = [] — should work even fully unauthenticated.
        r = APIClient().get("/messaging/health/")
        self.assertIn(r.status_code, (200, 207))

    def test_degraded_when_db_check_fails(self):
        with patch("django.db.connection.ensure_connection", side_effect=RuntimeError("db down")):
            r = _api().get("/messaging/health/")
        self.assertEqual(r.status_code, 207)
        self.assertIn("error", r.data["checks"]["database"])


class TestMentionsView(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        self.other = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.other, content="@user hi")

    def test_list_mentions(self):
        ChatMention.objects.create(
            message=self.msg, chat=self.chat, mentioned_user=self.user, mentioned_by=self.other,
        )
        r = _api(self.user).get("/messaging/mentions/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)

    def test_unread_filter(self):
        ChatMention.objects.create(
            message=self.msg, chat=self.chat, mentioned_user=self.user,
            mentioned_by=self.other, is_read=True,
        )
        r = _api(self.user).get("/messaging/mentions/?unread=1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 0)

    def test_mark_read(self):
        mention = ChatMention.objects.create(
            message=self.msg, chat=self.chat, mentioned_user=self.user,
            mentioned_by=self.other, is_read=False,
        )
        r = _api(self.user).get("/messaging/mentions/?mark_read=1")
        self.assertEqual(r.status_code, 200)
        mention.refresh_from_db()
        self.assertTrue(mention.is_read)
