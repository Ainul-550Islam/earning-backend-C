# engagement/signals/__init__.py
from django.dispatch import Signal

# Custom signals
level_up_signal = Signal()          # args: user, old_level, new_level
achievement_unlocked_signal = Signal()  # args: user, achievement
quest_completed_signal = Signal()   # args: user, user_quest
streak_broken_signal = Signal()     # args: user, old_streak
