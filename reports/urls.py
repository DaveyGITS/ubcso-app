from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    path('org/<int:org_id>/', views.org_reports_view, name='org_reports'),
    path('org/<int:org_id>/submit/', views.submit_report_view, name='submit_report'),
    path('org/<int:org_id>/archive/', views.report_archive_view, name='report_archive'),
    path('org/<int:org_id>/compilations/', views.report_compilation_list_view, name='report_compilation_list'),
    path('org/<int:org_id>/compilations/create/', views.report_compilation_create_view, name='report_compilation_create'),
    path('org/<int:org_id>/compilations/<int:compilation_id>/edit/', views.report_compilation_edit_view, name='report_compilation_edit'),
    path('org/<int:org_id>/compilations/<int:compilation_id>/delete/', views.report_compilation_delete_view, name='report_compilation_delete'),
    path('admin/', views.admin_reports_view, name='admin_reports'),
    path('admin/<int:report_id>/review/', views.admin_review_report_view, name='admin_review_report'),
]
