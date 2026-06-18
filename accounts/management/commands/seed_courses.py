from django.core.management.base import BaseCommand
from accounts.models import Course


class Command(BaseCommand):
    help = 'Seed the database with initial course data'

    def handle(self, *args, **options):
        courses_data = [
            # CASE - COLLEGE OF ARTS, SCIENCES, AND EDUCATION
            {
                'name': 'Bachelor of Science in Psychology',
                'abbreviation': 'BSPsych',
                'department': 'CASE'
            },
            {
                'name': 'Bachelor of Arts in English Language Studies',
                'abbreviation': 'BA-ELS',
                'department': 'CASE'
            },
            {
                'name': 'Bachelor of Arts in Political Science',
                'abbreviation': 'BA-PolSci',
                'department': 'CASE'
            },
            {
                'name': 'Bachelor of Arts in Philosophy',
                'abbreviation': 'BA-Phil',
                'department': 'CASE'
            },
            {
                'name': 'Bachelor of Secondary Education major in English',
                'abbreviation': 'BSEd-English',
                'department': 'CASE'
            },
            {
                'name': 'Bachelor of Secondary Education major in Filipino',
                'abbreviation': 'BSEd-Filipino',
                'department': 'CASE'
            },
            {
                'name': 'Bachelor of Secondary Education major in Mathematics',
                'abbreviation': 'BSEd-Math',
                'department': 'CASE'
            },
            {
                'name': 'Bachelor of Secondary Education major in Social Studies',
                'abbreviation': 'BSEd-Social',
                'department': 'CASE'
            },
            {
                'name': 'Bachelor of Secondary Education major in Science',
                'abbreviation': 'BSEd-Science',
                'department': 'CASE'
            },
            {
                'name': 'Bachelor of Elementary Education',
                'abbreviation': 'BEEd',
                'department': 'CASE'
            },
            {
                'name': 'Bachelor of Early Childhood Education',
                'abbreviation': 'BECEd',
                'department': 'CASE'
            },
            {
                'name': 'Bachelor of Special Needs Education (Generalist)',
                'abbreviation': 'BSNED-Gen',
                'department': 'CASE'
            },
            {
                'name': 'Bachelor of Physical Education',
                'abbreviation': 'BPE',
                'department': 'CASE'
            },
            {
                'name': 'Bachelor of Culture and Arts Education',
                'abbreviation': 'BCAE',
                'department': 'CASE'
            },

            # CBA - COLLEGE OF BUSINESS AND ACCOUNTANCY
            {
                'name': 'Bachelor of Science in Accountancy',
                'abbreviation': 'BSA',
                'department': 'CBA'
            },
            {
                'name': 'Bachelor of Science in Business Administration major in Marketing Management',
                'abbreviation': 'BSBA-MM',
                'department': 'CBA'
            },
            {
                'name': 'Bachelor of Science in Business Administration major in Financial Management',
                'abbreviation': 'BSBA-FM',
                'department': 'CBA'
            },
            {
                'name': 'Bachelor of Science in Business Administration major in Operations Management',
                'abbreviation': 'BSBA-OM',
                'department': 'CBA'
            },
            {
                'name': 'Bachelor of Science in Business Administration major in Human Resource Development Management',
                'abbreviation': 'BSBA-HRDM',
                'department': 'CBA'
            },

            # CETAFA - COLLEGE OF ENGINEERING, TECHNOLOGY, ARCHITECTURE, AND FINE ARTS
            {
                'name': 'Bachelor of Science in Civil Engineering – Structural',
                'abbreviation': 'BSCE-Struct',
                'department': 'CETAFA'
            },
            {
                'name': 'Bachelor of Science in Civil Engineering – Water Resources',
                'abbreviation': 'BSCE-WR',
                'department': 'CETAFA'
            },
            {
                'name': 'Bachelor of Science in Geodetic Engineering',
                'abbreviation': 'BSGE',
                'department': 'CETAFA'
            },
            {
                'name': 'Bachelor of Science in Electronics Engineering',
                'abbreviation': 'BSECE',
                'department': 'CETAFA'
            },
            {
                'name': 'Bachelor of Science in Electrical Engineering',
                'abbreviation': 'BSEE',
                'department': 'CETAFA'
            },
            {
                'name': 'Bachelor of Science in Industrial Engineering',
                'abbreviation': 'BSIE',
                'department': 'CETAFA'
            },
            {
                'name': 'Bachelor of Science in Mechanical Engineering',
                'abbreviation': 'BSME',
                'department': 'CETAFA'
            },
            {
                'name': 'Bachelor of Science in Computer Engineering',
                'abbreviation': 'BSCpE',
                'department': 'CETAFA'
            },
            {
                'name': 'Bachelor of Science in Computer Science',
                'abbreviation': 'BSCS',
                'department': 'CETAFA'
            },
            {
                'name': 'Bachelor of Science in Aircraft Maintenance Technology',
                'abbreviation': 'BSAMT',
                'department': 'CETAFA'
            },
            {
                'name': 'Associate in Aircraft Maintenance Technology',
                'abbreviation': 'AAMT',
                'department': 'CETAFA'
            },
            {
                'name': 'Bachelor of Science in Architecture',
                'abbreviation': 'BSArch',
                'department': 'CETAFA'
            },
            {
                'name': 'Bachelor of Fine Arts major in Visual Communication/Advertising',
                'abbreviation': 'BFA-VCA',
                'department': 'CETAFA'
            },

            # CHMTN - COLLEGE OF HOSPITALITY MANAGEMENT, TOURISM, AND NUTRITION
            {
                'name': 'Bachelor of Science in Hospitality Management',
                'abbreviation': 'BSHM',
                'department': 'CHMTN'
            },
            {
                'name': 'Bachelor of Science in Tourism Management',
                'abbreviation': 'BSTM',
                'department': 'CHMTN'
            },
            {
                'name': 'Bachelor of Science in Nutrition and Dietetics',
                'abbreviation': 'BSND',
                'department': 'CHMTN'
            },

            # CAHS - COLLEGE OF ALLIED HEALTH SCIENCES
            {
                'name': 'Bachelor of Science in Nursing',
                'abbreviation': 'BSN',
                'department': 'CAHS'
            },
            {
                'name': 'Bachelor of Science in Midwifery',
                'abbreviation': 'BSM',
                'department': 'CAHS'
            },

            # CPTOT - COLLEGE OF PHYSICAL THERAPY AND OCCUPATIONAL THERAPY
            {
                'name': 'Bachelor of Science in Physical Therapy',
                'abbreviation': 'BSPT',
                'department': 'CPTOT'
            },
            {
                'name': 'Bachelor of Science in Occupational Therapy',
                'abbreviation': 'BSOT',
                'department': 'CPTOT'
            },

            # COP - COLLEGE OF PHARMACY
            {
                'name': 'Bachelor of Science in Pharmacy',
                'abbreviation': 'BSP',
                'department': 'COP'
            },

            # CCJ - COLLEGE OF CRIMINAL JUSTICE
            {
                'name': 'Bachelor of Science in Criminology',
                'abbreviation': 'BSCrim',
                'department': 'CCJ'
            }
        ]

        created_count = 0
        updated_count = 0

        for course_data in courses_data:
            course, created = Course.objects.get_or_create(
                abbreviation=course_data['abbreviation'],
                defaults=course_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created course: {course.name}')
                )
            else:
                # Update existing course with new data
                for key, value in course_data.items():
                    setattr(course, key, value)
                course.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Updated course: {course.name}')
                )

        total_courses = len(courses_data)
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSeeding complete!\n'
                f'Total courses processed: {total_courses}\n'
                f'Created: {created_count}\n'
                f'Updated: {updated_count}\n'
                f'Active courses in database: {Course.objects.filter(is_active=True).count()}'
            )
        )
