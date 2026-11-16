/* 计划栏（新工作台右栏，决策 014）与任务呈现：阶段标题、路线/倒计时/LED、横幅、任务卡、
 * 窗口分档与中窄档计划条。由旧大屏 views/board.js 改名演进而来，元素 id 沿用，
 * 其他脚本按原函数名调用。 */

/* 表格地点展开/收起：只改当前控件与 aria-expanded，不重绘整块，
 * 键盘焦点不会丢，也不会因此触发勾选或开始计划。 */
function togglePlace(el) {
  if (!el || !el.getAttribute) return;
  const open = el.getAttribute("aria-expanded") === "true";
  el.setAttribute("aria-expanded", open ? "false" : "true");
  if (el.classList) el.classList.toggle("is-open", !open);
}

/* 大屏地点展开/收起：按钮原生处理 Enter/Space，这里只翻转 aria-expanded。
 * 只改当前按钮，不重绘整块，键盘焦点不会丢。 */
function bindPlaceToggle() {
  const box = $("#selected-meta");
  if (!box || !box.addEventListener) return;
  box.addEventListener("click", (event) => {
    const target = event.target;
    const btn = target && target.closest ? target.closest("[data-place-toggle]") : null;
    if (!btn) return;
    const open = btn.getAttribute("aria-expanded") === "true";
    btn.setAttribute("aria-expanded", open ? "false" : "true");
  });
}

/* 加入计划前的检查条（决策 014 第 7 条，原型 renderVals 的 checks）：
 * 有未满足的只列未满足的（!）；全满足时有开始前提醒就不显示，没有提醒就只留一条 ✓。
 * 开始前提醒只提醒不拦，有提醒时主按钮改叫「仍然开始报名计划」。 */
function planCheckList(warnCount) {
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

function paintChecks() {
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

/* 电脑自动登录要用到的三件事：保存了账号、装了验证码识别、保存的密码没被学校拒绝过。
 * 读 advanced_features_state.credential（bootstrap 与手机面板刷新都带）；读不到就当没开。
 * mask 是打码账号，只在后端给了 username 时才有（打码规则与手机页同一个函数）。 */
function autoLoginCredential() {
  const phone = window.PhonePanel && window.PhonePanel.state && window.PhonePanel.state.advanced;
  const adv = phone || S.advanced || {};
  const cred = adv.credential || {};
  const mask = cred.username && typeof maskAccount === "function" ? maskAccount(cred.username) : "";
  return { saved: !!cred.saved, ocr: !!cred.ocr_ready, paused: !!cred.paused, mask: mask, username: String(cred.username || "") };
}

function latestSelectedOpen() {
  let best = null;
  selectedItems().forEach((item) => {
    const ts = toTs(item.sign_start);
    if (ts !== null && (best === null || ts > best)) best = ts;
  });
  return best;
}

/* 开始前提醒五条（原型 preWarn / loginWarn）：断网 / 沿用上次校准 / 最晚一场要等 1 小时以上又没开全自动登录 /
 * 直到报名截止但缺截止时间 / 最晚一场 24 小时以后（按最晚一场算，旧界面按最早一场，有意改的） */
function preStartWarnings() {
  const items = selectedItems();
  if (!items.length || S.busy || termsLocked() || S.runtime.error) return [];
  const list = [];
  if (!S.online) list.push({ tone: "bad", text: "现在连不上网。到开放时间还没恢复，就提交不出去。" });
  if (!S.demo && clockUiState() === "holdover") {
    /* 误差取时钟快照的估计误差；拿不到就不写这一段 */
    const reading = clockReading();
    const ms = reading ? Number(reading.uncertaintyMs) : NaN;
    const err = Number.isFinite(ms) && ms > 0 ? "，误差" + clockUncertaintyText(ms) : "";
    list.push({ tone: "warn", text: "北京时间在用上次的校准结果" + err + "，工具正在自动重试校准。" });
  }
  const now = bnowS();
  const latest = latestSelectedOpen();
  const cred = autoLoginCredential();
  /* 原型 loginWarn 只在登录有效时提醒（没登录 / 失效由「还差一步」承担，不叠两句） */
  const loginOk = !!S.demo || (S.login.view || {}).state === "ok";
  if (loginOk && now !== null && latest !== null && latest - now > 3600 && !(cred.saved && cred.ocr && !cred.paused)) {
    /* 保存了账号、只差验证码识别 → 去安装；没保存或保存的密码学校不认（代码独有）→ 去保存 */
    const has = cred.saved && !cred.paused;
    const missing = has ? "验证码识别没装" : (cred.paused ? "保存的密码学校不认" : "自动登录没开");
    const until = hmsDay(latest).slice(0, -3);
    list.push({
      tone: "warn",
      /* U+2060：窄档下「重/新登录」不拆行（断行扫描 NarrowWarn 实测） */
      text: "要等到" + (/^\d/.test(until) ? " " : "") + until + "，" + missing + "。中途登录失效要你"
        + (has ? "输验证码" : "重⁠新登录") + "；开放前 100 秒内失效，那场就结束。",
      act: has ? "go-ocr" : "go-cred", label: has ? "去安装" : "去保存",
    });
  }
  if (S.retryPolicy.retry_for_s === 0) {
    const noEnd = items.filter((item) => !toTs(item.sign_end));
    if (noEnd.length) {
      list.push({ tone: "warn", text: "「" + noEnd[0].name + "」" + (noEnd.length > 1 ? "等 " + noEnd.length + " 场" : "")
        + "没给报名截止时间，“直到报名截止”对它只会尝试 2 分钟。" });
    }
  }
  if (now !== null && latest !== null && latest - now > 86400) {
    list.push({ tone: "warn", text: "有场次在 24 小时以后才开放，计划要一直运行到那时。这段时⁠间电⁠脑不能关机或睡眠。" });
  }
  return list;
}

function paintPrewarn(warns) {
  const box = $("#plan-prewarn");
  if (!box) return;
  box.hidden = !warns.length;
  box.innerHTML = warns.map((w) => '<li data-tone="' + w.tone + '"><span>' + esc(w.text) + "</span>"
    + (w.act ? '<button type="button" data-act="' + w.act + '">' + esc(w.label) + "</button>" : "") + "</li>").join("");
}

/* 「还差一步」（原型 blockers）：开始按钮禁用时写清缺什么，能就地解决的给一个动作 */
function startBlocker() {
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

function paintWhy() {
  const box = $("#plan-why");
  if (!box) return;
  const plan = $("#btn-plan");
  const blocker = plan && plan.disabled && !S.starting ? startBlocker() : null;
  box.hidden = !blocker;
  box.innerHTML = blocker ? "<span>还差一步：" + esc(blocker.text) + "</span>"
    + (blocker.act ? '<button type="button" data-act="' + blocker.act + '">' + esc(blocker.label) + "</button>" : "") : "";
}

/* 草稿里的已选场次：按开放批次分组，每场一张票，可逐场移除（运行中和结果页不显示） */
function paintTickets() {
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
function paintPolicyLine() {
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

/* 原型中的报名线路图：同时表达学校原定开放时间和本次实际执行窗口，
 * 多活动计划仍在任务卡里显示每场状态，不把多场压成一条假线路。 */
function paintRoute() {
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

/* 当前执行窗口的截止：统一走 effectiveRetryDeadline（telemetry 优先，
 * 其次任务 retry_for_s/sign_end/run_started_at 推导），与任务卡、LED
 * 同一个来源，长策略不再显示成 120 秒。 */
function routeDeadline(task, open, now) {
  return { name: "本次尝试截止", time: effectiveRetryDeadline(task, now) };
}

function routeTime(ts) {
  const bnMs = businessNowMs();
  const sameDay = bnMs != null && startOfDay(ts * 1000) === startOfDay(bnMs);
  return sameDay ? fmtClock(ts) : whenText(ts * 1000);
}

function routeTarget() {
  /* 运行中用执行模型的任务；模型没给任务时再按状态兜底（不读原勾选集合） */
  const view = executionView();
  const task = view.task
    || Array.from(S.plan.tasks.values()).find((item) => RUNNING_STATUSES.indexOf(String(item.status)) >= 0)
    || null;
  if (!task) return null;
  const item = taskDisplayItem(task);
  return item ? { item: item, task: task } : null;
}

function paintCountdown() {
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

/* ---------------------------------------------------------------- LED 点阵 */
function ledSet(text, tone) {
  const el = $("#led");
  if (!el || !window.LED_UI) return; /* led.js 缺席时退回纯文本层，语义不丢 */
  window.LED_UI.renderLed(el, text, tone);
}

/* 点阵只承载倒计时与结论：等待/最后10秒/提交中/成功/失败/停止 */
function fmtLed(seconds) {
  const value = Math.max(0, Math.floor(seconds));
  const pad = (n) => String(n).padStart(2, "0");
  return pad(Math.floor(value / 3600)) + ":" + pad(Math.floor((value % 3600) / 60)) + ":" + pad(value % 60);
}

/* LED 下方那行小字：跟点阵同一个状态源，说明屏上数字是什么 */
function paintLedLabel(prefix, value) {
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
function paintLedBox(mode) {
  const box = $("#led-box");
  const label = $("#led-label");
  if (box) {
    box.hidden = mode === "none";
    box.dataset.size = mode === "mini" ? "mini" : "";
  }
  if (label) label.hidden = mode !== "full";
}

function paintLed() {
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

function updateControls() {
  const componentDown = !!S.runtime.error;
  /* 条款门禁（决策 013）：未同意时登录/刷新/开始全部禁用；离线演示不受限 */
  const termsGate = termsLocked();
  /* 缺组件：登录/开始都禁用（点了也是结构化失败）；刷新保持可用——复查组件并恢复的唯一通道 */
  $("#btn-login").disabled = S.busy || componentDown || termsGate;
  $("#btn-refresh").disabled = S.listState === "loading" || termsGate || !!S.cancel.busyId;
  /* 帮助任何状态都可打开；运行中只禁重看引导，原因写在按钮上。 */
  paintReplayButtons();
  const validation = validateSelection();
  /* 开始门禁：真实计划只在学校接口确认登录有效（valid）后可点；
   * checking/unknown/none/expired 一律禁用（demo 模式例外，供视觉演示）。
   * checking 必须显式排除：新一轮检查开始时不清旧 result，
   * 不排除的话上次 valid 会放行尚未确认的检查期。 */
  const loginReady = !!S.demo || (!S.login.checking && S.login.result === "valid");
  const canStart = !S.busy && !S.starting && !S.cancel.busyId && !componentDown && !termsGate && loginReady && S.selected.size > 0
    && validation.errors.length === 0 && validation.conflicts.length === 0
    && S.listState === "ready";
  /* 独立北京时间门禁（决策 012）：时钟不可读或不在 ready/holdover 时开始禁用 */
  const clockDown = businessNowMs() === null && !S.demo;
  $("#btn-plan").disabled = !canStart || clockDown;
  /* 有开始前提醒时主按钮改叫「仍然开始报名计划」：只提醒不拦 */
  const warned = (Number(S.preWarnCount) || 0) > 0;
  $("#btn-plan").textContent = S.busy ? "计划运行中"
    : (S.startRequest.state === "reconciling" ? "正在确认是否启动…"
      : (S.starting ? "正在提交…"
        : (clockDown ? "北京时间未校准" : (S.editing ? "重新开始计划"
          : (warned ? "仍然开始报名计划" : "开始报名计划")))));
  paintWhy();
  $("#btn-stop").disabled = !S.busy || !S.plan.id || S.stopping;
  $("#btn-stop").textContent = S.stopping ? "正在停止…" : "停止计划";
  /* 运行中底部换成「修改计划 / 停止计划」；草稿时是开始前提醒、检查和主按钮 */
  const runActions = $("#run-actions");
  if (runActions) runActions.hidden = !S.busy;
  $("#btn-clear-plan").disabled = S.busy || S.starting || (!S.selected.size && !S.plan.tasks.size);
  document.querySelectorAll(".row-check").forEach((check) => {
    const item = findItem(check.dataset.id);
    /* 与行渲染同一份判据：已报名/已截止/忙碌都禁用，已截止仍可查看。
     * 与 list.js rowHtml 的 checkDisabled 同一条判据，改一处要同步另一处（H2：此前这里缺 signStartPending） */
    check.disabled = S.busy || S.starting || termsLocked() || !isEligibleForPlan(item) || !!signedClash(item) || signStartPending(item);
  });
  /* 取消报名按钮与行渲染同一份互斥判据：计划、刷新、登录或另一场取消都会置灰并写原因 */
  document.querySelectorAll("[data-cancel]").forEach((btn) => {
    const id = btn.dataset && btn.dataset.cancel;
    if (!id) return;
    const block = cancelBlock(id);
    btn.disabled = block.off;
    btn.title = block.why;
    btn.textContent = S.cancel.busyId === id ? "正在取消…" : "取消报名";
  });
  paintBoardActions();
  paintDock();
  /* 计划结束（不再运行）时收起停止确认弹层；焦点在弹层里就移到「完成」按钮，没有就落到 #board */
  if (!S.busy) {
    const ask = $("#plan-stop-ask");
    if (ask && !ask.hidden) {
      const active = document.activeElement;
      const inside = !!active && (active.id === "btn-stop-keep" || active.id === "btn-stop-yes");
      ask.hidden = true;
      if (inside) {
        const finish = $("#btn-finish");
        const target = finish && !finish.hidden && !($("#result-actions") || {}).hidden ? finish : $("#board");
        if (target && target.focus) {
          if (target === $("#board")) target.tabIndex = -1;
          target.focus();
        }
      }
    }
  }
}

/* ---------------------------------------------------------------- 窗口分档与计划条 */
/* 与 styles.css 的断点是同一组阈值：宽 ≥1040 双栏；中 720–1039、窄 <720 单栏 + 底部计划条；
 * 高 <660 为矮窗。只看视口宽高，不读 UA。 */
function bandOf(width, height) {
  const w = Number(width) || 1280;
  const h = Number(height) || 800;
  return { band: w >= 1040 ? "wide" : (w >= 720 ? "medium" : "narrow"), short: h < 660 };
}

function applyBand() {
  const got = bandOf(window.innerWidth, window.innerHeight);
  S.band = got.band;
  S.short = got.short;
  const zd = $("#zd");
  if (zd && zd.dataset) {
    zd.dataset.band = got.band;
    zd.dataset.short = got.short ? "1" : "0";
  }
  if (got.band === "wide" && S.planOpen) setPlanOpen(false);
  else paintDock();
}

/* 中、窄档里计划栏和时刻表二选一：查看计划时收起时刻表，「返回列表」再换回来 */
function setPlanOpen(open) {
  S.planOpen = !!open && S.band !== undefined && S.band !== "wide";
  const zd = $("#zd");
  if (zd && zd.dataset) zd.dataset.planOpen = S.planOpen ? "1" : "0";
  const back = $("#btn-plan-back");
  if (back) back.hidden = !S.planOpen;
  paintDock();
}

/* 计划条：已选几场 + 查看计划 + 开始；有开始前提醒时不给「开始」，先让用户看计划。
 * 四态照原型 dockTitle / dockSub（TF05 / PB16）：
 *  草稿  标题「已选 N 场」/「还没选活动」，副文 还差一步 > 开始前提醒 > 摘要句（优先级同原型）；
 *  修改中  「修改中：已选 N 场」+「计划已暂停，改完要重新开始」；
 *  运行中  沿用「报名计划运行中」+ 倒计时（原型取 LED 标签，表里没列这一行，不动）；
 *  结果  结论标题 / 正文，与结果页同一来源（resultView），窄档结果页藏在计划栏里时 dock 也要说结论。 */
function paintDock() {
  const dock = $("#plan-dock");
  if (!dock) return;
  const narrow = !!S.band && S.band !== "wide";
  dock.hidden = !narrow || !!S.planOpen;
  if (dock.hidden) return;
  const items = selectedItems();
  const plan = $("#btn-plan");
  const warns = S.busy ? 0 : Number(S.preWarnCount) || 0;
  const result = !S.busy && resultMode();
  let title = items.length ? "已选 " + items.length + " 场" : "还没选活动";
  let sub = "";
  if (S.busy) {
    title = "报名计划运行中";
    sub = $("#countdown") ? String($("#countdown").textContent || "") : "";
  } else if (result) {
    const res = resultView();
    title = res.title;
    sub = res.text;
  } else if (S.editing) {
    title = "修改中：已选 " + items.length + " 场";
    sub = "计划已暂停，改完要重新开始";
  } else {
    /* 「还差一步」与计划栏里的 #plan-why 同一个判据：开始按钮禁用且不是正在开始 */
    const blocker = plan && plan.disabled && !S.starting ? startBlocker() : null;
    sub = blocker ? "还差一步：" + blocker.text
      : (warns > 0 ? "有 " + warns + " 条提醒，开始前先看一眼" : selectionSummary(items));
  }
  const start = $("#btn-dock-start");
  if (start) start.hidden = S.busy || result || warns > 0 || !plan || !!plan.disabled;
  $("#dock-title").textContent = title;
  $("#dock-sub").textContent = sub;
}

/* ---------------------------------------------------------------- 横幅 */
/* 一次只显示一条，按优先级取最前面那条（决策 014 第 12 条；顺序照原型 attention()）：
 * 程序组件缺失 > 条款未同意 > 断网 > 电脑刚睡眠过 > 登录待确认 > 登录已失效 > 北京时间问题
 * > 工具已经开着（note） > 旧数据迁移（MG01/MG02，原型 attention() 最后两条）。 */
function paintBanners() {
  const parts = [];
  if (S.runtime.error) {
    /* 组件问题只挂一条横幅（一个主要提示 + 恢复动作），不在满屏重复 */
    const copy = runtimeErrorCopy();
    parts.push('<div class="banner" data-tone="bad" role="alert"><span class="grow"><b>' + esc(copy.title) + "。</b>" +
      esc(copy.hint) + "</span>" +
      '<button class="btn btn-ghost" type="button" data-act="runtime-refresh">重新检查</button></div>');
  }
  if (S.terms.unknown) {
    /* TM07 照原型 Main:2138：未知态横幅拆成标题＋两句正文（日志那条归
     * markTermsUnknown，原型 Main:1180，只写一次）；停用学校动作并给
     * 唯一的重试入口；不自动弹窗——用户点开的才是可确认的同意动作 */
    parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>条款状态没能确认。</b>' +
      "读不到你同意过哪一版。登录、活动列表和报名计划暂时停用，打开条款重新确认后恢复。</span>" +
      '<button class="btn btn-ghost" type="button" data-act="terms-open">查看条款</button></div>');
  } else if (termsLocked()) {
    /* TM06 照原型 Main:2138：之前同意过旧版（acceptedVersion 存在且 ≠ 当前版）
     * 说「更新了，还没有同意新版」；从没同意或拒绝过保留原句。 */
    const updated = !!S.terms.acceptedVersion && !!S.terms.version &&
      S.terms.acceptedVersion !== S.terms.version;
    parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>' +
      (updated ? "使用条款更新了，还没有同意新版。" : "还没有同意使用条款。") +
      (updated ? "同意后才能登录、查看活动和开始报名计划。"
        : (S.terms.declined ? "登录、活动列表和报名计划保持停用。"
                            : "同意后才能登录、查看活动列表与开始报名计划。")) +
      "</span>" +
      '<button class="btn btn-ghost" type="button" data-act="terms-open">查看条款</button></div>');
  }
  if (!S.online) {
    /* 断网横幅照原型 Main.dc.html:1849：给一句下一步，并让用户自己重新检测 ——
     * 网络事件不可靠（系统仍认为联网时请求会一直挂着），所以不能只等 online 事件。 */
    parts.push('<div class="banner" data-tone="bad" role="alert"><span class="grow"><b>网络断开了。</b>' +
      (S.busy ? "到点时还没恢复，这次报名会失败。恢复以后看一眼计划结果。" : "恢复以后点“刷新”。") + "</span>" +
      '<button class="btn btn-ghost" type="button" data-act="net-recheck">重新检测</button></div>');
  }
  if (S.sleepGap) {
    /* LS21 照原型：写约几分钟，并点名睡眠期间到了开放时间的计划场次。
     * 睡眠窗口没记下来（当时业务时钟不可用）时不能断言「没有场次」，沿用原来的提醒句。 */
    const minutes = Math.max(1, Math.round(S.sleepGap / 60000));
    const missed = S.sleepWindow ? sleepMissedNames() : null;
    const detail = missed === null ? "要是睡过了开放时间，就赶不上了。看看计划和运行记录。"
      : missed.length ? "期间" + missed.map((name) => "「" + esc(name) + "」").join("") + "到了开放时间，没有提交。"
      : "期间没有场次到开放时间。";
    parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>电脑刚才睡眠了约 ' + minutes +
      " 分钟。</b>" + detail + "</span>" +
      '<button class="btn btn-ghost" type="button" data-act="sleep-ok">知道了</button></div>');
  }
  parts.push(...[loginBannerHtml(S.login.view || {}, S.busy)].filter(Boolean));
  if (!S.demo && typeof clockUiState === "function" && clockUiState() === "unavailable") {
    parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>北京时间还没校准。</b>' +
      "校准后才能开始报名计划；已保存的登录不受影响。</span>" +
      '<button class="btn btn-ghost" type="button" data-act="clock-open">查看时间</button></div>');
  }
  if (S.secondOpen) {
    /* GL01 note 档（原型 attention() 的 second，排在时钟之后）：又开了一次，第二份已退出，窗口已切回来 */
    parts.push('<div class="banner" data-tone="note" role="status"><span class="grow"><b>工具已经开着。</b>' +
      "刚才又打开了一次，已切回这个窗口。同一台电脑只运行一份，免得同一场被提交两遍。</span>" +
      '<button class="btn btn-ghost" type="button" data-act="second-ok">知道了</button></div>');
  }
  if (S.migration && !S.migrationDismissed) {
    /* MG01/MG02（原型 Main:2146/2147 的 attention() 末两条）：迁移成功与失败互斥。
     * 成功走 note 档，「知道了」只收本次运行内的横幅（不落盘）；失败走警示档，
     * 「登录」复用登录失效横幅的同一入口（data-act=login → openLogin）。 */
    const mg = S.migration;
    if (mg.login_failed && mg.other_failed) {
      /* 登录和其他都失败：U+2060 连住末尾两字，防单字掉行 */
      parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>旧版本的数据没能搬过来。</b>' +
        "旧文件还留在原来的位置；重新登录一次就行，设置要重新调⁠一下。</span>" +
        '<button class="btn btn-ghost" type="button" data-act="login">登录</button></div>');
    } else if (mg.login_failed) {
      parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>旧版本的登录信息没能搬过来。</b>' +
        "设置和运行记录已经搬好；重新登录一次就行，旧文件还留在原来的位置。</span>" +
        '<button class="btn btn-ghost" type="button" data-act="login">登录</button></div>');
    } else if (mg.other_failed) {
      parts.push('<div class="banner" data-tone="note" role="status"><span class="grow"><b>旧版本的设置或运行记录没能搬过来。</b>' +
        "登录信息已经搬好，不用重新登录；旧文件还留在原来的位置。</span>" +
        '<button class="btn btn-ghost" type="button" data-act="migrated-ok">知道了</button></div>');
    } else {
      parts.push('<div class="banner" data-tone="note" role="status"><span class="grow"><b>已把旧版本的数据搬到新位置。</b>' +
        "登录、设置和运行记录都在，不用重新登录。位置在设置的“本机数据”里。</span>" +
        '<button class="btn btn-ghost" type="button" data-act="migrated-ok">知道了</button></div>');
    }
  }
  $("#banners").innerHTML = parts.slice(0, 1).join("");
}

/* ---------------------------------------------------------------- 动作 */
