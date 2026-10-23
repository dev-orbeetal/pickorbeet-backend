"""Inbox and device registration. Every row is scoped to the signed-in user."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .delivery import publish_read
from .models import Device, Notification
from .serializers import DeviceRegisterSerializer, DeviceSerializer, NotificationSerializer


class NotificationListView(generics.ListAPIView):
    """Newest inbox rows for the current user. ``?unread=1`` keeps unread only."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Notification.objects.filter(recipient=self.request.user)
        if self.request.query_params.get('unread') == '1':
            queryset = queryset.filter(read_at__isnull=True)
        return queryset


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(recipient=request.user, read_at__isnull=True).count()
        return Response({'unread_count': count})


class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=['read_at'])
            user_id = request.user.id
            transaction.on_commit(lambda: publish_read(user_id))
        return Response(NotificationSerializer(notification).data)


class MarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(
            read_at=timezone.now(),
        )
        user_id = request.user.id
        transaction.on_commit(lambda: publish_read(user_id))
        return Response({'unread_count': 0})


class DeviceRegisterView(APIView):
    """Upsert this phone and detach it from any previous account."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'device_register'

    def put(self, request):
        serializer = DeviceRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']
        platform = serializer.validated_data['platform']
        device_id = serializer.validated_data['device_id']

        with transaction.atomic():
            Device.objects.filter(device_id=device_id).exclude(user=request.user).update(
                is_active=False,
                token='',
            )
            Device.objects.filter(token=token).exclude(user=request.user, device_id=device_id).update(
                is_active=False,
                token='',
            )
            device, _created = Device.objects.update_or_create(
                user=request.user,
                device_id=device_id,
                defaults={
                    'token': token,
                    'platform': platform,
                    'is_active': True,
                    'last_seen': timezone.now(),
                },
            )
        return Response(DeviceSerializer(device).data)


class DeviceUnregisterView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, device_id):
        Device.objects.filter(user=request.user, device_id=device_id).update(
            is_active=False,
            token='',
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
