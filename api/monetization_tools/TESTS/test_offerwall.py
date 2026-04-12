"""TESTS/test_offerwall.py - Offerwall module tests."""
from decimal import Decimal
from ..OFFERWALL_SPECIFIC.offer_sorter import OfferSorter
from ..OFFERWALL_SPECIFIC.offer_filter import OfferFilter
from ..OFFERWALL_SPECIFIC.offer_priority import OfferPriorityRanker


class MockOffer:
    def __init__(self, id, point_value, is_featured=False, is_hot=False,
                  target_countries=None, offer_type="survey"):
        self.id = id
        self.point_value = point_value
        self.is_featured = is_featured
        self.is_hot = is_hot
        self.target_countries = target_countries or []
        self.offer_type = offer_type
        self.expiry_date = None


class TestOfferSorter:
    def test_featured_first(self):
        offers = [MockOffer(1, 100), MockOffer(2, 200, is_featured=True)]
        result = OfferSorter.sort(offers)
        assert result[0].id == 2

    def test_paginate(self):
        offers = [MockOffer(i, i * 10) for i in range(25)]
        page   = OfferSorter.paginate(offers, page=2, per_page=10)
        assert page["page"] == 2
        assert len(page["results"]) == 10
        assert page["total"] == 25


class TestOfferFilter:
    def test_by_country_no_restriction(self):
        offers = [MockOffer(1, 100, target_countries=[]), MockOffer(2, 200, target_countries=["BD"])]
        result = OfferFilter.by_country(offers, "BD")
        assert len(result) == 2

    def test_by_type(self):
        offers = [MockOffer(1, 100, offer_type="survey"), MockOffer(2, 200, offer_type="install")]
        result = OfferFilter.by_type(offers, "survey")
        assert len(result) == 1


class TestOfferPriorityRanker:
    def test_rank_returns_same_count(self):
        offers = [MockOffer(i, i * 50) for i in range(10)]
        ranked = OfferPriorityRanker.rank(offers)
        assert len(ranked) == 10
