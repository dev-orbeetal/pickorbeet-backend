# Authentication Credentials Setup Guide

This guide provides step-by-step instructions for setting up external authentication services for the Zzuhana e-commerce platform.

---

## Table of Contents

1. [Google OAuth Setup](#1-google-oauth-setup)
2. [SMTP Email Configuration](#2-smtp-email-configuration)
3. [Environment Variables](#3-environment-variables)
4. [Backend Configuration](#4-backend-configuration)
5. [Troubleshooting](#5-troubleshooting)

---

## 1. Google OAuth Setup

Google OAuth allows users to sign in/sign up using their Google account.

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a Project** → **New Project**
3. Enter project name (e.g., "Zzuhana E-commerce")
4. Click **Create**

### Step 2: Enable Required APIs

1. In the Cloud Console, go to **APIs & Services** → **Library**
2. Search for and enable:
   - **Google+ API** (for user profile info)
   - **Google Identity Services**

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **External** (for public users) or **Internal** (for organization only)
3. Fill in the required fields:
   - **App name**: Zzuhana
   - **User support email**: your-email@example.com
   - **App logo**: Upload your logo (optional)
   - **App domain**: Your production domain
   - **Developer contact email**: your-email@example.com
4. Click **Save and Continue**
5. Add scopes (click **Add or Remove Scopes**):
   - `email`
   - `profile`
   - `openid`
6. Click **Save and Continue**
7. Add test users if in testing mode
8. Click **Save and Continue**

### Step 4: Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Select **Web application**
4. Configure:
   - **Name**: Zzuhana Web Client
   - **Authorized JavaScript origins**:
     ```
     http://localhost:3000
     https://your-production-domain.com
     ```
   - **Authorized redirect URIs**:
     ```
     http://localhost:3000
     https://your-production-domain.com
     ```
5. Click **Create**
6. Copy the **Client ID** and **Client Secret**

### Step 5: Add to Environment Variables

```env
# Client (.env.local)
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com

# Server (.env)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

---

## 2. SMTP Email Configuration

SMTP is required for sending verification emails, password resets, and order notifications.

### Option A: Gmail SMTP (Development/Small Scale)

> **Note**: For Gmail, you need to use an App Password if 2FA is enabled.

#### Step 1: Enable 2-Factor Authentication
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification**

#### Step 2: Create App Password
1. Go to [App Passwords](https://myaccount.google.com/apppasswords)
2. Select **Mail** and **Other (Custom name)**
3. Enter "Zzuhana" and click **Generate**
4. Copy the 16-character password

#### Step 3: Add to Environment
```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-16-char-app-password
DEFAULT_FROM_EMAIL=Zzuhana <your-email@gmail.com>
```

### Option B: SendGrid (Recommended for Production)

#### Step 1: Create SendGrid Account
1. Go to [SendGrid](https://sendgrid.com/) and sign up
2. Verify your email

#### Step 2: Create API Key
1. Go to **Settings** → **API Keys**
2. Click **Create API Key**
3. Name: "Zzuhana Production"
4. Select **Full Access** or **Restricted Access** with Mail Send permission
5. Copy the API key

#### Step 3: Verify Sender Identity
1. Go to **Settings** → **Sender Authentication**
2. Either:
   - **Domain Authentication** (recommended for production)
   - **Single Sender Verification** (quick setup)

#### Step 4: Add to Environment
```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
DEFAULT_FROM_EMAIL=Zzuhana <noreply@yourdomain.com>
```

### Option C: Amazon SES (Enterprise Scale)

#### Step 1: Setup AWS Account
1. Go to [AWS Console](https://aws.amazon.com/ses/)
2. Navigate to **Amazon SES**

#### Step 2: Verify Domain/Email
1. Go to **Verified identities**
2. Click **Create identity**
3. Choose **Domain** or **Email address**
4. Follow verification steps

#### Step 3: Create SMTP Credentials
1. Go to **SMTP settings**
2. Click **Create SMTP credentials**
3. Download credentials

#### Step 4: Add to Environment
```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=email-smtp.us-east-1.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-ses-smtp-username
EMAIL_HOST_PASSWORD=your-ses-smtp-password
DEFAULT_FROM_EMAIL=Zzuhana <noreply@yourdomain.com>
```

---

## 3. Environment Variables

### Client Environment Variables (`.env.local`)

```env
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# Google OAuth
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com

# Site Configuration
NEXT_PUBLIC_SITE_URL=http://localhost:3000
NEXT_PUBLIC_SITE_NAME=Zzuhana
```

### Server Environment Variables (`.env`)

```env
# Django Settings
DEBUG=True
SECRET_KEY=your-super-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://user:password@localhost:5432/zzuhana

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Email/SMTP
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=Zzuhana <your-email@gmail.com>

# JWT Settings
ACCESS_TOKEN_LIFETIME=60  # minutes
REFRESH_TOKEN_LIFETIME=7  # days

# Frontend URL (for email links)
FRONTEND_URL=http://localhost:3000
```

---

## 4. Backend Configuration

### Install Required Packages

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2
pip install django-allauth  # Optional: for social auth
```

### Update Django Settings

Add to `settings.py`:

```python
# Google OAuth
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

# Email Configuration
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@example.com')

# Frontend URL for email links
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
```

### Create Google Auth View

Create `apps/accounts/views.py`:

```python
from google.oauth2 import id_token
from google.auth.transport import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .models import CustomUser

class GoogleAuthView(APIView):
    permission_classes = []
    
    def post(self, request):
        credential = request.data.get('credential')
        
        if not credential:
            return Response(
                {'error': 'Credential is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Verify the token
            idinfo = id_token.verify_oauth2_token(
                credential,
                requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )
            
            # Get user info
            email = idinfo.get('email')
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            
            # Get or create user
            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_email_verified': True,
                }
            )
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                }
            })
            
        except ValueError as e:
            return Response(
                {'error': 'Invalid credential'},
                status=status.HTTP_400_BAD_REQUEST
            )
```

### Add URL Pattern

In `apps/accounts/urls.py`:

```python
from .views import GoogleAuthView

urlpatterns = [
    # ... other patterns
    path('google/', GoogleAuthView.as_view(), name='google_auth'),
]
```

---

## 5. Troubleshooting

### Google OAuth Issues

| Issue | Solution |
|-------|----------|
| "popup_closed_by_user" | User closed the popup. Normal behavior. |
| "access_denied" | User denied permission. Check consent screen. |
| "invalid_client" | Check Client ID matches in frontend and backend. |
| "redirect_uri_mismatch" | Add your domain to Authorized JavaScript origins. |
| "idpiframe_initialization_failed" | Clear cookies or try incognito mode. |

### SMTP Issues

| Issue | Solution |
|-------|----------|
| Connection refused | Check EMAIL_HOST and EMAIL_PORT settings. |
| Authentication failed | Verify EMAIL_HOST_USER and EMAIL_HOST_PASSWORD. |
| Gmail "Less secure apps" | Use App Password with 2FA enabled. |
| Emails going to spam | Set up SPF, DKIM, and DMARC for your domain. |

### Testing Email Configuration

```python
# Django shell
python manage.py shell

from django.core.mail import send_mail
send_mail(
    'Test Email',
    'This is a test email from Zzuhana.',
    'noreply@yourdomain.com',
    ['your-email@example.com'],
    fail_silently=False,
)
```

---

## Quick Start Checklist

- [ ] Create Google Cloud Project
- [ ] Configure OAuth Consent Screen
- [ ] Create OAuth 2.0 Credentials
- [ ] Add `NEXT_PUBLIC_GOOGLE_CLIENT_ID` to client `.env.local`
- [ ] Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to server `.env`
- [ ] Configure SMTP settings in server `.env`
- [ ] Test Google Sign-In on login/register pages
- [ ] Test email sending (password reset, verification)
- [ ] Deploy and update Authorized origins for production domain

---

## Security Best Practices

1. **Never commit `.env` files** to version control
2. **Use different credentials** for development and production
3. **Rotate secrets regularly** (every 90 days recommended)
4. **Enable 2FA** on all admin accounts
5. **Use HTTPS** in production for all OAuth callbacks
6. **Restrict API key permissions** to only what's needed
7. **Monitor authentication logs** for suspicious activity

---

## Support

If you encounter issues not covered in this guide, please:
1. Check the [Google OAuth Documentation](https://developers.google.com/identity)
2. Review Django email [documentation](https://docs.djangoproject.com/en/4.2/topics/email/)
3. Contact the development team
