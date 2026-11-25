/* 更多筛选中的「活动类型」多选标签组呈现。 */
import { availableTypes, normalizeTypeFilter } from "./state-types.js";

function makeTypeBtn(label, on) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "tchip" + (on ? " on" : "");
  btn.dataset.type = label;
  btn.setAttribute("aria-pressed", on ? "true" : "false");
  btn.textContent = label;
  return btn;
}

export function paintTypeFilters() {
  const box = $("#more-types");
  if (!box) return;
  const selected = normalizeTypeFilter(S.filter && S.filter.types);
  const types = availableTypes(S.items, selected);
  while (box.firstChild) box.removeChild(box.firstChild);
  if (!types.length) {
    box.hidden = true;
    return;
  }
  box.hidden = false;
  const label = document.createElement("span");
  label.className = "more-lbl";
  label.textContent = "活动类型";
  box.appendChild(label);
  types.forEach((tp) => box.appendChild(makeTypeBtn(tp, selected.indexOf(tp) >= 0)));
  if (selected.length) {
    const clr = document.createElement("button");
    clr.type = "button";
    clr.className = "tchip clear";
    clr.dataset.typeClear = "1";
    clr.textContent = "不限";
    box.appendChild(clr);
  }
}
