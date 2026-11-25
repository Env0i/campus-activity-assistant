import { setResult } from "../shell/view-result.js";
import { cancelAsk, cancelAskDismiss, cancelConfirm } from "./actions-cancel.js";
import { openDescDialog } from "./actions-desc.js";
import { togglePlace } from "../plan/view-draft.js";
import { render } from "../shell/actions-render.js";
import { termsLocked } from "../terms/state.js";

export function toggleSelection(id, checked) {
  if (S.busy || S.starting) return;
  /* 条款门对「选中」同样生效：大屏「选这一场」走的是同一条选择路径，
   * 只拦列表复选框会自相矛盾。 */
  if (termsLocked()) return;
  const item = findItem(id);
  /* 已报名和已截止都不能进选择集合（含整行点击路径，复选框已禁用） */
  if (!item || !isEligibleForPlan(item)) return;
  if (checked) {
    const existing = selectedItems();
    const candidateStart = toTs(item.act_start);
    const candidateEnd = toTs(item.act_end);
    /* 已报名活动先挡：它是学校确认的外部占用，不是本次选择内部冲突 */
    const signedClash = S.items.find((other) => {
      if (!other.signed || String(other.id) === String(id)) return false;
      const start = toTs(other.act_start);
      const end = toTs(other.act_end);
      return candidateStart && candidateEnd && start && end
        && candidateStart < end && start < candidateEnd;
    });
    if (signedClash) {
      S.selectionNotice = "与已报名活动「" + signedClash.name + "」的举办时间重叠（"
        + activityTimeText(signedClash) + "），不能再加入计划。";
      render();
      return;
    }
    const conflict = existing.find((other) => {
      const start = toTs(other.act_start);
      const end = toTs(other.act_end);
      return candidateStart && candidateEnd && start && end && candidateStart < end && start < candidateEnd;
    });
    if (conflict) {
      S.selectionNotice = "与「" + conflict.name + "」的活动时间重叠，同一计划只能选择其中一场。已保留原选择。";
      render();
      return;
    }
    S.selected.add(String(id));
    S.selectionNotice = "";
  } else {
    S.selected.delete(String(id));
    S.selectionNotice = "";
  }
  setResult(null);
  render();
}

export function clearSelection() {
  if (S.busy || S.starting) return;
  S.selected.clear();
  S.selectionNotice = "";
  S.plan = { id: null, status: "idle", tasks: new Map() };
  S.editing = null;
  setResult(null);
  render();
}

/* 「去已报名那场」：滚到那一行并短暂高亮；列表被筛选藏起来时先放开筛选（排序保持不变） */
export function tipGoSigned() {
  const pair = tipPair();
  if (!pair) { tipClose(); return; }
  const id = String(pair.sg.id);
  tipClose();
  if (!filtered().some((it) => String(it.id) === id)) {
    S.filter = Object.assign({}, S.filter, { q: "", status: "all", time: "all", checkin: "all", checkout: "all", types: [] });
    $("#q").value = "";
    $("#time").value = "all";
    $("#checkin").value = "all";
    $("#checkout").value = "all";
    paintChips();
    savePrefs({ filter: Object.assign({}, S.filter) });
  }
  S.flashId = id;
  render();
  const row = S.rowEls.get(id);
  if (row && row.row && row.row.scrollIntoView) row.row.scrollIntoView({ block: "center", behavior: "smooth" });
  clearTimeout(S.tip.flashTimer);
  S.tip.flashTimer = setTimeout(() => {
    S.flashId = "";
    const el = S.rowEls.get(id);
    if (el && el.row) el.row.classList.remove("is-flash");
  }, 2000);
}

export function wireRowActions() {
  $("#rows").addEventListener("change", (event) => {
    const check = event.target.closest(".row-check");
    if (check) toggleSelection(check.dataset.id, check.checked);
  });
  $("#rows").addEventListener("click", (event) => {
    /* 取消报名：按钮只展开确认块；确认块里「不取消」不调接口，只有「确认取消报名」才调（features/list/actions-cancel.js） */
    const cancelBtn = event.target.closest("[data-cancel]");
    if (cancelBtn) { cancelAsk(cancelBtn.dataset.cancel); return; }
    const cancelNo = event.target.closest("[data-cancel-no]");
    if (cancelNo) { cancelAskDismiss(); return; }
    const cancelYes = event.target.closest("[data-cancel-yes]");
    if (cancelYes) { cancelConfirm(cancelYes.dataset.cancelYes); return; }
    if (event.target.closest(".rx")) return;
    const descBtn = event.target.closest(".desc-btn");
    if (descBtn) { event.stopPropagation(); openDescDialog(descBtn.dataset.desc, descBtn); return; }
    if (event.target.closest(".row-check")) return;
    /* 地点是独立可聚焦控件：点它只展开/收起完整文本，不改变选择 */
    const place = event.target.closest(".c-place");
    if (place) { togglePlace(place); return; }
    const row = event.target.closest(".row");
    if (!row) return;
    const check = row.querySelector(".row-check");
    if (check && !check.disabled) { check.checked = !check.checked; toggleSelection(check.dataset.id, check.checked); }
  });
  /* 键盘展开地点：Enter / Space 只翻转 aria-expanded，不触发开始计划或勾选 */
  $("#rows").addEventListener("keydown", (event) => {
    /* 「不可加入」标签上的键盘：Esc 收气泡，Enter / 空格把焦点移进气泡里的链接 */
    if (event.target.closest && event.target.closest(".state-clash")) { tipKey(event); return; }
    const place = event.target.closest(".c-place");
    if (!place) return;
    if (event.key !== "Enter" && event.key !== " " && event.key !== "Spacebar") return;
    event.preventDefault();
    togglePlace(place);
  });
}
