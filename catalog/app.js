/* NTE200 interactive parts catalog — vanilla JS, no dependencies.
   Data comes from window.CATALOG (data/parts.js). Cart persists in localStorage. */
(function () {
  "use strict";
  var DATA = window.CATALOG;
  if (!DATA) { document.body.innerHTML = "<p style='padding:40px'>Не удалось загрузить данные каталога (data/parts.js).</p>"; return; }

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };

  // index sections by code
  var byCode = {};
  DATA.sections.forEach(function (s) { byCode[s.code] = s; });

  /* ---------------- cart ---------------- */
  var CART_KEY = "nte200_cart_v1";
  var cart = load();
  function load() { try { return JSON.parse(localStorage.getItem(CART_KEY)) || {}; } catch (e) { return {}; } }
  function persist() { try { localStorage.setItem(CART_KEY, JSON.stringify(cart)); } catch (e) {} }

  function addToCart(part, sec) {
    var k = part.pn;
    if (cart[k]) { cart[k].qty += 1; }
    else {
      cart[k] = { pn: part.pn, en: part.en, zh: part.zh,
                  sec: sec.code, secName: sec.en, qty: 1 };
    }
    persist(); renderCart(); flashCount();
    toast("Добавлено: " + part.pn);
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
    var html = DATA.chapters.map(function (ch) {
      var secs = byChap[ch.code] || [];
      var items = secs.map(function (s) {
        return '<button class="sec-item" data-code="' + s.code + '">' +
          '<span class="sc">' + esc(s.code) + '</span>' +
          '<span class="cnt">' + s.parts.length + '</span>' +
          '<span class="sn">' + esc(s.zh) + ' · ' + esc(s.en) + '</span></button>';
      }).join("");
      return '<div class="chap" data-chap="' + ch.code + '">' +
        '<button class="chap-h"><span class="caret">&#9656;</span>' +
        '<span class="code">' + esc(ch.code) + '</span>' +
        '<span>' + esc(ch.zh) + '</span>' +
        '<span class="en">' + esc(ch.en) + '</span></button>' +
        '<div class="sec-list">' + items + '</div></div>';
    }).join("");
    nav.innerHTML = html;

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
    if (it) { it.closest(".chap").classList.add("open"); }
  }

  /* ---------------- section view ---------------- */
  function showSection(code) {
    var s = byCode[code];
    if (!s) return;
    $("#welcome").hidden = true;
    $("#searchView").hidden = true;
    var v = $("#sectionView");
    v.hidden = false;
    location.hash = code;
    markActive(code);

    var draws = s.images.map(function (src, i) {
      return '<figure class="drawing" data-src="' + esc(src) + '">' +
        '<img loading="lazy" src="' + esc(src) + '" alt="Чертёж ' + esc(s.code) + '">' +
        '<span class="zoom-ic">&#128269; чертёж ' + (i + 1) + '</span></figure>';
    }).join("");

    var rows = s.parts.length ? s.parts.map(function (p) {
      var name = '<div class="zh">' + esc(p.zh || p.en) + "</div>" +
        (p.en && p.zh ? '<div class="en">' + esc(p.en) + "</div>" : "");
      return '<tr class="lvl' + (p.lvl || 0) + '">' +
        '<td class="c-ref">' + esc(p.ref) + "</td>" +
        '<td class="c-pn"><button data-pn="' + esc(p.pn) + '" title="Добавить в заказ">' + esc(p.pn) + "</button></td>" +
        '<td class="c-name">' + name + "</td>" +
        '<td class="c-qty">' + esc(p.qty) + "</td>" +
        '<td class="c-add"><button class="addbtn" data-pn="' + esc(p.pn) + '" title="Добавить в заказ">&#65291;</button></td>' +
        "</tr>";
    }).join("") : "";

    var table = s.parts.length ?
      '<table class="parts-tbl"><thead><tr>' +
      "<th>№</th><th>Номер детали</th><th>Наименование</th><th>Кол-во</th><th></th>" +
      "</tr></thead><tbody>" + rows + "</tbody></table>" :
      '<div class="no-parts">Для этого раздела в книге приведён только чертёж, без таблицы деталей.</div>';

    v.innerHTML =
      '<div class="sv-head"><span class="sv-code">' + esc(s.code) + "</span>" +
      '<h1 class="sv-title">' + esc(s.zh) + "</h1>" +
      '<span class="sv-chip">' + esc(chapterName(s.chapter)) + "</span></div>" +
      '<div class="sv-sub">' + esc(s.en) + " · " + s.parts.length + " позиций</div>" +
      '<div class="drawings">' + (draws || "") + "</div>" +
      table;

    v.querySelector(".drawings") && v.querySelectorAll(".drawing").forEach(function (f) {
      f.addEventListener("click", function () { openLightbox(f.getAttribute("data-src")); });
    });
    v.addEventListener("click", onPartClick);
    window.scrollTo(0, 0);
  }

  function onPartClick(e) {
    var b = e.target.closest("[data-pn]");
    if (!b) return;
    var pn = b.getAttribute("data-pn");
    var sec = byCode[location.hash.replace("#", "")];
    var part = null;
    if (sec) part = sec.parts.filter(function (p) { return p.pn === pn; })[0];
    if (!part) { // from search view: find anywhere
      DATA.sections.some(function (s) { var f = s.parts.filter(function (p) { return p.pn === pn; })[0];
        if (f) { part = f; sec = s; return true; } return false; });
    }
    if (part && sec) {
      addToCart(part, sec);
      if (b.classList.contains("addbtn")) { b.classList.add("added");
        setTimeout(function () { b.classList.remove("added"); }, 500); }
    }
  }

  function chapterName(code) {
    var c = DATA.chapters.filter(function (x) { return x.code === code; })[0];
    return c ? c.zh + " · " + c.en : code;
  }

  /* ---------------- search ---------------- */
  var searchBox = $("#search");
  var tmr;
  searchBox.addEventListener("input", function () {
    clearTimeout(tmr); tmr = setTimeout(runSearch, 140);
  });
  function runSearch() {
    var q = searchBox.value.trim().toLowerCase();
    var sv = $("#searchView");
    if (q.length < 2) {
      sv.hidden = true;
      if (location.hash && byCode[location.hash.replace("#", "")]) { $("#sectionView").hidden = false; }
      else { $("#welcome").hidden = false; }
      filterSidebar("");
      return;
    }
    filterSidebar(q);
    $("#welcome").hidden = true; $("#sectionView").hidden = true; sv.hidden = false;

    var hits = [];
    DATA.sections.forEach(function (s) {
      s.parts.forEach(function (p) {
        if (p.pn.toLowerCase().indexOf(q) >= 0 ||
            (p.en && p.en.toLowerCase().indexOf(q) >= 0) ||
            (p.zh && p.zh.toLowerCase().indexOf(q) >= 0)) {
          hits.push({ p: p, s: s });
        }
      });
    });
    var secHits = DATA.sections.filter(function (s) {
      return (s.code + " " + s.en + " " + s.zh).toLowerCase().indexOf(q) >= 0;
    });

    var html = "<h2>Результаты поиска: «" + esc(searchBox.value.trim()) + "» — " +
      hits.length + " деталей</h2>";
    if (secHits.length) {
      html += '<div class="res-sec">Разделы</div>';
      html += secHits.slice(0, 12).map(function (s) {
        return '<button class="sec-item" data-code="' + s.code + '" style="max-width:520px">' +
          '<span class="sc">' + esc(s.code) + '</span><span class="cnt">' + s.parts.length + '</span>' +
          '<span class="sn">' + esc(s.zh) + " · " + esc(s.en) + "</span></button>";
      }).join("");
    }
    if (hits.length) {
      html += '<div class="res-sec">Детали</div>';
      html += '<table class="parts-tbl"><thead><tr><th>Номер детали</th><th>Наименование</th>' +
        "<th>Раздел</th><th>Кол-во</th><th></th></tr></thead><tbody>";
      html += hits.slice(0, 400).map(function (h) {
        return "<tr>" +
          '<td class="c-pn"><button data-pn="' + esc(h.p.pn) + '">' + hl(h.p.pn, q) + "</button></td>" +
          '<td class="c-name"><div class="zh">' + hl(h.p.zh || h.p.en, q) + "</div>" +
          (h.p.en && h.p.zh ? '<div class="en">' + hl(h.p.en, q) + "</div>" : "") + "</td>" +
          '<td class="c-qty" style="text-align:left;white-space:nowrap"><a href="#' + h.s.code +
          '" class="jump" data-code="' + h.s.code + '">' + esc(h.s.code) + "</a></td>" +
          '<td class="c-qty">' + esc(h.p.qty) + "</td>" +
          '<td class="c-add"><button class="addbtn" data-pn="' + esc(h.p.pn) + '">&#65291;</button></td></tr>';
      }).join("");
      html += "</tbody></table>";
      if (hits.length > 400) html += "<p class='note'>Показаны первые 400. Уточните запрос.</p>";
    }
    if (!hits.length && !secHits.length) html += "<p class='note'>Ничего не найдено.</p>";
    sv.innerHTML = html;
    sv.addEventListener("click", function (e) {
      var j = e.target.closest(".jump, .sec-item");
      if (j) { e.preventDefault(); showSection(j.getAttribute("data-code")); searchBox.value = ""; runSearch(); return; }
      onPartClick(e);
    });
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
        it.style.display = hit ? "" : "none";
        if (hit) any = true;
      });
      ch.style.display = any ? "" : (q ? "none" : "");
      if (q && any) ch.classList.add("open");
    });
  }

  /* ---------------- cart UI ---------------- */
  function renderCart() {
    var box = $("#cartItems"), empty = $("#cartEmpty");
    var keys = Object.keys(cart);
    $("#cartLines").textContent = cartLines();
    $("#cartQty").textContent = cartQty();
    var badge = $("#cartCount");
    if (cartLines()) { badge.hidden = false; badge.textContent = cartLines(); }
    else badge.hidden = true;

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
        '<button class="rm" data-rm="' + esc(k) + '">Удалить</button>' +
        "</div>";
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

  /* ---------------- export / print ---------------- */
  function orderRows() {
    return Object.keys(cart).map(function (k) { return cart[k]; });
  }
  $("#exportCsv").addEventListener("click", function () {
    var rows = orderRows();
    if (!rows.length) { toast("Корзина пуста"); return; }
    var serial = $("#serial").value.trim(), cust = $("#customer").value.trim();
    var out = [];
    out.push("NTE200 Parts Order");
    out.push("Serial No.," + csv(serial));
    if (cust) out.push("Customer/Note," + csv(cust));
    out.push("Date," + new Date().toISOString().slice(0, 10));
    out.push("");
    out.push("Part No.,Qty,Description (EN),Description (ZH),Section,Section Name");
    rows.forEach(function (c) {
      out.push([csv(c.pn), c.qty, csv(c.en), csv(c.zh), csv(c.sec), csv(c.secName)].join(","));
    });
    download("NTE200_order_" + new Date().toISOString().slice(0, 10) + ".csv",
      "﻿" + out.join("\r\n"), "text/csv");
  });
  function csv(v) { v = String(v == null ? "" : v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
  function download(name, text, mime) {
    var b = new Blob([text], { type: mime + ";charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(b); a.download = name;
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 100);
  }

  $("#printOrder").addEventListener("click", function () {
    var rows = orderRows();
    if (!rows.length) { toast("Корзина пуста"); return; }
    var serial = esc($("#serial").value.trim()), cust = esc($("#customer").value.trim());
    var old = $("#printArea"); if (old) old.remove();
    var d = document.createElement("div");
    d.id = "printArea";
    d.innerHTML =
      "<h1 style='font-size:18px'>NTE200 — Заявка на запчасти / Parts Order</h1>" +
      "<p>Serial No.: <b>" + (serial || "____________") + "</b>" +
      (cust ? " &nbsp; | &nbsp; " + cust : "") +
      " &nbsp; | &nbsp; Дата: " + new Date().toLocaleDateString() + "</p>" +
      "<table border='1' cellspacing='0' cellpadding='5' style='border-collapse:collapse;width:100%;font-size:12px'>" +
      "<thead><tr><th>№</th><th>Part No.</th><th>Qty</th><th>Description</th><th>Section</th></tr></thead><tbody>" +
      rows.map(function (c, i) {
        return "<tr><td>" + (i + 1) + "</td><td>" + esc(c.pn) + "</td><td align='center'>" + c.qty +
          "</td><td>" + esc(c.en || c.zh) + "</td><td>" + esc(c.sec) + "</td></tr>";
      }).join("") +
      "</tbody></table><p style='margin-top:10px;font-size:12px'>Позиций: " + rows.length +
      " &nbsp; Всего шт.: " + cartQty() + "</p>";
    document.body.appendChild(d);
    window.print();
  });

  $("#clearCart").addEventListener("click", function () {
    if (!cartLines()) return;
    if (confirm("Очистить весь заказ?")) { cart = {}; persist(); renderCart(); }
  });

  /* ---------------- lightbox ---------------- */
  var lb = $("#lightbox"), lbImg = $("#lbImg"), lbStage = $("#lbStage");
  var scale = 1, tx = 0, ty = 0, drag = false, sx = 0, sy = 0;
  function applyLb() { lbImg.style.transform = "translate(" + tx + "px," + ty + "px) scale(" + scale + ")"; }
  function openLightbox(src) {
    lbImg.src = src; scale = 1; tx = 0; ty = 0; applyLb(); lb.hidden = false;
  }
  function closeLb() { lb.hidden = true; lbImg.src = ""; }
  $("#lbClose").addEventListener("click", closeLb);
  lb.addEventListener("click", function (e) { if (e.target === lb || e.target === lbStage) closeLb(); });
  lbStage.addEventListener("wheel", function (e) {
    e.preventDefault();
    var f = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    scale = Math.min(8, Math.max(1, scale * f));
    if (scale === 1) { tx = 0; ty = 0; }
    applyLb();
  }, { passive: false });
  lbStage.addEventListener("mousedown", function (e) { drag = true; sx = e.clientX - tx; sy = e.clientY - ty; lbStage.style.cursor = "grabbing"; });
  window.addEventListener("mousemove", function (e) { if (!drag) return; tx = e.clientX - sx; ty = e.clientY - sy; applyLb(); });
  window.addEventListener("mouseup", function () { drag = false; lbStage.style.cursor = "grab"; });
  lbStage.addEventListener("dblclick", function () { scale = scale > 1 ? 1 : 2.5; if (scale === 1) { tx = 0; ty = 0; } applyLb(); });
  // basic touch pinch
  var pts = {}, pd = 0, ps = 1;
  lbStage.addEventListener("touchstart", function (e) {
    for (var i = 0; i < e.changedTouches.length; i++) { var t = e.changedTouches[i]; pts[t.identifier] = t; }
    var ks = Object.keys(pts);
    if (ks.length === 2) { pd = dist(pts[ks[0]], pts[ks[1]]); ps = scale; }
    else if (ks.length === 1) { drag = true; sx = e.touches[0].clientX - tx; sy = e.touches[0].clientY - ty; }
  }, { passive: false });
  lbStage.addEventListener("touchmove", function (e) {
    e.preventDefault();
    for (var i = 0; i < e.changedTouches.length; i++) { var t = e.changedTouches[i]; if (pts[t.identifier]) pts[t.identifier] = t; }
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
  $("#sDraws").textContent = DATA.sections.reduce(function (a, s) { return a + s.images.length; }, 0);
  buildSidebar();
  renderCart();
  var initial = location.hash.replace("#", "");
  if (initial && byCode[initial]) showSection(initial);
})();
