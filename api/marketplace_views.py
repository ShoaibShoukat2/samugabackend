# Marketplace API Views for Operator Features
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import models
from datetime import timedelta
from .models import (SpeedboatOperator, Speedboat, Quote, TripRequest, 
                    OperatorSubscription, OperatorRating, PlatformRevenue, PlatformSettings)
from .serializers import (SpeedboatOperatorSerializer, SpeedboatSerializer, 
                         QuoteSerializer, OperatorSubscriptionSerializer, OperatorRatingSerializer)

class SpeedboatOperatorViewSet(viewsets.ModelViewSet):
    serializer_class = SpeedboatOperatorSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.user_type == 'operator':
            return SpeedboatOperator.objects.filter(user=self.request.user)
        return SpeedboatOperator.objects.all()
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register as a speedboat operator — first month is FREE automatically"""
        try:
            if not request.user.is_authenticated:
                return Response({'error': 'Authentication required'}, 
                              status=status.HTTP_401_UNAUTHORIZED)
            
            if hasattr(request.user, 'operator_profile'):
                return Response({'error': 'User already registered as operator'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Update user type
            request.user.user_type = 'operator'
            request.user.save()
            
            # Create operator profile
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                operator = serializer.save(user=request.user)

                # Grant FREE first month subscription automatically
                from datetime import date
                from dateutil.relativedelta import relativedelta
                settings = PlatformSettings.get()
                today = date.today()
                free_end = today + timedelta(days=settings.free_trial_days - 1)

                OperatorSubscription.objects.create(
                    operator=operator,
                    plan='basic',
                    amount=0,  # Free trial
                    start_date=today,
                    end_date=free_end,
                    payment_status='paid',
                    paid_at=timezone.now(),
                )

                # Mark operator subscription as active
                operator.subscription_status = 'active'
                operator.subscription_expires_at = timezone.datetime.combine(
                    free_end, timezone.datetime.min.time()
                ).replace(tzinfo=timezone.get_current_timezone())
                operator.save()

                print(f"✅ Free {settings.free_trial_days}-day trial granted to {operator.company_name} until {free_end}")

                return Response({
                    **serializer.data,
                    'free_trial': True,
                    'trial_ends': str(free_end),
                    'message': f'Welcome! Your first {settings.free_trial_days} days are FREE. Subscription required after that.'
                }, status=status.HTTP_201_CREATED)
            else:
                print(f"❌ Operator registration validation errors: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            print(f"❌ Operator registration error: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({'error': 'Internal server error during operator registration'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        """Get operator dashboard data"""
        operator = self.get_object()
        
        # Get statistics
        total_quotes = operator.quotes.count()
        accepted_quotes = operator.quotes.filter(status='accepted').count()
        pending_quotes = operator.quotes.filter(status='pending').count()
        
        # Get recent quotes
        recent_quotes = operator.quotes.select_related('trip_request').order_by('-created_at')[:10]
        
        # Get subscription status
        current_subscription = operator.subscriptions.filter(
            end_date__gte=timezone.now().date()
        ).first()
        
        # Calculate earnings (full amount — no commission deducted)
        total_earnings = sum([
            float(quote.amount)
            for quote in operator.quotes.filter(status='accepted')
        ])
        
        data = {
            'operator': SpeedboatOperatorSerializer(operator).data,
            'statistics': {
                'total_quotes': total_quotes,
                'accepted_quotes': accepted_quotes,
                'pending_quotes': pending_quotes,
                'acceptance_rate': (accepted_quotes / total_quotes * 100) if total_quotes > 0 else 0,
                'total_earnings': total_earnings,
            },
            'recent_quotes': QuoteSerializer(recent_quotes, many=True).data,
            'subscription': OperatorSubscriptionSerializer(current_subscription).data if current_subscription else None,
        }
        
        return Response(data)
    
    @action(detail=True, methods=['get'])
    def trip_requests(self, request, pk=None):
        """Uber-style: ALL pending/quoted trip requests shown to every operator.
        First 30 days are completely FREE — no verification or subscription required.
        After 30 days, subscription must be active."""
        try:
            operator = self.get_object()

            from datetime import date
            settings = PlatformSettings.get()
            days_since_registration = (date.today() - operator.created_at.date()).days

            if days_since_registration > settings.free_trial_days and operator.subscription_status != 'active':
                return Response({
                    'error': 'Subscription not active',
                    'detail': f'Your {settings.free_trial_days}-day free trial has ended. Please activate your subscription.'
                }, status=status.HTTP_403_FORBIDDEN)

            from .serializers import TripRequestSerializer

            # 1. Available: pending/quoted trips (not yet taken by someone else)
            available_requests = TripRequest.objects.filter(
                status__in=['pending', 'quoted']
            ).prefetch_related('quotes__operator').select_related('user').order_by('-created_at')

            # 2. My accepted/confirmed/completed trips
            # Use subquery to correctly find trips where THIS operator's quote is accepted
            # (avoids Django ORM multi-join false positives)
            from django.db.models import Subquery, OuterRef
            accepted_quote_trip_ids = Quote.objects.filter(
                operator=operator,
                status='accepted'
            ).values_list('trip_request_id', flat=True)

            my_accepted_trips = TripRequest.objects.filter(
                id__in=accepted_quote_trip_ids,
                status__in=['accepted', 'payment_pending', 'confirmed', 'completed']
            ).prefetch_related(
                'quotes__operator', 'quotes__boat', 'payment', 'booking'
            ).select_related('user').distinct().order_by('-updated_at')

            print(f"✅ Operator {operator.company_name} — accepted quote trip IDs: {list(accepted_quote_trip_ids)}")
            print(f"✅ my_accepted_trips count: {my_accepted_trips.count()}")

            result = []

            # Add available trips
            for trip in available_requests:
                my_quote = trip.quotes.filter(operator=operator).first()
                accepted_quote = trip.quotes.filter(status='accepted').first()

                trip_data = TripRequestSerializer(trip).data
                trip_data['my_quote'] = None
                trip_data['is_taken'] = False
                trip_data['taken_by'] = None
                trip_data['total_quotes'] = trip.quotes.count()
                trip_data['section'] = 'available'

                if my_quote:
                    trip_data['my_quote'] = {
                        'id': str(my_quote.id),
                        'amount': float(my_quote.amount),
                        'currency': my_quote.currency,
                        'status': my_quote.status,
                    }

                if accepted_quote:
                    trip_data['is_taken'] = True
                    trip_data['taken_by'] = accepted_quote.operator.company_name if accepted_quote.operator else 'Another operator'

                result.append(trip_data)

            # Add my accepted/ongoing trips
            for trip in my_accepted_trips:
                my_quote = trip.quotes.filter(operator=operator, status='accepted').first()
                trip_data = TripRequestSerializer(trip).data
                trip_data['my_quote'] = None
                trip_data['is_taken'] = False
                trip_data['taken_by'] = operator.company_name
                trip_data['total_quotes'] = trip.quotes.count()
                trip_data['section'] = 'my_jobs'

                if my_quote:
                    trip_data['my_quote'] = {
                        'id': str(my_quote.id),
                        'amount': float(my_quote.amount),
                        'currency': my_quote.currency,
                        'status': my_quote.status,
                    }

                # Add payment info
                try:
                    p = trip.payment
                    trip_data['payment_info'] = {
                        'status': p.status,
                        'amount': float(p.amount),
                        'currency': p.currency,
                        'method': p.payment_method,
                        'submitted_at': p.created_at.isoformat() if p.created_at else None,
                        'verified_at': p.verified_at.isoformat() if p.verified_at else None,
                        'proof_url': request.build_absolute_uri(p.payment_proof.url) if p.payment_proof else None,
                        'transaction_id': p.transaction_id or '',
                    }
                except Exception:
                    trip_data['payment_info'] = None

                # Add booking info
                try:
                    b = trip.booking
                    trip_data['booking_info'] = {
                        'booking_code': b.booking_code,
                        'created_at': b.created_at.isoformat() if b.created_at else None,
                    }
                except Exception:
                    trip_data['booking_info'] = None

                result.append(trip_data)

            return Response(result)

        except Exception as e:
            print(f"❌ Error in trip_requests: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({'error': 'Internal server error', 'detail': str(e)},
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def complete_trip(self, request, pk=None):
        """Operator marks a trip as completed after the job is done."""
        try:
            operator = self.get_object()

            trip_id = request.data.get('trip_id')
            if not trip_id:
                return Response({'error': 'trip_id is required'}, status=status.HTTP_400_BAD_REQUEST)

            trip = get_object_or_404(TripRequest, id=trip_id)

            # Verify this operator's quote was accepted for this trip
            my_accepted_quote = trip.quotes.filter(operator=operator, status='accepted').first()
            if not my_accepted_quote:
                return Response({'error': 'You do not have an accepted quote for this trip'}, status=status.HTTP_403_FORBIDDEN)

            if trip.status not in ['confirmed', 'accepted', 'payment_pending']:
                return Response({'error': f'Trip cannot be completed from status: {trip.status}'}, status=status.HTTP_400_BAD_REQUEST)

            trip.status = 'completed'
            trip.save()

            # Record subscription revenue (no commission in subscription model)
            from .models import PlatformRevenue
            # Revenue is tracked via subscription payments, not per-trip commission

            # Notify customer
            from .models import Notification
            Notification.objects.create(
                user=trip.user,
                title='Trip Completed',
                message=f'Your {trip.trip_type} trip with {operator.company_name} has been marked as completed.',
                trip_request=trip,
            )

            print(f"✅ Trip {trip.id} marked completed by {operator.company_name}")
            return Response({'message': 'Trip marked as completed successfully', 'status': 'completed'})

        except Exception as e:
            print(f"❌ Error in complete_trip: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def verify_payment(self, request, pk=None):
        """Operator verifies customer payment for their accepted trip."""
        try:
            operator = self.get_object()

            trip_id = request.data.get('trip_id')
            if not trip_id:
                return Response({'error': 'trip_id is required'}, status=status.HTTP_400_BAD_REQUEST)

            trip = get_object_or_404(TripRequest, id=trip_id)

            # Ensure this operator has an accepted quote for this trip
            my_accepted_quote = trip.quotes.filter(operator=operator, status='accepted').first()
            if not my_accepted_quote:
                return Response({'error': 'You do not have an accepted quote for this trip'}, status=status.HTTP_403_FORBIDDEN)

            if trip.status != 'payment_pending':
                return Response({'error': f'No pending payment to verify (trip status: {trip.status})'}, status=status.HTTP_400_BAD_REQUEST)

            # Verify payment
            try:
                payment = trip.payment
            except Exception:
                return Response({'error': 'No payment record found for this trip'}, status=status.HTTP_404_NOT_FOUND)

            payment.status = 'verified'
            payment.verified_at = timezone.now()
            payment.save()

            # Confirm trip
            trip.status = 'confirmed'
            trip.save()

            # Generate booking code + QR if not already created
            import qrcode
            from io import BytesIO
            from django.core.files import File
            import random

            def generate_booking_code():
                return f"ST{random.randint(100000, 999999)}"

            from .models import Booking
            booking, created = Booking.objects.get_or_create(
                trip_request=trip,
                defaults={'booking_code': generate_booking_code()}
            )
            if created:
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(booking.booking_code)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                buffer.seek(0)
                booking.qr_code.save(f'{booking.booking_code}.png', File(buffer), save=True)

            # Notify customer
            from .models import Notification
            Notification.objects.create(
                user=trip.user,
                title='Payment Verified — Booking Confirmed',
                message=f'Your payment has been verified by {operator.company_name}. Booking code: {booking.booking_code}',
                trip_request=trip,
            )

            print(f"✅ Payment verified by operator {operator.company_name} for trip {trip.id}")
            return Response({
                'message': 'Payment verified and booking confirmed',
                'booking_code': booking.booking_code,
                'status': 'confirmed',
            })

        except Exception as e:
            print(f"❌ Error in verify_payment: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SpeedboatViewSet(viewsets.ModelViewSet):
    serializer_class = SpeedboatSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Operators see their own boats
        if hasattr(self.request.user, 'operator_profile'):
            return Speedboat.objects.filter(operator=self.request.user.operator_profile)
        # Customers see all active boats from verified operators
        if self.request.user.user_type == 'customer':
            return Speedboat.objects.filter(
                is_active=True,
                operator__verification_status='verified'
            ).select_related('operator')
        return Speedboat.objects.none()
    
    def perform_create(self, serializer):
        if not hasattr(self.request.user, 'operator_profile'):
            raise ValueError("User must be a registered operator")
        serializer.save(operator=self.request.user.operator_profile)

    @action(detail=False, methods=['get'], url_path='public')
    def public_list(self, request):
        """Public boat listing for customers - all active boats from verified operators"""
        boats = Speedboat.objects.filter(
            is_active=True,
            operator__verification_status='verified'
        ).select_related('operator')

        # Optional filters
        boat_type = request.query_params.get('boat_type')
        if boat_type:
            boats = boats.filter(boat_type=boat_type)

        min_capacity = request.query_params.get('min_capacity')
        if min_capacity:
            boats = boats.filter(capacity__gte=int(min_capacity))

        serializer = self.get_serializer(boats, many=True, context={'request': request})
        return Response(serializer.data)

class MarketplaceQuoteViewSet(viewsets.ModelViewSet):
    serializer_class = QuoteSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if hasattr(self.request.user, 'operator_profile'):
            return Quote.objects.filter(
                operator=self.request.user.operator_profile
            ).select_related('trip_request__user', 'operator', 'boat').order_by('-created_at')
        elif self.request.user.user_type == 'customer':
            return Quote.objects.filter(
                trip_request__user=self.request.user
            ).select_related('trip_request__user', 'operator', 'boat').order_by('-created_at')
        return Quote.objects.none()
    
    @action(detail=False, methods=['post'])
    def submit_quote(self, request):
        """Submit a quote for a trip request"""
        if not hasattr(request.user, 'operator_profile'):
            return Response({'error': 'User must be a registered operator'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        operator = request.user.operator_profile
        
        # Allow if within free trial period OR subscription active
        from datetime import date
        settings = PlatformSettings.get()
        days_since = (date.today() - operator.created_at.date()).days
        if days_since > settings.free_trial_days and operator.subscription_status != 'active':
            return Response({'error': f'Free trial ended. Please subscribe to submit quotes.'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        trip_request_id = request.data.get('trip_request_id')
        trip_request = get_object_or_404(TripRequest, id=trip_request_id)
        
        # Allow quoting on pending OR quoted trips (Uber style - multiple operators can quote)
        if trip_request.status not in ['pending', 'quoted']:
            return Response({'error': 'Trip request no longer available'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Block if trip is already taken (another operator's quote accepted)
        if trip_request.quotes.filter(status='accepted').exists():
            return Response({'error': 'This trip has already been taken by another operator'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Check if operator already quoted
        if Quote.objects.filter(trip_request=trip_request, operator=operator).exists():
            return Response({'error': 'Quote already submitted for this trip'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Create quote directly — bypass serializer to guarantee operator FK is set
        try:
            amount = request.data.get('amount')
            currency = request.data.get('currency', 'USD')
            pickup_time = request.data.get('pickup_time', '09:00:00')
            notes = request.data.get('notes', '')
            boat_id = request.data.get('boat')

            boat = None
            if boat_id:
                from .models import Speedboat
                boat = Speedboat.objects.filter(id=boat_id, operator=operator).first()

            from decimal import Decimal
            amount_decimal = Decimal(str(amount))

            quote = Quote.objects.create(
                trip_request=trip_request,
                operator=operator,
                boat=boat,
                amount=amount_decimal,
                currency=currency,
                pickup_time=pickup_time,
                notes=notes,
                status='pending',
                valid_until=timezone.now() + timedelta(days=7),
                commission_rate=Decimal('0.00'),
                commission_amount=Decimal('0.00'),
                bank_name=request.data.get('bank_name', ''),
                account_number=request.data.get('account_number', ''),
                account_name=request.data.get('account_name', ''),
            )
        except Exception as e:
            return Response({'error': f'Failed to create quote: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        # Update trip request status
        trip_request.status = 'quoted'
        trip_request.save()

        # Notify customer
        from .models import Notification
        Notification.objects.create(
            user=trip_request.user,
            title='New Quote Received',
            message=f'You received a quote from {operator.company_name} for your {trip_request.trip_type} trip',
            trip_request=trip_request
        )

        return Response({
            'id': str(quote.id),
            'trip_request': str(quote.trip_request_id),
            'operator': str(quote.operator_id),
            'amount': str(quote.amount),
            'currency': quote.currency,
            'status': quote.status,
            'message': 'Quote submitted successfully',
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def accept_quote(self, request, pk=None):
        """Customer accepts a quote"""
        quote = self.get_object()

        if quote.trip_request.user != request.user:
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        if quote.status != 'pending':
            return Response({'error': 'Quote no longer available'},
                          status=status.HTTP_400_BAD_REQUEST)

        if quote.valid_until and quote.valid_until < timezone.now():
            quote.status = 'expired'
            quote.save()
            return Response({'error': 'Quote has expired'},
                          status=status.HTTP_400_BAD_REQUEST)

        trip = quote.trip_request

        # Accept this quote, reject all others for this trip
        Quote.objects.filter(trip_request=trip).exclude(id=quote.id).update(status='rejected')
        quote.status = 'accepted'
        quote.save()

        # Update trip status
        trip.status = 'accepted'
        trip.save()

        # Notify operator
        try:
            from .models import Notification
            if quote.operator and quote.operator.user:
                Notification.objects.create(
                    user=quote.operator.user,
                    title='Quote Accepted',
                    message=f'Your quote for {trip.trip_type} trip has been accepted!',
                    trip_request=trip,
                )
        except Exception as e:
            print(f"⚠️ Notification failed: {e}")

        print(f"✅ Quote {quote.id} accepted — operator: {quote.operator_id}, trip: {trip.id}")
        return Response({'message': 'Quote accepted successfully'})

    @action(detail=False, methods=['post'])
    def direct_book(self, request):
        """Customer directly books a specific boat — creates trip request + pending quote in one step"""
        if request.user.user_type != 'customer':
            return Response({'error': 'Only customers can book boats'}, status=status.HTTP_403_FORBIDDEN)

        boat_id = request.data.get('boat_id')
        if not boat_id:
            return Response({'error': 'boat_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        boat = get_object_or_404(Speedboat, id=boat_id, is_active=True)
        operator = boat.operator

        if operator.verification_status != 'verified':
            return Response({'error': 'This boat operator is not verified'}, status=status.HTTP_400_BAD_REQUEST)

        # Create the trip request
        trip_data = {
            'trip_type': request.data.get('trip_type', 'transfer'),
            'pickup_location': request.data.get('pickup_location', ''),
            'destination': request.data.get('destination', ''),
            'trip_date': request.data.get('trip_date'),
            'trip_time': request.data.get('trip_time', '09:00:00'),
            'passenger_count': request.data.get('passenger_count', 1),
            'special_notes': request.data.get('special_notes', ''),
            'preferred_currency': request.data.get('currency', 'USD'),
        }

        from .serializers import TripRequestSerializer as TRS
        trip_serializer = TRS(data=trip_data)
        if not trip_serializer.is_valid():
            return Response(trip_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        trip = trip_serializer.save(user=request.user, status='pending')

        # Create a quote from the operator for this boat
        quoted_amount = request.data.get('quoted_amount')
        quote = Quote.objects.create(
            trip_request=trip,
            operator=operator,
            boat=boat,
            amount=quoted_amount if quoted_amount else 0,
            currency=request.data.get('currency', 'USD'),
            pickup_time=request.data.get('trip_time', '09:00:00'),
            notes=f'Direct booking for {boat.name}',
            status='pending',
            valid_until=timezone.now() + timedelta(days=7),
        )

        trip.status = 'quoted'
        trip.save()

        # Notify operator
        from .models import Notification
        Notification.objects.create(
            user=operator.user,
            title='New Direct Booking',
            message=f'{request.user.first_name} {request.user.last_name} wants to book {boat.name} for a {trip.trip_type} trip on {trip.trip_date}',
            trip_request=trip,
        )

        return Response({
            'trip_request_id': str(trip.id),
            'quote_id': str(quote.id),
            'boat': boat.name,
            'operator': operator.company_name,
            'message': 'Booking request sent to operator. They will confirm shortly.',
        }, status=status.HTTP_201_CREATED)

class OperatorSubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = OperatorSubscriptionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if hasattr(self.request.user, 'operator_profile'):
            return OperatorSubscription.objects.filter(operator=self.request.user.operator_profile)
        return OperatorSubscription.objects.none()
    
    @action(detail=False, methods=['post'])
    def create_subscription(self, request):
        """Create a new subscription payment"""
        if not hasattr(request.user, 'operator_profile'):
            return Response({'error': 'User must be a registered operator'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        operator = request.user.operator_profile
        
        # Create subscription for next month
        from datetime import date
        from dateutil.relativedelta import relativedelta
        
        start_date = date.today().replace(day=1)  # First day of current month
        end_date = start_date + relativedelta(months=1) - timedelta(days=1)  # Last day of current month
        
        # Check if subscription already exists for this period
        existing = OperatorSubscription.objects.filter(
            operator=operator,
            start_date=start_date,
            end_date=end_date
        ).first()
        
        if existing:
            return Response({'error': 'Subscription already exists for this period'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        subscription = OperatorSubscription.objects.create(
            operator=operator,
            start_date=start_date,
            end_date=end_date,
            amount=PlatformSettings.get().subscription_price,
            payment_status='pending'
        )
        
        return Response(OperatorSubscriptionSerializer(subscription).data, 
                       status=status.HTTP_201_CREATED)


class OperatorRatingViewSet(viewsets.ModelViewSet):
    serializer_class = OperatorRatingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return OperatorRating.objects.select_related('customer', 'operator', 'booking').order_by('-created_at')

    @action(detail=False, methods=['post'])
    def submit_rating(self, request):
        """Customer submits a rating + review for an operator after a completed trip."""
        if request.user.user_type != 'customer':
            return Response({'error': 'Only customers can submit ratings'}, status=status.HTTP_403_FORBIDDEN)

        trip_id = request.data.get('trip_id')
        rating_value = request.data.get('rating')
        review = request.data.get('review', '')

        if not trip_id or not rating_value:
            return Response({'error': 'trip_id and rating are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rating_value = int(rating_value)
            if not (1 <= rating_value <= 5):
                raise ValueError
        except (ValueError, TypeError):
            return Response({'error': 'Rating must be between 1 and 5'}, status=status.HTTP_400_BAD_REQUEST)

        trip = get_object_or_404(TripRequest, id=trip_id, user=request.user)

        if trip.status != 'completed':
            return Response({'error': 'You can only rate completed trips'}, status=status.HTTP_400_BAD_REQUEST)

        # Get the booking
        try:
            booking = trip.booking
        except Exception:
            return Response({'error': 'No booking found for this trip'}, status=status.HTTP_404_NOT_FOUND)

        # Check already rated
        if OperatorRating.objects.filter(booking=booking).exists():
            return Response({'error': 'You have already rated this trip'}, status=status.HTTP_400_BAD_REQUEST)

        # Get the accepted quote to find the operator
        accepted_quote = trip.quotes.filter(status='accepted').first()
        if not accepted_quote or not accepted_quote.operator:
            return Response({'error': 'No operator found for this trip'}, status=status.HTTP_400_BAD_REQUEST)

        operator = accepted_quote.operator

        # Create rating
        rating = OperatorRating.objects.create(
            booking=booking,
            customer=request.user,
            operator=operator,
            rating=rating_value,
            review=review,
        )

        # Update operator average rating
        all_ratings = OperatorRating.objects.filter(operator=operator)
        total = all_ratings.count()
        avg = all_ratings.aggregate(models.Avg('rating'))['rating__avg'] or 0
        operator.average_rating = round(avg, 2)
        operator.total_ratings = total
        operator.save()

        # Notify operator
        from .models import Notification
        Notification.objects.create(
            user=operator.user,
            title='New Rating Received',
            message=f'{request.user.first_name} gave you {rating_value} star{"s" if rating_value > 1 else ""}{"." if not review else f": {review[:80]}"}',
            trip_request=trip,
        )

        return Response({
            'message': 'Rating submitted successfully',
            'rating': rating_value,
            'operator': operator.company_name,
            'average_rating': float(operator.average_rating),
        }, status=status.HTTP_201_CREATED)
