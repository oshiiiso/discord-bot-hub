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
    "2. 「部屋を作る」を押して種類を選ぶ。部屋名・何時まで・詳細・人数は任意\n\n"
    "3. 募集チャンネルの部屋名から、他の人も入れる"
)
MSG_PANEL_FIELD_NOTE = "📌 きまり"
MSG_PANEL_NOTE = (
    "誰も入らない部屋は{vacant}で消えるよ\n\n"
    "全員が出たら{empty}で消えるよ\n\n"
    "連続作成は{cooldown}空けてね"
)
MSG_PANEL_FIELD_EXAMPLE = "🏠 部屋名の例"
MSG_PANEL_FOOTER = "原神-探索-夜まで / 雑談"
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
MSG_MODAL_UNTIL = "何時まで"
MSG_MODAL_UNTIL_DESC = "任意。部屋名の末尾と募集に出るよ"
MSG_MODAL_UNTIL_PLACEHOLDER = "例: 25:00 / 夜まで / 終わるまで"
MSG_MODAL_DETAILS = "詳細"
MSG_MODAL_DETAILS_DESC = "任意。募集にだけ出るよ"
MSG_MODAL_DETAILS_PLACEHOLDER = "例: 世界ランク60 / 初心者歓迎"
MSG_MODAL_OCCUPANCY = "入室人数"
MSG_MODAL_OCCUPANCY_DESC = "1〜15の数字。全角でもOK。このままで15人"
MSG_MODAL_OCCUPANCY_PLACEHOLDER = "1〜15（空なら15）"
MSG_OCCUPANCY_INVALID = "入室人数は 1〜15 の数字で入れてね"
MSG_KIND_INVALID = "種類を選び直してね"
MSG_CREATING = "今つくってるよ。少し待ってね"
MSG_CREATED = "部屋を作ったよ。募集チャンネルに出したよ"
MSG_CREATED_MOVED = "部屋を作ったよ。そちらに移したよ"
MSG_CREATED_JOIN = "部屋を作ったよ。ボイスに入っていないので、このリンクから入ってね。\n{url}"
MSG_JOIN_MOVED = "部屋に入ったよ"
MSG_EMBED_DESCRIPTION = "{mention} が部屋を作りました"
MSG_EMBED_KIND = "🎮 種類"
MSG_EMBED_CAPACITY = "👥 人数"
MSG_EMBED_UNTIL = "🕒 何時まで"
MSG_EMBED_ROOM = "🔊 部屋"
MSG_JOIN_LINK = "このリンクから参加できるよ\n{url}"
MSG_ROOM_GONE = "この部屋はもう無いよ"
MSG_INVITE_FAILED = "参加リンクを作れなかった。少し待って再試してね"
MSG_NOT_CONFIGURED = "VC マネージャのチャンネルがまだ設定されていないよ"
MSG_CREATE_FAILED = "部屋を作れなかった。Bot のチャンネル管理権限を見てね"
MSG_MOVE_FAILED = "部屋は作ったけど移動できなかった。接続し直してね"
MSG_COOLDOWN = "部屋の作成は少し間を空けてね（あと約{seconds}秒）"
