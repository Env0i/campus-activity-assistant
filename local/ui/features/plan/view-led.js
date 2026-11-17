/* 路线与点阵倒计时的视图。 */

import { termsLocked } from "../terms/state.js";
import { resultMode, resultView } from "./state-board.js";
import { fmtLed, ledSet, routeDeadline, routeTarget, routeTime } from "./state-led.js";
import { executionView } from "./state-task.js";

/* 原型中的报名线路图：同时表达学校原定开放时间和本次实际执行窗口，
 * 多活动计划仍在任务卡里显示每场状态，不把多场压成一条假线路。 */
export function paintRoute() {
  const box = $("#route");
  const line = $("#route-line");
  if (!box) return;
  const target = routeTarget();
  if (!target || !toTs(target.item.sign_start)) {
    box.innerHTML = "";
    if (line) line.hidden = true;
    return;
  }
  if (line) line.hidden = false;
  const now = bnowS();
  const open = toTs(target.item.sign_start);
  const task = target.task || {};
  /* 每个站点独立判断 done/now/todo（不再是单一线性 index）：
   * 本次执行链（启动→页面→开始监测）只认真实 checkpoint——事件没发生就
   * 显示「待启动/待打开/待开始」，不得拿计划时刻或当前时间编造
   * 看起来像已发生的事件时间；原定开放与截止是时间参考节点——历史开放
   * 照样标 done，但不抢占当前执行节点。时钟未知时参考节点不判 done。 */
  const runStarted = Number(task.run_started_at) || null;
  const pageOpened = Number(task.page_opened_at) || null;
  const watchStarted = Number(task.watch_started_at) || null;
  const deadline = routeDeadline(task, open, now);
  const terminal = ["success", "already_signed", "failed", "canceled"].indexOf(String(task.status)) >= 0;
  const deadlineKnown = deadline.time !== null;
  const openDone = now !== null && now >= open;
  /* 五站（决策 014）：本次启动 → 准备好提交（改用页面点击时叫「活动页已打开」）→ 原定开放 →
   * 本次尝试截止 → 向学校核对（每场结束时用 getJoinInfo 核对一次，终态才算到站） */
  const clickPath = String(task.path || "") === "click";
  const ready = clickPath ? pageOpened : (watchStarted || pageOpened);
  const stations = [
    { name: "本次启动", time: runStarted ? routeTime(runStarted) : "待启动", done: runStarted !== null },
    { name: clickPath ? "活动页已打开" : "准备好提交", time: ready ? routeTime(ready) : "待准备", done: ready !== null },
    { name: "原定开放", time: routeTime(open), done: openDone, hot: true },
    /* 截止未知时显示「待定」，不能因为 null 参与比较而被标成已发生 */
    { name: deadline.name, time: deadlineKnown ? routeTime(deadline.time) : "待定",
      done: terminal || (deadlineKnown && now !== null && now >= deadline.time) },
    { name: "向学校核对", time: terminal ? "已核对" : "结束时", done: terminal },
  ];
  const currentIndex = terminal ? stations.length : stations.findIndex((station) => !station.done);
  box.innerHTML = '<div class="route" style="--n:' + stations.length + '" aria-label="这次报名的时间点">' +
    stations.map((station, i) => {
      const state = station.done ? "done" : i === currentIndex ? (station.hot ? "hot" : "now") : "todo";
      return '<div class="stn" data-s="' + state + '"><i class="stn-dot"></i><span class="stn-name">' + esc(station.name) +
        '</span><span class="stn-time">' + esc(station.time) + "</span></div>";
    }).join("") + "</div>";
}

export function paintCountdown() {
  const countDown = $("#countdown");
  const view = executionView();
  if (S.busy && S.plan.id) {
    /* 运行中只报当前执行目标：终态场次不参与倒计时和批次数（UX-04）。
     * 已开放但还没真正提交时给「准备中」，不把预热当提交，也不编 0 秒。 */
    if (view.phase === "submitting") {
      countDown.classList.remove("is-hot");
      countDown.textContent = view.retryUntil === null
        ? "正在提交 " + view.count + " 场 · 等待结果"
        : (function () { const l = bnLeftSec(view.retryUntil);
            return l == null ? "待校准 · 正在提交 " + view.count + " 场"
                             : fmt(Math.max(0, l)) + " · 正在提交 " + view.count + " 场"; })();
      return;
    }
    if (view.phase === "arming") {
      countDown.classList.remove("is-hot");
      countDown.textContent = "已开放 · 准备提交 " + view.count + " 场";
      return;
    }
    if (view.phase === "waiting") {
      if (view.openAt === null) {
        countDown.classList.remove("is-hot");
        countDown.textContent = "时间待公布 · 同时开放 " + view.count + " 场";
        return;
      }
      const left = bnLeftSec(view.openAt);
      if (left === null) {
        countDown.classList.remove("is-hot");
        countDown.textContent = "待校准 · 同时开放 " + view.count + " 场";
        return;
      }
      countDown.classList.toggle("is-hot", left > 0 && left <= 10);
      countDown.textContent = (left <= 0 ? "现在开放 · " : fmt(left) + " · ") + "同时开放 " + view.count + " 场";
      return;
    }
    countDown.classList.remove("is-hot");
    countDown.textContent = view.phase === "settling" ? "正在汇总结果" : "正在准备";
    return;
  }
  const selected = selectedItems();
  if (!selected.length) {
    countDown.textContent = "待选";
    countDown.classList.remove("is-hot");
    return;
  }
  const groups = groupSelected(selected);
  const first = groups[0];
  const left = leftOf(first.items[0]);
  if (left === null) {
    countDown.textContent = signStartKnown(first.items[0]) ? "时间待校准" : "时间待公布";
    countDown.classList.remove("is-hot");
    return;
  }
  /* 最后 10 秒转红：文字与颜色同时表达 */
  countDown.classList.toggle("is-hot", left > 0 && left <= 10 && !S.busy);
  countDown.textContent = (left <= 0 ? "现在开放 · " : fmt(left) + " · ") + "同时提交 " + first.items.length + " 场";
}

/* LED 下方那行小字：跟点阵同一个状态源，说明屏上数字是什么 */
export function paintLedLabel(prefix, value) {
  const label = $("#led-label");
  if (!label) return;
  const bold = label.querySelector("b");
  if (!bold) return;
  /* metric-next 节点常驻：顶栏指标也写它，删了会让那边拿到空引用 */
  const textNode = Array.from(label.childNodes).find((node) => node.nodeType === 3);
  if (textNode) textNode.textContent = prefix + " ";
  else label.insertBefore(document.createTextNode(prefix + " "), bold);
  bold.textContent = value === null ? "—" : value;
}

/* 结果页只在全成功 / 全失败时显示一个缩小的 LED（原型 res.hasLed：限宽 5rem、没有下方说明行）；
 * 其余结果页不显示 LED */
export function paintLedBox(mode) {
  const box = $("#led-box");
  const label = $("#led-label");
  if (box) {
    box.hidden = mode === "none";
    box.dataset.size = mode === "mini" ? "mini" : "";
  }
  if (label) label.hidden = mode !== "full";
}

export function paintLed() {
  const view = executionView();
  if (S.busy && S.plan.id) {
    paintLedBox("full");
    if (view.phase === "submitting") {
      /* 提交中整块红色（原型 ex 段 led 'red'），下方「本次尝试到 HH:MM:SS」 */
      if (view.retryUntil === null) {
        /* 截止未知：点阵只有横线，不拿 00:00:00 冒充已到点 */
        ledSet("--:--:--", "red");
        paintLedLabel("本次尝试到", "待定");
        return;
      }
      {
        const l = bnLeftSec(view.retryUntil);
        ledSet(l == null ? "--:--" : fmtLed(Math.max(0, l)), "red");
      }
      paintLedLabel("本次尝试到", hmsDay(view.retryUntil));
      return;
    }
    if (view.phase === "arming") {
      /* 已开放、还没真正提交：不说「还剩 0 秒」，也不说「正在提交」 */
      ledSet("--:--:--", "amber");
      paintLedLabel("已开放，准备报名 " + view.count + " 场", "准备中");
      return;
    }
    if (view.phase === "waiting") {
      if (view.openAt === null) {
        ledSet("--:--:--", "off");
        paintLedLabel("开放时间", "待公布");
        return;
      }
      const left = bnLeftSec(view.openAt);
      if (left === null) {
        ledSet("--:--:--", "off");
        paintLedLabel("开放时间", "待校准");
        return;
      }
      ledSet(fmtLed(left), left <= 10 ? "red" : "amber");
      /* 直接格式化真实开放时刻：不再用 now + 已取整 left 重拼，避免 1 秒偏差 */
      paintLedLabel("开放时间", hmsDay(view.openAt));
      return;
    }
    /* 准备中/汇总中：屏上不给假倒计时，也不提前点亮成功 */
    ledSet("--:--:--", "off");
    paintLedLabel("计划状态", view.phase === "settling" ? "汇总中" : "准备中");
    return;
  }
  if (resultMode()) {
    const res = resultView();
    if (res.led) {
      paintLedBox("mini");
      ledSet(res.led[0], res.led[1]);
    } else {
      paintLedBox("none");
    }
    return;
  }
  paintLedBox("full");
  /* 草稿态（原型 draft 段 led）：条款没同意 / 时间待校准 / 列表没加载都灭灯，只写原因 */
  if (termsLocked() && S.login.present !== false) {
    ledSet("--:--:--", "off");
    paintLedLabel(S.terms.unknown ? "重新确认条款后才能报名" : "同意条款后才能报名", "");
    return;
  }
  if (bnowS() === null && !S.demo) {
    ledSet("--:--:--", "off");
    paintLedLabel("时间待校准", "");
    return;
  }
  if (S.listState !== "ready") {
    ledSet("--:--:--", "off");
    paintLedLabel(S.listState === "loading" ? "正在加载" : "活动未加载", "");
    return;
  }
  const selected = selectedItems();
  const now = bnowS();
  if (selected.length) {
    /* 选了活动：有未开放的就倒计时到最早那一批（琥珀，最后 10 秒红）；全已开放就是「现在」 */
    let first = null;
    selected.forEach((item) => {
      const ts = toTs(item.sign_start);
      if (ts !== null && now !== null && ts > now && (first === null || ts < first)) first = ts;
    });
    if (first !== null) {
      const left = first - now;
      ledSet(fmtLed(left), left <= 10 ? "red" : "amber");
      paintLedLabel("下一批开放", hmsDay(first));
      return;
    }
    if (selected.some((item) => toTs(item.sign_start) === null)) {
      /* 代码独有：开放时间没公布的场次不能说成「已开放」 */
      ledSet("--:--:--", "off");
      paintLedLabel("开放时间", "待公布");
      return;
    }
    ledSet("00:00:00", "amber");
    paintLedLabel("已开放，可以立即报名", "现在");
    return;
  }
  const next = nextOpen();
  if (next.openNow) {
    /* 已开放就是「现在可以报」，屏上不再给任何未来场的倒计时 */
    ledSet("00:00:00", "amber");
    paintLedLabel("已开放，可以立即报名", "现在");
    return;
  }
  if (next.best !== null) {
    ledSet(fmtLed(next.best), "amber");
    const open = toTs((S.byId.get(String(next.futureId)) || {}).sign_start);
    paintLedLabel("最近开放", open === null ? "待公布" : hmsDay(open));
    return;
  }
  ledSet("--:--:--", "off");
  /* 没有任何可报目标：屏下就写原型 led 的默认结论 */
  paintLedLabel("暂时没有目标", "");
}
