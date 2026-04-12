"""
Messaging Signals — Signal definitions.
Connected in MessagingConfig.ready() via receivers.py.
Existing signals preserved. New signals added.
"""

from django.dispatch import Signal

# ── Existing Signals (unchanged) ─────────────────────────────────────────────

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


# ── New Signals ───────────────────────────────────────────────────────────────

# Fired after a MessageReaction is created.
# kwargs: reaction (MessageReaction), message (ChatMessage)
message_reaction_added = Signal()

# Fired after a MessageReaction is deleted.
# kwargs: user_id (int), message_id (UUID), emoji (str)
message_reaction_removed = Signal()

# Fired when a CallSession is initiated (status=RINGING).
# kwargs: call (CallSession), caller (User)
call_started = Signal()

# Fired when a CallSession ends (status=ENDED/MISSED/DECLINED/FAILED).
# kwargs: call (CallSession), duration_seconds (int)
call_ended = Signal()

# Fired when a user's presence status changes.
# kwargs: user_id (int), old_status (str), new_status (str)
presence_changed = Signal()

# Fired when a message is pinned in a chat.
# kwargs: pin (MessagePin), chat (InternalChat), pinned_by (User)
message_pinned = Signal()

# Fired when a message is unpinned from a chat.
# kwargs: message_id (UUID), chat_id (UUID), unpinned_by (User)
message_unpinned = Signal()

# Fired when a ScheduledMessage is sent successfully.
# kwargs: scheduled_msg (ScheduledMessage), sent_message (ChatMessage)
scheduled_message_sent = Signal()

# Fired when a user is mentioned in a message.
# kwargs: message (ChatMessage), mentioned_user_ids (list[int])
users_mentioned = Signal()

# Fired when a user is blocked.
# kwargs: block (UserBlock)
user_blocked = Signal()

# Fired when a user is unblocked.
# kwargs: blocker_id (int), blocked_id (int)
user_unblocked = Signal()

# Fired when a ChatMessage is forwarded.
# kwargs: original_message (ChatMessage), forwarded_message (ChatMessage), forwarded_by (User)
message_forwarded = Signal()

# Fired after a bot auto-reply is sent.
# kwargs: bot_response (BotResponse)
bot_response_sent = Signal()

# Fired when a new user joins an AnnouncementChannel.
# kwargs: channel (AnnouncementChannel), user (User)
channel_subscribed = Signal()

# Fired when a user leaves/unsubscribes from an AnnouncementChannel.
# kwargs: channel (AnnouncementChannel), user_id (int)
channel_unsubscribed = Signal()

# Fired after a webhook delivery (success or failure).
# kwargs: delivery (WebhookDelivery)
webhook_delivery_attempted = Signal()


# ── Final 6% Signals ──────────────────────────────────────────────────────────

# Fired after a UserStory is created.
# kwargs: story (UserStory)
story_created = Signal()

# Fired after a StoryView is recorded.
# kwargs: view (StoryView), story (UserStory), viewer_id (int)
story_viewed = Signal()

# Fired after a story is replied to.
# kwargs: view (StoryView), reply_text (str), reaction_emoji (str)
story_replied = Signal()

# Fired after a message is edited (with history saved).
# kwargs: message (ChatMessage), edit_history (MessageEditHistory)
message_edited_with_history = Signal()

# Fired after disappearing messages config changes.
# kwargs: config (DisappearingMessageConfig), chat (InternalChat)
disappearing_config_changed = Signal()

# Fired after link previews are fetched for a message.
# kwargs: message_id (UUID), preview_count (int)
link_previews_fetched = Signal()

# Fired after voice message is transcribed.
# kwargs: transcription (VoiceMessageTranscription)
voice_message_transcribed = Signal()
