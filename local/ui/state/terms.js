/* 条款状态的纯投影：只读 S，不写 S、不碰 DOM、不发桥接请求（门禁编排见 controllers/terms.js）。 */

function termsAccepted() {
  return !!S.terms.version && S.terms.acceptedVersion === S.terms.version;
}

/* 学校动作是否被条款拦下（决策 013 返修）：
 * - 离线演示（demo）不做学校网络动作，不受限；
 * - unknown（bootstrap 失败、返回 null、缺 terms、版本为空或结构非法）一律拦，
 *   没有任何依据可以放行学校动作；
 * - 有版本但没同意当前版本 → 拦；
 * - 还没拿到任何条款状态（version 为空且未标 unknown，例如测试桩或桥接未
 *   就绪）→ 前端没有依据，交给后端门禁兜底，不在此处冒充「已确认未同意」。 */
function termsLocked() {
  if (S.demo) return false;
  if (S.terms.unknown) return true;
  if (!S.terms.version) return false;
  return !termsAccepted();
}
