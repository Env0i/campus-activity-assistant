/* 过渡期清单（ESM 地基批）：把模块里的名字挂回 window，给还没迁的普通脚本用。
 * 模块里的名字不进全局作用域，普通脚本只能经 window 拿到；清单里的每个名字必须真的
 * 有普通脚本在用（tools/code_shape/ui_modules.mjs 守着，没人用就红），一旦没有就要从
 * 这里删掉；全部脚本迁成模块、清单清空后，整个文件连同 main.js 里的调用一起删除。 */
import { termsAccepted, termsLocked } from "./features/terms/state.js";

export function installLegacyGlobals() {
  window.termsAccepted = termsAccepted;
  window.termsLocked = termsLocked;
}
