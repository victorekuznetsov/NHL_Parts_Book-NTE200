/* NTE200 interactive parts catalog — vanilla JS, no dependencies.
   Data comes from window.CATALOG (data/parts.js). Cart persists in localStorage.
   Each section holds one or more "figures": a drawing (or drawings) paired with
   exactly the list of positions shown on it. */
(function () {
  "use strict";
  var DATA = window.CATALOG;
  if (!DATA) { document.body.innerHTML = "<p style='padding:40px'>Не удалось загрузить данные каталога (data/parts.js).</p>"; return; }

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };

  var byCode = {};
  DATA.sections.forEach(function (s) { byCode[s.code] = s; });
  function secParts(s) {
    var a = []; (s.figures || []).forEach(function (f) { a.push.apply(a, f.parts); }); return a;
  }
  function secImages(s) {
    var a = []; (s.figures || []).forEach(function (f) { a.push.apply(a, f.images); }); return a;
  }
  function findPart(pn) {
    var res = null;
    DATA.sections.some(function (s) {
      return (s.figures || []).some(function (f) {
        return f.parts.some(function (p) { if (p.pn === pn) { res = { p: p, s: s }; return true; } });
      });
    });
    return res;
  }

  /* ---------------- cart ---------------- */
  var CART_KEY = "nte200_cart_v1";
  var cart = load();
  function load() { try { return JSON.parse(localStorage.getItem(CART_KEY)) || {}; } catch (e) { return {}; } }
  function persist() { try { localStorage.setItem(CART_KEY, JSON.stringify(cart)); } catch (e) {} }

  function addToCart(part, sec, qty) {
    if (!part.pn) return;                       // positions without a catalog number are not orderable
    qty = Math.max(1, Math.floor(qty || 1));
    if (cart[part.pn]) { cart[part.pn].qty += qty; }
    else {
      cart[part.pn] = { pn: part.pn, en: part.en, zh: part.zh,
                        sec: sec.code, secName: sec.en, qty: qty };
    }
    persist(); renderCart(); flashCount();
    toast("В заказ: " + part.pn + " ×" + qty);
  }
  function setQty(pn, q) {
    q = Math.max(0, Math.floor(q || 0));
    if (!cart[pn]) return;
    if (q === 0) delete cart[pn]; else cart[pn].qty = q;
    persist(); renderCart();
  }
  function cartLines() { return Object.keys(cart).length; }
  function cartQty() { return Object.keys(cart).reduce(function (a, k) { return a + cart[k].qty; }, 0); }

  /* ---------------- sidebar ---------------- */
  function buildSidebar() {
    var nav = $("#chapters");
    var byChap = {};
    DATA.sections.forEach(function (s) { (byChap[s.chapter] = byChap[s.chapter] || []).push(s); });
    nav.innerHTML = DATA.chapters.map(function (ch) {
      var items = (byChap[ch.code] || []).map(function (s) {
        return '<button class="sec-item" data-code="' + s.code + '">' +
          '<span class="sc">' + esc(s.code) + '</span>' +
          '<span class="cnt">' + secParts(s).length + '</span>' +
          '<span class="sn">' + esc(s.zh) + ' · ' + esc(s.en) + '</span></button>';
      }).join("");
      return '<div class="chap" data-chap="' + ch.code + '">' +
        '<button class="chap-h"><span class="caret">&#9656;</span>' +
        '<span class="code">' + esc(ch.code) + '</span>' +
        '<span>' + esc(ch.zh) + '</span>' +
        '<span class="en">' + esc(ch.en) + '</span></button>' +
        '<div class="sec-list">' + items + '</div></div>';
    }).join("");
    nav.addEventListener("click", function (e) {
      var h = e.target.closest(".chap-h");
      if (h) { h.parentNode.classList.toggle("open"); return; }
      var it = e.target.closest(".sec-item");
      if (it) { showSection(it.getAttribute("data-code")); closeSidebar(); }
    });
  }
  function markActive(code) {
    $$(".sec-item").forEach(function (b) { b.classList.toggle("active", b.getAttribute("data-code") === code); });
    var it = $('.sec-item[data-code="' + code + '"]');
    if (it) it.closest(".chap").classList.add("open");
  }
  function chapterName(code) {
    var c = DATA.chapters.filter(function (x) { return x.code === code; })[0];
    return c ? c.zh + " · " + c.en : code;
  }

  /* ---------------- parts table ---------------- */
  function partsTable(parts) {
    var rows = parts.map(function (p) {
      var name = '<div class="zh">' + esc(p.zh || p.en) + "</div>" +
        (p.en && p.zh ? '<div class="en">' + esc(p.en) + "</div>" : "");
      var qn = parseInt(p.qty, 10); if (!(qn > 0)) qn = 1;
      if (p.pn) {
        return '<tr class="lvl' + (p.lvl || 0) + '">' +
          '<td class="c-ref">' + esc(p.ref) + "</td>" +
          '<td class="c-pn"><button data-pn="' + esc(p.pn) + '" title="Добавить в заказ">' + esc(p.pn) + "</button></td>" +
          '<td class="c-name">' + name + "</td>" +
          '<td class="c-qty" title="Количество на схеме">' + esc(p.qty) + "</td>" +
          '<td class="c-need"><input class="need" type="number" min="1" value="' + qn + '" data-pn="' + esc(p.pn) + '" title="Требуемое количество" aria-label="Требуемое количество"></td>' +
          '<td class="c-add"><button class="addbtn" data-pn="' + esc(p.pn) + '" title="Добавить в заказ">&#65291;</button></td>' +
          "</tr>";
      }
      // listed position without an orderable catalog number
      return '<tr class="lvl' + (p.lvl || 0) + ' norow">' +
        '<td class="c-ref">' + esc(p.ref) + "</td>" +
        '<td class="c-pn dash">—</td>' +
        '<td class="c-name">' + name + "</td>" +
        '<td class="c-qty">' + esc(p.qty) + "</td>" +
        '<td class="c-need"></td><td class="c-add"></td></tr>';
    }).join("");
    return '<table class="parts-tbl"><thead><tr>' +
      "<th>№</th><th>Номер детали</th><th>Наименование</th>" +
      '<th title="Количество на схеме">Кол-во</th><th>Нужно</th><th></th>' +
      "</tr></thead><tbody>" + rows + "</tbody></table>";
  }

  function drawingsMarkup(images, label) {
    if (!images.length) return "";
    if (images.length === 1) {
      return '<figure class="drawing" data-src="' + esc(images[0]) + '">' +
        '<img loading="lazy" src="' + esc(images[0]) + '" alt="Чертёж">' +
        '<span class="zoom-ic">&#128269;</span></figure>';
    }
    var slides = images.map(function (src, i) {
      return '<figure class="drawing slide' + (i === 0 ? " on" : "") + '" data-src="' + esc(src) + '">' +
        '<img loading="lazy" src="' + esc(src) + '" alt="Чертёж ' + (i + 1) + '">' +
        '<span class="zoom-ic">&#128269;</span></figure>';
    }).join("");
    return '<div class="carousel" data-i="0" data-n="' + images.length + '">' + slides +
      '<button class="cbtn prev" aria-label="Назад">&#8249;</button>' +
      '<button class="cbtn next" aria-label="Вперёд">&#8250;</button>' +
      '<span class="ccount">1 / ' + images.length + "</span></div>";
  }

  /* ---------------- section view ---------------- */
  function showSection(code) {
    var s = byCode[code];
    if (!s) return;
    $("#welcome").hidden = true; $("#searchView").hidden = true;
    var v = $("#sectionView"); v.hidden = false;
    location.hash = code; markActive(code);

    var figs = s.figures || [];
    var multi = figs.length > 1;
    var body = figs.map(function (f, fi) {
      var head = multi ? '<div class="fig-head">Рисунок ' + (fi + 1) + " / " + figs.length +
        ' · позиции ' + posRange(f.parts) + "</div>" : "";
      var draw = f.images.length
        ? '<div class="fig-draw">' + drawingsMarkup(f.images) + "</div>"
        : "";
      var tbl = f.parts.length ? partsTable(f.parts)
        : '<div class="no-parts">Для этого рисунка в книге приведён только чертёж.</div>';
      return '<section class="figure' + (f.images.length ? "" : " nofig") + '">' + head +
        draw + '<div class="fig-parts">' + tbl + "</div></section>";
    }).join("");

    var np = secParts(s).length;
    v.innerHTML =
      '<div class="sv-head"><span class="sv-code">' + esc(s.code) + "</span>" +
      '<h1 class="sv-title">' + esc(s.zh) + "</h1>" +
      '<span class="sv-chip">' + esc(chapterName(s.chapter)) + "</span></div>" +
      '<div class="sv-sub">' + esc(s.en) + " · " + np + " позиций · " +
      figs.length + (figs.length === 1 ? " рисунок" : " рисунк(ов)") + "</div>" + body;

    wireSectionView(v);
    window.scrollTo(0, 0);
  }
  function posRange(parts) {
    var refs = parts.map(function (p) { return parseInt(p.ref, 10); }).filter(function (n) { return n > 0; });
    if (!refs.length) return "—";
    return Math.min.apply(null, refs) + "–" + Math.max.apply(null, refs);
  }

  function wireSectionView(root) {
    $$(".drawing", root).forEach(function (f) {
      f.addEventListener("click", function () { openLightbox(f.getAttribute("data-src")); });
    });
    $$(".carousel", root).forEach(function (c) { initCarousel(c); });
    root.onclick = function (e) { onPartClick(e); };
  }

  function initCarousel(c) {
    var n = +c.getAttribute("data-n");
    function go(delta, e) {
      if (e) { e.stopPropagation(); }
      var i = (+c.getAttribute("data-i") + delta + n) % n;
      c.setAttribute("data-i", i);
      $$(".slide", c).forEach(function (s, k) { s.classList.toggle("on", k === i); });
      $(".ccount", c).textContent = (i + 1) + " / " + n;
    }
    $(".prev", c).addEventListener("click", function (e) { go(-1, e); });
    $(".next", c).addEventListener("click", function (e) { go(1, e); });
  }

  function onPartClick(e) {
    var b = e.target.closest(".addbtn, .c-pn button");
    if (!b) return;
    var pn = b.getAttribute("data-pn");
    var row = b.closest("tr");
    var need = row ? row.querySelector(".need") : null;
    var qty = need ? parseInt(need.value, 10) : 1;
    var hit = findPart(pn);
    if (hit) {
      addToCart(hit.p, hit.s, qty);
      if (b.classList.contains("addbtn")) {
        b.classList.add("added");
        setTimeout(function () { b.classList.remove("added"); }, 500);
      }
    }
  }

  /* ---------------- search ---------------- */
  var searchBox = $("#search"), tmr;
  searchBox.addEventListener("input", function () { clearTimeout(tmr); tmr = setTimeout(runSearch, 140); });
  function runSearch() {
    var q = searchBox.value.trim().toLowerCase();
    var sv = $("#searchView");
    if (q.length < 2) {
      sv.hidden = true; filterSidebar("");
      if (location.hash && byCode[location.hash.replace("#", "")]) $("#sectionView").hidden = false;
      else $("#welcome").hidden = false;
      return;
    }
    filterSidebar(q);
    $("#welcome").hidden = true; $("#sectionView").hidden = true; sv.hidden = false;

    var hits = [];
    DATA.sections.forEach(function (s) {
      secParts(s).forEach(function (p) {
        if ((p.pn && p.pn.toLowerCase().indexOf(q) >= 0) ||
            (p.en && p.en.toLowerCase().indexOf(q) >= 0) ||
            (p.zh && p.zh.toLowerCase().indexOf(q) >= 0)) hits.push({ p: p, s: s });
      });
    });
    var secHits = DATA.sections.filter(function (s) {
      return (s.code + " " + s.en + " " + s.zh).toLowerCase().indexOf(q) >= 0;
    });

    var html = "<h2>Поиск: «" + esc(searchBox.value.trim()) + "» — " + hits.length + " деталей</h2>";
    if (secHits.length) {
      html += '<div class="res-sec">Разделы</div>' + secHits.slice(0, 12).map(function (s) {
        return '<button class="sec-item" data-code="' + s.code + '" style="max-width:560px">' +
          '<span class="sc">' + esc(s.code) + '</span><span class="cnt">' + secParts(s).length + '</span>' +
          '<span class="sn">' + esc(s.zh) + " · " + esc(s.en) + "</span></button>";
      }).join("");
    }
    if (hits.length) {
      html += '<div class="res-sec">Детали</div><table class="parts-tbl"><thead><tr>' +
        "<th>Номер детали</th><th>Наименование</th><th>Раздел</th><th>Кол-во</th><th>Нужно</th><th></th></tr></thead><tbody>";
      html += hits.slice(0, 400).map(function (h) {
        var p = h.p, qn = parseInt(p.qty, 10); if (!(qn > 0)) qn = 1;
        return "<tr>" +
          '<td class="c-pn"><button data-pn="' + esc(p.pn) + '">' + hl(p.pn, q) + "</button></td>" +
          '<td class="c-name"><div class="zh">' + hl(p.zh || p.en, q) + "</div>" +
          (p.en && p.zh ? '<div class="en">' + hl(p.en, q) + "</div>" : "") + "</td>" +
          '<td class="c-jump"><a href="#' + h.s.code + '" class="jump" data-code="' + h.s.code + '">' + esc(h.s.code) + "</a></td>" +
          '<td class="c-qty">' + esc(p.qty) + "</td>" +
          '<td class="c-need"><input class="need" type="number" min="1" value="' + qn + '" data-pn="' + esc(p.pn) + '"></td>' +
          '<td class="c-add"><button class="addbtn" data-pn="' + esc(p.pn) + '">&#65291;</button></td></tr>';
      }).join("");
      html += "</tbody></table>";
      if (hits.length > 400) html += "<p class='note'>Показаны первые 400 — уточните запрос.</p>";
    }
    if (!hits.length && !secHits.length) html += "<p class='note'>Ничего не найдено.</p>";
    sv.innerHTML = html;
    sv.onclick = function (e) {
      var j = e.target.closest(".jump, .sec-item");
      if (j) { e.preventDefault(); showSection(j.getAttribute("data-code")); searchBox.value = ""; runSearch(); return; }
      onPartClick(e);
    };
  }
  function hl(txt, q) {
    txt = String(txt || ""); var i = txt.toLowerCase().indexOf(q);
    if (i < 0) return esc(txt);
    return esc(txt.slice(0, i)) + "<mark>" + esc(txt.slice(i, i + q.length)) + "</mark>" + esc(txt.slice(i + q.length));
  }
  function filterSidebar(q) {
    $$(".chap").forEach(function (ch) {
      var any = false;
      $$(".sec-item", ch).forEach(function (it) {
        var hit = !q || it.textContent.toLowerCase().indexOf(q) >= 0;
        it.style.display = hit ? "" : "none"; if (hit) any = true;
      });
      ch.style.display = any ? "" : (q ? "none" : "");
      if (q && any) ch.classList.add("open");
    });
  }

  /* ---------------- cart UI ---------------- */
  function renderCart() {
    var box = $("#cartItems"), empty = $("#cartEmpty"), keys = Object.keys(cart);
    $("#cartLines").textContent = cartLines();
    $("#cartQty").textContent = cartQty();
    var badge = $("#cartCount");
    if (cartLines()) { badge.hidden = false; badge.textContent = cartLines(); } else badge.hidden = true;
    if (!keys.length) { box.innerHTML = ""; box.style.display = "none"; empty.style.display = "flex"; return; }
    box.style.display = "block"; empty.style.display = "none";
    box.innerHTML = keys.map(function (k) {
      var c = cart[k];
      return '<div class="citem">' +
        '<div class="cn">' + esc(c.pn) + "</div>" +
        '<div class="qty"><button data-dec="' + esc(k) + '">&minus;</button>' +
        '<input type="number" min="0" value="' + c.qty + '" data-q="' + esc(k) + '">' +
        '<button data-inc="' + esc(k) + '">&#65291;</button></div>' +
        '<div class="cd">' + esc(c.en || c.zh) + "</div>" +
        '<div class="cs">' + esc(c.sec) + " · " + esc(c.secName || "") + "</div>" +
        '<button class="rm" data-rm="' + esc(k) + '">Удалить</button></div>';
    }).join("");
  }
  $("#cartItems").addEventListener("click", function (e) {
    var t = e.target;
    if (t.dataset.inc) setQty(t.dataset.inc, cart[t.dataset.inc].qty + 1);
    else if (t.dataset.dec) setQty(t.dataset.dec, cart[t.dataset.dec].qty - 1);
    else if (t.dataset.rm) setQty(t.dataset.rm, 0);
  });
  $("#cartItems").addEventListener("change", function (e) {
    if (e.target.dataset.q) setQty(e.target.dataset.q, parseInt(e.target.value, 10));
  });

  /* ---------------- exports ---------------- */
  function orderRows() { return Object.keys(cart).map(function (k) { return cart[k]; }); }
  function csv(v) { v = String(v == null ? "" : v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
  function download(name, text, mime) {
    var b = new Blob([text], { type: mime + ";charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(b); a.download = name;
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 100);
  }
  $("#exportCsv").addEventListener("click", function () {
    var rows = orderRows(); if (!rows.length) { toast("Корзина пуста"); return; }
    var serial = $("#serial").value.trim(), cust = $("#customer").value.trim();
    var out = ["NTE200 Parts Order", "Serial No.," + csv(serial)];
    if (cust) out.push("Customer/Note," + csv(cust));
    out.push("Date," + new Date().toISOString().slice(0, 10), "");
    out.push("Part No.,Qty,Description (EN),Description (ZH),Section,Section Name");
    rows.forEach(function (c) { out.push([csv(c.pn), c.qty, csv(c.en), csv(c.zh), csv(c.sec), csv(c.secName)].join(",")); });
    download("NTE200_order_" + new Date().toISOString().slice(0, 10) + ".csv", "﻿" + out.join("\r\n"), "text/csv");
  });
  $("#printOrder").addEventListener("click", function () {
    var rows = orderRows(); if (!rows.length) { toast("Корзина пуста"); return; }
    var serial = esc($("#serial").value.trim()), cust = esc($("#customer").value.trim());
    var old = $("#printArea"); if (old) old.remove();
    var d = document.createElement("div"); d.id = "printArea";
    d.innerHTML = "<h1 style='font-size:18px'>NTE200 — Заявка на запчасти / Parts Order</h1>" +
      "<p>Serial No.: <b>" + (serial || "____________") + "</b>" + (cust ? " | " + cust : "") +
      " | Дата: " + new Date().toLocaleDateString() + "</p>" +
      "<table border='1' cellspacing='0' cellpadding='5' style='border-collapse:collapse;width:100%;font-size:12px'>" +
      "<thead><tr><th>№</th><th>Part No.</th><th>Qty</th><th>Description</th><th>Section</th></tr></thead><tbody>" +
      rows.map(function (c, i) {
        return "<tr><td>" + (i + 1) + "</td><td>" + esc(c.pn) + "</td><td align='center'>" + c.qty +
          "</td><td>" + esc(c.en || c.zh) + "</td><td>" + esc(c.sec) + "</td></tr>";
      }).join("") + "</tbody></table><p style='margin-top:10px;font-size:12px'>Позиций: " + rows.length +
      " Всего шт.: " + cartQty() + "</p>";
    document.body.appendChild(d); window.print();
  });
  function exportAllNumbers() {
    var uniq = {};
    DATA.sections.forEach(function (s) {
      var src = s.chapter === "600" ? "GE" : "NTE200";
      secParts(s).forEach(function (p) {
        if (!p.pn) return;
        var u = uniq[p.pn] || (uniq[p.pn] = { pn: p.pn, en: p.en, zh: p.zh, secs: {}, src: {} });
        u.secs[s.code] = 1; u.src[src] = 1;
        if (!u.en && p.en) u.en = p.en;
        if (!u.zh && p.zh) u.zh = p.zh;
      });
    });
    var keys = Object.keys(uniq).sort();
    var out = ["Part No.,Description (EN),Description (ZH),Source,Sections"];
    keys.forEach(function (k) {
      var u = uniq[k];
      out.push([csv(u.pn), csv(u.en), csv(u.zh), Object.keys(u.src).sort().join("/"),
        csv(Object.keys(u.secs).sort().join(" "))].join(","));
    });
    download("NTE200_all_part_numbers.csv", "﻿" + out.join("\r\n"), "text/csv");
    toast("Экспортировано номеров: " + keys.length);
  }
  $("#exportAll").addEventListener("click", exportAllNumbers);
  $("#exportAll2").addEventListener("click", exportAllNumbers);
  $("#clearCart").addEventListener("click", function () {
    if (cartLines() && confirm("Очистить весь заказ?")) { cart = {}; persist(); renderCart(); }
  });

  /* ---------------- lightbox ---------------- */
  var lb = $("#lightbox"), lbImg = $("#lbImg"), lbStage = $("#lbStage");
  var scale = 1, tx = 0, ty = 0, drag = false, sx = 0, sy = 0;
  function applyLb() { lbImg.style.transform = "translate(" + tx + "px," + ty + "px) scale(" + scale + ")"; }
  function openLightbox(src) { lbImg.src = src; scale = 1; tx = 0; ty = 0; applyLb(); lb.hidden = false; }
  function closeLb() { lb.hidden = true; lbImg.src = ""; }
  $("#lbClose").addEventListener("click", closeLb);
  lb.addEventListener("click", function (e) { if (e.target === lb || e.target === lbStage) closeLb(); });
  lbStage.addEventListener("wheel", function (e) {
    e.preventDefault(); scale = Math.min(8, Math.max(1, scale * (e.deltaY < 0 ? 1.15 : 1 / 1.15)));
    if (scale === 1) { tx = 0; ty = 0; } applyLb();
  }, { passive: false });
  lbStage.addEventListener("mousedown", function (e) { drag = true; sx = e.clientX - tx; sy = e.clientY - ty; lbStage.style.cursor = "grabbing"; });
  window.addEventListener("mousemove", function (e) { if (!drag) return; tx = e.clientX - sx; ty = e.clientY - sy; applyLb(); });
  window.addEventListener("mouseup", function () { drag = false; lbStage.style.cursor = "grab"; });
  lbStage.addEventListener("dblclick", function () { scale = scale > 1 ? 1 : 2.5; if (scale === 1) { tx = 0; ty = 0; } applyLb(); });
  var pts = {}, pd = 0, ps = 1;
  lbStage.addEventListener("touchstart", function (e) {
    for (var i = 0; i < e.changedTouches.length; i++) pts[e.changedTouches[i].identifier] = e.changedTouches[i];
    var ks = Object.keys(pts);
    if (ks.length === 2) { pd = dist(pts[ks[0]], pts[ks[1]]); ps = scale; }
    else if (ks.length === 1) { drag = true; sx = e.touches[0].clientX - tx; sy = e.touches[0].clientY - ty; }
  }, { passive: false });
  lbStage.addEventListener("touchmove", function (e) {
    e.preventDefault();
    for (var i = 0; i < e.changedTouches.length; i++) if (pts[e.changedTouches[i].identifier]) pts[e.changedTouches[i].identifier] = e.changedTouches[i];
    var ks = Object.keys(pts);
    if (ks.length === 2) { scale = Math.min(8, Math.max(1, ps * dist(pts[ks[0]], pts[ks[1]]) / pd)); applyLb(); }
    else if (ks.length === 1 && drag && scale > 1) { tx = e.touches[0].clientX - sx; ty = e.touches[0].clientY - sy; applyLb(); }
  }, { passive: false });
  lbStage.addEventListener("touchend", function (e) {
    for (var i = 0; i < e.changedTouches.length; i++) delete pts[e.changedTouches[i].identifier];
    if (!Object.keys(pts).length) drag = false;
  });
  function dist(a, b) { return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY); }
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { closeLb(); closeCart(); } });

  /* ---------------- drawers ---------------- */
  var cartEl = $("#cart"), cartScrim = $("#cartScrim");
  function openCart() { cartEl.classList.add("open"); cartScrim.classList.add("show"); }
  function closeCart() { cartEl.classList.remove("open"); cartScrim.classList.remove("show"); }
  $("#cartBtn").addEventListener("click", openCart);
  $("#cartClose").addEventListener("click", closeCart);
  cartScrim.addEventListener("click", closeCart);
  var sb = $("#sidebar"), scrim = $("#scrim");
  function openSidebar() { sb.classList.add("open"); scrim.classList.add("show"); }
  function closeSidebar() { sb.classList.remove("open"); scrim.classList.remove("show"); }
  $("#menuBtn").addEventListener("click", openSidebar);
  scrim.addEventListener("click", closeSidebar);

  /* ---------------- misc ---------------- */
  var toastEl;
  function toast(msg) {
    if (!toastEl) { toastEl = document.createElement("div"); toastEl.className = "toast"; document.body.appendChild(toastEl); }
    toastEl.textContent = msg; toastEl.classList.add("show");
    clearTimeout(toastEl._t); toastEl._t = setTimeout(function () { toastEl.classList.remove("show"); }, 1400);
  }
  function flashCount() {
    var b = $("#cartCount"); b.style.transform = "scale(1.4)";
    setTimeout(function () { b.style.transform = ""; }, 160);
  }

  /* ---------------- init ---------------- */
  $("#sSections").textContent = DATA.stats.sections;
  $("#sParts").textContent = DATA.stats.parts;
  $("#sDraws").textContent = DATA.sections.reduce(function (a, s) { return a + secImages(s).length; }, 0);
  buildSidebar();
  renderCart();
  var initial = location.hash.replace("#", "");
  if (initial && byCode[initial]) showSection(initial);
})();
