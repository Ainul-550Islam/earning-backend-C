# api/promotions/utils/telegram_bot.py
import logging, requests
from django.conf import settings
logger = logging.getLogger('utils.telegram')

BOT_TOKEN = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
BASE_URL  = f'https://api.telegram.org/bot{BOT_TOKEN}'

class TelegramBot:
    def send_message(self, chat_id: str, text: str, parse_mode: str = 'HTML') -> bool:
        if not BOT_TOKEN: return False
        try:
            r = requests.post(f'{BASE_URL}/sendMessage', json={'chat_id':chat_id,'text':text,'parse_mode':parse_mode}, timeout=10)
            return r.json().get('ok', False)
        except Exception as e:
            logger.error(f'Telegram send failed: {e}'); return False

    def send_campaign_notification(self, chat_id: str, campaign_title: str, reward_usd: float, task_url: str) -> bool:
        msg = (f'🎯 <b>New Task Available!</b>\n'
               f'📋 {campaign_title}\n💵 Reward: <b>${reward_usd:.2f}</b>\n'
               f'🔗 <a href="{task_url}">Start Task</a>')
        return self.send_message(chat_id, msg)

    def send_payout_notification(self, chat_id: str, amount_usd: float, method: str) -> bool:
        return self.send_message(chat_id, f'💰 Payment Sent!\n${amount_usd:.2f} via {method}')

    def get_channel_member_count(self, channel_id: str) -> int:
        try:
            r = requests.get(f'{BASE_URL}/getChatMemberCount', params={'chat_id': channel_id}, timeout=10)
            return r.json().get('result', 0)
        except Exception: return 0

    def verify_channel_membership(self, channel_id: str, user_id: str) -> bool:
        try:
            r = requests.get(f'{BASE_URL}/getChatMember', params={'chat_id': channel_id, 'user_id': user_id}, timeout=10)
            status = r.json().get('result', {}).get('status', 'left')
            return status in ('member', 'administrator', 'creator')
        except Exception: return False
