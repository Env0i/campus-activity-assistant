"use strict";

/* 帮助里的跨设备入口与高级功能安装状态。
 * 入口沿用帮助弹窗的工具行，手机地址只在服务已开启时展示；密码字段在每次
 * 请求后清空，二维码只编码当前地址，不把配对码拼进 URL。 */

/* 高级功能的状态文案与按钮文案按行独立派生：手机控制与 ddddocr 互不串台。
 * failed 表示组件包加载失败，此时只能引导重新导入，不给"安装"这种误导动作。 */
function featureCopy(row, fallback) {
  if (row && row.status === "failed") return { status: "加载失败", action: "重新导入组件包" };
  if (row && row.ready) return { status: "已启用", action: "" };
  if (row && row.available) return { status: "已停用", action: "启用" + fallback };
  return { status: "未安装", action: "安装" + fallback };
}

/* 通道文案也按行独立派生：Tailscale 是固定入口，Cloudflare 是临时地址，
 * 两者不能共用一句「不可用」，否则用户看不出该修哪一个。 */
function channelCopy(channels, selected) {
  const row = (channels && channels[selected]) || {};
  if (selected === "cloudflare") {
    if (row.state === "running") {
      return { label: "Cloudflare（临时地址）", status: "正在提供访问",
               hint: "地址是临时的：重新开启会变，手机需要重新扫码。", warn: true };
    }
    if (row.available) {
      return { label: "Cloudflare（临时地址）", status: "可用",
               hint: "开启后由 cloudflared 建一条临时隧道，不需要账号或域名；cloudflared 随「手机控制」组件包自带并校验版本与哈希。", warn: true };
    }
    return { label: "Cloudflare（临时地址）", status: "不可用",
             hint: String(row.text || "组件包里没有通过校验的 cloudflared：重新安装「手机控制」组件包。"), warn: true };
  }
  if (row.available) {
    return { label: "Tailscale（长期地址）", status: "已连接",
             hint: String(row.restart_note || "地址固定：重启程序后手机仍可直接打开。"), warn: false };
  }
  if (row.state === "not_logged_in") {
    return { label: "Tailscale（长期地址）", status: "已安装，未登录",
             hint: "在电脑上打开 Tailscale 登录，手机用同一个账号。", warn: false };
  }
  if (row.state === "missing") {
    return { label: "Tailscale（长期地址）", status: "未安装",
             hint: "装好并登录后点「重新检测」；不想装就改用 Cloudflare。", warn: false };
  }
  return { label: "Tailscale（长期地址）", status: "暂时读不到状态",
           hint: String(row.text || "点「重新检测」再试一次。"), warn: false };
}

/* 组件下载态：把服务端的八个状态翻成一句人话 + 进度条 + 一个能点的按钮。 */
function componentCopy(download, ready) {
  const snap = download || {};
  const state = String(snap.state || (ready ? "installed" : "missing"));
  const total = Number(snap.total_bytes || 0);
  const done = Number(snap.downloaded || 0);
  const percent = total > 0 ? Math.max(0, Math.min(100, Math.round((done / total) * 100))) : 0;
  const sizeText = total > 0
    ? " " + (done / 1048576).toFixed(1) + " / " + (total / 1048576).toFixed(1) + " MB"
    : "";
  if (state === "downloading") {
    return { text: "正在下载手机控制组件…" + (percent ? percent + "%" + sizeText : ""),
             percent: percent, error: "", install: false, cancel: true };
  }
  if (state === "verifying") {
    return { text: "下载完成，正在校验组件…", percent: 100, error: "", install: false, cancel: true };
  }
  if (state === "installed") {
    return { text: "手机控制组件：已安装", percent: null, error: "", install: false, cancel: false };
  }
  if (state === "failed") {
    return { text: "手机控制组件：安装失败",
             percent: null, error: String(snap.text || "下载或校验没有通过，可以重试。"),
             install: true, cancel: false };
  }
  if (state === "cancelled") {
    return { text: "下载已取消，现有组件没有改动。", percent: null, error: "", install: true, cancel: false };
  }
  if (state === "removing") {
    return { text: "正在移除手机控制组件…", percent: null, error: "", install: false, cancel: false };
  }
  return { text: "手机控制组件：未安装", percent: null, error: "", install: true, cancel: false };
}

/* 「多久以前」的人话：秒/分/小时/天四档，超过一天不再精确到分钟。 */
/* 账号打码：前两位加后两位，中间四个星号（与后端 domain/login_rules.mask_account 同一规则） */
function maskAccount(name) {
  const text = String(name || "").trim();
  if (!text) return "已保存";
  return text.length >= 5 ? text.slice(0, 2) + "****" + text.slice(-2) : text.slice(0, 1) + "****";
}

function agoText(seconds) {
  const s = Math.max(0, Math.floor(Number(seconds) || 0));
  if (s < 60) return s + " 秒前";
  if (s < 3600) return Math.floor(s / 60) + " 分钟前";
  if (s < 86400) return Math.floor(s / 3600) + " 小时前";
  return Math.floor(s / 86400) + " 天前";
}

const PhonePanel = {
  state: {
    running: false, address: "", pair_code: "", qr: "", channel: "",
    pair_code_status: null,
    feature: { ready: false, available: false }, advanced: {},
    preferred_channel: "", tailscale_autostart: false,
  },
  busy: false,
  // 开启/关闭是有耗时的动作（Cloudflare 要等隧道出域名），单独记一个进行中状态，
  // 既防重复点击，也让按钮自己说明「在做什么」而不是看起来卡住
  pending: "",
  pollTimer: null,
  lastCode: "",
  // 对话框里「选中的文件」与「自检通过的文件」分开记：自检不过时不能安装
  picked: { phone_control: "", relogin_ocr: "" },
  verified: { phone_control: "", relogin_ocr: "" },
  // 清除账号要先确认：确认行开着时不能被轮询刷新顺手关掉
  clearConfirm: false,

  async refresh() {
    try {
      const info = await api("phone_access_state");
      if (info && info.ok) PhonePanel.state = Object.assign(PhonePanel.state, info);
    } catch (err) {
      /* 帮助弹窗打不开状态时不影响其他帮助工具。 */
    }
    PhonePanel.paint();
    PhonePanel.paintComponents();
    // 运行中才轮询：配对码会过期或被用掉后自动换新，界面不能一直显示死码
    if (PhonePanel.state.running) PhonePanel.startPolling();
    else PhonePanel.stopPolling();
  },

  /* 五秒一次只问本机内存里的状态，让「码换新」尽快反映；面板没开或窗口最小化就不问 */
  startPolling() {
    if (typeof setInterval !== "function" || PhonePanel.pollTimer) return;
    PhonePanel.pollTimer = setInterval(() => {
      if (!PhonePanel.state.running || PhonePanel.busy) return;
      if (document.hidden) return;
      const detail = $("#phone-access-detail");
      const panelClosed = detail && detail.offsetParent === null;
      if (panelClosed) return;              // 帮助弹窗关着，没人看，不必刷新
      void PhonePanel.refresh();
    }, 5000);
  },

  stopPolling() {
    if (PhonePanel.pollTimer && typeof clearInterval === "function") {
      clearInterval(PhonePanel.pollTimer);
    }
    PhonePanel.pollTimer = null;
  },

  feature(key) {
    return (PhonePanel.state.advanced && PhonePanel.state.advanced.features || {})[key]
      || {};
  },

  paint() {
    /* 顶栏手机标识与手机详情卡跟着同一份快照刷新（views/status-cards.js） */
    if (typeof paintStatusCards === "function") paintStatusCards();
    const st = PhonePanel.state;
    const busy = !!PhonePanel.busy;
    const pending = String(PhonePanel.pending || "");
    // 手机控制既可能来自 state.feature，也可能来自 advanced.features；合并后以 advanced 为准
    const phoneRow = Object.assign({}, st.feature || {}, PhonePanel.feature("phone_control"));
    const ocrRow = PhonePanel.feature("relogin_ocr");
    const phoneCopy = featureCopy(phoneRow, "手机控制");
    const ocrCopy = featureCopy(ocrRow, " ddddocr");
    const phoneReady = !!phoneRow.ready;
    const phoneInstall = $("#btn-phone-feature-install");
    const phoneRemove = $("#btn-phone-feature-remove");
    const ocrInstall = $("#btn-ocr-feature-install");
    const detail = $("#phone-access-detail");
    const status = $("#phone-feature-status");
    const ocrStatus = $("#ocr-feature-status");
    const address = $("#phone-address");
    const code = $("#phone-code");
    const qr = $("#phone-qr");
    const empty = $("#phone-qr-empty");
    const start = $("#btn-phone-start");
    const stop = $("#btn-phone-stop");
    const channel = $("#phone-channel");
    const cred = (st.advanced && st.advanced.credential) || {};
    const credNote = $("#credential-note");
    const credClear = $("#btn-credentials-clear");
    const credSave = $("#btn-credentials-save");
    // 通道状态只从快照读，界面不自己推断「该恢复哪一个」
    const channels = (st.advanced && st.advanced.channels) || {};
    const prefs = (st.advanced && st.advanced.phone_access) || {};
    const select = $("#phone-channel");
    // 正在跑的那条通道以快照的 active_channel 为准（服务端说了算）；没在跑时
    // 才用用户当前选中的下拉值，避免「界面显示 A、实际跑 B」。
    const runningChannel = st.running ? String(st.active_channel || st.channel || "") : "";
    const selected = runningChannel
      || String((select && select.value) || st.preferred_channel
        || prefs.preferred_channel || "tailscale");
    if (runningChannel && select && select.value !== runningChannel) {
      select.value = runningChannel;
    }
    const copy = channelCopy(channels, selected);
    const channelLabel = $("#phone-channel-label");
    const channelState = $("#phone-channel-state-text");
    const channelHint = $("#phone-channel-hint");
    const guide = $("#tailscale-guide");
    const warn = $("#phone-channel-warn");
    const recheck = $("#btn-tailscale-recheck");
    const copyButton = $("#btn-phone-address-copy");
    const addressAlt = $("#phone-address-alt");
    const addressAltLine = $("#phone-address-alt-line");
    const confirmBox = $("#phone-stop-confirm");
    const tailscale = channels.tailscale || {};
    const addresses = tailscale.addresses || [];

    if (status) {
      status.textContent = phoneCopy.status;
      status.dataset.state = String(phoneRow.status || "missing");
    }
    if (ocrStatus) {
      /* 下载中 / 失败 / 停用时设置抽屉再按下载事务覆盖（views/settings.js paintOcrDownload） */
      ocrStatus.textContent = ocrCopy.status;
      ocrStatus.dataset.state = String(ocrRow.status || "missing");
    }
    if (phoneInstall) {
      // 组件 ready 只说明源码版的模块能导入；Cloudflare 通道真正要的是组件包
      // （cloudflared + 校验信息）。通道报「组件缺失」时入口必须还在，否则用户
      // 看到「不可用」却没有任何地方能补装，界面就把自己锁死了。
      const cloudflare = channels.cloudflare || {};
      const componentMissing = cloudflare.error === "cloudflared_missing"
        || cloudflare.state === "missing";
      phoneInstall.hidden = phoneReady && !componentMissing;
      phoneInstall.disabled = busy;
      phoneInstall.textContent = componentMissing
        ? "安装/更换组件包"
        : phoneCopy.action;
    }
    if (phoneRemove) phoneRemove.disabled = busy;
    if (ocrInstall) {
      /* 「导入已下载的组件包」只在一键下载失败、加载失败或停用时露出（显隐由设置抽屉决定） */
      ocrInstall.disabled = busy;
      ocrInstall.textContent = ocrCopy.action;
    }
    // 电脑续登录：ddddocr（能不能自动识别）与账号（有没有保存）分开展示，
    // 任一缺失都写清「缺什么、会怎样」，不让用户以为必须装 ddddocr 才能存账号
    const ocrReady = !!(ocrRow.ready || cred.ocr_ready);
    const storeOk = !(cred.store_available === false || cred.available === false);
    const overall = $("#relogin-overall-status");
    const ocrLine = $("#relogin-ocr-status");
    const credLine = $("#relogin-credential-status");
    const lastLine = $("#relogin-last-used");
    const autoPath = $("#relogin-auto-path");
    const phonePath = $("#relogin-phone-path");
    const clearBox = $("#relogin-clear-confirm");
    if (overall) {
      const configured = !!cred.saved && ocrReady && storeOk;
      overall.textContent = configured ? "已配置"
        : (!storeOk ? "存储不可用" : (cred.saved || ocrReady ? "部分可用" : "未配置"));
      overall.dataset.state = configured ? "ready" : (cred.saved || ocrReady ? "partial" : "missing");
    }
    if (ocrLine) {
      ocrLine.textContent = ocrReady
        ? "验证码识别：已装好，登录失效时电脑会自己认验证码；连续认错 3 次才转人工。"
        : "验证码识别：没装，验证码要人工输入（电脑或手机上都行）。";
    }
    if (credLine) {
      if (!storeOk) {
        credLine.textContent = "账号：本机加密存储不可用，输入后只在本次运行期间有效。";
      } else if (cred.saved && cred.paused) {
        credLine.textContent = "账号：" + maskAccount(cred.username) + "；学校说保存的密码不对，自动登录已暂停，换成新密码就恢复。";
      } else if (cred.saved) {
        credLine.textContent = "账号：" + maskAccount(cred.username) + "；密码只在本机加密保存。";
      } else {
        credLine.textContent = "账号：未保存。";
      }
    }
    if (lastLine) {
      const origin = String(cred.last_origin || "");
      const ago = Number((cred.automatic && cred.automatic.last_used_ago_s) || 0);
      if (origin === "auto_ocr") lastLine.textContent = "最近一次登录：由电脑自动恢复完成。";
      else if (origin === "phone_manual") lastLine.textContent = "最近一次登录：在手机上手动完成。";
      else if (ago > 0) lastLine.textContent = "最近一次自动恢复：" + agoText(ago) + "。";
      else lastLine.textContent = "最近一次登录：暂无记录。";
    }
    if (autoPath) {
      autoPath.textContent = (cred.saved && ocrReady && storeOk && !cred.paused)
        ? "失效后自动登录：已开启，登录失效时电脑自己登录，不需要你动手。"
        : "失效后自动登录：没开"
          + (cred.paused ? "（保存的密码不对，已暂停）" : (cred.saved ? "（还缺验证码识别，验证码要你输入）" : "（还没保存账号）")) + "。";
    }
    if (phonePath) {
      phonePath.textContent = ocrReady
        ? "手机上重新登录：验证码先由电脑自动识别，认不出来再由你输入。"
        : "手机上重新登录：验证码由你输入；手机上也可以输账号密码，默认不保存。";
    }
    if (typeof paintOcrDownload === "function") paintOcrDownload();
    if (clearBox) clearBox.hidden = !PhonePanel.clearConfirm;
    if (detail) detail.hidden = !phoneReady;
    if (channelLabel) channelLabel.textContent = copy.label;
    if (channelState) {
      channelState.textContent = copy.status;
      channelState.dataset.state = String((channels[selected] || {}).state || "unknown");
    }
    if (channelHint) channelHint.textContent = copy.hint;
    if (guide) guide.hidden = selected !== "tailscale";
    if (warn) warn.hidden = !copy.warn;
    if (recheck) { recheck.hidden = selected !== "tailscale"; recheck.disabled = busy; }
    // 地址固定时才值得存书签；临时地址存了下次就打不开
    const bookmarkHint = $("#phone-bookmark-hint");
    if (bookmarkHint) bookmarkHint.hidden = !(st.running && selected === "tailscale");
    const portMatch = /:(\d+)\//.exec(String(st.address || ""));
    const port = portMatch ? portMatch[1] : "8765";
    const alt = (st.running && selected === "tailscale" && addresses.length)
      ? "http://" + String(addresses[0]) + ":" + port + "/" : "";
    if (addressAlt) addressAlt.textContent = alt;
    if (addressAltLine) addressAltLine.hidden = !alt || alt === String(st.address || "");
    if (copyButton) { copyButton.hidden = !st.running; copyButton.disabled = busy || !st.running; }
    // 组件下载态（能力层）：装不上就看得到进度、看得到错，也能取消
    const features = (st.advanced && st.advanced.features) || {};
    const phoneFeature = features.phone_control || st.feature || {};
    const download = phoneFeature.download || {};
    const comp = componentCopy(download, !!phoneFeature.ready);
    const compState = $("#phone-component-state");
    const compProgress = $("#phone-component-progress");
    const compError = $("#phone-component-error");
    const compInstall = $("#btn-phone-component-install");
    const compCancel = $("#btn-phone-component-cancel");
    const downloading = String(download.state || "") === "downloading"
      || String(download.state || "") === "verifying";
    if (compState) compState.textContent = comp.text;
    /* 下载中说明照原型 Main.dc.html:663：下载和报名计划互不影响。 */
    const downloadNote = $("#phone-download-note");
    if (downloadNote) downloadNote.hidden = !downloading;
    if (compProgress) {
      compProgress.hidden = comp.percent === null || comp.percent === undefined;
      compProgress.value = Number(comp.percent || 0);
    }
    if (compError) {
      compError.hidden = !comp.error;
      compError.textContent = comp.error;
    }
    if (compInstall) {
      compInstall.hidden = !comp.install;
      compInstall.disabled = busy || downloading;
      compInstall.textContent = comp.install && String(download.state || "") === "available"
        ? "下载并安装组件包" : "重新安装组件包";
    }
    if (compCancel) {
      compCancel.hidden = !comp.cancel;
      compCancel.disabled = busy || !comp.cancel;
    }
    // 下载/校验期间不允许开启通道：组件还没落地，开了也用不上
    if (start) start.disabled = busy || !!(pending) || downloading;
    if (confirmBox && !st.running) confirmBox.hidden = true;
    if (address) address.textContent = st.running ? String(st.address || "") : "未开启";
    const codeInfo = st.pair_code_status || {};
    const codeText = st.running ? String(codeInfo.code || st.pair_code || "") : "";
    if (code) code.textContent = st.running ? (codeText || "—") : "—";
    const codeNote = $("#pair-code-note");
    if (codeNote) {
      codeNote.hidden = !st.running;
      const left = Number(codeInfo.expires_in || 0);
      codeNote.textContent = !st.running ? ""
        : left > 0
          ? "配对码 " + Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0") + " 后失效"
          : "配对码已过期，正在换新";
    }
    // 换来新码必须当场说一声：静默换码会让用户拿着旧码反复对不上
    if (st.running && codeText) {
      const last = PhonePanel.lastCode;
      if (last && last !== codeText) {
        const why = String(codeInfo.reason || "");
        helpStatus(why === "paired"
          ? "手机已配对，配对码已换成新的（旧码不能再用）。"
          : why === "expired"
            ? "配对码已过期，已经换成新的。"
            : "配对码已更新。",
          why === "expired" ? "warn" : "info");
      }
      PhonePanel.lastCode = codeText;
    } else if (!st.running) {
      PhonePanel.lastCode = "";
    }
    if (qr) {
      qr.hidden = !st.running || !st.qr;
      if (st.qr) qr.src = String(st.qr);
    }
    if (empty) empty.hidden = !!(st.running && st.qr);
    if (start) {
      start.hidden = !!st.running;
      // 组件还在下载/校验时也不许点：装完之前开了通道也用不上
      start.disabled = busy || !!pending || downloading;
      start.textContent = pending === "starting" ? "启动中…" : "开启手机访问";
    }
    if (stop) {
      stop.hidden = !st.running;
      stop.disabled = busy || !!pending;
      stop.textContent = pending === "stopping" ? "关闭中…" : "关闭访问";
    }
    if (channel) channel.disabled = busy || !!pending;
    if (channel && st.channel && channel.options
        && typeof channel.options.namedItem === "function"
        && channel.options.namedItem(st.channel)) channel.value = st.channel;
    if (credNote) {
      credNote.textContent = cred.saved
        ? "已保存账号：" + String(cred.username || "（未显示）") + "；密码只在本机加密保存。"
        : "账号密码使用本机 Windows 加密保存，只供电脑上的重新登录流程使用。";
    }
    if (credClear) { credClear.hidden = !cred.saved; credClear.disabled = busy; }
    if (credSave) {
      credSave.textContent = cred.available ? "保存到本机" : "仅本次准备";
      credSave.disabled = busy || (!cred.available && !phoneReady);
    }
  },

  /* 组件与通道：每一行都是「选文件 → 立刻自检 → 安装这份」。
     程序不代下载、不猜路径；选错东西由自检当场说明它到底是什么。 */
  openComponents() {
    const dlg = $("#dlg-components");
    if (!dlg) return;
    PhonePanel.picked = { phone_control: "", relogin_ocr: "" };
    PhonePanel.verified = { phone_control: "", relogin_ocr: "" };
    PhonePanel.paintComponents();
    if (typeof dlg.showModal === "function") dlg.showModal();
    else dlg.setAttribute("open", "");
  },

  paintComponents() {
    const advanced = (PhonePanel.state && PhonePanel.state.advanced) || {};
    const features = (advanced.features) || {};
    const channels = (advanced.channels) || {};
    const rows = [
      { key: "phone_control", prefix: "comp-phone" },
      { key: "relogin_ocr", prefix: "comp-ocr" },
    ];
    rows.forEach(({ key, prefix }) => {
      const feature = features[key] || {};
      const statusEl = $("#" + prefix + "-status");
      const noteEl = $("#" + prefix + "-note");
      const installEl = $("#btn-" + prefix + "-install");
      const pathEl = $("#" + prefix + "-path");
      if (statusEl) {
        statusEl.textContent = feature.ready ? "已启用"
          : (feature.available ? "已安装未启用"
            : (feature.status === "failed" ? "组件损坏" : "未安装"));
        statusEl.dataset.state = String(feature.status || "missing");
      }
      if (pathEl && PhonePanel.picked && PhonePanel.picked[key]) {
        pathEl.value = PhonePanel.picked[key];
      }
      const verified = PhonePanel.verified && PhonePanel.verified[key];
      if (installEl) installEl.disabled = !verified;
      if (noteEl && !noteEl.textContent) noteEl.hidden = true;
    });
    const tailscale = channels.tailscale || {};
    const tailscaleEl = $("#comp-tailscale-status");
    if (tailscaleEl) {
      tailscaleEl.textContent = tailscale.available ? "已连接"
        : (tailscale.state === "not_logged_in" ? "已安装，未登录" : "未安装");
      tailscaleEl.dataset.state = String(tailscale.state || "missing");
    }
  },

  async pickComponent(key) {
    const prefix = key === "phone_control" ? "comp-phone" : "comp-ocr";
    const result = await api("pick_advanced_component", key);
    if (!result || result.canceled) return;
    if (!result.ok) {
      PhonePanel.showComponentNote(prefix, (result && result.text) || "打不开文件选择框。", false);
      return;
    }
    const pathEl = $("#" + prefix + "-path");
    if (pathEl) pathEl.value = String(result.path || "");
    await PhonePanel.inspectComponent(key, String(result.path || ""));
  },

  async inspectComponent(key, path) {
    const prefix = key === "phone_control" ? "comp-phone" : "comp-ocr";
    const chosen = String(path || "").trim();
    PhonePanel.picked[key] = chosen;
    PhonePanel.verified[key] = "";
    const installEl = $("#btn-" + prefix + "-install");
    if (installEl) installEl.disabled = true;
    if (!chosen) {
      PhonePanel.showComponentNote(prefix, "还没有选择文件。", false);
      return;
    }
    const info = await api("inspect_advanced_component", key, chosen);
    PhonePanel.showComponentNote(prefix, (info && info.text) || "自检没有返回结论。", !!(info && info.ok));
    if (info && info.ok) PhonePanel.verified[key] = chosen;
    PhonePanel.paintComponents();
  },

  showComponentNote(prefix, text, ok) {
    const noteEl = $("#" + prefix + "-note");
    if (!noteEl) return;
    noteEl.textContent = String(text || "");
    noteEl.hidden = !text;
    noteEl.dataset.tone = ok ? "ok" : "warn";
  },

  async installComponent(key) {
    const prefix = key === "phone_control" ? "comp-phone" : "comp-ocr";
    const chosen = String((PhonePanel.verified || {})[key] || "");
    if (!chosen) {
      PhonePanel.showComponentNote(prefix, "先选文件并自检通过，再安装。", false);
      return;
    }
    const installEl = $("#btn-" + prefix + "-install");
    if (installEl) installEl.disabled = true;
    try {
      const result = await api("install_advanced_feature", key, chosen);
      const ok = !!(result && result.ok);
      PhonePanel.showComponentNote(prefix, (result && result.text) || (ok ? "已安装。" : "安装没有完成。"), ok);
      if (ok) {
        PhonePanel.picked[key] = "";
        PhonePanel.verified[key] = "";
        const pathEl = $("#" + prefix + "-path");
        if (pathEl) pathEl.value = "";
        await PhonePanel.refresh();
      }
    } finally {
      PhonePanel.paintComponents();
    }
  },

  closeComponents() {
    const dlg = $("#dlg-components");
    if (!dlg) return;
    if (typeof dlg.close === "function" && dlg.hasAttribute && dlg.hasAttribute("open")) dlg.close();
    else dlg.removeAttribute("open");
  },

  async toggleStart() {
    if (PhonePanel.busy || PhonePanel.pending) return;
    const channel = $("#phone-channel");
    const chosen = channel ? channel.value : "tailscale";
    PhonePanel.busy = true;
    PhonePanel.pending = "starting";
    PhonePanel.paint();
    helpStatus(chosen === "cloudflare"
      ? "正在建立 Cloudflare 临时隧道，最多等二十秒…"
      : "正在开启手机访问…", "info");
    try {
      const result = await api("start_phone_access", chosen);
      if (!result || !result.ok) {
        helpStatus((result && result.text) || "手机访问没有开启。", "warn");
      } else if (result.address) {
        helpStatus("手机访问已开启：" + String(result.address), "info");
      }
    } finally {
      PhonePanel.pending = "";
      PhonePanel.busy = false;
      await PhonePanel.refresh();
    }
  },

  async toggleStop() {
    if (PhonePanel.busy || PhonePanel.pending) return;
    PhonePanel.busy = true;
    PhonePanel.pending = "stopping";
    PhonePanel.paint();
    helpStatus("正在关闭手机访问…", "info");
    try {
      const result = await api("stop_phone_access");
      if (result && result.ok === false) {
        helpStatus((result && result.text) || "手机访问没有关闭。", "warn");
      } else {
        helpStatus("手机访问已关闭，手机需要重新配对才能再进。", "info");
      }
    } finally {
      PhonePanel.pending = "";
      PhonePanel.busy = false;
      await PhonePanel.refresh();
    }
  },

  /* 关闭是破坏性的（手机立刻失去权限、要重新扫码），所以先问一句再动手 */
  askStop() {
    const box = $("#phone-stop-confirm");
    if (box) box.hidden = false;
  },

  cancelStop() {
    const box = $("#phone-stop-confirm");
    if (box) box.hidden = true;
  },

  async confirmStop() {
    const box = $("#phone-stop-confirm");
    if (box) box.hidden = true;
    await PhonePanel.toggleStop();
  },

  /* 复制地址：优先 Clipboard API，被禁用时退回 textarea + execCommand */
  copyByTextarea(text) {
    try {
      const area = document.createElement("textarea");
      area.value = text;
      document.body.appendChild(area);
      area.select();
      const done = !!(document.execCommand && document.execCommand("copy"));
      document.body.removeChild(area);
      return done;
    } catch (err) {
      return false;
    }
  },

  async copyAddress() {
    const text = String(PhonePanel.state.address || "");
    if (!text) return;
    let done = false;
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard
          && typeof navigator.clipboard.writeText === "function") {
        await navigator.clipboard.writeText(text);
        done = true;
      }
    } catch (err) {
      done = false;
    }
    if (!done) done = PhonePanel.copyByTextarea(text);
    helpStatus(done ? "地址已复制： " + text : "复制没有成功，请手动选中地址。",
               done ? "info" : "warn");
  },

  /* 组件下载：一次点击就走完「取地址 → 下载 → 校验 → 安装」，用户不用选文件。
   * key 为 phone_control（手机控制）或 relogin_ocr（验证码识别），两者同一条后端事务。 */
  async downloadComponent(key) {
    const feature = key === "relogin_ocr" ? "relogin_ocr" : "phone_control";
    const title = feature === "relogin_ocr" ? "验证码识别" : "手机控制";
    if (PhonePanel.busy) return;
    PhonePanel.busy = true;
    PhonePanel.paint();
    let result = null;
    try {
      result = await api("download_advanced_feature", feature);
    } catch (err) {
      result = { ok: false, text: "组件下载没有开始，请稍后重试。" };
    } finally {
      PhonePanel.busy = false;
    }
    helpStatus(result && result.ok
      ? "开始下载" + title + "组件，下载完会自动校验并安装。"
      : String((result && result.text) || "组件下载没有开始。"),
      result && result.ok ? "info" : "warn");
    await PhonePanel.refresh();
    /* 下载在后台进行：没开手机访问时也要轮询，进度和结论才能更新 */
    if (result && result.ok) PhonePanel.startPolling();
  },

  async cancelComponent(key) {
    const feature = key === "relogin_ocr" ? "relogin_ocr" : "phone_control";
    let result = null;
    try {
      result = await api("cancel_advanced_feature_download", feature);
    } catch (err) {
      result = { ok: false, text: "取消没有生效，请稍后重试。" };
    }
    helpStatus(String((result && result.text) || "已取消下载。"),
               result && result.ok === false ? "warn" : "info");
    await PhonePanel.refresh();
  },

  /* 换通道只记偏好：不重启当前监听，也不偷偷帮用户把隧道切过去 */
  async changeChannel(value) {
    const chosen = String(value || "");
    if (!chosen) return;
    try {
      await api("set_phone_access_preferences", chosen);
    } catch (err) {
      /* 记忆失败不影响本次选择，只是下次要重选 */
    }
    await PhonePanel.refresh();
  },

  async saveCredentials() {
    const user = $("#credential-user");
    const pass = $("#credential-pass");
    if (!user || !pass) return;
    const username = String(user.value || "");
    const password = String(pass.value || "");
    const cred = (PhonePanel.state.advanced && PhonePanel.state.advanced.credential) || {};
    let result = null;
    PhonePanel.busy = true;
    PhonePanel.paint();
    try {
      result = cred.available
        ? await api("save_relogin_credentials", username, password)
        : await api("prepare_phone_relogin", username, password);
    } catch (err) {
      // 失败原因可能含账号细节，只给通用文案，不把异常原文带给用户
      result = { ok: false, text: "账号信息没有保存。" };
    } finally {
      user.value = "";
      pass.value = "";
      PhonePanel.busy = false;
    }
    helpStatus((result && result.text) || (result && result.ok
      ? "账号信息已准备好。"
      : "账号信息没有保存。"), result && result.ok ? "info" : "warn");
    await PhonePanel.refresh();
  },

  /* 清除账号先展开确认行：这是不可撤销的动作，不能一点就删 */
  askClearCredentials() {
    PhonePanel.clearConfirm = true;
    PhonePanel.paint();
  },

  cancelClearCredentials() {
    PhonePanel.clearConfirm = false;
    PhonePanel.paint();
  },

  async confirmClearCredentials() {
    PhonePanel.clearConfirm = false;
    PhonePanel.paint();
    await PhonePanel.clearCredentials();
  },

  async clearCredentials() {
    const result = await api("clear_relogin_credentials");
    helpStatus((result && result.ok) ? "已清除本机保存的账号信息。" : "清除没有完成。",
               result && result.ok ? "info" : "warn");
    await PhonePanel.refresh();
  },

  wire() {
    const installPhone = $("#btn-phone-feature-install");
    const installOcr = $("#btn-ocr-feature-install");
    const start = $("#btn-phone-start");
    const stop = $("#btn-phone-stop");
    const manage = $("#btn-credentials-manage");
    const save = $("#btn-credentials-save");
    const clear = $("#btn-credentials-clear");
    const editor = $("#credential-editor");
    const channel = $("#phone-channel");
    const recheck = $("#btn-tailscale-recheck");
    const copy = $("#btn-phone-address-copy");
    const stopCancel = $("#btn-phone-stop-cancel");
    const stopConfirm = $("#btn-phone-stop-confirm");
    if (installPhone) installPhone.addEventListener("click", () => PhonePanel.openComponents());
    if (installOcr) installOcr.addEventListener("click", () => PhonePanel.openComponents());
    const pickPhone = $("#btn-comp-phone-pick");
    if (pickPhone) pickPhone.addEventListener("click", () => void PhonePanel.pickComponent("phone_control"));
    const pickOcr = $("#btn-comp-ocr-pick");
    if (pickOcr) pickOcr.addEventListener("click", () => void PhonePanel.pickComponent("relogin_ocr"));
    const inspectPhone = $("#btn-comp-phone-inspect");
    if (inspectPhone) inspectPhone.addEventListener("click", () => {
      const field = $("#comp-phone-path");
      void PhonePanel.inspectComponent("phone_control", field ? field.value : "");
    });
    const inspectOcr = $("#btn-comp-ocr-inspect");
    if (inspectOcr) inspectOcr.addEventListener("click", () => {
      const field = $("#comp-ocr-path");
      void PhonePanel.inspectComponent("relogin_ocr", field ? field.value : "");
    });
    const installPhoneFile = $("#btn-comp-phone-install");
    if (installPhoneFile) installPhoneFile.addEventListener("click", () => void PhonePanel.installComponent("phone_control"));
    const installOcrFile = $("#btn-comp-ocr-install");
    if (installOcrFile) installOcrFile.addEventListener("click", () => void PhonePanel.installComponent("relogin_ocr"));
    const closeComponents = $("#btn-comp-close");
    if (closeComponents) closeComponents.addEventListener("click", () => PhonePanel.closeComponents());
    if (start) start.addEventListener("click", () => void PhonePanel.toggleStart());
    if (stop) stop.addEventListener("click", () => PhonePanel.askStop());
    if (stopCancel) stopCancel.addEventListener("click", () => PhonePanel.cancelStop());
    if (stopConfirm) stopConfirm.addEventListener("click", () => void PhonePanel.confirmStop());
    if (recheck) recheck.addEventListener("click", () => void PhonePanel.refresh());
    if (copy) copy.addEventListener("click", () => void PhonePanel.copyAddress());
    const compInstall = $("#btn-phone-component-install");
    if (compInstall) compInstall.addEventListener("click", () => void PhonePanel.downloadComponent());
    const compCancel = $("#btn-phone-component-cancel");
    if (compCancel) compCancel.addEventListener("click", () => void PhonePanel.cancelComponent());
    if (channel) channel.addEventListener("change", () => void PhonePanel.changeChannel(channel.value));
    if (manage && editor) manage.addEventListener("click", () => { editor.hidden = !editor.hidden; });
    if (save) save.addEventListener("click", () => void PhonePanel.saveCredentials());
    if (clear) clear.addEventListener("click", () => PhonePanel.askClearCredentials());
    const clearCancel = $("#btn-relogin-clear-cancel");
    const clearConfirm = $("#btn-relogin-clear-confirm");
    if (clearCancel) clearCancel.addEventListener("click", () => PhonePanel.cancelClearCredentials());
    if (clearConfirm) clearConfirm.addEventListener("click", () => void PhonePanel.confirmClearCredentials());
    void PhonePanel.refresh();
  },
};

if (typeof document !== "undefined") {
  if (document.readyState !== "loading") PhonePanel.wire();
  else document.addEventListener("DOMContentLoaded", PhonePanel.wire);
}

/* app.js 的 check 事件要顺手刷新这张卡片（重新登录成功会走 check）。跨文件只能靠
 * 一个显式挂载点：顶层 const 不会自动变成 window 属性。 */
if (typeof window !== "undefined") window.PhonePanel = PhonePanel;
