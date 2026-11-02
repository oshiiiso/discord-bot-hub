"""パネルから一時 VC を作り、空室になったら消す。"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import BOT_DISPLAY_NAME, GUILD_ID
from logging_config import get_logger
from replies import defer_ephemeral, delete_ephemeral, send_ephemeral
from vc_manager import messages as msg
from vc_manager.config import (
    CREATE_CATEGORY_ID,
    CREATE_COOLDOWN_SECONDS,
    EMPTY_GRACE_SECONDS,
    PANEL_CHANNEL_ID,
    RECRUIT_CHANNEL_ID,
)
from vc_manager.create_view import (
    VcCreateButton,
    apply_occupied_count,
    create_room_view,
    is_panel_message,
    panel_embed,
    recruit_embed,
)
from vc_manager.join_view import VcJoinButton
from vc_manager.rooms import (
    Room,
    composed_room_name,
    load_rooms,
    save_rooms,
    unique_channel_name,
    vacant_remaining_seconds,
)

logger = get_logger(__name__)


@dataclass
class _CreateResult:
    """部屋作成の結果。失敗時は ok=False。"""

    ok: bool
    moved: bool = False
    invite_url: str = ""
    channel_id: int = 0


class VcManagerCog(commands.Cog):
    """部屋作成パネルから募集 VC を出す。"""

    vc = app_commands.Group(name="vc", description=msg.MSG_GROUP_DESCRIPTION)

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._rooms: dict[int, Room] = {}
        self._grace_tasks: dict[int, asyncio.Task[None]] = {}
        self._creating: set[int] = set()
        self._cooldowns: dict[int, datetime] = {}
        self._owner_prompts: dict[int, list[discord.Interaction]] = {}
        self._active_names: dict[int, str] = {}
        self._embed_tasks: dict[int, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()
        self._create_lock = asyncio.Lock()

    async def cog_load(self) -> None:
        self.bot.add_dynamic_items(VcJoinButton)
        self.bot.add_dynamic_items(VcCreateButton)
        self._rooms = load_rooms()

    async def cog_unload(self) -> None:
        self.bot.remove_dynamic_items(VcJoinButton)
        self.bot.remove_dynamic_items(VcCreateButton)
        for task in list(self._grace_tasks.values()):
            task.cancel()
        self._grace_tasks.clear()
        for task in list(self._embed_tasks.values()):
            task.cancel()
        self._embed_tasks.clear()

    @vc.command(name="ping", description=msg.MSG_CMD_PING)
    async def ping(self, interaction: discord.Interaction) -> None:
        await send_ephemeral(
            interaction,
            msg.MSG_PING.format(ms=round(self.bot.latency * 1000)),
        )

    @vc.command(name="panel", description=msg.MSG_CMD_PANEL)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def panel_cmd(self, interaction: discord.Interaction) -> None:
        if not await defer_ephemeral(interaction):
            return
        if self.bot.user is None:
            await send_ephemeral(interaction, msg.MSG_CREATE_FAILED)
            return
        channel = await self._resolve_text_channel(PANEL_CHANNEL_ID) if PANEL_CHANNEL_ID else None
        if channel is None and isinstance(interaction.channel, discord.TextChannel):
            channel = interaction.channel
        if channel is None:
            await send_ephemeral(interaction, msg.MSG_PANEL_CHANNEL_MISSING)
            return

        me = channel.guild.me if channel.guild is not None else None
        if me is None:
            await send_ephemeral(interaction, msg.MSG_CREATE_FAILED)
            return
        perms = channel.permissions_for(me)
        missing: list[str] = []
        if not perms.view_channel:
            missing.append(msg.MSG_PERM_VIEW)
        if not perms.send_messages:
            missing.append(msg.MSG_PERM_SEND)
        if not perms.embed_links:
            missing.append(msg.MSG_PERM_EMBED)
        if not perms.read_message_history:
            missing.append(msg.MSG_PERM_HISTORY)
        if missing:
            await send_ephemeral(interaction, msg.MSG_PANEL_MISSING_PERMS.format(perms="、".join(missing)))
            return

        try:
            pins = await channel.pins()
        except discord.HTTPException:
            pins = []
        for pinned in pins:
            if is_panel_message(pinned, self.bot.user.id):
                try:
                    await pinned.unpin()
                except discord.HTTPException:
                    pass
                try:
                    await pinned.delete()
                except discord.HTTPException:
                    pass

        try:
            sent = await channel.send(embed=panel_embed(), view=create_room_view())
        except discord.HTTPException:
            logger.exception("部屋作成パネルの投稿に失敗しました channel_id=%s", channel.id)
            await send_ephemeral(interaction, msg.MSG_CREATE_FAILED)
            return

        if not perms.manage_messages:
            await send_ephemeral(interaction, msg.MSG_PANEL_PIN_FAILED)
            return
        try:
            await sent.pin()
        except discord.HTTPException:
            logger.warning("部屋作成パネルのピン留めに失敗しました channel_id=%s", channel.id)
            await send_ephemeral(interaction, msg.MSG_PANEL_PIN_FAILED)
            return
        await send_ephemeral(interaction, msg.MSG_PANEL_DONE)

    def resolve_member(self, interaction: discord.Interaction) -> discord.Member | None:
        """ギルド内の Member を取る。"""
        if isinstance(interaction.user, discord.Member):
            return interaction.user
        guild = self._target_guild()
        if guild is None:
            return None
        return guild.get_member(interaction.user.id)

    def _target_guild(self) -> discord.Guild | None:
        if GUILD_ID is not None:
            return self.bot.get_guild(GUILD_ID)
        if len(self.bot.guilds) == 1:
            return self.bot.guilds[0]
        return None

    def _is_configured(self) -> bool:
        return RECRUIT_CHANNEL_ID != 0 and CREATE_CATEGORY_ID != 0

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        try:
            await asyncio.sleep(1)
            await self._reconcile_rooms()
        except Exception:
            logger.exception("部屋の再同期に失敗しました")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot:
            return
        try:
            before_id = before.channel.id if before.channel is not None else None
            after_id = after.channel.id if after.channel is not None else None
            if before_id in self._rooms:
                await self._on_managed_leave(before_id)
            if after_id in self._rooms:
                self._cancel_grace(after_id)
                await self._on_managed_join(member, after_id)
        except Exception:
            logger.exception("ボイス状態の処理に失敗しました user_id=%s", member.id)

    async def join_managed_room(self, interaction: discord.Interaction, channel_id: int) -> None:
        """参加ボタン。ボイス接続中なら移し、未接続なら招待を出す。"""
        on_ephemeral = _is_ephemeral_message(interaction)
        if not on_ephemeral and not await defer_ephemeral(interaction):
            return
        channel = await self._resolve_voice_channel(channel_id)
        room = self._rooms.get(channel_id)
        if channel is None or room is None:
            if room is not None:
                await self._delete_room(channel_id, reason="参加時に VC が無かった")
            await self._respond_join(interaction, on_ephemeral, msg.MSG_ROOM_GONE, persist=True)
            return

        member = self.resolve_member(interaction)
        if member is not None:
            voice = member.voice
            if voice is not None and voice.channel is not None:
                if voice.channel.id == channel.id:
                    await self._respond_join(interaction, on_ephemeral, msg.MSG_JOIN_MOVED)
                    await self._clear_owner_prompts(channel_id)
                    return
                if await self._move_creator(member, channel):
                    await self._respond_join(interaction, on_ephemeral, msg.MSG_JOIN_MOVED)
                    return
                await self._respond_join(interaction, on_ephemeral, msg.MSG_MOVE_FAILED, persist=True)
                return

        url = await self._ensure_invite(room, channel)
        if not url:
            await self._respond_join(interaction, on_ephemeral, msg.MSG_INVITE_FAILED, persist=True)
            return
        await self._respond_join(
            interaction,
            on_ephemeral,
            msg.MSG_JOIN_LINK.format(url=url),
            persist=True,
        )
        if member is not None and member.id == room.owner_id:
            self._remember_owner_prompt(channel_id, interaction)

    async def _respond_join(
        self,
        interaction: discord.Interaction,
        on_ephemeral: bool,
        content: str,
        *,
        persist: bool = False,
    ) -> None:
        if on_ephemeral and not interaction.response.is_done():
            try:
                await interaction.response.edit_message(content=content, view=None)
                return
            except discord.HTTPException:
                logger.debug("参加エフェメラルの更新をスキップしました")
        await send_ephemeral(interaction, content, persist=persist)

    async def _ensure_invite(self, room: Room, channel: discord.VoiceChannel) -> str:
        if room.invite_url:
            return room.invite_url
        try:
            invite = await channel.create_invite(max_age=0, max_uses=0, unique=False)
        except discord.HTTPException:
            logger.exception("参加リンクの再発行に失敗しました channel_id=%s", channel.id)
            return ""
        room.invite_url = invite.url
        save_rooms(self._rooms)
        return invite.url

    async def complete_create_room(
        self,
        interaction: discord.Interaction,
        *,
        kind_label: str,
        title: str,
        details: str,
        until: str,
        occupancy: int,
    ) -> None:
        """モーダル送信後に部屋を作り、募集へ埋め込みリンクを出す。"""
        if not await defer_ephemeral(interaction):
            return
        member = self.resolve_member(interaction)
        if member is None:
            await send_ephemeral(interaction, msg.MSG_CREATE_FAILED, persist=True)
            return
        if not self._is_configured():
            await send_ephemeral(interaction, msg.MSG_NOT_CONFIGURED, persist=True)
            return
        wait = self._cooldown_remaining(member.id)
        if wait > 0:
            await send_ephemeral(interaction, msg.MSG_COOLDOWN.format(seconds=wait), persist=True)
            return
        if member.id in self._creating:
            await send_ephemeral(interaction, msg.MSG_CREATING)
            return

        self._creating.add(member.id)
        try:
            result = await self._build_room(
                member,
                kind_label=kind_label,
                title=title,
                details=details,
                until=until,
                occupancy=occupancy,
            )
            await self._send_create_result(interaction, result)
        except Exception:
            logger.exception("部屋作成中に例外が発生しました user_id=%s", member.id)
            await send_ephemeral(interaction, msg.MSG_CREATE_FAILED, persist=True)
        finally:
            self._creating.discard(member.id)

    async def _send_create_result(
        self, interaction: discord.Interaction, result: _CreateResult
    ) -> None:
        if not result.ok:
            await send_ephemeral(interaction, msg.MSG_CREATE_FAILED, persist=True)
            return
        if result.moved:
            await send_ephemeral(interaction, msg.MSG_CREATED_MOVED)
            return
        content = msg.MSG_CREATED_JOIN.format(url=result.invite_url) if result.invite_url else msg.MSG_CREATED
        await send_ephemeral(interaction, content, persist=True)
        if result.channel_id:
            self._remember_owner_prompt(result.channel_id, interaction)

    async def _build_room(
        self,
        member: discord.Member,
        *,
        kind_label: str,
        title: str,
        details: str,
        until: str,
        occupancy: int,
    ) -> _CreateResult:
        category = await self._resolve_category()
        if category is None:
            logger.warning("作成先カテゴリが見つかりません id=%s", CREATE_CATEGORY_ID)
            return _CreateResult(ok=False)

        async with self._create_lock:
            taken = {channel.name for channel in category.channels}
            taken.update(self._active_names.values())
            name = unique_channel_name(composed_room_name(kind_label, title, until), taken)
            try:
                new_channel = await member.guild.create_voice_channel(
                    name=name,
                    category=category,
                    user_limit=occupancy,
                    reason=f"{BOT_DISPLAY_NAME} の募集部屋",
                )
            except discord.HTTPException:
                logger.exception("部屋 VC の作成に失敗しました")
                return _CreateResult(ok=False)
            self._active_names[new_channel.id] = name

        moved = await self._move_creator(member, new_channel)

        recruit = await self._resolve_text_channel(RECRUIT_CHANNEL_ID)
        if recruit is None:
            logger.warning("募集チャンネルが見つかりません id=%s", RECRUIT_CHANNEL_ID)
            await self._abandon_channel(new_channel, "募集チャンネルが無い")
            return _CreateResult(ok=False)

        invite_url = ""
        if not moved:
            try:
                invite = await new_channel.create_invite(max_age=0, max_uses=0, unique=False)
                invite_url = invite.url
            except discord.HTTPException:
                logger.warning("作成者向けの招待を作れませんでした channel_id=%s", new_channel.id)

        occupied = _human_count(new_channel)
        embed = recruit_embed(
            name=name,
            mention=member.mention,
            details=details,
            until=until,
            kind_label=kind_label,
            occupied=occupied,
            occupancy=occupancy,
            room_mention=new_channel.mention,
        )
        try:
            posted = await recruit.send(embed=embed)
        except discord.HTTPException:
            logger.exception("募集埋め込みの投稿に失敗しました channel_id=%s", new_channel.id)
            await self._abandon_channel(new_channel, "募集埋め込みを出せなかった部屋")
            return _CreateResult(ok=False)

        room = Room(
            voice_channel_id=new_channel.id,
            guild_id=member.guild.id,
            message_id=posted.id,
            recruit_channel_id=recruit.id,
            invite_url=invite_url,
            owner_id=member.id,
            occupied_once=moved or _human_count(new_channel) > 0,
            created_at=time.time(),
        )
        async with self._lock:
            self._rooms[new_channel.id] = room
            save_rooms(self._rooms)
        if not room.occupied_once:
            self._schedule_vacant(new_channel.id)
        self._cooldowns[member.id] = datetime.now(timezone.utc)
        logger.info("募集部屋を作成しました channel_id=%s owner_id=%s", new_channel.id, member.id)
        return _CreateResult(
            ok=True,
            moved=moved,
            invite_url=invite_url,
            channel_id=new_channel.id,
        )

    async def _move_creator(self, member: discord.Member, dest: discord.VoiceChannel) -> bool:
        """ボイス接続中なら部屋へ移す。未接続は Discord が入れない。"""
        refreshed = member.guild.get_member(member.id) or member
        voice = refreshed.voice
        if voice is None or voice.channel is None:
            return False
        if voice.channel.id == dest.id:
            return True
        try:
            await refreshed.move_to(dest, reason="募集部屋へ移動")
        except discord.Forbidden:
            logger.warning("作成者を部屋へ移す権限が無い user_id=%s", member.id)
            return False
        except discord.HTTPException:
            logger.warning(msg.MSG_MOVE_FAILED)
            return False
        await self._clear_server_mute(refreshed)
        return True

    async def _on_managed_join(self, member: discord.Member, channel_id: int) -> None:
        """初回入室を記録し、待ち部屋でのサーバーミュートを外す。"""
        room = self._rooms.get(channel_id)
        if room is None:
            return
        if not room.occupied_once:
            room.occupied_once = True
            save_rooms(self._rooms)
            await self._clear_server_mute(member)
        if member.id == room.owner_id:
            await self._clear_owner_prompts(channel_id)
        self._schedule_recruit_count(channel_id)

    async def _clear_server_mute(self, member: discord.Member) -> None:
        voice = member.voice
        if voice is None or not voice.mute:
            return
        try:
            await member.edit(mute=False, reason="募集部屋の入室")
        except discord.HTTPException:
            logger.warning("サーバーミュート解除に失敗しました user_id=%s", member.id)

    async def _on_managed_leave(self, channel_id: int) -> None:
        room = self._rooms.get(channel_id)
        channel = await self._resolve_voice_channel(channel_id)
        if channel is None:
            await self._delete_room(channel_id, reason="チャンネルが無い")
            return
        if _human_count(channel) > 0:
            self._cancel_grace(channel_id)
            self._schedule_recruit_count(channel_id)
            return
        if room is None:
            self._cancel_grace(channel_id)
            return
        self._schedule_recruit_count(channel_id)
        if room.occupied_once:
            self._schedule_occupied_empty(channel_id)
            return
        self._schedule_vacant(channel_id)

    def _schedule_occupied_empty(self, channel_id: int) -> None:
        self._schedule_delete(channel_id, EMPTY_GRACE_SECONDS)

    def _schedule_vacant(self, channel_id: int) -> None:
        room = self._rooms.get(channel_id)
        if room is None or room.occupied_once:
            return
        self._schedule_delete(channel_id, vacant_remaining_seconds(room.created_at))

    def _schedule_delete(self, channel_id: int, delay: float) -> None:
        if channel_id in self._grace_tasks:
            return
        self._grace_tasks[channel_id] = asyncio.create_task(self._delayed_delete(channel_id, delay))

    def _cancel_grace(self, channel_id: int) -> None:
        task = self._grace_tasks.pop(channel_id, None)
        if task is None:
            return
        if task is asyncio.current_task():
            return
        task.cancel()

    def _schedule_recruit_count(self, channel_id: int) -> None:
        self._cancel_recruit_count(channel_id)
        self._embed_tasks[channel_id] = asyncio.create_task(self._refresh_recruit_count(channel_id))

    def _cancel_recruit_count(self, channel_id: int) -> None:
        task = self._embed_tasks.pop(channel_id, None)
        if task is None:
            return
        if task is asyncio.current_task():
            return
        task.cancel()

    async def _refresh_recruit_count(self, channel_id: int) -> None:
        try:
            await asyncio.sleep(0.4)
            room = self._rooms.get(channel_id)
            if room is None:
                return
            channel = await self._resolve_voice_channel(channel_id)
            if channel is None:
                return
            recruit = await self._resolve_text_channel(room.recruit_channel_id)
            if recruit is None:
                return
            try:
                message = await recruit.fetch_message(room.message_id)
            except discord.NotFound:
                return
            except discord.HTTPException:
                logger.exception("募集人数の取得に失敗しました message_id=%s", room.message_id)
                return
            if not message.embeds:
                return
            embed = message.embeds[0]
            if not apply_occupied_count(embed, _human_count(channel)):
                return
            try:
                await message.edit(embed=embed)
            except discord.HTTPException:
                logger.exception("募集人数の更新に失敗しました message_id=%s", room.message_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("募集人数の更新に失敗しました channel_id=%s", channel_id)
        finally:
            if self._embed_tasks.get(channel_id) is asyncio.current_task():
                self._embed_tasks.pop(channel_id, None)

    async def _delayed_delete(self, channel_id: int, delay: float) -> None:
        try:
            await asyncio.sleep(max(0.0, delay))
            room = self._rooms.get(channel_id)
            if room is None:
                return
            channel = await self._resolve_voice_channel(channel_id)
            if channel is None:
                await self._delete_room(channel_id, reason="チャンネルが無い")
                return
            if _human_count(channel) > 0:
                return
            reason = "空室" if room.occupied_once else "未入室"
            await self._delete_room(channel_id, reason=reason)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("空室削除に失敗しました channel_id=%s", channel_id)
        finally:
            self._grace_tasks.pop(channel_id, None)

    async def _delete_room(self, channel_id: int, reason: str) -> None:
        async with self._lock:
            room = self._rooms.pop(channel_id, None)
            if room is not None:
                save_rooms(self._rooms)
        self._cancel_grace(channel_id)
        self._cancel_recruit_count(channel_id)
        self._active_names.pop(channel_id, None)
        await self._clear_owner_prompts(channel_id)
        channel = await self._resolve_voice_channel(channel_id)
        if channel is not None:
            await self._safe_delete_channel(channel, f"{BOT_DISPLAY_NAME} {reason}")
        if room is not None:
            await self._delete_embed(room)
        logger.info("募集部屋を削除しました channel_id=%s reason=%s", channel_id, reason)

    async def _delete_embed(self, room: Room) -> None:
        channel = await self._resolve_text_channel(room.recruit_channel_id)
        if channel is None:
            return
        for message_id in (room.message_id, room.card_message_id):
            if not message_id:
                continue
            try:
                message = await channel.fetch_message(message_id)
                await message.delete()
            except discord.NotFound:
                continue
            except discord.HTTPException:
                logger.exception("募集メッセージの削除に失敗しました message_id=%s", message_id)

    async def _reconcile_rooms(self) -> None:
        """再起動後、残っている部屋と埋め込みを実際の VC に合わせる。"""
        for channel_id, room in list(self._rooms.items()):
            try:
                channel = await self._resolve_voice_channel(channel_id)
                if channel is None:
                    await self._delete_room(channel_id, reason="再起動時に VC が無かった")
                    continue
                self._active_names[channel_id] = channel.name
                if _human_count(channel) > 0:
                    if not room.occupied_once:
                        room.occupied_once = True
                        save_rooms(self._rooms)
                    self._schedule_recruit_count(channel_id)
                    continue
                if room.occupied_once:
                    self._schedule_occupied_empty(channel_id)
                    continue
                remaining = vacant_remaining_seconds(room.created_at)
                if remaining <= 0:
                    await self._delete_room(channel_id, reason="未入室")
                    continue
                self._schedule_vacant(channel_id)
            except Exception:
                logger.exception("部屋の再同期に失敗しました channel_id=%s", channel_id)

    async def _abandon_channel(self, channel: discord.VoiceChannel, reason: str) -> None:
        self._active_names.pop(channel.id, None)
        await self._safe_delete_channel(channel, reason)

    async def _safe_delete_channel(self, channel: discord.VoiceChannel, reason: str) -> None:
        try:
            await channel.delete(reason=reason)
        except discord.NotFound:
            return
        except discord.HTTPException:
            logger.exception("部屋 VC の削除に失敗しました channel_id=%s", channel.id)

    async def _resolve_category(self) -> discord.CategoryChannel | None:
        channel = await self._resolve_channel(CREATE_CATEGORY_ID)
        if isinstance(channel, discord.CategoryChannel):
            return channel
        return None

    async def _resolve_voice_channel(self, channel_id: int) -> discord.VoiceChannel | None:
        channel = await self._resolve_channel(channel_id)
        if isinstance(channel, discord.VoiceChannel):
            return channel
        return None

    async def _resolve_text_channel(self, channel_id: int) -> discord.TextChannel | None:
        channel = await self._resolve_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    async def _resolve_channel(
        self, channel_id: int
    ) -> discord.abc.GuildChannel | discord.Thread | None:
        if channel_id == 0:
            return None
        channel = self.bot.get_channel(channel_id)
        if isinstance(channel, (discord.abc.GuildChannel, discord.Thread)):
            return channel
        try:
            fetched = await self.bot.fetch_channel(channel_id)
        except discord.HTTPException:
            return None
        if isinstance(fetched, (discord.abc.GuildChannel, discord.Thread)):
            return fetched
        return None

    def _remember_owner_prompt(self, channel_id: int, interaction: discord.Interaction) -> None:
        prompts = self._owner_prompts.setdefault(channel_id, [])
        if interaction not in prompts:
            prompts.append(interaction)

    async def _clear_owner_prompts(self, channel_id: int) -> None:
        prompts = self._owner_prompts.pop(channel_id, [])
        for interaction in prompts:
            await delete_ephemeral(interaction)

    def _cooldown_remaining(self, user_id: int) -> int:
        last = self._cooldowns.get(user_id)
        if last is None:
            return 0
        elapsed = datetime.now(timezone.utc) - last
        remain = timedelta(seconds=CREATE_COOLDOWN_SECONDS) - elapsed
        return max(0, int(remain.total_seconds()))


def _human_count(channel: discord.VoiceChannel) -> int:
    return sum(1 for member in channel.members if not member.bot)


def _is_ephemeral_message(interaction: discord.Interaction) -> bool:
    message = interaction.message
    return message is not None and message.flags.ephemeral


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VcManagerCog(bot))
