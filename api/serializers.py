from rest_framework import serializers
from .models import User, TripRequest, Quote, Payment, Booking, SupportMessage, Notification
from django.contrib.auth import authenticate
import random

class UserSerializer(serializers.ModelSerializer):
    profile_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number', 'first_name', 'last_name', 'is_admin', 'profile_image', 'profile_image_url']
        read_only_fields = ['id', 'is_admin', 'profile_image_url']
    
    def get_profile_image_url(self, obj):
        if obj.profile_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_image.url)
        return None

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = User
        fields = ['email', 'phone_number', 'password', 'first_name', 'last_name']
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        email = validated_data.get('email')
        phone_number = validated_data.get('phone_number')
        
        # Set username to email or phone_number
        if email:
            validated_data['username'] = email
        elif phone_number:
            validated_data['username'] = phone_number
        else:
            # Generate random username if neither provided
            validated_data['username'] = f"user_{random.randint(100000, 999999)}"
        
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False)
    password = serializers.CharField(required=False, write_only=True)
    
    def validate(self, data):
        email = data.get('email')
        phone_number = data.get('phone_number')
        password = data.get('password')
        
        if not email and not phone_number:
            raise serializers.ValidationError("Email or phone number is required")
        
        return data

class OTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    
class OTPVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    otp = serializers.CharField()

class QuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quote
        fields = '__all__'
        read_only_fields = ['created_at']

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'verified_at', 'status']

class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = ['id', 'booking_code', 'created_at']

class TripRequestSerializer(serializers.ModelSerializer):
    quote = QuoteSerializer(read_only=True)
    payment = PaymentSerializer(read_only=True)
    booking = BookingSerializer(read_only=True)
    user_details = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = TripRequest
        fields = '__all__'
        read_only_fields = ['id', 'user', 'status', 'created_at', 'updated_at']

class SupportMessageSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = SupportMessage
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at']

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['id', 'created_at']
