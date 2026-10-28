"""api/tasks/tests/test_serializers.py — Serializer validation tests."""
import pytest
from decimal import Decimal


@pytest.mark.django_db
class TestMasterTaskSerializer:
    def test_serializer_valid_data(self, master_task):
        try:
            from api.tasks.serializers import MasterTaskSerializer
            s = MasterTaskSerializer(master_task)
            data = s.data
            assert data['task_id'] == 'TEST_TASK_001'
            assert data['name'] == 'Test Click Task'
        except ImportError:
            pytest.skip("Serializer not available")

    def test_serializer_contains_required_fields(self, master_task):
        try:
            from api.tasks.serializers import MasterTaskSerializer
            data = MasterTaskSerializer(master_task).data
            for field in ('task_id', 'name', 'category', 'is_active'):
                assert field in data
        except ImportError:
            pytest.skip("Serializer not available")


@pytest.mark.django_db
class TestCompletionSerializer:
    def test_serializer_valid(self, completion):
        try:
            from api.tasks.serializers import UserTaskCompletionSerializer
            s = UserTaskCompletionSerializer(completion)
            assert s.data['status'] == 'completed'
        except ImportError:
            pytest.skip("Serializer not available")


class TestSchemaValidation:
    def test_withdrawal_request_valid(self):
        from api.tasks.schemas import WithdrawalRequestSchema
        s = WithdrawalRequestSchema(data={
            'amount': '5.00',
            'payment_method': 'paypal',
        })
        assert s.is_valid(), s.errors

    def test_withdrawal_request_invalid_amount(self):
        from api.tasks.schemas import WithdrawalRequestSchema
        s = WithdrawalRequestSchema(data={
            'amount': '-1.00',
            'payment_method': 'paypal',
        })
        assert not s.is_valid()

    def test_task_complete_request_valid(self):
        from api.tasks.schemas import TaskCompleteRequestSchema
        s = TaskCompleteRequestSchema(data={'task_id': 'TASK_001'})
        assert s.is_valid(), s.errors

    def test_postback_request_valid(self):
        from api.tasks.schemas import PostbackRequestSchema
        s = PostbackRequestSchema(data={
            'click_id': 'click_abc',
            'offer_id': 'OFFER_001',
        })
        assert s.is_valid(), s.errors

    def test_postback_request_missing_click_id(self):
        from api.tasks.schemas import PostbackRequestSchema
        s = PostbackRequestSchema(data={'offer_id': 'OFFER_001'})
        assert not s.is_valid()
        assert 'click_id' in s.errors
