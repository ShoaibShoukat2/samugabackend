from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

def privacy_policy(request):
    html = """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Privacy Policy - SamugaTravels</title>
<style>body{font-family:Arial,sans-serif;max-width:800px;margin:40px auto;padding:0 20px;line-height:1.6;color:#333;}h1{color:#0066CC;}h2{color:#0052A3;}</style>
</head>
<body>
<h1>Privacy Policy - SamugaTravels</h1>
<p><strong>Last updated: July 2026</strong></p>

<h2>1. Information We Collect</h2>
<p>We collect information you provide when registering: name, email address, phone number, and profile photo. We also collect trip booking details, payment proof images, and location information for trip requests.</p>

<h2>2. How We Use Your Information</h2>
<p>We use your information to: process trip bookings and payments, connect customers with boat operators, send booking confirmations and notifications, and improve our services.</p>

<h2>3. Information Sharing</h2>
<p>We share your trip details with boat operators to fulfill your bookings. We do not sell your personal information to third parties.</p>

<h2>4. Data Security</h2>
<p>We use industry-standard HTTPS encryption to protect your data in transit. Payment proofs are stored securely and only accessible to authorized operators and admins.</p>

<h2>5. Photos and Media</h2>
<p>We access your camera and photo library only when you choose to upload payment proof or profile pictures. We do not access your media files without your explicit action.</p>

<h2>6. Your Rights</h2>
<p>You may request deletion of your account and personal data by contacting us at samugacreative@gmail.com.</p>

<h2>7. Contact Us</h2>
<p>For privacy concerns, contact: samugacreative@gmail.com</p>
</body>
</html>"""
    return HttpResponse(html)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('privacy-policy/', privacy_policy, name='privacy_policy'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
