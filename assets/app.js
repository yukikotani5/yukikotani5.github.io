/* ═══════════════════════════════════════════════════════════════
   小谷祐樹 ポートフォリオ

   ▼▼▼ 設定 ▼▼▼
   お問い合わせフォームを Gmail に届かせるためのキーです。
   取り直すときは https://web3forms.com で再発行して貼り替えてください。
   空にすると、フォームはメール送信アプリを開く方式に切り替わります。
   ═══════════════════════════════════════════════════════════════ */
const FORM_ACCESS_KEY = "dd09459b-cd85-4606-bb0b-00db06162823";

/* 送信先のメールアドレスはここには書きません。
   Web3Forms 側がキーに紐づいた宛先へ配信するので、コードに置く必要がなく、
   公開リポジトリに個人アドレスを残さずに済みます。
   宛先を変えたいときは web3forms.com でキーを取り直して上の行を差し替えてください。 */
/* ═══════════════════════════════════════════════════════════════ */

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

/** XSS対策: 外部フィード由来の文字列は必ずこれを通す */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** 外部リンクは新規タブ + rel を必ず付ける */
const EXT = 'target="_blank" rel="noopener noreferrer"';

const jget = (p) => fetch(p, { cache: "no-cache" })
  .then((r) => { if (!r.ok) throw new Error(`${p}: ${r.status}`); return r.json(); });

const fmtDate = (d) => {
  if (!d) return "";
  const m = String(d).match(/(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[1]}.${m[2]}.${m[3]}` : String(d);
};

/* ───────────────────────── nav ───────────────────────── */
function initNav() {
  const nav = $("#nav"), toggle = $("#navToggle"), links = $(".nav-links");
  addEventListener("scroll", () => nav.classList.toggle("stuck", scrollY > 12), { passive: true });

  toggle.addEventListener("click", () => {
    const open = links.classList.toggle("open");
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "メニューを閉じる" : "メニューを開く");
  });
  links.addEventListener("click", (e) => {
    if (e.target.closest("a")) {
      links.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
    }
  });
}

/* ───────────────────────── reveal ───────────────────────── */
function initReveal() {
  const targets = $$(".sec .sec-title, .about-grid, .tl-wrap, .offers, .stats, .chan-grid, .pub-list, .wr-list, .talk-list, .media-list, .form");

  // 【設計方針】入場アニメーションは装飾でしかない。
  // これが原因でコンテンツが読めなくなる事態は避ける。
  // 安全にアニメーションできると確認できたときだけ <html> に .js-anim を付ける
  // （CSS 側は .js-anim が無ければ最初から全部表示される）。
  const viewportH = innerHeight || document.documentElement.clientHeight || 0;
  const safe = !matchMedia("(prefers-reduced-motion: reduce)").matches &&
               typeof IntersectionObserver !== "undefined" &&
               viewportH > 200;
  if (!safe) return;

  document.documentElement.classList.add("js-anim");
  const show = (el) => el.classList.add("in");

  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      // isIntersecting だけだと、アンカーで一気に飛んだとき通り過ぎた要素が
      // opacity:0 のまま残る。すでに上へ流れた要素(top<0)も必ず表示する。
      if (e.isIntersecting || e.boundingClientRect.top < 0) {
        show(e.target);
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0, rootMargin: "0px 0px -40px" });

  targets.forEach((el) => { el.classList.add("reveal"); io.observe(el); });

  const sweep = () => {
    const h = innerHeight || document.documentElement.clientHeight || 800;
    targets.forEach((el) => {
      if (!el.classList.contains("in") && el.getBoundingClientRect().top < h) show(el);
    });
    if (targets.every((el) => el.classList.contains("in"))) removeEventListener("scroll", sweep);
  };
  addEventListener("scroll", sweep, { passive: true });
  addEventListener("hashchange", () => setTimeout(sweep, 60));
  setTimeout(sweep, 1200);
}

/* ───────────────────────── trace ─────────────────────────
   波形を一筆書きで引く。パスごとの実長を CSS 変数に渡してから描かせる。 */
function initTrace() {
  $$(".trace path").forEach((path) => {
    try {
      const len = Math.ceil(path.getTotalLength());
      if (len > 0) path.style.setProperty("--len", len);
    } catch { /* 非対応でも CSS 既定値で動く */ }
  });
}

/* ───────────────────────── profile ───────────────────────── */
const dot = (id) => `<span class="ic" data-p="${esc(id)}" aria-hidden="true"></span>`;

function renderProfile(p) {
  // タブ名と検索結果には「何者か」が要るので、ミッション文ではなく役割を使う
  document.title = `${p.name} | ${p.roles || p.tagline}`;
  $("#heroName").textContent    = p.name;
  $("#heroNameEn").textContent  = p.nameEn;
  $("#heroTagline").textContent = p.tagline;
  $("#heroAffil").textContent   = p.affiliation;
  $("#footName").textContent    = `${p.name} / ${p.nameEn}`;
  if (p.photo) { $("#heroPhoto").src = p.photo; $("#heroPhoto").alt = p.name; }

  $("#heroLinks").innerHTML = p.links.filter((l) => l.primary)
    .map((l) => `<li><a href="${esc(l.url)}" ${EXT}>${dot(l.id)}${esc(l.name)}</a></li>`).join("");
  $("#footLinks").innerHTML = p.links
    .map((l) => `<li><a href="${esc(l.url)}" ${EXT}>${esc(l.name)}</a></li>`).join("");

  // 改行はそのまま反映する。必ず esc() を通したあとに <br> へ置き換えること
  // （順序を逆にすると HTML を注入できてしまう）
  $("#aboutText").innerHTML = (p.intro || [])
    .map((t) => `<p>${esc(t).replace(/\n/g, "<br>")}</p>`).join("");
  $("#highlights").innerHTML = (p.highlights || [])
    .map((h) => `<li><b>${esc(h.label)}</b><span>${esc(h.detail)}</span></li>`).join("");

  const tl = (rows) => rows.map((r) => `<li>
      <div class="tl-p">${esc(r.period)}</div>
      <div class="tl-o">${esc(r.org)}</div>
      <div class="tl-r">${esc(r.role)}</div></li>`).join("");
  $("#career").innerHTML = tl(p.career || []);

  // 資格・学位・学会活動・研究助成は時系列よりも列挙のほうが読みやすい
  $("#activities").innerHTML = (p.activityGroups || []).map((g) => `
    <li class="ag">
      <h4 class="ag-title">${esc(g.title)}</h4>
      <ul class="ag-items">${(g.items || []).map((t) => `<li>${esc(t)}</li>`).join("")}</ul>
    </li>`).join("");

  // 3種類の訪問者（若手／編集者／学会）がそれぞれ自分ごとだと分かるようにする。
  // ここがこのサイトの「窓口」としての実質。
  const offers = p.offers || [];
  $("#offers").innerHTML = offers.length
    ? `<h3 class="offers-head">こんなときに</h3>
       <ul class="offers-list">${offers.map((o) => `
         <li><b>${esc(o.who)}</b><span>${esc(o.body)}</span></li>`).join("")}</ul>`
    : "";

  const sel = $("#fType");
  sel.innerHTML = `<option value="" disabled selected>選んでください</option>` +
    (p.requestTypes || []).map((t) => `<option>${esc(t)}</option>`).join("");

  if (p.orcid) $("#pubAll").href = `https://orcid.org/${p.orcid}`;
  if (p.email) PUBLIC_EMAIL = p.email;   // 送信失敗時の案内にだけ使う
}

/* ───────────────────────── お知らせ ─────────────────────────
   news.json（手で書くイベント告知など）に加えて、
   執筆・講演・取材の新着を自動で拾って混ぜる。
   同じ内容を二重に管理しなくて済むようにするため。 */
function renderNews(news, writings, talks, media) {
  const today = new Date().toISOString().slice(0, 10);
  const norm = (d) => String(d || "").length === 7 ? d + "-01" : String(d || "");

  const items = [
    ...(news?.items || []).map((n) => ({
      date: norm(n.date), type: n.type || "お知らせ", status: n.status,
      title: n.title, body: n.body, url: n.url, cta: n.cta,
    })),
    ...(writings?.items || []).map((w) => ({
      date: norm(w.date), type: "執筆",
      title: w.title, body: `${w.journal}${w.citation ? " " + w.citation : ""}`, url: w.url,
    })),
    ...(talks?.items || []).map((t) => ({
      date: norm(t.date), type: "登壇",
      title: t.title, body: t.venue, url: t.url,
    })),
    ...(media?.items || []).map((m) => ({
      date: norm(m.date), type: m.type || "取材",
      title: m.title, body: m.outlet, url: m.url,
    })),
  ].filter((x) => x.title && x.date);

  // これからの予定を先に、そのあと新しい順に
  const upcoming = items.filter((x) => x.date >= today).sort((a, b) => a.date.localeCompare(b.date));
  const past = items.filter((x) => x.date < today).sort((a, b) => b.date.localeCompare(a.date));
  const list = [...upcoming, ...past].slice(0, 5);

  const el = $("#newsList");
  if (!list.length) { el.innerHTML = ""; return; }

  el.innerHTML = list.map((n) => {
    const soon = n.date >= today;
    const closed = n.status === "受付終了";
    // これからの予定でも受付が終わっていれば、参加を促す見た目にはしない
    const open = soon && !closed;
    const label = closed ? "受付終了" : soon ? "開催予定" : n.type;
    const title = n.url
      ? `<a href="${esc(n.url)}" ${EXT}>${esc(n.title)}</a>`
      : esc(n.title);
    const cta = (n.url && open)
      ? `<a class="news-cta" href="${esc(n.url)}" ${EXT}>${esc(n.cta || "詳しく見る")}</a>`
      : "";
    return `<li class="news-item${open ? " is-open" : ""}${closed ? " is-closed" : ""}">
      <span class="news-date">${esc(String(n.date).slice(0, 10).replace(/-/g, "."))}</span>
      <span class="news-type">${esc(label)}</span>
      <span class="news-body">
        <span class="news-title">${title}</span>
        ${n.body ? `<span class="news-sub">${esc(n.body)}</span>` : ""}
        ${cta}
      </span>
    </li>`;
  }).join("");
}

/* ───────────────────────── 発信（3媒体 × 2件） ─────────────────────────
   各媒体について「最新」と「よく聴かれている / 読まれている」を1つずつ。 */
function renderChannels(profile, feeds) {
  const link = (id) => (profile.links || []).find((l) => l.id === id) || {};

  const channels = [
    {
      id: "youtube", name: "ICUトーク", note: "毎週配信 · Podcast",
      url: link("youtube").url,
      // pody では同じ回を記事としても読める。
      // 聴く時間がない人や、あとから検索して探したい人のための入口。
      extra: link("pody").url && { url: link("pody").url, label: "記事で読む →" },
      items: [feeds?.youtube?.latest, feeds?.youtube?.popular],
    },
    {
      id: "voicy", name: "小谷祐樹とICU", note: "毎日配信 · Voicy",
      url: link("voicy").url || profile.voicy?.channelUrl,
      // feeds が本線。取得に失敗した場合に備えて profile 側も見る
      items: [feeds?.voicy?.latest || profile.voicy?.latest,
              feeds?.voicy?.popular || profile.voicy?.popular],
    },
    {
      id: "note", name: "note", note: "書きもの",
      url: link("note").url,
      items: [feeds?.note?.latest, feeds?.note?.popular],
    },
  ];

  const card = (it) => {
    if (!it || !it.url) return "";
    return `<a class="ch-card" href="${esc(it.url)}" ${EXT}>
      ${it.thumbnail ? `<img class="ch-thumb" src="${esc(it.thumbnail)}" alt="" loading="lazy">` : ""}
      <span class="ch-label">${esc(it.label || "")}</span>
      <span class="ch-title">${esc(it.title || "")}</span>
      <span class="ch-meta">
        ${it.date ? `<span class="ch-date">${esc(fmtDate(it.date))}</span>` : ""}
        ${it.metric ? `<span class="ch-metric">${esc(it.metric)}</span>` : ""}
      </span>
    </a>`;
  };

  $("#channels").innerHTML = channels.map((c) => {
    const body = c.items.map(card).filter(Boolean).join("");
    return `<section class="chan">
      <header class="chan-head">
        <h3 class="chan-name">${dot(c.id)}${esc(c.name)}</h3>
        <p class="chan-note">${esc(c.note)}</p>
        <div class="chan-links">
          ${c.url ? `<a class="chan-link" href="${esc(c.url)}" ${EXT}>すべて見る →</a>` : ""}
          ${c.extra ? `<a class="chan-link" href="${esc(c.extra.url)}" ${EXT}>${esc(c.extra.label)}</a>` : ""}
        </div>
      </header>
      ${body || `<p class="empty">うまく読み込めませんでした。</p>`}
    </section>`;
  }).join("");
}

/* ───────────────────────── 研究業績（被引用トップ5） ───────────────────────── */
function renderResearch(d) {
  const s = d.stats || {};
  const nf = (n) => (typeof n === "number" ? n.toLocaleString("ja-JP") : "—");
  // 大きな数字を並べると「点数表」に見えて、初めて見た人には威圧的に映る。
  // 事実は落とさず、地の文の一行として静かに置く。
  $("#pubStats").innerHTML = s.total
    ? `<li class="pub-summary">これまでに${esc(nf(s.total))}本。`
      + `うち原著論文が${esc(nf(s.articles))}本、筆頭著者のものが${esc(nf(s.firstAuthor))}本です。</li>`
    : "";

  const top = d.top || [];
  if (!top.length) {
    $("#pubList").innerHTML = `<li class="empty">うまく読み込めませんでした。</li>`;
    return;
  }
  $("#pubList").innerHTML = top.map((p, i) => {
    const au = (p.authors || []).join(", ");
    const title = p.url ? `<a href="${esc(p.url)}" ${EXT}>${esc(p.title)}</a>` : esc(p.title);
    // 立場をはっきり書く。共著の大規模試験を筆頭論文と見分けがつかない形で
    // 並べると、実際より大きく見せることになる。
    const role = p.position === "first" ? "筆頭著者"
               : p.position === "last" ? "最終著者" : "共著";
    return `<li class="pub${p.position === "first" ? " is-first" : ""}">
      <div class="pub-body">
        <div class="pub-meta">
          <span class="pub-year">${esc(p.year || "")}</span>
          ${p.journal ? `<span class="pub-jr">${esc(p.journal)}</span>` : ""}
          <span class="tag${p.position === "first" ? " tag-first" : ""}">${esc(role)}</span>
        </div>
        <p class="pub-t">${title}</p>
        ${au ? `<p class="pub-au">${esc(au)}</p>` : ""}
        <p class="pub-cite">被引用 ${esc(nf(p.citations))} 回</p>
      </div>
    </li>`;
  }).join("");
}

/* ───────────────────────── 一覧の折りたたみ ─────────────────────────
   件数が増えてきた一覧は、最新 limit 件だけ出して残りはボタンで開く。
   非表示には hidden 属性を使う（display:none になるので支援技術からも外れる）。 */
function initCollapse(listSel, btnSel, limit = 5) {
  const list = $(listSel), btn = $(btnSel);
  if (!list || !btn) return;
  const items = [...list.children].filter((el) => el.tagName === "LI" && !el.classList.contains("loading"));
  if (items.length <= limit) { btn.hidden = true; items.forEach((el) => (el.hidden = false)); return; }

  let open = false;
  const apply = () => {
    items.forEach((el, i) => { el.hidden = !open && i >= limit; });
    btn.textContent = open ? "閉じる" : `すべて表示（${items.length}件）`;
    btn.setAttribute("aria-expanded", String(open));
  };
  btn.hidden = false;
  btn.onclick = () => {
    open = !open;
    apply();
    // 閉じたときに画面が飛ばないよう、一覧の先頭へ戻す
    if (!open) list.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  apply();
}

/* ───────────────────────── 原稿執筆 ───────────────────────── */
function renderWritings(items) {
  const el = $("#writingList");
  if (!items?.length) { el.innerHTML = `<li class="empty">準備中です。</li>`; return; }
  const sorted = [...items].sort((a, b) => String(b.date).localeCompare(String(a.date)));
  el.innerHTML = sorted.map((w) => {
    const title = w.url ? `<a href="${esc(w.url)}" ${EXT}>${esc(w.title)}</a>` : esc(w.title);
    const ym = String(w.date || "").replace("-", ".");
    return `<li class="wr">
      <div class="wr-when">${esc(ym)}</div>
      <div class="wr-body">
        <div class="wr-top">
          ${w.kind ? `<span class="wr-kind${w.kind === "和文論文" ? " is-paper" : ""}">${esc(w.kind)}</span>` : ""}
          <span class="wr-journal">${esc(w.journal)}</span>
          ${w.citation ? `<span class="wr-cite">${esc(w.citation)}</span>` : ""}
        </div>
        ${w.feature ? `<p class="wr-feature">${esc(w.feature)}</p>` : ""}
        <p class="wr-title">${title}</p>
        <p class="wr-sub">${esc(w.authors || "")}${w.publisher ? `　/　${esc(w.publisher)}` : ""}</p>
      </div>
    </li>`;
  }).join("");
  initCollapse("#writingList", "#writingMore");
}

/* ───────────────────────── 講演・セミナー ───────────────────────── */
function renderTalks(items) {
  const el = $("#talkList");
  if (!items?.length) { el.innerHTML = `<li class="empty">準備中です。</li>`; return; }
  const sorted = [...items].sort((a, b) => String(b.date).localeCompare(String(a.date)));
  el.innerHTML = sorted.map((t) => {
    const ym = String(t.date || "").slice(0, 7).replace("-", ".");
    const title = t.url ? `<a href="${esc(t.url)}" ${EXT}>${esc(t.title)}</a>` : esc(t.title);
    return `<li class="talk">
      <div class="talk-when">${esc(ym)}</div>
      <div class="talk-body">
        <div class="talk-top">
          ${t.kind ? `<span class="talk-kind">${esc(t.kind)}</span>` : ""}
          ${/* 演者以外（座長など）のときだけ役割を出す */ ""}
          ${t.role ? `<span class="talk-role">${esc(t.role)}</span>` : ""}
          ${t.venue ? `<span class="talk-venue">${esc(t.venue)}</span>` : ""}
        </div>
        <p class="talk-title">${title}</p>
        ${t.note ? `<p class="talk-note">${esc(t.note)}</p>` : ""}
      </div>
    </li>`;
  }).join("");
  initCollapse("#talkList", "#talkMore");
}

/* ───────────────────────── 取材・掲載 ───────────────────────── */
function renderMedia(items) {
  const el = $("#mediaList");
  if (!items?.length) { el.innerHTML = `<li class="empty">準備中です。</li>`; return; }
  const sorted = [...items].sort((a, b) => String(b.date).localeCompare(String(a.date)));
  el.innerHTML = sorted.map((m) => {
    const title = m.url ? `<a href="${esc(m.url)}" ${EXT}>${esc(m.title)}</a>` : esc(m.title);
    return `<li class="media-item${m.image ? " has-img" : ""}">
      ${m.image ? `<a class="media-thumb" href="${esc(m.url)}" ${EXT} tabindex="-1" aria-hidden="true">
          <img src="${esc(m.image)}" alt="" loading="lazy"></a>` : ""}
      <div class="media-body">
        <div class="media-top">
          <span class="media-date">${esc(fmtDate(m.date))}</span>
          ${m.type ? `<span class="media-type">${esc(m.type)}</span>` : ""}
          <span class="media-outlet">${esc(m.outlet)}</span>
        </div>
        <h3 class="media-title">${title}</h3>
        ${m.excerpt ? `<p class="media-ex">${esc(m.excerpt)}</p>` : ""}
      </div>
    </li>`;
  }).join("");
}

/* ───────────────────────── フォーム ─────────────────────────
   ページに出す連絡先は profile.json の email（researchmap 等で公開済みの所属アドレス）だけ。
   フォームの実際の配信先は Web3Forms 側が持っているので、ここには現れない。 */
let PUBLIC_EMAIL = "";

function initForm() {
  const form = $("#contactForm"), status = $("#formStatus"),
        note = $("#formNote"), btn = $("#submitBtn");
  const configured = FORM_ACCESS_KEY.trim().length > 0;

  // 公開ページに生のメールアドレスは出さない（収集ボットに拾われるため）。
  // 送信に失敗したときだけ、下の catch 側で連絡先を案内する。
  note.innerHTML = configured
    ? "いただいた内容は直接メールで届きます。"
    : `いまはメールアプリが開く設定です。フォームから直接送れるようにするには、
       <code>assets/app.js</code> の <code>FORM_ACCESS_KEY</code> を設定してください。`;
  if (!configured) status.className = "form-status warn";

  const RULES = {
    fName:  (v) => v.trim() ? "" : "お名前を入力してください。",
    fEmail: (v) => !v.trim() ? "メールアドレスを入力してください。"
                 : /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim()) ? "" : "メールアドレスの形式をご確認ください。",
    fType:  (v) => v ? "" : "ご用件を選んでください。",
    fMsg:   (v) => v.trim().length >= 10 ? "" : "内容を10文字以上でご記入ください。",
  };

  const check = (id) => {
    const el = $("#" + id), msg = RULES[id](el.value);
    $(`.err[data-for="${id}"]`).textContent = msg;
    el.setAttribute("aria-invalid", msg ? "true" : "false");
    return !msg;
  };
  Object.keys(RULES).forEach((id) => {
    const el = $("#" + id);
    el.addEventListener("blur", () => check(id));
    el.addEventListener("input", () => {
      if (el.getAttribute("aria-invalid") === "true") check(id);
    });
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    status.textContent = ""; status.className = "form-status";

    if (!Object.keys(RULES).map(check).every(Boolean)) {
      status.className = "form-status ng";
      status.textContent = "未入力の項目があります。ご確認ください。";
      $('[aria-invalid="true"]')?.focus();
      return;
    }
    if ($("#botcheck").value) return;               // ハニーポット: 静かに無視

    const d = Object.fromEntries(new FormData(form).entries());

    if (!configured) {                              // フォールバック: mailto
      const body = [
        `お名前: ${d.name}`, `ご所属: ${d.organization || "—"}`,
        `メール: ${d.email}`, `ご用件: ${d.request_type}`, "", d.message,
      ].join("\n");
      location.href = `mailto:${PUBLIC_EMAIL}` +
        `?subject=${encodeURIComponent(`【${d.request_type}】${d.name}様`)}` +
        `&body=${encodeURIComponent(body)}`;
      status.className = "form-status ok";
      status.textContent = "メールアプリを開きました。そのまま送信してください。";
      return;
    }

    btn.disabled = true; btn.textContent = "送信中…";
    try {
      const res = await fetch("https://api.web3forms.com/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          access_key: FORM_ACCESS_KEY,
          subject: `【${d.request_type}】${d.name}様`,
          from_name: "ポートフォリオ お問い合わせフォーム",
          replyto: d.email,
          お名前: d.name,
          ご所属: d.organization || "（未記入）",
          メールアドレス: d.email,
          ご用件: d.request_type,
          内容: d.message,
        }),
      });
      const j = await res.json().catch(() => ({}));
      if (!res.ok || j.success === false) throw new Error(j.message || `HTTP ${res.status}`);

      form.reset();
      $$(".err").forEach((p) => (p.textContent = ""));
      status.className = "form-status ok";
      status.textContent = "送信しました。ありがとうございます。数日以内にお返事します。";
    } catch (err) {
      status.className = "form-status ng";
      const alt = PUBLIC_EMAIL
        ? `お手数ですが <a href="mailto:${esc(PUBLIC_EMAIL)}">メールで直接ご連絡ください</a>。`
        : "お手数ですが、時間をおいてもう一度お試しください。";
      status.innerHTML = `送信できませんでした（${esc(err.message)}）。${alt}`;
    } finally {
      btn.disabled = false; btn.textContent = "送信する";
    }
  });
}

/* ───────────────────────── boot ───────────────────────── */
(async function boot() {
  $("#year").textContent = new Date().getFullYear();
  initNav(); initForm();

  const settle = (p) => p.then((v) => ({ ok: true, v })).catch((e) => { console.warn(e); return { ok: false }; });
  const [prof, pubs, feeds, media, writings, talks, news] = await Promise.all([
    settle(jget("data/profile.json")),
    settle(jget("data/publications.json")),
    settle(jget("data/feeds.json")),
    settle(jget("data/media.json")),
    settle(jget("data/writings.json")),
    settle(jget("data/talks.json")),
    settle(jget("data/news.json")),
  ]);

  if (prof.ok) renderProfile(prof.v);
  if (media.ok) renderMedia(media.v.items);
  if (writings.ok) renderWritings(writings.v.items);
  if (talks.ok) renderTalks(talks.v.items);
  renderNews(news.ok ? news.v : {}, writings.ok ? writings.v : {},
             talks.ok ? talks.v : {}, media.ok ? media.v : {});
  renderChannels(prof.ok ? prof.v : {}, feeds.ok ? feeds.v : {});

  if (pubs.ok) {
    renderResearch(pubs.v);
    const d = pubs.v.updatedAt ? new Date(pubs.v.updatedAt) : null;
    if (d && !isNaN(d)) {
      $("#lastUpdated").textContent =
        `研究業績と発信の情報は、毎日自動で更新しています（最終更新: ${d.toLocaleDateString("ja-JP")}）`;
    }
  } else {
    $("#pubList").innerHTML = `<li class="empty">うまく読み込めませんでした。<br>
      <a href="https://orcid.org/0000-0002-9532-2859" ${EXT}>ORCID</a> でご覧いただけます。</li>`;
  }

  initReveal();
  initTrace();
})();
