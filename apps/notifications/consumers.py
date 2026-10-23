"""Live inbox socket. History is loaded over REST, not replayed here."""
import json

from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    group = None

    async def connect(self):
        user = self.scope.get('user')
        if user is None or not user.is_authenticated:
            await self.accept()
            await self.close(code=4401)
            return
        self.group = f'notifications_{user.id}'
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if self.group:
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def notification_created(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification.created',
            'notification': event['notification'],
            'unread_count': event['unread_count'],
        }))

    async def notification_read(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification.read',
            'unread_count': event['unread_count'],
        }))
