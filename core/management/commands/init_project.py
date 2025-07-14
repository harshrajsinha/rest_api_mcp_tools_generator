"""
Management command to initialize the project with sample data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import APIConfiguration


class Command(BaseCommand):
    help = 'Initialize the project with sample data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-superuser',
            action='store_true',
            help='Create a superuser account',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Initializing REST API MCP Tools Generator...'))

        # Create superuser if requested
        if options['create_superuser']:
            self.create_superuser()

        # Create sample API configuration
        self.create_sample_config()

        self.stdout.write(
            self.style.SUCCESS('Project initialized successfully!')
        )

    def create_superuser(self):
        if not User.objects.filter(is_superuser=True).exists():
            try:
                user = User.objects.create_superuser(
                    username='admin',
                    email='admin@example.com',
                    password='admin123'
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Superuser created: {user.username}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error creating superuser: {str(e)}')
                )
        else:
            self.stdout.write(
                self.style.WARNING('Superuser already exists')
            )

    def create_sample_config(self):
        # Create a sample API configuration if none exists
        if not APIConfiguration.objects.exists():
            try:
                # Get or create a user for the configuration
                user, created = User.objects.get_or_create(
                    username='admin',
                    defaults={
                        'email': 'admin@example.com',
                        'is_staff': True,
                        'is_superuser': True
                    }
                )

                config = APIConfiguration.objects.create(
                    name='Petstore API (Sample)',
                    swagger_url='https://petstore.swagger.io/v2/swagger.json',
                    api_base_url='https://petstore.swagger.io/v2',
                    description='Sample Petstore API for testing the tool generator',
                    auth_type='none',
                    auth_config={},
                    created_by=user
                )

                self.stdout.write(
                    self.style.SUCCESS(f'Sample API configuration created: {config.name}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error creating sample config: {str(e)}')
                )
