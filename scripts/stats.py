#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
アクセス解析（GoatCounter）を読んで、要約を表示します。

  python3 scripts/stats.py            直近30日
  python3 scripts/stats.py 7          直近7日
  python3 scripts/stats.py 2026-08-24 指定日から今日まで

同じ長さの「直前の期間」と比べた増減も一緒に出します。

APIトークンはリポジトリに置きません。次のファイルから読みます。
  ~/.config/kotani-portfolio/goatcounter.env
      GOATCOUNTER_SITE=yukikotani5
      GOATCOUNTER_TOKEN=（Settings → API tokens で発行したもの）

  ※ トークンには「統計の読み取り」権限が要ります。
    サイト設定ページにある Secret token とは別物で、そちらでは 401 になります。

環境変数 GOATCOUNTER_TOKEN が設定されていれば、そちらが優先されます。
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

CONF = os.path.expanduser("~/.config/kotani-portfolio/goatcounter.env")

# 数字がこれ未満のときは「傾向」として読まない。
# 5件や10件の増減は、たまたま誰かが2回開いただけで簡単にひっくり返る。
NOISE_FLOOR = 20


def load_conf():
    conf = {}
    if os.path.exists(CONF):
        for line in open(CONF, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                conf[k.strip()] = v.strip()
    site = os.environ.get("GOATCOUNTER_SITE") or conf.get("GOATCOUNTER_SITE")
    token = os.environ.get("GOATCOUNTER_TOKEN") or conf.get("GOATCOUNTER_TOKEN")
    if not site or not token:
        sys.exit(f"サイトコードかトークンが見つかりません。{CONF} を確認してください。")
    return site, token


def api(site, token, path, params=None):
    url = f"https://{site}.goatcounter.com/api/v0/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            sys.exit(
                "認証に失敗しました（401）。\n"
                "  GoatCounter の Settings → API tokens でトークンを作り直し、\n"
                f"  {CONF} の GOATCOUNTER_TOKEN を差し替えてください。\n"
                "  ※「統計の読み取り」にチェックが要ります。サイト設定ページの\n"
                "    Secret token は別物で、これでは通りません。")
        if e.code == 403:
            sys.exit("権限がありません（403）。トークンに統計の読み取り権限を付けてください。")
        sys.exit(f"APIエラー {e.code}: {e.read()[:200].decode('utf-8', 'replace')}")


def fetch(site, token, path, start, end):
    """start〜end（両端とも含む）を取る。

    GoatCounter の end は「その日を含まない」扱いなので +1日して渡す。
    ここを間違えると当日ぶんが丸ごと落ちて、total だけ 0 になる。
    （実際にそれで「0回」と誤って報告したことがある）
    """
    return api(site, token, path, {
        "start": start.isoformat(),
        "end": (end + timedelta(days=1)).isoformat(),
    })


def views(total_json):
    return total_json.get("total", 0) or total_json.get("total_utc", 0)


def bar(n, mx, width=26):
    return "█" * max(1, round(n / mx * width)) if mx and n else ""


def diff(cur, prev):
    d = cur - prev
    if d > 0:
        return f"+{d}"
    if d < 0:
        return str(d)
    return "±0"


def section(title, rows, total=None, prev=None):
    """prev を渡すと、前の期間からの増減と『新規』を添える。"""
    print(f"\n── {title} ──")
    if not rows:
        print("  （データなし）")
        return
    mx = max(r[1] for r in rows)
    for name, cnt in rows:
        pct = f" {cnt / total * 100:4.1f}%" if total else ""
        note = ""
        if prev is not None:
            if name not in prev:
                note = "  ← 新規"
            elif prev[name] != cnt:
                note = f"  ({diff(cnt, prev[name])})"
        print(f"  {str(name)[:30]:30} {cnt:>5}{pct}  {bar(cnt, mx):26}{note}")


def main():
    site, token = load_conf()
    arg = sys.argv[1] if len(sys.argv) > 1 else "30"
    today = date.today()
    if arg.count("-") == 2:
        start = date.fromisoformat(arg)
    else:
        start = today - timedelta(days=int(arg))
    span = (today - start).days or 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span - 1)

    print(f"═══ アクセス解析  {start} 〜 {today}（{span}日間） ═══")

    cur_total = fetch(site, token, "stats/total", start, today)
    pv = views(cur_total)
    pv_prev = views(fetch(site, token, "stats/total", prev_start, prev_end))
    print(f"\n  閲覧 {pv:,} 回   （1日あたり {pv / span:.1f} 回）")
    print(f"  直前の{span}日間（{prev_start}〜{prev_end}）は {pv_prev:,} 回   → {diff(pv, pv_prev)}")

    # 日別の推移。投稿直後に跳ねて、その後どう落ち着くかを見る
    daily = [(d["day"], d.get("daily", 0)) for d in cur_total.get("stats", [])]
    shown = [(d, c) for d, c in daily if d <= today.isoformat()]
    if any(c for _, c in shown):
        first = next(i for i, (_, c) in enumerate(shown) if c)
        section("日別", shown[first:][-14:])

    # 流入元 ── このサイトでは、どこから来たかが一番知りたい
    def refs(a, b):
        st = fetch(site, token, "stats/toprefs", a, b).get("stats", [])
        return [(r.get("name") or "直接アクセス・不明", r["count"]) for r in st]

    section("流入元", refs(start, today)[:12], pv, dict(refs(prev_start, prev_end)))

    for path, label in [("stats/browsers", "ブラウザ"),
                        ("stats/systems", "OS"),
                        ("stats/locations", "地域")]:
        try:
            st = fetch(site, token, path, start, today).get("stats", [])
            section(label, [(r.get("name") or "不明", r["count"]) for r in st[:6]], pv)
        except SystemExit:
            raise
        except Exception:
            pass

    print()
    if pv < NOISE_FLOOR:
        print(f"  ⚠ 母数が{pv}回では、増減は傾向として読めません。")
        print("    1回2回の違いは、同じ人がもう一度開いただけで動きます。")
        print(f"    {NOISE_FLOOR}回を超えるまでは「出ているかどうか」だけ見てください。")
    print("  ※ Cookieを使わない計測のため、同一人物の再訪は完全には追えません。")
    print("    数字は「おおよその傾向」として読んでください。")


if __name__ == "__main__":
    main()
