"""UID から紹介キャラのビルドカードを出す。"""

from __future__ import annotations

import asyncio
from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands, tasks

import messages as msg
from config import CHANNEL_ID, CHARACTER_LEARN_HOURS
from games.base import CharacterBuild
from games.genshin import GenshinGame
from games.genshin.catalog import (
    parse_aliases,
    refresh_catalog,
    upsert_character,
    upsert_set,
    valid_set_id,
)
from logging_config import get_logger
from replies import defer_ephemeral, edit_original, send_ephemeral
from services.card_renderer import render_build_card
from services.channels import is_bot_channel
from services.character_check import collect_rows, format_report, note_rows, problem_rows
from services.character_learn import learn_new_characters
from services.preview_card import dummy_avatar, dummy_weapons_for, preview_targets
from services.copy import t
from services.enka_client import EnkaAvatar, EnkaClient, EnkaError, EnkaShowcase
from services.session_store import SessionStore, UidSession
from ui.guide_embed import formula_embed, guide_embed, is_guide_message
from ui.start_view import CardMessageView, StartCardView
from ui.uid_view import UidPickView

logger = get_logger(__name__)


class BuildCog(commands.Cog):
    """UID からビルドカード。"""

    buildcard = app_commands.Group(name="buildcard", description="原神のビルドカード")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.sessions = SessionStore()
        self.enka = EnkaClient()
        self._preview_all_lock = asyncio.Lock()

    async def cog_load(self) -> None:
        self.bot.add_view(StartCardView())
        if CHARACTER_LEARN_HOURS > 0:
            self.learn_characters.change_interval(hours=CHARACTER_LEARN_HOURS)
            self.learn_characters.start()

    async def cog_unload(self) -> None:
        if self.learn_characters.is_running():
            self.learn_characters.cancel()
        await self.enka.close()

    @tasks.loop(hours=24)
    async def learn_characters(self) -> None:
        """公開図鑑を見にいき、まだ表に無い子とセットを覚える。"""
        try:
            await self.enka.refresh_store()
            names, sets = await learn_new_characters(await self.enka._http(), force=True)
        except Exception:
            logger.exception("図鑑の定期取得に失敗しました")
            return
        if names:
            logger.info("図鑑からキャラを覚えた: %s", "、".join(names))
        if sets:
            logger.info("図鑑からセットを覚えた: %s", "、".join(sets))

    @learn_characters.before_loop
    async def _wait_ready_to_learn(self) -> None:
        await self.bot.wait_until_ready()

    def in_bot_channel(self, channel: discord.abc.Messageable | None) -> bool:
        if channel is None or isinstance(channel, discord.Thread):
            return False
        channel_id = getattr(channel, "id", None)
        return isinstance(channel_id, int) and is_bot_channel(channel_id)

    async def _require_channel(self, interaction: discord.Interaction) -> bool:
        if not self.in_bot_channel(interaction.channel):
            await send_ephemeral(interaction, t(msg.ERR_02))
            return False
        return True

    @buildcard.command(name="setup", description=msg.MSG_03)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def setup_cmd(self, interaction: discord.Interaction) -> None:
        if not await defer_ephemeral(interaction):
            return
        if self.bot.user is None:
            await send_ephemeral(interaction, t(msg.ERR_12))
            return
        if CHANNEL_ID == 0:
            await send_ephemeral(interaction, t(msg.ERR_05))
            return
        channel = interaction.client.get_channel(CHANNEL_ID)
        if channel is None:
            try:
                channel = await interaction.client.fetch_channel(CHANNEL_ID)
            except discord.HTTPException as e:
                logger.warning("対象チャンネルを取得できませんでした channel=%s err=%s", CHANNEL_ID, e)
                await send_ephemeral(interaction, t(msg.ERR_19))
                return
        if not isinstance(channel, discord.TextChannel):
            await send_ephemeral(interaction, t(msg.ERR_19))
            return

        me = channel.guild.me if channel.guild is not None else None
        if me is None:
            await send_ephemeral(interaction, t(msg.ERR_06))
            return
        perms = channel.permissions_for(me)
        missing: list[str] = []
        if not perms.view_channel:
            missing.append(t(msg.MSG_10))
        if not perms.send_messages:
            missing.append(t(msg.MSG_11))
        if not perms.embed_links:
            missing.append(t(msg.MSG_12))
        if not perms.read_message_history:
            missing.append(t(msg.MSG_13))
        if missing:
            await send_ephemeral(interaction, t(msg.ERR_08, perms="、".join(missing)))
            return

        try:
            pins = await channel.pins()
        except discord.HTTPException as e:
            logger.warning("ピン一覧の取得に失敗しました channel=%s err=%s", CHANNEL_ID, e)
            pins = []
        for pinned in pins:
            if is_guide_message(pinned, self.bot.user.id):
                try:
                    await pinned.unpin()
                except discord.HTTPException:
                    pass
                try:
                    await pinned.delete()
                except discord.HTTPException:
                    pass

        try:
            sent = await channel.send(embed=guide_embed(), view=StartCardView())
        except discord.HTTPException as e:
            logger.warning("案内の投稿に失敗しました channel=%s err=%s", CHANNEL_ID, e)
            await send_ephemeral(interaction, t(msg.ERR_06))
            return

        if not perms.manage_messages:
            await send_ephemeral(interaction, t(msg.ERR_07))
            return
        try:
            await sent.pin()
        except discord.HTTPException as e:
            logger.warning("案内のピン留めに失敗しました channel=%s err=%s", CHANNEL_ID, e)
            await send_ephemeral(interaction, t(msg.ERR_07))
            return
        await send_ephemeral(interaction, t(msg.MSG_14))

    @buildcard.command(name="reload", description=msg.MSG_08)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def reload_cmd(self, interaction: discord.Interaction) -> None:
        if not await defer_ephemeral(interaction):
            return
        try:
            await self.enka.refresh_store()
            refresh_catalog()
        except Exception:
            logger.exception("Enka のキャラ辞書の取り直しに失敗しました")
            await send_ephemeral(interaction, t(msg.ERR_09))
            return
        await send_ephemeral(interaction, t(msg.MSG_09))

    @buildcard.command(name="check", description=msg.MSG_45)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def check_cmd(self, interaction: discord.Interaction) -> None:
        if not await defer_ephemeral(interaction):
            return
        try:
            await self.enka.ensure_store()
            refresh_catalog()
            rows = collect_rows(self.enka)
        except Exception:
            logger.exception("全キャラ確認に失敗しました")
            await send_ephemeral(interaction, t(msg.ERR_09))
            return
        text = format_report(rows)
        if len(text) > 1900:
            await send_ephemeral(
                interaction,
                t(msg.MSG_46, count=len(rows), bad=len(problem_rows(rows)), notes=len(note_rows(rows))),
                file=discord.File(BytesIO(text.encode("utf-8")), filename="check.txt"),
            )
            return
        await send_ephemeral(interaction, text, persist=True)

    @buildcard.command(name="preview", description=msg.MSG_77)
    @app_commands.describe(name=msg.MSG_78)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def preview_cmd(self, interaction: discord.Interaction, name: str) -> None:
        if not await defer_ephemeral(interaction):
            return
        game = GenshinGame()
        character = game.resolve_character(name)
        if character is None:
            await send_ephemeral(interaction, t(msg.ERR_20))
            return
        try:
            await self.enka.ensure_store()
            refresh_catalog()
            character = game.resolve_character(name) or character
            weapons = await dummy_weapons_for(await self.enka._http(), self.enka, [character])
            avatar = dummy_avatar(self.enka, character, weapon=weapons.get(character.id))
            build = character.builds[0] if character.builds else None
            png = await self._render_avatar_png(avatar, build) if avatar and build else None
        except Exception:
            logger.exception("カード見本の生成に失敗しました")
            await send_ephemeral(interaction, t(msg.ERR_13))
            return
        if png is None:
            await send_ephemeral(interaction, t(msg.ERR_13))
            return
        await send_ephemeral(
            interaction,
            t(msg.MSG_79, name=character.name_ja),
            file=discord.File(BytesIO(png), filename=f"preview-{character.id}.png"),
        )

    @buildcard.command(name="previewall", description=msg.MSG_82)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def previewall_cmd(self, interaction: discord.Interaction) -> None:
        if not await self._require_channel(interaction):
            return
        if self._preview_all_lock.locked():
            await interaction.response.send_message(t(msg.ERR_21), ephemeral=True)
            return
        if not await defer_ephemeral(interaction):
            return
        async with self._preview_all_lock:
            await self._run_preview_all(interaction)

    async def _run_preview_all(self, interaction: discord.Interaction) -> None:
        try:
            await self.enka.ensure_store()
            refresh_catalog()
        except Exception:
            logger.exception("全員見本の準備に失敗しました")
            await send_ephemeral(interaction, t(msg.ERR_13))
            return
        targets = preview_targets()
        total = len(targets)
        if total == 0:
            await send_ephemeral(interaction, t(msg.ERR_13))
            return
        channel = self._public_channel(interaction)
        if channel is None:
            await send_ephemeral(interaction, t(msg.ERR_13))
            return
        try:
            starter = await channel.send(t(msg.MSG_83, count=total))
            dest: discord.abc.Messageable = starter
            try:
                dest = await starter.create_thread(name=t(msg.MSG_88), auto_archive_duration=1440)
            except discord.HTTPException:
                logger.warning("全員見本のスレッドを作れなかった。チャンネルに出します")
        except discord.HTTPException:
            logger.exception("全員見本の投稿先を用意できませんでした")
            await send_ephemeral(interaction, t(msg.ERR_13))
            return
        await send_ephemeral(
            interaction,
            t(msg.MSG_84, done=0, total=total, fail=0),
            persist=True,
        )
        dummy_weapons = await dummy_weapons_for(await self.enka._http(), self.enka, targets)
        failed: list[str] = []
        batch: list[tuple[str, str, bytes]] = []
        ok = 0

        async def flush() -> None:
            if not batch:
                return
            files = [
                discord.File(BytesIO(png), filename=f"preview-{char_id}.png")
                for _name, char_id, png in batch
            ]
            names = "、".join(name for name, _char_id, _png in batch)
            await dest.send(content=names[:1900], files=files)
            batch.clear()

        for index, character in enumerate(targets, start=1):
            try:
                avatar = dummy_avatar(self.enka, character, weapon=dummy_weapons.get(character.id))
                build = character.builds[0]
                png = await self._render_avatar_png(avatar, build) if avatar else None
            except Exception:
                logger.exception("全員見本の生成に失敗しました name=%s", character.name_ja)
                png = None
            if png is None:
                failed.append(character.name_ja)
            else:
                ok += 1
                batch.append((character.name_ja, character.id, png))
                if len(batch) >= 10:
                    try:
                        await flush()
                    except discord.HTTPException:
                        logger.exception("全員見本の投稿に失敗しました")
                        failed.extend(name for name, _char_id, _png in batch)
                        batch.clear()
                    await asyncio.sleep(1.2)
            if index % 5 == 0 or index == total:
                await edit_original(
                    interaction,
                    content=t(msg.MSG_84, done=index, total=total, fail=len(failed)),
                    persist=True,
                )
            await asyncio.sleep(0)
        try:
            await flush()
        except discord.HTTPException:
            logger.exception("全員見本の最後の投稿に失敗しました")
        summary = t(msg.MSG_85, ok=ok, fail=len(failed))
        if failed:
            summary += "\n" + t(msg.MSG_86, names="、".join(failed[:40]))
        try:
            await dest.send(summary[:1900])
        except discord.HTTPException:
            pass
        await edit_original(interaction, content=summary[:1900], persist=True)

    @buildcard.command(name="addchar", description=msg.MSG_58)
    @app_commands.rename(enka="number")
    @app_commands.describe(
        name=msg.MSG_60,
        enka=msg.MSG_61,
        element=msg.MSG_62,
        scale=msg.MSG_63,
        aliases=msg.MSG_64,
    )
    @app_commands.choices(
        element=[
            app_commands.Choice(name=label, value=key) for key, label in msg.MSG_ELEM.items()
        ],
        scale=[
            app_commands.Choice(name=label, value=key) for key, label in msg.MSG_SCALE.items()
        ],
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def addchar_cmd(
        self,
        interaction: discord.Interaction,
        name: str,
        enka: str,
        element: str,
        scale: str,
        aliases: str = "",
    ) -> None:
        if not await defer_ephemeral(interaction):
            return
        digits = "".join(c for c in enka if c.isdigit())
        if not 8 <= len(digits) <= 10:
            await send_ephemeral(interaction, t(msg.ERR_16))
            return
        name_ja = name.strip()
        if not name_ja:
            await send_ephemeral(interaction, t(msg.ERR_18))
            return
        alias_list = parse_aliases(aliases)
        if name_ja not in alias_list:
            alias_list.insert(0, name_ja)
        try:
            character = upsert_character(
                name_ja=name_ja,
                enka_id=digits,
                element=element,
                scale=scale,
                aliases=alias_list,
            )
        except Exception:
            logger.exception("キャラの登録に失敗しました")
            await send_ephemeral(interaction, t(msg.ERR_18))
            return
        await send_ephemeral(
            interaction,
            t(msg.MSG_66, name=character.name_ja, scale=msg.MSG_SCALE.get(scale, scale)),
        )

    @buildcard.command(name="addset", description=msg.MSG_59)
    @app_commands.describe(name=msg.MSG_60, set_id=msg.MSG_65, aliases=msg.MSG_64)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def addset_cmd(
        self,
        interaction: discord.Interaction,
        name: str,
        set_id: str,
        aliases: str = "",
    ) -> None:
        if not await defer_ephemeral(interaction):
            return
        name_ja = name.strip()
        normalized = set_id.strip().lower()
        if not name_ja:
            await send_ephemeral(interaction, t(msg.ERR_18))
            return
        if not valid_set_id(normalized):
            await send_ephemeral(interaction, t(msg.ERR_17))
            return
        try:
            row = upsert_set(set_id=normalized, name_ja=name_ja, aliases=parse_aliases(aliases))
        except Exception:
            logger.exception("セットの登録に失敗しました")
            await send_ephemeral(interaction, t(msg.ERR_18))
            return
        await send_ephemeral(interaction, t(msg.MSG_67, name=row["name_ja"]))

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await send_ephemeral(interaction, t(msg.ERR_04))
            return
        raise error

    @buildcard.command(name="formula", description=msg.MSG_04)
    async def formula_cmd(self, interaction: discord.Interaction) -> None:
        if not await self._require_channel(interaction):
            return
        await send_ephemeral(interaction, embed=formula_embed())

    @buildcard.command(name="uid", description=msg.MSG_05)
    @app_commands.describe(uid=msg.MSG_06)
    async def uid_cmd(self, interaction: discord.Interaction, uid: str) -> None:
        await self.begin_uid(interaction, uid)

    async def begin_uid(self, interaction: discord.Interaction, uid: str) -> None:
        """スラッシュと Modal の共通開始。選択は ephemeral、カードだけチャンネルへ。"""
        if not await self._require_channel(interaction):
            return
        digits = "".join(c for c in uid if c.isdigit())
        if not 8 <= len(digits) <= 10:
            await send_ephemeral(interaction, t(msg.ERR_15))
            return
        await send_ephemeral(interaction, t(msg.MSG_30), persist=True)
        if not interaction.response.is_done():
            return
        try:
            showcase = await self.enka.fetch_showcase(digits)
        except EnkaError as e:
            await edit_original(
                interaction,
                content=t(msg.ERR_ENKA.get(e.code, msg.ERR_12)),
                persist=True,
            )
            return
        except Exception:
            logger.exception("UID の取得に失敗しました")
            await edit_original(interaction, content=t(msg.ERR_12), persist=True)
            return
        if not showcase.avatars:
            await edit_original(interaction, content=t(msg.ERR_10), persist=True)
            return
        session = UidSession(
            user_id=interaction.user.id,
            uid=showcase.uid,
            nickname=showcase.nickname,
            avatars=list(showcase.avatars),
        )
        try:
            message = await interaction.original_response()
        except discord.HTTPException:
            logger.warning("UID 開始メッセージの取得に失敗しました")
            return
        self.sessions.put(message.id, session)
        view = UidPickView(self, message.id)
        await edit_original(
            interaction,
            content=t(msg.MSG_31, nickname=showcase.nickname, uid=showcase.uid),
            view=view,
            persist=True,
        )

    def _public_channel(self, interaction: discord.Interaction) -> discord.TextChannel | None:
        channel = interaction.channel
        if isinstance(channel, discord.TextChannel) and self.in_bot_channel(channel):
            return channel
        got = self.bot.get_channel(CHANNEL_ID)
        if isinstance(got, discord.TextChannel):
            return got
        return None

    def _swap_pick_view(self, session_key: int, old: UidPickView | None = None) -> UidPickView:
        if old is not None:
            old.stop()
        return UidPickView(self, session_key)

    async def _render_png(self, session: UidSession) -> bytes | None:
        avatar = session.selected_avatar()
        if avatar is None:
            return None
        build = None
        if session.build_id:
            build = next((b for b in avatar.character.builds if b.id == session.build_id), None)
        if build is None and avatar.character.builds:
            build = avatar.character.builds[0]
        return await self._render_avatar_png(avatar, build)

    async def _render_avatar_png(self, avatar: EnkaAvatar | None, build: CharacterBuild | None) -> bytes | None:
        if avatar is None or build is None:
            return None
        await self.enka.ensure_store()
        portrait_keys = self.enka.portrait_names(avatar.avatar_id, avatar.skill_depot_id, avatar.costume_id)
        portraits: list[bytes] = []
        for key in [*portrait_keys, avatar.splash_icon, avatar.icon]:
            if not key:
                continue
            data = await self.enka.download_icon(key)
            if data:
                portraits.append(data)
                break
        icon_names: list[str] = []
        if avatar.weapon:
            icon_names.append(avatar.weapon.icon)
        icon_names.extend(icon for icon, _level in avatar.skills)
        icon_names.extend(avatar.constellation_icons)
        icon_names.extend(piece.icon or "" for piece in avatar.pieces)
        icons = await self.enka.download_icons(icon_names)
        if not portraits:
            logger.warning(
                "立ち絵を取得できませんでした avatar_id=%s keys=%s",
                avatar.avatar_id,
                portrait_keys,
            )
        weapon_bytes = icons.get(avatar.weapon.icon) if avatar.weapon and avatar.weapon.icon else None
        showcase = EnkaShowcase(
            uid="",
            nickname="",
            level=0,
            avatars=[avatar],
            ttl=0,
        )
        try:
            return await asyncio.to_thread(
                render_build_card,
                showcase,
                avatar,
                build,
                portrait_bytes=portraits,
                weapon_bytes=weapon_bytes,
                icon_bytes=icons,
            )
        except Exception:
            logger.exception("ビルドカードの生成に失敗しました")
            return None

    async def _finish_public_card(
        self,
        interaction: discord.Interaction,
        session: UidSession,
        *,
        session_key: int,
        view: UidPickView | None = None,
    ) -> None:
        """カード画像だけチャンネルに出し、選択はそのまま残す。"""
        avatar = session.selected_avatar()
        png = await self._render_png(session)
        if avatar is None or png is None:
            await edit_original(interaction, content=t(msg.ERR_13), view=None)
            return
        channel = self._public_channel(interaction)
        if channel is None:
            await edit_original(interaction, content=t(msg.ERR_13), view=None)
            return
        file = discord.File(fp=BytesIO(png), filename="build.png")
        try:
            await channel.send(
                file=file,
                view=CardMessageView(
                    t(msg.MSG_33, nickname=session.nickname, character=avatar.name_ja)
                ),
            )
        except discord.HTTPException:
            logger.warning("カードの投稿に失敗しました channel=%s", channel.id)
            await edit_original(interaction, content=t(msg.ERR_13), view=None)
            return
        session.reset_pick()
        await edit_original(
            interaction,
            content=t(msg.MSG_34, character=avatar.name_ja),
            view=self._swap_pick_view(session_key, view),
        )

    async def publish_card(self, interaction: discord.Interaction, view: UidPickView) -> None:
        """選択完了後、チャンネルへカードだけ出す。"""
        session = self.sessions.get(view.session_key)
        avatar = session.selected_avatar() if session else None
        if session is None or avatar is None:
            await send_ephemeral(interaction, t(msg.ERR_03))
            return
        try:
            await interaction.response.defer()
        except discord.HTTPException:
            logger.warning("カード投稿の応答予約に失敗しました")
            return
        await self._finish_public_card(interaction, session, session_key=view.session_key, view=view)

    async def refresh_uid_session(self, interaction: discord.Interaction, view: UidPickView) -> None:
        """同じ UID の紹介枠を Enka から取り直す。"""
        session = self.sessions.get(view.session_key)
        if session is None:
            await send_ephemeral(interaction, t(msg.ERR_03))
            return
        for item in view.children:
            item.disabled = True
        try:
            await interaction.response.edit_message(content=t(msg.MSG_30), view=view)
        except discord.HTTPException:
            logger.warning("紹介の取り直しの応答に失敗しました")
            return
        try:
            showcase = await self.enka.fetch_showcase(session.uid, force=True)
        except EnkaError as e:
            await edit_original(
                interaction,
                content=t(msg.ERR_ENKA.get(e.code, msg.ERR_12)),
                view=self._swap_pick_view(view.session_key, view),
            )
            return
        except Exception:
            logger.exception("紹介の取り直しに失敗しました")
            await edit_original(
                interaction,
                content=t(msg.ERR_12),
                view=self._swap_pick_view(view.session_key, view),
            )
            return
        if not showcase.avatars:
            await edit_original(
                interaction,
                content=t(msg.ERR_10),
                view=self._swap_pick_view(view.session_key, view),
            )
            return
        session.apply_showcase(showcase.uid, showcase.nickname, showcase.avatars)
        await edit_original(
            interaction,
            content=t(msg.MSG_56),
            view=self._swap_pick_view(view.session_key, view),
        )

    @buildcard.command(name="ping", description=msg.MSG_07)
    async def ping_cmd(self, interaction: discord.Interaction) -> None:
        await send_ephemeral(
            interaction,
            t(msg.MSG_15, ms=str(round(self.bot.latency * 1000))),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BuildCog(bot))
