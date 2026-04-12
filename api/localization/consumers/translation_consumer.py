# consumers/translation_consumer.py
"""
Django Channels WebSocket Consumer — Real-time translation collaboration.
Phrase.com / Lokalise real-time collab equivalent।

Setup:
  pip install channels channels-redis
  CHANNEL_LAYERS = {'default': {'BACKEND': 'channels_redis.core.RedisChannelLayer', 'CONFIG': {'hosts': [('localhost', 6379)]}}}
  ASGI_APPLICATION = 'api.asgi.application'

Frontend usage:
  const ws = new WebSocket('ws://localhost:8000/ws/localization/translations/bn/');
  ws.onmessage = (e) => { const data = JSON.parse(e.data); console.log(data); }
  ws.send(JSON.stringify({type: 'start_editing', key: 'offer.title'}))
"""
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from channels.generic.websocket import AsyncWebsocketConsumer
    from channels.db import database_sync_to_async
    import asyncio

    class TranslationCollabConsumer(AsyncWebsocketConsumer):
        """
        Real-time translation collaboration consumer।
        Multiple translators একই language-এ simultaneously কাজ করতে পারে।

        Message types:
          → start_editing: {type, key} — translator starts editing a key
          → stop_editing:  {type, key} — translator stops editing
          → value_update:  {type, key, value} — live typing preview
          → save_translation: {type, key, value} — save to DB
          ← editing_status: {type, key, editor, language}
          ← translation_saved: {type, key, value, editor}
          ← user_list: {type, users: [...]}
        """

        async def connect(self):
            self.language = self.scope['url_route']['kwargs'].get('language', 'en')
            self.room_name = f"translation_{self.language}"
            self.user = self.scope.get('user')
            self.username = getattr(self.user, 'email', 'anonymous') if self.user else 'anonymous'

            # Join language room
            await self.channel_layer.group_add(self.room_name, self.channel_name)
            await self.accept()

            # Notify others
            await self.channel_layer.group_send(self.room_name, {
                'type': 'user_joined',
                'username': self.username,
                'language': self.language,
            })

            # Send current editing status
            await self.send_user_list()
            logger.info(f"WS connect: {self.username} joined {self.language} room")

        async def disconnect(self, close_code):
            # Notify others
            await self.channel_layer.group_send(self.room_name, {
                'type': 'user_left',
                'username': self.username,
                'language': self.language,
            })
            await self.channel_layer.group_discard(self.room_name, self.channel_name)
            logger.info(f"WS disconnect: {self.username} left {self.language} room")

        async def receive(self, text_data):
            """Client থেকে message receive করে"""
            try:
                data = json.loads(text_data)
                msg_type = data.get('type', '')

                if msg_type == 'start_editing':
                    await self.handle_start_editing(data)
                elif msg_type == 'stop_editing':
                    await self.handle_stop_editing(data)
                elif msg_type == 'value_update':
                    await self.handle_value_update(data)
                elif msg_type == 'save_translation':
                    await self.handle_save(data)
                elif msg_type == 'ping':
                    await self.send(text_data=json.dumps({'type': 'pong', 'timestamp': datetime.now().isoformat()}))

            except json.JSONDecodeError:
                await self.send(text_data=json.dumps({'type': 'error', 'message': 'Invalid JSON'}))
            except Exception as e:
                logger.error(f"WS receive error: {e}")

        async def handle_start_editing(self, data):
            """Key edit শুরু হলে সবাইকে notify করে"""
            key = data.get('key', '')
            await self.channel_layer.group_send(self.room_name, {
                'type': 'editing_status',
                'key': key,
                'editor': self.username,
                'language': self.language,
                'action': 'started',
                'timestamp': datetime.now().isoformat(),
            })

        async def handle_stop_editing(self, data):
            key = data.get('key', '')
            await self.channel_layer.group_send(self.room_name, {
                'type': 'editing_status',
                'key': key,
                'editor': self.username,
                'language': self.language,
                'action': 'stopped',
                'timestamp': datetime.now().isoformat(),
            })

        async def handle_value_update(self, data):
            """Live typing — অন্য translators দেখতে পায় কী টাইপ হচ্ছে"""
            await self.channel_layer.group_send(self.room_name, {
                'type': 'live_value',
                'key': data.get('key', ''),
                'value': data.get('value', ''),
                'editor': self.username,
                'language': self.language,
            })

        async def handle_save(self, data):
            """Translation save করে DB-তে এবং সবাইকে notify করে"""
            key = data.get('key', '')
            value = data.get('value', '')
            if not key or not value:
                return

            success = await self.save_translation_db(key, value)
            await self.channel_layer.group_send(self.room_name, {
                'type': 'translation_saved',
                'key': key,
                'value': value,
                'editor': self.username,
                'language': self.language,
                'success': success,
                'timestamp': datetime.now().isoformat(),
            })

        @database_sync_to_async
        def save_translation_db(self, key: str, value: str) -> bool:
            """DB-তে translation save করে (sync → async wrapper)"""
            try:
                from ..models.core import Language, Translation, TranslationKey
                lang = Language.objects.filter(code=self.language).first()
                tkey = TranslationKey.objects.filter(key=key).first()
                if not lang or not tkey:
                    return False
                Translation.objects.update_or_create(
                    key=tkey, language=lang,
                    defaults={
                        'value': value,
                        'source': 'manual',
                        'is_approved': False,
                    }
                )
                return True
            except Exception as e:
                logger.error(f"WS save_translation_db failed: {e}")
                return False

        async def send_user_list(self):
            """Active users list পাঠায়"""
            await self.send(text_data=json.dumps({
                'type': 'connected',
                'language': self.language,
                'username': self.username,
                'timestamp': datetime.now().isoformat(),
            }))

        # ── Channel layer message handlers ──────────────────────────
        # These are called when group_send messages arrive

        async def editing_status(self, event):
            await self.send(text_data=json.dumps({
                'type': 'editing_status',
                'key': event['key'],
                'editor': event['editor'],
                'language': event['language'],
                'action': event.get('action', ''),
                'timestamp': event.get('timestamp', ''),
            }))

        async def live_value(self, event):
            # Don't send back to the sender
            if event.get('editor') != self.username:
                await self.send(text_data=json.dumps({
                    'type': 'live_value',
                    'key': event['key'],
                    'value': event['value'],
                    'editor': event['editor'],
                }))

        async def translation_saved(self, event):
            await self.send(text_data=json.dumps({
                'type': 'translation_saved',
                'key': event['key'],
                'value': event['value'],
                'editor': event['editor'],
                'language': event['language'],
                'success': event.get('success', False),
                'timestamp': event.get('timestamp', ''),
            }))

        async def user_joined(self, event):
            await self.send(text_data=json.dumps({
                'type': 'user_joined',
                'username': event['username'],
                'language': event['language'],
            }))

        async def user_left(self, event):
            await self.send(text_data=json.dumps({
                'type': 'user_left',
                'username': event['username'],
            }))


except ImportError:
    # Django Channels not installed — provide fallback
    logger.warning("Django Channels not installed. Install: pip install channels channels-redis")

    class TranslationCollabConsumer:
        """Placeholder — install channels to enable WebSocket"""
        pass
