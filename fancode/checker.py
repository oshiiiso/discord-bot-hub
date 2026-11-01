"""全ゲームの交換コードチェック処理のコアロジックを担当するモジュール。"""
import discord

from .config import GAME_CONFIG
from .logger_setup import debug_log, info_log
from .storage import (
    load_saved_codes,
    save_current_codes,
    load_message_id,
    save_message_id,
    sent_codes_exists,
    save_codes_data,
    save_last_check,
    append_history,
)
from .scraper import fetch_latest_codes
from .embeds import create_list_embed
from .addition_notices import register_addition_notice


def _post_permission_warning(channel, game_name: str) -> str | None:
    """投稿できない理由。問題なければ None。"""
    guild = getattr(channel, "guild", None)
    me = getattr(guild, "me", None) if guild is not None else None
    if me is None:
        return None
    perms = channel.permissions_for(me)
    missing: list[str] = []
    if not perms.view_channel:
        missing.append("チャンネルを見る")
    if not perms.send_messages:
        missing.append("メッセージを送信")
    if not perms.embed_links:
        missing.append("埋め込みリンク")
    if not missing:
        return None
    name = getattr(channel, "name", str(getattr(channel, "id", "?")))
    return (
        f"[警告] {game_name} の #{name} に投稿できない。"
        f"チャンネル（または親カテゴリ）の権限で Bot に「{' / '.join(missing)}」を付けてね"
    )


async def get_game_channel(bot, channel_id: int):
    """設定チャンネルを取得する。キャッシュに無ければ API から取る。"""
    if not channel_id:
        return None
    channel = bot.get_channel(channel_id)
    if channel is not None:
        return channel
    try:
        return await bot.fetch_channel(channel_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
        info_log(f"[警告] チャンネル取得に失敗しました (id={channel_id}): {e}")
        return None


async def run_check_all_games(bot):
    """全ゲームのコードチェック処理本体（初回・定期実行共通）"""
    debug_log("=== 全ゲームの定期チェックを開始 ===")

    for key, config in GAME_CONFIG.items():
        try:
            channel = await get_game_channel(bot, config["channel_id"])
            if not channel:
                info_log(
                    f"[警告] {config['name']} のチャンネルが見つかりません。"
                    f"(チャンネルIDの設定を確認してください / id={config['channel_id']})"
                )
                continue
            permission_warning = _post_permission_warning(channel, config["name"])
            if permission_warning:
                info_log(permission_warning)
                continue

            is_first_run = not sent_codes_exists(key)

            current_codes = fetch_latest_codes(key, config["url"])
            if current_codes is None:
                # ページ取得やテーブル解析に失敗した場合は、
                # 「有効なコードが0件」として誤保存しないようスキップする。
                info_log(f"[警告] {config['name']} のコード取得に失敗したため、今回のチェックをスキップします。")
                continue

            saved_codes = load_saved_codes(key)
            current_keys = set(current_codes.keys())

            added_codes = current_keys - saved_codes
            removed_codes = saved_codes - current_keys

            if added_codes or removed_codes or is_first_run:
                save_current_codes(key, current_keys)

                if not is_first_run:
                    if added_codes:
                        info_log(f"【{config['name']}】新しい交換コードが追加されました: {', '.join(added_codes)}")
                        append_history(key, "added", added_codes)
                    if removed_codes:
                        del_code_str = ", ".join([f"`{c}`" for c in removed_codes])
                        info_log(f"【{config['name']}】コードが期限切れになりました: {del_code_str}")
                        append_history(key, "removed", removed_codes)

            # 一覧の固定メッセージは、変更の有無に関わらず毎回編集して
            # 「最終確認」時刻を更新する。
            save_codes_data(key, current_codes)
            save_last_check(key)
            fixed_msg_id = load_message_id(key)
            embed = create_list_embed(config["name"], current_codes, config)

            try:
                if fixed_msg_id:
                    try:
                        msg = await channel.fetch_message(fixed_msg_id)
                        await msg.edit(embed=embed)
                        debug_log(f"【{config['name']}】一覧メッセージを更新しました。")
                    except discord.HTTPException as e:
                        # 削除済みなど、編集できない場合は新規投稿し直す
                        msg = await channel.send(embed=embed)
                        save_message_id(key, msg.id)
                        info_log(
                            f"【{config['name']}】一覧メッセージを更新できなかったため、新規投稿しました: {e}"
                        )
                else:
                    msg = await channel.send(embed=embed)
                    save_message_id(key, msg.id)
                    info_log(f"【{config['name']}】新しく一覧メッセージを投稿しました。")

                # コードが追加された場合のみ、別途お知らせメッセージを投稿する(3日後に自動削除)
                if not is_first_run and added_codes:
                    code_str = ", ".join(f"`{c}`" for c in added_codes)
                    notice = await channel.send(
                        f"🎉 【{config['name']}】新しい交換コードが追加されました：{code_str}",
                    )
                    register_addition_notice(bot, notice)
            except discord.Forbidden:
                info_log(
                    f"[警告] {config['name']} のチャンネルに投稿する権限がないよ。"
                    "チャンネル（または親カテゴリ）の権限で Bot に"
                    "「チャンネルを見る / メッセージを送信 / 埋め込みリンク」を付けてね"
                )
                continue

            if not (added_codes or removed_codes or is_first_run):
                debug_log(f"【{config['name']}】変更はありません。")
        except Exception as e:
            # 1ゲームのエラーでループ全体が止まらないようにする
            info_log(f"[エラー] {config['name']} の処理中に例外が発生しました: {e}")

    debug_log("=== 全ゲームのチェックが完了しました ===")
