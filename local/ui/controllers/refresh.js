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

function ingestBootstrapPlan(info) {
  /* 页面重载会丢 plan/task 事件：用 bootstrap 快照恢复任务列表与终态呈现。
   * 只恢复显示，不重新提交；终态走与 plan_done 相同的呈现入口（FR05）。 */
  const plan = info && info.plan;
  if (!plan || !plan.plan_id) return;
  const id = String(plan.plan_id);
  const status = String(plan.status || "running");
  const tasks = plan.tasks || [];
  const gen = notePlanGeneration(plan.plan_generation);   /* 权威快照定归属（P1） */
  if (S.plan.id !== id) {
    S.plan = { id: id, gen: gen, status: status, tasks: new Map(), armedAt: Date.now() / 1000 };
  } else {
    /* 同 plan_id 也要推进：状态可能已从 running 走到终态（FR05） */
    if (gen > (Number(S.plan.gen) || 0)) S.plan.gen = gen;
    S.plan.status = status;
  }
  tasks.forEach((task) => {
    /* 快照携带完整运行时 detail（checkpoint/模式/策略/次数）：重载后
     * 时间线显示真实节点，已提交次数也不归零 */
    const key = String(task.task_id);
    S.plan.tasks.set(key, mergeTask(S.plan.tasks.get(key) || null, task));
  });
  /* PB11：重载前这个计划的「开始了」记录早写过了，恢复时不补写（handlePlan 看 startNoted） */
  S.plan.startNoted = true;
  if (["completed", "failed", "partial", "stopped"].indexOf(status) < 0) {
    /* 运行态：恢复进度与「停止」入口 */
    setBusy(true);
    render();
    return;
  }
  /* 终态：同一入口恢复结果框、卡片次数/原因、LED/边框、停止后动作与选择签名。
   * 不置 busy、不重发 start_plan、不重复写失败日志、不触发自动刷新。 */
  presentPlanDone({ plan_id: id, status: status, summary: plan.summary || {} }, false);
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
function settleRefreshBranch(branch) {
  if (branch === "check") S.runtime.checkPending = false;
  else S.runtime.listPending = false;
  if (S.runtime.checkPending || S.runtime.listPending) return;
  const next = S.runtime.roundError;
  if (S.runtime.error !== next) {
    S.runtime.error = next;
    paintBanners();
    updateControls();
    render();
  }
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
  /* 只要真发出了一轮刷新（手动、登录成功后、取消报名后、后台自己），自动刷新的 10 分钟就从此刻重新数 */
  autoRefreshState.attemptMono = _monoMs();
  /* 记下这一轮是不是后台轮：回包、超时、失败分支都按它决定要不要动界面 */
  S.round.background = background;
  const checkId = newRoundId("check");
  const listId = newRoundId("list");
  /* 每轮各自一个消费代次：这一轮的 ack/catch/终态只能收口这一轮，
   * 旧轮迟到的回调不许把新轮的 pending 提前清掉（FR04）。 */
  const checkGen = bumpRoundGeneration("check");
  const listGen = bumpRoundGeneration("list");
  S.round.check = checkId;
  S.round.list = listId;
  clearTimeout(S.round.checkTimer);
  clearTimeout(S.round.listTimer);
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
  /* 失联兜底：确认入队却丢终态时，不能永远停在「检查中」/骨架（R11） */
  S.round.checkTimer = setTimeout(() => {
    if (S.round.check !== checkId || !checkRoundOpen()) return;
    if (S.round.background) {
      /* 后台轮没回应：登录结论保持上次，不改成「待确认」也不写日志，只把本轮收口 */
      settleRefreshBranch("check");
      return;
    }
    S.login.checking = false;
    S.login.ok = false;
    S.login.result = "unknown";
    syncLoginDependentView();
    addLog("[X] 检查登录状态超过 100 秒没有回应，先按「暂时无法确认」处理；点「刷新」重试。");
    settleRefreshBranch("check");
  }, 100000);
  S.round.listTimer = setTimeout(() => {
    if (S.round.list !== listId || !listRoundOpen()) return;
    if (S.round.background) {
      /* 后台轮没回应：按一次后台失败算，原列表原勾选不动 */
      noteBackgroundListFailed();
      settleRefreshBranch("list");
      return;
    }
    S.listState = "error";
    S.listError = "活动列表超过 130 秒没有回应";
    noteListFailed(S.listError);
    render();
    settleRefreshBranch("list");
  }, 130000);
  api("check", checkId).then((res) => {
    if (S.round.gen.check !== checkGen) return;   // 旧轮 ack：不碰新一轮
    settleSynchronous(res, "check");
  }).catch((err) => {
    /* 桥接/脚本异常也必须离开「检查中」：落 unknown 结论并刷新胶囊与按钮，
     * 不能把界面永远停在「正在检查登录状态」；下一步是点「刷新」再试。
     * ok 必须同时置 false：旧的 valid/warn 状态不清理的话，
     * paintLogin 的 unknown 分支（要求 ok===false）接不住，顶栏会继续显示「登录有效」。 */
    if (S.round.gen.check !== checkGen || S.round.check !== checkId) return;
    clearTimeout(S.round.checkTimer);
    if (S.round.background) {
      settleRefreshBranch("check");   /* 后台轮桥接异常：登录结论保持上次，静默收口 */
      return;
    }
    S.login.checking = false;
    S.login.ok = false;
    S.login.result = "unknown";
    /* 结论变了：胶囊、时钟、空态与所有倒计时一起收口，不能只改胶囊 */
    syncLoginDependentView();
    addLog("[X] 检查登录状态失败：" + msg(err) + "；点「刷新」再试一次");
    settleRefreshBranch("check");
  });
  api("list_activities", listId).then((res) => {
    if (S.round.gen.list !== listGen) return;     // 旧轮 ack：不碰新一轮
    settleSynchronous(res, "list");
  }).catch((err) => {
    /* 桥接/脚本异常同 Worker 失败一个口径：完整说明归列表空态，
     * 不再为同一列表错误额外弹结果框 */
    if (S.round.gen.list !== listGen || S.round.list !== listId) return;
    clearTimeout(S.round.listTimer);
    if (S.round.background) {
      noteBackgroundListFailed();     /* 后台轮桥接异常：保留原列表，只累计失败次数 */
      settleRefreshBranch("list");
      return;
    }
    S.listState = "error";
    S.listError = msg(err);
    noteListFailed(S.listError);
    render();
    settleRefreshBranch("list");
  });
}

/* 同步拒绝（如正在关闭 / 正在检查）没有终态事件：本轮分支必须当场收口，
 * 不让界面挂在「检查中」等一个永远不会来的事件（R11）。 */
function settleSynchronous(res, branch) {
  if (!res) return;
  /* 去重命中在途操作（C06）：接续原请求 ID 并重绑本轮超时；
   * 原操作若已经结束，后端会把终态一起带回来，直接落地，不干等旧事件。 */
  if (res.skipped) {
    const id = String(res.request_id || "");
    if (branch === "check") {
      if (id) S.round.check = id;
      clearTimeout(S.round.checkTimer);
      S.round.checkTimer = setTimeout(() => {
        if (S.round.check !== id || !checkRoundOpen()) return;
        if (S.round.background) { settleRefreshBranch("check"); return; }
        S.login.checking = false;
        S.login.ok = false;
        S.login.result = "unknown";
        syncLoginDependentView();
        settleRefreshBranch("check");
      }, 100000);
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
    if (id) S.round.list = id;
    clearTimeout(S.round.listTimer);
    S.round.listTimer = setTimeout(() => {
      if (S.round.list !== id || !listRoundOpen()) return;
      if (S.round.background) {
        noteBackgroundListFailed();
        settleRefreshBranch("list");
        return;
      }
      S.listState = "error";
      S.listError = "活动列表超过 130 秒没有回应";
      noteListFailed(S.listError);
      render();
      settleRefreshBranch("list");
    }, 130000);
    if (res.result) {
      applyActivities(res.result, false);
      return;
    }
    const cachedList = takeRoundPayload("list", id);
    if (cachedList) applyActivities(cachedList, false);
    return;
  }
  if (res.ok !== false) return;
  /* 后端条款回绝（terms_required）：按钮可能被脚本、快捷键或旧界面绕过，
   * 这条路径必须把界面拉回条款门禁，而不是只把报错丢进结果框。 */
  if (res.error === "terms_required") {
    if (S.round.background) {
      /* 后台轮被条款拦下：不改列表和登录结论，只让界面跟上后端的条款状态 */
      clearTimeout(branch === "check" ? S.round.checkTimer : S.round.listTimer);
      settleRefreshBranch(branch);
      noteTermsRequired(res);
      return;
    }
    if (branch === "check") {
      clearTimeout(S.round.checkTimer);
      S.login.checking = false;
      S.login.result = "unknown";
      S.login.ok = false;
      syncLoginDependentView();
      settleRefreshBranch("check");
    } else {
      clearTimeout(S.round.listTimer);
      S.listState = "error";
      S.listError = (res && res.text) || "活动列表没能开始加载";
      render();
      settleRefreshBranch("list");
    }
    noteTermsRequired(res);
    return;
  }
  if (branch === "check") {
    clearTimeout(S.round.checkTimer);
    if (S.round.background) {
      settleRefreshBranch("check");   /* 后台轮没能开始：不改登录结论、不写日志 */
      return;
    }
    S.login.checking = false;
    S.login.result = "unknown";
    S.login.ok = false;
    syncLoginDependentView();
    addLog("[X] " + ((res && res.text) || "这次检查没能开始") + "；点「刷新」重试。");
    settleRefreshBranch("check");
    return;
  }
  clearTimeout(S.round.listTimer);
  if (S.round.background) {
    noteBackgroundListFailed();       /* 后台轮没能开始：保留原列表，只累计失败次数 */
    settleRefreshBranch("list");
    return;
  }
  S.listState = "error";
  S.listError = (res && res.text) || "活动列表没能开始加载";
  noteListFailed(S.listError);
  render();
  settleRefreshBranch("list");
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

/* 组件错误 → 一句话标题 + 恢复动作说明（后端 runtime_error 的唯一展示口径） */
const RUNTIME_ERRORS = {
  worker_missing: { title: "程序组件缺失", hint: "无法找到所需程序组件。请重新下载完整版本，再选择「重新检查」。" },
  worker_permission: { title: "程序组件无法读取", hint: "组件文件在，但被系统拦住或没有权限（刚下载的文件常见）。右键程序 → 属性 → 勾「解除锁定」，或重新解压后再点「重新检查」。" },
  spawn_failed: { title: "程序组件启动失败", hint: "组件在但没能启动。点「重新检查」再试一次；反复出现请重新下载完整版本。" },
};

function runtimeErrorCopy() {
  return RUNTIME_ERRORS[S.runtime.error] || RUNTIME_ERRORS.spawn_failed;
}

/* 报名结果回写（真实证据 P0-1）：success/already_signed 是已确认事实，
 * 立即映射到活动列表——计数、分组、行状态、复选框与冲突基线同步更新。
 * unconfirmed/failed/canceled 不写 signed，避免把未知猜成成功。 */
const SIGNED_SYNC_MS = 120000;
let confirmedRefreshTimer = null;

function planConfirmedAt() {
  const ms = businessNowMs();
  return ms == null ? Date.now() : ms;   // 仅用于界面同步窗口；门禁仍由后端裁决
}

function noteSignedTasks(tasks) {
  let changed = false;
  (tasks || []).forEach((task) => {
    const status = String((task && task.status) || "");
    if (status !== "success" && status !== "already_signed") return;
    const id = String((task && task.activity_id) || "");
    if (!id) return;
    const atMs = planConfirmedAt();
    S.confirmed.set(id, {
      source: status === "success" ? "plan_success" : "plan_already_signed",
      atMs: atMs,
    });
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
  syncResultSelection();
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
    refresh(true);
  }, 800);
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
