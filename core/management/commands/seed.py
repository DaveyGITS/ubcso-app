from django.core.management.base import BaseCommand
from django.utils import timezone
from organizations.models import Organization, OrganizationCategory
from core.models import SystemSetting, AcademicPeriod
from memberships.models import Membership
from accounts.models import User


class Command(BaseCommand):
    help = 'Seeds the database with initial data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding database...')

        # Create default categories
        categories = [
            {'name': 'Academic', 'description': 'Academically focused organizations'},
            {'name': 'Technology', 'description': 'Tech, computing, and engineering organizations'},
            {'name': 'Arts & Culture', 'description': 'Creative and cultural organizations'},
            {'name': 'Sports & Recreation', 'description': 'Athletic and recreational organizations'},
            {'name': 'Civic & Advocacy', 'description': 'Community service and advocacy organizations'},
            {'name': 'Religious', 'description': 'Faith-based organizations'},
            {'name': 'Environmental', 'description': 'Environment and sustainability organizations'},
            {'name': 'Social & Community', 'description': 'General community and social organizations'},
        ]

        for cat in categories:
            obj, created = OrganizationCategory.objects.get_or_create(
                name=cat['name'],
                defaults={'description': cat['description']}
            )
            if created:
                self.stdout.write(f'  ✔ Created category: {cat["name"]}')
            else:
                self.stdout.write(f'  — Category already exists: {cat["name"]}')

        # Create CSO organization
        cso, created = Organization.objects.get_or_create(
            is_cso=True,
            defaults={
                'name': 'Campus Student Organizations',
                'description': 'The official student governing body of the University of Bohol responsible for overseeing all campus student organizations.',
                'goals': 'To foster student leadership, organizational excellence, and campus engagement at the University of Bohol.',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write('  ✔ Created CSO organization')
        else:
            self.stdout.write('  — CSO organization already exists')

        # Link superuser to CSO org as chairman
        try:
            president = User.objects.filter(is_cso_president=True).first()
            if president:
                membership, created = Membership.objects.get_or_create(
                    user=president,
                    organization=cso,
                    defaults={
                        'role': 'chairman',
                        'has_chairman_privileges': True,
                        'status': 'active',
                    }
                )
                if created:
                    self.stdout.write(f'  ✔ Linked {president.email} as CSO chairman')
                else:
                    self.stdout.write(f'  — CSO chairman already linked')
            else:
                self.stdout.write('  ⚠ No CSO President found — run createsuperuser first')
        except Exception as e:
            self.stdout.write(f'  ⚠ Could not link president: {e}')

        # Create default academic period
        current_year = timezone.now().year
        period, created = AcademicPeriod.objects.get_or_create(
            name=f'1st Semester {current_year}-{current_year + 1}',
            defaults={
                'start_date': timezone.now().date().replace(month=6, day=1),
                'end_date': timezone.now().date().replace(month=10, day=31),
                'is_current': True,
            }
        )
        if created:
            self.stdout.write(f'  ✔ Created academic period: {period.name}')
        else:
            self.stdout.write(f'  — Academic period already exists: {period.name}')

        # Create default system settings
        settings_data = [
            {'key': 'admin_guide', 'value': 'Welcome to the UB-CSO Portal. This guide will help you understand how to manage the system effectively.'},
            {'key': 'welcome_message', 'value': 'Welcome to the UB-CSO Portal. You have been granted admin access by the CSO President.'},
            {'key': 'system_rules', 'value': 'All organizations must comply with the University of Bohol CSO policies and guidelines.'},
        ]

        for setting in settings_data:
            obj, created = SystemSetting.objects.get_or_create(
                key=setting['key'],
                defaults={'value': setting['value']}
            )
            if created:
                self.stdout.write(f'  ✔ Created setting: {setting["key"]}')
            else:
                self.stdout.write(f'  — Setting already exists: {setting["key"]}')

        self.stdout.write(self.style.SUCCESS('\nDatabase seeded successfully!'))