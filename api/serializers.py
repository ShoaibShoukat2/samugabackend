from rest_framework import serializers
from .models import User, TripRequest, Quote, Payment, Booking, SupportMessage, Notification
from django.contrib.auth import authenticate
import random

class UserSerializer(serializers.ModelSerializer):
    profile_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number', 'first_name', 'last_name', 'user_type', 'is_admin', 'profile_image', 'profile_image_url']
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
        fields = ['email', 'phone_number', 'password', 'first_name', 'last_name', 'user_type']
    
    def validate_email(self, value):
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value
    
    def validate_phone_number(self, value):
        if value and User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("An account with this phone number already exists.")
        return value
    
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
            validated_data['username'] = f"user_{random.randint(100000, 999999)}"
        
        # Check username uniqueness too
        if User.objects.filter(username=validated_data['username']).exists():
            raise serializers.ValidationError({"email": "An account with this email already exists."})
        
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
    operator_details = serializers.SerializerMethodField()
    boat_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Quote
        fields = '__all__'
        read_only_fields = ['created_at', 'commission_amount']
    
    def get_operator_details(self, obj):
        if obj.operator:
            # Import here to avoid circular imports
            return {
                'id': str(obj.operator.id),
                'company_name': obj.operator.company_name,
                'phone_number': obj.operator.phone_number,
                'average_rating': float(obj.operator.average_rating),
                'total_ratings': obj.operator.total_ratings,
            }
        return None
    
    def get_boat_details(self, obj):
        if obj.boat:
            return {
                'id': str(obj.boat.id),
                'name': obj.boat.name,
                'boat_type': obj.boat.boat_type,
                'capacity': obj.boat.capacity,
                'has_toilet': obj.boat.has_toilet,
                'has_shade': obj.boat.has_shade,
                'has_snorkel_gear': obj.boat.has_snorkel_gear,
                'has_fishing_gear': obj.boat.has_fishing_gear,
                'has_life_jackets': obj.boat.has_life_jackets,
            }
        return None

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
    quote = QuoteSerializer(read_only=True)  # Legacy single quote
    quotes = QuoteSerializer(many=True, read_only=True)  # Multiple quotes for marketplace
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
# Marketplace Serializers
from .models import SpeedboatOperator, Speedboat, OperatorSubscription, OperatorRating

class SpeedboatOperatorSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    boats_count = serializers.SerializerMethodField()
    license_document_url = serializers.SerializerMethodField()
    boat_registration_url = serializers.SerializerMethodField()
    insurance_document_url = serializers.SerializerMethodField()
    
    class Meta:
        model = SpeedboatOperator
        fields = '__all__'
        read_only_fields = ['id', 'user', 'verification_status', 'subscription_status', 
                           'subscription_expires_at', 'average_rating', 'total_ratings', 
                           'created_at', 'updated_at']
    
    def get_boats_count(self, obj):
        return obj.boats.count()
    
    def get_license_document_url(self, obj):
        if obj.license_document:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.license_document.url)
        return None
    
    def get_boat_registration_url(self, obj):
        if obj.boat_registration:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.boat_registration.url)
        return None
    
    def get_insurance_document_url(self, obj):
        if obj.insurance_document:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.insurance_document.url)
        return None

class SpeedboatSerializer(serializers.ModelSerializer):
    operator_details = SpeedboatOperatorSerializer(source='operator', read_only=True)
    main_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Speedboat
        fields = '__all__'
        read_only_fields = ['id', 'operator', 'created_at']
    
    def get_main_image_url(self, obj):
        if obj.main_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.main_image.url)
        return None

class OperatorSubscriptionSerializer(serializers.ModelSerializer):
    operator_details = SpeedboatOperatorSerializer(source='operator', read_only=True)
    payment_proof_url = serializers.SerializerMethodField()
    
    class Meta:
        model = OperatorSubscription
        fields = '__all__'
        read_only_fields = ['id', 'operator', 'created_at', 'paid_at']
    
    def get_payment_proof_url(self, obj):
        if obj.payment_proof:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.payment_proof.url)
        return None

class OperatorRatingSerializer(serializers.ModelSerializer):
    customer_details = UserSerializer(source='customer', read_only=True)
    operator_details = SpeedboatOperatorSerializer(source='operator', read_only=True)
    booking_details = BookingSerializer(source='booking', read_only=True)
    
    class Meta:
        model = OperatorRating
        fields = '__all__'
        read_only_fields = ['id', 'customer', 'operator', 'created_at']

# Enhanced Quote Serializer for Marketplace
class MarketplaceQuoteSerializer(serializers.ModelSerializer):
    operator_details = SpeedboatOperatorSerializer(source='operator', read_only=True)
    boat_details = SpeedboatSerializer(source='boat', read_only=True)
    trip_request_details = TripRequestSerializer(source='trip_request', read_only=True)
    
    class Meta:
        model = Quote
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'commission_amount']
    
    def create(self, validated_data):
        # Calculate commission when creating quote
        quote = super().create(validated_data)
        if quote.amount and quote.commission_rate:
            quote.commission_amount = (quote.amount * quote.commission_rate) / 100
            quote.save()
        return quote