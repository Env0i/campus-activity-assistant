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
  /* 开放状态：优先读电脑给出的 open_ts / close_ts，缺 close_ts 键时退回 PhoneModel.schoolSec(sign_end)；
   * 时钟不可用（nowS 为 null）时分辨不出 open/closed，按 pre/unknown 呈现「待校准」。 */
  stOf(item, nowS) {
    if (!item || item.signed) return "signed";
    if (item.closed) return "closed";
    const open = PhoneModel.openEpochOf(item);
    if (nowS !== null && nowS !== undefined) {
      const hasClose = Object.prototype.hasOwnProperty.call(item, "close_ts");
      const end = hasClose
        ? (typeof item.close_ts === "number" && Number.isFinite(item.close_ts) ? item.close_ts : null)
        : PhoneModel.schoolSec(item && item.sign_end);
      if (end !== null && nowS >= end) return "closed";
      if (open > 0 && nowS >= open) return "open";
    }
    return open > 0 ? "pre" : "unknown";
  },
  /* 时钟不可用时把 openEpochOf 时刻格式化为北京日历日组名，与桌面 relDayText 同口径 */
  openDayLabel(epochS) {
    const d = new Date((Number(epochS) + 8 * 3600) * 1000);
    const week = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
    return (d.getUTCMonth() + 1) + "月" + d.getUTCDate() + "日 " + week[d.getUTCDay()];
  },
  /* 时钟不可用时的组标题序：pre 场读 openEpochOf 按北京日历日升序，排在「待公布」「已报名」之前 */
  uncalibratedGroupTitles(visible) {
    const dayTitles = (visible || [])
      .filter((item) => PhoneModel.stOf(item, null) === "pre")
      .map((item) => PhoneModel.openEpochOf(item))
      .filter((open) => open > 0)
      .sort((a, b) => a - b)
      .map((open) => PhoneModel.openDayLabel(open))
      .filter((title, idx, arr) => arr.indexOf(title) === idx);
    return ["正在开放"].concat(dayTitles, ["待公布", "已报名", "已截止"]);
  },
  /* 列表分组名：nowS 有值时按今天/明天/后天/更晚开放分组；nowS 为 null 时不读手机时钟，按北京日历日分组 */
  groupKeyOf(item, st, nowS) {
    if (st === "signed") return "已报名";
    if (st === "open") return "正在开放";
    if (st === "closed") return "已截止";
    if (st === "unknown") return "待公布";
    if (nowS === null || nowS === undefined) {
      const open = PhoneModel.openEpochOf(item);
      return open > 0 ? PhoneModel.openDayLabel(open) : "待公布";
    }
    const diff = PhoneModel.dayOf(PhoneModel.openEpochOf(item)) - PhoneModel.dayOf(nowS);
    if (diff === 1) return "明天";
    if (diff === 2) return "后天";
    if (diff >= 3) return "更晚开放";
    return "今天";
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
  /* D9 类型、四层卡片与时间轴节点纯规则（只读活动对象与业务时钟，不碰 DOM） */
  activityTypeOf(item) {
    const raw = item && item.type;
    const text = raw === null || raw === undefined ? "" : String(raw).trim();
    return text || "其他";
  },
  cardDateTime(sec) {
    if (sec === null || sec === undefined || !Number.isFinite(sec)) return "";
    const d = new Date((sec + 8 * 3600) * 1000);
    return PhoneModel.pad2(d.getUTCMonth() + 1) + "-" + PhoneModel.pad2(d.getUTCDate())
      + " " + PhoneModel.pad2(d.getUTCHours()) + ":" + PhoneModel.pad2(d.getUTCMinutes());
  },
  compactActText(item, st) {
    const r = PhoneModel.actRange(item);
    if (!r) return (st === "open" || st === "pre") ? "举办时间待公布" : "时间待公布";
    const n = PhoneModel.spanDays(item);
    if (n <= 1) {
      const end = PhoneModel.endsAtMidnight(r.s, r.e)
        ? "24:00" : PhoneModel.cardDateTime(r.e).split(" ")[1];
      return PhoneModel.cardDateTime(r.s) + "–" + end;
    }
    const W = PhoneModel.WJ;
    return PhoneModel.cardDateTime(r.s) + " – " + PhoneModel.cardDateTime(r.e)
      + "（" + W + "跨" + W + n + W + "天" + W + "）";
  },
  attendanceCell(item, kind, noneLabel, verb) {
    const pend = item && item.attendance_state === "pending";
    const flag = item && item[kind + "_required"];
    if (flag === false) return { text: noneLabel, cls: "na", full: noneLabel };
    if (flag === true) {
      const s = PhoneModel.tsOf(item, kind + "_start_ts", kind + "_start");
      const e = PhoneModel.tsOf(item, kind + "_end_ts", kind + "_end");
      const hmOf = (sec) => PhoneModel.hhmmss(PhoneModel.beijingSecOf(sec)).slice(0, 5);
      const span = s !== null ? hmOf(s) + (e !== null && e > s ? "–" + hmOf(e) : "") : "";
      const text = span || ("需要" + verb);
      return { text: text, cls: "", full: span ? verb + " " + span : text };
    }
    return pend ? { text: "同步中", cls: "pend", full: verb + "信息同步中" }
      : { text: "待确认", cls: "na", full: verb + "时间待确认" };
  },
  cardSignEndText(item, st) {
    if (st !== "open" && st !== "pre") return "";
    const end = PhoneModel.tsOf(item, "close_ts", "sign_end");
    return end === null ? "" : PhoneModel.cardDateTime(end) + " 截止";
  },
  missedLayer4Text(item, st) {
    if (!item || !item.missed_by_sleep) return "";
    const open = PhoneModel.openEpochOf(item);
    const head = open > 0
      ? "电脑在 " + PhoneModel.hhmmss(PhoneModel.beijingSecOf(open)).slice(0, 5) + " 开放时睡着了"
      : "电脑睡着时错过了开放";
    return head + "，没有提交 · " + (st === "closed" ? "已截止" : "还能报");
  },
  rowFlags(st, clash, nextPreId, item) {
    if (clash) return [];
    const flags = [];
    if (st === "open") flags.push({ text: "立即报名", cls: "warn" });
    if (st === "pre") {
      const isNext = item.id === nextPreId;
      flags.push({ text: isNext ? "下一场" : "预报名", cls: isNext ? "next" : "" });
    }
    if (st === "signed") flags.push({ text: "已报名", cls: "signed" });
    if (st === "closed") flags.push({ text: "已截止", cls: "mute" });
    return flags;
  },
  /* G05 行呈现（原型 rows.map 的行对象，Phone.dc.html:738-762）：时刻大字 + 距开放 +
   * 旗标 + 时段/地点/奖励 + 行警；D9 升级为四层卡片纯数据，渲染层只建元素 */
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
    const termsOff = ctx.termsOk === false;
    /* TM01（原型 disabled 的 !s.termsOk 项，Phone.dc.html:742）：条款未同意列表行全禁用 */
    const disabled = !!ctx.busy || termsOff || st === "signed" || st === "closed"
      || st === "unknown" || !!hitSigned;
    const dimmed = termsOff || st === "signed" || st === "closed" || st === "unknown";
    const refund = (st === "open" || st === "pre") ? PhoneModel.refundFlag(item) : null;
    const open = PhoneModel.openEpochOf(item);
    const clockDown = nowS === null || nowS === undefined;
    const gap = open - (nowS || 0);
    /* 距开放（原型 left，Phone:760）：pre 且时钟不可用写「待校准」；10 分钟内与下一批标 soon 琥珀色，其余中性灰 */
    const left = st === "pre" ? (clockDown ? "待校准" : PhoneModel.leftCn(gap))
      : (st === "open" ? "已开放" : "");
    const soon = st === "pre" && !clockDown && (gap <= 600 || (ctx.nextOpenTs > 0 && open === ctx.nextOpenTs));
    const warn = hitSel ? "与已选的「" + hitSel.name + "」时间重叠" : "";
    const placeRaw = String(item.place || item.location || "").trim();
    const actCell = PhoneModel.compactActText(item, st);
    const missedText = PhoneModel.missedLayer4Text(item, st);
    const syncText = item.sync_pending && st === "signed" ? "报名已确认，学校列表正在同步" : "";
    const note = PhoneModel.cancelNote(item, nowS);
    const hasWarn = !!warn && !ctx.busy;
    return {
      id: item.id, item: item, name: PhoneModel.itemTitle(item), st: st, openTs: open,
      typeLabel: PhoneModel.activityTypeOf(item),
      selected: selected, disabled: disabled, clash: clash, signedItem: hitSigned || null,
      flags: PhoneModel.rowFlags(st, clash, ctx.nextPreId, item),
      rf: refund ? refund.text : "", rfNo: !!refund && refund.no, hasRf: !!refund,
      signEndText: PhoneModel.cardSignEndText(item, st),
      rw: PhoneModel.rewardText(item) || { cls: "", text: "" },
      time: st !== "unknown" ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(open)).slice(0, 5) : "待公布",
      timeCls: st !== "unknown" ? "" : "txt",
      hasLeft: !!left && !clash, left: left, leftCls: soon ? "soon" : "",
      act: actCell, actCell: actCell, actInvalid: !PhoneModel.actRange(item),
      place: placeRaw, hasPlace: !!placeRaw && st !== "closed",
      placeCell: placeRaw || "地点待定", placeNa: !placeRaw,
      inCell: PhoneModel.attendanceCell(item, "checkin", "无需签到", "签到"),
      outCell: PhoneModel.attendanceCell(item, "checkout", "无需签退", "签退"),
      warn: warn, hasWarn: hasWarn, missedText: missedText, syncText: syncText,
      note: note, hasL4: hasWarn || !!missedText || !!syncText || !!note,
      aria: "选择 " + PhoneModel.itemTitle(item),
      cls: "card-4l " + (clash ? "clash " : "") + (selected ? "sel " : "")
        + (disabled && !selected ? "off " : "") + (dimmed ? "dim" : ""),
    };
  },
  timelineNodes(rows, title, nowS, nextPreId, nextOpenTs) {
    const nodes = [];
    const byKey = new Map();
    const canBatchGroup = title !== "正在开放" && title !== "待公布" && title !== "已报名" && title !== "已截止";
    (rows || []).forEach((row) => {
      const open = row.st !== "unknown" ? Number(row.openTs || 0) : 0;
      const key = row.st === "unknown" ? "unknown" : row.st + "_" + String(open);
      if (!byKey.has(key)) {
        const sec = open > 0 ? PhoneModel.beijingSecOf(open) : 0;
        const secTail = sec % 60 ? ":" + PhoneModel.pad2(sec % 60) : "";
        const day = row.st === "pre" && open > 0 && nowS !== null && nowS !== undefined
          && PhoneModel.dayOf(open) !== PhoneModel.dayOf(nowS)
          ? PhoneModel.openDayLabel(open) : "";
        const nd = {
          key: key,
          time: row.st === "unknown" ? "待公布" : PhoneModel.hhmmss(sec).slice(0, 5) + secTail,
          timeCls: row.st === "unknown" ? "txt" : "",
          day: day, hasDay: !!day,
          dotCls: row.st === "unknown" ? "unknown" : (row.st === "open" ? "open" : "wait"),
          hasBatch: false, batchN: 0, rows: [],
        };
        byKey.set(key, nd);
        nodes.push(nd);
      }
      const node = byKey.get(key);
      if (node.dotCls === "wait" && (row.id === nextPreId || (nextOpenTs > 0 && open === nextOpenTs))) {
        node.dotCls = "next";
      }
      node.rows.push(row);
    });
    nodes.forEach((nd) => {
      nd.batchN = nd.rows.length;
      nd.hasBatch = canBatchGroup && nd.rows.length >= 2 && nd.rows.every((r) => r.st === "pre");
    });
    return nodes;
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
  /* 列表总聚合：只读业务时钟 nowS（不接收手机墙钟），未校准时按开放日组序呈现，组内附 D9 时间轴节点 */
  listView(items, filter, opts) {
    const options = opts || {};
    const nowS = options.nowS !== undefined ? options.nowS : null;
    const list = items || [];
    const pick = PhoneModel.nextPick(list, nowS);
    const nextOpenTs = pick.nextPreId
      ? PhoneModel.openEpochOf(list.find((i) => i && i.id === pick.nextPreId)) : 0;
    /* termsOk 缺省＝已同意（undefined !== false）：条款门只在快照明确说 false 时收紧（TM01） */
    const ctx = { items: list, nowS: nowS, selected: options.selected || [],
                  busy: !!options.busy, nextPreId: pick.nextPreId, nextOpenTs: nextOpenTs,
                  termsOk: options.termsOk !== false };
    const count = { free: 0, signed: 0, all: 0 };
    list.forEach((item) => {
      const st = PhoneModel.stOf(item, nowS);
      count.all += 1;
      if (st === "signed") count.signed += 1;
      if (st === "open" || st === "pre") count.free += 1;
    });
    const visible = PhoneModel.visibleItems(list, filter, nowS);
    const titles = nowS !== null && nowS !== undefined
      ? ["正在开放", "今天", "明天", "后天", "待公布", "更晚开放", "已报名", "已截止"]
      : PhoneModel.uncalibratedGroupTitles(visible);
    let nowPlaced = false;
    const nowText = nowS !== null && nowS !== undefined
      ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)).slice(0, 5) : null;
    const groups = [];
    titles.forEach((title) => {
      const rows = visible
        .filter((item) => PhoneModel.groupKeyOf(item, PhoneModel.stOf(item, nowS), nowS) === title)
        .map((item) => PhoneModel.rowView(item, ctx));
      if (!rows.length) return;
      const nowBefore = !nowPlaced && title !== "正在开放";
      if (nowBefore) nowPlaced = true;
      const hasRail = title !== "已报名" && title !== "已截止";
      const nodes = hasRail ? PhoneModel.timelineNodes(rows, title, nowS, pick.nextPreId, nextOpenTs) : [];
      groups.push({
        title: title, n: rows.length,
        cls: title === "正在开放" ? "open" : (title === "已报名" ? "signed" : ""),
        note: title === "正在开放" ? "现在就能报" : (title === "已截止" ? "只能查看" : ""),
        nowBefore: nowBefore, now: nowText, rows: rows, hasRail: hasRail, nodes: nodes,
      });
    });
    return {
      counts: count, groups: groups, total: visible.length,
      nextPreId: pick.nextPreId, nextIt: pick.nextIt, nextIsOpen: pick.isOpen,
      board: PhoneModel.draftBoard(list, nowS, options.selected || [], pick),
    };
  },
});
