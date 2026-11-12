/* Tantrāloka reading room. Plain JS; data comes from <script> files so the site also opens from disk. */
(() => {
  "use strict";
  const B = window.TL_BOOK, N = window.TL_NOTES, Lipi = window.SDLipi;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const main = $("#main"), side = $("#side"), pop = $("#pop"), popInner = $("#popInner");
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* storage unavailable */ } },
  };

  /* ------------------------------------------------------------ lazy data */
  const loaded = {};
  function load(name, test) {
    if (test()) return Promise.resolve();
    if (!loaded[name]) loaded[name] = new Promise((res, rej) => {
      const s = document.createElement("script");
      s.src = `data/${name}.js`; s.onload = () => res(); s.onerror = () => rej(new Error(name));
      document.head.appendChild(s);
    });
    return loaded[name];
  }
  const loadLex = () => load("lex", () => !!window.TL_LEX);
  const loadViveka = () => load("viveka", () => !!window.TL_VIVEKA);

  /* ------------------------------------------------------------ indexes */
  const blocks = B.blocks;
  const secs = B.sections;
  const blockSec = new Array(blocks.length);
  secs.forEach((s, i) => { for (let k = s.start; k < s.end; k++) blockSec[k] = i; });
  const byId = new Map();
  blocks.forEach((b, i) => { if (b.id) byId.set(b.id, i); });
  const nlab = (n) => (+n > 2000 ? `A${+n - 2000}` : String(n));
  const label = (img) => B.labels[img] ? `p. ${B.labels[img]}` : `image ${img}`;
  // which section shows each footnote, and where the ref is
  const noteSec = {}, noteBlock = {};
  blocks.forEach((b, i) => {
    if (!b.html) return;
    const re = /data-n="(\d+)"/g; let m;
    while ((m = re.exec(b.html))) { if (!(m[1] in noteSec)) { noteSec[m[1]] = blockSec[i]; noteBlock[m[1]] = b.id; } }
  });
  // notes without a placed reference: show in the section of their page
  const pageSec = {};
  blocks.forEach((b, i) => { if (b.t === "pg" && !(b.p in pageSec)) pageSec[b.p] = blockSec[i]; });
  Object.keys(N.html).forEach((n) => { if (!(n in noteSec)) noteSec[n] = pageSec[N.page[n]]; });
  const secNotes = secs.map(() => []);
  Object.keys(N.html).map(Number).sort((a, b) => a - b).forEach((n) => { if (noteSec[n] != null) secNotes[noteSec[n]].push(n); });
  // verses
  const verseBlock = {};
  blocks.forEach((b) => { if (b.t === "dv" && b.v) b.v.forEach((v) => { if (!(v in verseBlock)) verseBlock[v] = b.id; }); });
  const verseList = Object.keys(verseBlock).sort((a, b) => parseInt(a) - parseInt(b) || a.localeCompare(b));

  /* ------------------------------------------------------------ sidebar */
  function sectionRange(s) {
    const e = s.toc != null ? B.toc[s.toc] : null;
    const m = e && e.title.match(/\((vv?\. [^)]*)\)/);
    const first = blocks[s.start], lastP = (() => { for (let k = s.end - 1; k >= s.start; k--) if (blocks[k].p) return blocks[k].p; return null; })();
    const pg = first && first.p && B.labels[first.p] ? `pp. ${B.labels[first.p]}–${B.labels[lastP] || ""}` : "";
    return [m ? m[1] : "", pg].filter(Boolean).join(", ");
  }
  function cleanTitle(t) { return t.replace(/\s*\((vv?\. [^)]*)\)/, ""); }
  function renderSide(cur) {
    let h = `<h2>Contents</h2><ol>`;
    secs.forEach((s, i) => {
      const sub = s.level >= 3 ? " sub" : "";
      h += `<li class="${sub}"><a href="#/read/${i}" ${i === cur ? 'aria-current="true"' : ""}>${esc(cleanTitle(s.title))}<span class="rng">${esc(sectionRange(s))}</span></a></li>`;
    });
    h += `</ol>`;
    side.innerHTML = h;
    const a = $('[aria-current="true"]', side);
    if (a) a.scrollIntoView({ block: "nearest" });
  }

  /* ------------------------------------------------------------ reader */
  function verseTools(b) {
    const vs = b.v || [];
    const nums = [...new Set(vs)];
    const chip = nums.length ? `<span class="vchip">KSTS ${nums.length > 1 ? "vv." : "v."} ${esc(nums.length > 2 ? nums[0] + "–" + nums[nums.length - 1] : nums.join(", "))}</span>` : "";
    const viv = b.u && b.u.length ? `<button class="vbtn" data-viv="${esc(b.u.join(","))}" aria-expanded="false">Jayaratha’s Viveka in Sanskrit</button>` : "";
    return `<div class="verse-tools">${chip}${viv}<button class="vbtn" data-copy>Copy verse</button><button class="vbtn" data-scan="${b.p}">Page scan</button></div>`;
  }

  function blockHTML(b, k) {
    switch (b.t) {
      case "pg": {
        const inl = [1, 2, 3].some((d) => blocks[k + d] && blocks[k + d].html && blocks[k + d].html.includes(`data-p="${b.p}"`));
        return inl ? `<span class="pgline" id="pg${b.p}"></span>` : `<span class="pgline" id="pg${b.p}"><button class="pgm" data-scan="${b.p}" title="Open the scan of this page">${esc(label(b.p))}</button></span>`;
      }
      case "h": return b.lv <= 2 ? `<h2 id="${b.id}">${b.html}</h2>` : `<h3 id="${b.id}">${b.html}</h3>`;
      case "dv": {
        // attach the transliteration block that follows
        let ia = "";
        const nx = blocks[k + 1];
        if (nx && nx.t === "ia") ia = `<div class="ial">${nx.html}</div>`;
        return `<div class="verse" id="${b.id}"><div class="dvl">${b.html}</div>${ia}${verseTools(b)}</div>`;
      }
      case "ia": {
        const pv = blocks[k - 1];
        if (pv && pv.t === "dv") return "";
        return `<div class="ia-only" id="${b.id}">${b.html}</div>`;
      }
      case "fig": return b.table ? `<figure class="figure" id="${b.id}">${b.table}<figcaption>${esc(b.cap)}</figcaption></figure>` : `<figure class="figure" id="${b.id}"><img src="${esc(b.src)}" alt="${esc(b.cap)}" loading="lazy"><figcaption>${esc(b.cap)}</figcaption></figure>`;
      case "c": return `<p class="c" id="${b.id}">${b.html}</p>`;
      case "vt": return `<p class="vt" id="${b.id}">${b.html}</p>`;
      default: return `<p id="${b.id}" class="${b.ni ? "ni" : ""}">${b.html}</p>`;
    }
  }

  function notesHTML(list) {
    return list.map((n) => {
      const back = noteBlock[n] ? ` <a class="back" href="#/read/${noteSec[n]}/${noteBlock[n]}" data-fnback="${n}" aria-label="Back to the text">↩</a>` : "";
      return `<div class="note" id="n${n}"><div class="nn"><a href="#/note/${n}">${nlab(n)}</a></div><div>${N.html[n] || ""}${back}</div></div>`;
    }).join("");
  }

  let curSec = -1;
  function showSection(i, target) {
    i = Math.max(0, Math.min(secs.length - 1, i | 0));
    const s = secs[i];
    if (curSec !== i || !$(".reader", main)) {
      let h = `<article class="reader">`;
      const e = s.toc != null ? B.toc[s.toc] : null;
      h += `<h1 class="sec">${esc(cleanTitle(s.title))}</h1><p class="sec-meta">${esc(sectionRange(s))}</p>`;
      for (let k = s.start; k < s.end; k++) {
        const b = blocks[k];
        if (k === s.start && b.t === "h" && e && b.toc === s.toc) continue;
        h += blockHTML(b, k);
      }
      const nl = secNotes[i];
      if (nl.length) h += `<details class="sec-notes" open><summary>Footnotes <small>${nlab(nl[0])}–${nlab(nl[nl.length - 1])}</small></summary>${notesHTML(nl)}</details>`;
      const prev = i > 0 ? `<a href="#/read/${i - 1}"><small>Previous</small>${esc(cleanTitle(secs[i - 1].title))}</a>` : "<span></span>";
      const next = i < secs.length - 1 ? `<a href="#/read/${i + 1}" style="text-align:right"><small>Next</small>${esc(cleanTitle(secs[i + 1].title))}</a>` : "<span></span>";
      h += `<nav class="navfoot" aria-label="Sections">${prev}${next}</nav></article>`;
      main.innerHTML = h;
      placePageMarks();
      curSec = i;
      renderSide(i);
      store.set("tl-last", String(i));
    }
    closePop();
    requestAnimationFrame(() => {
      if (target) {
        const el = document.getElementById(target);
        if (el) {
          el.scrollIntoView({ block: "center" });
          el.classList.remove("hl-block"); void el.offsetWidth; el.classList.add("hl-block");
          return;
        }
      }
      window.scrollTo(0, 0);
    });
  }

  // page numbers inside paragraphs: show a small bar inline, and a margin label at that height
  function placePageMarks() {
    const art = $(".reader", main);
    $$(".pb", art).forEach((el) => {
      el.classList.add("inl");
      const btn = document.createElement("button");
      btn.className = "pgm"; btn.dataset.scan = el.dataset.p;
      btn.textContent = label(el.dataset.p);
      btn.title = "Open the scan of this page";
      el.dataset.mark = "1";
      art.appendChild(btn);
    });
    positionMarks();
  }
  function positionMarks() {
    const art = $(".reader", main);
    if (!art) return;
    const narrow = window.matchMedia("(max-width: 640px)").matches;
    const ar = art.getBoundingClientRect();
    const floating = $$(":scope > .pgm", art);
    const anchors = $$(".pb[data-mark]", art);
    floating.forEach((b, k) => {
      const a = anchors[k];
      if (!a) return;
      if (narrow) { b.style.display = "none"; return; }
      b.style.display = "";
      const r = a.getBoundingClientRect();
      b.style.top = `${r.top - ar.top - 2}px`;
    });
    $$(".pgline > .pgm", art).forEach((b) => { b.style.position = narrow ? "static" : "absolute"; });
  }
  window.addEventListener("resize", () => positionMarks());
  document.addEventListener("toggle", () => positionMarks(), true);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => positionMarks());

  /* ------------------------------------------------------------ popovers */
  let popAnchor = null;
  function openPop(anchor, html) {
    if (popAnchor) popAnchor.classList.remove("on");
    popAnchor = anchor; anchor.classList.add("on");
    popInner.innerHTML = html;
    pop.hidden = false;
    const r = anchor.getBoundingClientRect();
    const pw = pop.offsetWidth, ph = pop.offsetHeight;
    let left = Math.min(window.innerWidth - pw - 10, Math.max(10, r.left + r.width / 2 - pw / 2));
    let top = r.bottom + 8;
    if (top + ph > window.innerHeight - 10) top = Math.max(10, r.top - ph - 8);
    pop.style.left = `${left}px`; pop.style.top = `${top}px`;
  }
  function closePop() {
    pop.hidden = true;
    if (popAnchor) popAnchor.classList.remove("on");
    popAnchor = null;
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closePop(); closeScan(); }
    if (e.key === "/" && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) { e.preventDefault(); $("#q").focus(); }
    if (!$("#scan").hidden) { if (e.key === "ArrowLeft") scanGo(-1); if (e.key === "ArrowRight") scanGo(1); }
  });
  window.addEventListener("scroll", () => { if (!pop.hidden && !window.matchMedia("(max-width: 640px)").matches) closePop(); }, { passive: true });

  function footnotePop(sup) {
    const n = sup.dataset.n;
    const html = N.html[n];
    const where = N.page[n] ? label(N.page[n]) : "";
    openPop(sup, `<div class="phead"><span><b>Note ${esc(nlab(n))}</b> · ${esc(where)}</span><button class="x" data-close aria-label="Close"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
      <div class="note-body">${html || "<p>This note could not be read from the page scan.</p>"}</div>
      <div class="pfoot"><a href="#/read/${noteSec[n]}/n${n}">Show in the footnotes</a><button class="linkbtn" data-scan="${N.page[n] || ""}">Page scan</button></div>`);
  }

  /* word popup */
  const shorten = (s, n = 160) => (s && s.length > n ? s.slice(0, n).replace(/\s+\S*$/, "") + " …" : s || "");
  let iastIndex = null;
  function lexByForm(deva) {
    if (!iastIndex) {
      iastIndex = new Map();
      TL_LEX.lex.forEach((e, i) => { if (!iastIndex.has(e.w)) iastIndex.set(e.w, i); });
    }
    const ia = Lipi.toIast(deva.replace(/[।॥०-९]/g, "")).replace(/m̐/g, "ṃ");
    return iastIndex.has(ia) ? iastIndex.get(ia) : null;
  }
  function gloss(p) { const g = TL_LEX.glossary; return g[p.l] || (p.r && g[p.r]) || null; }
  function partCard(p) {
    const g = gloss(p);
    let h = `<div><span class="pd" lang="sa">${esc(p.ld || p.d || p.l)}</span> <span class="pi">${esc(p.l)}</span></div>`;
    if (p.g) h += `<p class="pg" style="margin:2px 0">${esc(p.g)}</p>`;
    h += `<p style="margin:4px 0">${g && g.m ? esc(g.m) : "<span class='pg'>No dictionary meaning was found for this form.</span>"}</p>`;
    if (g && g.mw) h += `<details class="mw"><summary>Monier-Williams</summary><p>${esc(g.mw)}</p></details>`;
    return h;
  }
  function wordPopHTML(deva, k, focus) {
    const e = k != null ? TL_LEX.lex[k] : null;
    const ia = e ? e.w : Lipi.toIast(deva);
    let h = `<div class="phead"><span>${e ? (e.p && e.p.length > 1 ? "Sandhi split and meaning" : "Meaning") : "Sanskrit word"}</span><button class="x" data-close aria-label="Close"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
      <p class="pw" lang="sa">${esc(deva)}</p><p class="pw-i">${esc(ia)}</p>`;
    if (e && e.p && e.p.length) {
      if (e.p.length > 1) {
        h += `<div class="split">` + e.p.map((p, i) => `${i ? '<span class="plus">+</span>' : ""}<button data-part="${i}" aria-pressed="${focus === i}" lang="sa" title="${esc(p.u)}">${esc(p.d)}</button>`).join("") + `</div>`;
      }
      if (focus != null && e.p[focus]) {
        h += `<div class="parts"><li style="list-style:none">${partCard(e.p[focus])}</li><button class="linkbtn" data-part="all">All parts</button></div>`;
      } else {
        h += `<ul class="parts">` + e.p.map((p) => {
          const g = gloss(p);
          return `<li><span class="pd" lang="sa">${esc(p.d)}</span><span class="pi">${esc(p.l)}</span><span class="pg">${esc(p.g || "")}</span><span class="pm">${esc(shorten(g && g.m ? g.m : ""))}</span></li>`;
        }).join("") + `</ul>`;
        if (e.p.length === 1) { const g = gloss(e.p[0]); if (g && g.mw) h += `<details class="mw"><summary>Monier-Williams</summary><p>${esc(g.mw)}</p></details>`; }
      }
    } else {
      h += `<p class="pg">This word is shown as read from the page; it has no word analysis yet.</p>`;
    }
    const lemma = e && e.p && e.p.length === 1 ? e.p[0].l : ia;
    const slug = lemma.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-zA-Z]/g, "").toLowerCase();
    h += `<div class="pfoot"><a href="#/search?q=${encodeURIComponent(deva)}">Find in the book</a><a href="https://www.wisdomlib.org/definition/${slug}" target="_blank" rel="noopener">Wisdomlib</a></div>`;
    return h;
  }
  let wordState = null;
  function wordPop(el, focus) {
    const deva = el.textContent.trim();
    loadLex().then(() => {
      let k = el.dataset.k != null ? +el.dataset.k : lexByForm(deva);
      wordState = { el, deva, k };
      openPop(el, wordPopHTML(deva, k, focus));
    }).catch(() => openPop(el, `<p class="pw" lang="sa">${esc(deva)}</p><p>${esc(Lipi.toIast(deva))}</p><p class="pg">The word list could not be loaded.</p>`));
  }

  /* ------------------------------------------------------------ Viveka */
  function toggleViveka(btn) {
    const box = btn.closest(".verse");
    let panel = $(".viveka", box);
    if (panel) { panel.remove(); btn.setAttribute("aria-expanded", "false"); positionMarks(); return; }
    btn.setAttribute("aria-expanded", "true");
    panel = document.createElement("div");
    panel.className = "viveka";
    panel.innerHTML = `<p class="src">Loading…</p>`;
    box.appendChild(panel);
    loadViveka().then(() => {
      const units = btn.dataset.viv.split(",");
      panel.innerHTML = `<p class="src">Sanskrit text of the verse with Jayaratha’s Viveka, from the Kashmir Series of Texts and Studies edition (vol. 23, 1918). Tap a word for its meaning.</p>` +
        units.map((u) => `<div class="vu">${TL_VIVEKA[u] || ""}</div>`).join("");
      positionMarks();
    });
  }

  /* ------------------------------------------------------------ scans */
  let scanImg = 0;
  function openScan(img) {
    img = +img; if (!img) return;
    scanImg = Math.max(1, Math.min(514, img));
    const ext = scanImg === 1 ? "jpg" : "png";
    $("#scanImg").src = `scans/p${String(scanImg).padStart(3, "0")}.${ext}`;
    $("#scanImg").alt = `Scan of ${label(scanImg)}`;
    $("#scanLabel").textContent = `${label(scanImg)} · image ${scanImg} of 514`;
    $("#scan").hidden = false;
    closePop();
  }
  function scanGo(d) { openScan(scanImg + d); }
  function closeScan() { $("#scan").hidden = true; }
  $("#scanPrev").addEventListener("click", () => scanGo(-1));
  $("#scanNext").addEventListener("click", () => scanGo(1));
  $("#scanClose").addEventListener("click", closeScan);
  $("#scanGo").addEventListener("click", () => { closeScan(); location.hash = `#/page/${scanImg}`; });
  $("#scan").addEventListener("click", (e) => { if (e.target.classList.contains("scan-img")) closeScan(); });

  /* ------------------------------------------------------------ clicks */
  document.addEventListener("click", (e) => {
    const t = e.target;
    const fn = t.closest("sup.fn");
    if (fn) { e.preventDefault(); if (popAnchor === fn) closePop(); else footnotePop(fn); return; }
    const w = t.closest(".w");
    if (w) { e.preventDefault(); if (popAnchor === w) closePop(); else wordPop(w); return; }
    const part = t.closest("[data-part]");
    if (part && wordState) { e.preventDefault(); const f = part.dataset.part === "all" ? null : +part.dataset.part; popInner.innerHTML = wordPopHTML(wordState.deva, wordState.k, f); return; }
    if (t.closest("[data-close]")) { closePop(); return; }
    const sc = t.closest("[data-scan]");
    if (sc) { e.preventDefault(); openScan(sc.dataset.scan); return; }
    const vb = t.closest("[data-viv]");
    if (vb) { toggleViveka(vb); return; }
    const cp = t.closest("[data-copy]");
    if (cp) {
      const v = cp.closest(".verse");
      const txt = $$(".dvl .vl", v).map((x) => x.textContent.replace(/\s+/g, " ").trim()).join("\n");
      (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(() => { cp.textContent = "Copied"; setTimeout(() => (cp.textContent = "Copy verse"), 1500); }).catch(() => {});
      return;
    }
    if (!pop.hidden && !t.closest("#pop")) closePop();
    if (side.classList.contains("open") && !t.closest("#side") && !t.closest("#tocBtn")) { side.classList.remove("open"); $("#tocBtn").setAttribute("aria-expanded", "false"); }
  });
  $("#tocBtn").addEventListener("click", () => {
    if (!side.innerHTML) renderSide(curSec);
    const o = side.classList.toggle("open");
    $("#tocBtn").setAttribute("aria-expanded", String(o));
  });

  /* ------------------------------------------------------------ settings */
  $("#themeBtn").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme === "dark" || (!document.documentElement.dataset.theme && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = dark ? "light" : "dark";
    store.set("tl-theme", document.documentElement.dataset.theme);
  });
  if (!document.documentElement.dataset.theme && window.matchMedia("(prefers-color-scheme: dark)").matches) document.documentElement.dataset.theme = "dark";
  function size(d) {
    const cur = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--fs")) || 19;
    const v = Math.max(15, Math.min(26, cur + d));
    document.documentElement.style.setProperty("--fs", v + "px");
    store.set("tl-size", String(v));
    positionMarks();
  }
  $("#smaller").addEventListener("click", () => size(-1));
  $("#larger").addEventListener("click", () => size(1));

  /* ------------------------------------------------------------ home */
  function home() {
    curSec = -1;
    const last = +store.get("tl-last", "-1");
    const nNotes = Object.keys(N.html).length;
    const top = secs.filter((s) => s.toc != null);
    let toc = "";
    secs.forEach((s, i) => {
      if (s.toc == null && i === 0) { toc += `<li><a href="#/read/0" class="top">Title, acknowledgements, contents and abbreviations</a></li>`; return; }
      toc += `<li><a href="#/read/${i}" class="${s.level <= 2 ? "top" : ""}">${esc(cleanTitle(s.title))}</a><span class="rng">${esc(sectionRange(s))}</span></li>`;
    });
    main.innerHTML = `<div class="home">
      <section class="hero">
        <div>
          <div class="hero-verse" lang="sa" aria-label="Tantrāloka 1.1">
            <span>विमलकलाश्रयाभिनवसृष्टिमहा जननी</span>
            <span class="l2">भरिततनुश्च पञ्चमुखगुप्तरुचिर्जनकः ।</span>
            <span>तदुभययामलस्फुरितभावविसर्गमयं</span>
            <span class="l2"><span class="glow" style="display:inline">हृदयमनुत्तरामृतकुलं</span> मम संस्फुरतात् ॥ १ ॥</span>
          </div>
          <p class="hero-tr">“May the body of the nectar of the Absolute, my Heart, the emission which is the vibrant state of the united form of both of them, pulsate radiantly!” (from Dyczkowski’s translation of verse 1)</p>
        </div>
        <div class="hero-side">
          <img src="scans/p001.jpg" alt="Cover of the book">
          <h1>Tantrāloka: The Light On and Of the Tantras</h1>
          <p class="by">Abhinavagupta, with Jayaratha’s commentary, the Viveka. Volume one, chapter one, translated with explanatory notes by Mark S. G. Dyczkowski (2023).</p>
          <a class="btn" href="#/read/${last >= 0 ? last : 1}">${last >= 0 ? "Continue reading" : "Start reading"}</a>
          <a class="btn ghost" href="#/verses">Browse the verses</a>
          <form class="finder" id="finder"><label for="vno">Go to verse</label><input id="vno" inputmode="numeric" placeholder="e.g. 132"><button class="btn ghost" type="submit">Go</button></form>
        </div>
      </section>
      <ul class="facts"><li><b>514</b> pages</li><li><b>${verseList.length}</b> verses in Devanagari with word meanings</li><li><b>${nNotes}</b> footnotes</li><li>Jayaratha’s Viveka in Sanskrit for every verse</li></ul>
      <h2>Contents</h2>
      <ol class="toc-list">${toc}</ol>
      <h2>About this copy</h2>
      <div class="about">
        <p>This is a private study copy of the whole book, read from the page images of the e-book and laid out as text. Every page carries its printed page number in the margin; select it to see the scan of that page, which is the place to check any word.</p>
        <p>The Sanskrit verses are shown from the Kashmir Series of Texts and Studies edition of the Tantrāloka (1918), matched line by line to the book, so each word can be selected for its sandhi split, grammar and meaning. Where a line of Devanagari could not be matched (quotations, and a few readings that differ), it is shown as read from the page, in grey. Below each verse, the Viveka button opens Jayaratha’s commentary in Sanskrit.</p>
        <p>The English was read by machine, so expect occasional misread letters, especially accents on romanised Sanskrit words. Search ignores accents, so <i>siva</i> finds Śiva, and Devanagari searches find romanised words too.</p>
        <p>© Mark S. G. Dyczkowski. Private copy for personal study; not for redistribution.</p>
      </div>
    </div>`;
    $("#finder").addEventListener("submit", (e) => { e.preventDefault(); const v = $("#vno").value.trim(); if (v) location.hash = `#/verse/${encodeURIComponent(v)}`; });
    renderSide(-1);
    window.scrollTo(0, 0);
  }

  /* ------------------------------------------------------------ verses list */
  function versesPage() {
    curSec = -1;
    const cards = verseList.map((v) => {
      const id = verseBlock[v];
      const b = blocks[byId.get(id)];
      const tmp = document.createElement("div"); tmp.innerHTML = b.html;
      const first = (tmp.querySelector(".vl") || tmp).textContent.replace(/\s+/g, " ").trim();
      return `<a class="vcard" href="#/verse/${encodeURIComponent(v)}" data-f="${esc(v + " " + first + " " + Lipi.toIast(first))}"><span class="n">Verse ${esc(v)}</span><span class="t" lang="sa">${esc(first)}</span><span class="p">${esc(label(b.p))}</span></a>`;
    }).join("");
    main.innerHTML = `<div class="page"><h1>Verses</h1><p class="lead">The verses of chapter one in the order of the book, numbered as in the KSTS edition. Select one to read it with its translation and notes.</p>
      <input class="filter" id="vf" placeholder="Filter by number or words, in Devanagari or romanised"><div class="vgrid" id="vg">${cards}</div></div>`;
    const norm = (s) => fold(s);
    $("#vf").addEventListener("input", (e) => {
      const q = norm(Lipi.isDeva(e.target.value) ? Lipi.toIast(e.target.value) : e.target.value);
      $$("#vg .vcard").forEach((c) => { c.hidden = q && !norm(c.dataset.f).includes(q); });
    });
    renderSide(-1);
    window.scrollTo(0, 0);
  }

  /* ------------------------------------------------------------ notes list */
  function notesPage(target) {
    curSec = -1;
    const all = Object.keys(N.html).map(Number).sort((a, b) => a - b);
    main.innerHTML = `<div class="page reader" style="padding-left:28px"><h1>Footnotes</h1><p class="lead" style="text-indent:0">All ${all.length} footnotes of the book. Each number opens the note; ↩ returns to its place in the text.</p>
      <input class="filter" id="nf" placeholder="Filter the footnotes (accents optional)"><div id="nl">${notesHTML(all)}</div></div>`;
    const idx = all.map((n) => [n, fold(String(n) + " " + strip(N.html[n] || ""))]);
    $("#nf").addEventListener("input", (e) => {
      const q = fold(e.target.value.trim());
      idx.forEach(([n, t]) => { const el = document.getElementById("n" + n); if (el) el.hidden = q && !t.includes(q); });
    });
    renderSide(-1);
    if (target) requestAnimationFrame(() => { const el = document.getElementById("n" + target); if (el) { el.scrollIntoView({ block: "center" }); el.classList.add("hl"); } });
    else window.scrollTo(0, 0);
  }

  /* ------------------------------------------------------------ search */
  function fold(s) {
    return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/ı/g, "i");
  }
  function strip(h) { const d = document.createElement("div"); d.innerHTML = h.replace(/<sup class="fn"[^>]*>\d+<\/sup>/g, ""); return d.textContent; }
  // folded text with a map back to the original string
  function foldMap(s) {
    let f = "", map = [];
    for (let i = 0; i < s.length; i++) {
      const c = s[i];
      const fc = c.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
      for (let j = 0; j < fc.length; j++) { f += fc[j]; map.push(i); }
    }
    return { f, map };
  }
  let SIDX = null;
  function buildIndex() {
    const out = [];
    blocks.forEach((b, i) => {
      if (!b.html || b.t === "pg") return;
      let t = strip(b.html).replace(/\s+/g, " ").trim();
      const kind = b.t === "dv" ? "verse" : b.t === "ia" ? "verse" : "text";
      let alt = "";
      if (b.t === "dv") alt = Lipi.toIast(t);
      out.push({ kind, t, alt: fold(alt), f: foldMap(t), sec: blockSec[i], id: b.id, p: b.p, v: b.v });
    });
    Object.keys(N.html).forEach((n) => {
      const t = strip(N.html[n]).replace(/\s+/g, " ").trim();
      out.push({ kind: "note", t, alt: "", f: foldMap(t), n, p: N.page[n] });
    });
    if (window.TL_VIVEKA) {
      Object.entries(TL_VIVEKA).forEach(([u, h]) => {
        const t = strip(h).replace(/\s+/g, " ").trim();
        out.push({ kind: "viveka", t, alt: fold(Lipi.toIast(t)), f: foldMap(t), u });
      });
    }
    return out;
  }
  let searchKind = "all";
  function searchPage(q) {
    curSec = -1;
    $("#q").value = q;
    main.innerHTML = `<div class="page"><h1>Search</h1><p class="lead" id="slead">Searching…</p><div class="chips" id="chips"></div><div id="sres"></div></div>`;
    renderSide(-1);
    loadViveka().catch(() => {}).then(() => {
      if (!SIDX || (window.TL_VIVEKA && !SIDX.some((e) => e.kind === "viveka"))) SIDX = buildIndex();
      runSearch(q);
    });
  }
  function runSearch(q) {
    const raw = q.trim();
    if (!raw) { $("#slead").textContent = "Type a word or phrase in the search box above."; return; }
    const isD = Lipi.isDeva(raw);
    const qf = fold(isD ? Lipi.toIast(raw) : raw).replace(/m̐/g, "m");
    const terms = qf.split(/\s+/).filter(Boolean);
    const qd = isD ? raw.replace(/\s+/g, " ") : null;
    const hits = [];
    for (const e of SIDX) {
      let ok = false, pos = -1;
      let viaD = false;
      if (qd && e.t.includes(qd)) { ok = true; pos = e.t.indexOf(qd); viaD = true; }
      else if (terms.every((t) => e.f.f.includes(t))) { ok = true; pos = e.f.map[e.f.f.indexOf(terms[0])]; }
      else if (e.alt && terms.every((t) => e.alt.includes(t))) { ok = true; pos = -1; }
      if (ok) hits.push({ e, pos, viaD });
    }
    const counts = { all: hits.length, verse: 0, text: 0, note: 0, viveka: 0 };
    hits.forEach((h) => counts[h.e.kind]++);
    const names = { all: "All", verse: "Verses", text: "Main text", note: "Footnotes", viveka: "Viveka (Sanskrit)" };
    $("#chips").innerHTML = Object.keys(names).map((k) => `<button data-kind="${k}" aria-pressed="${searchKind === k}">${names[k]} (${counts[k]})</button>`).join("");
    $$("#chips button").forEach((b) => b.addEventListener("click", () => { searchKind = b.dataset.kind; runSearch(q); }));
    const shown = hits.filter((h) => searchKind === "all" || h.e.kind === searchKind);
    $("#slead").textContent = hits.length ? `${hits.length} places match “${raw}”.` : `Nothing matches “${raw}”. Try fewer words, or the stem of a word (search ignores accents).`;
    const render = (list) => list.map(({ e, pos, viaD }) => {
      let snip;
      if (pos >= 0) {
        const a = Math.max(0, pos - 90), z = Math.min(e.t.length, pos + 170);
        let s = (a ? "… " : "") + e.t.slice(a, z) + (z < e.t.length ? " …" : "");
        snip = highlight(s, terms, viaD ? qd : null);
      } else snip = esc(e.t.slice(0, 240)) + (e.t.length > 240 ? " …" : "");
      let href, k;
      if (e.kind === "note") { href = `#/read/${noteSec[e.n]}/n${e.n}`; k = `<b>Footnote ${esc(nlab(e.n))}</b> · ${esc(label(e.p))}`; }
      else if (e.kind === "viveka") { const vs = (B.unitVerses[e.u] || []); href = vs.length ? `#/verse/${encodeURIComponent(vs[0])}` : "#/verses"; k = `<b>Viveka</b> on ${vs.length ? "verse " + esc(vs.join(", ")) : "the preface"}`; }
      else { href = `#/read/${e.sec}/${e.id}`; k = `<b>${e.kind === "verse" ? "Verse" + (e.v && e.v.length ? " " + esc(e.v[0]) : "") : esc(cleanTitle(secs[e.sec].title))}</b> · ${esc(label(e.p))}`; }
      const sa = e.kind === "viveka" || (e.kind === "verse" && Lipi.isDeva(e.t));
      return `<div class="res"><a class="go" href="${href}"><div class="k">${k}</div><p class="s${sa ? " sa" : ""}">${snip}</p></a></div>`;
    }).join("");
    $("#sres").innerHTML = render(shown.slice(0, 200)) + (shown.length > 200 ? `<button class="btn ghost more" id="moreRes">Show all ${shown.length}</button>` : "");
    const mb = $("#moreRes"); if (mb) mb.addEventListener("click", () => { $("#sres").innerHTML = render(shown); });
  }
  function highlight(s, terms, qd) {
    if (qd) return esc(s).split(esc(qd)).join(`<mark>${esc(qd)}</mark>`);
    const { f, map } = foldMap(s);
    const marks = [];
    terms.forEach((t) => { let i = f.indexOf(t); while (i >= 0 && t) { marks.push([map[i], map[i + t.length - 1] + 1]); i = f.indexOf(t, i + t.length); } });
    marks.sort((a, b) => a[0] - b[0]);
    let o = "", last = 0;
    for (const [a, z] of marks) { if (a < last) continue; o += esc(s.slice(last, a)) + "<mark>" + esc(s.slice(a, z)) + "</mark>"; last = z; }
    return o + esc(s.slice(last));
  }
  $("#searchForm").addEventListener("submit", (e) => { e.preventDefault(); const q = $("#q").value.trim(); if (q) location.hash = `#/search?q=${encodeURIComponent(q)}`; });

  /* ------------------------------------------------------------ router */
  function setTab(t) { $$(".tabs a").forEach((a) => a.toggleAttribute("aria-current", a.dataset.tab === t)); $$(".tabs a").forEach((a) => { if (a.dataset.tab === t) a.setAttribute("aria-current", "page"); }); }
  function route() {
    const h = decodeURIComponent(location.hash.replace(/^#\/?/, ""));
    side.classList.remove("open");
    let m;
    if ((m = h.match(/^read\/(\d+)(?:\/(.+))?$/))) { setTab("read"); showSection(+m[1], m[2]); }
    else if ((m = h.match(/^verse\/(.+)$/))) {
      setTab("read");
      const v = m[1].trim();
      const id = verseBlock[v] || verseBlock[String(parseInt(v))];
      if (id) showSection(blockSec[byId.get(id)], id);
      else { versesPage(); $("#vf").value = v; }
    }
    else if ((m = h.match(/^page\/(\d+)$/))) {
      setTab("read");
      const img = +m[1];
      let k = blocks.findIndex((b) => b.t === "pg" && b.p >= img);
      if (k < 0) k = 0;
      showSection(blockSec[k], `pg${blocks[k].p}`);
    }
    else if ((m = h.match(/^note\/(\d+)$/))) { setTab("notes"); notesPage(m[1]); }
    else if (h === "notes") { setTab("notes"); notesPage(); }
    else if (h === "verses") { setTab("verses"); versesPage(); }
    else if ((m = h.match(/^search\?q=(.*)$/))) { setTab(""); searchPage(m[1]); }
    else { setTab(""); home(); }
    if (!/^read|^verse|^page/.test(h)) main.focus({ preventScroll: true });
  }
  window.addEventListener("hashchange", route);
  route();
})();
