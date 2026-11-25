"use strict";

/* 手机页 DOM 层——告警、控件门禁、计划板与日志（依赖 model*.js、ui-session.js 先加载）：
 * 负责提示条、离线与条款告警、控件启用态、底栏、计划板、任务卡及运行记录。 */

/* 提示条带一个最小来源标签，不靠比对整句中文来区分谁写的：
   stale_action 是「状态过时」这类门禁提示，成功同步后可以自动清掉；
   error 是网络/403/服务端业务错误，必须留到下一次明确覆盖。 */
function setBanner(text, kind) {
  const el = $("banner");
  model.bannerKind = text ? String(kind || "info") : "";
  el.textContent = text || "";
  el.hidden = !text;
  el.dataset.kind = model.bannerKind;
}
/* 只清「过时」这一种：读状态成功不代表网络或服务端错误已经解决 */
function clearStaleBanner() {
  if (model.bannerKind === "stale_action") setBanner("", "");
}
/* EX01 离线告警（原型 alert bad + 重试钮，Phone.dc.html:852）：两句照原型逐字，
   标题在 N=0 时不带「已重试」尾缀；重试钮复用 poll(true)（与右上角刷新同一动作）。
   静默过期（pill「同步中」）不亮红条——那时由 #stale-note 说明，红条只给「离线」档。
   连不上时界面不能看起来一切正常：刷新按钮始终可点，这里是唯一自救入口。 */
function syncOffline(stale) {
  const note = $("offline-note");
  if (!stale) {
    note.hidden = true;
    model.offlineTries = 0;
    return;
  }
  /* flying 时不走 connState 的 busy 短路：正在重试的红条要保持可见，钮写「同步中…」 */
  if (PhoneModel.connState(model, false).state !== "off") {
    note.hidden = true;
    return;
  }
  const tries = Number(model.offlineTries || 0);
  $("offline-note-title").textContent =
    tries > 0 ? "连不上电脑，已重试 " + tries + " 次" : "连不上电脑";
  $("offline-note-text").textContent =
    "确认电脑没睡眠、程序没退出；只是手机断网的话，电脑照常报名。";
  $("btn-offline-retry").textContent = model.flying ? "同步中…" : "重试";
  note.hidden = false;
}
/* 五条告警互斥（原型 alert 链，Phone.dc.html:851-856 的 if/else 次序）：
   离线 > 条款 > 登录失效 > 电脑列表失败 > 时钟待校准。离线由 syncOffline 画，
   这里只管其余四条的开关与 EX05 副句的 HH:MM（BE2 的 pc_list_error.at） */
function renderAlerts(stale) {
  syncOffline(stale);
  const off = !$("offline-note").hidden;
  const terms = model.termsOk === false;
  const expired = PhoneModel.loginExpired(model.login, model.flow || null);
  const pcList = !!model.pcListError;
  const clockDown = model.clockState === "unavailable";
  /* TM01 条款告警两句照原型逐字（Phone:853），同意后收起（服务端同样拦写动作） */
  $("terms-alert-title").textContent = "电脑上还没有同意使用条款";
  $("terms-alert-text").textContent = "回电脑同意后才能登录和报名。现在显示的是上次的缓存。";
  $("terms-alert").hidden = !(!off && terms);
  const expiredCopy = PhoneModel.loginCopy(PhoneModel.loginState(model.login), false);
  $("login-expired-title").textContent = expiredCopy.bannerTitle;
  $("login-expired-text").textContent = expiredCopy.bannerText;
  $("btn-banner-relogin").textContent = expiredCopy.bannerAction;
  $("login-expired-banner").hidden = !(!off && !terms && expired);
  /* EX05（原型 Phone:855）：两句照原型，HH:MM 来自快照 pc_list_error.at */
  $("pclist-alert-title").textContent = "电脑上的活动列表没加载";
  $("pclist-alert").hidden = !(!off && !terms && !expired && pcList);
  if (!$("pclist-alert").hidden) {
    const when = String((model.pcListError || {}).at || "");
    $("pclist-alert-text").textContent = when
      ? "电脑那边连不上学校站点，现在显示的是 " + when + " 更新的列表。恢复后会自动更新。"
      : "电脑那边连不上学校站点，现在显示的是缓存列表。恢复后会自动更新。";
  }
  /* EX06（原型 Phone:856）：两句照原型，无钮——校准是电脑端的事 */
  $("pcclock-alert-title").textContent = "电脑上的北京时间还没校准";
  $("pcclock-alert-text").textContent = "校准后才能开始报名计划，现在可以先选活动。";
  $("pcclock-alert").hidden = !(!off && !terms && !expired && !pcList && clockDown);
  /* UI-F13（原型 .alert.ok，Phone.dc.html:36/857）：配对成功告警排告警链最末
     （任何一条真告警都优先），点过「知道了」本会话不再出现 */
  $("pair-ok-alert").hidden = !(!off && !terms && !expired && !pcList && !clockDown
    && model.pairOkPending);
}
function canWrite() {
  model.nowMs = Date.now();
  return !PhoneModel.isStale(model.lastOkAt, model.nowMs);
}

function refreshControls() {
  model.nowMs = Date.now();
  const stale = PhoneModel.isStale(model.lastOkAt, model.nowMs);
  const conn = PhoneModel.connState(model, model.flying);
  /* 圆点是 pill 的固定子元素：文案写进内层 #conn-text，不整体覆盖 textContent */
  $("conn-text").textContent = conn.text;
  $("conn").dataset.state = conn.state;
  $("stale-note").hidden = !stale;
  /* 刷新钮是图标钮（G01）：忙态不写字，交给 disabled + pill「同步中」 */
  $("btn-refresh").disabled = Boolean(model.flying);
  /* 电脑没同意条款：手机停在缓存，不能开始也不能重新登录（与电脑同一道门，后端也会拦） */
  $("btn-start").disabled = !PhoneModel.canStart(model) || model.termsOk === false;
  $("btn-stop").hidden = !model.busy;
  /* relCanSubmit（原型 Phone:675）：提交验证码要 4 位；登录要账号密码都填
     （relogin_setup 没到手前不猜 needAcct，与旧默认一致先亮着） */
  $("btn-relogin-submit").disabled = !PhoneModel.canSubmitRelogin(model, model.challenge)
    || !PhoneModel.relCanSubmit({ needCap: !!model.challenge,
                                  code: String(($("code") || {}).value || "") });
  $("btn-relogin").disabled = Boolean(model.reloginStarting) || model.termsOk === false
    || !PhoneModel.relCanSubmit({
      needAcct: model.reloginSetup
        ? PhoneModel.relNeedAcct(model.flow, model.reloginSetup) : false,
      user: String(($("relogin-user") || {}).value || ""),
      pass: String(($("relogin-pass") || {}).value || ""),
    });
  $("btn-relogin-auto").disabled = model.termsOk === false;
  $("btn-relogin-open").disabled = Boolean(model.reloginStarting) || model.termsOk === false;
  /* 电脑上没保存账号或保存的密码不对：手机上露出账号密码输入（RL04 needAcct；
     handoff 时电脑自己填，整块收起）；relogin_setup 没到手时先收着（与旧默认一致） */
  const setup = model.reloginSetup || null;
  const account = $("relogin-account");
  if (account) account.hidden = setup ? !PhoneModel.relNeedAcct(model.flow, setup) : true;
  $("btn-cancel-start").hidden = !(model.pending && !model.pending.done);
  /* SH01 fhint（#review-policy）与 SH05 登录行（#login-line）：随快照走，
     retry=0 的缺截止口径按已选场算（与 openReview 同一公式） */
  const pickedNow = (model.items || []).filter(
    (item) => model.selected.indexOf(item.id) >= 0);
  const hint = PhoneModel.retryHint(model.retry.retry_for_s,
    pickedNow.some((i) => i.sign_end_ts));
  $("review-policy").textContent = hint;
  $("review-policy").hidden = !hint;
  $("login-line").textContent = PhoneModel.loginLine(model.login, model.reloginSetup, model.flow || null);
  $("btn-relogin-open").textContent = PhoneModel.loginCopy(PhoneModel.loginState(model.login), false).reloginEntry;
  /* 验证中（提交验证码）sheet 不给关闭钮；开关本身在 openSheet/closeSheet 里管 */
  if (model.sheetId) $("btn-sheet-close").hidden = sheetBusy();
  renderAlerts(stale);   // EX01/EX02/EX05/EX06/TM01：五条告警按原型优先链互斥
  renderBar();
  renderRelogin();   // RL01–RL08：重登 sheet 的六态跟着模型走
}

/* G02 底栏左侧标题两行（原型 bar 段，Phone.dc.html:859-868）：草稿/核对中/运行中三态。
   RW02：核对中超过 15 秒对账窗（pendingLong）标题换「还没有查到结果」；
   运行中的来源标注「（从手机开始）」并入 bar-t（产品注记，原型无此句）。
   RS01（原型 isResult 的 .bar.stack，Phone.dc.html:295/933-934）：结果态整条换纵排两钮
   （重新选择仅在有未成功场时出现），左侧标题与三态主钮全收；
   TM01（原型 bar 分支，Phone.dc.html:863）：条款未同意副题换「电脑上同意条款后才能开始」，
   主钮禁用在 refreshControls（服务端同样拦写动作）；
   EX02（原型 Phone:864）：登录失效副题换「还差一步：重新登录」，主钮换「重新登录」
   并指向重登（原型 fn=beginRelogin；钮不禁用——这正是修复入口）；
   EX06（原型 Phone:865）：时钟待校准副题换「电脑校准北京时间后才能开始」+ 主钮禁用
   （canStart 拦）；
   EX05（原型 pclisterr 板没有 bar，Phone:860）：电脑列表失败时草稿态整条藏起，
   运行/核对/结果三态不受影响（停止计划在离线也必须可点）。 */
function renderBar() {
  const title = $("bar-title");
  const sub = $("bar-sub");
  const bar = $("action-bar");
  const result = PhoneModel.resultView(model.plan, model.busy);
  bar.hidden = false;
  bar.className = result ? "bar stack" : "bar";
  $("bar-info").hidden = !!result;
  $("btn-reselect").hidden = !result || !result.canRetry;
  $("btn-finish").hidden = !result;
  if (result) {
    $("btn-start").hidden = true;
    $("btn-cancel-start").hidden = true;
    return;
  }
  const expired = PhoneModel.loginExpired(model.login);
  // I2：副题与登录行同口径（电脑正在静默自动登录不叫用户「还差一步」）；主钮仍用上面的 expired，口径不动
  const expiredSub = PhoneModel.loginExpired(model.login, model.flow || null);
  const recoveringSub = PhoneModel.loginRaw(model.login)
    && PhoneModel.loginRecovering(model.login, model.flow || null);
  const copy = PhoneModel.loginCopy(PhoneModel.loginState(model.login), recoveringSub);
  if (model.busy) {
    const fromPhone = model.plan && String(model.plan.source || "") === "phone"
      ? "（从手机开始）" : "";
    title.textContent = "计划进行中" + fromPhone;
    sub.textContent = "断网时也可以点停止";
  } else if (model.pending && !model.pending.done) {
    title.textContent = PhoneModel.pendingLong(model.pending, Date.now())
      ? "还没有查到结果" : "正在核对";
    sub.textContent = "请先不要重复点击";
  } else if (model.pcListError) {
    /* EX05（原型 Phone:860）：列表没加载就没有「已选 N 场」可言，整条不出 */
    bar.hidden = true;
    $("btn-start").hidden = false;
    return;
  } else {
    const picked = (model.items || []).filter(
      (item) => model.selected.indexOf(item.id) >= 0);
    const actText = PhoneModel.actBlockText(PhoneModel.actBlock(model.items, model.selected));
    title.textContent = "已选 " + model.selected.length + " 场";
    sub.textContent = model.termsOk === false
      ? "电脑上同意条款后才能开始"
      : (recoveringSub ? copy.recoveringSub
                 : (expiredSub ? copy.barSub
                 : (model.clockState === "unavailable"                   // EX06（Phone:865）
                    ? "电脑校准北京时间后才能开始"
                    : (PhoneModel.connState(model, model.flying).state === "off"  // UI-F3：离线不冒充「已选 N 场，可开始」
                       ? "连上电脑后才能开始"
                       : (actText || PhoneModel.planSummary(picked, PhoneModel.businessNowS(model)))))));
  }
  /* EX02：登录失效时底栏主钮换成「重新登录」（点击在 wire 里分流到 openRelogin） */
  $("btn-start").textContent = expired && !model.busy
    && !(model.pending && !model.pending.done) ? copy.barAction : "核对并开始";
  $("btn-start").hidden = model.busy;
}

/* G04 四站进度渲染（原型 .rail，Phone.dc.html:267/820-825）：四个站台各带圆点与虚线，
   状态词 done/now/hot 由 taskRail 给；aria-hidden 照原型（板题/副题已说明进展）。
   标签包一层 span：测试沙箱的 DOM 替身没有 createTextNode */
function renderRail(rail) {
  const box = $("board-rail");
  if (!box) return;
  const steps = rail || [];
  box.hidden = !steps.length;          // 原型 hasRail：草稿/等待没有 rail
  box.textContent = "";
  steps.forEach((step) => {
    const div = document.createElement("div");
    if (step.state) div.className = step.state;
    const dot = document.createElement("i");
    const label = document.createElement("span");
    label.textContent = step.label;
    div.appendChild(dot);
    div.appendChild(label);
    box.appendChild(div);
  });
}

/* LD01/LD02 草稿板 + G04 运行/等待板 + RS01 结果板 + TM01 条款板（原型 board 段，
   Phone.dc.html:260-270/799-827/828-840/798）：草稿态取 listView().board；等待态取
   pendingBoard（RW02）；运行态取 runBoard；计划结束换结果板（LED/cap 换统计区）；
   条款未同意的草稿态整板换已暂停（Phone:798） */
function renderBoard(view) {
  const section = $("plan-board");
  if (!section) return;
  const pendingNow = !!(model.pending && !model.pending.done);
  const result = PhoneModel.resultView(model.plan, model.busy);
  let board = null;
  if (model.busy) {
    board = PhoneModel.runBoard(model.plan, PhoneModel.businessNowS(model),
      PhoneModel.connState(model, model.flying).state === "off",
      model.lastOkText);   // EX01：离线档 capB「最后同步 HH:MM:SS」用同步成功时记下的北京时间
  } else if (pendingNow) {
    board = PhoneModel.pendingBoard(model.pending, Date.now());
  } else if (result) {
    board = { tag: result.head.text, tagTone: result.head.tone,
              title: result.title, sub: result.text };
  } else if (model.termsOk === false) {
    board = PhoneModel.termsBoard();
  } else {
    board = view.board;
  }
  section.hidden = !board;
  /* RS01：结果板描边色档照原型 boardCls（st-ok/st-warn/st-bad），其余档复位 */
  section.className = "board"
    + (result && result.boardCls ? " " + result.boardCls : "");
  if (!board) return;
  const tag = $("board-tag");
  tag.className = "b-tag" + (board.tagTone ? " " + board.tagTone : "");
  $("board-tag-text").textContent = board.tag;
  const nowS = PhoneModel.businessNowS(model);
  const nowLine = $("board-now");
  /* EX06（原型 nowText，Phone.dc.html:928）：时钟待校准时这一位写「待校准」，
     不再整段藏起——板头始终占位，与电脑端「北京时间」位同一呈现 */
  nowLine.hidden = false;
  $("board-now-text").textContent = nowS !== null
    ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)) : "待校准";
  /* RS01：结果态 LED 与 cap 收起，换统计大数字区（原型 isResult，Phone.dc.html:262） */
  $("board-led-wrap").hidden = !!result;
  $("board-cap").hidden = !!result;
  $("board-stats").hidden = !result;
  $("board-title").textContent = board.title;
  $("board-sub").textContent = board.sub;
  if (result) {
    renderStats(result.counts);
    renderRail([]);                        // 结果板没有四站进度（原型 notResult 才画 rail）
    model.pickId = "";
    $("btn-pick-next").hidden = true;
    return;
  }
  $("board-led-wrap").className = "led-wrap " + board.led.tone;
  $("board-led-wrap").setAttribute("role", "img");
  $("board-led-wrap").setAttribute("aria-label", board.led.aria);
  const led = $("board-led");
  led.style.gridTemplateColumns = "repeat(" + board.led.cols + ", minmax(0, 1fr))";
  led.textContent = "";
  board.led.dots.forEach((d) => {
    const dot = document.createElement("i");
    if (d.cls) dot.className = d.cls;
    led.appendChild(dot);
  });
  $("board-cap-text").textContent = board.led.cap;
  $("board-cap-b").textContent = board.led.capB;
  renderRail(board.rail);
  model.pickId = board.pickId || "";
  $("btn-pick-next").hidden = !board.pickId;
}

/* RS01 统计区渲染（原型 res.counts 循环，Phone.dc.html:262/832）：只显非零、
   tone 写在 div 上供 .stats 色档着色 */
function renderStats(counts) {
  const box = $("board-stats");
  box.textContent = "";
  (counts || []).forEach((n) => {
    const div = document.createElement("div");
    if (n.tone) div.className = n.tone;
    const num = document.createElement("strong");
    num.textContent = String(n.n);
    const label = document.createElement("span");
    label.textContent = n.text;
    div.appendChild(num);
    div.appendChild(label);
    box.appendChild(div);
  });
}

/* G10 任务卡 + 运行提示（原型 hasTasks/tip，Phone.dc.html:272-277/842-848）：
   每场结论由任务卡承载（renderTasks），原 #plan-line 的一行拼接退役；
   tip 只在运行中显示（原型 isRun），文案照 Phone:276 逐字（「演示：」控件不进产品） */
function renderPlan() {
  renderTasks();
  const tip = $("run-tip");
  tip.textContent = "手机可以锁屏，电脑别关机、别睡眠；要改计划回电脑，或先停止。";
  tip.hidden = !model.busy;
}

/* G10 任务卡渲染（原型 .tasks/.task，Phone.dc.html:145-153/272-274）：数值来自
   taskCard，这里只建元素、只写 textContent；卡上的「取消这一场」先过确认槽
   （RW03/SH04），并带上这一场的 task_id（B-P1-1，见 cancelTask 的注释） */
function renderTasks() {
  const box = $("plan-tasks");
  if (!box) return;
  const tasks = (model.plan && model.plan.tasks) || [];
  /* 原型 hasTasks：running || result（Phone.dc.html:929；RS01 结果态任务卡也渲染，
     原因三句见 taskCard 的 RS02 注） */
  box.hidden = !(model.busy || PhoneModel.resultView(model.plan, model.busy)) || !tasks.length;
  box.textContent = "";
  if (box.hidden) return;
  const nowS = PhoneModel.businessNowS(model);
  tasks.forEach((task) => {
    const card = PhoneModel.taskCard(task, Number(task.max_attempts) || 0, nowS);
    const el = document.createElement("div");
    el.className = "task";
    const name = document.createElement("b");
    name.textContent = card.name;
    const ts = document.createElement("span");
    ts.className = "ts" + (card.tone ? " " + card.tone : "");
    ts.textContent = card.label;
    const detail = document.createElement("small");
    detail.textContent = card.detail;
    el.appendChild(name);
    el.appendChild(ts);
    el.appendChild(detail);
    if (card.canCancel) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "t-cancel";
      btn.textContent = "取消这一场";
      /* B-P1-1：确认槽带上被点卡片这一场的 task_id（onConfirmYes→cancelTask） */
      btn.addEventListener("click", () => askConfirm("cancelTask", card.name, task.task_id));
      el.appendChild(btn);
    }
    box.appendChild(el);
  });
}

function addLog(text) {
  const li = document.createElement("li");
  li.textContent = String(text || "");
  $("logs").appendChild(li);
  while ($("logs").childElementCount > 40) $("logs").removeChild($("logs").firstChild);
}
