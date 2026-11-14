"""VC マネージャのユーザー向け文言。"""

MSG_GROUP_DESCRIPTION = "募集用のボイスチャンネル"
MSG_CMD_PING = "応答速度を確認する"
MSG_CMD_PANEL = "部屋作成パネルを設置する"
MSG_PING = "Pong! {ms}ms"
MSG_JOIN_BUTTON = "参加する"
MSG_JOIN_BUTTON_EMOJI = "▶️"
MSG_CREATE_BUTTON = "部屋を作る"
MSG_CREATE_BUTTON_EMOJI = "➕"
MSG_PANEL_TITLE = "募集部屋を作る"
MSG_PANEL_DESCRIPTION = "下のボタンから募集用のボイスを作れるよ。できた部屋は募集チャンネルに出るよ。"
MSG_PANEL_FIELD_HOW = "📋 使い方"
MSG_PANEL_HOW = (
    "1. 先にどこかのボイスへ入っておくと、できた部屋へそのまま移るよ\n\n"
    "2. 「部屋を作る」を押して種類を選ぶ。部屋名・詳細は任意。人数無制限は最初オン\n\n"
    "3. 募集の「ここから参加」から、他の人も入れる"
)
MSG_PANEL_FIELD_NOTE = "📌 きまり"
MSG_PANEL_NOTE = (
    "誰も入らない部屋は{vacant}で消えるよ\n\n"
    "全員が出たら{empty}で消えるよ\n\n"
    "連続作成は{cooldown}空けてね"
)
MSG_PANEL_FIELD_EXAMPLE = "🏠 部屋名の例"
MSG_PANEL_FOOTER = "原神-探索 / 雑談"
MSG_PANEL_DONE = "パネルを設置したよ"
MSG_PANEL_PIN_FAILED = "パネルは出したけどピン留めできなかった"
MSG_PANEL_CHANNEL_MISSING = "部屋作成チャンネルが見つからないよ"
MSG_PANEL_MISSING_PERMS = "Bot に「{perms}」が足りないよ"
MSG_PERM_VIEW = "チャンネルを見る"
MSG_PERM_SEND = "メッセージを送信"
MSG_PERM_EMBED = "埋め込みリンク"
MSG_PERM_HISTORY = "メッセージ履歴を読む"
MSG_MODAL_TITLE = "部屋の作成"
MSG_MODAL_KIND = "種類"
MSG_MODAL_KIND_DESC = "どれか1つ選んでね"
MSG_MODAL_KIND_PLACEHOLDER = "種類を選んでね"
MSG_ROOM_KINDS = (
    ("genshin", "原神"),
    ("zzz", "ゼンゼロ"),
    ("starrail", "スタレ"),
    ("wuthering", "鳴潮"),
    ("valorant", "VALORANT"),
    ("amongus", "Among Us"),
    ("chat", "雑談"),
    ("other", "その他"),
)
ROOM_KIND_LABELS = dict(MSG_ROOM_KINDS)
MSG_MODAL_NAME = "部屋名"
MSG_MODAL_NAME_DESC = "任意。空なら種類名だけになるよ"
MSG_MODAL_NAME_PLACEHOLDER = "例) 探索 / ランク戦 / ゲーム名"
MSG_MODAL_DETAILS = "詳細"
MSG_MODAL_DETAILS_DESC = "任意。募集にだけ出るよ。何時までもここに書いてね"
MSG_MODAL_DETAILS_PLACEHOLDER = "例: 世界ランク60 / 夜まで / 初心者歓迎"
MSG_MODAL_UNLIMITED = "人数無制限"
MSG_MODAL_UNLIMITED_DESC = "⚠️ オンのままが無制限。人数欄に数字があっても無視するよ"
MSG_MODAL_OCCUPANCY = "入室人数"
MSG_MODAL_OCCUPANCY_DESC = "⚠️ 無制限を外したときだけ有効。1〜99の数字。全角でもOK"
MSG_MODAL_OCCUPANCY_PLACEHOLDER = "1〜99"
MSG_OCCUPANCY_INVALID = "無制限を外したら、入室人数は 1〜99 の数字で入れてね"
MSG_OCCUPANCY_UNLIMITED = "無制限"
MSG_KIND_INVALID = "種類を選び直してね"
MSG_CREATING = "今つくってるよ。少し待ってね"
MSG_CREATED = "部屋を作ったよ。募集チャンネルに出したよ"
MSG_CREATED_MOVED = "部屋を作ったよ。そちらに移したよ"
MSG_CREATED_JOIN = "部屋を作ったよ。ボイスに入っていないので、このリンクから入ってね。\n{url}"
MSG_JOIN_MOVED = "部屋に入ったよ"
MSG_EMBED_DESCRIPTION = "{mention} が部屋を作りました"
MSG_EMBED_KIND = "🎮 種類"
MSG_EMBED_CAPACITY = "👥 人数"
MSG_EMBED_ROOM = "▶️ ここから参加"
MSG_JOIN_LINK = "このリンクから参加できるよ\n{url}"
MSG_ROOM_GONE = "この部屋はもう無いよ"
MSG_INVITE_FAILED = "参加リンクを作れなかった。少し待って再試してね"
MSG_NOT_CONFIGURED = "VC マネージャのチャンネルがまだ設定されていないよ"
MSG_CREATE_FAILED = "部屋を作れなかった。Bot のチャンネル管理権限を見てね"
MSG_MOVE_FAILED = "部屋は作ったけど移動できなかった。接続し直してね"
MSG_COOLDOWN = "部屋の作成は少し間を空けてね（あと約{seconds}秒）"
