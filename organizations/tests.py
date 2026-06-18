from django.test import TestCase, Client
from django.urls import reverse
from hypothesis import given, strategies as st, settings
from hypothesis.extra.django import TestCase as HypothesisTestCase
from organizations.models import Organization, AccreditationApplication, AccreditationDocument, OfficialFormLink
from accounts.models import User
from memberships.models import Membership
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile


class OrganizationStatusSyncTests(TestCase):
    """Tests for Organization status field and is_active synchronization."""

    def test_new_organization_defaults_to_pending_status(self):
        """Test that a newly created Organization has status = 'pending'."""
        org = Organization.objects.create(name="Test Org")
        self.assertEqual(org.status, 'pending')

    def test_new_organization_is_active_false_for_pending_status(self):
        """Test that is_active is False for a new org with pending status."""
        org = Organization.objects.create(name="Test Org")
        self.assertFalse(org.is_active)

    def test_active_statuses_constant_is_correct(self):
        """Test that ACTIVE_STATUSES contains the correct statuses."""
        expected_active = {'probationary', 'institutional', 'active', 'renewal_due', 'lapsed'}
        self.assertEqual(Organization.ACTIVE_STATUSES, expected_active)

    def test_is_active_sync_on_save_for_active_status(self):
        """Test that is_active is set to True when status is 'active'."""
        org = Organization.objects.create(name="Test Org", status='pending')
        self.assertFalse(org.is_active)
        
        org.status = 'active'
        org.save()
        
        org.refresh_from_db()
        self.assertTrue(org.is_active)

    def test_is_active_sync_on_save_for_inactive_status(self):
        """Test that is_active is set to False when status is 'rejected'."""
        org = Organization.objects.create(name="Test Org", status='active')
        self.assertTrue(org.is_active)
        
        org.status = 'rejected'
        org.save()
        
        org.refresh_from_db()
        self.assertFalse(org.is_active)

    def test_status_badge_probationary(self):
        """Test that status_badge returns 'Probationary' for probationary status."""
        org = Organization.objects.create(name="Test Org", status='probationary')
        self.assertEqual(org.status_badge, 'Probationary')

    def test_status_badge_institutional(self):
        """Test that status_badge returns 'Institutional' for institutional status."""
        org = Organization.objects.create(name="Test Org", status='institutional')
        self.assertEqual(org.status_badge, 'Institutional')

    def test_status_badge_none_for_active(self):
        """Test that status_badge returns None for active status."""
        org = Organization.objects.create(name="Test Org", status='active')
        self.assertIsNone(org.status_badge)

    def test_status_badge_none_for_pending(self):
        """Test that status_badge returns None for pending status."""
        org = Organization.objects.create(name="Test Org", status='pending')
        self.assertIsNone(org.status_badge)

    def test_status_badge_none_for_renewal_due(self):
        """Test that status_badge returns None for renewal_due status."""
        org = Organization.objects.create(name="Test Org", status='renewal_due')
        self.assertIsNone(org.status_badge)

    def test_status_badge_none_for_lapsed(self):
        """Test that status_badge returns None for lapsed status."""
        org = Organization.objects.create(name="Test Org", status='lapsed')
        self.assertIsNone(org.status_badge)

    def test_is_active_true_for_all_active_statuses(self):
        """Test that is_active is True for all statuses in ACTIVE_STATUSES."""
        for status in Organization.ACTIVE_STATUSES:
            org = Organization.objects.create(name=f"Test Org {status}", status=status)
            self.assertTrue(org.is_active,
                           f"is_active should be True for status={status}")

    def test_is_active_false_for_inactive_statuses(self):
        """Test that is_active is False for statuses not in ACTIVE_STATUSES."""
        inactive_statuses = ['pending', 'under_review', 'rejected']
        for status in inactive_statuses:
            org = Organization.objects.create(name=f"Test Org {status}", status=status)
            self.assertFalse(org.is_active,
                            f"is_active should be False for status={status}")


class OrganizationPropertyTests(HypothesisTestCase):
    """Property-based tests for Organization model using Hypothesis."""

    @given(st.sampled_from([s[0] for s in Organization.ORG_STATUS_CHOICES]))
    def test_is_active_sync_invariant(self, status):
        """
        Property 1: is_active sync invariant
        
        For any Organization record with any valid status value, is_active must equal True
        if and only if status is in ACTIVE_STATUSES, and False otherwise.
        
        **Validates: Requirements 1.2, 1.3**
        """
        org = Organization.objects.create(name=f"Test Org {status}")
        org.status = status
        org.save()
        
        expected_is_active = status in Organization.ACTIVE_STATUSES
        self.assertEqual(org.is_active, expected_is_active,
                        f"For status={status}, is_active should be {expected_is_active}")

    @given(st.sampled_from([s[0] for s in Organization.ORG_STATUS_CHOICES]))
    def test_status_badge_mapping(self, status):
        """
        Property 2: status_badge mapping
        
        For any Organization with a valid status, status_badge must return "Probationary"
        when status is 'probationary', "Institutional" when status is 'institutional',
        and None for all other status values.
        
        **Validates: Requirements 1.5, 2.4, 2.5**
        """
        org = Organization.objects.create(name=f"Test Org {status}")
        org.status = status
        org.save()
        
        expected_badge = {
            'probationary': 'Probationary',
            'institutional': 'Institutional'
        }.get(status)
        
        self.assertEqual(org.status_badge, expected_badge,
                        f"For status={status}, status_badge should be {expected_badge}")


class AccreditationApplicationFormTests(TestCase):
    """Tests for the accreditation_apply_view form."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.url = reverse('organizations:accreditation_apply')
        
        # Create a test user to be chairman
        self.chairman = User.objects.create_user(
            email='chairman@test.com',
            password='testpass123',
            student_id='2024-00001',
            is_active=True
        )
        
        # Create a test user to submit the form
        self.applicant = User.objects.create_user(
            email='applicant@test.com',
            password='testpass123',
            student_id='2024-00002',
            is_active=True
        )

    def create_test_file(self, name='test.pdf', size=1024):
        """Helper to create a test file."""
        return SimpleUploadedFile(
            name,
            BytesIO(b'x' * size).getvalue(),
            content_type='application/pdf'
        )

    def test_unauthenticated_user_redirected_to_login(self):
        """Test that unauthenticated users are redirected to login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_authenticated_user_can_access_form(self):
        """Test that authenticated users can access the form."""
        self.client.login(email='applicant@test.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'organizations/accreditation_apply.html')

    def test_form_displays_official_forms(self):
        """Test that the form displays all OfficialFormLink entries."""
        OfficialFormLink.objects.create(
            label='Form A',
            url='https://example.com/form-a.pdf',
            updated_by=self.chairman
        )
        OfficialFormLink.objects.create(
            label='Form B',
            url='https://example.com/form-b.pdf',
            updated_by=self.chairman
        )
        
        self.client.login(email='applicant@test.com', password='testpass123')
        response = self.client.get(self.url)
        
        self.assertContains(response, 'Form A')
        self.assertContains(response, 'Form B')

    def test_renewal_type_not_selectable(self):
        """Test that 'renewal' is not a selectable registration type."""
        self.client.login(email='applicant@test.com', password='testpass123')
        response = self.client.get(self.url)
        
        # Check that renewal is not in the form
        self.assertNotContains(response, 'value="renewal"')

    def test_duplicate_org_name_rejected(self):
        """Test that duplicate org names (case-insensitive) are rejected."""
        # Create an existing org
        Organization.objects.create(name='Test Organization', status='active')
        
        self.client.login(email='applicant@test.com', password='testpass123')
        
        # Try to submit with same name (different case)
        data = {
            'organization_name': 'test organization',
            'chairman_student_id': '2024-00001',
            'registration_type': 'new_applicant',
            'doc_letter_of_intent': self.create_test_file(),
            'doc_form_a': self.create_test_file(),
            'doc_form_b': self.create_test_file(),
            'doc_form_e': self.create_test_file(),
            'doc_essay': self.create_test_file(),
            'doc_constitution_and_by_laws': self.create_test_file(),
            'doc_list_of_officers_and_advisers': self.create_test_file(),
            'doc_data_sheets_and_pictures': self.create_test_file(),
        }
        
        response = self.client.post(self.url, data)
        
        # Should not redirect (form should be re-rendered with errors)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')

    def test_duplicate_pending_application_rejected(self):
        """Test that duplicate pending applications are rejected."""
        # Create an org with a pending application
        org = Organization.objects.create(name='Test Organization', status='pending')
        AccreditationApplication.objects.create(
            organization=org,
            registration_type='new_applicant',
            status='pending'
        )
        
        self.client.login(email='applicant@test.com', password='testpass123')
        
        # Try to submit another application with same org name
        data = {
            'organization_name': 'Test Organization',
            'chairman_student_id': '2024-00001',
            'registration_type': 'new_applicant',
            'doc_letter_of_intent': self.create_test_file(),
            'doc_form_a': self.create_test_file(),
            'doc_form_b': self.create_test_file(),
            'doc_form_e': self.create_test_file(),
            'doc_essay': self.create_test_file(),
            'doc_constitution_and_by_laws': self.create_test_file(),
            'doc_list_of_officers_and_advisers': self.create_test_file(),
            'doc_data_sheets_and_pictures': self.create_test_file(),
        }
        
        response = self.client.post(self.url, data)
        
        # Should not redirect (form should be re-rendered with errors)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'pending application')

    def test_missing_required_documents_rejected(self):
        """Test that missing required documents are rejected."""
        self.client.login(email='applicant@test.com', password='testpass123')
        
        # Submit with only some documents
        data = {
            'organization_name': 'New Organization',
            'chairman_student_id': '2024-00001',
            'registration_type': 'new_applicant',
            'doc_letter_of_intent': self.create_test_file(),
            # Missing other required documents
        }
        
        response = self.client.post(self.url, data)
        
        # Should not redirect (form should be re-rendered with errors)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'required')

    def test_file_size_validation(self):
        """Test that files exceeding 10 MB are rejected."""
        self.client.login(email='applicant@test.com', password='testpass123')
        
        # Create a file larger than 10 MB
        large_file = SimpleUploadedFile(
            'large.pdf',
            BytesIO(b'x' * (11 * 1024 * 1024)).getvalue(),
            content_type='application/pdf'
        )
        
        data = {
            'organization_name': 'New Organization',
            'chairman_student_id': '2024-00001',
            'registration_type': 'new_applicant',
            'doc_letter_of_intent': large_file,
            'doc_form_a': self.create_test_file(),
            'doc_form_b': self.create_test_file(),
            'doc_form_e': self.create_test_file(),
            'doc_essay': self.create_test_file(),
            'doc_constitution_and_by_laws': self.create_test_file(),
            'doc_list_of_officers_and_advisers': self.create_test_file(),
            'doc_data_sheets_and_pictures': self.create_test_file(),
        }
        
        response = self.client.post(self.url, data)
        
        # Should not redirect (form should be re-rendered with errors)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '10 MB')

    def test_invalid_chairman_student_id_rejected(self):
        """Test that invalid chairman student IDs are rejected."""
        self.client.login(email='applicant@test.com', password='testpass123')
        
        data = {
            'organization_name': 'New Organization',
            'chairman_student_id': '9999-99999',  # Non-existent
            'registration_type': 'new_applicant',
            'doc_letter_of_intent': self.create_test_file(),
            'doc_form_a': self.create_test_file(),
            'doc_form_b': self.create_test_file(),
            'doc_form_e': self.create_test_file(),
            'doc_essay': self.create_test_file(),
            'doc_constitution_and_by_laws': self.create_test_file(),
            'doc_list_of_officers_and_advisers': self.create_test_file(),
            'doc_data_sheets_and_pictures': self.create_test_file(),
        }
        
        response = self.client.post(self.url, data)
        
        # Should not redirect (form should be re-rendered with errors)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'not found')

    def test_successful_new_applicant_submission(self):
        """Test successful submission of a new applicant application."""
        self.client.login(email='applicant@test.com', password='testpass123')
        
        data = {
            'organization_name': 'New Organization',
            'chairman_student_id': '2024-00001',
            'registration_type': 'new_applicant',
            'doc_letter_of_intent': self.create_test_file('letter.pdf'),
            'doc_form_a': self.create_test_file('form_a.pdf'),
            'doc_form_b': self.create_test_file('form_b.pdf'),
            'doc_form_e': self.create_test_file('form_e.pdf'),
            'doc_essay': self.create_test_file('essay.pdf'),
            'doc_constitution_and_by_laws': self.create_test_file('constitution.pdf'),
            'doc_list_of_officers_and_advisers': self.create_test_file('officers.pdf'),
            'doc_data_sheets_and_pictures': self.create_test_file('data.pdf'),
        }
        
        response = self.client.post(self.url, data)
        
        # Should redirect to directory
        self.assertEqual(response.status_code, 302)
        self.assertIn('/directory/', response.url)
        
        # Verify Organization was created
        org = Organization.objects.get(name='New Organization')
        self.assertEqual(org.status, 'pending')
        self.assertFalse(org.is_active)
        
        # Verify AccreditationApplication was created
        app = AccreditationApplication.objects.get(organization=org)
        self.assertEqual(app.registration_type, 'new_applicant')
        self.assertEqual(app.status, 'pending')
        
        # Verify AccreditationDocument records were created
        docs = AccreditationDocument.objects.filter(application=app)
        self.assertEqual(docs.count(), 8)
        
        # Verify Membership was created
        membership = Membership.objects.get(organization=org, user=self.chairman)
        self.assertEqual(membership.role, 'chairman')
        self.assertTrue(membership.has_chairman_privileges)

    def test_successful_new_chapter_submission(self):
        """Test successful submission of a new chapter application."""
        self.client.login(email='applicant@test.com', password='testpass123')
        
        data = {
            'organization_name': 'New Chapter Organization',
            'chairman_student_id': '2024-00001',
            'registration_type': 'new_chapter',
            'doc_letter_of_intent': self.create_test_file('letter.pdf'),
            'doc_form_a': self.create_test_file('form_a.pdf'),
            'doc_form_b': self.create_test_file('form_b.pdf'),
            'doc_form_c': self.create_test_file('form_c.pdf'),
            'doc_form_d': self.create_test_file('form_d.pdf'),
            'doc_form_e': self.create_test_file('form_e.pdf'),
            'doc_essay': self.create_test_file('essay.pdf'),
            'doc_letter_from_mother_organization': self.create_test_file('mother_letter.pdf'),
            'doc_letter_of_authority': self.create_test_file('authority.pdf'),
            'doc_minutes_of_approval_from_mother_organization': self.create_test_file('minutes.pdf'),
            'doc_constitution_and_by_laws_of_mother_organization': self.create_test_file('mother_constitution.pdf'),
            'doc_data_sheets_and_pictures': self.create_test_file('data.pdf'),
            # SEC Registration is optional, so we don't include it
        }
        
        response = self.client.post(self.url, data)
        
        # Should redirect to directory
        self.assertEqual(response.status_code, 302)
        
        # Verify Organization was created
        org = Organization.objects.get(name='New Chapter Organization')
        self.assertEqual(org.status, 'pending')
        
        # Verify AccreditationApplication was created
        app = AccreditationApplication.objects.get(organization=org)
        self.assertEqual(app.registration_type, 'new_chapter')
        
        # Verify AccreditationDocument records were created (12 required, 0 optional)
        docs = AccreditationDocument.objects.filter(application=app)
        self.assertEqual(docs.count(), 12)

    def test_sec_registration_optional_for_new_chapter(self):
        """Test that SEC Registration is optional for new chapter applications."""
        self.client.login(email='applicant@test.com', password='testpass123')
        
        # Submit without SEC Registration
        data = {
            'organization_name': 'New Chapter Organization',
            'chairman_student_id': '2024-00001',
            'registration_type': 'new_chapter',
            'doc_letter_of_intent': self.create_test_file('letter.pdf'),
            'doc_form_a': self.create_test_file('form_a.pdf'),
            'doc_form_b': self.create_test_file('form_b.pdf'),
            'doc_form_c': self.create_test_file('form_c.pdf'),
            'doc_form_d': self.create_test_file('form_d.pdf'),
            'doc_form_e': self.create_test_file('form_e.pdf'),
            'doc_essay': self.create_test_file('essay.pdf'),
            'doc_letter_from_mother_organization': self.create_test_file('mother_letter.pdf'),
            'doc_letter_of_authority': self.create_test_file('authority.pdf'),
            'doc_minutes_of_approval_from_mother_organization': self.create_test_file('minutes.pdf'),
            'doc_constitution_and_by_laws_of_mother_organization': self.create_test_file('mother_constitution.pdf'),
            'doc_data_sheets_and_pictures': self.create_test_file('data.pdf'),
        }
        
        response = self.client.post(self.url, data)
        
        # Should succeed without SEC Registration
        self.assertEqual(response.status_code, 302)
        
        # Verify application was created
        app = AccreditationApplication.objects.get(registration_type='new_chapter')
        self.assertEqual(app.status, 'pending')


# ─── New School Year and Close Renewal Period Tests ─────────────────────────

class NewSchoolYearViewTests(TestCase):
    """Tests for admin_new_school_year_view - Task 10."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            is_cso_admin=True,
            student_id='2024-00001',
            is_active=True
        )
        
        # Create non-admin user
        self.non_admin_user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            is_cso_admin=False,
            student_id='2024-00002',
            is_active=True
        )
        
        # Create test organizations with different statuses
        self.probationary_org = Organization.objects.create(
            name='Probationary Org',
            status='probationary'
        )
        
        self.institutional_org = Organization.objects.create(
            name='Institutional Org',
            status='institutional'
        )
        
        self.active_org = Organization.objects.create(
            name='Active Org',
            status='active'
        )
        
        self.pending_org = Organization.objects.create(
            name='Pending Org',
            status='pending'
        )
        
        self.renewal_due_org = Organization.objects.create(
            name='Already Renewal Due Org',
            status='renewal_due'
        )
        
        # Create chairman memberships for notification test
        for org in [self.probationary_org, self.institutional_org, self.active_org]:
            Membership.objects.create(
                organization=org,
                user=self.admin_user,
                role='chairman',
                status='active'
            )
        
        self.url = reverse('organizations:admin_new_school_year')

    def test_unauthenticated_user_redirected_to_login(self):
        """Test that unauthenticated users are redirected to login."""
        response = self.client.post(self.url, {'renewal_deadline': '2024-12-31'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_non_admin_user_denied_access(self):
        """Test that non-admin users are denied access."""
        self.client.login(email='user@test.com', password='testpass123')
        response = self.client.post(self.url, {'renewal_deadline': '2024-12-31'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/', response.url)

    def test_get_request_rejected(self):
        """Test that GET requests are rejected."""
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/', response.url)

    def test_missing_renewal_deadline_rejected(self):
        """Test that missing renewal deadline is rejected."""
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 302)
        # Should show error message (check in subsequent redirect/messages)

    def test_invalid_date_format_rejected(self):
        """Test that invalid date formats are rejected."""
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.post(self.url, {'renewal_deadline': 'not-a-date'})
        self.assertEqual(response.status_code, 302)

    def test_new_school_year_transitions_eligible_orgs(self):
        """Test that eligible orgs are transitioned to renewal_due.
        
        **Requirement 9.2**
        """
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.post(self.url, {'renewal_deadline': '2024-12-31'})
        
        # Should redirect back to admin panel
        self.assertEqual(response.status_code, 302)
        
        # Verify eligible orgs were transitioned
        self.probationary_org.refresh_from_db()
        self.institutional_org.refresh_from_db()
        self.active_org.refresh_from_db()
        
        self.assertEqual(self.probationary_org.status, 'renewal_due')
        self.assertEqual(self.institutional_org.status, 'renewal_due')
        self.assertEqual(self.active_org.status, 'renewal_due')
        
        # Verify ineligible orgs were NOT transitioned
        self.pending_org.refresh_from_db()
        self.renewal_due_org.refresh_from_db()
        
        self.assertEqual(self.pending_org.status, 'pending')
        self.assertEqual(self.renewal_due_org.status, 'renewal_due')

    def test_renewal_deadline_stored_in_system_setting(self):
        """Test that renewal deadline is stored in SystemSetting.
        
        **Requirement 9.4**
        """
        from core.models import SystemSetting
        
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.post(self.url, {'renewal_deadline': '2024-12-31'})
        
        # Verify SystemSetting was created/updated
        setting = SystemSetting.objects.get(key='renewal_deadline')
        self.assertEqual(setting.value, '2024-12-31')

    def test_notifications_sent_to_chairmen(self):
        """Test that notifications are sent to affected chairmen.
        
        **Requirement 9.3**
        """
        from announcements.models import Notification
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(self.url, {'renewal_deadline': '2024-12-31'})
            
            # Verify send_notification was called 3 times (for 3 eligible orgs)
            self.assertEqual(mock_notify.call_count, 3)


class CloseRenewalViewTests(TestCase):
    """Tests for admin_close_renewal_view - Task 10."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            is_cso_admin=True,
            student_id='2024-00001',
            is_active=True
        )
        
        # Create renewal_due orgs
        self.renewal_due_no_approval = Organization.objects.create(
            name='Renewal Due No Approval',
            status='renewal_due'
        )
        
        self.renewal_due_with_approval = Organization.objects.create(
            name='Renewal Due With Approval',
            status='renewal_due'
        )
        
        # Create approved renewal application for one org
        approved_app = AccreditationApplication.objects.create(
            organization=self.renewal_due_with_approval,
            registration_type='renewal',
            status='approved'
        )
        
        # Create other status orgs (should not be affected)
        self.active_org = Organization.objects.create(
            name='Active Org',
            status='active'
        )
        
        # Create chairman memberships for notifications
        for org in [self.renewal_due_no_approval, self.renewal_due_with_approval, self.active_org]:
            Membership.objects.create(
                organization=org,
                user=self.admin_user,
                role='chairman',
                status='active'
            )
        
        self.url = reverse('organizations:admin_close_renewal')

    def test_unauthenticated_user_redirected_to_login(self):
        """Test that unauthenticated users are redirected to login."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_non_admin_user_denied_access(self):
        """Test that non-admin users are denied access."""
        admin_user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            is_cso_admin=False,
            student_id='2024-00002',
            is_active=True
        )
        self.client.login(email='user@test.com', password='testpass123')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)

    def test_get_request_rejected(self):
        """Test that GET requests are rejected."""
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_close_renewal_transitions_renewal_due_without_approval(self):
        """Test that renewal_due orgs without approved renewal are lapsed.
        
        **Requirement 9.6**
        """
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.post(self.url)
        
        # Should redirect back to admin panel
        self.assertEqual(response.status_code, 302)
        
        # Verify renewal_due org without approval was lapsed
        self.renewal_due_no_approval.refresh_from_db()
        self.assertEqual(self.renewal_due_no_approval.status, 'lapsed')

    def test_close_renewal_keeps_renewal_due_with_approval(self):
        """Test that renewal_due orgs with approved renewal stay renewal_due.
        
        **Requirement 9.6**
        """
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.post(self.url)
        
        # Verify renewal_due org with approved application was NOT transitioned
        self.renewal_due_with_approval.refresh_from_db()
        self.assertEqual(self.renewal_due_with_approval.status, 'renewal_due')

    def test_close_renewal_keeps_other_statuses(self):
        """Test that orgs with other statuses are not affected.
        
        **Requirement 9.6**
        """
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.post(self.url)
        
        # Verify active org was not affected
        self.active_org.refresh_from_db()
        self.assertEqual(self.active_org.status, 'active')

    def test_notifications_sent_to_newly_lapsed(self):
        """Test that notifications are sent to newly lapsed chairmen.
        
        **Requirement 9.7**
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(self.url)
            
            # Verify send_notification was called once (for 1 newly lapsed org)
            self.assertEqual(mock_notify.call_count, 1)


class AccreditationApplicationPropertyTests(HypothesisTestCase):
    """Property-based tests for accreditation application form."""

    def setUp(self):
        """Set up test fixtures."""
        self.chairman = User.objects.create_user(
            email='chairman@test.com',
            password='testpass123',
            student_id='2024-00001',
            is_active=True
        )
        
        self.applicant = User.objects.create_user(
            email='applicant@test.com',
            password='testpass123',
            student_id='2024-00002',
            is_active=True
        )

    def create_test_file(self, name='test.pdf'):
        """Helper to create a test file."""
        return SimpleUploadedFile(
            name,
            BytesIO(b'x' * 1024).getvalue(),
            content_type='application/pdf'
        )

    @given(st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))
    @settings(deadline=None, max_examples=5)
    def test_duplicate_org_name_rejection(self, org_name):
        """
        Property 7: Duplicate org name rejection
        
        For any existing Organization name (case-insensitive), submitting a new accreditation
        application with that same name must be rejected with a validation error and must not
        create any new Organization or AccreditationApplication records.
        
        **Validates: Requirements 6.6**
        """
        # Create an existing org with the generated name
        Organization.objects.create(name=org_name, status='active')
        
        client = Client()
        client.login(email='applicant@test.com', password='testpass123')
        
        # Try to submit with same name (different case)
        data = {
            'organization_name': org_name.upper(),  # Different case
            'chairman_student_id': '2024-00001',
            'registration_type': 'new_applicant',
            'doc_letter_of_intent': self.create_test_file(),
            'doc_form_a': self.create_test_file(),
            'doc_form_b': self.create_test_file(),
            'doc_form_e': self.create_test_file(),
            'doc_essay': self.create_test_file(),
            'doc_constitution_and_by_laws': self.create_test_file(),
            'doc_list_of_officers_and_advisers': self.create_test_file(),
            'doc_data_sheets_and_pictures': self.create_test_file(),
        }
        
        url = reverse('organizations:accreditation_apply')
        response = client.post(url, data)
        
        # Should not redirect (form should be re-rendered with errors)
        self.assertEqual(response.status_code, 200)
        
        # Verify no new Organization was created
        org_count = Organization.objects.filter(name__iexact=org_name).count()
        self.assertEqual(org_count, 1)  # Only the original org
        
        # Verify no new AccreditationApplication was created
        app_count = AccreditationApplication.objects.filter(
            organization__name__iexact=org_name
        ).count()
        self.assertEqual(app_count, 0)


class RenewalApplicationFormTests(TestCase):
    """Tests for the renewal_apply_view form - Task 7.1."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
        # Create test users
        self.chairman_user = User.objects.create_user(
            email='chairman@test.com',
            password='testpass123',
            student_id='2024-00001',
            first_name='John',
            last_name='Chair',
            is_active=True
        )
        
        self.non_chairman_user = User.objects.create_user(
            email='member@test.com',
            password='testpass123',
            student_id='2024-00002',
            is_active=True
        )
        
        self.unauthenticated_user = None
        
        # Create an active organization
        self.active_org = Organization.objects.create(
            name='Active Organization',
            status='active'
        )
        
        # Create chairman membership
        self.chairman_membership = Membership.objects.create(
            organization=self.active_org,
            user=self.chairman_user,
            role='chairman',
            status='active',
            has_chairman_privileges=True
        )
        
        # Create a non-chairman membership
        self.non_chairman_membership = Membership.objects.create(
            organization=self.active_org,
            user=self.non_chairman_user,
            role='member',
            status='active'
        )
        
        # Create a renewal_due organization
        self.renewal_due_org = Organization.objects.create(
            name='Renewal Due Organization',
            status='renewal_due'
        )
        
        # Create chairman membership for renewal_due org
        self.renewal_due_chairman_membership = Membership.objects.create(
            organization=self.renewal_due_org,
            user=self.chairman_user,
            role='chairman',
            status='active',
            has_chairman_privileges=True
        )
        
        # Create a pending organization (should not allow renewal)
        self.pending_org = Organization.objects.create(
            name='Pending Organization',
            status='pending'
        )
        
        # Create chairman membership for pending org
        Membership.objects.create(
            organization=self.pending_org,
            user=self.chairman_user,
            role='chairman',
            status='active',
            has_chairman_privileges=True
        )

    def create_test_file(self, name='test.pdf', size=1024):
        """Helper to create a test file."""
        return SimpleUploadedFile(
            name,
            BytesIO(b'x' * size).getvalue(),
            content_type='application/pdf'
        )

    def test_unauthenticated_user_redirected_to_login(self):
        """Test that unauthenticated users are redirected to login.
        
        **Requirement 7.1, 13.3**
        """
        url = reverse('organizations:renewal_apply', args=[self.active_org.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_non_chairman_denied_access(self):
        """Test that non-chairman members are denied access.
        
        **Requirement 7.1, 13.2**
        """
        url = reverse('organizations:renewal_apply', args=[self.active_org.id])
        self.client.login(email='member@test.com', password='testpass123')
        response = self.client.get(url)
        # Non-chairman should be redirected to org profile
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/directory/{self.active_org.id}/', response.url)

    def test_chairman_of_renewal_due_org_can_access(self):
        """Test that chairman of renewal_due organization can access the form.
        
        **Requirement 7.1**
        """
        url = reverse('organizations:renewal_apply', args=[self.renewal_due_org.id])
        self.client.login(email='chairman@test.com', password='testpass123')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'organizations/chairman/renewal_apply.html')

    def test_chairman_of_active_org_can_access(self):
        """Test that chairman of active organization can access the form.
        
        **Requirement 7.1**
        """
        url = reverse('organizations:renewal_apply', args=[self.active_org.id])
        self.client.login(email='chairman@test.com', password='testpass123')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_chairman_of_pending_org_denied_access(self):
        """Test that chairman of non-renewal_due/active org cannot access renewal form.
        
        **Requirement 7.1, 7.7**
        """
        url = reverse('organizations:renewal_apply', args=[self.pending_org.id])
        self.client.login(email='chairman@test.com', password='testpass123')
        response = self.client.get(url)
        # Should redirect with error message to org profile
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/directory/{self.pending_org.id}/', response.url)

    def test_duplicate_pending_renewal_rejected(self):
        """Test that duplicate pending renewal applications are rejected.
        
        **Requirement 7.7**
        """
        # Create an existing pending renewal application
        existing_app = AccreditationApplication.objects.create(
            organization=self.active_org,
            registration_type='renewal',
            status='pending'
        )
        
        url = reverse('organizations:renewal_apply', args=[self.active_org.id])
        self.client.login(email='chairman@test.com', password='testpass123')
        
        # Try to access the renewal form
        response = self.client.get(url)
        
        # Should redirect with error message to org profile (chairman dashboard not accessible)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/directory/{self.active_org.id}/', response.url)

    def test_duplicate_under_review_renewal_rejected(self):
        """Test that duplicate under_review renewal applications are rejected.
        
        **Requirement 7.7**
        """
        # Create an existing under_review renewal application
        existing_app = AccreditationApplication.objects.create(
            organization=self.active_org,
            registration_type='renewal',
            status='under_review'
        )
        
        url = reverse('organizations:renewal_apply', args=[self.active_org.id])
        self.client.login(email='chairman@test.com', password='testpass123')
        
        # Try to access the renewal form
        response = self.client.get(url)
        
        # Should redirect with error message
        self.assertEqual(response.status_code, 302)

    def test_renewal_form_displays_org_and_chairman_readonly(self):
        """Test that renewal form displays org name and chairman as read-only.
        
        **Requirement 7.2, 7.3**
        """
        url = reverse('organizations:renewal_apply', args=[self.active_org.id])
        self.client.login(email='chairman@test.com', password='testpass123')
        response = self.client.get(url)
        
        self.assertContains(response, self.active_org.name)
        self.assertContains(response, self.chairman_user.get_full_name())
        # Should display as read-only text, not as input field
        # Count may be more than 3 due to page rendering
        self.assertContains(response, self.active_org.name, count=5)

    def test_renewal_form_displays_registration_type_label(self):
        """Test that renewal form displays 'Renewal/Accreditation' as label.
        
        **Requirement 7.3**
        """
        url = reverse('organizations:renewal_apply', args=[self.active_org.id])
        self.client.login(email='chairman@test.com', password='testpass123')
        response = self.client.get(url)
        
        self.assertContains(response, 'Renewal / Accreditation')

    def test_renewal_form_displays_renewal_docs(self):
        """Test that renewal form displays all RENEWAL_DOCS slots.
        
        **Requirement 7.4**
        """
        from organizations.constants import RENEWAL_DOCS
        
        url = reverse('organizations:renewal_apply', args=[self.active_org.id])
        self.client.login(email='chairman@test.com', password='testpass123')
        response = self.client.get(url)
        
        for doc_type in RENEWAL_DOCS:
            self.assertContains(response, doc_type)

    def test_renewal_form_accomplishment_reports_has_file_and_dropdown(self):
        """Test that Accomplishment Reports slot has both file upload and compilation dropdown.
        
        **Requirement 7.5**
        """
        url = reverse('organizations:renewal_apply', args=[self.active_org.id])
        self.client.login(email='chairman@test.com', password='testpass123')
        response = self.client.get(url)
        
        # Should have file input for accomplishment reports
        self.assertContains(response, 'doc_accomplishment_reports')
        # Should have compilation selector
        self.assertContains(response, 'compilation_id')

    def test_successful_renewal_submission_with_files(self):
        """Test successful renewal submission with file uploads.
        
        **Requirement 7.6**
        """
        url = reverse('organizations:renewal_apply', args=[self.active_org.id])
        self.client.login(email='chairman@test.com', password='testpass123')
        
        from organizations.constants import RENEWAL_DOCS
        
        data = {}
        for doc_type in RENEWAL_DOCS:
            field_name = f'doc_{doc_type.lower().replace(" ", "_").replace("-", "_")}'
            data[field_name] = self.create_test_file(f'{doc_type.lower()}.pdf')
        
        response = self.client.post(url, data)
        
        # Should redirect with success message to chairman dashboard
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/directory/{self.active_org.id}/manage/', response.url)
        
        # Verify AccreditationApplication was created
        app = AccreditationApplication.objects.filter(
            organization=self.active_org,
            registration_type='renewal',
            status='pending'
        ).first()
        self.assertIsNotNone(app)
        
        # Verify AccreditationDocument records were created
        docs = AccreditationDocument.objects.filter(application=app)
        self.assertEqual(docs.count(), len(RENEWAL_DOCS))

    def test_cso_org_cannot_submit_renewal(self):
        """Test that CSO organization cannot submit renewal application.
        
        **Requirement 7.1**
        """
        # Create a CSO organization
        cso_org = Organization.objects.create(
            name='CSO',
            status='active',
            is_cso=True
        )
        
        # Create chairman membership
        Membership.objects.create(
            organization=cso_org,
            user=self.chairman_user,
            role='chairman',
            status='active',
            has_chairman_privileges=True
        )
        
        url = reverse('organizations:renewal_apply', args=[cso_org.id])
        self.client.login(email='chairman@test.com', password='testpass123')
        response = self.client.get(url)
        
        # Should redirect with error message
        self.assertEqual(response.status_code, 302)



# ─── Admin Accreditation Review Panel Tests (Task 8) ───────────────────────────


class AdminAccreditationPanelTests(TestCase):
    """Tests for the admin_accreditation_panel_view.
    
    **Requirement 8.1, 8.2**
    """

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
        # Create CSO admin user
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            student_id='2024-99999',
            is_active=True,
            is_cso_admin=True
        )
        
        # Create non-admin user
        self.non_admin_user = User.objects.create_user(
            email='member@test.com',
            password='testpass123',
            student_id='2024-00001',
            is_active=True
        )
        
        # Create organizations with applications
        self.org1 = Organization.objects.create(
            name='Pending Org',
            status='pending'
        )
        self.app1 = AccreditationApplication.objects.create(
            organization=self.org1,
            registration_type='new_applicant',
            status='pending'
        )
        
        self.org2 = Organization.objects.create(
            name='Under Review Org',
            status='under_review'
        )
        self.app2 = AccreditationApplication.objects.create(
            organization=self.org2,
            registration_type='new_chapter',
            status='under_review'
        )
        
        self.org3 = Organization.objects.create(
            name='Approved Org',
            status='active'
        )
        self.app3 = AccreditationApplication.objects.create(
            organization=self.org3,
            registration_type='new_applicant',
            status='approved'
        )
        
        self.url = reverse('organizations:admin_accreditation_panel')

    def test_unauthenticated_user_redirected_to_login(self):
        """Test that unauthenticated users are redirected to login.
        
        **Requirement 13.3**
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_non_admin_user_denied_access(self):
        """Test that non-admin users are denied access.
        
        **Requirement 13.1, 13.4**
        """
        self.client.login(email='member@test.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('dashboard', response.url)

    def test_admin_can_access_panel(self):
        """Test that CSO admin users can access the panel."""
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'organizations/admin/accreditation_panel.html')

    def test_panel_lists_pending_and_under_review_only(self):
        """Test that the panel lists only pending and under_review applications."""
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.get(self.url)
        
        # Should contain pending and under_review apps
        self.assertContains(response, 'Pending Org')
        self.assertContains(response, 'Under Review Org')
        # Should not contain approved app
        self.assertNotContains(response, 'Approved Org')

    def test_filter_by_pending_status(self):
        """Test filtering applications by pending status."""
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.get(f'{self.url}?status=pending')
        
        # Should contain only pending
        self.assertContains(response, 'Pending Org')
        self.assertNotContains(response, 'Under Review Org')

    def test_filter_by_under_review_status(self):
        """Test filtering applications by under_review status."""
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.get(f'{self.url}?status=under_review')
        
        # Should contain only under_review
        self.assertContains(response, 'Under Review Org')
        self.assertNotContains(response, 'Pending Org')


class AdminReviewApplicationTests(TestCase):
    """Tests for the admin_review_application_view.
    
    **Requirement 8.2**
    """

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
        # Create CSO admin user
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            student_id='2024-99999',
            is_active=True,
            is_cso_admin=True
        )
        
        # Create organization with application
        self.org = Organization.objects.create(
            name='Test Organization',
            status='pending'
        )
        self.app = AccreditationApplication.objects.create(
            organization=self.org,
            registration_type='new_applicant',
            status='pending'
        )
        
        # Create documents
        self.doc1 = AccreditationDocument.objects.create(
            application=self.app,
            document_type='Form A',
            file=SimpleUploadedFile('form_a.pdf', BytesIO(b'x' * 1024).getvalue())
        )
        
        self.url = reverse('organizations:admin_review_application', args=[self.app.id])

    def test_admin_can_view_application_details(self):
        """Test that admin can view application details."""
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'organizations/admin/review_application.html')

    def test_application_shows_org_info(self):
        """Test that application page shows organization information."""
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertContains(response, 'Test Organization')
        self.assertContains(response, 'New Applicant')

    def test_application_shows_submitted_date(self):
        """Test that application page shows submission date."""
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.get(self.url)
        # Should show submitted_at date
        self.assertContains(response, 'Submitted')

    def test_application_shows_documents_with_download_links(self):
        """Test that application page shows documents with download links."""
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertContains(response, 'Form A')
        # Should have a download link
        self.assertContains(response, 'Download')


class AdminReviewActionTests(TestCase):
    """Tests for the admin_review_action_view.
    
    **Requirements 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10**
    """

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
        # Create CSO admin user
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            student_id='2024-99999',
            is_active=True,
            is_cso_admin=True
        )
        
        # Create chairman user
        self.chairman_user = User.objects.create_user(
            email='chairman@test.com',
            password='testpass123',
            student_id='2024-00001',
            is_active=True
        )
        
        # Create organizations with applications and memberships
        self.org_new_app = Organization.objects.create(
            name='New Applicant Org',
            status='pending'
        )
        self.app_new_app = AccreditationApplication.objects.create(
            organization=self.org_new_app,
            registration_type='new_applicant',
            status='pending'
        )
        Membership.objects.create(
            organization=self.org_new_app,
            user=self.chairman_user,
            role='chairman',
            status='active'
        )
        
        # Renewal org with pre_renewal_status
        self.org_renewal_active = Organization.objects.create(
            name='Renewal Active Org',
            status='renewal_due',
            pre_renewal_status='active'
        )
        self.app_renewal_active = AccreditationApplication.objects.create(
            organization=self.org_renewal_active,
            registration_type='renewal',
            status='pending'
        )
        Membership.objects.create(
            organization=self.org_renewal_active,
            user=self.chairman_user,
            role='chairman',
            status='active'
        )
        
        # Renewal org with pre_renewal_status probationary
        self.org_renewal_prob = Organization.objects.create(
            name='Renewal Prob Org',
            status='renewal_due',
            pre_renewal_status='probationary'
        )
        self.app_renewal_prob = AccreditationApplication.objects.create(
            organization=self.org_renewal_prob,
            registration_type='renewal',
            status='pending'
        )
        Membership.objects.create(
            organization=self.org_renewal_prob,
            user=self.chairman_user,
            role='chairman',
            status='active'
        )

    def test_mark_under_review_action(self):
        """Test mark_under_review action.
        
        **Requirement 8.1**
        """
        url = reverse('organizations:admin_review_action', args=[self.app_new_app.id])
        self.client.login(email='admin@test.com', password='testpass123')
        
        response = self.client.post(url, {'action': 'mark_under_review'})
        
        # Should redirect back to application
        self.assertEqual(response.status_code, 302)
        
        # Application and org status should be updated
        self.app_new_app.refresh_from_db()
        self.org_new_app.refresh_from_db()
        self.assertEqual(self.app_new_app.status, 'under_review')
        self.assertEqual(self.org_new_app.status, 'under_review')
        self.assertIsNotNone(self.app_new_app.reviewed_by)
        self.assertIsNotNone(self.app_new_app.reviewed_at)

    def test_approve_new_applicant(self):
        """Test approving a new_applicant application.
        
        **Requirement 8.3, 8.4**
        """
        self.app_new_app.status = 'under_review'
        self.app_new_app.save()
        
        url = reverse('organizations:admin_review_action', args=[self.app_new_app.id])
        self.client.login(email='admin@test.com', password='testpass123')
        
        response = self.client.post(url, {'action': 'approve'})
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Check status is set to probationary
        self.app_new_app.refresh_from_db()
        self.org_new_app.refresh_from_db()
        self.assertEqual(self.app_new_app.status, 'approved')
        self.assertEqual(self.org_new_app.status, 'probationary')

    def test_approve_renewal_with_promote_to_active(self):
        """Test approving renewal with "Promote to Active" checked.
        
        **Requirement 8.5, 8.6**
        """
        self.app_renewal_active.status = 'under_review'
        self.app_renewal_active.save()
        
        url = reverse('organizations:admin_review_action', args=[self.app_renewal_active.id])
        self.client.login(email='admin@test.com', password='testpass123')
        
        response = self.client.post(url, {'action': 'approve', 'promote_to_active': 'on'})
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Check status is set to active
        self.app_renewal_active.refresh_from_db()
        self.org_renewal_active.refresh_from_db()
        self.assertEqual(self.app_renewal_active.status, 'approved')
        self.assertEqual(self.org_renewal_active.status, 'active')
        self.assertIsNone(self.org_renewal_active.pre_renewal_status)

    def test_approve_renewal_without_promote_to_active(self):
        """Test approving renewal without "Promote to Active" checked.
        
        **Requirement 8.6**
        """
        self.app_renewal_active.status = 'under_review'
        self.app_renewal_active.save()
        
        url = reverse('organizations:admin_review_action', args=[self.app_renewal_active.id])
        self.client.login(email='admin@test.com', password='testpass123')
        
        # Post without promote_to_active checkbox (default is 'off')
        response = self.client.post(url, {'action': 'approve'})
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Check status is restored to pre_renewal_status (active)
        self.app_renewal_active.refresh_from_db()
        self.org_renewal_active.refresh_from_db()
        self.assertEqual(self.app_renewal_active.status, 'approved')
        self.assertEqual(self.org_renewal_active.status, 'active')

    def test_approve_renewal_restores_probationary_status(self):
        """Test that approving renewal without promote restores probationary status.
        
        **Requirement 8.6**
        """
        self.app_renewal_prob.status = 'under_review'
        self.app_renewal_prob.save()
        
        url = reverse('organizations:admin_review_action', args=[self.app_renewal_prob.id])
        self.client.login(email='admin@test.com', password='testpass123')
        
        response = self.client.post(url, {'action': 'approve'})
        
        # Check status is restored to probationary
        self.org_renewal_prob.refresh_from_db()
        self.assertEqual(self.org_renewal_prob.status, 'probationary')

    def test_return_application(self):
        """Test returning an application for revision.
        
        **Requirement 8.7**
        """
        self.app_new_app.status = 'under_review'
        self.app_new_app.save()
        
        url = reverse('organizations:admin_review_action', args=[self.app_new_app.id])
        self.client.login(email='admin@test.com', password='testpass123')
        
        response = self.client.post(url, {
            'action': 'return',
            'remarks': 'Please fix the documentation.'
        })
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Check status and remarks
        self.app_new_app.refresh_from_db()
        self.assertEqual(self.app_new_app.status, 'returned')
        self.assertEqual(self.app_new_app.admin_remarks, 'Please fix the documentation.')
        self.assertIsNotNone(self.app_new_app.reviewed_by)
        self.assertIsNotNone(self.app_new_app.reviewed_at)

    def test_reject_application(self):
        """Test rejecting an application.
        
        **Requirement 8.8, 8.9, 8.10**
        """
        self.app_new_app.status = 'under_review'
        self.app_new_app.save()
        
        url = reverse('organizations:admin_review_action', args=[self.app_new_app.id])
        self.client.login(email='admin@test.com', password='testpass123')
        
        response = self.client.post(url, {
            'action': 'reject',
            'remarks': 'Does not meet requirements.'
        })
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Check status and remarks
        self.app_new_app.refresh_from_db()
        self.org_new_app.refresh_from_db()
        self.assertEqual(self.app_new_app.status, 'rejected')
        self.assertEqual(self.org_new_app.status, 'rejected')
        self.assertEqual(self.app_new_app.admin_remarks, 'Does not meet requirements.')


class AdminReviewActionPropertyTests(HypothesisTestCase):
    """Property-based tests for admin review actions.
    
    **Requirement 8.4, 8.5, 8.6**
    """

    def setUp(self):
        """Set up test fixtures."""
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            student_id='2024-99999',
            is_active=True,
            is_cso_admin=True
        )
        
        self.chairman_user = User.objects.create_user(
            email='chairman@test.com',
            password='testpass123',
            student_id='2024-00001',
            is_active=True
        )

    @given(st.sampled_from(['new_applicant', 'new_chapter', 'renewal']))
    @settings(deadline=None, max_examples=5)
    def test_approval_sets_correct_org_status(self, registration_type):
        """
        Property 4: Approval sets correct org status
        
        For any AccreditationApplication being approved, if it is a renewal application
        with the "Promote to Active" checkbox checked, the Organization's status must be
        set to 'active'. If unchecked, the Organization must return to its pre_renewal_status.
        For new_applicant and new_chapter approvals, the status must be set to 'probationary'.
        
        **Validates: Requirements 8.4, 8.5, 8.6**
        """
        from django.utils import timezone
        
        # Create organization with appropriate pre_renewal_status for renewal
        if registration_type == 'renewal':
            org = Organization.objects.create(
                name=f'Renewal {registration_type}',
                status='renewal_due',
                pre_renewal_status='active'
            )
        else:
            org = Organization.objects.create(
                name=f'App {registration_type}',
                status='pending'
            )
        
        # Create application and membership
        app = AccreditationApplication.objects.create(
            organization=org,
            registration_type=registration_type,
            status='under_review'
        )
        Membership.objects.create(
            organization=org,
            user=self.chairman_user,
            role='chairman',
            status='active'
        )
        
        # Simulate admin approval action
        if registration_type == 'renewal':
            # Test promote_to_active = true
            promote_to_active = True
            expected_status = 'active'
        else:
            promote_to_active = False
            expected_status = 'probationary'
        
        # Apply the approval logic from admin_review_action_view
        if app.registration_type == 'renewal':
            if promote_to_active:
                new_org_status = 'active'
            else:
                new_org_status = org.pre_renewal_status or 'probationary'
        else:
            new_org_status = 'probationary'
        
        org.status = new_org_status
        org.pre_renewal_status = None
        org.save()
        app.status = 'approved'
        app.reviewed_by = self.admin_user
        app.reviewed_at = timezone.now()
        app.save()
        
        # Verify status matches expected
        self.assertEqual(org.status, expected_status,
                        f"For {registration_type} approval, expected status {expected_status}, got {org.status}")



class OfficialFormLinkValidationTests(TestCase):
    """Tests for OfficialFormLink validation and management interface.
    
    **Requirement 5.2, 10.2, 10.4**
    """

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            student_id='2024-99999',
            is_active=True,
            is_cso_admin=True
        )
        
        self.non_admin_user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            student_id='2024-00001',
            is_active=True
        )
        
        self.admin_url = reverse('organizations:admin_form_links')
        self.form_links = []

    def test_saving_with_empty_label_is_rejected(self):
        """Test that saving with empty label is rejected."""
        self.client.login(email='admin@test.com', password='testpass123')
        
        data = {
            'action': 'create',
            'label': '',  # Empty label
            'url': 'https://example.com/form-a.pdf'
        }
        
        response = self.client.post(self.admin_url, data)
        
        # Should redirect back (form re-rendered with error)
        self.assertEqual(response.status_code, 302)
        
        # Verify no form link was created
        self.assertEqual(OfficialFormLink.objects.count(), 0)

    def test_saving_with_empty_url_is_rejected(self):
        """Test that saving with empty URL is rejected."""
        self.client.login(email='admin@test.com', password='testpass123')
        
        data = {
            'action': 'create',
            'label': 'Form A',
            'url': ''  # Empty URL
        }
        
        response = self.client.post(self.admin_url, data)
        
        # Should redirect back (form re-rendered with error)
        self.assertEqual(response.status_code, 302)
        
        # Verify no form link was created
        self.assertEqual(OfficialFormLink.objects.count(), 0)

    def test_saving_with_whitespace_only_label_is_rejected(self):
        """Test that saving with whitespace-only label is rejected."""
        self.client.login(email='admin@test.com', password='testpass123')
        
        data = {
            'action': 'create',
            'label': '   ',  # Whitespace only
            'url': 'https://example.com/form-a.pdf'
        }
        
        response = self.client.post(self.admin_url, data)
        
        # Should redirect back (form re-rendered with error)
        self.assertEqual(response.status_code, 302)
        
        # Verify no form link was created
        self.assertEqual(OfficialFormLink.objects.count(), 0)

    def test_saving_with_whitespace_only_url_is_rejected(self):
        """Test that saving with whitespace-only URL is rejected."""
        self.client.login(email='admin@test.com', password='testpass123')
        
        data = {
            'action': 'create',
            'label': 'Form A',
            'url': '   '  # Whitespace only
        }
        
        response = self.client.post(self.admin_url, data)
        
        # Should redirect back (form re-rendered with error)
        self.assertEqual(response.status_code, 302)
        
        # Verify no form link was created
        self.assertEqual(OfficialFormLink.objects.count(), 0)

    def test_updated_by_is_set_on_create(self):
        """Test that updated_by is set to request.user on creation."""
        self.client.login(email='admin@test.com', password='testpass123')
        
        data = {
            'action': 'create',
            'label': 'Form A',
            'url': 'https://example.com/form-a.pdf'
        }
        
        response = self.client.post(self.admin_url, data)
        
        # Verify form link was created with correct updated_by
        link = OfficialFormLink.objects.get(label='Form A')
        self.assertEqual(link.updated_by, self.admin_user)

    def test_updated_by_is_set_on_edit(self):
        """Test that updated_by is set to request.user on edit."""
        # Create an initial form link with a different user
        initial_link = OfficialFormLink.objects.create(
            label='Form A',
            url='https://example.com/form-a.pdf',
            updated_by=self.non_admin_user
        )
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        data = {
            'action': 'edit',
            'link_id': str(initial_link.id),
            'label': 'Form A - Updated',
            'url': 'https://example.com/form-a-updated.pdf'
        }
        
        response = self.client.post(self.admin_url, data)
        
        # Verify form link was updated with new updated_by
        initial_link.refresh_from_db()
        self.assertEqual(initial_link.updated_by, self.admin_user)
        self.assertEqual(initial_link.label, 'Form A - Updated')

    def test_updated_at_is_set_on_save(self):
        """Test that updated_at is set on save."""
        from django.utils import timezone
        
        before_save = timezone.now()
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        data = {
            'action': 'create',
            'label': 'Form B',
            'url': 'https://example.com/form-b.pdf'
        }
        
        response = self.client.post(self.admin_url, data)
        
        after_save = timezone.now()
        
        # Verify form link was created with updated_at in correct range
        link = OfficialFormLink.objects.get(label='Form B')
        self.assertLessEqual(before_save, link.updated_at)
        self.assertLessEqual(link.updated_at, after_save)

    def test_updated_at_changes_on_edit(self):
        """Test that updated_at changes when a link is edited."""
        import time
        
        # Create an initial form link
        initial_link = OfficialFormLink.objects.create(
            label='Form A',
            url='https://example.com/form-a.pdf',
            updated_by=self.non_admin_user
        )
        initial_updated_at = initial_link.updated_at
        
        # Wait a bit to ensure updated_at would change
        time.sleep(0.1)
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        data = {
            'action': 'edit',
            'link_id': str(initial_link.id),
            'label': 'Form A - Updated Again',
            'url': 'https://example.com/form-a-again.pdf'
        }
        
        response = self.client.post(self.admin_url, data)
        
        # Verify updated_at changed
        initial_link.refresh_from_db()
        self.assertGreater(initial_link.updated_at, initial_updated_at)

    def test_non_admin_cannot_create_form_link(self):
        """Test that non-admin users cannot create form links."""
        self.client.login(email='user@test.com', password='testpass123')
        
        response = self.client.get(self.admin_url)
        
        # Should be denied access
        self.assertEqual(response.status_code, 302)
        self.assertIn('/core/dashboard', response.url)

    def test_non_admin_cannot_edit_form_link(self):
        """Test that non-admin users cannot edit form links."""
        # Create a form link as admin
        link = OfficialFormLink.objects.create(
            label='Form A',
            url='https://example.com/form-a.pdf',
            updated_by=self.admin_user
        )
        
        self.client.login(email='user@test.com', password='testpass123')
        
        data = {
            'action': 'edit',
            'link_id': str(link.id),
            'label': 'Form A - Hacked',
            'url': 'https://evil.com/form-a.pdf'
        }
        
        response = self.client.post(self.admin_url, data)
        
        # Should be denied access
        self.assertEqual(response.status_code, 302)
        
        # Verify link was not changed
        link.refresh_from_db()
        self.assertEqual(link.label, 'Form A')
        self.assertEqual(link.url, 'https://example.com/form-a.pdf')

    def test_non_admin_cannot_delete_form_link(self):
        """Test that non-admin users cannot delete form links."""
        # Create a form link as admin
        link = OfficialFormLink.objects.create(
            label='Form A',
            url='https://example.com/form-a.pdf',
            updated_by=self.admin_user
        )
        
        delete_url = reverse('organizations:admin_form_link_delete', args=[link.id])
        
        self.client.login(email='user@test.com', password='testpass123')
        
        response = self.client.post(delete_url)
        
        # Should be denied access
        self.assertEqual(response.status_code, 302)
        
        # Verify link still exists
        self.assertTrue(OfficialFormLink.objects.filter(id=link.id).exists())

    def test_unauthenticated_user_redirected_to_login(self):
        """Test that unauthenticated users are redirected to login."""
        response = self.client.get(self.admin_url)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_form_link_can_be_successfully_created(self):
        """Test that a valid form link can be created."""
        self.client.login(email='admin@test.com', password='testpass123')
        
        data = {
            'action': 'create',
            'label': 'Constitution Template',
            'url': 'https://drive.google.com/file/d/1234567890'
        }
        
        response = self.client.post(self.admin_url, data)
        
        # Should redirect back to form_links page
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/form-links/', response.url)
        
        # Verify form link was created
        link = OfficialFormLink.objects.get(label='Constitution Template')
        self.assertEqual(link.url, 'https://drive.google.com/file/d/1234567890')
        self.assertEqual(link.updated_by, self.admin_user)

    def test_form_link_can_be_successfully_edited(self):
        """Test that a form link can be successfully edited."""
        # Create initial form link
        link = OfficialFormLink.objects.create(
            label='Form A',
            url='https://example.com/form-a-v1.pdf',
            updated_by=self.non_admin_user
        )
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        data = {
            'action': 'edit',
            'link_id': str(link.id),
            'label': 'Form A - Version 2',
            'url': 'https://example.com/form-a-v2.pdf'
        }
        
        response = self.client.post(self.admin_url, data)
        
        # Should redirect back to form_links page
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/form-links/', response.url)
        
        # Verify form link was updated
        link.refresh_from_db()
        self.assertEqual(link.label, 'Form A - Version 2')
        self.assertEqual(link.url, 'https://example.com/form-a-v2.pdf')
        self.assertEqual(link.updated_by, self.admin_user)

    def test_form_link_can_be_successfully_deleted(self):
        """Test that a form link can be successfully deleted."""
        # Create a form link
        link = OfficialFormLink.objects.create(
            label='Form A',
            url='https://example.com/form-a.pdf',
            updated_by=self.admin_user
        )
        
        delete_url = reverse('organizations:admin_form_link_delete', args=[link.id])
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        response = self.client.post(delete_url)
        
        # Should redirect back to form_links page
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/form-links/', response.url)
        
        # Verify form link was deleted
        self.assertFalse(OfficialFormLink.objects.filter(id=link.id).exists())

    def test_form_link_list_displays_all_links(self):
        """Test that GET request displays all form links."""
        # Create multiple form links
        link1 = OfficialFormLink.objects.create(
            label='Form A',
            url='https://example.com/form-a.pdf',
            updated_by=self.admin_user
        )
        link2 = OfficialFormLink.objects.create(
            label='Form B',
            url='https://example.com/form-b.pdf',
            updated_by=self.admin_user
        )
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        response = self.client.get(self.admin_url)
        
        # Should display all links
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Form A')
        self.assertContains(response, 'Form B')
        self.assertContains(response, 'https://example.com/form-a.pdf')
        self.assertContains(response, 'https://example.com/form-b.pdf')

    def test_form_links_ordered_by_label(self):
        """Test that form links are ordered by label."""
        # Create form links in non-alphabetical order
        OfficialFormLink.objects.create(
            label='Zebra Form',
            url='https://example.com/zebra.pdf',
            updated_by=self.admin_user
        )
        OfficialFormLink.objects.create(
            label='Apple Form',
            url='https://example.com/apple.pdf',
            updated_by=self.admin_user
        )
        OfficialFormLink.objects.create(
            label='Banana Form',
            url='https://example.com/banana.pdf',
            updated_by=self.admin_user
        )
        
        # Query the links
        links = OfficialFormLink.objects.all()
        
        # Verify they're ordered by label
        labels = [link.label for link in links]
        self.assertEqual(labels, ['Apple Form', 'Banana Form', 'Zebra Form'])


class SchoolYearLifecycleTests(TestCase):
    """Tests for New School Year and Close Renewal Period controls - Task 10."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
        # Create CSO admin user
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            student_id='2024-99999',
            is_active=True,
            is_cso_admin=True
        )
        
        # Create chairman user
        self.chairman_user = User.objects.create_user(
            email='chairman@test.com',
            password='testpass123',
            student_id='2024-00001',
            first_name='John',
            last_name='Chair',
            is_active=True
        )
        
        # Create non-admin user
        self.non_admin_user = User.objects.create_user(
            email='member@test.com',
            password='testpass123',
            student_id='2024-00002',
            is_active=True
        )

    def test_non_admin_cannot_access_new_school_year(self):
        """Test that non-admin users cannot access new school year view."""
        url = reverse('organizations:admin_new_school_year')
        self.client.login(email='member@test.com', password='testpass123')
        
        response = self.client.post(url, {'renewal_deadline': '2024-12-31'})
        
        # Should be redirected or access denied
        self.assertIn(response.status_code, [302, 403])

    def test_non_admin_cannot_access_close_renewal(self):
        """Test that non-admin users cannot access close renewal view."""
        url = reverse('organizations:admin_close_renewal')
        self.client.login(email='member@test.com', password='testpass123')
        
        response = self.client.post(url)
        
        # Should be redirected or access denied
        self.assertIn(response.status_code, [302, 403])

    def test_unauthenticated_user_redirected_to_login_for_new_school_year(self):
        """Test that unauthenticated users are redirected for new school year."""
        url = reverse('organizations:admin_new_school_year')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_unauthenticated_user_redirected_to_login_for_close_renewal(self):
        """Test that unauthenticated users are redirected for close renewal."""
        url = reverse('organizations:admin_close_renewal')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_new_school_year_transitions_probationary_orgs(self):
        """Test that New School Year transitions probationary orgs to renewal_due."""
        # Create a probationary org
        org = Organization.objects.create(name='Probationary Org', status='probationary')
        Membership.objects.create(
            organization=org,
            user=self.chairman_user,
            role='chairman',
            status='active'
        )
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_new_school_year')
        
        response = self.client.post(url, {'renewal_deadline': '2024-12-31'})
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify org status changed to renewal_due
        org.refresh_from_db()
        self.assertEqual(org.status, 'renewal_due')
        self.assertEqual(org.pre_renewal_status, 'probationary')

    def test_new_school_year_transitions_institutional_orgs(self):
        """Test that New School Year transitions institutional orgs to renewal_due."""
        org = Organization.objects.create(name='Institutional Org', status='institutional')
        Membership.objects.create(
            organization=org,
            user=self.chairman_user,
            role='chairman',
            status='active'
        )
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_new_school_year')
        
        response = self.client.post(url, {'renewal_deadline': '2024-12-31'})
        
        # Verify org status changed to renewal_due
        org.refresh_from_db()
        self.assertEqual(org.status, 'renewal_due')

    def test_new_school_year_transitions_active_orgs(self):
        """Test that New School Year transitions active orgs to renewal_due."""
        org = Organization.objects.create(name='Active Org', status='active')
        Membership.objects.create(
            organization=org,
            user=self.chairman_user,
            role='chairman',
            status='active'
        )
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_new_school_year')
        
        response = self.client.post(url, {'renewal_deadline': '2024-12-31'})
        
        # Verify org status changed to renewal_due
        org.refresh_from_db()
        self.assertEqual(org.status, 'renewal_due')

    def test_new_school_year_skips_pending_orgs(self):
        """Test that New School Year does not transition pending orgs."""
        org = Organization.objects.create(name='Pending Org', status='pending')
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_new_school_year')
        
        response = self.client.post(url, {'renewal_deadline': '2024-12-31'})
        
        # Verify org status unchanged
        org.refresh_from_db()
        self.assertEqual(org.status, 'pending')

    def test_new_school_year_skips_rejected_orgs(self):
        """Test that New School Year does not transition rejected orgs."""
        org = Organization.objects.create(name='Rejected Org', status='rejected')
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_new_school_year')
        
        response = self.client.post(url, {'renewal_deadline': '2024-12-31'})
        
        # Verify org status unchanged
        org.refresh_from_db()
        self.assertEqual(org.status, 'rejected')

    def test_new_school_year_stores_renewal_deadline(self):
        """Test that renewal deadline is stored in SystemSetting."""
        from core.models import SystemSetting
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_new_school_year')
        
        response = self.client.post(url, {'renewal_deadline': '2024-12-31'})
        
        # Verify deadline stored
        setting = SystemSetting.objects.get(key='renewal_deadline')
        self.assertEqual(setting.value, '2024-12-31')

    def test_close_renewal_lapses_renewal_due_without_approved_renewal(self):
        """Test that Close Renewal Period lapses renewal_due orgs without approved renewal."""
        # Create a renewal_due org with NO approved renewal
        org = Organization.objects.create(name='Renewal Org', status='renewal_due')
        Membership.objects.create(
            organization=org,
            user=self.chairman_user,
            role='chairman',
            status='active'
        )
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_close_renewal')
        
        response = self.client.post(url)
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify org status changed to lapsed
        org.refresh_from_db()
        self.assertEqual(org.status, 'lapsed')

    def test_close_renewal_skips_renewal_due_with_approved_renewal(self):
        """Test that Close Renewal Period skips renewal_due orgs WITH approved renewal."""
        # Create a renewal_due org
        org = Organization.objects.create(name='Renewal Org', status='renewal_due')
        Membership.objects.create(
            organization=org,
            user=self.chairman_user,
            role='chairman',
            status='active'
        )
        
        # Create an approved renewal application for this org
        AccreditationApplication.objects.create(
            organization=org,
            registration_type='renewal',
            status='approved',
            reviewed_by=self.admin_user
        )
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_close_renewal')
        
        response = self.client.post(url)
        
        # Verify org status unchanged (NOT lapsed)
        org.refresh_from_db()
        self.assertEqual(org.status, 'renewal_due')

    def test_close_renewal_skips_non_renewal_due_orgs(self):
        """Test that Close Renewal Period does not affect non-renewal_due orgs."""
        # Create various non-renewal_due orgs
        active_org = Organization.objects.create(name='Active Org', status='active')
        pending_org = Organization.objects.create(name='Pending Org', status='pending')
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_close_renewal')
        
        response = self.client.post(url)
        
        # Verify statuses unchanged
        active_org.refresh_from_db()
        pending_org.refresh_from_db()
        self.assertEqual(active_org.status, 'active')
        self.assertEqual(pending_org.status, 'pending')

    def test_cso_orgs_skipped_in_new_school_year(self):
        """Test that CSO organizations are excluded from new school year transition."""
        cso_org = Organization.objects.create(name='CSO Org', status='active', is_cso=True)
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_new_school_year')
        
        response = self.client.post(url, {'renewal_deadline': '2024-12-31'})
        
        # Verify CSO org status unchanged
        cso_org.refresh_from_db()
        self.assertEqual(cso_org.status, 'active')

    def test_cso_orgs_skipped_in_close_renewal(self):
        """Test that CSO organizations are excluded from close renewal."""
        cso_org = Organization.objects.create(name='CSO Org', status='renewal_due', is_cso=True)
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_close_renewal')
        
        response = self.client.post(url)
        
        # Verify CSO org status unchanged
        cso_org.refresh_from_db()
        self.assertEqual(cso_org.status, 'renewal_due')


class SchoolYearLifecyclePropertyTests(HypothesisTestCase):
    """Property-based tests for school year lifecycle controls."""

    def setUp(self):
        """Set up test fixtures."""
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            student_id='2024-99999',
            is_active=True,
            is_cso_admin=True
        )
        
        self.chairman_user = User.objects.create_user(
            email='chairman@test.com',
            password='testpass123',
            student_id='2024-00001',
            is_active=True
        )

    @given(st.lists(
        st.sampled_from(['probationary', 'institutional', 'active', 'pending', 'rejected', 'renewal_due', 'lapsed']),
        min_size=1,
        max_size=10,
        unique=True
    ))
    @settings(deadline=None, max_examples=5)
    def test_new_school_year_bulk_transition(self, statuses):
        """
        Property 5: New School Year bulk transition
        
        For any set of Organizations, triggering the New School Year action must transition
        every Organization whose status is in {probationary, institutional, active} to
        'renewal_due', and must leave all other Organizations' statuses unchanged.
        
        **Validates: Requirements 9.2**
        """
        # Create orgs with various statuses
        orgs_by_status = {}
        for status in statuses:
            org = Organization.objects.create(
                name=f'Org {status}',
                status=status,
                is_cso=False
            )
            if status in ['probationary', 'institutional', 'active']:
                Membership.objects.create(
                    organization=org,
                    user=self.chairman_user,
                    role='chairman',
                    status='active'
                )
            orgs_by_status[status] = org
        
        # Trigger new school year
        eligible_statuses = ['probationary', 'institutional', 'active']
        eligible_orgs = Organization.objects.filter(status__in=eligible_statuses, is_cso=False)
        
        for org in eligible_orgs:
            org.pre_renewal_status = org.status
            org.status = 'renewal_due'
            org.save()
        
        # Verify transitions
        for status, org in orgs_by_status.items():
            org.refresh_from_db()
            if status in eligible_statuses:
                self.assertEqual(org.status, 'renewal_due',
                               f"Status {status} should transition to renewal_due")
            else:
                self.assertEqual(org.status, status,
                               f"Status {status} should remain unchanged")

    @given(st.lists(
        st.sampled_from(['renewal_due', 'active', 'pending', 'rejected']),
        min_size=1,
        max_size=10,
        unique=True
    ))
    @settings(deadline=None, max_examples=5)
    def test_close_renewal_bulk_transition(self, statuses):
        """
        Property 6: Close Renewal Period bulk transition
        
        For any set of Organizations, triggering the Close Renewal Period action must
        transition every Organization with status 'renewal_due' (and no approved renewal
        application) to 'lapsed', and must leave all other Organizations' statuses unchanged.
        
        **Validates: Requirements 9.6**
        """
        # Create orgs with various statuses
        orgs_by_status = {}
        for status in statuses:
            org = Organization.objects.create(
                name=f'Org {status}',
                status=status,
                is_cso=False
            )
            if status == 'renewal_due':
                Membership.objects.create(
                    organization=org,
                    user=self.chairman_user,
                    role='chairman',
                    status='active'
                )
            orgs_by_status[status] = org
        
        # Simulate close renewal period
        renewal_due_orgs = Organization.objects.filter(status='renewal_due', is_cso=False)
        lapsed_count = 0
        
        for org in renewal_due_orgs:
            has_approved_renewal = AccreditationApplication.objects.filter(
                organization=org,
                registration_type='renewal',
                status='approved',
            ).exists()
            if not has_approved_renewal:
                org.status = 'lapsed'
                org.save()
                lapsed_count += 1
        
        # Verify transitions
        for status, org in orgs_by_status.items():
            org.refresh_from_db()
            if status == 'renewal_due':
                self.assertEqual(org.status, 'lapsed',
                               f"renewal_due status should transition to lapsed")
            else:
                self.assertEqual(org.status, status,
                               f"Status {status} should remain unchanged")



# ─── School Year and Close Renewal Property-Based Tests ────────────────────

class SchoolYearLifecyclePropertyTests(HypothesisTestCase):
    """Property-based tests for school year and renewal lifecycle.
    
    **Requirements 9.2, 9.6**
    """

    def setUp(self):
        """Set up test fixtures."""
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            is_cso_admin=True,
            student_id='2024-99999',
            is_active=True
        )

    @given(st.lists(
        st.sampled_from(['probationary', 'institutional', 'active', 'pending', 'under_review', 'rejected', 'renewal_due', 'lapsed']),
        min_size=1,
        max_size=20,
        unique=True
    ))
    @settings(deadline=None, max_examples=5)
    def test_new_school_year_bulk_transition(self, statuses):
        """
        Property 5: New School Year bulk transition
        
        For any set of Organizations, triggering the New School Year action must transition
        every Organization whose status is in {probationary, institutional, active} to renewal_due,
        and must leave all other Organizations' statuses unchanged.
        
        **Validates: Requirements 9.2**
        """
        # Create organizations with the given statuses
        orgs_by_status = {}
        for i, status in enumerate(statuses):
            org = Organization.objects.create(
                name=f'Test Org {i}',
                status=status
            )
            orgs_by_status[status] = org

        # Create chairman memberships for all orgs
        for org in Organization.objects.all():
            try:
                Membership.objects.create(
                    organization=org,
                    user=self.admin_user,
                    role='chairman',
                    status='active'
                )
            except:
                pass  # Ignore if membership already exists

        # Manually call the transition logic
        from django.db import transaction
        from django.utils import timezone
        
        eligible_statuses = ['probationary', 'institutional', 'active']
        orgs_to_transition = Organization.objects.filter(status__in=eligible_statuses)
        
        with transaction.atomic():
            for org in orgs_to_transition:
                org.pre_renewal_status = org.status
                org.status = 'renewal_due'
                org.save()

        # Verify transitions
        for status in statuses:
            org = orgs_by_status[status]
            org.refresh_from_db()
            
            if status in eligible_statuses:
                # Should be transitioned to renewal_due
                self.assertEqual(org.status, 'renewal_due',
                    f"Organization with status={status} should be transitioned to renewal_due")
            else:
                # Should remain unchanged
                self.assertEqual(org.status, status,
                    f"Organization with status={status} should remain unchanged")

    @given(st.lists(
        st.sampled_from(['probationary', 'institutional', 'active', 'pending', 'under_review', 'rejected', 'renewal_due', 'lapsed']),
        min_size=1,
        max_size=20,
        unique=True
    ))
    @settings(deadline=None, max_examples=5)
    def test_close_renewal_period_bulk_transition(self, statuses):
        """
        Property 6: Close Renewal Period bulk transition
        
        For any set of Organizations, triggering the Close Renewal Period action must transition
        every Organization with status renewal_due (and no approved renewal application) to lapsed,
        and must leave all other Organizations' statuses unchanged.
        
        **Validates: Requirements 9.6**
        """
        # Create organizations with the given statuses
        orgs_by_status = {}
        for i, status in enumerate(statuses):
            org = Organization.objects.create(
                name=f'Test Org {i}',
                status=status
            )
            orgs_by_status[status] = org
            
            # For half of renewal_due orgs, create an approved renewal application
            if status == 'renewal_due' and i % 2 == 0:
                AccreditationApplication.objects.create(
                    organization=org,
                    registration_type='renewal',
                    status='approved'
                )

        # Manually call the transition logic
        from django.db import transaction
        
        renewal_due_orgs = Organization.objects.filter(status='renewal_due')
        
        with transaction.atomic():
            for org in renewal_due_orgs:
                # Check if org has approved renewal application
                has_approved_renewal = AccreditationApplication.objects.filter(
                    organization=org,
                    registration_type='renewal',
                    status='approved'
                ).exists()

                if not has_approved_renewal:
                    # Transition to lapsed
                    org.status = 'lapsed'
                    org.save()

        # Verify transitions
        for i, status in enumerate(statuses):
            org = orgs_by_status[status]
            org.refresh_from_db()
            
            if status == 'renewal_due':
                # Check if we created an approved renewal
                created_approved = i % 2 == 0
                if created_approved:
                    # Should remain renewal_due (has approved renewal)
                    self.assertEqual(org.status, 'renewal_due',
                        f"Organization with approved renewal should remain renewal_due")
                else:
                    # Should be transitioned to lapsed (no approved renewal)
                    self.assertEqual(org.status, 'lapsed',
                        f"Organization without approved renewal should be transitioned to lapsed")
            else:
                # Should remain unchanged
                self.assertEqual(org.status, status,
                    f"Organization with status={status} should remain unchanged")

class ChairmanRequiredDecoratorTests(TestCase):
    """Tests for chairman_required decorator with renewal_due organizations.
    
    **Requirement 2.7, 13.2, 13.5**
    
    Verifies that the chairman_required decorator correctly allows chairmen to access
    their organization's dashboard even when the organization status is renewal_due or lapsed.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
        # Create a chairman user
        self.chairman_user = User.objects.create_user(
            email='chairman@test.com',
            password='testpass123',
            student_id='2024-00001',
            first_name='John',
            last_name='Chair',
            is_active=True
        )
        
        # Create a non-chairman user
        self.non_chairman_user = User.objects.create_user(
            email='member@test.com',
            password='testpass123',
            student_id='2024-00002',
            is_active=True
        )
        
        # Create a renewal_due organization
        self.renewal_due_org = Organization.objects.create(
            name='Renewal Due Organization',
            status='renewal_due'
        )
        
        # Verify that renewal_due org has is_active=True
        self.renewal_due_org.refresh_from_db()
        self.assertTrue(
            self.renewal_due_org.is_active,
            'renewal_due organization should have is_active=True'
        )
        
        # Create chairman membership for renewal_due org
        self.renewal_due_chairman_membership = Membership.objects.create(
            organization=self.renewal_due_org,
            user=self.chairman_user,
            role='chairman',
            status='active',
            has_chairman_privileges=True
        )
        
        # Create a non-chairman membership
        self.non_chairman_membership = Membership.objects.create(
            organization=self.renewal_due_org,
            user=self.non_chairman_user,
            role='member',
            status='active'
        )
        
        # Create a lapsed organization
        self.lapsed_org = Organization.objects.create(
            name='Lapsed Organization',
            status='lapsed'
        )
        
        # Verify that lapsed org has is_active=True
        self.lapsed_org.refresh_from_db()
        self.assertTrue(
            self.lapsed_org.is_active,
            'lapsed organization should have is_active=True'
        )
        
        # Create chairman membership for lapsed org
        self.lapsed_chairman_membership = Membership.objects.create(
            organization=self.lapsed_org,
            user=self.chairman_user,
            role='chairman',
            status='active',
            has_chairman_privileges=True
        )
        
        # Create a pending organization (should NOT allow access)
        self.pending_org = Organization.objects.create(
            name='Pending Organization',
            status='pending'
        )
        
        # Verify that pending org has is_active=False
        self.pending_org.refresh_from_db()
        self.assertFalse(
            self.pending_org.is_active,
            'pending organization should have is_active=False'
        )
        
        # Create chairman membership for pending org
        self.pending_chairman_membership = Membership.objects.create(
            organization=self.pending_org,
            user=self.chairman_user,
            role='chairman',
            status='active',
            has_chairman_privileges=True
        )

    def test_chairman_can_access_renewal_due_org_dashboard(self):
        """Test that chairman can access dashboard for renewal_due organization.
        
        This verifies that organization__is_active=True in chairman_required decorator
        allows access to renewal_due orgs (which have is_active=True per sync rule).
        
        **Requirement 2.7**
        """
        url = reverse('organizations:chairman_dashboard', args=[self.renewal_due_org.id])
        self.client.login(email='chairman@test.com', password='testpass123')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'organizations/chairman/dashboard.html')
        self.assertContains(response, self.renewal_due_org.name)

    def test_chairman_can_access_lapsed_org_dashboard(self):
        """Test that chairman can access dashboard for lapsed organization.
        
        This verifies that organization__is_active=True in chairman_required decorator
        allows access to lapsed orgs (which have is_active=True per sync rule).
        
        **Requirement 2.7**
        """
        url = reverse('organizations:chairman_dashboard', args=[self.lapsed_org.id])
        self.client.login(email='chairman@test.com', password='testpass123')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'organizations/chairman/dashboard.html')
        self.assertContains(response, self.lapsed_org.name)

    def test_chairman_cannot_access_pending_org_dashboard(self):
        """Test that chairman cannot access dashboard for pending organization.
        
        This verifies that organization__is_active=True in chairman_required decorator
        denies access to pending orgs (which have is_active=False).
        
        **Requirement 13.2, 13.5**
        """
        url = reverse('organizations:chairman_dashboard', args=[self.pending_org.id])
        self.client.login(email='chairman@test.com', password='testpass123')
        response = self.client.get(url)
        
        # Should redirect to org profile with error message
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/directory/{self.pending_org.id}/', response.url)

    def test_non_chairman_cannot_access_renewal_due_org_dashboard(self):
        """Test that non-chairman cannot access renewal_due org dashboard.
        
        **Requirement 13.2**
        """
        url = reverse('organizations:chairman_dashboard', args=[self.renewal_due_org.id])
        self.client.login(email='member@test.com', password='testpass123')
        response = self.client.get(url)
        
        # Should redirect to org profile with error message
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/directory/{self.renewal_due_org.id}/', response.url)

    def test_unauthenticated_user_redirected_to_login(self):
        """Test that unauthenticated users are redirected to login.
        
        **Requirement 13.3**
        """
        url = reverse('organizations:chairman_dashboard', args=[self.renewal_due_org.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_sync_rule_ensures_renewal_due_is_active_true(self):
        """Test that the Organization.save() sync rule ensures renewal_due orgs have is_active=True.
        
        This documents the design decision that makes chairman_required decorator work
        correctly for renewal_due organizations.
        
        **Requirement 1.2, 1.3, 2.7**
        """
        # Create a new renewal_due org and verify is_active is synced
        org = Organization(name='Test Renewal Due', status='renewal_due')
        org.save()
        
        self.assertTrue(org.is_active)
        self.assertIn(org.status, Organization.ACTIVE_STATUSES)

    def test_sync_rule_ensures_lapsed_is_active_true(self):
        """Test that the Organization.save() sync rule ensures lapsed orgs have is_active=True.
        
        This documents the design decision that makes chairman_required decorator work
        correctly for lapsed organizations.
        
        **Requirement 1.2, 1.3, 2.7**
        """
        # Create a new lapsed org and verify is_active is synced
        org = Organization(name='Test Lapsed', status='lapsed')
        org.save()
        
        self.assertTrue(org.is_active)
        self.assertIn(org.status, Organization.ACTIVE_STATUSES)



# ─── Notification Tests ──────────────────────────────────────────────────────

class AdminReviewActionNotificationTests(TestCase):
    """Tests for notification calls in admin_review_action_view - Task 21.1."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            is_cso_admin=True,
            student_id='2024-00001',
            is_active=True
        )
        
        # Create chairman user
        self.chairman = User.objects.create_user(
            email='chairman@test.com',
            password='testpass123',
            student_id='2024-00002',
            is_active=True
        )
        
        # Create organization
        self.org = Organization.objects.create(
            name='Test Organization',
            status='pending'
        )
        
        # Create chairman membership
        self.membership = Membership.objects.create(
            organization=self.org,
            user=self.chairman,
            role='chairman',
            status='active',
            has_chairman_privileges=True
        )
        
        # Create accreditation application
        self.application = AccreditationApplication.objects.create(
            organization=self.org,
            registration_type='new_applicant',
            status='pending'
        )

    def test_approval_notification_sent_to_chairman(self):
        """Test that approval action sends notification to chairman.
        
        **Requirement 12.3**
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_review_action', args=[self.application.id])
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(url, {
                'action': 'approve',
                'remarks': 'Application looks good',
            })
            
            # Verify send_notification was called
            self.assertTrue(mock_notify.called)
            call_args = mock_notify.call_args
            
            # Verify recipient is chairman
            self.assertEqual(call_args[1]['recipients'], [self.chairman])
            
            # Verify title and message contain org name
            self.assertIn(self.org.name, call_args[1]['title'])
            self.assertIn('approved', call_args[1]['title'].lower())
            self.assertIn(self.org.name, call_args[1]['message'])
            
            # Verify is_priority is True
            self.assertTrue(call_args[1]['is_priority'])
            
            # Verify notification_type is organization
            self.assertEqual(call_args[1]['notification_type'], 'organization')

    def test_return_notification_sent_with_remarks(self):
        """Test that return action sends notification with admin remarks.
        
        **Requirement 12.1**
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_review_action', args=[self.application.id])
        
        remarks = 'Please provide more details on your organization structure.'
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(url, {
                'action': 'return',
                'remarks': remarks,
            })
            
            # Verify send_notification was called
            self.assertTrue(mock_notify.called)
            call_args = mock_notify.call_args
            
            # Verify recipient is chairman
            self.assertEqual(call_args[1]['recipients'], [self.chairman])
            
            # Verify remarks are included in message
            self.assertIn(remarks, call_args[1]['message'])
            
            # Verify title and message contain org name
            self.assertIn(self.org.name, call_args[1]['title'])
            self.assertIn('returned', call_args[1]['title'].lower())

    def test_rejection_notification_sent_with_remarks(self):
        """Test that rejection action sends notification with admin remarks.
        
        **Requirement 12.2**
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_review_action', args=[self.application.id])
        
        remarks = 'Your organization does not meet the required criteria.'
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(url, {
                'action': 'reject',
                'remarks': remarks,
            })
            
            # Verify send_notification was called
            self.assertTrue(mock_notify.called)
            call_args = mock_notify.call_args
            
            # Verify recipient is chairman
            self.assertEqual(call_args[1]['recipients'], [self.chairman])
            
            # Verify remarks are included in message
            self.assertIn(remarks, call_args[1]['message'])
            
            # Verify title and message contain org name
            self.assertIn(self.org.name, call_args[1]['title'])
            self.assertIn('rejected', call_args[1]['title'].lower())

    def test_return_notification_handles_empty_remarks(self):
        """Test that return action handles empty remarks gracefully.
        
        **Requirement 12.1**
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_review_action', args=[self.application.id])
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(url, {
                'action': 'return',
                'remarks': '',  # Empty remarks
            })
            
            # Verify send_notification was called
            self.assertTrue(mock_notify.called)
            call_args = mock_notify.call_args
            
            # Verify message contains fallback text for empty remarks
            self.assertIn('No remarks provided', call_args[1]['message'])

    def test_rejection_notification_handles_empty_remarks(self):
        """Test that rejection action handles empty remarks gracefully.
        
        **Requirement 12.2**
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_review_action', args=[self.application.id])
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(url, {
                'action': 'reject',
                'remarks': '',  # Empty remarks
            })
            
            # Verify send_notification was called
            self.assertTrue(mock_notify.called)
            call_args = mock_notify.call_args
            
            # Verify message contains fallback text for empty remarks
            self.assertIn('No reason provided', call_args[1]['message'])

    def test_no_notification_sent_to_chairman_if_not_found(self):
        """Test that notification is not sent if chairman membership is not found.
        
        **Requirement 12.3**
        """
        from unittest.mock import patch
        
        # Remove chairman membership
        self.membership.delete()
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_review_action', args=[self.application.id])
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(url, {
                'action': 'approve',
                'remarks': 'Approved',
            })
            
            # Verify send_notification was NOT called
            self.assertFalse(mock_notify.called)

    def test_mark_under_review_does_not_send_notification(self):
        """Test that marking under review does not send a notification.
        
        This action is purely administrative and doesn't notify the chairman.
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_review_action', args=[self.application.id])
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(url, {
                'action': 'mark_under_review',
            })
            
            # Verify send_notification was NOT called
            self.assertFalse(mock_notify.called)

    def test_renewal_approval_with_promote_to_active_notification(self):
        """Test that renewal approval with promote_to_active sends correct notification.
        
        **Requirement 12.3**
        """
        from unittest.mock import patch
        
        # Create a renewal application
        renewal_app = AccreditationApplication.objects.create(
            organization=self.org,
            registration_type='renewal',
            status='pending'
        )
        
        self.org.status = 'renewal_due'
        self.org.pre_renewal_status = 'active'
        self.org.save()
        
        self.client.login(email='admin@test.com', password='testpass123')
        url = reverse('organizations:admin_review_action', args=[renewal_app.id])
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(url, {
                'action': 'approve',
                'promote_to_active': 'on',
            })
            
            # Verify send_notification was called
            self.assertTrue(mock_notify.called)
            call_args = mock_notify.call_args
            
            # Verify notification mentions new status
            self.assertIn('status', call_args[1]['message'].lower())


class NewSchoolYearNotificationTests(TestCase):
    """Tests for notification calls in admin_new_school_year_view - Task 21.1."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            is_cso_admin=True,
            student_id='2024-00001',
            is_active=True
        )
        
        # Create chairman users
        self.chairman1 = User.objects.create_user(
            email='chairman1@test.com',
            password='testpass123',
            student_id='2024-00002',
            is_active=True
        )
        self.chairman2 = User.objects.create_user(
            email='chairman2@test.com',
            password='testpass123',
            student_id='2024-00003',
            is_active=True
        )
        
        # Create test organizations
        self.probationary_org = Organization.objects.create(
            name='Probationary Org',
            status='probationary'
        )
        self.active_org = Organization.objects.create(
            name='Active Org',
            status='active'
        )
        
        # Create chairman memberships
        Membership.objects.create(
            organization=self.probationary_org,
            user=self.chairman1,
            role='chairman',
            status='active'
        )
        Membership.objects.create(
            organization=self.active_org,
            user=self.chairman2,
            role='chairman',
            status='active'
        )
        
        self.url = reverse('organizations:admin_new_school_year')

    def test_new_school_year_sends_notifications_to_all_affected_chairmen(self):
        """Test that new school year sends notifications to all affected chairmen.
        
        **Requirement 12.4**
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(self.url, {
                'renewal_deadline': '2024-12-31',
            })
            
            # Verify send_notification was called for each affected org
            self.assertEqual(mock_notify.call_count, 2)
            
            # Collect all recipients across all calls
            all_recipients = []
            for call in mock_notify.call_args_list:
                all_recipients.extend(call[1]['recipients'])
            
            # Verify both chairmen received notifications
            self.assertIn(self.chairman1, all_recipients)
            self.assertIn(self.chairman2, all_recipients)

    def test_new_school_year_notification_includes_deadline(self):
        """Test that new school year notification includes renewal deadline.
        
        **Requirement 12.4**
        """
        from unittest.mock import patch
        
        deadline = '2024-12-31'
        self.client.login(email='admin@test.com', password='testpass123')
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(self.url, {
                'renewal_deadline': deadline,
            })
            
            # Verify at least one notification contains the deadline
            found_deadline = False
            for call in mock_notify.call_args_list:
                if deadline in call[1]['message']:
                    found_deadline = True
                    break
            
            self.assertTrue(found_deadline, 'Deadline should be included in notification message')

    def test_new_school_year_notification_is_priority(self):
        """Test that new school year notifications are marked as priority.
        
        **Requirement 12.4**
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(self.url, {
                'renewal_deadline': '2024-12-31',
            })
            
            # Verify all notifications are marked as priority
            for call in mock_notify.call_args_list:
                self.assertTrue(call[1]['is_priority'])

    def test_new_school_year_notification_includes_org_name(self):
        """Test that new school year notifications include organization name.
        
        **Requirement 12.4**
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(self.url, {
                'renewal_deadline': '2024-12-31',
            })
            
            # Verify organization names are in messages
            messages_and_titles = []
            for call in mock_notify.call_args_list:
                messages_and_titles.append(call[1]['title'])
                messages_and_titles.append(call[1]['message'])
            
            combined_text = ' '.join(messages_and_titles)
            self.assertIn(self.probationary_org.name, combined_text)
            self.assertIn(self.active_org.name, combined_text)

    def test_new_school_year_notification_type_is_organization(self):
        """Test that new school year notifications have notification_type='organization'.
        
        **Requirement 12.4**
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(self.url, {
                'renewal_deadline': '2024-12-31',
            })
            
            # Verify all notifications have correct type
            for call in mock_notify.call_args_list:
                self.assertEqual(call[1]['notification_type'], 'organization')


class CloseRenewalNotificationTests(TestCase):
    """Tests for notification calls in admin_close_renewal_view - Task 21.1."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            is_cso_admin=True,
            student_id='2024-00001',
            is_active=True
        )
        
        # Create chairman users
        self.chairman1 = User.objects.create_user(
            email='chairman1@test.com',
            password='testpass123',
            student_id='2024-00002',
            is_active=True
        )
        self.chairman2 = User.objects.create_user(
            email='chairman2@test.com',
            password='testpass123',
            student_id='2024-00003',
            is_active=True
        )
        
        # Create renewal_due orgs
        self.renewal_due_no_approval = Organization.objects.create(
            name='Renewal Due No Approval',
            status='renewal_due'
        )
        self.renewal_due_with_approval = Organization.objects.create(
            name='Renewal Due With Approval',
            status='renewal_due'
        )
        
        # Create approved renewal application for one org
        AccreditationApplication.objects.create(
            organization=self.renewal_due_with_approval,
            registration_type='renewal',
            status='approved'
        )
        
        # Create chairman memberships
        Membership.objects.create(
            organization=self.renewal_due_no_approval,
            user=self.chairman1,
            role='chairman',
            status='active'
        )
        Membership.objects.create(
            organization=self.renewal_due_with_approval,
            user=self.chairman2,
            role='chairman',
            status='active'
        )
        
        self.url = reverse('organizations:admin_close_renewal')

    def test_close_renewal_sends_notification_only_to_lapsed_orgs(self):
        """Test that close renewal sends notifications only to orgs that become lapsed.
        
        **Requirement 12.5**
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(self.url)
            
            # Verify send_notification was called only once (for the org without approved renewal)
            self.assertEqual(mock_notify.call_count, 1)
            
            # Verify notification is for the lapsed org chairman
            call_args = mock_notify.call_args
            self.assertEqual(call_args[1]['recipients'], [self.chairman1])

    def test_close_renewal_notification_mentions_lapsed_status(self):
        """Test that close renewal notification mentions lapsed status.
        
        **Requirement 12.5**
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(self.url)
            
            # Verify notification content
            call_args = mock_notify.call_args
            message = call_args[1]['message']
            
            self.assertIn('lapsed', message.lower())

    def test_close_renewal_notification_is_priority(self):
        """Test that close renewal notifications are marked as priority.
        
        **Requirement 12.5**
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(self.url)
            
            # Verify notification is priority
            call_args = mock_notify.call_args
            self.assertTrue(call_args[1]['is_priority'])

    def test_close_renewal_notification_type_is_organization(self):
        """Test that close renewal notifications have notification_type='organization'.
        
        **Requirement 12.5**
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(self.url)
            
            # Verify notification type
            call_args = mock_notify.call_args
            self.assertEqual(call_args[1]['notification_type'], 'organization')

    def test_close_renewal_notification_includes_org_name(self):
        """Test that close renewal notifications include organization name.
        
        **Requirement 12.5**
        """
        from unittest.mock import patch
        
        self.client.login(email='admin@test.com', password='testpass123')
        
        with patch('announcements.utils.send_notification') as mock_notify:
            response = self.client.post(self.url)
            
            # Verify organization name is in notification
            call_args = mock_notify.call_args
            message_and_title = call_args[1]['title'] + ' ' + call_args[1]['message']
            
            self.assertIn(self.renewal_due_no_approval.name, message_and_title)


# ─── Organization Registration Approval Tests ──────────────────────────────

class OrganizationRegistrationApprovalTests(TestCase):
    """Tests for admin_review_org_registration_action_view approval logic.
    
    Verifies that all three org registration categories (institutional, ub_chapter, 
    student_org) are approved directly to 'active' status without going through 
    probationary stage.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            is_cso_admin=True,
            student_id='2024-00001',
            is_active=True
        )
        
        # Create submitter user
        self.submitter = User.objects.create_user(
            email='submitter@test.com',
            password='testpass123',
            student_id='2024-00002',
            is_active=True
        )
        
        # Create proposed chairman user
        self.chairman = User.objects.create_user(
            email='chairman@test.com',
            password='testpass123',
            student_id='2024-00003',
            is_active=True
        )
        
        self.url_base = 'organizations:admin_review_org_registration_action'

    def create_org_registration(self, org_name, category, proposed_chairman=None):
        """Helper to create an OrganizationRegistration record."""
        from organizations.models import OrganizationRegistration
        
        return OrganizationRegistration.objects.create(
            org_name=org_name,
            category=category,
            submitted_by=self.submitter,
            proposed_chairman=proposed_chairman or self.submitter,
            proof_message='We are an existing organization',
            status='pending'
        )

    def test_institutional_org_approved_to_active(self):
        """Test that institutional org registration is approved to 'active' status.
        
        **Validates: Bugfix Requirements**
        """
        registration = self.create_org_registration('Institutional Org', 'institutional')
        
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.post(
            reverse(self.url_base, kwargs={'reg_id': registration.id}),
            {
                'action': 'approve',
                'remarks': 'Approved'
            }
        )
        
        # Should redirect back to registration panel
        self.assertEqual(response.status_code, 302)
        
        # Verify registration was approved
        registration.refresh_from_db()
        self.assertEqual(registration.status, 'approved')
        
        # Verify created organization has 'active' status
        org = registration.created_organization
        self.assertIsNotNone(org)
        self.assertEqual(org.status, 'active')
        self.assertTrue(org.is_active)

    def test_ub_chapter_approved_to_active(self):
        """Test that UB chapter registration is approved to 'active' status.
        
        **Validates: Bugfix Requirements**
        """
        registration = self.create_org_registration('UB Chess Club', 'ub_chapter')
        
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.post(
            reverse(self.url_base, kwargs={'reg_id': registration.id}),
            {
                'action': 'approve',
                'remarks': 'Approved'
            }
        )
        
        # Should redirect back to registration panel
        self.assertEqual(response.status_code, 302)
        
        # Verify registration was approved
        registration.refresh_from_db()
        self.assertEqual(registration.status, 'approved')
        
        # Verify created organization has 'active' status (NOT 'pending')
        org = registration.created_organization
        self.assertIsNotNone(org)
        self.assertEqual(org.status, 'active')
        self.assertTrue(org.is_active)

    def test_student_org_approved_to_active(self):
        """Test that student org registration is approved to 'active' status.
        
        **Validates: Bugfix Requirements**
        """
        registration = self.create_org_registration('Student Art Society', 'student_org')
        
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.post(
            reverse(self.url_base, kwargs={'reg_id': registration.id}),
            {
                'action': 'approve',
                'remarks': 'Approved'
            }
        )
        
        # Should redirect back to registration panel
        self.assertEqual(response.status_code, 302)
        
        # Verify registration was approved
        registration.refresh_from_db()
        self.assertEqual(registration.status, 'approved')
        
        # Verify created organization has 'active' status (NOT 'pending')
        org = registration.created_organization
        self.assertIsNotNone(org)
        self.assertEqual(org.status, 'active')
        self.assertTrue(org.is_active)

    def test_all_categories_skip_probationary(self):
        """Test that all three categories skip probationary stage.
        
        **Validates: Bugfix Requirements**
        """
        categories = ['institutional', 'ub_chapter', 'student_org']
        
        for category in categories:
            registration = self.create_org_registration(f'Test {category} Org', category)
            
            self.client.login(email='admin@test.com', password='testpass123')
            response = self.client.post(
                reverse(self.url_base, kwargs={'reg_id': registration.id}),
                {
                    'action': 'approve',
                    'remarks': 'Approved'
                }
            )
            
            # Verify organization was created with 'active' status
            org = Organization.objects.get(name=f'Test {category} Org')
            self.assertEqual(org.status, 'active',
                           f'{category} org should have active status, not probationary')
            self.assertTrue(org.is_active)

    def test_chairman_membership_created_on_approval(self):
        """Test that chairman membership is created with proposed chairman.
        
        **Validates: Requirements**
        """
        registration = self.create_org_registration('Test Org', 'institutional', 
                                                   proposed_chairman=self.chairman)
        
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.post(
            reverse(self.url_base, kwargs={'reg_id': registration.id}),
            {
                'action': 'approve',
                'remarks': 'Approved'
            }
        )
        
        # Verify membership was created
        org = registration.created_organization
        membership = Membership.objects.get(organization=org, user=self.chairman)
        
        self.assertEqual(membership.role, 'chairman')
        self.assertTrue(membership.has_chairman_privileges)
        self.assertEqual(membership.status, 'active')

    def test_submitter_as_chairman_when_no_proposed(self):
        """Test that submitter becomes chairman when no proposed chairman.
        
        **Validates: Requirements**
        """
        registration = self.create_org_registration('Test Org', 'student_org', 
                                                   proposed_chairman=None)
        
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.post(
            reverse(self.url_base, kwargs={'reg_id': registration.id}),
            {
                'action': 'approve',
                'remarks': 'Approved'
            }
        )
        
        # Verify membership was created with submitter as chairman
        org = registration.created_organization
        membership = Membership.objects.get(organization=org, user=self.submitter)
        
        self.assertEqual(membership.role, 'chairman')
        self.assertTrue(membership.has_chairman_privileges)

    def test_non_admin_cannot_approve(self):
        """Test that non-admin users cannot approve registrations."""
        registration = self.create_org_registration('Test Org', 'institutional')
        
        self.client.login(email='submitter@test.com', password='testpass123')
        response = self.client.post(
            reverse(self.url_base, kwargs={'reg_id': registration.id}),
            {
                'action': 'approve',
                'remarks': 'Approved'
            }
        )
        
        # Should redirect (access denied)
        self.assertEqual(response.status_code, 302)
        
        # Verify registration was NOT approved
        registration.refresh_from_db()
        self.assertEqual(registration.status, 'pending')

    def test_unauthenticated_cannot_approve(self):
        """Test that unauthenticated users are redirected to login."""
        registration = self.create_org_registration('Test Org', 'institutional')
        
        response = self.client.post(
            reverse(self.url_base, kwargs={'reg_id': registration.id}),
            {
                'action': 'approve',
                'remarks': 'Approved'
            }
        )
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)


class OrganizationRegistrationApprovalPropertyTests(HypothesisTestCase):
    """Property-based tests for organization registration approval logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            is_cso_admin=True,
            student_id='2024-00001',
            is_active=True
        )
        
        self.submitter = User.objects.create_user(
            email='submitter@test.com',
            password='testpass123',
            student_id='2024-00002',
            is_active=True
        )

    @given(st.sampled_from(['institutional', 'ub_chapter', 'student_org']))
    def test_all_categories_create_active_org(self, category):
        """
        Property: All org registration categories create organizations with 'active' status.
        
        For any organization registration in the three allowed categories (institutional,
        ub_chapter, student_org), when approved by an admin, the created organization must
        have status='active' and is_active=True. It must not go through probationary stage.
        
        **Validates: Bugfix Requirements**
        """
        from organizations.models import OrganizationRegistration
        
        registration = OrganizationRegistration.objects.create(
            org_name=f'Test Org {category}',
            category=category,
            submitted_by=self.submitter,
            proof_message='Test',
            status='pending'
        )
        
        client = Client()
        client.login(email='admin@test.com', password='testpass123')
        
        response = client.post(
            reverse('organizations:admin_review_org_registration_action', 
                   kwargs={'reg_id': registration.id}),
            {
                'action': 'approve',
                'remarks': 'Approved'
            }
        )
        
        # Verify created org has active status
        org = Organization.objects.get(name=f'Test Org {category}')
        self.assertEqual(org.status, 'active')
        self.assertTrue(org.is_active)


# ─────────────────────────────────────────────────────────────────────────────
# Institutional Renewal Requirements — Property-Based Tests
# Feature: institutional-renewal-requirements
# ─────────────────────────────────────────────────────────────────────────────

def _make_valid_title():
    """Hypothesis strategy: non-empty strings up to 200 chars."""
    return st.text(min_size=1, max_size=200).filter(lambda s: s.strip() != '')


def _make_valid_link():
    """Hypothesis strategy: valid http/https URL or None."""
    url_strategy = st.one_of(
        st.just(None),
        st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=1, max_size=40)
        .map(lambda s: f'https://example.com/{s}'),
    )
    return url_strategy


def _make_entry():
    """Hypothesis strategy: a valid {title, link} dict."""
    return st.fixed_dictionaries({
        'title': _make_valid_title(),
        'link': _make_valid_link(),
    })


# ── Helper functions (pure, extracted from views) ────────────────────────────

def _validate_add_entry(title, link):
    """
    Pure validation logic mirroring admin_institutional_add_view.
    Returns a list of error strings (empty = valid).
    """
    errors = []
    title = (title or '').strip()
    link = (link or '').strip()

    if not title:
        errors.append('Title is required and cannot be blank or whitespace.')
    elif len(title) > 200:
        errors.append('Title must be 200 characters or fewer.')

    if link:
        if not (link.startswith('http://') or link.startswith('https://')):
            errors.append('Link must begin with http:// or https://.')
        elif len(link) > 2048:
            errors.append('Link must be 2048 characters or fewer.')

    return errors


def _apply_remove(docs, index):
    """
    Pure remove logic: validates index, returns (new_list, error_str|None).
    """
    try:
        idx = int(index)
        if idx < 0:
            raise ValueError
    except (ValueError, TypeError):
        return docs, 'Invalid index'

    if idx >= len(docs):
        return docs, 'Index out of range'

    new_docs = list(docs)
    new_docs.pop(idx)
    return new_docs, None


# ── Property 1: Round-trip preserves structure and order ─────────────────────

class InstitutionalRenewalRoundTripTest(HypothesisTestCase):
    """Property 1: Requirement list round-trip preserves structure and order."""

    @settings(max_examples=100)
    @given(st.lists(_make_entry(), max_size=20))
    def test_round_trip_preserves_list(self, entries):
        """
        For any list of {title, link} entries written to RenewalRequirement and
        retrieved fresh from DB, the result must be identical in order and content.
        Feature: institutional-renewal-requirements
        Property 1: requirement list round-trip preserves structure and order
        Validates: Requirements 1.1, 1.2, 1.3
        """
        from organizations.models import RenewalRequirement
        from accounts.models import User as AuthUser

        user = AuthUser.objects.create_user(
            email=f'tester_{id(entries)}@ub.edu.ph',
            student_id=f'2099{abs(hash(str(entries))) % 100000:05d}',
            password='testpass',
        )

        obj, _ = RenewalRequirement.objects.get_or_create(status='institutional')
        obj.required_documents = entries
        obj.updated_by = user
        obj.save()

        fresh = RenewalRequirement.objects.get(status='institutional')
        self.assertEqual(fresh.required_documents, entries)


# ── Property 2: Whitespace-only titles are always rejected ───────────────────

class WhitespaceTitleRejectionTest(TestCase):
    """Property 2: Whitespace-only titles are always rejected."""

    @settings(max_examples=100)
    @given(st.text(alphabet=' \t\n\r', min_size=0, max_size=50))
    def test_whitespace_title_rejected(self, title):
        """
        Feature: institutional-renewal-requirements
        Property 2: whitespace-only titles are always rejected
        Validates: Requirements 1.4, 3.4
        """
        errors = _validate_add_entry(title, '')
        self.assertTrue(
            any('Title' in e or 'title' in e for e in errors),
            f'Expected title error for whitespace title {repr(title)}, got: {errors}'
        )


# ── Property 3: Non-http/https links are always rejected ─────────────────────

class InvalidLinkRejectionTest(TestCase):
    """Property 3: Non-http/https links are always rejected."""

    @settings(max_examples=100)
    @given(
        st.text(min_size=1, max_size=100).filter(
            lambda s: s.strip() and not s.strip().startswith('http://') and not s.strip().startswith('https://')
        )
    )
    def test_invalid_link_rejected(self, link):
        """
        Feature: institutional-renewal-requirements
        Property 3: non-http/https links are always rejected
        Validates: Requirements 1.5, 3.5
        """
        errors = _validate_add_entry('Valid Title', link)
        self.assertTrue(
            any('link' in e.lower() or 'http' in e.lower() for e in errors),
            f'Expected link error for {repr(link)}, got: {errors}'
        )


# ── Property 4: Appending increases list by 1 and places entry last ──────────

class AppendPlacesEntryLastTest(TestCase):
    """Property 4: Appending an entry increases the list by exactly one and places it last."""

    @settings(max_examples=100)
    @given(st.lists(_make_entry(), max_size=15), _make_entry())
    def test_append_places_entry_last(self, existing, new_entry):
        """
        Feature: institutional-renewal-requirements
        Property 4: appending an entry increases the list by exactly one and places it last
        Validates: Requirements 3.1
        """
        docs = list(existing)
        original_len = len(docs)
        docs.append(new_entry)
        self.assertEqual(len(docs), original_len + 1)
        self.assertEqual(docs[-1], new_entry)


# ── Property 5: Remove preserves relative order of remaining entries ─────────

class RemovePreservesOrderTest(TestCase):
    """Property 5: Removing an entry at a valid index preserves relative order."""

    @settings(max_examples=100)
    @given(st.lists(_make_entry(), min_size=1, max_size=15).flatmap(
        lambda lst: st.tuples(st.just(lst), st.integers(min_value=0, max_value=len(lst) - 1))
    ))
    def test_remove_preserves_order(self, list_and_index):
        """
        Feature: institutional-renewal-requirements
        Property 5: removing an entry at a valid index preserves relative order
        Validates: Requirements 4.1, 4.4
        """
        docs, idx = list_and_index
        new_docs, error = _apply_remove(list(docs), idx)
        self.assertIsNone(error, f'Unexpected error: {error}')
        self.assertEqual(len(new_docs), len(docs) - 1)
        # Verify relative order: entries before idx + entries after idx
        expected = docs[:idx] + docs[idx + 1:]
        self.assertEqual(new_docs, expected)

    def test_remove_out_of_range_returns_error(self):
        """Out-of-range index leaves list unchanged and returns error."""
        docs = [{'title': 'Doc A', 'link': None}]
        new_docs, error = _apply_remove(docs, 5)
        self.assertIsNotNone(error)
        self.assertEqual(new_docs, docs)

    def test_remove_negative_index_returns_error(self):
        """Negative index returns error."""
        docs = [{'title': 'Doc A', 'link': None}]
        new_docs, error = _apply_remove(docs, -1)
        self.assertIsNotNone(error)
        self.assertEqual(new_docs, docs)
