/* 过渡期清单（ESM 地基批）：把模块里的名字挂回 window，给还没迁的普通脚本用。
 * 模块里的名字不进全局作用域，普通脚本只能经 window 拿到；清单里的每个名字必须真的
 * 有普通脚本在用（tools/code_shape/ui_modules.mjs 守着，没人用就红），一旦没有就要从
 * 这里删掉；全部脚本迁成模块、清单清空后，整个文件连同 main.js 里的调用一起删除。 */
import { termsAccepted, termsLocked } from "./features/terms/state.js";
import { PhonePanel } from "./features/phone-access/state.js";
import { maskAccount } from "./features/login/state-recovery.js";
import { OcrPanel } from "./features/components/state-ocr.js";
import { paintOcrDownload } from "./features/components/view-ocr.js";

export function installLegacyGlobals() {
  window.termsAccepted = termsAccepted;
  window.termsLocked = termsLocked;
  /* app.js 的 check 事件要顺手刷新这张卡片（重新登录成功会走 check）。跨文件只能靠
   * 一个显式挂载点：顶层 const 不会自动变成 window 属性。 */
  if (typeof window !== "undefined") window.PhonePanel = PhonePanel;
  window.maskAccount = maskAccount;
  window.OcrPanel = OcrPanel;
  window.paintOcrDownload = paintOcrDownload;
}
