/* 筛选条与选择告警呈现（含计划错误浮层）。 */
function paintChips() {
  /* 状态胶囊带计数（原型样式）：可报名/已报名/全部按全量数据算；
   * 可报名排除已截止（只能查看），已报名单独计，剩下是已截止 */
  const free = S.items.filter(isEligibleForPlan).length;
  const signed = S.items.filter((item) => item.signed).length;
  /* 没有可信现在时，可报名/已截止的划分无法确定：计数显示待确认而不是伪 0 */
  const counts = { free: bnowS() !== null || !S.items.length ? free : "待确认",
                   signed, all: S.items.length };
  document.querySelectorAll(".chip").forEach((chip) => {
    const on = chip.dataset.status === S.filter.status;
    chip.classList.toggle("is-on", on);
    chip.setAttribute("aria-pressed", on ? "true" : "false");
    let count = chip.querySelector(".ct");
    if (!count) {
      count = document.createElement("span");
      count.className = "ct";
      chip.appendChild(count);
    }
    count.textContent = counts[chip.dataset.status] || 0;
  });
}

/* LS06 更多筛选：折叠按钮的计数 = 下拉里偏离默认值的个数（开放/排序/签到/签退）；
 * 搜索词和状态胶囊本来就常驻在筛选行上，不算进去（原型 Main.dc.html 的 fN）。 */
const MORE_FILTER_DEFAULTS = { time: "all", sort: "open", checkin: "all", checkout: "all" };
function moreFilterCount() {
  return Object.keys(MORE_FILTER_DEFAULTS).filter((key) => S.filter[key] !== MORE_FILTER_DEFAULTS[key]).length;
}

/* 折叠按钮与面板：文字「更多筛选」或「更多筛选（N）」，N>0 加 on 样式；aria-expanded 跟展开状态 */
function paintMoreFilters() {
  const count = moreFilterCount();
  const button = $("#btn-more");
  button.classList.toggle("on", count > 0 || S.filterOpen);
  button.setAttribute("aria-expanded", S.filterOpen ? "true" : "false");
  $("#more-label").textContent = count > 0 ? "更多筛选（" + count + "）" : "更多筛选";
  $("#more-filters").hidden = !S.filterOpen;
}

/* 展开状态与筛选值一样记进偏好；记不下来不影响本次使用 */
function setFilterOpen(open) {
  S.filterOpen = !!open;
  savePrefs({ filter_open: S.filterOpen });
  paintMoreFilters();
}

function setFilter(key, value) {
  S.filter[key] = value;
  savePrefs({ filter: Object.assign({}, S.filter) });
  render();
}

/* 后端验证失败：errors/conflicts 逐条翻译成「哪一场、什么问题」，
 * 不折成一句泛化文案；同 sign_start 不是冲突依据，只报举办时段。 */
const PLAN_ERROR_TEXT = {
  missing_id: "有活动缺少 id，刷新列表后再选。",
  duplicate_id: "同一活动被选了两遍，去掉重复的那一条。",
  already_signed: "此活动已报名，请从本次计划中移除。",
  invalid_sign_start: "报名开放时间缺失或格式不对。",
  activity_time_unknown: "缺少完整的活动举办起止时间。",
  activity_time_invalid: "活动结束时间不晚于开始时间。",
  activity_overlap: "活动举办时段重叠。",
  sign_end_passed: "报名已截止，不能加入计划。",
};

function showPlanError(text, conflicts, errors) {
  const messages = [];
  (errors || []).forEach((error) => {
    const kind = error && error.kind;
    if (kind === "activity_overlap") return; /* 冲突单列，避免重复 */
    const label = PLAN_ERROR_TEXT[kind] || "这一项不能加入计划。";
    const name = error && (error.name || error.activity_id);
    messages.push("<div class=\"conflict-item\"><strong>" + esc(label) + "</strong><br>" + (name ? "「" + esc(name) + "」" : "") + "</div>");
  });
  (conflicts || []).forEach((conflict) => {
    const left = conflict.left || {};
    const right = conflict.right || {};
    messages.push("<div class=\"conflict-item\"><strong>活动时间重叠</strong><br>「" + esc(left.name) + "」与「" + esc(right.name) +
      "」举办时段重叠（" + esc(shortTime(left.act_start)) + " – " + esc(shortTime(left.act_end)) + "），只能选其中一场。</div>");
  });
  if (messages.length) {
    S.selectionNotice = "计划未能开始，先处理上面的提示再试。";
    const box = $("#plan-conflicts");
    box.innerHTML = messages.join("");
    box.hidden = false;
    render();
  }
  setResult({ ok: false, title: "计划没能开始", text: (messages.length ? "上面列出了每一场的问题。" : "") + (text || "先处理提示，再试一次。") });
}
