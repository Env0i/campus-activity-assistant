import { setResult } from "../shell/view-result.js";
import { setBusy } from "../shell/actions-render.js";
/* 登录的编排层（浏览器登录）：打开登录窗口、done 收口与失败文案。 */

import { setLogin, syncLoginDependentView } from "./actions.js";
import { loginSnapshotState, restoreLoginSnapshotState } from "./state.js";
import { paintSelected } from "../plan/view.js";
import { termsLocked } from "../terms/state.js";
import { RUNTIME_ERRORS } from "../shell/state-runtime.js";

function settleBrowserOutcome(attempt, ok, text) {
  if (!S.login || S.login.browserAttempt !== attempt) return;
  S.login.browserOutcome = { attempt, ok: !!ok, text: String(text || "") };
}

export function doLogin() {
  if (S.busy) return;
  /* 条款未同意：登录是学校网络动作，拒绝后按钮已禁用，这里只兜底不强弹 */
  if (termsLocked()) {
    if (!S.terms.declined && !S.terms.unknown) openTerms();
    return;
  }
  /* 登录是异步尝试：先把当前登录结论整份存下来。取消/超时/窗口关闭/失败
   * 都整份回滚，只显示这次尝试的错误；只有真实成功才作废快照并等新锚点
   * （见 handleDone），不能把仍有效的旧凭证画成「登录已失效」。 */
  S.login.preLoginSnapshot = loginSnapshotState();
  S.login.loginPending = true;
  const attempt = (S.login.browserAttempt = (S.login.browserAttempt || 0) + 1);
  S.login.browserOutcome = null;
  setResult(null);
  setBusy(true);
  /* setBusy 会把 S.busy 置真；大屏据此会误判「报名计划在跑」，
   * 立刻重画一次，让登录尝试显示成「登录中」而不是「正在准备报名」。 */
  paintSelected();
  addLog("正在打开登录窗口，在弹出的浏览器里登完再回来…");
  api("login").then((res) => {
    if (res && res.demo) {
      /* 演示模式不打开学校登录页：如实说明，不当成登录失败（R20） */
      S.login.loginPending = false;
      S.login.preLoginSnapshot = null;
      settleBrowserOutcome(attempt, false, res.text || "演示模式不联网。");
      setBusy(false);
      setResult({ ok: "partial", title: "演示模式不登录", text: res.text || "演示模式不联网。" });
      return;
    }
    if (!res || res.ok === false) {
      S.login.loginPending = false;
      /* 登录窗口没起来 / 被忙碌或条款拦下：回滚到尝试前的结论，只留错误提示 */
      restoreLoginSnapshotState(S.login.preLoginSnapshot);
      S.login.preLoginSnapshot = null;
      settleBrowserOutcome(attempt, false, (res && res.text) || "登录没能开始，再试一次。");
      if (res && res.error && RUNTIME_ERRORS[res.error]) {
        /* FB4：登录的同步组件失败只挂横幅与唯一恢复入口，
         * 不再生成「登录没能开始」同义结果框；同时计入本轮刷新故障累计——
         * 刷新尚有分支未返回时，迟到的成功 check/list 不得撤掉这个新横幅 */
        noteRoundError(res.error);
        setBusy(false);
        syncLoginDependentView();
        return;
      }
      setBusy(false);
      syncLoginDependentView();
      setResult({ ok: false, kind: "login_attempt", title: "登录没能开始", text: (res && res.text) || "再点一次「登录」试试。" });
    }
  }).catch((err) => {
    S.login.loginPending = false;
    restoreLoginSnapshotState(S.login.preLoginSnapshot);
    S.login.preLoginSnapshot = null;
    settleBrowserOutcome(attempt, false, msg(err));
    setBusy(false);
    syncLoginDependentView();
    setResult({ ok: false, kind: "login_attempt", title: "登录没能开始", text: msg(err) });
  });
}

/* ---------------------------------------------------------------- 事件 */
export function handleDone(payload) {
  const data = payload || {};
  if (data.kind === "login") {
    const attempt = (S.login && S.login.browserAttempt) || 0;
    S.login.loginPending = false;
    setBusy(false);
    if (data.ok) {
      /* 登录成功=新会话已保存：作废尝试前快照，旧锚点立即清掉；紧接着的校验
       * 事件会带新锚点回来，这两秒里宁可显示未知，也不能拿旧凭证的剩余时间充数。 */
      S.login.preLoginSnapshot = null;
      settleBrowserOutcome(attempt, true, "");
      setLogin(null, true, true, { estimated_expires_at: null, saved_at: null });
      syncLoginDependentView();
      setResult({ ok: true, title: "登录成功", text: "正在加载活动列表。", autoClose: Date.now() + 6000 });
      doCheck();
      /* 登录成功后的刷新是程序自己发起的（U2/U3）：列表已有内容就走后台轮，失败不清列表和勾选；
       * 列表空着（常常正是因为没登录才空）走前台轮，才有骨架和错误空态可看 */
      refresh(true, S.items.length ? { background: true } : undefined);
    } else {
      /* 取消 / 超时 / 窗口关闭 / 登录失败：整份回滚到尝试前——旧会话仍然有效，
       * 不能因为这次没登成把胶囊画成「登录已失效」或丢掉剩余时间；
       * 只显示这次尝试的失败说明（present 也随快照回滚，不再单独保留）。 */
      restoreLoginSnapshotState(S.login.preLoginSnapshot);
      S.login.preLoginSnapshot = null;
      syncLoginDependentView();
      const copy = loginFailCopy(data.reason);
      settleBrowserOutcome(attempt, false, copy.title + "：" + copy.text);
      setResult({ ok: false, kind: "login_attempt", title: copy.title, text: copy.text, action: { label: "再试一次", run: doLogin } });
    }
    return;
  }
  if (data.kind === "grab") {
    setBusy(false);
    if (data.ok) setResult({ ok: true, title: "报名成功：" + stripLabel(data.label), text: "建议去活动页确认一眼。" });
    else setResult({ ok: false, title: "报名未成功：" + cleanReason(data.reason), text: grabHint(data.reason) });
  }
}

/* 登录失败：按 grab.py login 真会打印的句子归类，回答发生了什么+现在能做什么 */
export function loginFailCopy(reason) {
  const raw = String(reason || "");
  if (/窗口被关掉/.test(raw)) return { title: "登录窗口被关掉了", text: "登录还没完成，窗口就关了。点「再试一次」重新打开。" };
  if (/仍未检测到登录成功/.test(raw)) return { title: "等了 10 分钟还没登录成功", text: "浏览器窗口里一直没完成登录，超时了。点「再试一次」。" };
  if (/打不开登录页/.test(raw)) return { title: "打不开学校的登录页", text: "检查网络、校园网或代理，然后再试一次。" };
  if (/接口校验失败/.test(raw)) return { title: "登录后学校那边没校验通过", text: "登录状态存下来了，但学校那边没校验通过。再登录一次试试。" };
  if (/没找到可用的浏览器/.test(raw)) return { title: "没找到能用的浏览器", text: "这台电脑上要有 Chrome 或 Edge，装好以后再试。" };
  return { title: "登录没完成", text: cleanReason(raw) || "原因不明。可以再试一次，或者看看运行记录。" };
}

/* 运行时 checkpoint 字段：晚到的 plan 快照或恢复载荷缺这些字段时，
 * 不得用空值抹掉已经收到的真实事件（页面重载恢复与晚到 plan 事件共用）。 */
