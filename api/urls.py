from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AuthViewSet, TripRequestViewSet, PaymentViewSet, BookingViewSet,
    SupportMessageViewSet, NotificationViewSet, dashboard_stats
)
from .marketplace_views import (
    SpeedboatOperatorViewSet, SpeedboatViewSet, MarketplaceQuoteViewSet,
    OperatorSubscriptionViewSet
)
from .auth_views import admin_login_view, admin_logout_view
from .admin_views import (
    admin_dashboard, trip_requests_list, send_quote_view, payments_list,
    verify_payment, bookings_list, support_messages, send_support_reply, users_list,
    accepted_requests,
    # Marketplace views
    operators_list, operator_detail, verify_operator, subscriptions_list,
    verify_subscription, marketplace_quotes, revenue_dashboard, platform_settings
)

router = DefaultRouter()
router.register(r'trip-requests', TripRequestViewSet, basename='trip-request')
router.register(r'trips', TripRequestViewSet, basename='trips')  # Alias for frontend compatibility
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'support', SupportMessageViewSet, basename='support')
router.register(r'notifications', NotificationViewSet, basename='notification')

# Marketplace endpoints
router.register(r'operators', SpeedboatOperatorViewSet, basename='operator')
router.register(r'boats', SpeedboatViewSet, basename='boat')
router.register(r'marketplace-quotes', MarketplaceQuoteViewSet, basename='marketplace-quote')
router.register(r'subscriptions', OperatorSubscriptionViewSet, basename='subscription')

urlpatterns = [
    # API endpoints
    path('', include(router.urls)),
    path('auth/register/', AuthViewSet.as_view({'post': 'register'}), name='auth-register'),
    path('auth/login/', AuthViewSet.as_view({'post': 'login'}), name='auth-login'),
    path('auth/send-otp/', AuthViewSet.as_view({'post': 'send_otp'}), name='auth-send-otp'),
    path('auth/verify-otp/', AuthViewSet.as_view({'post': 'verify_otp'}), name='auth-verify-otp'),
    path('auth/update-profile/', AuthViewSet.as_view({'post': 'update_profile', 'put': 'update_profile'}), name='auth-update-profile'),
    path('auth/check-account/', AuthViewSet.as_view({'post': 'check_account'}), name='auth-check-account'),
    path('dashboard/stats/', dashboard_stats, name='dashboard-stats'),
    
    # Admin panel views
    path('admin-panel/login/', admin_login_view, name='admin_login'),
    path('admin-panel/logout/', admin_logout_view, name='admin_logout'),
    path('admin-panel/dashboard/', admin_dashboard, name='admin_dashboard'),
    path('admin-panel/trip-requests/', trip_requests_list, name='admin_trip_requests'),
    path('admin-panel/accepted-requests/', accepted_requests, name='admin_accepted_requests'),
    path('admin-panel/send-quote/<uuid:trip_id>/', send_quote_view, name='admin_send_quote'),
    path('admin-panel/payments/', payments_list, name='admin_payments'),
    path('admin-panel/verify-payment/<uuid:payment_id>/', verify_payment, name='admin_verify_payment'),
    path('admin-panel/bookings/', bookings_list, name='admin_bookings'),
    path('admin-panel/support/', support_messages, name='admin_support'),
    path('admin-panel/support/reply/<int:user_id>/', send_support_reply, name='admin_support_reply'),
    path('admin-panel/users/', users_list, name='admin_users'),
    
    # Marketplace admin views
    path('admin-panel/operators/', operators_list, name='admin_operators'),
    path('admin-panel/operators/<uuid:operator_id>/', operator_detail, name='admin_operator_detail'),
    path('admin-panel/operators/<uuid:operator_id>/verify/', verify_operator, name='admin_verify_operator'),
    path('admin-panel/subscriptions/', subscriptions_list, name='admin_subscriptions'),
    path('admin-panel/subscriptions/<uuid:subscription_id>/verify/', verify_subscription, name='admin_verify_subscription'),
    path('admin-panel/marketplace-quotes/', marketplace_quotes, name='admin_marketplace_quotes'),
    path('admin-panel/revenue/', revenue_dashboard, name='admin_revenue_dashboard'),
    path('admin-panel/settings/', platform_settings, name='admin_platform_settings'),
]
