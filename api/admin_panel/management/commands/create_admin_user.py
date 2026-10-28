# api/admin_panel/management/commands/create_admin_user.py
"""
Management command: create a new admin user with AdminProfile and role assignment.
Usage:
  python manage.py create_admin_user --username admin2 --email admin2@example.com --password secret123 --role admin
  python manage.py create_admin_user --username superuser --email su@example.com --superuser
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create a new admin user with an AdminProfile and assigned role.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            required=True,
            help='Username for the new admin user.',
        )
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Email address for the new admin user.',
        )
        parser.add_argument(
            '--password',
            type=str,
            default=None,
            help='Password (will prompt interactively if omitted).',
        )
        parser.add_argument(
            '--first-name',
            type=str,
            default='',
            help='First name.',
        )
        parser.add_argument(
            '--last-name',
            type=str,
            default='',
            help='Last name.',
        )
        parser.add_argument(
            '--role',
            type=str,
            choices=['superadmin', 'admin', 'moderator', 'support', 'finance', 'analyst', 'viewer'],
            default='admin',
            help='Admin role (default: admin).',
        )
        parser.add_argument(
            '--superuser',
            action='store_true',
            default=False,
            help='Make this user a Django superuser (is_superuser=True).',
        )
        parser.add_argument(
            '--phone',
            type=str,
            default='',
            help='Phone number for AdminProfile.',
        )
        parser.add_argument(
            '--department',
            type=str,
            default='',
            help='Department for AdminProfile.',
        )
        parser.add_argument(
            '--no-profile',
            action='store_true',
            default=False,
            help='Skip creating AdminProfile (only create the User).',
        )

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        username = options['username']
        email = options['email']
        password = options.get('password')
        role = options['role']
        is_superuser = options['superuser']
        first_name = options['first_name']
        last_name = options['last_name']
        phone = options['phone']
        department = options['department']
        no_profile = options['no_profile']

        # Check existing user
        if User.objects.filter(username=username).exists():
            raise CommandError(f'User "{username}" already exists.')
        if User.objects.filter(email=email).exists():
            raise CommandError(f'Email "{email}" is already in use.')

        # Password prompt if not provided
        if not password:
            import getpass
            password = getpass.getpass(f'Password for {username}: ')
            confirm = getpass.getpass('Confirm password: ')
            if password != confirm:
                raise CommandError('Passwords do not match.')

        if len(password) < 8:
            raise CommandError('Password must be at least 8 characters.')

        # Create user
        if is_superuser:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=True,
            )

        self.stdout.write(f'✅ User created: {username} (id={user.pk})')

        # Create AdminProfile
        if not no_profile:
            try:
                from api.admin_panel.models.core import AdminProfile
                profile_role = 'superadmin' if is_superuser else role
                profile = AdminProfile.objects.create(
                    user=user,
                    role=profile_role,
                    phone=phone,
                    department=department,
                    receive_digest=True,
                    receive_alerts=True,
                )
                self.stdout.write(f'✅ AdminProfile created: role={profile_role}')
            except Exception as e:
                self.stderr.write(f'⚠️  AdminProfile creation failed: {e}')

        # Log activity
        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(
                actor=None,
                action='create_admin_user',
                model_name='User',
                object_id=str(user.pk),
                object_repr=str(user),
                changes={'username': username, 'role': role, 'is_superuser': is_superuser},
                status='success',
            )
        except Exception:
            pass

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Admin user created successfully:'))
        self.stdout.write(f'  Username:   {username}')
        self.stdout.write(f'  Email:      {email}')
        self.stdout.write(f'  Role:       {"superadmin" if is_superuser else role}')
        self.stdout.write(f'  Superuser:  {is_superuser}')
        self.stdout.write(f'  Staff:      {user.is_staff}')