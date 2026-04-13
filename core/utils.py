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

from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags

def send_otp_email(email, otp):
    try:
        subject = "Email Verification - Nepixo"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f4;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    background-color: #ffffff;
                    border-radius: 10px;
                    overflow: hidden;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .content {{
                    padding: 30px;
                    text-align: center;
                }}
                .otp-code {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #667eea;
                    text-align: center;
                    padding: 20px;
                    background-color: #f8f9fa;
                    border-radius: 8px;
                    letter-spacing: 5px;
                    margin: 20px 0;
                    display: inline-block;
                }}
                .footer {{
                    background-color: #f8f9fa;
                    padding: 20px;
                    text-align: center;
                    color: #6c757d;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Nepixo</h1>
                    <p>Email Verification</p>
                </div>

                <div class="content">
                    <h2>Hello!</h2>
                    <p>Please use the following OTP to verify your email address:</p>

                    <div class="otp-code">{otp}</div>

                    <p>This OTP is valid for 10 minutes.</p>
                </div>

                <div class="footer">
                    <p>&copy; 2026 Nepixo. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"Your OTP is: {otp}. It is valid for 10 minutes."

        msg = EmailMultiAlternatives(
            subject,
            text_content,
            "noreply@nepixo.com",
            [email]
        )

        msg.attach_alternative(html_content, "text/html")
        msg.send()

        print(f"OTP email sent to {email}")
        return True

    except Exception as e:
        print(f"Error sending OTP email: {str(e)}")
        return False
    



import random

def generate_otp():
    return str(random.randint(100000, 999999))    
