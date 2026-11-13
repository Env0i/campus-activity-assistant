/* 任务展示纯模型：状态归类、阶段/文案/细节投影（无 DOM）。 */
const RUNNING_STATUSES = ["queued", "waiting", "submitting"];

/* 任务 → 可显示项：列表项在就用真列表项；不在（被筛掉、刷新掉了、快照
 * 先到）就用任务自带字段现构。缺字段显示未知，绝不回退到另一场活动。 */
function taskDisplayItem(task) {
  const found = findItem(task && task.activity_id);
  if (found) return found;
  if (!task) return null;
  return {
    id: String(task.activity_id || task.task_id || ""),
    name: String(task.name || "这一场活动"),
    sign_start: task.sign_start || "",
    sign_end: task.sign_end || "",
    act_start: task.act_start || "",
    act_end: task.act_end || "",
    place: task.place || "",
    signed: false,
    fromTask: true,
  };
}

/* 工作状态 → 显示阶段（纯函数，只读真实时间与提交证据）。
 * 后端在拉起 runner **之前**就把任务置 submitting，这也包含预报名开放前
 * lead_s 秒打开活动页的预热（signup_plan.py 的 _run_one / _prepare_ts），
 * 所以原始状态不能直接当「正在提交」说话：
 *   preopen   还没到原定开放（哪怕 worker 已经在开页）
 *   preparing 已开放，但还没有一次真正发起的提交
 *   retrying  有真实提交且仍非终态（attempts 是唯一「已提交」证据）
 *   terminal  终态，不参与运行目标
 * 只影响展示，不写回 task.status、不改协调器与取消条件。 */
function taskDisplayPhase(task, now) {
  if (!task) return "terminal";
  const status = String(task.status || "");
  if (RUNNING_STATUSES.indexOf(status) < 0) return "terminal";
  const attempts = Number(task.attempts);
  if (Number.isFinite(attempts) && attempts > 0) return "retrying";
  const at = Number.isFinite(now) ? now : bnowS();
  const open = toTs(task.sign_start);
  const mode = String(task.signup_mode || "");
  /* 立即模式本来就不等开放：时间不可读时也不能说成「等待开放」 */
  if (at == null) return mode === "instant_signup" ? "preparing" : "preopen";
  /* 开放时间未知时只能「等」：不能因为算不出时间就说已经开放 */
  if (open === null) return mode === "instant_signup" ? "preparing" : "preopen";
  if (open > at) return "preopen";
  return "preparing";
}

/* 任务卡的阶段标签：raw「等待开放」在已开放时是假话，按显示阶段改写 */
function taskDisplayLabel(task) {
  const phase = taskDisplayPhase(task);
  if (phase === "preopen") return "等待开放";
  if (phase === "preparing") return "准备报名";
  if (phase === "retrying") return "提交中";
  const state = String(task && task.status || "queued");
  if (state === "failed") {
    /* 刷新核对确认过已报名：照原型 card.verify 改成「报名成功」（先判它，否则会被「待核对」截走） */
    if (typeof verifiedSigned === "function" && verifiedSigned(task)) return "报名成功";
    /* 电脑睡眠盖住了开放时刻、一次都没提交（LS22 / PB15）：原型动词「错过了」 */
    if (typeof taskMissedBySleep === "function" && taskMissedBySleep(task)) return taskLabel("missed");
    /* 结果没确认 / 登录状态未知都不是「失败」：标签必须留出核对空间（「未提交」是代码独有） */
    if (task.stop_reason === "unconfirmed") return "待核对";
    if (task.stop_reason === "auth_unavailable") return "未提交";
    /* 名额已满是学校给的结束结论，不是工具失败（架构方案 3.3） */
    if (task.stop_reason === "full") return "名额已满";
  }
  return taskLabel(state);
}

/* 任务卡的模式前缀（混合计划每场标自己的模式）：taskHtml 与 tick 共用一份 */
function taskModePrefix(task) {
  const state = String(task && task.status || "queued");
  const mode = String(task && (task.signup_mode || modeOf(task)));
  return RUNNING_STATUSES.indexOf(state) >= 0 && modeText(mode) ? modeText(mode) + " · " : "";
}

/* 预报名场次是否已准备好提交：和路线图「准备好提交」同一个信号（改用页面点击时看活动页打开）。
 * 照原型 card 的 prepped = t.prep && s.now >= t.prep：记下的时刻还没到（时钟对不上）就不算准备好；
 * 读不到可信的现在时只看有没有这个 checkpoint。 */
function taskPrepared(task, now) {
  const clickPath = String(task && task.path || "") === "click";
  const page = Number(task && task.page_opened_at) || 0;
  const watch = Number(task && task.watch_started_at) || 0;
  const at = clickPath ? page : (watch > 0 ? watch : page);
  if (!(at > 0)) return false;
  const current = Number.isFinite(now) ? now : bnowS();
  return current == null || at <= current + 1;
}

/* 任务卡的说明行（原型 card 的 waiting / submitting 支）：与标题/LED 同一解释，tick 每秒复用同一份 */
function taskDisplayDetail(task, now) {
  const phase = taskDisplayPhase(task, now);
  if (phase !== "terminal" && String(task && task.login_wait || "") === "waiting") {
    /* 代码独有：报名进程确认登录失效、在等电脑自动登录（架构方案 4.3），换上新登录态后接着提交 */
    return "电脑正在自动登录，换上新登录态后接着提交";
  }
  if (phase === "preopen") {
    const open = toTs(task && task.sign_start);
    if (open === null) return "提前准备，开放时间待公布";
    return taskPrepared(task, now) ? "已准备好，" + hmsDay(open) + " 开放时提交"
      : "提前准备，等到 " + hmsDay(open) + " 开放";
  }
  if (phase === "preparing") return "已开放，正在准备提交";
  if (phase === "retrying") return submittingDetail(task);
  return "";
}

/* 运行目标的唯一只读模型（标题、路线、LED、批次数共用一份）：
 * 只读 S.plan.tasks 快照，不读也不改 S.selected——原勾选继续服务草稿与重开。
 * phase: idle / preparing（还没任务）/ waiting（等开放）/ arming（已开放未提交）
 *        / submitting（已有真实提交）/ settling（全终态、plan_done 未到）。
 * 目标优先级：真实重试 > 已开放准备 > 未来预热；同阶段取更早的开放时刻，
 * 并列时保持快照顺序。未运行时返回 idle，调用方回落到用户选择的预览态。 */
function executionView() {
  const empty = { phase: "idle", display: "idle", task: null, item: null,
                  count: 0, openAt: null, retryUntil: null };
  if (!S.busy || !S.plan.id) return empty;
  const now = bnowS();
  const tasks = Array.from(S.plan.tasks.values());
  const running = tasks.filter((task) => RUNNING_STATUSES.indexOf(String(task.status)) >= 0);
  if (!running.length) {
    /* 还没有任务 = 准备中；任务都结束但 plan_done 未到 = 汇总中。
     * 两种情况都不许提前显示计划成功。 */
    return Object.assign({}, empty, { phase: tasks.length ? "settling" : "preparing" });
  }
  /* 快照顺序做初值：并列时不会被排序打乱 */
  const stages = running.map((task) => ({
    task: task,
    display: taskDisplayPhase(task, now),
    at: toTs(task.sign_start),
  }));
  const earliest = (list) => {
    let best = list[0];
    let bestAt = best.at === null ? Infinity : best.at;
    for (let i = 1; i < list.length; i += 1) {
      const at = list[i].at === null ? Infinity : list[i].at;
      if (at < bestAt) { best = list[i]; bestAt = at; }
    }
    return best;
  };
  const batchCount = (signStart) => running.filter(
    (task) => String(task.sign_start || "") === String(signStart || "")).length;

  const retrying = stages.filter((stage) => stage.display === "retrying");
  if (retrying.length) {
    /* 真正在提交：取真实重试截止最早的一场；未知截止排最后 */
    let best = retrying[0];
    let bestAt = effectiveRetryDeadline(best.task, now);
    for (let i = 1; i < retrying.length; i += 1) {
      const at = effectiveRetryDeadline(retrying[i].task, now);
      if (at !== null && (bestAt === null || at < bestAt)) { best = retrying[i]; bestAt = at; }
    }
    return { phase: "submitting", display: "retrying", task: best.task,
             item: taskDisplayItem(best.task), count: retrying.length,
             openAt: null, retryUntil: bestAt };
  }
  const arming = stages.filter((stage) => stage.display === "preparing");
  if (arming.length) {
    /* 已开放但还没发起提交：说「准备报名」，不说「还在等开放」 */
    const best = earliest(arming);
    return { phase: "arming", display: "preparing", task: best.task,
             item: taskDisplayItem(best.task), count: batchCount(best.task.sign_start),
             openAt: best.at, retryUntil: null };
  }
  const preopen = stages.filter((stage) => stage.display === "preopen");
  const best = earliest(preopen);
  return { phase: "waiting", display: "preopen", task: best.task,
           item: taskDisplayItem(best.task), count: batchCount(best.task.sign_start),
           openAt: best.at, retryUntil: null };
}

/* 从 views/plan-panel.js 搬来：任务卡用的纯投影，只读 S、不写 S、不碰 DOM。 */

/* 刷新核对确认过的待核对场次：结束时没拿到结论，事后学校列表显示已报名 */
function verifiedSigned(task) {
  if (!task || String(task.stop_reason || "") !== "unconfirmed") return false;
  const item = findItem(task.activity_id);
  return !!(item && item.signed);
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
