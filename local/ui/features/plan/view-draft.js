/* 计划栏草稿段的视图：地点开关、检查条、还差一步、票区与门禁推导。 */

import { termsLocked } from "../terms/state.js";
import { resultMode } from "./state-board.js";
import { preStartWarnings } from "./state-draft.js";

/* 表格地点展开/收起：只改当前控件与 aria-expanded，不重绘整块，
 * 键盘焦点不会丢，也不会因此触发勾选或开始计划。 */
export function togglePlace(el) {
  if (!el || !el.getAttribute) return;
  const open = el.getAttribute("aria-expanded") === "true";
  el.setAttribute("aria-expanded", open ? "false" : "true");
  if (el.classList) el.classList.toggle("is-open", !open);
}

export function paintChecks() {
  const box = $("#plan-checks");
  const warns = preStartWarnings();
  S.preWarnCount = warns.length;
  paintPrewarn(warns);
  if (S.busy) {
    box.innerHTML = "";
    return;
  }
  box.innerHTML = planCheckList(warns.length).map((c) => '<span class="chk" data-tone="' + (c.ok ? "ok" : "no")
    + '"><i aria-hidden="true">' + (c.ok ? "✓" : "!") + "</i>" + esc(c.text) + "</span>").join("");
}

export function paintPrewarn(warns) {
  const box = $("#plan-prewarn");
  if (!box) return;
  box.hidden = !warns.length;
  box.innerHTML = warns.map((w) => '<li data-tone="' + w.tone + '"><span>' + esc(w.text) + "</span>"
    + (w.act ? '<button type="button" data-act="' + w.act + '">' + esc(w.label) + "</button>" : "") + "</li>").join("");
}

/* 加入计划前的检查条（决策 014 第 7 条，原型 renderVals 的 checks）：
 * 有未满足的只列未满足的（!）；全满足时有开始前提醒就不显示，没有提醒就只留一条 ✓。
 * 开始前提醒只提醒不拦，有提醒时主按钮改叫「仍然开始报名计划」。 */
export function planCheckList(warnCount) {
  if (S.runtime.error) return [{ ok: false, text: "程序组件缺失" }];
  if (termsLocked()) {
    const newer = typeof termsUpdateMode === "function" && termsUpdateMode();
    return [{ ok: false, text: S.terms.unknown ? "条款状态没能确认" : (newer ? "还没有同意新版条款" : "还没有同意使用条款") }];
  }
  const misses = [];
  const login = (S.login.view || {}).state;
  if (!S.demo && login !== "ok") {
    misses.push(login === "unknown" || login === "checking" ? "登录状态待确认"
      : login === "bad" ? "登录已失效" : login === "pending" ? "正在登录" : "还没有登录");
  }
  if (!S.demo && businessNowMs() === null) misses.push("北京时间待校准");
  if (misses.length) return misses.map((text) => ({ ok: false, text: text }));
  if (warnCount > 0) return [];
  return [{ ok: true, text: selectedItems().length ? "登录、北京时间和举办时间都没问题" : "登录和北京时间都没问题" }];
}

/* 「还差一步」（原型 blockers）：开始按钮禁用时写清缺什么，能就地解决的给一个动作 */
export function startBlocker() {
  if (S.busy) return null;
  if (S.runtime.error) return { text: "程序组件缺失，看顶部提示" };
  /* 取消报名进行中：学校动作互斥（X3），写在最前面，与原型 blockers 的第二条一致 */
  if (S.cancel.busyId) return { text: "正在取消报名，等它结束再开始" };
  if (termsLocked()) {
    const newer = typeof termsUpdateMode === "function" && termsUpdateMode();
    return { text: S.terms.unknown ? "先重新确认条款" : (newer ? "先同意新版条款" : "先同意使用条款"),
             act: "terms-open", label: "查看条款" };
  }
  if (!S.demo) {
    const login = (S.login.view || {}).state;
    if (S.login.present === false || login === "none") return { text: "还没有登录", act: "login", label: "去登录" };
    if (login === "bad") return { text: "登录已失效", act: "login", label: "重新登录" };
    if (login === "unknown") return { text: "登录状态还没确认", act: "refresh", label: "刷新" };
    /* 代码独有：学校接口正在校验（checking）——已经在查了，不再给「刷新」 */
    if (login === "checking") return { text: "登录状态还没确认" };
    if (login === "pending") return { text: S.autoLogin ? "正在自动登录" : "正在登录" };
  }
  if (businessNowMs() === null && !S.demo) return { text: "北京时间还没校准", act: "clock-sync", label: "重新校准" };
  if (S.listState !== "ready") return { text: "活动列表还没加载", act: "refresh", label: "刷新" };
  if (!S.selected.size) {
    return S.items.length ? { text: "先在时刻表勾选活动" } : { text: "学校还没有可选的活动", act: "refresh", label: "刷新" };
  }
  const validation = validateSelection();
  if (validation.errors.length || validation.conflicts.length) return { text: "已选场次有问题，看上面的提醒" };
  return null;
}

export function paintWhy() {
  const box = $("#plan-why");
  if (!box) return;
  const plan = $("#btn-plan");
  const blocker = plan && plan.disabled && !S.starting ? startBlocker() : null;
  box.hidden = !blocker;
  box.innerHTML = blocker ? "<span>还差一步：" + esc(blocker.text) + "</span>"
    + (blocker.act ? '<button type="button" data-act="' + blocker.act + '">' + esc(blocker.label) + "</button>" : "") : "";
}

/* 草稿里的已选场次：按开放批次分组，每场一张票，可逐场移除（运行中和结果页不显示） */
export function paintTickets() {
  const box = $("#plan-tickets");
  if (!box) return;
  const items = S.busy || resultMode() ? [] : selectedItems();
  if (!items.length) {
    box.innerHTML = "";
    return;
  }
  box.innerHTML = groupSelected(items).map((group) => {
    /* 批次头照原型 batches：已开放的批次写「现在」，预报名写 hms（HH:MM:SS，跨天加「明天 / 后天」） */
    const instant = modeOf(group.items[0]) === "instant_signup";
    const count = group.items.length;
    const note = instant ? "立即报名 " + count + " 场"
      : (count > 1 ? "预报名，同时提交 " + count + " 场" : "预报名 1 场");
    const at = toTs(group.key);
    return '<div class="bh"><b>' + esc(instant ? "现在" : (at === null ? "待公布" : hmsDay(at))) + "</b><span>" + esc(note) + "</span></div>"
      + group.items.map((item) => '<div class="tk"><div><b title="' + esc(item.name) + '">' + esc(item.name)
        + "</b><small>" + esc(activityTimeText(item)) + "</small>"
        + (item.cancel_allowed === false ? '<small class="nr">报后不可退</small>' : "")
        + '</div><button type="button" data-remove="'
        + esc(String(item.id)) + '" aria-label="' + esc("从计划移除「" + item.name + "」") + '">'
        + '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>').join("");
  }).join("");
}

/* 尝试设置一行概括：「尝试 2 分钟，不限次数」，点「修改」才展开三个控件；只在草稿态显示（原型 isDraft） */
export function paintPolicyLine() {
  const line = $("#policy-line");
  if (!line) return;
  const hide = S.busy || resultMode();
  line.hidden = hide;
  if (hide) {
    const edit = $("#policy-edit");
    if (edit) edit.hidden = true;
    const btn = $("#btn-policy");
    if (btn) {
      btn.textContent = "修改";
      btn.setAttribute("aria-expanded", "false");
    }
  }
  const choices = (S.retryOptions && S.retryOptions.choices) || [];
  const picked = choices.filter((c) => Number(c.value) === Number(S.retryPolicy.retry_for_s))[0];
  const cap = Number(S.retryPolicy.max_attempts) || 0;
  /* GL06 概括行照原型 retryText：自动延长只写四个字，括号里的「最多 25 分钟」留给下拉选项 */
  const retryText = picked ? (Number(picked.value) === -1 ? "自动延长" : picked.label) : "2 分钟";
  $("#policy-text").innerHTML = "尝试 <b>" + esc(retryText) + "</b>，<b>"
    + (cap > 0 ? "最多 " + cap + " 次" : "不限次数") + "</b>";
}
