/* 登录恢复的状态层：账号打码与「还差 N 步」清单模型（纯函数，不碰 DOM / window）；
 * maskAccount 被计划面板这个普通脚本用到，经过渡名单挂回 window。 */

import { ocrPhase } from "../components/state-ocr.js";

/* 账号打码：前两位加后两位，中间四个星号（与后端 domain/login_rules.mask_account 同一规则） */
export function maskAccount(name) {
  const text = String(name || "").trim();
  if (!text) return "已保存";
  return text.length >= 5 ? text.slice(0, 2) + "****" + text.slice(-2) : text.slice(0, 1) + "****";
}

function step2DownloadSub(ocrRow) {
  const dl = (ocrRow && ocrRow.download) || {};
  const done = Number(dl.downloaded) || 0;
  const total = Number(dl.total_bytes) || 0;
  if (total <= 0) return "正在下载…";
  return "正在下载（" + Math.floor(done / total * 100) + "%）";
}

/* 第 2 步（验证码识别组件）清单一行的派生文案与动作（与 view-ocr 共用 ocrPhase 状态机）。 */
export function step2Checklist(ocrRow, cred) {
  const o = ocrRow || {};
  const c = cred || {};
  const rawPhase = ocrPhase(o);
  const phase = rawPhase === "missing" && c.ocr_ready ? "on" : rawPhase;
  const ok = phase === "on";
  const unreadable = !ok && !!(o.read_error || o.check_timed_out);
  const warn = phase === "off" || phase === "outdated" || phase === "broken";
  const subMap = {
    on: "已启用（连续 3 次认错转手动）",
    off: "本机已安装，还没启用",
    verifying: "下载完成，正在校验…",
    outdated: "需要随新版本更新",
    broken: "组件损坏，需要修复",
    checking: "正在检查组件…",
  };
  const sub = unreadable ? "状态暂未读到"
    : (phase === "downloading" ? step2DownloadSub(o) : (subMap[phase] || "未安装（可选）"));
  const btnMap = {
    on: "查看组件",
    off: "启用",
    missing: "去安装",
    outdated: "去更新",
    broken: "去修复",
    downloading: "查看进度",
    verifying: "查看进度",
  };
  return {
    ok: ok,
    phase: phase,
    cls: ok ? "done" : (warn ? "warn" : ""),
    mark: ok ? "✓" : (warn ? "!" : "2"),
    sub: sub,
    subCls: ok ? "ok" : (warn ? "warn" : ""),
    btnLabel: btnMap[phase] || "去检查",
    action: phase === "off" ? "enable" : "go_ocr",
  };
}

/* 登录组「失效后自动登录」二步清单模型（D6，对应原型 credView）。 */
export function loginChecklistModel(cred, ocrRow) {
  const c = cred || {};
  const saved = !!c.saved;
  const once = !saved && !!c.staged;
  const has = saved || once;
  const bad = !!c.paused;
  const credOk = has && !bad;
  const masked = saved ? maskAccount(c.username) : String(c.staged_hint || "");
  const s1Sub = !has ? "未保存（只加密存在这台电脑）"
    : (bad ? "学校不认账号 " + (masked || "已保存") + " 的密码，需要更换"
      : (saved ? "已加密保存 " + masked
        : (masked ? "这次运行会用 " + masked + "，退出后清除" : "已准备好，只在这次运行中使用")));
  const step2 = step2Checklist(ocrRow, c);
  const leftN = (credOk ? 0 : 1) + (step2.ok ? 0 : 1);
  const foot = leftN === 0
    ? "两步都完成了：计划期间登录失效会全自动恢复，不用人守着。"
    : (!credOk && step2.ok
      ? "保存账号密码后就能自动登录，否则失效后要手动重新登录。"
      : "装好并启用验证码识别后，失效才能无人值守恢复；目前需要手动输验证码。");
  return {
    leftN: leftN,
    headStatus: leftN === 0 ? "已就绪" : "还差 " + leftN + " 步",
    headCls: leftN === 0 ? "green" : (has && bad ? "red" : "amber"),
    has: has,
    saved: saved,
    credOk: credOk,
    bad: bad,
    s1Cls: credOk ? "done" : (has && bad ? "bad" : ""),
    s1Mark: credOk ? "✓" : (has && bad ? "!" : "1"),
    s1Sub: s1Sub,
    s1SubCls: has && bad ? "bad" : (credOk ? "ok" : ""),
    slotLabel: has ? "更换" : "填写账号密码",
    slotCls: (!has || (has && bad)) ? "btn-solid" : "btn-line",
    s2Cls: step2.cls,
    s2Mark: step2.mark,
    s2Sub: step2.sub,
    s2SubCls: step2.subCls,
    s2BtnLabel: step2.btnLabel,
    s2Action: step2.action,
    ocrReady: step2.ok,
    foot: foot,
  };
}
