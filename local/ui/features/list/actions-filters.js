import { render } from "../shell/actions-render.js";
/* 展开状态与筛选值一样记进偏好；记不下来不影响本次使用 */
export function setFilterOpen(open) {
  S.filterOpen = !!open;
  savePrefs({ filter_open: S.filterOpen });
  paintMoreFilters();
}

export function setFilter(key, value) {
  S.filter[key] = value;
  savePrefs({ filter: Object.assign({}, S.filter) });
  render();
}


export function wireFilters() {
  $("#q").addEventListener("input", (event) => setFilter("q", event.target.value));
  $("#chips").addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (chip) { setFilter("status", chip.dataset.status); paintChips(); }
  });
  /* LS06 更多筛选：折叠按钮开合下拉面板，展开状态记进偏好 */
  $("#btn-more").addEventListener("click", () => setFilterOpen(!S.filterOpen));
  $("#time").addEventListener("change", (event) => setFilter("time", event.target.value));
  $("#sort").addEventListener("change", (event) => setFilter("sort", event.target.value));
  $("#checkin").addEventListener("change", (event) => setFilter("checkin", event.target.value));
  $("#checkout").addEventListener("change", (event) => setFilter("checkout", event.target.value));
}
