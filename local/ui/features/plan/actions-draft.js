/* 计划栏草稿段的编排：地点展开的点击绑定。 */

/* 大屏地点展开/收起：按钮原生处理 Enter/Space，这里只翻转 aria-expanded。
 * 只改当前按钮，不重绘整块，键盘焦点不会丢。 */
export function bindPlaceToggle() {
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
