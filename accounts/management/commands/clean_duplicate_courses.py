from django.core.management.base import BaseCommand
from django.db import models
from accounts.models import Course


class Command(BaseCommand):
    help = 'Remove duplicate courses keeping only the first one'

    def handle(self, *args, **options):
        # Get all abbreviations that have duplicates
        duplicate_abbrevs = Course.objects.values('abbreviation').annotate(
            count=models.Count('id')
        ).filter(count__gt=1).values_list('abbreviation', flat=True)

        removed_count = 0
        kept_count = 0

        for abbrev in duplicate_abbrevs:
            # Get all courses with this abbreviation, ordered by ID
            courses = Course.objects.filter(abbreviation=abbrev).order_by('id')
            
            # Keep the first one, remove the rest
            to_keep = courses.first()
            to_remove = courses[1:]  # All except the first
            
            self.stdout.write(f'\nAbbreviation: {abbrev}')
            self.stdout.write(f'  Keeping: {to_keep.name} (ID: {to_keep.id})')
            
            for course in to_remove:
                self.stdout.write(f'  Removing: {course.name} (ID: {course.id})')
                course.delete()
                removed_count += 1
                kept_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nCleanup complete!\n'
                f'Duplicate courses removed: {removed_count}\n'
                f'Unique courses kept: {kept_count}'
            )
        )
