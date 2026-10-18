"""
Email utilities for Pickorbeet - Beautiful themed email templates.
Theme colors: Burgundy (#8B0000), Gold (#D4AF37), Cream (#F5F5DC)
"""
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags


def get_base_email_template(content):
    """Base email template with Pickorbeet branding."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pickorbeet</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #F5F5DC;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 600px; width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 24px rgba(139, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #8B0000 0%, #6B0000 100%); padding: 30px 40px; border-radius: 16px 16px 0 0; text-align: center;">
                            <h1 style="margin: 0; color: #D4AF37; font-size: 32px; font-weight: 700; letter-spacing: 2px;">PICKORBEET</h1>
                            <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.8); font-size: 14px; letter-spacing: 1px;">Premium Fashion & Lifestyle</p>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            {content}
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #F5F5DC; padding: 30px 40px; border-radius: 0 0 16px 16px; text-align: center;">
                            <p style="margin: 0 0 10px 0; color: #666; font-size: 14px;">Follow us on social media</p>
                            <table role="presentation" style="margin: 0 auto 20px auto;">
                                <tr>
                                    <td style="padding: 0 8px;">
                                        <a href="https://facebook.com/pickorbeet" style="color: #8B0000; text-decoration: none; font-size: 14px;">Facebook</a>
                                    </td>
                                    <td style="padding: 0 8px; color: #D4AF37;">•</td>
                                    <td style="padding: 0 8px;">
                                        <a href="https://instagram.com/pickorbeet" style="color: #8B0000; text-decoration: none; font-size: 14px;">Instagram</a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 0; color: #999; font-size: 12px;">
                                © 2024 Pickorbeet. All rights reserved.<br>
                                <a href="{settings.FRONTEND_URL}/unsubscribe" style="color: #8B0000; text-decoration: none;">Unsubscribe</a> | 
                                <a href="{settings.FRONTEND_URL}/privacy" style="color: #8B0000; text-decoration: none;">Privacy Policy</a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def send_otp_email(user, otp_code):
    """Send 6-digit OTP verification email."""
    content = f"""
    <div style="text-align: center;">
        <div style="width: 80px; height: 80px; margin: 0 auto 20px auto; background: linear-gradient(135deg, #D4AF37 0%, #B8960C 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center;">
            <span style="font-size: 36px;">✉️</span>
        </div>
        <h2 style="margin: 0 0 10px 0; color: #8B0000; font-size: 24px; font-weight: 600;">Verify Your Email</h2>
        <p style="margin: 0 0 30px 0; color: #666; font-size: 16px;">Hi {user.first_name}, please use this verification code:</p>
        
        <!-- OTP Box -->
        <div style="background: linear-gradient(135deg, #8B0000 0%, #6B0000 100%); padding: 25px 40px; border-radius: 12px; margin: 0 auto 30px auto; display: inline-block;">
            <span style="font-size: 36px; font-weight: 700; color: #D4AF37; letter-spacing: 12px; font-family: 'Courier New', monospace;">{otp_code}</span>
        </div>
        
        <p style="margin: 0 0 10px 0; color: #666; font-size: 14px;">This code will expire in <strong style="color: #8B0000;">10 minutes</strong></p>
        <p style="margin: 0; color: #999; font-size: 13px;">If you didn't create an account, please ignore this email.</p>
    </div>
    
    <div style="margin-top: 30px; padding-top: 30px; border-top: 1px solid #eee;">
        <p style="margin: 0; color: #999; font-size: 12px; text-align: center;">
            For security reasons, never share this code with anyone.<br>
            Pickorbeet staff will never ask for your verification code.
        </p>
    </div>
    """
    
    html_message = get_base_email_template(content)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject='🔐 Your Pickorbeet Verification Code',
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_welcome_email(user):
    """Send beautiful welcome/congratulations email after verification."""
    content = f"""
    <div style="text-align: center;">
        <div style="width: 100px; height: 100px; margin: 0 auto 20px auto; background: linear-gradient(135deg, #D4AF37 0%, #B8960C 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center;">
            <span style="font-size: 50px;">🎉</span>
        </div>
        <h2 style="margin: 0 0 10px 0; color: #8B0000; font-size: 28px; font-weight: 700;">Welcome to Pickorbeet!</h2>
        <p style="margin: 0 0 30px 0; color: #666; font-size: 18px;">Congratulations, {user.first_name}! 🎊</p>
    </div>
    
    <div style="background: linear-gradient(135deg, #F5F5DC 0%, #EDE8D0 100%); padding: 25px; border-radius: 12px; margin-bottom: 30px;">
        <p style="margin: 0 0 15px 0; color: #333; font-size: 16px; line-height: 1.6;">
            Your account has been successfully verified. You're now part of our exclusive community of fashion enthusiasts!
        </p>
        <p style="margin: 0; color: #333; font-size: 16px; line-height: 1.6;">
            Get ready to explore our curated collection of premium fashion and lifestyle products.
        </p>
    </div>
    
    <div style="text-align: center; margin-bottom: 30px;">
        <h3 style="margin: 0 0 20px 0; color: #8B0000; font-size: 18px;">What's Next?</h3>
        <table role="presentation" style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 15px; text-align: center; width: 33%;">
                    <div style="width: 50px; height: 50px; margin: 0 auto 10px auto; background-color: #8B0000; border-radius: 50%; line-height: 50px;">
                        <span style="color: #D4AF37; font-size: 24px;">🛍️</span>
                    </div>
                    <p style="margin: 0; color: #666; font-size: 13px;">Browse Collections</p>
                </td>
                <td style="padding: 15px; text-align: center; width: 33%;">
                    <div style="width: 50px; height: 50px; margin: 0 auto 10px auto; background-color: #8B0000; border-radius: 50%; line-height: 50px;">
                        <span style="color: #D4AF37; font-size: 24px;">❤️</span>
                    </div>
                    <p style="margin: 0; color: #666; font-size: 13px;">Save Favorites</p>
                </td>
                <td style="padding: 15px; text-align: center; width: 33%;">
                    <div style="width: 50px; height: 50px; margin: 0 auto 10px auto; background-color: #8B0000; border-radius: 50%; line-height: 50px;">
                        <span style="color: #D4AF37; font-size: 24px;">🎁</span>
                    </div>
                    <p style="margin: 0; color: #666; font-size: 13px;">Get Rewards</p>
                </td>
            </tr>
        </table>
    </div>
    
    <div style="text-align: center;">
        <a href="{settings.FRONTEND_URL}/shop" style="display: inline-block; background: linear-gradient(135deg, #8B0000 0%, #6B0000 100%); color: #ffffff; padding: 15px 40px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px; box-shadow: 0 4px 15px rgba(139, 0, 0, 0.3);">
            Start Shopping →
        </a>
    </div>
    
    <div style="margin-top: 30px; padding: 20px; background-color: #FFF9E6; border-radius: 8px; border-left: 4px solid #D4AF37;">
        <p style="margin: 0; color: #8B6914; font-size: 14px;">
            <strong>🌟 Special Welcome Offer!</strong><br>
            Use code <strong style="color: #8B0000;">WELCOME10</strong> for 10% off your first order!
        </p>
    </div>
    """
    
    html_message = get_base_email_template(content)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject='🎉 Welcome to Pickorbeet - Your Account is Ready!',
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_google_welcome_email(user):
    """Send welcome email for Google OAuth signups."""
    content = f"""
    <div style="text-align: center;">
        <div style="width: 100px; height: 100px; margin: 0 auto 20px auto; background: linear-gradient(135deg, #D4AF37 0%, #B8960C 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center;">
            <span style="font-size: 50px;">✨</span>
        </div>
        <h2 style="margin: 0 0 10px 0; color: #8B0000; font-size: 28px; font-weight: 700;">Welcome to Pickorbeet!</h2>
        <p style="margin: 0 0 10px 0; color: #666; font-size: 18px;">Hello {user.first_name}! 👋</p>
        <p style="margin: 0 0 30px 0; color: #999; font-size: 14px;">Signed in with Google</p>
    </div>
    
    <div style="background: linear-gradient(135deg, #F5F5DC 0%, #EDE8D0 100%); padding: 25px; border-radius: 12px; margin-bottom: 30px;">
        <p style="margin: 0 0 15px 0; color: #333; font-size: 16px; line-height: 1.6;">
            Thank you for joining Pickorbeet! Your account has been created successfully using your Google account.
        </p>
        <p style="margin: 0; color: #333; font-size: 16px; line-height: 1.6;">
            You can now enjoy a seamless shopping experience with us. Discover our exclusive collection of premium fashion items curated just for you.
        </p>
    </div>
    
    <div style="text-align: center; margin-bottom: 30px;">
        <h3 style="margin: 0 0 20px 0; color: #8B0000; font-size: 18px;">Your Account Benefits</h3>
        <table role="presentation" style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 10px 15px; text-align: left; border-bottom: 1px solid #eee;">
                    <span style="color: #D4AF37; font-size: 18px; margin-right: 10px;">✓</span>
                    <span style="color: #333; font-size: 14px;">Quick & secure checkout</span>
                </td>
            </tr>
            <tr>
                <td style="padding: 10px 15px; text-align: left; border-bottom: 1px solid #eee;">
                    <span style="color: #D4AF37; font-size: 18px; margin-right: 10px;">✓</span>
                    <span style="color: #333; font-size: 14px;">Order tracking & history</span>
                </td>
            </tr>
            <tr>
                <td style="padding: 10px 15px; text-align: left; border-bottom: 1px solid #eee;">
                    <span style="color: #D4AF37; font-size: 18px; margin-right: 10px;">✓</span>
                    <span style="color: #333; font-size: 14px;">Exclusive member discounts</span>
                </td>
            </tr>
            <tr>
                <td style="padding: 10px 15px; text-align: left;">
                    <span style="color: #D4AF37; font-size: 18px; margin-right: 10px;">✓</span>
                    <span style="color: #333; font-size: 14px;">Early access to new arrivals</span>
                </td>
            </tr>
        </table>
    </div>
    
    <div style="text-align: center;">
        <a href="{settings.FRONTEND_URL}/shop" style="display: inline-block; background: linear-gradient(135deg, #8B0000 0%, #6B0000 100%); color: #ffffff; padding: 15px 40px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px; box-shadow: 0 4px 15px rgba(139, 0, 0, 0.3);">
            Explore Collections →
        </a>
    </div>
    
    <div style="margin-top: 30px; padding: 20px; background-color: #FFF9E6; border-radius: 8px; border-left: 4px solid #D4AF37;">
        <p style="margin: 0; color: #8B6914; font-size: 14px;">
            <strong>🎁 Welcome Gift!</strong><br>
            Use code <strong style="color: #8B0000;">WELCOME10</strong> for 10% off your first purchase!
        </p>
    </div>
    """
    
    html_message = get_base_email_template(content)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject='✨ Welcome to Pickorbeet - Let\'s Get Started!',
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_password_reset_email(user, reset_url):
    """Send password reset email."""
    content = f"""
    <div style="text-align: center;">
        <div style="width: 80px; height: 80px; margin: 0 auto 20px auto; background: linear-gradient(135deg, #8B0000 0%, #6B0000 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center;">
            <span style="font-size: 36px;">🔒</span>
        </div>
        <h2 style="margin: 0 0 10px 0; color: #8B0000; font-size: 24px; font-weight: 600;">Password Reset Request</h2>
        <p style="margin: 0 0 30px 0; color: #666; font-size: 16px;">Hi {user.first_name}, we received a request to reset your password.</p>
    </div>
    
    <div style="background: linear-gradient(135deg, #F5F5DC 0%, #EDE8D0 100%); padding: 25px; border-radius: 12px; margin-bottom: 30px; text-align: center;">
        <p style="margin: 0 0 20px 0; color: #333; font-size: 16px;">
            Click the button below to create a new password:
        </p>
        <a href="{reset_url}" style="display: inline-block; background: linear-gradient(135deg, #8B0000 0%, #6B0000 100%); color: #ffffff; padding: 15px 40px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px; box-shadow: 0 4px 15px rgba(139, 0, 0, 0.3);">
            Reset Password
        </a>
    </div>
    
    <div style="text-align: center; margin-bottom: 20px;">
        <p style="margin: 0; color: #666; font-size: 14px;">
            This link will expire in <strong style="color: #8B0000;">1 hour</strong>
        </p>
    </div>
    
    <div style="padding: 20px; background-color: #FFF3F3; border-radius: 8px; border-left: 4px solid #8B0000;">
        <p style="margin: 0; color: #8B0000; font-size: 14px;">
            <strong>⚠️ Didn't request this?</strong><br>
            If you didn't request a password reset, please ignore this email. Your account is still secure.
        </p>
    </div>
    """
    
    html_message = get_base_email_template(content)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject='🔒 Reset Your Pickorbeet Password',
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_password_changed_email(user):
    """Send confirmation email after password change."""
    content = f"""
    <div style="text-align: center;">
        <div style="width: 80px; height: 80px; margin: 0 auto 20px auto; background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center;">
            <span style="font-size: 36px;">✅</span>
        </div>
        <h2 style="margin: 0 0 10px 0; color: #4CAF50; font-size: 24px; font-weight: 600;">Password Changed Successfully</h2>
        <p style="margin: 0 0 30px 0; color: #666; font-size: 16px;">Hi {user.first_name}, your password has been updated.</p>
    </div>
    
    <div style="background: linear-gradient(135deg, #F5F5DC 0%, #EDE8D0 100%); padding: 25px; border-radius: 12px; margin-bottom: 30px;">
        <p style="margin: 0; color: #333; font-size: 16px; line-height: 1.6;">
            Your Pickorbeet account password was successfully changed. If you made this change, no further action is required.
        </p>
    </div>
    
    <div style="padding: 20px; background-color: #FFF3F3; border-radius: 8px; border-left: 4px solid #8B0000;">
        <p style="margin: 0; color: #8B0000; font-size: 14px;">
            <strong>⚠️ Wasn't you?</strong><br>
            If you didn't change your password, please <a href="{settings.FRONTEND_URL}/forgot-password" style="color: #8B0000; text-decoration: underline;">reset it immediately</a> and contact our support team.
        </p>
    </div>
    """
    
    html_message = get_base_email_template(content)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject='✅ Your Pickorbeet Password Was Changed',
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )
