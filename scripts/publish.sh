#!/bin/bash
# data/ を書き換えたあと、これを実行すればサイトに反映されます。
#   ./scripts/publish.sh              → 「サイト更新」というメモで反映
#   ./scripts/publish.sh "9月の説明会" → メモを自分で書く
#
# git の順番（コミット→取り込み→push）を間違えると弾かれるので、
# ここでまとめて面倒を見ています。

set -euo pipefail
cd "$(dirname "$0")/.."

# JSON が壊れていたら反映しない（壊れたまま公開されるのを防ぐ）
for f in data/*.json; do
  err=$(python3 -c "
import json,sys
try: json.load(open(sys.argv[1]))
except Exception as e: print(e); sys.exit(1)
" "$f" 2>&1) || {
    echo "❌ $f の書式が壊れています。反映を中止しました。"
    echo "   $err"
    echo "   （よくある原因: カンマの付け忘れ・余分なカンマ・閉じ括弧の不足）"
    exit 1
  }
done

# profile.json を直したとき、構造化データが古いまま残らないようにする
# （検索エンジンに渡す内容とページの表示がズレると逆効果になるため）
python3 scripts/build_jsonld.py || {
  echo "❌ 構造化データを作れませんでした。反映を中止しました。"
  exit 1
}

git add -A
if git diff --cached --quiet; then
  echo "変更はありませんでした。"
  exit 0
fi

echo "── 変更されたファイル ──"
git diff --cached --name-only | sed 's/^/  /'

git commit -qm "${1:-サイト更新}"
git pull --rebase --autostash -q origin main   # 自動更新のコミットを先に取り込む
git push -q origin main

echo
echo "✅ 反映しました。1〜2分で https://yukikotani5.github.io/ に出ます。"
echo "   進行状況: https://github.com/yukikotani5/yukikotani5.github.io/actions"
