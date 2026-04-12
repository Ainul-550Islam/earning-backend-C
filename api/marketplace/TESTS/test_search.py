"""TESTS/test_search.py — Search Engine Tests (ORM fallback)"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from api.tenants.models import Tenant
from api.marketplace.models import Category, Product
from api.marketplace.SEARCH_DISCOVERY.search_engine import SearchEngine
from api.marketplace.SELLER_MANAGEMENT.seller_profile import create_seller_profile

User = get_user_model()

class SearchTest(TestCase):
    def setUp(self):
        self.tenant  = Tenant.objects.create(name="Search T", slug="st", domain="st.localhost")
        su           = User.objects.create_user(username="seller_s", password="pass")
        self.seller  = create_seller_profile(su, self.tenant, "Search Store", "+8801700000013")
        self.cat     = Category.objects.create(tenant=self.tenant, name="Electronics", slug="elec-s")
        for i, name in enumerate(["Samsung Galaxy", "iPhone 15", "OnePlus 12", "Xiaomi 14"]):
            Product.objects.create(
                tenant=self.tenant, seller=self.seller, category=self.cat,
                name=name, slug=f"phone-{i}", description=f"A great phone: {name}",
                base_price=Decimal(str(20000 + i * 5000)), status="active",
            )

    def test_text_search(self):
        engine  = SearchEngine(self.tenant)
        results = engine.search("samsung")
        self.assertEqual(results.engine, "django_orm")
        self.assertEqual(results.total, 1)

    def test_price_filter(self):
        engine  = SearchEngine(self.tenant)
        results = engine.search(filters={"min_price": 25000, "max_price": 35000})
        self.assertGreater(results.total, 0)

    def test_autocomplete(self):
        engine = SearchEngine(self.tenant)
        suggestions = engine.autocomplete("sam")
        self.assertIn("Samsung Galaxy", suggestions)

    def test_sort_by_price(self):
        engine  = SearchEngine(self.tenant)
        results = engine.search(sort_by="price_asc")
        prices  = [p.base_price for p in results.products]
        self.assertEqual(prices, sorted(prices))
