# api/wallet/tests/test_survey_router.py
"""Tests for SurveyRouter — survey routing, targeting, and completion payouts."""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


def _make_user(username):
    return User.objects.create_user(username=username, password="pass",
                                    email=f"{username}@test.com")


def _make_wallet(user):
    from ..services import WalletService
    return WalletService.get_or_create(user)


def _make_provider(**kwargs):
    from ..survey_router import SurveyProvider
    return SurveyProvider.objects.create(
        name=kwargs.get("name", "TestProvider"),
        api_endpoint=kwargs.get("api_endpoint", "https://surveys.example.com/api"),
        payout_rate=kwargs.get("payout_rate", Decimal("1.00")),
        is_active=kwargs.get("is_active", True),
        priority=kwargs.get("priority", 50),
    )


def _make_survey(provider, **kwargs):
    from ..survey_router import Survey
    return Survey.objects.create(
        provider=provider,
        external_id=kwargs.get("external_id", "EXT001"),
        title=kwargs.get("title", "Test Survey"),
        survey_url=kwargs.get("survey_url", "https://surveys.example.com/take/001"),
        payout_amount=kwargs.get("payout_amount", Decimal("2.50")),
        target_country=kwargs.get("target_country", "BD"),
        estimated_mins=kwargs.get("estimated_mins", 5),
        status=kwargs.get("status", Survey.STATUS_ACTIVE),
        quota=kwargs.get("quota", 0),
    )


class SurveyModelTest(TestCase):

    def setUp(self):
        self.provider = _make_provider()

    def test_survey_is_available_active(self):
        from ..survey_router import Survey
        survey = _make_survey(self.provider)
        self.assertTrue(survey.is_available)

    def test_survey_is_not_available_when_paused(self):
        from ..survey_router import Survey
        survey = _make_survey(self.provider, status=Survey.STATUS_PAUSED)
        self.assertFalse(survey.is_available)

    def test_survey_not_available_when_quota_full(self):
        from ..survey_router import Survey
        survey = _make_survey(self.provider, quota=10)
        survey.completions = 10
        survey.save()
        self.assertFalse(survey.is_available)

    def test_ecpm_calculation(self):
        from ..survey_router import Survey
        survey = _make_survey(self.provider,
                              payout_amount=Decimal("5.00"),
                              estimated_mins=10)
        # ecpm = (5.00 / 10) * 1000 = 500
        self.assertEqual(survey.ecpm, Decimal("500.00"))

    def test_ecpm_higher_payout_ranked_first(self):
        from ..survey_router import Survey
        high = _make_survey(self.provider, external_id="HIGH",
                            payout_amount=Decimal("10.00"), estimated_mins=5)
        low  = _make_survey(self.provider, external_id="LOW",
                            payout_amount=Decimal("1.00"),  estimated_mins=5)
        self.assertGreater(high.ecpm, low.ecpm)


class SurveyRouterTest(TestCase):

    def setUp(self):
        self.user     = _make_user("survey_user")
        self.wallet   = _make_wallet(self.user)
        self.provider = _make_provider()

    def test_get_surveys_for_user_returns_available(self):
        from ..survey_router import SurveyRouter
        _make_survey(self.provider, external_id="S1")
        _make_survey(self.provider, external_id="S2", payout_amount=Decimal("5.00"))
        surveys = SurveyRouter.get_surveys_for_user(
            self.user, self.wallet, country_code="BD"
        )
        self.assertEqual(len(surveys), 2)

    def test_surveys_ranked_by_ecpm_descending(self):
        from ..survey_router import SurveyRouter
        _make_survey(self.provider, external_id="LOW",
                     payout_amount=Decimal("1.00"), estimated_mins=10)
        _make_survey(self.provider, external_id="HIGH",
                     payout_amount=Decimal("10.00"), estimated_mins=2)
        surveys = SurveyRouter.get_surveys_for_user(
            self.user, self.wallet, country_code="BD"
        )
        ecpms = [Decimal(s["ecpm"]) for s in surveys]
        self.assertEqual(ecpms, sorted(ecpms, reverse=True))

    def test_completed_surveys_excluded(self):
        from ..survey_router import SurveyRouter, SurveyAttempt
        survey = _make_survey(self.provider, external_id="DONE")
        SurveyAttempt.objects.create(
            survey=survey, user=self.user, wallet=self.wallet,
            result=SurveyAttempt.RESULT_COMPLETED,
        )
        surveys = SurveyRouter.get_surveys_for_user(
            self.user, self.wallet, country_code="BD"
        )
        survey_ids = [s["survey_id"] for s in surveys]
        self.assertNotIn(str(survey.survey_id), survey_ids)

    def test_start_attempt_creates_record(self):
        from ..survey_router import SurveyRouter, SurveyAttempt
        survey = _make_survey(self.provider, external_id="START1")
        result = SurveyRouter.start_attempt(
            str(survey.survey_id), self.user, self.wallet
        )
        self.assertIn("attempt_id", result)
        self.assertTrue(
            SurveyAttempt.objects.filter(
                survey=survey, user=self.user,
                result=SurveyAttempt.RESULT_STARTED,
            ).exists()
        )

    def test_start_attempt_invalid_survey_raises(self):
        from ..survey_router import SurveyRouter
        with self.assertRaises(ValueError):
            SurveyRouter.start_attempt(
                "00000000-0000-0000-0000-000000000000",
                self.user, self.wallet,
            )

    @patch("api.wallet.survey_router.SurveyRouter.complete")
    def test_complete_credits_wallet(self, mock_complete):
        from ..survey_router import SurveyRouter, SurveyAttempt
        mock_complete.return_value = {
            "credited": True, "amount": "2.50",
            "txn_id": "TXN001", "result": "completed",
        }
        survey  = _make_survey(self.provider, external_id="COMP1")
        attempt = SurveyAttempt.objects.create(
            survey=survey, user=self.user, wallet=self.wallet,
            result=SurveyAttempt.RESULT_STARTED,
        )
        result = SurveyRouter.complete(str(attempt.attempt_id))
        self.assertTrue(result["credited"])

    def test_complete_disqualified_does_not_credit(self):
        from ..survey_router import SurveyRouter, SurveyAttempt
        survey  = _make_survey(self.provider, external_id="DQ1")
        attempt = SurveyAttempt.objects.create(
            survey=survey, user=self.user, wallet=self.wallet,
            result=SurveyAttempt.RESULT_STARTED,
        )
        result = SurveyRouter.complete(
            str(attempt.attempt_id),
            result=SurveyAttempt.RESULT_DISQUALIFIED,
        )
        self.assertFalse(result["credited"])

    def test_country_filter_excludes_wrong_country(self):
        from ..survey_router import SurveyRouter, Survey
        _make_survey(self.provider, external_id="US_ONLY",
                     target_country="US", payout_amount=Decimal("10.00"))
        _make_survey(self.provider, external_id="BD_ONLY",
                     target_country="BD", payout_amount=Decimal("5.00"))
        surveys = SurveyRouter.get_surveys_for_user(
            self.user, self.wallet, country_code="BD"
        )
        # Should include BD_ONLY and exclude US_ONLY
        titles = [s["title"] for s in surveys]
        self.assertNotIn("Test Survey", [t for t in titles if "US" in t])
