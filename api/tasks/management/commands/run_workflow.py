"""
tasks/management/commands/run_workflow.py
Manually trigger a TaskWorkflow by name or ID from the CLI.

Usage:
  python manage.py run_workflow --name "Daily Revenue Rollup"
  python manage.py run_workflow --id 3 --input '{"date": "2025-01-01"}'
  python manage.py run_workflow --name "Export Users" --sync
"""
import json
import sys
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Manually trigger a TaskWorkflow by name or ID'

    def add_arguments(self, parser):
        parser.add_argument(
            '--name',
            type=str,
            help='Workflow name (partial match allowed)',
        )
        parser.add_argument(
            '--id',
            type=int,
            dest='workflow_id',
            help='Workflow primary key',
        )
        parser.add_argument(
            '--input',
            type=str,
            default='{}',
            help='JSON string of input data to pass to the workflow',
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            default=False,
            help='Run synchronously (wait for completion) instead of async',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            default=False,
            help='List all available active workflows and exit',
        )

    def handle(self, *args, **options):
        from api.tasks.services.WorkflowService import WorkflowService

        svc = WorkflowService()

        # ── List mode ────────────────────────────────────────────────
        if options['list']:
            workflows = svc.list_workflows(active_only=True)
            if not workflows:
                self.stdout.write(self.style.WARNING('No active workflows found.'))
                return

            self.stdout.write(self.style.SUCCESS(f'\nActive Workflows ({len(workflows)}):'))
            self.stdout.write('-' * 60)
            for wf in workflows:
                self.stdout.write(
                    f"  [{wf['id']:>4}]  {wf['name']:<40}  trigger={wf['trigger_type']}"
                )
            return

        # ── Resolve workflow ──────────────────────────────────────────
        workflow_id = options.get('workflow_id')
        name        = options.get('name')

        if not workflow_id and not name:
            raise CommandError('Provide --name or --id. Use --list to see available workflows.')

        if not workflow_id:
            try:
                from api.tasks.models.workflow import TaskWorkflow
                wf = TaskWorkflow.objects.filter(name__icontains=name, is_active=True).first()
                if not wf:
                    raise CommandError(f"No active workflow matching name '{name}'")
                workflow_id = wf.pk
                self.stdout.write(f"Resolved workflow: [{workflow_id}] {wf.name}")
            except Exception as e:
                raise CommandError(str(e))

        # ── Parse input ───────────────────────────────────────────────
        try:
            input_data = json.loads(options['input'])
        except json.JSONDecodeError as e:
            raise CommandError(f'Invalid JSON for --input: {e}')

        # ── Trigger ───────────────────────────────────────────────────
        async_exec = not options['sync']
        self.stdout.write(
            f"Triggering workflow id={workflow_id} "
            f"async={async_exec} input={input_data} ..."
        )

        result = svc.trigger_workflow(
            workflow_id=workflow_id,
            input_data=input_data,
            trigger_type='manual',
            async_execute=async_exec,
        )

        if result.get('success'):
            self.stdout.write(self.style.SUCCESS(
                f"[OK] WorkflowInstance #{result['instance_id']} created. "
                f"Status: {result['status']}"
            ))
            if not async_exec:
                # Poll until done
                self._poll_instance(svc, result['instance_id'])
        else:
            self.stderr.write(self.style.ERROR(
                f"[FAIL] Could not trigger workflow: {result.get('error')}"
            ))
            sys.exit(1)

    def _poll_instance(self, svc, instance_id: int, max_wait: int = 300):
        """Poll instance status until terminal state or timeout."""
        import time
        self.stdout.write(f'Polling instance #{instance_id}...')
        waited = 0
        while waited < max_wait:
            info = svc.get_instance_status(instance_id)
            if not info:
                break
            st = info.get('status')
            self.stdout.write(
                f"  [{timezone.now().strftime('%H:%M:%S')}] "
                f"step={info.get('current_step')} status={st}"
            )
            if st in ('success', 'failed', 'cancelled'):
                if st == 'success':
                    self.stdout.write(self.style.SUCCESS('[DONE] Workflow completed successfully.'))
                else:
                    self.stderr.write(self.style.ERROR(
                        f'[FAIL] Workflow ended with status={st}: {info.get("error")}'
                    ))
                return
            time.sleep(3)
            waited += 3
        self.stdout.write(self.style.WARNING(f'[TIMEOUT] Stopped polling after {max_wait}s'))
