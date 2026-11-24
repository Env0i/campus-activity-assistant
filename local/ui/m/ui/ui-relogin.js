"use strict";

/* 手机页 DOM 层——重新登录流程与重登面板（依赖 model*.js、ui-session.js、ui-status.js 先加载）：
 * 负责重登面板呈现、打开重登抽屉、验证码控制、提交/取消/换图与流程状态摄入。 */

/* RL01–RL08 重登 sheet 渲染（原型 sh.isRelogin 段，Phone.dc.html:326-350）：
   取值全在 PhoneModel.reloginView，这里只写 DOM；面板显隐由 openSheet/closeSheet 管，
   refreshControls 每次都重画一遍（忙态、主钮与附言随模型走） */
function renderRelogin() {
  if (model.sheetId === "relogin") {
    $("sheet-title").textContent = PhoneModel.loginCopy(
      model.relFirstLogin ? "never" : "expired", false).reloginEntry;
  }
  const view = PhoneModel.reloginView(model.flow, model.reloginSetup, {
    confirm: model.relConfirm,
    starting: model.reloginStarting,
    submitting: model.reloginSubmitting,
    entered: model.relEnteredAcct,
    savedChoice: model.relSavedChoice,
    planBusy: model.busy,
    firstLogin: !!model.relFirstLogin,
  });
  $("rel-err").textContent = view.err;
  $("rel-err").hidden = !view.err;
  $("rel-spin").hidden = !view.spin;
  $("rel-busy-text").textContent = view.spin;
  $("rel-text").textContent = view.text;
  $("rel-text").hidden = !view.text;
  $("rel-form").hidden = !view.showForm;
  $("rel-lead").textContent = view.lead;
  $("rel-lead").hidden = !view.lead;
  $("relogin-account").hidden = !view.needAcct;
  $("relogin-captcha-group").hidden = !view.needCap;
  $("rel-auto").hidden = !view.autoCap;
  $("rel-save-gain").textContent = view.saveLine;
  /* 主钮三选一（原型 rel.submitLabel 槽）：登录 / 提交验证码 / 自动登录一次 */
  $("btn-relogin-auto").hidden = view.mainKind !== "auto";
  $("btn-relogin").hidden = view.mainKind !== "begin";
  $("btn-relogin-submit").hidden = view.mainKind !== "submit";
  $("rel-second-row").hidden = !(view.refresh || view.cancel);
  $("btn-relogin-refresh").hidden = !view.refresh;
  $("btn-relogin-cancel").hidden = !view.cancel;
  $("btn-relogin-done").hidden = !view.done;
  $("btn-relogin-done").textContent = view.done;
}

/* 重登 sheet 的入口（更多面板「在手机上重新登录」钮）：按 relogin_setup 决定先看哪一态——
   电脑存着账号且装了识别 → RL06 确认层（原型 beginRelogin 的 confirm 分支，Phone:654）；
   保存的密码不对 → RL07 relbad；有在途流程直接回到现场（RL01/RL03）。
   原型对「存了账号但没装识别」在 opener 上直接 begin（Phone:655）；这里留在表单初态
   由「登录」显式开始，不在导航点击里偷发写请求（偏差已记 result） */
function openRelogin() {
  /* A-P1：openSheet 的「一次一张」守卫会拦掉从 more/review/confirm 直接切到重登，
     更多面板里的入口钮就点不动。切换语义：先收旧 sheet（确认档/重登确认层随
     收起），已在重登 sheet 则不重开。 */
  if (model.sheetId === "relogin") return;
  if (model.sheetId) closeSheet(true);
  const flow = model.flow;
  const liveFlow = !!(flow && flow.live
    && ["starting", "waiting_code", "verifying"].indexOf(String(flow.state || "")) >= 0);
  const setup = model.reloginSetup || {};
  model.relFirstLogin = PhoneModel.loginState(model.login) === "never";
  model.relConfirm = !liveFlow && !setup.paused && !!setup.saved && !!setup.ocr_ready;
  openSheet("relogin");
  renderRelogin();
}

/* ---- 重新登录 ---- */
/* 流程结束（成功或中断）：收起整组验证码输入，只留"重新开始"入口 */

/* 流程收尾（成功/失败/取消/auto 接手）：收掉本场验证码图；
   表单与按钮的显隐由 renderRelogin 按 reloginView 重画（refreshControls 里调用） */
function endReloginControls() {
  $("captcha").hidden = true;
  $("captcha").removeAttribute("src");
}
function ingestRelogin(info) {
  model.flow = info;
  const relayState = String(info.state || "");
  if (String(info.mode || "") === "auto"
      && relayState !== "success" && relayState !== "failed" && relayState !== "canceled") {
    // 电脑自己认图：手机不给验证码，也就不可能和电脑抢同一张图。
    // 这里只报进度；连续失败到阈值后服务端会把 mode 换成 manual，图自然会来。
    // （auto 的终态落到底下各自的分支：RL03 只描述「正在进行」）
    const rounds = Math.max(Number(info.attempts || 0), Number(info.auto_failures || 0));
    if (info.retrying) {
      $("relogin-note").textContent = "电脑正在自动登录" +
        (rounds > 0 ? "（第 " + (rounds + 1) + " 次）" : "") + "…";
    } else {
      $("relogin-note").textContent =
        "电脑会自动识别验证码；连续失败几次之后才会转到这里手动输入";
    }
    model.challenge = null;
    model.reloginSubmitting = false;
    model.reloginStarting = false;
    endReloginControls();
    refreshControls();
    return;
  }
  if (relayState === "waiting_code" && info.challenge_id) {
    if (PhoneModel.matchesChallenge(model.challenge, info.flow_id, info.challenge_id)) {
      // 对账同一张图：服务端确认没有在途提交才解除自锁，否则继续等着
      if (!info.submit_pending) model.reloginSubmitting = false;
      refreshControls();
      return;
    }
    model.challenge = {
      flow_id: info.flow_id, challenge_id: info.challenge_id,
    };
    model.reloginSubmitting = false;
    const img = $("captcha");
    if (String(info.image || "").indexOf("data:image/png;base64,") === 0) {
      img.src = info.image;
      img.hidden = false;
    } else {
      img.hidden = true;
      img.removeAttribute("src");
    }
    $("code").value = "";
    refreshControls();   // renderRelogin：RL01 captcha 态（图+输入+三钮）
    return;
  }
  if (relayState === "verifying") {
    // 提交已经被 worker 收下、正在校验：RL02 归并成「正在登录，请等结果」，
    // 整组收起 + sheet 加锁（sheetBusy），想对同一张图重发也没有入口
    model.reloginSubmitting = false;
    $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;
  } else if (relayState === "starting") {
    // 进程刚起来还没出验证码：RL02 按档给「正在向电脑要验证码…」/「正在准备…」
    model.reloginSubmitting = false;
    $("relogin-note").textContent = String(info.mode || "") === "auto"
      ? PhoneModel.RELOGIN_BUSY.prepare : PhoneModel.RELOGIN_BUSY.needCode;
  } else if (relayState === "success") {
    model.challenge = null;
    model.reloginSubmitting = false;
    endReloginControls();
    if (info.live) {
      /* RL08（原型 Phone:892-894）：完成态两套文案；计划在跑＝照常继续，闲时按打开面板时记下的 relFirstLogin 取句 */
      $("relogin-note").textContent = PhoneModel.loginDoneText(!!model.relFirstLogin, model.busy);
      void poll(true);
    } else {
      // 中继在空闲时会回上一场的结论：那是历史，不是这一次。只按 live 播报，
      // 否则每次打开手机页都会把很早以前那一次成功再演一遍。
      $("relogin-note").textContent = "上次重新登录已完成；需要时点「重新登录」再试";
    }
  } else if (relayState === "failed" || relayState === "canceled") {
    model.challenge = null;
    model.reloginSubmitting = false;
    endReloginControls();
    const reason = String(info.safe_error || relayState);
    /* B-P2-1：bad_password 走原型整句（两处「结束」呈现同一映射），其余码保留前缀+码 */
    $("relogin-note").textContent = info.live
      ? PhoneModel.reloginFailText(reason)
      : PhoneModel.reloginFailText(reason, "上次重新登录未完成：");
  } else if (relayState && relayState !== "waiting_code") {
    // idle 表示「本来就没有在进行的重新登录」，不是一次结束：写成「重新登录结束：idle」
    // 会把上一次真正的原因（比如 bad_csrf、凭据没准备好）盖成一句空话。
    model.challenge = null;
    model.reloginSubmitting = false;
    endReloginControls();
  }
  refreshControls();
}
async function beginRelogin() {
  // 单飞：连点两下也只是同一次开始，不会发出第二个 POST
  if (model.reloginStarting) return;
  // 新的一次开始先清上一轮的红条，失败原因由下面按分支写回抽屉
  showSheetError("");
  if (!canWrite()) { setBanner("状态已过时，先刷新再重新登录", "stale_action"); return; }
  model.reloginStarting = true;
  /* RL06：确认层用完即收；RL08 附言：先清上一轮的「输过账号/勾了保存」 */
  model.relConfirm = false;
  model.relEnteredAcct = false;
  model.relSavedChoice = false;
  refreshControls();
  /* 手机上输了账号密码就带上（默认不保存，勾选才保存到电脑）；没输就用电脑上保存的 */
  const args = {};
  const account = $("relogin-account");
  if (account && !account.hidden) {
    const user = String(($("relogin-user") || {}).value || "").trim();
    const pass = String(($("relogin-pass") || {}).value || "");
    if (!user || !pass) {
      // 主钮已按 relCanSubmit 禁用，这里是直调/竞态的保险丝
      model.reloginStarting = false;
      $("relogin-note").textContent = "账号和密码都要填。";
      showSheetError("账号和密码都要填。");
      refreshControls();
      return;
    }
    args.username = user;
    args.password = pass;
    args.save = !!($("relogin-save") || {}).checked;
    model.relEnteredAcct = true;       // RL08 附言：这一轮输过账号
    model.relSavedChoice = args.save;
    $("relogin-pass").value = "";
  }
  const { body } = await postAction({ action: "phone_relogin_begin", args: args });
  model.reloginStarting = false;
  if (!body || !body.ok) {
    /* 失败原因两处都写：更多面板的后台行 + 重登抽屉里的红条；
       抽屉打开时 #relogin-note 被面板挡住，只写它会像点了没反应 */
    const text = body && body.error === "plan_late"
      ? "现在来不及重新登录：" + String(body.text || "有场次正在提交，或者离开放不到 100 秒。")
      : "还不能开始：" + String((body && body.text) || (body && body.error) || "请到电脑上准备账号");
    $("relogin-note").textContent = text;
    showSheetError(text);
    refreshControls();
    return;
  }
  if (String(body.mode || "") === "auto") {
    // 电脑接手了：手机不进入验证码流程，只等快照回报进度
    $("relogin-note").textContent = "电脑正在自动登录，手机上不用再操作";
    refreshControls();
    void poll(true);
    return;
  }
  /* RL02：旧句「等待验证码…」归并为「正在向电脑要验证码…」，快照马上接管 */
  $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.needCode;
  refreshControls();
  void poll(true);
}
async function submitRelogin() {
  const code = String($("code").value || "").trim();
  if (!model.flow || !model.challenge) return;
  if (!PhoneModel.canSubmitRelogin(model, model.challenge)) return;
  if (!PhoneModel.relCanSubmit({ needCap: true, code })) return;   // relCanSubmit（原型 Phone:675）：4 位才发
  // 新的一次提交先清上一轮的红条
  showSheetError("");
  if (!PhoneModel.matchesChallenge(model.flow, model.challenge.flow_id,
                                   model.challenge.challenge_id)) {
    $("relogin-note").textContent = "验证码已换代，请看新图";
    showSheetError("验证码已换代，请看新图");
    $("code").value = "";
    return;
  }
  model.reloginSubmitting = true;
  refreshControls();   // renderRelogin：RL02「正在登录，请等结果」+ sheet 锁定
  let result;
  try {
    result = await api("/api/action", { method: "POST",
      body: { action: "phone_relogin_submit", args: {
        flow_id: model.challenge.flow_id,
        challenge_id: model.challenge.challenge_id, code } } });
  } catch (err) {
    // 结果未知：既不能当成功也不能当失败。保持禁用，先对账问服务端
    // 这张图到底有没有在途提交，等快照给结论再决定放行还是收口。
    // RL02：旧句「提交结果未知，正在对账…」归并为「正在登录，请等结果」
    $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;
    void poll(true);
    return;
  }
  if (!result || result.status !== 200 || !result.body || !result.body.ok) {
    const error = String((result && result.body && result.body.error) || "");
    if (error === "duplicate_submit") {
      // 服务端说同一张图还有在途提交：别解锁，等它的结论再放行
      // RL02：旧句「验证码正在提交，请等待结果」同样归并进「正在登录，请等结果」
      $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;
      void poll(true);
      return;
    }
    model.reloginSubmitting = false;
    const text = String(
      (result && result.body && (result.body.text || result.body.error))
        || "提交没有被接受");
    $("relogin-note").textContent = text;
    showSheetError(text);
    refreshControls();
    return;
  }
  $("code").value = "";
  void poll(true);
}
async function cancelRelogin() {
  const flow = model.flow;
  const flowId = flow && String(flow.flow_id || "");
  /* 没有在途流程（表单初态/确认层）取消只是收起：不发无谓的 cancel POST；
     终态的历史现场（live=false）同样没有东西可撤 */
  if (!flowId || (flow && flow.live === false)) return true;
  const { body } = await postAction({
    action: "phone_relogin_cancel", args: { flow_id: flowId } });
  if (body && body.error) {
    // 取消没发出去就不能假装已经取消：留着旧图，让用户重试
    const text = "没能取消这次重新登录：" + String(body.text || body.error);
    addLog(text);
    showSheetError(text);
    return false;
  }
  model.challenge = null;
  $("captcha").hidden = true;
  void poll(true);
  return true;
}
/* 换一张图 = 取消旧场 + 开始新场；旧场不撤掉会被服务端判成同一个挑战 */
async function refreshRelogin() {
  const canceled = await cancelRelogin();
  // 旧场没撤掉就开新场，服务端会判成同一个挑战：宁可不换图
  if (canceled === false) return;
  await beginRelogin();
}
