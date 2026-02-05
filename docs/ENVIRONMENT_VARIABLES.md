# Environment Variables Reference

Complete list of all environment variables used in the Zzuhana e-commerce platform.

---

## Server Environment Variables (`.env`)

### Core Django Settings
| Variable | Type | Default | Used In | Description |
|----------|------|---------|---------|-------------|
| `SECRET_KEY` | string | `django-insecure-change-this-in-production` | `settings.py:20` | Django secret key for cryptographic signing |
| `DEBUG` | boolean | `True` | `settings.py:23` | Enable/disable debug mode |
| `ALLOWED_HOSTS` | string (comma-separated) | `localhost,127.0.0.1` | `settings.py:25` | Allowed hostnames for the server |

### Database Configuration
| Variable | Type | Default | Used In | Description |
|----------|------|---------|---------|-------------|
| `DB_NAME` | string | `zzuhana_db` | `settings.py:90` | PostgreSQL database name |
| `DB_USER` | string | `postgres` | `settings.py:91` | PostgreSQL user |
| `DB_PASSWORD` | string | `` | `settings.py:92` | PostgreSQL password |
| `DB_HOST` | string | `localhost` | `settings.py:93` | PostgreSQL host |
| `DB_PORT` | integer | `5432` | `settings.py:94` | PostgreSQL port |

### Google OAuth
| Variable | Type | Default | Used In | Description |
|----------|------|---------|---------|-------------|
| `GOOGLE_CLIENT_ID` | string | `` | `settings.py:155`, `apps/accounts/views.py:164` | Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | string | `` | `settings.py:156` | Google OAuth Client Secret |

### Email/SMTP Configuration
| Variable | Type | Default | Used In | Description |
|----------|------|---------|---------|-------------|
| `EMAIL_BACKEND` | string | `django.core.mail.backends.console.EmailBackend` | `settings.py:159` | Email backend (console for dev, smtp for prod) |
| `EMAIL_HOST` | string | `smtp.gmail.com` | `settings.py:160` | SMTP server host |
| `EMAIL_PORT` | integer | `587` | `settings.py:161` | SMTP server port |
| `EMAIL_USE_TLS` | boolean | `True` | `settings.py:162` | Use TLS for SMTP |
| `EMAIL_HOST_USER` | string | `` | `settings.py:163` | SMTP username/email |
| `EMAIL_HOST_PASSWORD` | string | `` | `settings.py:164` | SMTP password or app password |
| `DEFAULT_FROM_EMAIL` | string | `Zzuhana <noreply@zzuhana.com>` | `settings.py:165` | Default sender email address |

### CORS & CSRF Settings
| Variable | Type | Default | Used In | Description |
|----------|------|---------|---------|-------------|
| `CORS_ALLOWED_ORIGINS` | string (comma-separated) | `http://localhost:3000,http://localhost:3001,...` | `settings.py:168-172` | Allowed CORS origins |
| `CORS_ALLOW_CREDENTIALS` | boolean | `True` | `settings.py:173` | Allow credentials in CORS requests |
| `CSRF_TRUSTED_ORIGINS` | string (comma-separated) | `http://localhost:3000,...` | `settings.py:176-180` | Trusted origins for CSRF |
| `CSRF_COOKIE_SECURE` | boolean | `False` | `settings.py:181` | CSRF cookie secure flag |
| `SESSION_COOKIE_SECURE` | boolean | `False` | `settings.py:182` | Session cookie secure flag |
| `CSRF_COOKIE_SAMESITE` | string | `Lax` | `settings.py:183` | CSRF cookie SameSite attribute |
| `SESSION_COOKIE_SAMESITE` | string | `Lax` | `settings.py:184` | Session cookie SameSite attribute |

### Payment Gateway (SSLCommerz)
| Variable | Type | Default | Used In | Description |
|----------|------|---------|---------|-------------|
| `SSLCOMMERZ_STORE_ID` | string | `` | `settings.py:187` | SSLCommerz store ID |
| `SSLCOMMERZ_STORE_PASSWORD` | string | `` | `settings.py:188` | SSLCommerz store password |
| `SSLCOMMERZ_SANDBOX` | boolean | `True` | `settings.py:189` | Use SSLCommerz sandbox mode |

### Frontend URLs
| Variable | Type | Default | Used In | Description |
|----------|------|---------|---------|-------------|
| `FRONTEND_URL` | string | `http://localhost:3000` | `settings.py:192` | Client application URL (for email links) |
| `ADMIN_PANEL_URL` | string | `http://localhost:3001` | `settings.py:193` | Admin panel URL |

---

## Client Environment Variables (`.env.local`)

### API Configuration
| Variable | Type | Default | Used In | Description |
|----------|------|---------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | string | `http://localhost:8000/api/v1` | `lib/api.js:3`, `pages/category/[slug].jsx:11`, `pages/category/[slug]/[subcategory].jsx:11`, `components/search/SearchModal.jsx:8`, `components/products/ProductCard.jsx:67`, `components/home/CategoryShowcase.jsx:93` | Backend API base URL |

### Google OAuth
| Variable | Type | Default | Used In | Description |
|----------|------|---------|---------|-------------|
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | string | `` | `pages/login.jsx:12`, `pages/register.jsx:12` | Google OAuth Client ID (must match server) |

---

## Server `.env` Template

```env
# Core Django Settings
SECRET_KEY=your-super-secret-key-here-change-in-production
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Database
DB_NAME=zzuhana_db
DB_USER=postgres
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Email/SMTP (Gmail Example)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-16-char-app-password
DEFAULT_FROM_EMAIL=Zzuhana <noreply@zzuhana.com>

# CORS & CSRF
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001,https://your-domain.com
CORS_ALLOW_CREDENTIALS=True
CSRF_TRUSTED_ORIGINS=http://localhost:3000,http://localhost:3001,https://your-domain.com
CSRF_COOKIE_SECURE=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SAMESITE=Lax
SESSION_COOKIE_SAMESITE=Lax

# Payment Gateway (SSLCommerz)
SSLCOMMERZ_STORE_ID=your-store-id
SSLCOMMERZ_STORE_PASSWORD=your-store-password
SSLCOMMERZ_SANDBOX=True

# Frontend URLs
FRONTEND_URL=http://localhost:3000
ADMIN_PANEL_URL=http://localhost:3001
```

---

## Client `.env.local` Template

```env
PORT=3000
NEXT_PUBLIC_API_URL=https://server.zzuhana.com/api/v1
NEXT_PUBLIC_ADMIN_URL=https://admin.zzuhana.com
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
```

---

## Environment-Specific Configurations

### Development
```env
# Server
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_COOKIE_SECURE=False
SESSION_COOKIE_SECURE=False
SSLCOMMERZ_SANDBOX=True
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Client
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### Production
```env
# Server
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
SSLCOMMERZ_SANDBOX=False
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend

# Client
NEXT_PUBLIC_API_URL=https://server.your-domain.com/api/v1
```

---

## Checklist for Setup

### Server Setup
- [ ] `SECRET_KEY` - Set a strong random key
- [ ] `DEBUG` - Set to `False` in production
- [ ] `ALLOWED_HOSTS` - Add your domain
- [ ] `DB_*` - Configure PostgreSQL connection
- [ ] `GOOGLE_CLIENT_ID` - Add from Google Cloud Console
- [ ] `GOOGLE_CLIENT_SECRET` - Add from Google Cloud Console
- [ ] `EMAIL_HOST_USER` - Add your email
- [ ] `EMAIL_HOST_PASSWORD` - Add app password
- [ ] `CORS_ALLOWED_ORIGINS` - Add client domain
- [ ] `SSLCOMMERZ_STORE_ID` - Add if using payments
- [ ] `SSLCOMMERZ_STORE_PASSWORD` - Add if using payments
- [ ] `FRONTEND_URL` - Set to client URL

### Client Setup
- [ ] `NEXT_PUBLIC_API_URL` - Set to server API URL
- [ ] `NEXT_PUBLIC_GOOGLE_CLIENT_ID` - Must match server value

---

## Notes

1. **NEXT_PUBLIC_ prefix**: Variables with this prefix are exposed to the browser. Never put secrets here.
2. **Google OAuth**: Both server and client must have matching `GOOGLE_CLIENT_ID`.
3. **Email**: For Gmail, use App Password with 2FA enabled, not your actual password.
4. **CORS**: Must include all domains where the client is hosted.
5. **Production**: Always set `DEBUG=False` and use HTTPS URLs in production.
6. **Secrets**: Never commit `.env` files to version control.

