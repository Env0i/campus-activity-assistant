/* 活动简介与面向范围纯模型（无 DOM、不发请求）。 */
import { cardDateTime, compactActText } from "./state-timeline.js";
import { activityTypeOf } from "./state-types.js";

function splitAudienceItems(text) {
  return String(text || "").split(/[、,，]/).map((x) => x.trim()).filter(Boolean);
}

function foldBranches(list, expanded) {
  if (!list.length) return { text: "", hasMore: false };
  if (list.length <= 3 || expanded) return { text: list.join("、"), hasMore: list.length > 3 };
  return { text: list.slice(0, 3).join("、") + " 等 " + list.length + " 个", hasMore: true };
}

/* 面向范围按学校代码拆行：0 全校、1 分公司、2 年级、3 年级+分公司、其余或未知原样；文字为空写学校未公布 */
export function parseAudience(code, rawText, expanded) {
  const t = rawText === null || rawText === undefined ? "" : String(rawText).trim();
  const c = (code === null || code === undefined || code === "") ? null : Number(code);
  if (c === 0) return { lines: [{ label: "", text: t || "全校" }], hasMore: false };
  if (c === 1) {
    const b = foldBranches(splitAudienceItems(t), !!expanded);
    return { lines: [{ label: "分公司", text: b.text || "学校未公布" }], hasMore: b.hasMore };
  }
  if (c === 2) return { lines: [{ label: "年级", text: t || "学校未公布" }], hasMore: false };
  if (c === 3) {
    const gradeMatch = t.match(/年级[：:]\s*([^;；]*)/);
    const branchMatch = t.match(/分公司[：:]\s*([^;；]*)/);
    const grade = gradeMatch ? gradeMatch[1].trim() : "";
    const branches = foldBranches(splitAudienceItems(branchMatch ? branchMatch[1] : ""), !!expanded);
    return {
      lines: [
        { label: "年级", text: grade || "未写明" },
        { label: "分公司", text: branches.text || "未写明" },
      ],
      hasMore: branches.hasMore,
    };
  }
  return { lines: [{ label: "", text: t || "学校未公布" }], hasMore: false };
}

export function groupLabelOf(item) {
  const st = stateOf(item);
  if (st === "open") return "正在开放";
  if (st === "signed") return "已报名";
  if (st === "closed") return "已截止";
  if (st === "waiting" && signStartKnown(item)) {
    return businessNowMs() !== null ? dayLabel(toTs(item.sign_start) * 1000) : "待校准";
  }
  return signStartKnown(item) ? "待校准" : "待公布";
}

export function descModalModel(item, opts) {
  const st = opts || {};
  const refreshing = !!st.refreshing;
  const openTs = toTs(item && item.sign_start);
  const endTs = toTs(item && item.sign_end);
  const signTime = openTs === null ? "待公布"
    : cardDateTime(openTs) + " 开放，" + (endTs !== null ? cardDateTime(endTs) + " 截止" : "截止未知");
  const rawDesc = item ? item.description : null;
  const syncMissing = rawDesc === null || rawDesc === undefined;
  const text = syncMissing ? "" : String(rawDesc).trim();
  const isLong = !syncMissing && text.length > 160;
  return {
    name: String((item && item.name) || "活动"),
    sub: activityTypeOf(item) + " · " + groupLabelOf(item),
    actTime: compactActText(item),
    place: String((item && item.place) || "").trim() || "地点待定",
    signTime: signTime,
    scope: parseAudience(item && item.audience_code, item && item.audience, !!st.scopeExpanded),
    scopeToggleLabel: st.scopeExpanded ? "收起" : "展开全部",
    body: syncMissing ? "活动简介暂时没同步下来" : (text || "学校未提供活动简介"),
    bodyMode: syncMissing ? "fail" : (!text ? "empty" : (isLong && !st.bodyExpanded ? "clamp" : "")),
    canToggleBody: isLong,
    bodyToggleLabel: st.bodyExpanded ? "收起" : "展开全文",
    canRetry: syncMissing,
    retryDisabled: refreshing,
  };
}
