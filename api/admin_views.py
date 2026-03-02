from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import User, TripRequest, Quote, Payment, Booking, SupportMessage, Notification
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
        'recent_trips': recent_trips,
        'pending_payment_list': pending_payment_list,
        'recent_messages': recent_messages,
    }
    
    return render(request, 'admin_panel/dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def trip_requests_list(request):
    status_filter = request.GET.get('status', 'all')
    
    trips = TripRequest.objects.select_related('user').order_by('-created_at')
    
    if status_filter != 'all':
        trips = trips.filter(status=status_filter)
    
    context = {
        'trips': trips,
        'status_filter': status_filter,
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
            
            booking = Booking.objects.create(
                trip_request=trip,
                booking_code=booking_code
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
            
            # Notify user
            Notification.objects.create(
                user=trip.user,
                title='Booking Confirmed',
                message=f'Your booking is confirmed! Booking code: {booking_code}',
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
