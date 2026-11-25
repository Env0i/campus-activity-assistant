/* 时间轴节点与四层卡片视图拼装（纯 DOM 字符串，状态判定借由 state-timeline）。 */
import { taskDisplayLabel } from "../plan/state-task.js";
import { termsLocked } from "../terms/state.js";
import { attendanceCells, buildTimelineNodes, cardCancelUntilText, cardSignEndText, compactActText, isSoonCountdown, missedLayer4Text } from "./state-timeline.js";
import { activityTypeOf } from "./state-types.js";

/* 与已报名活动重叠、需要显示「不可加入」的行：只限等待开放 / 开放中的未报名行（原型 clash 条件）；
 * 已截止、已报名、正在提交、本机时钟不可用（待校准）的行不画这个标签 */
export function clashOfItem(item, armed) {
  if (armed || !isEligibleForPlan(item)) return null;
  const st = stateOf(item);
  return st === "waiting" || st === "open" ? signedClash(item) : null;
}

/* 「取消报名」按钮：条件不满足时仍画出来但置灰，title 写原因 */
function cancelButtonHtml(item) {
  const id = String(item.id);
  const block = cancelBlock(id);
  const here = S.cancel.busyId === id;
  return '<button class="btn btn-line cx-btn" type="button" data-cancel="' + esc(id) + '"'
    + (block.off ? " disabled" : "") + (block.why ? ' title="' + esc(block.why) + '"' : "") + ">"
    + (here ? "正在取消…" : "取消报名") + "</button>";
}

/* 行下面的确认块 / 结果句（照原型 .rx）：只在这一场被点了取消或有结果时出现 */
function cancelRxHtml(item) {
  const id = String(item.id);
  const ask = S.cancel.askId === id && !S.cancel.busyId && canCancelNow(item);
  const res = S.cancel.res && S.cancel.res.id === id ? cancelResultView(S.cancel.res, item.name) : null;
  if (!ask && !res) return "";
  return '<div class="rx" data-rx="' + esc(id) + '">'
    + (ask ? '<div class="ph-confirm" role="alert">取消「' + esc(item.name) + '」的报名？取消后名额可能被别人报走，不能撤回。'
      + '<div class="ph-acts"><button class="btn btn-line" type="button" data-cancel-no="' + esc(id) + '">不取消</button>'
      + '<button class="btn btn-stop" type="button" data-cancel-yes="' + esc(id) + '">确认取消报名</button></div></div>' : "")
    + (res ? '<p class="cx-res ' + res.cls + '" role="status">' + esc(res.text) + "</p>" : "") + "</div>";
}

export function cardStateHtml(item, state, armed) {
  if (armed) return '<span class="state-tag state-armed">' + esc(taskDisplayLabel(armed)) + "</span>";
  /* 与已报名的活动时间重叠：只剩虚线的「不可加入」，不带倒计时；可聚焦，原因在气泡里 */
  if (clashOfItem(item, armed)) {
    return '<span class="state-tag state-clash" tabindex="0" aria-describedby="cx-tip">不可加入'
      + '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/><path d="M12 7.6h.01"/></svg></span>';
  }
  const missedTag = missedBySleep(item) ? '<span class="state-tag state-missed">错过了</span>' : "";
  if (state === "waiting") {
    const left = leftOf(item);
    const soon = isSoonCountdown(item, left);
    const isNext = String(item.id) === String(nextOpen().bestId);
    return missedTag + '<span class="left' + (soon ? " is-soon" : "") + '">' + esc(leftTextOf(item)) + "</span>"
      + (isNext ? '<span class="state-tag state-next">下一场</span>' : "");
  }
  if (state === "open") {
    const left = leftOf(item);
    const ago = left === null ? "已开放" : "已开放 " + durText(-left);
    return missedTag + '<span class="state-tag state-open">开放中</span><span class="small" data-ago>' + esc(ago) + "</span>";
  }
  if (state === "signed") {
    /* 可取消（qxbm 为 1 且业务北京时间在报名窗口内）才有「可取消至」和取消按钮 */
    return '<span class="state-tag state-signed">已报名</span>'
      + (canCancelNow(item) ? '<span class="cx-until">' + esc(cardCancelUntilText(item)) + "</span>" + cancelButtonHtml(item) : "");
  }
  if (state === "closed") {
    return missedTag + '<span class="state-tag state-closed">已截止</span>';
  }
  /* 还不知道开放时刻就写「待公布」（原型 Main.dc.html:1944），不拿 --:-- 冒充一个时刻 */
  return '<span class="state-tag state-unknown">' + (signStartKnown(item) ? "待校准" : "待公布") + "</span>";
}

function cardClasses(item, state, selected, invalid, conflict, clash, armed) {
  const id = String(item.id);
  const list = ["card-4l", "row"];
  if (selected) list.push("is-selected");
  if (item.signed) list.push("is-signed");
  if (state === "closed") list.push("is-closed");
  if (state === "unknown" || invalid) list.push("is-unknown");
  if (conflict) list.push("is-conflict");
  if (clash) list.push("is-clash");
  if (S.tip.id === id) list.push("is-tipon");
  if (S.flashId === id) list.push("is-flash");
  if (armed) list.push("is-armed");
  return list.join(" ");
}

function cardLayer2Html(item, state, armed) {
  const typeText = activityTypeOf(item);
  const parts = ['<span class="type-tag" title="' + esc(typeText) + '">' + esc(typeText) + "</span>"];
  /* 活动行显示自己的执行模式：预报名 / 立即报名（抢名额）；已截止由状态格标示 */
  if (state === "waiting" || state === "open") {
    const mode = modeOf(item);
    const mText = modeText(mode);
    const warnCls = mode === "instant_signup" ? " is-warn" : "";
    if (mText) parts.push('<span class="activity-flags"><span class="activity-flag' + warnCls + '">' + esc(mText) + "</span></span>");
  }
  /* 报后可退 / 报后不可退：未报名的等待、开放中行；cancel_allowed 为 null 时不写 */
  const refund = refundFlag(item, state);
  if (refund) parts.push('<span class="rf' + (refund.no ? " no" : "") + '">' + esc(refund.text) + "</span>");
  const signEnd = cardSignEndText(item, state);
  if (signEnd) parts.push('<span class="sign-end">' + esc(signEnd) + "</span>");
  return '<div class="l2"><div class="l2-l">' + parts.join("") + '</div><div class="l2-r c-state">'
    + cardStateHtml(item, state, armed) + "</div></div>";
}

function cardLayer3Html(item, invalid) {
  const actText = compactActText(item);
  const place = item.place || "地点待定";
  const cells = attendanceCells(item);
  const actCls = invalid ? " na" : "";
  const placeCls = !item.place || item.place === "地点待定" ? " na" : "";
  const inCls = cells.inCell.cls ? " " + cells.inCell.cls : "";
  const outCls = cells.outCell.cls ? " " + cells.outCell.cls : "";
  return '<div class="l3 l3-4">'
    + '<span class="l3-c' + actCls + '" title="' + esc(actText) + '"><em>举办</em><span>' + esc(actText) + "</span></span>"
    + '<span class="l3-c c-place' + placeCls + '" tabindex="0" role="button" aria-expanded="false" aria-label="地点：'
    + esc(place) + '，按回车展开全部" title="' + esc(place) + '"><em>地点</em><span>' + esc(place) + "</span></span>"
    + '<span class="l3-c' + inCls + '" title="' + esc(cells.inCell.full) + '"><em>签到</em><span>' + esc(cells.inCell.text) + "</span></span>"
    + '<span class="l3-c' + outCls + '" title="' + esc(cells.outCell.full) + '"><em>签退</em><span>' + esc(cells.outCell.text) + "</span></span>"
    + "</div>";
}

function cardLayer4Html(item, state, conflict, clash) {
  /* 行内只留与已选的那一句；与已报名的冲突改由「不可加入」标签 + 气泡讲 */
  const partner = !clash && conflict ? selectedClash(item) : null;
  const warnHtml = partner ? '<div class="note-w">与已选的「' + esc(partner.name) + "」时间重叠</div>" : "";
  const missHtml = missedBySleep(item) ? '<div class="note-m">' + esc(missedLayer4Text(item, state)) + "</div>" : "";
  /* 学校列表还没同步回 signed=true：说清「已确认，只是列表在同步」，
   * 不把这场重新画成可报名。 */
  const syncHtml = item.sync_pending && state === "signed"
    ? '<div class="note-s">报名已确认，学校列表正在同步</div>' : "";
  const rxHtml = cancelRxHtml(item);
  if (!warnHtml && !missHtml && !syncHtml && !rxHtml) return "";
  return '<div class="l4">' + warnHtml + missHtml + syncHtml + rxHtml + "</div>";
}

export function buildCardHtml(item) {
  const id = String(item.id);
  const state = stateOf(item);
  const selected = S.selected.has(id);
  const invalid = !validActivityTime(item);
  const conflict = conflictIds().has(id);
  const armed = armedTaskByActivity(id);
  const clash = clashOfItem(item, armed);
  /* 已截止活动保留在列表里查看，但复选框禁用；已报名同理 */
  /* 条款未同意时与登录/刷新/开始同一道门：勾选也算学校动作的前置，不能漏拦。 */
  /* 与已报名活动时间重叠的直接禁选（决策 004 的外部占用基线）；
   * 原因不写在行内：状态格只留「不可加入」，悬停或聚焦弹气泡（20261107-conflict-cancel U1） */
  /* LS14：开放时间待公布的行也禁勾（原型 off 含 unknown），见 signStartPending */
  /* 与 plan-panel.js updateControls 同一条判据，改一处要同步另一处（H2：此前这里缺 S.starting） */
  const disabled = S.busy || S.starting || termsLocked() || !isEligibleForPlan(item) || !!signedClash(item) || signStartPending(item);
  const cls = cardClasses(item, state, selected, invalid, conflict, clash, armed);
  /* D3 四层卡片将奖励统一放进第一层右侧 .l1-r（宽窄同源，取代旧 .sub 内 rwInline） */
  const l1 = '<div class="l1"><div class="c-sel"><input class="row-check" type="checkbox" data-id="' + esc(id) + '"'
    + (selected ? " checked" : "") + (disabled ? " disabled" : "") + ' aria-label="选择' + esc(item.name) + '"></div>'
    + '<div class="c-main nl"><div class="nl-title"><div class="name" title="' + esc(item.name) + '">' + esc(item.name) + "</div>"
    + '<button class="desc-btn" type="button" data-desc="' + esc(id) + '" aria-label="查看活动简介" title="查看活动简介">?</button></div>'
    + '<div class="l1-r">' + rewardChips(item) + "</div></div></div>";
  return '<div class="' + cls + '" data-id="' + esc(id) + '" aria-label="' + esc(item.name) + '">'
    + l1 + cardLayer2Html(item, state, armed) + cardLayer3Html(item, invalid) + cardLayer4Html(item, state, conflict, clash)
    + "</div>";
}

function nodeAxisHtml(nd) {
  /* 学校常把开放时间定在 00:59:59 这种点：有秒就把秒写成小号；未知时刻写「待公布」（原型 Main.dc.html:1944） */
  return '<div class="tl-axis"><div class="tl-time">'
    + '<span class="tl-t' + (nd.timeCls ? " " + nd.timeCls : "") + '">' + esc(nd.time)
    + (nd.sec ? '<span class="tl-s">' + esc(nd.sec) + "</span>" : "") + "</span>"
    + (nd.day ? '<span class="tl-d">' + esc(nd.day) + "</span>" : "")
    + (nd.hasBatch ? '<span class="tl-batch">同抢 ' + nd.batchN + " 场</span>" : "")
    + '</div><span class="tl-dot ' + nd.dotCls + '" aria-hidden="true"></span></div>';
}

export function buildGroupBodyHtml(items, kind, byName) {
  const noRail = !byName && (kind === "signed" || kind === "closed");
  if (noRail) {
    return '<div class="tl-below">' + items.map(buildCardHtml).join("") + "</div>";
  }
  const nodes = buildTimelineNodes(items, kind, byName);
  return nodes.map((nd) => '<div class="tl-node">' + nodeAxisHtml(nd)
    + '<div class="tl-cards">' + nd.items.map(buildCardHtml).join("") + "</div></div>").join("");
}
