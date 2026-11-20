/* 顶栏三张状态详情卡（北京时间 / 登录 / 手机，决策 014 第 3 条）：
 * 悬停约 0.2 秒打开、移开关闭，点击固定，Esc 关闭；卡片贴在各自按钮下面，窄档铺满宽度。
 * 时间卡沿用 views/clock-pop.js 的渲染，这里只管登录卡、手机卡和三张卡共用的开合规则。
 * 卡里只写后端快照里有的东西：登录只写「预计有效」（锚点 + 10 小时估，纯提示，
 * 不参与放行或过期判定；决策 006 修订 2026-11-09），
 * 手机状态只读 PhonePanel.state（phone_access_state 快照）。 */
const STATUS_HOVER_MS = 200;
const STATUS_CARDS = {
  clock: { button: "#clock", pop: "#clock-pop" },
  login: { button: "#pill", pop: "#login-pop" },
  phone: { button: "#phone-badge", pop: "#phone-pop" },
};

function statusCardOpen() {
  return S.statusCard ? S.statusCard.kind : "";
}

function openStatusCard(kind, pinned) {
  const spec = STATUS_CARDS[kind];
  if (!spec) return;
  /* 手机访问正在开启或停止时只有标识在说话，详情卡没有可讲的（照原型：开启中、停止中不弹卡） */
  if (kind === "phone" && typeof PhonePanel !== "undefined"
    && (PhonePanel.pending === "starting" || PhonePanel.pending === "stopping")) return;
  if (S.statusCard && S.statusCard.kind !== kind) closeStatusCards(false);
  S.statusCard = { kind: kind, pinned: !!pinned };
  if (kind === "clock") {
    /* 悬停打开不抢焦点；点击固定时才把焦点交给卡片（clock-pop 自己处理） */
    if (!clockPopOpenNow()) toggleClockPop(!pinned);
    return;
  }
  renderStatusCard(kind);
  const pop = $(spec.pop);
  if (!pop) return;
  pop.hidden = false;
  $(spec.button).setAttribute("aria-expanded", "true");
  placeStatusCard(kind);
}

function closeStatusCards(restoreFocus) {
  const current = S.statusCard;
  S.statusCard = null;
  if (clockPopOpenNow()) closeClockPop(!!restoreFocus && !!current && current.kind === "clock");
  ["login", "phone"].forEach((kind) => {
    const spec = STATUS_CARDS[kind];
    const pop = $(spec.pop);
    if (pop) pop.hidden = true;
    const button = $(spec.button);
    if (button) button.setAttribute("aria-expanded", "false");
  });
  if (restoreFocus && current && current.kind !== "clock") {
    const button = $(STATUS_CARDS[current.kind].button);
    if (button && button.focus) button.focus();
  }
}

function placeStatusCard(kind) {
  const spec = STATUS_CARDS[kind];
  const pop = $(spec.pop);
  const button = $(spec.button);
  if (!pop || !button || !button.getBoundingClientRect) return;
  const rect = button.getBoundingClientRect();
  pop.style.top = Math.round(rect.bottom + 8) + "px";
  pop.style.left = Math.round(Math.max(12,
    Math.min(window.innerWidth - pop.offsetWidth - 12, rect.right - pop.offsetWidth))) + "px";
}

function renderStatusCard(kind) {
  if (kind === "login") renderLoginCard();
  else if (kind === "phone") renderPhoneCard();
}

/* 卡片内容随状态变化重画：打开着的卡跟着刷新，关着的不动 */
function paintStatusCards() {
  const kind = statusCardOpen();
  if (kind === "login" || kind === "phone") renderStatusCard(kind);
  paintPhoneBadge();
}

function cardRows(rows) {
  return rows.map((row) => "<dt>" + esc(row[0]) + "</dt><dd>" + esc(row[1]) + "</dd>").join("");
}

/* 上次校验时刻：bootstrap.login / check 事件里的 last_check_at（北京时间文本） */
function lastCheckText() {
  const at = String(S.login.lastCheckAt || "");
  return at ? at.slice(-8, -3) || at : "";
}

const LOGIN_CARD_BIG = {
  ok: "登录有效", bad: "登录已失效", none: "还没登录", unknown: "暂时无法确认",
  checking: "正在检查", pending: "正在登录", demo: "演示模式", terms: "等同意条款",
};
/* 阶段覆盖只换与胶囊同步的标签和大字，详情卡其余信息沿用结论状态。 */
const LOGIN_CARD_PHASES = {
  rechecking: { tone: "ok", big: "登录有效" },
  needs_code: { tone: "warn", big: "要你输验证码" },
};

/* 条款门下这张卡没有可做的事：两只学校动作按钮仍按决策 013 禁用，这里只是把它们收起来——
 * 灰着又点不动的按钮比看不见更像坏了。留下的只有「为什么停着」和唯一能走的那一步。
 * 「已保存的登录还在」只对登录过的人成立：从没登录过的人看到它就是假话。 */
function paintLoginCardTermsHold() {
  $("#login-pop-chip-text").textContent = S.terms.unknown ? "等确认条款" : "等同意条款";
  $("#login-pop-big").textContent = "暂停检查";
  $("#login-pop-sub").textContent = "同意条款后才会检查登录状态";
  $("#login-pop-rows").innerHTML = S.login.present === true
    ? cardRows([["已保存的登录", "还在，不会删除"]]) : "";
  $("#login-pop-note").textContent = "";
}

/* 卡片底部的三只按钮：条款门下只留「查看条款」，出了条款门回到两只学校动作。 */
function paintLoginCardActions(paused) {
  const check = $("#btn-login-check");
  const login = $("#btn-login");
  const terms = $("#btn-login-terms");
  if (check) check.hidden = !!paused;
  if (login) login.hidden = !!paused;
  if (terms) terms.hidden = !paused;
}

function renderLoginCard() {
  const view = S.login.view || { state: "none", text: "未登录", note: "" };
  const phaseLook = LOGIN_CARD_PHASES[view.phase];
  const tone = phaseLook ? phaseLook.tone
    : ({ ok: "ok", bad: "bad", none: "warn", unknown: "warn", terms: "warn" }[view.state] || "");
  const chip = $("#login-pop-chip");
  if (chip) chip.dataset.tone = tone;
  /* 检查按钮的禁用照旧按原规则算：条款门下它是被收起来，不是解禁 */
  const check = $("#btn-login-check");
  if (check) check.disabled = S.busy || !!S.login.checking || termsLocked() || !!S.runtime.error;
  if (termsLocked()) {
    paintLoginCardTermsHold();
    paintLoginCardActions(true);
    return;
  }
  paintLoginCardActions(false);
  $("#login-pop-chip-text").textContent = view.text;
  $("#login-pop-big").textContent = phaseLook ? phaseLook.big
    : (LOGIN_CARD_BIG[view.state] || view.text);
  const at = String(S.login.lastCheckAt || "");
  $("#login-pop-sub").textContent = at
    ? "上次校验 " + at + (S.login.lastCheckState === "valid" ? "，学校确认有效" : "")
    : "还没有向学校校验过";
  $("#login-pop-rows").innerHTML = cardRows([
    ["预计有效", loginEstimateText()],
    ["别处登录", "可能让这里失效，比如手机上的学校页面；以实际登录状态为准"],
  ]);
  $("#login-pop-note").textContent = view.note || "";
}

/* 手机访问的快照挂在 features 里，由 legacy-globals 挂回 window 给普通脚本用；
 * 这里直接写 PhonePanel（挂回后的全局名），typeof 兜住启动早期还没挂上的那一瞬。 */
function phoneSnapshot() {
  return typeof PhonePanel === "undefined" ? {} : (PhonePanel.state || {});
}

function phonePending() {
  return typeof PhonePanel === "undefined" ? "" : String(PhonePanel.pending || "");
}

/* 标识的五个样子：「连着没有」读后端 link（手机两分钟没来就是「已断开 · N 分钟前」，
 * 规则在 features/phone-access/state-link.js），过程读 PhonePanel.pending：
 *   正在开启… / 正在停止…   灰色，前面挂一个转圈（说话的是过程，不是连接状态）
 *   手机已连接              绿底
 *   等手机连接              琥珀底，手机图标慢闪
 *   已断开 · N 分钟前       灰底，带时间
 * 没开就收起；配对与否与标识无关，点进详情卡才看得到。 */
function phoneBadgeLook() {
  const state = phoneSnapshot();
  const view = phoneLinkView(state);
  const pending = phonePending();
  const busy = pending === "starting" || pending === "stopping";
  if (busy) {
    const text = pending === "starting" ? "正在开启…" : "正在停止…";
    return { show: true, link: view.link, text: text, tone: "", busy: true };
  }
  return { show: view.link !== "off", link: view.link, text: view.title, tone: view.tone, busy: false };
}

function paintPhoneBadge() {
  const badge = $("#phone-badge");
  if (!badge) return;
  const look = phoneBadgeLook();
  const spin = $("#phone-badge-spin");
  badge.hidden = !look.show;
  badge.dataset.link = look.link;
  if (spin) spin.hidden = !look.busy;
  if (!look.show) return;
  const tone = look.tone === "ok" ? " is-ok" : (look.tone === "warn" ? " is-warn blink" : "");
  badge.className = "pill phone-badge" + tone;
  $("#phone-badge-text").textContent = look.text;
  /* 屏幕阅读器要听得出是哪种状态；等手机连接那句单独写全，因为它不能只念「等手机连接」 */
  const spoken = look.busy ? look.text : (look.link === "waiting" ? "手机访问已开启，等手机连接" : look.text);
  badge.setAttribute("aria-label", spoken + "，查看详情");
}

/* 详情卡的三句话：副句随连接状态走，底部提醒随通道走（临时地址会变、程序退出手机就打不开） */
const PHONE_CARD_SUB = {
  waiting: "用手机扫码打开页面，再输入配对码",
  connected: "在手机上能看活动、开始和停止计划",
  disconnected: "手机一段时间没来访问，不算出错；手机回来会自动变成已连接",
};
const PHONE_CARD_NOTE = {
  cloudflare: "这是临时地址，关闭访问或重启程序后就会变，手机要重新扫码配对。",
  tailscale: "程序退出后手机就打不开了。想在外面随时用，关窗口时选最小化或隐藏到后台。",
};

/* 配对码还剩多久：「m:ss」。这里不引 features 里的同名函数——普通脚本只能看挂回 window 的名字，
 * 为一个倒计时多挂一个全局不划算，格式只有这一行。 */
function countdown(seconds) {
  const left = Math.max(0, Math.floor(Number(seconds) || 0));
  return Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0");
}

function phoneCardRows(state, view, paired) {
  if (!state.running) return [];
  const cf = state.channel === "cloudflare";
  const rows = [
    ["通道", cf ? "Cloudflare，临时地址" : "Tailscale，地址固定"],
    ["地址", String(state.address || "—").replace(/^https?:\/\//, "").replace(/\/$/, "")],
  ];
  if (paired) {
    /* 只有活动会话、还没真配过对时不能写「1 台手机」，那是另一件事 */
    const count = Number(state.paired_count || 0);
    rows.push(["已配对", count > 1 ? count + " 台手机" : (count === 1 ? "1 台手机" : "有手机连着")]);
    rows.push(["手机最近访问", view.ago || "—"]);
    return rows;
  }
  const info = state.pair_code_status || {};
  rows.push(["配对码", info.code ? countdown(info.expires_in) + " 后换新" : "在设置里看配对码"]);
  return rows;
}

function renderPhoneCard() {
  const state = phoneSnapshot();
  const view = phoneLinkView(state);
  const paired = phoneLinkedNow(state);
  const chip = $("#phone-pop-chip");
  if (chip) chip.dataset.tone = state.running ? view.tone : "";
  $("#phone-pop-chip-text").textContent = state.running ? view.chip : "未开启";
  const cap = $("#phone-pop-cap");
  if (cap) cap.textContent = state.channel === "cloudflare" ? "临时地址" : "长期地址";
  $("#phone-pop-big").textContent = state.running ? view.big : "手机访问未开启";
  $("#phone-pop-sub").textContent = state.running ? (PHONE_CARD_SUB[view.link] || "") : "到设置 → 高级功能里开启";
  const note = $("#phone-pop-note");
  if (note) {
    note.textContent = state.running
      ? (state.channel === "cloudflare" ? PHONE_CARD_NOTE.cloudflare : PHONE_CARD_NOTE.tailscale)
      : "";
  }
  $("#phone-pop-rows").innerHTML = cardRows(phoneCardRows(state, view, paired));
}

function wireStatusCards() {
  Object.keys(STATUS_CARDS).forEach((kind) => {
    const spec = STATUS_CARDS[kind];
    const button = $(spec.button);
    const pop = $(spec.pop);
    if (!button || !button.addEventListener) return;
    let hoverTimer = null;
    let leaveTimer = null;
    const cancel = () => { clearTimeout(hoverTimer); clearTimeout(leaveTimer); };
    const leave = () => {
      cancel();
      leaveTimer = setTimeout(() => {
        if (S.statusCard && S.statusCard.kind === kind && !S.statusCard.pinned) closeStatusCards(false);
      }, 150);
    };
    button.addEventListener("mouseenter", () => {
      cancel();
      if (S.statusCard && S.statusCard.pinned) return;   /* 已固定另一张卡时悬停不抢 */
      hoverTimer = setTimeout(() => openStatusCard(kind, false), STATUS_HOVER_MS);
    });
    button.addEventListener("mouseleave", leave);
    if (pop && pop.addEventListener) {
      pop.addEventListener("mouseenter", cancel);
      pop.addEventListener("mouseleave", leave);
    }
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      cancel();
      if (S.statusCard && S.statusCard.kind === kind && S.statusCard.pinned) {
        closeStatusCards(true);
        return;
      }
      if (S.statusCard && S.statusCard.kind === kind) {
        S.statusCard.pinned = true;   /* 悬停打开后再点：就地固定，不闪一下 */
        return;
      }
      openStatusCard(kind, true);
    });
  });
  document.addEventListener("mousedown", (event) => {
    if (!S.statusCard || !event.target || !event.target.closest) return;
    const spec = STATUS_CARDS[S.statusCard.kind];
    if (!event.target.closest(spec.pop) && !event.target.closest(spec.button)) closeStatusCards(false);
  });

}
