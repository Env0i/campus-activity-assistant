import { runtimeErrorCopy } from "../shell/state-runtime.js";

function failHint(text) {
  const raw = String(text || "");
  if (S.login.present === false || S.login.result === "none") return "完成登录后点「刷新」加载活动。";
  /* 静默恢复中：不提示用户重新登录，说明电脑正在做什么就够了 */
  if (S.login.result === "expired") return S.autoLogin
    ? "电脑正在用保存的账号自动登录，登录好以后这里会自动加载。"
    : "点「重新登录」后刷新。";
  if (S.login.result === "unknown") return "恢复网络后点「刷新」重试。";
  if (needLogin(raw)) return "点「重新登录」后刷新。";
  if (/网络|连接|超时|timeout|连不上|dns|ssl|代理/i.test(raw)) return "连不上学校站点。检查校园网或代理，恢复后点「刷新」。";
  return "程序组件没能正常启动。先点「刷新」；还不行就看下面的运行记录。";
}

/* cause 是这一句的第一个分句（运行记录用，不带恢复动作，也不带原始异常名）。 */
export function listErrorCopy(raw) {
  /* 组件问题优先：缺组件时列表失败不许被翻译成「先登录/重新登录」 */
  if (S.runtime.error) {
    const copy = runtimeErrorCopy();
    return { title: copy.title, text: copy.hint, cause: copy.title };
  }
  /* 登录本身有问题时仍按登录分支给下一步：重新登录能修好，说成「连不上」是误判 */
  if (S.login.present === false || S.login.result === "none") return { title: "还没登录", text: failHint(raw), cause: "还没登录" };
  /* 静默恢复中不报「登录已过期」：用户不需要为一件电脑正在处理的事动手 */
  if (S.login.result === "expired") {
    return S.autoLogin
      ? { title: "正在自动登录", text: failHint(raw), cause: "正在自动登录" }
      : { title: "登录已过期", text: failHint(raw), cause: "登录已过期" };
  }
  if (S.login.result === "unknown") return { title: "暂时无法加载", text: failHint(raw), cause: "登录状态还没确认" };
  /* 已登录仍然拉不到列表：用原型 Main.dc.html 的 listerr 空态原话（LS12：先说已保存的登录不受影响，
   * 再给下一步，按钮叫「刷新」）。登录是有效的，重新登录修不好网络，所以不把失败归因成登录问题。 */
  return { title: "活动暂时没加载", text: "连不上学校站点，已保存的登录不受影响。检查网络后点“刷⁠新”。", cause: "连不上学校站点" };
}

function needLogin(text) { return /登录状态|登录状态|未登录|请先登录|session|401|403|token/i.test(String(text || "")); }
