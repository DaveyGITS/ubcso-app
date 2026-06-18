"""
Unit tests for AccomplishmentReport model, specifically testing new archive fields.
Validates: Requirement 11.1
"""

from django.test import TestCase
from django.utils import timezone
from datetime import date
from accounts.models import User
from organizations.models import Organization
from core.models import AcademicPeriod
from reports.models import AccomplishmentReport, ReportAttachment


class AccomplishmentReportNewFieldsTestCase(TestCase):
    """Tests for the new archive fields added to AccomplishmentReport."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
        )
        
        self.organization = Organization.objects.create(
            name='Test Organization',
            is_active=True,
            is_cso=False,
        )
        
        self.academic_period = AcademicPeriod.objects.create(
            name='Spring 2024',
            is_current=True,
        )

    def test_existing_report_without_new_fields_remains_valid(self):
        """
        Test that existing reports without new fields remain valid.
        Existing reports should have blank/null values for new fields.
        Validates: Requirement 11.1 (backwards compatibility)
        """
        # Create a report without providing new fields
        report = AccomplishmentReport.objects.create(
            organization=self.organization,
            submitted_by=self.user,
            academic_period=self.academic_period,
            title='Legacy Report',
            description='This is a legacy report without new fields',
            status='pending',
            # Not providing activity_name, date_of_activity, academic_year, semester
        )
        
        # Verify the report was created successfully
        self.assertIsNotNone(report.id)
        
        # Verify new fields have their default/blank values
        self.assertEqual(report.activity_name, '')
        self.assertIsNone(report.date_of_activity)
        self.assertEqual(report.academic_year, '')
        self.assertEqual(report.semester, '')
        
        # Verify the report is still retrievable
        fetched_report = AccomplishmentReport.objects.get(id=report.id)
        self.assertEqual(fetched_report.title, 'Legacy Report')

    def test_new_fields_are_saved_correctly(self):
        """
        Test that new fields are saved correctly when provided.
        Validates: Requirement 11.1
        """
        activity_date = date(2024, 3, 15)
        
        report = AccomplishmentReport.objects.create(
            organization=self.organization,
            submitted_by=self.user,
            academic_period=self.academic_period,
            title='Community Outreach Report',
            description='Organized community service event',
            status='pending',
            activity_name='Community Outreach Program',
            date_of_activity=activity_date,
            academic_year='2024–2025',
            semester='1st',
        )
        
        # Verify all new fields are saved correctly
        self.assertEqual(report.activity_name, 'Community Outreach Program')
        self.assertEqual(report.date_of_activity, activity_date)
        self.assertEqual(report.academic_year, '2024–2025')
        self.assertEqual(report.semester, '1st')
        
        # Verify the data persists when fetched from database
        fetched_report = AccomplishmentReport.objects.get(id=report.id)
        self.assertEqual(fetched_report.activity_name, 'Community Outreach Program')
        self.assertEqual(fetched_report.date_of_activity, activity_date)
        self.assertEqual(fetched_report.academic_year, '2024–2025')
        self.assertEqual(fetched_report.semester, '1st')

    def test_all_semester_choices_are_valid(self):
        """
        Test that all valid semester choices can be saved.
        Validates: Requirement 11.1
        """
        semester_choices = ['1st', '2nd', 'Summer']
        
        for semester_value in semester_choices:
            report = AccomplishmentReport.objects.create(
                organization=self.organization,
                submitted_by=self.user,
                academic_period=self.academic_period,
                title=f'Report for {semester_value}',
                description='Test report',
                status='pending',
                activity_name='Test Activity',
                academic_year='2024–2025',
                semester=semester_value,
            )
            
            self.assertEqual(report.semester, semester_value)
            
            # Verify persistence
            fetched = AccomplishmentReport.objects.get(id=report.id)
            self.assertEqual(fetched.semester, semester_value)

    def test_activity_name_can_be_empty_string(self):
        """
        Test that activity_name can be empty string (blank=True).
        Validates: Requirement 11.1
        """
        report = AccomplishmentReport.objects.create(
            organization=self.organization,
            submitted_by=self.user,
            academic_period=self.academic_period,
            title='Report Without Activity Name',
            description='Test',
            status='pending',
            activity_name='',  # Explicitly empty
        )
        
        self.assertEqual(report.activity_name, '')
        fetched = AccomplishmentReport.objects.get(id=report.id)
        self.assertEqual(fetched.activity_name, '')

    def test_date_of_activity_can_be_null(self):
        """
        Test that date_of_activity can be null (null=True, blank=True).
        Validates: Requirement 11.1
        """
        report = AccomplishmentReport.objects.create(
            organization=self.organization,
            submitted_by=self.user,
            academic_period=self.academic_period,
            title='Report Without Activity Date',
            description='Test',
            status='pending',
            date_of_activity=None,  # Explicitly null
        )
        
        self.assertIsNone(report.date_of_activity)
        fetched = AccomplishmentReport.objects.get(id=report.id)
        self.assertIsNone(fetched.date_of_activity)

    def test_academic_year_can_store_various_formats(self):
        """
        Test that academic_year field can store various formats.
        Validates: Requirement 11.1
        """
        test_years = [
            '2024–2025',
            '2023-2024',
            '2025/2026',
            'Spring 2024',
            '2024',
        ]
        
        for year in test_years:
            report = AccomplishmentReport.objects.create(
                organization=self.organization,
                submitted_by=self.user,
                academic_period=self.academic_period,
                title=f'Report for {year}',
                description='Test',
                status='pending',
                academic_year=year,
            )
            
            self.assertEqual(report.academic_year, year)
            fetched = AccomplishmentReport.objects.get(id=report.id)
            self.assertEqual(fetched.academic_year, year)

    def test_mixed_old_and_new_field_reports(self):
        """
        Test that reports with and without new fields can coexist in the database.
        Validates: Requirement 11.1
        """
        # Create an old-style report (no new fields)
        old_report = AccomplishmentReport.objects.create(
            organization=self.organization,
            submitted_by=self.user,
            academic_period=self.academic_period,
            title='Old Style Report',
            description='Legacy format',
            status='pending',
        )
        
        # Create a new-style report (with new fields)
        new_report = AccomplishmentReport.objects.create(
            organization=self.organization,
            submitted_by=self.user,
            academic_period=self.academic_period,
            title='New Style Report',
            description='Enhanced format',
            status='pending',
            activity_name='New Activity',
            date_of_activity=date(2024, 5, 20),
            academic_year='2024–2025',
            semester='2nd',
        )
        
        # Verify both exist and can be retrieved independently
        all_reports = AccomplishmentReport.objects.all()
        self.assertEqual(all_reports.count(), 2)
        
        fetched_old = AccomplishmentReport.objects.get(id=old_report.id)
        fetched_new = AccomplishmentReport.objects.get(id=new_report.id)
        
        self.assertEqual(fetched_old.title, 'Old Style Report')
        self.assertEqual(fetched_new.title, 'New Style Report')
        self.assertEqual(fetched_new.activity_name, 'New Activity')

    def test_new_fields_with_report_attachments(self):
        """
        Test that new fields work correctly with report attachments.
        Validates: Requirement 11.1
        """
        report = AccomplishmentReport.objects.create(
            organization=self.organization,
            submitted_by=self.user,
            academic_period=self.academic_period,
            title='Report with Attachments',
            description='Testing attachments with new fields',
            status='pending',
            activity_name='Activity with Files',
            date_of_activity=date(2024, 4, 10),
            academic_year='2024–2025',
            semester='1st',
        )
        
        # Create attachments (though we won't actually upload files in this test)
        # This tests that the relationship works correctly
        self.assertEqual(report.attachments.count(), 0)
        
        # Verify report metadata is still intact
        fetched = AccomplishmentReport.objects.get(id=report.id)
        self.assertEqual(fetched.activity_name, 'Activity with Files')
        self.assertEqual(fetched.semester, '1st')


class ReportCompilationTestCase(TestCase):
    """Tests for the ReportCompilation model.
    Validates: Requirement 11.3, 11.4
    """

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='chairman@example.com',
            password='testpass123',
        )
        
        self.organization = Organization.objects.create(
            name='Test Organization',
            is_active=True,
            is_cso=False,
        )
        
        self.academic_period = AcademicPeriod.objects.create(
            name='Spring 2024',
            is_current=True,
        )
        
        # Create some approved reports
        self.report1 = AccomplishmentReport.objects.create(
            organization=self.organization,
            submitted_by=self.user,
            academic_period=self.academic_period,
            title='Report 1',
            description='First report',
            status='approved',
            activity_name='Activity 1',
            date_of_activity=date(2024, 3, 15),
            academic_year='2024–2025',
            semester='1st',
        )
        
        self.report2 = AccomplishmentReport.objects.create(
            organization=self.organization,
            submitted_by=self.user,
            academic_period=self.academic_period,
            title='Report 2',
            description='Second report',
            status='approved',
            activity_name='Activity 2',
            date_of_activity=date(2024, 4, 20),
            academic_year='2024–2025',
            semester='1st',
        )

    def test_compilation_creation_with_valid_data(self):
        """
        Test that a ReportCompilation can be created with valid data.
        Validates: Requirement 11.3
        """
        from reports.models import ReportCompilation
        
        compilation = ReportCompilation.objects.create(
            organization=self.organization,
            name='1st Semester Reports',
            created_by=self.user,
        )
        compilation.reports.set([self.report1, self.report2])
        
        # Verify creation
        self.assertIsNotNone(compilation.id)
        self.assertEqual(compilation.name, '1st Semester Reports')
        self.assertEqual(compilation.organization, self.organization)
        self.assertEqual(compilation.created_by, self.user)
        self.assertEqual(compilation.reports.count(), 2)

    def test_compilation_created_at_is_auto_set(self):
        """
        Test that created_at is automatically set on creation.
        Validates: Requirement 11.3
        """
        from reports.models import ReportCompilation
        
        compilation = ReportCompilation.objects.create(
            organization=self.organization,
            name='Auto Timestamp Test',
            created_by=self.user,
        )
        
        self.assertIsNotNone(compilation.created_at)

    def test_compilation_can_have_zero_reports_initially(self):
        """
        Test that a compilation can be created with zero reports initially.
        Validates: Requirement 11.3
        """
        from reports.models import ReportCompilation
        
        compilation = ReportCompilation.objects.create(
            organization=self.organization,
            name='Empty Compilation',
            created_by=self.user,
        )
        
        self.assertEqual(compilation.reports.count(), 0)

    def test_compilation_ordering_by_created_at_descending(self):
        """
        Test that compilations are ordered by -created_at (newest first).
        Validates: Requirement 11.3
        """
        from reports.models import ReportCompilation
        import time
        
        comp1 = ReportCompilation.objects.create(
            organization=self.organization,
            name='First Compilation',
            created_by=self.user,
        )
        time.sleep(0.1)  # Small delay to ensure different timestamps
        comp2 = ReportCompilation.objects.create(
            organization=self.organization,
            name='Second Compilation',
            created_by=self.user,
        )
        
        compilations = ReportCompilation.objects.filter(organization=self.organization)
        self.assertEqual(compilations.first().id, comp2.id)
        self.assertEqual(compilations.last().id, comp1.id)

    def test_compilation_with_multiple_reports(self):
        """
        Test that a compilation can link multiple reports via M2M.
        Validates: Requirement 11.3, 11.4
        """
        from reports.models import ReportCompilation
        
        compilation = ReportCompilation.objects.create(
            organization=self.organization,
            name='Multi-Report Compilation',
            created_by=self.user,
        )
        compilation.reports.add(self.report1, self.report2)
        
        self.assertEqual(compilation.reports.count(), 2)
        self.assertIn(self.report1, compilation.reports.all())
        self.assertIn(self.report2, compilation.reports.all())

    def test_compilation_foreign_key_relationships(self):
        """
        Test that ReportCompilation has correct foreign key relationships.
        Validates: Requirement 11.3
        """
        from reports.models import ReportCompilation
        
        compilation = ReportCompilation.objects.create(
            organization=self.organization,
            name='FK Test Compilation',
            created_by=self.user,
        )
        
        # Verify FK relationships
        self.assertEqual(compilation.organization, self.organization)
        self.assertEqual(compilation.created_by, self.user)

    def test_compilation_name_field_max_length(self):
        """
        Test that compilation name field respects max_length=200.
        Validates: Requirement 11.3
        """
        from reports.models import ReportCompilation
        
        long_name = 'A' * 200  # Max length
        compilation = ReportCompilation.objects.create(
            organization=self.organization,
            name=long_name,
            created_by=self.user,
        )
        
        self.assertEqual(len(compilation.name), 200)
        
        # Verify it can be retrieved
        fetched = ReportCompilation.objects.get(id=compilation.id)
        self.assertEqual(fetched.name, long_name)

    def test_compilation_created_by_nullable(self):
        """
        Test that created_by can be null (SET_NULL on user deletion).
        Validates: Requirement 11.3
        """
        from reports.models import ReportCompilation
        
        compilation = ReportCompilation.objects.create(
            organization=self.organization,
            name='Test Compilation',
            created_by=None,
        )
        
        self.assertIsNone(compilation.created_by)

    def test_multiple_compilations_per_organization(self):
        """
        Test that an organization can have multiple compilations.
        Validates: Requirement 11.4
        """
        from reports.models import ReportCompilation
        
        comp1 = ReportCompilation.objects.create(
            organization=self.organization,
            name='Compilation 1',
            created_by=self.user,
        )
        comp2 = ReportCompilation.objects.create(
            organization=self.organization,
            name='Compilation 2',
            created_by=self.user,
        )
        
        compilations = ReportCompilation.objects.filter(organization=self.organization)
        self.assertEqual(compilations.count(), 2)
        self.assertIn(comp1, compilations)
        self.assertIn(comp2, compilations)

    def test_compilation_string_representation(self):
        """
        Test the __str__ method of ReportCompilation.
        Validates: Requirement 11.3
        """
        from reports.models import ReportCompilation
        
        compilation = ReportCompilation.objects.create(
            organization=self.organization,
            name='Test Compilation',
            created_by=self.user,
        )
        
        expected_str = f'Test Compilation ({self.organization.name})'
        self.assertEqual(str(compilation), expected_str)
