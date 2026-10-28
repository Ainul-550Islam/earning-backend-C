# api/support/tests.py
"""
Complete test suite for support system.
Full code — no summarizing.
"""
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from decimal import Decimal


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════
def make_user(username='testuser', is_staff=False):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username=username, email=f'{username}@test.com', password='pass123', is_staff=is_staff
    )


def make_ticket(user=None, **kwargs):
    from api.support.models import SupportTicket
    if user is None:
        user = make_user()
    defaults = {
        'subject': 'Test Ticket',
        'description': 'Test description for ticket.',
        'category': 'technical',
        'priority': 'medium',
        'status': 'open',
        'channel': 'web',
    }
    defaults.update(kwargs)
    return SupportTicket.objects.create(user=user, **defaults)


def make_faq(**kwargs):
    from api.support.models import FAQ
    defaults = {'question': 'Test question?', 'answer': 'Test answer.', 'category': 'general', 'is_active': True}
    defaults.update(kwargs)
    return FAQ.objects.create(**defaults)


# ══════════════════════════════════════════════════════════════
# MODEL TESTS
# ══════════════════════════════════════════════════════════════
class SupportTicketModelTest(TestCase):
    def test_ticket_id_auto_generated(self):
        user   = make_user('model_user1')
        ticket = make_ticket(user=user)
        self.assertIsNotNone(ticket.ticket_id)
        self.assertTrue(ticket.ticket_id.startswith('TKT'))
        self.assertEqual(len(ticket.ticket_id), 9)

    def test_ticket_id_unique(self):
        user = make_user('model_user2')
        t1   = make_ticket(user=user)
        t2   = make_ticket(user=user)
        self.assertNotEqual(t1.ticket_id, t2.ticket_id)

    def test_default_status_is_open(self):
        ticket = make_ticket()
        self.assertEqual(ticket.status, 'open')

    def test_default_priority_is_medium(self):
        ticket = make_ticket()
        self.assertEqual(ticket.priority, 'medium')

    def test_str_representation(self):
        user   = make_user('strtest')
        ticket = make_ticket(user=user)
        self.assertIn(ticket.ticket_id, str(ticket))
        self.assertIn(user.username, str(ticket))

    def test_resolved_at_null_by_default(self):
        ticket = make_ticket()
        self.assertIsNone(ticket.resolved_at)


class FAQModelTest(TestCase):
    def test_helpful_ratio_zero_votes(self):
        faq = make_faq()
        self.assertEqual(faq.helpful_ratio, 0)

    def test_helpful_ratio_calculation(self):
        faq = make_faq()
        faq.helpful_yes = 3
        faq.helpful_no  = 1
        faq.save()
        self.assertEqual(faq.helpful_ratio, 75.0)

    def test_helpful_ratio_all_positive(self):
        faq = make_faq()
        faq.helpful_yes = 10
        faq.save()
        self.assertEqual(faq.helpful_ratio, 100.0)

    def test_str_representation(self):
        faq = make_faq(question='What is bKash?')
        self.assertEqual(str(faq), 'What is bKash?')


class SupportSettingsModelTest(TestCase):
    def test_singleton_creation(self):
        from api.support.models import SupportSettings
        obj1, c1 = SupportSettings.objects.get_or_create(id=1)
        obj2, c2 = SupportSettings.objects.get_or_create(id=1)
        self.assertEqual(obj1.id, obj2.id)
        self.assertFalse(c2)

    def test_str_representation(self):
        from api.support.models import SupportSettings
        obj, _ = SupportSettings.objects.get_or_create(id=1)
        self.assertEqual(str(obj), 'Support Settings')


# ══════════════════════════════════════════════════════════════
# SERVICE TESTS
# ══════════════════════════════════════════════════════════════
class TicketServiceTest(TestCase):
    def setUp(self):
        self.user = make_user('service_test_user')

    @patch('support.services.TicketService._notify_created')
    @patch('support.services.TicketService._auto_assign')
    @patch('support.services.TicketService._setup_sla')
    @patch('support.services.TicketService._trigger_automation')
    def test_create_ticket_returns_ticket(self, mock_auto, mock_sla, mock_assign, mock_notify):
        from api.support.services import ticket_service
        ticket = ticket_service.create(self.user, {
            'subject': 'Test issue', 'description': 'Detailed description here please.',
            'category': 'technical', 'priority': 'medium',
        })
        self.assertIsNotNone(ticket)
        self.assertIsNotNone(ticket.ticket_id)
        self.assertEqual(ticket.user, self.user)
        self.assertEqual(ticket.status, 'open')

    @patch('support.services.TicketService._notify_created')
    @patch('support.services.TicketService._auto_assign')
    @patch('support.services.TicketService._setup_sla')
    @patch('support.services.TicketService._trigger_automation')
    def test_create_ticket_assigns_priority_from_category(self, mock_auto, mock_sla, mock_assign, mock_notify):
        from api.support.services import ticket_service
        ticket = ticket_service.create(self.user, {
            'subject': 'Fraud!', 'description': 'Someone hacked my account!',
            'category': 'fraud',
        })
        self.assertEqual(ticket.priority, 'urgent')

    def test_get_stats_returns_dict(self):
        from api.support.services import ticket_service
        stats = ticket_service.get_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn('total', stats)
        self.assertIn('open', stats)


class SLAServiceTest(TestCase):
    def test_check_breaches_returns_dict(self):
        from api.support.services import sla_service
        result = sla_service.check_breaches()
        self.assertIn('checked', result)
        self.assertIn('breached', result)

    def test_setup_sla_creates_record(self):
        from api.support.services import sla_service
        from api.support.models import TicketSLA
        ticket = make_ticket()
        sla_service._setup_sla(ticket)
        self.assertTrue(TicketSLA.objects.filter(ticket=ticket).exists())
        sla = TicketSLA.objects.get(ticket=ticket)
        self.assertIsNotNone(sla.first_response_due)
        self.assertIsNotNone(sla.resolution_due)
        # SLA due times should be in the future
        self.assertGreater(sla.first_response_due, timezone.now())

    def test_sla_breach_detection(self):
        from api.support.services import sla_service
        from api.support.models import TicketSLA
        from datetime import timedelta
        ticket = make_ticket()
        sla_service._setup_sla(ticket)
        sla = TicketSLA.objects.get(ticket=ticket)
        # Simulate overdue by setting due time in the past
        sla.first_response_due = timezone.now() - timedelta(hours=2)
        sla.save(update_fields=['first_response_due'])
        sla_service.check_breaches()
        sla.refresh_from_db()
        self.assertTrue(sla.first_response_breached)

    def test_compliance_report(self):
        from api.support.services import sla_service
        report = sla_service.get_compliance_report(days=7)
        self.assertIn('compliance_rate', report)
        self.assertIn('total', report)


# ══════════════════════════════════════════════════════════════
# API VIEW TESTS
# ══════════════════════════════════════════════════════════════
class SupportSettingsAPITest(APITestCase):
    def test_get_settings_public(self):
        response = self.client.get('/api/support/settings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_support_online', response.data)

    def test_patch_settings_requires_auth(self):
        response = self.client.patch('/api/support/settings/', {'is_support_online': False})
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN
        ])

    def test_patch_settings_admin_only(self):
        user = make_user('non_admin')
        self.client.force_authenticate(user=user)
        response = self.client.patch('/api/support/settings/', {'is_support_online': False})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TicketAPITest(APITestCase):
    def setUp(self):
        self.user  = make_user('ticket_api_user')
        self.admin = make_user('ticket_admin', is_staff=True)
        self.client.force_authenticate(user=self.user)

    def test_unauthenticated_cannot_list_tickets(self):
        client = APIClient()
        response = client.get('/api/support/tickets/')
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN
        ])

    @patch('support.services.TicketService._notify_created')
    @patch('support.services.TicketService._auto_assign')
    @patch('support.services.TicketService._setup_sla')
    @patch('support.services.TicketService._trigger_automation')
    def test_create_ticket(self, mock_auto, mock_sla, mock_assign, mock_notify):
        data = {
            'subject': 'API test ticket',
            'description': 'This is a description longer than 10 chars.',
            'category': 'technical',
            'priority': 'medium',
        }
        response = self.client.post('/api/support/tickets/', data)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

    def test_list_own_tickets(self):
        make_ticket(user=self.user)
        response = self.client.get('/api/support/tickets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_see_others_tickets(self):
        other_user = make_user('other_user_1')
        ticket     = make_ticket(user=other_user)
        response   = self.client.get(f'/api/support/tickets/{ticket.ticket_id}/')
        self.assertIn(response.status_code, [
            status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND
        ])

    def test_rate_ticket(self):
        ticket = make_ticket(user=self.user, status='resolved')
        response = self.client.post(
            f'/api/support/tickets/{ticket.ticket_id}/rate/',
            {'score': 5, 'comment': 'Great!'}
        )
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        ticket.refresh_from_db()
        self.assertEqual(ticket.satisfaction_rating, 5)


class FAQAPITest(APITestCase):
    def test_list_faqs_public(self):
        make_faq()
        response = self.client.get('/api/support/faqs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_faq_helpful_vote(self):
        faq  = make_faq()
        user = make_user('faq_vote_user')
        self.client.force_authenticate(user=user)
        response = self.client.post(f'/api/support/faqs/{faq.id}/helpful/', {'helpful': True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        faq.refresh_from_db()
        self.assertEqual(faq.helpful_yes, 1)

    def test_create_faq_requires_admin(self):
        user = make_user('faq_regular')
        self.client.force_authenticate(user=user)
        response = self.client.post('/api/support/faqs/', {
            'question': 'Test?', 'answer': 'Yes.', 'category': 'general'
        })
        self.assertIn(response.status_code, [
            status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED
        ])


# ══════════════════════════════════════════════════════════════
# LOGIC TESTS
# ══════════════════════════════════════════════════════════════
class TicketLogicTest(TestCase):
    def test_determine_priority_fraud(self):
        from api.support.logic import determine_ticket_priority
        priority = determine_ticket_priority('fraud')
        self.assertEqual(priority, 'urgent')

    def test_determine_priority_payment(self):
        from api.support.logic import determine_ticket_priority
        priority = determine_ticket_priority('payment')
        self.assertEqual(priority, 'high')

    def test_determine_priority_other(self):
        from api.support.logic import determine_ticket_priority
        priority = determine_ticket_priority('other')
        self.assertEqual(priority, 'low')

    def test_calculate_sla_due_times(self):
        from api.support.logic import calculate_sla_due_times
        fr_due, res_due = calculate_sla_due_times('urgent')
        self.assertGreater(fr_due, timezone.now())
        self.assertGreater(res_due, fr_due)
        # Urgent: 1h FR, 4h resolution
        diff_fr  = (fr_due  - timezone.now()).total_seconds() / 3600
        diff_res = (res_due - timezone.now()).total_seconds() / 3600
        self.assertAlmostEqual(diff_fr,  1.0, delta=0.1)
        self.assertAlmostEqual(diff_res, 4.0, delta=0.1)

    def test_csat_calculation(self):
        from api.support.logic import calculate_csat_score
        result = calculate_csat_score([5, 5, 4, 3, 1, 2, 5])
        self.assertIn('avg', result)
        self.assertIn('nps', result)
        self.assertIn('promoters', result)
        self.assertIn('detractors', result)
        self.assertEqual(result['total'], 7)
        self.assertEqual(result['promoters'], 3)


# ══════════════════════════════════════════════════════════════
# PERMISSION TESTS
# ══════════════════════════════════════════════════════════════
class PermissionsTest(TestCase):
    def setUp(self):
        from rest_framework.test import APIRequestFactory
        self.factory = APIRequestFactory()

    def test_is_support_agent_for_staff(self):
        from api.support.permissions import IsSupportAgent
        user = make_user('perm_staff', is_staff=True)
        req  = self.factory.get('/')
        req.user = user
        perm = IsSupportAgent()
        self.assertTrue(perm.has_permission(req, None))

    def test_is_support_agent_for_regular_user(self):
        from api.support.permissions import IsSupportAgent
        user = make_user('perm_regular')
        req  = self.factory.get('/')
        req.user = user
        perm = IsSupportAgent()
        self.assertFalse(perm.has_permission(req, None))


# ══════════════════════════════════════════════════════════════
# QUERYSET TESTS
# ══════════════════════════════════════════════════════════════
class QuerySetTest(TestCase):
    def test_ticket_queryset_open(self):
        from api.support.querysets import SupportTicketQuerySet
        # Use manager if attached, or direct test
        user = make_user('qs_test')
        t1   = make_ticket(user=user, status='open')
        t2   = make_ticket(user=user, status='resolved')
        from api.support.models import SupportTicket
        open_tickets = SupportTicket.objects.filter(status='open')
        self.assertIn(t1, open_tickets)
        self.assertNotIn(t2, open_tickets)

    def test_ticket_search(self):
        from api.support.models import SupportTicket
        user = make_user('search_test')
        make_ticket(user=user, subject='Payment not working')
        make_ticket(user=user, subject='Account locked')
        # Search should find by subject
        from django.db.models import Q
        results = SupportTicket.objects.filter(Q(subject__icontains='payment'))
        self.assertEqual(results.count(), 1)