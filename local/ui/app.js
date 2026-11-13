"use strict";

/* 校园活动预报名工具：界面逻辑。
 * 只按 local/app.py 的真实契约说话：
 *   调用  window.pywebview.api.bootstrap / check / list_activities / login / start_plan /
 *         cancel_task / stop_plan / open_data / save_prefs / front_ready
 *   事件  window.onBackend.log / check / activities / done / plan / task / plan_done
 * 多活动计划由 signup_plan.py 协调；视觉语言参照 design/prototype（候车厅 + 时刻表 + LED 大屏），
 * 但状态机以多活动业务为准，不回退单活动模型。 */

async function boot() {
  const bridgeReady = await waitForBridge();
  const bootStarted = _monoMs();
  const info = bridgeReady ? await api("bootstrap").catch(() => null) : null;
  const bootRtt = _monoMs() - bootStarted;
  fillHelp((info && info.help) || DEFAULT_HELP);
  /* 当前版本唯一显示位，来自后端；打开帮助不代表已查询GitHub。 */
  $("#help-version").textContent = info && info.version ? String(info.version) : "—";
  restoreUpdate(info && info.update_check);
  if (info) {
    /* demo 标记由后端 bootstrap 带来：演示模式绕过「登录校验 valid」的开始门禁 */
    S.demo = !!info.demo;
    /* 生命周期快照（上次关闭时长/质量、登录估算）：只进时钟浮层当提示，
     * 不参与登录四态判定，也不影响开始门禁 */
    S.lifecycle = info.lifecycle || null;
    /* MG01/MG02：本次进程真发生过旧数据迁移才有 bootstrap.migration；
     * 运行记录照原型 Main:1182/1183，null 不写（N 用后端真实的 moved） */
    S.migration = info.migration || null;
    if (S.migration) {
      /* 按实际结果分四种：全成功 / 只登录失败 / 登录和其他都失败 / 只其他失败 */
      const mg = S.migration;
      addLog(mg.login_failed && mg.other_failed
        ? "[!] 旧版本的数据没能搬过来，旧文件还在原来的位置"
        : mg.login_failed
          ? "[!] 旧版本的登录信息没能搬过来，其他数据已搬好"
          : mg.other_failed
            ? "[!] 旧版本的设置或运行记录没能搬过来，登录信息已搬好"
            : "已把 " + (Number(mg.moved) || 0) + " 个旧数据文件搬到新的数据目录");
    }
    /* 三种重试模式的权威选项与默认值：桌面/手机共用 bootstrap 口径，
     * 覆盖 store.js 的离线兜底副本（两者由用例对照，不各写一套） */
    if (info.retry_options && info.retry_options.choices) S.retryOptions = info.retry_options;
    /* 高级功能快照（含保存的账号、验证码识别）：开始前提醒据此判断「自动登录开没开」 */
    S.advanced = info.advanced_features || null;
    applyPrefs(info.prefs || {});
    /* 条款快照（bootstrap.terms）：未同意时拦下后面的首轮自动加载；
     * 首次（且本版本从未拒绝过）弹一次条款，之后只留横幅入口不强弹 */
    ingestTerms(info.terms);
    /* 独立北京时间：bootstrap 权威快照建立锚点（决策 012），
     * 桥接往返计入误差；随后由后台轮询接管后续快照 */
    ingestBusinessClock(info.business_clock, { authoritative: true, rttMs: bootRtt });
    S.businessClock.attempted = true;
    setLogin(info.login && info.login.hours_left, null,
             loginPresent(info.login, !!info.demo), info.login);
    setBusy(!!info.busy);
    ingestBootstrapPlan(info);
    /* 首次使用：五步引导代替一次性静态弹窗——但条款决定更早：未同意/未知
     * 时欢迎与引导都延后到同意后只继续一次；「暂不使用」过（declined）本
     * 会话不再自动开引导；绝不写 tour_version（看过与否只由引导自己落盘）。 */
    const tourWillAuto = tourShouldAutoStart();
    const firstRun = !S.prefs.welcome_seen;
    if (firstRun) savePrefs({ welcome_seen: true });
    if (termsLocked()) {
      S.terms.deferredIntro = {
        tour: !S.terms.declined && tourWillAuto,
        welcome: firstRun && !tourWillAuto,
      };
    } else {
      if (firstRun && !tourWillAuto) showHelp();
      if (tourWillAuto) requestAutoTour();
    }
  } else {
    /* 拿不到 bootstrap：条款状态也无从而知，按未知处理（fail closed），
     * 学校动作交给后端门禁 + 前端横幅双重拦住 */
    markTermsUnknown();
    setLogin(null, null);
    S.listState = "idle";
    render();
  }
  if (hasBridge()) {
    api("front_ready").catch(() => {});
    startClockPolling();
    pollClockNow();
    refresh(true);
    startAutoRefresh();   /* 活动列表每 10 分钟后台自动刷新（条件见 controllers/refresh.js） */
  }
}


window.onBackend = {
  log: (line) => addLog(line),
  /* 点右上角 X：后端取消了关闭，改为让用户选「最小化 / 退出」 */
  window_close_ask: (payload) => openWindowCloseDialog(payload),
  check: (payload) => {
    const data = payload || {};
    /* 旧轮迟到：不能覆盖新一轮的检查结论（R11）。先有界暂存，
     * 等 skipped ack 接续回这个 owner 再重放一次。 */
    if (data.request_id && S.round.check && data.request_id !== S.round.check) {
      cacheRoundPayload("check", data.request_id, data);
      return;
    }
    if (data.request_id && !markRoundApplied("check", data.request_id)) return;
    if (data.request_id && data.request_id === S.round.check) {
      clearTimeout(S.round.checkTimer);
    }
    /* 真实校验回来了：解除「检查中」，记下四态结论（valid/none/expired/unknown） */
    S.login.checking = false;
    S.login.result = data.result || null;
    /* FB4：组件结论按刷新轮次处理——本轮 check 报组件故障立即挂横幅并计入
     * 故障累计（另一分支成功/普通 unknown 不得撤）；本轮 check 无故障只收口
     * 自己的分支，撤横幅必须等本轮两分支都完成（两到达顺序语义一致） */
    const code = data.runtime_error || null;
    if (code && RUNTIME_ERRORS[code]) {
      S.runtime.roundError = code;
      S.runtime.error = code;
      S.runtime.checkPending = false;
    } else if (S.runtime.checkPending) {
      S.runtime.checkPending = false;
      if (!S.runtime.listPending) S.runtime.error = S.runtime.roundError;
    }
    if (data.demo) S.demo = true;
    /* demo 的 session_present 是 null（没有真实会话）：不能 !! 成 false，
     * 否则会走「首次未登录」板面，把演示样例全遮住（C07） */
    setLogin(data.hours_left, !!data.ok, loginPresent(data, !!data.demo), data);
    if (data.result === "valid" && firstNotice("check", data.request_id, "valid")) {
      addLog("[OK] 已复用本机登录态，学校接口校验通过");
    }
    /* 时钟只认结构化载荷：没有结论就落 unknown，绝不从文本猜「慢几秒」（R08） */
    applyClock(data.clock);
    /* 静默恢复中（recovering）不刷失败日志：登录失效这件事已由「自动登录中」表达，
     * 用户不需要看到一条他没法处理的错误。静默失败、转人工后照常记。 */
    if (!data.ok && !data.recovering && firstNotice("check", data.request_id, "fail")) {
      const reason = String(data.reason || data.text || "登录状态检查没通过");
      addLog(reason.startsWith("[X]") ? reason : "[X] " + reason);
    }
    paintBanners();     /* 组件横幅随 check 结论出现/撤销 */
    paintChecks();
    /* 同一轮校验结论统一收口：胶囊、时钟、大屏、路线、列表空态与各倒计时
     * 一起刷新，不留「胶囊更新了、倒计时还是旧的」混合态（上面的 request_id
     * 代次校验已保证只有本轮结果能走到这里）。 */
    syncLoginDependentView();
    maybeStartTour();   /* 登录确认有效后，等着的首次引导看看能不能开始 */
    /* 重新登录成功也会走这条 check 事件：顶栏换了，右侧「电脑续登录」卡片还是旧
     * 记录（最近一次登录/账号状态）。顺手让手机面板重取一次自己的快照，
     * 失败就静默——卡片陈旧不该影响登录结论本身。 */
    if (window.PhonePanel && typeof window.PhonePanel.refresh === "function") {
      try { window.PhonePanel.refresh(); } catch (error) { /* 面板刷新失败不干扰 check */ }
    }
  },
  activities: (payload) => applyActivities(payload, false),
  done: (payload) => handleDone(payload),
  business_clock: (payload) => {
    /* 事件只作「重取通知」：先落地推送内容，再向本机取一次带往返测量的权威快照 */
    ingestBusinessClock(payload);
    pollClockNow();
  },
  plan: (payload) => handlePlan(payload),
  task: (payload) => handleTask(payload),
  plan_done: (payload) => handlePlanDone(payload),
  /* GL01 防止开两份：第二份启动时后端切回这个窗口并推此事件，payload { at: 业务时钟秒 | null } */
  second_open: (payload) => receiveSecondOpen(payload),
  update: (payload) => receiveUpdate(payload),
  /* 重新登录这一场的进度（电脑和手机共用的中继流程）：对话框开着时接管画面 */
  phone_relogin: (payload) => receiveReloginState(payload),
};

bindPlaceToggle();

$("#q").addEventListener("input", (event) => setFilter("q", event.target.value));
$("#chips").addEventListener("click", (event) => {
  const chip = event.target.closest(".chip");
  if (chip) { setFilter("status", chip.dataset.status); paintChips(); }
});
/* LS06 更多筛选：折叠按钮开合下拉面板，展开状态记进偏好 */
$("#btn-more").addEventListener("click", () => setFilterOpen(!S.filterOpen));
$("#time").addEventListener("change", (event) => setFilter("time", event.target.value));
$("#sort").addEventListener("change", (event) => setFilter("sort", event.target.value));
$("#checkin").addEventListener("change", (event) => setFilter("checkin", event.target.value));
$("#checkout").addEventListener("change", (event) => setFilter("checkout", event.target.value));
$("#rows").addEventListener("change", (event) => {
  const check = event.target.closest(".row-check");
  if (check) toggleSelection(check.dataset.id, check.checked);
});
$("#rows").addEventListener("click", (event) => {
  /* 取消报名：按钮只展开确认块；确认块里「不取消」不调接口，只有「确认取消报名」才调（controllers/cancel.js） */
  const cancelBtn = event.target.closest("[data-cancel]");
  if (cancelBtn) { cancelAsk(cancelBtn.dataset.cancel); return; }
  const cancelNo = event.target.closest("[data-cancel-no]");
  if (cancelNo) { cancelAskDismiss(); return; }
  const cancelYes = event.target.closest("[data-cancel-yes]");
  if (cancelYes) { cancelConfirm(cancelYes.dataset.cancelYes); return; }
  if (event.target.closest(".rx")) return;
  if (event.target.closest(".row-check")) return;
  /* 地点是独立可聚焦控件：点它只展开/收起完整文本，不改变选择 */
  const place = event.target.closest(".c-place");
  if (place) { togglePlace(place); return; }
  const row = event.target.closest(".row");
  if (!row) return;
  const check = row.querySelector(".row-check");
  if (check && !check.disabled) { check.checked = !check.checked; toggleSelection(check.dataset.id, check.checked); }
});
/* 键盘展开地点：Enter / Space 只翻转 aria-expanded，不触发开始计划或勾选 */
$("#rows").addEventListener("keydown", (event) => {
  /* 「不可加入」标签上的键盘：Esc 收气泡，Enter / 空格把焦点移进气泡里的链接 */
  if (event.target.closest && event.target.closest(".state-clash")) { tipKey(event); return; }
  const place = event.target.closest(".c-place");
  if (!place) return;
  if (event.key !== "Enter" && event.key !== " " && event.key !== "Spacebar") return;
  event.preventDefault();
  togglePlace(place);
});
/* 「不可加入」气泡：只有指针停在标签上（或聚焦标签）才开；扫过整行不弹，
 * 否则冲突行多时会一个接一个地冒。移开稍等收起；鼠标进了气泡就不收 */
$("#rows").addEventListener("mouseover", (event) => {
  const tag = event.target.closest(".state-clash");
  if (tag && tag.closest(".row")) tipSoon(tag.closest(".row").dataset.id);
  else tipLater();
});
$("#rows").addEventListener("mouseout", (event) => {
  if (event.target.closest(".state-clash")) tipLater();
});
$("#rows").addEventListener("mouseleave", tipLater);
$("#rows").addEventListener("focusin", (event) => {
  const tag = event.target.closest(".state-clash");
  const row = tag && tag.closest(".row");
  if (row) tipOpen(row.dataset.id);
});
$("#rows").addEventListener("focusout", (event) => {
  if (event.target.closest(".state-clash")) tipLater();
});
const cxTip = $("#cx-tip");
cxTip.addEventListener("mouseenter", tipStay);
cxTip.addEventListener("mouseleave", tipLater);
cxTip.addEventListener("focusin", tipStay);
cxTip.addEventListener("focusout", tipLater);
cxTip.addEventListener("click", (event) => {
  if (event.target.closest("[data-act='cx-go']")) tipGoSigned();
});
cxTip.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  event.preventDefault();
  event.stopPropagation();
  const id = S.tip.id;
  tipClose();
  const tag = id && S.rowEls.get(String(id)) && S.rowEls.get(String(id)).row.querySelector(".state-clash");
  if (tag && tag.focus) tag.focus();
});
$("#list").addEventListener("scroll", () => { if (S.tip.id) placeTip(); });
$("#btn-refresh").addEventListener("click", () => refresh(false));
/* 「登录 / 重新登录」先走重新登录对话框（三种情况）；对话框里保留「改用浏览器登录」 */
$("#btn-login").addEventListener("click", loginEntry);
wireRelogin();
$("#btn-help").addEventListener("click", showHelp);
/* 条款弹窗：同意 / 暂不使用 / 只读关闭 / 重新确认。TM01（decisions 014 修订）：
 * Esc 与右上角 X 只等于「关闭」（close 监听统一收口），拒绝只走「暂不使用」钮；
 * 保存中 Esc 被 cancel 明确拒绝；同意成功由 acceptTerms 自己走程序性关闭。
 * 全文阅读器只呈现全文（decisions 第 1 条）：旧的「要点⇄全文」切换钮已删，
 * 正文里的内联链接只负责切页签。 */
/* 方案 A：勾选是解锁「同意」的唯一前置；勾选态只活在这个弹窗实例里，
 * 不写 prefs、不写 ui.json——取消勾选立刻把同意按钮压回禁用。 */
$("#chk-terms-agree").addEventListener("change", applyTermsFooter);
  $("#tab-terms-agreement").addEventListener("click", function () { switchTermsDoc("agreement"); });
  $("#tab-terms-privacy").addEventListener("click", function () { switchTermsDoc("privacy"); });
  /* MIT 许可证：切换即懒加载（S.licenseText 已缓存/在途时是零请求） */
  $("#tab-terms-license").addEventListener("click", function () { switchTermsDoc("license"); ensureLicenseText(); });
  /* 正文/勾选行/第 3 条里的《用户协议》《隐私政策》《随包 LICENSE》内联链接：
   * 切到对应页签（全文常显）。preventDefault 同时拦下 label 把点击转成勾选翻转
   * 的默认行为——点链接不改变勾选状态，点链接外的文字照常 toggle。 */
  $("#dlg-terms").addEventListener("click", (event) => {
    const link = event.target.closest(".doc-link");
    if (!link) return;
    event.preventDefault();
    event.stopPropagation();
    const doc = link.getAttribute("data-doc");
    switchTermsDoc(doc);
    if (doc === "license") ensureLicenseText();
  });
  $("#btn-license-retry").addEventListener("click", () => ensureLicenseText(true));
$("#terms-toc").addEventListener("click", (event) => {
  const btn = event.target.closest("[data-toc]");
  if (!btn) return;
  const doc = document.querySelector(".terms-doc:not([hidden])");
  const heads = doc ? Array.from(doc.querySelectorAll(".terms-section > h3, .terms-section > h4")) : [];
  const head = heads[Number(btn.dataset.toc)];
  if (head && head.scrollIntoView) head.scrollIntoView({ block: "start" });
});
$("#btn-terms-accept").addEventListener("click", acceptTerms);
$("#btn-terms-decline").addEventListener("click", declineTerms);
/* 「设置 → 程序」里的查看条款：关闭后焦点回到这里，不把帮助弹出来 */
$("#btn-help-terms").addEventListener("click", () => openTerms("settings"));
$("#btn-terms-recheck").addEventListener("click", recheckTerms);
$("#btn-terms-close").addEventListener("click", () => {
  /* 只读查看的「关闭」：走原生关闭，由下面的 close 监听恢复来源焦点 */
  const dialog = $("#dlg-terms");
  if (dialog && dialog.open) dialog.close();
});
const termsDialog = $("#dlg-terms");
if (termsDialog) {
  /* 保存中的 Esc：cancel 明确拒绝（同意/暂不使用/X 已禁用）；其余按模式关闭 */
  termsDialog.addEventListener("cancel", (event) => {
    if (S.terms.saving) { event.preventDefault(); return; }
  });
  termsDialog.addEventListener("close", () => {
    /* 程序性关闭（同意成功/重新确认成功）已在各自路径处理焦点与引导 */
    if (S.terms.closeHandled) { S.terms.closeHandled = false; return; }
    /* 防御：保存中的关闭不该发生（cancel 已拦）；发生了也不记拒绝 */
    if (S.terms.saving) return;
    if (S.terms.unconfirmed) {
      /* 超时后关闭 = 离开待确认界面：不记成「同意未发生」，下次按 bootstrap 事实处理 */
      S.terms.unconfirmed = false;
      applyTermsFooter();
    }
    /* TM01（decisions 014 修订）：× 与 Esc 统一为「关闭」——未同意的关闭不再
     * 记成拒绝，拒绝只走「暂不使用」钮（declineTerms 自己落盘）。
     * FU01/TM08（decisions 第 1 条）：从小框进来的全文，×/Esc＝「回到原来的
     * 小框」（不等于拒绝）；条款流程还没结束，引导让位保持（回小框不恢复）；
     * 没有小框在等才走来源焦点恢复。 */
    if (termsCloseIntent() === "back" && reopenTermsBox()) {
      S.terms.xClose = "close";
      return;
    }
    S.terms.box = "";
    restoreTermsFocus();
    resumeTermsTour();
  });
}
/* 首次说明框（FU01）：勾选解锁「同意并继续」；「暂不使用」走 declineTerms；
 * 「现在就看」收起本框开全文（回小框由阅读器 close 监听按 xClose 收口）。 */
$("#chk-terms-intro-agree").addEventListener("change", applyTermsFooter);
$("#btn-terms-intro-accept").addEventListener("click", acceptTerms);
$("#btn-terms-intro-decline").addEventListener("click", declineTerms);
$("#dlg-terms-intro").addEventListener("click", (event) => {
  if (!event.target.closest("#btn-terms-intro-fulltext")) return;
  openTermsReader("intro");
});
const termsIntroDialog = $("#dlg-terms-intro");
if (termsIntroDialog) {
  /* FU01：Esc＝暂不使用（照原型键盘口径收进产品）；保存中照阅读器先拦；
   * 未确认＝离开待确认界面（不记拒绝，门禁保持），同阅读器 close 语义。 */
  termsIntroDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    if (S.terms.saving) return;
    if (S.terms.unconfirmed) {
      S.terms.unconfirmed = false;
      applyTermsFooter();
      closeTermsIntroBox();
      S.terms.box = "";
      return;
    }
    declineTerms();
  });
}
/* 条款更新框（TM08）：无勾选门（原型 Main:881），「同意新版条款」打开即可点；
 * 「看完整条款」同首次说明框的入口——收本框、开全文、关全文回本框。 */
$("#btn-tu-accept").addEventListener("click", acceptTerms);
$("#btn-tu-decline").addEventListener("click", declineTerms);
$("#btn-tu-full").addEventListener("click", () => openTermsReader("update"));
const termsUpdateDialog = $("#dlg-terms-update");
if (termsUpdateDialog) {
  /* TM08：Esc＝暂不同意；保存中拦、未确认＝离开待确认界面，同上。 */
  termsUpdateDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    if (S.terms.saving) return;
    if (S.terms.unconfirmed) {
      S.terms.unconfirmed = false;
      applyTermsFooter();
      closeTermsUpdateBox();
      S.terms.box = "";
      return;
    }
    declineTerms();
  });
}
/* 顶栏三张详情卡（时间 / 登录 / 手机）：悬停预览、点击固定、Esc 关闭 */
wireStatusCards();
$("#btn-settings").addEventListener("click", () => {
  /* 设置抽屉（views/settings.js）；没有抽屉的旧资源回退到帮助，不让按钮点了没反应 */
  if (typeof openSettings === "function") openSettings();
  else showHelp();
});
/* 中、窄档：计划条的「查看计划」打开计划栏，「返回列表」收起；「开始」与计划栏主按钮同一路径 */
$("#btn-dock-open").addEventListener("click", () => setPlanOpen(true));
$("#btn-plan-back").addEventListener("click", () => setPlanOpen(false));
$("#btn-dock-start").addEventListener("click", startPlan);
$("#btn-policy").addEventListener("click", () => {
  const box = $("#policy-edit");
  const open = !!box.hidden;
  box.hidden = !open;
  $("#btn-policy").setAttribute("aria-expanded", open ? "true" : "false");
  $("#btn-policy").textContent = open ? "收起" : "修改";   /* 原型 policyBtn */
});
window.addEventListener("resize", () => { applyBand(); if (S.tip.id) placeTip(); });
applyBand();
/* 计划栏里的就地动作：移除一场、开始前提醒的「去保存 / 去安装」、「还差一步」和运行中提醒的按钮 */
$("#plan-tickets").addEventListener("click", (event) => {
  const btn = event.target.closest("[data-remove]");
  if (btn) toggleSelection(btn.dataset.remove, false);
});
$("#board").addEventListener("click", (event) => {
  const btn = event.target.closest("#plan-prewarn [data-act], #plan-why [data-act], #run-warn [data-act]");
  if (!btn) return;
  const act = btn.dataset.act;
  if (act === "go-cred") openSettingsSection("login");
  else if (act === "go-ocr") openSettingsSection("adv");
  else if (act === "login") loginEntry();
  else if (act === "refresh") refresh(false);
  else if (act === "clock-open") openStatusCard("clock", true);
  /* 「还差一步：北京时间还没校准」的「重新校准」直接触发校准（原型 blockers 的 syncClock） */
  else if (act === "clock-sync") resyncClock();
  else if (act === "terms-open") openTerms("banner", btn);
});
wireSettings();
$("#btn-modify").addEventListener("click", modifyPlan);
$("#btn-edit-restore").addEventListener("click", restoreEditedPlan);
$("#btn-reselect").addEventListener("click", reselectFailed);
$("#btn-finish").addEventListener("click", finishResult);
$("#btn-log-folder").addEventListener("click", () => api("open_data")
  .then((res) => addLog("数据目录：" + ((res && res.path) || "已打开")))
  .catch((err) => addLog("[X] 打不开数据目录：" + msg(err))));
$("#btn-log-copy").addEventListener("click", copyLog);
$("#btn-plan").addEventListener("click", startPlan);
$("#btn-stop").addEventListener("click", stopPlan);
/* 计划栏的快捷「登录」已删：没登录时由「还差一步：还没有登录」的「去登录」打开登录对话框 */
$("#btn-board-pick").addEventListener("click", () => {
  const id = nextOpen().bestId;
  if (id) toggleSelection(id, true);
});
/* 大屏「时间待校准」的唯一恢复入口：打开现有时间详情，不新增第二个校准入口 */
$("#board-text").addEventListener("click", (event) => {
  const target = event.target;
  if (target && target.closest && target.closest("[data-open-clock]")) toggleClockPop();
});
/* 停止确认弹层（计划栏内遮罩）：只有「停止计划」才真正停止；Esc/继续计划只关弹层 */
$("#btn-stop-keep").addEventListener("click", () => closeStopAsk(true));
$("#btn-stop-yes").addEventListener("click", confirmStopPlan);
$("#btn-clear-plan").addEventListener("click", clearSelection);
$("#plan-tasks").addEventListener("click", (event) => {
  const button = event.target.closest(".task-cancel");
  if (button) cancelTask(button.dataset.taskId);
  const verify = event.target.closest(".task-verify");
  if (verify) verifyTask(verify.dataset.taskId);
});
$("#banners").addEventListener("click", (event) => {
  if (event.target.closest('[data-act="sleep-ok"]')) {
    S.sleepGap = 0;
    paintBanners();
  }
  if (event.target.closest('[data-act="second-ok"]')) {
    S.secondOpen = false;
    paintBanners();
  }
  if (event.target.closest('[data-act="migrated-ok"]')) {
    /* MG01「知道了」：只收本次运行内的横幅，不落盘（S 只存内存） */
    S.migrationDismissed = true;
    paintBanners();
  }
  if (event.target.closest('[data-act="runtime-refresh"]')) {
    /* 横幅上的「重新检查」= 一次完整刷新：check 事件带回组件结论，恢复即撤横幅 */
    refresh(false);
  }
  if (event.target.closest('[data-act="net-recheck"]')) {
    /* 断网横幅的「重新检测」：重读 navigator.onLine（原型 Main.dc.html:1702 的
     * netRecheck 只改网络状态并写运行记录，不自动刷新 —— 刷新由用户自己点）。 */
    if (navigator.onLine) {
      S.online = true;
      addLog("[OK] 网络已恢复");
      paintBanners();
      paintChecks();
    }
  }
  if (event.target.closest('[data-act="login"]')) loginEntry();
  if (event.target.closest('[data-act="clock-open"]')) openStatusCard("clock", true);
  const termsBtn = event.target.closest('[data-act="terms-open"]');
  if (termsBtn) {
    /* 条款横幅的「查看条款」：拒绝后的再同意入口，也是唯一入口；记住被点
     * 的按钮，关闭后焦点回到它（入口被重画消失就落回 #btn-help） */
    openTerms("banner", termsBtn);
  }
});
$("#headed").addEventListener("change", (event) => savePrefs({ headed: event.target.checked }));
/* 计划级重试策略：改完即存偏好，下一个计划生效（运行中的计划不受影响） */
function setRetryPolicy(patch) {
  Object.assign(S.retryPolicy, patch);
  savePrefs({ retry_policy: Object.assign({}, S.retryPolicy) });
}
$("#retry-for").addEventListener("change", (event) => {
  /* 选项表以 S.retryOptions.choices 为唯一口径（store.js 的注释已写明不各自维护
   * 第二套清单）：之前这里硬编码 ["120","600","1800","3600","0"]，漏了 -1 自动延长，
   * 选中会被当成非法值回滚成原值。 */
  const choices = (S.retryOptions && S.retryOptions.choices) || [];
  const picked = choices.filter((c) => String(c.value) === event.target.value)[0];
  if (picked) {
    setRetryPolicy({ retry_for_s: picked.value });
  } else {
    event.target.value = String(S.retryPolicy.retry_for_s);
  }
});
$("#max-attempts").addEventListener("change", (event) => {
  const value = Math.floor(Number(event.target.value));
  if (Number.isFinite(value) && value >= 0 && String(value).length <= 4) {
    setRetryPolicy({ max_attempts: value });
  } else {
    event.target.value = String(S.retryPolicy.max_attempts);
  }
});
$("#btn-log-toggle").addEventListener("click", () => setLogOpen(!S.logOpen));
$("#btn-log-clear").addEventListener("click", () => { $("#log").textContent = ""; $("#log-last").textContent = "还没有记录"; });
/* 五步引导：跳过/上一步/下一步；说明页重播入口；GitHub 最新版本外链（点击才打开） */
$("#tour-skip").addEventListener("click", tourSkip);
$("#tour-prev").addEventListener("click", () => {
  if (S.tour.step > 0) { S.tour.step -= 1; paintTour(); }
});
$("#tour-next").addEventListener("click", () => {
  if (S.tour.step >= TOUR_STEPS.length - 1) { tourClose(true); return; }
  S.tour.step += 1;
  paintTour();
});
/* 单帮助入口：重播仍走 replayTourFrom 的关闭模态与焦点恢复路径；
 * 计划运行中禁用重播（不打断计划），弹窗本身任何状态都能打开。 */
$("#btn-help-tour").addEventListener("click", () => replayTourFrom("#help", "#btn-help"));
$("#btn-update-check").addEventListener("click", checkUpdate);
$("#btn-update-install").addEventListener("click", startDownload);
$("#btn-update-confirm").addEventListener("click", confirmDownload);
$("#btn-update-launch").addEventListener("click", launchInstaller);
$("#btn-update-cancel").addEventListener("click", cancelDownload);
/* 启动安装程序以后：「关闭本工具…」接到关窗对话框，由用户自己决定怎么退 */
$("#btn-update-close").addEventListener("click", () => api("ask_window_close").catch(() => {}));
$("#btn-help-latest").addEventListener("click", () => {
  /* 用户点击才打开外链：后端用系统默认浏览器打开固定的 releases/latest 地址；
   * 打不开时把地址摆成可选文本（局部反馈），不在 WebView 里跳转 */
  helpStatus("");
  api("open_latest_release").then((res) => {
    if (!res || res.ok === false) {
      helpStatus("发布页没能打开（系统浏览器可能被拦）。地址：" + RELEASES_LATEST_URL, "warn");
    }
  }).catch((err) => {
    helpStatus("发布页没能打开：" + msg(err) + "。地址：" + RELEASES_LATEST_URL, "warn");
  });
});
$("#btn-help-data").addEventListener("click", () => {
  helpStatus("");
  api("open_data")
    .then((res) => {
      /* 成功时**不进 help-status**：那块是错误/警告位，塞成功信息会把「出错」的
         语义冲淡（既有契约也明确要求成功时保持隐藏）。路径写回说明正文里，
         用户既能看见又能选中复制，下次也不用再点一遍。 */
      const line = $("#help-data-path");
      if (line && res && res.path) line.textContent = "数据目录：" + res.path;
    })
    .catch((err) => {
      helpStatus("打不开数据目录：" + msg(err) + "。可以先再试一次，或在系统里手动打开本机数据目录。", "bad");
    });
});
/* 窗口尺寸或内部滚动变化时重新定位高亮与卡片 */
window.addEventListener("resize", () => { if (S.tour.open && !S.tour.paused) paintTour(); });
document.addEventListener("click", tourGuardClick, true);
document.addEventListener("scroll", () => { if (S.tour.open && !S.tour.paused) paintTour(); }, true);
$("#empty-action").addEventListener("click", () => {
  /* 只按 paintEmpty 写下的动作意图分派：
   * 「有缓存 + 列表失败」的空态写的是 refresh，不能被 items.length 猜成清筛选。 */
  const intent = $("#empty-action").dataset.action;
  if (intent === "clear-filters") clearFilters();
  else if (intent === "terms-open") openTerms("banner", true);
  else refresh(false);
});

document.addEventListener("keydown", (event) => {
  /* 打开的条款弹窗独占键盘——第一道判断，在引导/搜索处理之前：Enter/Esc/
   * Ctrl+F/`/` 不穿透到背景业务（不开始计划、不清选择、不抢搜索框），Tab、
   * 按钮激活与正常重载交给浏览器原生；保存中的 Esc 由 dialog 的 cancel 拦。
   * FU01/TM08（UI_SPEC §5.13 第 2 条）：两个条款小框同样独占键盘——Esc 的
   * 拒绝语义由各自 dialog 的 cancel 监听处理（原生 Esc→cancel），这里只负责
   * 不让背景快捷键（F5/Ctrl+F//、Enter 开始计划）穿透到模态背后的业务。 */
  const termsDlg = $("#dlg-terms");
  if (termsDlg && termsDlg.open) return;
  if (["#dlg-terms-intro", "#dlg-terms-update"].some((sel) => {
    const box = $(sel); return !!box && box.open;
  })) return;
  if (event.key === "F5") { event.preventDefault(); refresh(false); return; }
  const typing = event.target.closest && event.target.closest("input, select, textarea");
  /* 引导可见时键盘约束在卡片内：Esc=跳过、Tab 在卡片按钮间循环，
   * 背景 Ctrl+F / `/` / Enter 不移焦点、不触发开始计划；
   * 计划运行把引导暂停（tourVisible=false）时全部放行——停止操作不受影响。 */
  if (tourVisible()) {
    if (event.key === "Escape") { event.preventDefault(); tourSkip(); return; }
    if (event.key === "Tab") { tourTrapTab(event); return; }
    if ((event.ctrlKey && (event.key === "f" || event.key === "F")) ||
        (event.key === "/" && !typing)) { event.preventDefault(); return; }
    if (event.key === "Enter" && !typing) {
      const inCard = event.target.closest && event.target.closest("#tour-card");
      if (!inCard) { event.preventDefault(); return; }   /* 背景回车不开始计划 */
      return;   /* 卡片内回车：交给按钮原生激活（click 监听照常触发） */
    }
  }
  /* 停止确认弹层打开时键盘只属于它：Esc 关弹层，Tab 在两个按钮间循环，
   * 其余（Enter、Ctrl+F、/）不穿透到背景；Esc/「继续计划」=不停止 */
  if (stopAskOpen()) { stopAskKey(event); return; }
  /* 帮助打开时：Enter/Esc 只属于弹窗——不穿透到背景开始计划、不清空选择、不误跳引导 */
  if ((event.key === "Enter" || event.key === "Escape") &&
      ["#help"].some((sel) => { const d = $(sel); return !!d && d.open; })) {
    return;
  }
  /* Ctrl+F 或 / 跳到搜索框 */
  if ((event.ctrlKey && (event.key === "f" || event.key === "F")) || (event.key === "/" && !typing)) {
    event.preventDefault();
    $("#q").focus();
    $("#q").select();
    return;
  }
  if (event.key === "Escape") {
    /* 依次：关引导 → 关浮层 → 退输入 → 收起结论 → 清空选择；弹窗由浏览器自己收 */
    if (tourVisible()) { tourSkip(); return; }
    /* 原因气泡开着时 Esc 先收它（鼠标悬停打开的气泡焦点不在标签上） */
    if (S.tip.id) { tipClose(); return; }
    /* 逐层关闭：详情卡 → 对话框（浏览器自己收）→ 设置抽屉 */
    if (statusCardOpen() || clockPopOpenNow()) { closeStatusCards(true); return; }
    if (typeof settingsOpen === "function" && settingsOpen()) { closeSettings(true); return; }
    if (typing) { event.target.blur(); return; }
    if (!$("#result").hidden) { setResult(null); return; }
    if (S.selected.size && !S.busy) { clearSelection(); return; }
    return;
  }
  if (event.key !== "Enter") return;
  const active = document.activeElement;
  const tagName = active && active.tagName ? active.tagName : "BODY";
  if (["INPUT", "SELECT", "TEXTAREA", "BUTTON", "A"].indexOf(tagName) >= 0 || $("#help").open) return;
  startPlan();
});

window.addEventListener("online", () => { S.online = true; paintBanners(); paintChecks(); });
window.addEventListener("offline", () => { S.online = false; paintBanners(); paintChecks(); });

document.addEventListener("visibilitychange", () => {
  if (document.hidden) return;
  tick();
  if (!hasBridge()) return;
  api("bootstrap").then((info) => {
    if (info) {
      ingestBootstrapPlan(info);
      if (!!info.busy !== S.busy) setBusy(!!info.busy);
      if (!info.busy) refresh(true, { background: true });   /* 窗口恢复是程序自己发起的：不闪骨架，失败不清列表（U2/U3） */
    }
    /* 窗口变为可见：计划运行中上面不会刷新，隐藏期间错过的那次自动刷新在这里立即补上；
     * 上面刚刷新过的话，autoRefreshTick 会因为「正在拉列表」自己跳过，不会连刷两次 */
    autoRefreshTick().catch(() => {});
  }).catch(() => { autoRefreshTick().catch(() => {}); });
});

setInterval(tick, 1000);
boot().catch((error) => {
  /* 启动链路整体失败同样没有条款依据：先按未知拦住学校动作再报错 */
  markTermsUnknown();
  addLog("[X] 界面初始化失败：" + msg(error));
  render();
});
