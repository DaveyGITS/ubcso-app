"""
Quick verification tests for Tasks 2, 3, and 5 of org-board-visibility-toggle spec.
These tests verify the basic functionality of the updated permission helpers and edit view.
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from padlet.models import Board
from padlet.views import _can_see_board, _can_post_on_board, padlet_edit_board_view
from core.models import Organization
from memberships.models import Membership

User = get_user_model()


class PermissionHelperTests(TestCase):
    """Test the updated permission helper functions."""
    
    def setUp(self):
        """Set up test data."""
        # Create users
        self.member_user = User.objects.create_user(
            email='member@test.com',
            password='testpass123',
            first_name='Member',
            last_name='User',
            student_id='M001'
        )
        self.non_member_user = User.objects.create_user(
            email='nonmember@test.com',
            password='testpass123',
            first_name='NonMember',
            last_name='User',
            student_id='N001'
        )
        
        # Create organization
        self.org = Organization.objects.create(
            name='Test Org',
            status='active'
        )
        
        # Create membership for member_user
        Membership.objects.create(
            user=self.member_user,
            organization=self.org,
            status='active',
            role='member'
        )
        
        # Create boards
        self.system_board = Board.objects.create(
            title='System Board',
            scope='system',
            created_by=self.member_user
        )
        
        self.public_org_board = Board.objects.create(
            title='Public Org Board',
            scope='org',
            organization=self.org,
            is_public=True,
            created_by=self.member_user
        )
        
        self.private_org_board = Board.objects.create(
            title='Private Org Board',
            scope='org',
            organization=self.org,
            is_public=False,
            created_by=self.member_user
        )
    
    def test_system_board_visible_to_all(self):
        """Task 2: System boards should be visible to all users."""
        self.assertTrue(_can_see_board(self.member_user, self.system_board))
        self.assertTrue(_can_see_board(self.non_member_user, self.system_board))
    
    def test_public_org_board_visible_to_all(self):
        """Task 2: Public org boards should be visible to all users."""
        self.assertTrue(_can_see_board(self.member_user, self.public_org_board))
        self.assertTrue(_can_see_board(self.non_member_user, self.public_org_board))
    
    def test_private_org_board_visible_to_members_only(self):
        """Task 2: Private org boards should be visible only to members."""
        self.assertTrue(_can_see_board(self.member_user, self.private_org_board))
        self.assertFalse(_can_see_board(self.non_member_user, self.private_org_board))
    
    def test_system_board_posting_allowed_for_all(self):
        """Task 3: System boards should allow all users to post."""
        self.assertTrue(_can_post_on_board(self.member_user, self.system_board))
        self.assertTrue(_can_post_on_board(self.non_member_user, self.system_board))
    
    def test_org_board_posting_requires_membership(self):
        """Task 3: Org boards (public or private) should require membership to post."""
        # Public org board - only members can post
        self.assertTrue(_can_post_on_board(self.member_user, self.public_org_board))
        self.assertFalse(_can_post_on_board(self.non_member_user, self.public_org_board))
        
        # Private org board - only members can post
        self.assertTrue(_can_post_on_board(self.member_user, self.private_org_board))
        self.assertFalse(_can_post_on_board(self.non_member_user, self.private_org_board))
    
    def test_posting_independent_of_is_public(self):
        """Task 3: Posting permissions should be independent of is_public flag."""
        # Both public and private org boards should have same posting logic
        public_result = _can_post_on_board(self.non_member_user, self.public_org_board)
        private_result = _can_post_on_board(self.non_member_user, self.private_org_board)
        self.assertEqual(public_result, private_result)
        self.assertFalse(public_result)  # Both should be False for non-members


class EditBoardViewTests(TestCase):
    """Test the updated padlet_edit_board_view function."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        
        # Create users
        self.board_manager = User.objects.create_user(
            email='manager@test.com',
            password='testpass123',
            first_name='Manager',
            last_name='User',
            student_id='MGR001'
        )
        
        # Create organization
        self.org = Organization.objects.create(
            name='Test Org',
            status='active'
        )
        
        # Create membership with chairman role (board manager)
        Membership.objects.create(
            user=self.board_manager,
            organization=self.org,
            status='active',
            role='chairman'
        )
        
        # Create org board
        self.org_board = Board.objects.create(
            title='Test Org Board',
            scope='org',
            organization=self.org,
            is_public=False,
            created_by=self.board_manager
        )
        
        # Create system board
        self.system_board = Board.objects.create(
            title='Test System Board',
            scope='system',
            is_public=False,
            created_by=self.board_manager
        )
    
    def test_edit_org_board_updates_is_public(self):
        """Task 5: Editing org board should update is_public field."""
        # Create POST request to toggle is_public to True
        request = self.factory.post(
            f'/padlet/board/{self.org_board.id}/edit/',
            data={
                'title': 'Updated Title',
                'description': 'Updated description',
                'is_public': 'on'
            }
        )
        request.user = self.board_manager
        
        # Add messages middleware
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        # Call the view
        response = padlet_edit_board_view(request, self.org_board.id)
        
        # Refresh from database
        self.org_board.refresh_from_db()
        
        # Verify is_public was updated
        self.assertTrue(self.org_board.is_public)
    
    def test_edit_org_board_unchecked_is_public(self):
        """Task 5: Unchecking is_public should set it to False."""
        # Start with public board
        self.org_board.is_public = True
        self.org_board.save()
        
        # Create POST request without is_public (unchecked)
        request = self.factory.post(
            f'/padlet/board/{self.org_board.id}/edit/',
            data={
                'title': 'Updated Title',
                'description': 'Updated description'
                # is_public not included = unchecked
            }
        )
        request.user = self.board_manager
        
        # Add messages middleware
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        # Call the view
        response = padlet_edit_board_view(request, self.org_board.id)
        
        # Refresh from database
        self.org_board.refresh_from_db()
        
        # Verify is_public was set to False
        self.assertFalse(self.org_board.is_public)
    
    def test_edit_system_board_ignores_is_public(self):
        """Task 5: Editing system board should ignore is_public parameter."""
        # Create POST request with is_public for system board
        request = self.factory.post(
            f'/padlet/board/{self.system_board.id}/edit/',
            data={
                'title': 'Updated System Board',
                'description': 'Updated description',
                'is_public': 'on'
            }
        )
        request.user = self.board_manager
        
        # Add messages middleware
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        # Call the view
        response = padlet_edit_board_view(request, self.system_board.id)
        
        # Refresh from database
        self.system_board.refresh_from_db()
        
        # Verify is_public was NOT updated (should remain False)
        self.assertFalse(self.system_board.is_public)


if __name__ == '__main__':
    import django
    django.setup()
    from django.test.utils import get_runner
    from django.conf import settings
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(['padlet.test_visibility_changes'])
