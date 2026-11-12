import logging

from django.conf import settings

from core.mailer import send_branded

logger = logging.getLogger(__name__)


def send_career_application_email(application):
    """Tell support a student applied. The CV and photo stay on the server."""
    try:
        return send_branded(
            f'New student application from {application.name}',
            'emails/career_application.html',
            {
                'preheader': f'{application.name} from {application.university} applied.',
                'applicant_name': application.name,
                'university': application.university,
                'department': application.department,
                'review_url': f'{settings.ADMIN_PANEL_URL.rstrip("/")}/career-applications',
                'footer_mode': 'support',
                'support_line': 'This note was sent because a student applied on the website.',
            },
            settings.SUPPORT_EMAIL,
        )
    except Exception:
        logger.exception('Career application email failed for %s', application.pk)
        return False
