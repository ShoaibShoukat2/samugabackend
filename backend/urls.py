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


def support_page(request):
    html = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Support - SamugaTravels</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; background: #F0F4F8; color: #333; }
  .header { background: #0D2137; padding: 32px 20px; text-align: center; }
  .header h1 { color: #FFF; font-size: 28px; font-weight: 700; }
  .header p { color: #A0C4E8; margin-top: 8px; font-size: 15px; }
  .container { max-width: 720px; margin: 40px auto; padding: 0 20px 60px; }
  .card { background: #FFF; border-radius: 16px; padding: 28px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); }
  .card h2 { color: #0D2137; font-size: 18px; margin-bottom: 14px; display: flex; align-items: center; gap: 10px; }
  .card p, .card li { color: #555; font-size: 15px; line-height: 1.7; }
  .card ul { padding-left: 20px; }
  .card ul li { margin-bottom: 6px; }
  .contact-btn { display: inline-block; background: #0D2137; color: #FFF; padding: 14px 28px; border-radius: 10px; text-decoration: none; font-weight: 600; font-size: 15px; margin-top: 14px; }
  .contact-btn:hover { background: #1A3A5C; }
  .faq-q { font-weight: 600; color: #0D2137; margin-top: 14px; margin-bottom: 4px; }
  .badge { background: #E8F4FD; color: #0D2137; border-radius: 6px; padding: 2px 10px; font-size: 13px; font-weight: 600; }
  footer { text-align: center; color: #AAA; font-size: 13px; margin-top: 40px; }
</style>
</head>
<body>

<div class="header">
  <h1>🌴 SamugaTravels Support</h1>
  <p>Maldives Speedboat Booking Platform</p>
</div>

<div class="container">

  <div class="card">
    <h2>📬 Contact Us</h2>
    <p>We're here to help. Reach out to our support team and we'll respond within 24 hours.</p>
    <p style="margin-top:12px;"><strong>Email:</strong> samugacreative@gmail.com</p>
    <a href="mailto:samugacreative@gmail.com" class="contact-btn">Send us an Email</a>
  </div>

  <div class="card">
    <h2>❓ Frequently Asked Questions</h2>

    <p class="faq-q">How do I book a speedboat trip?</p>
    <p>Open the app, tap "New Trip Request", fill in your pickup location, destination, date and passenger count, then submit. Operators will send you quotes within minutes.</p>

    <p class="faq-q">How do I pay for my booking?</p>
    <p>Once you accept a quote, you'll see the operator's bank details. Transfer the amount and upload your payment proof in the app. The operator will confirm your booking.</p>

    <p class="faq-q">Can I cancel a trip?</p>
    <p>Please contact us at samugacreative@gmail.com as soon as possible if you need to cancel. Cancellation policies depend on the individual operator.</p>

    <p class="faq-q">I'm a boat operator. How do I join?</p>
    <p>Download the SamugaTravels app, register an account, and select "Apply as Operator". Your first 30 days are completely free.</p>

    <p class="faq-q">How do I delete my account?</p>
    <p>Open the app → Profile → scroll to the bottom → tap "Delete Account". You'll be asked to confirm with your password. All your data will be permanently removed.</p>

    <p class="faq-q">My payment was uploaded but booking isn't confirmed?</p>
    <p>The operator needs to verify your payment. This usually takes a few hours. If it has been more than 24 hours, contact us with your booking details.</p>
  </div>

  <div class="card">
    <h2>📱 App Information</h2>
    <ul>
      <li>App Name: SamugaTravels</li>
      <li>Platform: iOS &amp; Android</li>
      <li>Developer: Samuga Creative</li>
      <li>Support Email: samugacreative@gmail.com</li>
      <li><a href="/privacy-policy/" style="color:#0D2137;">Privacy Policy</a></li>
    </ul>
  </div>

</div>

<footer>
  &copy; 2026 SamugaTravels. All rights reserved.
</footer>

</body>
</html>"""
    return HttpResponse(html)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('privacy-policy/', privacy_policy, name='privacy_policy'),
    path('support/', support_page, name='support_page'),
    path('', support_page, name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
