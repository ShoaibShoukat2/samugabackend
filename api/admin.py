from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import User, TripRequest, Quote, Payment, Booking, SupportMessage, Notification

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'phone_number', 'is_admin', 'trip_count', 'date_joined']
    list_filter = ['is_admin', 'date_joined']
    search_fields = ['username', 'email', 'phone_number', 'first_name', 'last_name']
    readonly_fields = ['date_joined', 'last_login']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('username', 'email', 'phone_number', 'first_name', 'last_name')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_admin', 'is_superuser')
        }),
        ('Important Dates', {
            'fields': ('date_joined', 'last_login')
        }),
    )
    
    def trip_count(self, obj):
        count = obj.trip_requests.count()
        return format_html(
            '<span style="background: #0066CC; color: white; padding: 3px 10px; border-radius: 12px;">{}</span>',
            count
        )
    trip_count.short_description = 'Total Trips'

@admin.register(TripRequest)
class TripRequestAdmin(admin.ModelAdmin):
    list_display = ['trip_id', 'user_info', 'trip_type_badge', 'route', 'trip_datetime', 'status_badge', 'quick_actions']
    list_filter = ['status', 'trip_type', 'trip_date', 'created_at']
    search_fields = ['user__email', 'user__phone_number', 'pickup_location', 'destination']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'trip_date'
    
    fieldsets = (
        ('Trip Information', {
            'fields': ('user', 'trip_type', 'status')
        }),
        ('Location Details', {
            'fields': ('pickup_location', 'destination')
        }),
        ('Schedule', {
            'fields': ('trip_date', 'trip_time', 'passenger_count')
        }),
        ('Additional Info', {
            'fields': ('special_notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def trip_id(self, obj):
        return str(obj.id)[:8]
    trip_id.short_description = 'ID'
    
    def user_info(self, obj):
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            obj.user.email,
            obj.user.phone_number or 'No phone'
        )
    user_info.short_description = 'Customer'
    
    def trip_type_badge(self, obj):
        icons = {
            'transfer': '🚤',
            'snorkeling': '🤿',
            'fishing': '🎣',
            'sandbank': '🏖️',
            'guesthouse_transfer': '🏨',
        }
        return format_html(
            '<span style="font-size: 20px;">{}</span> {}',
            icons.get(obj.trip_type, '🚤'),
            obj.get_trip_type_display()
        )
    trip_type_badge.short_description = 'Trip Type'
    
    def route(self, obj):
        return format_html(
            '<strong>From:</strong> {}<br><strong>To:</strong> {}',
            obj.pickup_location,
            obj.destination
        )
    route.short_description = 'Route'
    
    def trip_datetime(self, obj):
        return format_html(
            '📅 {}<br>🕐 {}',
            obj.trip_date.strftime('%d %b %Y'),
            obj.trip_time.strftime('%I:%M %p')
        )
    trip_datetime.short_description = 'Date & Time'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#FFA500',
            'quoted': '#2196F3',
            'accepted': '#4CAF50',
            'payment_pending': '#FF9800',
            'confirmed': '#4CAF50',
            'completed': '#9E9E9E',
            'cancelled': '#F44336',
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 5px 12px; border-radius: 12px; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#9E9E9E'),
            obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def quick_actions(self, obj):
        if obj.status == 'pending':
            return format_html(
                '<a class="button" href="/admin/api/triprequest/{}/send-quote/" style="background: #0066CC; color: white; padding: 5px 10px; border-radius: 5px; text-decoration: none;">Send Quote</a>',
                obj.id
            )
        elif hasattr(obj, 'quote'):
            return format_html(
                '<span style="color: green;">✓ Quote Sent</span>'
            )
        return '-'
    quick_actions.short_description = 'Quick Actions'

@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ['quote_id', 'trip_info', 'amount_display', 'operator_info', 'validity', 'created_at']
    search_fields = ['operator_name', 'trip_request__user__email']
    readonly_fields = ['created_at']
    
    def quote_id(self, obj):
        return f"Q-{obj.id}"
    quote_id.short_description = 'Quote ID'
    
    def trip_info(self, obj):
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            obj.trip_request.user.email,
            obj.trip_request.get_trip_type_display()
        )
    trip_info.short_description = 'Trip'
    
    def amount_display(self, obj):
        return format_html(
            '<span style="font-size: 18px; font-weight: bold; color: #0066CC;">${}</span>',
            obj.amount
        )
    amount_display.short_description = 'Amount'
    
    def operator_info(self, obj):
        return format_html(
            '<strong>{}</strong><br><small>📞 {}</small>',
            obj.operator_name,
            obj.operator_contact
        )
    operator_info.short_description = 'Operator'
    
    def validity(self, obj):
        from django.utils import timezone
        if obj.valid_until > timezone.now():
            return format_html(
                '<span style="color: green;">✓ Valid until {}</span>',
                obj.valid_until.strftime('%d %b %Y')
            )
        return format_html(
            '<span style="color: red;">✗ Expired</span>'
        )
    validity.short_description = 'Validity'

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_id', 'trip_info', 'amount_display', 'payment_method_badge', 'status_badge', 'proof', 'quick_actions']
    list_filter = ['status', 'payment_method', 'created_at']
    readonly_fields = ['id', 'created_at', 'verified_at', 'payment_proof_preview']
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('trip_request', 'payment_method', 'amount', 'transaction_id')
        }),
        ('Proof', {
            'fields': ('payment_proof', 'payment_proof_preview')
        }),
        ('Status', {
            'fields': ('status', 'verified_at')
        }),
    )
    
    def payment_id(self, obj):
        return str(obj.id)[:8]
    payment_id.short_description = 'Payment ID'
    
    def trip_info(self, obj):
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            obj.trip_request.user.email,
            obj.trip_request.get_trip_type_display()
        )
    trip_info.short_description = 'Customer'
    
    def amount_display(self, obj):
        return format_html(
            '<span style="font-size: 18px; font-weight: bold; color: #0066CC;">${}</span>',
            obj.amount
        )
    amount_display.short_description = 'Amount'
    
    def payment_method_badge(self, obj):
        icons = {
            'card': '💳',
            'bml': '🏦',
            'mib': '🏦',
        }
        return format_html(
            '{} {}',
            icons.get(obj.payment_method, '💰'),
            obj.get_payment_method_display()
        )
    payment_method_badge.short_description = 'Method'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#FFA500',
            'verified': '#4CAF50',
            'failed': '#F44336',
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 5px 12px; border-radius: 12px; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#9E9E9E'),
            obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def proof(self, obj):
        if obj.payment_proof:
            return format_html(
                '<a href="{}" target="_blank">View Proof</a>',
                obj.payment_proof.url
            )
        return '-'
    proof.short_description = 'Proof'
    
    def payment_proof_preview(self, obj):
        if obj.payment_proof:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px;" />',
                obj.payment_proof.url
            )
        return 'No proof uploaded'
    payment_proof_preview.short_description = 'Payment Proof'
    
    def quick_actions(self, obj):
        if obj.status == 'pending':
            return format_html(
                '<a class="button" href="/admin/api/payment/{}/verify/" style="background: #4CAF50; color: white; padding: 5px 10px; border-radius: 5px; text-decoration: none;">Verify Payment</a>',
                obj.id
            )
        elif obj.status == 'verified':
            return format_html(
                '<span style="color: green;">✓ Verified on {}</span>',
                obj.verified_at.strftime('%d %b %Y') if obj.verified_at else 'N/A'
            )
        return '-'
    quick_actions.short_description = 'Quick Actions'

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['booking_code_display', 'trip_info', 'trip_details', 'qr_preview', 'created_at']
    search_fields = ['booking_code', 'trip_request__user__email']
    readonly_fields = ['id', 'created_at', 'qr_code_preview']
    
    def booking_code_display(self, obj):
        return format_html(
            '<span style="font-size: 20px; font-weight: bold; color: #0066CC;">{}</span>',
            obj.booking_code
        )
    booking_code_display.short_description = 'Booking Code'
    
    def trip_info(self, obj):
        return format_html(
            '<strong>{}</strong><br><small>📞 {}</small>',
            obj.trip_request.user.email,
            obj.trip_request.user.phone_number or 'No phone'
        )
    trip_info.short_description = 'Customer'
    
    def trip_details(self, obj):
        return format_html(
            '<strong>{}</strong><br>📅 {} 🕐 {}',
            obj.trip_request.get_trip_type_display(),
            obj.trip_request.trip_date.strftime('%d %b %Y'),
            obj.trip_request.trip_time.strftime('%I:%M %p')
        )
    trip_details.short_description = 'Trip Details'
    
    def qr_preview(self, obj):
        if obj.qr_code:
            return format_html(
                '<img src="{}" style="width: 80px; height: 80px;" />',
                obj.qr_code.url
            )
        return '-'
    qr_preview.short_description = 'QR Code'
    
    def qr_code_preview(self, obj):
        if obj.qr_code:
            return format_html(
                '<img src="{}" style="max-width: 300px;" />',
                obj.qr_code.url
            )
        return 'No QR code generated'
    qr_code_preview.short_description = 'QR Code'

@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ['message_id', 'user_info', 'message_preview', 'type_badge', 'read_status', 'created_at']
    list_filter = ['is_admin_reply', 'read', 'created_at']
    search_fields = ['user__email', 'message']
    
    def message_id(self, obj):
        return str(obj.id)[:8]
    message_id.short_description = 'ID'
    
    def user_info(self, obj):
        return format_html(
            '<strong>{}</strong>',
            obj.user.email
        )
    user_info.short_description = 'User'
    
    def message_preview(self, obj):
        preview = obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
        return format_html('<span>{}</span>', preview)
    message_preview.short_description = 'Message'
    
    def type_badge(self, obj):
        if obj.is_admin_reply:
            return format_html(
                '<span style="background: #0066CC; color: white; padding: 3px 8px; border-radius: 8px;">Admin</span>'
            )
        return format_html(
            '<span style="background: #4CAF50; color: white; padding: 3px 8px; border-radius: 8px;">Customer</span>'
        )
    type_badge.short_description = 'Type'
    
    def read_status(self, obj):
        if obj.read:
            return format_html('<span style="color: green;">✓ Read</span>')
        return format_html('<span style="color: orange;">● Unread</span>')
    read_status.short_description = 'Status'

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['notification_id', 'user_info', 'title', 'read_status', 'created_at']
    list_filter = ['read', 'created_at']
    search_fields = ['user__email', 'title', 'message']
    
    def notification_id(self, obj):
        return str(obj.id)
    notification_id.short_description = 'ID'
    
    def user_info(self, obj):
        return format_html('<strong>{}</strong>', obj.user.email)
    user_info.short_description = 'User'
    
    def read_status(self, obj):
        if obj.read:
            return format_html('<span style="color: green;">✓ Read</span>')
        return format_html('<span style="color: orange;">● Unread</span>')
    read_status.short_description = 'Status'

