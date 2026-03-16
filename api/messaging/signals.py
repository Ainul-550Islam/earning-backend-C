"""
Messaging Signals — Signal definitions.
Connected in MessagingConfig.ready() via receivers.py.
"""

from django.dispatch import Signal

# Fired after a ChatMessage is successfully sent.
# kwargs: message (ChatMessage), chat (InternalChat)
chat_message_sent = Signal()

# Fired after an AdminBroadcast transitions to SENT.
# kwargs: broadcast (AdminBroadcast)
broadcast_sent = Signal()

# Fired after a SupportMessage is posted by an agent.
# kwargs: support_message (SupportMessage), thread (SupportThread)
support_reply_posted = Signal()

# Fired after a SupportThread status changes.
# kwargs: thread (SupportThread), old_status (str), new_status (str)
support_thread_status_changed = Signal()
