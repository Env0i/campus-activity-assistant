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
