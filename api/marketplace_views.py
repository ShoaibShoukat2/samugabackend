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
                    OperatorSubscription, OperatorRating, PlatformRevenue)
from .serializers import (SpeedboatOperatorSerializer, SpeedboatSerializer, 
                         QuoteSerializer, OperatorSubscriptionSerializer)

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
                today = date.today()
                free_end = today + relativedelta(months=1) - timezone.timedelta(days=1)

                OperatorSubscription.objects.create(
                    operator=operator,
                    plan='basic',
                    amount=0,  # Free
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

                print(f"✅ Free 1-month subscription granted to {operator.company_name} until {free_end}")

                return Response({
                    **serializer.data,
                    'free_trial': True,
                    'trial_ends': str(free_end),
                    'message': 'Welcome! Your first month is FREE. Subscription starts from month 2.'
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
        
        # Calculate earnings (commission-based)
        total_earnings = sum([
            quote.amount - (quote.commission_amount or 0) 
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
        """Get trip requests matching operator's boat capacity — Uber style"""
        try:
            operator = self.get_object()

            if operator.verification_status != 'verified':
                return Response({
                    'error': 'Operator not verified',
                    'detail': f'Your account status is: {operator.verification_status}. Please wait for admin approval.'
                }, status=status.HTTP_403_FORBIDDEN)

            if operator.subscription_status != 'active':
                return Response({
                    'error': 'Subscription not active',
                    'detail': f'Your subscription status is: {operator.subscription_status}. Please activate your subscription.'
                }, status=status.HTTP_403_FORBIDDEN)

            service_islands = [island.strip().lower() for island in operator.service_islands.split(',')]

            # Get max capacity across all operator's active boats
            max_capacity = operator.boats.filter(is_active=True).aggregate(
                max_cap=models.Max('capacity')
            )['max_cap'] or 0

            # Show pending AND quoted requests (Uber style)
            # Filter: only show requests where passenger_count <= operator's max boat capacity
            available_requests = TripRequest.objects.filter(
                status__in=['pending', 'quoted'],
                passenger_count__lte=max_capacity if max_capacity > 0 else 9999,
            ).prefetch_related('quotes__operator').order_by('-created_at')

            result = []
            for trip in available_requests:
                pickup_lower = trip.pickup_location.lower()
                dest_lower = trip.destination.lower()

                serves = any(island in pickup_lower or island in dest_lower for island in service_islands)
                if not serves:
                    continue

                # Check if THIS operator already quoted
                my_quote = trip.quotes.filter(operator=operator).first()
                # Check if trip is already taken (another operator's quote accepted)
                accepted_quote = trip.quotes.filter(status='accepted').first()

                from .serializers import TripRequestSerializer
                trip_data = TripRequestSerializer(trip).data
                trip_data['my_quote'] = None
                trip_data['is_taken'] = False
                trip_data['taken_by'] = None
                trip_data['total_quotes'] = trip.quotes.count()

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

            return Response(result)

        except Exception as e:
            print(f"❌ Error in trip_requests: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({'error': 'Internal server error', 'detail': str(e)},
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            return Quote.objects.filter(operator=self.request.user.operator_profile)
        elif self.request.user.user_type == 'customer':
            return Quote.objects.filter(trip_request__user=self.request.user)
        return Quote.objects.none()
    
    @action(detail=False, methods=['post'])
    def submit_quote(self, request):
        """Submit a quote for a trip request"""
        if not hasattr(request.user, 'operator_profile'):
            return Response({'error': 'User must be a registered operator'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        operator = request.user.operator_profile
        
        if operator.verification_status != 'verified':
            return Response({'error': 'Operator not verified'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        if operator.subscription_status != 'active':
            return Response({'error': 'Subscription expired'}, 
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
        
        # Create quote
        quote_data = request.data.copy()
        quote_data['trip_request'] = trip_request.id
        quote_data['operator'] = operator.id
        quote_data['valid_until'] = timezone.now() + timedelta(days=7)  # Valid for 7 days
        
        serializer = self.get_serializer(data=quote_data)
        if serializer.is_valid():
            quote = serializer.save()
            
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
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def accept_quote(self, request, pk=None):
        """Customer accepts a quote"""
        quote = self.get_object()
        
        if quote.trip_request.user != request.user:
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        
        if quote.status != 'pending':
            return Response({'error': 'Quote no longer available'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if quote.valid_until < timezone.now():
            quote.status = 'expired'
            quote.save()
            return Response({'error': 'Quote has expired'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Accept this quote and reject others
        Quote.objects.filter(trip_request=quote.trip_request).exclude(id=quote.id).update(status='rejected')
        quote.status = 'accepted'
        quote.save()
        
        # Update trip request
        quote.trip_request.status = 'accepted'
        quote.trip_request.save()
        
        # Notify operator
        from .models import Notification
        Notification.objects.create(
            user=quote.operator.user,
            title='Quote Accepted',
            message=f'Your quote for {quote.trip_request.trip_type} trip has been accepted!',
            trip_request=quote.trip_request
        )
        
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
            amount=450.00,  # MVR
            payment_status='pending'
        )
        
        return Response(OperatorSubscriptionSerializer(subscription).data, 
                       status=status.HTTP_201_CREATED)