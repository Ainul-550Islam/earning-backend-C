# engagement/tests/test_guild.py
import pytest
from decimal import Decimal
from ..services.guild_service import GuildService
from ..models.guild import Guild, GuildMember
from .factories import UserFactory, UserXPFactory


@pytest.mark.django_db
class TestGuildService:

    def _make_guild(self, owner, name="Test Guild", is_public=True):
        return GuildService.create(
            owner=owner, name=name, slug=name.lower().replace(" ", "-"),
            description="Test", is_public=is_public,
        )

    def test_create_guild_adds_owner_as_member(self):
        owner = UserFactory(coin_balance=Decimal("0"))
        guild = self._make_guild(owner)
        assert Guild.objects.filter(name="Test Guild").exists()
        member = GuildMember.objects.get(user=owner, guild=guild)
        assert member.role   == "owner"
        assert member.status == "active"

    def test_join_guild_creates_member(self):
        owner  = UserFactory(coin_balance=Decimal("0"))
        user   = UserFactory(coin_balance=Decimal("0"))
        guild  = self._make_guild(owner)
        member = GuildService.join(user, guild)
        assert member.role   == "member"
        assert member.status == "active"

    def test_join_guild_full_raises_error(self):
        owner = UserFactory(coin_balance=Decimal("0"))
        guild = self._make_guild(owner)
        guild.max_members = 1
        guild.save(update_fields=["max_members"])
        user2 = UserFactory(coin_balance=Decimal("0"))
        with pytest.raises(ValueError, match="full"):
            GuildService.join(user2, guild)

    def test_join_already_member_raises_error(self):
        owner = UserFactory(coin_balance=Decimal("0"))
        guild = self._make_guild(owner)
        user  = UserFactory(coin_balance=Decimal("0"))
        GuildService.join(user, guild)
        with pytest.raises(ValueError):
            GuildService.join(user, guild)

    def test_join_min_level_requirement(self):
        owner = UserFactory(coin_balance=Decimal("0"))
        guild = self._make_guild(owner)
        guild.min_level_required = 10
        guild.save(update_fields=["min_level_required"])
        user = UserFactory(coin_balance=Decimal("0"))
        # User has level 1 by default
        with pytest.raises(ValueError, match="level"):
            GuildService.join(user, guild)

    def test_leave_guild_updates_status(self):
        owner = UserFactory(coin_balance=Decimal("0"))
        user  = UserFactory(coin_balance=Decimal("0"))
        guild = self._make_guild(owner)
        GuildService.join(user, guild)
        GuildService.leave(user, guild)
        member = GuildMember.objects.get(user=user, guild=guild)
        assert member.status == "left"

    def test_leave_owner_transfers_ownership(self):
        owner  = UserFactory(coin_balance=Decimal("0"))
        member = UserFactory(coin_balance=Decimal("0"))
        guild  = self._make_guild(owner)
        GuildService.join(member, guild)
        GuildService.leave(owner, guild)
        guild.refresh_from_db()
        assert guild.owner == member

    def test_leave_last_member_deactivates_guild(self):
        owner = UserFactory(coin_balance=Decimal("0"))
        guild = self._make_guild(owner)
        GuildService.leave(owner, guild)
        guild.refresh_from_db()
        assert guild.is_active is False

    def test_contribute_xp_increments_guild_total(self):
        owner = UserFactory(coin_balance=Decimal("0"))
        guild = self._make_guild(owner)
        GuildService.contribute_xp(owner, guild, xp_amount=500)
        guild.refresh_from_db()
        assert guild.total_xp == 500

    def test_member_count_is_correct(self):
        owner = UserFactory(coin_balance=Decimal("0"))
        guild = self._make_guild(owner)
        u2    = UserFactory(coin_balance=Decimal("0"))
        u3    = UserFactory(coin_balance=Decimal("0"))
        GuildService.join(u2, guild)
        GuildService.join(u3, guild)
        assert guild.member_count == 3
