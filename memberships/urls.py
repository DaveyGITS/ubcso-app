from django.urls import path
from . import views

app_name = 'memberships'

urlpatterns = [
    path('request/<int:org_id>/', views.membership_request_view, name='membership_request'),
    path('requests/', views.my_requests_view, name='my_requests'),
    path('leave/<int:org_id>/', views.leave_request_view, name='leave_request'),
    path('request/<int:request_id>/cancel/', views.cancel_membership_request_view, name='cancel_membership_request'),
    path('leave/<int:request_id>/cancel/', views.cancel_leave_request_view, name='cancel_leave_request'),
    path('invite/<int:request_id>/respond/', views.respond_invite_view, name='respond_invite'),
]