"""TESTS/test_performance.py — Performance & Load Tests (conceptual)"""
import time
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from api.tenants.models import Tenant
from api.marketplace.models import Category, Product
from api.marketplace.SELLER_MANAGEMENT.seller_profile import create_seller_profile

User = get_user_model()


class PerformanceTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Perf T", slug="pft", domain="pft.localhost")
        su          = User.objects.create_user(username="perf_seller", password="pass")
        self.seller = create_seller_profile(su, self.tenant, "Perf Store", "+8801700000014")
        self.cat    = Category.objects.create(tenant=self.tenant, name="Perf Cat", slug="perf-cat")
        # Create 100 products for query performance
        Product.objects.bulk_create([
            Product(
                tenant=self.tenant, seller=self.seller, category=self.cat,
                name=f"Product {i}", slug=f"perf-prod-{i}",
                description="Perf test", base_price=Decimal("100"),
                status="active",
            )
            for i in range(100)
        ])

    def test_product_list_query_time(self):
        start = time.monotonic()
        products = list(Product.objects.filter(tenant=self.tenant, status="active")
                        .select_related("category", "seller")[:50])
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 1.0, "Product list query should complete in <1s")
        self.assertEqual(len(products), 50)

    def test_search_engine_response_time(self):
        from api.marketplace.SEARCH_DISCOVERY.search_engine import SearchEngine
        engine  = SearchEngine(self.tenant)
        start   = time.monotonic()
        results = engine.search("Product")
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 2.0, "Search should complete in <2s")
        self.assertGreater(results.total, 0)
