/* 「不可加入」的原因气泡（照原型 Main.dc.html 的 cxTipOpen / placeTip / tipView）：
 * 只有鼠标停在「不可加入」标签上（或键盘聚焦标签）才开；扫过整行不弹，
 * 否则冲突行多时会一个接一个地冒，反而看不清。Esc 或移开收起。
 * 气泡挂在 body 下、position: fixed，不被列表滚动容器裁掉；下面放不下就翻到行上方。 */
function tipHtml(model) {
  const rows = model.rows.map((r) => "<dt>" + esc(r.label) + "</dt><dd><b>" + esc(r.name) + "</b>　" + esc(r.span) + "</dd>").join("");
  const cuts = model.cuts.map((c) => '<i style="left:' + c.left + '%"></i>').join("");
  const days = model.days.map((d) => "<span>" + esc(d.text) + "</span>").join("");
  return '<i class="tipb-ar"></i><p class="tipb-t">和已报名的活动时间重叠</p><dl class="tipb-r">' + rows + "</dl>" +
    '<div class="tl" role="img" aria-label="' + esc(model.aria) + '"><div class="tl-track">' + cuts +
    '<span class="tl-ov" style="left:' + model.ovL + "%;width:" + model.ovW + '%"></span>' +
    '<span class="tl-bar bar-a" style="left:' + model.aL + "%;width:" + model.aW + '%"></span>' +
    '<span class="tl-bar bar-b" style="left:' + model.bL + "%;width:" + model.bW + '%"></span></div>' +
    '<div class="tl-d' + (model.sparse ? " is-sparse" : "") + '">' + days + "</div>" +
    '<div class="tl-k"><span class="k-a">已报名</span><span class="k-b">这一场</span><span class="k-o">重叠</span></div></div>' +
    '<p class="tipb-s">' + esc(model.way) +
    (model.hasGo ? ' <button id="cx-tip-go" class="ph-link" type="button" data-act="cx-go">去已报名那场</button>' : "") + "</p>";
}

/* 当前气泡对应的（这一场, 已报名那场）；两场已不再冲突就是 null，气泡随之收起 */
function tipPair() {
  const item = S.tip.id ? findItem(S.tip.id) : null;
  const sg = item ? clashOf(item, armedTaskByActivity(item.id)) : null;
  return sg ? { item: item, sg: sg } : null;
}

function tipOpen(id) {
  clearTimeout(S.tip.timer);
  clearTimeout(S.tip.openTimer);
  if (S.tip.id === String(id)) return;
  S.tip.id = String(id);
  paintTip();
}

/* 指针只是扫过标签时不立刻弹：停住一会儿才开，避免沿列表往下滑时一路冒泡 */
function tipSoon(id) {
  clearTimeout(S.tip.openTimer);
  /* 已为这一场开着：指针只是从标签文字挪到它的图标上（先 mouseout 设了关闭计时），要把关闭计时取消 */
  if (S.tip.id === String(id)) { clearTimeout(S.tip.timer); return; }
  S.tip.openTimer = setTimeout(() => tipOpen(id), 140);
}

function tipClose() {
  clearTimeout(S.tip.timer);
  clearTimeout(S.tip.openTimer);
  if (!S.tip.id) return;
  S.tip.id = "";
  paintTip();
}

/* 移开后稍等一下再收：鼠标从行移到气泡上不能闪一下 */
function tipLater() {
  clearTimeout(S.tip.timer);
  clearTimeout(S.tip.openTimer);   // 气泡还没开时，待开的计时也要取消，否则移开后它照样弹出来
  if (!S.tip.id) return;
  S.tip.timer = setTimeout(tipClose, 160);
}

function tipStay() { clearTimeout(S.tip.timer); }

function paintTip() {
  const box = $("#cx-tip");
  if (!box) return;
  const pair = tipPair();
  if (!pair) {
    S.tip.id = "";
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  box.innerHTML = tipHtml(conflictTipModel(pair.item, pair.sg));
  box.hidden = false;
  box.classList.remove("up");
  box.style.visibility = "hidden";
  placeTip();
}

/* 优先放在行下方，下面放不下且上面放得下就翻到上方；箭头对准「不可加入」标签 */
function placeTip() {
  const box = $("#cx-tip");
  const row = S.tip.id ? S.rowEls.get(String(S.tip.id)) : null;
  if (!box || !row || !row.row) return;
  const rr = row.row.getBoundingClientRect();
  const stateEl = row.state || row.row;
  const cr = stateEl.getBoundingClientRect();
  const tag = row.row.querySelector(".state-clash");
  const tr = (tag || row.row).getBoundingClientRect();
  const bh = box.offsetHeight;
  const bw = box.offsetWidth;
  const vh = window.innerHeight;
  const vw = window.innerWidth;
  const up = rr.bottom + bh + 10 > vh - 8 && rr.top - bh - 10 > 8;
  const top = Math.round(up ? rr.top - bh - 8 : rr.bottom + 8);
  const left = Math.round(Math.max(8, Math.min(cr.right - bw, vw - bw - 8)));
  const ax = Math.round(Math.max(16, Math.min(bw - 16, tr.left + tr.width / 2 - left)));
  box.classList.toggle("up", up);
  box.style.top = top + "px";
  box.style.left = left + "px";
  const arrow = box.querySelector(".tipb-ar");
  if (arrow) arrow.style.left = ax + "px";
  box.style.visibility = "visible";
  box.dataset.placed = up ? "up" : "down";
}

/* 「去已报名那场」：滚到那一行并短暂高亮；列表被筛选藏起来时先放开筛选（排序保持不变） */
function tipGoSigned() {
  const pair = tipPair();
  if (!pair) { tipClose(); return; }
  const id = String(pair.sg.id);
  tipClose();
  if (!filtered().some((it) => String(it.id) === id)) {
    S.filter = Object.assign({}, S.filter, { q: "", status: "all", time: "all", checkin: "all", checkout: "all" });
    $("#q").value = "";
    $("#time").value = "all";
    $("#checkin").value = "all";
    $("#checkout").value = "all";
    paintChips();
    savePrefs({ filter: Object.assign({}, S.filter) });
  }
  S.flashId = id;
  render();
  const row = S.rowEls.get(id);
  if (row && row.row && row.row.scrollIntoView) row.row.scrollIntoView({ block: "center", behavior: "smooth" });
  clearTimeout(S.tip.flashTimer);
  S.tip.flashTimer = setTimeout(() => {
    S.flashId = "";
    const el = S.rowEls.get(id);
    if (el && el.row) el.row.classList.remove("is-flash");
  }, 2000);
}

/* 标签上的键盘：Esc 收起；Enter / 空格把焦点移进气泡里的链接（气泡在 DOM 末尾，Tab 到不了） */
function tipKey(event) {
  const key = event.key;
  if (key === "Escape") {
    event.preventDefault();
    event.stopPropagation();
    tipClose();
    return true;
  }
  if (key === "Enter" || key === " " || key === "Spacebar") {
    const go = $("#cx-tip-go");
    if (go) { event.preventDefault(); go.focus(); }
    return true;
  }
  return false;
}
