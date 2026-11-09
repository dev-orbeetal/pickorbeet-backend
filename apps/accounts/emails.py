"""Account mail. Layout lives in templates/emails; this module only fills it."""
from core.mailer import frontend, send_branded


def _digits(otp_code):
    return [char for char in str(otp_code) if char.isdigit()][:6]


def send_otp_email(user, otp_code):
    """Send the 6-digit verification code. It expires in 10 minutes."""
    _send_code(
        user.email,
        otp_code,
        'Your PickOrbeet verification code',
        f'Your verification code is {_joined(otp_code)}. It expires in 10 minutes.',
    )


_SECURITY_COPY = {
    'login_2fa': (
        'Your PickOrbeet sign-in code',
        'Your sign-in code',
        'Enter this code to finish signing in to PickOrbeet.',
        "If you didn't try to sign in, you can ignore this email.",
    ),
    'enable_2fa': (
        'Turn on two-factor authentication',
        'Turn on two-factor authentication',
        'Enter this code to turn on email verification for your PickOrbeet account.',
        "If you didn't request this, you can ignore this email.",
    ),
    'disable_2fa': (
        'Turn off two-factor authentication',
        'Turn off two-factor authentication',
        'Enter this code to turn off email verification for your PickOrbeet account.',
        "If you didn't request this, you can ignore this email.",
    ),
    'recovery_email': (
        'Confirm your recovery email',
        'Confirm your recovery email',
        'Enter this code to save this address for PickOrbeet account recovery.',
        "If you didn't request this, you can ignore this email.",
    ),
}


def send_security_code_email(user, otp_code, purpose, to):
    """Email a 6-digit security code. The body explains the purpose."""
    subject, headline, intro, ignore = _SECURITY_COPY[purpose]
    digits = _digits(otp_code)
    joined = ''.join(digits)
    send_branded(
        subject,
        'emails/otp.html',
        {
            'preheader': f'Your code is {joined}. It expires in 10 minutes.',
            'otp_digits': digits,
            'headline': headline,
            'intro': intro,
            'ignore_line': ignore,
            'footer_mode': 'support',
            'support_line': 'Need help? Contact us and we will sort it out.',
        },
        to,
    )


def _joined(otp_code):
    return ''.join(_digits(otp_code))


def _send_code(recipient, otp_code, subject, preheader):
    send_branded(
        subject,
        'emails/otp.html',
        {
            'preheader': preheader,
            'otp_digits': _digits(otp_code),
            'footer_mode': 'support',
            'support_line': 'Need help? Contact us and we will sort it out.',
        },
        recipient,
    )


def send_welcome_email(user):
    """Welcome a customer after they verify, or after Google sign-up."""
    send_branded(
        'Welcome to PickOrbeet',
        'emails/welcome.html',
        {
            'preheader': 'Glad to have you with us. Shop your favorite products at the best prices.',
            'footer_mode': 'split',
        },
        user.email,
    )


def send_google_welcome_email(user):
    """Google sign-ups use the same welcome card as email sign-ups."""
    send_welcome_email(user)


def send_password_reset_email(user, reset_url, to=None):
    """Password reset link. The token itself expires in one hour."""
    send_branded(
        'Reset your PickOrbeet password',
        'emails/password_reset.html',
        {
            'preheader': 'Reset your PickOrbeet password. This link expires in 1 hour.',
            'reset_url': reset_url,
            'footer_mode': 'support',
            'support_line': 'Need help? Contact us at the address below.',
        },
        to or user.email,
    )


def send_password_changed_email(user):
    """Confirm a password change."""
    send_branded(
        'Your PickOrbeet password was changed',
        'emails/password_changed.html',
        {
            'preheader': 'Your PickOrbeet password was changed.',
            'forgot_url': frontend('forgot-password'),
            'footer_mode': 'support',
            'support_line': 'Need help? Contact us at the address below.',
        },
        user.email,
    )
