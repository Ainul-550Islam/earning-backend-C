import random
import logging
from django.db import transaction
from django.utils import timezone
from ...models import SmartLink, SmartLinkVersion, ABTestResult
from ...choices import ABTestStatus
from ...exceptions import ABTestConfigError
from ...constants import AB_TEST_MIN_SAMPLE_SIZE, AB_TEST_CONFIDENCE_LEVEL, AB_TEST_MAX_VARIANTS

logger = logging.getLogger('smartlink.ab_test')


class ABTestService:
    """
    Split traffic between SmartLink variants for A/B testing.
    Evaluates statistical significance and determines winner.
    """

    def select_variant(self, smartlink: SmartLink, request_context: dict = None):
        """
        Select a SmartLink version for this request based on traffic split.
        Returns the selected SmartLinkVersion, or None to use default routing.
        """
        if not smartlink.enable_ab_test:
            return None

        versions = list(
            smartlink.versions.filter(is_active=True, is_winner=False).order_by('id')
        )
        if not versions:
            return None

        # Total split must sum to ~100
        total_split = sum(v.traffic_split for v in versions)
        if total_split == 0:
            return None

        rand = random.uniform(0, total_split)
        cumulative = 0
        for version in versions:
            cumulative += version.traffic_split
            if rand <= cumulative:
                return version

        return versions[-1]

    @transaction.atomic
    def create_test(self, smartlink: SmartLink, variants: list) -> list:
        """
        Set up an A/B test with multiple variants.

        Args:
            variants: [
                {'name': 'Control', 'traffic_split': 50, 'is_control': True},
                {'name': 'Variant A', 'traffic_split': 50},
            ]
        """
        if len(variants) < 2:
            raise ABTestConfigError("A/B test requires at least 2 variants.")
        if len(variants) > AB_TEST_MAX_VARIANTS:
            raise ABTestConfigError(f"Maximum {AB_TEST_MAX_VARIANTS} variants allowed.")

        total_split = sum(v.get('traffic_split', 0) for v in variants)
        if total_split != 100:
            raise ABTestConfigError(f"Variant traffic splits must sum to 100. Got: {total_split}")

        # Deactivate existing versions
        smartlink.versions.update(is_active=False)

        created_versions = []
        for v in variants:
            version = SmartLinkVersion.objects.create(
                smartlink=smartlink,
                name=v['name'],
                description=v.get('description', ''),
                traffic_split=v['traffic_split'],
                is_control=v.get('is_control', False),
                is_active=True,
            )
            created_versions.append(version)

        # Enable A/B test on SmartLink
        smartlink.enable_ab_test = True
        smartlink.save(update_fields=['enable_ab_test', 'updated_at'])

        # Create result tracking record
        control = next((v for v in created_versions if v.is_control), created_versions[0])
        ABTestResult.objects.create(
            smartlink=smartlink,
            status=ABTestStatus.RUNNING,
            control_version=control,
            started_at=timezone.now(),
        )

        logger.info(f"A/B test created for [{smartlink.slug}] with {len(created_versions)} variants")
        return created_versions

    def evaluate_significance(self, result: ABTestResult) -> dict:
        """
        Evaluate statistical significance of an A/B test.
        Uses chi-square test for conversion rate comparison.
        Returns updated result dict with p_value, confidence, winner.
        """
        from scipy import stats

        control = result.control_version
        versions = list(result.smartlink.versions.filter(is_active=True).exclude(pk=control.pk))

        if not versions:
            return {'significant': False, 'reason': 'no variants'}

        # Compare each variant vs control
        best_variant = None
        best_uplift = 0

        for variant in versions:
            if control.clicks < AB_TEST_MIN_SAMPLE_SIZE or variant.clicks < AB_TEST_MIN_SAMPLE_SIZE:
                continue

            # Chi-square test for conversion rate difference
            control_failures = control.clicks - control.conversions
            variant_failures = variant.clicks - variant.conversions

            if control_failures < 0 or variant_failures < 0:
                continue

            contingency_table = [
                [control.conversions, control_failures],
                [variant.conversions, variant_failures],
            ]

            try:
                chi2, p_value, _, _ = stats.chi2_contingency(contingency_table)
                confidence = 1 - p_value

                control_cr = control.conversions / control.clicks if control.clicks else 0
                variant_cr = variant.conversions / variant.clicks if variant.clicks else 0
                uplift = ((variant_cr - control_cr) / control_cr * 100) if control_cr > 0 else 0

                if confidence >= AB_TEST_CONFIDENCE_LEVEL and uplift > best_uplift:
                    best_variant = variant
                    best_uplift = uplift
                    best_p = p_value
                    best_confidence = confidence
                    best_control_cr = control_cr
                    best_variant_cr = variant_cr

            except Exception as e:
                logger.warning(f"Chi-square test failed for variant {variant.pk}: {e}")
                continue

        if best_variant:
            result.winner_version = best_variant
            result.confidence_level = best_confidence
            result.uplift_percent = round(best_uplift, 2)
            result.p_value = best_p
            result.control_cr = best_control_cr
            result.winner_cr = best_variant_cr
            result.control_clicks = control.clicks
            result.winner_clicks = best_variant.clicks
            result.status = ABTestStatus.WINNER_FOUND
            result.completed_at = timezone.now()
            result.save()

            logger.info(
                f"A/B test winner found: [{result.smartlink.slug}] "
                f"variant={best_variant.name} uplift={best_uplift:.2f}% "
                f"confidence={best_confidence:.3f}"
            )
            return {
                'significant': True,
                'winner': best_variant,
                'uplift': best_uplift,
                'confidence': best_confidence,
                'p_value': best_p,
            }

        return {'significant': False, 'reason': 'insufficient data or no winner'}

    def apply_winner(self, result: ABTestResult):
        """
        Apply the A/B test winner to the SmartLink's main rotation.
        Marks winner version, deactivates others, disables A/B test mode.
        """
        if not result.winner_version:
            raise ABTestConfigError("No winner determined yet.")

        winner = result.winner_version
        winner.is_winner = True
        winner.save(update_fields=['is_winner', 'updated_at'])

        # Deactivate losing variants
        result.smartlink.versions.exclude(pk=winner.pk).update(is_active=False)

        # Disable A/B test mode
        result.smartlink.enable_ab_test = False
        result.smartlink.save(update_fields=['enable_ab_test', 'updated_at'])

        result.auto_applied = True
        result.save(update_fields=['auto_applied', 'updated_at'])

        logger.info(
            f"A/B test winner applied: [{result.smartlink.slug}] "
            f"winner={winner.name}"
        )

    def record_click(self, version: SmartLinkVersion):
        """Increment click counter for a version (thread-safe)."""
        from django.db.models import F
        SmartLinkVersion.objects.filter(pk=version.pk).update(clicks=F('clicks') + 1)

    def record_conversion(self, version: SmartLinkVersion, revenue: float = 0):
        """Increment conversion counter for a version."""
        from django.db.models import F
        SmartLinkVersion.objects.filter(pk=version.pk).update(
            conversions=F('conversions') + 1,
            revenue=F('revenue') + revenue,
        )
