#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
index.html の構造化データ（JSON-LD）を data/profile.json から作り直します。

  python3 scripts/build_jsonld.py

なぜ手書きにしないか:
  検索エンジンに「小谷祐樹はこの人物です」と機械可読な形で伝えるものなので、
  ページの表示内容と食い違うと逆効果になります。profile.json を唯一の出典にして、
  そこから生成することで、直し忘れによるズレを防ぎます。

なぜ必要か:
  「Kotani Y」は同姓同名が多く、PubMed では別人の論文が21件混ざります
  （大阪の整形外科医、東京大学の化学者など）。検索エンジンでも同じ混同が起きます。
  ORCID・所属・各SNSアカウントを明示して、別人と区別されやすくします。

安全のため、次のときは index.html を書き換えずに終了します。
  - 目印のコメントが1組見つからない
  - 生成したJSONが壊れている
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://yukikotani5.github.io/"

BEGIN = "<!-- 構造化データ: scripts/build_jsonld.py が生成します。手で編集しないでください -->"
END = "<!-- 構造化データ ここまで -->"


# 本人のプロフィール（＝「この人物の別の居場所」）
PERSONAL_LINKS = ["x", "note", "researchmap", "orcid", "facebook", "instagram"]

# ポッドキャスト番組。これらは「番組」であって「本人」ではないので、
# Person の sameAs に混ぜてはいけない。
# 混ぜると検索エンジンに「小谷祐樹という人物 ＝ このSpotifyの番組」と
# 伝えることになり、人物を区別させたいという目的と逆に働く。
PODCASTS = [
    {"name": "ICUトーク", "main": "youtube", "also": ["spotify", "amazonmusic", "pody"],
     "description": "集中治療について話すポッドキャスト。毎週配信しています。"},
    {"name": "小谷祐樹とICU", "main": "voicy", "also": [],
     "description": "Voicyでのひとりポッドキャスト。毎日配信しています。"},
]

PERSON_ID = SITE + "#person"


def build(p):
    """profile.json から構造化データを組み立てる。

    書いてよいのは profile.json に実際にある事実だけ。
    肩書きや専門領域を「それらしく」盛らないこと。
    """
    by_id = {l["id"]: l for l in p.get("links", []) if l.get("url")}

    # profile.json にリンクを足したとき、黙って抜け落ちないようにする
    known = set(PERSONAL_LINKS) | {x["main"] for x in PODCASTS} \
        | {a for x in PODCASTS for a in x["also"]}
    unknown = set(by_id) - known
    if unknown:
        sys.exit(
            f"分類していないリンクがあります: {', '.join(sorted(unknown))}\n"
            "  本人のプロフィールなら PERSONAL_LINKS に、\n"
            "  ポッドキャストなら PODCASTS に追加してください。\n"
            "  （どちらに入れるかで意味が変わるため、自動では判断しません）")

    person = {
        "@type": "Person",
        "@id": PERSON_ID,
        "name": p["name"],
        "alternateName": [p["nameEn"], p["nameKana"]],
        "familyName": p["name"].split()[0],
        "givenName": p["name"].split()[-1],
        "url": SITE,
        "image": SITE + p["photo"],
        "jobTitle": "集中治療医",
        "description": (
            f"{p['tagline']}"
            f"{p['location']}の亀田総合病院で、ICUに専従する集中治療医です。"
            "集中治療医として働く中で得た経験を、話したり書いたりして伝えています。"
        ),
        # ORCID は研究者を一意に識別する番号。同姓同名の切り分けに一番効く
        "identifier": {
            "@type": "PropertyValue",
            "propertyID": "ORCID",
            "value": f"https://orcid.org/{p['orcid']}",
        },
        "worksFor": {
            "@type": "MedicalOrganization",
            "name": "亀田総合病院 集中治療科",
            "url": "https://www.kameda.com/",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": p["location"],
                "addressCountry": "JP",
            },
        },
        # 留学は Visiting Researcher であって卒業生ではないので alumniOf に入れない
        "alumniOf": {
            "@type": "CollegeOrUniversity",
            "name": "京都大学 医学部 医学科",
            "url": "https://www.kyoto-u.ac.jp/",
        },
    }

    # 専門医資格・関心領域は highlights の実データから拾う（勝手に足さない）
    hl = {h["label"]: h["detail"] for h in p.get("highlights", [])}
    if "専門医" in hl:
        person["hasCredential"] = [
            {"@type": "EducationalOccupationalCredential",
             "credentialCategory": "専門医資格", "name": n.strip()}
            for n in re.split(r"[／/]", hl["専門医"]) if n.strip()
        ]
    if "関心領域" in hl:
        person["knowsAbout"] = ["集中治療"] + [
            s.strip() for s in re.split(r"[・､、]", hl["関心領域"]) if s.strip()
        ]

    person["sameAs"] = [by_id[i]["url"] for i in PERSONAL_LINKS if i in by_id]

    graph = [person]
    for pod in PODCASTS:
        if pod["main"] not in by_id:
            continue
        node = {
            "@type": "PodcastSeries",
            "name": pod["name"],
            "description": pod["description"],
            "url": by_id[pod["main"]]["url"],
            "inLanguage": "ja",
            "author": {"@id": PERSON_ID},
        }
        also = [by_id[a]["url"] for a in pod["also"] if a in by_id]
        if also:
            node["sameAs"] = also
        graph.append(node)

    return {"@context": "https://schema.org", "@graph": graph}


def main():
    with open(os.path.join(ROOT, "data", "profile.json"), encoding="utf-8") as f:
        profile = json.load(f)

    person = build(profile)
    body = json.dumps(person, ensure_ascii=False, indent=2)

    # 出力が本当にJSONとして読めるかを確認してから書き込む
    json.loads(body)

    block = (
        f"{BEGIN}\n"
        f'<script type="application/ld+json">\n{body}\n</script>\n'
        f"{END}"
    )

    path = os.path.join(ROOT, "index.html")
    with open(path, encoding="utf-8") as f:
        html = f.read()

    if BEGIN in html and END in html:
        start, end = html.index(BEGIN), html.index(END) + len(END)
        html = html[:start] + block + html[end:]
    else:
        # 初回。所有権確認タグの直後に置く
        anchor = '<meta name="google-site-verification"'
        i = html.find(anchor)
        if i < 0:
            sys.exit("index.html に差し込み位置が見つかりません。中止しました。")
        j = html.index(">", i) + 1
        html = html[:j] + "\n" + block + html[j:]

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    kinds = [n["@type"] for n in person["@graph"]]
    same = len(person["@graph"][0].get("sameAs", []))
    print(f"  構造化データを書きました（{' + '.join(kinds)} / "
          f"本人のプロフィール {same}件 / {len(body)}バイト）")


if __name__ == "__main__":
    main()
