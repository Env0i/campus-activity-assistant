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

  /* 状态过时：30 秒没有新快照 pill 就不再算「已连接」。
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

  /* 过时/忙/空选都禁开始；时钟完全不可用也禁（EX06，决策 012「时钟不可用时不能开始报名」，
     与电脑端开始门禁同一口径）；停止始终可点。
     A-BUG-4：快照声称 ready/holdover 但投影不出可信时刻（business_clock 字段缺失
     得不到 clock 对象、或 holdover 样本已超 900 秒）时同样拦——决策 012：时间
     不可信不能开始；syncing 档仍由服务端拦，前端不额外拦 */
  canStart(model) {
    if (!model || PhoneModel.isStale(model.lastOkAt, model.nowMs)) return false;
    if (model.busy) return false;
    if (model.clockState === "unavailable") return false;   // EX06：快照明说不可用才拦，syncing 由服务端拦
    if ((model.clockState === "ready" || model.clockState === "holdover")
        && PhoneModel.businessNowS(model) === null) return false;   // A-BUG-4
    return (model.selected || []).length > 0;
  },
  /* 登录是否已失效（EX02）：session_expired 或快照明说没有会话；与 loginLine/ingest 同一口径 */
  loginExpired(login) {
    return !!login && (!!login.session_expired || login.session_present === false);
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

  /* 0 模式缺截止：老实提示 2 分钟兜底。
     SH01 fhint（原型 Phone.dc.html:917 逐字，含句号）：两句只差模式，标签由 review-policy 承载 */
  retryHint(mode, hasSignEnd) {
    if (Number(mode) === 0 && !hasSignEnd) return "缺报名截止时间的场次，本次最多 2 分钟。";
    if (Number(mode) === -1) return "自动延长，最多 25 分钟；报名截止仍是硬上限。";
    return "";
  },

  /* 未确认 start：同 request_id 只读对账；对账窗内不重复，超时也不清 pending。
     A-BUG-1：终态要带原因（outcome）——canceled/rejected 已有结论，立即放行新的
     开始；accepted 仍保留 15 秒窗口防双击（计划可能已开跑，等快照接管 busy） */
  startPending(pending, nowMs) {
    if (!pending) return false;
    if (pending.done && (pending.outcome === "canceled"
                         || pending.outcome === "rejected")) return false;
    return (Number(nowMs) - Number(pending.at || 0)) < PhoneModel.PENDING_WINDOW_MS
      || !pending.done;
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
  /* items 可选：给了就同时按已报名活动的举办时间挡掉重叠的行（电脑上 signedClash 同一规则） */
  actionable(item, items) {
    if (!item || item.signed) return false;
    if (!item.open_ts && !item.sign_start) return false;      // 时间未知不可执行
    if (item.closed) return false;                            // 已截止不可执行
    if (items && PhoneModel.signedClash(item, items)) return false;   // 与已报名重叠：不可加入
    return true;
  },

  /* ---------------- 冲突原因、跨天时段、报后可退、可取消至（计划 20261107-conflict-cancel，fe-phone-page） ----------------
   * 与电脑端 state/conflict.js 同一套规则、同一批文案（原型 Phone.dc.html 的 whyOf / spanAbs）；
   * 手机上只读：没有取消按钮，不调任何写操作，只说去哪取消。时间只认学校时区（UTC+8）与电脑给的北京时间快照。 */
  WJ: "\u2060",   // U+2060：连住「（跨N天）」「这一场报不了。」「学校网站取消。」，避免孤字换行
  glue(text) { return Array.from(String(text)).join(PhoneModel.WJ); },
  /* 学校时间文本 → epoch 秒；非法 / 空返回 null */
  schoolSec(text) {
    const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})$/.exec(String(text || "").trim());
    if (!m) return null;
    const [y, mo, d, h, mi, s] = m.slice(1).map(Number);
    if (mo < 1 || mo > 12 || d < 1 || d > 31 || h > 23 || mi > 59 || s > 59) return null;
    const utc = Date.UTC(y, mo - 1, d, h, mi, s);
    const back = new Date(utc);
    if (back.getUTCMonth() !== mo - 1 || back.getUTCDate() !== d) return null;   // 2 月 30 日不滚成 3 月
    return utc / 1000 - 8 * 3600;
  },
  pad2(n) { return String(n).padStart(2, "0"); },
  /* 「11月8日 22:40」：与电脑列表同一写法，不带秒 */
  absWhen(sec) {
    const d = new Date((sec + 8 * 3600) * 1000);
    return (d.getUTCMonth() + 1) + "月" + d.getUTCDate() + "日 "
      + PhoneModel.pad2(d.getUTCHours()) + ":" + PhoneModel.pad2(d.getUTCMinutes());
  },
  dayOf(sec) { return Math.floor((sec + 8 * 3600) / 86400); },
  /* 结束恰为 00:00 按前一天算 */
  endsAtMidnight(start, end) { return end > start && (end + 8 * 3600) % 86400 === 0; },
  lastDayOf(start, end) {
    return PhoneModel.dayOf(PhoneModel.endsAtMidnight(start, end) ? end - 1 : end);
  },
  /* 举办时段：{s, e}（epoch 秒）；缺失或结束不晚于开始返回 null */
  actRange(item) {
    const s = PhoneModel.schoolSec(item && item.act_start);
    const e = PhoneModel.schoolSec(item && item.act_end);
    return s !== null && e !== null && e > s ? { s, e } : null;
  },
  spanDays(item) {
    const r = PhoneModel.actRange(item);
    return r ? PhoneModel.lastDayOf(r.s, r.e) - PhoneModel.dayOf(r.s) + 1 : null;
  },
  /* 绝对日期时段：同一天「11月9日 08:00–17:00」，跨天「… – …（跨N天）」。行内与原因面板共用 */
  actSpan(item) {
    const r = PhoneModel.actRange(item);
    if (!r) return "";
    const n = PhoneModel.spanDays(item);
    if (n <= 1) {
      const end = PhoneModel.endsAtMidnight(r.s, r.e) ? "24:00" : PhoneModel.absWhen(r.e).split(" ")[1];
      return PhoneModel.absWhen(r.s) + "–" + end;
    }
    const W = PhoneModel.WJ;
    return PhoneModel.absWhen(r.s) + " – " + PhoneModel.absWhen(r.e) + "（" + W + "跨" + W + n + W + "天" + W + "）";
  },
  /* 电脑给的北京时间快照 → 此刻的业务北京时间（秒）。没有可信快照返回 null，不读手机时钟 */
  mono() {
    return (typeof performance !== "undefined" && performance && typeof performance.now === "function")
      ? performance.now() : Date.now();
  },
  setClock(model, snap) {
    const s = snap && typeof snap === "object" ? snap : {};
    const epoch = Number(s.epoch_s);
    const tick = Number(s.tick_s);
    const sampled = Number(s.sampled_tick_s);
    const ok = [epoch, tick, sampled].every(Number.isFinite)
      && (s.state === "ready" || s.state === "holdover");
    model.clock = ok ? { epochAtSampleS: epoch + (sampled - tick), monoAt: PhoneModel.mono(),
                         ageS: Number.isFinite(Number(s.age_s)) ? Math.max(0, Number(s.age_s)) : 0 } : null;
  },
  businessNowS(model) {
    const c = model && model.clock;
    if (!c) return null;
    const elapsed = (PhoneModel.mono() - c.monoAt) / 1000;
    if (!Number.isFinite(elapsed) || elapsed < 0 || c.ageS + elapsed > 900) return null;   // 超过 900 秒不可信
    return c.epochAtSampleS + elapsed;
  },
  /* 取消窗口：现在在 [报名开始, 报名截止] 内 true；时钟不可用或没有截止返回 null */
  cancelWindowOpen(item, nowS) {
    const end = PhoneModel.schoolSec(item && item.sign_end);
    if (nowS === null || nowS === undefined || end === null) return null;
    const start = PhoneModel.schoolSec(item.sign_start);
    if (start !== null && nowS < start) return false;
    return nowS <= end;
  },
  /* 与已报名活动举办时间重叠的那一场（半开区间，与电脑 signedClash 同一规则）。
   * 已报名、已截止的行本身不算；没有完整举办时段的行无从判断，不算 */
  signedClash(item, items) {
    if (!item || item.signed || item.closed) return null;
    const a = PhoneModel.actRange(item);
    if (!a) return null;
    return (items || []).find((other) => {
      if (!other || !other.signed || other.id === item.id) return false;
      const b = PhoneModel.actRange(other);
      return !!b && a.s < b.e && b.s < a.e;
    }) || null;
  },
  /* 报后可退 / 报后不可退：未报名、未截止的行；cancel_allowed 为 null 或缺失时不写 */
  refundFlag(item) {
    if (!item || item.signed || item.closed) return null;
    if (item.cancel_allowed === false) return { text: "报后不可退", no: true };
    if (item.cancel_allowed === true) return { text: "报后可退", no: false };
    return null;
  },
  /* 奖励（实践分 / 虚拟工资，原型 Phone.dc.html:485 的 rwText）：和签到信息来自同一次
   * 详情请求。详情没回来是「同步中」，回来了但学校没给才是「未公布」；0 是真实回答，照实写 0。 */
  rewardText(item) {
    if (!item) return null;
    if (String(item.reward_state || "") !== "ready") {
      return { cls: "rw p", text: "奖励同步中" };
    }
    const num = (value) => {
      if (value === null || value === undefined || value === "") return "";
      const n = Number(value);
      return Number.isFinite(n) ? String(n) : "";
    };
    const pts = num(item.points);
    const wage = num(item.wage);
    return {
      cls: "rw",
      text: (pts ? pts + " 分" : "分未公布") + " · " + (wage ? "工资 " + wage : "工资未公布"),
    };
  },
  /* 已报名且还能取消的行：只说去哪取消，手机上没有取消按钮 */
  cancelNote(item, nowS) {
    if (!item || !item.signed || item.cancel_allowed !== true) return "";
    if (PhoneModel.cancelWindowOpen(item, nowS) !== true) return "";
    return "可取消至 " + PhoneModel.absWhen(PhoneModel.schoolSec(item.sign_end)) + "，在电脑上或" + PhoneModel.glue("学校网站取消。");
  },
  /* 解除路径四选一（与电脑气泡同文案） */
  clashWay(sg, nowS) {
    const nm = "「" + sg.name + "」";
    const open = PhoneModel.cancelWindowOpen(sg, nowS);
    const end = PhoneModel.schoolSec(sg.sign_end);
    if (sg.cancel_allowed === true && open === true) {
      return { kind: "a", hasGo: true, text: "想报这一场，要先取消" + nm + "的报名，" + PhoneModel.absWhen(end) + " 前可以取消。" };
    }
    if (sg.cancel_allowed === false) {
      return { kind: "b", hasGo: false, text: nm + "报名后不能取消，" + PhoneModel.glue("这一场报不了。") };
    }
    if (sg.cancel_allowed === true && open === false) {
      return { kind: "c", hasGo: false, text: nm + "的取消时间已过（截至 " + PhoneModel.absWhen(end) + "），" + PhoneModel.glue("这一场报不了。") };
    }
    return { kind: "d", hasGo: false, text: nm + "能不能取消还没查到，刷新后再看。" };
  },
  /* 原因面板的数据：两个时段、时间条（日序号换成百分比）和解除路径 */
  whyView(item, sg, nowS) {
    const a = PhoneModel.actRange(sg);
    const b = PhoneModel.actRange(item);
    const lo = Math.min(PhoneModel.dayOf(a.s), PhoneModel.dayOf(b.s));
    const hi = Math.max(PhoneModel.lastDayOf(a.s, a.e), PhoneModel.lastDayOf(b.s, b.e));
    const n = hi - lo + 1;
    const base = lo * 86400 - 8 * 3600;
    const pc = (t) => Math.round((t - base) / (n * 86400) * 10000) / 100;
    const ov0 = Math.max(a.s, b.s);
    const ov1 = Math.min(a.e, b.e);
    const days = [];
    const cuts = [];
    for (let k = 0; k < n; k += 1) {
      const d = new Date((lo + k) * 86400000);
      days.push((d.getUTCMonth() + 1) + "月" + d.getUTCDate() + "日");
      if (k) cuts.push(pc(base + k * 86400));
    }
    const sparse = days.length > 7;
    const way = PhoneModel.clashWay(sg, nowS);
    return {
      title: "和已报名的活动时间重叠",
      rows: [{ label: "已报名", name: sg.name, span: PhoneModel.actSpan(sg) },
             { label: "这一场", name: item.name, span: PhoneModel.actSpan(item) }],
      cuts: sparse ? [] : cuts, days: sparse ? [days[0], days[days.length - 1]] : days,
      ovL: pc(ov0), ovW: pc(ov1) - pc(ov0), aL: pc(a.s), aW: pc(a.e) - pc(a.s), bL: pc(b.s), bW: pc(b.e) - pc(b.s),
      aria: "时间线：" + PhoneModel.absWhen(a.s) + " 起的已报名活动与这一场在 " + PhoneModel.absWhen(ov0) + " 到 " + PhoneModel.absWhen(ov1) + " 重叠",
      way: way.text, wayKind: way.kind, hasGo: way.hasGo,
    };
  },
  /* 点按展开 / 收起原因：一次只开一条（再点同一行收起，点另一行上一条自动收起） */
  toggleWhy(model, id) {
    model.whyId = model.whyId === id ? "" : id;
    return model.whyId;
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
  /* 开始前提醒（SH02，原型 pwList，Phone.dc.html:912-916，只提醒不拦）：
   * 三支句式逐字照原型——缺截止（retry=0，原型 pwNe 只点第一场）、等待久
   * （pwHas=saved&&!paused：有保存账号→「没装验证码识别/输验证码」，没有→
   * 「没开自动登录/重新登录」；保存的密码不对并入「没有」支，语义等价）、
   * 24 小时。开放间隔仍用后端给的 seconds_to_open，不读手机时钟；
   * holdover 一句原型 reviewwarn 板没画但电脑端有，保留（记 deviation）。 */
  preStartWarnings(model, picked) {
    const list = [];
    if (model && model.clockState === "holdover") list.push("北京时间在用上次的校准结果，电脑会自动重新校准。");
    const setup = (model && model.reloginSetup) || {};
    const pwHas = !!setup.saved && !setup.paused;
    const ocrOn = !!setup.ocr_ready;
    if (model && model.retry && Number(model.retry.retry_for_s) === 0) {
      const noEnd = (picked || []).filter((i) => !i.sign_end && !i.sign_end_ts);
      if (noEnd.length) {
        list.push("「" + PhoneModel.itemTitle(noEnd[0]) + "」没给报名截止时间，“直到报名截止”对它只会尝试 2 分钟。");
      }
    }
    const pre = (picked || []).filter((i) => Number(i.seconds_to_open) > 0);
    if (pre.length) {
      const latest = Math.max.apply(null, pre.map((i) => Number(i.seconds_to_open)));
      /* {HH:MM}：优先场次自带的 sign_start（北京时间文本，不依赖时钟）；
         缺文本时退回业务此刻 + seconds_to_open 投影，两者都拿不到就不出这句（不编时刻） */
      const last = pre.reduce((a, b) =>
        (Number(b.seconds_to_open) > Number(a.seconds_to_open) ? b : a));
      const nowS = PhoneModel.businessNowS(model);
      const open = PhoneModel.openEpochOf(last)
        || (nowS !== null ? nowS + Number(last.seconds_to_open) : 0);
      /* UI-F4（原型 pwHas 句 hms(pwLast).slice(0,-3)，Phone:915）：目标时刻带
         明天/后天 日前缀，丢前缀会把「明天 09:00」说成「09:00」；时钟不可用
         时算不了日偏移，退回当天时刻（不带前缀，也不拿手机墙钟编日子） */
      const when = open > 0 ? (nowS !== null
        ? PhoneModel.hmsAt(open, nowS).slice(0, -3).replace(/^(\d)/, " $1")
        : PhoneModel.hhmmss(PhoneModel.beijingSecOf(open)).slice(0, 5).replace(/^(\d)/, " $1"))
        : "";
      if (latest > 3600 && !(pwHas && ocrOn) && when) {
        list.push("要等到" + when + "，" + (pwHas ? "电脑上没装验证码识别" : "电脑上没开自动登录")
          + "。中途登录失效要你" + (pwHas ? "输验证码" : "重新登录")
          + "；开放前 100 秒内失效，那场就结束。");
      }
      if (latest > 86400) list.push("有场次在 24 小时后才开放，电脑要开着、不能睡眠。");
    }
    return list;
  },
  /* 顶栏 pill 三态（G01/G13，原型 Phone:923）：ok 已连接 / off 离线 / stale 同步中。
     stale 是 G13 接通的档：数据过时但没在重试，pill 显示「同步中」并留 stale 数据提示；
     正在重试（offlineTries>0）或从没连上过才是「离线」。渲染层只写 data-state 与文案。 */
  connState(model, flying) {
    if (flying) return { state: "busy", text: "同步中" };
    if (!model || !PhoneModel.isStale(model.lastOkAt, model.nowMs)) {
      return { state: "ok", text: "已连接" };
    }
    if (!model.lastOkAt || Number(model.offlineTries) > 0) {
      return { state: "off", text: "离线" };
    }
    return { state: "stale", text: "同步中" };
  },

  /* 底栏副题（G02/LD01 先照原型补）：已选场按开放状态分「立即报名 / 预报名」两档计数，
     同原型 review sheet 上方的 summary 句式；开放状态按 businessNowS 判定，不读手机时钟 */
  planSummary(items, nowS) {
    const list = items || [];
    let instant = 0;
    list.forEach((item) => {
      const open = PhoneModel.openEpochOf(item);
      if (open > 0 && nowS !== null && nowS !== undefined && open <= nowS) instant += 1;
    });
    const pre = list.length - instant;
    return [instant ? instant + " 场立即报名" : "", pre ? pre + " 场预报名" : ""]
      .filter(Boolean).join("，");
  },

  /* ---------------- 列表与详情（计划 20261108-phone-1to1 任务 list-detail；G05 G07 G08 G09 LD01–LD04） ----------------
   * 开放状态、分组、距开放、段钮计数全部在前端聚合（原型 renderVals 的 groups/count 段，
   * Phone.dc.html:704-765/931），渲染函数只做 DOM。时刻与倒计时只用 businessNowS，
   * 不读手机墙钟（决策 012）；分组的日历日在时钟不可用时退回手机墙钟——只影响归组，
   * 不产生任何倒计时。 */

  /* 原型 hhmmss/hms/leftCn（Phone.dc.html:359-376）逐字照抄；原型的 open 是「当天秒数」，
   * 我们是 epoch 秒，所以统一经 beijingSecOf / hmsAt 换算后再进这两个函数 */
  hhmmss(v) {
    if (v < 0) v = 0;
    const p = (n) => (n < 10 ? "0" : "") + n;
    return p(Math.min(99, Math.floor(v / 3600))) + ":" + p(Math.floor(v % 3600 / 60)) + ":"
      + p(Math.floor(v % 60));
  },
  /* epoch 秒 → 北京时间当天的秒数（原型数据 open 就是这个口径） */
  beijingSecOf(epochS) {
    return (((Number(epochS) || 0) + 8 * 3600) % 86400 + 86400) % 86400;
  },
  hms(v) {
    const d = Math.floor(v / 86400), x = ((v % 86400) + 86400) % 86400;
    const t = PhoneModel.hhmmss(x);
    return d > 0 ? (d === 1 ? "明天 " : (d === 2 ? "后天 " : d + " 天后 ")) + t : t;
  },
  /* 「目标时刻」的 capB（原型 hms(open) 的等价换算）：按业务此刻算日偏移，出「明天 09:00:00」这类 */
  hmsAt(epochS, nowS) {
    const b = (Number(nowS) || 0) + 8 * 3600;
    const midnight = b - (b % 86400) - 8 * 3600;
    return PhoneModel.hms((Number(epochS) || 0) - midnight);
  },
  /* G05 距开放（原型 leftCn，Phone.dc.html:369-376）：≥10 小时取整小时，不足 1 小时带秒 */
  leftCn(v) {
    if (v < 0) v = 0;
    const h = Math.floor(v / 3600), m = Math.floor(v % 3600 / 60), s = Math.floor(v % 60);
    if (h >= 10) return Math.round(v / 3600) + " 小时后";
    if (h > 0) return h + " 时 " + m + " 分";
    if (m > 0) return m + " 分 " + s + " 秒";
    return s + " 秒";
  },
  /* 开放状态（原型 stOf，Phone.dc.html:489-493）：signed → closed（报名截止已过，与电脑
   * classify_signup_mode 同一口径）→ open（已到开放时刻）→ pre → unknown（待公布）。
   * 时钟不可用（nowS 为 null）时分辨不出 open/closed，按 pre/unknown 呈现「待校准」，
   * 不在没有可信时钟时假装「已开放」 */
  stOf(item, nowS) {
    if (!item || item.signed) return "signed";
    if (item.closed) return "closed";
    const open = PhoneModel.openEpochOf(item);
    if (nowS !== null && nowS !== undefined) {
      const end = PhoneModel.schoolSec(item && item.sign_end);
      if (end !== null && nowS >= end) return "closed";
      if (open > 0 && nowS >= open) return "open";
    }
    return open > 0 ? "pre" : "unknown";
  },
  /* G07 分组（原型 groups 构建的组名序，Phone.dc.html:728-731）：今天/明天/后天按
   * openEpochOf 的北京时间日历日（dayOf 即 UTC+8 日序）与业务此刻比对；原型只演示到后天，
   * 真实列表有更晚的场次，归入「更晚开放」（沿用既有空态句的措辞），不丢行 */
  groupKeyOf(item, st, nowS, wallS) {
    if (st === "signed") return "已报名";
    if (st === "open") return "正在开放";
    if (st === "closed") return "已截止";
    if (st === "unknown") return "待公布";
    const base = nowS !== null && nowS !== undefined ? nowS : wallS;
    const diff = PhoneModel.dayOf(PhoneModel.openEpochOf(item)) - PhoneModel.dayOf(base);
    if (diff === 1) return "明天";
    if (diff === 2) return "后天";
    if (diff >= 3) return "更晚开放";
    return "今天";   // diff <= 0：开放日就是今天或已过（只在时钟不可用时出现）
  },
  /* G08 段钮可见集（原型 visible 过滤的 seg 分支，Phone.dc.html:721-722）：
   * 「可报名」= 开放状态 open/pre，与段钮计数同一口径；关键词与时间档沿用 filterItems */
  visibleItems(items, filter, nowS) {
    const status = (filter && filter.status) || "all";
    return PhoneModel.filterItems(items, { q: filter && filter.q, time: filter && filter.time, status: "all" }, nowS)
      .filter((item) => {
        const st = PhoneModel.stOf(item, nowS);
        if (status === "free") return st === "open" || st === "pre";
        if (status === "signed") return st === "signed";
        return true;
      });
  },
  /* 与某场举办时段重叠的第一场（G05 行警 / LD04 的 hitSel；半开区间同 signedClash） */
  overlapFirst(item, others) {
    const a = PhoneModel.actRange(item);
    if (!a) return null;
    return (others || []).find((other) => {
      if (!other || other.id === item.id) return false;
      const b = PhoneModel.actRange(other);
      return !!b && a.s < b.e && b.s < a.e;
    }) || null;
  },
  /* LD04 勾选冲突提示条（原型 toggle 的 notice，Phone.dc.html:700） */
  conflictNotice(item, hit) {
    return "「" + ((item && item.name) || "") + "」与「" + ((hit && hit.name) || "")
      + "」的活动时间重叠，只能选其中一场。已保留原选择。";
  },
  /* 勾选一场：撞上已选场就保留原选择并回提示，选成/取消都清提示（原型 toggle） */
  pickItem(selected, items, id, on) {
    const keep = (selected || []).slice();
    if (!on) return { selected: keep.filter((x) => x !== id), notice: "" };
    const it = (items || []).find((i) => i && i.id === id);
    if (!it) return { selected: keep, notice: "" };
    const picked = keep.map((x) => (items || []).find((i) => i && i.id === x)).filter(Boolean);
    const hit = PhoneModel.overlapFirst(it, picked);
    if (hit) return { selected: keep, notice: PhoneModel.conflictNotice(it, hit) };
    return { selected: keep.concat(id), notice: "" };
  },
  /* G05/LD02 的「下一场」（原型 nextPreId/nextIt，Phone.dc.html:711-713）：
   * 未报名且不与已报名重叠的最早 pre 场；详情卡优先给已开放的那场 */
  nextPick(items, nowS) {
    const list = items || [];
    const eligible = list.filter((i) => PhoneModel.stOf(i, nowS) === "pre"
      && !PhoneModel.signedClash(i, list))
      .sort((a, b) => PhoneModel.openEpochOf(a) - PhoneModel.openEpochOf(b));
    const openIt = list.filter((i) => PhoneModel.stOf(i, nowS) === "open"
      && !PhoneModel.signedClash(i, list))[0] || null;
    const nextIt = openIt || eligible[0] || null;
    return { nextPreId: eligible.length ? eligible[0].id : "", nextIt: nextIt,
             isOpen: !!nextIt && PhoneModel.stOf(nextIt, nowS) === "open" };
  },
  /* G05 行呈现（原型 rows.map 的行对象，Phone.dc.html:738-762）：时刻大字 + 距开放 +
   * 旗标 + 时段/地点/奖励 + 行警；全部是纯数据，渲染层只建元素 */
  rowView(item, ctx) {
    const nowS = ctx.nowS;
    const st = PhoneModel.stOf(item, nowS);
    const selected = (ctx.selected || []).indexOf(item.id) >= 0;
    const hitSigned = st !== "signed" ? PhoneModel.signedClash(item, ctx.items) : null;
    const hitSel = !selected && (st === "open" || st === "pre")
      ? PhoneModel.overlapFirst(item, (ctx.selected || [])
          .map((x) => (ctx.items || []).find((i) => i && i.id === x)).filter(Boolean))
      : null;
    const clash = !!hitSigned && (st === "open" || st === "pre");
    /* TM01（原型 disabled 的 !s.termsOk 项，Phone.dc.html:742）：条款未同意列表行全禁用 */
    const termsOff = ctx.termsOk === false;
    const disabled = !!ctx.busy || termsOff || st === "signed" || st === "closed"
      || st === "unknown" || !!hitSigned;
    const dimmed = termsOff || st === "signed" || st === "closed" || st === "unknown";
    const flags = [];
    if (st === "open") flags.push({ text: "立即报名", cls: "warn" });            // Phone:744
    if (st === "pre") flags.push({                                              // Phone:745
      text: item.id === ctx.nextPreId ? "下一场" : "预报名",
      cls: item.id === ctx.nextPreId ? "next" : "" });
    if (st === "signed") flags.push({ text: "已报名", cls: "signed" });          // Phone:746
    if (st === "closed") flags.push({ text: "已截止", cls: "mute" });            // Phone:747
    if (clash) flags.length = 0;                                                // Phone:750 冲突行只留「不可加入」
    const refund = (st === "open" || st === "pre") ? PhoneModel.refundFlag(item) : null;
    const reward = PhoneModel.rewardText(item);
    const open = PhoneModel.openEpochOf(item);
    const clockDown = nowS === null || nowS === undefined;
    const gap = open - (nowS || 0);
    /* 距开放（原型 left，Phone:760）：pre 且时钟不可用写「待校准」；<10 分钟标 soon 橙色 */
    const left = st === "pre" ? (clockDown ? "待校准" : PhoneModel.leftCn(gap))
      : (st === "open" ? "已开放" : "");
    const leftCls = st === "pre" && !clockDown && gap < 600 ? "soon" : "";
    const warn = hitSel ? "与已选的「" + hitSel.name + "」时间重叠" : "";         // Phone:761
    const act = PhoneModel.actSpan(item)
      || (st === "closed" || st === "unknown" ? PhoneModel.itemMeta(item) : "");
    return {
      id: item.id, item: item, name: PhoneModel.itemTitle(item), st: st,
      selected: selected, disabled: disabled, clash: clash, signedItem: hitSigned || null,
      flags: flags,
      rf: refund ? refund.text : "", rfNo: !!refund && refund.no, hasRf: !!refund,
      rw: reward || { cls: "", text: "" },
      time: st !== "unknown" ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(open)).slice(0, 5) : "待公布",
      timeCls: st !== "unknown" ? "" : "txt",
      hasLeft: !!left && !clash, left: left, leftCls: leftCls,
      act: act, place: String(item.place || item.location || ""),
      hasPlace: !!item.place && st !== "closed",        // 原型 hasPlace：已截止行不显示地点（Phone:762）
      warn: warn, hasWarn: !!warn && !ctx.busy,         // busy 时不显（Phone:762 hasWarn）
      note: PhoneModel.cancelNote(item, nowS),
      aria: "选择 " + PhoneModel.itemTitle(item),
      cls: (clash ? "clash " : "") + (selected ? "sel " : "")
        + (disabled && !selected ? "off " : "") + (dimmed ? "dim" : ""),
    };
  },
  /* LD01/LD02 草稿板（原型 draft 分支，Phone.dc.html:781-794）：
   * 已选＝「核对后再开始」确认页（LED 是下一批倒计时）；未选＝下一场详情卡 + 选这一场；
   * 时钟不可用只给待校准屏（原型 Phone:797 的 pcClock down 档，EX06 再补横幅与底栏） */
  draftBoard(items, nowS, selected, pick) {
    const list = items || [];
    const p = pick || PhoneModel.nextPick(list, nowS);
    const clockDown = nowS === null || nowS === undefined;
    const ledDown = () => PhoneModel.ledOf("--:--:--", "off", "电脑上的北京时间待校准", "");
    const sel = (selected || []).map((id) => list.find((i) => i && i.id === id)).filter(Boolean);
    if (sel.length) {
      const futures = sel.filter((i) => PhoneModel.stOf(i, nowS) === "pre")
        .sort((a, b) => PhoneModel.openEpochOf(a) - PhoneModel.openEpochOf(b));
      const first = futures.length ? PhoneModel.openEpochOf(futures[0]) : 0;
      return {
        tag: "已选 " + sel.length + " 场", tagTone: "",
        title: "核对后再开始", sub: "勾选不会开始报名。", pickId: "",
        led: clockDown ? ledDown()
          : (futures.length
            ? PhoneModel.ledOf(PhoneModel.hhmmss(first - nowS), "amber", "下一批开放",
                               PhoneModel.hmsAt(first, nowS))
            : PhoneModel.ledOf("00:00:00", "amber", "已开放，可以立即报名", "现在")),
      };
    }
    if (p.nextIt) {
      const it = p.nextIt;
      const open = PhoneModel.openEpochOf(it);
      return {
        tag: p.isOpen ? "开放中" : "下一场", tagTone: "",
        title: PhoneModel.itemTitle(it),
        sub: [String(it.place || it.location || ""), PhoneModel.actSpan(it)].filter(Boolean).join("，"),
        pickId: it.id,
        led: clockDown ? ledDown()
          : (p.isOpen
            ? PhoneModel.ledOf("00:00:00", "amber", "已开放，可以立即报名", "现在")
            : PhoneModel.ledOf(PhoneModel.hhmmss(open - nowS), "amber", "最近开放",
                               PhoneModel.hmsAt(open, nowS))),
      };
    }
    return {
      tag: "暂时没有", tagTone: "off",
      title: "没有可报名的场次",
      sub: "列表里的活动已报名、已截止或还没公布报名时间。",
      pickId: "",
      led: PhoneModel.ledOf("--:--:--", "off", "暂时没有目标", ""),
    };
  },
  /* G07/G08/G09 列表总聚合（原型 renderVals 的 groups/count/seg 段，Phone.dc.html:704-765/931）：
   * 计数对全部活动按开放状态聚合（原型 count 在 visible 过滤前累加），分组只收段钮放行的行 */
  listView(items, filter, opts) {
    const options = opts || {};
    const nowS = options.nowS !== undefined ? options.nowS : null;
    const wallS = options.wallS !== undefined ? options.wallS : 0;
    const list = items || [];
    const pick = PhoneModel.nextPick(list, nowS);
    /* termsOk 缺省＝已同意（undefined !== false）：条款门只在快照明确说 false 时收紧（TM01） */
    const ctx = { items: list, nowS: nowS, selected: options.selected || [],
                  busy: !!options.busy, nextPreId: pick.nextPreId,
                  termsOk: options.termsOk !== false };
    const count = { free: 0, signed: 0, all: 0 };
    list.forEach((item) => {
      const st = PhoneModel.stOf(item, nowS);
      count.all += 1;
      if (st === "signed") count.signed += 1;
      if (st === "open" || st === "pre") count.free += 1;
    });
    const visible = PhoneModel.visibleItems(list, filter,
      nowS !== null && nowS !== undefined ? nowS : wallS);
    const titles = ["正在开放", "今天", "明天", "后天", "待公布", "更晚开放", "已报名", "已截止"];
    let nowPlaced = false;
    const nowText = nowS !== null && nowS !== undefined
      ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)).slice(0, 5) : null;
    const groups = [];
    titles.forEach((title) => {
      const rows = visible
        .filter((item) => PhoneModel.groupKeyOf(item, PhoneModel.stOf(item, nowS), nowS, wallS) === title)
        .map((item) => PhoneModel.rowView(item, ctx));
      if (!rows.length) return;
      const nowBefore = !nowPlaced && title !== "正在开放";   // 原型 nowPlaced：首个非开放组前插「现在」
      if (nowBefore) nowPlaced = true;
      groups.push({
        title: title, n: rows.length,
        cls: title === "正在开放" ? "open" : (title === "已报名" ? "signed" : ""),
        note: title === "正在开放" ? "现在就能报" : (title === "已截止" ? "只能查看" : ""),
        nowBefore: nowBefore, now: nowText, rows: rows,
      });
    });
    return {
      counts: count, groups: groups, total: visible.length,
      nextPreId: pick.nextPreId, nextIt: pick.nextIt, nextIsOpen: pick.isOpen,
      board: PhoneModel.draftBoard(list, nowS, options.selected || [], pick),
    };
  },

  /* ---------------- 运行与等待（计划 20261108-phone-1to1 任务 run-wait；G04 G10 RW01–RW03） ----------------
   * 板、四站进度与任务卡的取值照原型 renderVals 的 pending/running 段（Phone.dc.html:799-827）
   * 与 card()（Phone:842-848）；时刻只用 businessNowS，不读手机墙钟（决策 012）。 */

  /* 未确认 start 的对账窗：与 startPending 同源；超过它还没结果就按
     「还没有查到开始结果」呈现（RW02 的 pendingLong 口径） */
  PENDING_WINDOW_MS: 15000,
  pendingLong(pending, nowMs) {
    if (!pending || pending.done) return false;
    return (Number(nowMs) - Number(pending.at || 0)) >= PhoneModel.PENDING_WINDOW_MS;
  },
  /* RW02 等待板（原型 pending 分支，Phone.dc.html:799-803）：LED --:--:-- off 档，
     cap 与副题按 pendingLong 分两档；板题固定「开始请求已发出」 */
  pendingBoard(pending, nowMs) {
    const long = PhoneModel.pendingLong(pending, nowMs);
    return {
      tag: "核对中", tagTone: "off",
      led: PhoneModel.ledOf("--:--:--", "off",
                            long ? "还没有查到开始结果" : "正在核对开始结果", ""),
      title: "开始请求已发出",
      sub: long ? "电脑可能已经开始，也可能没收到。工具只查询结果，不会重复发送。"
                : "请先不要重复点击。",
    };
  },
  /* 场次的开放时刻（epoch 秒）：计划任务带 sign_start 学校时间文本，按北京时间换算；
     缺失返回 0（倒计时落归零档，不猜时刻） */
  taskOpenOf(task) {
    return PhoneModel.schoolSec(task && task.sign_start) || 0;
  },
  /* 四站进度（原型 rail 段，Phone.dc.html:819-825）：启动＝worker 已拉起（run_started_at），
     第二站＝详情页已开（page_opened_at），via=click（path）的场叫「打开页面」；
     开放提交＝提交中 hot、页开完转 now；核对结果恒空（结果在任务卡上逐场说） */
  taskRail(task, nowS) {
    const t = task || {};
    const passed = (v) => {
      const n = Number(v);
      return Number.isFinite(n) && n > 0
        && nowS !== null && nowS !== undefined && nowS >= n;
    };
    const started = passed(t.run_started_at);
    const prepped = passed(t.page_opened_at);
    return [
      { label: "启动", state: started ? "done" : "" },
      { label: String(t.path || "") === "click" ? "打开页面" : "准备好",
        state: prepped ? "done" : (started ? "now" : "") },
      { label: "开放提交", state: t.status === "submitting" ? "hot" : (prepped ? "now" : "") },
      { label: "核对结果", state: "" },
    ];
  },
  /* G04 运行板（原型 running 分支，Phone.dc.html:804-827）：当前场＝提交中优先，
     其次最早开放的等待场；等待态 tag 等开放/即将开放（gap>5/≤5）、LED 琥珀且 ≤10 秒
     转红（原型 gap>5/≤10 口径）、cap「开放时间」+capB（hms 带明天/后天前缀）；
     提交态 tag 与 LED 都红、cap「本次尝试到」；离线（off）LED 转 dim 档，且 cap 换成
     「状态已过时 / 最后同步 HH:MM:SS」（EX01，原型 Phone:826；lastOkText 是同步成功时
     记下的北京时间，钟不可用时落 --:--:--，不拿手机墙钟冒充）。时钟不可用不给倒计时，
     capB 退回当天时刻，不拿手机墙钟冒充。 */
  runBoard(plan, nowS, off, lastOkText) {
    const tasks = (plan && plan.tasks) || [];
    const active = tasks.filter((t) => t.status === "submitting");
    const wait = tasks.filter((t) => t.status === "waiting")
      .sort((a, b) => PhoneModel.taskOpenOf(a) - PhoneModel.taskOpenOf(b));
    const cur = active[0] || wait[0] || tasks[0];
    if (!cur) return null;
    const clockDown = nowS === null || nowS === undefined;
    const targetText = (epoch) => clockDown
      ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(epoch))
      : PhoneModel.hmsAt(epoch, nowS);
    let tag = ""; let tagTone = ""; let led = null; let sub = "";
    if (cur.status === "submitting") {
      tag = "正在提交"; tagTone = "red";
      const deadline = PhoneModel.taskDeadline(cur);
      led = PhoneModel.ledOf(deadline !== null && !clockDown
        ? PhoneModel.hhmmss(deadline - nowS) : "--:--:--",
        off ? "dim" : "red", "本次尝试到",
        deadline !== null ? targetText(deadline) : "");
      sub = active.length > 1
        ? "正在提交 " + active.length + " 场，每场结果单独显示。"
        : "已提交 " + (Number(cur.attempts) || 0) + " 次，最近：" + String(cur.last_reason || "");
    } else {
      const open = PhoneModel.taskOpenOf(cur);
      const gap = clockDown ? null : open - nowS;
      tag = gap !== null && gap <= 5 ? "即将开放" : "等开放";
      led = PhoneModel.ledOf(gap === null ? "--:--:--" : PhoneModel.hhmmss(gap),
        off ? "dim" : (gap !== null && gap <= 10 ? "red" : "amber"),
        "开放时间", targetText(open));
      const same = wait.filter((t) => PhoneModel.taskOpenOf(t) === open).length;
      sub = same > 1 ? "这一批 " + same + " 场同时提交，到点自动开始。"
                     : "这一场等开放，到点自动开始。";
    }
    /* EX01（原型 Phone:826）：离线时 cap 换「状态已过时 / 最后同步 HH:MM:SS」，
       倒计时与开放时刻照旧给出，只是注明数据可能过时 */
    if (off) {
      led.cap = "状态已过时";
      led.capB = "最后同步 " + (lastOkText || "--:--:--");
    }
    return { tag: tag, tagTone: tagTone, led: led, title: PhoneModel.itemTitle(cur),
             sub: sub, rail: PhoneModel.taskRail(cur, nowS) };
  },
  /* G10 任务卡（原型 card()，Phone.dc.html:842-848）：状态词与 tone 映射照抄
     （waiting 按报名模式分等待开放/准备报名，full/unconfirmed 从 failed 单列）；
     detail 优先级照抄——等待明细 → 页点击尾注 → 提交中明细覆盖；终态场：
     RS02 三句照原型 advance 的 reason（Phone.dc.html:560/564/565，次数取 attempts），
     其余仍用电脑口径 taskText（说法不另起一套）；取消的那场：计划停止给原型整句
     （finishState，Phone:580），手动取消透传后端 reason（signup_plan 给「你取消了这一场」）；
     取消钮只给等待中的场（原型 canCancel=status==='waiting'） */
  taskCard(task, maxAttempts, nowS) {
    const t = task || {};
    const st = String(t.status || "");
    const clockDown = nowS === null || nowS === undefined;
    const targetText = (epoch) => clockDown
      ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(epoch))
      : PhoneModel.hmsAt(epoch, nowS);
    const isPre = String(t.signup_mode || "") !== "instant_signup";
    const failedFull = st === "failed" && String(t.stop_reason || "") === "full";
    const failedAsk = st === "failed" && String(t.stop_reason || "") === "unconfirmed";
    const map = {
      waiting: ["", isPre ? "等待开放" : "准备报名"],
      submitting: ["run", "提交中"],
      success: ["ok", "报名成功"],
      already_signed: ["ok", "报名成功"],
      failed: [failedFull ? "" : (failedAsk ? "ask" : "bad"),
               failedFull ? "名额已满" : (failedAsk ? "待核对" : "报名未成功")],
      canceled: ["", "已取消"],
    };
    const toneAndLabel = map[st] || map.waiting;   // queued 等未知态按等待呈现，不编结论
    const attempts = Number(t.attempts) || 0;
    let detail;
    if (st === "waiting" || st === "queued") {
      const open = PhoneModel.taskOpenOf(t);
      if (!isPre) {
        detail = "已开放，正在准备提交";
      } else {
        const prepped = !clockDown && Number(t.page_opened_at) > 0
          && nowS >= Number(t.page_opened_at);
        detail = prepped ? "已准备好，" + targetText(open) + " 开放时提交"
                         : "等到 " + targetText(open) + " 开放";
      }
    } else if (st === "canceled") {                    // RS02（Phone:580/877）
      const reason = String(t.reason || "");
      detail = reason === "计划已停止" ? "计划已停止，这一场没有提交"
        : (reason || "已取消");
    } else if (st === "success") {                     // RS02 原型句（Phone:564）
      detail = "学校回“操作成功”，结束时向学校核对过：已报名";
    } else if (failedFull) {                           // RS02 原型句（Phone:560）
      detail = "学校说报名人数已满，这一场到此结束，不再提交。不是工具出错。已提交 "
        + attempts + " 次";
    } else if (failedAsk) {                            // RS02 原型句（Phone:565）
      detail = "已提交 " + attempts + " 次，没拿到确定回应；结束时向学校核对也没查到结果。"
        + "去活动页看一眼，或稍后刷新核对。工具不会再自动重发。";
    } else {
      detail = PhoneModel.taskText(t);
    }
    if (String(t.path || "") === "click" && st !== "canceled" && st !== "submitting") {
      detail += "。改用页面点击" + (t.path_reason ? "：" + t.path_reason : "");
    }
    if (st === "submitting") {
      const deadline = PhoneModel.taskDeadline(t);
      detail = "已提交 " + (Number(t.attempts) || 0) + " 次（"
        + (Number(maxAttempts) > 0 ? "上限 " + Number(maxAttempts) + " 次" : "不限次数") + "）"
        + (deadline !== null ? "，重试到 " + targetText(deadline) : "");
    }
    return { name: PhoneModel.itemTitle(t), tone: toneAndLabel[0], label: toneAndLabel[1],
             detail: detail, canCancel: st === "waiting" };
  },
  /* RW03/SH03/SH04 确认文案（原型 isConfirm 三档，Phone.dc.html:874-879）逐字照抄：
     常量放纯函数层供 node 用例直接调；取消一场那句带场名。
     sheets-ops 迁移停止/取消确认时复用同一容器 */
  confirmView(kind, taskName) {
    const copy = {
      cancelstart: {
        title: "取消这次等待？",
        text: "只是不再等这次结果。如果计划其实已经启动，刷新后还要再点“停止计划”。",
        no: "继续等", yes: "取消等待" },
      stop: {
        title: "停止报名计划？",
        text: "工具会停止后续尝试。已经发出的提交仍可能成功，停止不会取消已成功的报名。",
        no: "继续计划", yes: "停止计划" },
      cancelTask: { title: "取消这一场？", text: "", no: "先不取消", yes: "取消这一场" },
    }[kind];
    if (!copy) return null;
    return Object.assign({}, copy, {
      text: kind === "cancelTask"
        ? "「" + String(taskName || "") + "」还没提交，取消后不会再报名，其他场次继续。"
        : copy.text });
  },

  /* ---------------- 结果页与条款态（计划 20261108-phone-1to1 任务 result-and-terms；RS01 TM01） ----------------
   * 统计与六支板头照原型 renderVals 的 result 段（Phone.dc.html:828-840）；
   * 统计由 state.plan.tasks 的 status/stop_reason 前端聚合（原型 c() 按 status 计数，
   * 这边名额已满/待核对是 failed 的 stop_reason——口径与 taskText 一致），不改后端。 */

  /* 计划是否已结束（RS01）：不忙且每场都到终态。queued/waiting/submitting 都算未结束；
     没有计划或空计划不算（原型 phase==='result' 只在全部终态后由 finishState 进入） */
  planFinished(plan, busy) {
    if (busy) return false;
    const tasks = (plan && plan.tasks) || [];
    if (!tasks.length) return false;
    const TERM = ["success", "already_signed", "failed", "canceled"];
    return tasks.every((t) => TERM.indexOf(String((t && t.status) || "")) >= 0);
  },
  /* RS01 结果页数据（原型 res 段，Phone.dc.html:828-840）：五类统计只显非零、
     tone ok/wait/bad/ask/wait 照原型 res.counts（832）；六支板头照 834-839 逐支；
     stopped 取计划级 status（signup_plan 停止后的终态快照即 stopped）；
     canRetry＝未成功+已取消（原型 833：bad + none > 0） */
  resultView(plan, busy) {
    if (!PhoneModel.planFinished(plan, busy)) return null;
    const tasks = (plan && plan.tasks) || [];
    const statusOf = (t) => String((t && t.status) || "");
    const reasonOf = (t) => String((t && t.stop_reason) || "");
    const ok = tasks.filter((t) => statusOf(t) === "success" || statusOf(t) === "already_signed").length;
    const full = tasks.filter((t) => statusOf(t) === "failed" && reasonOf(t) === "full").length;
    const ask = tasks.filter((t) => statusOf(t) === "failed" && reasonOf(t) === "unconfirmed").length;
    const bad = tasks.filter((t) => statusOf(t) === "failed"
      && reasonOf(t) !== "full" && reasonOf(t) !== "unconfirmed").length;
    const none = tasks.filter((t) => statusOf(t) === "canceled").length;
    const counts = [
      { tone: "ok", n: ok, text: "已报名" },
      { tone: "wait", n: full, text: "名额已满" },
      { tone: "bad", n: bad, text: "未成功" },
      { tone: "ask", n: ask, text: "待核对" },
      { tone: "wait", n: none, text: "已取消" },
    ].filter((x) => x.n > 0);
    const stopped = String((plan && plan.status) || "") === "stopped";
    const head = { text: "", tone: "" };
    let title = ""; let text = ""; let boardCls = "";
    if (stopped) {                                       // Phone:834
      head.text = ask ? "已停止，需确认" : "已停止";
      head.tone = ask ? "" : "off";
      title = "报名计划已停止";
      text = "已提交的场次保留原状态，还没提交的场次已取消。";
      if (ask) boardCls = "st-warn";
    } else if (ok && !bad && !ask && !none && !full) {   // Phone:835
      head.text = "报名成功"; head.tone = "green";
      title = "报名计划完成";
      text = "每场结束时都向学校核对过。";
      boardCls = "st-ok";
    } else if (ok) {                                     // Phone:836
      head.text = "部分完成";
      title = "报名计划部分完成";
      text = ask ? "有 " + ask + " 场需要到活动页核对，结果以学校为准。"
        : (full ? "有 " + full + " 场名额已满，不是工具出错。"
                : "结果以学校活动页为准。");
      boardCls = "st-warn";
    } else if (ask) {                                    // Phone:837
      head.text = "需确认";
      title = "计划已结束，有 " + ask + " 场需确认";
      text = "工具不会自动重发，到学校活动页核对。";
      boardCls = "st-warn";
    } else if (full && !bad) {                           // Phone:838
      head.text = "名额已满";
      title = "这次没报上：名额满了";
      text = "学校的名额在开放后被报满了，不是工具出错。";
      boardCls = "st-warn";
    } else {                                             // Phone:839
      head.text = "未成功"; head.tone = "red";
      title = "报名计划没有成功";
      text = "每场的原因都列在下面。";
      boardCls = "st-bad";
    }
    return { head: head, title: title, text: text, counts: counts,
             canRetry: bad + none > 0, boardCls: boardCls };
  },
  /* TM01 条款板（原型 Phone:798 逐字）：草稿态且电脑没同意条款时整板换成已暂停；
     LED 与倒计时一并停住——同意前没有「下一场」可言 */
  termsBoard() {
    return {
      tag: "已暂停", tagTone: "off",
      led: PhoneModel.ledOf("--:--:--", "off", "电脑上同意条款后才能报名", ""),
      title: "电脑上还没有同意条款",
      sub: "同意前只能看缓存，不能报名，也不能重新登录。",
    };
  },

  /* ---------------- 核对计划与更多 sheet（计划 20261108-phone-1to1 任务 sheets-ops；SH01 SH02 SH05） ----------------
   * 批次/条目照原型 batchMap（Phone.dc.html:767-779），登录行照原型 loginLine（Phone:937）；
   * 纯函数出数据，renderReview/refreshControls 只做 DOM。 */

  /* SH01 核对批次（原型 batchMap 逐支照抄）：已选场按开放状态分批——
   * 已开放（stOf=open）同归「现在」批，其余按开放时刻分批；批次头＝时刻（原型 hms(open)，
   * 这里 epoch 秒经 hmsAt 换算，时钟不可用时退回当天时刻，不给假倒计时）+ 数量注
   * （立即报名 N 场／预报名，同时提交 N 场／预报名 1 场）；条目带移除 aria 与时段。
   * 缺举办时段的场次回退「开放 …」说明（原型数据恒有时段，记 deviation）。 */
  reviewBatches(items, nowS) {
    const map = new Map();
    const keys = [];
    (items || []).slice()
      .sort((a, b) => PhoneModel.openEpochOf(a) - PhoneModel.openEpochOf(b))
      .forEach((item) => {
        const st = PhoneModel.stOf(item, nowS);
        const open = PhoneModel.openEpochOf(item);
        const key = st === "open" ? "now" : String(open);
        if (!map.has(key)) {
          map.set(key, {
            time: st === "open" ? "现在"
              : (nowS !== null && nowS !== undefined
                ? PhoneModel.hmsAt(open, nowS)
                : PhoneModel.hhmmss(PhoneModel.beijingSecOf(open))),
            instant: st === "open", items: [],
          });
          keys.push(key);
        }
        const span = PhoneModel.actSpan(item);
        map.get(key).items.push({
          id: item.id, name: PhoneModel.itemTitle(item),
          act: span ? "活动 " + span : PhoneModel.itemMeta(item),
          aria: "从计划移除 " + PhoneModel.itemTitle(item),
        });
      });
    return keys.map((k) => {
      const b = map.get(k);
      const n = b.items.length;
      b.note = b.instant ? "立即报名 " + n + " 场"
        : (n > 1 ? "预报名，同时提交 " + n + " 场" : "预报名 1 场");
      return b;
    });
  },

  /* SH05 登录行四态（原型 loginLine，Phone.dc.html:937 逐字）：
   * 前半句按 state.login（session_expired / session_present，与 ingest 同一口径），
   * 后半句按 relogin_setup——has=saved 且未暂停（密码不对时自动登录同样开不全，
   * 并入「没保存账号」支，与 relNeedAcct 同口径）；ocrOn=ocr_ready。 */
  loginLine(login, setup) {
    const s = setup || {};
    const expired = PhoneModel.loginExpired(login);
    const has = !!s.saved && !s.paused;
    const ocrOn = !!s.ocr_ready;
    return (expired ? "电脑上的登录已失效。" : "电脑上的登录有效。")
      + (has ? (ocrOn ? "失效时电脑会自己重新登录。" : "失效时只需在这里输验证码。")
             : (ocrOn ? "电脑上没保存账号，重新登录要输账号和密码。"
                      : "电脑上没保存账号，重新登录要输账号、密码和验证码。"));
  },

  /* ---------------- 重新登录 sheet（计划 20261108-phone-1to1 任务 relogin-sheet；RL01–RL08/G11） ----------------
   * 六态呈现照原型 renderVals 的 rel 段（Phone.dc.html:881-905）与 beginRelogin/relCanSubmit/
   * autoRelogin（Phone:649-680）；纯函数出数据，renderRelogin 只做 DOM。 */

  /* RL02 忙态三句（原型 Phone:886-887）。旧句映射（对账态归并进三句）：
   *   正在校验验证码…            → verify（提交已被收下，等结果）
   *   正在准备验证码…            → prepare（worker 刚拉起，无需下图）／needCode（manual 等图）
   *   等待验证码…                → needCode
   *   提交结果未知，正在对账…    → verify（保持禁用，先对账再放行）
   *   验证码正在提交，请等待结果 → verify（同一张图还有在途提交） */
  RELOGIN_BUSY: {
    needCode: "正在向电脑要验证码…",
    prepare: "正在准备…",
    verify: "正在登录，请等结果",
  },

  /* G11 saveGain（原型 rel.saveGain，Phone:882）：装了识别→失效时电脑自己来；没装→手机输码 */
  relSaveGain(ocrReady) {
    return ocrReady ? "电脑会自己重新登录，不用你动手" : "只要输验证码";
  },

  /* RL04 态 1「识别连续失败交接」：这一场是 manual 且电脑认错到了阈值。
   * 服务端阈值 _MANUAL_RELOGIN_AFTER=3（app.py），与原型「连续认错 3 次」同口径；
   * attempts 是这一场的认图次数、auto_failures 是整轮自动重登的连续失败数 */
  REL_HANDOFF_AFTER: 3,
  relHandoff(flow) {
    if (!flow || String(flow.mode || "") !== "manual" || !flow.live) return false;
    return (Number(flow.attempts) || 0) >= PhoneModel.REL_HANDOFF_AFTER
      || (Number(flow.auto_failures) || 0) >= PhoneModel.REL_HANDOFF_AFTER;
  },

  /* RL04 needAcct：电脑没保存账号或保存的密码不对（paused）时手机输；
   * handoff 时账号密码由电脑自动填写，字段整块收起（原型 relNeedAcct/relHandoff，Phone:655/667） */
  relNeedAcct(flow, setup) {
    if (PhoneModel.relHandoff(flow)) return false;
    const s = setup || {};
    return !s.saved || !!s.paused;
  },

  /* RL04 lead 四态（原型 Phone:898 逐字）；RL07 relbad 无 lead（红错由 err 承担） */
  relLead(flow, setup) {
    const s = setup || {};
    if (s.paused) return "";
    if (PhoneModel.relHandoff(flow)) {
      return "电脑连续 3 次没认对验证码，换你来输。账号密码由电脑自动填写。";
    }
    const needAcct = !s.saved || !!s.paused;
    if (!needAcct) return "电脑会自动填账号密码，你只要输验证码。";
    return s.ocr_ready ? "电脑上没有保存账号密码，输入账号和密码就行。"
                       : "电脑上没有保存账号密码，账号、密码和验证码都要输。";
  },

  /* relCanSubmit（原型 Phone.dc.html:675-680 同一口径）：主钮什么时候能按——
   * needAcct 要账号密码都填，needCap 要 4 位验证码；stale/在途门禁另见 canSubmitRelogin */
  relCanSubmit(fields) {
    const f = fields || {};
    if (f.needAcct && (!String(f.user || "").trim() || !String(f.pass || ""))) return false;
    if (f.needCap && String(f.code || "").length !== 4) return false;
    return true;
  },

  /* RL07 relbad 固定句（原型 Phone:885/519/666）：保存的密码学校不认、自动登录已暂停 */
  RELBAD_TEXT: "电脑上保存的密码学校不认，自动登录已暂停。请输入新的账号密码；勾选保存会替换旧的。",

  /* B-P2-1（RL05）：失败结论句。safe_error 是服务端白名单里的英文安全码
     （login_relay_service._SAFE_ERRORS：eof/timeout/internal…），直出会变成
     「重新登录结束：bad_password」；其中 bad_password（学校明确说账号或密码不对，
     登录进程就此停手、不重试）按原型映射成整句，其余码保留「前缀+码」通用句 */
  RELOGIN_BAD_PASSWORD_TEXT:
    "学校说账号或密码不对。为了避免账号被锁，没有重试。核对后再登录。",
  reloginFailText(safeError, prefix) {
    const code = String(safeError || "");
    if (code === "bad_password") return PhoneModel.RELOGIN_BAD_PASSWORD_TEXT;
    return String(prefix || "重新登录结束：") + code;
  },

  /* RL01–RL08 重登 sheet 的呈现数据（原型 rel 段，Phone.dc.html:881-905）。
   * flow=state.login_relay、setup=state.relogin_setup（拿不到时不猜 needAcct，字段先收着）、
   * local={confirm,starting,submitting,entered,savedChoice,planBusy}。 */
  reloginView(flow, setup, local) {
    const f = (flow && typeof flow === "object") ? flow : {};
    const s = (setup && typeof setup === "object") ? setup : null;
    const o = local || {};
    const B = PhoneModel.RELOGIN_BUSY;
    const view = { spin: "", text: "", err: "", showForm: false, lead: "",
                   needAcct: false, needCap: false, autoCap: false, saveLine: "",
                   main: "", mainKind: "", refresh: false, cancel: false, done: "" };
    const saveGain = PhoneModel.relSaveGain(!!s && !!s.ocr_ready);
    /* G11 保存勾选小字（原型 Phone:342） */
    view.saveLine = "加密保存，只有这台电脑能解开。下次失效时" + saveGain
      + "。不勾的话，只在这次运行中有效。";
    /* needAcct 在所有态都要算：忙态虽然整组收起，字段显隐仍按 setup 走，
       否则 begin 在途的窗口里字段被藏住，提交中的凭据读取会扑空 */
    const state = String(f.state || "idle");
    view.needAcct = s ? PhoneModel.relNeedAcct(f, s) : false;
    const lead = s ? PhoneModel.relLead(f, s) : "";
    /* RL06 确认层（原型 relogin==='confirm'，Phone:889）：begin 之前拦一步 */
    if (o.confirm) {
      view.text = "用电脑上存的账号密码登录一次，验证码由电脑识别。"
        + "这会向学校发送一次账号密码，工具会替你勾选学校登录页上的“我已阅读并同意《隐私协议》”。"
        + (o.planBusy ? "成功后报名计划照常继续。" : "成功后会刷新活动列表，计划不会自动开始。");
      view.main = "自动登录一次";
      view.mainKind = "auto";
      view.cancel = true;
      return view;
    }
    /* RL03 auto 态（原型 relogin==='auto'，Phone:888）：电脑自己认图，手机可收起在后台等；
       终态不算（结论归 RL08/RL05），快照没带 live 时以状态名判断 */
    const terminal = state === "success" || state === "failed" || state === "canceled";
    if (String(f.mode || "") === "auto" && !terminal
        && (!!f.retrying || state === "starting" || state === "waiting_code"
            || state === "verifying")) {
      view.spin = "电脑正在自动登录";
      view.text = "验证码由电脑识别，手机上不用操作。电脑连续认错 3 次，才会转给你输入。";
      view.done = "收起，在后台继续";
      return view;
    }
    /* RL02 忙态：提交在途（含对账）与 verifying 归并为「正在登录，请等结果」 */
    if (o.submitting || state === "verifying") {
      view.spin = B.verify;
      return view;
    }
    if (o.starting || state === "starting") {
      /* manual 等图 / auto 无图（原型 relNeedCap 分支，Phone:886） */
      view.spin = (s && s.ocr_ready) ? B.prepare : B.needCode;
      return view;
    }
    /* RL01 captcha 态（原型 rel.isForm 且有挑战图，Phone:898/900） */
    if (state === "waiting_code" && f.challenge_id) {
      view.showForm = true;
      view.lead = lead;
      view.needCap = true;
      view.main = "提交验证码";
      view.mainKind = "submit";
      view.refresh = true;      // 换一张图：仍是 cancel+begin 两步，后端没有换图接口
      view.cancel = true;
      return view;
    }
    if (state === "waiting_code") {
      view.spin = B.needCode;   // manual 已开跑、图还在路上：不给空输入框
      return view;
    }
    /* RL08 完成态（原型 relogin==='done'，Phone:892-894）：两套文案 + 附言 */
    if (state === "success" && f.live) {
      view.text = (o.planBusy ? "重新登录成功，报名计划照常继续。"
        : "重新登录成功，活动列表已刷新。计划不会自动重新开始，要你重新核对后再点开始。")
        + (o.entered ? (o.savedChoice
          ? "账号已加密保存到电脑，下次失效时" + saveGain + "。"
          : "账号只在这次运行中有效，关闭工具后清除。") : "");
      view.done = "完成";
      return view;
    }
    /* RL05：失败结论进红条（safe_error 服务端透传；B-P2-1：bad_password 走原型整句，
       其余码保留通用句）；回表单初态可重试 */
    if ((state === "failed" || state === "canceled") && f.live) {
      view.err = PhoneModel.reloginFailText(String(f.safe_error || state));
    }
    /* 表单初态（RL04 lead 四态 / RL07 relbad 红错盖过原因） */
    view.showForm = true;
    view.lead = lead;
    view.autoCap = view.needAcct && !!s && !!s.ocr_ready;
    view.main = "登录";
    view.mainKind = "begin";
    view.cancel = true;
    if (s && s.paused) view.err = PhoneModel.RELBAD_TEXT;
    return view;
  },

  /* ---------------- 配对点阵屏（PA03；glyphs/ledOf 照抄 Phone.dc.html:377-406，run-wait 的 LED 计划板复用） ----------------
   * 字形表：每个字符 7 行、每行 '0'/'1' 串（空格 2 列、冒号 1 列、其余 5 列）。 */
  glyphs() {
    if (!PhoneModel._glyphs) PhoneModel._glyphs = {
      "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
      "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
      "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
      "3": ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
      "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
      "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
      "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
      "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
      "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
      "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
      "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
      " ": ["00", "00", "00", "00", "00", "00", "00"],
      ":": ["0", "0", "1", "0", "1", "0", "0"],
    };
    return PhoneModel._glyphs;
  },
  /* 原型 ledOf 照抄：按行展开成点阵，字符间插 gap 点；blinkAt 指到哪个字符，
     那个字符的亮点就闪（配对屏用它当光标）。cap/capB/aria 供 LED 计划板复用 */
  ledOf(text, tone, cap, capB, blinkAt) {
    const G = PhoneModel.glyphs();
    let cols = 0;
    const dots = [];
    const chars = Array.from(text);
    chars.forEach((ch, i) => {
      cols += (G[ch] || G[" "])[0].length + (i < chars.length - 1 ? 1 : 0);
    });
    for (let r = 0; r < 7; r += 1) {
      chars.forEach((ch, i) => {
        const g = G[ch] || G[" "];
        for (let c = 0; c < g[0].length; c += 1) {
          dots.push({ cls: g[r][c] === "1" ? (i === blinkAt ? "blink" : "on") : "" });
        }
        if (i < chars.length - 1) dots.push({ cls: "gap" });
      });
    }
    return { cols: cols, dots: dots, tone: tone,
             cap: cap || "", capB: capB || "",
             aria: (cap || "") + " " + (capB || "") + " " + text };
  },
  /* 配对视图状态（PA01/PA03；原型 renderVals 的 pair 段，Phone.dc.html:908-910）：
   * LED 显示 code+"------" 前 6 位、满 3 位插空格；blinkAt 是光标点（满 3 位
   * 要跳过空格位）。锁定时 LED 转 off、tag 转「已锁定」；EX04 配错转 red。 */
  pairView(code, lockLeft, pairErr) {
    const text = String(code || "");
    const locked = (Number(lockLeft) || 0) > 0;
    const shown = (text + "------").slice(0, 6);
    const led = PhoneModel.ledOf(shown.slice(0, 3) + " " + shown.slice(3),
      locked ? "off" : (pairErr ? "red" : "amber"), "", "",
      locked ? -1 : (text.length < 3 ? text.length : text.length + 1));
    return {
      led: led,
      locked: locked,
      tag: locked ? "已锁定" : "输入配对码",
      tagTone: locked ? "red" : "",
      cap: locked ? (Number(lockLeft) || 0) + " 秒后可以再试"
        : (text.length
          ? (text.length < 6 ? "还差 " + (6 - text.length) + " 位" : "输完了，点“配对”")
          : "点上面的点阵屏，输入电脑上的 6 位数"),
      cantSubmit: locked || text.length !== 6,
      hasErr: !!pairErr,
      err: String(pairErr || ""),
    };
  },
  /* EX03：锁定倒计时每秒只做一步呈现递减；0 停住，不把本地计时当权威值 */
  pairTickLeft(left) {
    const n = Math.floor(Number(left) || 0);
    return n > 0 ? n - 1 : 0;
  },
  /* PA04/EX04 配错态错误条：N 来自服务端 remaining_attempts（BE1）。
   * 第 3 次失败（N=0）不拼尾句——服务端已落锁，下一次应答就是锁定态。
   * R-P3-6：句中的「60 秒」与 domain/phone_rules 的 IP_LOCK_S（配错落锁时长）
   * 耦合——改 IP_LOCK_S 必须同步改这句文案。 */
  pairWrongText(remainingAttempts) {
    const n = Number(remainingAttempts) || 0;
    return "配对码不对，请核对后重试。"
      + (n > 0 ? "再错 " + n + " 次要等 60 秒。" : "");
  },
  /* EX03 锁定态错误条：固定句；倒计时在屏下说明里（秒数来自服务端 retry_after_s） */
  pairLockedText() {
    return "尝试次数过多，请稍后再试。换一台设备也一样要等。";
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
    /* G08：默认段钮＝可报名（原型 init 的 seg:'free'，Phone.dc.html:499） */
    items: [], selected: [], filter: { q: "", status: "free", time: "all" },
    retry: { retry_for_s: 120, max_attempts: 0 }, busy: false,
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
    relConfirm: false, relEnteredAcct: false, relSavedChoice: false,
    /* PA01/EX03/EX04 配对视图：锁定倒计时的呈现值（权威值是服务端 retry_after_s）、
       当前配对错误句、1 秒呈现 tick 的定时器 id；pairing 是在途单飞锁（A-BUG-6）、
       pairOkPending 是配对成功告警的待展示标记（UI-F13，本会话关闭后不再出现） */
    pairLockLeft: 0, pairErr: "", pairTickTimer: 0, pairing: false, pairOkPending: false,
    /* RS01：结果态里点过「完成/重新选择」的计划不再回头——服务端快照会一直带
       最后一份终态计划，按 plan_id 记住已收起的那份，新计划（plan_id 不同）照常接纳 */
    dismissedPlanId: "",
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
  /* EX01 离线告警（原型 alert bad + 重试钮，Phone.dc.html:852）：两句照原型逐字，
     标题在 N=0 时不带「已重试」尾缀；重试钮复用 poll(true)（与右上角刷新同一动作）。
     静默过期（pill「同步中」）不亮红条——那时由 #stale-note 说明，红条只给「离线」档。
     连不上时界面不能看起来一切正常：刷新按钮始终可点，这里是唯一自救入口。 */
  function syncOffline(stale) {
    const note = $("offline-note");
    if (!stale) {
      note.hidden = true;
      model.offlineTries = 0;
      return;
    }
    /* flying 时不走 connState 的 busy 短路：正在重试的红条要保持可见，钮写「同步中…」 */
    if (PhoneModel.connState(model, false).state !== "off") {
      note.hidden = true;
      return;
    }
    const tries = Number(model.offlineTries || 0);
    $("offline-note-title").textContent =
      tries > 0 ? "连不上电脑，已重试 " + tries + " 次" : "连不上电脑";
    $("offline-note-text").textContent =
      "确认电脑开着、程序没退出。如果只是手机断网，电脑上的计划不受影响。";
    $("btn-offline-retry").textContent = model.flying ? "同步中…" : "重试";
    note.hidden = false;
  }
  /* 五条告警互斥（原型 alert 链，Phone.dc.html:851-856 的 if/else 次序）：
     离线 > 条款 > 登录失效 > 电脑列表失败 > 时钟待校准。离线由 syncOffline 画，
     这里只管其余四条的开关与 EX05 副句的 HH:MM（BE2 的 pc_list_error.at） */
  function renderAlerts(stale) {
    syncOffline(stale);
    const off = !$("offline-note").hidden;
    const terms = model.termsOk === false;
    const expired = PhoneModel.loginExpired(model.login);
    const pcList = !!model.pcListError;
    const clockDown = model.clockState === "unavailable";
    /* TM01 条款告警两句照原型逐字（Phone:853），同意后收起（服务端同样拦写动作） */
    $("terms-alert-title").textContent = "电脑上还没有同意使用条款";
    $("terms-alert-text").textContent = "回电脑同意后才能登录和报名。现在显示的是上次的缓存。";
    $("terms-alert").hidden = !(!off && terms);
    $("login-expired-banner").hidden = !(!off && !terms && expired);
    /* EX05（原型 Phone:855）：两句照原型，HH:MM 来自快照 pc_list_error.at */
    $("pclist-alert-title").textContent = "电脑上的活动列表没加载";
    $("pclist-alert").hidden = !(!off && !terms && !expired && pcList);
    if (!$("pclist-alert").hidden) {
      const when = String((model.pcListError || {}).at || "");
      $("pclist-alert-text").textContent = when
        ? "电脑那边连不上学校站点，现在显示的是 " + when + " 更新的列表。恢复后会自动更新。"
        : "电脑那边连不上学校站点，现在显示的是缓存列表。恢复后会自动更新。";
    }
    /* EX06（原型 Phone:856）：两句照原型，无钮——校准是电脑端的事 */
    $("pcclock-alert-title").textContent = "电脑上的北京时间还没校准";
    $("pcclock-alert-text").textContent = "校准后才能开始报名计划，现在可以先选活动。";
    $("pcclock-alert").hidden = !(!off && !terms && !expired && !pcList && clockDown);
    /* UI-F13（原型 .alert.ok，Phone.dc.html:36/857）：配对成功告警排告警链最末
       （任何一条真告警都优先），点过「知道了」本会话不再出现 */
    $("pair-ok-alert").hidden = !(!off && !terms && !expired && !pcList && !clockDown
      && model.pairOkPending);
  }
  function canWrite() {
    model.nowMs = Date.now();
    return !PhoneModel.isStale(model.lastOkAt, model.nowMs);
  }

  function refreshControls() {
    model.nowMs = Date.now();
    const stale = PhoneModel.isStale(model.lastOkAt, model.nowMs);
    const conn = PhoneModel.connState(model, model.flying);
    /* 圆点是 pill 的固定子元素：文案写进内层 #conn-text，不整体覆盖 textContent */
    $("conn-text").textContent = conn.text;
    $("conn").dataset.state = conn.state;
    $("stale-note").hidden = !stale;
    /* 刷新钮是图标钮（G01）：忙态不写字，交给 disabled + pill「同步中」 */
    $("btn-refresh").disabled = Boolean(model.flying);
    /* 电脑没同意条款：手机停在缓存，不能开始也不能重新登录（与电脑同一道门，后端也会拦） */
    $("btn-start").disabled = !PhoneModel.canStart(model) || model.termsOk === false;
    $("btn-stop").hidden = !model.busy;
    /* relCanSubmit（原型 Phone:675）：提交验证码要 4 位；登录要账号密码都填
       （relogin_setup 没到手前不猜 needAcct，与旧默认一致先亮着） */
    $("btn-relogin-submit").disabled = !PhoneModel.canSubmitRelogin(model, model.challenge)
      || !PhoneModel.relCanSubmit({ needCap: !!model.challenge,
                                    code: String(($("code") || {}).value || "") });
    $("btn-relogin").disabled = Boolean(model.reloginStarting) || model.termsOk === false
      || !PhoneModel.relCanSubmit({
        needAcct: model.reloginSetup
          ? PhoneModel.relNeedAcct(model.flow, model.reloginSetup) : false,
        user: String(($("relogin-user") || {}).value || ""),
        pass: String(($("relogin-pass") || {}).value || ""),
      });
    $("btn-relogin-auto").disabled = model.termsOk === false;
    $("btn-relogin-open").disabled = Boolean(model.reloginStarting) || model.termsOk === false;
    /* 电脑上没保存账号或保存的密码不对：手机上露出账号密码输入（RL04 needAcct；
       handoff 时电脑自己填，整块收起）；relogin_setup 没到手时先收着（与旧默认一致） */
    const setup = model.reloginSetup || null;
    const account = $("relogin-account");
    if (account) account.hidden = setup ? !PhoneModel.relNeedAcct(model.flow, setup) : true;
    $("btn-cancel-start").hidden = !(model.pending && !model.pending.done);
    /* SH01 fhint（#review-policy）与 SH05 登录行（#login-line）：随快照走，
       retry=0 的缺截止口径按已选场算（与 openReview 同一公式） */
    const pickedNow = (model.items || []).filter(
      (item) => model.selected.indexOf(item.id) >= 0);
    const hint = PhoneModel.retryHint(model.retry.retry_for_s,
      pickedNow.some((i) => i.sign_end_ts));
    $("review-policy").textContent = hint;
    $("review-policy").hidden = !hint;
    $("login-line").textContent = PhoneModel.loginLine(model.login, model.reloginSetup);
    /* 验证中（提交验证码）sheet 不给关闭钮；开关本身在 openSheet/closeSheet 里管 */
    if (model.sheetId) $("btn-sheet-close").hidden = sheetBusy();
    renderAlerts(stale);   // EX01/EX02/EX05/EX06/TM01：五条告警按原型优先链互斥
    renderBar();
    renderRelogin();   // RL01–RL08：重登 sheet 的六态跟着模型走
  }

  /* G03 sheet 外壳（原型 Phone:299-300/924-926）：一个通用容器，openSheet/closeSheet
     管焦点归还与开关；验证中 busyLock 不收（Esc、点遮罩、关闭钮都不关）。
     RL03：电脑自动登录（mode=auto）时手机只是看进度，「收起，在后台继续」要能收——
     busyLock 只锁人工流程（starting/waiting_code/verifying/提交在途） */
  function sheetBusy() {
    const flow = model.flow;
    if (flow && String(flow.mode || "") === "auto") return Boolean(model.reloginSubmitting);
    return Boolean(model.reloginSubmitting || PhoneModel.reloginBusy(flow));
  }
  /* confirm 的标题是占位：askConfirm 会按档覆写（RW03/SH03/SH04）；relogin 题固定（RL01，原型 Phone:884） */
  const SHEET_TITLES = { more: "更多", review: "核对计划", confirm: "确认",
                         relogin: "在手机上重新登录" };
  function openSheet(id) {
    const root = $("sheet-root");
    if (!root || !SHEET_TITLES[id] || model.sheetId) return;   // 一次只开一张
    model.sheetOpener = document.activeElement || null;
    model.sheetId = id;
    $("sheet-err").hidden = true;
    $("more-panel").hidden = id !== "more";
    $("review-panel").hidden = id !== "review";
    $("confirm-panel").hidden = id !== "confirm";
    $("relogin-panel").hidden = id !== "relogin";
    /* UI-F2：review/relogin 的页脚在 .sh-b 滚动区之外（sheet 级），随所属面板同开同收 */
    $("review-foot").hidden = id !== "review";
    $("relogin-foot").hidden = id !== "relogin";
    $("sheet-title").textContent = SHEET_TITLES[id];
    $("btn-sheet-close").hidden = sheetBusy();
    root.hidden = false;
    $("sheet-box").focus();
  }
  function closeSheet(force) {
    const root = $("sheet-root");
    if (!root || !model.sheetId) return;
    if (!force && sheetBusy()) {
      $("btn-sheet-close").hidden = true;   // 验证中：顺手把关闭钮也藏住
      return;
    }
    model.sheetId = "";
    root.hidden = true;
    $("more-panel").hidden = true;
    $("review-panel").hidden = true;
    $("confirm-panel").hidden = true;
    $("relogin-panel").hidden = true;
    $("review-foot").hidden = true;    // UI-F2：页脚随 sheet 收起
    $("relogin-foot").hidden = true;
    $("sheet-err").hidden = true;
    /* SEC-P3-3：重登 sheet 收起（含「取消」路径）即清账号/密码/验证码输入，
       重开时不得残留上一轮的密码；这些字段只属于重登 sheet，收其他 sheet 是空操作 */
    ["relogin-user", "relogin-pass", "code"].forEach((id) => {
      const el = $(id);
      if (el) el.value = "";
    });
    model.confirm = null;                   // RW03：确认档随 sheet 收起
    model.relConfirm = false;               // RL06：确认层是开 sheet 那一次的事
    const opener = model.sheetOpener;
    model.sheetOpener = null;
    if (opener && typeof opener.focus === "function") opener.focus();
  }
  /* SH06 操作失败红条（原型 netErr，Phone:870）：sheet 开着时写动作发不出去要就地说明 */
  function showSheetError(text) {
    if (!model.sheetId) return;
    const el = $("sheet-err");
    el.textContent = String(text || "");
    el.hidden = !text;
  }

  /* RL01–RL08 重登 sheet 渲染（原型 sh.isRelogin 段，Phone.dc.html:326-350）：
     取值全在 PhoneModel.reloginView，这里只写 DOM；面板显隐由 openSheet/closeSheet 管，
     refreshControls 每次都重画一遍（忙态、主钮与附言随模型走） */
  function renderRelogin() {
    const view = PhoneModel.reloginView(model.flow, model.reloginSetup, {
      confirm: model.relConfirm,
      starting: model.reloginStarting,
      submitting: model.reloginSubmitting,
      entered: model.relEnteredAcct,
      savedChoice: model.relSavedChoice,
      planBusy: model.busy,
    });
    $("rel-err").textContent = view.err;
    $("rel-err").hidden = !view.err;
    $("rel-spin").hidden = !view.spin;
    $("rel-busy-text").textContent = view.spin;
    $("rel-text").textContent = view.text;
    $("rel-text").hidden = !view.text;
    $("rel-form").hidden = !view.showForm;
    $("rel-lead").textContent = view.lead;
    $("rel-lead").hidden = !view.lead;
    $("relogin-account").hidden = !view.needAcct;
    $("relogin-captcha-group").hidden = !view.needCap;
    $("rel-auto").hidden = !view.autoCap;
    $("rel-save-gain").textContent = view.saveLine;
    /* 主钮三选一（原型 rel.submitLabel 槽）：登录 / 提交验证码 / 自动登录一次 */
    $("btn-relogin-auto").hidden = view.mainKind !== "auto";
    $("btn-relogin").hidden = view.mainKind !== "begin";
    $("btn-relogin-submit").hidden = view.mainKind !== "submit";
    $("rel-second-row").hidden = !(view.refresh || view.cancel);
    $("btn-relogin-refresh").hidden = !view.refresh;
    $("btn-relogin-cancel").hidden = !view.cancel;
    $("btn-relogin-done").hidden = !view.done;
    $("btn-relogin-done").textContent = view.done;
  }

  /* 重登 sheet 的入口（更多面板「在手机上重新登录」钮）：按 relogin_setup 决定先看哪一态——
     电脑存着账号且装了识别 → RL06 确认层（原型 beginRelogin 的 confirm 分支，Phone:654）；
     保存的密码不对 → RL07 relbad；有在途流程直接回到现场（RL01/RL03）。
     原型对「存了账号但没装识别」在 opener 上直接 begin（Phone:655）；这里留在表单初态
     由「登录」显式开始，不在导航点击里偷发写请求（偏差已记 result） */
  function openRelogin() {
    /* A-P1：openSheet 的「一次一张」守卫会拦掉从 more/review/confirm 直接切到重登，
       更多面板里的入口钮就点不动。切换语义：先收旧 sheet（确认档/重登确认层随
       收起），已在重登 sheet 则不重开。 */
    if (model.sheetId === "relogin") return;
    if (model.sheetId) closeSheet(true);
    const flow = model.flow;
    const liveFlow = !!(flow && flow.live
      && ["starting", "waiting_code", "verifying"].indexOf(String(flow.state || "")) >= 0);
    const setup = model.reloginSetup || {};
    model.relConfirm = !liveFlow && !setup.paused && !!setup.saved && !!setup.ocr_ready;
    openSheet("relogin");
    renderRelogin();
  }

  /* RW03/SH03/SH04 确认槽（原型 isConfirm，Phone.dc.html:311-314/874-879）：文案在
     PhoneModel.confirmView，这里只填 DOM；取消等待本任务接线，停止与取消一场共用
     同一槽（sheets-ops 迁移停止/取消 sheet 时复用）。
     用户决策 1（2026-11-08）：三处原生 confirm 全部改走 sheet 外壳。
     B-P1-1：取消一场要记住被点卡片那一场的 task_id（confirmView 只管文案）；
     UI-F5：动作失败不静默收场——sheet 保持打开，失败句写进 #sheet-err（SH06），
     成功才收 sheet；在途时禁用双钮防重发。 */
  function askConfirm(kind, taskName, taskId) {
    const view = PhoneModel.confirmView(kind, taskName);
    if (!view || model.sheetId) return;
    model.confirm = { kind: kind, taskId: taskId };
    openSheet("confirm");
    $("sheet-title").textContent = view.title;
    $("confirm-text").textContent = view.text;
    $("btn-confirm-no").textContent = view.no;
    $("btn-confirm-yes").textContent = view.yes;
    $("btn-confirm-no").disabled = false;    // 上一轮在途禁用过的钮要放开（UI-F5）
    $("btn-confirm-yes").disabled = false;
  }
  function onConfirmYes() {
    const slot = model.confirm;
    const kind = slot && slot.kind;
    const run = kind === "cancelstart" ? cancelPendingStart()
      : kind === "stop" ? stopPlan()
      : kind === "cancelTask" ? cancelTask(slot && slot.taskId) : null;
    if (!run) { closeSheet(true); return; }
    $("btn-confirm-yes").disabled = true;   // 在途防重发；失败分支重新放开
    $("btn-confirm-no").disabled = true;
    void Promise.resolve(run).then((ok) => {
      if (ok !== false) { closeSheet(true); return; }
      $("btn-confirm-yes").disabled = false;
      $("btn-confirm-no").disabled = false;
    });
  }

  /* G02 底栏左侧标题两行（原型 bar 段，Phone.dc.html:859-868）：草稿/核对中/运行中三态。
     RW02：核对中超过 15 秒对账窗（pendingLong）标题换「还没有查到结果」；
     运行中的来源标注「（从手机开始）」并入 bar-t（产品注记，原型无此句）。
     RS01（原型 isResult 的 .bar.stack，Phone.dc.html:295/933-934）：结果态整条换纵排两钮
     （重新选择仅在有未成功场时出现），左侧标题与三态主钮全收；
     TM01（原型 bar 分支，Phone.dc.html:863）：条款未同意副题换「电脑上同意条款后才能开始」，
     主钮禁用在 refreshControls（服务端同样拦写动作）；
     EX02（原型 Phone:864）：登录失效副题换「还差一步：重新登录」，主钮换「重新登录」
     并指向重登（原型 fn=beginRelogin；钮不禁用——这正是修复入口）；
     EX06（原型 Phone:865）：时钟待校准副题换「电脑校准北京时间后才能开始」+ 主钮禁用
     （canStart 拦）；
     EX05（原型 pclisterr 板没有 bar，Phone:860）：电脑列表失败时草稿态整条藏起，
     运行/核对/结果三态不受影响（停止计划在离线也必须可点）。 */
  function renderBar() {
    const title = $("bar-title");
    const sub = $("bar-sub");
    const bar = $("action-bar");
    const result = PhoneModel.resultView(model.plan, model.busy);
    bar.hidden = false;
    bar.className = result ? "bar stack" : "bar";
    $("bar-info").hidden = !!result;
    $("btn-reselect").hidden = !result || !result.canRetry;
    $("btn-finish").hidden = !result;
    if (result) {
      $("btn-start").hidden = true;
      $("btn-cancel-start").hidden = true;
      return;
    }
    const expired = PhoneModel.loginExpired(model.login);
    if (model.busy) {
      const fromPhone = model.plan && String(model.plan.source || "") === "phone"
        ? "（从手机开始）" : "";
      title.textContent = "计划进行中" + fromPhone;
      sub.textContent = "断网时也可以点停止";
    } else if (model.pending && !model.pending.done) {
      title.textContent = PhoneModel.pendingLong(model.pending, Date.now())
        ? "还没有查到结果" : "正在核对";
      sub.textContent = "请先不要重复点击";
    } else if (model.pcListError) {
      /* EX05（原型 Phone:860）：列表没加载就没有「已选 N 场」可言，整条不出 */
      bar.hidden = true;
      $("btn-start").hidden = false;
      return;
    } else {
      const picked = (model.items || []).filter(
        (item) => model.selected.indexOf(item.id) >= 0);
      title.textContent = "已选 " + model.selected.length + " 场";
      sub.textContent = model.termsOk === false
        ? "电脑上同意条款后才能开始"
        : (expired ? "还差一步：重新登录"                                  // EX02（Phone:864）
                   : (model.clockState === "unavailable"                   // EX06（Phone:865）
                      ? "电脑校准北京时间后才能开始"
                      : (PhoneModel.connState(model, model.flying).state === "off"  // UI-F3：离线不冒充「已选 N 场，可开始」
                         ? "连上电脑后才能开始"
                         : PhoneModel.planSummary(picked, PhoneModel.businessNowS(model)))));
    }
    /* EX02：登录失效时底栏主钮换成「重新登录」（点击在 wire 里分流到 openRelogin） */
    $("btn-start").textContent = expired && !model.busy
      && !(model.pending && !model.pending.done) ? "重新登录" : "核对并开始";
    $("btn-start").hidden = model.busy;
  }

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
    const shown = PhoneModel.visibleItems(model.items, model.filter,
      clockNow !== null ? clockNow : Date.now() / 1000).some((it) => it.id === id);
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
  const LIST_ZONES = [
    ["items", ["正在开放", "今天"]],
    ["upcoming-items", ["明天", "后天", "待公布", "更晚开放", "已报名", "已截止"]],
    ["signed-items", []],
  ];

  function renderItems() {
    model.nowMs = Date.now();
    const nowS = PhoneModel.businessNowS(model);
    /* RS01：结果态供任务卡/底栏/列表开合共用；termsOk 传给行禁用（TM01） */
    const result = PhoneModel.resultView(model.plan, model.busy);
    const view = PhoneModel.listView(model.items, model.filter, {
      nowS: nowS, wallS: model.nowMs / 1000,
      selected: model.selected, busy: model.busy, termsOk: model.termsOk,
    });
    const zoneCount = [0, 0, 0];
    LIST_ZONES.forEach((zone, zi) => {
      const box = $(zone[0]);
      if (!box) return;
      box.textContent = "";
      view.groups.forEach((group) => {
        if (zone[1].indexOf(group.title) < 0) return;
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

  /* G04 四站进度渲染（原型 .rail，Phone.dc.html:267/820-825）：四个站台各带圆点与虚线，
     状态词 done/now/hot 由 taskRail 给；aria-hidden 照原型（板题/副题已说明进展）。
     标签包一层 span：测试沙箱的 DOM 替身没有 createTextNode */
  function renderRail(rail) {
    const box = $("board-rail");
    if (!box) return;
    const steps = rail || [];
    box.hidden = !steps.length;          // 原型 hasRail：草稿/等待没有 rail
    box.textContent = "";
    steps.forEach((step) => {
      const div = document.createElement("div");
      if (step.state) div.className = step.state;
      const dot = document.createElement("i");
      const label = document.createElement("span");
      label.textContent = step.label;
      div.appendChild(dot);
      div.appendChild(label);
      box.appendChild(div);
    });
  }

  /* LD01/LD02 草稿板 + G04 运行/等待板 + RS01 结果板 + TM01 条款板（原型 board 段，
     Phone.dc.html:260-270/799-827/828-840/798）：草稿态取 listView().board；等待态取
     pendingBoard（RW02）；运行态取 runBoard；计划结束换结果板（LED/cap 换统计区）；
     条款未同意的草稿态整板换已暂停（Phone:798） */
  function renderBoard(view) {
    const section = $("plan-board");
    if (!section) return;
    const pendingNow = !!(model.pending && !model.pending.done);
    const result = PhoneModel.resultView(model.plan, model.busy);
    let board = null;
    if (model.busy) {
      board = PhoneModel.runBoard(model.plan, PhoneModel.businessNowS(model),
        PhoneModel.connState(model, model.flying).state === "off",
        model.lastOkText);   // EX01：离线档 capB「最后同步 HH:MM:SS」用同步成功时记下的北京时间
    } else if (pendingNow) {
      board = PhoneModel.pendingBoard(model.pending, Date.now());
    } else if (result) {
      board = { tag: result.head.text, tagTone: result.head.tone,
                title: result.title, sub: result.text };
    } else if (model.termsOk === false) {
      board = PhoneModel.termsBoard();
    } else {
      board = view.board;
    }
    section.hidden = !board;
    /* RS01：结果板描边色档照原型 boardCls（st-ok/st-warn/st-bad），其余档复位 */
    section.className = "board"
      + (result && result.boardCls ? " " + result.boardCls : "");
    if (!board) return;
    const tag = $("board-tag");
    tag.className = "b-tag" + (board.tagTone ? " " + board.tagTone : "");
    $("board-tag-text").textContent = board.tag;
    const nowS = PhoneModel.businessNowS(model);
    const nowLine = $("board-now");
    /* EX06（原型 nowText，Phone.dc.html:928）：时钟待校准时这一位写「待校准」，
       不再整段藏起——板头始终占位，与电脑端「北京时间」位同一呈现 */
    nowLine.hidden = false;
    $("board-now-text").textContent = nowS !== null
      ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)) : "待校准";
    /* RS01：结果态 LED 与 cap 收起，换统计大数字区（原型 isResult，Phone.dc.html:262） */
    $("board-led-wrap").hidden = !!result;
    $("board-cap").hidden = !!result;
    $("board-stats").hidden = !result;
    $("board-title").textContent = board.title;
    $("board-sub").textContent = board.sub;
    if (result) {
      renderStats(result.counts);
      renderRail([]);                        // 结果板没有四站进度（原型 notResult 才画 rail）
      model.pickId = "";
      $("btn-pick-next").hidden = true;
      return;
    }
    $("board-led-wrap").className = "led-wrap " + board.led.tone;
    $("board-led-wrap").setAttribute("role", "img");
    $("board-led-wrap").setAttribute("aria-label", board.led.aria);
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
    renderRail(board.rail);
    model.pickId = board.pickId || "";
    $("btn-pick-next").hidden = !board.pickId;
  }

  /* RS01 统计区渲染（原型 res.counts 循环，Phone.dc.html:262/832）：只显非零、
     tone 写在 div 上供 .stats 色档着色 */
  function renderStats(counts) {
    const box = $("board-stats");
    box.textContent = "";
    (counts || []).forEach((n) => {
      const div = document.createElement("div");
      if (n.tone) div.className = n.tone;
      const num = document.createElement("strong");
      num.textContent = String(n.n);
      const label = document.createElement("span");
      label.textContent = n.text;
      div.appendChild(num);
      div.appendChild(label);
      box.appendChild(div);
    });
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

  /* G10 任务卡 + 运行提示（原型 hasTasks/tip，Phone.dc.html:272-277/842-848）：
     每场结论由任务卡承载（renderTasks），原 #plan-line 的一行拼接退役；
     tip 只在运行中显示（原型 isRun），文案照 Phone:276 逐字（「演示：」控件不进产品） */
  function renderPlan() {
    renderTasks();
    const tip = $("run-tip");
    tip.textContent = "手机能锁屏，电脑不能关机或睡眠。要改，回电脑点“修改计划”，或者停止后重新选。";
    tip.hidden = !model.busy;
  }

  /* G10 任务卡渲染（原型 .tasks/.task，Phone.dc.html:145-153/272-274）：数值来自
     taskCard，这里只建元素、只写 textContent；卡上的「取消这一场」先过确认槽
     （RW03/SH04），并带上这一场的 task_id（B-P1-1，见 cancelTask 的注释） */
  function renderTasks() {
    const box = $("plan-tasks");
    if (!box) return;
    const tasks = (model.plan && model.plan.tasks) || [];
    /* 原型 hasTasks：running || result（Phone.dc.html:929；RS01 结果态任务卡也渲染，
       原因三句见 taskCard 的 RS02 注） */
    box.hidden = !(model.busy || PhoneModel.resultView(model.plan, model.busy)) || !tasks.length;
    box.textContent = "";
    if (box.hidden) return;
    const nowS = PhoneModel.businessNowS(model);
    tasks.forEach((task) => {
      const card = PhoneModel.taskCard(task, Number(task.max_attempts) || 0, nowS);
      const el = document.createElement("div");
      el.className = "task";
      const name = document.createElement("b");
      name.textContent = card.name;
      const ts = document.createElement("span");
      ts.className = "ts" + (card.tone ? " " + card.tone : "");
      ts.textContent = card.label;
      const detail = document.createElement("small");
      detail.textContent = card.detail;
      el.appendChild(name);
      el.appendChild(ts);
      el.appendChild(detail);
      if (card.canCancel) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "t-cancel";
        btn.textContent = "取消这一场";
        /* B-P1-1：确认槽带上被点卡片这一场的 task_id（onConfirmYes→cancelTask） */
        btn.addEventListener("click", () => askConfirm("cancelTask", card.name, task.task_id));
        el.appendChild(btn);
      }
      box.appendChild(el);
    });
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
      $("pair").hidden = true;
      $("app").hidden = false;
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
    stopPairLock();                    // 会话都没了，旧锁定倒计时一并收回
    $("app").hidden = true;
    $("pair").hidden = false;
    renderPair();                      // A-BUG-5：回配对页要按当前模型重画点阵屏，不残留旧点亮状态
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
    if (state.retry_options && Array.isArray(state.retry_options.choices)) {
      model.retryOptions = state.retry_options;
      fillRetryOptions(state.retry_options);
    }
    (payload.events || []).forEach((event) => {
      model.seq = Math.max(model.seq, Number(event.seq || 0));
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
      /* A-BUG-1：提示只在未决时给——accepted 的防双击窗口静默拦（开始已受理，
         不是「还没核对完」）；canceled/rejected 已在 startPending 放行，不会进来 */
      if (model.pending && !model.pending.done) {
        setBanner("上一次开始还没核对完，请先等结果", "info");
      }
      return;
    }
    /* A-BUG-1：走到这里说明没有未决的开始（终态 pending 已放行）——一律发新 request_id */
    const requestId = PhoneModel.newRequestId();
    model.pending = { request_id: requestId, at: Date.now(), done: false };
    model.notice = "";      // 原型 startState 会清掉勾选冲突提示（Phone.dc.html:540），计划已发出不再适用
    model.listOpen = false; // 原型 startState listOpen:false：计划一开始就收起活动列表（RW01）
    refreshControls();
    const { status, body } = await postAction({ action: "start_plan", args: {
      items, headed: false,
      retry_policy: { retry_for_s: Number(model.retry.retry_for_s),
                      max_attempts: Number(model.retry.max_attempts || 0) },
      request_id: requestId } });
    if (status === 401) return;
    if (body && body.ok && !body.pending) {
      model.pending.done = true;
      model.pending.outcome = "accepted";   // A-BUG-1：同步受理也记终态，保留防双击窗口
    }
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
      model.pending.outcome = body.state;   // A-BUG-1：终态原因随 pending 记下
      /* A-BUG-3：rejected/canceled 不能静默收口——回包文本（有则）或状态词亮到
         banner；accepted 照旧清掉「核对中」一类的提示 */
      if (body.state === "accepted") setBanner("");
      else setBanner(String(body.text || (body.state === "canceled"
        ? "开始已取消" : "开始请求被拒绝")),
        body.state === "canceled" ? "info" : "error");
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
    // RW03：确认改走 sheet（askConfirm("cancelstart")，用户决策 1），这里只做取消动作。
    // UI-F5：失败经 showSheetError 就地说明并回 false，成功收 sheet
    if (!model.pending || model.pending.done || model.cancelingStart) return false;
    const pending = model.pending;
    model.cancelingStart = true;
    try {
      const { body } = await postAction({action:"cancel_start_request",
        args:{request_id:pending.request_id}});
      if (body && body.ok && body.state === "canceled") {
        pending.done = true;
        pending.outcome = "canceled";   // A-BUG-1：终态原因随 pending 记下，立即放行新的开始
        setBanner("已取消这次开始，可以重新选择报名活动。", "info");
      } else {
        showSheetError(String((body && (body.text || body.error))
          || "取消结果尚未确认，请刷新核对"));
        return false;
      }
    } finally {
      model.cancelingStart = false;
      refreshControls();
    }
    if (model.paired) void poll(true);
    return true;
  }
  async function stopPlan() {
    // SH03：确认改走 sheet（askConfirm("stop")，用户决策 1），这里只做停止动作。
    // UI-F5：失败经 showSheetError 就地说明并回 false，成功收 sheet
    const planId = model.plan && model.plan.plan_id;
    if (!planId) return false;
    const { body } = await postAction({ action: "stop_plan", args: { plan_id: planId } });
    if (body && body.error) {
      showSheetError("没能停止计划：" + String(body.text || body.error));
      return false;
    }
    void poll(true);
    return true;
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
  /* 取消一场（SH04）：确认改走 sheet（askConfirm("cancelTask")，用户决策 1），这里只做动作。
     B-P1-1：取消被点卡片的那一场——后端（Api.cancel_task→PlanCoordinator.cancel_task→
     phone_rules 白名单）本就收任意 task_id，桌面端也早就在发任意 taskId；
     旧实现固定发 tasks[0] 是前端自设的限制，多场计划会取消错对象。
     UI-F5：失败经 showSheetError 就地说明并回 false（确认 sheet 保持打开），成功收 sheet */
  async function cancelTask(taskId) {
    const planId = model.plan && model.plan.plan_id;
    const task = ((model.plan && model.plan.tasks) || [])
      .find((t) => t && String(t.task_id) === String(taskId));
    if (!planId || !task) return false;
    const { body } = await postAction({
      action: "cancel_task", args: { plan_id: planId, task_id: task.task_id } });
    if (body && body.error) {
      showSheetError("没能取消这一场：" + String(body.text || body.error));
      return false;
    }
    void poll(true);
    return true;
  }
  /* RS01 结果态底栏两钮（原型 reselect/finishView，Phone.dc.html:933-934）：都清计划回草稿，
     并按 plan_id 记住已收起（服务端快照一直带终态计划，见 ingest 的 dismissedPlanId）。
     重新选择：把没成功（failed/canceled）的场放回选择集——放回的依据是 state.activities
     里对应活动仍可选（actionable：未报名、未截止、时间已知、不与已报名冲突）；
     放不回的场（已截止/时间未知）记进运行记录，不硬塞进勾选（原型是无条件放回，偏差已记） */
  function reselectFailed() {
    const tasks = (model.plan && model.plan.tasks) || [];
    model.dismissedPlanId = String((model.plan && model.plan.plan_id) || "");
    model.plan = null;
    const picked = [];
    let skipped = 0;
    tasks.forEach((t) => {
      const st = String(t.status || "");
      if (st !== "failed" && st !== "canceled") return;
      const item = (model.items || []).find((i) => i && i.id === t.activity_id);
      if (item && PhoneModel.actionable(item, model.items)) picked.push(item.id);
      else skipped += 1;
    });
    model.selected = picked;
    model.listOpen = false;
    model.notice = "";
    if (skipped > 0) addLog("有 " + skipped + " 场已截止或时间冲突，没能放回选择集，可另选其他场次");
    renderItems();
    renderPlan();   // A-BUG-2：任务卡随计划清空立即重画，不残留旧卡到下一次 poll
  }
  function finishPlanView() {
    model.dismissedPlanId = String((model.plan && model.plan.plan_id) || "");
    model.plan = null;
    model.selected = [];
    model.listOpen = false;
    model.notice = "";
    renderItems();
    renderPlan();   // A-BUG-2：完成后 #plan-tasks 立即清空，不等下一次轮询
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
  /* SH01 核对 sheet 渲染（原型 isReview 段，Phone.dc.html:302-309）：批次头+条目+移除钮
     （reviewBatches）、提醒 ul.pw（preStartWarnings）；尝试设置字段为静态 markup
     （#retry-panel 随 SH01 从更多面板迁入），这里只写动态部分；主钮文案随提醒切换 */
  function renderReview() {
    const picked = (model.items || []).filter((item) => model.selected.indexOf(item.id) >= 0);
    const box = $("review-items");
    box.textContent = "";
    PhoneModel.reviewBatches(picked, PhoneModel.businessNowS(model)).forEach((batch) => {
      const head = document.createElement("div");
      head.className = "bh";
      const time = document.createElement("b");
      time.textContent = batch.time;
      const note = document.createElement("span");
      note.textContent = batch.note;
      head.appendChild(time);
      head.appendChild(note);
      box.appendChild(head);
      batch.items.forEach((tk) => {
        const row = document.createElement("div");
        row.className = "tk";
        const main = document.createElement("div");
        const name = document.createElement("b");
        name.textContent = tk.name;
        main.appendChild(name);
        if (tk.act) {
          const act = document.createElement("small");
          act.textContent = tk.act;
          main.appendChild(act);
        }
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "ic";
        btn.setAttribute("aria-label", tk.aria);
        btn.dataset.id = tk.id;
        /* 移除钮图标（原型 tk.remove 的 X，Phone:771）：静态常量串，不带任何用户数据 */
        btn.innerHTML = '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"></path></svg>';
        row.appendChild(main);
        row.appendChild(btn);
        box.appendChild(row);
      });
    });
    const warns = PhoneModel.preStartWarnings(model, picked);
    $("review-warns").innerHTML = warns.map((text) => "<li>" + PhoneModel.escape(text) + "</li>").join("");
    $("review-warns").hidden = !warns.length;   // 原型 hasPreWarn：没有提醒整块不出
    $("btn-review-start").textContent = warns.length ? "仍然开始报名计划" : "开始报名计划";
  }
  /* SH01 移除条目（原型 tk.remove，Phone:771）：走现有勾选反选（toggle off），不发任何动作；
     移除后计划空了就关 sheet（原型 setState({sheet:''})）。监听挂在 #review-items 上
     （事件委托），重画批次不会叠监听 */
  function removeFromReview(id) {
    const res = PhoneModel.pickItem(model.selected, model.items, id, false);
    model.selected = res.selected;
    model.notice = "";
    renderItems();
    if (!model.selected.length) closeSheet(true);
    else renderReview();
  }
  function openReview() {
    if ($("btn-start").disabled) return;
    renderReview();
    openSheet("review");   // G03：核对面板迁进 sheet 外壳
  }

  /* 流程结束（成功或中断）：收起整组验证码输入，只留"重新开始"入口 */

  /* 流程收尾（成功/失败/取消/auto 接手）：收掉本场验证码图；
     表单与按钮的显隐由 renderRelogin 按 reloginView 重画（refreshControls 里调用） */
  function endReloginControls() {
    $("captcha").hidden = true;
    $("captcha").removeAttribute("src");
  }
  function ingestRelogin(info) {
    model.flow = info;
    const relayState = String(info.state || "");
    if (String(info.mode || "") === "auto"
        && relayState !== "success" && relayState !== "failed" && relayState !== "canceled") {
      // 电脑自己认图：手机不给验证码，也就不可能和电脑抢同一张图。
      // 这里只报进度；连续失败到阈值后服务端会把 mode 换成 manual，图自然会来。
      // （auto 的终态落到底下各自的分支：RL03 只描述「正在进行」）
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
      endReloginControls();
      refreshControls();
      return;
    }
    if (relayState === "waiting_code" && info.challenge_id) {
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
      refreshControls();   // renderRelogin：RL01 captcha 态（图+输入+三钮）
      return;
    }
    if (relayState === "verifying") {
      // 提交已经被 worker 收下、正在校验：RL02 归并成「正在登录，请等结果」，
      // 整组收起 + sheet 加锁（sheetBusy），想对同一张图重发也没有入口
      model.reloginSubmitting = false;
      $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;
    } else if (relayState === "starting") {
      // 进程刚起来还没出验证码：RL02 按档给「正在向电脑要验证码…」/「正在准备…」
      model.reloginSubmitting = false;
      $("relogin-note").textContent = String(info.mode || "") === "auto"
        ? PhoneModel.RELOGIN_BUSY.prepare : PhoneModel.RELOGIN_BUSY.needCode;
    } else if (relayState === "success") {
      model.challenge = null;
      model.reloginSubmitting = false;
      endReloginControls();
      if (info.live) {
        /* RL08（原型 Phone:892-894）：完成态两套文案照原型；计划在跑＝照常继续，
           闲时＝列表已刷新但计划不会自动重新开始 */
        $("relogin-note").textContent = model.busy
          ? "重新登录成功，报名计划照常继续。"
          : "重新登录成功，活动列表已刷新。计划不会自动重新开始，要你重新核对后再点开始。";
        void poll(true);
      } else {
        // 中继在空闲时会回上一场的结论：那是历史，不是这一次。只按 live 播报，
        // 否则每次打开手机页都会把很早以前那一次成功再演一遍。
        $("relogin-note").textContent = "上次重新登录已完成；需要时点「重新登录」再试";
      }
    } else if (relayState === "failed" || relayState === "canceled") {
      model.challenge = null;
      model.reloginSubmitting = false;
      endReloginControls();
      const reason = String(info.safe_error || relayState);
      /* B-P2-1：bad_password 走原型整句（两处「结束」呈现同一映射），其余码保留前缀+码 */
      $("relogin-note").textContent = info.live
        ? PhoneModel.reloginFailText(reason)
        : PhoneModel.reloginFailText(reason, "上次重新登录未完成：");
    } else if (relayState && relayState !== "waiting_code") {
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
    /* RL06：确认层用完即收；RL08 附言：先清上一轮的「输过账号/勾了保存」 */
    model.relConfirm = false;
    model.relEnteredAcct = false;
    model.relSavedChoice = false;
    refreshControls();
    /* 手机上输了账号密码就带上（默认不保存，勾选才保存到电脑）；没输就用电脑上保存的 */
    const args = {};
    const account = $("relogin-account");
    if (account && !account.hidden) {
      const user = String(($("relogin-user") || {}).value || "").trim();
      const pass = String(($("relogin-pass") || {}).value || "");
      if (!user || !pass) {
        // 主钮已按 relCanSubmit 禁用，这里是直调/竞态的保险丝
        model.reloginStarting = false;
        $("relogin-note").textContent = "账号和密码都要填。";
        refreshControls();
        return;
      }
      args.username = user;
      args.password = pass;
      args.save = !!($("relogin-save") || {}).checked;
      model.relEnteredAcct = true;       // RL08 附言：这一轮输过账号
      model.relSavedChoice = args.save;
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
    /* RL02：旧句「等待验证码…」归并为「正在向电脑要验证码…」，快照马上接管 */
    $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.needCode;
    refreshControls();
    void poll(true);
  }
  async function submitRelogin() {
    const code = String($("code").value || "").trim();
    if (!model.flow || !model.challenge) return;
    if (!PhoneModel.canSubmitRelogin(model, model.challenge)) return;
    if (!PhoneModel.relCanSubmit({ needCap: true, code })) return;   // relCanSubmit（原型 Phone:675）：4 位才发
    if (!PhoneModel.matchesChallenge(model.flow, model.challenge.flow_id,
                                     model.challenge.challenge_id)) {
      $("relogin-note").textContent = "验证码已换代，请看新图";
      $("code").value = "";
      return;
    }
    model.reloginSubmitting = true;
    refreshControls();   // renderRelogin：RL02「正在登录，请等结果」+ sheet 锁定
    let result;
    try {
      result = await api("/api/action", { method: "POST",
        body: { action: "phone_relogin_submit", args: {
          flow_id: model.challenge.flow_id,
          challenge_id: model.challenge.challenge_id, code } } });
    } catch (err) {
      // 结果未知：既不能当成功也不能当失败。保持禁用，先对账问服务端
      // 这张图到底有没有在途提交，等快照给结论再决定放行还是收口。
      // RL02：旧句「提交结果未知，正在对账…」归并为「正在登录，请等结果」
      $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;
      void poll(true);
      return;
    }
    if (!result || result.status !== 200 || !result.body || !result.body.ok) {
      const error = String((result && result.body && result.body.error) || "");
      if (error === "duplicate_submit") {
        // 服务端说同一张图还有在途提交：别解锁，等它的结论再放行
        // RL02：旧句「验证码正在提交，请等待结果」同样归并进「正在登录，请等结果」
        $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;
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
    const flow = model.flow;
    const flowId = flow && String(flow.flow_id || "");
    /* 没有在途流程（表单初态/确认层）取消只是收起：不发无谓的 cancel POST；
       终态的历史现场（live=false）同样没有东西可撤 */
    if (!flowId || (flow && flow.live === false)) return true;
    const { body } = await postAction({
      action: "phone_relogin_cancel", args: { flow_id: flowId } });
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
    /* PA03：点阵屏只是可视化层，输入仍走 #pair-code；数字归一化照原型 onCode、
       Enter 提交照原型 onCodeKey（Phone:922），输入即清上一轮错误 */
    $("pair-code").addEventListener("input", () => {
      const el = $("pair-code");
      const digits = String(el.value || "").replace(/\D/g, "").slice(0, 6);
      if (el.value !== digits) el.value = digits;
      model.pairErr = "";
      renderPair();
    });
    $("pair-code").addEventListener("keydown", (event) => {
      if (event && event.key === "Enter") void pair();
    });
    $("btn-refresh").addEventListener("click", () => void poll(true));
    /* EX01（原型 alert.fn=refresh，Phone.dc.html:852）：离线告警上的「重试」＝同一次刷新 */
    $("btn-offline-retry").addEventListener("click", () => void poll(true));
    /* UI-F13（原型 Phone:857 的 fn=setState({bookmark:false})）：「知道了」收起
       配对成功告警，本会话不再出现 */
    $("btn-pair-ok").addEventListener("click", () => {
      model.pairOkPending = false;
      renderAlerts(PhoneModel.isStale(model.lastOkAt, model.nowMs));
    });
    /* G03：更多钮开 sheet（先迁更多面板；停止/取消/重登随各自任务迁） */
    $("btn-more").addEventListener("click", () => openSheet("more"));
    /* sheet 外壳：关闭钮、点遮罩、Esc 三条收起路径；验证中由 closeSheet 自己拦 */
    $("btn-sheet-close").addEventListener("click", () => closeSheet());
    $("sheet-root").addEventListener("click", (event) => {
      if (event && event.target === event.currentTarget) closeSheet();
    });
    document.addEventListener("keydown", (event) => {
      if (event && event.key === "Escape") closeSheet();
    });
    /* 开始前先核对计划：列出已选场次、尝试设置和开始前提醒，确认后才真的开始。
       EX02（原型 bar.fn=beginRelogin，Phone.dc.html:864）：登录失效时这颗主钮换成
       「重新登录」，直接开重登 sheet——canStart 不拦登录失效（只拦过时/忙），
       服务端会拦真正的开始，这里不给用户一条必然失败的路 */
    $("btn-start").addEventListener("click", () => {
      if (PhoneModel.loginExpired(model.login) && !model.busy
          && !(model.pending && !model.pending.done)) openRelogin();
      else openReview();
    });
    /* EX02（原型 alert.fn=beginRelogin，Phone.dc.html:854）：告警条上的「重新登录」 */
    $("btn-banner-relogin").addEventListener("click", () => openRelogin());
    $("btn-review-start").addEventListener("click", () => { closeSheet(true); void startPlan(); });
    $("btn-review-back").addEventListener("click", () => closeSheet());
    /* SH01 批次条目的移除钮（原型 tk.remove，Phone:771）：委托在容器上，
       按 dataset.id 走勾选反选；图标钮自身不带监听 */
    $("review-items").addEventListener("click", (event) => {
      const id = event && event.target && event.target.dataset
        ? String(event.target.dataset.id || "") : "";
      if (id) removeFromReview(id);
    });
    /* RW03/SH03：停止与取消等待先过确认槽（原型 isConfirm，用户决策 1）；
       卡上的「取消这一场」在 renderTasks 里接 askConfirm("cancelTask")（SH04） */
    $("btn-stop").addEventListener("click", () => askConfirm("stop"));
    $("btn-cancel-start").addEventListener("click", () => askConfirm("cancelstart"));
    $("btn-confirm-no").addEventListener("click", () => closeSheet());
    $("btn-confirm-yes").addEventListener("click", () => onConfirmYes());
    /* RS01 结果态两钮（原型 reselect/finishView，Phone.dc.html:933-934）：纯前端回草稿，
       不发任何写动作 */
    $("btn-reselect").addEventListener("click", () => reselectFailed());
    $("btn-finish").addEventListener("click", () => finishPlanView());
    /* RW01 列表开合（原型 toggleList，Phone.dc.html:930） */
    $("btn-toggle-list").addEventListener("click", () => {
      model.listOpen = !model.listOpen;
      renderItems();
    });
    if ($("btn-show-window")) {
      $("btn-show-window").addEventListener("click", () => void showComputerWindow());
    }
    /* RL 迁移：更多面板的入口钮开重登 sheet（RL01 题），表单动作都在 sheet 里 */
    $("btn-relogin-open").addEventListener("click", () => openRelogin());
    $("btn-relogin").addEventListener("click", () => void beginRelogin());
    /* RL06（原型 autoRelogin，Phone:661 口径）：确认后交给电脑自动登录，手机只看进度 */
    $("btn-relogin-auto").addEventListener("click", () => void beginRelogin());
    $("btn-relogin-submit").addEventListener("click", () => void submitRelogin());
    $("btn-relogin-cancel").addEventListener("click", async () => {
      model.relConfirm = false;
      /* 取消成立（或本来就没有在途流程）才收 sheet；撤不掉就留着重试 */
      const ok = await cancelRelogin();
      if (ok !== false) closeSheet(true);
    });
    $("btn-relogin-refresh").addEventListener("click", () => void refreshRelogin());
    /* RL03/RL08 doneLabel（收起，在后台继续/完成）：auto 态不锁 sheet，直接收 */
    $("btn-relogin-done").addEventListener("click", () => closeSheet());
    /* relCanSubmit（原型 Phone:675）：主钮可用性随输入走 */
    ["relogin-user", "relogin-pass", "code"].forEach((id) => {
      $(id).addEventListener("input", () => refreshControls());
    });
    /* 折叠内 #q 快捷入口（LD03 保留）：与整页搜索框写同一个关键词 */
    $("q").addEventListener("input", () => {
      model.filter.q = $("q").value;
      if ($("search-q")) $("search-q").value = $("q").value;
      renderItems();
    });
    /* LD03 整页搜索：搜索钮开合（aria-expanded 随动），搜索框输入即筛 */
    $("btn-search").addEventListener("click", () => toggleSearch());
    $("search-q").addEventListener("input", () => {
      model.filter.q = $("search-q").value;
      if ($("q")) $("q").value = $("search-q").value;
      renderItems();
    });
    /* LD02 未选场详情卡的「选这一场」（原型 pickNext，Phone.dc.html:928） */
    $("btn-pick-next").addEventListener("click", () => {
      if (!model.pickId) return;
      const res = PhoneModel.pickItem(model.selected, model.items, model.pickId, true);
      model.selected = res.selected;
      model.notice = res.notice;
      renderItems();
    });
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
    renderPair();                      // PA01：配对视图首屏点亮点阵屏
  }

  globalThis.PhoneUI = { model, poll, wire, renderItems, refreshControls,
                         ingest, startPlan, cancelPendingStart, submitRelogin, beginRelogin,
                         cancelRelogin, refreshRelogin, showComputerWindow,
                         openSheet, closeSheet, renderPair, beginPairLock, pair,
                         toggleSearch, renderBoard, renderRelogin, openRelogin,
                         renderReview, askConfirm };   // SH01/SH03/SH04：核对渲染与确认槽供 vm 用例直接驱动
  if (document.readyState !== "loading") wire();
  else document.addEventListener("DOMContentLoaded", wire);
}
