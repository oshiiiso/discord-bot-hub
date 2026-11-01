# Discord Bot - おしーそBot（hub）

交換コード通知・原神ビルドカード・募集 VC を1プロセスにまとめた Bot（Python + discord.py）

個人・身内利用向けに開発した Bot です。ソースは公開しています。**不特定多数向けの配布・運用は想定していません**が、ソースの使い方は基本的に自由です。自分のサーバーで動かしたい場合は、[Issues](https://github.com/oshiiiso/discord-bot-hub/issues) か連絡をもらえればセットアップを補助します。

Discord 上の表示名は `おしーそBot`。TikTok 監視と AutoMuteUs は別プロセスのままです。FanCode / BuildCard / Among Us 用 Bot はこのリポジトリに統合しました。

- リポジトリ: https://github.com/oshiiiso/discord-bot-hub
- 不具合・要望: [Issues](https://github.com/oshiiiso/discord-bot-hub/issues)
- 使い方: [docs/USER.md](docs/USER.md)

## 機能概要

- **FanCode** … HoYoverse 系ゲームの交換コードを Wiki から取得し、固定メッセージで通知（`/fancode`）
- **BuildCard** … 原神 UID から聖遺物スコア入りビルドカード（`/buildcard`）
- **VC マネージャ** … 部屋作成パネルから、自由作成カテゴリに募集 VC を出す（`/vc`）

## ディレクトリ構成

```
main.py                 # エントリーポイント
bot.py                  # Bot 本体・Cog 読み込み
config.py               # 環境変数の読み込み
logging_config.py       # ログ設定
cogs/                   # スラッシュコマンド（機能ごと）
fancode/                # 交換コード取得・保存
games/ / services/ / ui/  # ビルドカード
vc_manager/             # 一時 VC
messages.py             # ビルドカードのユーザー向け文言
data/genshin/           # キャラ・セット表
docs/USER.md            # セットアップ・運用ガイド
storage/                # 実行時キャッシュ（.gitignore）
logs/                   # ログ（.gitignore）
tests/                  # 回帰テスト
```

## 開発環境セットアップ

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # トークン・チャンネル ID を編集
python main.py
```

詳細な手順・権限設定・コマンド一覧は [docs/USER.md](docs/USER.md) を参照。

### 環境変数（`.env`）

| 変数 | 説明 | デフォルト |
|---|---|---|
| `DISCORD_BOT_TOKEN` | Bot トークン | —（必須） |
| `GUILD_ID` | 動作させるサーバー ID | 未設定時はグローバル同期 |
| `GENSHIN_CHANNEL_ID` 等 | 交換コード通知チャンネル | — |
| `CHECK_INTERVAL_HOURS` | コード自動チェック間隔（時間） | `1` |
| `BUILDCARD_CHANNEL_ID` | ビルドカード用テキストチャンネル | — |
| `VC_PANEL_CHANNEL_ID` | 部屋作成パネルを置くテキストチャンネル | 未設定なら `/vc panel` を実行したチャンネル |
| `VC_RECRUIT_CHANNEL_ID` | 募集埋め込みを出すテキストチャンネル | — |
| `VC_CREATE_CATEGORY_ID` | 自由作成 VC を置くカテゴリ | — |
| `VC_EMPTY_GRACE_SECONDS` | 一度入ったあと 0人になってから部屋を消すまでの秒数 | `10` |
| `VC_VACANT_TIMEOUT_SECONDS` | 誰も入らない部屋を消すまでの秒数 | `300` |
| `VC_CREATE_COOLDOWN_SECONDS` | 同一ユーザーの部屋作成間隔 | `30` |
| `EPHEMERAL_DELETE_SECONDS` | コマンド等の短い確認を消すまでの秒数 | `5` |
| `LOG_LEVEL` | DEBUG / INFO / WARNING / ERROR | `INFO` |
| `LOG_RETENTION_DAYS` | ログ保持日数 | `30` |
| `ENKA_ASSET_RETENTION_DAYS` | 立ち絵などの画像キャッシュ保持日数（`0` で消さない） | `30` |
| `CHARACTER_LEARN_HOURS` | 公開図鑑を見にいく間隔（時間）。`0` で定期取得しない | `24` |

`.env` は Git に含めません。旧 BuildCard の `DISCORD_TOKEN` / `CHANNEL_ID` も読めます。

## ブランチ運用

| ブランチ | 用途 |
|---------|------|
| **develop** | 日常の開発 |
| **main** | 確定版（develop からマージ。タグ `v*` で版を管理） |

## 注意事項

- 交換コードは Fandom Wiki、ビルドカードは Enka.Network に依存します。障害・仕様変更のリスクは自己責任でください。
- 本 Bot は個人サーバー向けです。公開サービスとしての提供は想定していません。
- このリポジトリのライセンス（MIT）が及ぶのは **ソースコードだけ** です。原神の立ち絵・名称や Enka から取得するデータは、それぞれの権利者のものです。

## ライセンス

MIT License — Copyright (c) 2026 oshiiiso

詳細は [LICENSE](LICENSE) を参照。
