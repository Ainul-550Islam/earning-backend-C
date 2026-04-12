"""TESTS/test_reviews.py — Review & Rating Tests"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from api.tenants.models import Tenant
from api.marketplace.models import Category, Product, ProductReview
from api.marketplace.SELLER_MANAGEMENT.seller_profile import create_seller_profile
from api.marketplace.REVIEW_RATING.rating_calculator import product_rating_stats
from api.marketplace.REVIEW_RATING.review_moderation import auto_moderate_review

User = get_user_model()

class ReviewTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Review T", slug="rt", domain="rt.localhost")
        self.user   = User.objects.create_user(username="reviewer", password="pass")
        su          = User.objects.create_user(username="seller_rv", password="pass")
        self.seller = create_seller_profile(su, self.tenant, "RV Store", "+8801700000012")
        self.cat    = Category.objects.create(tenant=self.tenant, name="Books", slug="books-rv")
        self.product= Product.objects.create(
            tenant=self.tenant, seller=self.seller, category=self.cat,
            name="Python Book", slug="python-book-rv", description="Python",
            base_price=Decimal("300.00"), status="active",
        )

    def test_create_review(self):
        review = ProductReview.objects.create(
            tenant=self.tenant, product=self.product, user=self.user,
            rating=5, title="Great!", body="Excellent book.",
        )
        self.assertEqual(review.rating, 5)
        self.assertTrue(review.is_approved)

    def test_rating_stats(self):
        for r in [5, 5, 4, 3]:
            ProductReview.objects.create(
                tenant=self.tenant, product=self.product,
                user=self.user, rating=r, body="Review",
            )
        stats = product_rating_stats(self.product)
        self.assertEqual(stats["total"], 4)
        self.assertAlmostEqual(stats["average"], 4.25, places=1)

    def test_auto_moderation_flags_spam(self):
        review = ProductReview.objects.create(
            tenant=self.tenant, product=self.product, user=self.user,
            rating=1, body="Contact on whatsapp +8801700000099 for better deal",
        )
        result = auto_moderate_review(review)
        self.assertFalse(result["clean"])
