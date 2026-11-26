/* 列表渲染：render/paintList/行与分组/空态/统计条。 */
/* ---------------------------------------------------------------- 时刻表 */
function paintList() {
  const box = $("#rows");
  const listEl = $("#list");
  S.rowEls = new Map();
  S.rowCancel = new Map();
  const isLoading = S.listState === "loading";
  const hasOld = S.items.length > 0;
  /* 首次空列表加载态一律换成骨架行；D7 有旧列表时保留旧行并顶部加进度条
   * （原型 Main.dc.html:2138）：点刷新后必须马上看得见「在动」，否则请求挂着不回来时用户只会觉得没反应。 */
  listEl.classList.toggle("is-loading", isLoading && !hasOld);
  listEl.classList.toggle("is-refreshing", isLoading && hasOld);
  if (typeof paintRefreshBarAndFail === "function") paintRefreshBarAndFail();
  if (isLoading && !hasOld) {
    box.innerHTML = typeof skeletonHtml === "function" ? skeletonHtml() : "";
    S.rowStates = new Map();
    $("#empty").hidden = true;
    paintCount([]);
    return;
  }
  const rows = filtered();
  paintEmpty(rows);
  paintCount(rows);
  if (!rows.length) {
    box.innerHTML = "";
    S.rowStates = new Map();
    return;
  }
  if (S.filter.sort === "name") {
    box.innerHTML = groupHtml("全部活动", rows) ;
  } else {
    box.innerHTML = groupTimetable(rows);
  }
  S.rowStates = new Map(rows.map((item) => [String(item.id), stateOf(item)]));
  /* 「可取消至」随报名截止消失，不改 stateOf：单记一份让心跳能发现这一刻 */
  rows.forEach((item) => { if (item.signed) S.rowCancel.set(String(item.id), canCancelNow(item)); });
  box.querySelectorAll(".row").forEach((tr) => {
    const id = tr.dataset.id;
    S.rowEls.set(id, {
      row: tr,
      check: tr.querySelector(".row-check"),
      left: tr.querySelector(".c-state .left"),
      ago: tr.querySelector(".c-state .small"),
      state: tr.querySelector(".c-state"),
    });
  });
  const nowChip = box.querySelector("[data-now]");
  if (nowChip) {
    const bnMs = businessNowMs();
    nowChip.textContent = bnMs == null ? "待校准" : hm(bnMs);
  }
  if (typeof paintDescIfOpen === "function") paintDescIfOpen();
}

/* 按天分组的车站时刻表：正在开放 → 「现在」线 → 按天 → 待公布 → 已报名 → 已截止
 * （LS01：后三组的顺序照原型 Main.dc.html 的 order 数组，已报名在已截止前） */
function groupTimetable(rows) {
  const open = [];
  const unknown = [];
  const closed = [];
  const signed = [];
  const days = new Map();
  const now = businessNowMs() || 0;   // 仅兜底分桶键；分类由 stateOf 决定
  rows.forEach((item) => {
    const st = stateOf(item);
    if (st === "open") open.push(item);
    else if (st === "waiting") {
      const key = String(startOfDay(toTs(item.sign_start) * 1000 || now));
      if (!days.has(key)) days.set(key, []);
      days.get(key).push(item);
    }
    else if (st === "unknown" && !signStartKnown(item)) unknown.push(item);
    else if (st === "unknown") {
      /* 开放时间已知、只是本机暂时没有可信现在：保留绝对日期分组，
       * 状态列标「待校准」，不能整体塞进「报名时间待公布」。 */
      const key = String(startOfDay(toTs(item.sign_start) * 1000));
      if (!days.has(key)) days.set(key, []);
      days.get(key).push(item);
    }
    else if (st === "closed") closed.push(item);
    else signed.push(item);
  });
  const byStart = (a, b) => (toTs(a.sign_start) || Infinity) - (toTs(b.sign_start) || Infinity) || String(a.name).localeCompare(String(b.name), "zh");
  let html = "";
  if (open.length) html += groupHtml("正在开放", open.sort(byStart), "open", "现在就能报");
  if (open.length || days.size) html += nowlineHtml();
  Array.from(days.keys()).sort((a, b) => Number(a) - Number(b)).forEach((key) => {
    const dayMs = Number(key);
    html += groupHtml(dayLabel(dayMs), days.get(key).sort(byStart), "day");
  });
  if (unknown.length) html += groupHtml("报名时间待公布", unknown.sort(byStart), "unknown", "公布以后才能到点报名");
  if (signed.length) html += groupHtml("已报名", signed.sort(byStart), "signed");
  /* 组名与旁注照原型 Main.dc.html:1922：已截止的场次只能查看 */
  if (closed.length) html += groupHtml("已截止", closed.sort(byStart), "closed", "只能查看");
  return html;
}

function groupHtml(label, items, kind, note) {
  const byName = S.filter.sort === "name" && !kind;
  return '<section class="gsec" data-g="' + (kind || "") + '"><div class="grp"><b>' + esc(label) + "</b>" +
    (note ? "<span>" + esc(note) + "</span>" : "") + '<span class="count">' + items.length + " 场</span></div>" +
    buildGroupBodyHtml(items, kind || "", byName) + "</section>";
}

function nowlineHtml() {
  const bnMs = businessNowMs();
  return '<div class="nowline" aria-hidden="true"><span class="nowline-chip">现在 <b data-now>' + (bnMs == null ? "待校准" : hm(bnMs)) + "</b></span></div>";
}

function rowHtml(item) {
  return buildCardHtml(item);
}

function clashOf(item, armed) {
  return clashOfItem(item, armed);
}

function stateCellHtml(item, state, leftText, armed) {
  return cardStateHtml(item, state, armed);
}

/* 空列表的登录四态 → 下一步。检查没结束时不许提前宣布有效；
 * 结论缺失或无法判定一律按 unknown 处理——把「还不知道」说成
 * 「登录是有效的」比说「暂时无法确认」更伤人。 */
function loginEmptyState() {
  if (S.login.checking) return "checking";
  if (S.login.present === false || S.login.result === "none") return "none";
  if (S.login.result === "expired") return "expired";
  if (S.login.result === "valid") return "valid";
  return "unknown";
}

/* 登录结论变化会影响空态文案（checking → valid/expired/unknown）。
 * 有列表数据时空态走筛选/错误分支，与登录无关；骨架在场时也不插手。 */
function refreshLoginEmptyState() {
  if (S.items.length) return;
  if (S.listState === "loading") return;
  paintEmpty([]);
}

function paintEmpty(rows) {
  const empty = $("#empty");
  const title = $("#empty-title");
  const text = $("#empty-text");
  const action = $("#empty-action");
  if (rows.length) {
    empty.hidden = true;
    return;
  }
  empty.hidden = false;
  action.hidden = false;
  /* 动作意图每次渲染都写清楚：handler 只认这个键，
   * 不按 items.length 猜（有缓存时的失败重试会被猜成清筛选）。 */
  action.dataset.action = "refresh";
  if (S.runtime.error) {
    /* 缺组件不许显示成「登录后查看活动」：重新登录解决不了缺组件。
     * 完整原因与恢复动作只在顶部横幅——这里只放未加载占位，
     * 不复读长说明，也不重复恢复按钮。 */
    /* LS16：标题照原型 Main.dc.html 的 broken 空态「活动列表没加载」；正文按三种错误码的横幅保留原有说法 */
    title.textContent = "活动列表没加载";
    text.textContent = "组件有问题，处理办法看页面顶部的提示。";
    action.hidden = true;
    return;
  }
  if (S.listState === "error") {
    /* 普通列表失败：完整原因与「刷新」唯一归这里（用真实失败原话归因；按钮名照原型 LS12） */
    const copy = listErrorCopy(S.listError || "");
    title.textContent = copy.title;
    text.textContent = copy.text;
    action.textContent = "刷新";
    return;
  }
  if (S.items.length) {
    /* 有数据但都被筛掉：只有这一种空态给「清除筛选」 */
    title.textContent = "没有符合筛选的活动";
    text.textContent = "一共 " + S.items.length + " 场。换个关键词，或者清除筛选。";
    action.textContent = "清除筛选";
    action.dataset.action = "clear-filters";
    return;
  }
  if (S.listState !== "ready") {
    /* 还没成功加载过一次（idle，或首屏加载中）：未知占位，
     * 不能趁这时候说「学校没有活动」，也不能先让用户去登录 */
    title.textContent = "还没有加载活动列表";
    /* 条款没同意时「刷新」是禁用的，还写「点刷新」就是把人指进死路。 */
    /* 副行防拆词（方案 B，各分支统一）：受保护词（书名号词与「可以」）所在的
     * 短语整段用 nowrap 包住。只包词本身的 2 字 span 能防拆词（f541ba4），
     * 但 kinsoku 会把「点「刷新」」整簇压到次行成标点开头孤行（f538cc9 实测），
     * 所以 span 从短语起点包到子句尾/句尾；各 span ≤252px < max-width 330px，
     * 不会撑破。textContent 一字不变（span 不产生文本），契约断言仍按原文比对。 */
    text.innerHTML = termsLocked()
      ? '同意使用条款后才会加载活动列表；<span style="white-space:nowrap">点顶部的「查看条款」可以先看内容。</span>'
      : '<span style="white-space:nowrap">点「刷新」加载一次；</span>需要登录时，顶部会提示下一步。';
    if (termsLocked()) {
      /* 按钮也得换：光改文案、按钮仍指向被禁用的刷新，等于换个位置把人指进死路。 */
      action.textContent = "查看条款";
      action.dataset.action = "terms-open";
    } else {
      action.textContent = "刷新";
      action.dataset.action = "refresh";
    }
    return;
  }
  /* 以下都是「学校成功返回了 0 场」：按登录状态给各自下一步 */
  const login = loginEmptyState();
  if (login === "checking") {
    /* 校验还没回来：不提前说有效，也不逼用户重新登录 */
    title.textContent = "正在检查登录状态";
    text.innerHTML = '正在核对已保存的登录，稍等一下；<span style="white-space:nowrap">这段时间先不用重新登录。</span>';
    action.textContent = "刷新";
    return;
  }
  if (login === "none") {
    title.textContent = "登录后查看活动";
    text.innerHTML = '<span style="white-space:nowrap">打开顶栏的登录状态，点「登录」，</span>在打开的浏览器中完成登录，<span style="white-space:nowrap">然后点「刷新」。</span>';
    action.textContent = "刷新";
    return;
  }
  if (login === "expired") {
    title.textContent = "登录状态失效，先重新登录";
    text.innerHTML = '<span style="white-space:nowrap">打开顶栏的登录状态，点「重新登录」，完成后点「刷新」。</span>';
    action.textContent = "刷新";
    return;
  }
  if (login === "unknown") {
    title.textContent = "暂时无法确认登录状态";
    text.innerHTML = '<span style="white-space:nowrap">请检查网络后点「刷新」。</span>';
    action.textContent = "刷新";
    return;
  }
  title.textContent = "学校当前没有活动";
  text.textContent = "这不是登录问题，学校发布新活动后会出现在这里。";
  /* 按钮照原型 Main.dc.html:2096 就叫「刷新」；dataset.action 仍是 refresh，分派逻辑不动 */
  action.textContent = "刷新";
}

function paintCount(rows) {
  /* 列表还没加载过时不显示场数和新鲜度：不能把「还没拿到」说成「0 场」；
   * 手里已有列表时刷新由 #fresh 写「正在刷新…」，#count 保持 N / M 场，不并排重复。 */
  const known = S.listState === "ready" || S.items.length > 0;
  $("#count").textContent = known ? rows.length + " / " + S.items.length + " 场"
    : (S.listState === "loading" ? "正在刷新…" : "");
  paintFreshness();
}

/* 列表新鲜度：刚刚更新 / N 分钟前更新，超过 10 分钟转警告色（时刻来自本机单调钟，只算间隔） */
function paintFreshness() {
  const fresh = $("#fresh");
  if (!fresh) return;
  const known = S.listState === "ready" || S.items.length > 0;
  if (S.listState === "loading") {
    fresh.hidden = !known;
    fresh.textContent = known ? "正在刷新…" : "";
    fresh.className = known ? "fresh busy" : "fresh";
    fresh.dataset.tone = "";
    return;
  }
  if (!known || !S.listAtMono) {
    fresh.hidden = true;
    return;
  }
  const nowMono = _monoMs();
  if (S.refreshDoneUntil && nowMono < S.refreshDoneUntil && !termsLocked()) {
    fresh.hidden = false;
    fresh.textContent = "已更新 ✓";
    fresh.className = "fresh ok";
    fresh.dataset.tone = "";
    return;
  }
  const minutes = Math.floor(Math.max(0, nowMono - S.listAtMono) / 60000);
  fresh.hidden = false;
  fresh.className = "fresh";
  if (termsLocked()) {
    /* 没同意条款：不刷新，列表只读停在上次结果，明说可能过时 */
    fresh.textContent = "没同意条款，停在上次的结果，可能过时";
    fresh.dataset.tone = "warn";
    return;
  }
  fresh.textContent = minutes < 1 ? "刚刚更新" : minutes + " 分钟前更新";
  fresh.dataset.tone = minutes > 10 ? "warn" : "";
}

/* ---------------------------------------------------------------- 大屏 */
function paintRail() {
  /* 可报名指标排除已截止：与筛选、开始门禁同一份 isEligibleForPlan 口径 */
  const free = S.items.filter(isEligibleForPlan).length;
  /* 已知零 ≠ 未知：成功返回过（或手里还有缓存快照）就写真实数字，
   * 只有还没拉到时才用破折号，避免把「0 场」说成「还没获取」。 */
  const countsKnown = S.listState === "ready" || S.items.length > 0;
  const freeKnown = bnowS() !== null;
  $("#metric-total").textContent = countsKnown ? String(S.items.length) : "—";
  /* 可报名数依赖当前是否已截止：没有可信现在时只能说「待确认」，不能报 0/6 */
  $("#metric-free").textContent = countsKnown
    ? (freeKnown ? String(free) : "待确认") : "—";
  /* metric-next（LED 标注）统一由 paintLedLabel 维护，这里不再抢写 */
  let text = "先选活动，系统会检查举办时间冲突。";
  if (!S.busy && S.login.present === false) text = "完成登录后选活动。";
  else if (S.busy && S.plan.id) {
    /* 大屏摘要与标题/LED/任务卡同一套阶段解释：等开放 / 准备提交 / 正在提交 */
    const view = executionView();
    /* 单场时不再反复说「本批 1 场 · 每场独立」：同一句话在三处复读（R18） */
    text = view.count <= 1
      ? (view.phase === "submitting" ? "正在提交这一场。"
        : view.phase === "arming" ? "已开放，正在准备提交。"
        : view.phase === "waiting" ? "这一场等开放 · 到点自动开始。"
        : "计划运行中。")
      : view.phase === "submitting" ? "正在提交 " + view.count + " 场 · 每场结果单独显示。"
      : view.phase === "arming" ? "已开放，正在准备提交。"
      : view.phase === "waiting" ? "同时开放 " + view.count + " 场 · 开放后自动开始。"
      : "计划运行中 · 每场任务独立显示结果。";
  }
  else if (S.plan.status === "failed" && planOutcome().unknown > 0) text = "计划已结束 · " + unknownLabel(planOutcome()) + "，去活动页确认。";
  else if (S.plan.status === "partial") text = "计划部分完成 · 失败的场次可以单独查看。";
  else if (S.plan.status === "completed") text = "计划已完成 · 建议去活动页确认一眼。";
  else if (S.plan.status === "stopped") {
    text = "计划已停止 · 已提交的场次保留原状态。"
      + (planOutcome().unknown ? " " + unknownLabel(planOutcome()) + "，去活动页核对。" : "");
  }
  else if (S.selected.size) text = "已选 " + S.selected.size + " 场 · 先看右侧冲突提示。";
  $("#rail-message").textContent = text;
}

/* ---------------------------------------------------------------- 运行目标 */
/* 还能动的任务状态：只有这三种参与「当前目标、当前批次、倒计时」。
 * 已取消/已成功/已报名/已失败是终态，不许再充当运行目标或剩余场次。 */
