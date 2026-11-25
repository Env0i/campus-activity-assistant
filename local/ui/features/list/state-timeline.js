/* 时间轴与四层卡片纯状态/格式化规则（只读活动字段与业务时钟，不碰 DOM）。 */

function pad2(n) {
  return String(n).padStart(2, "0");
}

/* 卡片内部统一使用 MM-DD HH:MM 日期格式（学校时区） */
export function cardDateTime(sec) {
  if (sec === null || sec === undefined) return "";
  const p = schoolParts(sec * 1000);
  return pad2(p.mo) + "-" + pad2(p.d) + " " + pad2(p.h) + ":" + pad2(p.mi);
}

export function cardCancelUntilText(item) {
  const end = toTs(item && item.sign_end);
  return end === null ? "" : "可取消至 " + cardDateTime(end);
}

export function cardSignEndText(item, state) {
  if (state !== "open" && state !== "waiting") return "";
  const end = toTs(item && item.sign_end);
  return end === null ? "" : cardDateTime(end) + " 截止";
}

/* 举办时段格子：MM-DD HH:MM–HH:MM（结束 00:00 写 24:00，跨天写 MM-DD HH:MM – MM-DD HH:MM） */
export function compactActText(item) {
  if (!validActivityTime(item)) return "时间待公布";
  const s = toTs(item.act_start);
  const e = toTs(item.act_end);
  const days = spanDays(item);
  if (days !== null && days <= 1) {
    const endClock = endsAtMidnight(s, e) ? "24:00" : hm(e * 1000);
    return cardDateTime(s) + "–" + endClock;
  }
  return cardDateTime(s) + " – " + cardDateTime(e) + (days ? "（跨" + days + "天）" : "");
}

function attendanceRange(start, end) {
  const s = toTs(start);
  if (s === null) return "";
  const e = toTs(end);
  return hm(s * 1000) + (e !== null && e > s ? "–" + hm(e * 1000) : "");
}

/* 签到 / 签退格子文字与色调（pend 同步中 / na 无需或待确认） */
export function attendanceCells(item) {
  const pend = item && item.attendance_state === "pending";
  const pick = (flag, start, end, noneLabel, verb) => {
    if (flag === false) return { text: noneLabel, cls: "na", full: noneLabel };
    if (flag === true) {
      const span = attendanceRange(start, end);
      const text = span || ("需要" + verb);
      return { text: text, cls: "", full: span ? verb + " " + span : text };
    }
    return pend ? { text: "同步中", cls: "pend", full: verb + "信息同步中" }
      : { text: "待确认", cls: "na", full: verb + "时间待确认" };
  };
  return {
    inCell: pick(item && item.checkin_required, item && item.checkin_start, item && item.checkin_end, "无需签到", "签到"),
    outCell: pick(item && item.checkout_required, item && item.checkout_start, item && item.checkout_end, "无需签退", "签退"),
  };
}

export function missedLayer4Text(item, state) {
  const ts = toTs(item && item.sign_start);
  const head = ts === null ? "电脑睡着时错过了开放" : "电脑在 " + hm(ts * 1000) + " 开放时睡着了";
  const tail = state === "closed" ? "已截止" : "还能报";
  return head + "，没有提交 · " + tail;
}

/* 下一批开放时间戳（最近未来场次 futureId）：即使同时存在已开放场次，下一批等待节点仍亮琥珀 */
export function nextBatchOpenTs() {
  const nextId = nextOpen().futureId;
  if (!nextId) return null;
  const item = findItem(nextId);
  return item ? toTs(item.sign_start) : null;
}

export function isSoonCountdown(item, left) {
  if (left === null || left <= 0) return false;
  if (left <= 600) return true;
  const nextTs = nextBatchOpenTs();
  const itemTs = toTs(item && item.sign_start);
  return nextTs !== null && itemTs !== null && itemTs === nextTs;
}

/* 把同组活动按开放时刻聚成时间轴节点；未开放节点 >=2 场标「同抢 N 场」 */
export function buildTimelineNodes(items, kind, byName) {
  const nodes = [];
  const byKey = new Map();
  const nextId = String(nextOpen().futureId || "");
  const nextTs = nextBatchOpenTs();
  const bnMs = businessNowMs();
  items.forEach((item) => {
    const st = stateOf(item);
    const known = signStartKnown(item);
    const openTs = known ? toTs(item.sign_start) : null;
    const key = byName ? "item_" + item.id : (known ? st + "_" + String(openTs) : "unknown");
    if (!byKey.has(key)) {
      const parts = openTs !== null ? schoolParts(openTs * 1000) : null;
      const dayDiff = (parts && bnMs !== null)
        ? Math.round((startOfDay(openTs * 1000) - startOfDay(bnMs)) / 86400000) : 0;
      const sec = parts && parts.s ? ":" + pad2(parts.s) : "";
      const day = (st === "waiting" || st === "unknown") && known && bnMs !== null && dayDiff !== 0
        ? relDayText(openTs * 1000) : "";
      const node = {
        key: key,
        time: parts ? pad2(parts.h) + ":" + pad2(parts.mi) : "待公布",
        sec: sec,
        timeCls: known ? "" : "txt",
        day: day,
        dotCls: st === "unknown" ? "unknown" : (st === "open" ? "open" : "wait"),
        hasBatch: false,
        batchN: 0,
        items: [],
      };
      byKey.set(key, node);
      nodes.push(node);
    }
    const nd = byKey.get(key);
    if (nd.dotCls === "wait" && (String(item.id) === nextId || (nextTs !== null && openTs === nextTs))) {
      nd.dotCls = "next";
    }
    nd.items.push(item);
  });
  nodes.forEach((nd) => {
    const canBatch = kind === "day" && nd.items.length >= 2
      && nd.items.every((it) => stateOf(it) === "waiting");
    nd.batchN = nd.items.length;
    nd.hasBatch = canBatch;
  });
  return nodes;
}
