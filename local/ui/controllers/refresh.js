/* 刷新用例：偏好落地、计划快照摄入、check/list 双分支收口与列表合并。 */
function applyPrefs(prefs) {
  S.prefs = Object.assign({}, prefs || {});
  const filter = S.prefs.filter || {};
  S.filter = {
    q: String(filter.q || ""),
    status: ["all", "free", "signed"].indexOf(filter.status) >= 0 ? filter.status : "all",
    time: ["all", "today", "week"].indexOf(filter.time) >= 0 ? filter.time : "all",
    sort: ["open", "name"].indexOf(filter.sort) >= 0 ? filter.sort : "open",
    checkin: ["all", "yes", "no"].indexOf(filter.checkin) >= 0 ? filter.checkin : "all",
    checkout: ["all", "yes", "no"].indexOf(filter.checkout) >= 0 ? filter.checkout : "all",
  };
  S.logOpen = !!S.prefs.log_open;
  S.filterOpen = !!S.prefs.filter_open;   /* LS06 更多筛选面板的展开状态 */
  /* 重试策略偏好：只认白名单值，脏数据回落默认（120 秒 / 不限）。
   * 白名单与默认值来自 bootstrap 的权威选项（桌面/手机同源），不各写一套。 */
  const policy = S.prefs.retry_policy || {};
  const allowedFor = (S.retryOptions.choices || []).map((item) => String(item.value));
  const fallbackFor = Number(S.retryOptions.default) || 120;
  S.retryPolicy = {
    retry_for_s: allowedFor.indexOf(String(policy.retry_for_s)) >= 0 ? Number(policy.retry_for_s) : fallbackFor,
    max_attempts: Number.isInteger(policy.max_attempts) && policy.max_attempts >= 0 ? policy.max_attempts : 0,
  };
  $("#q").value = S.filter.q;
  $("#time").value = S.filter.time;
  $("#sort").value = S.filter.sort;
  $("#checkin").value = S.filter.checkin;
  $("#checkout").value = S.filter.checkout;
  $("#headed").checked = !!S.prefs.headed;
  $("#retry-for").value = String(S.retryPolicy.retry_for_s);
  $("#max-attempts").value = String(S.retryPolicy.max_attempts);
  paintChips();
  setLogOpen(S.logOpen, true);
}

/* 清筛选的唯一实现：只重置 6 个筛选键与对应控件。
 * 不能拿「半个 prefs」回调 applyPrefs——那会把重试策略、浏览器开关、
 * 运行记录展开、引导版本等一起重置掉，用户设的 10 分钟/3 次就白设了。 */
function clearFilters() {
  S.filter = { q: "", status: "all", time: "all", sort: "open", checkin: "all", checkout: "all" };
  $("#q").value = S.filter.q;
  $("#time").value = S.filter.time;
  $("#sort").value = S.filter.sort;
  $("#checkin").value = S.filter.checkin;
  $("#checkout").value = S.filter.checkout;
  paintChips();
  /* 只写过滤器差量：savePrefs 按 key 合并，其他偏好原样保留 */
  savePrefs({ filter: Object.assign({}, S.filter) });
  render();
}

/* 接纳代次并入会话记录（bootstrap/终态/ack 共用）：返回可用于 S.plan.gen 的值 */
function notePlanGeneration(value) {
  const gen = Number(value);
  if (!Number.isFinite(gen)) return Number(S.plan.gen) || 0;
  S.maxPlanGen = Math.max(S.maxPlanGen || 0, gen);
  return gen;
}

/* 窗口请求的归属上下文：发出 bootstrap 前记下当前计划对象与关键标记；
 * 回复到达时只有这份上下文没变，空闲快照的忙态和停止位才允许同步。 */
function planSyncContext() {
  return { plan: S.plan, status: String(S.plan.status || ""),
           gen: Number(S.maxPlanGen) || 0,
           starting: !!S.starting, stopping: !!S.stopping };
}

function planSyncContextCurrent(ctx) {
  return !!ctx && S.plan === ctx.plan && String(S.plan.status || "") === ctx.status
    && (Number(S.maxPlanGen) || 0) === ctx.gen
    && !!S.starting === ctx.starting && !!S.stopping === ctx.stopping;
}

function ingestBootstrapPlan(info, syncBusy = false) {
  /* 计划快照与实时事件共用同一条归属与合并路径（restore：只回放显示，不重发）；
   * 空闲快照的 busy 与停止位只在请求仍未过期时同步，已定终态或旧归属一律拒绝。 */
  const plan = info && info.plan;
  const explicitBusy = typeof (info && info.busy) === "boolean";
  if (plan && plan.plan_id) {
    const accepted = handlePlan(plan, { restore: true });
    if (!accepted || !syncBusy || !explicitBusy) return false;
  } else if (!syncBusy || !explicitBusy) {
    return false;   /* 缺 plan 时只接受调用方已核对归属且带显式布尔 busy 的回复 */
  }
  if (!info.busy) S.stopping = false;
  setBusy(info.busy);
  return true;
}

/* FB4：组件码唯一接收点——只认可知三码；未知 error 字段保持既有业务失败路径 */
function noteRoundError(code) {
  if (!code || !RUNTIME_ERRORS[code]) return false;
  S.runtime.roundError = code;
  S.runtime.error = code;
  return true;
}

/* FB4：刷新轮次收口——一个分支终态后，若本轮两分支都完成，按该轮故障累计
 * 决定撤/留横幅（有故障保持，无故障恢复）。任一分支未完成绝不提前清。 */
function updateRefreshBranchState(branch) {
  if (branch === "check") S.runtime.checkPending = false;
  else S.runtime.listPending = false;
  if (S.runtime.checkPending || S.runtime.listPending) return false;
  const next = S.runtime.roundError;
  if (S.runtime.error === next) return false;
  S.runtime.error = next;
  return true;
}

/* 状态结算独立于界面重画，检查回包在原有位置统一刷新。 */
function settleRefreshBranch(branch) {
  if (updateRefreshBranchState(branch)) {
    paintBanners();
    updateControls();
    render();
  }
}

/* 回调须匹配代次、请求号，且分支仍在等待。 */
function roundOpen(branch, id, gen) {
  return S.round.gen[branch] === gen && S.round[branch] === id &&
    (branch === "check" ? checkRoundOpen() : listRoundOpen());
}

/* 首次与接续共用计时及收口；捕获代次，避免旧轮影响新轮。 */
function armRefreshTimeout(branch, id, logCheckTimeout) {
  const gen = S.round.gen[branch];
  const timer = branch + "Timer";
  const seconds = branch === "check" ? 100 : 130;
  clearTimeout(S.round[timer]);
  S.round[timer] = setTimeout(() => {
    if (!roundOpen(branch, id, gen)) return;
    if (branch === "check") {
      settleCheckWaitFailure(logCheckTimeout ? "[X] 检查登录状态超过 " + seconds + " 秒没有回应，先按「暂时无法确认」处理；点「刷新」重试。" : "");
    } else {
      settleListWaitFailure("活动列表超过 " + seconds + " 秒没有回应");
    }
  }, seconds * 1000);
}

/* 未完成的登录结果条在检查确认有效后自动收起；放 refresh 前免混入其 setResult 计数 */
function clearStaleLoginResult(result) {
  const el = $("#result");
  if (result === "valid" && el && !el.hidden && el.dataset && el.dataset.kind === "login_attempt") setResult(null);
}

/* options.background 为真是「后台自动刷新」（见文件末尾的 autoRefreshTick）：
 * 它和手动刷新走同一套 check + list 双分支，但不能让画面闪——不置 loading（不出骨架）、
 * 不置 S.login.checking（不进「检查中」）、不 render、不开条款弹窗；
 * 失败时也不清列表和勾选（见 applyActivities / settleSynchronous 里的 S.round.background 分支）。 */
function refresh(quiet, options) {
  const background = !!(options && options.background);
  if (!hasBridge()) {
    if (!quiet) setResult({ ok: false, title: "还没有连接本机程序", text: "请从图形界面启动，再点「刷新」加载活动列表。" });
    return;
  }
  /* 取消报名进行中：学校动作互斥（X3），F5 与自动刷新也不放行 */
  if (S.cancel.busyId) return;
  /* 手动刷新（点按钮 / F5 / 空态按钮）清掉上一次取消的结果句；取消成功后的自动刷新是 quiet，保留它 */
  if (!quiet) { S.cancel.res = null; S.cancel.askId = ""; }
  /* 条款未同意：真实校验与活动列表都是学校网络动作，这一轮不发起；
   * 还没拒绝过就先弹条款，拒绝过或条款状态未知时安静返回——未知状态由
   * 横幅给重试入口，不在每次自动刷新时反复弹窗（按钮本就禁用，此处兜底） */
  if (termsLocked()) {
    /* 后台轮绝不替用户弹条款：这类打扰只留给用户自己点的刷新 */
    if (!background && !S.terms.declined && !S.terms.unknown) openTerms();
    return;
  }
  /* 已经知道断网就不要再发学校请求：结果只会是失败，用户看到的反馈是横幅
   * （原型 Main.dc.html:1849）。网络恢复后由用户自己点刷新。 */
  if (!S.online) {
    paintBanners();
    return;
  }
  autoRefreshState.attemptMono = _monoMs();
  S.round.background = background;
  const checkId = newRoundId("check");
  const listId = newRoundId("list");
  /* 消费代次隔离旧轮回调（FR04）。 */
  const checkGen = bumpRoundGeneration("check");
  const listGen = bumpRoundGeneration("list");
  S.round.check = checkId;
  S.round.list = listId;
  if (!background) {
    S.listState = "loading";
    S.listError = "";
  }
  /* 开启新一轮复查：两分支 pending、故障累计清零；旧横幅保持到本轮收口 */
  S.runtime.checkPending = true;
  S.runtime.listPending = true;
  S.runtime.roundError = null;
  if (!background) {
    /* 先进「检查中」：本机有会话也不提前说「登录有效」，等真实校验回来 */
    S.login.checking = true;
    paintLogin();
    render();
  }
  /* 首次检查超时写说明；接续检查沿用静默收口。 */
  armRefreshTimeout("check", checkId, true);
  armRefreshTimeout("list", listId);
  api("check", checkId).then((res) => {
    if (!roundOpen("check", checkId, checkGen)) return;
    settleSynchronous(res, "check");
  }).catch((err) => {
    if (!roundOpen("check", checkId, checkGen)) return;
    clearTimeout(S.round.checkTimer);
    settleCheckWaitFailure("[X] 检查登录状态失败：" + msg(err) + "；点「刷新」再试一次");
  });
  api("list_activities", listId).then((res) => {
    if (!roundOpen("list", listId, listGen)) return;
    settleSynchronous(res, "list");
  }).catch((err) => {
    if (!roundOpen("list", listId, listGen)) return;
    clearTimeout(S.round.listTimer);
    settleListWaitFailure(msg(err));
  });
}

/* 前端等待失败只收口本轮，不改后台保留的登录结论。 */
function settleCheckWaitFailure(log) {
  if (!S.round.background) {
    S.login.checking = false;
    S.login.ok = false;
    S.login.result = "unknown";
    syncLoginDependentView();
    if (log) addLog(log);
  }
  settleRefreshBranch("check");
}

/* 条款拒绝不是列表失败，不记普通日志或后台失败次数。 */
function settleListWaitFailure(reason, options) {
  const countFailure = !(options && options.termsRequired);
  if (S.round.background) {
    if (countFailure) noteBackgroundListFailed();
  } else {
    S.listState = "error";
    S.listError = reason;
    if (countFailure) noteListFailed(S.listError);
    render();
  }
  settleRefreshBranch("list");
}

/* 同步拒绝（如正在关闭 / 正在检查）没有终态事件：本轮分支必须当场收口，
 * 不让界面挂在「检查中」等一个永远不会来的事件（R11）。 */
function settleSynchronous(res, branch) {
  if (!res) return;
  /* 去重命中在途操作（C06）：接续原请求 ID 并重绑本轮超时；
   * 原操作若已经结束，后端会把终态一起带回来，直接落地，不干等旧事件。 */
  if (res.skipped) {
    const id = String(res.request_id || "");
    if (id) S.round[branch] = id;
    /* 后端未提供编号时保留本轮编号；缓存仍按真实编号查找。 */
    armRefreshTimeout(branch, S.round[branch]);
    if (branch === "check") {
      if (res.result) {
        window.onBackend.check(res.result);
        return;
      }
      const cached = takeRoundPayload("check", id);
      if (cached) {
        /* 终态比 skipped ack 先到：接续回原 owner 后重放一次，不干等 100 秒。
         * 提示本身按请求幂等：跨轮再重放同一 owner 时状态要恢复，日志不刷屏。 */
        if (firstNotice("check", id, "replay")) addLog("[i] 已接续这次检查的原结果。");
        window.onBackend.check(cached);
      }
      return;
    }
    if (res.result) {
      applyActivities(res.result, false);
      return;
    }
    const cachedList = takeRoundPayload("list", id);
    if (cachedList) applyActivities(cachedList, false);
    return;
  }
  if (res.ok !== false) return;
  /* 先结束分支，再把条款回绝交给门禁。 */
  const termsRequired = res.error === "terms_required";
  if (branch === "check") {
    clearTimeout(S.round.checkTimer);
    const log = termsRequired ? "" : "[X] " + ((res && res.text) || "这次检查没能开始") + "；点「刷新」重试。";
    settleCheckWaitFailure(log);
  } else {
    clearTimeout(S.round.listTimer);
    settleListWaitFailure((res && res.text) || "活动列表没能开始加载", { termsRequired: termsRequired });
  }
  if (termsRequired) noteTermsRequired(res);
}

/* LS11：列表没加载成功，补一条运行记录，句式照原型 listerr 画板的日志末行
 * 「活动列表没加载：连不上学校站点」。失败有四个来源（错误回包、Promise 失败、130 秒超时、
 * 入队被同步拒绝），各调一次；条款门拦下的那条不算失败，不写。 */
function noteListFailed(reason) {
  /* 只写用户看得懂的原因（与空态同一套归因的第一个分句），不回显「接口异常：URLError」这类原始异常名 */
  addLogFresh("活动列表没加载：" + listErrorCopy(cleanReason(reason)).cause);
}

/* addLog 会把最近 40 条里相同的句子整句吞掉，连续两次刷新都失败时第二次就看不到新的一行。
 * 失败类的记录要让用户看得见「又发生了一次」，所以只在紧挨着的上一行就是同一句时才不重复写。 */
function addLogFresh(line) {
  const text = String(line == null ? "" : line);
  const recent = S.recentLogs;
  if (recent.length && recent[recent.length - 1] === text) return;
  const at = recent.indexOf(text);
  if (at >= 0) recent.splice(at, 1);
  addLog(text);
}

const SIGNED_SYNC_MS = 120000;
let confirmedRefreshTimer = null;

function planConfirmedAt() {
  const ms = businessNowMs();
  return ms == null ? Date.now() : ms;   // 仅用于界面同步窗口；门禁仍由后端裁决
}

/* 报名结果回写（真实证据 P0-1）：success/already_signed 是已确认事实，
 * 立即映射到活动列表——计数、分组、行状态、复选框与冲突基线同步更新。
 * unconfirmed/failed/canceled 不写 signed，避免把未知猜成成功。
 * 同一计划同一事实只消费一次：已消费身份记在计划对象上（新计划自然重建），
 * 列表覆盖、缓存超时或取消成功撤销缓存都不会把它清掉。
 * 确认事实独立于活动行载入顺序：行还没到时先缓存，后到列表按既有窗口规则归并。
 * restore 只登记身份：页面恢复不以恢复时刻造同步窗口，也不改列表与选择。 */
function noteSignedTasks(tasks, options) {
  const restore = !!(options && options.restore);
  if (!S.plan.signedSeen) S.plan.signedSeen = new Set();
  let changed = false;
  (tasks || []).forEach((task) => {
    const status = String((task && task.status) || "");
    if (status !== "success" && status !== "already_signed") return;
    const id = String((task && task.activity_id) || "");
    if (!id) return;
    /* 后端旧载荷缺任务标识时，以同计划同活动作兼容键 */
    const key = String((task && task.task_id) || "") || ("activity:" + id);
    if (S.plan.signedSeen.has(key)) return;
    S.plan.signedSeen.add(key);
    if (restore) return;
    const atMs = planConfirmedAt();
    S.confirmed.set(id, {
      source: status === "success" ? "plan_success" : "plan_already_signed",
      atMs: atMs,
    });
    /* 活动行可能还没载入：确认先缓存，后到列表由 applyConfirmedToItems 按窗口归并 */
    const item = findItem(id);
    if (item) {
      item.signed = true;
      item.signed_source = status === "success" ? "plan_success" : "plan_already_signed";
      item.signed_confirmed_at = atMs / 1000;
    }
    /* 已成功的场次从下一次可执行选择集合移除；任务卡与结果卡保留 */
    S.selected.delete(id);
    changed = true;
  });
  /* 自动移出不是用户改勾选：结果页照常开着，只同步它记下的选择 */
  if (changed) syncResultSelection();
  return changed;
}

/* 列表载荷合并：后端已把窗口内的本地确认合并进来；这里再兜一层，
 * 覆盖「后端进程重启但界面还在」这类只有前端记得的确认。 */
function applyConfirmedToItems() {
  if (!S.confirmed.size) return;
  const nowMs = planConfirmedAt();
  S.items.forEach((item) => {
    const id = String(item.id);
    if (item.signed) {
      item.sync_pending = !!item.sync_pending && item.signed_source !== "school";
      return;
    }
    const record = S.confirmed.get(id);
    if (!record) return;
    if (nowMs - record.atMs > SIGNED_SYNC_MS) {
      S.confirmed.delete(id);       // 超过同步窗口：学校列表是最终权威
      return;
    }
    item.signed = true;
    item.signed_source = record.source;
    item.signed_confirmed_at = record.atMs / 1000;
    item.sync_pending = true;
  });
}

/* 计划收尾后安排一次有界列表刷新：只补权威列表，不重发、不改结论。
 * 刷新失败时后端仍保留已确认成功，界面下一轮成功刷新会重新合并。 */
function scheduleSignedRefresh() {
  if (confirmedRefreshTimer) clearTimeout(confirmedRefreshTimer);
  confirmedRefreshTimer = setTimeout(() => {
    confirmedRefreshTimer = null;
    if (S.busy || S.starting || S.demo) return;
    refresh(true, { background: true });   /* 程序自己发起的刷新走后台轮：失败不清列表和勾选（U2/U3） */
  }, 800);
}

function handleCheck(payload) {
  const data = payload || {};
  /* 旧轮迟到：不能覆盖新一轮的检查结论（R11）。先有界暂存，
   * 等 skipped ack 接续回这个 owner 再重放一次。 */
  if (data.request_id && S.round.check && data.request_id !== S.round.check) {
    cacheRoundPayload("check", data.request_id, data);
    return;
  }
  if (data.request_id && !markRoundApplied("check", data.request_id)) return;
  if (data.request_id && data.request_id === S.round.check) {
    clearTimeout(S.round.checkTimer);
  }
  /* 真实校验回来了：解除「检查中」，记下四态结论（valid/none/expired/unknown） */
  S.login.checking = false;
  S.login.result = data.result || null;
  /* FB4：组件结论按刷新轮次处理——本轮 check 报组件故障立即挂横幅并计入
   * 故障累计（另一分支成功/普通 unknown 不得撤）；本轮 check 无故障只收口
   * 自己的分支，撤横幅必须等本轮两分支都完成（两到达顺序语义一致） */
  const componentError = noteRoundError(data.runtime_error);
  if (componentError || S.runtime.checkPending) updateRefreshBranchState("check");
  if (data.demo) S.demo = true;
  /* demo 的 session_present 是 null（没有真实会话）：不能 !! 成 false，
   * 否则会走「首次未登录」板面，把演示样例全遮住（C07） */
  setLogin(data.hours_left, !!data.ok, loginPresent(data, !!data.demo), data);
  if (data.result === "valid" && firstNotice("check", data.request_id, "valid")) {
    addLog("[OK] 已复用本机登录态，学校接口校验通过");
  }
  /* 时钟只认结构化载荷：没有结论就落 unknown，绝不从文本猜「慢几秒」（R08） */
  applyClock(data.clock);
  /* 静默恢复中（recovering）不刷失败日志：登录失效这件事已由「自动登录中」表达，
   * 用户不需要看到一条他没法处理的错误。静默失败、转人工后照常记。 */
  if (!data.ok && !data.recovering && firstNotice("check", data.request_id, "fail")) {
    const reason = String(data.reason || data.text || "登录状态检查没通过");
    addLog(reason.startsWith("[X]") ? reason : "[X] " + reason);
  }
  paintBanners();     /* 组件横幅随 check 结论出现/撤销 */
  paintChecks();
  /* 同一轮校验结论统一收口：胶囊、时钟、大屏、路线、列表空态与各倒计时
   * 一起刷新，不留「胶囊更新了、倒计时还是旧的」混合态（上面的 request_id
   * 代次校验已保证只有本轮结果能走到这里）。 */
  syncLoginDependentView();
  clearStaleLoginResult(data.result);
  maybeStartTour();   /* 登录确认有效后，等着的首次引导看看能不能开始 */
  /* 重新登录成功也会走这条 check 事件：顶栏换了，右侧「电脑续登录」卡片还是旧
   * 记录（最近一次登录/账号状态）。顺手让手机面板重取一次自己的快照，
   * 失败就静默——卡片陈旧不该影响登录结论本身。 */
  if (window.PhonePanel && typeof window.PhonePanel.refresh === "function") {
    try { window.PhonePanel.refresh(); } catch (error) { /* 面板刷新失败不干扰 check */ }
  }

}

function applyActivities(payload, quiet) {
  const res = payload || {};  /* 旧轮的迟到列表不得覆盖新一轮（无 ID 的旧载荷放行）。确属本 UI 旧轮的
   * 终态先暂存：skipped ack 接续回原 owner 后还要重放。 */
  if (res.request_id && S.round.list && res.request_id !== S.round.list) {
    cacheRoundPayload("list", res.request_id, res);
    return;
  }
  if (res.request_id && !markRoundApplied("list", res.request_id)) return;
  if (res.request_id && res.request_id === S.round.list) {
    clearTimeout(S.round.listTimer);
  }
  if (!res.ok) {
    if (S.round.background) {
      /* 后台轮失败：用户正在看的列表、勾选、筛选一概不动，不挂横幅、不切错误空态、不写失败日志；
       * 只累计次数，连续 3 次才在运行记录里说一句（noteBackgroundListFailed） */
      noteBackgroundListFailed();
      settleRefreshBranch("list");
      return;
    }
    S.items = [];
    S.byId = new Map();
    S.selected.clear();
    syncResultSelection();   /* 列表失败清掉选择不是用户改勾选，不关结果页 */
    S.listState = "error";
    /* FB4：先消费后端的 runtime_error 再渲染——check 成功而 list 起不来时
     * 组件横幅不能缺席；失败原话留给列表空态做唯一完整说明，不再生成
     * 同义结果框，也不靠清空 result 去藏重复——真实业务结果原样保留 */
    if (noteRoundError(res.runtime_error)) {
      paintBanners();
      updateControls();
    }
    S.listError = res.text || "";
    noteListFailed(S.listError);
    render();
    settleRefreshBranch("list");
    return;
  }
  S.listError = "";
  S.items = (res.items || []).map(normalize);
  applyConfirmedToItems();
  S.byId = new Map(S.items.map((item) => [String(item.id), item]));
  Array.from(S.selected).forEach((id) => { if (!S.byId.has(String(id))) S.selected.delete(id); });
  syncResultSelection();   /* 列表里没了的场次自动移出，不关结果页 */
  S.listState = "ready";
  S.listAtMono = _monoMs();   /* 时刻表上方的「N 分钟前更新」从这一刻算 */
  /* 任何一次列表成功（手动或后台）都让后台失败计数清零，并记下这份列表的北京时间 HH:MM，
   * 供「连续 3 次没成功」那句说清列表还是几点的 */
  autoRefreshState.fails = 0;
  const loadedAt = businessNowMs();
  autoRefreshState.okLabel = loadedAt === null ? "" : hm(loadedAt);
  render();
  maybeStartTour();   /* 列表到了：等着的首次引导看看能不能开始 */
  settleRefreshBranch("list");
}

/* ================================================================ 后台自动刷新
 * 活动列表每 10 分钟自动刷新一次，等于替用户点一次顶栏「刷新」，但不能让画面闪
 * （计划 20261112-auto-list-refresh）。
 * 做法：一个 30 秒的 setInterval 只负责「看条件」，条件满足才发一轮 refresh(true, {background:true})；
 * 不用 10 分钟的长定时器，是因为窗口隐藏、断网、临近开放这些状态随时在变，每 30 秒重新判断才跟得上。 */
const AUTO_REFRESH_INTERVAL_MS = 600000;   /* 距上一次列表刷新满 10 分钟才刷 */
const AUTO_REFRESH_CHECK_MS = 30000;       /* 每 30 秒看一眼条件 */
const AUTO_REFRESH_GUARD_S = 300;          /* 计划场次离开放不到 5 分钟，不碰学校接口 */
const AUTO_REFRESH_NOTE_AFTER = 3;         /* 连续 3 次后台失败才写一条运行记录 */
/* attemptMono：上一次刷新（手动或后台，成功与否）发出的单调时刻；
 * fails：连续后台失败次数；okLabel：最近一次列表成功的北京时间 HH:MM */
const autoRefreshState = { attemptMono: 0, fails: 0, okLabel: "" };
let autoRefreshTimer = null;

/* 本轮 check / list 还在不在等结果。前台轮看可见状态（检查中 / loading）；
 * 后台轮刻意不碰这两个可见状态，改看内部的 pending 标志，否则兜底计时器永远等不到条件。 */
function checkRoundOpen() {
  return S.round.background ? !!S.runtime.checkPending : !!S.login.checking;
}

function listRoundOpen() {
  return S.round.background ? !!S.runtime.listPending : S.listState === "loading";
}

/* 后台列表轮没成功（回包失败 / 桥接异常 / 入队被拒 / 130 秒无回应）统一在这里记数：
 * 只在第 3 次写一条运行记录，之后继续失败也不刷屏；任何一次列表成功会把计数清零。 */
function noteBackgroundListFailed() {
  autoRefreshState.fails += 1;
  if (autoRefreshState.fails !== AUTO_REFRESH_NOTE_AFTER) return;
  const when = autoRefreshState.okLabel ? "列表还是 " + autoRefreshState.okLabel + " 的" : "列表还是上次的";
  addLogFresh("活动列表自动刷新连续 " + AUTO_REFRESH_NOTE_AFTER + " 次没成功，" + when + "；可以点「刷新」重试");
}

/* 计划里有场次不适合此刻打扰学校：还没终态的场次，离开放不到 5 分钟，或已过开放时刻。
 * 临近和刚过开放时刻正是报名链路最忙的时候，列表刷新既不急也不该和它抢网络与登录态。 */
function planTaskBlocksAutoRefresh() {
  if (!S.plan || !S.plan.tasks || !S.plan.tasks.size) return false;
  /* 计划已经有终态，worker 都收了，残留的任务行不再算「还在跑」 */
  if (PLAN_TERMINAL.indexOf(String(S.plan.status)) >= 0) return false;
  const now = bnowS();   /* 业务钟，不读本机墙钟 */
  let blocked = false;
  S.plan.tasks.forEach((task) => {
    if (RUNNING_STATUSES.indexOf(String(task && task.status)) < 0) return;   /* 已有终态的场次不拦 */
    const open = toTs(task.sign_start);
    /* 时钟不可用或开放时间读不出来：判断不了离开放多久，宁可这一拍不刷 */
    if (now === null || open === null || open - now < AUTO_REFRESH_GUARD_S) blocked = true;
  });
  return blocked;
}

/* 这一拍该不该后台刷新（不含窗口是否可见，那一项要问后端，见 autoRefreshTick）。
 * 任一跳过条件成立就返回 false，下一拍（30 秒后）再看。 */
function autoRefreshDue() {
  if (S.demo) return false;                    /* 演示模式没有真实学校请求 */
  if (!hasBridge()) return false;              /* 没连上本机程序，refresh 也发不出去 */
  if (termsLocked()) return false;             /* 条款未同意：学校动作一律不发 */
  if (!S.online) return false;                 /* 已知断网：结果只会是失败 */
  if (S.login.result !== "valid") return false;   /* 登录结论不是 valid：该由登录流程处理，不是列表刷新 */
  if (S.login.loginPending) return false;      /* 登录窗口开着，别和它抢 */
  /* 刷新按钮当前不可用 = 手动刷新也点不了。这里复用 plan-panel.js updateControls 里同一条规则
   * （加载中、条款门、取消报名中），并直接读按钮本身，那条规则以后改了这里自动跟着走。
   * 注意计划运行中按钮仍可用，所以计划运行不在这里拦，由下面按场次时间判断。 */
  if (S.listState === "loading" || S.cancel.busyId) return false;
  if ($("#btn-refresh").disabled) return false;
  if (S.starting) return false;                /* 开始请求正在提交 */
  /* 正在检查登录或正在拉列表（前台轮看可见状态，后台轮看内部 pending 标志） */
  if (S.login.checking) return false;
  if (S.round.background && (S.runtime.checkPending || S.runtime.listPending)) return false;
  /* 满 10 分钟：以上一次列表成功与上一次刷新尝试中较晚者为准；从没锚定过就不刷 */
  const last = Math.max(Number(S.listAtMono) || 0, autoRefreshState.attemptMono);
  if (!last || _monoMs() - last < AUTO_REFRESH_INTERVAL_MS) return false;
  if (planTaskBlocksAutoRefresh()) return false;
  return true;
}

/* 每 30 秒一拍（以及窗口从不可见变可见时）：条件满足就发一轮后台刷新，返回是否发了。
 * 窗口不可见时不刷新，恢复可见后若已满 10 分钟，下一拍（或可见事件里的这一拍）立即补刷。
 * 可见性有两个来源：document.hidden，以及后端的 _window_hidden（pywebview 隐藏窗口时
 * WebView2 是否把 document.hidden 置真无法离线验证，所以两个都问）。 */
function autoRefreshTick() {
  if (!autoRefreshDue()) return Promise.resolve(false);
  if (document.hidden) return Promise.resolve(false);
  const go = (hiddenByBackend) => {
    if (hiddenByBackend) return false;
    /* 等后端回答的这一小会儿，状态可能变了（用户点了刷新、窗口又被隐藏）：再判一次 */
    if (document.hidden || !autoRefreshDue()) return false;
    autoRefreshState.attemptMono = _monoMs();   /* 先记下尝试时刻：同一刻不会被第二个 tick 连发 */
    refresh(true, { background: true });
    return true;
  };
  /* 老后端没有 window_visibility：问不到就当可见，只看 document.hidden */
  return api("window_visibility").then((res) => go(!!(res && res.hidden)), () => go(false));
}

function startAutoRefresh() {
  if (autoRefreshTimer !== null) return;   /* 只起一个 */
  /* 开机后第一次刷新从此刻算起；启动时的 refresh(true) 也会再记一次 */
  autoRefreshState.attemptMono = autoRefreshState.attemptMono || _monoMs();
  autoRefreshTimer = setInterval(() => { autoRefreshTick().catch(() => {}); }, AUTO_REFRESH_CHECK_MS);
}
