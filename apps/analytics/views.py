import secrets

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsStaffUser

from .authentication import OptionalJWTAuthentication
from .ingest import browser_user_agent, is_prefetch, record_collect
from .reports import breakdown, customers, funnel, live_feed, overview, parse_range, timeline
from .serializers import CollectSerializer
from .throttles import AnalyticsCollectThrottle


def ingest_authorized(request):
    secret = getattr(settings, 'ANALYTICS_INGEST_SECRET', '') or ''
    provided = request.headers.get('X-Analytics-Secret') or ''
    if secret:
        return secrets.compare_digest(provided, secret)
    return bool(settings.DEBUG)


def geo_trusted(request):
    secret = getattr(settings, 'ANALYTICS_INGEST_SECRET', '') or ''
    provided = request.headers.get('X-Analytics-Secret') or ''
    return bool(secret) and secrets.compare_digest(provided, secret)


class CollectView(APIView):
    authentication_classes = [OptionalJWTAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [AnalyticsCollectThrottle]

    def post(self, request):
        if not ingest_authorized(request):
            return Response(status=403)
        if is_prefetch(request):
            return Response(status=204)
        serializer = CollectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data['type'] == 'pageview':
            errors = {}
            if not data.get('session_id'):
                errors['session_id'] = 'This field is required.'
            if not (data.get('path') or '').strip():
                errors['path'] = 'This field is required.'
            if errors:
                raise ValidationError(errors)
        elif data.get('duration_ms') is None:
            raise ValidationError({'duration_ms': 'This field is required.'})

        user = request.user if request.user.is_authenticated else None
        record_collect(
            data,
            user=user,
            user_agent=browser_user_agent(request),
            trust_geo=geo_trusted(request),
        )
        return Response(status=204)


class StaffAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsStaffUser]

    def window(self, request):
        start, end, _start_dt, _end_dt = parse_range(request.query_params)
        return start, end


class OverviewView(StaffAnalyticsView):
    def get(self, request):
        start, end = self.window(request)
        return Response(overview(start, end))


class BreakdownView(StaffAnalyticsView):
    def get(self, request):
        start, end = self.window(request)
        return Response(breakdown(start, end, request.query_params.get('dimension') or ''))


class CustomerListView(StaffAnalyticsView):
    def get(self, request):
        start, end = self.window(request)
        query = (request.query_params.get('q') or '').strip()
        return Response(customers(start, end, query))


class CustomerTimelineView(StaffAnalyticsView):
    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id, role='customer')
        return Response(timeline(user))


class LiveView(StaffAnalyticsView):
    def get(self, request):
        return Response(live_feed())


class FunnelView(StaffAnalyticsView):
    def get(self, request):
        start, end = self.window(request)
        return Response(funnel(start, end))
