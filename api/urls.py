from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AuthViewSet, TripRequestViewSet, PaymentViewSet, BookingViewSet,
    SupportMessageViewSet, NotificationViewSet, dashboard_stats
)
from .admin_views import (
    admin_dashboard, trip_requests_list, send_quote_view, payments_list,
    verify_payment, bookings_list, support_messages, send_support_reply, users_list
)
from .auth_views import admin_login_view, admin_logout_view

router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'trips', TripRequestViewSet, basename='trip')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'support', SupportMessageViewSet, basename='support')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    # API endpoints
    path('', include(router.urls)),
    path('dashboard/stats/', dashboard_stats, name='dashboard-stats'),
    
    # Admin authentication
    path('admin-panel/login/', admin_login_view, name='admin_login'),
    path('admin-panel/logout/', admin_logout_view, name='admin_logout'),
    
    # Admin panel URLs
    path('admin-panel/', admin_dashboard, name='admin_dashboard'),
    path('admin-panel/trips/', trip_requests_list, name='admin_trip_requests'),
    path('admin-panel/trips/<uuid:trip_id>/quote/', send_quote_view, name='admin_send_quote'),
    path('admin-panel/payments/', payments_list, name='admin_payments'),
    path('admin-panel/payments/<uuid:payment_id>/verify/', verify_payment, name='admin_verify_payment'),
    path('admin-panel/bookings/', bookings_list, name='admin_bookings'),
    path('admin-panel/support/', support_messages, name='admin_support'),
    path('admin-panel/support/<int:user_id>/reply/', send_support_reply, name='admin_support_reply'),
    path('admin-panel/users/', users_list, name='admin_users'),
]

