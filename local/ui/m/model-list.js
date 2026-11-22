"use strict";

/* 手机页纯规则——列表与详情板（依赖 model.js、model-conflict.js 先加载）：
 * 补齐倒计时文案、开放分组、勾选冲突、行呈现与草稿板聚合成员。 */

Object.assign(PhoneModel, {
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
});
