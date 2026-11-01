/* 关窗三选：右上角 X 只是「请求关闭」，真正关不关由这里决定。
 *
 * 后端在 closing 事件里取消关闭并推 window_close_ask 过来；界面上给四个出口：
 * 先不关 / 隐藏到后台运行 / 最小化到任务栏 / 直接退出。勾了「以后都这样」就把
 * 选择写进 ui.json 的 window.close_action，下次点 X 直接照做（计划在跑时仍会先问）。
 *
 * 「隐藏到后台」和「最小化」的区别：隐藏之后任务栏上没有按钮，程序在托盘里，
 * 手机访问和报名计划继续跑；最小化只是把窗口缩下去。
 */

function closeDialogEl() {
  return document.getElementById("dlg-close");
}

function closeDialogOpen() {
  const dlg = closeDialogEl();
  return !!(dlg && dlg.open);
}

/* 打开后把焦点放到「最小化」：三个出口里最轻、随时能回来的那一个。
 * 取不到元素、替身没有 focus、或者旧内核不许聚焦——一律静默跳过：
 * 焦点不是关窗流程的必需品，绝不能因为聚焦失败让人卡在弹窗里。 */
function focusSafestClose(dlg) {
  const target = document.getElementById("btn-close-minimize");
  if (!target || typeof target.focus !== "function") return;
  try {
    target.focus();
  } catch (error) {
    /* 元素还没上树或替身没实现 focus：忽略 */
  }
}

/* 打开三选。payload.plan_running 为真时把话说重一点：这时候退出会带走计划。 */
function openWindowCloseDialog(payload) {
  const data = payload || {};
  const dlg = closeDialogEl();
  if (!dlg) return;
  const body = document.getElementById("dlg-close-body");
  if (body) {
    body.textContent = data.plan_running
      ? "报名计划正在运行：退出会停掉计划，手机立刻失去访问。建议隐藏到后台，让它继续跑。"
      : "退出后手机访问和电脑端的推送、自动报名都会停。想让它继续干活就选「隐藏到后台运行」。";
  }
  const remember = document.getElementById("dlg-close-remember");
  if (remember) remember.checked = false;
  const minimize = document.getElementById("btn-close-minimize");
  if (minimize) minimize.disabled = false;
  if (typeof dlg.showModal === "function") {
    if (!dlg.open) dlg.showModal();
  } else {
    dlg.setAttribute("open", "");
  }
  focusSafestClose(dlg);
}

function hideWindowCloseDialog() {
  const dlg = closeDialogEl();
  if (!dlg) return;
  if (typeof dlg.close === "function" && dlg.open) dlg.close();
  else dlg.removeAttribute("open");
}

/* 把选择交给后端：先隐藏弹窗，再发请求；失败只记一条日志，不弹二次确认 */
function submitWindowClose(action) {
  const remember = document.getElementById("dlg-close-remember");
  const verb = remember && remember.checked ? "remember_" : "";
  hideWindowCloseDialog();
  return api("request_window_close", verb + action).then((res) => {
    if (res && res.ok === false) {
      addLog("[X] " + String(res.text || "关闭动作没有生效"));
    }
    return res;
  }).catch((error) => {
    addLog("[X] 关闭动作失败：" + msg(error));
  });
}

function wireWindowClose() {
  const cancel = document.getElementById("btn-close-cancel");
  if (cancel) cancel.addEventListener("click", () => hideWindowCloseDialog());
  const hide = document.getElementById("btn-close-hide");
  if (hide) hide.addEventListener("click", () => { void submitWindowClose("hide"); });
  const minimize = document.getElementById("btn-close-minimize");
  if (minimize) minimize.addEventListener("click", () => { void submitWindowClose("minimize"); });
  const exit = document.getElementById("btn-close-exit");
  if (exit) exit.addEventListener("click", () => { void submitWindowClose("exit"); });
}

/* 测试替身里的 document 只有一部分接口：取不到元素就跳过接线，
 * 绝不让「关窗弹窗没接上」把整个界面的脚本执行拖崩。 */
if (typeof document !== "undefined" && typeof document.getElementById === "function") {
  try {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", wireWindowClose);
    } else {
      wireWindowClose();
    }
  } catch (error) {
    /* 测试替身缺 addEventListener / 元素替身不带方法：静默跳过 */
  }
}
