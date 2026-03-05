from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid

class User(AbstractUser):
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    otp = models.CharField(max_length=6, null=True, blank=True)
    otp_created_at = models.DateTimeField(null=True, blank=True)
    is_admin = models.BooleanField(default=False)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    
    def __str__(self):
        return self.email or self.phone_number or self.username

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
    
    def __str__(self):
        return f"{self.trip_type} - {self.user.email} - {self.trip_date}"

class Quote(models.Model):
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('MVR', 'Maldivian Rufiyaa'),
    ]
    
    trip_request = models.OneToOneField(TripRequest, on_delete=models.CASCADE, related_name='quote')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    operator_name = models.CharField(max_length=255)
    operator_contact = models.CharField(max_length=100)
    notes = models.TextField(blank=True)
    valid_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Quote for {self.trip_request.id} - {self.currency} {self.amount}"

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
    booking_code = models.CharField(max_length=20, unique=True)
    qr_code = models.ImageField(upload_to='qr_codes/', null=True, blank=True)
    e_ticket = models.FileField(upload_to='e_tickets/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Booking {self.booking_code}"

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
