/* 设置抽屉「高级功能」组里一项一行的标题行推导：给两份组件行（手机控制、验证码识别）
 * 算出圆点颜色、状态句、主按钮、标题行下那句小字与进度条。
 *
 * 这一层只管「该显示成什么样」，不碰 DOM、不发桥接请求、不读时钟、不用定时器；
 * 状态判定仍由 ../components/state-machine.js 的 componentState 与
 * ../phone-access/state.js 的 phonePhase 负责，这里只按它们给的事实与调用方
 * 另外算好的几项（面板忙、所选通道、组件版本、面板备注）挑一句话。
 * 界面口径见 docs/UI_SPEC.md 的「设置里的组件行」一节，画法照
 * design/prototype/workbench-2026-11 的 AdvCheck.dc.html 一类画板。 */



/* 圆点颜色的清单：灰没装或没开、蓝正在做、绿能用、琥珀要留意、红坏了；
 * amber-dot 是「只有圆点变琥珀、字不变色」，用在读不到组件状态那一档 */
export const ROW_TONES = Object.freeze(["grey", "blue", "green", "amber", "red", "amber-dot"]);

/* 组件文件坏了时两行都写的说明：账号与设置不在组件包里，重装不会动它们 */
export const BROKEN_NOTE = "组件文件不完整。重新安装不会动你的账号和设置。";

const WAIT_TEXT = "另一个窗口正在安装或更新组件，已等 30 秒";
const CHECKING_TEXT = "正在确认组件状态…";
const UNREADABLE_TEXT = "暂时读不到组件状态";
const RETRY_TEXT = "重试";
const CANCEL_TEXT = "取消";
const VERIFY_CANCEL_TEXT = "校验中…";
const OUTDATED_NOTE_PHONE = "主程序升级了，组件要跟着换；手机不用重新配对。";
const OUTDATED_NOTE_OCR = "主程序升级了，组件要跟着换；账号密码不用重填。";



/* 两条展开区的开合：一次运行内记住，不落盘。手机访问默认展开，验证码识别默认收起 */
const ROW_OPEN = { phone: true, ocr: false };



export function rowOpen(kind) {
  return !!ROW_OPEN[kind === "ocr" ? "ocr" : "phone"];
}



export function setRowOpen(kind, open) {
  ROW_OPEN[kind === "ocr" ? "ocr" : "phone"] = !!open;
}



function megabytes(value) {
  const bytes = Number(value || 0);
  return bytes > 0 ? (bytes / 1048576).toFixed(1) : "";
}



/* 下载中那句带上已下与总量：总量读不到时只说「下载中」，不编数字 */
function downloadingText(download) {
  const total = megabytes(download && download.total_bytes);
  const done = megabytes(download && download.downloaded);
  return total && done ? "下载中 " + done + " / " + total + " MB" : "下载中";
}



function progressOf(download) {
  const total = Number((download && download.total_bytes) || 0);
  const done = Number((download && download.downloaded) || 0);
  if (total <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((done / total) * 100)));
}



/* 主按钮这一格的文字：有结论的状态各自说清这一下会做什么，其余（没装、或只是下载失败过）
 * 都是重新下一份 */
function installLabel(state, failed) {
  if (state === "outdated") return "更新组件";
  if (state === "broken") return "重新安装";
  return failed ? "重新下载" : "下载并安装";
}



function button(label, cls, action, disabled) {
  return { label: label, cls: cls || "btn-line", action: action || "", disabled: !!disabled };
}



/* 手机访问这一行独有的两档：组件停用了要重新启用，没开启要选通道再开 */
function phoneIdleHead(phase, env, head) {
  if (phase === "disabled") {
    head.text = "已停用";
    head.tone = "grey";
    head.button = button("启用手机控制", "btn-line", "enable", env.busy);
    return true;
  }
  if (phase !== "off") return false;
  if (env.starting) {
    head.text = "正在开启…";
    head.tone = "blue";
    return true;
  }
  head.text = "未开启 · 通道用 " + (env.channelName || "Tailscale");
  head.tone = "grey";
  /* 按钮位只放「开启 / 重新开启」：缺 cloudflared 时补装那只收在展开区，不占标题行 */
  head.button = button(env.startFailed ? "重新开启" : "开启", "btn-solid", "start", env.startDisabled);
  /* 开不起来的原因不放这里：它属于「这次出错了」，由手机行标题行下的红条承担 */
  return true;
}



/* 已开启这一档：字与颜色取 phoneLinkView 的结论，等手机连接时圆点慢闪 */
function phoneRunningHead(env, head) {
  if (env.stopping) {
    head.text = "正在停止…";
    head.tone = "blue";
    return;
  }
  const link = env.link || {};
  head.text = String(link.title || "等手机连接");
  head.tone = link.link === "connected" ? "green" : (link.link === "waiting" ? "amber" : "grey");
  head.blink = link.link === "waiting";
  head.button = button("关闭手机访问", "btn-line", "stop", env.stopAsk);
}



/* 组件行共有的六档：没装、下载中、校验中、安装中、检查中、需要更新、坏了 */
function componentHead(kind, phase, facts, env, head) {
  const download = (facts && facts.download) || {};
  if (phase === "missing") {
    head.text = "没装";
    head.tone = "grey";
    head.button = button(installLabel("missing", facts.failed), "btn-solid", "install");
    return true;
  }
  if (phase === "downloading") {
    head.text = downloadingText(download);
    head.tone = "blue";
    head.bar = progressOf(download);
    head.button = button(CANCEL_TEXT, "btn-line", "cancel");
    return true;
  }
  if (phase === "verifying") {
    head.text = "下载完了，正在校验…";
    head.tone = "blue";
    head.bar = 100;
    /* 校验中这只按钮只是「告诉你还在校验」，所以沿用取消那一格的位置、禁用着 */
    head.button = button(VERIFY_CANCEL_TEXT, "btn-line", "cancel");
    return true;
  }
  if (phase === "installing") {
    head.text = "正在安装组件…";
    head.tone = "blue";
    return true;
  }
  if (phase === "checking") {
    head.text = CHECKING_TEXT;
    head.tone = "blue";
    return true;
  }
  if (phase === "outdated") {
    head.text = "需要更新";
    head.tone = "amber";
    head.button = button(installLabel("outdated", facts.failed), "btn-solid", "install");
    head.note = { text: kind === "phone" ? OUTDATED_NOTE_PHONE : OUTDATED_NOTE_OCR, tone: "" };
    return true;
  }
  if (phase === "broken") {
    head.text = "加载失败";
    head.tone = "red";
    head.button = button(installLabel("broken", facts.failed), "btn-solid", "install");
    head.note = { text: BROKEN_NOTE, tone: "red" };
    return true;
  }
  return false;
}



/* 读状态（等锁、超时、读不到）压过其余一切：三种都不给「装/更新」这类动作按钮 */
function applyProbe(head, probe, phase) {
  if (probe === "waiting") {
    if (phase === "checking") head.text = CHECKING_TEXT;
    head.tone = "blue";
    head.button = null;
    return;
  }
  if (probe === "timeout") {
    head.text = WAIT_TEXT;
    head.tone = "amber";
    head.button = button(RETRY_TEXT, "btn-line", "retry");
    return;
  }
  if (probe === "unreadable") {
    head.tone = "amber-dot";
    head.note = { text: UNREADABLE_TEXT, tone: "amber" };
    head.button = button(RETRY_TEXT, "btn-line", "retry");
  }
}



/* kind 为 phone 或 ocr；facts 是 componentState 的结果；extra 是状态机不管、
 * 画面要用的几项——phase（phonePhase / ocrPhase 的结论）、starting、stopping、
 * channelName、startDisabled、startFailed、stopAsk、link（phoneLinkView 的结果）、
 * version 与 note（验证码识别装好那句）。 */
export function rowHead(kind, facts, extra) {
  const env = extra || {};
  const data = facts || {};
  const phase = String(env.phase || data.state || "");
  const phone = kind !== "ocr";
  const head = { tone: "grey", text: "", button: null, note: null, bar: null, blink: false };
  if (!componentHead(kind, phase, data, env, head)) {
    if (phone) {
      if (!phoneIdleHead(phase, env, head)) phoneRunningHead(env, head);
    } else if (phase === "off") {
      head.text = "已装好还没启用";
      head.button = button("启用", "btn-solid", "enable");
    } else if (phase === "on") {
      const version = String(env.version || "");
      head.text = version ? "已启用 · 版本 " + version : "已启用";
      head.tone = "green";
      if (env.note) head.note = { text: String(env.note), tone: "green" };
    }
  }
  /* 面板留的备注（刚装好、刚启用）没有别的说明时也要落到标题行下那一行字，
     它是这次动作的结果，与当前是哪个阶段无关 */
  if (!head.note && env.note) head.note = { text: String(env.note), tone: "green" };
  applyProbe(head, String(data.probe || ""), phase);
  return head;
}
