from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from decimal import Decimal
from yourapp.models import Customer, Txn, Event


class CustomerModelTest(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            code='CUST001',
            firstname='Ainul',
            lastname='Islam',
            email='ainul@example.com',
            phone='01712345678',
            city='Dhaka',
            newsletter=True
        )

    def test_str_representation(self):
        self.assertEqual(str(self.customer), '[CUST001] Ainul Islam')

    def test_str_with_no_name(self):
        """Null Object Pattern - নাম না থাকলে crash হবে না"""
        c = Customer.objects.create(code='ANON001')
        self.assertEqual(str(c), '[ANON001] ')

    def test_code_unique(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Customer.objects.create(code='CUST001')

    def test_newsletter_default_true(self):
        c = Customer.objects.create(code='NEWS001')
        self.assertTrue(c.newsletter)


class TxnModelTest(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(code='TXN001')
        self.txn = Txn.objects.create(
            customer=self.customer,
            value=Decimal('99.99'),
            is_discount=False
        )
        self.discount_txn = Txn.objects.create(
            customer=self.customer,
            value=Decimal('49.99'),
            is_discount=True
        )
        self.spending_txn = Txn.objects.create(
            customer=self.customer,
            value=Decimal('-20.00'),
            is_discount=False
        )

    def test_full_price_manager(self):
        """FullPriceTxnManager সঠিকভাবে filter করে"""
        qs = Txn.txn_full.all()
        self.assertIn(self.txn, qs)
        self.assertNotIn(self.discount_txn, qs)

    def test_discount_manager(self):
        """DiscountedTxnManager সঠিকভাবে filter করে"""
        qs = Txn.txn_discount.all()
        self.assertIn(self.discount_txn, qs)
        self.assertNotIn(self.txn, qs)

    def test_spending_manager(self):
        """SpendingTxnManager negative values filter করে"""
        qs = Txn.spending.all()
        self.assertIn(self.spending_txn, qs)
        self.assertNotIn(self.txn, qs)

    def test_str_representation(self):
        self.assertIn('99.99', str(self.txn))


class EventModelTest(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(code='EVT001')

    def test_event_with_customer(self):
        event = Event.objects.create(
            customer=self.customer,
            action='login',
            description='User logged in'
        )
        self.assertEqual(event.customer, self.customer)

    def test_anonymous_event(self):
        """Customer ছাড়া Event তৈরি হয় (Null Object Pattern)"""
        event = Event.objects.create(
            customer=None,
            action='page_view',
            description='Anonymous page view'
        )
        self.assertIsNone(event.customer)

    def test_customer_related_manager(self):
        """CustomerRelatedEvtManager anonymous events filter করে"""
        Event.objects.create(customer=self.customer, action='login')
        anon_event = Event.objects.create(customer=None, action='view')
        qs = Event.customer_related.all()
        self.assertIn(anon_event, qs)
        self.assertNotIn(
            Event.objects.filter(customer=self.customer).first(), qs
        )


class CustomerAPITest(APITestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            code='API001',
            firstname='Test',
            lastname='User',
            email='test@example.com'
        )

    def test_list_customers(self):
        url = reverse('customer-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_create_customer(self):
        url = reverse('customer-list')
        data = {'code': 'NEW001', 'firstname': 'New', 'email': 'new@test.com'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'NEW001')

    def test_create_duplicate_code_fails(self):
        url = reverse('customer-list')
        data = {'code': 'API001'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customer_stats(self):
        Txn.objects.create(customer=self.customer, value=Decimal('100.00'))
        url = reverse('customer-stats', args=[self.customer.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_transactions'], 1)

    def test_search_by_email(self):
        url = reverse('customer-list') + '?search=test@example.com'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)