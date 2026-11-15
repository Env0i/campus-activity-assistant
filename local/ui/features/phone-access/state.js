/* 手机面板的状态层：手机访问的状态机推导、通道卡与倒计时文案、账号打码以外的
 * 纯推导函数，以及 PhonePanel 本体（全部字段加四个只读推导方法）；其余方法由
 * actions-panel.js 用 Object.assign 从各方法包装回来。 */


"use strict";



/* 帮助里的跨设备入口与高级功能安装状态。
 * 入口沿用帮助弹窗的工具行，手机地址只在服务已开启时展示；密码字段在每次
 * 请求后清空，二维码只编码当前地址，不把配对码拼进 URL。 */

/* 验证码识别一节的状态、按钮和文案在 features/components/view-ocr.js（paintOcrDownload）；这里管手机访问、登录恢复和导入弹窗。 */



/* 手机访问状态机（settings-gap PH07，原型 phView，Main.dc.html 1244–1308）：
 * missing 没装 / downloading 下载中 / verifying 校验中 / checking 检查中（组件事务锁被占、还没结论，不是没装）/
 * off 装好未开启（含开启中）/ on 已开启。
 * 原型没画、代码里真有的两档保留现状（kept_not_in_prototype）：broken 已装但加载失败（PH14b）、
 * disabled 组件在本机但启用位没开（换机迁移、手动改过设置）。 */
export function phonePhase(st, row) {
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
export function phoneLinkedNow(st) {
  return !!(st && st.running) && (Number(st.paired_count || 0) > 0 || st.live_session === true);
}



/* PH17：两张通道卡的文案逐字照原型 phView（1270–1273 行）；卡名写在 index.html 里。
 * 「暂时读不到状态」「不可用」两档原型没有（检测本身失败、组件包缺 cloudflared），保留现状。 */
export function channelCards(channels) {
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



/* PH25：倒计时句改成原型的「m:ss 后失效，一码只能用一次」；点阵二维码和点阵配对码不做（审核决定 3） */
export function pairLeftText(seconds) {
  const left = Math.max(0, Math.floor(Number(seconds) || 0));
  return Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0");
}

/* 「多久以前」的人话：秒/分/小时/天四档，超过一天不再精确到分钟。 */
export function agoText(seconds) {
  const s = Math.max(0, Math.floor(Number(seconds) || 0));
  if (s < 60) return s + " 秒前";
  if (s < 3600) return Math.floor(s / 60) + " 分钟前";
  if (s < 86400) return Math.floor(s / 3600) + " 小时前";
  return Math.floor(s / 86400) + " 天前";
}



export const PhonePanel = {

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

};
