"""
queue_management/kafka_queue.py
────────────────────────────────
Apache Kafka queue adapter for Postback Engine.
Used for ultra-high-throughput postback processing (millions/day).
Kafka provides: ordered delivery, replay, consumer groups, partitioning.

Requires: pip install kafka-python
Configure in settings:
    KAFKA_BOOTSTRAP_SERVERS = ["localhost:9092"]
    KAFKA_POSTBACK_TOPIC = "postback_engine_events"
"""
from __future__ import annotations
import json
import logging
from typing import Optional, List, Callable

logger = logging.getLogger(__name__)

_DEFAULT_TOPIC     = "postback_engine"
_DEFAULT_GROUP_ID  = "postback_engine_consumer"


class KafkaQueue:
    """
    Kafka-backed queue for ultra-high-throughput postback processing.
    Falls back gracefully if Kafka is not configured.
    """

    def __init__(self):
        self._producer = None
        self._consumer = None

    def _get_bootstrap_servers(self) -> List[str]:
        from django.conf import settings
        return getattr(settings, "KAFKA_BOOTSTRAP_SERVERS", []) or []

    def _get_topic(self) -> str:
        from django.conf import settings
        return getattr(settings, "KAFKA_POSTBACK_TOPIC", _DEFAULT_TOPIC)

    def _get_producer(self):
        if self._producer:
            return self._producer
        servers = self._get_bootstrap_servers()
        if not servers:
            return None
        try:
            from kafka import KafkaProducer
            self._producer = KafkaProducer(
                bootstrap_servers=servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                acks="all",             # Wait for all replicas to acknowledge
                retries=3,
                max_block_ms=5000,      # 5 second publish timeout
            )
            return self._producer
        except ImportError:
            logger.warning("Kafka: kafka-python not installed. Install with: pip install kafka-python")
            return None
        except Exception as exc:
            logger.warning("Kafka: producer init failed: %s", exc)
            return None

    def publish(self, data: dict, partition_key: str = "") -> bool:
        """
        Publish a message to Kafka.
        partition_key: use network_key or lead_id to ensure ordering per key.
        """
        producer = self._get_producer()
        if not producer:
            return False
        try:
            key = partition_key.encode("utf-8") if partition_key else None
            future = producer.send(self._get_topic(), value=data, key=key)
            future.get(timeout=5)     # Wait for acknowledgement
            return True
        except Exception as exc:
            logger.warning("Kafka.publish failed: %s", exc)
            return False

    def publish_batch(self, messages: List[dict]) -> int:
        """Publish multiple messages. Returns count published."""
        producer = self._get_producer()
        if not producer:
            return 0
        count = 0
        for msg in messages:
            try:
                producer.send(self._get_topic(), value=msg)
                count += 1
            except Exception as exc:
                logger.warning("Kafka.publish_batch item failed: %s", exc)
        try:
            producer.flush(timeout=10)
        except Exception:
            pass
        return count

    def consume(
        self,
        callback: Callable,
        group_id: str = _DEFAULT_GROUP_ID,
        max_messages: int = 100,
        timeout_ms: int = 5000,
    ) -> int:
        """Consume messages from Kafka and call callback for each."""
        servers = self._get_bootstrap_servers()
        if not servers:
            return 0
        count = 0
        try:
            from kafka import KafkaConsumer
            consumer = KafkaConsumer(
                self._get_topic(),
                bootstrap_servers=servers,
                group_id=group_id,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                consumer_timeout_ms=timeout_ms,
                max_poll_records=max_messages,
            )
            for msg in consumer:
                if count >= max_messages:
                    break
                try:
                    callback(msg.value)
                    consumer.commit()
                    count += 1
                except Exception as exc:
                    logger.error("Kafka: message processing failed: %s", exc)
            consumer.close()
        except ImportError:
            logger.warning("Kafka: kafka-python not installed.")
        except Exception as exc:
            logger.warning("Kafka.consume error: %s", exc)
        return count

    def close(self) -> None:
        try:
            if self._producer:
                self._producer.close()
        except Exception:
            pass


kafka_queue = KafkaQueue()
