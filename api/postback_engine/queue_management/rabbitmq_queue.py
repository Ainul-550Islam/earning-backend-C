"""
queue_management/rabbitmq_queue.py
────────────────────────────────────
RabbitMQ queue adapter for Postback Engine.
Alternative to Redis queue for high-reliability message delivery.
RabbitMQ provides: message persistence, dead-letter exchanges, acknowledgements.

Requires: pip install pika
Configure in settings:
    RABBITMQ_URL = "amqp://user:pass@localhost:5672/vhost"
"""
from __future__ import annotations
import json
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

_QUEUE_NAME = "postback_engine"
_DEAD_LETTER_QUEUE = "postback_engine_dlq"
_EXCHANGE = ""


class RabbitMQQueue:
    """
    RabbitMQ-backed queue for postback processing.
    Falls back gracefully if RabbitMQ is not configured.
    """

    def __init__(self):
        self._connection = None
        self._channel = None

    def _get_channel(self):
        """Lazy connection — connect on first use."""
        if self._channel and not self._channel.is_closed:
            return self._channel
        try:
            import pika
            from django.conf import settings
            url = getattr(settings, "RABBITMQ_URL", "")
            if not url:
                return None
            params = pika.URLParameters(url)
            self._connection = pika.BlockingConnection(params)
            self._channel = self._connection.channel()
            # Declare queues
            self._channel.queue_declare(
                queue=_QUEUE_NAME,
                durable=True,
                arguments={"x-dead-letter-exchange": "", "x-dead-letter-routing-key": _DEAD_LETTER_QUEUE},
            )
            self._channel.queue_declare(queue=_DEAD_LETTER_QUEUE, durable=True)
            return self._channel
        except ImportError:
            logger.warning("RabbitMQ: pika not installed. Install with: pip install pika")
            return None
        except Exception as exc:
            logger.warning("RabbitMQ: connection failed: %s", exc)
            return None

    def publish(self, data: dict, priority: int = 0) -> bool:
        """Publish a message to RabbitMQ. Returns True on success."""
        try:
            import pika
            channel = self._get_channel()
            if not channel:
                return False
            body = json.dumps(data, default=str)
            channel.basic_publish(
                exchange=_EXCHANGE,
                routing_key=_QUEUE_NAME,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=2,     # Persistent message
                    priority=min(priority, 9),
                ),
            )
            return True
        except Exception as exc:
            logger.warning("RabbitMQ.publish failed: %s", exc)
            return False

    def consume(self, callback, limit: int = 50) -> int:
        """Consume up to `limit` messages and call callback for each."""
        channel = self._get_channel()
        if not channel:
            return 0
        count = 0
        try:
            for method, properties, body in channel.consume(
                _QUEUE_NAME, auto_ack=False, inactivity_timeout=1
            ):
                if method is None or count >= limit:
                    break
                try:
                    data = json.loads(body)
                    callback(data)
                    channel.basic_ack(method.delivery_tag)
                    count += 1
                except Exception as exc:
                    logger.error("RabbitMQ: message processing failed: %s", exc)
                    channel.basic_nack(method.delivery_tag, requeue=False)
        except Exception as exc:
            logger.warning("RabbitMQ.consume error: %s", exc)
        finally:
            try:
                channel.cancel()
            except Exception:
                pass
        return count

    def depth(self) -> int:
        """Return approximate queue depth."""
        try:
            channel = self._get_channel()
            if not channel:
                return 0
            result = channel.queue_declare(_QUEUE_NAME, passive=True, durable=True)
            return result.method.message_count
        except Exception:
            return 0

    def close(self) -> None:
        try:
            if self._connection and not self._connection.is_closed:
                self._connection.close()
        except Exception:
            pass


rabbitmq_queue = RabbitMQQueue()
