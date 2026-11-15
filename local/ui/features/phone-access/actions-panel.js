/* 手机面板的编排层·装配：面板的 wire 方法在这里，各方法包用一句 Object.assign
 * 一次装回 PhonePanel，最后导出启动函数给 main.js 调——普通脚本阶段模块还没执行，
 * 接线必须等模块就绪以后做。 */


import { PhonePanel } from "./state.js";
import { phonePaintPack } from "./view.js";
import { phoneActionsPack } from "./actions.js";
import { componentsPaintPack } from "../components/view.js";
import { componentsActionsPack, wireComponentRetries, wireRowToggles } from "../components/actions.js";
import { recoveryPaintPack } from "../login/view-recovery.js";
import { recoveryActionsPack } from "../login/actions-recovery.js";



const panelWirePack = {

  wire() {
    const start = $("#btn-phone-start");
    const stop = $("#btn-phone-stop");
    const manage = $("#btn-credentials-manage");
    const save = $("#btn-credentials-save");
    const clear = $("#btn-credentials-clear");
    const recheck = $("#btn-tailscale-recheck");
    const copy = $("#btn-phone-address-copy");
    const stopCancel = $("#btn-phone-stop-cancel");
    const stopConfirm = $("#btn-phone-stop-confirm");
    // PH07：没装时标题行的「下载并安装」直接一键下载（决策 010 第 54 行），不再打开导入弹窗
    const compInstall = $("#btn-phone-component-install");
    if (compInstall) compInstall.addEventListener("click", () => void PhonePanel.downloadComponent("phone_control"));
    const compCancel = $("#btn-phone-component-cancel");
    if (compCancel) compCancel.addEventListener("click", () => void PhonePanel.cancelComponent("phone_control"));
    const featureBtn = $("#btn-phone-feature-install");
    if (featureBtn) featureBtn.addEventListener("click", () => PhonePanel.featureAction());
    // PH10：下载失败后才露出的「导入已下载的组件包」
    const importPhone = $("#btn-phone-import");
    if (importPhone) importPhone.addEventListener("click", () => PhonePanel.openComponents("phone_control"));
    const pickPhone = $("#btn-comp-phone-pick");
    if (pickPhone) pickPhone.addEventListener("click", () => void PhonePanel.pickComponent("phone_control"));
    const pickOcr = $("#btn-comp-ocr-pick");
    if (pickOcr) pickOcr.addEventListener("click", () => void PhonePanel.pickComponent("relogin_ocr"));
    const installPhoneFile = $("#btn-comp-phone-install");
    if (installPhoneFile) installPhoneFile.addEventListener("click", () => void PhonePanel.installComponent("phone_control"));
    const installOcrFile = $("#btn-comp-ocr-install");
    if (installOcrFile) installOcrFile.addEventListener("click", () => void PhonePanel.installComponent("relogin_ocr"));
    const closeComponents = $("#btn-comp-close");
    if (closeComponents) closeComponents.addEventListener("click", () => PhonePanel.closeComponents());
    // PH16：两张单选卡，选中即记偏好
    ["tailscale", "cloudflare"].forEach((key) => {
      const radio = $("#phone-chan-" + key);
      if (radio) radio.addEventListener("change", () => void PhonePanel.changeChannel(key));
    });
    if (start) start.addEventListener("click", () => void PhonePanel.toggleStart());
    if (stop) stop.addEventListener("click", () => PhonePanel.askStop());
    if (stopCancel) stopCancel.addEventListener("click", () => PhonePanel.cancelStop());
    if (stopConfirm) stopConfirm.addEventListener("click", () => void PhonePanel.confirmStop());
    const addPair = $("#btn-phone-add-pair");
    if (addPair) addPair.addEventListener("click", () => PhonePanel.addPairing());
    const credGo = $("#btn-phone-cred-go");
    if (credGo) credGo.addEventListener("click", () => PhonePanel.goSaveCredentials());
    const openLoc = $("#btn-phone-open-loc");
    if (openLoc) openLoc.addEventListener("click", () => void PhonePanel.openComponentDir());
    if (recheck) recheck.addEventListener("click", () => void PhonePanel.recheckTailscale());
    if (copy) copy.addEventListener("click", () => void PhonePanel.copyAddress());
    if (manage) manage.addEventListener("click", () => PhonePanel.openCredForm());
    const credCancel = $("#btn-credentials-cancel");
    if (credCancel) credCancel.addEventListener("click", () => PhonePanel.cancelCredForm());
    // CR14：账号或密码为空时保存按钮禁用；CR12：勾选项改按钮名
    ["#credential-user", "#credential-pass"].forEach((sel) => {
      const field = $(sel);
      if (field) field.addEventListener("input", () => PhonePanel.paintCredForm());
    });
    const onceBox = $("#credential-once");
    if (onceBox) onceBox.addEventListener("change", () => PhonePanel.paintCredForm());
    if (save) save.addEventListener("click", () => void PhonePanel.saveCredentials());
    if (clear) clear.addEventListener("click", () => PhonePanel.askClearCredentials());
    const clearCancel = $("#btn-relogin-clear-cancel");
    const clearConfirm = $("#btn-relogin-clear-confirm");
    if (clearCancel) clearCancel.addEventListener("click", () => PhonePanel.cancelClearCredentials());
    if (clearConfirm) clearConfirm.addEventListener("click", () => void PhonePanel.confirmClearCredentials());
    void PhonePanel.refresh();
  },

};



Object.assign(PhonePanel, phonePaintPack, phoneActionsPack,
  componentsPaintPack, componentsActionsPack,
  recoveryPaintPack, recoveryActionsPack, panelWirePack);



export function startPhonePanel() {
  if (typeof document !== "undefined") {
    if (document.readyState !== "loading") PhonePanel.wire();
    else document.addEventListener("DOMContentLoaded", PhonePanel.wire);
    // 两个「重试」在面板里是常驻元素，不经过 wire 挂（wire 的绑定清单不再变长）
    wireComponentRetries();
  wireRowToggles();
  }
}
