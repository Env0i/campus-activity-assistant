/* 登录恢复的状态层：账号打码函数；被计划面板这个普通脚本用到，经过渡名单挂回
 * window。 */

/* 账号打码：前两位加后两位，中间四个星号（与后端 domain/login_rules.mask_account 同一规则） */
export function maskAccount(name) {
  const text = String(name || "").trim();
  if (!text) return "已保存";
  return text.length >= 5 ? text.slice(0, 2) + "****" + text.slice(-2) : text.slice(0, 1) + "****";
}
