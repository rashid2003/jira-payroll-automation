"""
Management command to manually trigger payroll automation.
"""

from django.core.management.base import BaseCommand, CommandError
from payroll.tasks import auto_run_payroll, run_payroll_for_period
from payroll.models import PayrollPeriod


class Command(BaseCommand):
    help = 'Run payroll automation manually'

    def add_arguments(self, parser):
        parser.add_argument(
            '--period-id',
            type=int,
            help='Process a specific payroll period by ID'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force processing regardless of automation rules'
        )
        parser.add_argument(
            '--async',
            action='store_true',
            help='Run the task asynchronously through Celery'
        )

    def handle(self, *args, **options):
        period_id = options.get('period_id')
        force = options.get('force', False)
        run_async = options.get('async', False)

        try:
            if period_id:
                # Process a specific period
                self.stdout.write(
                    f"Processing payroll for period {period_id} "
                    f"(force={force}, async={run_async})"
                )
                
                if run_async:
                    # Run asynchronously through Celery
                    task = run_payroll_for_period.delay(period_id, force)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Task queued with ID: {task.id}"
                        )
                    )
                else:
                    # Run synchronously
                    result = run_payroll_for_period(period_id, force)
                    self.stdout.write(
                        self.style.SUCCESS(f"Result: {result}")
                    )
            else:
                # Run full automation
                self.stdout.write("Running full payroll automation...")
                
                if run_async:
                    # Run asynchronously through Celery
                    task = auto_run_payroll.delay()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Task queued with ID: {task.id}"
                        )
                    )
                else:
                    # Run synchronously
                    result = auto_run_payroll()
                    self.stdout.write(
                        self.style.SUCCESS(f"Result: {result}")
                    )

        except Exception as e:
            raise CommandError(f"Error running payroll automation: {str(e)}")
