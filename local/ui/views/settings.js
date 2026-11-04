/* 设置抽屉（决策 011 修订、014）：右侧抽屉，顶部分组跳转（高级功能 / 登录 / 程序）。
 * 需要动手的恢复动作都在这里：手机访问、验证码识别、保存的账号与自动登录、关闭窗口方式、
 * 版本与更新、本机数据、条款与隐私（含撤回同意）。帮助只做解释。
 * 这里只读后端快照（PhonePanel.state.advanced / bootstrap），不自己推断组件或条款状态。 */
function settingsOpen() {
  /* 以自己记的开合为准：Esc 逐层关闭时不能把「没打开」误判成打开、去抢别人的焦点 */
  return !!S.settingsOpen;
}

function openSettings(section) {
  const drawer = $("#settings");
  if (!drawer) return;
  if (typeof closeStatusCards === "function") closeStatusCards(false);
  const wasOpen = !!S.settingsOpen;
  drawer.hidden = false;
  S.settingsOpen = true;
  $("#btn-settings").setAttribute("aria-expanded", "true");
  if (!wasOpen && window.PhonePanel && typeof window.PhonePanel.refresh === "function") {
    /* 打开时重取一次手机访问与高级功能快照：组件、通道、账号状态都以后端为准 */
    try { window.PhonePanel.refresh(); } catch (error) { /* 面板刷新失败不影响抽屉本身 */ }
  }
  paintSettings();
  if (section) openSettingsSection(section);
  else if (!wasOpen) {
    const close = $("#btn-settings-close");
    if (close && close.focus) close.focus();
  }
}

/* 跳到某一组：标题带 scroll-margin，不被顶部分组按钮遮住 */
function openSettingsSection(section) {
  if (!settingsOpen()) { openSettings(section); return; }
  const head = $("#set-" + section);
  if (!head) return;
  if (head.scrollIntoView) head.scrollIntoView({ block: "start" });
  if (head.focus) head.focus();
}

function closeSettings(restoreFocus) {
  const drawer = $("#settings");
  if (!drawer || !S.settingsOpen) return;
  S.settingsOpen = false;
  drawer.hidden = true;
  $("#btn-settings").setAttribute("aria-expanded", "false");
  const box = $("#terms-withdraw-confirm");
  if (box) box.hidden = true;
  if (restoreFocus && $("#btn-settings").focus) $("#btn-settings").focus();
}

function paintSettings() {
  paintClosePref();
  paintTermsRow();
  paintOcrDownload();
}

/* 关闭窗口时：每次询问 / 最小化 / 隐藏到后台 / 直接退出（写 ui.json 的 window.close_action） */
function paintClosePref() {
  const select = $("#close-pref");
  if (!select) return;
  const action = String(((S.prefs || {}).window || {}).close_action || "");
  select.value = ["minimize", "hide", "exit"].indexOf(action) >= 0 ? action : "ask";
}

function saveClosePref(value) {
  const windowPrefs = Object.assign({}, (S.prefs || {}).window || {});
  windowPrefs.close_action = value === "ask" ? "" : value;
  savePrefs({ window: windowPrefs });
}

/* 条款与隐私：同意了哪一版、什么时候；没同意时写清停用了什么。计划运行中不能撤回 */
function paintTermsRow() {
  const line = $("#settings-terms-state");
  const withdraw = $("#btn-terms-withdraw");
  if (!line || !withdraw) return;
  const terms = S.terms || {};
  const accepted = typeof termsAccepted === "function" ? termsAccepted() : false;
  line.textContent = accepted
    ? "你在 " + (terms.acceptedAt || "之前") + " 同意了这一版。"
    : "还没有同意这一版：登录、登录检查、自动登录、刷新活动和开始计划都已停用。";
  withdraw.hidden = !accepted;
  withdraw.disabled = !!S.busy;
  withdraw.title = S.busy ? "计划运行中不能撤回，先停止计划" : "撤回同意（保存的账号和登录信息不会删除）";
}

async function withdrawTerms() {
  const box = $("#terms-withdraw-confirm");
  let result = null;
  try {
    result = await api("withdraw_terms");
  } catch (err) {
    result = { ok: false, text: "撤回没有完成：" + msg(err) };
  }
  if (box) box.hidden = true;
  if (!result || !result.ok) {
    helpStatus(String((result && result.text) || "撤回没有完成。"), "warn");
    return;
  }
  /* 回执里的条款快照就是后端事实：门禁立刻按它关上，界面不另算 */
  if (typeof ingestTerms === "function") ingestTerms(result.terms);
  addLog("已撤回使用条款同意；保存的账号和登录信息没有删除");
  helpStatus("已撤回同意。重新同意后可以继续登录和报名。", "info");
  paintTermsRow();
  paintBanners();
  render();
}

function ocrFeature() {
  if (window.PhonePanel && typeof window.PhonePanel.feature === "function") {
    const row = window.PhonePanel.feature("relogin_ocr");
    if (row && Object.keys(row).length) return row;
  }
  const adv = S.advanced || {};
  return ((adv.features || {}).relogin_ocr) || {};
}

/* 验证码识别：未安装时标题行右侧一个「下载并安装」，下载中可取消，失败才露出「导入已下载的组件包」 */
function paintOcrDownload() {
  const feature = ocrFeature();
  const dl = feature.download || {};
  const state = String(dl.state || "");
  const ready = !!feature.ready;
  const busy = state === "downloading" || state === "verifying";
  const failed = state === "failed";
  /* 已经装过的两种：组件在但加载失败（要重新导入），装了但停用（启用即可）——都不需要再下载 */
  const loadFailed = String(feature.status || "") === "failed";
  const disabled = !ready && !loadFailed && !!feature.available;
  const status = $("#ocr-feature-status");
  if (status) {
    status.textContent = ready ? "已启用" : (busy ? "下载中" : (failed ? "下载失败"
      : (loadFailed ? "加载失败" : (disabled ? "已停用" : "未安装"))));
  }
  const download = $("#btn-ocr-download");
  if (download) {
    download.hidden = ready || busy || loadFailed || disabled;
    download.textContent = failed ? "重试下载" : "下载并安装";
  }
  const importBtn = $("#btn-ocr-feature-install");
  if (importBtn) {
    importBtn.textContent = loadFailed ? "重新导入组件包" : (disabled ? "启用验证码识别" : "导入已下载的组件包");
  }
  const cancel = $("#btn-ocr-cancel");
  if (cancel) cancel.hidden = !busy;
  const line = $("#ocr-download-state");
  if (line) {
    line.textContent = ready ? "已装好：登录失效时电脑会自己认验证码，连续认错 3 次才转人工。"
      : (busy ? String(dl.text || "正在下载组件包…")
        : "装好以后，登录失效时电脑能自己认验证码；没装时要你手动输入。");
  }
  const error = $("#ocr-download-error");
  if (error) {
    error.hidden = !failed;
    error.textContent = failed ? String(dl.text || "下载没有完成，现有组件没有改动，可以重试。") : "";
  }
  const importRow = $("#ocr-import-row");
  if (importRow) importRow.hidden = !(failed || loadFailed || disabled);
}

function wireSettings() {
  const close = $("#btn-settings-close");
  if (close) close.addEventListener("click", () => closeSettings(true));
  const nav = document.querySelector(".set-nav");
  if (nav && nav.addEventListener) {
    nav.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-sec]");
      if (btn) openSettingsSection(btn.dataset.sec);
    });
  }
  const pref = $("#close-pref");
  if (pref) pref.addEventListener("change", (event) => saveClosePref(event.target.value));
  const withdraw = $("#btn-terms-withdraw");
  if (withdraw) {
    withdraw.addEventListener("click", () => {
      if (S.busy) return;
      $("#terms-withdraw-confirm").hidden = false;
    });
  }
  const cancel = $("#btn-terms-withdraw-cancel");
  if (cancel) cancel.addEventListener("click", () => { $("#terms-withdraw-confirm").hidden = true; });
  const confirm = $("#btn-terms-withdraw-confirm");
  if (confirm) confirm.addEventListener("click", () => { void withdrawTerms(); });
  const ocrDownload = $("#btn-ocr-download");
  if (ocrDownload && window.PhonePanel) {
    ocrDownload.addEventListener("click", () => void window.PhonePanel.downloadComponent("relogin_ocr"));
  }
  const ocrCancel = $("#btn-ocr-cancel");
  if (ocrCancel && window.PhonePanel) {
    ocrCancel.addEventListener("click", () => void window.PhonePanel.cancelComponent("relogin_ocr"));
  }
  const helpTerms = $("#btn-help-terms-view");
  if (helpTerms) helpTerms.addEventListener("click", () => openTerms("help"));
}
