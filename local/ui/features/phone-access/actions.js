/* 手机面板的编排层：手机访问的动作方法包（取快照与轮询、倒计时、启用、开启与
 * 关闭及确认、再配对、复制、换通道、重新检测）；发桥接请求、用定时器与剪贴板的
 * 方法都放在这一层。 */


import { PhonePanel, clearSettledRetryBase } from "./state.js";



export const phoneActionsPack = {

  async refresh() {
    try {
      const info = await api("phone_access_state");
      if (info && info.ok) PhonePanel.state = Object.assign(PhonePanel.state, info);
    } catch (err) {
      /* 帮助弹窗打不开状态时不影响其他帮助工具。 */
    }
    await PhonePanel.loadLocation();
    // 新快照到手后，已经读到结论的那一行不用再记着「重试」的起点
    clearSettledRetryBase();
    PhonePanel.paint();
    PhonePanel.paintComponents();
    // 开着手机访问（配对码会过期或被用掉后换新）或组件在后台下载时才轮询
    if (PhonePanel.needsPolling()) PhonePanel.startPolling();
    else PhonePanel.stopPolling();
    if (PhonePanel.state.running) PhonePanel.startTick();
    else PhonePanel.stopTick();
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

};
