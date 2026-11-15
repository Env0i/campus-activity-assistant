/* 验证码识别一节的状态层：识别面板的字段、快照取行与状态机推导；不碰 DOM，不发桥接请求。 */

import { componentState } from "./state-machine.js";



export function ocrFeature() {
  if (window.PhonePanel && typeof window.PhonePanel.feature === "function") {
    const row = window.PhonePanel.feature("relogin_ocr");
    if (row && Object.keys(row).length) return row;
  }
  const adv = (typeof S !== "undefined" && S.advanced) || {};
  return ((adv.features || {}).relogin_ocr) || {};
}



/* 验证码识别一节：反馈就地写在这一节里，不走抽屉底部那一行；组件位置只走
 * 电脑端专用接口，取不到就不显示。note / error 由 views/settings.js 的动作和
 * features/components/actions.js 里 relogin_ocr 的下载、取消、导入三处写入。 */
export const OcrPanel = {
  busy: false,
  note: "",
  error: "",
  location: null,
  lastDownload: "",
};



/* 状态机：downloading / verifying 下载中 / broken 已装但加载失败（原型没画，保留）/
 * on 已启用 / off 已装好还没启用 / missing 没装 / checking 检查中（组件事务锁被占，
 * 还没结论，不是没装）。与手机控制那一行共用一台状态机（./state-machine.js 的
 * componentState）：识别行把 enabled 当已启用、disabled 也当未启用，其余同名映射。
 * 名字、参数、返回值与搬进模块前一致。 */
export function ocrPhase(feature) {
  const facts = componentState(feature, {});
  if (facts.state === "enabled") return "on";
  if (facts.state === "disabled") return "off";
  return facts.state;
}
