/* 顶栏登录胶囊与详情卡的呈现。 */

import { loginEstimateShort } from "./state.js";
import { termsLocked } from "../terms/state.js";

/* 顶栏登录胶囊、结果条与运行日志呈现。 */
export function paintLogin() {
  const pill = $("#pill");
  const detail = $("#status-detail");
  /* 登录胶囊旁只写上次校验时刻；详情卡写「预计有效」（锚点 + 10 小时估，
   * 纯提示，不参与放行或过期判定；决策 006 修订 2026-11-09）。 */
  const ok = S.login.ok;
  let cls = "pill";
  let text = "未登录";
  let sub = "";
  let note = "打开顶栏的登录状态，点「登录」开始使用";
  let state = "none";
  /* 计划运行中胶囊保持「已登录」，不打扰运行中的计划；但学校明确说登录失效（expired）时
   * 必须走「登录已失效」，电脑在自动登录时走「自动登录中…」——否则计划栏运行提醒和
   * 顶部「登录已失效」横幅永远出不来（决策 014 第 8 条）。网络原因的「暂时无法确认」仍保持原样。 */
  const busyExpired = S.login.result === "expired" && S.login.present !== false;
  if (S.busy && !S.login.loginPending && !busyExpired && !S.autoLogin) {
    cls += " is-busy";
    /* 忙时胶囊只表达登录结论，不拿「正在处理」替换它（计划进度属于报名区域） */
    text = S.login.present === false ? "未登录" : "已登录";
    sub = "";
    note = S.stopping ? "正在停止计划；已报名的场次不受影响"
      : "登录状态保持不变；计划进度见报名区域";
    state = S.login.present === false ? "none" : "ok";
  } else if (S.demo) {
    /* 演示模式必须自己说出来：不能借「登录有效」的外观掩盖没有真实会话（R20） */
    cls += " is-warn";
    text = "演示模式";
    sub = "内存样例";
    note = "不读取登录信息、不访问学校，只演示界面与流程";
    state = "demo";
  } else if (S.autoLogin) {
    /* 电脑正在用保存的账号自动登录（中继进度事件 origin=auto）：只说明在做什么，不出横幅 */
    cls += " is-busy";
    text = "自动登录中…";
    note = "学校说登录失效了，电脑正在用保存的账号自动登录";
    state = "pending";
  } else if (S.login.loginPending) {
    /* 登录窗口仍在等待用户完成；不能把旧的有效/失效结论伪装成成功。 */
    cls += " is-busy";
    text = "登录中…";
    note = "请在弹出的浏览器中完成登录；取消或关闭窗口后会保留原状态";
    state = "pending";
  } else if (S.login.checking || (ok === null && S.login.present === true)) {
    /* 正在真实校验：本机有会话也不提前宣布「已登录」，等学校接口结论 */
    cls += " is-busy";
    text = "检查登录…";
    note = "正在检查登录状态，马上就好";
    state = "checking";
  } else if (S.login.present === false) {
    /* 从没登录过（session.json 缺失/解析不了/没有 token）：引导首次登录，
     * 不算失效。check 失败也是「还没登录」，不是「登录状态坏了」。 */
    cls += " is-none";
    note = "打开顶栏的登录状态，点「登录」，在打开的浏览器中完成登录";
  } else if (S.login.result === "unknown" && ok === false) {
    /* 学校接口没应答/网络异常：不能误报成「重新登录」，会话原样保留 */
    cls += " is-none";
    text = "登录待确认";
    note = "暂时无法确认登录状态；检查网络后点「刷新」，先不用重新登录";
    state = "unknown";
  } else if (ok === false && S.login.present !== false) {
    /* 登录过且确认失败/过期，才叫登录已失效；hours_left=0 单独出现
     * 不代表首次未登录。present 未知（老载荷）时维持保守判失效。 */
    cls += " is-bad";
    text = "登录已失效";
    note = "重新登录后可继续使用";
    state = "bad";
  } else if (ok === true) {
    cls += " is-ok";
    text = "已登录";
    /* 只报事实：上次向学校校验的时刻；在别处登录（比如手机上的学校页面）可能让这里失效，以实际校验为准 */
    sub = lastCheckText() ? lastCheckText() + " 校验" : "";
    /* E2：有估算才补「预计约到…，以学校为准」；没有就只报学校确认事实 */
    const estimate = loginEstimateShort();
    note = estimate && estimate.indexOf("约到") === 0
      ? "学校确认登录有效；预计" + estimate + "，以学校为准"
      : "学校确认登录有效";
    state = "ok";
  }
  if (termsLocked() && !S.demo && state !== "pending") {
    /* 没同意条款时登录、登录检查都停用：胶囊明说在等条款，不报旧结论 */
    cls = "pill is-none";
    text = "等同意条款";
    sub = "";
    note = "同意使用条款后才会检查登录";
    state = "terms";
  }
  S.login.view = { state: state, text: text, sub: sub, note: note };
  pill.className = cls;
  pill.dataset.state = state;
  pill.setAttribute("aria-label", text + (sub ? "，" + sub : ""));
  $("#pill-text").textContent = text;
  $("#pill-sub").textContent = sub;
  detail.textContent = note;
  const loginBtnText = $("#btn-login-text");
  /* 只在「确实登录过」的几种状态里叫重新登录；首次使用和未知状态都叫登录 */
  if (loginBtnText) loginBtnText.textContent = state === "bad" || state === "warn" || state === "ok" ? "重新登录" : "登录";
  const loginBtn = $("#btn-login");
  /* 按原型：未登录/失效时转实心更醒目，有效时回到描边 */
  const solid = state === "none" || state === "bad";
  loginBtn.classList.toggle("btn-solid", solid);
  loginBtn.classList.toggle("btn-line", !solid);
  if (typeof paintStatusCards === "function") paintStatusCards();
}
