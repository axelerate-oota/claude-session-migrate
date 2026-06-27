#!/usr/bin/env python3
"""
migrate.py — Claude Code (desktop) のセッション履歴を別アカウントへ引き継ぐエンジン。

背景:
  会話本体は ~/.claude/projects/.../*.jsonl にアカウント非依存で保存される。
  GUI一覧は ~/Library/Application Support/Claude/claude-code-sessions/
    <accountUuid>/<orgUuid>/local_*.json という索引だけを見ている。
  アカウント切替で履歴が消えて見えるのは、別UUIDフォルダを見にいくから。
  → 索引ファイルを今のアカウントのフォルダにコピーすれば履歴が復活する。

macOS 専用。サブコマンド:
  list                                       アカウント/セッションを一覧（JSON or 表）
  copy --src <i> --dst <i> [--days N]        i番のアカウントからi番へ索引をコピー
                                             --days 0 で全件、未指定は2

実行前に Claude デスクトップアプリを終了しておくこと。
"""
import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime

BASE = os.path.expanduser(
    "~/Library/Application Support/Claude/claude-code-sessions"
)


def fail(msg, code=1):
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(code)


def guard_macos():
    if sys.platform != "darwin":
        fail("このツールは macOS 専用です。")


def find_pairs():
    """<account>/<org> のディレクトリ組を返す（パスのリスト、ソート済み）。"""
    if not os.path.isdir(BASE):
        fail(
            "セッションフォルダが見つかりません:\n   "
            + BASE
            + "\n   Claude デスクトップアプリ(macOS版)がインストールされていますか？"
        )
    pairs = []
    for acct in sorted(os.listdir(BASE)):
        ap = os.path.join(BASE, acct)
        if not os.path.isdir(ap) or acct.startswith("."):
            continue
        for org in sorted(os.listdir(ap)):
            op = os.path.join(ap, org)
            if os.path.isdir(op) and not org.startswith("."):
                pairs.append(op)
    if not pairs:
        fail("アカウントフォルダが見つかりませんでした。")
    return pairs


def summarize(pair_path):
    """1組のセッション数・最新タイトル・最新activity(ms)を返す。"""
    files = [f for f in os.listdir(pair_path) if f.endswith(".json")]
    latest_ms, latest_title = 0, "(なし)"
    for f in files:
        try:
            d = json.load(open(os.path.join(pair_path, f)))
        except Exception:
            continue
        la = d.get("lastActivityAt") or d.get("createdAt") or 0
        if la > latest_ms:
            latest_ms = la
            latest_title = d.get("title") or "無題"
    return {
        "path": pair_path,
        "rel": os.path.relpath(pair_path, BASE),
        "count": len(files),
        "latest_ms": latest_ms,
        "latest_title": latest_title,
    }


def cmd_list(as_json):
    pairs = find_pairs()
    rows = [summarize(p) for p in pairs]
    # 最新activityが最も新しい組を「現在ログイン中の可能性が高い」とみなす
    current_idx = max(range(len(rows)), key=lambda i: rows[i]["latest_ms"])
    for i, r in enumerate(rows):
        r["index"] = i
        r["likely_current"] = i == current_idx

    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    print(f"検出フォルダ: {BASE}\n")
    for r in rows:
        when = (
            datetime.fromtimestamp(r["latest_ms"] / 1000).strftime("%Y-%m-%d %H:%M")
            if r["latest_ms"]
            else "-"
        )
        mark = " ← 今ログイン中の可能性大" if r["likely_current"] else ""
        print(f"[{r['index']}] {r['count']:>3}件  最新 {when}{mark}")
        print(f"      最新タイトル: {r['latest_title'][:46]}")
        print(f"      {r['rel']}\n")
    print("ヒント: 件数が多い方=履歴が残っているアカウント(コピー元)。")
    print("        『今ログイン中の可能性大』がコピー先の候補。")


def cmd_copy(src_i, dst_i, days):
    pairs = find_pairs()
    if not (0 <= src_i < len(pairs)) or not (0 <= dst_i < len(pairs)):
        fail("番号が範囲外です。先に list を実行して番号を確認してください。")
    if src_i == dst_i:
        fail("コピー元とコピー先が同じです。")
    src, dst = pairs[src_i], pairs[dst_i]

    # バックアップ（コピー先フォルダを丸ごと退避）
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bk = f"{BASE}-backup-{stamp}"
    os.makedirs(bk, exist_ok=True)
    bk_dst = os.path.join(bk, os.path.relpath(dst, BASE))
    os.makedirs(os.path.dirname(bk_dst), exist_ok=True)
    shutil.copytree(dst, bk_dst)
    print(f"🛟 バックアップ: {bk}\n")

    now_ms = int(time.time() * 1000)
    threshold = 0 if days == 0 else now_ms - days * 24 * 3600 * 1000

    copied, skipped = [], []
    for fn in sorted(os.listdir(src)):
        if not fn.endswith(".json"):
            continue
        sp = os.path.join(src, fn)
        try:
            d = json.load(open(sp))
        except Exception:
            continue
        la = d.get("lastActivityAt") or d.get("createdAt") or 0
        if la < threshold:
            continue
        title = (d.get("title") or "無題")[:44]
        when = datetime.fromtimestamp(la / 1000).strftime("%m-%d %H:%M") if la else "-"
        dp = os.path.join(dst, fn)
        if os.path.exists(dp):
            skipped.append((when, title))
            continue
        shutil.copy2(sp, dp)
        copied.append((when, title))

    for when, t in sorted(copied, reverse=True):
        print(f"  ✅ {when}  {t}")
    for when, t in sorted(skipped, reverse=True):
        print(f"  ⏭  {when}  {t}  (既存・スキップ)")
    print(f"\nコピー {len(copied)}件 / スキップ {len(skipped)}件")
    print(f"バックアップを消すには: rm -rf '{bk}'")


def main():
    guard_macos()
    p = argparse.ArgumentParser(description="Claude Code session migrator (macOS)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", help="アカウント/セッションを一覧")
    pl.add_argument("--json", action="store_true", help="JSONで出力")

    pc = sub.add_parser("copy", help="索引を別アカウントへコピー")
    pc.add_argument("--src", type=int, required=True, help="コピー元の番号")
    pc.add_argument("--dst", type=int, required=True, help="コピー先の番号")
    pc.add_argument("--days", type=int, default=2, help="直近N日(0=全件, 既定2)")

    a = p.parse_args()
    if a.cmd == "list":
        cmd_list(a.json)
    elif a.cmd == "copy":
        cmd_copy(a.src, a.dst, a.days)


if __name__ == "__main__":
    main()
