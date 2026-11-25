/* 计划栏草稿段的纯推导：自动登录前提与开始前提醒。 */

import { maskAccount } from "../login/state-recovery.js";
import { termsLocked } from "../terms/state.js";
import { PhonePanel } from "../phone-access/state.js";

/* 电脑自动登录要用到的三件事：保存了账号、装了验证码识别、保存的密码没被学校拒绝过。
 * 读 advanced_features_state.credential（bootstrap 与手机面板刷新都带）；读不到就当没开。
 * mask 是打码账号，只在后端给了 username 时才有（打码规则与手机页同一个函数）。 */
export function autoLoginCredential() {
  const phone = window.PhonePanel && window.PhonePanel.state && window.PhonePanel.state.advanced;
  const adv = phone || S.advanced || {};
  const cred = adv.credential || {};
  const mask = cred.username && typeof maskAccount === "function" ? maskAccount(cred.username) : "";
  return { saved: !!cred.saved, ocr: !!cred.ocr_ready, paused: !!cred.paused, mask: mask, username: String(cred.username || "") };
}

export function latestSelectedOpen() {
  let best = null;
  selectedItems().forEach((item) => {
    const ts = toTs(item.sign_start);
    if (ts !== null && (best === null || ts > best)) best = ts;
  });
  return best;
}

/* 开始前提醒五条（原型 preWarn / loginWarn）：断网 / 沿用上次校准 / 最晚一场要等 1 小时以上又没开全自动登录 /
 * 直到报名截止但缺截止时间 / 最晚一场 24 小时以后（按最晚一场算，旧界面按最早一场，有意改的） */
export function preStartWarnings() {
  const items = selectedItems();
  if (!items.length || S.busy || termsLocked() || S.runtime.error) return [];
  const list = [];
  if (!S.online) list.push({ tone: "bad", text: "现在连不上网。到开放时间还没恢复，就提交不出去。" });
  if (!S.demo && clockUiState() === "holdover") {
    /* 误差取时钟快照的估计误差；拿不到就不写这一段 */
    const reading = clockReading();
    const ms = reading ? Number(reading.uncertaintyMs) : NaN;
    const err = Number.isFinite(ms) && ms > 0 ? "，误差" + clockUncertaintyText(ms) : "";
    list.push({ tone: "warn", text: "北京时间在用上次的校准结果" + err + "，工具正在自动重试校准。" });
  }
  const now = bnowS();
  const latest = latestSelectedOpen();
  const cred = autoLoginCredential();
  /* 原型 loginWarn 只在登录有效时提醒（没登录 / 失效由「还差一步」承担，不叠两句） */
  const loginOk = !!S.demo || (S.login.view || {}).state === "ok";
  if (loginOk && now !== null && latest !== null && latest - now > 3600 && !(cred.saved && cred.ocr && !cred.paused)) {
    /* 保存了账号、只差验证码识别 → 去安装；没保存或保存的密码学校不认（代码独有）→ 去保存 */
    const has = cred.saved && !cred.paused;
    const missing = has ? "验证码识别没装" : (cred.paused ? "保存的密码学校不认" : "自动登录没开");
    const until = hmsDay(latest).slice(0, -3);
    list.push({
      tone: "warn",
      /* U+2060：窄档下「重/新登录」不拆行（断行扫描 NarrowWarn 实测） */
      text: "要等到" + (/^\d/.test(until) ? " " : "") + until + "，" + missing + "。中途登录失效要你"
        + (has ? "输验证码" : "重⁠新登录") + "；开放前 100 秒内失效，那场就结束。",
      act: has ? "go-ocr" : "go-cred", label: has ? "去安装" : "去保存",
    });
  }
  if (S.retryPolicy.retry_for_s === 0) {
    const noEnd = items.filter((item) => !toTs(item.sign_end));
    if (noEnd.length) {
      list.push({ tone: "warn", text: "「" + noEnd[0].name + "」" + (noEnd.length > 1 ? "等 " + noEnd.length + " 场" : "")
        + "没给报名截止时间，“直到报名截止”对它只会尝试 2 分钟。" });
    }
  }
  if (now !== null && latest !== null && latest - now > 86400) {
    list.push({ tone: "warn", text: "有场次 24 小时后才开放，这段时间电脑别关机、别睡眠。" });
  }
  return list;
}
