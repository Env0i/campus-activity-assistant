"use strict";

/* 手机页 DOM 层——状态容器、网络请求与配对轮询（依赖 model*.js 先加载；运行期调用其他 ui-*.js）：
 * 定义 $、请求超时常量、cookie 读取、model 状态对象及配对/轮询会话函数。 */

/* ---------------- DOM 层 ---------------- */
const $ = (id) => document.getElementById(id);
/* 手机走的是自架的电脑 HTTP 服务：断网、网卡被拔、Wi-Fi 漂移都可能让
   fetch 挂着不返回。超过这个时间就主动放弃，把单飞锁放回去。 */
const REQUEST_TIMEOUT_MS = 8000;
/* 页面刷新后 csrf 只留在 cookie 里：取回来才敢继续发写请求 */
function readCookie(name) {
  const raw = typeof document.cookie === "string" ? document.cookie : "";
  const parts = raw.split(";");
  for (let i = 0; i < parts.length; i += 1) {
    const part = parts[i];
    const at = part.indexOf("=");
    if (at < 0) continue;
    if (part.slice(0, at).trim() !== name) continue;
    const value = part.slice(at + 1).trim();
    try { return decodeURIComponent(value); } catch (err) { return value; }
  }
  return "";
}
const model = {
  /* G08：默认段钮＝可报名（原型 init 的 seg:'free'，Phone.dc.html:499） */
  items: [], selected: [], filter: { q: "", status: "free", time: "all" },
  retry: { retry_for_s: 120, max_attempts: 0 }, retryHydrated: false, retryDirty: false,
  seenEventSeq: new Set(), busy: false,
  /* SH05 登录行（loginLine）的 state.login 快照 */
  login: null,
  lastOkAt: 0, nowMs: 0, backoff: 1000, seq: 0,
  flow: null, challenge: null, reloginSubmitting: false,
  reloginStarting: false, offlineTries: 0,
  pending: null, csrf: "", pollTimer: null,
  /* 会话是否已经建立：未配对时一个定时器都不许排，否则未配对页会一直请求 */
  paired: false, flying: false, probed: false, bannerKind: "",
  /* 重叠行点按展开的原因（一次一条）、刚跳转到的那一行、电脑给的北京时间快照 */
  whyId: "", flashId: "", clock: null,
  /* 时钟档位（EX06）、最近一次同步成功时的北京时间文本（EX01）、
     电脑侧最近一次拉活动列表失败（EX05/BE2，快照字段 pc_list_error） */
  clockState: "", lastOkText: "", pcListError: null,
  /* LD03 整页搜索开合、LD04 勾选冲突提示条、LD02「选这一场」当前指向的场次 */
  searchOpen: false, notice: "", pickId: "",
  /* G03 sheet 外壳：当前开着的 sheet（more/review/…）与打开前的焦点元素（关闭后归还） */
  sheetId: "", sheetOpener: null,
  /* RW01 列表开合（原型 listOpen）：运行中默认收起活动列表，点「查看活动列表」展开 */
  listOpen: false,
  /* RW03/SH03/SH04 确认槽：当前确认档（cancelstart/stop/cancelTask），随 sheet 开关收放 */
  confirm: null,
  /* RL06 确认层：电脑存着账号且装了识别时，begin 前先拦一步（openRelogin 置位）；
     RL08 附言：本轮是否在手机上输了账号、勾没勾「保存到这台电脑」 */
  relConfirm: false, relFirstLogin: false, relEnteredAcct: false, relSavedChoice: false,
  /* PA01/EX03/EX04 配对视图：锁定倒计时的呈现值（权威值是服务端 retry_after_s）、
     当前配对错误句、1 秒呈现 tick 的定时器 id；pairing 是在途单飞锁（A-BUG-6）、
     pairOkPending 是配对成功告警的待展示标记（UI-F13，本会话关闭后不再出现） */
  pairLockLeft: 0, pairErr: "", pairTickTimer: 0, pairing: false, pairOkPending: false,
  /* RS01：结果态里点过「完成/重新选择」的计划不再回头——服务端快照会一直带
     最后一份终态计划，按 plan_id 记住已收起的那份，新计划（plan_id 不同）照常接纳 */
  dismissedPlanId: "",
};

/* 收拢 api() 写请求分支与 onForbidden() 的 CSRF cookie 刷新逻辑，读取 cookie 并写入 model.csrf。 */
function adoptCookieCsrf() {
  const fresh = readCookie("campus_phone_csrf");
  if (fresh) model.csrf = fresh;
}
/* 收拢 pair() 成功与 poll() 成功时切到主界面的显隐切换，写入 #pair.hidden 与 #app.hidden。 */
function showAppView() {
  $("pair").hidden = true;
  $("app").hidden = false;
}
/* 收拢 onNeedPair() 回退配对页的显隐切换，写入 #app.hidden 与 #pair.hidden。 */
function showPairView() {
  $("app").hidden = true;
  $("pair").hidden = false;
}

/* ---- 接口 ---- */
async function api(path, options) {
  const opts = Object.assign({ credentials: "same-origin" }, options || {});
  opts.headers = Object.assign({}, opts.headers || {});
  if (opts.body && typeof opts.body !== "string") {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  if (opts.method === "POST") {
    // 重启后设备信任会换发新的 CSRF cookie：写请求每次都按当前 cookie 取值。
    // 沿用页面打开时读到的旧值，就会变成「能看状态、点什么都没反应」，
    // 而且界面上只看到 bad_csrf，看不出是令牌过期。
    adoptCookieCsrf();
    if (model.csrf) opts.headers["X-Campus-Csrf"] = model.csrf;
  }
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  let timer = 0;
  if (controller) {
    opts.signal = controller.signal;
    timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  }
  try {
    const resp = await fetch(path, opts);
    const body = await resp.json().catch(() => ({}));
    if (path === "/api/action") {
      const verdict = PhoneModel.sessionVerdict(resp.status);
      if (verdict === "need_pair") onNeedPair();
      if (verdict === "forbidden") onForbidden(body);
      if (resp.status !== 200 || body.ok === false) {
        body.ok = false;
        body.error = body.error || "action_failed";
      }
    }
    return { status: resp.status, body };
  } finally {
    if (controller) clearTimeout(timer);
  }
}

/* 写动作统一兜底：超时、断网、服务端掉线都不许变成「按钮点了没反应」。
   失败时返回和真响应同形的 {status:0, body:{ok:false, error:"network", text}}，
   各个按钮照原来的错误分支处理，就不会有未处理的 Promise 拒绝。 */
async function postAction(payload) {
  try {
    return await api("/api/action", { method: "POST", body: payload });
  } catch (err) {
    // SH06（原型 netErr，Phone:870）：sheet 开着就在里面挂红条，主屏 banner 照旧兜底
    showSheetError("网络不通，这次操作没有发出去。电脑上的计划还在跑，恢复连接后再试。");
    return { status: 0, body: { ok: false, error: "network",
                               text: "连接中断，操作结果尚未确认；请刷新核对，避免重复操作" } };
  }
}

/* ---- PA01/PA03 配对视图：渲染只写 DOM，取值全在 PhoneModel.pairView ---- */
function renderPair() {
  const view = PhoneModel.pairView(String($("pair-code").value || ""),
                                   model.pairLockLeft, model.pairErr);
  const tag = $("pair-tag");
  tag.textContent = view.tag;
  tag.className = "b-tag" + (view.tagTone ? " " + view.tagTone : "");
  $("pair-led-wrap").className = "led-wrap " + view.led.tone;
  const led = $("pair-led");
  led.style.gridTemplateColumns = "repeat(" + view.led.cols + ", minmax(0, 1fr))";
  led.textContent = "";
  view.led.dots.forEach((d) => {
    const dot = document.createElement("i");
    if (d.cls) dot.className = d.cls;
    led.appendChild(dot);
  });
  $("pair-cap").textContent = view.cap;
  $("pair-code").disabled = view.locked;
  $("btn-pair").disabled = view.cantSubmit;
  const err = $("pair-error");
  err.textContent = view.hasErr ? view.err : "";
  err.hidden = !view.hasErr;
}
function setPairError(text) {
  model.pairErr = String(text || "");
  renderPair();
}
/* EX03：锁定倒计时——权威值只有服务端回包里的 retry_after_s，这里排 1 秒一个的
   setTimeout 只做呈现递减，归零就重新放开输入；服务端仍是唯一的闸门。 */
function beginPairLock(seconds) {
  stopPairLock();
  model.pairLockLeft = Math.max(0, Math.floor(Number(seconds) || 0));
  if (model.pairLockLeft > 0) schedulePairTick();
}
function schedulePairTick() {
  model.pairTickTimer = setTimeout(() => {
    model.pairTickTimer = 0;
    model.pairLockLeft = PhoneModel.pairTickLeft(model.pairLockLeft);
    if (model.pairLockLeft > 0) schedulePairTick();
    else model.pairErr = "";   // UI-F6（原型 lockLeft 归零清 pairErr）：解锁即收回旧错误条
    renderPair();
  }, 1000);
}
function stopPairLock() {
  if (model.pairTickTimer) clearTimeout(model.pairTickTimer);
  model.pairTickTimer = 0;
  model.pairLockLeft = 0;
}
/* PA04/EX03/EX04：失败按结构化回包（BE1）呈现；网络/旧回包退回原句。
   原型 submitPair（Phone:627-634）失败就清空重输。 */
function applyPairFailure(status, body) {
  const error = String((body && body.error) || "");
  $("pair-code").value = "";
  if (error === "locked") {
    beginPairLock(Number((body || {}).retry_after_s) || 0);
    setPairError(PhoneModel.pairLockedText());
    return;
  }
  if (error === "bad_code") {
    setPairError(PhoneModel.pairWrongText((body || {}).remaining_attempts));
    return;
  }
  setPairError("配对失败：" + String((body && (body.text || body.error)) || status));
}

async function pair() {
  /* A-BUG-6：在途锁防双击双发——配对码一次一用，第二个请求必失败还白吃一次
     失败计数；超时/断网路径也要把锁放回去 */
  if (model.pairing) return;
  const code = String($("pair-code").value || "").trim();
  model.pairErr = "";
  stopPairLock();                    // 新的一次尝试：旧倒计时收回（服务端仍会拦）
  renderPair();
  if (!code) { setPairError("请输入 6 位配对码"); return; }
  model.pairing = true;
  try {
    let answer;
    try {
      answer = await api("/pair", { method: "POST", body: { code } });
    } catch (err) {
      // 超时或断网：别让「配对」按下去毫无反应，也别把异常丢到控制台里
      setPairError("配对失败：网络不通，请确认手机和电脑连的是同一个网络");
      return;
    }
    const { status, body } = answer;
    if (status !== 200 || !body.ok) {
      applyPairFailure(status, body);
      return;
    }
    model.csrf = String(body.csrf || "");
    model.paired = true;
    model.pairOkPending = true;   // UI-F13（原型 Phone:630/857）：配对成功给「已连接电脑」告警
    stopPairLock();
    model.pairErr = "";
    renderPair();
    showAppView();
    await poll(true);
  } finally {
    model.pairing = false;
  }
}

/* ---- 轮询：按活动态自适应（进行中 2 秒、空闲 15 秒），失败按退避 ---- */
async function poll(force) {
  if (model.flying) return;                     // 单飞：在途不重发
  if (!model.csrf) model.csrf = readCookie("campus_phone_csrf"); // 刷新后沿用旧会话的写权限
  model.flying = true;
  refreshControls();   // R-备注：先把「同步中」pill 与禁用的刷新钮画出来再发请求（不是「刷新中…」字样）
  try {
    const { status, body } = await api("/api/state?after=" + (force ? 0 : model.seq));
    const verdict = PhoneModel.sessionVerdict(status);
    if (verdict === "need_pair") { onNeedPair(); return; }
    if (verdict === "forbidden") { onForbidden(body); return; }
    if (verdict !== "ok") { onPollFail(); return; }
    model.lastOkAt = Date.now();
    model.backoff = 1000;
    model.paired = true;
    // 状态能读到就说明会话还在：直接进主界面，不要求重新配对
    showAppView();
    // 读到新快照：过时门禁解除，但网络/403 的提示要留到下次明确覆盖
    clearStaleBanner();
    ingest(body || {});
  } catch (err) {
    onPollFail();
  } finally {
    model.flying = false;
    schedule();
    scheduleTick();                 // P1：每次拉到快照都重新对齐整秒
    refreshControls();
    renderItems();
    renderPlan();
  }
}
function onPollFail() {
  // 失败也要有可见反应：计数加一，界面按「连不上」呈现并能继续重试
  model.offlineTries = Number(model.offlineTries || 0) + 1;
  model.backoff = PhoneModel.nextBackoff(model.backoff);
}
function onNeedPair() {
  // 401＝这条会话没了：停表并退出自动同步，等用户重新配对再开始
  model.paired = false;
  if (model.pollTimer) clearTimeout(model.pollTimer);
  model.pollTimer = null;
  if (model.tickTimer) clearTimeout(model.tickTimer);
  model.tickTimer = null;
  stopPairLock();                    // 会话都没了，旧锁定倒计时一并收回
  showPairView();
  renderPair();                      // A-BUG-5：回配对页要按当前模型重画点阵屏，不残留旧点亮状态
}
/* 403 不等于「没配对」：bad_csrf 是令牌和目标会话对不上（比如两个手机页同时开着，
   后打开的那个把 cookie 换了），bad_host/bad_origin 是请求被代理或中间层改写过。
   这两种都不该把用户赶回配对界面——他配过对，只是这次请求不合格。 */
function onForbidden(body) {
  const code = String((body && body.error) || "");
  adoptCookieCsrf();
  setBanner(code === "bad_csrf"
    ? "会话令牌已更新，正在重新同步；一直失败就刷新页面再试"
    : "请求被拒绝（" + (code || "403") + "），请刷新页面再试", "error");
  model.backoff = PhoneModel.nextBackoff(model.backoff);
}
/* 唯一的排期入口：先清旧定时器，再决定要不要排。
   后台不排、未配对不排、有请求在途不排（finally 出来会重排一次）。 */
function schedule() {
  if (model.pollTimer) clearTimeout(model.pollTimer);
  model.pollTimer = null;
  if (typeof document !== "undefined" && document.hidden) return;
  if (!model.paired || model.flying) return;
  model.pollTimer = setTimeout(() => poll(false), PhoneModel.syncDelay(model));
}

/* 首屏只做一次只读探测：只有可能已有会话（csrf cookie 还在）时才发一次，
   没 cookie 就是没配对过，直接停在配对页——不发请求，也不排定时器。 */
function probeExistingSession() {
  if (model.probed) return;
  model.probed = true;
  if (!readCookie("campus_phone_csrf")) return;
  void poll(true);
}
