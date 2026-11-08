/* 冲突原因、跨天时段与取消报名的纯规则（计划 20261107-conflict-cancel：R1/R2、X3/X4、U1；
 * 照原型 Main.dc.html 的 tipView / spanAbs / cxWhy 逐条对应）。
 * 只读活动字段与业务时钟（bnowS），不读本机墙钟；不碰 DOM。 */
const WJ = "\u2060";   /* U+2060 WORD JOINER：连住「（跨N天）」「这一场报不了。」，避免孤字换行 */

/* 把一句话逐字用 U+2060 连起来（原型里「这一场报不了。」每个字之间都有一个，Edge 才不会把句尾孤字挤到下一行） */
function glue(text) {
  return Array.from(String(text)).join(WJ);
}

function pad2(n) { return String(n).padStart(2, "0"); }

/* 绝对时刻「11月8日 22:40」：与列表原有日期写法一致，不写今天/明天，不带秒 */
function absWhen(sec) {
  const p = schoolParts(sec * 1000);
  return p.mo + "月" + p.d + "日 " + pad2(p.h) + ":" + pad2(p.mi);
}

/* 学校时区的日序号（自 1970-01-01 起的第几天），纯整数运算，不依赖本机时区 */
function schoolDayOf(sec) { return Math.floor((sec + SCHOOL_OFFSET_S) / 86400); }

/* 结束时刻恰为学校时间 00:00:00：按前一天算（R 跨 N 天口径） */
function endsAtMidnight(start, end) { return end > start && (end + SCHOOL_OFFSET_S) % 86400 === 0; }
function lastDayOf(start, end) { return schoolDayOf(endsAtMidnight(start, end) ? end - 1 : end); }

/* 跨 N 天 = 结束日期 − 开始日期 + 1；时段不合法返回 null */
function spanDays(item) {
  if (!validActivityTime(item)) return null;
  const s = toTs(item.act_start);
  const e = toTs(item.act_end);
  return lastDayOf(s, e) - schoolDayOf(s) + 1;
}

function crossDayMark(n) {
  return "（" + WJ + "跨" + WJ + n + WJ + "天" + WJ + "）";
}

/* 绝对日期时段：气泡一律用它；同一天「11月9日 08:00–17:00」，跨天带「（跨N天）」 */
function actSpanAbs(item) {
  const n = spanDays(item);
  if (n === null) return "活动时间待确认";
  const s = toTs(item.act_start);
  const e = toTs(item.act_end);
  if (n <= 1) return absWhen(s) + "–" + (endsAtMidnight(s, e) ? "24:00" : hm(e * 1000));
  return absWhen(s) + " – " + absWhen(e) + crossDayMark(n);
}

/* ---------------------------------------------------------------- 报后可退 / 可取消至 */
/* 未报名、等待开放或开放中的行：cancel_allowed 为 null 时不写 */
function refundFlag(item, state) {
  if (!item || item.signed || (state !== "waiting" && state !== "open")) return null;
  if (item.cancel_allowed === false) return { text: "报后不可退", no: true };
  if (item.cancel_allowed === true) return { text: "报后可退", no: false };
  return null;
}

/* 取消窗口：业务北京时间在 [报名开始, 报名截止] 内才是 true；
 * 时钟不可用或没有报名截止时无从判断，返回 null（不是 false） */
function cancelWindowOpen(item) {
  const now = bnowS();
  const end = toTs(item && item.sign_end);
  if (now === null || end === null) return null;
  const start = toTs(item.sign_start);
  if (start !== null && now < start) return false;
  return now <= end;
}

/* 已报名行显示「可取消至」与「取消报名」的唯一条件 */
function canCancelNow(item) {
  return !!item && !!item.signed && item.cancel_allowed === true && cancelWindowOpen(item) === true;
}

function cancelUntilText(item) {
  return "可取消至 " + absWhen(toTs(item.sign_end));
}

/* ---------------------------------------------------------------- 冲突气泡 */
/* 解除路径四选一（a 能取消 / b 不允许 / c 时间已过 / d 还没查到），依据已报名那场 */
function clashWay(sg) {
  const nm = "「" + sg.name + "」";
  const open = cancelWindowOpen(sg);
  const end = toTs(sg.sign_end);
  if (sg.cancel_allowed === true && open === true) {
    return { kind: "a", hasGo: true, text: "想报这一场，要先取消" + nm + "的报名，" + absWhen(end) + " 前可以取消。" };
  }
  if (sg.cancel_allowed === false) {
    return { kind: "b", hasGo: false, text: nm + "报名后不能取消，" + glue("这一场报不了。") };
  }
  if (sg.cancel_allowed === true && open === false) {
    return { kind: "c", hasGo: false, text: nm + "的取消时间已过（截至 " + absWhen(end) + "），" + glue("这一场报不了。") };
  }
  return { kind: "d", hasGo: false, text: nm + "能不能取消还没查到，刷新后再看。" };
}

/* 气泡内容的数据模型：两个时段、时间条（日序号换成百分比）与解除路径。
 * 重叠段按半开区间取交集；只在 signedClash 已确认两场重叠时调用。 */
function conflictTipModel(item, sg) {
  const a0 = toTs(sg.act_start);
  const a1 = toTs(sg.act_end);
  const b0 = toTs(item.act_start);
  const b1 = toTs(item.act_end);
  const lo = Math.min(schoolDayOf(a0), schoolDayOf(b0));
  const hi = Math.max(lastDayOf(a0, a1), lastDayOf(b0, b1));
  const n = hi - lo + 1;
  const base = lo * 86400 - SCHOOL_OFFSET_S;
  const total = n * 86400;
  const pc = (t) => Math.round((t - base) / total * 10000) / 100;
  const ov0 = Math.max(a0, b0);
  const ov1 = Math.min(a1, b1);
  const days = [];
  const cuts = [];
  for (let k = 0; k < n; k += 1) {
    const d = new Date((lo + k) * 86400000);
    days.push({ text: (d.getUTCMonth() + 1) + "月" + d.getUTCDate() + "日" });
    if (k) cuts.push({ left: pc(base + k * 86400) });
  }
  /* 跨很多天时日期标签挤不下：只留首尾 */
  const sparse = days.length > 7;
  const way = clashWay(sg);
  return {
    rows: [
      { label: "已报名", name: sg.name, span: actSpanAbs(sg) },
      { label: "这一场", name: item.name, span: actSpanAbs(item) },
    ],
    cuts: sparse ? [] : cuts,
    days: sparse ? [days[0], days[days.length - 1]] : days,
    sparse: sparse,
    ovL: pc(ov0), ovW: pc(ov1) - pc(ov0),
    aL: pc(a0), aW: pc(a1) - pc(a0),
    bL: pc(b0), bW: pc(b1) - pc(b0),
    aria: "时间线：" + absWhen(a0) + " 起的已报名活动与这一场在 " + absWhen(ov0) + " 到 " + absWhen(ov1) + " 重叠",
    way: way.text,
    wayKind: way.kind,
    hasGo: way.hasGo,
  };
}

/* ---------------------------------------------------------------- 取消报名 */
/* 取消按钮的互斥（X3）：返回 {off, why}。文案照原型 cxWhy；
 * 条款未同意与组件缺失沿用开始计划门禁里现成的说法。 */
function cancelBlock(id) {
  if (S.cancel.busyId && S.cancel.busyId === String(id)) return { off: true, why: "" };
  if (S.cancel.busyId) return { off: true, why: "正在取消另一场" };
  if (S.busy || S.starting) return { off: true, why: "计划在运行，先停下来再取消" };
  if (S.listState === "loading" || S.login.checking) return { off: true, why: "正在刷新，等它结束再取消" };
  if (S.login.loginPending || (S.login.view || {}).state === "pending") return { off: true, why: "正在登录，等它结束再取消" };
  if (termsLocked()) return { off: true, why: "先同意使用条款" };
  if (S.runtime.error) return { off: true, why: "程序组件缺失，看顶部提示" };
  return { off: false, why: "" };
}

/* 前置失败的原因码 → 一句话。前四条照原型；其余沿用 app 里现成的说法 */
const CANCEL_REASONS = {
  window_closed: "取消时间已过",
  not_allowed: "这个活动报名后不能取消",
  not_signed: "学校记录里没有这场报名",
  not_in_list: "学校记录里没有这场报名",
  clock_unavailable: "北京时间暂不可用",
  login_expired: "登录已失效",
  unknown_state: "暂时无法确认这场的报名状态",
  busy: "计划在运行或正在刷新，等它结束再取消",
};

/* 结果句：cancelled 绿、refused 红、unknown 琥珀、precheck 琥珀 */
function cancelResultView(res, name) {
  if (!res) return null;
  if (res.kind === "cancelled") return { cls: "ok", text: "已取消「" + name + "」的报名，学校记录已核对。" };
  if (res.kind === "refused") {
    return { cls: "bad", text: res.say ? "学校没有取消这场报名：" + res.say : "学校没有取消这场报名。" };
  }
  if (res.kind === "unknown") return { cls: "warn", text: "没能确认是否已取消，请到学校网站的活动详情里核对。" };
  if (res.kind === "precheck") {
    return { cls: "warn", text: "现在不能取消：" + (CANCEL_REASONS[res.reason] || res.say || "暂时不能取消") };
  }
  return null;
}
