#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
アクセス解析（GoatCounter）を読んで、要約を表示します。

  python3 scripts/stats.py            直近30日
  python3 scripts/stats.py 7          直近7日
  python3 scripts/stats.py 2026-08-24 指定日から今日まで
  python3 scripts/stats.py 2026-09-14 2026-09-21
                                      指定日から指定日まで（過去の週の取り直し用）

  --record を付けると、表示した内容をそのまま記録ファイル
  ~/.config/kotani-portfolio/weekly-reports.md に追記します（失敗したときはエラーを追記）。

同じ長さの「直前の期間」と比べた増減も一緒に出します。

APIトークンはリポジトリに置きません。次のファイルから読みます。
  ~/.config/kotani-portfolio/goatcounter.env
      GOATCOUNTER_SITE=yukikotani5
      GOATCOUNTER_TOKEN=（Settings → API tokens で発行したもの）

  ※ トークンには「統計の読み取り」権限が要ります。
    サイト設定ページにある Secret token とは別物で、そちらでは 401 になります。

環境変数 GOATCOUNTER_TOKEN が設定されていれば、そちらが優先されます。
"""

import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

CONF = os.path.expanduser("~/.config/kotani-portfolio/goatcounter.env")
LOG = os.path.expanduser("~/.config/kotani-portfolio/weekly-reports.md")

# 週1回の記録なので、前回の見出しからこれより空いていたら抜けがある。
RECORD_GAP = 8

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


def api(site, token, path, params=None, tries=4):
    """GoatCounter の API を叩く。一時的な失敗は数回まで待って試し直す。

    週1回しか走らない集計なので、たまたま通信が落ちた1回で
    その週のレポートが丸ごと消えるのが一番困る。
    実際 2026-09-07 の自動実行は、一過性の 404 で何も出せずに終わった。
    （同じURLを直後に叩くと 200 が返った）

    認証エラー（401/403）だけは待っても直らないので、すぐ諦める。
    """
    url = f"https://{site}.goatcounter.com/api/v0/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })

    for attempt in range(1, tries + 1):
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
            body = e.read()[:200].decode("utf-8", "replace")
            last = f"APIエラー {e.code}: {body}"
        except urllib.error.URLError as e:
            last = f"通信に失敗しました: {e.reason}"

        if attempt < tries:
            wait = 2 ** attempt          # 2秒, 4秒, 8秒
            print(f"  …取得に失敗しました（{attempt}/{tries}）。{wait}秒待って試し直します。",
                  file=sys.stderr)
            time.sleep(wait)

    sys.exit(f"{last}\n  {tries}回試しましたが取得できませんでした。\n  呼び出し先: {url}")


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
    """total が 0 のときに total_utc へ落ちないようにする。

    `total or total_utc` と書くと、閲覧が本当に 0 回だった期間で total が
    偽と見なされ、無関係な total_utc の値が代わりに返る。
    実際それで「前の7日間は31回」と出たことがある（正しくは0回）。
    total が無いときだけ total_utc を使う。
    """
    total = total_json.get("total")
    return total if total is not None else total_json.get("total_utc", 0)


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


def parse_range(args):
    """引数から (start, end) を決める。end を省けば今日。"""
    today = date.today()
    arg = args[0] if args else "30"
    end = date.fromisoformat(args[1]) if len(args) > 1 else today
    if arg.count("-") == 2:
        start = date.fromisoformat(arg)
    else:
        start = end - timedelta(days=int(arg))
    return start, end


def last_record_date():
    """記録ファイルの最後の見出しの日付。無ければ None。"""
    if not os.path.exists(LOG):
        return None
    found = re.findall(r"^## (\d{4}-\d{2}-\d{2})", open(LOG, encoding="utf-8").read(), re.M)
    return date.fromisoformat(max(found)) if found else None


def main(args):
    site, token = load_conf()
    start, today = parse_range(args)
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
        """同じ名前が複数行で返ることがあるので合算する。

        実際 www.facebook.com が count=1 の行として2つ返ってきた。
        そのまま出すと同じ行が2回並び、割合も合わなくなる。
        """
        st = fetch(site, token, "stats/toprefs", a, b).get("stats", [])
        merged = {}
        for r in st:
            name = r.get("name") or "直接アクセス・不明"
            merged[name] = merged.get(name, 0) + r["count"]
        return sorted(merged.items(), key=lambda kv: -kv[1])

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


class Tee(io.StringIO):
    """画面に出しつつ、同じ内容を手元にも残す。"""

    def __init__(self, out):
        super().__init__()
        self.out = out

    def write(self, s):
        self.out.write(s)
        return super().write(s)


def run_and_record(args):
    """集計して、結果を必ず記録ファイルに追記する。

    2026-09-28 と 10-05 の自動実行は、数字を取ったあと記録を書く前に止まり、
    しかも実行履歴上は「成功」になっていた。9-21 は実行自体が起動していない。
    記録を書く役目をあとの手順に任せると、途中で止まった週は何も残らない。
    そこで、数字を取ったその場で（失敗ならエラーを）書いてしまう。
    """
    start, end = parse_range(args)
    head = f"## {end}（{start.month}/{start.day}〜{end.month}/{end.day}）"
    stamp = date.today().isoformat()

    gap_note = ""
    last = last_record_date()
    if last and (end - last).days > RECORD_GAP:
        gap_note = (f"⚠ 前回の記録（{last}）から{(end - last).days}日空いています。"
                    "あいだの週の記録が抜けています。")
        print(gap_note)

    buf = Tee(sys.stdout)
    sys.stdout = buf
    try:
        main(args)
    except SystemExit as e:
        sys.stdout = buf.out
        if e.code not in (None, 0):
            body = f"集計できませんでした。エラー: {e.code}"
            entry = f"{head.split('（')[0]}（取得失敗）\n\n{body}\n"
            if gap_note:
                entry += f"\n{gap_note}\n"
            append_log(entry + "\n---\n")
            print(f"\n（記録ファイルに取得失敗として追記しました: {LOG}）", file=sys.stderr)
        raise
    finally:
        sys.stdout = buf.out

    entry = f"{head} 集計値（{stamp} に自動記録）\n\n"
    if gap_note:
        entry += f"{gap_note}\n\n"
    entry += "```\n" + buf.getvalue().strip("\n") + "\n```\n\n---\n"
    append_log(entry)
    print(f"\n（集計値を記録ファイルに追記しました: {LOG}）")


def append_log(entry):
    """追記のみ。上書きはしない。"""
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(entry)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--record"]
    if "--record" in sys.argv[1:]:
        run_and_record(args)
    else:
        main(args)
