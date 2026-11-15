/* 组件的编排层：组件的动作方法包（取位置、打开与关闭导入弹窗、选文件、自检、
 * 安装、打开所在文件夹、下载、取消下载）；发桥接请求的方法都放在这一层。 */


import { PhonePanel, phonePhase, setRetryWaitBase } from "../phone-access/state.js";
import { importCheckText } from "./view.js";
import { OcrPanel } from "./state-ocr.js";
import { rowOpen, setRowOpen } from "./state-row.js";



export const componentsActionsPack = {

  /* PH09：位置只问一次就记住（数据目录这次运行里不会变）；没拿到就下次刷新再问 */
  async loadLocation() {
    if (PhonePanel.location) return;
    try {
      const loc = await api("advanced_component_location", "phone_control");
      PhonePanel.location = (loc && loc.ok && loc.short)
        ? { path: String(loc.path || ""), short: String(loc.short) } : null;
    } catch (err) {
      PhonePanel.location = null;
    }
  },



  /* 导入已下载的组件包（原型 impView，IM01）：一次只导入一个组件，标题随 key 变；
     程序不代选文件，选错东西由自检当场说明它到底是什么。 */
  openComponents(key) {
    const dlg = $("#dlg-components");
    if (!dlg) return;
    const which = key === "relogin_ocr" ? "relogin_ocr" : "phone_control";
    PhonePanel.importKey = which;
    PhonePanel.picked = { phone_control: "", relogin_ocr: "" };
    PhonePanel.verified = { phone_control: "", relogin_ocr: "" };
    ["comp-phone", "comp-ocr"].forEach((prefix) => {
      const pathEl = $("#" + prefix + "-path");
      if (pathEl) pathEl.value = "";
      PhonePanel.showComponentNote(prefix, "", false);
    });
    PhonePanel.paintComponents();
    if (typeof dlg.showModal === "function") dlg.showModal();
    else dlg.setAttribute("open", "");
  },



  async pickComponent(key) {
    const prefix = key === "phone_control" ? "comp-phone" : "comp-ocr";
    const result = await api("pick_advanced_component", key);
    if (!result || result.canceled) return;
    if (!result.ok) {
      PhonePanel.showComponentNote(prefix, (result && result.text) || "打不开文件选择框。", false);
      return;
    }
    const pathEl = $("#" + prefix + "-path");
    if (pathEl) pathEl.value = String(result.path || "");
    await PhonePanel.inspectComponent(key, String(result.path || ""));
  },



  /* 选完文件立刻自检（IM01 没有单独的「自检」按钮）。.exe 不进后端：这里只接收组件包 ZIP（IM01，
     裸 cloudflared.exe 的入口随弹窗改版去掉，后端接口不动）；结论文案在 importCheckText（IM03）。 */
  async inspectComponent(key, path) {
    const prefix = key === "phone_control" ? "comp-phone" : "comp-ocr";
    const chosen = String(path || "").trim();
    PhonePanel.picked[key] = chosen;
    PhonePanel.verified[key] = "";
    const installEl = $("#btn-" + prefix + "-install");
    if (installEl) installEl.disabled = true;
    if (!chosen) {
      PhonePanel.showComponentNote(prefix, "还没有选择文件。", false);
      return;
    }
    const isExe = /[.]exe$/i.test(chosen);
    const info = isExe ? { ok: false, kind: "not_zip" } : await api("inspect_advanced_component", key, chosen);
    PhonePanel.showComponentNote(prefix, importCheckText(key, chosen, info), !!(info && info.ok));
    if (info && info.ok) PhonePanel.verified[key] = chosen;
    PhonePanel.paintComponents();
  },



  /* 装好后关掉弹窗，结论就地说在抽屉里对应的那一节（原型 impInstall：imp 置空，再给一句 note） */
  async installComponent(key) {
    const prefix = key === "phone_control" ? "comp-phone" : "comp-ocr";
    const chosen = String((PhonePanel.verified || {})[key] || "");
    if (!chosen) {
      PhonePanel.showComponentNote(prefix, "先选文件并自检通过，再安装。", false);
      return;
    }
    // I1：置位到 refresh 返回为止，抽屉与对话框都按「安装中」画，不按导入前的旧快照说失败
    PhonePanel.installing[key] = true;
    PhonePanel.paint();
    const installEl = $("#btn-" + prefix + "-install");
    if (installEl) { installEl.disabled = true; installEl.textContent = "安装中…"; }
    try {
      const result = await api("install_advanced_feature", key, chosen);
      const ok = !!(result && result.ok);
      if (!ok) {
        PhonePanel.showComponentNote(prefix, (result && result.text) || "安装没有完成。", false);
      } else {
        PhonePanel.picked[key] = "";
        PhonePanel.verified[key] = "";
        const pathEl = $("#" + prefix + "-path");
        if (pathEl) pathEl.value = "";
        PhonePanel.showComponentNote(prefix, "", false);
        // PH32 / OC15：导入装好后在对应的那一节说一句（原型 impInstall）
        if (key === "phone_control") {
          PhonePanel.notes.off = "手机控制组件已导入并启用，选一条通道就能开启。";
          PhonePanel.notes.missing = "";
        } else if (typeof OcrPanel !== "undefined") {
          OcrPanel.note = "验证码识别组件已导入并启用。";
          OcrPanel.error = "";
        }
        PhonePanel.closeComponents();
        await PhonePanel.refresh();
      }
    } finally {
      PhonePanel.installing[key] = false;
      if (installEl) installEl.textContent = "安装这份";
      PhonePanel.paintComponents();
      // refresh 已按「安装中」画过一遍；这里按刷新后的真实快照重画（失败路径也要把旧红条放回来）
      PhonePanel.paint();
    }
  },



  closeComponents() {
    const dlg = $("#dlg-components");
    if (!dlg) return;
    if (typeof dlg.close === "function" && dlg.hasAttribute && dlg.hasAttribute("open")) dlg.close();
    else dlg.removeAttribute("open");
  },



  async openComponentDir() {
    let result = null;
    try {
      result = await api("open_advanced_component_dir", "phone_control");
    } catch (err) {
      result = { ok: false };
    }
    if (result && result.ok) return;
    const text = String((result && result.text) || "打不开所在文件夹。");
    const phase = phonePhase(PhonePanel.state,
      Object.assign({}, PhonePanel.state.feature || {}, PhonePanel.feature("phone_control")));
    if (phase === "on") PhonePanel.notes.onErr = text;
    else if (phase === "off") PhonePanel.notes.offErr = text;
    else PhonePanel.notes.feature = text;
    PhonePanel.paint();
  },



  /* 组件下载：一次点击就走完「取地址 → 下载 → 校验 → 安装」，用户不用选文件。
   * key 为 phone_control（手机控制）或 relogin_ocr（验证码识别），两者同一条后端事务。 */
  async downloadComponent(key) {
    const feature = key === "relogin_ocr" ? "relogin_ocr" : "phone_control";
    if (PhonePanel.busy) return;
    PhonePanel.busy = true;
    if (feature === "phone_control") PhonePanel.notes.missing = "";
    PhonePanel.paint();
    let result = null;
    try {
      result = await api("download_advanced_feature", feature);
    } catch (err) {
      result = { ok: false, text: "组件下载没有开始，请稍后重试。" };
    } finally {
      PhonePanel.busy = false;
    }
    if (feature === "relogin_ocr") {
      // OC11 / OC15：反馈就地写在验证码识别那一节（features/components/state-ocr.js OcrPanel），不再走抽屉底部；开始下载不另说，进度块会出现
      if (typeof OcrPanel !== "undefined") {
        OcrPanel.note = "";
        OcrPanel.error = result && result.ok ? "" : String((result && result.text) || "组件下载没有开始。");
      }
    } else if (!(result && result.ok)) {
      PhonePanel.notes.missing = String((result && result.text) || "组件下载没有开始。");
    }
    await PhonePanel.refresh();
    /* 下载在后台进行：没开手机访问时也要轮询，进度和结论才能更新 */
    if (result && result.ok) PhonePanel.startPolling();
  },



  async cancelComponent(key) {
    const feature = key === "relogin_ocr" ? "relogin_ocr" : "phone_control";
    let result = null;
    try {
      result = await api("cancel_advanced_feature_download", feature);
    } catch (err) {
      result = { ok: false, text: "取消没有生效，请稍后重试。" };
    }
    if (feature === "relogin_ocr") {
      // OC13：成功后回到没装态，不留「已取消」那些字（由 features/components/view-ocr.js 决定）；失败才在本节红条里说
      if (typeof OcrPanel !== "undefined") {
        OcrPanel.note = "";
        OcrPanel.error = result && result.ok === false
          ? String((result && result.text) || "取消没有生效，请稍后重试。") : "";
      }
    } else {
      // 手机控制：成功后回到没装态，不留「已取消」那些字；失败就在进度下面说
      PhonePanel.notes.loading = result && result.ok === false
        ? String((result && result.text) || "取消没有生效，请稍后重试。") : "";
    }
    await PhonePanel.refresh();
  },



};


/* 读状态那句旁边的「重试」：先记下这一行此刻等了多久当起点，再要一次快照。
 * 起点之后又等满 30 秒才算再次超时（判定在 features/components/state-machine.js），
 * 否则点一次还是「超时」，用户点了等于没点。 */
export function retryComponent(key) {
  const feature = key === "relogin_ocr" ? "relogin_ocr" : "phone_control";
  setRetryWaitBase(feature, PhonePanel.feature(feature).lock_wait_s);
  void PhonePanel.refresh();
}


/* 两个「重试」按钮的绑定：由 features/phone-access/actions-panel.js 的 startPhonePanel
 * 在挂完全部面板绑定之后调一次（wire 里的绑定清单不动）。 */
export function wireComponentRetries() {
  /* 缺 cloudflared 时的补装入口：标题行只留「开启」，这只在展开区 */
  const pack = $("#btn-phone-package");
  if (pack) pack.addEventListener("click", () => PhonePanel.openComponents("phone_control"));
  const phoneRetry = $("#btn-phone-component-retry");
  if (phoneRetry) {
    phoneRetry.addEventListener("click", () => retryComponent("phone_control"));
  }
  const ocrRetry = $("#btn-ocr-retry");
  if (ocrRetry) {
    ocrRetry.addEventListener("click", () => retryComponent("relogin_ocr"));
  }
}


/* 两只展开箭头：开合状态记在 features/components/state-row.js 的模块变量里（一次运行内记住、
 * 不落盘），点了就地重画——手机访问默认展开、验证码识别默认收起。绑定同样由
 * features/phone-access/actions-panel.js 的 startPhonePanel 调一次，wire 里的清单不动。 */
export function wireRowToggles() {
  [["#btn-phone-row-toggle", "phone"], ["#btn-ocr-row-toggle", "ocr"]].forEach((pair) => {
    const btn = $(pair[0]);
    if (!btn) return;
    btn.addEventListener("click", () => {
      setRowOpen(pair[1], !rowOpen(pair[1]));
      PhonePanel.paint();
    });
  });
}
