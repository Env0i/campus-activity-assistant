"use strict";

/* 手机页纯规则——冲突、跨天时段与状态摘要（依赖 model.js 先加载）：
 * 补齐时间格式化、时段重叠、取消说明、原因面板与顶底栏状态计算成员。 */

Object.assign(PhoneModel, {
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
  /* H4：设备睡眠检测。手机锁屏时 performance.now() 通常不走、Date.now() 照走；
     上一次 tick 以来两个钟走过的时长之差超过阈值，就说明中间睡过，推算出的业务时间落后了 */
  SLEEP_JUMP_MS: 2000,
  sleepJumped(mark, wallMs, monoMs) {
    if (!mark) return false;
    const drift = (wallMs - mark.wall) - (monoMs - mark.mono);
    return Number.isFinite(drift) && Math.abs(drift) > PhoneModel.SLEEP_JUMP_MS;
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
});
