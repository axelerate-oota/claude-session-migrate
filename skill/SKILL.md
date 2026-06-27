---
name: session-migrate
description: >-
  macOS版 Claude Code デスクトップアプリで、アカウント切り替えにより一覧から消えた
  セッション履歴を別アカウントへ引き継いで復活させる。会話本体(.jsonl)はアカウント
  非依存で残っているため、GUIの索引ファイルを今ログイン中アカウントのフォルダへ
  コピーするだけで履歴が戻る。Use when user says "session-migrate", "セッション移管",
  "履歴 復活", "アカウント切り替えで履歴が消えた", "過去セッションが見えない",
  "別アカウントに履歴を移したい", "session history disappeared". Do NOT use for
  ~/.claude/projects の .jsonl 直接編集、会話内容の検索・閲覧のみ、
  Windows/Linux環境、ブラウザ版claude.aiの履歴。
---

# session-migrate

macOS版 Claude Code（Claudeデスクトップアプリの Code タブ）で、アカウントを切り替えると過去セッションが一覧から消える問題を解決する。**データは消えておらず、表示アカウントが変わっただけ**。GUIの索引ファイルを今のアカウントへコピーして履歴を復活させる。

## 仕組み（これだけ理解すれば良い）

- 会話本体: `~/.claude/projects/<encoded-path>/<sessionId>.jsonl` … **アカウント情報を持たない共有データ**。絶対に編集しない。
- GUI索引: `~/Library/Application Support/Claude/claude-code-sessions/<accountUuid>/<orgUuid>/local_*.json` … 一覧表示はこれだけを見る。`cliSessionId` で会話本体に対応。
- アカウント切替＝別UUIDフォルダを見にいく＝前アカウントの索引が一覧から消える。
- 解決＝消えて見えるアカウントの `local_*.json` を、今ログイン中アカウントのフォルダへ**コピー**するだけ。会話本体は共有なので開けば中身も読める。

## 重要な安全チェック（最初に必ず実行）

### 1. macOS か確認
macOS 専用。`scripts/migrate.py` は darwin 以外で自動停止する。

### 2. 「ターミナルCLI」か「デスクトップアプリ内」かを見極める（最重要）
コピー作業中は **Claudeデスクトップアプリを終了している必要がある**。

- **ターミナルの `claude` で実行中**（Terminal/iTerm等）→ Claude自身がアプリを終了してよい:
  ```bash
  osascript -e 'quit app "Claude"'
  ```
  終了後にコピーし、最後に「アプリを再起動して」と案内する。
- **デスクトップアプリの Code タブ内で実行中** → **アプリを終了すると自分のセッションごと落ちる**。Claudeからは終了させず、ユーザーに「アプリを完全終了 → ターミナルで `claude` を開いて再実行」を案内するか、手順だけ提示する。
- 判別が曖昧なら必ずユーザーに「今ターミナルで動かしていますか？」と確認する。誤ってアプリを落とすと体験を損なう。

## 手順

引数を見て分岐（未指定なら対話で進める）。`list` だけ求められたら一覧表示で止める。

### ステップ1: 一覧表示
```bash
python3 scripts/migrate.py list
```
各 `<account>/<org>` 組を番号付きで表示（件数・最新日時・最新タイトル）。
- **件数が多い／見覚えのあるタイトルがある方** = コピー元（履歴が残っているアカウント）
- **「今ログイン中の可能性大」マークが付く方** = コピー先

この一覧をユーザーに見せ、コピー元/先の番号を確認する。自動判定が怪しければ必ずユーザーに選ばせる。

### ステップ2: アプリ終了（上の安全チェックに従う）
ターミナル実行なら `osascript -e 'quit app "Claude"'`。アプリ内実行ならユーザーに終了を依頼。

### ステップ3: コピー実行
```bash
python3 scripts/migrate.py copy --src <元の番号> --dst <先の番号>          # 直近2日(既定)
python3 scripts/migrate.py copy --src <元> --dst <先> --days 7             # 直近7日
python3 scripts/migrate.py copy --src <元> --dst <先> --days 0             # 全件
```
スクリプトは**コピー前にコピー先を自動バックアップ**し、何をコピーしたか一覧表示する。既存セッションは自動スキップ。

引数マッピング: `--days N` → `--days N`、`--all` → `--days 0`、無指定 → `--days 2`。

### ステップ4: 確認案内
1. Claudeデスクトップアプリを起動
2. Code タブの一覧に履歴が戻っていれば成功
3. 出ない場合 → 一度アプリ終了して `copy` を再実行。それでも駄目なら元アカウントへ再ログインが確実、と伝える。

## 注意（ユーザーに必ず伝える）

- 非公式手順。アプリ更新でフォルダ構造が変わると動かなくなる可能性がある。
- macOS専用。`.jsonl`（会話本体）は触らない。
- バックアップは `claude-code-sessions-backup-<日時>` に残る（パスはスクリプト出力に表示）。不要なら削除を案内。

## Resources

- `scripts/migrate.py` - 一覧表示(list)・索引コピー(copy)を行うエンジン。バックアップ自動。
