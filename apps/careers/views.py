from pathlib import Path

from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffUser
from core.pagination import AdminPagination

from .emails import send_career_application_email
from .models import CareerApplication
from .serializers import CareerApplicationSerializer, CareerApplicationSubmitSerializer

_IMAGE_TYPES = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.webp': 'image/webp',
}


class PublicCareerApplyView(APIView):
    """Public student application. No account, and no file URLs in the response."""

    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'career_apply'

    def post(self, request):
        serializer = CareerApplicationSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        send_career_application_email(application)
        return Response(
            {'message': 'Your application has been received. We will be in touch.'},
            status=status.HTTP_201_CREATED,
        )


class AdminCareerApplicationListView(generics.ListAPIView):
    serializer_class = CareerApplicationSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = AdminPagination

    def get_queryset(self):
        qs = CareerApplication.objects.all()
        status_value = (self.request.query_params.get('status') or '').strip()
        if status_value in dict(CareerApplication.STATUS_CHOICES):
            qs = qs.filter(status=status_value)
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
                | Q(student_id__icontains=search)
                | Q(university__icontains=search)
            )
        return qs


class AdminCareerApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CareerApplicationSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = CareerApplication.objects.all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status == 'new':
            instance.status = 'reviewing'
            instance.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(instance).data)


class CareerApplicationFileView(APIView):
    """Stream a CV or portrait to staff. The file is not on a public URL."""

    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request, pk, kind):
        application = get_object_or_404(CareerApplication, pk=pk)
        if kind == 'cv':
            field = application.cv
            content_type = 'application/pdf'
            filename = 'cv.pdf'
            as_attachment = True
        elif kind == 'picture':
            field = application.picture
            ext = Path(field.name).suffix.lower() if field else ''
            content_type = _IMAGE_TYPES.get(ext, 'application/octet-stream')
            filename = f'photo{ext}' if ext in _IMAGE_TYPES else 'photo'
            as_attachment = False
        else:
            raise Http404('File not found.')
        if not field:
            raise Http404('File not found.')
        response = FileResponse(
            field.open('rb'),
            content_type=content_type,
            as_attachment=as_attachment,
            filename=filename,
        )
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
