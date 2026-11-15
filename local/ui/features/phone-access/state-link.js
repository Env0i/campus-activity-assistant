/* 手机连接状态（「现在连着没有」）：设置抽屉的 chip、顶栏手机标识与手机详情卡共用一份推导。
 * 后端 phone_access_state 带 link 与 last_contact_ago_s，规则在 local/domain/phone_rules.py
 * 的 phone_link_state，阈值 PHONE_IDLE_DISCONNECT_S = 120（手机两分钟没来算已断开）。
 * 四种状态在屏幕上的样子：
 *   off          没开：抽屉 chip 写「未开启」，顶栏标识收起，详情卡写「未开启」；
 *   waiting      开着但手机还没来过：抽屉 chip 与顶栏标识都写「等手机连接」，详情卡小 chip 同字；
 *   connected    手机来过：抽屉 chip 与顶栏标识写「手机已连接」，标识带 is-ok，详情卡小 chip「已连接」；
 *   disconnected 手机两分钟没来：写「已断开 · N 分钟前」，标识不带 is-ok，详情卡小 chip「已断开」。
 * 「配过对没有」是另一件事，仍由 state.js 的 phoneLinkedNow 判断（配对码、绿条、详情卡配对行）。
 * 纯函数：不碰 DOM、不发请求、不用定时器、不读时钟。 */

import { agoText, phoneLinkedNow } from "./state.js";

/* 推导只会给出这四个值，测试按这份清单核对 */
export const PHONE_LINK_STATES = Object.freeze(["off", "waiting", "connected", "disconnected"]);

/* 四种状态各自的屏上文字与语气；off 的标题行为空（标识收起，详情卡另写「手机访问未开启」） */
const LINK_TEXT = {
  off: { title: "", big: "手机访问未开启", chip: "未开启", tone: "" },
  waiting: { title: "等手机连接", big: "等手机连接", chip: "等连接", tone: "warn" },
  connected: { title: "手机已连接", big: "手机已连接", chip: "已连接", tone: "ok" },
  disconnected: { title: "已断开", big: "已断开", chip: "已断开", tone: "" },
};

/* 秒数不是数字（还没来访过）时不写「N 分钟前」，只写「已断开」 */
function contactAgo(ago) {
  if (ago === null || ago === undefined || ago === "") return "";
  const value = Number(ago);
  return Number.isFinite(value) ? agoText(value) : "";
}

/* tail 才加在文字后面（只有「已断开」要「· 2 分钟前」）；ago 一律单独带出去，
 * 详情卡的「手机最近访问」用它，已连接时读得到「12 秒前」而标题仍是「手机已连接」 */
function withAgo(link, tail, ago) {
  const base = LINK_TEXT[link];
  const suffix = tail ? " · " + tail : "";
  return { link: link, title: base.title + suffix, big: base.big + suffix,
           chip: base.chip, tone: base.tone, ago: ago || "" };
}

export function phoneLinkView(st) {
  const state = st || {};
  if (!state.running) return withAgo("off", "", "");
  const ago = contactAgo(state.last_contact_ago_s);
  const link = String(state.link || "");
  if (link === "waiting" || link === "connected") return withAgo(link, "", ago);
  if (link === "disconnected") return withAgo(link, ago, ago);
  /* 没有 link、unknown，或开着却给了 off：退回配对与活动会话的两档规则，老快照下界面一字不变 */
  return withAgo(phoneLinkedNow(state) ? "connected" : "waiting", "", ago);
}
