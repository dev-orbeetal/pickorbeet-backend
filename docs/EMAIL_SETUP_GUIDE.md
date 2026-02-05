# Email Setup Guide for Zzuhana

Complete guide for setting up email with aPanel mail server and Cloudflare DNS.

---

## Option 1: Gmail SMTP (Quick Setup - Current)

Your current setup uses Gmail SMTP. To complete it:

### Step 1: Create Gmail App Password

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already enabled
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Select **Mail** and **Other (Custom name)** → Enter "Zzuhana Server"
5. Click **Generate**
6. Copy the **16-character password** (e.g., `abcd efgh ijkl mnop`)

### Step 2: Update Server `.env`

```env
EMAIL_HOST_PASSWORD=abcdefghijklmnop
```

Remove spaces from the app password.

### Limitations of Gmail SMTP:
- Daily limit: 500 emails/day (personal) or 2,000/day (Google Workspace)
- Sender shows as your Gmail address
- Not ideal for professional transactional emails

---

## Option 2: aPanel Mail Server (Professional Setup)

### Part A: aPanel Mail Server Setup

#### Step 1: Access aPanel
1. Login to your aPanel at `https://your-server-ip:2222` or your aPanel URL
2. Go to **Email** → **Email Accounts** or **Mail Manager**

#### Step 2: Create Email Domain
1. Click **Add Mail Domain**
2. Enter domain: `zzuhana.com`
3. Click **Create**

#### Step 3: Create Email Accounts
Create these email accounts:

| Email | Purpose |
|-------|---------|
| `noreply@zzuhana.com` | Transactional emails (order confirmations, password reset) |
| `support@zzuhana.com` | Customer support |
| `admin@zzuhana.com` | Admin notifications |

For each account:
1. Click **Add Email Account**
2. Enter username (e.g., `noreply`)
3. Set a strong password
4. Set quota (e.g., 1GB)
5. Click **Create**

#### Step 4: Get SMTP Settings from aPanel
In aPanel Email settings, find:
- **SMTP Server**: Usually `mail.zzuhana.com` or `your-server-ip`
- **SMTP Port**: `587` (TLS) or `465` (SSL)
- **Username**: `noreply@zzuhana.com`
- **Password**: The password you set

---

### Part B: Cloudflare DNS Setup for Email

#### Step 1: Login to Cloudflare
1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Select your domain `zzuhana.com`
3. Go to **DNS** → **Records**

#### Step 2: Add MX Records (Mail Exchange)

| Type | Name | Mail Server | Priority | TTL |
|------|------|-------------|----------|-----|
| MX | `@` | `mail.zzuhana.com` | 10 | Auto |

Or if using server IP directly:
| Type | Name | Mail Server | Priority | TTL |
|------|------|-------------|----------|-----|
| MX | `@` | `your-server-ip` | 10 | Auto |

#### Step 3: Add A Record for Mail Server

| Type | Name | Content | Proxy | TTL |
|------|------|---------|-------|-----|
| A | `mail` | `your-server-ip` | DNS only (gray cloud) | Auto |

**Important**: Mail record must be **DNS only** (gray cloud), NOT proxied!

#### Step 4: Add SPF Record (Prevents Spam Marking)

| Type | Name | Content | TTL |
|------|------|---------|-----|
| TXT | `@` | `v=spf1 ip4:YOUR_SERVER_IP a mx ~all` | Auto |

Replace `YOUR_SERVER_IP` with your actual server IP.

Example:
```
v=spf1 ip4:185.123.456.789 a mx ~all
```

#### Step 5: Add DKIM Record (Email Authentication)

1. In aPanel, go to **Email** → **DKIM** or **Email Authentication**
2. Generate DKIM key for `zzuhana.com`
3. Copy the DKIM public key
4. In Cloudflare, add:

| Type | Name | Content | TTL |
|------|------|---------|-----|
| TXT | `default._domainkey` | `v=DKIM1; k=rsa; p=YOUR_DKIM_PUBLIC_KEY` | Auto |

The name might be `default._domainkey` or `mail._domainkey` depending on aPanel.

#### Step 6: Add DMARC Record (Email Policy)

| Type | Name | Content | TTL |
|------|------|---------|-----|
| TXT | `_dmarc` | `v=DMARC1; p=quarantine; rua=mailto:admin@zzuhana.com` | Auto |

---

### Part C: Update Server `.env` for aPanel Mail

```env
# Email Configuration (aPanel Mail Server)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mail.zzuhana.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@zzuhana.com
EMAIL_HOST_PASSWORD=your-email-password-here
DEFAULT_FROM_EMAIL=Zzuhana <noreply@zzuhana.com>
```

Or if using SSL on port 465:
```env
EMAIL_PORT=465
EMAIL_USE_TLS=False
EMAIL_USE_SSL=True
```

---

## Complete Cloudflare DNS Records Summary

Here's what your Cloudflare DNS should look like:

```
# Website Records (Proxied - Orange Cloud)
A       @           your-server-ip      Proxied     Auto
A       www         your-server-ip      Proxied     Auto
A       server      your-server-ip      Proxied     Auto
A       admin       your-server-ip      Proxied     Auto

# Mail Records (DNS Only - Gray Cloud)
A       mail        your-server-ip      DNS only    Auto
MX      @           mail.zzuhana.com    Priority 10 Auto

# Email Authentication (TXT Records)
TXT     @           v=spf1 ip4:YOUR_IP a mx ~all              Auto
TXT     default._domainkey   v=DKIM1; k=rsa; p=YOUR_KEY       Auto
TXT     _dmarc      v=DMARC1; p=quarantine; rua=mailto:admin@zzuhana.com   Auto
```

---

## Testing Email Setup

### Test 1: Django Shell Test
```bash
cd /path/to/server
python manage.py shell
```

```python
from django.core.mail import send_mail
from django.conf import settings

send_mail(
    'Test Email from Zzuhana',
    'This is a test email from Zzuhana e-commerce.',
    settings.DEFAULT_FROM_EMAIL,
    ['your-personal-email@gmail.com'],
    fail_silently=False,
)
```

### Test 2: Check DNS Records
```bash
# Check MX record
dig MX zzuhana.com

# Check SPF record
dig TXT zzuhana.com

# Check DKIM record
dig TXT default._domainkey.zzuhana.com
```

### Test 3: Online Tools
- [MXToolbox](https://mxtoolbox.com/) - Check MX, SPF, DKIM, DMARC
- [Mail-Tester](https://www.mail-tester.com/) - Test email deliverability

---

## Troubleshooting

### Email Not Sending
1. Check firewall allows port 587/465
2. Verify SMTP credentials
3. Check Django logs for errors

### Email Going to Spam
1. Verify SPF record is correct
2. Set up DKIM
3. Set up DMARC
4. Use consistent "From" address

### Connection Refused
1. Check if mail server is running in aPanel
2. Verify port is open: `telnet mail.zzuhana.com 587`
3. Check firewall rules

### Authentication Failed
1. Verify email/password in `.env`
2. Check if email account exists in aPanel
3. Try logging into webmail to verify credentials

---

## Quick Checklist

### aPanel Setup
- [ ] Mail domain created for zzuhana.com
- [ ] Email account noreply@zzuhana.com created
- [ ] DKIM key generated

### Cloudflare DNS
- [ ] MX record pointing to mail.zzuhana.com
- [ ] A record for mail subdomain (DNS only, not proxied)
- [ ] SPF TXT record added
- [ ] DKIM TXT record added
- [ ] DMARC TXT record added

### Server Configuration
- [ ] EMAIL_HOST set to mail.zzuhana.com
- [ ] EMAIL_HOST_USER set to noreply@zzuhana.com
- [ ] EMAIL_HOST_PASSWORD set
- [ ] DEFAULT_FROM_EMAIL set
- [ ] Test email sent successfully

---

## Current Server `.env` Email Section

For Gmail (current):
```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=hatg966@gmail.com
EMAIL_HOST_PASSWORD=your-16-char-app-password
DEFAULT_FROM_EMAIL=Zzuhana <noreply@zzuhana.com>
```

For aPanel Mail (professional):
```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mail.zzuhana.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@zzuhana.com
EMAIL_HOST_PASSWORD=your-email-password
DEFAULT_FROM_EMAIL=Zzuhana <noreply@zzuhana.com>
```

