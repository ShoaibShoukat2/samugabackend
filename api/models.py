from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from decimal import Decimal
import uuid

class User(AbstractUser):
    USER_TYPES = [
        ('customer', 'Customer'),
        ('operator', 'Speedboat Operator'),
        ('admin', 'Admin'),
    ]
    
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    otp = models.CharField(max_length=6, null=True, blank=True)
    otp_created_at = models.DateTimeField(null=True, blank=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='customer')
    is_admin = models.BooleanField(default=False)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    
    def __str__(self):
        return self.email or self.phone_number or self.username

class SpeedboatOperator(models.Model):
    VERIFICATION_STATUS = [
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('suspended', 'Suspended'),
        ('rejected', 'Rejected'),
    ]
    
    SUBSCRIPTION_STATUS = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='operator_profile')
    company_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    business_license = models.CharField(max_length=100, blank=True)
    
    # Verification documents
    license_document = models.ImageField(upload_to='operator_documents/', null=True, blank=True)
    boat_registration = models.ImageField(upload_to='operator_documents/', null=True, blank=True)
    insurance_document = models.ImageField(upload_to='operator_documents/', null=True, blank=True)
    
    # Status
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='pending')
    subscription_status = models.CharField(max_length=20, choices=SUBSCRIPTION_STATUS, default='expired')
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Service areas
    service_islands = models.TextField(help_text="Comma-separated list of islands served")
    
    # Ratings
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_ratings = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.company_name} - {self.contact_person}"

class Speedboat(models.Model):
    BOAT_TYPES = [
        ('speedboat', 'Speedboat'),
        ('dhoni', 'Traditional Dhoni'),
        ('yacht', 'Yacht'),
        ('catamaran', 'Catamaran'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(SpeedboatOperator, on_delete=models.CASCADE, related_name='boats')
    name = models.CharField(max_length=255)
    boat_type = models.CharField(max_length=50, choices=BOAT_TYPES)
    capacity = models.IntegerField()
    registration_number = models.CharField(max_length=100)
    year_built = models.IntegerField(null=True, blank=True)
    
    # Features
    has_toilet = models.BooleanField(default=False)
    has_shade = models.BooleanField(default=False)
    has_snorkel_gear = models.BooleanField(default=False)
    has_fishing_gear = models.BooleanField(default=False)
    has_life_jackets = models.BooleanField(default=True)
    
    # Images
    main_image = models.ImageField(upload_to='boat_images/', null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.operator.company_name}"

class TripRequest(models.Model):
    TRIP_TYPES = [
        ('transfer', 'Transfer'),
        ('snorkeling', 'Snorkeling'),
        ('fishing', 'Fishing'),
        ('sandbank', 'Sandbank'),
        ('guesthouse_transfer', 'Guesthouse Transfer'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('quoted', 'Quoted'),
        ('accepted', 'Accepted'),
        ('payment_pending', 'Payment Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('MVR', 'Maldivian Rufiyaa'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trip_requests')
    trip_type = models.CharField(max_length=50, choices=TRIP_TYPES)
    pickup_location = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    trip_date = models.DateField()
    trip_time = models.TimeField()
    passenger_count = models.IntegerField()
    special_notes = models.TextField(blank=True)
    preferred_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def quote(self):
        """Return the first quote for backward compatibility"""
        return self.quotes.first()
    
    def __str__(self):
        return f"{self.trip_type} - {self.user.email} - {self.trip_date}"

class Quote(models.Model):
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('MVR', 'Maldivian Rufiyaa'),
    ]
    
    QUOTE_STATUS = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip_request = models.ForeignKey(TripRequest, on_delete=models.CASCADE, related_name='quotes')
    operator = models.ForeignKey(SpeedboatOperator, on_delete=models.CASCADE, related_name='quotes', null=True, blank=True)
    boat = models.ForeignKey(Speedboat, on_delete=models.CASCADE, related_name='quotes', null=True, blank=True)
    
    # Quote details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    pickup_time = models.TimeField(default='09:00:00')
    estimated_duration = models.DurationField(null=True, blank=True)
    
    # Legacy fields for admin quotes
    operator_name = models.CharField(max_length=255, blank=True)
    operator_contact = models.CharField(max_length=100, blank=True)
    
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=QUOTE_STATUS, default='pending')
    valid_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    # Operator bank details for payment
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=100, blank=True)
    account_name = models.CharField(max_length=255, blank=True)
    
    # Commission tracking
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)  # 5%
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        # Calculate commission amount
        if self.amount and self.commission_rate:
            # Ensure both values are Decimal to avoid float multiplication
            amount_decimal = Decimal(str(self.amount))
            rate_decimal = Decimal(str(self.commission_rate))
            self.commission_amount = (amount_decimal * rate_decimal) / Decimal('100')
        super().save(*args, **kwargs)
    
    def __str__(self):
        operator_name = self.operator.company_name if self.operator else self.operator_name
        return f"Quote for {self.trip_request.id} - {operator_name} - {self.currency} {self.amount}"

class Payment(models.Model):
    PAYMENT_METHODS = [
        ('card', 'Card Payment'),
        ('bml', 'BML Transfer'),
        ('mib', 'MIB Transfer'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('failed', 'Failed'),
    ]
    
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('MVR', 'Maldivian Rufiyaa'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip_request = models.OneToOneField(TripRequest, on_delete=models.CASCADE, related_name='payment')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    payment_proof = models.ImageField(upload_to='payment_proofs/', null=True, blank=True)
    transaction_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Payment {self.id} - {self.payment_method} - {self.currency} {self.amount}"

class Booking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip_request = models.OneToOneField(TripRequest, on_delete=models.CASCADE, related_name='booking')
    selected_quote = models.OneToOneField(Quote, on_delete=models.CASCADE, related_name='booking', null=True, blank=True)
    booking_code = models.CharField(max_length=20, unique=True)
    qr_code = models.ImageField(upload_to='qr_codes/', null=True, blank=True)
    e_ticket = models.FileField(upload_to='e_tickets/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Booking {self.booking_code}"

class OperatorSubscription(models.Model):
    SUBSCRIPTION_PLANS = [
        ('basic', 'Basic Plan - 450 MVR/month'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(SpeedboatOperator, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.CharField(max_length=20, choices=SUBSCRIPTION_PLANS, default='basic')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=450.00)  # MVR
    
    # Billing period
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Payment
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_proof = models.ImageField(upload_to='subscription_payments/', null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.operator.company_name} - {self.plan} - {self.start_date} to {self.end_date}"

class OperatorRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='rating')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_ratings')
    operator = models.ForeignKey(SpeedboatOperator, on_delete=models.CASCADE, related_name='received_ratings')
    
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])  # 1-5 stars
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.rating} stars for {self.operator.company_name}"

class PlatformRevenue(models.Model):
    REVENUE_TYPES = [
        ('subscription', 'Operator Subscription'),
        ('commission', 'Booking Commission'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revenue_type = models.CharField(max_length=20, choices=REVENUE_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='MVR')
    
    # Related objects
    subscription = models.OneToOneField(OperatorSubscription, on_delete=models.CASCADE, null=True, blank=True, related_name='revenue')
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, null=True, blank=True, related_name='revenue')
    
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.revenue_type} - {self.currency} {self.amount}"

class SupportMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_messages')
    message = models.TextField()
    is_admin_reply = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message from {self.user.email} at {self.created_at}"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    trip_request = models.ForeignKey(TripRequest, on_delete=models.CASCADE, null=True, blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.email}"
