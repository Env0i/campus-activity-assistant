"use strict";

/* 手机页 DOM 层——活动列表、原因面板与整页搜索（依赖 model*.js、ui-session.js、ui-status.js 先加载）：
 * 负责列表分区常量、行与冲突原因面板构造、跳转已报名行、列表重画与搜索开合。 */

/* G05 列表行（原型 .row 三列：勾选框 / 时刻大字 / 主体，Phone.dc.html:288/738-762）：
 * 数值全部来自 PhoneModel.rowView，这里只建元素、只写 textContent */
function buildRow(box, row) {
  const label = document.createElement("label");
  label.className = "row" + (row.cls ? " " + row.cls : "")
    + (model.flashId === row.id ? " flash" : "");
  label.dataset.id = row.id;
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = row.selected;
  input.disabled = row.disabled;
  input.setAttribute("aria-label", row.aria);
  input.addEventListener("change", () => {
    /* LD04（原型 toggle，Phone:696-702）：撞上已选场就保留原选择并给提示条 */
    const res = PhoneModel.pickItem(model.selected, model.items, row.id, input.checked);
    model.selected = res.selected;
    model.notice = res.notice;
    renderItems();
  });
  const time = document.createElement("span");
  time.className = "time";
  const big = document.createElement("b");
  if (row.timeCls) big.className = row.timeCls;
  big.textContent = row.time;
  time.appendChild(big);
  if (row.hasLeft) {
    const small = document.createElement("small");
    if (row.leftCls) small.className = row.leftCls;
    small.textContent = row.left;
    time.appendChild(small);
  }
  const main = document.createElement("span");
  main.className = "main";
  const name = document.createElement("span");
  name.className = "name";
  name.textContent = row.name;
  main.appendChild(name);
  const sub = document.createElement("span");
  sub.className = "sub";
  row.flags.forEach((f) => {
    const flag = document.createElement("span");
    flag.className = "flag" + (f.cls ? " " + f.cls : "");
    flag.textContent = f.text;
    sub.appendChild(flag);
  });
  if (row.clash) {
    /* 冲突与取消（20261107-conflict-cancel 在途块保留）：不可加入标签，点行展开原因 */
    const flag = document.createElement("span");
    flag.className = "flag clash";
    flag.textContent = "不可加入";
    sub.appendChild(flag);
  }
  if (row.act) {
    const act = document.createElement("span");
    act.textContent = row.act;
    sub.appendChild(act);
  }
  if (row.hasRf) {
    const rf = document.createElement("span");
    rf.className = row.rfNo ? "rf no" : "rf";
    rf.textContent = row.rf;
    sub.appendChild(rf);
  }
  if (row.hasPlace) {
    const place = document.createElement("span");
    place.textContent = row.place;
    sub.appendChild(place);
  }
  if (row.rw && row.rw.text) {
    /* 奖励排在这一行末尾，与原型 .sub 里 rw 的位置一致 */
    const rw = document.createElement("span");
    rw.className = row.rw.cls;
    rw.textContent = row.rw.text;
    sub.appendChild(rw);
  }
  main.appendChild(sub);
  if (row.hasWarn) {
    const warn = document.createElement("span");
    warn.className = "w";
    warn.textContent = row.warn;
    main.appendChild(warn);
  }
  if (row.note) {
    const note = document.createElement("span");
    note.className = "cx-n";
    note.textContent = row.note;
    main.appendChild(note);
  }
  label.appendChild(input);
  label.appendChild(time);
  label.appendChild(main);
  /* 重叠行：点按这一行展开 / 收起原因，一次只开一条（面板在行内占满整行宽） */
  if (row.clash) {
    label.addEventListener("click", (event) => {
      if (event && event.preventDefault) event.preventDefault();
      PhoneModel.toggleWhy(model, row.id);
      renderItems();
    });
    if (model.whyId === row.id) {
      label.appendChild(buildWhy(row.item, row.signedItem, PhoneModel.businessNowS(model)));
    }
  }
  box.appendChild(label);
}

/* 原因面板：内容与电脑端气泡一致；手机上只有「去已报名那场」，没有取消按钮 */
function buildWhy(item, signedItem, nowS) {
  const view = PhoneModel.whyView(item, signedItem, nowS);
  const why = document.createElement("div");
  why.className = "why";
  why.setAttribute("role", "group");
  why.setAttribute("aria-label", view.title);
  const title = document.createElement("b");
  title.className = "why-t";
  title.textContent = view.title;
  why.appendChild(title);
  const rows = document.createElement("dl");
  rows.className = "why-r";
  view.rows.forEach((r) => {
    const dt = document.createElement("dt");
    dt.textContent = r.label;
    const dd = document.createElement("dd");
    const b = document.createElement("b");
    b.textContent = r.name;
    const sp = document.createElement("span");
    sp.textContent = "\u3000" + r.span;
    dd.appendChild(b);
    dd.appendChild(sp);
    /* 一对 dt/dd 包一层 div 横排：手机页样式不用多列网格（test_mobile_layout_statics 钉着单栏） */
    const pair = document.createElement("div");
    pair.className = "why-row";
    pair.appendChild(dt);
    pair.appendChild(dd);
    rows.appendChild(pair);
  });
  why.appendChild(rows);
  const tl = document.createElement("div");
  tl.className = "tl";
  tl.setAttribute("role", "img");
  tl.setAttribute("aria-label", view.aria);
  const track = document.createElement("div");
  track.className = "tl-track";
  view.cuts.forEach((left) => {
    const cut = document.createElement("i");
    cut.style.left = left + "%";
    track.appendChild(cut);
  });
  [["tl-ov", view.ovL, view.ovW], ["tl-bar bar-a", view.aL, view.aW], ["tl-bar bar-b", view.bL, view.bW]].forEach((bar) => {
    const el = document.createElement("span");
    el.className = bar[0];
    el.style.left = bar[1] + "%";
    el.style.width = bar[2] + "%";
    track.appendChild(el);
  });
  tl.appendChild(track);
  const days = document.createElement("div");
  days.className = "tl-d";
  view.days.forEach((text) => {
    const d = document.createElement("span");
    d.textContent = text;
    days.appendChild(d);
  });
  tl.appendChild(days);
  const key = document.createElement("div");
  key.className = "tl-k";
  [["k-a", "已报名"], ["k-b", "这一场"], ["k-o", "重叠"]].forEach((k) => {
    const s = document.createElement("span");
    s.className = k[0];
    s.textContent = k[1];
    key.appendChild(s);
  });
  tl.appendChild(key);
  why.appendChild(tl);
  const way = document.createElement("p");
  way.className = "why-s";
  way.textContent = view.way;
  if (view.hasGo) {
    const go = document.createElement("button");
    go.type = "button";
    go.className = "why-go";
    go.textContent = "去已报名那场";
    /* 原型 whyOf 的 go（Phone.dc.html:481）：stopPropagation 免得行点按又把原因收起 */
    go.addEventListener("click", (event) => {
      if (event && event.stopPropagation) event.stopPropagation();
      goSigned(signedItem.id);
    });
    way.appendChild(go);
  }
  why.appendChild(way);
  return why;
}

/* 「去已报名那场」：收起原因，放开可能藏住它的筛选，滚到那一行。
 * UI-F1 后已报名行在主列表里；结果态的汇总折叠区（若开着）顺带展开，不作为主入口 */
function goSigned(id) {
  model.whyId = "";
  const clockNow = PhoneModel.businessNowS(model);
  // 时钟不可用时只传 clockNow=null，不拿手机墙钟充当筛选日历日
  const shown = PhoneModel.visibleItems(model.items, model.filter, clockNow).some((it) => it.id === id);
  if (!shown) {
    model.filter = { q: "", status: "all", time: "all" };
    if ($("q")) $("q").value = "";
    if ($("search-q")) $("search-q").value = "";
    document.querySelectorAll("[data-status]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.status === "all" ? "true" : "false"));
    document.querySelectorAll("[data-time]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.time === "all" ? "true" : "false"));
  }
  if ($("signed-summary")) $("signed-summary").open = true;
  model.flashId = id;
  renderItems();
  const row = document.querySelector('[data-id="' + String(id).replace(/(["\\])/g, "\\$1") + '"]');
  if (row && row.scrollIntoView) row.scrollIntoView({ block: "center", behavior: "smooth" });
  setTimeout(() => { model.flashId = ""; if (row && row.classList) row.classList.remove("flash"); }, 2000);
}

/* G07 分组渲染：组条、「现在」分隔行与行全部由 PhoneModel.listView 聚合生成，这里只建 DOM。
 * UI-F1（G07，原型 Phone.dc.html:285-289）：已报名/已截止是列表内的普通组
 * （组条+旗标+计数连排），照原型进主列表；details#signed-summary 按用户决策 2
 * 只留作结果态的「已报名汇总」入口——草稿态主列表已直接展示这些行，折叠区收起不重复 */
const TODAY_ZONE_TITLES = ["正在开放", "今天"];
const LIST_ZONES = [
  ["items", TODAY_ZONE_TITLES],
  ["upcoming-items", ["明天", "后天", "待公布", "更晚开放", "已报名", "已截止"]],
  ["signed-items", []],
];

/* 时钟未校准时的绝对日期组归入下方列表区，按开放日期升序展示且不丢行 */
function inListZone(zone, title) {
  if (zone[1].indexOf(title) >= 0) return true;
  return zone[0] === "upcoming-items" && TODAY_ZONE_TITLES.indexOf(title) < 0;
}

function renderItems() {
  model.nowMs = Date.now();
  const nowS = PhoneModel.businessNowS(model);
  /* RS01：结果态供任务卡/底栏/列表开合共用；termsOk 传给行禁用（TM01） */
  const result = PhoneModel.resultView(model.plan, model.busy);
  const view = PhoneModel.listView(model.items, model.filter, {
    nowS: nowS, selected: model.selected, busy: model.busy, termsOk: model.termsOk,
  });
  const zoneCount = [0, 0, 0];
  LIST_ZONES.forEach((zone, zi) => {
    const box = $(zone[0]);
    if (!box) return;
    box.textContent = "";
    view.groups.forEach((group) => {
      if (!inListZone(zone, group.title)) return;
      zoneCount[zi] += group.n;
      /* 「现在 {HH:MM}」分隔行（原型 nowline/nowchip，Phone.dc.html:93-97/286） */
      if (group.nowBefore && group.now) {
        const line = document.createElement("div");
        line.className = "nowline";
        const chip = document.createElement("span");
        chip.className = "nowchip";
        const label = document.createElement("span");
        label.textContent = "现在 ";
        const clock = document.createElement("b");
        clock.textContent = group.now;
        chip.appendChild(label);
        chip.appendChild(clock);
        line.appendChild(chip);
        box.appendChild(line);
      }
      /* 组条（原型 .grp，Phone:287）：组名 + 组注 + 计数 */
      const bar = document.createElement("div");
      bar.className = "grp" + (group.cls ? " " + group.cls : "");
      const title = document.createElement("b");
      title.textContent = group.title;
      const note = document.createElement("span");
      note.textContent = group.note;
      const ct = document.createElement("span");
      ct.className = "ct";
      ct.textContent = group.n + " 场";
      bar.appendChild(title);
      bar.appendChild(note);
      bar.appendChild(ct);
      box.appendChild(bar);
      group.rows.forEach((row) => buildRow(box, row));
    });
  });
  /* G08 段钮计数（原型 segs 的 <small>N</small>，Phone:931）：对全部活动按开放状态聚合 */
  $("seg-free").textContent = String(view.counts.free);
  $("seg-signed").textContent = String(view.counts.signed);
  $("seg-all").textContent = String(view.counts.all);
  const signedCount = (model.items || []).filter((i) => i.signed).length;
  if ($("signed-count")) $("signed-count").textContent = String(signedCount);
  /* G09 空态三分：筛选后（含按段钮）一行都没有走原型那句（Phone:290，tip 居中），
     并收起两个空区盒；有结果但该区没行时保留原有两句区提示，与这句分开 */
  const noMatch = view.total === 0;
  /* RW01 列表显隐（原型 showList/canToggleList，Phone.dc.html:930）：运行与结果两态默认
     收起（RS01 接通 result），pending 与草稿照常显示；#btn-toggle-list 开合（aria-expanded 随动） */
  const pendingNow = !!(model.pending && !model.pending.done);
  const showList = model.listOpen || (!model.busy && !pendingNow);
  $("fbar").hidden = !showList;
  $("search-view").hidden = !showList || !model.searchOpen;
  const toggle = $("btn-toggle-list");
  toggle.hidden = !(model.busy || result);
  toggle.setAttribute("aria-expanded", model.listOpen ? "true" : "false");
  toggle.textContent = model.listOpen ? "收起活动列表" : "查看活动列表";
  const tip = $("filter-empty");
  tip.textContent = "没有符合筛选的活动。";
  tip.hidden = !showList || !noMatch;
  $("today-items").hidden = !showList || noMatch;
  if ($("upcoming-zone")) $("upcoming-zone").hidden = !showList || noMatch;
  /* UI-F1/R-P3-7（用户决策 2）：details#signed-summary 只在结果态作「已报名汇总」
     入口；行集不过段钮过滤，与「已报名 N 场」计数同一口径（都是已报名行总数），
     修掉「折叠区有数无行」——草稿态主列表已展示这些行，整块收起不与列表重复 */
  if ($("signed-summary")) {
    $("signed-summary").hidden = !showList || !result;
    if (result) {
      const sumBox = $("signed-items");
      sumBox.textContent = "";
      (model.items || []).filter((i) => i && i.signed).forEach((item) => {
        buildRow(sumBox, PhoneModel.rowView(item, {
          items: model.items, nowS: nowS, selected: [], busy: model.busy,
          nextPreId: "", termsOk: model.termsOk }));
      });
    }
  }
  $("empty").hidden = !showList || noMatch || zoneCount[0] > 0;
  if ($("upcoming-empty")) $("upcoming-empty").hidden = !showList || noMatch || zoneCount[1] > 0;
  /* LD04 勾选冲突提示条（原型 notice，role=alert，显示在列表区） */
  const notice = $("list-notice");
  notice.textContent = model.notice || "";
  notice.hidden = !showList || !model.notice;
  renderBoard(view);
  refreshControls();
}

/* LD03 整页搜索（原型 toggleSearch，Phone.dc.html:932）：搜索钮展开 / 收起搜索框，
 * 开合都清空关键词（原型 q:''）；折叠内的 #q 保留为快捷入口，两处输入同步同一关键词 */
function toggleSearch() {
  model.searchOpen = !model.searchOpen;
  $("search-view").hidden = !model.searchOpen;
  $("btn-search").setAttribute("aria-expanded", model.searchOpen ? "true" : "false");
  model.filter.q = "";
  if ($("q")) $("q").value = "";
  $("search-q").value = "";
  if (model.searchOpen && $("search-q").focus) $("search-q").focus();
  renderItems();
}
