/* 验证码识别一节的状态层：识别面板的字段、快照取行与状态机推导；不碰 DOM，不发桥接请求。 */



export function ocrFeature() {
  if (window.PhonePanel && typeof window.PhonePanel.feature === "function") {
    const row = window.PhonePanel.feature("relogin_ocr");
    if (row && Object.keys(row).length) return row;
  }
  const adv = (typeof S !== "undefined" && S.advanced) || {};
  return ((adv.features || {}).relogin_ocr) || {};
}



/* 验证码识别（settings-gap 二、OC01–OC15，原型 ocrView，Main.dc.html 1399–1411）。
 * 反馈就地写在这一节里（OC15），不走抽屉底部那一行；组件位置只走电脑端专用接口（B3），取不到就不显示。
 * note / error 由 views/settings.js 的动作和 features/components/actions.js 里 relogin_ocr 的下载、取消、导入三处写入。 */
export const OcrPanel = {
  busy: false,
  note: "",
  error: "",
  location: null,
  lastDownload: "",
};



/* 状态机：downloading / verifying 下载中 / broken 已装但加载失败（原型没画，保留，OC14）/
 * on 已启用 / off 已装好还没启用（R3，冲突 6）/ missing 没装 / checking 检查中（组件事务锁被占，还没结论，不是没装）。 */
export function ocrPhase(feature) {
  const dl = String(((feature && feature.download) || {}).state || "");
  if (dl === "downloading") return "downloading";
  if (dl === "verifying") return "verifying";
  if (feature && String(feature.status || "") === "checking") return "checking";
  if (feature && String(feature.status || "") === "outdated") return "outdated";
  if (feature && String(feature.status || "") === "failed") return "broken";
  if (feature && feature.ready) return "on";
  if (feature && feature.available) return "off";
  return "missing";
}
