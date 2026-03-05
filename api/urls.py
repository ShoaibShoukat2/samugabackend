from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AuthViewSet, TripRequestViewSet, PaymentViewSet, BookingViewSet,
    SupportMessageViewSet, NotificationViewSet, dashboard_stats
)
from .auth_views import admin_login_view, admin_logout_view
from .admin_views import (
    admin_dashboard, trip_requests_list, send_quote_view, payments_list,
    verify_payment, bookings_list, support_messages, send_support_reply, users_list
)

router = DefaultRouter()
router.register(r'trip-requests', TripRequestViewSet, basename='trip-request')
router.register(r'trips', TripRequestViewSet, basename='trips')  # Alias for frontend compatibility
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'support', SupportMessageViewSet, basename='support')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    # API endpoints
    path('', include(router.urls)),
    path('auth/register/', AuthViewSet.as_view({'post': 'register'}), name='auth-register'),
    path('auth/login/', AuthViewSet.as_view({'post': 'login'}), name='auth-login'),
    path('auth/send-otp/', AuthViewSet.as_view({'post': 'send_otp'}), name='auth-send-otp'),
    path('auth/verify-otp/', AuthViewSet.as_view({'post': 'verify_otp'}), name='auth-verify-otp'),
    path('auth/update-profile/', AuthViewSet.as_view({'post': 'update_profile', 'put': 'update_profile'}), name='auth-update-profile'),
    path('dashboard/stats/', dashboard_stats, name='dashboard-stats'),
    
    # Admin panel views
    path('admin-panel/login/', admin_login_view, name='admin_login'),
    path('admin-panel/logout/', admin_logout_view, name='admin_logout'),
    path('admin-panel/dashboard/', admin_dashboard, name='admin_dashboard'),
    path('admin-panel/trip-requests/', trip_requests_list, name='admin_trip_requests'),
    path('admin-panel/send-quote/<uuid:trip_id>/', send_quote_view, name='admin_send_quote'),
    path('admin-panel/payments/', payments_list, name='admin_payments'),
    path('admin-panel/verify-payment/<uuid:payment_id>/', verify_payment, name='admin_verify_payment'),
    path('admin-panel/bookings/', bookings_list, name='admin_bookings'),
    path('admin-panel/support/', support_messages, name='admin_support'),
    path('admin-panel/support/reply/<int:user_id>/', send_support_reply, name='admin_support_reply'),
    path('admin-panel/users/', users_list, name='admin_users'),
]
