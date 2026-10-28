"""Test validate_event_type() and EventTypeValidateAPIView

Regression coverage for a correction made within Session 9 itself: an
earlier fix in the same session made validate_event_type() reject any
event_type not in EventType.choices. That was wrong - see
validators.validate_event_type()'s own docstring for the full writeup.
This file covers both the corrected validator directly and
EventTypeValidateAPIView (views.py), which had zero test coverage before
and whose own warnings-not-errors design is exactly what the earlier
over-strict fix silently made unreachable.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

from ..validators import validate_event_type
from ..constants import EventType

User = get_user_model()


class ValidateEventTypeUnitTest(SimpleTestCase):

    def test_rejects_malformed_strings(self):
        with self.assertRaises(DjangoValidationError):
            validate_event_type('not-a-valid-event-type')

    def test_rejects_empty_string(self):
        with self.assertRaises(DjangoValidationError):
            validate_event_type('')

    def test_accepts_a_real_eventtype_value(self):
        self.assertEqual(
            validate_event_type(EventType.USER_REGISTERED), EventType.USER_REGISTERED,
        )

    def test_accepts_a_well_formatted_value_not_in_eventtype(self):
        """The correction this file exists for: format-valid event types
        that aren't (yet) in EventType must still be accepted - see
        EventTypeValidateAPIViewTest below for a real-world-evidenced
        example (as of when this was written; this session kept finding
        and adding real ones, see FIXES_APPLIED_SESSION9.md, so a
        deliberately fictional value is used here instead of depending on
        some specific real value staying unregistered).
        """
        self.assertEqual(validate_event_type('custom.internal_event'), 'custom.internal_event')


class EventTypeValidateAPIViewTest(APITestCase):
    """Had zero test coverage before Session 9."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='evt_validate_user', email='evu@example.com', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('webhooks:webhook-event-type-validate')

    def test_real_eventtype_value_is_valid_with_no_warnings(self):
        response = self.client.post(self.url, {'event_type': EventType.USER_REGISTERED})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['valid'])
        self.assertEqual(response.data['warnings'], [])

    def test_well_formatted_non_predefined_value_is_valid_with_a_warning(self):
        """The specific case an earlier fix in this same session would
        have silently broken: format is fine, not in EventType.choices -
        should be valid=True with a warning, not rejected outright. Uses
        a deliberately fictional value rather than a real-but-missing one
        - this session kept finding and adding real ones (see
        FIXES_APPLIED_SESSION9.md), which would make this test increasingly
        fragile if it depended on some specific value staying unregistered.
        """
        response = self.client.post(self.url, {'event_type': 'custom.internal_event'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['valid'])
        self.assertEqual(len(response.data['warnings']), 1)
        self.assertIn('custom/internal events', response.data['warnings'][0])

    def test_malformed_value_is_invalid_with_errors(self):
        response = self.client.post(self.url, {'event_type': 'not-valid'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['valid'])
        self.assertTrue(response.data['errors'])
        self.assertEqual(response.data['warnings'], [])
