#!/usr/bin/env bash
#
# session-migrate.sh
# Claude Code（デスクトップアプリ）のセッション履歴を、別アカウントへ引き継ぐツール。
#
# アカウントを切り替えると過去セッションが一覧から消えますが、データは残っています。
# このスクリプトは、消えて見えるアカウントのセッション索引を
# 今ログイン中のアカウントへコピーして、再び一覧に表示させます。
#
# 仕組み:
#   会話本体は ~/.claude/projects/.../*.jsonl に「アカウント非依存」で保存されている。
#   GUIの一覧は ~/Library/Application Support/Claude/claude-code-sessions/
#     <アカウントUUID>/<組織UUID>/local_*.json という索引ファイルだけを見ている。
#   なので、この索引ファイルを別アカウントのフォルダにコピーするだけで履歴が「復活」する。
#
# 対応OS: macOS のみ
# 免責: 非公式な手順です。アプリのアップデートでフォルダ構造が変わると動かなくなる可能性があります。
#       実行前に必ずアプリを終了してください。自己責任でお願いします。
#
set -euo pipefail

BASE="$HOME/Library/Application Support/Claude/claude-code-sessions"

if [[ ! -d "$BASE" ]]; then
  echo "❌ セッションフォルダが見つかりません:"
  echo "   $BASE"
  echo "   Claude デスクトップアプリ（macOS版）がインストールされていますか？"
  exit 1
fi

echo "============================================================"
echo " Claude Code セッション移管ツール (session-migrate)"
echo "============================================================"
echo
echo "⚠️  実行前に Claude デスクトップアプリを必ず終了してください。"
echo "    起動中だと内部データが上書きされ、反映されない/壊れる恐れがあります。"
echo
read -r -p "アプリは終了しましたか？ (y/N): " ok
[[ "${ok:-N}" =~ ^[Yy]$ ]] || { echo "中止しました。アプリを終了してから再実行してください。"; exit 0; }
echo

# --- アカウント一覧を表示（各 <アカウント>/<組織> の組をインデックス付きで列挙） -------------
echo "▼ 検出したアカウント／セッション一覧"
echo

mapfile -t PAIRS < <(find "$BASE" -mindepth 2 -maxdepth 2 -type d 2>/dev/null | sort)
if [[ ${#PAIRS[@]} -eq 0 ]]; then
  echo "❌ アカウントフォルダが見つかりませんでした。"
  exit 1
fi

i=0
for d in "${PAIRS[@]}"; do
  n=$(find "$d" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
  latest=$(ls -t "$d"/*.json 2>/dev/null | head -1 || true)
  title="(なし)"
  if [[ -n "$latest" ]]; then
    title=$(python3 -c "import json,sys
try:
  d=json.load(open(sys.argv[1])); print((d.get('title') or '無題')[:38])
except: print('?')" "$latest" 2>/dev/null || echo "?")
  fi
  rel="${d#$BASE/}"
  printf "  [%d] %-3s件  最新: %-40s\n        %s\n" "$i" "$n" "$title" "$rel"
  i=$((i+1))
done
echo

read -r -p "コピー元（履歴が消えて見える方）の番号: " SRC_IDX
read -r -p "コピー先（今ログイン中の方）の番号: " DST_IDX

SRC="${PAIRS[$SRC_IDX]}"
DST="${PAIRS[$DST_IDX]}"

if [[ "$SRC" == "$DST" ]]; then
  echo "❌ コピー元とコピー先が同じです。中止します。"
  exit 1
fi

echo
echo "コピー元: ${SRC#$BASE/}"
echo "コピー先: ${DST#$BASE/}"
echo
echo "▼ コピーする範囲を選択"
echo "  [1] 直近 2 日間"
echo "  [2] 直近 7 日間"
echo "  [3] すべて"
read -r -p "選択 (1/2/3): " RANGE
case "${RANGE:-1}" in
  1) DAYS=2 ;;
  2) DAYS=7 ;;
  3) DAYS=0 ;;   # 0 = 無制限
  *) echo "不正な入力。中止します。"; exit 1 ;;
esac

# --- バックアップ -------------------------------------------------------------
STAMP=$(date +%Y%m%d-%H%M%S)
BK="$BASE-backup-$STAMP"
mkdir -p "$BK"
cp -R "$DST" "$BK/" 2>/dev/null || true
echo
echo "🛟 コピー先をバックアップしました: $BK"

# --- コピー本体（Pythonで日付判定して索引jsonをコピー） ----------------------
python3 - "$SRC" "$DST" "$DAYS" <<'PY'
import json, os, sys, shutil, time, datetime

SRC, DST, DAYS = sys.argv[1], sys.argv[2], int(sys.argv[3])
now_ms = int(time.time() * 1000)
threshold = 0 if DAYS == 0 else now_ms - DAYS * 24 * 3600 * 1000

copied, skipped = [], []
for fn in sorted(os.listdir(SRC)):
    if not fn.endswith(".json"):
        continue
    sp = os.path.join(SRC, fn)
    try:
        d = json.load(open(sp))
    except Exception:
        continue
    la = d.get("lastActivityAt") or d.get("createdAt") or 0
    if la < threshold:
        continue
    dp = os.path.join(DST, fn)
    title = (d.get("title") or "無題")[:40]
    dt = datetime.datetime.fromtimestamp(la / 1000).strftime("%m-%d %H:%M")
    if os.path.exists(dp):
        skipped.append((dt, title))
        continue
    shutil.copy2(sp, dp)
    copied.append((dt, title))

print()
for dt, t in sorted(copied, reverse=True):
    print(f"  ✅ {dt}  {t}")
for dt, t in sorted(skipped, reverse=True):
    print(f"  ⏭  {dt}  {t}  (既に存在・スキップ)")

print()
print(f"コピー完了: {len(copied)} 件 / スキップ: {len(skipped)} 件")
PY

echo
echo "============================================================"
echo " 完了しました 🎉"
echo "============================================================"
echo "1. Claude デスクトップアプリを起動してください。"
echo "2. Code タブのセッション一覧に履歴が出ていれば成功です。"
echo
echo "うまく出ない場合:"
echo "  - 一度アプリを終了して、このスクリプトをもう一度実行"
echo "  - それでも駄目なら、元のアカウントにログインし直すのが確実です。"
echo
echo "バックアップを消したいとき:"
echo "  rm -rf \"$BK\""
