from django.urls import path
from . import views

app_name = 'organizations'

urlpatterns = [
    path('', views.directory_view, name='directory'),
    path('<int:org_id>/', views.org_profile_view, name='org_profile'),
    path('apply/', views.accreditation_apply_view, name='accreditation_apply'),
    path('claim/', views.claim_existing_org_view, name='claim_existing_org'),
    path('request/', views.org_request_view, name='org_request'),
    path('request/<int:request_id>/cancel/', views.cancel_org_request_view, name='cancel_org_request'),
    path('registration/<int:registration_id>/cancel/', views.cancel_org_registration_view, name='cancel_org_registration'),

    # Chairman dashboard
    path('<int:org_id>/manage/', views.chairman_dashboard_view, name='chairman_dashboard'),
    path('<int:org_id>/manage/members/', views.chairman_members_view, name='chairman_members'),
    path('<int:org_id>/manage/members/promote/<int:membership_id>/', views.chairman_promote_member_view, name='chairman_promote_member'),
    path('<int:org_id>/manage/members/add/', views.chairman_direct_add_view, name='chairman_direct_add'),
    path('<int:org_id>/manage/roles/create/', views.chairman_create_role_view, name='chairman_create_role'),
    path('<int:org_id>/manage/join-requests/<int:request_id>/review/', views.chairman_review_join_request_view, name='chairman_review_join'),
    path('<int:org_id>/manage/leave-requests/<int:request_id>/review/', views.chairman_review_leave_request_view, name='chairman_review_leave'),
    path('<int:org_id>/manage/edit/', views.chairman_edit_org_view, name='chairman_edit_org'),
    path('<int:org_id>/manage/members/remove/<int:membership_id>/', views.chairman_remove_member_view, name='chairman_remove_member'),
    path('<int:org_id>/manage/roles/<int:role_id>/delete/', views.chairman_delete_role_view, name='chairman_delete_role'),
    path('<int:org_id>/member-view/', views.student_org_view, name='student_org_view'),

    # Chairman handover
    path('<int:org_id>/manage/handover/', views.chairman_handover_view, name='chairman_handover'),
    path('<int:org_id>/manage/handover/revoke/', views.chairman_revoke_temp_access_view, name='chairman_revoke_temp'),

    # Renewal application
    path('<int:org_id>/manage/renew/', views.renewal_apply_view, name='renewal_apply'),

    # Media: Albums
    path('<int:org_id>/media/albums/create/', views.album_create_view, name='album_create'),
    path('<int:org_id>/media/albums/<int:album_id>/edit/', views.album_edit_view, name='album_edit'),
    path('<int:org_id>/media/albums/<int:album_id>/delete/', views.album_delete_view, name='album_delete'),

    # Media: Videos
    path('<int:org_id>/media/videos/upload/', views.video_upload_view, name='video_upload'),
    path('<int:org_id>/media/videos/<int:video_id>/delete/', views.video_delete_view, name='video_delete'),

    # Media: Showcase
    path('<int:org_id>/media/showcase/', views.showcase_form_view, name='showcase_form'),
    path('<int:org_id>/media/showcase/set/', views.showcase_set_view, name='showcase_set'),
    path('<int:org_id>/media/showcase/clear/', views.showcase_clear_view, name='showcase_clear'),

    # Leadership reorder
    path('<int:org_id>/manage/officers/reorder/', views.reorder_officers_view, name='reorder_officers'),

    # Member search (autocomplete for invite)
    path('<int:org_id>/manage/members/search/', views.chairman_member_search_view, name='chairman_member_search'),

    # Accreditation admin
    path('admin/accreditation/', views.admin_accreditation_panel_view, name='admin_accreditation_panel'),
    path('admin/accreditation/<int:app_id>/', views.admin_review_application_view, name='admin_review_application'),
    path('admin/accreditation/<int:app_id>/action/', views.admin_review_action_view, name='admin_review_action'),

    # Organization registration admin
    path('admin/registrations/', views.admin_org_registration_panel_view, name='admin_org_registration_panel'),
    path('admin/registrations/<int:reg_id>/', views.admin_review_org_registration_view, name='admin_review_org_registration'),
    path('admin/registrations/<int:reg_id>/action/', views.admin_review_org_registration_action_view, name='admin_review_org_registration_action'),

    # School year controls
    path('admin/new-school-year/', views.admin_new_school_year_view, name='admin_new_school_year'),
    path('admin/close-renewal/', views.admin_close_renewal_view, name='admin_close_renewal'),

    # Official form links
    path('admin/form-links/', views.admin_form_links_view, name='admin_form_links'),
    path('admin/form-links/<int:link_id>/delete/', views.admin_form_link_delete_view, name='admin_form_link_delete'),

    # Renewal requirements
    path('admin/renewal-requirements/', views.admin_renewal_requirements_view, name='admin_renewal_requirements'),
    path('admin/renewal-requirements/institutional/add/', views.admin_institutional_add_view, name='admin_institutional_add'),
    path('admin/renewal-requirements/institutional/remove/', views.admin_institutional_remove_view, name='admin_institutional_remove'),
    path('admin/renewal-requirements/standard/add/', views.admin_standard_renewal_add_view, name='admin_standard_renewal_add'),
    path('admin/renewal-requirements/standard/remove/', views.admin_standard_renewal_remove_view, name='admin_standard_renewal_remove'),
    path('admin/accreditation-requirements/<str:reg_type>/add/', views.admin_accreditation_req_add_view, name='admin_accreditation_req_add'),
    path('admin/accreditation-requirements/<str:reg_type>/remove/', views.admin_accreditation_req_remove_view, name='admin_accreditation_req_remove'),
    
    # Organization management
    path('admin/organizations/', views.admin_organizations_view, name='admin_organizations'),
    path('admin/organizations/<int:org_id>/edit-category/', views.admin_edit_org_category_view, name='admin_edit_org_category'),
]
