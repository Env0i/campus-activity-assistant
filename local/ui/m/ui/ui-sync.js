"use strict";

/* 手机页 DOM 层——快照摄入与整秒计时（依赖 model*.js、ui-session.js、ui-status.js、ui-list.js 先加载）：
 * 负责整秒时钟/倒计时局部刷新与服务端状态快照增量摄入。 */

/* P1：每秒对整秒刷一次只读数字（北京时间、点阵屏倒计时、「现在 HH:MM」与行内倒计时）。
   不整页重画、不额外联网；快照仍由 schedule() 的 poll 更新，这里只按已有快照推进。
   后台不排；回前台由 visibilitychange 立刻同步一次，重新对时。 */
function scheduleTick() {
  if (model.tickTimer) clearTimeout(model.tickTimer);
  model.tickTimer = null;
  if (typeof document !== "undefined" && document.hidden) return;
  if (!model.paired) return;
  model.tickTimer = setTimeout(() => {
    model.tickTimer = null;
    tickClock();
    scheduleTick();
  }, PhoneModel.nextTickDelay(PhoneModel.businessNowS(model)));
}
function tickClock() {
  if (typeof document !== "undefined" && document.hidden) return;
  /* H4：每次 tick 记一对 (Date.now, performance.now)。两者走时对不上（锁屏睡过）时，
     推算的业务时间已落后，不能当可信时间显示：丢掉旧快照让整页落「待校准」，
     并立刻补一次轮询重新对时（poll 成功后 setClock 会换上新快照）。 */
  const wallMs = Date.now();
  const monoMs = PhoneModel.mono();
  const slept = PhoneModel.sleepJumped(model.tickMark, wallMs, monoMs);
  model.tickMark = { wall: wallMs, mono: monoMs };
  if (slept && model.clock) {
    model.clock = null;
    if (model.paired) void poll(false);
  }
  const nowS = PhoneModel.businessNowS(model);
  const clockText = nowS !== null
    ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)) : "待校准";
  const nowEl = $("board-now-text");
  if (nowEl && !$("board-now").hidden && nowEl.textContent !== clockText) {
    nowEl.textContent = clockText;
  }
  const chipText = nowS !== null
    ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)).slice(0, 5) : "";
  if (typeof document !== "undefined" && typeof document.querySelectorAll === "function") {
    /* 「现在」分隔行只有一个值，草稿/明天各区相同，逐个按当前时间对齐 */
    document.querySelectorAll(".nowchip b").forEach((el) => {
      if (chipText && el.textContent !== chipText) el.textContent = chipText;
    });
  }
  const view = PhoneModel.listView(model.items, model.filter, {
    nowS: nowS, selected: model.selected, busy: model.busy, termsOk: model.termsOk,
  });
  tickBoardLed(nowS, view);
  tickRowLeft(view);
}
/* 点阵屏只换数字：aria 里带着两行说明与倒计时文本，内容变了才重建点阵 */
function tickBoardLed(nowS, view) {
  const section = $("plan-board");
  if (!section || section.hidden) return;
  const pendingNow = !!(model.pending && !model.pending.done);
  const result = PhoneModel.resultView(model.plan, model.busy);
  if (result) return;                    // 结果板没有 LED（renderBoard 已收起）
  let board = null;
  if (model.busy) {
    board = PhoneModel.runBoard(model.plan, nowS,
      PhoneModel.connState(model, model.flying).state === "off", model.lastOkText);
  } else if (pendingNow) {
    board = PhoneModel.pendingBoard(model.pending, Date.now());
  } else if (model.termsOk === false) {
    board = PhoneModel.termsBoard();
  } else {
    board = view.board;
  }
  if (!board || !board.led) return;
  const wrap = $("board-led-wrap");
  if (!wrap || wrap.hidden) return;
  if (wrap.getAttribute("aria-label") === board.led.aria) return;
  wrap.className = "led-wrap " + board.led.tone;
  wrap.setAttribute("aria-label", board.led.aria);
  const led = $("board-led");
  led.style.gridTemplateColumns = "repeat(" + board.led.cols + ", minmax(0, 1fr))";
  led.textContent = "";
  board.led.dots.forEach((d) => {
    const dot = document.createElement("i");
    if (d.cls) dot.className = d.cls;
    led.appendChild(dot);
  });
  $("board-cap-text").textContent = board.led.cap;
  $("board-cap-b").textContent = board.led.capB;
}
/* 行内倒计时只打补丁：按 data-id 找到已渲染的行，只换 .time small，不重建列表 */
function tickRowLeft(view) {
  if (typeof document === "undefined") return;
  const nodes = {};
  /* H5：只在列表行容器里找。核对抽屉里的移除钮也带 data-id 且排在文档后面，
     按整个文档找会让它覆盖行节点，抽屉开着时行倒计时就停走。 */
  LIST_ZONES.forEach((zone) => {
    const box = $(zone[0]);
    if (!box || typeof box.querySelectorAll !== "function") return;
    box.querySelectorAll("[data-id]").forEach((el) => {
      if (el && el.dataset) nodes[String(el.dataset.id)] = el;
    });
  });
  /* 行在两次轮询之间跨过开放时刻：推算值已是 open，而这一行还是按「待开放」画的（倒计时文字不是
     「已开放」）。分组与标记要以服务端快照为准，所以补一次轮询；文字先就地对齐，下一次 tick
     这行已是「已开放」，不会重复触发。 */
  let crossed = false;
  (view.groups || []).forEach((group) => {
    (group.rows || []).forEach((row) => {
      const el = nodes[String(row.id)];
      const small = el && el.querySelector ? el.querySelector(".time small") : null;
      if (!small || !row.hasLeft) return;
      if (row.st === "open" && small.textContent !== "已开放") crossed = true;
      if (small.textContent !== row.left) small.textContent = row.left;
      const cls = row.leftCls || "";
      if (String(small.className || "") !== cls) small.className = cls;
    });
  });
  if (crossed && model.paired) void poll(false);
}

function ingest(payload) {
  if (payload.reset) {
    // reset 开启新的事件缓冲周期，清掉上一轮的去重记录。
    model.seenEventSeq.clear();
    model.seq = 0;
    // 断得太久服务端已丢中间事件：日志整体重置，不把旧事件再叠一遍
    const logs = $("logs");
    if (logs) logs.textContent = "";
  }
  const state = payload.state || {};
  // 服务端把当前重新登录现场放在 state.login_relay：先按快照重建，再叠加增量事件
  if (state.login_relay && typeof state.login_relay === "object") {
    ingestRelogin(state.login_relay);
  }
  if (Array.isArray(state.activities)) {
    model.items = state.activities;
    const before = model.selected.slice();
    const businessNow = PhoneModel.businessNowS(model);
    model.selected = before.filter((id) => {
      const item = model.items.find((candidate) => candidate && candidate.id === id);
      if (!item || !PhoneModel.actionable(item, model.items)) return false;
      const status = PhoneModel.stOf(item, businessNow);
      return status === "open" || status === "pre";
    });
    if (model.selected.length !== before.length) model.notice = "";
  }
  /* RS01：用户在结果态收起过的计划不再回头（服务端快照会一直带终态计划）；
     新计划 plan_id 不同，照常接纳 */
  if (state.plan && String(state.plan.plan_id || "") !== model.dismissedPlanId) {
    model.plan = state.plan;
  }
  if (typeof state.terms_ok === "boolean") model.termsOk = state.terms_ok;
  if (state.relogin_setup && typeof state.relogin_setup === "object") model.reloginSetup = state.relogin_setup;
  if (state.business_clock && typeof state.business_clock === "object") {
    model.clockState = String(state.business_clock.state || "");
    PhoneModel.setClock(model, state.business_clock);
    /* EX01：同步成功时记下这份快照的北京时间（HH:MM:SS），离线档「最后同步」用它；
       钟不可用就不记（呈现层落 --:--:--），不拿手机墙钟冒充 */
    const sampled = model.clock ? model.clock.epochAtSampleS : null;
    model.lastOkText = sampled !== null
      ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(sampled)) : "";
  }
  /* EX05/BE2：电脑侧最近一次拉活动列表失败（原因短语 + 北京 HH:MM），正常为 null */
  model.pcListError = state.pc_list_error || null;
  if (typeof state.busy === "boolean") model.busy = state.busy;
  if (state.retry_policy && typeof state.retry_policy === "object"
      && !model.retryHydrated && !model.retryDirty) {
    model.retry = {
      retry_for_s: Number(state.retry_policy.retry_for_s),
      max_attempts: Number(state.retry_policy.max_attempts || 0),
    };
    model.retryHydrated = true;
  }
  if (state.retry_options && Array.isArray(state.retry_options.choices)) {
    model.retryOptions = state.retry_options;
    fillRetryOptions(state.retry_options);
  }
  (payload.events || []).forEach((event) => {
    const eventSeq = Number(event.seq || 0);
    model.seq = Math.max(model.seq, eventSeq);
    if (eventSeq > 0) {
      if (model.seenEventSeq.has(eventSeq)) return;
      model.seenEventSeq.add(eventSeq);
      while (model.seenEventSeq.size > 400) {
        model.seenEventSeq.delete(Math.min.apply(null, Array.from(model.seenEventSeq)));
      }
    }
    if (event.kind === "log") {
      /* 后端 _emit("log", 字符串) 发的是字符串；对象负载才取 text/detail；空串不进记录 */
      const raw = event.payload;
      const line = typeof raw === "string" ? raw
        : String((raw && (raw.text || raw.detail)) || "");
      if (line) addLog(line);
    }
    if (event.kind === "phone_relogin" && !state.login_relay) ingestRelogin(event.payload || {});
  });
  if (payload.seq) model.seq = Math.max(model.seq, Number(payload.seq));
  /* TM01：条款未同意走专用告警条（renderTermsAlert，refreshControls 里写文案与开关），
     不再占用 #banner——原单句 kind=terms 退役，别的错误提示不受影响 */
  // 登录失效的呈现（EX02 告警 + 底栏）由 renderAlerts/renderBar 按优先链管：
  // 这里只存快照，手机能看列表不代表电脑还能报名
  if (state.login && typeof state.login === "object") {
    model.login = state.login;   // SH05 登录行（loginLine）同一份快照
  }
  const syncLine = $("last-sync");
  if (syncLine) {
    /* U7：按北京时间写，取法同本文件其他处（业务此刻 → beijingSecOf）。原来读手机本机时钟和手机时区，
       手机不在东八区就是错的；业务钟不可用时与离线档「最后同步」一样落 --:--，不拿手机时钟冒充 */
    const syncNow = PhoneModel.businessNowS(model);
    const syncAt = syncNow !== null
      ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(syncNow)).slice(0, 5) : "--:--";
    syncLine.textContent = "最近同步 " + syncAt;
  }
  /* U4：核对弹层开着时轮询带回的新状态也要重画（列表、勾选、提醒都可能变了），
     不然弹层停在打开那一刻的样子；勾选被新状态清空了就收起，同 removeFromReview 的收口 */
  if (model.sheetId === "review") {
    if (!model.selected.length) closeSheet(true);
    else renderReview();
  }
  if (model.pending && !model.pending.done) void reconcile();
}
