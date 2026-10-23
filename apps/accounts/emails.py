"""Account mail. Layout lives in templates/emails; this module only fills it."""
from core.mailer import frontend, send_branded


def _digits(otp_code):
    return [char for char in str(otp_code) if char.isdigit()][:6]


def send_otp_email(user, otp_code):
    """Send the 6-digit verification code. It expires in 10 minutes."""
    digits = _digits(otp_code)
    send_branded(
        'Your PickOrbeet verification code',
        'emails/otp.html',
        {
            'preheader': f'Your verification code is {"".join(digits)}. It expires in 10 minutes.',
            'otp_digits': digits,
            'footer_mode': 'support',
            'support_line': 'Need help? Contact us and we will sort it out.',
        },
        user.email,
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


def send_password_reset_email(user, reset_url):
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
        user.email,
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
