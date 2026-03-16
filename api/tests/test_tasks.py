# api/tests/test_tasks.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from api.tasks.models import MasterTask, UserTaskCompletion, AdminLedger
import uuid
from decimal import Decimal

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]


class TaskModelTest(TestCase):

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username=f'u_{uid()}', 
            email=f'{uid()}@test.com', 
            password='x'
        )

    def test_create_master_task(self):
        """Test MasterTask creation - with actual model fields"""
        task = MasterTask.objects.create(
            task_id=f'TASK_{uid()}',
            name='Watch Video',
            description='Watch video to earn coins',
            system_type='click_visit',
            category='daily_retention',
            # ✅ শুধু আপনার মডেলের ফিল্ডগুলো ব্যবহার করুন
        )
        self.assertEqual(task.name, 'Watch Video')
        self.assertEqual(task.system_type, 'click_visit')
        self.assertTrue(task.is_active)  # default is True

    def test_user_task_completion(self):
        """Test UserTaskCompletion creation"""
        task = MasterTask.objects.create(
            task_id=f'TASK_{uid()}',
            name=f'Task_{uid()}',
            system_type='gamified',
        )
        
        completion = UserTaskCompletion.objects.create(
            user=self.user,
            task=task,
            status='completed',
            # ✅ rewards_awarded is JSONField
            rewards_awarded={
                'points': 50,
                'coins': 1.00,
                'experience': 10
            },
            admin_revenue_received=Decimal('10.00')  # ✅ এই field টি আপনার মডেলে আছে
        )
        self.assertEqual(completion.status, 'completed')
        self.assertEqual(completion.user, self.user)
        self.assertEqual(completion.task, task)
        self.assertEqual(completion.points_earned, 50)

    def test_admin_ledger(self):
        """Test AdminLedger creation with required fields"""
        task = MasterTask.objects.create(
            task_id=f'TASK_{uid()}',
            name='Test Task',
            system_type='click_visit',
        )
        
        # ✅ AdminLedger তৈরি - আপনার মডেল অনুযায়ী
        ledger = AdminLedger.objects.create(
            entry_id=f'LED_{uid()}',
            amount=Decimal('100.00'),
            source='task_revenue',
            source_type=AdminLedger.SOURCE_TASK,  # 'task'
            task=task,  # ✅ task field is required
            user=self.user,
            description='Task revenue from test',
            metadata={'test': True}
        )
        self.assertEqual(ledger.amount, Decimal('100.00'))
        self.assertEqual(ledger.source_type, AdminLedger.SOURCE_TASK)
        self.assertEqual(ledger.task, task)
        
        # ✅ Test profit summary methods
        total_profit = AdminLedger.get_total_profit()
        self.assertIsNotNone(total_profit)
        
        profit_by_period = AdminLedger.get_profit_by_period(days=30)
        self.assertIsInstance(profit_by_period, dict)
        
        profit_summary = AdminLedger.get_profit_summary(days=30)
        self.assertIn('total_profit', profit_summary)

    def test_task_reward_calculation(self):
        """Test task reward calculation"""
        task = MasterTask.objects.create(
            task_id=f'TASK_{uid()}',
            name='Reward Test Task',
            system_type='gamified',
            rewards={
                'points': 100,
                'coins': 10,
                'experience': 50
            },
            constraints={
                'cooldown_minutes': 5,
                'daily_limit': 10
            }
        )
        
        # Test base reward calculation
        reward = task.calculate_reward()
        self.assertIn('base', reward)
        self.assertIn('final', reward)
        self.assertEqual(reward['base']['points'], 100)
        
        # Test with user and metadata
        user_reward = task.calculate_reward(
            user=self.user,
            metadata={'double_points': True}
        )
        self.assertGreaterEqual(user_reward['final']['points'], 100)

    def test_task_availability_check(self):
        """Test task availability methods"""
        task = MasterTask.objects.create(
            task_id=f'TASK_{uid()}',
            name='Availability Test',
            system_type='click_visit',
            is_active=True
        )
        
        self.assertTrue(task.is_available_now)
        self.assertFalse(task.is_expired)
        self.assertFalse(task.is_future_task)
        self.assertEqual(task.time_status, 'available')

    def test_task_completion_with_rewards(self):
        """Test completing task with rewards"""
        task = MasterTask.objects.create(
            task_id=f'TASK_{uid()}',
            name='Reward Test',
            system_type='gamified',
            rewards={
                'points': 50,
                'coins': 5
            }
        )
        
        completion = UserTaskCompletion.objects.create(
            user=self.user,
            task=task,
            status='started'
        )
        
        # Complete with rewards
        result = completion.complete_with_rewards(
            proof={'screenshot': 'test.png'},
            metadata={'bonus': True}
        )
        
        self.assertTrue(result['success'])
        self.assertIn('rewards', result)
        
        # Refresh from DB
        completion.refresh_from_db()
        self.assertEqual(completion.status, 'completed')
        self.assertIsNotNone(completion.completed_at)

    def test_admin_ledger_profit_calculation(self):
        """Test profit calculation methods"""
        # Create some test data
        task = MasterTask.objects.create(
            task_id=f'TASK_{uid()}',
            name='Profit Test',
            system_type='click_visit'
        )
        
        for i in range(5):
            AdminLedger.objects.create(
                entry_id=f'LED_{uid()}',
                amount=Decimal('10.00'),
                source='task_revenue',
                source_type=AdminLedger.SOURCE_TASK,
                task=task,
                description=f'Test profit {i}'
            )
        
        # Test profit summary
        summary = AdminLedger.get_profit_summary(days=30)
        self.assertGreaterEqual(summary['total_profit'], 50.00)
        
        # Test profit by task
        task_profit = AdminLedger.get_profit_by_task(task.id)
        self.assertEqual(task_profit, Decimal('50.00'))

    def test_bulk_operations(self):
        """Test bulk task operations"""
        tasks = []
        for i in range(3):
            task = MasterTask.objects.create(
                task_id=f'TASK_{uid()}',
                name=f'Bulk Test {i}',
                system_type='click_visit',
                is_active=True
            )
            tasks.append(task)
        
        task_ids = [t.id for t in tasks]
        
        # Test bulk deactivate
        deactivated = MasterTask.bulk_deactivate(task_ids)
        self.assertEqual(deactivated, 3)
        
        for task in MasterTask.objects.filter(id__in=task_ids):
            self.assertFalse(task.is_active)
        
        # Test bulk activate
        activated = MasterTask.bulk_activate(task_ids)
        self.assertEqual(activated, 3)
        
        for task in MasterTask.objects.filter(id__in=task_ids):
            self.assertTrue(task.is_active)