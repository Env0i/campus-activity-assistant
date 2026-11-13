# -*- coding: utf-8 -*-
"""界面契约：手动更新、更新看板与首次使用弹层。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import read, run_js  # noqa: E402


class ManualUpdateUiBehaviorTests(unittest.TestCase):
    """更新通道独立于报名，覆盖请求时序、失败收尾与页面恢复。"""

    def test_late_snapshot_does_not_replace_newer_check(self):
        """接管旧请求后的快照可能晚到，不能覆盖用户随后新开的查询。"""
        res = run_js(r"""
let finishSnapshot, first = true;
window.pywebview = { api: {
  check_update: id => {
    if (first) { first = false; return Promise.resolve({ok:true,queued:true,skipped:true,request_id:"old"}); }
    return Promise.resolve({ok:true,queued:true,request_id:id});
  },
  bootstrap: () => new Promise(resolve => { finishSnapshot = resolve; }),
} };
checkUpdate();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
window.onBackend.update({request_id:"old",state:"current"});
checkUpdate();
const fresh = S.update.requestId;
finishSnapshot({update_check:{checking:false,request_id:"old",result:{request_id:"old",state:"current"}}});
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
const pending = {preserved:S.update.requestId===fresh,state:S.update.state};
window.onBackend.update({request_id:fresh,state:"available",latest_version:"1.2.0"});
out.push({pending,state:S.update.state});
""")
        self.assertEqual(res[0], {"pending": {"preserved": True, "state": "checking"},
                                  "state": "available"})

    def test_result_timestamp_is_not_a_live_check(self):
        res = run_js(r"""
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"current",checked_at:"2026-10-25T15:00:00Z"});
const known = {hidden:document.querySelector("#update-checked-at").hidden,
  text:document.querySelector("#update-checked-at").textContent};
window.onBackend.update({request_id:"request",state:"error",checked_at:"invalid"});
out.push({known,unknownHidden:document.querySelector("#update-checked-at").hidden});
""")
        self.assertFalse(res[0]["known"]["hidden"])
        self.assertIn("检查时间", res[0]["known"]["text"])
        self.assertTrue(res[0]["unknownHidden"])

    def test_open_help_never_queries_update(self):
        res = run_js(r"""
let calls = 0;
window.pywebview = { api: { check_update: () => { calls += 1; } } };
document.querySelector("#btn-help").click();
document.querySelector("#btn-help").click();
out.push({ calls, open: document.querySelector("#help").open,
  state: document.querySelector("#update-status").textContent });
""")
        # 文案跟原型 Main.dc.html:1262 走：空闲态也要说清什么时候才联网
        self.assertEqual(res[0], {"calls": 0, "open": True, "state": "只有点“检查更新”时才联网，下载前还会再确认。"})

    def test_double_click_is_single_flight(self):
        res = run_js(r"""
let calls = 0;
window.pywebview = { api: { check_update: id => { calls += 1; return Promise.resolve({ok:true,queued:true,request_id:id}); } } };
document.querySelector("#btn-update-check").click();
document.querySelector("#btn-update-check").click();
out.push({ calls, disabled: document.querySelector("#btn-update-check").disabled });
""")
        self.assertEqual(res[0], {"calls": 1, "disabled": True})

    def test_result_before_ack_does_not_reenter_checking(self):
        res = run_js(r"""
window.pywebview = { api: { check_update: id => {
  window.onBackend.update({request_id:id,state:"current"});
  return Promise.resolve({ok:true,queued:true,request_id:id});
} } };
document.querySelector("#btn-update-check").click();
await Promise.resolve(); await Promise.resolve();
out.push({state:S.update.state,disabled:document.querySelector("#btn-update-check").disabled});
""")
        self.assertEqual(res[0], {"state": "current", "disabled": False})

    def test_stale_event_cannot_replace_current_request(self):
        res = run_js(r"""
window.pywebview = { api: { check_update: id => Promise.resolve({ok:true,queued:true,request_id:id}) } };
checkUpdate();
const current = S.update.requestId;
window.onBackend.update({request_id:"old",state:"available",latest_version:"9.9.9"});
const stale = S.update.state;
window.onBackend.update({request_id:current,state:"preview",latest_version:"1.0.2"});
out.push({stale,state:S.update.state,text:document.querySelector("#update-status").textContent});
""")
        self.assertEqual(res[0]["stale"], "checking")
        self.assertEqual(res[0]["state"], "preview")
        self.assertIn("1.0.2", res[0]["text"])

    def test_all_terminal_states_restore_button(self):
        res = run_js(r"""
for (const state of ["available","current","preview","unavailable","error"]) {
  S.update.requestId = "request"; S.update.state = "checking";
  window.onBackend.update({request_id:"request",state,latest_version:"1.2.0",text:"连接超时"});
  out.push({state,disabled:document.querySelector("#btn-update-check").disabled,
    text:document.querySelector("#update-status").textContent});
}
""")
        self.assertTrue(all(not item["disabled"] for item in res))
        self.assertIn("发现新版本", res[0]["text"])
        self.assertIn("最新正式版", res[1]["text"])
        self.assertIn("预览", res[2]["text"])
        self.assertEqual(res[3]["text"], "还没有正式发布的版本。")
        self.assertIn("暂时无法检查", res[4]["text"])

    def test_launching_shows_backend_text(self):
        """启动成功的二段文案由后端下发，前端固定「正在启动安装程序…」只是兜底。"""
        res = run_js(r"""
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"launching",
  text:"安装程序已启动。请先关闭本工具，再按向导完成安装。"});
out.push({state:S.update.state,text:document.querySelector("#update-status").textContent});
""")
        self.assertEqual(res[0]["state"], "launching")
        self.assertEqual(res[0]["text"], "安装程序已启动。请先关闭本工具，再按向导完成安装。")

    def test_launcher_started_text_turns_button_into_close_tool(self):
        """版本目录切换（C1）：「更新启动器已启动」与「安装程序已启动」同为第二段文案，
        按钮要从「启动中…」换成「关闭本工具…」，不能一直停在启动中。"""
        res = run_js(r"""
S.update.requestId = "request";
const close = () => document.querySelector("#btn-update-close");
window.onBackend.update({request_id:"request",state:"launching",text:"正在准备重启…"});
out.push({text:close().textContent});
window.onBackend.update({request_id:"request",state:"launching",
  text:"更新启动器已启动，正在关闭本工具完成切换…"});
out.push({text:close().textContent});
window.onBackend.update({request_id:"request",state:"launching",
  text:"安装程序已启动。请先关闭本工具，再按向导完成安装。"});
out.push({text:close().textContent});
""")
        self.assertEqual([item["text"] for item in res],
                         ["启动中…", "关闭本工具…", "关闭本工具…"])

    def test_no_installer_shows_backend_reason(self):
        """no_installer 的三类原因由后端区分下发（update_check.py），前端不得一律说「没有可校验的安装包」。"""
        res = run_js(r"""
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"no_installer",latest_version:"1.2.0",
  text:"发现新版本 1.2.0，但安装包大小与校验信息不一致，请前往下载页手动下载。"});
out.push({state:S.update.state,text:document.querySelector("#update-status").textContent});
""")
        self.assertEqual(res[0]["state"], "no_installer")
        self.assertEqual(res[0]["text"], "发现新版本 1.2.0，但安装包大小与校验信息不一致，请前往下载页手动下载。")

    def test_bridge_reject_is_local_and_recoverable(self):
        res = run_js(r"""
S.runtime.error = "worker_missing"; S.busy = true;
const oldResult = document.querySelector("#result").textContent;
window.pywebview = { api: { check_update: () => Promise.reject(new Error("桥接失败")) } };
checkUpdate();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
out.push({state:S.update.state,runtime:S.runtime.error,busy:S.busy,
  result:document.querySelector("#result").textContent===oldResult,
  disabled:document.querySelector("#btn-update-check").disabled});
""")
        self.assertEqual(res[0], {"state": "error", "runtime": "worker_missing", "busy": True,
                                  "result": True, "disabled": False})

    def test_bootstrap_restores_without_network_query(self):
        res = run_js(r"""
let calls = 0;
window.pywebview = { api: { check_update: () => { calls += 1; } } };
restoreUpdate({checking:true,request_id:"inflight",result:null});
const pending = S.update.state;
restoreUpdate({checking:false,request_id:"inflight",result:{request_id:"inflight",state:"current"}});
out.push({calls,pending,state:S.update.state});
""")
        self.assertEqual(res[0], {"calls": 0, "pending": "checking", "state": "current"})

    def test_lost_event_has_finite_wait(self):
        res = run_js(r"""
const original = setTimeout; let timeout;
setTimeout = fn => { timeout = fn; return 1; };
window.pywebview = { api: { check_update: id => Promise.resolve({ok:true,queued:true,request_id:id}) } };
checkUpdate(); timeout(); setTimeout = original;
out.push({state:S.update.state,disabled:document.querySelector("#btn-update-check").disabled});
""")
        self.assertEqual(res[0], {"state": "error", "disabled": False})


class UpdateBoardPaintTests(unittest.TestCase):
    """更新组画板 UP01-UP12（c3-dialogs-gap 二）：每个状态只露一枚主钮、检查时间连字符、
    确认问句带真实体积、哈希失败专句、进度条 aria、黄警示独立块、底注句内链接钮。

    原型基准：Main.dc.html:771-786（markup）、1426-1451（状态行与钮槽）、1456/1459（错误框/进度块）。
    示意值（1.3.0、92.4 MB、11-03 14:20）不写死：全部由用例注入假数据、实现读真实回包。"""

    INSTALLER = {"url": "https://example.invalid/x.exe", "bytes": 96927744}  # 92.4375 MiB -> fmtBytes 92.4 MB

    def test_one_primary_action_per_state(self):
        """UP01 钮显隐矩阵（原型 Main.dc.html:1446-1451）：每态只露该态唯一的主动作钮；
        confirm 是中间态，确认下载与取消两枚同显；校验中禁用；error 走重试检查（原型 :1448）。"""
        res = run_js(r"""
const q = (id) => document.querySelector(id);
const flow = { install: q("#btn-update-install"), confirm: q("#btn-update-confirm"),
  launch: q("#btn-update-launch"), cancel: q("#btn-update-cancel"), close: q("#btn-update-close") };
const installer = { url: "https://example.invalid/x.exe", bytes: 96927744 };
function paint(state, result) {
  S.update.state = state;
  S.update.result = result || null;
  S.update.paintedState = null;
  S.update.guardUntil = 0;
  paintUpdate();
}
paint("idle");
out.push({ state: "idle", check: [!q("#btn-update-check").hidden, q("#btn-update-check").textContent],
  flowHidden: q("#update-flow").hidden });
paint("available", { latest_version: "9.9.9", installer: installer });
out.push({ state: "available", install: [!flow.install.hidden, flow.install.textContent],
  checkHidden: q("#btn-update-check").hidden, confirmHidden: flow.confirm.hidden,
  cancelHidden: flow.cancel.hidden, launchHidden: flow.launch.hidden, closeHidden: flow.close.hidden });
paint("confirm", { latest_version: "9.9.9", installer: installer });
out.push({ state: "confirm", confirm: [!flow.confirm.hidden, flow.confirm.textContent],
  cancel: [!flow.cancel.hidden, flow.cancel.textContent],
  installHidden: flow.install.hidden, checkHidden: q("#btn-update-check").hidden });
paint("downloading", { downloaded: 39845888, total_bytes: 96927744 });
out.push({ state: "downloading", cancel: [!flow.cancel.hidden, flow.cancel.textContent],
  checkHidden: q("#btn-update-check").hidden });
paint("verifying");
out.push({ state: "verifying", cancel: [!flow.cancel.hidden, flow.cancel.textContent, flow.cancel.disabled],
  checkHidden: q("#btn-update-check").hidden });
paint("ready_to_install");
out.push({ state: "ready", launch: [!flow.launch.hidden, flow.launch.textContent] });
S.busy = true;
paint("ready_to_install");
out.push({ state: "ready-busy", launch: [!flow.launch.hidden, flow.launch.textContent] });
S.busy = false;
paint("launching", { text: "正在启动安装程序…" });
out.push({ state: "launching", close: [!flow.close.hidden, flow.close.textContent, flow.close.disabled],
  launchHidden: flow.launch.hidden });
/* 二段启动与真实时序一致：第一段先画过（paintedState 已是 launching），二段不再重置防误触 */
S.update.guardUntil = Date.now() - 1;
S.update.result = { text: "安装程序已启动。请先关闭本工具，再按向导完成安装。" };
paintUpdate();
out.push({ state: "launched", close: [!flow.close.hidden, flow.close.textContent, flow.close.disabled] });
paint("failed", { error_code: "hash_mismatch", installer: installer });
out.push({ state: "failed", install: [!flow.install.hidden, flow.install.textContent],
  checkHidden: q("#btn-update-check").hidden });
paint("error", { text: "连接超时" });
out.push({ state: "error", check: [!q("#btn-update-check").hidden, q("#btn-update-check").textContent],
  flowHidden: q("#update-flow").hidden });
""")
        r = {row["state"]: row for row in res}
        self.assertEqual(r["idle"]["check"], [True, "检查更新"])
        self.assertTrue(r["idle"]["flowHidden"])
        self.assertEqual(r["available"]["install"], [True, "下载并安装"])
        self.assertTrue(r["available"]["checkHidden"])
        self.assertTrue(all(r["available"][k] for k in ("confirmHidden", "cancelHidden", "launchHidden", "closeHidden")))
        self.assertEqual(r["confirm"]["confirm"], [True, "确认下载"])
        self.assertEqual(r["confirm"]["cancel"], [True, "取消"])
        self.assertTrue(r["confirm"]["installHidden"] and r["confirm"]["checkHidden"])
        self.assertEqual(r["downloading"]["cancel"], [True, "取消下载"])
        self.assertTrue(r["downloading"]["checkHidden"])
        self.assertEqual(r["verifying"]["cancel"], [True, "校验中…", True], "校验中禁用（原型 :1449）")
        self.assertTrue(r["verifying"]["checkHidden"])
        self.assertEqual(r["ready"]["launch"], [True, "启动安装程序"])
        self.assertEqual(r["ready-busy"]["launch"], [True, "仍然启动安装程序"], "计划运行中要明说会中断（UP12）")
        self.assertEqual(r["launching"]["close"], [True, "启动中…", True], "启动段禁用（UP01）")
        self.assertTrue(r["launching"]["launchHidden"])
        self.assertEqual(r["launched"]["close"], [True, "关闭本工具…", False], "启动成功才交回关窗（UP10）")
        self.assertEqual(r["failed"]["install"], [True, "重新下载"], "哈希失败或普通失败都叫重新下载（UP08）")
        self.assertTrue(r["failed"]["checkHidden"])
        self.assertEqual(r["error"]["check"], [True, "重试检查"], "检查失败没有安装包可重下，走重试（原型 :1448）")
        self.assertTrue(r["error"]["flowHidden"])

    def test_checked_at_is_hyphen_padded_format(self):
        """UP03 检查时间自拼 MM-DD HH:mm（连字符、pad2），不靠 toLocaleString（Chromium 出斜杠）。"""
        res = run_js(r"""
out.push(formatCheckedAt(new Date(2026, 10, 3, 14, 20).getTime()));
out.push(formatCheckedAt(new Date(2026, 0, 5, 8, 5).getTime()));
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"current",checked_at:"2026-11-03T06:20:00Z"});
const at = document.querySelector("#update-checked-at");
out.push({ hidden: at.hidden, tail: at.textContent.slice(5),
  pattern: /^\d{2}-\d{2} \d{2}:\d{2}$/.test(at.textContent.slice(5)) });
""")
        self.assertEqual(res[0], "11-03 14:20")
        self.assertEqual(res[1], "01-05 08:05")
        self.assertTrue(res[2]["pattern"], "回包时间也要落成连字符格式：%s" % res[2]["tail"])
        self.assertFalse(res[2]["hidden"])

    def test_confirm_question_carries_real_size(self):
        """UP04 确认问句带真实体积（X=版本、Y=installer.bytes 换算）；无体积时去括号段。"""
        res = run_js(r"""
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"confirm",latest_version:"9.9.9",
  installer:{url:"https://example.invalid/x.exe", bytes:96927744}});
const withSize = document.querySelector("#update-confirm-question").textContent;
window.onBackend.update({request_id:"request",state:"confirm",latest_version:"9.9.9",
  installer:{url:"https://example.invalid/x.exe"}});
const withoutSize = document.querySelector("#update-confirm-question").textContent;
out.push({ withSize, withoutSize, boxShown: !document.querySelector("#update-confirm-box").hidden });
""")
        self.assertEqual(res[0]["withSize"],
                         "下载 9.9.9 安装包（92.4 MB）？只写临时目录，不动现在的程序和你的数据。"
                         "校验通过后，什么时候安装由你决定。")
        self.assertEqual(res[0]["withoutSize"],
                         "下载 9.9.9 安装包？只写临时目录，不动现在的程序和你的数据。"
                         "校验通过后，什么时候安装由你决定。")
        self.assertTrue(res[0]["boxShown"])

    def test_available_shows_version_block_with_real_size(self):
        """UP04 新版本块：大版本数字＋体积句；后端没带 bytes 时不显示体积句。"""
        res = run_js(r"""
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"available",latest_version:"9.9.9",
  installer:{url:"https://example.invalid/x.exe", bytes:96927744}});
const box = document.querySelector("#update-version-box");
const sized = { shown: !box.hidden, num: document.querySelector("#update-version-num").textContent,
  note: document.querySelector("#update-version-note").textContent };
window.onBackend.update({request_id:"request",state:"available",latest_version:"9.9.9",
  installer:{url:"https://example.invalid/x.exe"}});
const bare = { shown: !box.hidden, num: document.querySelector("#update-version-num").textContent,
  note: document.querySelector("#update-version-note").textContent };
out.push({ sized, bare });
""")
        # 句中「安」「装」之间插了不可见的 U+2060，防止窄屏下末行只剩「装」一个字
        self.assertEqual(res[0]["sized"], {"shown": True, "num": "9.9.9",
                                           "note": "完整安装包 92.4 MB，下载后先校验，再由你决定什么时候安⁠装"})
        self.assertEqual(res[0]["bare"], {"shown": True, "num": "9.9.9", "note": ""})

    def test_hash_mismatch_gets_dedicated_sentence(self):
        """UP08 哈希专句只按 error_code=hash_mismatch 显示；其余 error_code 照旧显示后端 text。"""
        res = run_js(r"""
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"failed",error_code:"hash_mismatch",
  text:"下载内容哈希校验未通过，已放弃并清理。"});
const box = document.querySelector("#update-error-box");
const hash = { hidden: box.hidden, text: box.textContent,
  status: document.querySelector("#update-status").textContent };
window.onBackend.update({request_id:"request",state:"failed",error_code:"size_mismatch",
  text:"下载大小与校验信息不一致（96927744 / 96927744 字节），已放弃。"});
const other = { hidden: box.hidden, text: box.textContent };
window.onBackend.update({request_id:"request",state:"error",text:"暂时无法连接GitHub，请检查网络后重试。"});
const checkErr = { hidden: box.hidden, text: box.textContent };
out.push({ hash, other, checkErr });
""")
        self.assertEqual(res[0]["hash"], {
            "hidden": False, "text": "下载内容的哈希校验没通过，已放弃并删掉临时文件。旧版本和你的数据都没动。",
            "status": "更新没有完成。"})
        self.assertEqual(res[0]["other"]["text"], "下载大小与校验信息不一致（96927744 / 96927744 字节），已放弃。")
        self.assertNotIn("哈希校验没通过", res[0]["other"]["text"])
        self.assertEqual(res[0]["checkErr"]["text"], "暂时无法连接GitHub，请检查网络后重试。")
        self.assertFalse(res[0]["checkErr"]["hidden"])

    def test_progress_block_carries_aria_and_percent(self):
        """UP06 进度块：aria-valuenow 随真实进度走，右侧「A / B MB（P%）」；
        校验中左句换「下载完成，正在校验」、右侧数字让位。
        （role/aria-label/aria-valuemax 是静态骨架，在 test_update_board_markup_follows_prototype 钉。）"""
        res = run_js(r"""
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"downloading",downloaded:39845888,total_bytes:96927744});
const bar = document.querySelector("#update-progress-bar");
const box = document.querySelector("#update-progress-box");
const down = { shown: !box.hidden, label: document.querySelector("#update-progress-label").textContent,
  num: document.querySelector("#update-progress-num").textContent,
  now: bar.getAttribute("aria-valuenow"),
  noteShown: !document.querySelector("#update-download-note").hidden };
window.onBackend.update({request_id:"request",state:"verifying"});
const verify = { shown: !box.hidden, label: document.querySelector("#update-progress-label").textContent,
  num: document.querySelector("#update-progress-num").textContent,
  now: bar.getAttribute("aria-valuenow"),
  noteShown: !document.querySelector("#update-download-note").hidden };
out.push({ down, verify });
""")
        self.assertEqual(res[0]["down"], {"shown": True, "label": "已下载", "num": "38.0 / 92.4 MB（41%）",
                                          "now": "41", "noteShown": True})
        # 校验中的 aria-valuenow 沿用合并结果里最后一次下载进度（真实链路末包 done==total → 100）
        self.assertEqual(res[0]["verify"], {"shown": True, "label": "下载完成，正在校验", "num": "",
                                            "now": "41", "noteShown": True})

    def test_versioned_update_states_show_delta_progress_and_switch_action(self):
        """版本目录更新的增量下载与重启切换状态不能退回未知态。"""
        res = run_js(r"""
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"downloading_delta",
  downloaded:524288,total_bytes:1048576});
const delta = {state:S.update.state,
  text:document.querySelector("#update-status").textContent,
  progress:!document.querySelector("#update-progress-box").hidden,
  label:document.querySelector("#update-progress-label").textContent};
S.update.guardUntil = Date.now() - 1;
window.onBackend.update({request_id:"request",state:"ready_to_restart",
  text:"更新目录已准备好，关闭程序后完成切换。"});
S.update.guardUntil = Date.now() - 1;
paintUpdate();
const ready = {state:S.update.state,
  launch:!document.querySelector("#btn-update-launch").hidden,
  label:document.querySelector("#btn-update-launch").textContent,
  text:document.querySelector("#update-status").textContent};
out.push({delta,ready});
""")
        self.assertEqual(res[0]["delta"], {"state": "downloading_delta",
                                             "text": "正在下载增量包…",
                                             "progress": True,
                                             "label": "已下载增量包"})
        self.assertEqual(res[0]["ready"], {"state": "ready_to_restart",
                                             "launch": True,
                                             "label": "重启并切换版本",
                                             "text": "更新目录已准备好，关闭程序后完成切换。"})

    def test_ready_warn_block_is_independent(self):
        """UP11/UP12 黄警示独立成块（不再拼进进度行）：busy 才显示，向导句常驻就绪块。"""
        res = run_js(r"""
S.update.requestId = "request";
S.busy = true;
window.onBackend.update({request_id:"request",state:"ready_to_install"});
const busy = { boxShown: !document.querySelector("#update-ready-box").hidden,
  warnShown: !document.querySelector("#update-plan-warn").hidden,
  progressGone: document.querySelector("#update-progress-box").hidden,
  status: document.querySelector("#update-status").textContent };
S.busy = false;
paintUpdate();
const idle = { warnShown: !document.querySelector("#update-plan-warn").hidden,
  status: document.querySelector("#update-status").textContent };
out.push({ busy, idle });
""")
        self.assertEqual(res[0]["busy"], {"boxShown": True, "warnShown": True, "progressGone": True,
                                          "status": "安装包已通过大小和 SHA-256 校验。"})
        self.assertFalse(res[0]["idle"]["warnShown"], "计划没跑就不该吓唬人")
        self.assertEqual(res[0]["idle"]["status"], "安装包已通过大小和 SHA-256 校验。")

    def test_update_board_markup_follows_prototype(self):
        """UP01/UP04/UP06/UP08/UP10/UP11 静态骨架：状态行、错误框、新版本块、确认/就绪盒、
        进度条 aria、黄警示独立块、底注句内链接钮，全部照原型 Main.dc.html:771-786 落位。"""
        html = read("ui/index.html")
        row = html[html.index('<div class="help-tool-row set-update">'):]
        row = row[:row.index('<div class="help-tool-row">')]
        for needle in ("help-version", "update-status", "update-checked-at", "update-error-box",
                       "update-version-box", "update-confirm-box", "update-progress-box",
                       "update-progress-bar", "update-progress-fill",
                       "update-plan-warn", "update-ready-box", "update-download-note",
                       "btn-update-install", "btn-update-confirm", "btn-update-launch",
                       "btn-update-cancel", "btn-update-close", "btn-update-check", "btn-help-latest"):
            self.assertIn('id="%s"' % needle, row, "「版本与更新」缺 #%s" % needle)
        self.assertIn('role="progressbar"', row)
        self.assertIn('aria-label="安装包下载进度"', row)
        self.assertIn('aria-valuemax="100"', row)
        self.assertIn("启动后按安装向导操作。工具不会自己退出或重启。", row, "就绪块的向导句（UP12，原型 :781）")
        # 「建」「议」之间插了不可见的 U+2060，防止「建议」被拆到两行
        self.assertIn("报名计划还在运行。安装时要先关闭本工具，计划会停止，建⁠议等这次计划结束再装。", row,
                      "黄警示独立成块（UP11，原型 :781）")
        note = row[row.index('<p class="ph-note">'):]
        self.assertIn('<button class="ph-link" id="btn-help-latest" type="button">打开发布页</button>', note,
                      "底注句内链接钮（UP10，原型 :784）")
        self.assertIn("，看更新说明，或者手动下载完整包。", note)
        self.assertNotIn("前往下载页", row, "独立「前往下载页」钮撤底（UP10）")
        css = read("ui/styles.css")
        for rule in (".up-v {", ".upbox {", ".help-tool-row p.ph-err", ".help-tool-row p.ph-warn"):
            self.assertIn(rule, css, "样式缺 %s（UP04/UP08/UP11）" % rule)
        for state in ('[data-state="available"]', '[data-state="ready_to_install"]'):
            self.assertIn("#update-status%s" % state, css, "状态行配色缺 %s（UP03/UP12）" % state)


class FirstUseAndUpdateModalsTests(unittest.TestCase):
    """FU01/FU02/TM08/TM09（plan 20261108-c3-dialogs decisions 第 1/2 条）：
    首次说明框与条款更新框的打开时机、小框⇄全文往返、勾选门、拒绝路径与数据。"""

    # views/terms.js 的 TERMS_CHANGES 条数（r6 变更记录归纳 3 条，TM09 用其真实内容；条款升 r6 后由 4 条改为 3 条）
    TERMS_CHANGES_COUNT = 3

    def test_routing_three_terms_states(self):
        """三种条款状态各开哪个框：从没同意→首次说明框；同意过旧版→条款更新框；
        状态未知→直接开全文阅读器（同意态）。"""
        res = run_js(r"""
window.pywebview = { api: { save_prefs: () => Promise.resolve({ ok: true }) } };
S.demo = false;
S.prefs = {};
S.terms.prompted = true;
ingestTerms({ version: "v2", accepted_version: "", accepted_at: "" });
openTerms("banner");
const neverBox = document.querySelector("#dlg-terms-intro").open;
const neverReader = document.querySelector("#dlg-terms").open;
document.querySelector("#dlg-terms-intro").close();
ingestTerms({ version: "v2", accepted_version: "v1", accepted_at: "" });
openTerms("banner");
const updateBox = document.querySelector("#dlg-terms-update").open;
const updateReader = document.querySelector("#dlg-terms").open;
document.querySelector("#dlg-terms-update").close();
markTermsUnknown();
openTerms("banner");
const unknownReader = document.querySelector("#dlg-terms").open;
const unknownIntro = document.querySelector("#dlg-terms-intro").open;
out.push({ neverBox, neverReader, updateBox, updateReader, unknownReader, unknownIntro });
""")
        r = res[0]
        self.assertTrue(r["neverBox"], "从没同意过 → 首次说明框（FU01）")
        self.assertFalse(r["neverReader"], "从没同意过不开全文阅读器")
        self.assertTrue(r["updateBox"], "同意过旧版 → 条款更新框（TM08）")
        self.assertFalse(r["updateReader"], "同意过旧版不开全文阅读器")
        self.assertTrue(r["unknownReader"], "状态未知 → 直接开全文阅读器（同意态）")
        self.assertFalse(r["unknownIntro"], "状态未知不弹小框")

    def test_update_box_paints_versions_changes_and_focus(self):
        """TM08/TM09：副题版本读真实值（示意值不进产品）、变更清单 4 条带
        「新增」徽章（r5 真实内容，原型 Main:880 版式）、打开时焦点落同意钮
        （Main:1828）。"""
        res = run_js(r"""
window.pywebview = { api: {} };
S.demo = false; S.prefs = {}; S.terms.prompted = true;
ingestTerms({ version: "2026-11-09-r6", accepted_version: "2026-10-27-r3", accepted_at: "" });
openTerms("banner");
const box = document.querySelector("#dlg-terms-update");
out.push({
  open: box.open,
  version: document.querySelector("#terms-update-version").textContent,
  from: document.querySelector("#terms-update-from").textContent,
  items: document.querySelector("#terms-update-list").innerHTML.split("<li>").length - 1,
  badges: document.querySelector("#terms-update-list").innerHTML.split("tu-new").length - 1,
  focus: document.activeElement && document.activeElement.__sel,
  lead: document.querySelector("#dlg-terms-update-lead").textContent,
});
""")
        r = res[0]
        self.assertTrue(r["open"])
        self.assertEqual(r["version"], "2026-11-09-r6", "副题新版号读 S.terms.version")
        self.assertEqual(r["from"], "2026-10-27-r3", "副题旧版号读已同意版本")
        self.assertEqual(r["items"], self.TERMS_CHANGES_COUNT, "变更清单条数＝TERMS_CHANGES")
        self.assertEqual(r["badges"], self.TERMS_CHANGES_COUNT, "每条一个「新增」徽章")
        self.assertEqual(r["focus"], "#btn-tu-accept", "打开时焦点落「同意新版条款」（Main:1828）")

    def test_full_text_roundtrip_from_boxes_via_x_and_esc(self):
        """小框→全文→关全文回小框：× 与 Esc 两种关法都回到原来的小框，
        不记拒绝、不落盘（decisions 第 1 条）。"""
        res = run_js(r"""
window.pywebview = { api: { save_prefs: () => Promise.resolve({ ok: true }) } };
S.demo = false; S.prefs = {}; S.terms.prompted = true;
ingestTerms({ version: "v2", accepted_version: "v1", accepted_at: "" });
openTerms("banner");
const dlg = document.querySelector("#dlg-terms");
const tu = document.querySelector("#dlg-terms-update");
/* × 关法：close + 手动收口 close 监听（桩不模拟原生 close 事件） */
openTermsReader("update");
dlg.close(); (dlg.listeners.close || []).forEach((fn) => fn());
const viaX = { readerOpen: dlg.open, tuBack: tu.open, declined: S.terms.declined };
/* Esc 关法：cancel 放行 + close 收口 */
openTermsReader("update");
const cancelEv = { defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
(dlg.listeners.cancel || []).forEach((fn) => fn(cancelEv));
dlg.close(); (dlg.listeners.close || []).forEach((fn) => fn());
const viaEsc = { readerOpen: dlg.open, tuBack: tu.open, declined: S.terms.declined,
  escPrevented: cancelEv.defaultPrevented };
out.push({ viaX, viaEsc });
""")
        r = res[0]
        self.assertFalse(r["viaX"]["readerOpen"])
        self.assertTrue(r["viaX"]["tuBack"], "× 关全文回条款更新框")
        self.assertFalse(r["viaX"]["declined"], "关全文不等于拒绝")
        self.assertFalse(r["viaEsc"]["escPrevented"], "未保存时 Esc 放行原生关闭")
        self.assertTrue(r["viaEsc"]["tuBack"], "Esc 关全文回条款更新框")
        self.assertFalse(r["viaEsc"]["declined"])

    def test_agree_in_full_text_closes_update_box_too(self):
        """从条款更新框进全文、在全文里同意：两框都关（先关全文再关更新框）。"""
        res = run_js(r"""
let accepted = 0;
window.pywebview = { api: {
  accept_terms: () => { accepted += 1;
    return Promise.resolve({ ok: true, terms: { version: "v2",
      accepted_version: "v2", accepted_at: "2026-11-08 12:00:00" } }); },
  save_prefs: () => Promise.resolve({ ok: true }),
} };
S.demo = false; S.prefs = {}; S.terms.prompted = true;
ingestTerms({ version: "v2", accepted_version: "v1", accepted_at: "" });
openTerms("banner");   /* 同意过旧版：先进条款更新框（TM08） */
openTermsReader("update"); /* 「看完整条款」入口 */
document.querySelector("#dlg-terms-document-version").textContent = "v2";
document.querySelector("#chk-terms-agree").checked = true;
document.querySelector("#btn-terms-accept").click();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
out.push({ accepted, readerOpen: document.querySelector("#dlg-terms").open,
  tuOpen: document.querySelector("#dlg-terms-update").open,
  locked: termsLocked() });
""")
        r = res[0]
        self.assertEqual(r["accepted"], 1)
        self.assertFalse(r["readerOpen"], "全文关闭")
        self.assertFalse(r["tuOpen"], "条款更新框一并关闭")
        self.assertFalse(r["locked"])

    def test_intro_accept_gated_by_checkbox(self):
        """FU01（Main:2484）：勾选前「同意并继续」禁用，点不动、零请求；
        勾选后解锁，同意成功关闭说明框。"""
        res = run_js(r"""
let accepted = 0;
window.pywebview = { api: {
  accept_terms: () => { accepted += 1;
    return Promise.resolve({ ok: true, terms: { version: "v2",
      accepted_version: "v2", accepted_at: "2026-11-08 12:00:00" } }); },
  save_prefs: () => Promise.resolve({ ok: true }),
} };
S.demo = false; S.prefs = {}; S.terms.prompted = true;
ingestTerms({ version: "v2", accepted_version: "", accepted_at: "" });
openTerms("banner");
/* accept_terms 的回执契约按内嵌全文版本校验（同阅读器路径） */
document.querySelector("#dlg-terms-document-version").textContent = "v2";
const intro = document.querySelector("#dlg-terms-intro");
const accept = document.querySelector("#btn-terms-intro-accept");
const agree = document.querySelector("#chk-terms-intro-agree");
const disabledBefore = accept.disabled;
accept.click();   /* 勾选前点击：桩不模拟 disabled，控制器里的勾选门必须拦 */
const acceptedBefore = accepted;
agree.checked = true;
(agree.listeners.change || []).forEach((fn) => fn({ target: agree }));
const enabledAfter = !accept.disabled;
accept.click();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
out.push({ disabledBefore, acceptedBefore, enabledAfter, accepted,
  introOpen: intro.open, readerOpen: document.querySelector("#dlg-terms").open,
  focus: document.activeElement && document.activeElement.__sel });
""")
        r = res[0]
        self.assertTrue(r["disabledBefore"], "勾选前同意钮禁用（Main:2484）")
        self.assertEqual(r["acceptedBefore"], 0, "勾选门前点击零请求")
        self.assertTrue(r["enabledAfter"], "勾选后同意钮解锁")
        self.assertEqual(r["accepted"], 1)
        self.assertFalse(r["introOpen"], "同意成功关闭说明框")
        self.assertFalse(r["readerOpen"])
        self.assertEqual(r["focus"], "#btn-help")

    def test_esc_on_small_boxes_is_decline_and_saving_is_blocked(self):
        """FU01/TM08：小框 Esc＝暂不使用／暂不同意（拒绝路径落盘）；保存中
        Esc 被 cancel 拦下不关闭；未确认＝离开待确认界面不记拒绝。"""
        res = run_js(r"""
let saved = [];
window.pywebview = { api: {
  save_prefs: (patch) => { saved.push(JSON.parse(JSON.stringify(patch))); return Promise.resolve({ ok: true }); },
  accept_terms: () => new Promise(() => {}),
} };
S.demo = false; S.prefs = {}; S.terms.prompted = true;
const intro = document.querySelector("#dlg-terms-intro");
const tu = document.querySelector("#dlg-terms-update");
const mkCancel = () => ({ defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } });
/* 更新框：保存中 Esc 拦下（在途） */
ingestTerms({ version: "v2", accepted_version: "v1", accepted_at: "" });
openTerms("banner");
S.terms.saving = true;
let ev = mkCancel();
(tu.listeners.cancel || []).forEach((fn) => fn(ev));
const savingBlocked = ev.defaultPrevented && tu.open;
S.terms.saving = false;
S.terms.unconfirmed = true;
ev = mkCancel();
(tu.listeners.cancel || []).forEach((fn) => fn(ev));
const unconfirmedLeave = !tu.open;
S.terms.unconfirmed = false;
/* 首启说明框：Esc＝暂不使用，落盘拒绝版本 */
document.querySelector("#dlg-terms-update").close();
S.terms.declined = false;
S.terms.acceptedVersion = "";
ingestTerms({ version: "v2", accepted_version: "", accepted_at: "" });
openTerms("banner");
ev = mkCancel();
(intro.listeners.cancel || []).forEach((fn) => fn(ev));
out.push({ savingBlocked, unconfirmedLeave, declined: S.terms.declined,
  introOpen: intro.open, tuOpen: tu.open,
  declinedSaved: saved.some((p) => p.terms_declined_version === "v2"),
  readerOpen: document.querySelector("#dlg-terms").open });
""")
        r = res[0]
        self.assertTrue(r["savingBlocked"], "保存中 Esc 必须 preventDefault 且不关闭")
        self.assertTrue(r["unconfirmedLeave"], "未确认时 Esc＝离开待确认界面（不记拒绝）")
        self.assertTrue(r["declined"], "Esc 在小框上等于拒绝（拒绝路径）")
        self.assertFalse(r["introOpen"])
        self.assertTrue(r["declinedSaved"], "拒绝版本落盘（现有拒绝路径不变）")
        self.assertFalse(r["readerOpen"])

    def test_first_use_points_data_and_rendering(self):
        """FU02：六条要点在 store（数据）与渲染（6 条 li、第六条带「现在就看」
        链接钮），关键句与 r5 正文一致（decisions 第 2 条）。"""
        store = read("ui/state/store.js")
        # 抽两条钉关键词：第 1 条的目标学校限定、第 5 条的对外通信三类口径
        self.assertIn("只适用于一所目标学校", store)
        self.assertIn("访问 GitHub", store, "对外通信按 r6 隐私第 3 节四类口径（GitHub 下载）")
        self.assertIn("运行时密钥", store, "密钥叫法按 r5 用户协议第 1/3 节")
        self.assertIn("不提供多账号、批量占位或代他人报名", store,
                      "义务表述按 r5 用户协议第 5 节")
        res = run_js(r"""
window.pywebview = { api: {} };
S.demo = false; S.prefs = {}; S.terms.prompted = true;
ingestTerms({ version: "v2", accepted_version: "", accepted_at: "" });
openTerms("banner");
const list = document.querySelector("#dlg-terms-intro-points");
out.push({
  items: list.innerHTML.split("<li>").length - 1,
  html: list.innerHTML,
  open: document.querySelector("#dlg-terms-intro").open,
  agree: document.querySelector("#chk-terms-intro-agree").checked,
});
""")
        r = res[0]
        self.assertTrue(r["open"])
        self.assertEqual(r["items"], 6, "六条要点")
        self.assertFalse(r["agree"], "每次打开回到未勾选")
        # 桩不解析 HTML：标题等静态文案由 test_first_use_and_update_modals_static_contract 覆盖
        self.assertEqual(r["html"].count('id="btn-terms-intro-fulltext"'), 1,
                         "第六条「完整条款」只有一个入口链接钮")
        self.assertIn("现在就看", r["html"])

    def test_small_boxes_block_background_shortcuts(self):
        """UI_SPEC §5.13 第 2 条：小框开着时 F5/Ctrl+F//、Enter 不落到背景
        （不刷新、不抢搜索、不开始计划）。"""
        res = run_js(r"""
let calls = [];
window.pywebview = { api: {
  start_plan: () => { calls.push("start"); return Promise.resolve({ ok: true }); },
} };
S.demo = false; S.prefs = {}; S.terms.prompted = true;
ingestTerms({ version: "v2", accepted_version: "", accepted_at: "" });
openTerms("banner");
const eF5 = __dispatchKey({ key: "F5" });
const eEnter = __dispatchKey({ key: "Enter" });
const eCtrlF = __dispatchKey({ key: "f", ctrlKey: true });
const eSlash = __dispatchKey({ key: "/" });
out.push({ f5: eF5.defaultPrevented, enter: eEnter.defaultPrevented,
  ctrlF: eCtrlF.defaultPrevented, slash: eSlash.defaultPrevented,
  calls, introOpen: document.querySelector("#dlg-terms-intro").open });
""")
        r = res[0]
        self.assertTrue(r["introOpen"])
        self.assertEqual(r["calls"], [], "背景 Enter 不开始计划")
        self.assertFalse(r["f5"], "F5 保留原生语义（背景刷新按钮不响应）")
        self.assertFalse(r["enter"], "Enter 保留原生语义")
        self.assertFalse(r["ctrlF"], "Ctrl+F 不抢搜索框")
        self.assertFalse(r["slash"], "斜杠不抢搜索框")


if __name__ == "__main__":
    unittest.main()
