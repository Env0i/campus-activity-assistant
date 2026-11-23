"use strict";

/* 手机页纯规则核心（首份加载，无前置脚本依赖）：
 * 定义 PhoneModel 与筛选、开放状态、倒计时、登录态及计划启停校验成员。 */

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

  /* 筛选：关键词 + 报名状态 + 开放时间（北京自然日，正在开放两档都留，未校准时不筛） */
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
      if (time !== "all" && nowS != null) {
        const open = PhoneModel.openEpochOf(item);
        if (!(open > 0)) return false;
        const diff = PhoneModel.dayOf(open) - PhoneModel.dayOf(nowS);
        if (PhoneModel.stOf(item, nowS) !== "open"
            && ((time === "today" && diff !== 0) || (time === "week" && (diff < 0 || diff > 6)))) return false;
      }
      return true;
    });
  },

  /* 开放时刻的 epoch 秒：读快照的 item.open_ts（由电脑端 school_epoch 换算）；
   * 缺 open_ts 键的旧夹具或预览退回严格格式校验并用 PhoneModel.schoolSec 校日历。 */
  openEpochOf(item) {
    if (!item) return 0;
    if (Object.prototype.hasOwnProperty.call(item, "open_ts")) {
      const ts = item.open_ts;
      return typeof ts === "number" && Number.isFinite(ts) && ts > 0 ? ts : 0;
    }
    const raw = typeof item.sign_start === "string" ? item.sign_start.trim() : "";
    if (!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(raw)) return 0;
    const ts = PhoneModel.schoolSec(raw);
    return ts !== null ? ts : 0;
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
  /* P1：离业务时间（北京时间）的下一个整秒还有多少毫秒。排程必须用显示时间的同一个
     起点——performance.now() 取整秒与 businessNowS 的小数偏移对不上，首个 tick 会偏近一秒；
     时间不可信（待校准）时退回 1 秒，仍比拉数据的周期短 */
  nextTickDelay(nowS) {
    const s = Number(nowS);
    if (!Number.isFinite(s) || s < 0) return 1000;
    const remain = 1000 - ((s * 1000) % 1000);
    return Math.min(1000, Math.max(16, remain));
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
    return (model.selected || []).length > 0
      && PhoneModel.actBlock(model.items, model.selected) === null;
  },
  /* 登录是否已失效（EX02）：session_expired、快照明说没有会话，或电脑最近一次学校校验
   * 说已失效（last_check_state=expired：本机会话文件还在也可能被学校判失效）；
   * 与 loginLine/ingest 同一口径。 */
  loginRaw(login) {
    return !!login && (!!login.session_expired || login.session_present === false
      || login.last_check_state === "expired");
  },
  /* 登录四态判法：依据 login.session_present、login.session_expired 与 login.last_check_state；
   * 非对象判 unknown，无会话（session_present===false）先于失效判 never，失效或校验 expired 判 expired，valid 判 valid，其余 unknown。 */
  loginState(login) {
    if (!login || typeof login !== "object" || Array.isArray(login)) return "unknown";
    if (login.session_present === false) return "never";
    if (login.session_expired || login.last_check_state === "expired") return "expired";
    if (login.last_check_state === "valid") return "valid";
    return "unknown";
  },
  /* 按四态集中返回横幅、底栏、重登入口与自动恢复文案（DOM 层只从这里取字）；未登录取「登录」，其余三态取「重新登录」。 */
  loginCopy(state, recovering) {
    if (state === "never") {
      return {
        bannerTitle: "电脑上还没有登录",
        bannerText: "可以在手机上登录，也可以回电脑处理。",
        bannerAction: "登录",
        barSub: "还差一步：登录",
        barAction: "登录",
        reloginEntry: "在手机上登录",
        recoveringLine: "电脑正在自动登录。",
        recoveringSub: "电脑正在自动登录，好了就能开始",
      };
    }
    return {
      bannerTitle: "电脑上的登录已失效",
      bannerText: "可以在手机上重新登录，也可以回电脑处理。",
      bannerAction: "重新登录",
      barSub: "还差一步：重新登录",
      barAction: "重新登录",
      reloginEntry: "在手机上重新登录",
      recoveringLine: "电脑正在自动重新登录。",
      recoveringSub: "电脑正在自动重新登录，好了就能开始",
    };
  },
  /* 电脑这一场静默自动登录还在进行（与桌面胶囊「自动登录中」同口径）：中继里是电脑自己发起、
   * 还在进行、没转人工的一场，或电脑快照里 recovering 为真（失效已判、中继还没起来）。
   * 转人工（等用户输验证码）后不算。 */
  loginRecovering(login, flow) {
    if (flow && flow.handoff) return false;
    const ended = flow && ["success", "failed", "canceled"].indexOf(String(flow.state || "")) >= 0;
    if (flow && !ended && String(flow.origin || "") === "auto" && flow.live) return true;
    return !!login && !!login.recovering;
  },
  /* 给 flow 时：电脑正在自动重新登录就不算失效（不出失效横幅、不写已失效）；
   * 不给 flow 时保持原口径（底栏「重新登录」主钮用它，那条入口会接上正在跑的这一场）。 */
  loginExpired(login, flow) {
    if (!PhoneModel.loginRaw(login)) return false;
    return flow === undefined ? true : !PhoneModel.loginRecovering(login, flow);
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
  /* items 与 nowS 可选：给 items 挡已报名冲突，给 nowS 按业务此刻排除已截止 */
  actionable(item, items, nowS) {
    if (!item || item.signed) return false;
    if (!item.open_ts && !item.sign_start) return false;      // 时间未知不可执行
    if (item.closed || (Number.isFinite(nowS) && !["open", "pre"].includes(PhoneModel.stOf(item, nowS)))) return false;
    if (items && PhoneModel.signedClash(item, items)) return false;   // 与已报名重叠：不可加入
    return true;
  },
};
