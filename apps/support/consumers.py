"""Live support socket. Messages are saved over REST, then pushed here."""
import asyncio
import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Conversation
from .presence import join, leave
from .realtime import CUSTOMERS_GROUP, STAFF_GROUP, customer_group, publish_presence

STAFF_ROLES = {'seller', 'super_admin'}


def _customer_id(conversation_id):
    row = Conversation.objects.filter(pk=conversation_id).values_list('customer_id', flat=True).first()
    return row


def _conversation_id(user_id):
    return Conversation.objects.filter(customer_id=user_id).values_list('id', flat=True).first()


class SupportConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.groups_joined = []
        self.counts_presence = False
        self._pulse = None

    async def connect(self):
        user = self.scope.get('user')
        if user is None or not user.is_authenticated:
            await self.accept()
            await self.close(code=4401)
            return
        query = parse_qs(self.scope.get('query_string', b'').decode())
        audience = (query.get('audience') or ['customer'])[0]
        self.user = user
        self.staff = audience == 'staff'
        if self.staff and getattr(user, 'role', '') not in STAFF_ROLES:
            await self.accept()
            await self.close(code=4403)
            return
        if self.staff:
            await self.channel_layer.group_add(STAFF_GROUP, self.channel_name)
            self.groups_joined.append(STAFF_GROUP)
            self.counts_presence = True
            agent_online = await database_sync_to_async(join)(self.channel_name)
            self._pulse = asyncio.create_task(self._heartbeat())
        else:
            group = customer_group(user.id)
            await self.channel_layer.group_add(group, self.channel_name)
            await self.channel_layer.group_add(CUSTOMERS_GROUP, self.channel_name)
            self.groups_joined.extend([group, CUSTOMERS_GROUP])
            agent_online = await database_sync_to_async(_agent_online)()
        await self.accept()
        if self.staff:
            await database_sync_to_async(publish_presence)(agent_online)
        await self.send(text_data=json.dumps({'type': 'presence', 'agent_online': bool(agent_online)}))

    async def disconnect(self, code):
        if self._pulse is not None:
            self._pulse.cancel()
        for group in self.groups_joined:
            await self.channel_layer.group_discard(group, self.channel_name)
        self.groups_joined = []
        if self.counts_presence:
            self.counts_presence = False
            agent_online = await database_sync_to_async(leave)(self.channel_name)
            await database_sync_to_async(publish_presence)(agent_online)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return
        if data.get('type') != 'typing':
            return
        active = bool(data.get('active'))
        if self.staff:
            conversation_id = data.get('conversation_id')
            customer_id = await database_sync_to_async(_customer_id)(conversation_id)
            if customer_id is None:
                return
            await self.channel_layer.group_send(customer_group(customer_id), {
                'type': 'support.typing',
                'conversation_id': str(conversation_id),
                'active': active,
                'author': 'agent',
            })
            return
        conversation_id = await database_sync_to_async(_conversation_id)(self.user.id)
        if conversation_id is None:
            return
        await self.channel_layer.group_send(STAFF_GROUP, {
            'type': 'support.typing',
            'conversation_id': str(conversation_id),
            'active': active,
            'author': 'customer',
        })

    async def support_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message.created',
            'message': event['message'],
        }))

    async def support_read(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message.read',
            'conversation_id': event['conversation_id'],
            'author': event['author'],
            'read_at': event['read_at'],
        }))

    async def support_presence(self, event):
        await self.send(text_data=json.dumps({
            'type': 'presence',
            'agent_online': event['agent_online'],
        }))

    async def support_typing(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'conversation_id': event['conversation_id'],
            'active': event['active'],
            'author': event['author'],
        }))

    async def _heartbeat(self):
        try:
            while True:
                await asyncio.sleep(20)
                await database_sync_to_async(join)(self.channel_name)
        except asyncio.CancelledError:
            return


def _agent_online():
    from .presence import online

    return online()
