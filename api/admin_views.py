from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import timedelta
from .models import (User, TripRequest, Quote, Payment, Booking, SupportMessage, 
                    Notification, SpeedboatOperator, Speedboat, OperatorSubscription, 
                    OperatorRating, PlatformRevenue)
from decimal import Decimal

def is_admin(user):
    return user.is_authenticated and user.is_admin

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    # Get statistics
    total_trips = TripRequest.objects.count()
    pending_trips = TripRequest.objects.filter(status='pending').count()
    confirmed_bookings = TripRequest.objects.filter(status='confirmed').count()
    pending_payments = Payment.objects.filter(status='pending').count()
    total_users = User.objects.filter(is_admin=False).count()
    
    # Marketplace statistics
    total_operators = SpeedboatOperator.objects.count()
    verified_operators = SpeedboatOperator.objects.filter(verification_status='verified').count()
    pending_operators = SpeedboatOperator.objects.filter(verification_status='pending').count()
    active_subscriptions = SpeedboatOperator.objects.filter(subscription_status='active').count()
    
    # Revenue statistics
    monthly_subscription_revenue = PlatformRevenue.objects.filter(
        revenue_type='subscription',
        created_at__month=timezone.now().month
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    monthly_commission_revenue = PlatformRevenue.objects.filter(
        revenue_type='commission',
        created_at__month=timezone.now().month
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Recent trips
    recent_trips = TripRequest.objects.select_related('user').order_by('-created_at')[:10]
    
    # Pending payments
    pending_payment_list = Payment.objects.filter(status='pending').select_related('trip_request__user')[:5]
    
    # Recent support messages
    recent_messages = SupportMessage.objects.filter(is_admin_reply=False, read=False).select_related('user')[:5]
    
    context = {
        'total_trips': total_trips,
        'pending_trips': pending_trips,
        'confirmed_bookings': confirmed_bookings,
        'pending_payments': pending_payments,
        'total_users': total_users,
        'total_operators': total_operators,
        'verified_operators': verified_operators,
        'pending_operators': pending_operators,
        'active_subscriptions': active_subscriptions,
        'monthly_subscription_revenue': monthly_subscription_revenue,
        'monthly_commission_revenue': monthly_commission_revenue,
        'recent_trips': recent_trips,
        'pending_payment_list': pending_payment_list,
        'recent_messages': recent_messages,
    }
    
    return render(request, 'admin_panel/dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def accepted_requests(request):
    """Shows all trips that have been accepted by an operator — full assignment details"""
    trips = TripRequest.objects.filter(
        status__in=['accepted', 'payment_pending', 'confirmed', 'completed']
    ).select_related('user').prefetch_related(
        'quotes__operator__user',
        'quotes__boat',
        'payment',
        'booking',
    ).order_by('-updated_at')

    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        trips = trips.filter(status=status_filter)

    # Attach accepted quote to each trip for easy template access
    trip_data = []
    for trip in trips:
        accepted_q = trip.quotes.filter(status='accepted').first()
        trip_data.append({
            'trip': trip,
            'accepted_quote': accepted_q,
        })

    context = {
        'trip_data': trip_data,
        'status_filter': status_filter,
        'filter_tabs': [
            ('all', 'All Assigned', 'bg-blue-600'),
            ('accepted', 'Awaiting Payment', 'bg-orange-500'),
            ('payment_pending', 'Payment Pending', 'bg-purple-600'),
            ('confirmed', 'Confirmed', 'bg-green-600'),
            ('completed', 'Completed', 'bg-gray-600'),
        ],
    }
    return render(request, 'admin_panel/accepted_requests.html', context)


@login_required
@user_passes_test(is_admin)
def trip_requests_list(request):
    status_filter = request.GET.get('status', 'all')
    
    trips = TripRequest.objects.select_related('user').prefetch_related(
        'quotes__operator'
    ).order_by('-created_at')
    
    if status_filter != 'all':
        trips = trips.filter(status=status_filter)
    
    context = {
        'trips': trips,
        'status_filter': status_filter,
        'filter_tabs': [
            ('all', 'All', 'bg-blue-600'),
            ('pending', 'Pending', 'bg-yellow-600'),
            ('quoted', 'Quoted', 'bg-blue-500'),
            ('accepted', 'Accepted', 'bg-orange-500'),
            ('payment_pending', 'Payment Pending', 'bg-purple-600'),
            ('confirmed', 'Confirmed', 'bg-green-600'),
            ('completed', 'Completed', 'bg-gray-600'),
        ],
    }
    
    return render(request, 'admin_panel/trip_requests.html', context)

@login_required
@user_passes_test(is_admin)
def send_quote_view(request, trip_id):
    trip = get_object_or_404(TripRequest, id=trip_id)
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        currency = request.POST.get('currency', 'USD')
        operator_name = request.POST.get('operator_name')
        operator_contact = request.POST.get('operator_contact')
        notes = request.POST.get('notes', '')
        valid_days = int(request.POST.get('valid_days', 7))
        
        # Create or update quote
        quote, created = Quote.objects.update_or_create(
            trip_request=trip,
            defaults={
                'amount': Decimal(amount),
                'currency': currency,
                'operator_name': operator_name,
                'operator_contact': operator_contact,
                'notes': notes,
                'valid_until': timezone.now() + timedelta(days=valid_days)
            }
        )
        
        # Update trip status
        trip.status = 'quoted'
        trip.save()
        
        # Create notification for user
        currency_symbol = '$' if currency == 'USD' else 'MVR'
        Notification.objects.create(
            user=trip.user,
            title='Quote Received',
            message=f'You have received a quote of {currency_symbol}{amount} for your {trip.trip_type} trip',
            trip_request=trip
        )
        
        messages.success(request, 'Quote sent successfully!')
        return redirect('admin_trip_requests')
    
    context = {
        'trip': trip,
    }
    
    return render(request, 'admin_panel/send_quote.html', context)

@login_required
@user_passes_test(is_admin)
def payments_list(request):
    status_filter = request.GET.get('status', 'all')
    
    payments = Payment.objects.select_related('trip_request__user').order_by('-created_at')
    
    if status_filter != 'all':
        payments = payments.filter(status=status_filter)
    
    context = {
        'payments': payments,
        'status_filter': status_filter,
    }
    
    return render(request, 'admin_panel/payments.html', context)

@login_required
@user_passes_test(is_admin)
def verify_payment(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'reject':
            # Reject payment
            payment.status = 'failed'
            payment.save()
            
            # Update trip status back to accepted
            trip = payment.trip_request
            trip.status = 'accepted'
            trip.save()
            
            # Notify user
            Notification.objects.create(
                user=trip.user,
                title='Payment Rejected',
                message=f'Your payment for {trip.trip_type} trip was rejected. Please resubmit with correct details.',
                trip_request=trip
            )
            
            messages.warning(request, 'Payment rejected. Customer has been notified.')
            return redirect('admin_payments')
        
        elif action == 'approve':
            # Approve payment
            payment.status = 'verified'
            payment.verified_at = timezone.now()
            payment.save()
            
            # Update trip status
            trip = payment.trip_request
            trip.status = 'confirmed'
            trip.save()
            
            # Generate booking
            import random
            booking_code = f"ST{random.randint(100000, 999999)}"
            
            # Find the accepted quote (operator's quote that was accepted)
            accepted_quote = trip.quotes.filter(status='accepted').first()
            
            booking = Booking.objects.create(
                trip_request=trip,
                booking_code=booking_code,
                selected_quote=accepted_quote,
            )
            
            # Generate QR code
            import qrcode
            from io import BytesIO
            from django.core.files import File
            
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(booking_code)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            booking.qr_code.save(f'{booking_code}.png', File(buffer), save=True)
            
            # Notify customer
            Notification.objects.create(
                user=trip.user,
                title='Booking Confirmed',
                message=f'Your booking is confirmed! Booking code: {booking_code}',
                trip_request=trip
            )
            
            # Notify the operator whose quote was accepted
            if accepted_quote and accepted_quote.operator:
                Notification.objects.create(
                    user=accepted_quote.operator.user,
                    title='Payment Confirmed — Trip Ready',
                    message=f'Payment verified for your {trip.trip_type} trip on {trip.trip_date}. '
                            f'Customer: {trip.user.first_name} {trip.user.last_name}. '
                            f'Booking code: {booking_code}',
                    trip_request=trip
                )
            
            messages.success(request, f'Payment approved and booking {booking_code} created!')
            return redirect('admin_payments')
    
    context = {
        'payment': payment,
    }
    
    return render(request, 'admin_panel/verify_payment.html', context)

@login_required
@user_passes_test(is_admin)
def bookings_list(request):
    bookings = Booking.objects.select_related('trip_request__user').order_by('-created_at')
    
    context = {
        'bookings': bookings,
    }
    
    return render(request, 'admin_panel/bookings.html', context)

@login_required
@user_passes_test(is_admin)
def support_messages(request):
    conversations = []
    users_with_messages = User.objects.filter(support_messages__isnull=False).distinct()
    
    for user in users_with_messages:
        messages_list = SupportMessage.objects.filter(user=user).order_by('created_at')
        unread_count = messages_list.filter(is_admin_reply=False, read=False).count()
        
        conversations.append({
            'user': user,
            'messages': messages_list,
            'unread_count': unread_count,
            'last_message': messages_list.last()
        })
    
    context = {
        'conversations': conversations,
    }
    
    return render(request, 'admin_panel/support.html', context)

@login_required
@user_passes_test(is_admin)
def send_support_reply(request, user_id):
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        message_text = request.POST.get('message')
        
        SupportMessage.objects.create(
            user=user,
            message=message_text,
            is_admin_reply=True
        )
        
        # Mark user messages as read
        SupportMessage.objects.filter(user=user, is_admin_reply=False, read=False).update(read=True)
        
        messages.success(request, 'Reply sent successfully!')
        return redirect('admin_support')
    
    return redirect('admin_support')

@login_required
@user_passes_test(is_admin)
def users_list(request):
    users = User.objects.filter(is_admin=False).order_by('-date_joined')
    
    context = {
        'users': users,
    }
    
    return render(request, 'admin_panel/users.html', context)

# ============ MARKETPLACE ADMIN VIEWS ============

@login_required
@user_passes_test(is_admin)
def operators_list(request):
    status_filter = request.GET.get('status', 'all')
    
    operators = SpeedboatOperator.objects.select_related('user').order_by('-created_at')
    
    if status_filter != 'all':
        operators = operators.filter(verification_status=status_filter)
    
    context = {
        'operators': operators,
        'status_filter': status_filter,
    }
    
    return render(request, 'admin_panel/operators.html', context)

@login_required
@user_passes_test(is_admin)
def operator_detail(request, operator_id):
    operator = get_object_or_404(SpeedboatOperator, id=operator_id)
    boats = operator.boats.all()
    subscriptions = operator.subscriptions.order_by('-created_at')
    quotes = operator.quotes.select_related('trip_request').order_by('-created_at')[:10]
    ratings = operator.received_ratings.select_related('customer', 'booking').order_by('-created_at')[:10]
    
    context = {
        'operator': operator,
        'boats': boats,
        'subscriptions': subscriptions,
        'quotes': quotes,
        'ratings': ratings,
    }
    
    return render(request, 'admin_panel/operator_detail.html', context)

@login_required
@user_passes_test(is_admin)
def verify_operator(request, operator_id):
    operator = get_object_or_404(SpeedboatOperator, id=operator_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        if action == 'approve':
            operator.verification_status = 'verified'
            operator.save()
            
            # Notify operator
            Notification.objects.create(
                user=operator.user,
                title='Operator Account Approved',
                message=f'Congratulations! Your operator account has been approved. You can now receive trip requests.'
            )
            
            messages.success(request, f'Operator {operator.company_name} has been approved!')
            
        elif action == 'reject':
            operator.verification_status = 'rejected'
            operator.save()
            
            # Notify operator
            Notification.objects.create(
                user=operator.user,
                title='Operator Account Rejected',
                message=f'Your operator account application has been rejected. Reason: {notes}'
            )
            
            messages.warning(request, f'Operator {operator.company_name} has been rejected.')
            
        elif action == 'suspend':
            operator.verification_status = 'suspended'
            operator.subscription_status = 'cancelled'
            operator.save()
            
            # Notify operator
            Notification.objects.create(
                user=operator.user,
                title='Account Suspended',
                message=f'Your operator account has been suspended. Reason: {notes}'
            )
            
            messages.warning(request, f'Operator {operator.company_name} has been suspended.')
        
        return redirect('admin_operators')
    
    context = {
        'operator': operator,
    }
    
    return render(request, 'admin_panel/verify_operator.html', context)

@login_required
@user_passes_test(is_admin)
def subscriptions_list(request):
    status_filter = request.GET.get('status', 'all')
    
    subscriptions = OperatorSubscription.objects.select_related('operator').order_by('-created_at')
    
    if status_filter != 'all':
        subscriptions = subscriptions.filter(payment_status=status_filter)
    
    context = {
        'subscriptions': subscriptions,
        'status_filter': status_filter,
    }
    
    return render(request, 'admin_panel/subscriptions.html', context)

@login_required
@user_passes_test(is_admin)
def verify_subscription(request, subscription_id):
    subscription = get_object_or_404(OperatorSubscription, id=subscription_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            subscription.payment_status = 'paid'
            subscription.paid_at = timezone.now()
            subscription.save()
            
            # Update operator subscription status
            operator = subscription.operator
            operator.subscription_status = 'active'
            operator.subscription_expires_at = subscription.end_date
            operator.save()
            
            # Create revenue record
            PlatformRevenue.objects.create(
                revenue_type='subscription',
                amount=subscription.amount,
                currency='MVR',
                subscription=subscription,
                description=f'Subscription payment from {operator.company_name}'
            )
            
            # Notify operator
            Notification.objects.create(
                user=operator.user,
                title='Subscription Activated',
                message=f'Your subscription has been activated until {subscription.end_date.strftime("%B %d, %Y")}'
            )
            
            messages.success(request, f'Subscription approved for {operator.company_name}!')
            
        elif action == 'reject':
            subscription.payment_status = 'overdue'
            subscription.save()
            
            # Update operator subscription status
            operator = subscription.operator
            operator.subscription_status = 'expired'
            operator.save()
            
            # Notify operator
            Notification.objects.create(
                user=operator.user,
                title='Subscription Payment Rejected',
                message='Your subscription payment was rejected. Please resubmit with correct payment proof.'
            )
            
            messages.warning(request, f'Subscription rejected for {operator.company_name}.')
        
        return redirect('admin_subscriptions')
    
    context = {
        'subscription': subscription,
    }
    
    return render(request, 'admin_panel/verify_subscription.html', context)

@login_required
@user_passes_test(is_admin)
def marketplace_quotes(request):
    status_filter = request.GET.get('status', 'all')
    
    try:
        # Get quotes without select_related to avoid UUID errors
        quotes = Quote.objects.select_related('trip_request__user').order_by('-created_at')
        
        if status_filter != 'all':
            quotes = quotes.filter(status=status_filter)
        
        context = {
            'quotes': quotes,
            'status_filter': status_filter,
        }
        
        return render(request, 'admin_panel/marketplace_quotes.html', context)
    except Exception as e:
        print(f"Error in marketplace_quotes: {e}")
        # Return empty quotes if there's an error
        context = {
            'quotes': Quote.objects.none(),
            'status_filter': status_filter,
        }
        return render(request, 'admin_panel/marketplace_quotes.html', context)

@login_required
@user_passes_test(is_admin)
def revenue_dashboard(request):
    # Monthly revenue breakdown
    current_month = timezone.now().month
    current_year = timezone.now().year
    
    subscription_revenue = PlatformRevenue.objects.filter(
        revenue_type='subscription',
        created_at__month=current_month,
        created_at__year=current_year
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    commission_revenue = PlatformRevenue.objects.filter(
        revenue_type='commission',
        created_at__month=current_month,
        created_at__year=current_year
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Recent revenue records
    recent_revenues = PlatformRevenue.objects.select_related('subscription__operator', 'booking__trip_request').order_by('-created_at')[:20]
    
    # Operator subscription summary
    active_operators = SpeedboatOperator.objects.filter(subscription_status='active').count()
    expired_operators = SpeedboatOperator.objects.filter(subscription_status='expired').count()
    
    # Projected monthly revenue
    projected_subscription = active_operators * 450  # 450 MVR per operator
    
    context = {
        'subscription_revenue': subscription_revenue,
        'commission_revenue': commission_revenue,
        'total_monthly_revenue': subscription_revenue + commission_revenue,
        'recent_revenues': recent_revenues,
        'active_operators': active_operators,
        'expired_operators': expired_operators,
        'projected_subscription': projected_subscription,
    }
    
    return render(request, 'admin_panel/revenue_dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def platform_settings(request):
    if request.method == 'POST':
        # Handle platform settings updates
        commission_rate = request.POST.get('commission_rate', '5.0')
        subscription_fee = request.POST.get('subscription_fee', '450.0')
        
        # You can store these in a settings model or configuration
        messages.success(request, 'Platform settings updated successfully!')
        return redirect('admin_platform_settings')
    
    context = {
        'commission_rate': 5.0,  # Default values
        'subscription_fee': 450.0,
    }
    
    return render(request, 'admin_panel/platform_settings.html', context)