"""GAMIFICATION/leaderboard.py — Leaderboard management."""
from ..services import LeaderboardService


class Leaderboard:
    @classmethod
    def top(cls, scope: str = "global", board_type: str = "earnings",
             period: str = "", limit: int = 50) -> list:
        return LeaderboardService.get_leaderboard(scope, board_type, limit)

    @classmethod
    def rank_of(cls, user, scope: str = "global",
                 board_type: str = "earnings") -> int:
        from ..models import LeaderboardRank
        entry = LeaderboardRank.objects.filter(
            user=user, scope=scope, board_type=board_type
        ).first()
        return entry.rank if entry else 0

    @classmethod
    def update(cls, user, score: Decimal, scope: str = "global",
                board_type: str = "earnings"):
        from ..models import LeaderboardRank
        from django.db.models import F
        LeaderboardRank.objects.update_or_create(
            user=user, scope=scope, board_type=board_type,
            defaults={"score": score},
        )
