/* 计划事件用例：plan/task/plan_done 收口、终态呈现与重启停止计划。 */
function presentPlanDone(payload, autoRefresh) {
  const data = payload || {};
  /* 终态载荷也带接纳代次：并入会话记录，旧代次事件此后不得再改写（P1） */
  const doneGen = notePlanGeneration(data.plan_generation);
  if (doneGen > (Number(S.plan.gen) || 0)) S.plan.gen = doneGen;
  S.plan.id = String(data.plan_id || S.plan.id || "");
  S.plan.status = String(data.status || "failed");
  /* 计划收尾：解除「正在停止」并解锁 busy（canceled/终态都已落定） */
  S.stopping = false;
  /* 记下终态时的选择集合（旧口径，保留给 QA 与诊断读）；结果页进出改由结果页标记决定 */
  S.plan.doneSelection = selectionSignature();
  setBusy(false);
  /* 已确认成功的场次立即回写列表（计数/分组/门禁/冲突基线），
   * 再安排一次有界刷新去取学校权威列表；刷新失败不撤销成功事实。 */
  const signedChanged = noteSignedTasks(Array.from(S.plan.tasks.values()));
  if (S.editing && S.plan.status === "stopped") {
    /* 修改计划：停下以后把没提交的场次放回选择，等用户改完重新开始（不弹停止结论） */
    S.selected.clear();
    (S.editing.ids || []).forEach((id) => {
      const item = findItem(id);
      if (item && isEligibleForPlan(item)) S.selected.add(String(id));
    });
    /* U9：停止真的成功了才写这一句，场次数就是放回草稿的场次数 */
    addLogFresh(editPausedLine((S.editing.ids || []).length));
    S.plan = { id: null, status: "idle", tasks: new Map() };
    closeResultPage();
  } else {
    /* U1：停止请求发出后计划没以 stopped 结束（自己跑完了、已经终态），修改中到此为止，
     * 不清的话结果页出不来（resultMode 要求没有 editing），计划栏还写「修改中」 */
    S.editing = null;
    /* 计划结束就进结果页（P1）：结论由计划栏的大数字、标题和副行承担（原型 res 段），
     * 不再往 #result 条写结论和「重新选择活动 / 刷新列表」内联动作（P8）。
     * 成功场次已在上面移出选择集合，结果页从这之后的选择开始记。 */
    openResultPage();
  }
  setResult(null);
  render();
  if (signedChanged && autoRefresh !== false) scheduleSignedRefresh();
}

function handlePlanDone(payload) {
  const data = payload || {};
  if (!planEventOwns(data)) return;           // 旧计划的完成事件不得改写当前计划（P1）
  admitPlanEvent(data);
  /* 同计划已定终态：重复终态只补任务详情，不把结论改成另一状态（P1） */
  if (S.plan.id === String(data.plan_id || "")
      && PLAN_TERMINAL.indexOf(S.plan.status) >= 0) {
    /* 重复终态：合并任务详情但不重开结果页。
     * doStopPlan 曾把 S.stopping 置 true，presentPlanDone 不会走到这里，
     * 所以必须在这个早返回分支自己收口停止标记。 */
    S.stopping = false;
    (data.tasks || []).forEach((task) => {
      S.plan.tasks.set(String(task.task_id),
                       mergeTask(S.plan.tasks.get(String(task.task_id)) || null, task));
    });
    render();
    return;
  }
  presentPlanDone(data);
}

/* 停止后一键把原计划里还能报的场次重新选上 */
function restartStoppedPlan() {
  if (S.busy) return;
  S.selected.clear();
  S.plan.tasks.forEach((task) => {
    const item = findItem(task.activity_id);
    /* 重新选择也要过门禁：已截止的场次不能被重新选上 */
    if (item && isEligibleForPlan(item) && ["canceled", "failed"].indexOf(String(task.status)) >= 0) S.selected.add(String(item.id));
  });
  closeResultPage();   /* 重新选择就是离开结果页（state/plan.js） */
  S.selectionNotice = "";
  setResult(null);
  render();
}

/* worker 已经就同一场写过结论时，不再叠一条同义摘要（RC-06）。
 * 只认「同一场名称 + 同一结论关键词」，不同场次的成功互不影响。 */
function loggedConclusion(name, keyword) {
  const target = String(name || "");
  return S.recentLogs.some((line) => line.indexOf(target) >= 0 && line.indexOf(keyword) >= 0);
}

function showTaskResult(task) {
  const name = task.name || "这一场活动";
  /* 计划还在跑时，单场终态只更新任务卡与运行记录：结果框和整屏留给
   * handlePlanDone 的计划级结论（单场成功不得抢写全局成功，UX-05）。 */
  const planLive = !!S.busy;
  if (task.status === "success") {
    if (!loggedConclusion(name, "报名成功")) addLog("[OK] 报名成功：" + name);
    if (!planLive) setResult({ ok: true, title: "报名成功：" + name, text: "建议去活动页确认一眼。" });
  } else if (task.status === "already_signed") {
    if (!loggedConclusion(name, "已经报过")) addLog("[i] 已经报过：" + name);
    if (!planLive) setResult({ ok: "partial", title: "已经报过：" + name, text: "这场保留为已报名，其他场次继续。" });
  } else if (task.status === "canceled") {
    addLog("[i] 已取消：" + name);
    if (!planLive) setResult({ ok: "partial", title: "已取消：" + name, text: "其他场次继续按计划处理。" });
  } else if (task.stop_reason === "unconfirmed") {
    /* 结果未确认：不说没抢到、不画失败叉；只给次数与下一步核对动作 */
    const tried = Math.max(0, Math.floor(Number(task.attempts) || 0));
    addLog("[?] 结果待核对：" + name + " · 已提交 " + tried + " 次，没有确定回应");
    if (!planLive) {
      setResult({ ok: "partial", title: "报名结果待核对：" + name,
                  text: "已提交 " + tried + " 次，但没拿到学校的确定回应。请打开活动页核对是否已报名；本工具已停止自动重发，不会自动开始新计划。",
                  action: { label: "刷新列表", run: () => refresh(false) } });
    }
  } else if (task.stop_reason === "auth_unavailable") {
    /* 网络/接口无法确认 ≠ 登录过期：不跳到「重新登录」 */
    addLog("[X] 登录状态暂时无法确认：" + name + " · 本场没有提交");
    if (!planLive) {
      setResult({ ok: "partial", title: "暂时无法验证登录状态：" + name,
                  text: "本场没有提交。先检查网络或校园网，再点「刷新」重试；不要急着重新登录。",
                  action: { label: "刷新列表", run: () => refresh(false) } });
    }
  } else {
    /* 终态文案 = 归因建议 + 学校原话 + 到达的停止条件（时长/次数/截止） */
    const bits = [grabHint(task.reason), "原话：" + cleanReason(task.reason)];
    const stopNote = stopReasonText(task.stop_reason);
    if (stopNote && task.stop_reason !== "process_error") bits.push(stopNote);
    addLog("[X] 报名未成功：" + name + " · " + cleanReason(task.reason));
    if (!planLive) setResult({ ok: false, title: "报名未成功：" + name, text: bits.join(" ") });
    /* 失败后顺手复查一次登录状态和列表：掉了登录的页面只会看到按钮不出现，
     * 复查能把这个真原因翻到登录胶囊上。只查状态，不改写已出的结论。
     * 计划还在跑也要查——不能因为改成「只更新单场反馈」就把这条副作用丢掉。 */
    if (!S.recheckPending) {
      S.recheckPending = true;
      setTimeout(() => { S.recheckPending = false; refresh(true); }, 400);
    }
  }
}

/* 登录尝试前的完整快照：取消 / 超时 / 窗口关闭 / 失败时整份回滚。
 * 只回滚界面用的登录结论，不动 session.json——这次没登成不等于旧凭证失效。 */
