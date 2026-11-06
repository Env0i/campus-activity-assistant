"use strict";

/* 手机页逻辑：只做配对、8 项操作与恢复对账。
 * 纯规则集中在 PhoneModel（node vm 可直接执行），DOM 层只负责取值与渲染。
 * 全列表一律 textContent，不拼 HTML；session cookie 不进 localStorage。 */

const PhoneModel = {
  /* 请求 ID：crypto.getRandomValues 在 HTTP 页面上也可用，不假定 randomUUID */
  newRequestId() {
    const buf = new Uint8Array(12);
    (globalThis.crypto || {}).getRandomValues
      ? globalThis.crypto.getRandomValues(buf)
      : buf.forEach((_, i) => { buf[i] = Math.floor(Math.random() * 256); });
    return Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join("");
  },

  /* 筛选：关键词 + 报名状态 + 开放时间（今天 / 未来 7 天） */
  filterItems(items, filter, nowS) {
    const q = String((filter && filter.q) || "").trim().toLowerCase();
    const status = (filter && filter.status) || "all";
    const time = (filter && filter.time) || "all";
    return (items || []).filter((item) => {
      if (q) {
        const hay = String(item.name || "") + " " + String(item.place || item.location || "");
        if (hay.toLowerCase().indexOf(q) < 0) return false;
      }
      const signed = !!item.signed;
      if (status === "free" && signed) return false;
      if (status === "signed" && !signed) return false;
      if (time !== "all") {
        const open = Number(item.open_ts || 0);
        if (!(open > 0)) return false;
        const day = 86400;
        if (time === "today" && !(open <= nowS + day)) return false;
        if (time === "week" && !(open <= nowS + 7 * day)) return false;
      }
      return true;
    });
  },

  /* 开放时刻的 epoch 秒：优先 open_ts；真实手机快照里没有 open_ts，
     只有 sign_start 文本，按北京时间（UTC+8）解析，和运行机器的时区无关。 */
  openEpochOf(item) {
    if (!item) return 0;
    const direct = Number(item.open_ts || 0);
    if (direct > 0) return direct;
    const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?$/
      .exec(String(item.sign_start || "").trim());
    if (!m) return 0;
    const ms = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]),
      Number(m[4]) - 8, Number(m[5]), Number(m[6] || 0));
    return Math.floor(ms / 1000);
  },

  /* 分区：手机上先看「今天」，再看「即将开放」，已报名的折起来。
   * 24 小时内开放（或已经在报）的算今天：手机上真正要动手的就是这些。 */
  bucketOf(item, nowS) {
    if (!item) return "upcoming";
    if (item.signed) return "signed";
    const open = PhoneModel.openEpochOf(item);
    if (!(open > 0)) {
      // 缺开放时间的只能算「以后」，但截止还没到的仍然可勾选
      return item.closed ? "signed" : "upcoming";
    }
    return open <= nowS + 86400 ? "today" : "upcoming";
  },

  /* 断线退避：指数增长，上限 15 秒 */
  nextBackoff(currentMs) {
    const cur = Number(currentMs) || 1000;
    return Math.min(15000, Math.max(1000, cur * 2));
  },

  /* 状态过时：30 秒没有新快照就显示离线/未知。
     空闲同步是 15 秒一次，门禁必须比它长一个周期，否则正常空闲也会被误判成
     「先刷新再开始」；连续失联两个周期（约 30 秒）才锁写入口。 */
  staleAfterMs: 30000,
  isStale(lastOkMs, nowMs) {
    if (!lastOkMs) return true;
    return (Number(nowMs) - Number(lastOkMs)) > PhoneModel.staleAfterMs;
  },

  /* 自适应同步：手上有事就快、没事就慢。两个周期都是产品参数，
     不是学校接口实测值——8 秒请求超时决定了活动态不能比 2 秒更密。 */
  IDLE_SYNC_MS: 15000,
  ACTIVE_SYNC_MS: 2000,

  /* 重新登录是不是「正在进行」：这几个状态里界面上的数字每秒都在变，同步要跟上 */
  reloginBusy(flow) {
    if (!flow) return false;
    if (flow.submit_pending) return true;
    return flow.state === "starting" || flow.state === "waiting_code"
      || flow.state === "verifying";
  },
  /* 有没有正在进行的事：报名计划、待对账的开始请求、重新登录开始/提交/验证中 */
  isActive(model) {
    if (!model) return false;
    if (model.busy) return true;
    if (model.reloginStarting || model.reloginSubmitting) return true;
    if (PhoneModel.startPending(model.pending, Date.now())) return true;
    return PhoneModel.reloginBusy(model.flow);
  },
  /* 失败退避优先；退避清零后按活动态选 2 秒或 15 秒 */
  syncDelay(model) {
    const backoff = Number(model && model.backoff);
    if (Number.isFinite(backoff) && backoff > 1000) return backoff;
    return PhoneModel.isActive(model) ? PhoneModel.ACTIVE_SYNC_MS
      : PhoneModel.IDLE_SYNC_MS;
  },

  /* 过时/忙/空选都禁开始；停止始终可点 */
  canStart(model) {
    if (!model || PhoneModel.isStale(model.lastOkAt, model.nowMs)) return false;
    if (model.busy) return false;
    return (model.selected || []).length > 0;
  },
  canSubmitRelogin(model, challenge) {
    if (!model || PhoneModel.isStale(model.lastOkAt, model.nowMs)) return false;
    if (!challenge || !challenge.challenge_id) return false;
    if (model.reloginSubmitting) return false;
    // 服务端说还有一张在途提交（或正在校验）时，同一张图绝不能再发第二个 POST
    const flow = model.flow;
    if (flow && (flow.submit_pending || flow.state === "verifying")) return false;
    return true;
  },

  /* 验证码代次：只有当前 flow/challenge 才能渲染与提交；验证码不倒计时 */
  challengeExpired(challenge, nowMs) {
    return !challenge;
  },
  matchesChallenge(state, flowId, challengeId) {
    return !!state && String(state.flow_id || "") === String(flowId || "")
      && String(state.challenge_id || "") === String(challengeId || "");
  },

  /* 倒计时：优先后端已接纳 deadline；-1 初始 120，0 直达 sign_end（缺则 2 分钟） */
  RETRY_FALLBACK_S: 120,
  taskDeadline(task, nowS) {
    const telemetry = Number(task && task.retry_deadline);
    if (Number.isFinite(telemetry) && telemetry > 0) return telemetry;
    const raw = Number(task && task.retry_for_s);
    const retryFor = raw === -1 ? PhoneModel.RETRY_FALLBACK_S
      : (Number.isFinite(raw) ? raw : PhoneModel.RETRY_FALLBACK_S);
    const signEnd = Number(task && task.sign_end_ts || 0) || null;
    const anchor = Number(task && task.retry_started_at || 0) || null;
    if (retryFor === 0 && signEnd !== null) return signEnd;
    if (anchor === null) return null;
    let deadline = retryFor > 0 ? anchor + retryFor : anchor + PhoneModel.RETRY_FALLBACK_S;
    if (signEnd !== null) deadline = Math.min(deadline, signEnd);
    return deadline;
  },

  /* 0 模式缺截止：老实提示 2 分钟兜底 */
  retryHint(mode, hasSignEnd) {
    if (Number(mode) === 0 && !hasSignEnd) return "没有报名截止时间：本次最多 2 分钟";
    if (Number(mode) === -1) return "自动延长，最多 25 分钟；报名截止仍是硬上限";
    return "";
  },

  /* 未确认 start：同 request_id 只读对账；15 秒内不重复，超时也不清 pending */
  startPending(pending, nowMs) {
    if (!pending) return false;
    return (Number(nowMs) - Number(pending.at || 0)) < 15000 || !pending.done;
  },

  /* 呈现：安全 textContent 文本，不拼标签 */
  itemTitle(item) {
    return String(item && item.name || "未命名活动");
  },
  itemMeta(item) {
    const bits = [];
    if (item && item.sign_start) bits.push("开放 " + item.sign_start);
    if (item && item.sign_end) bits.push("截止 " + item.sign_end);
    if (item && item.signed) bits.push("已报名");
    return bits.join(" · ");
  },
  actionable(item) {
    if (!item || item.signed) return false;
    if (!item.open_ts && !item.sign_start) return false;      // 时间未知不可执行
    if (item.closed) return false;                            // 已截止不可执行
    return true;
  },
  /* 每场一句话（与电脑同一套说法，设计第 10 节）：提交方式、等自动登录、名额已满等结束结论 */
  taskText(task) {
    const t = task || {};
    const st = String(t.status || "");
    const stop = String(t.stop_reason || "");
    if (st === "success" || st === "already_signed") return "已报名";
    if (stop === "full") return "名额已满（学校说满了，不再提交，不是工具出错）";
    if (stop === "unconfirmed") return "待核对（去活动页看一眼，工具不会再自动重发）";
    if (st === "failed" || st === "canceled") {
      return "报名未成功" + (t.outcome_label ? "：" + t.outcome_label : (st === "canceled" ? "：已取消" : ""));
    }
    if (String(t.login_wait || "") === "waiting") return "电脑正在自动登录，换上新登录态后接着提交";
    const via = t.path === "click" ? "；改用页面点击" + (t.path_reason ? "：" + t.path_reason : "")
      : (t.path === "direct" ? "；直接提交" : "");
    return (st === "submitting" ? "提交中" : "等开放") + via;
  },
  escape(text) {
    return String(text == null ? "" : text).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[c]);
  },
  /* 开始前提醒（与电脑同一套，只提醒不拦）：开放时间用后端给的 seconds_to_open，不读手机时钟 */
  preStartWarnings(model, picked) {
    const list = [];
    if (model && model.clockState === "holdover") list.push("北京时间在用上次的校准结果，电脑会自动重新校准。");
    const secs = (picked || []).map((i) => Number(i.seconds_to_open)).filter((n) => Number.isFinite(n));
    const latest = secs.length ? Math.max.apply(null, secs) : null;
    const setup = (model && model.reloginSetup) || {};
    if (latest !== null && latest > 3600 && !(setup.saved && setup.ocr_ready && !setup.paused)) {
      list.push("最晚一场要等 1 小时以上，电脑的自动登录没开全：中途登录失效要你重新登录；开放前 100 秒内失效的那场会直接结束。");
    }
    if (model && model.retry && Number(model.retry.retry_for_s) === 0
        && (picked || []).some((i) => !i.sign_end && !i.sign_end_ts)) {
      list.push("尝试时长选了「直到报名截止」，但有场次没给截止时间：这些场次最多试 2 分钟。");
    }
    if (latest !== null && latest > 86400) list.push("最晚一场 24 小时以后才开放：这段时间别关电脑上的工具，也别让电脑睡眠。");
    return list;
  },
  connText(model) {
    if (!model || PhoneModel.isStale(model.lastOkAt, model.nowMs)) return "离线/未知";
    return "已连接";
  },
};

/* 纯状态导出：node vm 行为测试直接跑真实函数，不用搜字符串代替断言 */
if (typeof globalThis !== "undefined") globalThis.PhoneModel = PhoneModel;

/* ---------------- DOM 层 ---------------- */
if (typeof document !== "undefined") {
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
    items: [], selected: [], filter: { q: "", status: "all", time: "all" },
    retry: { retry_for_s: 120, max_attempts: 0 }, busy: false,
    lastOkAt: 0, nowMs: 0, backoff: 1000, seq: 0,
    flow: null, challenge: null, reloginSubmitting: false,
    reloginStarting: false, offlineTries: 0,
    pending: null, csrf: "", pollTimer: null,
    /* 会话是否已经建立：未配对时一个定时器都不许排，否则未配对页会一直请求 */
    paired: false, flying: false, probed: false, bannerKind: "",
  };

  /* 提示条带一个最小来源标签，不靠比对整句中文来区分谁写的：
     stale_action 是「状态过时」这类门禁提示，成功同步后可以自动清掉；
     error 是网络/403/服务端业务错误，必须留到下一次明确覆盖。 */
  function setBanner(text, kind) {
    const el = $("banner");
    model.bannerKind = text ? String(kind || "info") : "";
    el.textContent = text || "";
    el.hidden = !text;
    el.dataset.kind = model.bannerKind;
  }
  /* 只清「过时」这一种：读状态成功不代表网络或服务端错误已经解决 */
  function clearStaleBanner() {
    if (model.bannerKind === "stale_action") setBanner("", "");
  }
  function canWrite() {
    model.nowMs = Date.now();
    return !PhoneModel.isStale(model.lastOkAt, model.nowMs);
  }
  /* 连不上电脑时，界面不能看起来一切正常、点着又没反应：
     顶部固定一条说明 + 刷新按钮始终可点，是唯一能自救的入口。 */
  function syncOffline(stale) {
    const note = $("offline-note");
    if (!stale) {
      note.hidden = true;
      model.offlineTries = 0;
      return;
    }
    const tries = Number(model.offlineTries || 0);
    note.hidden = false;
    note.textContent = tries > 0
      ? "连不上电脑（已重试 " + tries + " 次）：确认电脑上的程序还开着、手机和电脑在同一网络，再点右上角「刷新」。"
      : "连不上电脑：确认电脑上的程序还开着、手机和电脑在同一网络，再点右上角「刷新」。";
  }

  function refreshControls() {
    model.nowMs = Date.now();
    const stale = PhoneModel.isStale(model.lastOkAt, model.nowMs);
    $("conn").textContent = PhoneModel.connText(model);
    $("conn").dataset.state = stale ? "off" : "ok";
    syncOffline(stale);
    $("stale-note").hidden = !stale;
    const refresh = $("btn-refresh");
    refresh.disabled = Boolean(model.flying);
    refresh.textContent = model.flying ? "刷新中…" : "刷新";
    /* 电脑没同意条款：手机停在缓存，不能开始也不能重新登录（与电脑同一道门，后端也会拦） */
    $("btn-start").disabled = !PhoneModel.canStart(model) || model.termsOk === false;
    $("btn-stop").hidden = !model.busy;
    $("btn-cancel-task").hidden = !model.busy;
    $("btn-relogin-submit").disabled = !PhoneModel.canSubmitRelogin(model, model.challenge);
    $("btn-relogin").disabled = Boolean(model.reloginStarting) || model.termsOk === false;
    /* 电脑上没保存账号或保存的密码不对：手机上露出账号密码输入 */
    const setup = model.reloginSetup || {};
    const account = $("relogin-account");
    if (account) account.hidden = !(model.reloginSetup && (!setup.saved || setup.paused));
    $("pending-note").hidden = !(model.pending && !model.pending.done);
    $("btn-cancel-start").hidden = !(model.pending && !model.pending.done);
    $("retry-hint").textContent = PhoneModel.retryHint(
      model.retry.retry_for_s, (model.items || []).some((i) => i.sign_end_ts));
  }

  function buildRow(list, item) {
    const li = document.createElement("li");
    const usable = PhoneModel.actionable(item);
    li.dataset.disabled = usable ? "0" : "1";
    const label = document.createElement("label");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = model.selected.indexOf(item.id) >= 0;
    box.disabled = !usable;
    box.addEventListener("change", () => {
      const at = model.selected.indexOf(item.id);
      if (box.checked && at < 0) model.selected.push(item.id);
      if (!box.checked && at >= 0) model.selected.splice(at, 1);
      refreshControls();
    });
    const span = document.createElement("span");
    const name = document.createElement("div");
    name.className = "name";
    name.textContent = PhoneModel.itemTitle(item);
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = PhoneModel.itemMeta(item);
    span.appendChild(name);
    span.appendChild(meta);
    label.appendChild(box);
    label.appendChild(span);
    li.appendChild(label);
    list.appendChild(li);
  }

  function renderItems() {
    model.nowMs = Date.now();
    const nowS = model.nowMs / 1000;
    const shown = PhoneModel.filterItems(model.items, model.filter, nowS);
    const buckets = { today: [], upcoming: [], signed: [] };
    shown.forEach((item) => buckets[PhoneModel.bucketOf(item, nowS)].push(item));
    [["items", buckets.today], ["upcoming-items", buckets.upcoming],
     ["signed-items", buckets.signed]].forEach(([id, items]) => {
      const list = $(id);
      if (!list) return;
      list.textContent = "";
      items.forEach((item) => buildRow(list, item));
    });
    const signedCount = (model.items || []).filter((i) => i.signed).length;
    if ($("signed-count")) $("signed-count").textContent = String(signedCount);
    $("empty").hidden = buckets.today.length > 0;
    if ($("upcoming-empty")) $("upcoming-empty").hidden = buckets.upcoming.length > 0;
    refreshControls();
  }

  function renderPlan() {
    const plan = model.plan;
    if (!plan) {
      $("plan-line").textContent = "未开始";
      return;
    }
    const tasks = plan.tasks || [];
    const lines = tasks.map((task) => PhoneModel.itemTitle(task) + "：" + PhoneModel.taskText(task));
    const source = String(plan.source || "") === "phone" ? "（从手机开始）" : "";
    /* 手机上运行中只能停止；修改计划要回电脑（设计第 10 节） */
    $("plan-line").textContent = (lines.join("；") || "计划进行中") + source + "。要修改计划，回电脑上改。";
  }

  function addLog(text) {
    const li = document.createElement("li");
    li.textContent = String(text || "");
    $("logs").appendChild(li);
    while ($("logs").childElementCount > 40) $("logs").removeChild($("logs").firstChild);
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
      const fresh = readCookie("campus_phone_csrf");
      if (fresh) model.csrf = fresh;
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
        if (resp.status === 401) onNeedPair();
        if (resp.status === 403) onForbidden(body);
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
      return { status: 0, body: { ok: false, error: "network",
                                 text: "连接中断，操作结果尚未确认；请刷新核对，避免重复操作" } };
    }
  }

  async function pair() {
    const code = String($("pair-code").value || "").trim();
    $("pair-error").textContent = "";
    if (!code) { $("pair-error").textContent = "请输入 6 位配对码"; return; }
    let answer;
    try {
      answer = await api("/pair", { method: "POST", body: { code } });
    } catch (err) {
      // 超时或断网：别让「配对」按下去毫无反应，也别把异常丢到控制台里
      $("pair-error").textContent = "配对失败：网络不通，请确认手机和电脑连的是同一个网络";
      return;
    }
    const { status, body } = answer;
    if (status !== 200 || !body.ok) {
      $("pair-error").textContent = "配对失败：" + String(body.text || body.error || status);
      return;
    }
    model.csrf = String(body.csrf || "");
    model.paired = true;
    $("pair").hidden = true;
    $("app").hidden = false;
    await poll(true);
  }

  /* ---- 轮询：按活动态自适应（进行中 2 秒、空闲 15 秒），失败按退避 ---- */
  async function poll(force) {
    if (model.flying) return;                     // 单飞：在途不重发
    if (!model.csrf) model.csrf = readCookie("campus_phone_csrf"); // 刷新后沿用旧会话的写权限
    model.flying = true;
    refreshControls();                            // 立刻把「刷新中…」显示出来
    try {
      const { status, body } = await api("/api/state?after=" + (force ? 0 : model.seq));
      if (status === 401) { onNeedPair(); return; }
      if (status === 403) { onForbidden(body); return; }
      if (status !== 200) { onPollFail(); return; }
      model.lastOkAt = Date.now();
      model.backoff = 1000;
      model.paired = true;
      // 状态能读到就说明会话还在：直接进主界面，不要求重新配对
      $("pair").hidden = true;
      $("app").hidden = false;
      // 读到新快照：过时门禁解除，但网络/403 的提示要留到下次明确覆盖
      clearStaleBanner();
      ingest(body || {});
    } catch (err) {
      onPollFail();
    } finally {
      model.flying = false;
      schedule();
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
    $("app").hidden = true;
    $("pair").hidden = false;
  }
  /* 403 不等于「没配对」：bad_csrf 是令牌和目标会话对不上（比如两个手机页同时开着，
     后打开的那个把 cookie 换了），bad_host/bad_origin 是请求被代理或中间层改写过。
     这两种都不该把用户赶回配对界面——他配过对，只是这次请求不合格。 */
  function onForbidden(body) {
    const code = String((body && body.error) || "");
    const fresh = readCookie("campus_phone_csrf");
    if (fresh) model.csrf = fresh;
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
  function ingest(payload) {
    if (payload.reset) {
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
    if (Array.isArray(state.activities)) model.items = state.activities;
    if (state.plan) model.plan = state.plan;
    if (typeof state.terms_ok === "boolean") model.termsOk = state.terms_ok;
    if (state.relogin_setup && typeof state.relogin_setup === "object") model.reloginSetup = state.relogin_setup;
    if (state.business_clock && typeof state.business_clock === "object") model.clockState = String(state.business_clock.state || "");
    if (typeof state.busy === "boolean") model.busy = state.busy;
    if (state.retry_options && Array.isArray(state.retry_options.choices)) {
      model.retryOptions = state.retry_options;
      fillRetryOptions(state.retry_options);
    }
    (payload.events || []).forEach((event) => {
      model.seq = Math.max(model.seq, Number(event.seq || 0));
      if (event.kind === "log") addLog((event.payload || {}).text || (event.payload || {}).detail || "");
      if (event.kind === "phone_relogin" && !state.login_relay) ingestRelogin(event.payload || {});
    });
    if (payload.seq) model.seq = Math.max(model.seq, Number(payload.seq));
    if (model.termsOk === false) {
      setBanner("电脑上还没同意使用条款：这里停在上次的结果，不能开始报名，也不能重新登录。", "terms");
    } else if (model.bannerKind === "terms") {
      /* 电脑上同意了：只收条款这一条，别的错误提示留着等明确覆盖 */
      setBanner("", "");
    }
    // 登录失效要在最上面说清楚：手机能看列表不代表电脑还能报名
    if (state.login && typeof state.login === "object") {
      const expired = !!state.login.session_expired || !state.login.session_present;
      const banner = $("login-expired-banner");
      if (banner) banner.hidden = !expired;
    }
    const syncLine = $("last-sync");
    if (syncLine) {
      const at = new Date();
      const hh = String(at.getHours()).padStart(2, "0");
      const mm = String(at.getMinutes()).padStart(2, "0");
      syncLine.textContent = "最近同步 " + hh + ":" + mm;
    }
    if (model.pending && !model.pending.done) void reconcile();
  }

  /* ---- 开始 / 停止 / 取消：未确认 start 用同一 request_id 只读对账 ---- */
  async function startPlan() {
    if (!canWrite()) { setBanner("状态已过时，先刷新再开始", "stale_action"); return; }
    const items = model.selected.map((id) => ({ id }));
    if (!items.length) return;
    if (model.pending && PhoneModel.startPending(model.pending, Date.now())) {
      setBanner("上一次开始还没核对完，请先等结果", "info");
      return;
    }
    const requestId = model.pending && !model.pending.done
      ? model.pending.request_id : PhoneModel.newRequestId();
    model.pending = { request_id: requestId, at: Date.now(), done: false };
    refreshControls();
    const { status, body } = await postAction({ action: "start_plan", args: {
      items, headed: false,
      retry_policy: { retry_for_s: Number(model.retry.retry_for_s),
                      max_attempts: Number(model.retry.max_attempts || 0) },
      request_id: requestId } });
    if (status === 401) return;
    if (body && body.ok && !body.pending) model.pending.done = true;
    else if (body && body.error) setBanner(String(body.text || body.error), "error");
    refreshControls();
    void poll(true);
  }
  async function reconcile() {
    if (model.reconciling) return;
    const requestId = model.pending && model.pending.request_id;
    if (!requestId) return;
    model.reconciling = true;
    try {
    const { body } = await postAction({
      action: "start_request_state", args: { request_id: requestId } });
    if (body && (body.state === "accepted" || body.state === "rejected"
                 || body.state === "canceled")) {
      model.pending.done = true;
      setBanner("");
    }
    if (body && body.state === "unknown") {
      setBanner("还没有查到开始结果。可点「取消等待」结束本次请求，再重新选择。", "info");
    }
    } finally {
      model.reconciling = false;
      refreshControls();
    }
  }
  async function cancelPendingStart() {
    if (!model.pending || model.pending.done || model.cancelingStart) return;
    if (!window.confirm("取消这次待确认的开始？已经启动的计划仍需点「停止计划」。")) return;
    const pending = model.pending;
    model.cancelingStart = true;
    try {
      const { body } = await postAction({action:"cancel_start_request",
        args:{request_id:pending.request_id}});
      if (body && body.ok && body.state === "canceled") {
        pending.done = true;
        setBanner("已取消这次开始，可以重新选择报名活动。", "info");
      } else {
        setBanner(String((body && (body.text || body.error)) || "取消结果尚未确认，请刷新核对"), "error");
      }
    } finally {
      model.cancelingStart = false;
      refreshControls();
    }
    if (model.paired) void poll(true);
  }
  async function stopPlan() {
    if (!window.confirm("确定停止这次计划？")) return;
    const planId = model.plan && model.plan.plan_id;
    if (!planId) return;
    const { body } = await postAction({ action: "stop_plan", args: { plan_id: planId } });
    if (body && body.error) {
      addLog("没能停止计划：" + String(body.text || body.error));
      return;
    }
    void poll(true);
  }
  /* 电脑窗口被隐藏到后台时，从这里把它叫回来：只发一个无参数动作，不动任何报名状态 */
  async function showComputerWindow() {
    const { status, body } = await postAction({ action: "show_window", args: {} });
    if (status !== 200 || (body && body.ok === false)) {
      addLog("没能显示电脑窗口：" + String((body && (body.text || body.error)) || status));
      return;
    }
    addLog("已请电脑把窗口显示出来");
  }
  async function cancelTask() {
    if (!window.confirm("确定取消这一场？")) return;
    const planId = model.plan && model.plan.plan_id;
    const task = (model.plan && model.plan.tasks || [])[0];
    if (!planId || !task) return;
    const { body } = await postAction({
      action: "cancel_task", args: { plan_id: planId, task_id: task.task_id } });
    if (body && body.error) {
      addLog("没能取消这一场：" + String(body.text || body.error));
      return;
    }
    void poll(true);
  }
  async function saveRetry() {
    const { body } = await postAction({ action: "save_retry_policy", args: {
      retry_policy: {
        retry_for_s: Number(model.retry.retry_for_s),
        max_attempts: Number(model.retry.max_attempts || 0) } } });
    if (body && body.error) addLog("没能保存重试设置：" + String(body.text || body.error));
  }
  function fillRetryOptions(options) {
    const sel = $("retry-for");
    sel.textContent = "";
    (options.choices || []).forEach((choice) => {
      const opt = document.createElement("option");
      opt.value = String(choice.value);
      opt.textContent = String(choice.label);
      sel.appendChild(opt);
    });
    sel.value = String(model.retry.retry_for_s);
  }

  /* ---- 重新登录 ---- */
  /* 流程结束（成功或中断）：收起整组验证码输入，只留"重新开始"入口 */
  function openReview() {
    if ($("btn-start").disabled) return;
    const picked = (model.items || []).filter((item) => model.selected.indexOf(item.id) >= 0);
    $("review-items").innerHTML = picked.map((item) => "<li>" + PhoneModel.escape(PhoneModel.itemTitle(item)) + "</li>").join("");
    $("review-policy").textContent = PhoneModel.retryHint(model.retry.retry_for_s, picked.some((i) => i.sign_end_ts));
    const warns = PhoneModel.preStartWarnings(model, picked);
    $("review-warns").innerHTML = warns.map((text) => "<li>" + PhoneModel.escape(text) + "</li>").join("");
    $("btn-review-start").textContent = warns.length ? "仍然开始报名计划" : "开始报名计划";
    $("review-panel").hidden = false;
  }

  function endReloginControls() {
    $("relogin-captcha-group").hidden = true;
    $("btn-relogin-submit").hidden = true;
    $("btn-relogin-refresh").hidden = true;
    $("btn-relogin-cancel").hidden = true;
    $("captcha").hidden = true;
    $("btn-relogin").hidden = false;
  }
  function ingestRelogin(info) {
    model.flow = info;
    if (String(info.mode || "") === "auto") {
      // 电脑自己认图：手机不给验证码，也就不可能和电脑抢同一张图。
      // 这里只报进度；连续失败到阈值后服务端会把 mode 换成 manual，图自然会来。
      const rounds = Math.max(Number(info.attempts || 0), Number(info.auto_failures || 0));
      if (info.retrying) {
        $("relogin-note").textContent = "电脑正在自动登录" +
          (rounds > 0 ? "（第 " + (rounds + 1) + " 次）" : "") + "…";
      } else {
        $("relogin-note").textContent =
          "电脑会自动识别验证码；连续失败几次之后才会转到这里手动输入";
      }
      model.challenge = null;
      model.reloginSubmitting = false;
      model.reloginStarting = false;
      $("relogin-captcha-group").hidden = true;
      $("captcha").hidden = true;
      $("captcha").removeAttribute("src");
      endReloginControls();
      refreshControls();
      return;
    }
    if (info.state === "waiting_code" && info.challenge_id) {
      if (PhoneModel.matchesChallenge(model.challenge, info.flow_id, info.challenge_id)) {
        // 对账同一张图：服务端确认没有在途提交才解除自锁，否则继续等着
        if (!info.submit_pending) model.reloginSubmitting = false;
        refreshControls();
        return;
      }
      model.challenge = {
        flow_id: info.flow_id, challenge_id: info.challenge_id,
      };
      model.reloginSubmitting = false;
      const img = $("captcha");
      if (String(info.image || "").indexOf("data:image/png;base64,") === 0) {
        img.src = info.image;
        img.hidden = false;
      } else {
        img.hidden = true;
        img.removeAttribute("src");
      }
      $("code").value = "";
      $("relogin-captcha-group").hidden = false;
      $("btn-relogin-submit").hidden = false;
      $("btn-relogin-refresh").hidden = false;
      $("btn-relogin-cancel").hidden = false;
      $("btn-relogin").hidden = true;
    } else if (info.state === "verifying") {
      // 提交已经被 worker 收下、正在校验：输入区必须留着但禁用，
      // 不能说成"结束"再让人对着同一张图重发一遍。
      model.reloginSubmitting = false;
      $("relogin-note").textContent = "正在校验验证码…";
      $("relogin-captcha-group").hidden = !model.challenge;
      $("captcha").hidden = !model.challenge;
      $("btn-relogin-submit").hidden = false;
      $("btn-relogin-refresh").hidden = false;
      $("btn-relogin-cancel").hidden = false;
      $("btn-relogin").hidden = true;
    } else if (info.state === "starting") {
      // 进程刚起来还没出验证码：既不是结束也没有可提交的图
      model.reloginSubmitting = false;
      $("relogin-note").textContent = "正在准备验证码…";
    } else if (info.state === "success") {
      model.challenge = null;
      model.reloginSubmitting = false;
      endReloginControls();
      if (info.live) {
        /* 计划在跑：成功的意义是计划照常往下走（设计 9.3，与电脑同一句） */
        $("relogin-note").textContent = model.busy ? "重新登录成功，报名计划照常继续" : "重新登录成功，正在刷新列表";
        void poll(true);
      } else {
        // 中继在空闲时会回上一场的结论：那是历史，不是这一次。只按 live 播报，
        // 否则每次打开手机页都会把很早以前那一次成功再演一遍。
        $("relogin-note").textContent = "上次重新登录已完成；需要时点「重新登录」再试";
      }
    } else if (info.state === "failed" || info.state === "canceled") {
      model.challenge = null;
      model.reloginSubmitting = false;
      endReloginControls();
      const reason = String(info.safe_error || info.state);
      $("relogin-note").textContent = info.live
        ? "重新登录结束：" + reason
        : "上次重新登录未完成：" + reason;
    } else if (info.state && info.state !== "waiting_code") {
      // idle 表示「本来就没有在进行的重新登录」，不是一次结束：写成「重新登录结束：idle」
      // 会把上一次真正的原因（比如 bad_csrf、凭据没准备好）盖成一句空话。
      model.challenge = null;
      model.reloginSubmitting = false;
      endReloginControls();
    }
    refreshControls();
  }
  async function beginRelogin() {
    // 单飞：连点两下也只是同一次开始，不会发出第二个 POST
    if (model.reloginStarting) return;
    if (!canWrite()) { setBanner("状态已过时，先刷新再重新登录", "stale_action"); return; }
    model.reloginStarting = true;
    refreshControls();
    /* 手机上输了账号密码就带上（默认不保存，勾选才保存到电脑）；没输就用电脑上保存的 */
    const args = {};
    const account = $("relogin-account");
    if (account && !account.hidden) {
      const user = String(($("relogin-user") || {}).value || "").trim();
      const pass = String(($("relogin-pass") || {}).value || "");
      if (!user || !pass) {
        model.reloginStarting = false;
        $("relogin-note").textContent = "账号和密码都要填。";
        refreshControls();
        return;
      }
      args.username = user;
      args.password = pass;
      args.save = !!($("relogin-save") || {}).checked;
      $("relogin-pass").value = "";
    }
    const { body } = await postAction({ action: "phone_relogin_begin", args: args });
    model.reloginStarting = false;
    if (!body || !body.ok) {
      $("relogin-note").textContent = body && body.error === "plan_late"
        ? "现在来不及重新登录：" + String(body.text || "有场次正在提交，或者离开放不到 100 秒。")
        : "还不能开始：" + String((body && body.text) || (body && body.error) || "请到电脑上准备账号");
      refreshControls();
      return;
    }
    if (String(body.mode || "") === "auto") {
      // 电脑接手了：手机不进入验证码流程，只等快照回报进度
      $("relogin-note").textContent = "电脑正在自动登录，手机上不用再操作";
      refreshControls();
      void poll(true);
      return;
    }
    $("relogin-note").textContent = "等待验证码…";
    refreshControls();
    void poll(true);
  }
  async function submitRelogin() {
    const code = String($("code").value || "").trim();
    if (!model.flow || !model.challenge) return;
    if (!PhoneModel.canSubmitRelogin(model, model.challenge)) return;
    if (!PhoneModel.matchesChallenge(model.flow, model.challenge.flow_id,
                                     model.challenge.challenge_id)) {
      $("relogin-note").textContent = "验证码已换代，请看新图";
      $("code").value = "";
      return;
    }
    model.reloginSubmitting = true;
    refreshControls();
    let result;
    try {
      result = await api("/api/action", { method: "POST",
        body: { action: "phone_relogin_submit", args: {
          flow_id: model.challenge.flow_id,
          challenge_id: model.challenge.challenge_id, code } } });
    } catch (err) {
      // 结果未知：既不能当成功也不能当失败。保持禁用，先对账问服务端
      // 这张图到底有没有在途提交，等快照给结论再决定放行还是收口。
      $("relogin-note").textContent = "提交结果未知，正在对账…";
      void poll(true);
      return;
    }
    if (!result || result.status !== 200 || !result.body || !result.body.ok) {
      const error = String((result && result.body && result.body.error) || "");
      if (error === "duplicate_submit") {
        // 服务端说同一张图还有在途提交：别解锁，等它的结论再放行
        $("relogin-note").textContent = "验证码正在提交，请等待结果";
        void poll(true);
        return;
      }
      model.reloginSubmitting = false;
      $("relogin-note").textContent = String(
        (result && result.body && (result.body.text || result.body.error))
          || "提交没有被接受");
      refreshControls();
      return;
    }
    $("code").value = "";
    void poll(true);
  }
  async function cancelRelogin() {
    const flowId = model.flow && model.flow.flow_id;
    const { body } = await postAction({
      action: "phone_relogin_cancel", args: { flow_id: flowId || "" } });
    if (body && body.error) {
      // 取消没发出去就不能假装已经取消：留着旧图，让用户重试
      addLog("没能取消这次重新登录：" + String(body.text || body.error));
      return false;
    }
    model.challenge = null;
    $("captcha").hidden = true;
    void poll(true);
    return true;
  }
  /* 换一张图 = 取消旧场 + 开始新场；旧场不撤掉会被服务端判成同一个挑战 */
  async function refreshRelogin() {
    const canceled = await cancelRelogin();
    // 旧场没撤掉就开新场，服务端会判成同一个挑战：宁可不换图
    if (canceled === false) return;
    await beginRelogin();
  }

  function wire() {
    $("btn-pair").addEventListener("click", () => void pair());
    $("btn-refresh").addEventListener("click", () => void poll(true));
    /* 开始前先核对计划：列出已选场次、尝试设置和开始前提醒，确认后才真的开始 */
    $("btn-start").addEventListener("click", () => openReview());
    $("btn-review-start").addEventListener("click", () => { $("review-panel").hidden = true; void startPlan(); });
    $("btn-review-back").addEventListener("click", () => { $("review-panel").hidden = true; });
    $("btn-stop").addEventListener("click", () => void stopPlan());
    $("btn-cancel-start").addEventListener("click", () => void cancelPendingStart());
    $("btn-cancel-task").addEventListener("click", () => void cancelTask());
    if ($("btn-show-window")) {
      $("btn-show-window").addEventListener("click", () => void showComputerWindow());
    }
    $("btn-relogin").addEventListener("click", () => void beginRelogin());
    $("btn-relogin-submit").addEventListener("click", () => void submitRelogin());
    $("btn-relogin-cancel").addEventListener("click", () => void cancelRelogin());
    $("btn-relogin-refresh").addEventListener("click", () => void refreshRelogin());
    $("q").addEventListener("input", () => { model.filter.q = $("q").value; renderItems(); });
    document.querySelectorAll("[data-status]").forEach((btn) => {
      btn.addEventListener("click", () => {
        model.filter.status = btn.dataset.status;
        document.querySelectorAll("[data-status]").forEach((other) =>
          other.setAttribute("aria-pressed", other === btn ? "true" : "false"));
        renderItems();
      });
    });
    document.querySelectorAll("[data-time]").forEach((btn) => {
      btn.addEventListener("click", () => {
        model.filter.time = btn.dataset.time;
        document.querySelectorAll("[data-time]").forEach((other) =>
          other.setAttribute("aria-pressed", other === btn ? "true" : "false"));
        renderItems();
      });
    });
    $("retry-for").addEventListener("change", () => {
      model.retry.retry_for_s = Number($("retry-for").value);
      void saveRetry();
      refreshControls();
    });
    $("max-attempts").addEventListener("change", () => {
      model.retry.max_attempts = Number($("max-attempts").value || 0);
      void saveRetry();
    });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        if (model.pollTimer) clearTimeout(model.pollTimer);
        model.pollTimer = null;
      } else if (model.paired) {
        void poll(false);       // 回前台立刻补一次，仍按事件游标补齐
      }
    });
    if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
      window.addEventListener("pagehide", () => {
        if (model.pollTimer) clearTimeout(model.pollTimer);
        model.pollTimer = null;
      });
      window.addEventListener("pageshow", () => {
        if (!document.hidden && model.paired) void poll(false); // bfcache 恢复后按游标补齐
      });
    }
    probeExistingSession();
    refreshControls();
  }

  globalThis.PhoneUI = { model, poll, wire, renderItems, refreshControls,
                         ingest, startPlan, cancelPendingStart, submitRelogin, beginRelogin,
                         cancelRelogin, refreshRelogin, showComputerWindow };
  if (document.readyState !== "loading") wire();
  else document.addEventListener("DOMContentLoaded", wire);
}
