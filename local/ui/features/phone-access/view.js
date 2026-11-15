/* 手机面板的视图层：取元素与写文案的小工具，加手机访问一组的三段绘制；
 * 不发桥接请求，不调编排层的方法。 */


import { PhonePanel, channelCards, pairLeftText, phoneLinkedNow, phonePhase, retryWaitBase } from "./state.js";
import { componentState } from "../components/state-machine.js";
import { BROKEN_NOTE, paintComponentRow } from "../components/view-row.js";
import { downloadFailText } from "../components/state.js";
import { paintOcrDownload } from "../components/view-ocr.js";



/* 手机控制这一行的元素 id 与固定文字：共有部分由 features/components/view-row.js
 * 的 paintComponentRow 画，行与行的差别（下载文案等）由这里的 spec 常量与调用方
 * 算好的 texts 保留。 */
const PHONE_ROW_SPEC = {
  installId: "#btn-phone-component-install",
  cancelId: "#btn-phone-component-cancel",
  missingId: "#phone-missing",
  importLineId: "#phone-import-line",
  loadingId: "#phone-loading",
  progTextId: "#phone-prog-text",
  progNumId: "#phone-prog-num",
  progressBarId: "#phone-component-progress",
  progFillId: "#phone-prog-fill",
  errorId: "#phone-component-error",
  probeId: "#phone-probe",
  retryId: "#btn-phone-component-retry",
  locIds: ["#phone-loc-before", "#phone-loc-after"],
  openLocId: "#btn-phone-open-loc",
  downloadText: "正在下载手机控制组件",
};



export function phoneShow(selector, visible) {
  const el = $(selector);
  if (el) el.hidden = !visible;
  return el;
}



export function phoneText(selector, text) {
  const el = $(selector);
  if (el) {
    el.textContent = String(text || "");
    el.hidden = !text;
  }
  return el;
}



export const phonePaintPack = {

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
    /* 验证码识别一节的状态、按钮和文案由设置抽屉按组件快照与下载事务统一决定（features/components/view-ocr.js） */
    if (typeof paintOcrDownload === "function") paintOcrDownload();
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

    // 组件那一行（标题行两个按钮、没装块、导入兜底、进度块、位置两行、红条、读状态说明）
    // 由两行共有的 paintComponentRow 画；手机访问开着时状态机按 running 直接给装好，
    // 这里不再改写 facts。
    const facts = componentState(phoneRow, {
      busy: busy, installing: installing, location: PhonePanel.location,
      running: !!st.running, retryWaitBase: retryWaitBase("phone_control"),
    });
    // 手机行的红条：没装、需要更新或坏了才显示；先说面板留的备注，其次下载失败那句，
    // 坏了又没失败过就说明文件本身不完整
    const componentErr = (phase === "missing" || phase === "outdated" || phase === "broken")
      && !installing
      ? (notes.missing || (failed ? downloadFailText(download)
        : (phase === "broken" ? BROKEN_NOTE : ""))) : "";
    paintComponentRow(PHONE_ROW_SPEC, facts, { componentError: componentErr });
    // 原型没画的两种（保留现状）：启用位没开要启用（走 B2）、缺 cloudflared 要补装；
    // 读不到组件状态时两个都不给——那时连装没装都还没有结论
    const featureBtn = $("#btn-phone-feature-install");
    const featureAction = phase === "disabled" ? "启用手机控制"
      : (phase === "off" && componentMissing ? "安装/更换组件包" : "");
    if (featureBtn) {
      featureBtn.hidden = !featureAction || !!facts.probe;
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

    phoneShow("#phone-access-detail", phase === "off" || phase === "on");
    phoneShow("#phone-off", phase === "off");
    phoneShow("#phone-on", phase === "on");
    // 进度块里的加载错误行只有手机行有；进度块本体与文字由共有绘制画
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

};
