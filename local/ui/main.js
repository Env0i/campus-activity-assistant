/* 模块入口（ESM 地基批）：普通脚本先跑，这里最后接管。依次——挂回 window 的
 * 过渡名单（legacy-globals.js），app.js 末尾原样搬来的启动调用，置就绪标记，
 * 放出排队期间到达的后端事件（boot-guard.js 存下的），再调手机面板的接线启动
 * （普通脚本阶段模块还没执行，接线只能放在这里，先后与搬之前一致：先放事件、后接线）。
 * 全部脚本迁成模块后，legacy-globals.js 与 boot-guard.js 会先后退场，本文件只剩
 * 功能模块的接线。 */
import { installLegacyGlobals } from "./legacy-globals.js";
import { loginEntry, wireRelogin } from "./features/login/actions-relogin.js";
import { startPhonePanel } from "./features/phone-access/actions-panel.js";

installLegacyGlobals();

/* 「登录 / 重新登录」先走重新登录对话框（三种情况）；对话框里保留「改用浏览器登录」。
 * 这两行原来在 app.js 顶层，搬到登录块之后它们是模块里的名字，普通脚本阶段还找不到，
 * 只能放到 installLegacyGlobals() 之后再接。 */
$("#btn-login").addEventListener("click", loginEntry);
wireRelogin();
/* 按窗口宽度分档的首次绘制（原来在 app.js 顶层，与其它顶层绑定同一批执行）。
 * 它会一路走到 paintDock -> startBlocker -> termsLocked()，而那个名字要等上面
 * installLegacyGlobals() 才挂回 window：中、窄档下计划栏可见，普通脚本阶段就调
 * 会抛 ReferenceError，把 app.js 后面那 40 余处绑定整批带走。放到这里之后，
 * 先挂回名字再绘制，宽档（不画计划栏）行为不变。 */
applyBand();
boot().catch((error) => {
  /* 启动链路整体失败同样没有条款依据：先按未知拦住学校动作再报错 */
  markTermsUnknown();
  addLog("[X] 界面初始化失败：" + msg(error));
  render();
});
window.__modulesReady = true;
window.__replayBackendQueue();
startPhonePanel();
