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
    S.filter = Object.assign({}, S.filter, { q: "", status: "all", time: "all", checkin: "all", checkout: "all" });
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
