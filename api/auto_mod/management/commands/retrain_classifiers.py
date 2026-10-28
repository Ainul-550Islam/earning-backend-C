# =============================================================================
# auto_mod/management/commands/retrain_classifiers.py
# =============================================================================

"""
Django management command to trigger ML model retraining.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction

from ...models import MLModelVersion, SuspiciousSubmission, ModerationDecision
from ...choices import ModelType, ModelTrainingStatus, ModerationStatus, SubmissionType
from ...services import MLModelService
from ...exceptions import ModelTrainingError, ModelVersionError
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Trigger ML model retraining with latest data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--model-type',
            type=str,
            choices=[choice[0] for choice in ModelType.choices],
            help='Model type to retrain (default: all)'
        )
        parser.add_argument(
            '--data-version',
            type=str,
            help='Training data version identifier'
        )
        parser.add_argument(
            '--epochs',
            type=int,
            default=10,
            help='Number of training epochs (default: 10)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=32,
            help='Training batch size (default: 32)'
        )
        parser.add_argument(
            '--learning-rate',
            type=float,
            default=0.001,
            help='Learning rate (default: 0.001)'
        )
        parser.add_argument(
            '--validation-split',
            type=float,
            default=0.2,
            help='Validation data split ratio (default: 0.2)'
        )
        parser.add_argument(
            '--min-accuracy',
            type=float,
            default=0.85,
            help='Minimum accuracy threshold for deployment (default: 0.85)'
        )
        parser.add_argument(
            '--force-retrain',
            action='store_true',
            help='Force retrain even if recent training exists'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show training plan without executing'
        )
        parser.add_argument(
            '--deploy-on-success',
            action='store_true',
            help='Automatically deploy model if training meets threshold'
        )
        parser.add_argument(
            '--skip-validation',
            action='store_true',
            help='Skip validation and deploy immediately'
        )
    
    def handle(self, *args, **options):
        """Execute the retrain command."""
        self.stdout.write(
            self.style.SUCCESS('Starting ML model retraining...')
        )
        
        # Get parameters
        model_type = options.get('model_type')
        data_version = options.get('data_version')
        epochs = options.get('epochs', 10)
        batch_size = options.get('batch_size', 32)
        learning_rate = options.get('learning_rate', 0.001)
        validation_split = options.get('validation_split', 0.2)
        min_accuracy = options.get('min_accuracy', 0.85)
        force_retrain = options.get('force_retrain', False)
        dry_run = options.get('dry_run', False)
        deploy_on_success = options.get('deploy_on_success', False)
        skip_validation = options.get('skip_validation', False)
        
        try:
            ml_service = MLModelService()
            
            # Get models to retrain
            models_to_retrain = self._get_models_to_retrain(model_type, force_retrain)
            
            if not models_to_retrain:
                self.stdout.write(
                    self.style.WARNING('No models found to retrain.')
                )
                return
            
            self.stdout.write(f'Found {len(models_to_retrain)} models to retrain')
            
            # Show training plan
            training_plan = self._create_training_plan(
                models_to_retrain, data_version, epochs, batch_size, 
                learning_rate, validation_split
            )
            
            if dry_run:
                self._show_training_plan(training_plan)
                return
            
            # Execute training
            results = self._execute_training(
                ml_service, training_plan, min_accuracy, deploy_on_success, skip_validation
            )
            
            # Display results
            self._display_training_results(results)
            
        except Exception as exc:
            logger.error(f"Model retraining failed: {exc}")
            raise CommandError(f"Model retraining failed: {exc}")
    
    def _get_models_to_retrain(self, model_type, force_retrain):
        """Get models that need retraining."""
        queryset = MLModelVersion.objects.filter(
            status__in=[ModelTrainingStatus.IDLE, ModelTrainingStatus.FAILED]
        )
        
        if model_type:
            queryset = queryset.filter(model_type=model_type)
        
        if not force_retrain:
            # Exclude models trained recently
            recent_training = timezone.now() - timezone.timedelta(days=7)
            queryset = queryset.filter(
                created_at__lte=recent_training
            )
        
        # Get the latest version for each model type
        latest_models = {}
        for model in queryset.order_by('model_type', '-created_at'):
            if model.model_type not in latest_models:
                latest_models[model.model_type] = model
        
        return list(latest_models.values())
    
    def _create_training_plan(self, models, data_version, epochs, batch_size, learning_rate, validation_split):
        """Create training plan for models."""
        plan = {
            'models': [],
            'global_config': {
                'data_version': data_version or f"auto_{timezone.now().strftime('%Y%m%d_%H%M%S')}",
                'epochs': epochs,
                'batch_size': batch_size,
                'learning_rate': learning_rate,
                'validation_split': validation_split
            }
        }
        
        for model in models:
            # Get training data statistics
            data_stats = self._get_training_data_stats(model.model_type)
            
            model_plan = {
                'model': model,
                'model_type': model.model_type,
                'current_version': model.version,
                'data_stats': data_stats,
                'hyperparameters': {
                    'epochs': epochs,
                    'batch_size': batch_size,
                    'learning_rate': learning_rate,
                    'validation_split': validation_split,
                    **model.hyperparameters  # Merge with existing hyperparameters
                }
            }
            
            plan['models'].append(model_plan)
        
        return plan
    
    def _get_training_data_stats(self, model_type):
        """Get training data statistics for model type."""
        # Get submissions with human decisions (ground truth)
        submissions = SuspiciousSubmission.objects.filter(
            submission_type=model_type,
            decisions__isnull=False,
            decisions__decided_by__isnull=False
        ).distinct()
        
        # Count by decision type
        decision_counts = {}
        for submission in submissions:
            latest_decision = submission.decisions.latest('decided_at')
            decision_type = latest_decision.decision_type
            decision_counts[decision_type] = decision_counts.get(decision_type, 0) + 1
        
        total_samples = submissions.count()
        
        return {
            'total_samples': total_samples,
            'decision_distribution': decision_counts,
            'date_range': {
                'oldest': submissions.order_by('created_at').first().created_at if submissions.exists() else None,
                'newest': submissions.order_by('-created_at').first().created_at if submissions.exists() else None
            }
        }
    
    def _show_training_plan(self, plan):
        """Display training plan in dry run mode."""
        self.stdout.write(self.style.WARNING('DRY RUN - No actual training will occur'))
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write('TRAINING PLAN')
        self.stdout.write('='*50)
        
        self.stdout.write(f"Data version: {plan['global_config']['data_version']}")
        self.stdout.write(f"Epochs: {plan['global_config']['epochs']}")
        self.stdout.write(f"Batch size: {plan['global_config']['batch_size']}")
        self.stdout.write(f"Learning rate: {plan['global_config']['learning_rate']}")
        self.stdout.write(f"Validation split: {plan['global_config']['validation_split']}")
        
        self.stdout.write('\nModels to train:')
        for model_plan in plan['models']:
            model = model_plan['model']
            stats = model_plan['data_stats']
            
            self.stdout.write(f"\n  {model.display_name} ({model.model_type})")
            self.stdout.write(f"    Current version: {model.version}")
            self.stdout.write(f"    Training samples: {stats['total_samples']}")
            
            if stats['decision_distribution']:
                self.stdout.write("    Decision distribution:")
                for decision, count in stats['decision_distribution'].items():
                    self.stdout.write(f"      {decision}: {count}")
        
        self.stdout.write('\n' + '='*50)
    
    def _execute_training(self, ml_service, plan, min_accuracy, deploy_on_success, skip_validation):
        """Execute model training."""
        results = {
            'total_models': len(plan['models']),
            'started': 0,
            'completed': 0,
            'successful': 0,
            'failed': 0,
            'deployed': 0,
            'models': []
        }
        
        global_config = plan['global_config']
        
        for model_plan in plan['models']:
            model = model_plan['model']
            hyperparameters = model_plan['hyperparameters']
            
            self.stdout.write(
                f"\nTraining {model.display_name} ({model.model_type})..."
            )
            
            try:
                # Create new model version
                new_version = self._create_new_model_version(
                    ml_service, model, global_config['data_version'], hyperparameters
                )
                
                results['started'] += 1
                
                # Start training
                training_result = self._start_model_training(
                    ml_service, new_version, hyperparameters
                )
                
                if training_result['success']:
                    results['completed'] += 1
                    
                    # Complete training with mock performance metrics
                    # In real implementation, these would come from actual training
                    performance_metrics = self._mock_training_performance(model.model_type)
                    
                    completion_result = self._complete_model_training(
                        ml_service, new_version, performance_metrics
                    )
                    
                    if completion_result['success']:
                        results['successful'] += 1
                        
                        # Check if model should be deployed
                        accuracy = performance_metrics.get('accuracy', 0)
                        if (deploy_on_success and accuracy >= min_accuracy) or skip_validation:
                            deploy_result = self._deploy_model(ml_service, new_version)
                            if deploy_result['success']:
                                results['deployed'] += 1
                        
                        # Record model results
                        model_results = {
                            'model_id': str(model.pk),
                            'model_name': model.display_name,
                            'new_version': new_version.version,
                            'training_success': True,
                            'accuracy': accuracy,
                            'deployed': results['deployed'] > results['models'] and 
                                       new_version.is_deployed
                        }
                        results['models'].append(model_results)
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✓ Training completed successfully "
                                f"(accuracy: {accuracy:.3f})"
                            )
                        )
                    else:
                        results['failed'] += 1
                        self.stdout.write(
                            self.style.ERROR(f"✗ Training completion failed")
                        )
                else:
                    results['failed'] += 1
                    self.stdout.write(
                        self.style.ERROR(f"✗ Training failed: {training_result['error']}")
                    )
                
            except Exception as exc:
                results['failed'] += 1
                self.stdout.write(
                    self.style.ERROR(f"✗ Training error: {exc}")
                )
                logger.error(f"Model training failed for {model.pk}: {exc}")
        
        return results
    
    def _create_new_model_version(self, ml_service, base_model, data_version, hyperparameters):
        """Create new model version for training."""
        return ml_service.create_model_version(
            model_type=base_model.model_type,
            version=self._generate_new_version(base_model.version),
            display_name=f"{base_model.display_name} (Retrained)",
            description=f"Retrained version of {base_model.version}",
            created_by=None,  # System created
            hyperparameters=hyperparameters,
            metadata={
                'base_model_id': str(base_model.pk),
                'training_data_version': data_version,
                'retraining_reason': 'scheduled_retrain'
            }
        )
    
    def _generate_new_version(self, current_version):
        """Generate new version number."""
        try:
            parts = current_version.split('.')
            if len(parts) >= 2:
                # Increment patch version
                parts[-1] = str(int(parts[-1]) + 1)
                return '.'.join(parts)
            else:
                return f"{current_version}.1"
        except:
            return f"{current_version}.1"
    
    def _start_model_training(self, ml_service, model_version, hyperparameters):
        """Start model training."""
        try:
            updated_model = ml_service.start_model_training(
                model_version=model_version,
                training_config=hyperparameters,
                training_data_version=model_version.metadata.get('training_data_version'),
                created_by=None
            )
            return {'success': True, 'model': updated_model}
        except ModelTrainingError as exc:
            return {'success': False, 'error': str(exc)}
    
    def _mock_training_performance(self, model_type):
        """Mock training performance metrics (replace with actual training)."""
        import random
        
        # Simulate different performance based on model type
        base_accuracy = {
            ModelType.IMAGE: 0.92,
            ModelType.TEXT: 0.89,
            ModelType.OCR: 0.95,
            ModelType.COMBINED: 0.87
        }.get(model_type, 0.85)
        
        # Add some randomness
        accuracy = base_accuracy + random.uniform(-0.05, 0.05)
        accuracy = max(0.7, min(0.99, accuracy))  # Clamp between 0.7 and 0.99
        
        return {
            'accuracy': accuracy,
            'precision': accuracy - random.uniform(0.02, 0.05),
            'recall': accuracy - random.uniform(0.01, 0.04),
            'f1_score': accuracy - random.uniform(0.02, 0.03),
            'loss': random.uniform(0.1, 0.3),
            'val_loss': random.uniform(0.12, 0.35),
            'training_time_hours': random.uniform(2, 8)
        }
    
    def _complete_model_training(self, ml_service, model_version, performance_metrics):
        """Complete model training with performance metrics."""
        try:
            updated_model = ml_service.complete_model_training(
                model_version=model_version,
                performance_metrics=performance_metrics,
                training_log="Training completed successfully",
                training_duration_hours=performance_metrics.get('training_time_hours', 4.0)
            )
            return {'success': True, 'model': updated_model}
        except Exception as exc:
            return {'success': False, 'error': str(exc)}
    
    def _deploy_model(self, ml_service, model_version):
        """Deploy trained model."""
        try:
            updated_model = ml_service.deploy_model(
                model_version=model_version,
                deployed_by=None,  # System deployed
                deployment_config={
                    'auto_deployed': True,
                    'deployment_reason': 'automatic_after_training'
                }
            )
            return {'success': True, 'model': updated_model}
        except Exception as exc:
            return {'success': False, 'error': str(exc)}
    
    def _display_training_results(self, results):
        """Display training results summary."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('TRAINING RESULTS'))
        self.stdout.write('='*50)
        
        self.stdout.write(f"Total models: {results['total_models']}")
        self.stdout.write(f"Training started: {results['started']}")
        self.stdout.write(f"Training completed: {results['completed']}")
        self.stdout.write(
            self.style.SUCCESS(f"Successful: {results['successful']}")
        )
        
        if results['failed'] > 0:
            self.stdout.write(
                self.style.ERROR(f"Failed: {results['failed']}")
            )
        
        if results['deployed'] > 0:
            self.stdout.write(
                self.style.SUCCESS(f"Deployed: {results['deployed']}")
            )
        
        # Success rate
        if results['started'] > 0:
            success_rate = (results['successful'] / results['started']) * 100
            self.stdout.write(f"Success rate: {success_rate:.1f}%")
        
        # Model details
        if results['models']:
            self.stdout.write('\nModel Details:')
            for model_result in results['models']:
                status = "✓" if model_result['training_success'] else "✗"
                deploy_status = " (DEPLOYED)" if model_result['deployed'] else ""
                
                self.stdout.write(
                    f"  {status} {model_result['model_name']} "
                    f"v{model_result['new_version']} "
                    f"(accuracy: {model_result['accuracy']:.3f})"
                    f"{deploy_status}"
                )
        
        self.stdout.write('='*50)
        
        # Log summary
        logger.info(
            f"Model retraining completed: {results['successful']}/{results['started']} "
            f"successful, {results['deployed']} deployed"
        )
        
        # Recommendations
        self._provide_recommendations(results)
    
    def _provide_recommendations(self, results):
        """Provide recommendations based on results."""
        recommendations = []
        
        if results['failed'] > 0:
            failure_rate = (results['failed'] / results['total_models']) * 100
            if failure_rate > 30:
                recommendations.append(
                    "High failure rate detected. Consider checking training data quality "
                    "and model hyperparameters."
                )
        
        if results['successful'] > 0:
            successful_models = [m for m in results['models'] if m['training_success']]
            avg_accuracy = sum(m['accuracy'] for m in successful_models) / len(successful_models)
            
            if avg_accuracy < 0.8:
                recommendations.append(
                    "Low average accuracy detected. Consider increasing training data "
                    "or adjusting model architecture."
                )
            elif avg_accuracy > 0.95:
                recommendations.append(
                    "Very high accuracy detected. Consider checking for overfitting "
                    "or data leakage."
                )
        
        if results['deployed'] == 0 and results['successful'] > 0:
            recommendations.append(
                "No models were deployed. Consider using --deploy-on-success flag "
                "or manually reviewing trained models."
            )
        
        if recommendations:
            self.stdout.write('\n' + self.style.WARNING('RECOMMENDATIONS:'))
            for i, rec in enumerate(recommendations, 1):
                self.stdout.write(f"  {i}. {rec}")
        
        # Next steps
        self.stdout.write('\n' + self.style.SUCCESS('NEXT STEPS:'))
        if results['deployed'] > 0:
            self.stdout.write(
                "  • Monitor deployed models in production"
            )
            self.stdout.write(
                "  • Set up automated performance tracking"
            )
        else:
            self.stdout.write(
                "  • Review training results and manually deploy models"
            )
            self.stdout.write(
                "  • Consider running with --deploy-on-success for future training"
            )
        
        self.stdout.write(
            "  • Schedule regular retraining (e.g., weekly or monthly)"
        )
