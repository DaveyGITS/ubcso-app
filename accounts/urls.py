from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('verify/', views.verify_otp_view, name='verify_otp'),
    path('verify/resend/', views.resend_otp_view, name='resend_otp'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('profile/correction-request/', views.submit_correction_request_view, name='submit_correction_request'),
    path('profile/correction-requests/', views.my_correction_requests_view, name='my_correction_requests'),
    path('profile/correction-requests/<int:request_id>/cancel/', views.cancel_correction_request_view, name='cancel_correction_request'),
    path('settings/', views.settings_view, name='settings'),
    path('profile/<int:user_id>/', views.student_profile_view, name='student_profile'),
    path('register/faculty/', views.faculty_register_view, name='faculty_register'),
    path('register/faculty/verify/', views.faculty_verify_otp_view, name='faculty_verify_otp'),
    path('register/faculty/verify/resend/', views.faculty_resend_otp_view, name='faculty_resend_otp'),
]