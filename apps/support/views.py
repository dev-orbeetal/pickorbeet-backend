"""Customer chat and the staff inbox. Each side only sees its own thread."""
from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404
from PIL import Image, UnidentifiedImageError
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSeller

from .models import Conversation, Message
from .presence import online
from .serializers import MessageSerializer, conversation_payload
from .services import customer_name, mark_read, open_conversation, post_customer_message, post_staff_reply

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_BODY = 2000


class ConversationView(APIView):
    """The signed-in customer's thread, including the greeting on the first open."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversation = open_conversation(request.user)
        mark_read(conversation, by_staff=False)
        return Response(conversation_payload(conversation))


class MessageCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        body = (request.data.get('body') or '').strip()
        topic = (request.data.get('topic') or '').strip()
        order_number = (request.data.get('order_number') or '').strip()
        image = request.FILES.get('image')
        if topic and topic not in Message.TOPIC_LABELS:
            return Response({'topic': ['Choose a support topic.']}, status=status.HTTP_400_BAD_REQUEST)
        if len(body) > MAX_BODY:
            return Response({'body': ['That message is too long.']}, status=status.HTTP_400_BAD_REQUEST)
        if not body and not topic and image is None:
            return Response({'body': ['Write a message or choose a topic.']}, status=status.HTTP_400_BAD_REQUEST)
        if image is not None:
            error = _image_error(image)
            if error:
                return Response({'image': [error]}, status=status.HTTP_400_BAD_REQUEST)
        _conversation, message = post_customer_message(
            request.user,
            body=body,
            topic=topic,
            order_number=order_number,
            image=image,
        )
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)


class CustomerReadView(APIView):
    """Mark agent replies seen while the chat stays open."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        conversation = Conversation.objects.filter(customer=request.user).first()
        if conversation is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        mark_read(conversation, by_staff=False)
        return Response({'customer_unread': 0})


class StaffInboxView(APIView):
    permission_classes = [IsSeller]

    def get(self, request):
        latest = Message.objects.filter(conversation=OuterRef('pk')).order_by('-created_at')
        rows = (
            Conversation.objects.select_related('customer')
            .annotate(
                preview_body=Subquery(latest.values('body')[:1]),
                preview_topic=Subquery(latest.values('topic')[:1]),
            )
            .order_by('-last_message_at', '-created_at')
        )
        results = []
        for row in rows[:200]:
            preview = (row.preview_body or '').strip()
            if not preview:
                preview = Message.TOPIC_LABELS.get(row.preview_topic or '', '')
            results.append({
                'id': str(row.id),
                'customer_name': customer_name(row.customer),
                'customer_email': row.customer.email or '',
                'topic': row.topic,
                'topic_label': Message.TOPIC_LABELS.get(row.topic, ''),
                'preview': preview,
                'staff_unread': row.staff_unread,
                'last_message_at': row.last_message_at,
            })
        return Response({'agent_online': online(), 'results': results})


class StaffThreadView(APIView):
    permission_classes = [IsSeller]

    def get(self, request, pk):
        conversation = get_object_or_404(
            Conversation.objects.select_related('customer'),
            pk=pk,
        )
        mark_read(conversation, by_staff=True)
        return Response(conversation_payload(conversation, include_customer=True))


class StaffReadView(APIView):
    permission_classes = [IsSeller]

    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk)
        mark_read(conversation, by_staff=True)
        return Response({'staff_unread': 0})


class StaffReplyView(APIView):
    permission_classes = [IsSeller]

    def post(self, request, pk):
        conversation = get_object_or_404(
            Conversation.objects.select_related('customer'),
            pk=pk,
        )
        body = (request.data.get('body') or '').strip()
        if not body:
            return Response({'body': ['Write a reply.']}, status=status.HTTP_400_BAD_REQUEST)
        if len(body) > MAX_BODY:
            return Response({'body': ['That reply is too long.']}, status=status.HTTP_400_BAD_REQUEST)
        message = post_staff_reply(request.user, conversation, body)
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)


def _image_error(upload):
    if upload.size > MAX_IMAGE_BYTES:
        return 'Photos need to be under 5 MB.'
    try:
        image = Image.open(upload)
        image.verify()
    except (UnidentifiedImageError, OSError):
        return 'Choose a JPEG, PNG, or WebP photo.'
    upload.seek(0)
    return ''
