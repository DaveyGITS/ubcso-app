from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('admin-panel/', views.admin_panel_view, name='admin_panel'),
    path('admin-panel/org-requests/', views.admin_org_requests_view, name='admin_org_requests'),
    path('admin-panel/org-requests/<int:request_id>/action/', views.admin_approve_org_request_view, name='admin_approve_org_request'),
    path('admin-panel/membership-requests/', views.admin_membership_requests_view, name='admin_membership_requests'),
    path('admin-panel/students/', views.admin_students_view, name='admin_students'),
    path('admin-panel/students/<int:user_id>/deactivate/', views.admin_deactivate_student_view, name='admin_deactivate_student'),
    path('admin-panel/faculty-requests/', views.admin_faculty_requests_view, name='admin_faculty_requests'),
    path('admin-panel/orgs/', views.admin_orgs_view, name='admin_orgs'),
    path('admin-panel/orgs/<int:org_id>/dissolve/', views.admin_dissolve_org_view, name='admin_dissolve_org'),
    path('admin-panel/categories/', views.admin_categories_view, name='admin_categories'),
    path('admin-panel/privileges/', views.admin_privileges_view, name='admin_privileges'),
    path('admin-panel/system-settings/', views.system_settings_view, name='system_settings'),
    path('admin-panel/presidency-transfer/', views.presidency_transfer_view, name='presidency_transfer'),
    path('admin-panel/revoke-temp-admin/', views.revoke_temp_admin_view, name='revoke_temp_admin'),
    path('admin-panel/handover-notes/', views.handover_notes_view, name='handover_notes'),
    path('admin-panel/correction-requests/', views.admin_correction_requests_view, name='admin_correction_requests'),
    path('admin-panel/correction-requests/<int:request_id>/action/', views.admin_review_correction_request_view, name='admin_review_correction_request'),
    path('admin-panel/academic-periods/', views.admin_academic_periods_view, name='admin_academic_periods'),
    path('admin-panel/school-year-transition/', views.admin_school_year_transition_view, name='admin_school_year_transition'),
    path('admin-panel/audit-log/', views.admin_audit_log_view, name='admin_audit_log'),
    path('admin-panel/export/', views.admin_export_view, name='admin_export'),
    path('admin-panel/export/students/', views.export_students_view, name='export_students'),
    path('admin-panel/export/orgs/', views.export_orgs_view, name='export_orgs'),
    path('search/', views.search_view, name='search'),
    path('admin-panel/privileges/search/', views.cso_member_search_view, name='cso_member_search'),
    path('admin-panel/presidency-transfer/search/', views.cso_successor_search_view, name='cso_successor_search'),
    path('discovery-widget/', views.discovery_widget_view, name='discovery_widget'),
]