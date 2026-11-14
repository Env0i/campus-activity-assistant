/* 模块入口（ESM 地基批）：普通脚本先跑，这里最后接管。依次——挂回 window 的
 * 过渡名单（legacy-globals.js），app.js 末尾原样搬来的启动调用，置就绪标记，
 * 放出排队期间到达的后端事件（boot-guard.js 存下的）。全部脚本迁成模块后，
 * legacy-globals.js 与 boot-guard.js 会先后退场，本文件只剩功能模块的接线。 */
import { installLegacyGlobals } from "./legacy-globals.js";

installLegacyGlobals();
boot().catch((error) => {
  /* 启动链路整体失败同样没有条款依据：先按未知拦住学校动作再报错 */
  markTermsUnknown();
  addLog("[X] 界面初始化失败：" + msg(error));
  render();
});
window.__modulesReady = true;
window.__replayBackendQueue();
