"""Task services stub: ab_test."""
from celery import shared_task


from celery import shared_task

class ABTestService:
    """Task-level A/B test service for background operations."""
    @staticmethod
    def evaluate_active_tests():
        from offer_routing.services import ab_test_service
        return ab_test_service.evaluate_active_tests() if ab_test_service else {}

    @staticmethod
    def check_test_duration():
        from offer_routing.services import ab_test_service
        return ab_test_service.check_test_duration() if ab_test_service else {}

# Auto-generated re-exports for task imports
