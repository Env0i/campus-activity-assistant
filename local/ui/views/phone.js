"use strict";

/* 帮助里的跨设备入口与高级功能安装状态。
 * 入口沿用帮助弹窗的工具行，手机地址只在服务已开启时展示；密码字段在每次
 * 请求后清空，二维码只编码当前地址，不把配对码拼进 URL。 */

/* 验证码识别一节的状态、按钮和文案在 views/settings.js（paintOcrDownload）；这里管手机访问、登录恢复和导入弹窗。 */

/* 手机访问状态机（settings-gap PH07，原型 phView，Main.dc.html 1244–1308）：
 * missing 没装 / downloading 下载中 / verifying 校验中 / checking 检查中（组件事务锁被占、还没结论，不是没装）/
 * off 装好未开启（含开启中）/ on 已开启。
 * 原型没画、代码里真有的两档保留现状（kept_not_in_prototype）：broken 已装但加载失败（PH14b）、
 * disabled 组件在本机但启用位没开（换机迁移、手动改过设置）。 */
function phonePhase(st, row) {
  const dl = String(((row && row.download) || {}).state || "");
  if (st && st.running) return "on";
  if (dl === "downloading") return "downloading";
  if (dl === "verifying") return "verifying";
  if (row && row.status === "checking") return "checking";
  if (row && row.status === "outdated") return "outdated";
  if (row && row.status === "failed") return "broken";
  if (row && row.ready) return "off";
  if (row && row.available) return "disabled";
  return "missing";
}

/* PH06 / PH23（审核决定 A4）：「手机已连接」= 开着，且本次兑换过配对码或有活动会话。
 * 只看 paired_count 会漏掉重启后靠设备信任 cookie 回来的手机；不再看 pair_code_status.reason，
 * 那个 reason 只挂在刚换出的那张码上，码一过期「已连接」就会自己消失。
 * 顶栏手机标识用同一条规则（views/status-cards.js phoneLinked）。 */
function phoneLinkedNow(st) {
  return !!(st && st.running) && (Number(st.paired_count || 0) > 0 || st.live_session === true);
}

/* PH17：两张通道卡的文案逐字照原型 phView（1270–1273 行）；卡名写在 index.html 里。
 * 「暂时读不到状态」「不可用」两档原型没有（检测本身失败、组件包缺 cloudflared），保留现状。 */
function channelCards(channels) {
  const ts = (channels && channels.tailscale) || {};
  const cf = (channels && channels.cloudflare) || {};
  let tailscale;
  if (ts.available) {
    tailscale = { status: "已连接", tone: "ok",
                  text: "地址固定，重启程序和电脑后不用重新配对。电脑和手机要登录同一个账号。" };
  } else if (ts.state === "not_logged_in") {
    tailscale = { status: "已安装，未登录", tone: "warn",
                  text: "在电脑上打开 Tailscale 登录，手机用同一个账号。" };
  } else if (ts.state === "missing") {
    tailscale = { status: "未安装", tone: "warn",
                  text: "电脑和手机都要装好并登录同一个账号；工具不会替你安装。" };
  } else {
    tailscale = { status: "暂时读不到状态", tone: "warn",
                  text: String(ts.text || "点“重新检测”再试一次。") };
  }
  const cloudflare = cf.available
    ? { status: "可用", tone: "ok",
        text: "不用账号，组件里已带好。但每次开启地址都会变，要重新扫码和配对。" }
    : { status: "不可用", tone: "warn",
        text: String(cf.text || "组件包里没有通过校验的 cloudflared：重新安装“手机控制”组件包。") };
  return { tailscale: tailscale, cloudflare: cloudflare };
}

/* IM03：导入自检的结论文案，字面照原型 impCheck（Main.dc.html 1368–1376），拼法按后端实际回包的字段：
 * 通过时回 ok / kind / feature / version；失败时只回 kind / feature / text，没有这个包自己的版本。
 * 所以：
 *   - 「大小和哈希都对得上」不写：自检只读了清单，没核每个文件的哈希（安装时才核），说出来就是替它担保；
 *   - 「这个组件包是给 x 用的」不写：失败回包里没有包的版本，只能说和现在的程序版本不配套（需要后端补 package_version）；
 *   - Tailscale 的 exe 只能按文件名认；其余 exe 照后端原话说不是组件包。 */
const IMPORT_TITLE = { relogin_ocr: "验证码识别", phone_control: "手机控制" };

function importCheckText(key, path, info) {
  const full = String(path || "");
  const name = full.slice(Math.max(full.lastIndexOf("/"), full.lastIndexOf(String.fromCharCode(92))) + 1);
  if (/[.]exe$/i.test(name)) {
    return /tailscale/i.test(name)
      ? "这是 Tailscale 的安装程序，不是组件包。Tailscale 要用官方安装包装好并登录，不用在这里导入。"
      : "这里需要组件包 ZIP，不是可执行文件。";
  }
  if (!info) return "自检没有返回结论。";
  const version = String(info.version || "");
  if (info.ok) {
    return version ? "已识别为「" + (IMPORT_TITLE[key] || key) + "」组件包，版本 " + version + "。"
      : String(info.text || "自检通过。");
  }
  if (info.kind === "not_component") return "这个 ZIP 里没有组件清单，不是本程序的组件包。";
  if (info.kind === "incompatible_manifest") {
    const versionEl = $("#help-version");
    const shown = versionEl ? String(versionEl.textContent || "").trim() : "";
    if (shown && shown !== "—") {
      return "这个组件包和现在的 " + shown + " 不配套。到发布页下载 " + shown + " 的组件包。";
    }
  }
  return String(info.text || "自检没有返回结论。");
}

/* PH11：下载失败照原型拼「下载没有完成：原因，可以重试。」。G2：限流、超时和断网分开说——
 * 限流是 GitHub 按出口 IP 限制查询次数，等一会或去发布页手动下载都能绕过，不是连不上；
 * 超时（连上了但没在时限内回包）与连不上（根本没连上）也要分开，用户才知道该等还是查网络；
 * 认不出的码（比如这个版本没有发布组件包、校验没过）回落后端原话，不硬套。 */
const PHONE_DOWNLOAD_REASON = {
  network_error: "连不上发布页",
  http_error: "GitHub 暂时无法响应，请稍后重试",
  rate_limited: "GitHub 暂时限制了查询次数，过一会再试，或到发布页手动下载后导入",
  timeout: "连接超时",
  not_published: "发布页上还没有这个版本的组件包，可以稍后再试，或手动下载后导入",
};

function downloadFailText(download) {
  const snap = download || {};
  const code = String(snap.error_code || "");
  const reason = PHONE_DOWNLOAD_REASON[code];
  // 限速与「发布页上还没有」的原因文案自己说了怎么办，结尾不再加「可以重试」
  if ((code === "rate_limited" || code === "not_published") && reason) return "下载没有完成：" + reason + "。";
  if (reason) return "下载没有完成：" + reason + "，可以重试。";
  return String(snap.text || "下载没有完成，可以重试。");
}

/* PH25：倒计时句改成原型的「m:ss 后失效，一码只能用一次」；点阵二维码和点阵配对码不做（审核决定 3） */
function pairLeftText(seconds) {
  const left = Math.max(0, Math.floor(Number(seconds) || 0));
  return Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0");
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

function phoneShow(selector, visible) {
  const el = $(selector);
  if (el) el.hidden = !visible;
  return el;
}

function phoneText(selector, text) {
  const el = $(selector);
  if (el) {
    el.textContent = String(text || "");
    el.hidden = !text;
  }
  return el;
}

const PhonePanel = {
  state: {
    running: false, address: "", pair_code: "", qr: "", channel: "",
    pair_code_status: null, paired_count: 0, live_session: false,
    feature: { ready: false, available: false }, advanced: {},
    preferred_channel: "", tailscale_autostart: false,
  },
  busy: false,
  // 开启/关闭是有耗时的动作（Cloudflare 要等隧道出域名），单独记一个进行中状态，
  // 既防重复点击，也让按钮自己说明「在做什么」而不是看起来卡住
  pending: "",
  pollTimer: null,
  pollTicks: 0,
  tickTimer: null,
  lastCode: "",
  // 用户在通道卡里点的那一条；没点过时用快照里记住的偏好
  channel: "",
  // PH30：反馈就地显示在各块里，不再写抽屉最底部（用户在上面点，底部那行可能在屏幕外）
  notes: { feature: "", missing: "", loading: "", off: "", offErr: "", pair: "", onErr: "" },
  // PH28 关闭确认开着；PH29 点了「再配对一台手机」（addPairAt 记点的时候已经配过几台）
  stopAsk: false,
  addPair: false,
  addPairAt: 0,
  copied: false,
  copyTimer: null,
  // PH09：组件位置只走电脑端专用接口 B3，取不到就是 null，界面不显示也不编
  location: null,
  lastDownload: "",
  // 配对码倒计时：快照给剩余秒数，两次刷新之间每秒自减，不读墙钟
  codeLeft: 0,
  codeSync: null,
  // 对话框里「选中的文件」与「自检通过的文件」分开记：自检不过时不能安装
  picked: { phone_control: "", relogin_ocr: "" },
  verified: { phone_control: "", relogin_ocr: "" },
  // 清除账号要先确认：确认行开着时不能被轮询刷新顺手关掉
  clearConfirm: false,
  // CR11：账号表单是否展开、行内反馈（CR19）；导入弹窗当前在导入哪个组件（IM01）
  credForm: false,
  credNote: "",
  credNoteTone: "ok",
  importKey: "phone_control",
  // I1：点「安装这份」到 refresh 返回为止，按功能记「安装中」；这段时间快照还是导入前的旧状态，不能照旧画
  installing: { phone_control: false, relogin_ocr: false },

  async refresh() {
    try {
      const info = await api("phone_access_state");
      if (info && info.ok) PhonePanel.state = Object.assign(PhonePanel.state, info);
    } catch (err) {
      /* 帮助弹窗打不开状态时不影响其他帮助工具。 */
    }
    await PhonePanel.loadLocation();
    PhonePanel.paint();
    PhonePanel.paintComponents();
    // 开着手机访问（配对码会过期或被用掉后换新）或组件在后台下载时才轮询
    if (PhonePanel.needsPolling()) PhonePanel.startPolling();
    else PhonePanel.stopPolling();
    if (PhonePanel.state.running) PhonePanel.startTick();
    else PhonePanel.stopTick();
  },

  /* PH09：位置只问一次就记住（数据目录这次运行里不会变）；没拿到就下次刷新再问 */
  async loadLocation() {
    if (PhonePanel.location) return;
    try {
      const loc = await api("advanced_component_location", "phone_control");
      PhonePanel.location = (loc && loc.ok && loc.short)
        ? { path: String(loc.path || ""), short: String(loc.short) } : null;
    } catch (err) {
      PhonePanel.location = null;
    }
  },

  downloadActive() {
    const features = (PhonePanel.state.advanced && PhonePanel.state.advanced.features) || {};
    return ["phone_control", "relogin_ocr"].some((key) => {
      const state = String((((features[key] || {}).download) || {}).state || "");
      return state === "downloading" || state === "verifying";
    });
  },

  needsPolling() {
    return !!PhonePanel.state.running || PhonePanel.downloadActive();
  },

  /* 五秒一次只问本机内存里的状态。抽屉开着时每次都问：下载进度、配对码和「手机已连接」要及时；
   * 抽屉关着时只为顶栏手机标识每 15 秒问一次，没开手机访问就不问；窗口最小化不问。 */
  startPolling() {
    if (typeof setInterval !== "function" || PhonePanel.pollTimer) return;
    PhonePanel.pollTicks = 0;
    PhonePanel.pollTimer = setInterval(() => {
      if (!PhonePanel.needsPolling()) { PhonePanel.stopPolling(); return; }
      if (PhonePanel.busy || document.hidden) return;
      PhonePanel.pollTicks += 1;
      const drawer = $("#settings");
      const drawerClosed = !!(drawer && drawer.hidden);
      if (drawerClosed && (!PhonePanel.state.running || PhonePanel.pollTicks % 3 !== 0)) return;
      void PhonePanel.refresh();
    }, 5000);
  },

  stopPolling() {
    if (PhonePanel.pollTimer && typeof clearInterval === "function") {
      clearInterval(PhonePanel.pollTimer);
    }
    PhonePanel.pollTimer = null;
  },

  startTick() {
    if (typeof setInterval !== "function" || PhonePanel.tickTimer) return;
    PhonePanel.tickTimer = setInterval(() => {
      if (PhonePanel.codeLeft > 0) {
        PhonePanel.codeLeft -= 1;
        PhonePanel.paintCountdown();
      }
    }, 1000);
  },

  stopTick() {
    if (PhonePanel.tickTimer && typeof clearInterval === "function") {
      clearInterval(PhonePanel.tickTimer);
    }
    PhonePanel.tickTimer = null;
  },

  feature(key) {
    return (PhonePanel.state.advanced && PhonePanel.state.advanced.features || {})[key]
      || {};
  },

  /* 正在跑的那条通道以快照的 active_channel 为准（服务端说了算）；没在跑时
     才用用户在卡片里点的那一条，避免「界面显示 A、实际跑 B」。 */
  selectedChannel() {
    const st = PhonePanel.state;
    if (st.running) {
      const active = String(st.active_channel || st.channel || "");
      if (active) return active;
    }
    const prefs = (st.advanced && st.advanced.phone_access) || {};
    const chosen = String(PhonePanel.channel || st.preferred_channel
      || prefs.preferred_channel || "tailscale");
    return chosen === "cloudflare" ? "cloudflare" : "tailscale";
  },

  paint() {
    /* 顶栏手机标识与手机详情卡跟着同一份快照刷新（views/status-cards.js） */
    if (typeof paintStatusCards === "function") paintStatusCards();
    const st = PhonePanel.state;
    const busy = !!PhonePanel.busy;
    // 手机控制既可能来自 state.feature，也可能来自 advanced.features；合并后以 advanced 为准
    const phoneRow = Object.assign({}, st.feature || {}, PhonePanel.feature("phone_control"));
    const ocrRow = PhonePanel.feature("relogin_ocr");
    const phoneRemove = $("#btn-phone-feature-remove");
    const cred = (st.advanced && st.advanced.credential) || {};

    PhonePanel.paintPhoneAccess(st, phoneRow, cred);
    if (phoneRemove) phoneRemove.disabled = busy;
    PhonePanel.paintRelogin(cred, ocrRow);
    /* 验证码识别一节的状态、按钮和文案由设置抽屉按组件快照与下载事务统一决定（views/settings.js） */
    if (typeof paintOcrDownload === "function") paintOcrDownload();
  },

  /* 登录恢复一组（settings-gap 三、CR01–CR22，原型 credView，Main.dc.html 1388–1398）。
   * 审核决定 A3：先看 saved 再看 staged——暂存区也会放保存账号的副本（手机重新登录要用），所以 staged 单独为真
   * 不等于「只用这一次」；「这次运行的账号」= 没保存、但暂存区有（CR06）。
   * 冲突 5（CR20）：这次运行的账号和保存过的一样能自动登录，所以识别已启用时结论行写「已启用」。
   * 「这次那份被学校拒了」时 staged 变假、automatic.state 是 paused：表里没有这一档的文案，按「还没有账号密码」显示。 */
  paintRelogin(cred, ocrRow) {
    const busy = !!PhonePanel.busy;
    const saved = !!cred.saved;
    const once = !saved && !!cred.staged;
    const has = saved || once;
    const ocrReady = !!(ocrRow.ready || cred.ocr_ready);
    const ocrInstalled = !ocrReady && !!ocrRow.available && String(ocrRow.status || "") !== "failed";
    const storeOk = !(cred.store_available === false || cred.available === false);
    const formOn = !!PhonePanel.credForm;
    const ask = !!PhonePanel.clearConfirm;

    // CR05：表单展开或清除确认中隐藏；否则没有账号「填写账号密码」，有账号「更换」
    const slot = $("#btn-credentials-manage");
    if (slot) {
      slot.hidden = formOn || ask;
      slot.disabled = busy;
      slot.textContent = has ? "更换" : "填写账号密码";
    }
    // CR06：没账号时不显示这一行；只用这一次的打码账号只用后端给的 staged_hint，没有就不显示，不编
    const credLine = $("#relogin-credential-status");
    if (credLine) {
      const text = saved ? "已保存账号 " + maskAccount(cred.username) + "。"
        : (once && cred.staged_hint
          ? "这次运行可以用账号 " + String(cred.staged_hint) + " 重新登录，关闭工具后自动清除。" : "");
      credLine.textContent = text;
      credLine.hidden = !text;
    }
    // CR07 / CR20：四种结论；保存的密码被拒走 CR18 的单独红字，这里不再写括号
    const autoPath = $("#relogin-auto-path");
    if (autoPath) {
      let text;
      let cls = "";
      if (!has) {
        text = "失效后自动登录：未启用，还没有账号密码。登录失效后要手动重新登录；报名计划开放前 100 秒内失效的场次会直接结束。";
      } else if (ocrReady) {
        text = "失效后自动登录：已启用。登录失效时电脑自己重新登录，报名计划等开放或提交时也一样，不用你动手。";
        cls = "up-ok";
      } else if (ocrInstalled) {
        text = "失效后自动登录：验证码识别本机已装，还没启用（在上面“高级功能”里点“启用”）。现在登录失效时要你输验证码；报名计划开放前 100 秒内失效的场次会直接结束。";
        cls = "up-warn";
      } else if (String(ocrRow.status || "") === "checking") {
        text = "失效后自动登录：正在检查验证码识别组件。";
      } else if (String(ocrRow.status || "") === "outdated") {
        text = "失效后自动登录：验证码识别组件需要随新版本更新（在上面“高级功能”里点“更新组件”）。更新前登录失效时要你输验证码；报名计划开放前 100 秒内失效的场次会直接结束。";
        cls = "up-warn";
      } else {
        text = "失效后自动登录：还缺验证码识别组件（在上面的“高级功能”里一键安装）。现在登录失效时要你输验证码；报名计划开放前 100 秒内失效的场次会直接结束。";
        cls = "up-warn";
      }
      autoPath.textContent = text;
      autoPath.className = cls;
    }
    // CR03 的「存储不可用」、CR09、CR10 三行原型没有、代码里有真实信号，保留（kept_not_in_prototype）
    const storeNote = $("#relogin-store-note");
    if (storeNote) storeNote.hidden = storeOk;
    const lastLine = $("#relogin-last-used");
    if (lastLine) {
      const origin = String(cred.last_origin || "");
      const ago = Number((cred.automatic && cred.automatic.last_used_ago_s) || 0);
      if (origin === "auto_ocr") lastLine.textContent = "最近一次登录：由电脑自动恢复完成。";
      else if (origin === "phone_manual") lastLine.textContent = "最近一次登录：在手机上手动完成。";
      else if (ago > 0) lastLine.textContent = "最近一次自动恢复：" + agoText(ago) + "。";
      else lastLine.textContent = "最近一次登录：暂无记录。";
    }
    const phonePath = $("#relogin-phone-path");
    if (phonePath) {
      phonePath.textContent = ocrReady
        ? "手机上重新登录：验证码先由电脑自动识别，认不出来再由你输入。"
        : "手机上重新登录：验证码由你输入；手机上也可以输账号密码，默认不保存。";
    }
    // CR11 / CR14 / CR15：表单、勾选项与按钮
    phoneShow("#credential-editor", formOn);
    PhonePanel.paintCredForm();
    // CR16 / CR17：「清除已保存」只有保存过的账号才有，表单和确认展开时隐藏；确认块红底
    phoneShow("#relogin-clear-row", saved && !formOn && !ask);
    const credClear = $("#btn-credentials-clear");
    if (credClear) credClear.disabled = busy;
    phoneShow("#relogin-clear-confirm", ask);
    // CR18：保存的密码学校不认，单独一条红字
    phoneShow("#relogin-bad", !!cred.paused && has && !formOn);
    // CR19 / CR21：操作结果就地说，不再写抽屉底部那一行
    const note = $("#credential-note");
    if (note) {
      note.textContent = PhonePanel.credNote;
      note.hidden = !PhonePanel.credNote;
      note.className = PhonePanel.credNoteTone === "bad" ? "ph-err" : "ph-note";
    }
  },

  /* CR12 / CR14：保存按钮随勾选项改名，账号或密码为空时禁用。
   * 本机加密存储不可用（kept）时只能「只用这一次」，勾选项锁住；而且手机控制和验证码识别都没装时没处用，按钮不开。 */
  paintCredForm() {
    const st = PhonePanel.state;
    const cred = (st.advanced && st.advanced.credential) || {};
    const storeOk = !(cred.store_available === false || cred.available === false);
    const onceBox = $("#credential-once");
    if (onceBox) {
      if (!storeOk) onceBox.checked = true;
      onceBox.disabled = !!PhonePanel.busy || !storeOk;
    }
    const once = !storeOk || !!(onceBox && onceBox.checked);
    const user = $("#credential-user");
    const pass = $("#credential-pass");
    const empty = !String((user && user.value) || "").trim() || !String((pass && pass.value) || "");
    const phoneRow = Object.assign({}, st.feature || {}, PhonePanel.feature("phone_control"));
    const ocrRow = PhonePanel.feature("relogin_ocr");
    const usable = !!phoneRow.ready || !!(ocrRow.ready || cred.ocr_ready);
    const save = $("#btn-credentials-save");
    if (save) {
      save.textContent = once ? "只用这一次" : "保存到本机";
      save.disabled = !!PhonePanel.busy || empty || (!storeOk && !usable);
    }
  },

  /* 手机访问一组（settings-gap 一、PH01–PH32），按 phonePhase 的状态机逐块显隐。
   * 文案逐字照原型 phView；原型没画的状态（PH14b 等）保留现状。 */
  paintPhoneAccess(st, phoneRow, cred) {
    const busy = !!PhonePanel.busy;
    const pending = String(PhonePanel.pending || "");
    const starting = pending === "starting";
    const download = phoneRow.download || {};
    const dl = String(download.state || "");
    const phase = phonePhase(st, phoneRow);
    // I1：安装中（点「安装这份」到 refresh 返回为止）快照还是导入前的旧状态，不画旧红条与导入行
    const installing = !!(PhonePanel.installing && PhonePanel.installing.phone_control);
    const downloading = phase === "downloading" || phase === "verifying";
    const loading = downloading || phase === "checking" || installing;
    const linked = phoneLinkedNow(st);
    const notes = PhonePanel.notes;
    const channels = (st.advanced && st.advanced.channels) || {};
    const cloudflare = channels.cloudflare || {};
    const tailscale = channels.tailscale || {};
    // 组件 ready 只说明源码版的模块能导入；Cloudflare 通道真正要的是组件包
    // （cloudflared + 校验信息）。通道报「组件缺失」时入口必须还在，否则用户
    // 看到「不可用」却没有任何地方能补装，界面就把自己锁死了（原型没画，保留现状）。
    const componentMissing = cloudflare.error === "cloudflared_missing"
      || cloudflare.state === "missing";
    const failed = dl === "failed";

    // PH32：亲眼看着下载 → 校验 → 装好，才说一句「已安装」；刷新到旧的 installed 不重复说
    const prev = PhonePanel.lastDownload;
    if ((prev === "downloading" || prev === "verifying") && dl === "installed") {
      notes.off = "手机控制组件已安装，选一条通道就能开启。";
    }
    PhonePanel.lastDownload = dl;
    if (!st.running) {
      PhonePanel.stopAsk = false;
      PhonePanel.addPair = false;
      notes.pair = "";
      notes.onErr = "";
    }

    // PH03 标题行：右侧二选一——没装或下载中放按钮，装好后放状态 chip
    const install = $("#btn-phone-component-install");
    if (install) {
      install.hidden = phase !== "missing" && phase !== "outdated";
      install.disabled = busy || installing;
      install.textContent = phase === "outdated" ? "更新组件"
        : (failed ? "重新下载" : "下载并安装");
    }
    const cancel = $("#btn-phone-component-cancel");
    if (cancel) {
      cancel.hidden = !downloading;
      cancel.disabled = busy || phase === "verifying";
      cancel.textContent = phase === "verifying" ? "校验中…" : "取消下载";
    }
    // 原型没画的三种（保留现状）：加载失败要重新导入、启用位没开要启用（走 B2）、缺 cloudflared 要补装
    const featureBtn = $("#btn-phone-feature-install");
    const featureAction = phase === "broken" ? "重新导入组件包"
      : (phase === "disabled" ? "启用手机控制"
        : (phase === "off" && componentMissing ? "安装/更换组件包" : ""));
    if (featureBtn) {
      featureBtn.hidden = !featureAction;
      featureBtn.disabled = busy;
      featureBtn.textContent = featureAction;
      featureBtn.dataset.action = phase === "disabled" ? "enable" : "import";
    }
    // PH06：chip 说的是「手机访问开没开」，不是「组件装没装」；没装和下载中没有 chip
    const chip = $("#phone-feature-status");
    if (chip) {
      let text = "";
      let tone = "";
      if (phase === "off") text = "未开启";
      else if (phase === "on") { text = linked ? "手机已连接" : "等手机连接"; tone = linked ? "ok" : "warn"; }
      else if (phase === "outdated") { text = "需要更新"; tone = "warn"; }
      else if (phase === "broken") { text = "加载失败"; tone = "warn"; }
      else if (phase === "disabled") text = "已停用";
      chip.hidden = !text;
      chip.textContent = text;
      chip.className = "ph-st" + (tone ? " " + tone : "");
      chip.dataset.state = phase;
    }
    // PH05：lead 随状态变
    const lead = $("#phone-feature-note");
    if (lead) {
      lead.textContent = phase === "on"
        ? (linked ? "手机可以查看活动、开始和停止计划。程序退出后手机就打不开了。"
          : "第一次连接要扫码和配对。扫码只负责打开页面，配对靠这 6 位数。")
        : phase === "off"
          ? (starting ? "正在开启，先不要切换通道。" : "选一条通道再开启。没开启时不监听端口，手机连不上电脑。")
          : phase === "outdated"
            ? "主程序已升级，组件需要随新版本更新。点「更新组件」重新装一份，手机访问不用重新配对。"
            : downloading ? "可以关掉设置继续用，下载和报名计划互不影响。"
            : "从手机查看活动、开始和停止计划。手机只是遥控器，真正报名的还是这台电脑，所以电脑要开着、不能睡眠。";
    }
    phoneText("#phone-feature-error", (phase === "broken" || phase === "disabled") ? notes.feature : "");

    phoneShow("#phone-missing", phase === "missing" && !installing);
    phoneShow("#phone-loading", loading);
    phoneShow("#phone-access-detail", phase === "off" || phase === "on");
    phoneShow("#phone-off", phase === "off");
    phoneShow("#phone-on", phase === "on");

    // ---- 没装（PH08–PH12）----
    // 更新失败后状态回到「需要更新」，原因同样要看得见；红条在「没装」块外，块收着也显示
    const missingErr = ((phase === "missing" || phase === "outdated") && !installing)
      ? (notes.missing || (failed ? downloadFailText(download) : "")) : "";
    phoneText("#phone-component-error", missingErr);
    // PH12：取消后回到没装态；已装过组件再取消的场景原型没有，落在 off 那块说现有组件没动
    phoneText("#phone-component-state", phase === "missing" && !missingErr && dl === "cancelled"
      ? "下载已取消，没有装任何东西。" : "");
    // PH10：导入链接只在下载失败后出现；更新失败停在 outdated 时也要留着这条兜底
    phoneShow("#phone-import-line", (phase === "missing" || phase === "outdated") && failed && !installing);
    const loc = PhonePanel.location;
    phoneShow("#phone-loc-before", phase === "missing" && !!loc);
    const after = phoneShow("#phone-loc-after", phase !== "missing" && !loading && !!loc);
    ["#phone-loc-before", "#phone-loc-after"].forEach((sel) => {
      const box = $(sel);
      const code = $(sel + "-path");
      if (box && loc) box.title = loc.path || loc.short;
      if (code) code.textContent = loc ? loc.short : "";
    });
    if (after) {
      const open = $("#btn-phone-open-loc");
      if (open) open.disabled = busy;
    }

    // ---- 下载中 / 校验中（PH13–PH15），进度条墨色（styles.css .ph-bar）----
    const total = Number(download.total_bytes || 0);
    const done = Number(download.downloaded || 0);
    const pct = phase === "verifying" ? 100
      : (total > 0 ? Math.max(0, Math.min(100, Math.round((done / total) * 100))) : 0);
    phoneText("#phone-prog-text", installing ? "正在安装组件…"
      : (phase === "checking" ? "正在检查组件…"
      : (phase === "verifying" ? "下载完成，正在校验组件…" : "正在下载手机控制组件")));
    const num = $("#phone-prog-num");
    if (num) {
      num.textContent = phase === "downloading" && total > 0
        ? (done / 1048576).toFixed(1) + " / " + (total / 1048576).toFixed(1) + " MB" : "";
    }
    const bar = $("#phone-component-progress");
    if (bar) bar.setAttribute("aria-valuenow", String(pct));
    const fill = $("#phone-prog-fill");
    if (fill && fill.style) fill.style.width = pct + "%";
    phoneText("#phone-loading-error", loading ? notes.loading : "");

    // ---- 装好未开启（PH16–PH21、PH31、PH32）----
    const selected = PhonePanel.selectedChannel();
    const cards = channelCards(channels);
    ["tailscale", "cloudflare"].forEach((key) => {
      const card = cards[key];
      const radio = $("#phone-chan-" + key);
      const label = $("#phone-chan-" + key + "-card");
      const status = $("#phone-chan-" + key + "-status");
      if (radio) {
        radio.checked = selected === key;
        // 启动中整组禁用：开到一半换通道，拿到的地址会和界面对不上
        radio.disabled = busy || !!pending;
      }
      if (label) label.className = "chan" + (selected === key ? " on" : "");
      if (status) {
        status.textContent = card.status;
        status.className = "chan-s " + card.tone;
        status.dataset.state = String((channels[key] || {}).state || "unknown");
      }
      phoneText("#phone-chan-" + key + "-text", card.text);
    });
    const tsBad = selected === "tailscale" && !tailscale.available;
    const start = $("#btn-phone-start");
    if (start) {
      start.hidden = !!st.running;
      // 组件还在下载/校验时、Tailscale 没连上时都不许点（PH18）
      start.disabled = busy || !!pending || loading || tsBad;
      start.textContent = starting ? "启动中…" : "开启手机访问";
    }
    const recheck = phoneShow("#btn-tailscale-recheck", tsBad && !starting);
    if (recheck) recheck.disabled = busy;
    // PH20：提示就在按钮下面一行
    let hint = "";
    if (tsBad && tailscale.state === "not_logged_in") hint = "还差一步：登录 Tailscale 后点“重新检测”，或者改用 Cloudflare。";
    else if (tsBad && tailscale.state === "missing") hint = "还差一步：装好 Tailscale 后点“重新检测”，或者改用 Cloudflare。";
    if (starting && selected === "cloudflare") hint = "正在建立临时隧道，最多等 20 秒。";
    phoneText("#phone-channel-hint", hint);
    // PH31：隧道断开时快照里 running 已被置假，cloudflare.state 是 exited
    const tunnelGone = cloudflare.state === "exited" || cloudflare.error === "tunnel_exited";
    phoneText("#phone-off-error", phase === "off"
      ? (notes.offErr || (failed ? downloadFailText(download)
        : (tunnelGone ? "Cloudflare 隧道断了，旧地址和二维码已失效。重新开启后要重新扫码配对。" : ""))) : "");
    phoneText("#phone-off-note", phase === "off"
      ? (notes.off || (dl === "cancelled" ? "下载已取消，现有组件没有改动。" : "")) : "");

    // ---- 已开启（PH22–PH29）----
    phoneShow("#phone-ok", phase === "on" && linked);
    // PH24（审核决定 A3）：先看 saved 再看 staged；「没有账号」= 既没保存、也没有这次运行的
    phoneShow("#phone-cred-tip", phase === "on" && linked && !cred.saved && !cred.staged);
    const pairedCount = Number(st.paired_count || 0);
    if (PhonePanel.addPair && pairedCount > PhonePanel.addPairAt) PhonePanel.addPair = false;
    const showPair = !linked || PhonePanel.addPair;
    phoneShow("#phone-pair", phase === "on" && showPair);
    const codeInfo = st.pair_code_status || {};
    const codeText = st.running ? String(codeInfo.code || st.pair_code || "") : "";
    const code = $("#phone-code");
    if (code) code.textContent = codeText || "—";
    if (st.pair_code_status !== PhonePanel.codeSync) {
      PhonePanel.codeSync = st.pair_code_status;
      PhonePanel.codeLeft = Math.max(0, Math.floor(Number(codeInfo.expires_in || 0)));
    }
    PhonePanel.paintCountdown();
    // 换来新码必须当场说一声：静默换码会让用户拿着旧码反复对不上
    if (st.running && codeText) {
      const last = PhonePanel.lastCode;
      if (last && last !== codeText) {
        const why = String(codeInfo.reason || "");
        // 被兑换换出的新码由「手机已连接」那条绿条说明，这里不重复
        if (why === "expired") notes.pair = "配对码已过期，已经换成新的。";
        else if (why !== "paired") notes.pair = "配对码已更新。";
      }
      PhonePanel.lastCode = codeText;
    } else if (!st.running) {
      PhonePanel.lastCode = "";
    }
    phoneText("#phone-pair-note", phase === "on" && showPair ? notes.pair : "");
    const qr = $("#phone-qr");
    if (qr) {
      qr.hidden = !st.running || !st.qr;
      if (st.qr) qr.src = String(st.qr);
    }
    phoneShow("#phone-qr-empty", !(st.running && st.qr));
    // PH26：地址行；MagicDNS 为主，100.x 作备用
    const address = $("#phone-address");
    if (address) address.textContent = st.running ? String(st.address || "") : "未开启";
    const addresses = tailscale.addresses || [];
    const portMatch = /:(\d+)\//.exec(String(st.address || ""));
    const port = portMatch ? portMatch[1] : "8765";
    const alt = (st.running && selected === "tailscale" && addresses.length)
      ? "http://" + String(addresses[0]) + ":" + port + "/" : "";
    const addressAlt = $("#phone-address-alt");
    if (addressAlt) addressAlt.textContent = alt;
    phoneShow("#phone-address-alt-line", !!alt && alt !== String(st.address || ""));
    const copyButton = $("#btn-phone-address-copy");
    if (copyButton) {
      copyButton.hidden = !st.running;
      copyButton.disabled = busy || !st.running;
      copyButton.textContent = PhonePanel.copied ? "已复制" : "复制";
    }
    // PH27：临时地址用警告色说会变；固定地址才值得存书签
    const channelNote = $("#phone-channel-note");
    if (channelNote) {
      const temporary = selected === "cloudflare";
      channelNote.className = temporary ? "ph-warn" : "ph-note";
      channelNote.textContent = temporary
        ? "这是临时地址：关闭访问或重启程序后就会变，手机要重新扫码配对。"
        : "地址固定，建议在手机上存成书签，下次直接打开。";
    }
    phoneText("#phone-on-error", phase === "on" ? notes.onErr : "");
    // PH28：确认块开着时收起「关闭手机访问」那一行
    phoneShow("#phone-stop-confirm", phase === "on" && PhonePanel.stopAsk);
    phoneShow("#phone-stop-row", !PhonePanel.stopAsk);
    const stop = $("#btn-phone-stop");
    if (stop) {
      stop.hidden = !st.running;
      stop.disabled = busy || !!pending;
      stop.textContent = pending === "stopping" ? "关闭中…" : "关闭手机访问";
    }
    // PH29：已连接、配对区收起时才给「再配对一台手机」
    const addPair = phoneShow("#btn-phone-add-pair", phase === "on" && linked && !showPair);
    if (addPair) addPair.disabled = busy;
  },

  /* PH25：倒计时每秒走一格，两次刷新之间不必等后端 */
  paintCountdown() {
    const note = $("#pair-code-note");
    if (!note) return;
    note.innerHTML = PhonePanel.codeLeft > 0
      ? "<b>" + pairLeftText(PhonePanel.codeLeft) + "</b> 后失效，一码只能用一次"
      : "配对码已过期，正在换新";
  },

  /* 导入已下载的组件包（原型 impView，IM01）：一次只导入一个组件，标题随 key 变；
     程序不代选文件，选错东西由自检当场说明它到底是什么。 */
  openComponents(key) {
    const dlg = $("#dlg-components");
    if (!dlg) return;
    const which = key === "relogin_ocr" ? "relogin_ocr" : "phone_control";
    PhonePanel.importKey = which;
    PhonePanel.picked = { phone_control: "", relogin_ocr: "" };
    PhonePanel.verified = { phone_control: "", relogin_ocr: "" };
    ["comp-phone", "comp-ocr"].forEach((prefix) => {
      const pathEl = $("#" + prefix + "-path");
      if (pathEl) pathEl.value = "";
      PhonePanel.showComponentNote(prefix, "", false);
    });
    PhonePanel.paintComponents();
    if (typeof dlg.showModal === "function") dlg.showModal();
    else dlg.setAttribute("open", "");
  },

  paintComponents() {
    const key = PhonePanel.importKey === "relogin_ocr" ? "relogin_ocr" : "phone_control";
    const title = $("#dlg-components-title");
    if (title) title.textContent = key === "relogin_ocr" ? "导入验证码识别组件" : "导入手机控制组件";
    [{ k: "phone_control", prefix: "comp-phone" }, { k: "relogin_ocr", prefix: "comp-ocr" }].forEach(({ k, prefix }) => {
      const here = k === key;
      phoneShow("#" + prefix, here);
      const installEl = phoneShow("#btn-" + prefix + "-install", here);
      const pathEl = $("#" + prefix + "-path");
      if (pathEl && PhonePanel.picked && PhonePanel.picked[k]) pathEl.value = PhonePanel.picked[k];
      const verified = PhonePanel.verified && PhonePanel.verified[k];
      if (installEl) installEl.disabled = !verified;
    });
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

  /* 选完文件立刻自检（IM01 没有单独的「自检」按钮）。.exe 不进后端：这里只接收组件包 ZIP（IM01，
     裸 cloudflared.exe 的入口随弹窗改版去掉，后端接口不动）；结论文案在 importCheckText（IM03）。 */
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
    const isExe = /[.]exe$/i.test(chosen);
    const info = isExe ? { ok: false, kind: "not_zip" } : await api("inspect_advanced_component", key, chosen);
    PhonePanel.showComponentNote(prefix, importCheckText(key, chosen, info), !!(info && info.ok));
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

  /* 装好后关掉弹窗，结论就地说在抽屉里对应的那一节（原型 impInstall：imp 置空，再给一句 note） */
  async installComponent(key) {
    const prefix = key === "phone_control" ? "comp-phone" : "comp-ocr";
    const chosen = String((PhonePanel.verified || {})[key] || "");
    if (!chosen) {
      PhonePanel.showComponentNote(prefix, "先选文件并自检通过，再安装。", false);
      return;
    }
    // I1：置位到 refresh 返回为止，抽屉与对话框都按「安装中」画，不按导入前的旧快照说失败
    PhonePanel.installing[key] = true;
    PhonePanel.paint();
    const installEl = $("#btn-" + prefix + "-install");
    if (installEl) { installEl.disabled = true; installEl.textContent = "安装中…"; }
    try {
      const result = await api("install_advanced_feature", key, chosen);
      const ok = !!(result && result.ok);
      if (!ok) {
        PhonePanel.showComponentNote(prefix, (result && result.text) || "安装没有完成。", false);
      } else {
        PhonePanel.picked[key] = "";
        PhonePanel.verified[key] = "";
        const pathEl = $("#" + prefix + "-path");
        if (pathEl) pathEl.value = "";
        PhonePanel.showComponentNote(prefix, "", false);
        // PH32 / OC15：导入装好后在对应的那一节说一句（原型 impInstall）
        if (key === "phone_control") {
          PhonePanel.notes.off = "手机控制组件已导入并启用，选一条通道就能开启。";
          PhonePanel.notes.missing = "";
        } else if (typeof OcrPanel !== "undefined") {
          OcrPanel.note = "验证码识别组件已导入并启用。";
          OcrPanel.error = "";
        }
        PhonePanel.closeComponents();
        await PhonePanel.refresh();
      }
    } finally {
      PhonePanel.installing[key] = false;
      if (installEl) installEl.textContent = "安装这份";
      PhonePanel.paintComponents();
      // refresh 已按「安装中」画过一遍；这里按刷新后的真实快照重画（失败路径也要把旧红条放回来）
      PhonePanel.paint();
    }
  },

  closeComponents() {
    const dlg = $("#dlg-components");
    if (!dlg) return;
    if (typeof dlg.close === "function" && dlg.hasAttribute && dlg.hasAttribute("open")) dlg.close();
    else dlg.removeAttribute("open");
  },

  /* 标题行右侧那颗「原型没画」的按钮：启用位没开就走 B2 启用，其余（加载失败、缺 cloudflared）打开导入弹窗 */
  featureAction() {
    const btn = $("#btn-phone-feature-install");
    if (btn && btn.dataset && btn.dataset.action === "enable") {
      void PhonePanel.enableFeature();
      return;
    }
    PhonePanel.openComponents("phone_control");
  },

  async enableFeature() {
    if (PhonePanel.busy) return;
    PhonePanel.busy = true;
    PhonePanel.notes.feature = "";
    PhonePanel.paint();
    let result = null;
    try {
      result = await api("enable_advanced_feature", "phone_control");
    } catch (err) {
      result = { ok: false, text: "没有启用，请重试。" };
    } finally {
      PhonePanel.busy = false;
    }
    if (result && result.ok) PhonePanel.notes.off = "手机控制已启用，选一条通道就能开启。";
    else PhonePanel.notes.feature = String((result && result.text) || "没有启用，请重试。");
    await PhonePanel.refresh();
  },

  async toggleStart() {
    if (PhonePanel.busy || PhonePanel.pending) return;
    const chosen = PhonePanel.selectedChannel();
    PhonePanel.busy = true;
    PhonePanel.pending = "starting";
    PhonePanel.notes.off = "";
    PhonePanel.notes.offErr = "";
    PhonePanel.paint();
    try {
      const result = await api("start_phone_access", chosen);
      if (!result || !result.ok) {
        PhonePanel.notes.offErr = String((result && result.text) || "手机访问没有开启。");
      } else {
        PhonePanel.notes.pair = "";
        PhonePanel.addPair = false;
      }
    } catch (err) {
      PhonePanel.notes.offErr = "手机访问没有开启。";
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
    PhonePanel.notes.onErr = "";
    PhonePanel.paint();
    try {
      const result = await api("stop_phone_access");
      if (result && result.ok === false) {
        PhonePanel.notes.onErr = String((result && result.text) || "手机访问没有关闭。");
      } else {
        PhonePanel.notes.off = "手机访问已关闭，手机需要重新配对才能再进。";
        PhonePanel.notes.offErr = "";
      }
    } catch (err) {
      PhonePanel.notes.onErr = "手机访问没有关闭。";
    } finally {
      PhonePanel.pending = "";
      PhonePanel.busy = false;
      await PhonePanel.refresh();
    }
  },

  /* 关闭是破坏性的（手机立刻失去权限、要重新扫码），所以先问一句再动手（PH28） */
  askStop() {
    PhonePanel.stopAsk = true;
    PhonePanel.paint();
  },

  cancelStop() {
    PhonePanel.stopAsk = false;
    PhonePanel.paint();
  },

  async confirmStop() {
    PhonePanel.stopAsk = false;
    PhonePanel.paint();
    await PhonePanel.toggleStop();
  },

  /* PH29：已连接后再配一台，重新显示配对区；新手机配上（paired_count 变大）后自动收起 */
  addPairing() {
    PhonePanel.addPair = true;
    PhonePanel.addPairAt = Number(PhonePanel.state.paired_count || 0);
    PhonePanel.notes.pair = "";
    PhonePanel.paint();
  },

  /* PH24「去保存」（CR22）：打开设置的登录组、展开账号密码表单并聚焦账号框。表单已经开着就不清用户输到一半的内容 */
  goSaveCredentials() {
    if (typeof openSettings === "function") openSettings("login");
    if (!PhonePanel.credForm) {
      PhonePanel.credNote = "";
      const onceBox = $("#credential-once");
      if (onceBox) onceBox.checked = false;
    }
    PhonePanel.credForm = true;
    const editor = $("#credential-editor");
    if (editor) editor.hidden = false;
    PhonePanel.paint();
    const user = $("#credential-user");
    if (user && typeof user.focus === "function") user.focus();
  },

  async openComponentDir() {
    let result = null;
    try {
      result = await api("open_advanced_component_dir", "phone_control");
    } catch (err) {
      result = { ok: false };
    }
    if (result && result.ok) return;
    const text = String((result && result.text) || "打不开所在文件夹。");
    const phase = phonePhase(PhonePanel.state,
      Object.assign({}, PhonePanel.state.feature || {}, PhonePanel.feature("phone_control")));
    if (phase === "on") PhonePanel.notes.onErr = text;
    else if (phase === "off") PhonePanel.notes.offErr = text;
    else PhonePanel.notes.feature = text;
    PhonePanel.paint();
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

  /* PH26：复制后按钮 1.6 秒内显示「已复制」，失败才在本块红字说明 */
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
    PhonePanel.notes.onErr = done ? "" : "复制没有成功，请手动选中地址。";
    PhonePanel.copied = done;
    if (PhonePanel.copyTimer && typeof clearTimeout === "function") clearTimeout(PhonePanel.copyTimer);
    PhonePanel.copyTimer = done && typeof setTimeout === "function"
      ? setTimeout(() => { PhonePanel.copied = false; PhonePanel.copyTimer = null; PhonePanel.paint(); }, 1600)
      : null;
    PhonePanel.paint();
  },

  /* 组件下载：一次点击就走完「取地址 → 下载 → 校验 → 安装」，用户不用选文件。
   * key 为 phone_control（手机控制）或 relogin_ocr（验证码识别），两者同一条后端事务。 */
  async downloadComponent(key) {
    const feature = key === "relogin_ocr" ? "relogin_ocr" : "phone_control";
    if (PhonePanel.busy) return;
    PhonePanel.busy = true;
    if (feature === "phone_control") PhonePanel.notes.missing = "";
    PhonePanel.paint();
    let result = null;
    try {
      result = await api("download_advanced_feature", feature);
    } catch (err) {
      result = { ok: false, text: "组件下载没有开始，请稍后重试。" };
    } finally {
      PhonePanel.busy = false;
    }
    if (feature === "relogin_ocr") {
      // OC11 / OC15：反馈就地写在验证码识别那一节（views/settings.js OcrPanel），不再走抽屉底部；开始下载不另说，进度块会出现
      if (typeof OcrPanel !== "undefined") {
        OcrPanel.note = "";
        OcrPanel.error = result && result.ok ? "" : String((result && result.text) || "组件下载没有开始。");
      }
    } else if (!(result && result.ok)) {
      PhonePanel.notes.missing = String((result && result.text) || "组件下载没有开始。");
    }
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
    if (feature === "relogin_ocr") {
      // OC13：成功后回到没装态，取消的那句话由快照的 cancelled 派生（写在 views/settings.js）；失败才在本节红条里说
      if (typeof OcrPanel !== "undefined") {
        OcrPanel.note = "";
        OcrPanel.error = result && result.ok === false
          ? String((result && result.text) || "取消没有生效，请稍后重试。") : "";
      }
    } else {
      // 手机控制：成功后回到没装态，那句话由快照的 cancelled 派生（PH12）；失败就在进度下面说
      PhonePanel.notes.loading = result && result.ok === false
        ? String((result && result.text) || "取消没有生效，请稍后重试。") : "";
    }
    await PhonePanel.refresh();
  },

  /* 换通道只记偏好：不重启当前监听，也不偷偷帮用户把隧道切过去 */
  async changeChannel(value) {
    const chosen = String(value || "");
    if (!chosen) return;
    PhonePanel.channel = chosen;
    PhonePanel.notes.off = "";
    PhonePanel.notes.offErr = "";
    PhonePanel.paint();
    try {
      await api("set_phone_access_preferences", chosen);
    } catch (err) {
      /* 记忆失败不影响本次选择，只是下次要重选 */
    }
    await PhonePanel.refresh();
  },

  /* PH30：重新检测的结论就地说；仍没连上时通道卡和提示行已经说清差哪一步 */
  async recheckTailscale() {
    await PhonePanel.refresh();
    const channels = (PhonePanel.state.advanced && PhonePanel.state.advanced.channels) || {};
    if ((channels.tailscale || {}).available) {
      PhonePanel.notes.off = "已重新检测：Tailscale 已连接。";
      PhonePanel.paint();
    }
  },

  /* CR11 / CR12 / CR19：勾了「只在这次运行中用」或本机加密存储不可用，就只把账号放进内存（prepare_phone_relogin，
   * 不落盘）；否则加密保存。成功后收起表单、就地说一句；失败留着表单，只给通用文案，不带异常原文。 */
  async saveCredentials() {
    const user = $("#credential-user");
    const pass = $("#credential-pass");
    if (!user || !pass) return;
    const username = String(user.value || "");
    const password = String(pass.value || "");
    const cred = (PhonePanel.state.advanced && PhonePanel.state.advanced.credential) || {};
    const onceBox = $("#credential-once");
    const once = !!(onceBox && onceBox.checked) || !cred.available;
    let result = null;
    PhonePanel.busy = true;
    PhonePanel.paint();
    try {
      result = once
        ? await api("prepare_phone_relogin", username, password)
        : await api("save_relogin_credentials", username, password);
    } catch (err) {
      // 失败原因可能含账号细节，只给通用文案，不把异常原文带给用户
      result = { ok: false, text: "账号信息没有保存。" };
    } finally {
      user.value = "";
      pass.value = "";
      PhonePanel.busy = false;
    }
    if (result && result.ok) {
      PhonePanel.credForm = false;
      PhonePanel.credNote = once ? "已准备好，只在这次运行中使用。" : "已加密保存到本机。";
      PhonePanel.credNoteTone = "ok";
    } else {
      PhonePanel.credNote = String((result && result.text) || "账号信息没有保存。");
      PhonePanel.credNoteTone = "bad";
    }
    await PhonePanel.refresh();
  },

  /* CR05：标题行按钮展开表单——清掉旧反馈和上次的输入，勾选项回到默认（保存到本机） */
  openCredForm() {
    PhonePanel.credForm = true;
    PhonePanel.credNote = "";
    const user = $("#credential-user");
    const pass = $("#credential-pass");
    const onceBox = $("#credential-once");
    if (user) user.value = "";
    if (pass) pass.value = "";
    if (onceBox) onceBox.checked = false;
    PhonePanel.paint();
    if (user && typeof user.focus === "function") user.focus();
  },

  /* CR15：取消——清空输入并收起表单 */
  cancelCredForm() {
    PhonePanel.credForm = false;
    const user = $("#credential-user");
    const pass = $("#credential-pass");
    if (user) user.value = "";
    if (pass) pass.value = "";
    PhonePanel.paint();
  },

  /* 清除账号先展开确认行：这是不可撤销的动作，不能一点就删 */
  askClearCredentials() {
    PhonePanel.clearConfirm = true;
    PhonePanel.credNote = "";
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
    let result = null;
    try {
      result = await api("clear_relogin_credentials");
    } catch (err) {
      result = { ok: false };
    }
    PhonePanel.credNote = (result && result.ok) ? "已清除本机保存的账号密码。" : "清除没有完成。";
    PhonePanel.credNoteTone = (result && result.ok) ? "ok" : "bad";
    await PhonePanel.refresh();
  },

  wire() {
    const start = $("#btn-phone-start");
    const stop = $("#btn-phone-stop");
    const manage = $("#btn-credentials-manage");
    const save = $("#btn-credentials-save");
    const clear = $("#btn-credentials-clear");
    const recheck = $("#btn-tailscale-recheck");
    const copy = $("#btn-phone-address-copy");
    const stopCancel = $("#btn-phone-stop-cancel");
    const stopConfirm = $("#btn-phone-stop-confirm");
    // PH07：没装时标题行的「下载并安装」直接一键下载（决策 010 第 54 行），不再打开导入弹窗
    const compInstall = $("#btn-phone-component-install");
    if (compInstall) compInstall.addEventListener("click", () => void PhonePanel.downloadComponent("phone_control"));
    const compCancel = $("#btn-phone-component-cancel");
    if (compCancel) compCancel.addEventListener("click", () => void PhonePanel.cancelComponent("phone_control"));
    const featureBtn = $("#btn-phone-feature-install");
    if (featureBtn) featureBtn.addEventListener("click", () => PhonePanel.featureAction());
    // PH10：下载失败后才露出的「导入已下载的组件包」
    const importPhone = $("#btn-phone-import");
    if (importPhone) importPhone.addEventListener("click", () => PhonePanel.openComponents("phone_control"));
    const pickPhone = $("#btn-comp-phone-pick");
    if (pickPhone) pickPhone.addEventListener("click", () => void PhonePanel.pickComponent("phone_control"));
    const pickOcr = $("#btn-comp-ocr-pick");
    if (pickOcr) pickOcr.addEventListener("click", () => void PhonePanel.pickComponent("relogin_ocr"));
    const installPhoneFile = $("#btn-comp-phone-install");
    if (installPhoneFile) installPhoneFile.addEventListener("click", () => void PhonePanel.installComponent("phone_control"));
    const installOcrFile = $("#btn-comp-ocr-install");
    if (installOcrFile) installOcrFile.addEventListener("click", () => void PhonePanel.installComponent("relogin_ocr"));
    const closeComponents = $("#btn-comp-close");
    if (closeComponents) closeComponents.addEventListener("click", () => PhonePanel.closeComponents());
    // PH16：两张单选卡，选中即记偏好
    ["tailscale", "cloudflare"].forEach((key) => {
      const radio = $("#phone-chan-" + key);
      if (radio) radio.addEventListener("change", () => void PhonePanel.changeChannel(key));
    });
    if (start) start.addEventListener("click", () => void PhonePanel.toggleStart());
    if (stop) stop.addEventListener("click", () => PhonePanel.askStop());
    if (stopCancel) stopCancel.addEventListener("click", () => PhonePanel.cancelStop());
    if (stopConfirm) stopConfirm.addEventListener("click", () => void PhonePanel.confirmStop());
    const addPair = $("#btn-phone-add-pair");
    if (addPair) addPair.addEventListener("click", () => PhonePanel.addPairing());
    const credGo = $("#btn-phone-cred-go");
    if (credGo) credGo.addEventListener("click", () => PhonePanel.goSaveCredentials());
    const openLoc = $("#btn-phone-open-loc");
    if (openLoc) openLoc.addEventListener("click", () => void PhonePanel.openComponentDir());
    if (recheck) recheck.addEventListener("click", () => void PhonePanel.recheckTailscale());
    if (copy) copy.addEventListener("click", () => void PhonePanel.copyAddress());
    if (manage) manage.addEventListener("click", () => PhonePanel.openCredForm());
    const credCancel = $("#btn-credentials-cancel");
    if (credCancel) credCancel.addEventListener("click", () => PhonePanel.cancelCredForm());
    // CR14：账号或密码为空时保存按钮禁用；CR12：勾选项改按钮名
    ["#credential-user", "#credential-pass"].forEach((sel) => {
      const field = $(sel);
      if (field) field.addEventListener("input", () => PhonePanel.paintCredForm());
    });
    const onceBox = $("#credential-once");
    if (onceBox) onceBox.addEventListener("change", () => PhonePanel.paintCredForm());
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
