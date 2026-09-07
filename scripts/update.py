#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小谷祐樹ポートフォリオ 自動更新スクリプト

外部依存なし（Python 3.9+ 標準ライブラリのみ）。

取得元:
  1. PubMed E-utilities … 論文（著者名 + 所属で同姓同名の別人を除外）
  2. ORCID Public API   … 論文（PubMed 未収載分を補完）
  3. OpenAlex API       … 被引用数（PubMed にはこの数字がない）
  4. YouTube            … 「ICUトーク」全エピソードと再生回数
  5. note API           … 全記事とスキ数
  6. Voicy 内部API      … 「小谷祐樹とICU」全話と再生回数
  7. 各取材記事の OGP   … media.json に画像が未設定なら補う

出力:
  data/publications.json  被引用トップ5 + 全体の統計
  data/feeds.json         ICUトーク / note / Voicy の「最新」と「人気」
  data/media.json         画像URLを補完（他の項目は手で書いたまま）

使い方:
  python3 scripts/update.py
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# ---------------------------------------------------------------- 設定
ORCID_ID = "0000-0002-9532-2859"
# OpenAlex は連絡先を送ると優先的に処理される。公開リポジトリに個人アドレスを
# 残さないよう、researchmap 等で公開済みの所属アドレスを使う。
CONTACT = "kotani.yuki@kameda.jp"

# 同姓同名対策: "Kotani Y" は大阪の整形外科医・東大の化学者などにも該当する。
# 所属で必ず絞り込むこと。ここを緩めると別人の論文が載ります。
PUBMED_QUERY = 'Kotani Y[Author] AND (Kameda[Affiliation] OR "San Raffaele"[Affiliation])'

YOUTUBE_CHANNEL_ID = "UCmP6AkeW0xv4ol8EPOu5gfg"          # ICUトーク
# チャンネルの「アップロード」再生リスト。UC… の UC を UU に変えると得られる。
# チャンネルページは30本しか返さないが、再生リストは100本まで一度に返す。
YOUTUBE_UPLOADS = "UU" + YOUTUBE_CHANNEL_ID[2:]
NOTE_USER = "yukikotani5"

# Voicy は公式APIを公開していないため、Web版が使っている内部APIを利用する。
# 認証は Firebase の匿名サインイン（このAPIキーは公開クライアント用でブラウザ内にも露出している）。
# 【注意】非公開APIなので予告なく変わり得る。失敗しても前回値を残す設計にしてある。
VOICY_CHANNEL_ID = "848405"
VOICY_API = "https://vmedia-player-api.voicy.jp/v1"
VOICY_FIREBASE_KEY = "AIzaSyC5Rg-sxiYu6ySD8V-f6Eljwll8gHvgUK4"

TOP_PUBLICATIONS = 5

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
TIMEOUT = 45


def fetch(url, data=None, retries=4, headers=None):
    last = None
    for i in range(retries):
        try:
            h = {"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"}
            h.update(headers or {})
            req = urllib.request.Request(
                url, data=data.encode() if isinstance(data, str) else data, headers=h)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except Exception as e:                                    # noqa: BLE001
            last = e
            wait = 2 ** i
            print(f"    retry {i + 1}/{retries} in {wait}s ({e})", file=sys.stderr)
            time.sleep(wait)
    raise last


def norm_doi(d):
    if not d:
        return None
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", str(d).strip().lower())
    return d or None


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", "", (t or "").lower())[:90]


# ═══════════════════════════════════════════════════ 論文
def pubmed():
    print("  PubMed …")
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    q = urllib.parse.quote(PUBMED_QUERY)
    ids = json.loads(fetch(f"{base}esearch.fcgi?db=pubmed&term={q}"
                           "&retmax=500&retmode=json"))["esearchresult"]["idlist"]
    print(f"    {len(ids)} PMIDs")
    out = []
    for i in range(0, len(ids), 200):
        body = urllib.parse.urlencode(
            {"db": "pubmed", "id": ",".join(ids[i:i + 200]), "retmode": "xml"})
        root = ET.fromstring(fetch(f"{base}efetch.fcgi", data=body))
        out += [p for p in (parse_pubmed(a) for a in root.findall(".//PubmedArticle")) if p]
        time.sleep(0.4)                       # NCBI のレート制限（3 req/s）を尊重
    return out


def parse_pubmed(art):
    tnode = art.find(".//ArticleTitle")
    title = re.sub(r"\.$", "", "".join(tnode.itertext()).strip()) if tnode is not None else ""
    if not title:
        return None
    year = art.findtext(".//JournalIssue/PubDate/Year")
    if not year:
        m = re.search(r"(\d{4})", art.findtext(".//JournalIssue/PubDate/MedlineDate") or "")
        year = m.group(1) if m else None
    doi = next((a.text for a in art.findall(".//ArticleId")
                if a.get("IdType") == "doi"), None)

    authors, position = [], None
    alist = art.findall(".//AuthorList/Author")
    for i, a in enumerate(alist):
        ln = a.findtext("LastName") or ""
        if not ln:
            continue
        authors.append(f"{ln} {a.findtext('Initials') or ''}".strip())
        if ln == "Kotani" and (a.findtext("ForeName") or "").startswith("Yuki"):
            position = "first" if i == 0 else ("last" if i == len(alist) - 1 else "middle")

    return {
        "title": title,
        "journal": (art.findtext(".//Journal/ISOAbbreviation")
                    or art.findtext(".//Journal/Title") or ""),
        "year": int(year) if year and year.isdigit() else None,
        "doi": norm_doi(doi),
        "pmid": art.findtext(".//PMID"),
        "authors": authors,
        "authorCount": len(alist),
        "position": position,
        "types": [p.text for p in art.findall(".//PublicationType") if p.text],
    }


def orcid():
    print("  ORCID …")
    groups = json.loads(fetch(f"https://pub.orcid.org/v3.0/{ORCID_ID}/works",
                              headers={"Accept": "application/json"})).get("group", [])
    print(f"    {len(groups)} works")
    out = []
    for g in groups:
        s = g["work-summary"][0]
        ids = {e["external-id-type"]: e["external-id-value"]
               for e in g.get("external-ids", {}).get("external-id", [])}
        pd = s.get("publication-date") or {}
        yr = (pd.get("year") or {}).get("value") if isinstance(pd.get("year"), dict) else None
        jt = s.get("journal-title")
        out.append({
            "title": (s.get("title", {}).get("title", {}) or {}).get("value", "").strip(),
            "journal": jt.get("value") if isinstance(jt, dict) else "",
            "year": int(yr) if yr and str(yr).isdigit() else None,
            "doi": norm_doi(ids.get("doi")), "pmid": ids.get("pmid"),
            "authors": [], "authorCount": 0, "position": None, "types": [],
        })
    return [x for x in out if x["title"]]


def openalex():
    """被引用数を取得する。PubMed にはこの数字が無いので OpenAlex を使う。"""
    print("  OpenAlex（被引用数）…")
    url = ("https://api.openalex.org/works"
           f"?filter=author.orcid:{ORCID_ID}&per-page=200"
           "&select=doi,title,publication_year,cited_by_count,primary_location,authorships"
           f"&mailto={urllib.parse.quote(CONTACT)}")
    d = json.loads(fetch(url))
    print(f"    {d['meta']['count']} works")
    out = {}
    for w in d["results"]:
        rec = {
            "citations": w.get("cited_by_count") or 0,
            "title": w.get("title") or "",
            "year": w.get("publication_year"),
            "journal": ((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
        }
        doi = norm_doi(w.get("doi"))
        if doi:
            out[doi] = rec
        out.setdefault("t:" + norm_title(rec["title"]), rec)
    return out


# 原著以外（返信・訂正・論説）は「原著論文」の数から外す
NON_ARTICLE_TITLE = re.compile(
    r"^(the )?authors?[' ]*(reply|response)|^reply\b|^response to\b|"
    r"^correction\b|^erratum\b|^comment on\b|^letter\b|^in reply\b", re.I)
NON_ARTICLE_TYPES = {"Comment", "Published Erratum", "Editorial", "Letter"}


def build_publications():
    pm, oc = pubmed(), orcid()
    merged, by_doi, by_pmid, by_title = [], {}, {}, {}

    def add(rec):
        merged.append(rec)
        if rec["doi"]:
            by_doi[rec["doi"]] = rec
        if rec["pmid"]:
            by_pmid[rec["pmid"]] = rec
        by_title[norm_title(rec["title"])] = rec

    for r in pm:
        add(r)
    added = 0
    for r in oc:
        hit = (by_doi.get(r["doi"]) if r["doi"] else None) \
            or (by_pmid.get(r["pmid"]) if r["pmid"] else None) \
            or by_title.get(norm_title(r["title"]))
        if hit:
            if not hit["doi"] and r["doi"]:
                hit["doi"] = r["doi"]
            continue
        add(r)
        added += 1
    print(f"    ORCID から新規追加: {added} 件")

    cites = openalex()
    matched = 0
    for r in merged:
        c = (cites.get(r["doi"]) if r["doi"] else None) or cites.get("t:" + norm_title(r["title"]))
        r["citations"] = (c or {}).get("citations", 0)
        if c:
            matched += 1
        is_reply = bool(NON_ARTICLE_TITLE.match(r["title"])) or \
            bool(set(r["types"]) & NON_ARTICLE_TYPES)
        r["article"] = not is_reply
        r["url"] = (f"https://doi.org/{r['doi']}" if r["doi"]
                    else f"https://pubmed.ncbi.nlm.nih.gov/{r['pmid']}/" if r["pmid"] else None)
    print(f"    被引用数を紐づけ: {matched}/{len(merged)} 件")

    arts = [r for r in merged if r["article"]]
    top = sorted(arts, key=lambda r: (-(r["citations"] or 0), -(r["year"] or 0)))[:TOP_PUBLICATIONS]

    def slim(r):
        au = r["authors"]
        return {
            "title": r["title"], "journal": r["journal"], "year": r["year"],
            "citations": r["citations"], "doi": r["doi"], "url": r["url"],
            "position": r["position"], "authorCount": r["authorCount"],
            "authors": (au[:3] + ["…", au[-1]]) if len(au) > 5 else au,
        }

    return {
        "stats": {
            "total": len(merged),
            "articles": len(arts),
            "firstAuthor": sum(1 for r in arts if r["position"] == "first"),
            "citations": sum(r["citations"] or 0 for r in merged),
            "since": min((r["year"] for r in merged if r["year"]), default=None),
        },
        "top": [slim(r) for r in top],
    }


# ═══════════════════════════════════════════════════ YouTube
def yt_number(text):
    """'2,319回視聴' / '1.2万回視聴' → int"""
    if not text:
        return 0
    t = text.replace(",", "")
    m = re.search(r"([\d.]+)\s*万", t)
    if m:
        return int(float(m.group(1)) * 10000)
    m = re.search(r"(\d+)", t)
    return int(m.group(1)) if m else 0


def youtube():
    """
    アップロード再生リストのページから全エピソードと再生回数を取る。
    チャンネルページは30本しか返さないため、全期間の最多再生を出すには
    再生リスト（100本まで一度に返る）を使う必要がある。
    """
    print("  YouTube（ICUトーク）…")
    html = fetch(f"https://www.youtube.com/playlist?list={YOUTUBE_UPLOADS}"
                 ).decode("utf-8", "replace")
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if not m:
        raise RuntimeError("ytInitialData が見つかりません（YouTube の仕様変更の可能性）")
    data = json.loads(m.group(1))

    items, seen = [], set()

    def walk(o):
        if isinstance(o, dict):
            # YouTube は 2025 年に videoRenderer から lockupViewModel へ移行した
            lv = o.get("lockupViewModel")
            if lv and lv.get("contentId") not in seen:
                meta = (lv.get("metadata") or {}).get("lockupMetadataViewModel") or {}
                title = (meta.get("title") or {}).get("content")
                views = None
                rows = (((meta.get("metadata") or {}).get("contentMetadataViewModel") or {})
                        .get("metadataRows") or [])
                for row in rows:
                    for part in row.get("metadataParts", []):
                        t = (part.get("text") or {}).get("content", "")
                        if "視聴" in t:
                            views = t
                if title:
                    seen.add(lv["contentId"])
                    items.append({
                        "id": lv["contentId"], "title": title,
                        "views": yt_number(views), "viewsText": views,
                    })
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    if not items:
        raise RuntimeError("エピソードを1本も取得できませんでした")
    print(f"    {len(items)} 本")

    def card(it, label):
        return {
            "label": label, "title": it["title"],
            "url": f"https://www.youtube.com/watch?v={it['id']}",
            "thumbnail": f"https://i.ytimg.com/vi/{it['id']}/mqdefault.jpg",
            "metric": f"{it['views']:,} 回再生" if it["views"] else None,
        }

    # 最多再生は再生リスト（全92本）から求める
    popular = max(items, key=lambda x: x["views"])

    # 最新回は RSS の公開日時で決める。
    # 再生リストの並び順は公開日と一致しないことがあり（#86 が #85 より先に公開されている等）、
    # 先頭を最新とみなすと取り違える。
    latest = items[0]
    try:
        feed = ET.fromstring(fetch("https://www.youtube.com/feeds/videos.xml"
                                   f"?channel_id={YOUTUBE_CHANNEL_ID}"))
        ns = {"a": "http://www.w3.org/2005/Atom",
              "yt": "http://www.youtube.com/xml/schemas/2015"}
        entries = [(e.findtext("a:published", namespaces=ns) or "",
                    e.findtext("yt:videoId", namespaces=ns))
                   for e in feed.findall("a:entry", ns)]
        entries = [e for e in entries if e[1]]
        if entries:
            newest_id = max(entries)[1]
            by_id = {i["id"]: i for i in items}
            latest = by_id.get(newest_id, latest)
    except Exception as e:                                        # noqa: BLE001
        print(f"    RSS で公開日を確認できず、再生リストの先頭を最新とします（{e}）",
              file=sys.stderr)
    print(f"    最新: {latest['title'][:32]}")
    print(f"    最多: {popular['title'][:32]}（{popular['views']:,}回）")
    return {"latest": card(latest, "最新回"), "popular": card(popular, "よく聴かれている回")}


# ═══════════════════════════════════════════════════ note
def note():
    print("  note …")
    items, page = [], 1
    while page <= 12:
        d = json.loads(fetch(f"https://note.com/api/v2/creators/{NOTE_USER}"
                             f"/contents?kind=note&page={page}"))["data"]
        items += d.get("contents", [])
        if d.get("isLastPage"):
            break
        page += 1
        time.sleep(0.3)
    items = [n for n in items if n.get("noteUrl")]
    if not items:
        raise RuntimeError("記事を取得できませんでした")
    print(f"    {len(items)} 本")

    def card(n, label, metric):
        return {
            "label": label, "title": n.get("name") or "",
            "url": n.get("noteUrl"), "thumbnail": n.get("eyecatch"),
            "date": (n.get("publishAt") or "")[:10], "metric": metric,
        }

    latest = max(items, key=lambda n: n.get("publishAt") or "")
    popular = max(items, key=lambda n: n.get("likeCount") or 0)
    print(f"    最新: {latest.get('name','')[:32]}")
    print(f"    最多スキ: {popular.get('name','')[:32]}（{popular.get('likeCount')}）")
    return {
        "latest": card(latest, "最新記事", None),
        "popular": card(popular, "よく読まれている記事", f"スキ {popular.get('likeCount', 0)}"),
    }


# ═══════════════════════════════════════════════════ Voicy
def voicy():
    """
    Voicy「小谷祐樹とICU」の最新話と最多再生話。

    Voicy は RSS を出しておらず、チャンネルページも JavaScript 描画のため
    HTML からは何も取れない。Web版が内部で叩いている API を同じ手順で使う。

      1. Firebase の匿名サインインで idToken を取る
      2. その Bearer トークンで stories API をページングする

    ページの「再生順」表示は読み込み済みの分しか並べ替えないため、
    全話を取得してから最大値を求めること（UI 上の1位と実際の1位は違う）。
    """
    print("  Voicy（小谷祐樹とICU）…")
    tok = json.loads(fetch(
        "https://identitytoolkit.googleapis.com/v1/accounts:signUp"
        f"?key={VOICY_FIREBASE_KEY}",
        data=json.dumps({"returnSecureToken": True}),
        headers={"Content-Type": "application/json"},
    ))["idToken"]
    auth = {"Authorization": f"Bearer {tok}", "Accept": "application/json"}

    items, page_token, page = [], None, 0
    while page < 20:
        url = (f"{VOICY_API}/channels/{VOICY_CHANNEL_ID}/stories/latests"
               f"?channel_view_id={VOICY_CHANNEL_ID}&page_size=200")
        if page_token:
            url += "&page_token=" + urllib.parse.quote(page_token)
        d = json.loads(fetch(url, headers=auth))
        got = d.get("stories") or []
        items += got
        page_token = (d.get("pagination") or {}).get("next_page_token")
        page += 1
        if not got or not page_token:
            break
        time.sleep(0.3)

    seen, uniq = set(), []
    for x in items:
        if x.get("id") not in seen:
            seen.add(x["id"])
            uniq.append(x)
    if not uniq:
        raise RuntimeError("エピソードを1話も取得できませんでした")
    print(f"    {len(uniq)} 話")

    def card(st, label, metric):
        return {
            "label": label,
            "title": st.get("name") or "",
            "url": st.get("share_url")
                   or f"https://voicy.jp/channel/{VOICY_CHANNEL_ID}/{st.get('id')}",
            "date": (st.get("published") or "")[:10],
            "metric": metric,
            "thumbnail": None,
        }

    latest = max(uniq, key=lambda x: x.get("published") or "")
    popular = max(uniq, key=lambda x: x.get("play_count") or 0)
    print(f"    最新: {latest.get('name','')[:32]}")
    print(f"    最多: {popular.get('name','')[:32]}（{popular.get('play_count'):,}回）")
    return {
        "latest": card(latest, "最新話", None),
        "popular": card(popular, "よく聴かれている話",
                        f"{popular.get('play_count', 0):,} 回再生"),
    }


# ═══════════════════════════════════════════════════ 取材記事の画像
def resolve_media_images():
    """media.json の各項目に画像が無ければ、記事ページの OGP 画像を補う。"""
    print("  取材記事の画像 …")
    path = os.path.join(DATA, "media.json")
    with open(path, encoding="utf-8") as f:
        media = json.load(f)

    changed = 0
    for it in media.get("items", []):
        if it.get("image") or not it.get("url"):
            continue
        try:
            html = fetch(it["url"]).decode("utf-8", "replace")
            m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                          html) or \
                re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
                          html)
            if m:
                it["image"] = urllib.parse.urljoin(it["url"], m.group(1))
                changed += 1
                print(f"    + {it['outlet'][:28]}")
        except Exception as e:                                    # noqa: BLE001
            print(f"    - 取得失敗（スキップ）: {it.get('outlet')} … {e}", file=sys.stderr)
        time.sleep(0.3)

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(media, f, ensure_ascii=False, indent=1)
            f.write("\n")
    print(f"    {changed} 件に画像を追加")


# ═══════════════════════════════════════════════════ 書き出し
SITE_URL = "https://yukikotani5.github.io/"

# 「2026-09-07」または「2026-09」の形だけを日付とみなす
DATE_RE = re.compile(r"^(\d{4})-(\d{2})(?:-(\d{2}))?$")

# updatedAt は取得を走らせた時刻なので、中身が変わっていなくても毎日動く。
# これを lastmod に使うと毎日コミットが生まれるため、日付として数えない。
NOT_A_CONTENT_DATE = {"updatedAt"}


def latest_content_date():
    """data/ にある一番新しい日付を返す（未来の予定は除く）。

    sitemap の lastmod に「今日」を入れるのは避けたい。
    中身が変わっていない日まで更新扱いになり、毎日 diff が出てコミットが増えるし、
    毎日更新されている sitemap は検索エンジンからも信用されなくなる。
    実際に載っている一番新しいものの日付を使う。

    講演やイベントの予定は未来の日付で入るので、そこは数えない
    （まだ起きていないものを「最終更新日」にはできない）。
    """
    today = datetime.now(timezone.utc).date().isoformat()
    best = None

    def walk(node, key=None):
        nonlocal best
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, key)
        elif isinstance(node, str) and key not in NOT_A_CONTENT_DATE:
            m = DATE_RE.match(node)
            if m:
                d = "%s-%s-%s" % (m.group(1), m.group(2), m.group(3) or "01")
                if d <= today and (best is None or d > best):
                    best = d

    for name in sorted(os.listdir(DATA)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(DATA, name), encoding="utf-8") as f:
                walk(json.load(f))
        except Exception:                                           # noqa: BLE001
            continue                    # 壊れたJSONで sitemap 生成を巻き込まない

    return best or today


def build_sitemap():
    """1ページなので URL は1本。Search Console に出す用。"""
    lastmod = latest_content_date()
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url>\n"
        f"    <loc>{SITE_URL}</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        "  </url>\n"
        "</urlset>\n"
    )
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"  sitemap.xml を書きました（最終更新 {lastmod}）")


def write(name, payload):
    path = os.path.join(DATA, name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)
    print(f"  → {os.path.relpath(path, ROOT)}")


def main():
    os.makedirs(DATA, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    failures = []

    try:
        pubs = build_publications()
        write("publications.json", {"updatedAt": now, **pubs})
        s = pubs["stats"]
        print(f"  論文 {s['total']} 件 / 被引用 {s['citations']:,} 回 → 上位{TOP_PUBLICATIONS}件を掲載")
    except Exception as e:                                        # noqa: BLE001
        failures.append(f"publications: {e}")

    feeds = {"updatedAt": now}
    for key, fn in (("youtube", youtube), ("note", note), ("voicy", voicy)):
        try:
            feeds[key] = fn()
        except Exception as e:                                    # noqa: BLE001
            failures.append(f"{key}: {e}")
    if len(feeds) > 1:
        # 取れた分だけ更新し、落ちた系統は前回値を残す
        old = {}
        p = os.path.join(DATA, "feeds.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                old = json.load(f)
        old.update(feeds)
        write("feeds.json", old)

    try:
        resolve_media_images()
    except Exception as e:                                        # noqa: BLE001
        failures.append(f"media images: {e}")

    try:
        build_sitemap()
    except Exception as e:                                          # noqa: BLE001
        failures.append(f"sitemap: {e}")

    if failures:
        print("\n⚠ 一部の取得に失敗しました（既存データは保持）:", file=sys.stderr)
        for f in failures:
            print("   -", f, file=sys.stderr)
        sys.exit(1)
    print("\n✅ 更新完了")


if __name__ == "__main__":
    main()
