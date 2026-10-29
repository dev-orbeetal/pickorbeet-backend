from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed


class OptionalJWTAuthentication(JWTAuthentication):
    """Attach a customer when the token is valid, and stay anonymous when it is not."""

    def authenticate(self, request):
        if self.get_header(request) is None:
            return None
        try:
            return super().authenticate(request)
        except AuthenticationFailed:
            return None
