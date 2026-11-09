/* 关窗三选：右上角 X 只是「请求关闭」，真正关不关由这里决定。
 *
 * 后端在 closing 事件里取消关闭并推 window_close_ask 过来；界面上给四个出口：
 * 先不关 / 最小化到任务栏 / 隐藏到后台 / 退出程序（原型 closeask 画板，
 * c3-dialogs-gap CW01–CW08、CW12、CW14）。勾了「以后都这样」就把选择写进
 * ui.json 的 window.close_action，下次点 X 直接照做（计划在跑时仍会先问）。
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

/* 打开后把焦点放到「最小化」（CW06，原型 Main:1818-1822 聚焦第一张选择卡）：
 * 卡序改成「最小化→隐藏→退出」后它就是第一张，也是三个出口里最轻、随时能回来的那一个。
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

/* 载荷里的 waiting_count（BE1）：缺字段（旧后端）返回 null，文案退回不带数字的说法 */
function closeWaitCount(data) {
  const raw = data ? data.waiting_count : null;
  const n = Number(raw);
  const present = raw !== undefined && raw !== null && raw !== "";
  return present && Number.isFinite(n) ? n : null;
}

/* 「还没提交的 N 场」：数字缺失时退回「还没提交的场次」（CW04/CW08） */
function closeWaitPhrase(waitingCount) {
  const n = Number(waitingCount);
  const present = waitingCount !== undefined && waitingCount !== null && waitingCount !== "";
  return present && Number.isFinite(n) ? "还没提交的 " + n + " 场" : "还没提交的场次";
}

/* 标题与副题随状态切换（CW02/CW12，原型 closeView Main:1724-1725）；确认步换一套 */
const CLOSE_HEAD_TEXT = {
  run: { title: "报名计划还在运行", sub: "最小化或隐藏都不影响计划，退出会停止它。" },
  idle: { title: "要关闭窗口吗？", sub: "选一个关闭方式。Esc 先不关。" },
  confirm: { title: "退出会停止报名计划", sub: "确定要退出吗？" },
};

function paintCloseHead(step) {
  const text = CLOSE_HEAD_TEXT[step] || CLOSE_HEAD_TEXT.idle;
  const title = document.getElementById("dlg-close-title");
  if (title) title.textContent = text.title;
  const body = document.getElementById("dlg-close-body");
  if (body) body.textContent = text.sub;
}

/* 利害清单（CW03，原型 .stakes Main:815、closeStake Main:1700-1710）：
 * 计划行写「N 场等开放，最近一批 HH:MM:SS」（BE1 载荷 waiting_count/next_batch_at），
 * 字段缺失时整行退回现有的「报名计划正在运行」；手机行已连接时挂绿点（li.ok）。
 * 空闲时不渲染整块（CW11 保持现状）。 */
function paintCloseStakes(data) {
  const running = document.getElementById("dlg-close-running");
  if (!running) return;
  const lines = [];
  if (data.plan_running) {
    const n = closeWaitCount(data);
    const nextAt = String(data.next_batch_at || "");
    if (n !== null && nextAt) {
      lines.push({ label: "报名计划", text: n + " 场等开放，最近一批 " + nextAt, tone: "" });
    } else {
      lines.push({ label: "报名计划", text: "正在运行", tone: "" });
    }
    if (data.phone_running) {
      lines.push({ label: "手机访问", tone: data.phone_live ? "ok" : "",
                   text: data.phone_live ? "手机已连接" : "手机访问开着" });
    }
  }
  running.innerHTML = lines.map((line) => {
    const cls = line.tone ? ' class="' + line.tone + '"' : "";
    return "<li" + cls + "><b>" + esc(line.label) + "</b><span>" + esc(line.text) + "</span></li>";
  }).join("");
  running.hidden = !lines.length;
}

/* 三张选择卡的正文（CW04/CW05/CW12，原型 closeView Main:1712-1721）：
 * 运行态推荐最小化、退出卡写清代价；空闲态换 CW12 那套；隐藏卡在托盘与手机
 * 都不可用时禁用并写原因（CW05）。 */
function paintCloseChoices(data) {
  const minText = document.getElementById("close-min-text");
  if (minText) {
    minText.textContent = data.plan_running
      ? "窗口缩到任务栏，计划和手机访问都照常。"
      : "窗口缩到任务栏，点一下就回来。";
  }
  const hideText = document.getElementById("close-hide-text");
  if (hideText) {
    hideText.textContent = "窗口不见了，工具在后台继续运行。从右下角托盘图标" +
      (data.phone_live ? "或手机页" : "") + "叫回来。";
  }
  const hide = document.getElementById("btn-close-hide");
  const hideWhy = document.getElementById("close-hide-why");
  /* 老载荷没有 tray_ok 字段：按可用处理，交给后端 hide_window 再把一次门 */
  const cannotHide = data.tray_ok === false && !data.phone_live;
  if (hide) hide.disabled = cannotHide;
  if (hideWhy) {
    hideWhy.hidden = !cannotHide;
    hideWhy.textContent = cannotHide ? "现在叫不回来：托盘图标没建起来，手机也没连着，所以不能隐藏。" : "";
  }
  const rec = document.getElementById("close-rec");
  if (rec) rec.hidden = !data.plan_running;
  const exitText = document.getElementById("close-exit-text");
  if (exitText) {
    exitText.textContent = data.plan_running
      ? "报名计划会停止，" + closeWaitPhrase(data.waiting_count) + "不会再报名。" +
        (data.phone_running ? "手机也会断开。" : "")
      : "登录状态会保留，下次打开不用重新登录。";
  }
}

/* 确认步是否在前台：以确认段本身的显隐为准，不引入新状态
 * （替身/旧内核缺元素时按选择步算，Esc 语义退回「先不关」）。 */
function closeConfirmShown() {
  const box = document.getElementById("dlg-close-confirm");
  return !!(box && !box.hidden);
}

/* 确认步切换（CW07，原型 closePick Main:1742-1752、closeBack Main:2447）：
 * 进确认步：隐藏选择卡与选择步脚部（勾选、先不关），确认段与两钮上前台，焦点落「返回」；
 * 退回选择步：反过来（焦点由调用方还给第一张选择卡）。 */
function showCloseConfirm(show) {
  const state = S.closeAsk || {};
  const box = document.getElementById("dlg-close-confirm");
  const choices = document.getElementById("dlg-close-choices");
  if (box) box.hidden = !show;
  if (choices) choices.hidden = show;
  const rememberRow = document.getElementById("dlg-close-remember-row");
  if (rememberRow) rememberRow.hidden = show;
  const cancel = document.getElementById("btn-close-cancel");
  if (cancel) cancel.hidden = show;
  const back = document.getElementById("btn-close-exit-back");
  if (back) back.hidden = !show;
  const yes = document.getElementById("btn-close-exit-confirm");
  if (yes) yes.hidden = !show;
  paintCloseHead(show ? "confirm" : (state.planRunning ? "run" : "idle"));
  if (show) {
    /* CW08 确认正文（原型 Main:1722）：数字取 BE1 载荷，缺字段退回「场次」 */
    if (box) box.textContent = closeWaitPhrase(state.waitingCount) + "不会再报名。已经成功的报名不受影响。";
    if (back && typeof back.focus === "function") {
      try {
        back.focus();
      } catch (error) {
        /* 焦点失败不拦流程（同 focusSafestClose 的口径） */
      }
    }
  }
}

/* 打开三选（决策 014 设计 9.1；c3-dialogs-gap CW01–CW06、CW11、CW12）。
 * 先按状态铺利害清单与三张卡，再开弹窗并聚焦第一张选择卡（最小化）；
 * 计划运行时标「推荐」，退出要再确认一次；托盘不可用且手机没连时「隐藏到后台」禁用并写原因。 */
function openWindowCloseDialog(payload) {
  const data = payload || {};
  const dlg = closeDialogEl();
  if (!dlg) return;
  S.closeAsk = { planRunning: !!data.plan_running, waitingCount: data.waiting_count };
  paintCloseStakes(data);
  paintCloseChoices(data);
  showCloseConfirm(false);   /* 每次打开都回到选择步（CW07） */
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
  const dlg = closeDialogEl();
  const cancel = document.getElementById("btn-close-cancel");
  if (cancel) cancel.addEventListener("click", () => hideWindowCloseDialog());
  const hide = document.getElementById("btn-close-hide");
  if (hide) hide.addEventListener("click", () => { void submitWindowClose("hide"); });
  const minimize = document.getElementById("btn-close-minimize");
  if (minimize) minimize.addEventListener("click", () => { void submitWindowClose("minimize"); });
  const exit = document.getElementById("btn-close-exit");
  if (exit) {
    exit.addEventListener("click", () => {
      /* 计划运行中退出要二次确认：先换成确认步（CW07），用户点「停止计划并退出」才真的退 */
      if (S.closeAsk && S.closeAsk.planRunning) {
        showCloseConfirm(true);
        return;
      }
      void submitWindowClose("exit");
    });
  }
  const exitConfirm = document.getElementById("btn-close-exit-confirm");
  if (exitConfirm) exitConfirm.addEventListener("click", () => { void submitWindowClose("exit"); });
  const exitBack = document.getElementById("btn-close-exit-back");
  if (exitBack) {
    exitBack.addEventListener("click", () => {
      showCloseConfirm(false);
      focusSafestClose(closeDialogEl());
    });
  }
  /* CW06（原型 closeKey，Main:2446-2448）：Esc 只属于关窗框。
   * keydown 捕获在 dialog 元素上 stopPropagation——挡住 app.js 的全局 Esc 链
   * （引导→气泡→状态卡→设置→输入→结果→清空已选活动），关窗时绝不能顺手清掉勾选；
   * 确认步 Esc 回选择步（preventDefault 拦下原生 cancel 后自己切），选择步 Esc
   * 交给 <dialog> 原生 cancel 静默关闭，等价「先不关」、不发任何动作。 */
  if (dlg && typeof dlg.addEventListener === "function") {
    dlg.addEventListener("keydown", (event) => {
      if (!event || event.key !== "Escape") return;
      if (typeof event.stopPropagation === "function") event.stopPropagation();
      if (closeConfirmShown()) {
        if (typeof event.preventDefault === "function") event.preventDefault();
        showCloseConfirm(false);
        focusSafestClose(closeDialogEl());
      }
    }, true);
    dlg.addEventListener("cancel", (event) => {
      /* 没经 keydown 的 cancel（内核直接派发）：同样只在确认步拦下回选择步 */
      if (!closeConfirmShown()) return;
      if (typeof event.preventDefault === "function") event.preventDefault();
      showCloseConfirm(false);
      focusSafestClose(closeDialogEl());
    });
  }
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
