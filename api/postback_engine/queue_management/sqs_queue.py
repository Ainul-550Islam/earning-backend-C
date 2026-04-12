"""
queue_management/sqs_queue.py
───────────────────────────────
AWS SQS queue adapter for Postback Engine.
Used for cloud-native deployments on AWS.
SQS provides: managed queuing, auto-scaling, dead-letter queues, FIFO options.

Requires: pip install boto3
Configure in settings:
    AWS_SQS_QUEUE_URL  = "https://sqs.us-east-1.amazonaws.com/123456/postback-engine"
    AWS_SQS_DLQ_URL   = "https://sqs.us-east-1.amazonaws.com/123456/postback-engine-dlq"
    AWS_REGION_NAME   = "us-east-1"
    AWS_ACCESS_KEY_ID  = "..."  (or use IAM role)
    AWS_SECRET_ACCESS_KEY = "..."
"""
from __future__ import annotations
import json
import logging
from typing import Optional, List, Callable

logger = logging.getLogger(__name__)


class SQSQueue:
    """
    AWS SQS queue adapter for PostbackEngine.
    Falls back gracefully if boto3 or SQS is not configured.
    """

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client:
            return self._client
        try:
            import boto3
            from django.conf import settings
            region = getattr(settings, "AWS_REGION_NAME", "us-east-1")
            self._client = boto3.client("sqs", region_name=region)
            return self._client
        except ImportError:
            logger.warning("SQS: boto3 not installed. Install with: pip install boto3")
            return None
        except Exception as exc:
            logger.warning("SQS: client init failed: %s", exc)
            return None

    def _get_queue_url(self) -> str:
        from django.conf import settings
        return getattr(settings, "AWS_SQS_QUEUE_URL", "")

    def _get_dlq_url(self) -> str:
        from django.conf import settings
        return getattr(settings, "AWS_SQS_DLQ_URL", "")

    def publish(self, data: dict, delay_seconds: int = 0, dedup_id: str = "") -> bool:
        """
        Send a message to SQS.
        Returns True on success.
        """
        client = self._get_client()
        queue_url = self._get_queue_url()
        if not client or not queue_url:
            return False
        try:
            kwargs = {
                "QueueUrl":    queue_url,
                "MessageBody": json.dumps(data, default=str),
                "DelaySeconds": min(delay_seconds, 900),  # SQS max = 900s
            }
            if dedup_id:
                kwargs["MessageDeduplicationId"] = dedup_id
                kwargs["MessageGroupId"] = data.get("network_key", "default")
            client.send_message(**kwargs)
            return True
        except Exception as exc:
            logger.warning("SQS.publish failed: %s", exc)
            return False

    def publish_batch(self, messages: List[dict]) -> int:
        """
        Send up to 10 messages in a batch (SQS limit).
        Returns count published.
        """
        client = self._get_client()
        queue_url = self._get_queue_url()
        if not client or not queue_url:
            return 0
        count = 0
        for i in range(0, len(messages), 10):
            batch = messages[i:i + 10]
            entries = [
                {"Id": str(j), "MessageBody": json.dumps(msg, default=str)}
                for j, msg in enumerate(batch)
            ]
            try:
                resp = client.send_message_batch(QueueUrl=queue_url, Entries=entries)
                count += len(resp.get("Successful", []))
            except Exception as exc:
                logger.warning("SQS.publish_batch chunk failed: %s", exc)
        return count

    def consume(
        self,
        callback: Callable,
        max_messages: int = 10,
        wait_seconds: int = 5,
    ) -> int:
        """
        Poll SQS for messages and call callback for each.
        Returns count successfully processed.
        """
        client = self._get_client()
        queue_url = self._get_queue_url()
        if not client or not queue_url:
            return 0
        count = 0
        try:
            resp = client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=min(max_messages, 10),
                WaitTimeSeconds=wait_seconds,
                AttributeNames=["All"],
            )
            for msg in resp.get("Messages", []):
                receipt = msg["ReceiptHandle"]
                try:
                    data = json.loads(msg["Body"])
                    callback(data)
                    client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
                    count += 1
                except Exception as exc:
                    logger.error("SQS: message processing failed: %s", exc)
                    # Message will become visible again after visibility timeout
        except Exception as exc:
            logger.warning("SQS.consume error: %s", exc)
        return count

    def depth(self) -> dict:
        """Return queue depth (visible + not visible + delayed messages)."""
        client = self._get_client()
        queue_url = self._get_queue_url()
        if not client or not queue_url:
            return {}
        try:
            resp = client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=[
                    "ApproximateNumberOfMessages",
                    "ApproximateNumberOfMessagesNotVisible",
                    "ApproximateNumberOfMessagesDelayed",
                ],
            )
            attrs = resp.get("Attributes", {})
            return {
                "visible":     int(attrs.get("ApproximateNumberOfMessages", 0)),
                "in_flight":   int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0)),
                "delayed":     int(attrs.get("ApproximateNumberOfMessagesDelayed", 0)),
            }
        except Exception as exc:
            logger.warning("SQS.depth failed: %s", exc)
            return {}


sqs_queue = SQSQueue()
