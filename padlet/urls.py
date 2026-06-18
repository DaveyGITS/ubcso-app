from django.urls import path
from . import views

app_name = 'padlet'

urlpatterns = [
    # Board list & management
    path('', views.padlet_list_view, name='padlet_list'),
    path('create/', views.padlet_create_board_view, name='padlet_create'),
    path('archive/', views.padlet_archive_view, name='padlet_archive'),
    path('board/<int:board_id>/', views.padlet_board_view, name='padlet_board'),
    path('board/<int:board_id>/edit/', views.padlet_edit_board_view, name='padlet_edit'),
    path('board/<int:board_id>/archive/', views.padlet_archive_board_view, name='padlet_archive_board'),
    path('board/<int:board_id>/delete/', views.padlet_delete_board_view, name='padlet_delete_board'),

    # Post actions
    path('board/<int:board_id>/post/', views.padlet_add_post_view, name='padlet_add_post'),
    path('post/<int:post_id>/edit/', views.padlet_edit_post_view, name='padlet_edit_post'),
    path('post/<int:post_id>/delete/', views.padlet_delete_post_view, name='padlet_delete_post'),
    path('post/<int:post_id>/react/', views.padlet_react_view, name='padlet_react'),
    path('post/<int:post_id>/pin/', views.padlet_pin_post_view, name='padlet_pin_post'),

    # Reply actions
    path('post/<int:post_id>/reply/', views.padlet_add_reply_view, name='padlet_add_reply'),
    path('post/<int:post_id>/replies/', views.padlet_get_replies_view, name='padlet_get_replies'),
    path('post/<int:post_id>/detail/', views.padlet_post_detail_view, name='padlet_post_detail'),
    path('reply/<int:reply_id>/edit/', views.padlet_edit_reply_view, name='padlet_edit_reply'),
    path('reply/<int:reply_id>/delete/', views.padlet_delete_reply_view, name='padlet_delete_reply'),

    # Attachment actions
    path('post/<int:post_id>/attachment/', views.padlet_add_attachment_view, name='padlet_add_attachment'),
    path('attachment/<int:attachment_id>/delete/', views.padlet_delete_attachment_view, name='padlet_delete_attachment'),
]
