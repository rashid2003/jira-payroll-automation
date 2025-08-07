"""
Management command to create users with specific payroll system roles.

This command simplifies the process of creating users with appropriate roles
and permissions for the payroll system.

Usage:
    python manage.py create_payroll_user --username finance_user --email finance@company.com --role finance
    python manage.py create_payroll_user --username admin_user --email admin@company.com --role admin --department IT
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from payroll.models import UserProfile


class Command(BaseCommand):
    help = 'Create a new user with a specific payroll system role'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            required=True,
            help='Username for the new user'
        )
        
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Email address for the new user'
        )
        
        parser.add_argument(
            '--password',
            type=str,
            help='Password for the new user (will prompt if not provided)'
        )
        
        parser.add_argument(
            '--role',
            type=str,
            choices=['employee', 'manager', 'hr', 'finance', 'admin'],
            default='employee',
            help='Role to assign to the user'
        )
        
        parser.add_argument(
            '--department',
            type=str,
            help='Department for the user'
        )
        
        parser.add_argument(
            '--employee-id',
            type=str,
            help='Employee ID for the user'
        )
        
        parser.add_argument(
            '--first-name',
            type=str,
            help='First name for the user'
        )
        
        parser.add_argument(
            '--last-name',
            type=str,
            help='Last name for the user'
        )
        
        parser.add_argument(
            '--is-staff',
            action='store_true',
            help='Give the user Django admin access'
        )
        
        parser.add_argument(
            '--is-superuser',
            action='store_true',
            help='Give the user superuser privileges'
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options.get('password')
        role = options['role']
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            raise CommandError(f'User "{username}" already exists')
        
        if User.objects.filter(email=email).exists():
            raise CommandError(f'User with email "{email}" already exists')
        
        # Get password if not provided
        if not password:
            password = self._get_password()
        
        try:
            # Create the user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=options.get('first_name', ''),
                last_name=options.get('last_name', ''),
                is_staff=options.get('is_staff', False),
                is_superuser=options.get('is_superuser', False)
            )
            
            # Get the automatically created profile and update it
            profile = user.userprofile
            profile.role = role
            
            if options.get('department'):
                profile.department = options['department']
            
            if options.get('employee_id'):
                profile.employee_id = options['employee_id']
            
            profile.save()
            
            # Display creation summary
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created user "{username}"')
            )
            
            self._display_user_summary(user, profile)
            
        except Exception as e:
            raise CommandError(f'Error creating user: {e}')

    def _get_password(self):
        """Get password from user input with confirmation."""
        import getpass
        
        while True:
            password = getpass.getpass('Password: ')
            if not password:
                self.stdout.write(self.style.ERROR('Password cannot be empty'))
                continue
                
            password_confirm = getpass.getpass('Password (again): ')
            
            if password != password_confirm:
                self.stdout.write(self.style.ERROR("Passwords don't match"))
                continue
                
            return password

    def _display_user_summary(self, user, profile):
        """Display a summary of the created user and their permissions."""
        
        self.stdout.write(self.style.SUCCESS('\n=== User Created Successfully ==='))
        self.stdout.write(f'Username: {user.username}')
        self.stdout.write(f'Email: {user.email}')
        if user.first_name or user.last_name:
            self.stdout.write(f'Name: {user.get_full_name()}')
        
        self.stdout.write(f'\n=== Profile Information ===')
        self.stdout.write(f'Role: {profile.get_role_display()}')
        if profile.department:
            self.stdout.write(f'Department: {profile.department}')
        if profile.employee_id:
            self.stdout.write(f'Employee ID: {profile.employee_id}')
        
        self.stdout.write(f'\n=== Django Permissions ===')
        self.stdout.write(f'Staff Access: {"Yes" if user.is_staff else "No"}')
        self.stdout.write(f'Superuser: {"Yes" if user.is_superuser else "No"}')
        
        self.stdout.write(f'\n=== Payroll Permissions ===')
        self.stdout.write(f'Can Create Periods: {"Yes" if profile.can_create_periods else "No"}')
        self.stdout.write(f'Can Run Payroll: {"Yes" if profile.can_run_payroll else "No"}')
        self.stdout.write(f'Can View All Periods: {"Yes" if profile.can_view_all_periods else "No"}')
        
        # Show automatic permission assignments
        if profile.is_finance_or_admin:
            self.stdout.write(
                self.style.WARNING(f'\nNote: {profile.get_role_display()} role automatically grants all payroll permissions')
            )
        elif profile.role == 'hr':
            self.stdout.write(
                self.style.WARNING(f'\nNote: HR role automatically grants view permissions')
            )
        
        self.stdout.write(f'\n=== API Access ===')
        self.stdout.write(f'Base URL: /api/payroll/')
        self.stdout.write(f'Available endpoints based on permissions:')
        
        if profile.can_view_all_periods or profile.role in ['hr', 'finance', 'admin']:
            self.stdout.write('  - GET /api/payroll/periods/ (list periods)')
            self.stdout.write('  - GET /api/payroll/periods/{id}/ (view period)')
            self.stdout.write('  - GET /api/payroll/periods/{id}/summary/ (period summary)')
        
        if profile.can_create_periods or profile.role in ['finance', 'admin']:
            self.stdout.write('  - POST /api/payroll/periods/ (create period)')
        
        if profile.role in ['finance', 'admin']:
            self.stdout.write('  - PUT/PATCH /api/payroll/periods/{id}/ (update period)')
            self.stdout.write('  - DELETE /api/payroll/periods/{id}/ (delete period)')
            self.stdout.write('  - GET /api/payroll/periods/export-csv/ (export data)')
            self.stdout.write('  - POST /api/payroll/periods/import-csv/ (import data)')
        
        if profile.can_run_payroll or profile.role in ['finance', 'admin']:
            self.stdout.write('  - POST /api/payroll/periods/{id}/run/ (run payroll)')
        
        self.stdout.write(f'\n=== Next Steps ===')
        self.stdout.write('1. The user can now log in to the system')
        if user.is_staff:
            self.stdout.write('2. They can access the Django admin at /admin/')
        self.stdout.write('3. They can access the API endpoints based on their role')
        self.stdout.write('4. Consider creating an authentication token for API access:')
        self.stdout.write(f'   python manage.py drf_create_token {user.username}')
        
        self.stdout.write(self.style.SUCCESS('\n=== Creation Complete ==='))
