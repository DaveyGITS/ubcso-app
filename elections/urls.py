from django.urls import path
from . import views

app_name = 'elections'

urlpatterns = [
    path('', views.election_list_view, name='election_list'),
    path('create/', views.election_create_view, name='election_create'),
    path('archive/', views.admin_archive_view, name='admin_archive'),
    path('archive/<int:election_id>/', views.admin_archive_detail_view, name='admin_archive_detail'),
    path('<int:election_id>/manage/', views.election_manage_view, name='election_manage'),
    path('<int:election_id>/action-buttons/', views.election_action_buttons_view, name='election_action_buttons'),
    path('<int:election_id>/open/', views.election_open_view, name='election_open'),
    path('<int:election_id>/close/', views.election_close_view, name='election_close'),
    path('<int:election_id>/release/', views.election_release_view, name='election_release'),
    path('<int:election_id>/vote/', views.election_vote_view, name='election_vote'),
    path('<int:election_id>/live-count/', views.election_live_count_view, name='live_count'),
    path('<int:election_id>/voter-stats/', views.election_voter_stats_view, name='voter_stats'),
    path('<int:election_id>/results/', views.election_results_view, name='election_results'),
    path('<int:election_id>/promote/', views.election_promote_view, name='election_promote'),
    path('<int:election_id>/handover-confirm/', views.election_handover_confirm_view, name='election_handover_confirm'),
    path('<int:election_id>/cancel/', views.election_cancel_view, name='election_cancel'),
    path('<int:election_id>/delete/', views.election_delete_view, name='election_delete'),
    path('<int:election_id>/member-search/', views.election_member_search_view, name='member_search'),
]
