"""
Bug Condition Exploration Test for Notes Editing Bugfix

**Validates: Requirement 1.1 (Bug 1 - Missing Removal Controls)**

This test MUST FAIL on unfixed code - failure confirms the bug exists.
DO NOT attempt to fix the test or the code when it fails.

This test encodes the expected behavior - it will validate the fix when it passes after implementation.

GOAL: Surface counterexamples that demonstrate Bug 1 exists:
- Bug 1: Notes with existing attachments in edit mode lack X buttons for removal

NOTE: Bug 2 (placeholder text in public view) was investigated and does NOT exist in the current code.
The _post_card.html template already has correct logic: {% if post.title %} ... {% endif %}
This means placeholder text is never shown in public view for empty titles.

EXPECTED OUTCOME: Test FAILS for Bug 1 (this is correct - it proves the bug exists)
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from hypothesis import given, strategies as st, settings, HealthCheck
from hypothesis.extra.django import TestCase as HypothesisTestCase
from padlet.models import Board, Post, PostAttachment

import io
from PIL import Image

User = get_user_model()


def create_test_image():
    """Create a simple test image file"""
    file = io.BytesIO()
    image = Image.new('RGB', (100, 100), color='red')
    image.save(file, 'PNG')
    file.seek(0)
    return SimpleUploadedFile('test_image.png', file.read(), content_type='image/png')


def create_test_video():
    """Create a simple test video file (mock)"""
    # For testing purposes, we'll use a minimal valid video file
    # In a real scenario, you'd use an actual video file
    return SimpleUploadedFile('test_video.mp4', b'fake video content', content_type='video/mp4')


class BugConditionExplorationTest(HypothesisTestCase):
    """
    Property 1: Bug Condition - Missing Removal Controls for Existing Attachments
    
    This test verifies that Bug 1 exists on unfixed code by checking:
    - Notes with existing attachments in edit mode do NOT have X buttons (Bug 1)
    
    When the code is fixed, this test will pass, confirming the expected behavior:
    - Notes with existing attachments in edit mode HAVE X buttons (Expected Behavior)
    
    NOTE: Bug 2 (placeholder in public view) does not exist - the template already handles this correctly.
    """
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            student_id='2024-00001',
            is_active=True
        )
        self.board = Board.objects.create(
            title='Test Board',
            scope='system',
            created_by=self.user
        )
        self.client.login(email='test@example.com', password='testpass123')
    
    def tearDown(self):
        """Clean up test data"""
        # Delete all attachments and their files
        for att in PostAttachment.objects.all():
            if att.file:
                att.file.delete()
        PostAttachment.objects.all().delete()
        Post.objects.all().delete()
        Board.objects.all().delete()
        User.objects.all().delete()
    
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow]
    )
    @given(
        attachment_type=st.sampled_from(['image', 'video']),
        title_is_empty=st.booleans(),
        post_color=st.sampled_from(['yellow', 'blue', 'green', 'pink', 'purple', 'white'])
    )
    def test_bug_condition_missing_removal_controls(
        self, attachment_type, title_is_empty, post_color
    ):
        """
        **Property 1: Bug Condition** - Missing Removal Controls for Existing Attachments
        
        **Validates: Requirement 1.1**
        
        This property tests Bug 1:
        - WHEN a note has existing attachments AND is in edit mode
        - THEN on UNFIXED code: X buttons are NOT present (test will FAIL)
        - THEN on FIXED code: X buttons ARE present (test will PASS)
        """
        # Create a post with or without title
        title = '' if title_is_empty else 'Test Post Title'
        post = Post.objects.create(
            board=self.board,
            author=self.user,
            title=title,
            content='Test content for bug exploration',
            color=post_color,
            is_anonymous=False
        )
        
        # Create an attachment (image or video)
        if attachment_type == 'image':
            attachment_file = create_test_image()
        else:
            attachment_file = create_test_video()
        
        attachment = PostAttachment.objects.create(
            post=post,
            attachment_type=attachment_type,
            file=attachment_file,
            original_filename=f'test_{attachment_type}.{"png" if attachment_type == "image" else "mp4"}'
        )
        
        # ===== BUG 1 TEST: Missing Removal Controls for Existing Attachments =====
        # Render the post detail template (edit mode context)
        detail_html = render_to_string('padlet/_post_detail.html', {
            'post': post,
            'board': self.board,
            'can_edit': True,
            'can_delete': True,
            'is_manager': False,
            'attachments': post.attachments.all(),
            'replies': [],
            'reaction_choices': [('thumbsup', '👍'), ('thumbsdown', '👎')],
            'reaction_counts': {},
            'user_reaction': None,
            'color_choices': Post.COLOR_CHOICES,
            'csrf_token': 'test-csrf-token'
        })
        
        # Check for removal button on existing attachment
        # Expected behavior (after fix): removal button should be present
        # Bug condition (before fix): removal button is NOT present
        
        # Look for the removal button structure that should exist for existing attachments
        # The button should have onclick="removeExistingAttachment(...)"
        has_removal_button = (
            f'removeExistingAttachment({attachment.id}' in detail_html or
            f'att-wrap-{attachment.id}' in detail_html and 'existing-att-remove-btn' in detail_html
        )
        
        # ASSERTION: On FIXED code, this should be True (removal button exists)
        # On UNFIXED code, this will be False (removal button missing) - TEST WILL FAIL
        self.assertTrue(
            has_removal_button,
            f"Bug 1 detected: Note with existing {attachment_type} attachment (ID: {attachment.id}) "
            f"in edit mode does NOT have a removal button. "
            f"Expected: X button with 'removeExistingAttachment({attachment.id})' or 'existing-att-remove-btn' class. "
            f"This confirms the bug exists on unfixed code."
        )
        
        # Clean up the attachment file
        if attachment.file:
            attachment.file.delete()


class ManualBugConditionTest(TestCase):
    """
    Manual test cases for Bug 1 (Missing Removal Controls)
    
    These tests provide concrete examples of the bug for documentation purposes.
    
    NOTE: Bug 2 tests removed as Bug 2 does not exist in the current code.
    """
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            student_id='2024-00001',
            is_active=True
        )
        self.board = Board.objects.create(
            title='Test Board',
            scope='system',
            created_by=self.user
        )
        self.client.login(email='test@example.com', password='testpass123')
    
    def tearDown(self):
        """Clean up test data"""
        for att in PostAttachment.objects.all():
            if att.file:
                att.file.delete()
        PostAttachment.objects.all().delete()
        Post.objects.all().delete()
        Board.objects.all().delete()
        User.objects.all().delete()
    
    def test_bug1_image_attachment_no_removal_button(self):
        """
        Bug 1 Example: Note with image attachment in edit mode has no X button
        
        **Validates: Requirement 1.1**
        """
        post = Post.objects.create(
            board=self.board,
            author=self.user,
            title='Post with Image',
            content='This post has an image attachment',
            color='yellow'
        )
        
        attachment = PostAttachment.objects.create(
            post=post,
            attachment_type='image',
            file=create_test_image(),
            original_filename='test_image.png'
        )
        
        detail_html = render_to_string('padlet/_post_detail.html', {
            'post': post,
            'board': self.board,
            'can_edit': True,
            'can_delete': True,
            'is_manager': False,
            'attachments': post.attachments.all(),
            'replies': [],
            'reaction_choices': [('thumbsup', '👍'), ('thumbsdown', '👎')],
            'reaction_counts': {},
            'user_reaction': None,
            'color_choices': Post.COLOR_CHOICES,
            'csrf_token': 'test-csrf-token'
        })
        
        has_removal_button = f'removeExistingAttachment({attachment.id}' in detail_html
        
        self.assertTrue(
            has_removal_button,
            "Bug 1: Image attachment in edit mode should have X button for removal"
        )
        
        if attachment.file:
            attachment.file.delete()
    
    def test_bug1_video_attachment_no_removal_button(self):
        """
        Bug 1 Example: Note with video attachment in edit mode has no X button
        
        **Validates: Requirement 1.1**
        """
        post = Post.objects.create(
            board=self.board,
            author=self.user,
            title='Post with Video',
            content='This post has a video attachment',
            color='blue'
        )
        
        attachment = PostAttachment.objects.create(
            post=post,
            attachment_type='video',
            file=create_test_video(),
            original_filename='test_video.mp4'
        )
        
        detail_html = render_to_string('padlet/_post_detail.html', {
            'post': post,
            'board': self.board,
            'can_edit': True,
            'can_delete': True,
            'is_manager': False,
            'attachments': post.attachments.all(),
            'replies': [],
            'reaction_choices': [('thumbsup', '👍'), ('thumbsdown', '👎')],
            'reaction_counts': {},
            'user_reaction': None,
            'color_choices': Post.COLOR_CHOICES,
            'csrf_token': 'test-csrf-token'
        })
        
        has_removal_button = f'removeExistingAttachment({attachment.id}' in detail_html
        
        self.assertTrue(
            has_removal_button,
            "Bug 1: Video attachment in edit mode should have X button for removal"
        )
        
        if attachment.file:
            attachment.file.delete()
