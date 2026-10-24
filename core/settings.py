"""
Django settings for Pickorbeet E-commerce project.
"""
import os
import sys
from pathlib import Path
from datetime import timedelta
from decouple import config

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-this-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    # Daphne before staticfiles so `runserver` speaks WebSocket in development.
    'daphne',
    # Jazzmin must be before django.contrib.admin
    'jazzmin',
    
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_yasg',
    'channels',
    
    # Local apps
    'apps.accounts',
    'apps.products',
    'apps.orders',
    'apps.payments',
    'apps.reports',
    'apps.shipping',
    'apps.notifications',
    'apps.support',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='pickorbeet_db'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    # Only views that opt in with ScopedRateThrottle use these.
    'DEFAULT_THROTTLE_RATES': {
        'shipment_refresh': config('SHIPMENT_REFRESH_RATE', default='10/min'),
        'device_register': config('DEVICE_REGISTER_RATE', default='30/hour'),
    },
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Google OAuth Settings
GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID', default='')
GOOGLE_CLIENT_SECRET = config('GOOGLE_CLIENT_SECRET', default='')

# Email Settings
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='Pickorbeet <noreply@pickorbeet.com>')
SUPPORT_EMAIL = config('SUPPORT_EMAIL', default='support@pickorbeet.com')
SUPPORT_PHONE = config('SUPPORT_PHONE', default='+880 9610-123456')
APP_STORE_URL = config('APP_STORE_URL', default='')
PLAY_STORE_URL = config('PLAY_STORE_URL', default='')
DELIVERY_ETA_DAYS = config('DELIVERY_ETA_DAYS', default=5, cast=int)
# Absolute origin for /media images inside mail. Falls back to the storefront.
PUBLIC_BASE_URL = config('PUBLIC_BASE_URL', default='')
EMAIL_FACEBOOK_URL = config('EMAIL_FACEBOOK_URL', default='https://facebook.com/pickorbeet')
EMAIL_X_URL = config('EMAIL_X_URL', default='https://x.com/pickorbeet')
EMAIL_YOUTUBE_URL = config('EMAIL_YOUTUBE_URL', default='https://youtube.com/@pickorbeet')
EMAIL_LINKEDIN_URL = config('EMAIL_LINKEDIN_URL', default='https://www.linkedin.com/company/pickorbeet')

# CORS Settings
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://localhost:3001,http://localhost:3777,http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:3777,https://www.pickorbeet.com,https://pickorbeet.com,https://admin.pickorbeet.com',
    cast=lambda v: [s.strip() for s in v.split(',')]
)
CORS_ALLOW_CREDENTIALS = config('CORS_ALLOW_CREDENTIALS', default=True, cast=bool)

# CSRF Settings
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:3000,http://localhost:3001,http://localhost:3777,http://127.0.0.1:3000,http://127.0.0.1:3777,https://www.pickorbeet.com,https://pickorbeet.com,https://admin.pickorbeet.com',
    cast=lambda v: [s.strip() for s in v.split(',')]
)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
CSRF_COOKIE_SAMESITE = config('CSRF_COOKIE_SAMESITE', default='Lax')
SESSION_COOKIE_SAMESITE = config('SESSION_COOKIE_SAMESITE', default='Lax')

# SSLCommerz Settings
SSLCOMMERZ_STORE_ID = config('SSLCOMMERZ_STORE_ID', default='')
SSLCOMMERZ_STORE_PASSWORD = config('SSLCOMMERZ_STORE_PASSWORD', default='')
SSLCOMMERZ_SANDBOX = config('SSLCOMMERZ_SANDBOX', default=True, cast=bool)

# Frontend URLs - Check os.environ first for production servers
FRONTEND_URL = os.environ.get('FRONTEND_URL') or config('FRONTEND_URL', default='https://www.pickorbeet.com')
ADMIN_PANEL_URL = os.environ.get('ADMIN_PANEL_URL') or config('ADMIN_PANEL_URL', default='https://admin.pickorbeet.com')

# Jazzmin Admin Configuration
JAZZMIN_SETTINGS = {
    "site_title": "Pickorbeet Admin",
    "site_header": "Pickorbeet",
    "site_brand": "Pickorbeet",
    "site_logo": "images/logo.png",
    "login_logo": "images/logo.png",
    "login_logo_dark": "images/logo-dark.png",
    "site_logo_classes": "img-circle",
    "site_icon": "images/favicon.ico",
    "welcome_sign": "Welcome to Pickorbeet Admin Panel",
    "copyright": "Pickorbeet Ltd",
    "search_model": ["accounts.User", "products.Product", "orders.Order"],
    "user_avatar": None,
    
    # Top Menu
    "topmenu_links": [
        {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "View Site", "url": "/", "new_window": True},
        {"model": "accounts.User"},
    ],

    # Side Menu
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": [
        "accounts",
        "products",
        "orders",
        "shipping",
        "payments",
        "notifications",
        "reports",
    ],

    # Icons
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "accounts.User": "fas fa-user",
        "products.Category": "fas fa-folder",
        "products.SubCategory": "fas fa-folder-open",
        "products.Product": "fas fa-tshirt",
        "products.ProductImage": "fas fa-image",
        "orders.Order": "fas fa-shopping-cart",
        "orders.OrderItem": "fas fa-shopping-basket",
        "shipping.Shipment": "fas fa-truck",
        "shipping.ShipmentEvent": "fas fa-stream",
        "payments.Payment": "fas fa-credit-card",
        "notifications.Notification": "fas fa-bell",
        "notifications.Device": "fas fa-mobile-alt",
        "reports.StockReport": "fas fa-chart-bar",
        "reports.SalesReport": "fas fa-chart-line",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",

    # Related Modal
    "related_modal_active": True,

    # UI Tweaks
    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,

    # Change view
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-success",
    "accent": "accent-teal",
    "navbar": "navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-success",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}

# Delivery Charge Settings
DELIVERY_CHARGE_INSIDE_DHAKA = 60
DELIVERY_CHARGE_OUTSIDE_DHAKA = 120

# Steadfast Courier. Keys stay on the server; apps and the website never call Steadfast.
STEADFAST_BASE_URL = config('STEADFAST_BASE_URL', default='https://portal.packzy.com/api/v1')
STEADFAST_API_KEY = config('STEADFAST_API_KEY', default='')
STEADFAST_SECRET_KEY = config('STEADFAST_SECRET_KEY', default='')
# Bearer token Steadfast sends to POST /api/v1/shipping/steadfast/webhook/
STEADFAST_WEBHOOK_TOKEN = config('STEADFAST_WEBHOOK_TOKEN', default='')
STEADFAST_TRACKING_URL = config('STEADFAST_TRACKING_URL', default='https://steadfast.com.bd/t/{code}')
# Booking marks the order shipped; a confirmed courier delivery marks it delivered.
STEADFAST_SYNC_ORDER_STATUS = config('STEADFAST_SYNC_ORDER_STATUS', default=True, cast=bool)

# Low Stock Alert Threshold
LOW_STOCK_THRESHOLD = 10

# Live inbox (Channels) and push delivery (Celery). Both use Redis in production.
# Tests use an in-memory channel layer and run tasks in-process so Redis is optional.
REDIS_URL = config('REDIS_URL', default='redis://127.0.0.1:6379/0')
FIREBASE_CREDENTIALS = config('FIREBASE_CREDENTIALS', default='')
RUNNING_TESTS = 'test' in sys.argv

if RUNNING_TESTS:
    CHANNEL_LAYERS = {
        'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
    }
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [REDIS_URL]},
        },
    }
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_TASK_ALWAYS_EAGER = config('CELERY_TASK_ALWAYS_EAGER', default=False, cast=bool)
    CELERY_TASK_EAGER_PROPAGATES = True

# Exported PickOrbeet admin panel, served at /admin/.
ADMIN_PANEL_DIST = BASE_DIR / 'admin_panel' / 'out'

from core.py314_compat import apply as _apply_py314_compat

_apply_py314_compat()
