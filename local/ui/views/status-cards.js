/* 顶栏三张状态详情卡（北京时间 / 登录 / 手机，决策 014 第 3 条）：
 * 悬停约 0.2 秒打开、移开关闭，点击固定，Esc 关闭；卡片贴在各自按钮下面，窄档铺满宽度。
 * 时间卡沿用 views/clock-pop.js 的渲染，这里只管登录卡、手机卡和三张卡共用的开合规则。
 * 卡里只写后端快照里有的东西：登录不显示剩余时间（学校不公布，工具不估算），
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

function renderLoginCard() {
  const view = S.login.view || { state: "none", text: "未登录", note: "" };
  const tone = { ok: "ok", bad: "bad", none: "warn", unknown: "warn", terms: "warn" }[view.state] || "";
  const chip = $("#login-pop-chip");
  if (chip) chip.dataset.tone = tone;
  $("#login-pop-chip-text").textContent = view.text;
  $("#login-pop-big").textContent = LOGIN_CARD_BIG[view.state] || view.text;
  const at = String(S.login.lastCheckAt || "");
  $("#login-pop-sub").textContent = at
    ? "上次校验 " + at + (S.login.lastCheckState === "valid" ? "，学校确认有效" : "")
    : "还没有向学校校验过";
  $("#login-pop-rows").innerHTML = cardRows([
    ["有效多久", "学校不公布，工具不估算"],
    ["别处登录", "会让这里失效，比如手机上的学校页面"],
  ]);
  $("#login-pop-note").textContent = view.note || "";
  const check = $("#btn-login-check");
  if (check) check.disabled = S.busy || !!S.login.checking || termsLocked() || !!S.runtime.error;
}

function phoneSnapshot() {
  return (window.PhonePanel && window.PhonePanel.state) || {};
}

/* 手机标识只在手机访问开启时出现：开启了就常显，关了就收起 */
function paintPhoneBadge() {
  const badge = $("#phone-badge");
  if (!badge) return;
  const state = phoneSnapshot();
  const running = !!state.running;
  badge.hidden = !running;
  if (!running) return;
  const status = state.pair_code_status || {};
  const linked = status.reason === "paired";
  badge.className = "pill phone-badge" + (linked ? " is-ok" : "");
  $("#phone-badge-text").textContent = linked ? "手机已连接" : "等手机连接";
}

function renderPhoneCard() {
  const state = phoneSnapshot();
  const status = state.pair_code_status || {};
  const linked = status.reason === "paired";
  const chip = $("#phone-pop-chip");
  if (chip) chip.dataset.tone = state.running ? (linked ? "ok" : "warn") : "";
  $("#phone-pop-chip-text").textContent = state.running ? (linked ? "已连接" : "等手机连接") : "未开启";
  $("#phone-pop-big").textContent = state.running ? (linked ? "手机已连接" : "等手机连接") : "手机访问未开启";
  const channel = state.channel === "cloudflare" ? "Cloudflare 临时地址" : (state.channel ? "Tailscale" : "—");
  $("#phone-pop-sub").textContent = state.running ? "通道：" + channel : "到设置 → 高级功能里开启";
  $("#phone-pop-rows").innerHTML = state.running ? cardRows([
    ["手机地址", String(state.address || "—")],
    ["配对", linked ? "已配对，配对码已收起" : "在设置里看配对码"],
  ]) : "";
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
  const check = $("#btn-login-check");
  if (check && check.addEventListener) check.addEventListener("click", () => { doCheck(); });
  const manage = $("#btn-phone-manage");
  if (manage && manage.addEventListener) {
    manage.addEventListener("click", () => {
      closeStatusCards(false);
      if (typeof openSettings === "function") openSettings("adv");
    });
  }
}
