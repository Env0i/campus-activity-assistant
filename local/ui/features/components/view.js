/* 组件的视图层：导入弹窗的绘制方法包与导入自检的结论文案；只读写 DOM，
 * 不发桥接请求。 */


import { PhonePanel } from "../phone-access/state.js";
import { IMPORT_TITLE } from "./state.js";
import { phoneShow } from "../phone-access/view.js";



export function importCheckText(key, path, info) {
  const full = String(path || "");
  const name = full.slice(Math.max(full.lastIndexOf("/"), full.lastIndexOf(String.fromCharCode(92))) + 1);
  if (/[.]exe$/i.test(name)) {
    return /tailscale/i.test(name)
      ? "这是 Tailscale 的安装程序，不是组件包。Tailscale 要用官方安装包装好并登录，不用在这里导入。"
      : "这里需要组件包 ZIP，不是可执行文件。";
  }
  if (!info) return "自检没有返回结论。";
  const version = String(info.version || "");
  if (info.ok) {
    return version ? "已识别为「" + (IMPORT_TITLE[key] || key) + "」组件包，版本 " + version + "。"
      : String(info.text || "自检通过。");
  }
  if (info.kind === "not_component") return "这个 ZIP 里没有组件清单，不是本程序的组件包。";
  if (info.kind === "incompatible_manifest") {
    const versionEl = $("#help-version");
    const shown = versionEl ? String(versionEl.textContent || "").trim() : "";
    if (shown && shown !== "—") {
      return "这个组件包和现在的 " + shown + " 不配套。到发布页下载 " + shown + " 的组件包。";
    }
  }
  return String(info.text || "自检没有返回结论。");
}



export const componentsPaintPack = {

  paintComponents() {
    const key = PhonePanel.importKey === "relogin_ocr" ? "relogin_ocr" : "phone_control";
    const title = $("#dlg-components-title");
    if (title) title.textContent = key === "relogin_ocr" ? "导入验证码识别组件" : "导入手机控制组件";
    [{ k: "phone_control", prefix: "comp-phone" }, { k: "relogin_ocr", prefix: "comp-ocr" }].forEach(({ k, prefix }) => {
      const here = k === key;
      phoneShow("#" + prefix, here);
      const installEl = phoneShow("#btn-" + prefix + "-install", here);
      const pathEl = $("#" + prefix + "-path");
      if (pathEl && PhonePanel.picked && PhonePanel.picked[k]) pathEl.value = PhonePanel.picked[k];
      const verified = PhonePanel.verified && PhonePanel.verified[k];
      if (installEl) installEl.disabled = !verified;
    });
  },



  showComponentNote(prefix, text, ok) {
    const noteEl = $("#" + prefix + "-note");
    if (!noteEl) return;
    noteEl.textContent = String(text || "");
    noteEl.hidden = !text;
    noteEl.dataset.tone = ok ? "ok" : "warn";
  },

};
