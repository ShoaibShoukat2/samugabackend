# Marketplace API Views for Operator Features
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
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
        """Register as a speedboat operator"""
        if hasattr(request.user, 'operator_profile'):
            return Response({'error': 'User already registered as operator'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Update user type
        request.user.user_type = 'operator'
        request.user.save()
        
        # Create operator profile
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
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
        """Get available trip requests for operator"""
        operator = self.get_object()
        
        if operator.verification_status != 'verified' or operator.subscription_status != 'active':
            return Response({'error': 'Operator not verified or subscription expired'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        # Get trip requests that match operator's service areas
        service_islands = [island.strip().lower() for island in operator.service_islands.split(',')]
        
        available_requests = TripRequest.objects.filter(
            status='pending'
        ).exclude(
            quotes__operator=operator  # Exclude requests operator already quoted
        )
        
        # Filter by service areas (basic matching)
        filtered_requests = []
        for request in available_requests:
            pickup_lower = request.pickup_location.lower()
            destination_lower = request.destination.lower()
            
            # Check if operator serves this route
            serves_pickup = any(island in pickup_lower for island in service_islands)
            serves_destination = any(island in destination_lower for island in service_islands)
            
            if serves_pickup or serves_destination:
                filtered_requests.append(request)
        
        from .serializers import TripRequestSerializer
        return Response(TripRequestSerializer(filtered_requests, many=True).data)

class SpeedboatViewSet(viewsets.ModelViewSet):
    serializer_class = SpeedboatSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if hasattr(self.request.user, 'operator_profile'):
            return Speedboat.objects.filter(operator=self.request.user.operator_profile)
        return Speedboat.objects.none()
    
    def perform_create(self, serializer):
        if not hasattr(self.request.user, 'operator_profile'):
            raise ValueError("User must be a registered operator")
        serializer.save(operator=self.request.user.operator_profile)

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
        
        if trip_request.status != 'pending':
            return Response({'error': 'Trip request no longer available'}, 
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