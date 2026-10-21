#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
和文原稿のページ番号を CiNii Research から埋めます。

  python3 scripts/fill_pages.py          足りないものを探して、確実なものだけ埋める
  python3 scripts/fill_pages.py --dry    何を埋めるかだけ表示して、書き込まない

なぜ必要か:
  雑誌が出たばかりのときは、巻号は分かってもページ番号が分かりません
  （目次ページには載らないため）。CiNii に収載されるのは数週間〜数ヶ月後です。
  「あとで確認する」を人の記憶に頼ると必ず抜けるので、毎日の更新で自動的に見に行きます。

同姓同名について:
  著者名では検索しません（CiNii で「小谷祐樹」を引くと溶接工学の別人が20件以上出ます）。
  **題名で引き、巻と号が一致したものだけ**を採用します。
  同じ誌の同じ巻号に同じ題名の別記事が載ることは無いので、これで取り違えません。
"""

import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRITINGS = os.path.join(ROOT, "data", "writings.json")
UA = "kotani-portfolio/1.0 (+https://yukikotani5.github.io/)"

# 「50(10)」は巻号のみ（ページなし）、「50(10):4-11」はページあり
VOL_NO = re.compile(r"^\s*(\d+)\s*\((\d+)\)\s*$")


def norm(s):
    """題名を比べるために均す。全角半角・空白・記号のゆれを吸収する。"""
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = re.sub(r"[\s　]+", "", s)
    # 長音「ー」と中黒「・」は語の一部なので消さない。
    # 消すと「フェーズ」が「フェズ」になり、一致しなくなる。
    s = re.sub(r"[-‐‑–—―─~〜．。，、:：;；!！?？\"'“”’（）()\[\]【】]", "", s)
    return s.lower()


def cinii(title, retries=3):
    """題名で CiNii を引く。"""
    url = "https://cir.nii.ac.jp/opensearch/all?" + urllib.parse.urlencode(
        {"q": title, "format": "json", "count": 20, "start": 1, "sortorder": 0})
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read()).get("items") or []
        except Exception as e:                                      # noqa: BLE001
            last = e
            time.sleep(2 ** i)
    raise last


def find_pages(entry):
    """巻と号が一致する記事を探して (開始, 終了) を返す。見つからなければ None。"""
    m = VOL_NO.match(entry.get("citation") or "")
    if not m:
        return None                      # 巻号が無い、またはページが既にある
    vol, no = m.group(1), m.group(2)
    want = norm(entry.get("title"))
    jr = norm(entry.get("journal"))
    if len(want) < 6:
        return None                      # 題名が短すぎると誤爆しうるので触らない

    for it in cinii(entry["title"]):
        got = norm(it.get("title"))
        # 完全一致、または片方がもう片方を含む（CiNii は副題の付け方が違うことがある）
        if not (got == want or (len(got) >= 8 and (got in want or want in got))):
            continue
        if str(it.get("prism:volume") or "") != vol:
            continue
        if str(it.get("prism:number") or "") != no:
            continue
        # 誌名も確かめる。巻号が偶然そろった別誌の記事を拾わないため。
        # CiNii の誌名は「Intensive care next : new evidence…」のように長いので、
        # こちらの誌名が含まれていればよしとする。
        if jr and jr not in norm(it.get("prism:publicationName")):
            continue
        sp, ep = it.get("prism:startingPage"), it.get("prism:endingPage")
        if sp and ep:
            return str(sp), str(ep)
    return None


def main():
    dry = "--dry" in sys.argv
    with open(WRITINGS, encoding="utf-8") as f:
        raw = f.read()
    data = json.loads(raw)

    targets = [e for e in data["items"] if VOL_NO.match(e.get("citation") or "")]
    if not targets:
        print("  ページ番号が足りない原稿はありません")
        return

    filled = 0
    for e in targets:
        try:
            hit = find_pages(e)
        except Exception as ex:                                     # noqa: BLE001
            print(f"  CiNii を引けませんでした（{ex}）", file=sys.stderr)
            raise
        label = f"{e.get('journal')} {e.get('citation')} {e.get('title','')[:28]}"
        if not hit:
            print(f"  まだ CiNii に出ていません: {label}")
            continue
        new = f"{e['citation']}:{hit[0]}-{hit[1]}"
        print(f"  ページ番号が分かりました: {label} → {new}")
        if not dry:
            # 既存の書式を壊さないよう、その1行だけを置き換える
            old_line = f'"citation": "{e["citation"]}"'
            if raw.count(old_line) != 1:
                print(f"    ※ {e['citation']} が複数あるため自動では直しません", file=sys.stderr)
                continue
            raw = raw.replace(old_line, f'"citation": "{new}"')
            filled += 1
        time.sleep(1)                    # CiNii に連続で負荷をかけない

    if filled and not dry:
        json.loads(raw)                  # 壊していないことを確かめてから書く
        with open(WRITINGS, "w", encoding="utf-8") as f:
            f.write(raw)
        print(f"  → data/writings.json を更新しました（{filled}件）")


if __name__ == "__main__":
    main()
