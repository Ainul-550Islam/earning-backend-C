"""
SMS Alert Service — Twilio/ShohoSMS for critical alerts
"""
import logging

logger = logging.getLogger(__name__)


class SMSAlertService:
    """Send SMS alerts via Twilio or ShohoSMS"""

    @staticmethod
    def send(notification, channel):
        try:
            config = channel.config
            provider = config.get('provider', 'twilio')
            to_number = notification.recipient
            message = notification.message[:160]  # SMS limit

            if provider == 'twilio':
                return SMSAlertService._send_twilio(config, to_number, message, channel)
            elif provider == 'shohosms':
                return SMSAlertService._send_shohosms(config, to_number, message, channel)
            else:
                logger.warning(f"Unknown SMS provider: {provider}")
                return False

        except Exception as e:
            logger.error(f"SMSAlertService error: {e}")
            channel.record_failure()
            return False

    @staticmethod
    def _send_twilio(config, to_number, message, channel):
        try:
            from twilio.rest import Client
            client = Client(config['account_sid'], config['auth_token'])
            client.messages.create(
                body=message,
                from_=config['from_number'],
                to=to_number
            )
            channel.record_success()
            logger.info(f"Twilio SMS sent to {to_number}")
            return True
        except ImportError:
            logger.error("twilio package not installed")
            channel.record_failure()
            return False
        except Exception as e:
            logger.error(f"Twilio error: {e}")
            channel.record_failure()
            return False

    @staticmethod
    def _send_shohosms(config, to_number, message, channel):
        try:
            import requests
            resp = requests.post(
                'https://api.shohosms.com/sms/send',
                json={
                    'api_key': config['api_key'],
                    'to': to_number,
                    'message': message,
                    'sender_id': config.get('sender_id', 'ALERT'),
                },
                timeout=10
            )
            resp.raise_for_status()
            channel.record_success()
            logger.info(f"ShohoSMS sent to {to_number}")
            return True
        except Exception as e:
            logger.error(f"ShohoSMS error: {e}")
            channel.record_failure()
            return False
