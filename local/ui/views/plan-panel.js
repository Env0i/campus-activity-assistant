/* 计划栏（新工作台右栏，决策 014）与任务呈现：阶段标题、路线/倒计时/LED、横幅、任务卡、
 * 窗口分档与中窄档计划条。由旧大屏 views/board.js 改名演进而来，元素 id 沿用，
 * 其他脚本按原函数名调用。 */
function paintSelected() {
  const box = $("#selected");
  const meta = $("#selected-meta");
  const boardText = $("#board-text");
  const items = selectedItems();
  const next = boardTargetItem();
  /* 运行中以 executionView() 为唯一目标：标题、路线、LED、批次数同源，
   * 不再从原勾选集合里补位（取消的场次不能继续当目标）。 */
  const view = executionView();
  box.className = "b-title";
  meta.innerHTML = "";
  boardText.textContent = "";
  if (!S.busy && S.login.present === false && !S.runtime.error) {
    setBoardTag("首次使用", "off", true);
    box.textContent = "登录后开始";
    boardText.textContent = "活动会在登录完成后自动加载。";
    return;
  }
  if (S.login.loginPending) {
    /* 登录尝试期间 S.busy 也为真，但这不是报名计划：
     * 不能把大屏说成「正在准备报名」，否则用户以为点登录触发了抢报名。 */
    setBoardTag("登录中", "amber", true);
    box.textContent = "正在打开登录窗口";
    boardText.textContent = "在浏览器里登完再回来；中途关掉窗口会保留原来的登录状态。";
    return;
  }
  if (resultMode()) {
    /* 结果页是独立分支（原型 phase === 'result' 的 res 段，P1）：标签、结论标题、副行都来自 resultView；
     * 不写地点时间 meta，成功场次被移出选择集合也不会退回草稿的「下一场」 */
    const res = resultView();
    setBoardTag(res.tag, res.tone, true);
    box.textContent = res.title;
    boardText.textContent = res.text;
    return;
  }
  /* 条款没同意（且登录过）：原型渲染函数 draft 段的 !s.terms 覆盖——标签「已暂停」，
   * 没选活动时标题副行说停用了什么（帮助和设置照常可用）。 */
  const termsHold = !S.busy && termsLocked() && S.login.present !== false;
  if (termsHold && !items.length) {
    setBoardTag("已暂停", "off", true);
    box.textContent = S.terms.unknown ? "重新确认条款后才能报名" : "同意条款后才能报名";
    boardText.textContent = S.terms.unknown ? "登录、活动列表和报名计划暂时停用。帮助和设置照常可用。"
      : "登录、活动列表和报名计划都停用了。帮助和设置照常可用。";
    return;
  }
  if (!S.busy && S.runtime.error && S.listState !== "ready") {
    /* 组件问题只留短状态（原型 draft 段 s.list === 'broken'）：完整原因与恢复动作在顶部横幅 */
    setBoardTag("不可用", "red", true);
    box.textContent = "暂时不能报名";
    boardText.textContent = "程序组件缺失，处理办法在顶部提示里。";
    return;
  }
  if (!S.busy && S.listState === "error" && !S.items.length) {
    /* 列表失败只留短状态：完整原因与「重试」在列表空态 */
    setBoardTag("需重试", "red", true);
    box.textContent = "活动暂时没加载";
    boardText.textContent = "具体原因看左边列表的提示。";
    return;
  }
  /* 加载态与「有没有选中」无关（原型 Main.dc.html:2006 只看 !sel.length）：
   * 手上有旧列表时点刷新同样要立刻显示在加载，否则界面像没反应。 */
  if (!S.busy && S.listState === "loading" && !items.length) {
    /* 列表还在拉：不得把「近期没有要开放的活动」当事实说出口 */
    setBoardTag("加载中", "off", true);
    box.textContent = "活动列表正在加载";
    boardText.textContent = "先等这一次加载结束。";
    return;
  }
  if (S.busy) {
    /* 运行中（原型渲染函数 ex 段）：标题与批次数都来自同一个执行目标，单场结束不会把这里改成结论。
     * 标题下面只留一行说明，不再写地点时间（原型运行态没有）；三个阶段分开说：
     * 等开放 ≠ 已开放待提交（代码独有的「准备报名」）≠ 真正在提交。 */
    if (view.phase === "submitting" || view.phase === "arming" || view.phase === "waiting") {
      setBoardTag(runTagText(view), view.phase === "submitting" ? "red" : "amber", true);
      box.textContent = view.item ? view.item.name : "这一场活动";
      boardText.textContent = runCaption(view);
      return;
    }
    /* 没有可执行任务、plan_done 还没到：准备中 / 正在汇总，不提前报成功 */
    setBoardTag(view.phase === "settling" ? "汇总中" : "准备中", "amber", true);
    box.textContent = view.phase === "settling" ? "正在汇总结果" : "正在准备报名";
    boardText.textContent = view.phase === "settling"
      ? "每一场都结束了，正在汇总这一轮的结果。"
      : "计划已经接管，正在核对每一场的开放时间。";
    return;
  }
  if (!items.length) {
    if (next) {
      const openNow = stateOf(next) === "open";
      setBoardTag(openNow ? "开放中" : "下一场", "amber", !openNow);
      box.textContent = next.name;
      /* 副行只留地点与时间（原型 draft 段 nextIt），「选这一场」按钮就在票区下面 */
      meta.innerHTML = boardMetaHtml(next);
    } else if (S.listState === "ready" && !S.items.length) {
      /* 学校成功返回 0 场（原型 draft 段）：大屏只留一句短状态，完整原因在列表空态，不在这里复读 */
      setBoardTag("暂时没有", "off", true);
      box.textContent = "学校当前没有活动";
      boardText.textContent = "稍后刷新再看。";
    } else if (S.listState === "ready" && bnowS() === null && !S.demo) {
      /* 没有可信现在：不能断言「没有可报名的场次」，也不能显示伪计数。
       * 只给短状态和单一恢复入口（打开时间详情重新校准）。 */
      setBoardTag("时间待校准", "amber", true);
      box.textContent = "时间待校准";
      boardText.innerHTML = "校准北京时间后才能判断哪些场次可以报名。" +
        '<button type="button" class="btn btn-line btn-mini" data-open-clock>查看时间详情</button>';
    } else if (S.listState === "ready") {
      /* 列表里有活动，只是没有可执行目标（全已报名 / 全已截止 / 报名时间待公布）：
       * 这不是「学校没返回」，数据仍在列表里，别替学校下结论。 */
      setBoardTag("暂时没有", "off", true);
      box.textContent = "没有可报名的场次";
      boardText.textContent = "列表里的活动已报名、已截止或还没公布报名时间。";
    } else {
      setBoardTag("暂时没有", "off", true);
      box.textContent = "近期没有要开放的活动";
      boardText.textContent = "可能还没公布报名时间，也可能都报过了。过一会儿点「刷新」看看。";
    }
    return;
  }
  /* 选了活动（原型 draft 段）：标题一律「已选 N 场」，副行一句汇总；地点时间和场名都在票里，不再复读 */
  if (termsHold) setBoardTag("已暂停", "off", true);
  else setBoardTag(S.editing ? "修改中" : "报名计划", "amber", true);
  box.textContent = "已选 " + items.length + " 场";
  boardText.textContent = selectionSummary(items);
}

/* 草稿副行（原型 renderVals 的 summary）：「X 场立即报名，Y 场预报名等开放」，为 0 的一半不写 */
function selectionSummary(items) {
  const instant = items.filter((item) => modeOf(item) === "instant_signup").length;
  const pre = items.length - instant;
  return [instant ? instant + " 场立即报名" : "", pre ? pre + " 场预报名等开放" : ""]
    .filter(Boolean).join("，");
}

/* 原型 hms()：HH:MM:SS，跨天时前面加「明天 / 后天 / N 天后」（学校时区）。
 * 读不到可信的现在时只给时刻，不猜是哪一天。 */
function hmsDay(ts) {
  if (ts === null || ts === undefined || !Number.isFinite(Number(ts))) return "—";
  const clock = fmtClock(ts);
  const bnMs = businessNowMs();
  if (bnMs == null) return clock;
  const diff = Math.round((startOfDay(ts * 1000) - startOfDay(bnMs)) / 86400000);
  if (diff <= 0) return clock;
  return (diff === 1 ? "明天 " : (diff === 2 ? "后天 " : diff + " 天后 ")) + clock;
}

/* 运行中标签（原型 ex 段 head）：离开放 5 秒以内叫「即将开放」 */
const RUN_SOON_S = 5;
function runTagText(view) {
  if (view.phase === "submitting") return "正在提交";
  if (view.phase === "arming") return "准备报名";
  const left = view.openAt === null ? null : bnLeftSec(view.openAt);
  return left !== null && left <= RUN_SOON_S ? "即将开放" : "等开放";
}

/* 每秒走字用：阶段或标签一变就重画标题区（tick.js） */
function runHeadKey() {
  const view = executionView();
  return view.phase + "|" + (["submitting", "arming", "waiting"].indexOf(view.phase) >= 0 ? runTagText(view) : "");
}

/* 运行中标题下面那一行（原型 ex.cap）；「准备报名」是代码独有的阶段，标点照同一口径 */
function runCaption(view) {
  const count = view.count;
  if (view.phase === "submitting") {
    if (count > 1) return "正在提交 " + count + " 场，每场结果单独显示。";
    const task = view.task || {};
    const tried = Math.max(0, Math.floor(Number(task.attempts) || 0));
    const last = String(task.last_reason || "").trim();
    return "已提交 " + tried + " 次" + (last ? "，最近：" + last : "");
  }
  if (view.phase === "arming") {
    return count > 1 ? "已开放，正在准备 " + count + " 场，每场结果单独显示。" : "已开放，正在准备提交。";
  }
  return count > 1 ? "这一批 " + count + " 场同时提交，到点自动开始。" : "这一场等开放，到点自动开始。";
}

function setBoardTag(text, tone, dot) {
  const tag = $("#board-tag");
  const label = $("#board-tag-text");
  if (!tag || !label) return;
  tag.dataset.tone = tone || "amber";
  tag.dataset.dot = dot === false ? "false" : "true";
  label.textContent = text;
}

/* 整屏外框（原型 .board.st-ok / st-warn / st-bad）：只在结果页按结论上色，运行中保持运行色。
 * 含「待核对」的计划不画成确定失败的红框，展示语义不能替用户宣布失败（FR06）。 */
function boardPlanState() {
  if (S.busy) return "running";
  if (!resultMode()) return "idle";
  const frame = resultView().frame;
  if (frame === "ok") return "completed";
  if (frame === "bad") return "failed";
  if (frame === "warn") return String(S.plan.status) === "partial" ? "partial" : "attention";
  return "stopped";
}

function paintBoardState() {
  const board = $("#board");
  if (!board) return;
  board.dataset.planState = boardPlanState();
}

function boardMetaHtml(item) {
  if (!item) return "";
  const placeText = String(item.place || "地点待定");
  const place = esc(placeText);
  const act = esc(activityTimeText(item));
  /* 大屏地点默认两行；按钮原生支持 Enter/Space，聚焦即可展开全文（R19）。
   * 表格的 .c-place 用同一套「两行 + 聚焦展开」口径，但互不依赖。 */
  return '<button type="button" class="b-place" data-place-toggle aria-expanded="false"'
    + ' title="' + esc("完整地点：" + placeText + "（Enter 展开/收起）") + '">'
    + '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-6-5.3-6-10a6 6 0 1 1 12 0c0 4.7-6 10-6 10z"/><circle cx="12" cy="11" r="2.2"/></svg>'
    + '<span class="b-place-text">' + place + '</span></button>'
    + '<span><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/></svg>' + act + "</span>";
}

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

function paintBoardActions() {
  const actions = $("#route-actions");
  const quickPick = $("#btn-board-pick");
  const checks = $("#plan-checks");
  const headed = $("#headed-label");
  const clear = $("#btn-clear-plan");
  const start = $("#btn-plan");
  const policyFor = $("#retry-for") ? $("#retry-for").closest(".policy-select") : null;
  const policyMax = $("#max-attempts") ? $("#max-attempts").closest(".policy-select") : null;
  if (!actions) return;
  const result = resultMode();
  /* 「选这一场」在正文票区下面（原型 hasPick）：没选活动、有下一场、列表已加载、条款已同意、不在结果页 */
  const showPick = !S.busy && !result && !selectedItems().length && !!boardTargetItem()
    && S.listState === "ready" && !termsLocked();
  if (quickPick) quickPick.hidden = !showPick;
  /* 结果页（计划结束）只留「重新选择 / 完成」，不再摆开始按钮 */
  /* 「清空」只在草稿且有选中时出现（原型 showClear）；运行中、结果页都不显示 */
  if (clear) clear.hidden = S.busy || result || !S.selected.size;
  if (S.busy || result) {
    actions.hidden = true;
    return;
  }
  actions.hidden = false;
  /* 主按钮一直在（禁用时下面写「还差一步」）；没登录由「还差一步：还没有登录」+「去登录」承担 */
  [checks, headed, policyFor, policyMax, start].forEach((el) => { if (el) el.hidden = false; });
  const restore = $("#btn-edit-restore");
  if (restore) restore.hidden = !S.editing;
  paintEditNote();
}

/* 修改中的说明（原型 editNote）：三句拼成，离最近一场开放不到 300 秒时报剩余时间 */
function editNoteText() {
  let text = "计划已暂停，重新开始前不会自动报名。";
  const done = Math.max(0, Math.floor(Number(S.editing && S.editing.doneN) || 0));
  if (done > 0) text += "已结束的 " + done + " 场不受影响。";
  const now = bnowS();
  let first = null;
  ((S.editing && S.editing.ids) || []).forEach((id) => {
    const item = findItem(id);
    const ts = item ? toTs(item.sign_start) : null;
    if (ts !== null && (first === null || ts < first)) first = ts;
  });
  if (now !== null && first !== null) {
    const gap = first - now;
    if (gap > 0 && gap <= 300) text += "离最近一场开放只剩 " + durText(gap) + "。";
  }
  return text;
}

function paintEditNote() {
  const note = $("#edit-note");
  if (!note) return;
  note.hidden = !S.editing || S.busy;
  note.textContent = S.editing && !S.busy ? editNoteText() : "";
}

/* 结果页（原型 phase === 'result'）：计划已结束，且结果页标记还开着（state/plan.js）。
 * 不再靠选择签名相等来判断：成功场次被自动移出选择集合不会让结果页退回草稿。 */
function resultMode() {
  return !S.busy && !S.editing && S.plan.tasks.size > 0
    && PLAN_TERMINAL.indexOf(String(S.plan.status || "")) >= 0 && resultPageOpen();
}

/* 空选状态优先展示当前开放场次；没有开放场次时再展示最近的未来场次。 */
function boardTargetItem() {
  const next = nextOpen();
  if (next.bestId) return findItem(next.bestId);
  if (next.openNow) return S.items.find((item) => !item.signed && stateOf(item) === "open") || null;
  return null;
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
 * 读 advanced_features_state.credential（bootstrap 与手机面板刷新都带）；读不到就当没开。 */
function autoLoginCredential() {
  const phone = window.PhonePanel && window.PhonePanel.state && window.PhonePanel.state.advanced;
  const adv = phone || S.advanced || {};
  const cred = adv.credential || {};
  return { saved: !!cred.saved, ocr: !!cred.ocr_ready, paused: !!cred.paused };
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
      text: "要等到" + (/^\d/.test(until) ? " " : "") + until + "，" + missing + "。中途登录失效要你"
        + (has ? "输验证码" : "重新登录") + "；开放前 100 秒内失效，那场就结束。",
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
    list.push({ tone: "warn", text: "有场次在 24 小时以后才开放，计划要一直运行到那时。这段时间电脑不能关机或睡眠。" });
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
        + "</b><small>" + esc(activityTimeText(item)) + '</small></div><button type="button" data-remove="'
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
  $("#policy-text").innerHTML = "尝试 <b>" + esc(picked ? picked.label : "2 分钟") + "</b>，<b>"
    + (cap > 0 ? "最多 " + cap + " 次" : "不限次数") + "</b>";
}

/* 运行中「来不及」的判断（架构方案 4.3）：有场次在提交，或还没提交的场次离开放不到 100 秒。
 * 与后端 local/domain/login_rules.py 的 LATE_WINDOW_S 同一个数；修改计划的禁用条件也用它。 */
const LATE_WINDOW_S = 100;
function planLate() {
  const now = bnowS();
  if (now === null) return true;
  let late = false;
  S.plan.tasks.forEach((task) => {
    const st = String(task.status || "");
    if (st === "submitting") late = true;
    else if (st === "queued" || st === "waiting") {
      const open = toTs(task.sign_start);
      if (open !== null && open - now <= LATE_WINDOW_S) late = true;
    }
  });
  return late;
}

/* 最早一场还没提交的开放时刻：运行中登录失效时，「HH:MM:SS 前重新登录」按它减 100 秒算 */
function earliestWaitingOpen() {
  let best = null;
  S.plan.tasks.forEach((task) => {
    if (["queued", "waiting"].indexOf(String(task.status || "")) < 0) return;
    const open = toTs(task.sign_start);
    if (open !== null && (best === null || open < best)) best = open;
  });
  return best;
}

function paintRunPanel() {
  const warn = $("#run-warn");
  const hint = $("#plan-hint");
  const modify = $("#btn-modify");
  const why = $("#modify-why");
  if (!warn || !hint) return;
  if (!S.busy || !S.plan.id) {
    warn.hidden = true;
    hint.hidden = true;
    if (why) why.hidden = true;
    return;
  }
  const late = planLate();
  const tasks = Array.from(S.plan.tasks.values());
  const waitList = tasks.filter((t) => ["queued", "waiting"].indexOf(String(t.status || "")) >= 0);
  const submitting = tasks.some((t) => String(t.status || "") === "submitting");
  /* 运行中登录失效（决策 014 第 8 条，原型 runWarnV）：电脑在自动登录时只写一行说明；来得及就给「重新登录」 */
  const waitingAuto = tasks.some((t) => String(t.login_wait || "") === "waiting");
  const login = (S.login.view || {}).state;
  let text = "";
  let tone = "";
  let act = null;
  if ((waitingAuto || login === "bad") && (waitList.length || submitting)) {
    if (waitingAuto) {
      tone = "info";
      text = submitting ? "登录失效了，电脑正在自动登录（最多约 20 秒），成功后接着提交。"
        : "登录失效了，电脑正在自动登录。计划照常等开放，不用你管。";
    } else {
      const now = bnowS();
      const first = earliestWaitingOpen();
      if (late || first === null) {
        /* 来不及：有场次在提交，或最早一场离开放不到 100 秒（与修改计划同一个 planLate） */
        const pivot = submitting ? now : first;
        const later = pivot !== null && waitList.some((t) => {
          const open = toTs(t.sign_start);
          return open !== null && open > pivot;
        });
        text = "登录失效了。" + (submitting ? "正在提交" : "离开放不到 100 秒") + "，来不及重新登录，"
          + (submitting ? "正在提交的场次" : "这一批") + "会以“登录失效”结束。"
          + (later ? "后面的场次等它结束后重新登录就行。" : "");
      } else {
        text = "登录失效了，计划还在等。只要在 " + hmsDay(first - LATE_WINDOW_S) + " 前重新登录，计划照常继续；否则 "
          + hmsDay(first) + " 开放的那批会以“登录失效”结束。";
        act = { act: "login", label: "重新登录" };
      }
    }
  }
  warn.hidden = !text;
  warn.dataset.tone = tone;
  /* 每秒走字也调这里（tick.js，离开放 100 秒时「来得及」要改成「来不及」）：内容没变就不重写，
   * 免得「重新登录」按钮每秒重建、键盘焦点丢掉 */
  const html = text ? "<span>" + esc(text) + "</span>"
    + (act ? '<button type="button" data-act="' + act.act + '">' + esc(act.label) + "</button>" : "") : "";
  if (warn.dataset.html !== html) {
    warn.innerHTML = html;
    warn.dataset.html = html;
  }
  const fromPhone = String(S.plan.source || "") === "phone";
  hint.hidden = false;
  hint.textContent = "可以最小化窗口，但不要关闭工具或让电脑睡眠。"
    + (fromPhone ? "这个计划是从手机开始的，在电脑和手机上都能看进度、停止。" : "");
  /* 原型 modifyInfo.ok：没有还没提交的场次时也不能修改（没有能放回草稿的） */
  if (modify) modify.disabled = late || S.stopping || !waitList.length;
  if (why) {
    /* 修改说明逐字照原型 modifyInfo */
    why.hidden = false;
    why.textContent = submitting ? "有场次正在提交，现在不能修改。"
      : (late ? "有场次 100 秒内开放，工具已在准备，现在不能修改。"
        : "还没提交的场次可以放回草稿，改完要重新开始。");
  }
}

/* 刷新核对确认过的待核对场次：结束时没拿到结论，事后学校列表显示已报名 */
function verifiedSigned(task) {
  if (!task || String(task.stop_reason || "") !== "unconfirmed") return false;
  const item = findItem(task.activity_id);
  return !!(item && item.signed);
}

/* 「刷新核对」：只刷新活动列表（不新增学校接口、不重发报名），结果由列表的 signed 决定 */
function verifyTask(taskId) {
  if (!S.verifyAsked) S.verifyAsked = new Set();
  S.verifyAsked.add(String(taskId));
  refresh(false);
}

/* 结果页大数字（原型 res.counts）：五类，名额已满单列、中性色。
 * 「报名未成功」含 failed 里除名额已满、待核对以外的，以及 auth_unavailable（没提交）；
 * 刷新核对确认过的算「已报名」。pending 即「待核对」。 */
function resultCounts() {
  const counts = { ok: 0, full: 0, bad: 0, pending: 0, canceled: 0 };
  S.plan.tasks.forEach((task) => {
    const st = String(task.status || "");
    const stop = String(task.stop_reason || "");
    if (st === "success" || st === "already_signed" || verifiedSigned(task)) counts.ok += 1;
    else if (st === "canceled") counts.canceled += 1;
    else if (stop === "full") counts.full += 1;
    else if (stop === "unconfirmed") counts.pending += 1;
    else if (st === "failed") counts.bad += 1;
  });
  return counts;
}

/* 结果页结论（原型渲染函数 res 段，按顺序判断）：标签、标题、副行、外框，以及只在全成功 / 全失败时的小 LED */
function resultView() {
  const c = resultCounts();
  if (String(S.plan.status) === "stopped") {
    return { tag: c.pending ? "已停止，需确认" : "已停止", tone: c.pending ? "amber" : "off",
             title: "报名计划已停止", text: "已提交的场次保留原状态，还没提交的场次已取消。",
             frame: c.pending ? "warn" : "", led: null };
  }
  /* 计划结束时仍有没出结论的场次（排队 / 等待 / 提交中）不算全部报上 */
  const allSettled = Array.from(S.plan.tasks.values()).every((task) => TASK_TERMINAL.indexOf(String(task.status || "")) >= 0);
  if (c.ok && !c.bad && !c.pending && !c.canceled && !c.full && allSettled) {
    return { tag: "报名成功", tone: "green", title: "报名计划完成", text: "每场结束时都向学校核对过。",
             frame: "ok", led: ["✓", "green"] };
  }
  if (c.ok) {
    return { tag: "部分完成", tone: "amber", title: "报名计划部分完成",
             text: c.pending ? "有 " + c.pending + " 场需要到活动页核对，结果以学校为准。"
               : (c.full ? "有 " + c.full + " 场名额已满，不是工具出错。" : "结果以学校活动页为准。"),
             frame: "warn", led: null };
  }
  if (c.pending) {
    return { tag: "需确认", tone: "amber", title: "计划已结束，有 " + c.pending + " 场需确认",
             text: "工具不会自动重发，到学校活动页核对。", frame: "warn", led: null };
  }
  if (c.full && !c.bad) {
    return { tag: "名额已满", tone: "amber", title: "这次没报上：名额满了",
             text: "学校的名额在开放后被报满了，不是工具出错。", frame: "warn", led: null };
  }
  return { tag: "未成功", tone: "red", title: "报名计划没有成功", text: "每场的原因都列在下面。",
           frame: "bad", led: ["✕", "red"] };
}

/* 可以重新选的场次（原型 res.canRetry）：报名未成功和已取消的；不含名额已满、待核对（工具不自动重发），
 * 还要能加入计划（没截止、没报上、不和已报名冲突） */
function reselectableIds() {
  const ids = [];
  S.plan.tasks.forEach((task) => {
    const st = String(task.status || "");
    const stop = String(task.stop_reason || "");
    if (["failed", "canceled"].indexOf(st) < 0 || stop === "full" || stop === "unconfirmed") return;
    const item = findItem(task.activity_id);
    if (item && isEligibleForPlan(item) && !signedClash(item)) ids.push(String(item.id));
  });
  return ids;
}

function paintResultPanel() {
  const stats = $("#plan-stats");
  const actions = $("#result-actions");
  const done = resultMode();
  if (stats) {
    const c = resultCounts();
    /* 顺序和颜色照原型 .stats：已报名 ok、名额已满 wait、报名未成功 bad、待核对 ask、已取消 wait */
    const cells = [[c.ok, "已报名", "ok"], [c.full, "名额已满", "wait"], [c.bad, "报名未成功", "bad"],
      [c.pending, "待核对", "ask"], [c.canceled, "已取消", "wait"]].filter((cell) => cell[0] > 0);
    stats.hidden = !done || !cells.length;
    stats.innerHTML = done ? cells.map((cell) => '<div data-tone="' + cell[2] + '"><strong>' + cell[0]
      + "</strong><span>" + cell[1] + "</span></div>").join("") : "";
  }
  if (actions) {
    /* 页脚只有两个按钮（原型 res 模板）：重新选择未成功的场次（有可重选时）、完成，回到活动列表 */
    actions.hidden = !done;
    const reselect = $("#btn-reselect");
    if (reselect) reselect.hidden = !done || !reselectableIds().length;
  }
}

function earliestSelectedOpen() {
  let best = null;
  selectedItems().forEach((item) => {
    const ts = toTs(item.sign_start);
    if (ts !== null && (best === null || ts < best)) best = ts;
  });
  return best;
}

function paintPlan() {
  const conflictBox = $("#plan-conflicts");
  const validation = validateSelection();
  const messages = [];
  if (S.selectionNotice) messages.push("<div class=\"conflict-item\"><strong>选择提醒</strong><br>" + esc(S.selectionNotice) + "</div>");
  validation.errors.forEach((error) => messages.push("<div class=\"conflict-item\"><strong>" + esc(error.title) + "</strong><br>" + esc(error.text) + "</div>"));
  validation.conflicts.forEach((conflict) => messages.push("<div class=\"conflict-item\"><strong>活动时间重叠</strong><br>「" + esc(conflict.left.name) + "」与「" + esc(conflict.right.name) + "」举办时段重叠（" + esc(shortTime(conflict.left.act_start)) + " – " + esc(shortTime(conflict.left.act_end)) + "），只能选其中一场。</div>"));
  conflictBox.innerHTML = messages.join("");
  /* 选择提醒和冲突是草稿内容：结果页不摆（原型 res 模板没有），留在选择里的失败场次回到草稿后照常提醒 */
  conflictBox.hidden = messages.length === 0 || resultMode();

  const tasksBox = $("#plan-tasks");
  const tasks = Array.from(S.plan.tasks.values());
  /* 同一帧用同一个业务时刻；未知传 null，由任务卡显示「等待开放/待校准」 */
  const now = bnowS();
  /* 任务卡只在运行中和结果页出现；草稿（含结果页关掉以后）不摆上一轮的卡片 */
  const showTasks = tasks.length && (S.busy || resultMode());
  tasksBox.innerHTML = showTasks ? tasks.map((task) => taskHtml(task, now)).join("") : "";
  paintCountdown();
  paintTickets();
  paintPolicyLine();
  paintRunPanel();
  paintResultPanel();
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

function selectionSignature() {
  return Array.from(S.selected).slice().sort().join(",");
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

/* 秒级时间戳 → 学校时区 HH:MM:SS（LED 标注与点阵同款数字口径） */
function fmtClock(ts) {
  if (ts === null || ts === undefined) return "—";
  const p = schoolParts(ts * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return pad(p.h) + ":" + pad(p.mi) + ":" + pad(p.s);
}

/* 终态的停止条件人话：让用户知道是「到点/到次数/到截止」里的哪一个。
 * unconfirmed/auth_unavailable 不是「失败原因」，是「结果没确认」：
 * 用词必须留出核对空间，不能写成没抢到。 */
function stopReasonText(reason) {
  return {
    success: "报名成功",
    already_signed: "已经报过",
    login_invalid: "登录失效，先重新登录",
    auth_unavailable: "登录状态暂时无法确认",
    max_attempts: "达到最大提交次数",
    retry_duration: "重试时长到了",
    sign_end: "报名已截止",
    unconfirmed: "报名结果待核对",
    user_stopped: "已停止",
    process_error: "程序流程异常结束",
    /* 回包分类后的结束结论（架构方案 3.3）：后端另给 outcome_label，这里是兜底同义词 */
    full: "名额已满",
    closed: "报名已截止",
    conflict: "时间冲突",
    no_activity: "活动不存在",
    clock_skew: "本机时钟不准",
    unknown_reply: "学校回了无法识别的结果",
    page_unavailable: "学校页面打不开",
  }[reason] || "";
}

/* 每场准备好以后写明提交方式（架构方案 3.1）：直接提交，或改用页面点击并写原因 */
function taskViaHtml(task) {
  const path = String(task && task.path || "");
  if (path === "direct") return '<small class="t-via">直接提交，不经过活动页</small>';
  if (path === "click") {
    const why = String(task.path_reason || "").trim();
    return '<small class="t-via" data-tone="warn">改用页面点击' + (why ? "：" + esc(why) : "")
      + "。活动页已提前打开</small>";
  }
  return "";
}

/* telemetry 的 retry_deadline 是 epoch 秒（后端结构化行）；空串/0 表示没有 */
function telemetryDeadline(task) {
  const epoch = Number(task && task.retry_deadline);
  return Number.isFinite(epoch) && epoch > 0 ? epoch : null;
}

/* 提交中任务卡的说明（原型 card 的 submitting 支）：「已提交 N 次（上限 M 次）。最近：<原因>，重试到 HH:MM:SS」。
 * taskHtml 与每秒走字共用这一份；0 表示不限，必须明说。截止优先 telemetry，其次统一推导；
 * 截止未知（已开放又没有任何启动参考点）时最后一段写「等待提交结果」，不编 0 秒。 */
function submittingDetail(task) {
  const attempts = Math.max(0, Math.floor(Number(task && task.attempts) || 0));
  const cap = Number(task && task.max_attempts);
  const limited = Number.isFinite(cap) && cap > 0;
  const head = "已提交 " + attempts + " 次（" + (limited ? "上限 " + cap + " 次" : "不限次数") + "）";
  const tail = [];
  const last = String(task && task.last_reason || "").trim();
  if (last) tail.push("最近：" + last);
  const deadline = effectiveRetryDeadline(task);
  tail.push(deadline === null ? "等待提交结果" : "重试到 " + hmsDay(deadline));
  return head + "。" + tail.join("，");
}

function taskHtml(task, now) {
  const state = String(task.status || "queued");
  /* 标签与说明都按显示阶段改写：raw submitting 可能只是提前开页的预热 */
  const label = taskDisplayLabel(task);
  const cls = taskClass(state, task);
  /* 混合计划每场显示自己的模式：快照带 signup_mode，旧载荷按时间现算 */
  const mode = String(task.signup_mode || modeOf(task));
  const modePrefix = taskModePrefix(task);
  const stop = String(task.stop_reason || "");
  const tried = Math.max(0, Math.floor(Number(task.attempts) || 0));
  let detail = task.reason || task.detail || "";
  if (RUNNING_STATUSES.indexOf(state) >= 0) {
    /* 等待 / 准备 / 提交 / 等电脑自动登录共用一份解释（每秒走字也用它）；typing 的等待文案只在没有阶段说明时兜底 */
    detail = taskDisplayDetail(task, now)
      || (state === "waiting" ? (mode === "pre_register" ? "等待报名开放" : "报名已开放，马上开始") : detail);
  } else if (verifiedSigned(task)) {
    /* 刷新核对：学校列表显示这场已报名，就按成功说，不再让用户去核对（原型 card.verify） */
    detail = "刷新核对：学校显示已报名";
  } else if (state === "failed" && stop === "full") {
    detail = "学校说报名人数已满，这一场到此结束，不再提交。不是工具出错。" + (tried ? "已提交 " + tried + " 次" : "");
  } else if (state === "canceled") {
    /* 整个计划停下时还没提交的场次 vs 用户逐场取消的（原型 finishState / card.cancel） */
    detail = String(S.plan.status || "") === "stopped" ? "计划已停止，这一场没有提交" : "你取消了这一场";
  } else if (state === "failed") {
    if (stop === "unconfirmed" && S.verifyAsked && S.verifyAsked.has(String(task.task_id))
        && S.listState === "ready") {
      detail = "刷新核对：学校列表还没显示已报名，可能有延迟，去活动页看一眼；本工具不会再自动重发";
    } else if (stop === "unconfirmed") {
      /* 已发出的请求撤不回来：只陈述「发过几次、没拿到回应」，不下失败结论（原型 finishState） */
      detail = "已提交 " + tried + " 次，没拿到确定回应；结束时向学校核对也没查到结果。去活动页看一眼，或稍后刷新核对。工具不会再自动重发。";
    } else if (stop === "auth_unavailable") {
      detail = "登录状态无法确认，本场没有提交 · 检查网络后刷新重试";
    } else {
      const bits = [];
      if (task.attempts) bits.push("提交了 " + task.attempts + " 次");
      const stopNote = String(task.outcome_label || "") || stopReasonText(task.stop_reason);
      if (stopNote && stop !== "success" && stop !== "already_signed") bits.push(stopNote);
      if (bits.length) detail = (detail ? detail + "（" : "") + bits.join("，") + (detail ? "）" : "");
    }
  } else if (state === "success") {
    /* 学校回包原话（last_reason）有就引用，去掉句末标点；没有就只说核对结论 */
    const said = String(task.last_reason || "").trim().replace(/[！!。.]+$/, "");
    detail = (said ? "学校回“" + said + "”，" : "") + "结束时向学校核对过：已报名";
  }
  const canCancel = ["queued", "waiting"].indexOf(state) >= 0 && S.busy;
  /* 待核对场次只给「刷新核对」：刷新活动列表看这一场是否已报名（ui-amendment-001 选项 A），不自动重发；
   * 不做「打开活动页」（后端没有按活动打开学校页面的接口，b-amendment-007） */
  const canVerify = !S.busy && stop === "unconfirmed" && !verifiedSigned(task);
  /* 名称与状态同排，说明在下，按钮另起一行（原型 .task / .t-acts） */
  const actionsHtml = (canCancel ? "<button class=\"task-cancel\" type=\"button\" data-task-id=\"" + esc(task.task_id) + "\">取消这一场</button>" : "")
    + (canVerify ? "<button class=\"task-cancel task-verify\" type=\"button\" data-task-id=\"" + esc(task.task_id) + "\">刷新核对</button>" : "");
  return "<div class=\"task-row\" data-task-id=\"" + esc(task.task_id) + "\"><strong class=\"task-name\" title=\"" + esc(task.name) + "\">" + esc(task.name) + "</strong><span class=\"task-state " + cls + "\">" + esc(label) + "</span><span class=\"task-detail\">" + esc(modePrefix + detail) + "</span>" + taskViaHtml(task) + (actionsHtml ? "<div class=\"task-actions\">" + actionsHtml + "</div>" : "") + "</div>";
}

/* 统一的有效重试截止（路线图、任务卡、LED、终态文案共用唯一来源）：
 * 优先 worker telemetry 的真实截止（epoch 秒）；没有再按任务推导。
 *
 * 推导锚点必须**不随墙钟跨过开放时刻而切换**。worker 的 retry_anchor()
 * 在 page.goto 之前取一次 max(原定开放, 启动时刻) 之后就钉死（grab.py），
 * 界面若按「open 还在未来就用 open，否则改用启动点」逐帧重算，会在开放那一秒
 * 把截止倒退 lead_s——预报名提前 100 秒开页，就会提前 100 秒归零。
 * 因此：有真实启动参考点时锚点固定为 max(原定开放, 启动点)；缺 open 只用启动点；
 * 只有「未来场且还没启动」才拿原定开放当计划参考。
 *
 * 「直到报名截止」且 sign_end 已知时，截止就是 sign_end，与启动点/开放点无关——
 * 排队中或快照字段还没齐时正会出现「有绝对截止、没有启动参考点」，这时不能判未知。
 *
 * 返回 null = 既没有绝对截止、也没有任何时间参考：调用方显示未知/预计，
 * 不拿当前时刻冒充 0 秒。缺 sign_end 的 0 时长回退 120 秒、sign_end 硬截断都保留。
 * 这里只算界面参考点，worker 的实际停止时机仍由后端决定。 */
function effectiveRetryDeadline(task, fallbackNow) {
  const telemetry = telemetryDeadline(task);
  /* 倒计时优先后端已接纳的 deadline：合法扩窗后的权威截止也从这里接管 */
  if (telemetry !== null) return telemetry;
  const now = Number.isFinite(fallbackNow) ? fallbackNow : bnowS();
  const rawFor = task && Number.isFinite(Number(task.retry_for_s)) ? Number(task.retry_for_s) : RETRY_WINDOW_S;
  /* -1 自动延长：初始预算按 120 秒算，扩窗后由上面的 telemetry 接管；
   * 它不是「直到报名截止」——只有 0 才直接取 sign_end */
  const retryFor = rawFor === -1 ? RETRY_WINDOW_S : rawFor;
  const signEnd = task ? toTs(task.sign_end) : null;
  /* 绝对截止不依赖任何起点：先把这条独立路径处理掉，别被 anchor 判空挡住 */
  if (retryFor === 0 && signEnd !== null) return signEnd;
  /* 计划接纳时冻结的起点最权威：worker 就是拿它算 --retry-start，
   * 界面用它推导与 worker 完全同一口径（慢启动不会让两边差出几秒） */
  const policyStart = Number(task && task.retry_started_at);
  if (Number.isFinite(policyStart) && policyStart > 0) {
    let frozen = retryFor > 0 ? policyStart + retryFor : policyStart + RETRY_WINDOW_S;
    if (signEnd !== null) frozen = Math.min(frozen, signEnd);
    return frozen;
  }
  const started = Number(task && task.run_started_at) || Number(task && task.submitSeen) / 1000 || null;
  const open = toTs(task && task.sign_start);
  let anchor = null;
  if (started !== null) anchor = open !== null ? Math.max(open, started) : started;
  else if (open !== null && open > now) anchor = open;
  if (anchor === null) return null;
  let deadline = retryFor > 0 ? anchor + retryFor : anchor + RETRY_WINDOW_S;
  if (signEnd !== null) deadline = Math.min(deadline, signEnd);
  return deadline;
}

/* 提交中的重试截止（任务卡与 LED 的旧入口）：已并入统一推导 */
function retryDeadline(task) {
  return effectiveRetryDeadline(task);
}

function updateControls() {
  const componentDown = !!S.runtime.error;
  /* 条款门禁（决策 013）：未同意时登录/刷新/开始全部禁用；离线演示不受限 */
  const termsGate = termsLocked();
  /* 缺组件：登录/开始都禁用（点了也是结构化失败）；刷新保持可用——复查组件并恢复的唯一通道 */
  $("#btn-login").disabled = S.busy || componentDown || termsGate;
  $("#btn-refresh").disabled = S.listState === "loading" || termsGate;
  /* 帮助任何状态都可打开；运行中只禁重看引导，原因写在按钮上。 */
  paintReplayButtons();
  const validation = validateSelection();
  /* 开始门禁：真实计划只在学校接口确认登录有效（valid）后可点；
   * checking/unknown/none/expired 一律禁用（demo 模式例外，供视觉演示）。
   * checking 必须显式排除：新一轮检查开始时不清旧 result，
   * 不排除的话上次 valid 会放行尚未确认的检查期。 */
  const loginReady = !!S.demo || (!S.login.checking && S.login.result === "valid");
  const canStart = !S.busy && !S.starting && !componentDown && !termsGate && loginReady && S.selected.size > 0
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
  $("#btn-clear-plan").disabled = S.busy || (!S.selected.size && !S.plan.tasks.size);
  document.querySelectorAll(".row-check").forEach((check) => {
    const item = findItem(check.dataset.id);
    /* 与行渲染同一份判据：已报名/已截止/忙碌都禁用，已截止仍可查看 */
    check.disabled = S.busy || termsLocked() || !isEligibleForPlan(item) || !!signedClash(item);
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

/* 计划条：已选几场 + 查看计划 + 开始；有开始前提醒时不给「开始」，先让用户看计划 */
function paintDock() {
  const dock = $("#plan-dock");
  if (!dock) return;
  const narrow = !!S.band && S.band !== "wide";
  dock.hidden = !narrow || !!S.planOpen;
  if (dock.hidden) return;
  const items = selectedItems();
  let title = "还没选活动";
  let sub = "在时刻表里勾选想报的活动";
  if (S.busy) {
    title = "报名计划运行中";
    sub = $("#countdown") ? String($("#countdown").textContent || "") : "";
  } else if (items.length) {
    title = "已选 " + items.length + " 场";
    sub = $("#countdown") ? String($("#countdown").textContent || "") : "";
  }
  const warns = S.busy ? 0 : Number(S.preWarnCount) || 0;
  if (warns > 0) sub = "有 " + warns + " 条提醒，开始前先看一眼";
  const plan = $("#btn-plan");
  const start = $("#btn-dock-start");
  if (start) start.hidden = S.busy || warns > 0 || !plan || !!plan.disabled;
  $("#dock-title").textContent = title;
  $("#dock-sub").textContent = sub;
}

/* ---------------------------------------------------------------- 横幅 */
/* 一次只显示一条，按优先级取最前面那条（决策 014 第 12 条）：
 * 程序组件缺失 > 条款未同意 > 断网 > 电脑刚睡眠过 > 登录问题 > 北京时间问题。 */
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
    /* 条款状态没读到（bootstrap 失败/缺 terms/版本非法）：停用学校动作并给
     * 唯一的重试入口；不自动弹窗——用户点开的才是可确认的同意动作 */
    parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>条款状态没能确认。</b>' +
      "登录、活动列表和报名计划暂时停用；点「查看条款」打开全文并重新确认，确认成功才会恢复。</span>" +
      '<button class="btn btn-ghost" type="button" data-act="terms-open">查看条款</button></div>');
  } else if (termsLocked()) {
    /* 条款未同意：一条横幅说明停用范围，并提供唯一的再同意入口；不强弹 */
    parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>还没有同意使用条款。</b>' +
      (S.terms.declined ? "登录、活动列表和报名计划保持停用。" : "同意后才能登录、查看活动列表与开始报名计划。") +
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
    parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>刚才有 ' + durText(S.sleepGap / 1000) +
      " 界面没动静，电脑可能睡眠了。</b>要是睡过了开放时间，就赶不上了。看看计划和运行记录。</span>" +
      '<button class="btn btn-ghost" type="button" data-act="sleep-ok">知道了</button></div>');
  }
  const loginView = S.login.view || {};
  if (loginView.state === "bad") {
    parts.push('<div class="banner" data-tone="bad" role="alert"><span class="grow"><b>登录已失效。</b>' +
      (S.busy ? "报名计划还在等，开放前 100 秒以前重新登录就照常继续。" : "重新登录后可以继续刷新和报名。") +
      "</span>" + '<button class="btn btn-ghost" type="button" data-act="login">重新登录</button></div>');
  } else if (loginView.state === "unknown") {
    parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>暂时无法确认登录状态。</b>' +
      "检查网络后点「刷新」，先不用重新登录。</span>" +
      '<button class="btn btn-ghost" type="button" data-act="runtime-refresh">刷新</button></div>');
  }
  if (!S.demo && typeof clockUiState === "function" && clockUiState() === "unavailable") {
    parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>北京时间还没校准。</b>' +
      "校准后才能开始报名计划；已保存的登录不受影响。</span>" +
      '<button class="btn btn-ghost" type="button" data-act="clock-open">查看时间</button></div>');
  }
  $("#banners").innerHTML = parts.slice(0, 1).join("");
}

/* ---------------------------------------------------------------- 动作 */
