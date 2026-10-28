"""
Regression test for the view_story() authorization fix found while
verifying tenant isolation on the viewsets that don't override
get_queryset() (world-system audit follow-up to Part 20).

Before this fix, view_story() recorded a StoryView for any story_id
regardless of whether the viewer shared a chat with the story's owner.
"""
from __future__ import annotations

from django.test import TestCase

from .factories import UserFactory, InternalChatFactory, ChatParticipantFactory
from .. import services
from ..exceptions import ChatAccessDeniedError
from ..models import UserStory, StoryView


class TestViewStoryScoping(TestCase):
    def setUp(self):
        self.owner = UserFactory()
        self.contact = UserFactory()
        self.stranger = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=self.owner)
        ChatParticipantFactory(chat=chat, user=self.contact)

        from django.utils import timezone
        from datetime import timedelta
        self.story = UserStory.objects.create(
            user=self.owner,
            story_type="text",
            content="hello",
            expires_at=timezone.now() + timedelta(hours=24),
            is_active=True,
        )

    def test_contact_can_view_story(self):
        view = services.view_story(story_id=self.story.id, viewer_id=self.contact.id)
        self.assertIsNotNone(view)
        self.assertEqual(StoryView.objects.count(), 1)

    def test_owner_can_view_own_story(self):
        view = services.view_story(story_id=self.story.id, viewer_id=self.owner.id)
        self.assertIsNotNone(view)

    def test_stranger_cannot_view_story(self):
        with self.assertRaises(ChatAccessDeniedError):
            services.view_story(story_id=self.story.id, viewer_id=self.stranger.id)
        self.assertEqual(StoryView.objects.count(), 0)
