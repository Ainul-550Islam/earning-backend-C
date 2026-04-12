"""TESTS/test_products.py — Product model & API tests"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from api.tenants.models import Tenant
from api.marketplace.models import Category, Product, ProductVariant, ProductInventory
from api.marketplace.SELLER_MANAGEMENT.seller_profile import create_seller_profile

User = get_user_model()


class CategoryModelTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test", domain="test.localhost")

    def test_category_level_auto_set(self):
        root = Category.objects.create(tenant=self.tenant, name="Electronics", slug="electronics")
        child = Category.objects.create(tenant=self.tenant, name="Mobile", slug="mobile", parent=root)
        self.assertEqual(root.level, 0)
        self.assertEqual(child.level, 1)

    def test_category_full_path(self):
        root = Category.objects.create(tenant=self.tenant, name="Electronics", slug="electronics")
        child = Category.objects.create(tenant=self.tenant, name="Mobile", slug="mobile", parent=root)
        self.assertEqual(child.full_path, "Electronics > Mobile")


class ProductModelTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant 2", slug="test2", domain="test2.localhost")
        self.user = User.objects.create_user(username="seller1", password="pass123")
        self.seller = create_seller_profile(self.user, self.tenant, "My Store", "+8801700000000")
        self.category = Category.objects.create(tenant=self.tenant, name="Clothing", slug="clothing")

    def test_product_effective_price_with_sale(self):
        product = Product.objects.create(
            tenant=self.tenant, seller=self.seller, category=self.category,
            name="T-Shirt", slug="t-shirt", description="Nice shirt",
            base_price=500, sale_price=400, status="active",
        )
        self.assertEqual(product.effective_price, 400)

    def test_product_effective_price_without_sale(self):
        product = Product.objects.create(
            tenant=self.tenant, seller=self.seller, category=self.category,
            name="Jeans", slug="jeans", description="Blue jeans",
            base_price=1200, status="active",
        )
        self.assertEqual(product.effective_price, 1200)

    def test_product_discount_percent(self):
        product = Product.objects.create(
            tenant=self.tenant, seller=self.seller, category=self.category,
            name="Jacket", slug="jacket", description="Warm jacket",
            base_price=2000, sale_price=1500, status="active",
        )
        self.assertEqual(product.discount_percent, 25.0)
