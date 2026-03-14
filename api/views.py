from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from datetime import timedelta
import random
import qrcode
from io import BytesIO
from django.core.files import File
from .models import User, TripRequest, Quote, Payment, Booking, SupportMessage, Notification
from .serializers import (
    UserSerializer, RegisterSerializer, LoginSerializer, OTPSerializer, OTPVerifySerializer,
    TripRequestSerializer, QuoteSerializer, PaymentSerializer, BookingSerializer,
    SupportMessageSerializer, NotificationSerializer
)

def generate_otp():
    return str(random.randint(100000, 999999))

def generate_booking_code():
    return f"ST{random.randint(100000, 999999)}"

class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        try:
            print(f"📥 Registration request data: {request.data}")

            serializer = RegisterSerializer(data=request.data)
            if serializer.is_valid():
                print("✅ Serializer validation passed")
                user = serializer.save()
                print(f"✅ User created: {user.email}, type: {user.user_type}")

                refresh = RefreshToken.for_user(user)
                return Response({
                    'user': UserSerializer(user).data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }, status=status.HTTP_201_CREATED)
            else:
                print(f"❌ Serializer validation failed: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print(f"❌ Registration error: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                'error': 'Internal server error during registration',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
    @action(detail=False, methods=['post'])
    def login(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data.get('email')
            phone_number = serializer.validated_data.get('phone_number')
            password = serializer.validated_data.get('password')
            
            user = None
            if email and password:
                user = authenticate(username=email, password=password)
                if not user:
                    try:
                        user_obj = User.objects.get(email=email)
                        if user_obj.check_password(password):
                            user = user_obj
                    except User.DoesNotExist:
                        pass
            elif phone_number:
                try:
                    user = User.objects.get(phone_number=phone_number)
                except User.DoesNotExist:
                    pass
            
            if user:
                refresh = RefreshToken.for_user(user)
                return Response({
                    'user': UserSerializer(user).data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                })
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def send_otp(self, request):
        serializer = OTPSerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data['phone_number']
            otp = generate_otp()
            
            user, created = User.objects.get_or_create(
                phone_number=phone_number,
                defaults={'username': phone_number}
            )
            user.otp = otp
            user.otp_created_at = timezone.now()
            user.save()
            
            # In production, send OTP via SMS (Twilio)
            # For now, return OTP in response (development only)
            return Response({
                'message': 'OTP sent successfully',
                'otp': otp  # Remove in production
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def verify_otp(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data['phone_number']
            otp = serializer.validated_data['otp']
            
            try:
                user = User.objects.get(phone_number=phone_number)
                if user.otp == otp:
                    # Check if OTP is still valid (10 minutes)
                    if user.otp_created_at and timezone.now() - user.otp_created_at < timedelta(minutes=10):
                        user.otp = None
                        user.otp_created_at = None
                        user.save()
                        
                        refresh = RefreshToken.for_user(user)
                        return Response({
                            'user': UserSerializer(user).data,
                            'tokens': {
                                'refresh': str(refresh),
                                'access': str(refresh.access_token),
                            }
                        })
                    return Response({'error': 'OTP expired'}, status=status.HTTP_400_BAD_REQUEST)
                return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post', 'put'], permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        user = request.user
        serializer = UserSerializer(user, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Profile updated successfully',
                'user': serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TripRequestViewSet(viewsets.ModelViewSet):
    serializer_class = TripRequestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_admin:
            return TripRequest.objects.all().order_by('-created_at')
        return TripRequest.objects.filter(user=self.request.user).order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        
        # Create notification for admin
        admin_users = User.objects.filter(is_admin=True)
        for admin in admin_users:
            Notification.objects.create(
                user=admin,
                title='New Trip Request',
                message=f'New {serializer.instance.trip_type} request from {self.request.user.email}',
                trip_request=serializer.instance
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def send_quote(self, request, pk=None):
        if not request.user.is_admin:
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
        
        trip_request = self.get_object()
        serializer = QuoteSerializer(data=request.data)
        
        if serializer.is_valid():
            quote = serializer.save(trip_request=trip_request)
            trip_request.status = 'quoted'
            trip_request.save()
            
            # Create notification for user
            Notification.objects.create(
                user=trip_request.user,
                title='Quote Received',
                message=f'You have received a quote for your {trip_request.trip_type} trip',
                trip_request=trip_request
            )
            
            return Response(QuoteSerializer(quote).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def accept_quote(self, request, pk=None):
        trip_request = self.get_object()
        if trip_request.user != request.user:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        
        if not hasattr(trip_request, 'quote'):
            return Response({'error': 'No quote available'}, status=status.HTTP_400_BAD_REQUEST)
        
        trip_request.status = 'accepted'
        trip_request.save()
        
        return Response({'message': 'Quote accepted. Please proceed with payment.'})
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        trips = TripRequest.objects.filter(
            user=request.user,
            trip_date__gte=timezone.now().date(),
            status__in=['pending', 'quoted', 'accepted', 'payment_pending', 'confirmed']
        ).order_by('trip_date')
        serializer = self.get_serializer(trips, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def past(self, request):
        trips = TripRequest.objects.filter(
            user=request.user,
            trip_date__lt=timezone.now().date()
        ).order_by('-trip_date')
        serializer = self.get_serializer(trips, many=True)
        return Response(serializer.data)

class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_admin:
            return Payment.objects.all()
        return Payment.objects.filter(trip_request__user=self.request.user)
    
    def create(self, request):
        trip_request_id = request.data.get('trip_request')
        try:
            trip_request = TripRequest.objects.get(id=trip_request_id, user=request.user)
        except TripRequest.DoesNotExist:
            return Response({'error': 'Trip request not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if not hasattr(trip_request, 'quote'):
            return Response({'error': 'No quote available'}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            payment = serializer.save(amount=trip_request.quote.amount)
            trip_request.status = 'payment_pending'
            trip_request.save()
            
            # Notify admin
            admin_users = User.objects.filter(is_admin=True)
            for admin in admin_users:
                Notification.objects.create(
                    user=admin,
                    title='Payment Submitted',
                    message=f'Payment proof submitted for booking {trip_request.id}',
                    trip_request=trip_request
                )
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def verify(self, request, pk=None):
        if not request.user.is_admin:
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
        
        payment = self.get_object()
        payment.status = 'verified'
        payment.verified_at = timezone.now()
        payment.save()
        
        trip_request = payment.trip_request
        trip_request.status = 'confirmed'
        trip_request.save()
        
        # Generate booking
        booking_code = generate_booking_code()
        booking = Booking.objects.create(
            trip_request=trip_request,
            booking_code=booking_code
        )
        
        # Generate QR code
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
            user=trip_request.user,
            title='Booking Confirmed',
            message=f'Your booking is confirmed! Booking code: {booking_code}',
            trip_request=trip_request
        )
        
        return Response({'message': 'Payment verified and booking confirmed'})

class BookingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_admin:
            return Booking.objects.all()
        return Booking.objects.filter(trip_request__user=self.request.user)

class SupportMessageViewSet(viewsets.ModelViewSet):
    serializer_class = SupportMessageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_admin:
            # Admin sees all messages grouped by user
            return SupportMessage.objects.all().order_by('user', 'created_at')
        return SupportMessage.objects.filter(user=self.request.user).order_by('created_at')
    
    def perform_create(self, serializer):
        is_admin_reply = self.request.user.is_admin
        serializer.save(user=self.request.user, is_admin_reply=is_admin_reply)
    
    @action(detail=False, methods=['get'])
    def conversations(self, request):
        if not request.user.is_admin:
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get unique users with messages
        users_with_messages = User.objects.filter(support_messages__isnull=False).distinct()
        conversations = []
        
        for user in users_with_messages:
            last_message = SupportMessage.objects.filter(user=user).order_by('-created_at').first()
            unread_count = SupportMessage.objects.filter(user=user, read=False, is_admin_reply=False).count()
            
            conversations.append({
                'user': UserSerializer(user).data,
                'last_message': SupportMessageSerializer(last_message).data,
                'unread_count': unread_count
            })
        
        return Response(conversations)

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.read = True
        notification.save()
        return Response({'message': 'Notification marked as read'})
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        Notification.objects.filter(user=request.user, read=False).update(read=True)
        return Response({'message': 'All notifications marked as read'})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    if not request.user.is_admin:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    total_requests = TripRequest.objects.count()
    pending_requests = TripRequest.objects.filter(status='pending').count()
    confirmed_bookings = TripRequest.objects.filter(status='confirmed').count()
    pending_payments = Payment.objects.filter(status='pending').count()
    
    return Response({
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'confirmed_bookings': confirmed_bookings,
        'pending_payments': pending_payments
    })
