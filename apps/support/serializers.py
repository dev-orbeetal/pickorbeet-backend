from rest_framework import serializers

from .models import Message
from .presence import online
from .profile import load_profile
from .services import customer_name, messages_for, order_card


class MessageSerializer(serializers.ModelSerializer):
    conversation_id = serializers.UUIDField(read_only=True)
    topic_label = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    order = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id',
            'conversation_id',
            'author',
            'body',
            'topic',
            'topic_label',
            'image',
            'order',
            'read_at',
            'created_at',
        ]

    def get_topic_label(self, message):
        return Message.TOPIC_LABELS.get(message.topic, '')

    def get_image(self, message):
        if not message.image:
            return ''
        return message.image.url

    def get_order(self, message):
        if message.order_id is None:
            return None
        return order_card(message.order)


def profile_payload():
    profile = load_profile()
    return {
        'display_name': profile.display_name,
        'reply_line': profile.reply_line,
        'avatar': profile.avatar.url if profile.avatar else '',
        'phone': profile.phone,
        'email': profile.email,
    }


def conversation_payload(conversation, *, include_customer=False):
    payload = {
        'id': str(conversation.id),
        'topic': conversation.topic,
        'topic_label': Message.TOPIC_LABELS.get(conversation.topic, ''),
        'agent_online': online(),
        'customer_unread': conversation.customer_unread,
        'staff_unread': conversation.staff_unread,
        'last_message_at': conversation.last_message_at,
        'profile': profile_payload(),
        'messages': MessageSerializer(messages_for(conversation), many=True).data,
    }
    if include_customer:
        customer = conversation.customer
        payload['customer_name'] = customer_name(customer)
        payload['customer_email'] = customer.email or ''
    return payload

