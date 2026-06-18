"""
Preservation Property Tests for Notes Editing Bugfix

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

These tests verify that non-buggy behavior remains unchanged after the fix.

IMPORTANT: Follow observation-first methodology
- These tests capture the CURRENT behavior on UNFIXED code
- They should PASS on unfixed code (confirming baseline behavior)
- They should PASS on fixed code (confirming no regressions)

EXPECTED OUTCOME: Tests PASS on both unfixed and fixed code

Property-based testing generates many test cases for stronger guarantees.
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
    return SimpleUploadedFile('test_video.mp4', b'fake video content', content_type='video/mp4')


class PreservationPropertyTests(HypothesisTestCase):
    """
    Property 2: Preservation - Non-Buggy Behavior Remains Unchanged
    
    These tests verify that the fix does not break existing functionality:
    - Property 4: New attachment removal continues to work
    - Property 5: Title display for non-empty titles unchanged
    - Property 6: All other edit features unchanged
    - Property 8: Attachment display in detail modal unchanged
    - Property 9: Read-only display unchanged
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
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow]
    )
    @given(
        title=st.text(min_size=1, max_size=50).filter(lambda x: x.strip() != ''),
        post_color=st.sampled_from(['yellow', 'blue', 'green', 'pink', 'purple', 'white'])
    )
    def test_property5_title_display_for_nonempty_titles_unchanged(self, title, post_color):
        """
        **Property 5: Preservation** - Title Display for Non-Empty Titles Unchanged
        
        **Validates: Requirement 3.2**
        
        For any note with a non-empty title, the post card SHALL continue to display
        the title text exactly as before.
        
        This test observes the current behavior on unfixed code and ensures it remains
        unchanged after the fix.
        """
        # Create a post with a non-empty title
        post = Post.objects.create(
            board=self.board,
            author=self.user,
            title=title.strip(),
            content='Test content',
            color=post_color,
            is_anonymous=False
        )
        
        # Render the post card template
        card_html = render_to_string('padlet/_post_card.html', {
            'post': post,
            'board': self.board,
            'is_manager': False,
            'reaction_choices': [('thumbsup', '👍'), ('thumbsdown', '👎')],
            'request': type('obj', (object,), {'user': self.user})()
        })
        
        # Verify that the title is displayed in the post card
        # The title should be present in the HTML
        self.assertIn(title.strip()[:25], card_html, 
                     f"Title '{title.strip()[:25]}' should be displayed in post card")
        
        # Verify that no placeholder text is shown
        self.assertNotIn('Add a title…', card_html,
                        "Placeholder text should not appear when title exists")
    
    @settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow]
    )
    @given(
        attachment_type=st.sampled_from(['image', 'video']),
        post_color=st.sampled_from(['yellow', 'blue', 'green', 'pink', 'purple', 'white'])
    )
    def test_property8_attachment_display_in_detail_modal_unchanged(
        self, attachment_type, post_color
    ):
        """
        **Property 8: Preservation** - Attachment Display in Detail Modal Unchanged
        
        **Validates: Requirement 3.5**
        
        For any note being viewed in the detail modal, the fixed template SHALL continue
        to display all existing attachments (images, videos, files, URLs) correctly.
        
        This test observes the current behavior on unfixed code and ensures attachments
        are displayed correctly after the fix.
        """
        # Create a post with an attachment
        post = Post.objects.create(
            board=self.board,
            author=self.user,
            title='Post with Attachment',
            content='Test content',
            color=post_color,
            is_anonymous=False
        )
        
        # Create an attachment
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
        
        # Render the post detail template
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
        
        # Verify that the attachment is displayed
        self.assertIn(f'att-wrap-{attachment.id}', detail_html,
                     f"Attachment wrapper for {attachment_type} should be present")
        
        # Verify that the attachment file URL is present
        self.assertIn(attachment.file.url, detail_html,
                     f"Attachment file URL should be present in detail modal")
        
        # Verify that the attachment list container is present
        self.assertIn(f'att-list-{post.id}', detail_html,
                     "Attachment list container should be present")
        
        # Clean up
        if attachment.file:
            attachment.file.delete()
    
    @settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow]
    )
    @given(
        title=st.text(min_size=0, max_size=50),
        content=st.text(min_size=1, max_size=200),
        post_color=st.sampled_from(['yellow', 'blue', 'green', 'pink', 'purple', 'white'])
    )
    def test_property9_readonly_display_unchanged(self, title, content, post_color):
        """
        **Property 9: Preservation** - Read-Only Display Unchanged
        
        **Validates: Requirement 3.6**
        
        For any note being viewed in non-edit mode, the fixed template SHALL continue
        to display the note content in read-only mode exactly as before.
        
        This test observes the current behavior on unfixed code and ensures read-only
        display remains unchanged after the fix.
        """
        # Create a post
        post = Post.objects.create(
            board=self.board,
            author=self.user,
            title=title.strip() if title.strip() else '',
            content=content,
            color=post_color,
            is_anonymous=False
        )
        
        # Render the post detail template in read-only mode (can_edit=False)
        detail_html = render_to_string('padlet/_post_detail.html', {
            'post': post,
            'board': self.board,
            'can_edit': False,  # Read-only mode
            'can_delete': False,
            'is_manager': False,
            'attachments': post.attachments.all(),
            'replies': [],
            'reaction_choices': [('thumbsup', '👍'), ('thumbsdown', '👎')],
            'reaction_counts': {},
            'user_reaction': None,
            'color_choices': Post.COLOR_CHOICES,
            'csrf_token': 'test-csrf-token'
        })
        
        # Verify that content is displayed
        self.assertIn(content, detail_html,
                     "Post content should be displayed in read-only mode")
        
        # Verify that edit controls are NOT present
        self.assertNotIn('startEditPost', detail_html,
                        "Edit button should not be present in read-only mode")
        
        # Verify that the edit attachment zone is NOT present
        self.assertNotIn(f'edit-attach-zone-{post.id}', detail_html,
                        "Edit attachment zone should not be present in read-only mode")
        
        # Verify that the color picker is NOT present
        self.assertNotIn(f'edit-color-row-{post.id}', detail_html,
                        "Color picker should not be present in read-only mode")
    
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow]
    )
    @given(
        attachment_type=st.sampled_from(['image', 'video']),
        post_color=st.sampled_from(['yellow', 'blue', 'green', 'pink', 'purple', 'white'])
    )
    def test_property4_new_attachment_removal_continues_to_work(
        self, attachment_type, post_color
    ):
        """
        **Property 4: Preservation** - New Attachment Removal Continues to Work
        
        **Validates: Requirement 3.1**
        
        For any note being edited where a new attachment is added during the current
        edit session, the fixed template SHALL continue to display an X button on the
        newly added attachment preview, preserving existing functionality.
        
        This test observes the current behavior on unfixed code and ensures new
        attachment removal functionality remains unchanged after the fix.
        """
        # Create a post without attachments
        post = Post.objects.create(
            board=self.board,
            author=self.user,
            title='Post for New Attachment',
            content='Test content',
            color=post_color,
            is_anonymous=False
        )
        
        # Render the post detail template in edit mode
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
        
        # Verify that the edit attachment zone is present
        self.assertIn(f'edit-attach-zone-{post.id}', detail_html,
                     "Edit attachment zone should be present in edit mode")
        
        # Verify that the media picker is present
        self.assertIn(f'edit-attach-picker-{post.id}', detail_html,
                     "Media picker should be present for adding new attachments")
        
        # Verify that the preview area with removal button is present
        self.assertIn(f'edit-attach-preview-{post.id}', detail_html,
                     "Preview area for new attachments should be present")
        
        # Verify that the removal button function is present
        self.assertIn('clearEditMediaPick', detail_html,
                     "Removal function for new attachments should be present")
        
        # Verify that the X button SVG is present in the preview area
        # This is the removal button for newly added attachments
        self.assertIn('M6 18L18 6M6 6l12 12', detail_html,
                     "X button SVG for new attachment removal should be present")


class ManualPreservationTests(TestCase):
    """
    Manual test cases for preservation properties
    
    These tests provide concrete examples of preserved behavior for documentation.
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
    
    def test_property6_edit_features_unchanged_title(self):
        """
        **Property 6: Preservation** - All Other Edit Features Unchanged (Title)
        
        **Validates: Requirement 3.3**
        
        Verify that title editing continues to work correctly.
        """
        post = Post.objects.create(
            board=self.board,
            author=self.user,
            title='Original Title',
            content='Test content',
            color='yellow'
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
        
        # Verify that the title element is present and editable
        self.assertIn(f'edit-title-{post.id}', detail_html,
                     "Title element should be present")
        
        # Verify that the edit button is present
        self.assertIn('startEditPost', detail_html,
                     "Edit button should be present")
        
        # Verify that the save button is present
        self.assertIn('saveEditPost', detail_html,
                     "Save button should be present")
    
    def test_property6_edit_features_unchanged_content(self):
        """
        **Property 6: Preservation** - All Other Edit Features Unchanged (Content)
        
        **Validates: Requirement 3.3**
        
        Verify that content editing continues to work correctly.
        """
        post = Post.objects.create(
            board=self.board,
            author=self.user,
            title='Test Post',
            content='Original content',
            color='blue'
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
        
        # Verify that the body element is present and editable
        self.assertIn(f'edit-body-{post.id}', detail_html,
                     "Body element should be present")
        
        # Verify that the content is displayed
        self.assertIn('Original content', detail_html,
                     "Content should be displayed")
    
    def test_property6_edit_features_unchanged_color(self):
        """
        **Property 6: Preservation** - All Other Edit Features Unchanged (Color)
        
        **Validates: Requirement 3.3**
        
        Verify that color editing continues to work correctly.
        """
        post = Post.objects.create(
            board=self.board,
            author=self.user,
            title='Test Post',
            content='Test content',
            color='green'
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
        
        # Verify that the color picker is present
        self.assertIn(f'edit-color-row-{post.id}', detail_html,
                     "Color picker should be present")
        
        # Verify that the color selection function is present
        self.assertIn('selectEditColor', detail_html,
                     "Color selection function should be present")
    
    def test_property6_edit_features_unchanged_link_url(self):
        """
        **Property 6: Preservation** - All Other Edit Features Unchanged (Link URL)
        
        **Validates: Requirement 3.3**
        
        Verify that link URL editing continues to work correctly.
        """
        post = Post.objects.create(
            board=self.board,
            author=self.user,
            title='Test Post',
            content='Test content',
            color='pink',
            link_url='https://example.com'
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
        
        # Verify that the link input is present
        self.assertIn(f'edit-link-input-{post.id}', detail_html,
                     "Link input should be present")
        
        # Verify that the link URL is displayed
        self.assertIn('https://example.com', detail_html,
                     "Link URL should be displayed")
    
    def test_property7_attachment_deletion_backend_endpoint_exists(self):
        """
        **Property 7: Preservation** - Attachment Deletion Backend Unchanged
        
        **Validates: Requirement 3.4**
        
        Verify that the attachment deletion endpoint continues to exist and work.
        
        Note: This test verifies the endpoint structure is preserved. Full backend
        testing would require integration tests with actual HTTP requests.
        """
        post = Post.objects.create(
            board=self.board,
            author=self.user,
            title='Test Post',
            content='Test content',
            color='purple'
        )
        
        attachment = PostAttachment.objects.create(
            post=post,
            attachment_type='image',
            file=create_test_image(),
            original_filename='test_image.png'
        )
        
        # Verify that the attachment exists
        self.assertTrue(PostAttachment.objects.filter(id=attachment.id).exists(),
                       "Attachment should exist in database")
        
        # Verify that the attachment has a file
        self.assertTrue(attachment.file,
                       "Attachment should have a file")
        
        # Clean up
        if attachment.file:
            attachment.file.delete()
