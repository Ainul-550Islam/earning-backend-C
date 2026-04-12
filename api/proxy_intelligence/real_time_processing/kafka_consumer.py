"""Kafka Consumer — consumes IP events from Kafka topics."""
import logging
logger = logging.getLogger(__name__)

class KafkaIPEventConsumer:
    """
    Consumes IP intelligence events from a Kafka topic.
    Requires: pip install kafka-python

    Configure in settings.py:
        KAFKA_BOOTSTRAP_SERVERS = ['localhost:9092']
        KAFKA_IP_EVENTS_TOPIC = 'ip-events'
    """

    def __init__(self, topic: str = None, group_id: str = 'pi-consumer',
                 tenant=None):
        self.topic = topic or 'ip-events'
        self.group_id = group_id
        self.tenant = tenant
        self.consumer = None

    def start(self):
        try:
            from kafka import KafkaConsumer
            from django.conf import settings
            import json
            self.consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=getattr(settings, 'KAFKA_BOOTSTRAP_SERVERS', ['localhost:9092']),
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True,
            )
            logger.info(f"Kafka consumer started: topic={self.topic}")
        except ImportError:
            logger.warning("kafka-python not installed. Run: pip install kafka-python")

    def consume(self, max_messages: int = 100):
        if not self.consumer:
            self.start()
        if not self.consumer:
            return

        from .stream_processor import StreamProcessor
        processor = StreamProcessor(self.tenant)
        count = 0
        for message in self.consumer:
            try:
                processor.process_event(message.value)
                count += 1
                if count >= max_messages:
                    break
            except Exception as e:
                logger.error(f"Kafka message processing failed: {e}")

    def stop(self):
        if self.consumer:
            self.consumer.close()
            self.consumer = None
