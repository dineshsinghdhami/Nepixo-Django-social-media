# your_app/utils.py
import random
import string
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User

def generate_temp_password(length=10):
    """Generate a random temporary password"""
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(characters) for _ in range(length))

def send_temp_password_email(user_email, temp_password):
    """Send temporary password to user's email"""
    subject = 'Your Temporary Password - Nepixo'
    message = f'''
Hello,

You requested a password reset for your Nepixo account.

Your temporary password is: **{temp_password}**

Instructions:
1. Login with your email and this temporary password
2. Go to your profile settings
3. Change your password immediately

If you didn't request this password reset, please ignore this email.

Best regards,
Nepxio Team
'''
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
