#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机页行为测试：node vm 跑真实 JS + 本机 HTTP 端到端（离线）。

覆盖筛选、请求、对账、轮询单飞/退避、刷新恢复、stale 禁用、截止投影、
验证码代次与状态呈现；另做 375/430 布局静态检查与旧桌面契约回归。
不连学校、不开 100.x 监听、不启真实浏览器、不假截图。

@author Author
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from application.phone_service import PhoneAccessService  # noqa: E402
from infrastructure.phone_http import PhoneHttpServer  # noqa: E402

PHONE_DIR = LOCAL / "ui" / "m"

# 合法的一像素 PNG（1×1 透明）：投影层只放行真 PNG 魔数的图，
# 'AAAA' 这类假图会被丢成空串，用它测正常流程等于测一个不可能发生的事件。
CAPTCHA_PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
               "AAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII=")

# ---- node vm 装置：加载真实 ui/m/app.js + 最小受控 DOM -----------------
PHONE_JS_HARNESS = r"""
"use strict";
const vm = require("vm");
const fs = require("fs");
const path = require("path");
const uiDir = process.argv[2];
const snippetFile = process.argv[3];

const out = [];
const els = new Map();
function makeEl(sel) {
  const el = {
    __sel: sel, hidden: false, disabled: false, checked: false,
    value: "", textContent: "", innerHTML: "", tagName: "DIV",
    dataset: {}, style: {}, src: "",
    listeners: {}, childElementCount: 0, _children: [],
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    removeEventListener() {},
    setAttribute(k, v) { this["attr_" + k] = v; },
    getAttribute(k) { return this["attr_" + k]; },
    appendChild(child) { this._children.push(child); this.childElementCount = this._children.length; return child; },
    removeChild(child) { const at = this._children.indexOf(child); if (at >= 0) this._children.splice(at, 1); this.childElementCount = this._children.length; return child; },
    removeAttribute(k) { this["attr_" + k] = undefined; },
    click() { (this.listeners.click || []).forEach((fn) => fn({ target: this })); },
    focus() {}, blur() {}, select() {},
  };
  Object.defineProperty(el, "firstChild", { get() { return this._children[0] || null; } });
  return el;
}
function el2(sel) { if (!els.has(sel)) els.set(sel, makeEl(sel)); return els.get(sel); }

const listeners = [];
const docListeners = {};
const winListeners = {};
const timers = new Map();
let timerSeq = 0;
const sandbox = {
  console, Math, JSON, Object, Array, Number, String, Boolean, RegExp, Error,
  parseInt, parseFloat, isNaN, Date, Uint8Array, Promise, Map, Set,
  /* 可观测的定时器替身：回调不会被自动执行，但排了多久、还剩几个都能查，
     这样「空闲 15 秒 / 忙碌 2 秒 / 后台停表 / 401 后不重排」才是可断言的。 */
  setTimeout: (fn, delay) => { const id = ++timerSeq; timers.set(id, { fn, delay: Number(delay) || 0 }); return id; },
  clearTimeout: (id) => { timers.delete(id); },
  setInterval: () => 0, clearInterval: () => {},
  crypto: { getRandomValues: (buf) => { for (let i = 0; i < buf.length; i++) buf[i] = (i * 37 + 11) % 256; return buf; } },
  fetch: (...args) => sandbox.__fetch(...args),
  confirm: () => true,
  out, __els: els,
  document: {
    hidden: false, readyState: "complete", cookie: "",
    getElementById: (id) => el2("#" + id),
    querySelector: (s) => el2(s),
    querySelectorAll: (s) => (s === "[data-status]" ? ["#s-all", "#s-free"].map(el2)
                              : s === "[data-time]" ? ["#t-all", "#t-today"].map(el2) : []),
    createElement: (tag) => el2("<" + tag + ">"),
    addEventListener: (t, fn) => {
      (docListeners[t] = docListeners[t] || []).push(fn);
      if (t === "DOMContentLoaded") listeners.push(fn);
    },
    removeEventListener: () => {},
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
// 页面里 $ 是全局选择器辅助函数；主模式（手机页）与视图模式都要能取到元素
// 视图文件按 "#id" 取，手机页断言按裸 id 取，统一成同一个元素实例
sandbox.$ = (sel) => el2(String(sel).charAt(0) === "#" ? sel : "#" + String(sel));
sandbox.addEventListener = (t, fn) => { (winListeners[t] = winListeners[t] || []).push(fn); };
sandbox.removeEventListener = () => {};
sandbox.__fire = (target, type) => {
  const map = target === "window" ? winListeners : docListeners;
  (map[type] || []).slice().forEach((fn) => fn());
};
sandbox.__timers = timers;
sandbox.__timerDelays = () => Array.from(timers.values()).map((t) => t.delay);
sandbox.__fireTimers = () => {
  const due = Array.from(timers.values());
  timers.clear();
  due.forEach((t) => t.fn());
};
sandbox.__fetch = () => Promise.resolve({ status: 500, json: () => Promise.resolve({}) });
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(uiDir, "app.js"), "utf8"), sandbox, { filename: "m/app.js" });
const snippetSource = fs.readFileSync(snippetFile, "utf8");
const result = vm.runInContext("(async () => {\n" + snippetSource + "\n})()", sandbox, { filename: "snippet.js" });
const finish = () => process.stdout.write("__RESULT__" + JSON.stringify(out));
result.then(finish, (err) => { process.stderr.write(String(err && err.stack || err)); process.exit(1); });
"""


def run_phone_js(snippet: str, files=None):
    """在受控 node vm 里跑 ui/m/app.js + 片段，返回 out 数组。node 缺失则 skip。"""
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("本机没有 node，无法运行 JS 行为测试")
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        harness = root / "harness.js"
        part = root / "snippet.js"
        harness_source = PHONE_JS_HARNESS
        ui_dir = PHONE_DIR
        if files:
            ui_dir = PHONE_DIR.parent
            harness_source = harness_source.replace(
                'vm.runInContext(fs.readFileSync(path.join(uiDir, "app.js"), "utf8"), sandbox, { filename: "m/app.js" });',
                'sandbox.document.readyState = "loading";\n'
                'sandbox.api = (...args) => sandbox.__api(...args);\n'
                'sandbox.helpStatus = (text, tone) => out.push({text, tone});\n'
                'sandbox.__api = async () => ({ok:true});\n'
                + "\n".join('vm.runInContext(fs.readFileSync(path.join(uiDir, %s), "utf8"), sandbox);'
                            % json.dumps(file) for file in files))
        harness.write_text(harness_source, encoding="utf-8")
        part.write_text(snippet, encoding="utf-8")
        res = subprocess.run([node, str(harness), str(ui_dir), str(part)],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=30)
        if res.returncode != 0:
            raise AssertionError("手机 JS 行为测试崩溃：%s" % res.stderr[-800:])
        marker = res.stdout.rfind("__RESULT__")
        if marker < 0:
            raise AssertionError("手机 JS 没有输出结果：%s" % res.stdout[-500:])
        return json.loads(res.stdout[marker + len("__RESULT__"):].strip() or "[]")


class PhoneModelTests(unittest.TestCase):
    """PhoneModel 纯规则：node vm 执行真实函数，不搜字符串。"""

    def test_filter_items_by_keyword_status_and_time(self):
        values = run_phone_js("""
const nowS = 1000;
const items = [
  { id: "a1", name: "篮球赛", place: "体育馆", signed: false, open_ts: nowS + 3600 },
  { id: "a2", name: "讲座", place: "报告厅", signed: true, open_ts: nowS + 3600 },
  { id: "a3", name: "远足", place: "体育馆", signed: false, open_ts: nowS + 3 * 86400 },
  { id: "a4", name: "未知", place: "", signed: false, open_ts: 0 },
];
out.push(PhoneModel.filterItems(items, { q: "体育" }, nowS).map((i) => i.id));
out.push(PhoneModel.filterItems(items, { status: "free" }, nowS).map((i) => i.id));
out.push(PhoneModel.filterItems(items, { status: "signed" }, nowS).map((i) => i.id));
out.push(PhoneModel.filterItems(items, { time: "today" }, nowS).map((i) => i.id));
out.push(PhoneModel.filterItems(items, { time: "week" }, nowS).map((i) => i.id));
""")
        self.assertEqual(values[0], ["a1", "a3"])
        self.assertEqual(values[1], ["a1", "a3", "a4"])
        self.assertEqual(values[2], ["a2"])
        self.assertEqual(values[3], ["a1", "a2"])
        self.assertEqual(values[4], ["a1", "a2", "a3"])

    def test_backoff_is_exponential_and_capped_at_15s(self):
        values = run_phone_js("""
let cur = 1000;
const steps = [cur];
for (let i = 0; i < 5; i++) { cur = PhoneModel.nextBackoff(cur); steps.push(cur); }
out.push(steps);
""")
        self.assertEqual(values[0], [1000, 2000, 4000, 8000, 15000, 15000])

    def test_stale_disables_start_and_relogin_submit(self):
        values = run_phone_js("""
const model = { lastOkAt: 1000, nowMs: 1000 + PhoneModel.staleAfterMs + 1,
                busy: false, selected: ["a1"] };
out.push(PhoneModel.isStale(model.lastOkAt, model.nowMs));
out.push(PhoneModel.canStart(model));
model.nowMs = 1000 + 100;
out.push(PhoneModel.canStart(model));
model.selected = [];
out.push(PhoneModel.canStart(model));
out.push(PhoneModel.canSubmitRelogin(
  { lastOkAt: 8900, nowMs: 9000 },
  { challenge_id: "c1", got_at: 9000, expires_in: null }));
out.push(PhoneModel.canSubmitRelogin(
  { lastOkAt: 8900, nowMs: 9000 },
  { challenge_id: "c1", got_at: 1000, expires_in: null }));
""")
        self.assertEqual(values, [True, False, True, False, True, True])

    def test_deadline_projection_prefers_telemetry_and_three_modes(self):
        values = run_phone_js("""
const anchor = 1000, signEnd = 5000;
out.push(PhoneModel.taskDeadline(
  { retry_deadline: 4321, retry_for_s: 120, retry_started_at: anchor, sign_end_ts: signEnd }, 0));
out.push(PhoneModel.taskDeadline(
  { retry_for_s: 120, retry_started_at: anchor, sign_end_ts: signEnd }, 0));
out.push(PhoneModel.taskDeadline(
  { retry_for_s: -1, retry_started_at: anchor, sign_end_ts: signEnd }, 0));
out.push(PhoneModel.taskDeadline(
  { retry_for_s: 0, retry_started_at: anchor, sign_end_ts: signEnd }, 0));
out.push(PhoneModel.taskDeadline(
  { retry_for_s: 0, retry_started_at: anchor, sign_end_ts: 0 }, 0));
out.push(PhoneModel.taskDeadline(
  { retry_for_s: 120, retry_started_at: anchor, sign_end_ts: 1030 }, 0));
""")
        self.assertEqual(values, [4321, 1120, 1120, 5000, 1120, 1030])

    def test_retry_hint_for_zero_without_sign_end(self):
        values = run_phone_js("""
out.push(PhoneModel.retryHint(0, false));
out.push(PhoneModel.retryHint(0, true));
out.push(PhoneModel.retryHint(-1, true));
""")
        self.assertIn("2 分钟", values[0])
        self.assertEqual(values[1], "")
        self.assertIn("25 分钟", values[2])

    def test_challenge_generation_matching_and_expiry(self):
        values = run_phone_js("""
const flow = { flow_id: "f1", challenge_id: "c9" };
out.push(PhoneModel.matchesChallenge(flow, "f1", "c9"));
out.push(PhoneModel.matchesChallenge(flow, "f2", "c9"));
out.push(PhoneModel.matchesChallenge(flow, "f1", "c0"));
out.push(PhoneModel.challengeExpired({ got_at: 1000, expires_in: null }, 1000 + 59000));
out.push(PhoneModel.challengeExpired({ got_at: 1000, expires_in: null }, 1000 + 61000));
out.push(PhoneModel.newRequestId().length);
""")
        self.assertEqual(values[:5], [True, False, False, False, False])
        self.assertEqual(values[5], 24, "request id 用 getRandomValues，HTTP 页面也可用")

    def test_item_actionable_and_presentation(self):
        values = run_phone_js("""
out.push(PhoneModel.actionable({ signed: false, sign_start: "2026-01-01 09:00:00" }));
out.push(PhoneModel.actionable({ signed: true, sign_start: "2026-01-01 09:00:00" }));
out.push(PhoneModel.actionable({ signed: false, sign_start: "" }));
out.push(PhoneModel.actionable({ signed: false, sign_start: "x", closed: true }));
out.push(PhoneModel.itemTitle({ name: "篮球" }));
out.push(PhoneModel.itemMeta({ sign_start: "09:00", signed: true }));
""")
        self.assertEqual(values, [True, False, False, False, "篮球", "开放 09:00 · 已报名"])

    def test_start_pending_keeps_reconciling_window(self):
        values = run_phone_js("""
out.push(PhoneModel.startPending(null, 0));
out.push(PhoneModel.startPending({ at: 1000, done: false }, 1000 + 14000));
out.push(PhoneModel.startPending({ at: 1000, done: false }, 1000 + 16000));
out.push(PhoneModel.startPending({ at: 1000, done: true }, 1000 + 16000));
""")
        self.assertEqual(values, [False, True, True, False])


class PhoneDomBehaviourTests(unittest.TestCase):
    """DOM 层行为：轮询单飞、退避、stale 禁用、刷新恢复（最小受控 DOM）。"""

    def test_poll_is_single_flight_and_recovers_on_visibility(self):
        values = run_phone_js("""
let calls = 0;
globalThis.__fetch = () => {
  calls += 1;
  return Promise.resolve({ status: 200, json: () => Promise.resolve({
    state: { activities: [{ id: "a1", name: "活动", sign_start: "2026-01-01 09:00:00" }],
             busy: false, plan: null, retry_options: { default: 120, choices: [] } },
    events: [], reset: false, seq: 3 }) });
};
const ui = globalThis.PhoneUI;
ui.model.selected = [];
const first = ui.poll(true);
const second = ui.poll(true);          // 单飞：在途不重发
await first; await second;
out.push(calls);
out.push(ui.model.seq);
out.push(ui.model.items.length);
""")
        self.assertEqual(values, [1, 3, 1], "轮询必须单飞；快照要落进 model")

    def test_background_recovery_backfills_by_event_cursor_only(self):
        values = run_phone_js("""
const ui = globalThis.PhoneUI;
const urls = [];
globalThis.__fetch = (path, opts) => {
  urls.push(((opts && opts.method) || "GET") + " " + path);
  return Promise.resolve({ status: 200, json: () => Promise.resolve({
    state: { activities: [], busy: false, plan: null,
             retry_options: { default: 120, choices: [] } },
    events: [], reset: false, seq: 7 }) });
};
ui.model.seq = 7;
ui.model.paired = true;                       // 已经配过对：后台恢复才有意义
document.hidden = true;
__fire("document", "visibilitychange");
out.push(urls.length);                        // 进后台：只取消轮询
document.hidden = false;
__fire("document", "visibilitychange");       // 回前台：按游标补齐
for (let i = 0; i < 30; i++) await Promise.resolve();
out.push(urls.length);
out.push(urls[urls.length - 1] || "");
__fire("window", "pagehide");
const afterHide = urls.length;
for (let i = 0; i < 30; i++) await Promise.resolve();
out.push(urls.length - afterHide);            // pagehide 只收定时器
__fire("window", "pageshow");
for (let i = 0; i < 30; i++) await Promise.resolve();
out.push(urls.length - afterHide);            // pageshow 只读补齐一次
out.push(urls[urls.length - 1] || "");
out.push(urls.filter((u) => u.indexOf("POST") === 0).length);
""")
        self.assertEqual(
            values, [0, 1, "GET /api/state?after=7", 0, 1,
                     "GET /api/state?after=7", 0],
            "后台恢复必须按事件游标补齐，且只读、不重放写操作")

    def test_poll_failure_backs_off_and_stale_disables_start(self):
        values = run_phone_js("""
globalThis.__fetch = () => Promise.resolve({ status: 500, json: () => Promise.resolve({}) });
const ui = globalThis.PhoneUI;
ui.model.selected = ["a1"];
ui.model.lastOkAt = Date.now();
await ui.poll(true);
out.push(ui.model.backoff);
await ui.poll(true);
out.push(ui.model.backoff);
ui.model.lastOkAt = Date.now() - PhoneModel.staleAfterMs - 1;
ui.refreshControls();
out.push(document.getElementById("btn-start").disabled);
out.push(document.getElementById("conn").textContent);
""")
        self.assertEqual(values, [2000, 4000, True, "离线/未知"])

    def test_refresh_restores_busy_plan_and_stop(self):
        values = run_phone_js("""
const ui = globalThis.PhoneUI;
ui.ingest({ reset: true, seq: 9,
  state: { activities: [], busy: true,
           plan: { plan_id: "p1", tasks: [{ task_id: "t1", name: "篮球", status: "submitting",
                                            retry_for_s: -1, retry_started_at: 1000 }] },
           retry_options: { default: 120,
             choices: [{ value: 120, label: "2 分钟" }, { value: -1, label: "自动" }] } },
  events: [{ seq: 8, kind: "log", payload: { text: "开始" } }] });
ui.refreshControls();
out.push(ui.model.busy);
out.push(ui.model.plan.plan_id);
out.push(document.getElementById("btn-stop").hidden);
out.push(document.getElementById("logs").childElementCount);
out.push(document.getElementById("retry-for").__sel ? 1 : 0);
""")
        self.assertEqual(values, [True, "p1", False, 1, 1])

    def test_unconfirmed_start_keeps_same_request_id(self):
        values = run_phone_js("""
globalThis.__fetch = (path, opts) => {
  const body = JSON.parse(opts.body);
  out.push(body.action + ":" + body.args.request_id);
  return Promise.resolve({ status: 200, json: () => Promise.resolve({ ok: false, error: "busy" }) });
};
const ui = globalThis.PhoneUI;
ui.model.selected = ["a1"];
ui.model.lastOkAt = Date.now();
ui.model.pending = null;
await ui.startPlan();
const firstId = ui.model.pending.request_id;
out.push(PhoneModel.startPending(ui.model.pending, Date.now()));
ui.model.pending.done = true;
out.push(PhoneModel.startPending(ui.model.pending, Date.now() + 16000));
out.push(firstId.length);
""")
        kinds = [v.split(":")[0] for v in values if isinstance(v, str) and ":" in v]
        self.assertIn("start_plan", kinds)
        self.assertTrue(values[1], "15 秒内未确认必须仍在对账窗口")
        self.assertFalse(values[2])
        self.assertEqual(values[3], 24)


class HelpAdvancedBehaviorTests(unittest.TestCase):
    def test_import_disabled_and_failure_states_are_independent(self):
        values = run_phone_js('''
PhonePanel.state.advanced = {features: {
  phone_control: {available:true, enabled:false, ready:false, install_mode:"import", status:"ready"},
  relogin_ocr: {ready:false, status:"failed", install_mode:"import"}
}};
PhonePanel.paint();
out.push($("#btn-phone-feature-install").textContent);
out.push($("#phone-feature-status").textContent);
out.push($("#ocr-feature-status").textContent);
out.push($("#btn-ocr-feature-install").textContent);
out.push($("#phone-access-detail").hidden);
''', files=["views/phone.js"])
        self.assertEqual(values, ["启用手机控制", "已停用", "加载失败", "重新导入组件包", True])

    def test_busy_disables_all_mutations_and_a_canceled_pick_is_quiet(self):
        """忙的时候按钮一起禁用；用户在选择框里按取消不算错误，什么都不提示。"""
        values = run_phone_js('''
PhonePanel.busy = true;
PhonePanel.paint();
out.push(["#btn-phone-start", "#btn-ocr-feature-install", "#btn-credentials-save",
          "#btn-phone-feature-remove"].every((id) => $(id).disabled));
PhonePanel.busy = false;
globalThis.__api = async (name) => name === "pick_advanced_component"
  ? {ok: true, canceled: true} : {ok: true};
await PhonePanel.pickComponent("phone_control");
out.push([$("#comp-phone-note").textContent, PhonePanel.verified.phone_control]);
''', files=["views/phone.js"])
        self.assertEqual(values, [True, ["", ""]])

    def test_failed_save_clears_password_and_recovers_buttons(self):
        values = run_phone_js('''
PhonePanel.state.advanced = {credential:{available:true}};
$("#credential-user").value = "fictional";
$("#credential-pass").value = "fictional-password";
globalThis.__api = async (name) => { if (name === "save_relogin_credentials") throw Error("private details"); return {ok:true}; };
await PhonePanel.saveCredentials();
out.push($("#credential-pass").value);
out.push(PhonePanel.busy);
''', files=["views/phone.js"])
        self.assertEqual(values[-2:], ["", False])
        self.assertNotIn("private details", json.dumps(values))


class PhoneChannelUiTests(unittest.TestCase):
    """帮助里的通道引导：两个通道各自成句，通道状态不串台。"""

    def test_channels_render_independently(self):
        values = run_phone_js('''
PhonePanel.state.advanced = {channels:{
  tailscale:{available:false, state:"missing", text:"电脑上没有 Tailscale"},
  cloudflare:{available:true, state:"available", text:"可用"}}};
$("#phone-channel").value = "cloudflare";
PhonePanel.paint();
out.push({status:$("#phone-channel-state-text").textContent,
          label:$("#phone-channel-label").textContent,
          warn:$("#phone-channel-warn").hidden,
          guide:$("#tailscale-guide").hidden});
$("#phone-channel").value = "tailscale";
PhonePanel.paint();
out.push({status:$("#phone-channel-state-text").textContent,
          warn:$("#phone-channel-warn").hidden,
          guide:$("#tailscale-guide").hidden});
''', files=["views/phone.js"])
        cloudflare, tailscale = values
        self.assertEqual(cloudflare, {"status": "可用", "label": "Cloudflare（临时地址）",
                                      "warn": False, "guide": True})
        self.assertEqual(tailscale, {"status": "未安装", "warn": True, "guide": False})

    def test_magicdns_is_primary_and_ip_is_backup(self):
        values = run_phone_js('''
PhonePanel.state.running = true;
PhonePanel.state.address = "http://pc.tail.ts.net:8765/";
PhonePanel.state.advanced = {features:{phone_control:{ready:true, available:true}},
  channels:{tailscale:{available:true, state:"connected", addresses:["100.64.0.9"],
                       magicdns:"pc.tail.ts.net", public_host:"pc.tail.ts.net"}}, credential:{}};
$("#phone-channel").value = "tailscale";
PhonePanel.paint();
out.push($("#phone-address").textContent);
out.push($("#phone-address-alt").textContent);
out.push($("#phone-address-alt-line").hidden);
''', files=["views/phone.js"])
        self.assertEqual(values, ["http://pc.tail.ts.net:8765/", "http://100.64.0.9:8765/", False])

    def test_pair_code_change_is_announced_with_leftover_time(self):
        """配对码过期/被用掉后会换新码，界面必须说一声并给出剩余时间。"""
        values = run_phone_js('''
PhonePanel.state.running = true;
PhonePanel.state.advanced = {features:{phone_control:{ready:true, available:true}},
  channels:{tailscale:{available:true, state:"connected"}}, credential:{}};
PhonePanel.state.pair_code_status = {code:"111111", expires_in:265, seq:1,
                                    reason:"started"};
PhonePanel.paint();
out.push({code:$("#phone-code").textContent,
          note:$("#pair-code-note").textContent,
          hidden:$("#pair-code-note").hidden});
PhonePanel.state.pair_code_status = {code:"222222", expires_in:300, seq:2,
                                    reason:"expired"};
PhonePanel.paint();
out.push({code:$("#phone-code").textContent,
          note:$("#pair-code-note").textContent,
          hidden:$("#pair-code-note").hidden});
''', files=["views/phone.js"])
        first, notice, second = values
        self.assertEqual(first["code"], "111111")
        self.assertEqual(first["note"], "配对码 4:25 后失效")
        self.assertFalse(first["hidden"])
        self.assertEqual(second["code"], "222222")
        self.assertEqual(second["note"], "配对码 5:00 后失效")
        self.assertEqual(notice["tone"], "warn")
        self.assertIn("配对码已过期", notice["text"])

class ReloginCardUiTests(unittest.TestCase):
    """电脑续登录：ddddocr 与账号保存分开说，清除账号必须先确认。"""

    def test_missing_ocr_still_saves_account(self):
        values = run_phone_js("""
const calls = [];
globalThis.__api = async (name) => { calls.push(name); return {ok:true, saved:true}; };
PhonePanel.state.advanced = {
  features:{relogin_ocr:{available:false, ready:false, status:"missing"}},
  credential:{available:true, store_available:true, saved:false, ocr_ready:false}};
PhonePanel.paint();
out.push({ocr: $("#relogin-ocr-status").textContent,
          overall: $("#relogin-overall-status").textContent,
          auto: $("#relogin-auto-path").textContent});
$("#credential-user").value = "20230001";
$("#credential-pass").value = "secret";
await PhonePanel.saveCredentials();
out.push({calls: calls.slice()});
""", files=["views/phone.js"])
        # helpStatus 会往 out 里补提示，这里只取自己 push 的结构
        first = values[0]
        second = [row for row in values if "calls" in row][-1]
        self.assertIn("人工输入", first["ocr"], "没装 ddddocr 也要说清验证码人工输入")
        self.assertEqual(first["overall"], "未配置")
        self.assertIn("还没保存账号", first["auto"])
        self.assertIn("save_relogin_credentials", second["calls"])
        self.assertNotIn("prepare_phone_relogin", second["calls"],
                         "本机存储可用时就该真正落盘，不能退成只存内存")

    def test_clear_waits_for_confirmation(self):
        values = run_phone_js("""
const calls = [];
globalThis.__api = async (name) => { calls.push(name); return {ok:true}; };
PhonePanel.wire();
await PhonePanel.refresh();
calls.length = 0;
$("#btn-credentials-clear").click();
out.push({shown: !$("relogin-clear-confirm").hidden, calls: calls.slice()});
$("#btn-relogin-clear-cancel").click();
out.push({shown: !$("relogin-clear-confirm").hidden, calls: calls.slice()});
$("#btn-credentials-clear").click();
$("#btn-relogin-clear-confirm").click();
await Promise.resolve();
out.push({shown: !$("relogin-clear-confirm").hidden, calls: calls.slice()});
""", files=["views/phone.js"])
        shown, cancelled = values[0], values[1]
        confirmed = [row for row in values if "shown" in row][-1]
        self.assertTrue(shown["shown"], "点清除先展开确认行")
        self.assertNotIn("clear_relogin_credentials", shown["calls"],
                         "确认之前绝不能删账号")
        self.assertFalse(cancelled["shown"])
        self.assertNotIn("clear_relogin_credentials", cancelled["calls"])
        self.assertIn("clear_relogin_credentials", confirmed["calls"])
        self.assertFalse(confirmed["shown"])

    def test_configured_card_explains_paths(self):
        values = run_phone_js("""
PhonePanel.state.advanced = {
  features:{relogin_ocr:{available:true, ready:true, status:"ready"}},
  credential:{available:true, store_available:true, saved:true,
    username:"20230001", ocr_ready:true, last_origin:"auto_ocr",
    automatic:{last_used_ago_s:90, last_used_method:"auto_ocr"}}};
PhonePanel.paint();
out.push({overall: $("#relogin-overall-status").textContent,
          cred: $("#relogin-credential-status").textContent,
          last: $("#relogin-last-used").textContent,
          auto: $("#relogin-auto-path").textContent,
          phone: $("#relogin-phone-path").textContent});
""", files=["views/phone.js"])
        row = values[0]
        self.assertEqual(row["overall"], "已配置")
        # 旧断言「卡片写出完整账号」改为只露首尾各两位（设计 9.3：界面上的账号一律打码）
        self.assertIn("20****01", row["cred"])
        self.assertNotIn("20230001", row["cred"], "完整账号不得出现在界面上")
        self.assertIn("电脑自动恢复", row["last"])
        self.assertIn("不需要你动手", row["auto"])
        # 旧断言要求写出库名 ddddocr：界面统一叫「验证码识别」/「电脑自动识别」，不露技术名（设计第 12 节）
        self.assertIn("先由电脑自动识别", row["phone"])
        self.assertIn("再由你输入", row["phone"], "认不出来时的人工兜底要写清")
        self.assertNotIn("ddddocr", row["phone"], "界面不露组件技术名")

    def test_closing_access_requires_confirmation(self):
        values = run_phone_js('''
const calls = [];
globalThis.__api = async (name) => { calls.push(name); return {ok:true}; };
PhonePanel.wire();
await PhonePanel.refresh();
PhonePanel.state.running = true;
PhonePanel.state.feature = {ready:true, available:true};
PhonePanel.state.advanced = {features:{phone_control:{ready:true, available:true}},
  channels:{}, credential:{}};
PhonePanel.paint();
$("#btn-phone-stop").click();
out.push({shown: !$("phone-stop-confirm").hidden, calls: calls.slice()});
$("#btn-phone-stop-cancel").click();
out.push({shown: !$("phone-stop-confirm").hidden, calls: calls.slice()});
await PhonePanel.confirmStop();
out.push({shown: !$("phone-stop-confirm").hidden, calls: calls.slice()});
''', files=["views/phone.js"])
        shown, cancelled = values[:2]
        confirmed = values[-1]
        self.assertTrue(shown["shown"], "关闭前必须先问一句")
        self.assertNotIn("stop_phone_access", shown["calls"])
        self.assertFalse(cancelled["shown"])
        self.assertNotIn("stop_phone_access", cancelled["calls"],
                         "取消关闭不能顺手调用停止接口")
        self.assertIn("stop_phone_access", confirmed["calls"])
        self.assertFalse(confirmed["shown"])

    def test_start_button_locks_and_reports_progress(self):
        values = run_phone_js('''
const calls = [];
let release;
globalThis.__api = (name) => {
  calls.push(name);
  if (name === "start_phone_access") return new Promise((resolve) => { release = resolve; });
  return Promise.resolve({ok:true, running:true, address:"https://x.trycloudflare.com"});
};
$("#phone-channel").value = "cloudflare";
const task = PhonePanel.toggleStart();
await Promise.resolve();
out.push({mark:"pending", hidden: $("#btn-phone-start").hidden,
          disabled: $("#btn-phone-start").disabled,
          text: $("#btn-phone-start").textContent,
          channelDisabled: $("#phone-channel").disabled});
await PhonePanel.toggleStart();
out.push({mark:"calls", starts: calls.filter((n) => n === "start_phone_access").length});
release({ok:true, address:"https://x.trycloudflare.com"});
await task;
out.push({mark:"done", startHidden: $("#btn-phone-start").hidden,
          stopHidden: $("#btn-phone-stop").hidden,
          stopText: $("#btn-phone-stop").textContent});
''', files=["views/phone.js"])
        marks = {item["mark"]: item for item in values if isinstance(item, dict) and "mark" in item}
        self.assertFalse(marks["pending"]["hidden"], "启动过程中按钮不能消失")
        self.assertTrue(marks["pending"]["disabled"], "启动过程中按钮必须禁用，防重复点击")
        self.assertIn("启动中", marks["pending"]["text"])
        self.assertTrue(marks["pending"]["channelDisabled"],
                        "启动过程中不能改通道，否则拿到的地址和界面显示对不上")
        self.assertEqual(marks["calls"]["starts"], 1, "连点两次只能发一次启动请求")
        self.assertTrue(marks["done"]["startHidden"])
        self.assertFalse(marks["done"]["stopHidden"])
        self.assertEqual(marks["done"]["stopText"], "关闭访问")

    def test_stop_button_reports_closing(self):
        values = run_phone_js('''
let release;
globalThis.__api = (name) => {
  if (name === "stop_phone_access") return new Promise((resolve) => { release = resolve; });
  return Promise.resolve({ok:true, running:false});
};
PhonePanel.state.running = true;
PhonePanel.paint();
const task = PhonePanel.toggleStop();
await Promise.resolve();
out.push({mark:"pending", hidden: $("#btn-phone-stop").hidden,
          disabled: $("#btn-phone-stop").disabled,
          text: $("#btn-phone-stop").textContent});
release({ok:true});
await task;
out.push({mark:"done", startText: $("#btn-phone-start").textContent,
          startHidden: $("#btn-phone-start").hidden});
''', files=["views/phone.js"])
        marks = {item["mark"]: item for item in values if isinstance(item, dict) and "mark" in item}
        self.assertFalse(marks["pending"]["hidden"])
        self.assertTrue(marks["pending"]["disabled"])
        self.assertIn("关闭中", marks["pending"]["text"])
        self.assertFalse(marks["done"]["startHidden"])
        self.assertEqual(marks["done"]["startText"], "开启手机访问")

    def test_copy_address_reports_success_and_failure(self):
        values = run_phone_js('''
PhonePanel.state.running = true;
PhonePanel.state.address = "http://pc.tail.ts.net:8765/";
await PhonePanel.copyAddress();
globalThis.navigator = {clipboard:{writeText: async (text) => { out.push(text); }}};
await PhonePanel.copyAddress();
''', files=["views/phone.js"])
        failed = values[0]
        self.assertEqual(failed["tone"], "warn")
        self.assertIn("没有成功", failed["text"])
        self.assertEqual(values[1], "http://pc.tail.ts.net:8765/")
        self.assertEqual(values[2]["tone"], "info")
        self.assertIn("已复制", values[2]["text"])

    def test_recheck_button_asks_the_backend_again(self):
        values = run_phone_js('''
const calls = [];
globalThis.__api = async (name) => { calls.push(name); return {ok:true}; };
PhonePanel.wire();
await PhonePanel.refresh();
const before = calls.length;
$("#btn-tailscale-recheck").click();
for (let i = 0; i < 5; i += 1) await Promise.resolve();
out.push({wired: typeof ($("btn-tailscale-recheck").listeners.click || [])[0] === "function",
          grew: calls.length > before});
''', files=["views/phone.js"])
        self.assertEqual(values, [{"wired": True, "grew": True}],
                         "重新检测必须真的去问后端，不能只改本地文案")

    def test_channel_switch_remembers_preference(self):
        values = run_phone_js('''
const calls = [];
globalThis.__api = async (name, value) => { calls.push([name, value]); return {ok:true}; };
PhonePanel.wire();
out.push(typeof ($("phone-channel").listeners.change || [])[0] === "function");
await PhonePanel.changeChannel("cloudflare");
out.push(calls);
''', files=["views/phone.js"])
        wired, calls = values
        self.assertTrue(wired, "下拉框必须绑定 change")
        self.assertIn(["set_phone_access_preferences", "cloudflare"], calls)


class ComponentDownloadUiTests(unittest.TestCase):
    """组件下载态：进度、失败、取消，以及「缺 cloudflared 时入口不许消失」。"""

    def _features(self, **download):
        return ("PhonePanel.state.advanced = {channels:{cloudflare:{available:false,"
                "state:'missing',text:'组件包里没有校验过的 cloudflared'}},"
                "features:{phone_control:{ready:false, download:%s}}};"
                % json.dumps(download, ensure_ascii=False))

    def test_downloading_shows_progress_and_offers_cancel(self):
        snippet = self._features(state="downloading", downloaded=32 * 1048576,
                                 total_bytes=100 * 1048576) + '''
$("#phone-channel").value = "cloudflare";
PhonePanel.paint();
out.push({text:$("#phone-component-state").textContent,
          progress:$("#phone-component-progress").value,
          progressHidden:$("#phone-component-progress").hidden,
          installHidden:$("#btn-phone-component-install").hidden,
          cancelHidden:$("#btn-phone-component-cancel").hidden,
          startDisabled:$("#btn-phone-start").disabled});
'''
        row = run_phone_js(snippet, files=["views/phone.js"])[0]
        self.assertIn("32%", row["text"])
        self.assertEqual(row["progress"], 32)
        self.assertFalse(row["progressHidden"])
        self.assertTrue(row["installHidden"], "下载中不能再点安装")
        self.assertFalse(row["cancelHidden"])
        self.assertTrue(row["startDisabled"], "组件没落地就别让开通道")

    def test_failure_shows_reason_and_allows_retry(self):
        snippet = self._features(state="failed", text="下载超时，请重试。") + '''
PhonePanel.paint();
out.push({text:$("#phone-component-state").textContent,
          error:$("#phone-component-error").textContent,
          errorHidden:$("#phone-component-error").hidden,
          installHidden:$("#btn-phone-component-install").hidden});
'''
        row = run_phone_js(snippet, files=["views/phone.js"])[0]
        self.assertEqual(row["text"], "手机控制组件：安装失败")
        self.assertEqual(row["error"], "下载超时，请重试。")
        self.assertFalse(row["errorHidden"])
        self.assertFalse(row["installHidden"], "失败后必须能重试")

    def test_missing_cloudflared_keeps_the_install_entry(self):
        snippet = self._features(state="missing") + '''
PhonePanel.paint();
out.push({featureHidden:$("#btn-phone-feature-install").hidden,
          featureText:$("#btn-phone-feature-install").textContent,
          component:$("#phone-component-state").textContent});
'''
        row = run_phone_js(snippet, files=["views/phone.js"])[0]
        self.assertFalse(row["featureHidden"], "缺组件时安装入口不能消失")
        self.assertTrue(row["featureText"])
        self.assertEqual(row["component"], "手机控制组件：未安装")

    def test_cancelled_state_says_nothing_was_changed(self):
        snippet = self._features(state="cancelled") + '''
PhonePanel.paint();
out.push({text:$("#phone-component-state").textContent,
          installHidden:$("#btn-phone-component-install").hidden,
          cancelHidden:$("#btn-phone-component-cancel").hidden});
'''
        row = run_phone_js(snippet, files=["views/phone.js"])[0]
        self.assertIn("已取消", row["text"])
        self.assertFalse(row["installHidden"])
        self.assertTrue(row["cancelHidden"])

    def test_install_button_calls_the_download_action(self):
        snippet = self._features(state="missing") + '''
const calls = [];
globalThis.__api = (name, ...args) => {
  if (name === "phone_access_state") {
    return Promise.resolve({ok:true, running:false, channels:{}, features:{},
                            advanced:{features:{}, channels:{}}});
  }
  calls.push([name].concat(args));
  return Promise.resolve({ok:true, text:"开始下载"});
};
PhonePanel.wire();
$("#btn-phone-component-install").click();
for (let i = 0; i < 8; i += 1) await Promise.resolve();
out.push({calls:calls});
'''
        values = run_phone_js(snippet, files=["views/phone.js"])
        row = [item for item in values if "calls" in item][-1]
        self.assertIn(["download_advanced_feature", "phone_control"], row["calls"])

    def test_cloudflare_note_asks_for_a_new_scan_and_keeps_the_bookmark_hint(self):
        snippet = self._features(state="installed") + '''
$("#phone-channel").value = "cloudflare";
PhonePanel.paint();
out.push({warnHidden:$("#phone-channel-warn").hidden,
          guideHidden:$("#tailscale-guide").hidden,
          note:$("#phone-qr-note").textContent,
          selectValue:$("#phone-channel").value});
'''
        row = run_phone_js(snippet, files=["views/phone.js"])[0]
        self.assertFalse(row["warnHidden"], "Cloudflare 要显示换地址提示（文案在 HTML 里）")
        self.assertTrue(row["guideHidden"])
        self.assertNotIn("hidden", row)

        self.assertEqual(row["selectValue"], "cloudflare", "界面不许自己切通道")


class PhoneReloginRecoveryTests(unittest.TestCase):
    def test_snapshot_restores_challenge_without_erasing_typed_code(self):
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const png = "%s";
const state = {login_relay:{state:"waiting_code", flow_id:"f1", challenge_id:"c1",
  image:png, expires_in:60}};
ui.ingest({state});
out.push(ui.model.challenge && ui.model.challenge.challenge_id);
out.push([$("captcha").hidden, $("captcha").src === png]);
$("code").value = "Ab12";
ui.ingest({state});
out.push($("code").value);
ui.ingest({state:{login_relay:{state:"success",flow_id:"f1"}}});
out.push([$("btn-relogin").hidden, $("btn-relogin-submit").hidden,
          $("btn-relogin-refresh").hidden, $("btn-relogin-cancel").hidden, $("captcha").hidden]);
''' % CAPTCHA_PNG)
        self.assertEqual(values, ["c1", [False, True], "Ab12",
                                  [False, True, True, True, True]])

    def test_illegal_image_is_not_rendered(self):
        """非法图在服务端已被投影成空串：页面只许收起验证码，不许挂一张坏图。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state:{login_relay:{state:"waiting_code", flow_id:"f1", challenge_id:"c1",
  image:"", expires_in:60}}});
out.push([$("captcha").hidden, $("captcha").src, ui.model.challenge.challenge_id]);
''')
        self.assertEqual(values, [[True, "", "c1"]])

    def test_lost_submit_keeps_locked_and_reconciles(self):
        """网络异常：不许当成失败解锁，必须先对账再决定。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.model.challenge = {flow_id:"f1", challenge_id:"c1"};
ui.model.flow = {state:"waiting_code", flow_id:"f1", challenge_id:"c1",
                 submit_pending:false};
$("code").value = "Ab12";
let posts = 0;
globalThis.__fetch = async (path, opts) => {
  if (opts && opts.body) {
    posts += 1;
    out.push(JSON.parse(opts.body).action);
    throw new Error("network");
  }
  out.push("reconcile");
  return {status:200, json:async()=>({state:{}, events:[]})};
};
await PhoneUI.submitRelogin();
out.push([posts, ui.model.reloginSubmitting,
          PhoneModel.canSubmitRelogin(ui.model, ui.model.challenge)]);
out.push($("relogin-note").textContent);
''')
        self.assertEqual(values, ["phone_relogin_submit", "reconcile",
                                  [1, True, False], "提交结果未知，正在对账…"])

    def test_reconcile_unlocks_only_without_submit_in_flight(self):
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.model.challenge = {flow_id:"f1", challenge_id:"c1"};
ui.model.reloginSubmitting = true;
ui.ingest({state:{login_relay:{state:"waiting_code", flow_id:"f1", challenge_id:"c1",
  image:"", expires_in:60, submit_pending:true}}});
out.push([ui.model.reloginSubmitting,
          PhoneModel.canSubmitRelogin(ui.model, ui.model.challenge)]);
ui.ingest({state:{login_relay:{state:"waiting_code", flow_id:"f1", challenge_id:"c1",
  image:"", expires_in:60, submit_pending:false}}});
out.push([ui.model.reloginSubmitting,
          PhoneModel.canSubmitRelogin(ui.model, ui.model.challenge)]);
''')
        self.assertEqual(values, [[True, False], [False, True]])

    def test_verifying_keeps_controls_and_disables_resubmit(self):
        """校验途中不能说成"结束"，更不能让人对同一张图再发一次。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state:{login_relay:{state:"waiting_code", flow_id:"f1", challenge_id:"c1",
  image:"", expires_in:60, submit_pending:true}}});
ui.ingest({state:{login_relay:{state:"verifying", flow_id:"f1", challenge_id:"c1",
  submit_pending:true}}});
out.push([$("btn-relogin-submit").hidden, $("btn-relogin-submit").disabled,
          $("btn-relogin-cancel").hidden, $("btn-relogin").hidden]);
out.push(ui.model.challenge && ui.model.challenge.challenge_id);
out.push($("relogin-note").textContent);
''')
        self.assertEqual(values, [[False, True, False, True], "c1", "正在校验验证码…"])

    def test_new_challenge_clears_old_input_and_unlocks(self):
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.model.challenge = {flow_id:"f1", challenge_id:"c1"};
ui.model.reloginSubmitting = true;
$("code").value = "Ab12";
ui.ingest({state:{login_relay:{state:"waiting_code", flow_id:"f1", challenge_id:"c2",
  image:"", expires_in:60, submit_pending:false}}});
out.push([$("code").value, ui.model.reloginSubmitting,
          PhoneModel.canSubmitRelogin(ui.model, ui.model.challenge)]);
''')
        self.assertEqual(values, [["", False, True]])

    def test_existing_session_restores_app_and_csrf_without_pairing_again(self):
        values = run_phone_js('''
document.cookie = "campus_phone_csrf=fixture-csrf";
globalThis.__fetch = async (path, opts) => {
  if (opts && opts.method === "POST") out.push(opts.headers["X-Campus-Csrf"]);
  return {status:200, json:async()=>({state:{activities:[],busy:false},events:[]})};
};
await PhoneUI.poll(true);
out.push([$("pair").hidden, $("app").hidden]);
await PhoneUI.beginRelogin();
''')
        self.assertEqual(values[:2], [[True, False], "fixture-csrf"])

    def test_refresh_challenge_cancels_then_starts_once(self):
        values = run_phone_js('''
PhoneUI.model.lastOkAt = Date.now();
PhoneUI.model.flow = {flow_id:"old",state:"waiting_code"};
globalThis.__fetch = async (path, opts) => {
  if (opts && opts.body) out.push(JSON.parse(opts.body).action);
  return {status:200, json:async()=>({ok:true,flow_id:"new"})};
};
await PhoneUI.refreshRelogin();
''')
        self.assertEqual(values, ["phone_relogin_cancel", "phone_relogin_begin"])

    def test_write_requests_use_the_current_csrf_cookie(self):
        """重启后设备信任会换发新 csrf：写请求必须按当前 cookie 取，不能吃老值。

        症状（真机 2026-10-31）：状态读得到、页面显示已连接，但每次写操作都
        403 bad_csrf，界面上只看到「还不能开始」「没能显示电脑窗口」。
        """
        values = run_phone_js('''
document.cookie = "campus_phone_csrf=old-token";
globalThis.__fetch = async (path, opts) => {
  if (opts && opts.method === "POST") out.push(opts.headers["X-Campus-Csrf"]);
  return {status:200, json:async()=>({state:{activities:[],busy:false},events:[]})};
};
await PhoneUI.poll(true);
document.cookie = "campus_phone_csrf=new-token";
await PhoneUI.beginRelogin();
out.push(PhoneUI.model.csrf);
''')
        self.assertEqual(values, ["new-token", "new-token"])

    def test_idle_snapshot_does_not_overwrite_the_last_reason(self):
        """没有在进行的重登只是 idle，不是「结束」，更不能盖掉上一次的原因。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
$("relogin-note").textContent = "还不能开始：bad_csrf";
ui.ingest({state:{login_relay:{state:"idle"}}});
out.push([$("relogin-note").textContent, $("btn-relogin").hidden,
          $("btn-relogin-submit").hidden]);
ui.ingest({state:{login_relay:{state:"failed", safe_error:"eof", live:true}}});
out.push($("relogin-note").textContent);
''')
        # 用语统一：「重登」→「重新登录」（设计第 12 节用词表），行为不变
        self.assertEqual(values, [["还不能开始：bad_csrf", False, True], "重新登录结束：eof"])

    def test_the_archived_success_is_not_replayed_as_this_round(self):
        """中继空闲时会回上一场的结论：历史成功不能在每次打开页面时重播。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state:{login_relay:{state:"success", flow_id:"old-1", live:false}}});
out.push([$("relogin-note").textContent.indexOf("重新登录成功") === -1,
          $("relogin-note").textContent.indexOf("上次重新登录已完成") === 0]);
ui.ingest({state:{login_relay:{state:"success", flow_id:"now-1", live:true}}});
out.push($("relogin-note").textContent);
''')
        # 用语统一：「重登」→「重新登录」，历史成功仍只说「上次……已完成」，不重播
        self.assertEqual(values, [[True, True], "重新登录成功，正在刷新列表"])

    def test_the_archived_failure_is_reported_as_last_time(self):
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state:{login_relay:{state:"failed", safe_error:"eof", live:false}}});
out.push($("relogin-note").textContent);
''')
        self.assertEqual(values, ["上次重新登录未完成：eof"])

    def test_hung_request_cannot_latch_the_refresh_button(self):
        """断网时 fetch 可能永不返回：失败后单飞锁必须放开，刷新还能再发。"""
        values = run_phone_js('''
let calls = 0;
let signals = 0;
globalThis.AbortController = class {
  constructor() { this.signal = { aborted: false }; }
  abort() { this.signal.aborted = true; }
};
globalThis.__fetch = async (path, opts) => {
  calls += 1;
  if (opts && opts.signal) signals += 1;
  throw new Error("offline");
};
await PhoneUI.poll(true);
const latched = PhoneUI.model.flying;
await PhoneUI.poll(true);
out.push([latched, calls, signals]);
''')
        self.assertEqual(values, [[False, 2, 2]])

    # ---------- 电脑自己认图时，手机不该看到验证码 ----------
    def test_auto_mode_hides_the_captcha_and_reports_progress(self):
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const png = "%s";
ui.ingest({state:{login_relay:{mode:"auto", state:"waiting_code", retrying:true,
  flow_id:"f1", challenge_id:"c1", image:png, attempts:1, auto_failures:0,
  expires_in:null}}});
out.push([$("captcha").hidden, $("btn-relogin-submit").hidden,
          ui.model.challenge, $("relogin-note").textContent]);
''' % CAPTCHA_PNG)
        self.assertEqual(values[0][:3], [True, True, None])
        # 用语统一：「自动重登」→「自动登录」
        self.assertIn("电脑正在自动登录", values[0][3])
        self.assertIn("第 2 次", values[0][3], "第几次要照尝试次数报，不能含糊")

    def test_auto_mode_idle_explains_who_will_solve_the_captcha(self):
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state:{login_relay:{mode:"auto", state:"idle", retrying:false}}});
out.push([$("captcha").hidden, $("relogin-note").textContent]);
''')
        self.assertTrue(values[0][0])
        self.assertIn("电脑会自动识别验证码", values[0][1])

    def test_manual_takeover_renders_the_captcha_again(self):
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const png = "%s";
ui.ingest({state:{login_relay:{mode:"manual", state:"waiting_code", flow_id:"f1",
  challenge_id:"c1", image:png, attempts:3, auto_failures:0, expires_in:null}}});
out.push([$("captcha").hidden, $("captcha").src === png,
          $("btn-relogin-submit").hidden]);
''' % CAPTCHA_PNG)
        self.assertEqual(values, [[False, True, False]])

    def test_begin_shows_the_computer_took_over(self):
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
globalThis.__fetch = async () => ({status: 200, json: async () => ({ok: true, mode: "auto"})});
await ui.beginRelogin();
out.push([$("relogin-note").textContent, $("captcha").hidden,
          $("btn-relogin").disabled, ui.model.reloginStarting]);
''')
        self.assertIn("电脑正在自动登录", values[0][0])
        self.assertFalse(values[0][1])
        self.assertFalse(values[0][2])
        self.assertFalse(values[0][3])

    def test_auto_mode_hides_the_whole_captcha_area(self):
        """电脑在认图时，手机连输入框都不该出现——留个空框只会让人以为轮到自己。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const png = "%s";
ui.ingest({state:{login_relay:{mode:"auto", state:"waiting_code", retrying:true,
  flow_id:"f1", challenge_id:"c1", image:png, attempts:1, auto_failures:0,
  expires_in:null}}});
out.push([$("relogin-captcha-group").hidden, $("btn-relogin").hidden]);
''' % CAPTCHA_PNG)
        self.assertEqual(values, [[True, False]])

    def test_manual_mode_opens_the_whole_captcha_area(self):
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const png = "%s";
ui.ingest({state:{login_relay:{mode:"manual", state:"waiting_code", flow_id:"f1",
  challenge_id:"c1", image:png, attempts:3, expires_in:null}}});
out.push([$("relogin-captcha-group").hidden, $("captcha").hidden,
          $("btn-relogin-submit").hidden]);
''' % CAPTCHA_PNG)
        self.assertEqual(values, [[False, False, False]])

    def test_manual_takeover_after_auto_opens_the_captcha_area_again(self):
        """真实路径：电脑认图（组收起）→ 连续失败到阈值 → 整组重新出现。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const png = "%s";
ui.ingest({state:{login_relay:{mode:"auto", state:"waiting_code", retrying:true,
  flow_id:"f1", challenge_id:"c1", image:png, attempts:2, expires_in:null}}});
const auto = [$("relogin-captcha-group").hidden, $("btn-relogin").hidden];
ui.ingest({state:{login_relay:{mode:"manual", state:"waiting_code", flow_id:"f1",
  challenge_id:"c2", image:png, attempts:3, expires_in:null}}});
out.push(auto);
out.push([$("relogin-captcha-group").hidden, $("captcha").hidden,
          $("btn-relogin-submit").hidden, $("btn-relogin").hidden]);
''' % CAPTCHA_PNG)
        self.assertEqual(values[0], [True, False])
        self.assertEqual(values[1], [False, False, False, True])

    def test_offline_says_why_and_keeps_refresh_tappable(self):
        """断网时界面必须自己说明原因，刷新按钮不能被一起禁掉。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = 0;                    // 从没连上过 = 判旧
ui.refreshControls();
const first = [$("offline-note").hidden, $("offline-note").textContent,
               $("stale-note").hidden, $("btn-refresh").disabled];
globalThis.__fetch = async () => { throw new Error("offline"); };
await ui.poll(true);
await ui.poll(true);
out.push(first);
out.push([ui.model.offlineTries, $("offline-note").textContent.indexOf("已重试") >= 0]);
''')
        self.assertFalse(values[0][0], "离线提示必须显示")
        self.assertIn("连不上电脑", values[0][1])
        self.assertFalse(values[0][2], "还要告诉用户先刷新")
        self.assertFalse(values[0][3], "刷新按钮必须可点")
        self.assertEqual(values[1][0], 2)
        self.assertTrue(values[1][1], "重试次数要让用户看见")

    def test_refresh_button_shows_it_is_working(self):
        values = run_phone_js('''
const ui = PhoneUI;
let release;
globalThis.__fetch = () => new Promise((resolve) => {
  release = () => resolve({status: 200, json: async () => ({})});
});
const pending = ui.poll(true);
const during = [$("btn-refresh").disabled, $("btn-refresh").textContent];
release();
await pending;
out.push(during);
out.push([$("btn-refresh").disabled, $("btn-refresh").textContent]);
''')
        self.assertEqual(values[0], [True, "刷新中…"])
        self.assertEqual(values[1], [False, "刷新"])

    def test_a_successful_poll_clears_the_offline_note(self):
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = 0;
ui.model.offlineTries = 3;
ui.refreshControls();
const before = $("offline-note").hidden;
globalThis.__fetch = async () => ({status: 200, json: async () => ({})});
await ui.poll(true);
out.push([before, $("offline-note").hidden, ui.model.offlineTries]);
''')
        self.assertEqual(values, [[False, True, 0]])

    def test_double_tap_starts_only_one_relogin(self):
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
let posts = 0;
globalThis.__fetch = async (path, opts) => {
  if (String(path).indexOf("/api/action") >= 0) posts += 1;
  return {status: 200, json: async () => ({ok: true})};
};
const first = ui.beginRelogin();
const second = ui.beginRelogin();
await Promise.all([first, second]);
out.push(posts);
''')
        self.assertEqual(values, [1], "连点两下不能发出第二个开始请求")


class MobileWriteResilienceTests(unittest.TestCase):
    def test_older_event_cannot_overwrite_current_relogin_snapshot(self):
        values = run_phone_js('''
PhoneUI.ingest({state:{login_relay:{state:"success",flow_id:"f",live:false}},
  events:[{kind:"phone_relogin",seq:1,payload:{mode:"manual",state:"waiting_code",
    flow_id:"f",challenge_id:"old",image:"%s",live:true}}]});
out.push(PhoneUI.model.flow.state);
''' % CAPTCHA_PNG)
        self.assertEqual(values, ["success"])

    def test_action_401_returns_to_pairing_without_continuing_poll(self):
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.paired = true; ui.model.lastOkAt = Date.now();
ui.model.selected = ["a1"];
let calls = 0;
globalThis.__fetch = async () => { calls++; return {status:401, json:async()=>({ok:false,text:"need pair"})}; };
await ui.startPlan();
out.push([ui.model.paired, $("pair").hidden, calls, __timers.size]);
''')
        self.assertEqual(values, [[False, False, 1, 0]])

    def test_failed_cancel_without_error_field_keeps_challenge(self):
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.flow = {flow_id:"f"}; ui.model.challenge = {challenge_id:"c"};
globalThis.__fetch = async () => ({status:200, json:async()=>({ok:false,text:"still running"})});
out.push(await ui.cancelRelogin());
out.push(ui.model.challenge);
''')
        self.assertEqual(values, [False, {"challenge_id": "c"}])

    def test_unknown_start_can_be_explicitly_canceled_before_restarting(self):
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.paired = true; ui.model.lastOkAt = Date.now();
ui.model.pending = {request_id:"late", done:false};
ui.refreshControls();
out.push($("btn-cancel-start").hidden);
const actions = [];
globalThis.__fetch = async (url, opts) => {
  if (!opts.method) return {status:200,json:async()=>({state:{busy:false},events:[]})};
  actions.push(JSON.parse(opts.body));
  return {status:200,json:async()=>({ok:true,state:"canceled",request_id:"late"})};
};
await ui.cancelPendingStart();
out.push([ui.model.pending.done, actions[0].action, actions[0].args.request_id]);
''')
        self.assertEqual(values, [False, [True, "cancel_start_request", "late"]])

    """写动作出错时不能「点了没反应」：网络断、超时、403 都要有可见交代。

    起因（2026-10-31 真机）：手机页的写请求没有任何兜底，超时/断网会变成
    未处理的 Promise 拒绝，界面上什么都不说；403（bad_csrf）又会被当成
    「没配对」把用户赶回配对界面，而其实他刚配过对。
    """

    def test_write_action_network_failure_is_visible_not_swallowed(self):
        """断网点「开始报名计划」：要留下能读的话，而不是静默失败。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.model.selected = ["a1"];
globalThis.__fetch = async () => { throw new Error("offline"); };
await ui.startPlan();
out.push([$("banner").textContent, $("banner").hidden]);
''')
        self.assertEqual(values, [["连接中断，操作结果尚未确认；请刷新核对，避免重复操作", False]])

    def test_forbidden_csrf_keeps_the_app_open(self):
        """403 bad_csrf 不是「没配对」：停在主界面并提示刷新，不能踢回配对页。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
$("app").hidden = false;
$("pair").hidden = true;
document.cookie = "campus_phone_csrf=fresh-token";
globalThis.__fetch = async () => ({status: 403,
  json: async () => ({ok: false, error: "bad_csrf"})});
await ui.poll(true);
out.push([$("app").hidden, $("pair").hidden, ui.model.csrf,
          $("banner").textContent.indexOf("会话令牌已更新") >= 0]);
''')
        self.assertEqual(values, [[False, True, "fresh-token", True]])

    def test_need_pair_still_sends_the_user_back_to_pairing(self):
        """401 need_pair 才是「要重新配对」，这条老行为不能一起改掉。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
$("app").hidden = false;
$("pair").hidden = true;
globalThis.__fetch = async () => ({status: 401,
  json: async () => ({ok: false, error: "need_pair"})});
await ui.poll(true);
out.push([$("app").hidden, $("pair").hidden]);
''')
        self.assertEqual(values, [[True, False]])

    def test_pair_failure_says_the_network_is_down(self):
        """配对时断网：错误要写进配对卡片，不能只留一个未处理的异常。"""
        values = run_phone_js('''
$("pair-code").value = "123456";
globalThis.__fetch = async () => { throw new Error("offline"); };
$("btn-pair").click();
for (let i = 0; i < 20; i += 1) await Promise.resolve();
out.push($("pair-error").textContent.indexOf("网络不通") >= 0);
''')
        self.assertEqual(values, [True])


class PhoneHttpEnd2EndTests(unittest.TestCase):
    """本机 HTTP 端到端：pair → state → action，替身 Api，不开 100.x。"""

    def setUp(self):
        self.api_calls = []
        self.ui_dir = Path(tempfile.mkdtemp(prefix="campus-phone-ui-"))
        self.addCleanup(shutil.rmtree, str(self.ui_dir), True)
        for name in ("index.html", "styles.css", "app.js"):
            (self.ui_dir / name).write_text(
                (PHONE_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")

        class Api:
            def check(inner, request_id=""):
                self.api_calls.append(("check", request_id))
                return {"ok": True, "result": "valid"}

            def start_plan(inner, items, headed=False, retry_policy=None, request_id=""):
                self.api_calls.append(("start_plan", items, request_id))
                return {"ok": True, "plan_id": "p1", "request_id": request_id}

        self.service = PhoneAccessService(
            api=Api(), now=lambda: 100.0,
            state_of=lambda: {"activities": [], "busy": False,
                              "terms": {"accepted_version": "1"}},
            server_factory=lambda host, port, svc: PhoneHttpServer(
                host, port, svc, ui_dir=self.ui_dir))
        started = self.service.start("127.0.0.1", 0)
        self.assertTrue(started["ok"], started)
        self.base = started["address"].rstrip("/")
        self.code = started["pair_code"]
        self.addCleanup(self.service.stop)

    def _req(self, method, path, body=None, headers=None, cookie=None):
        data = None
        merged = {"Host": self.base.split("//", 1)[1]}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            merged["Content-Type"] = "application/json"
        merged.update(headers or {})
        if cookie:
            merged["Cookie"] = cookie
        req = urllib.request.Request(self.base + path, data=data, method=method)
        for key, value in merged.items():
            req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    def test_html_entry_resources_are_really_served(self):
        for path, ctype in (("/", "text/html"), ("/styles.css", "text/css"),
                            ("/app.js", "javascript")):
            with self.subTest(path=path):
                status, headers, body = self._req("GET", path)
                self.assertEqual(status, 200)
                self.assertIn(ctype, headers.get("Content-Type", ""))
                self.assertTrue(body, "入口资源必须真的可取")
                self.assertIn("content-security-policy",
                              {k.lower() for k in headers})

    def test_pair_state_action_roundtrip(self):
        status, headers, body = self._req(
            "POST", "/pair", body={"code": self.code},
            headers={"Origin": self.base})
        self.assertEqual(status, 200)
        payload = json.loads(body)
        cookie = next(v for k, v in headers.items()
                      if k.lower() == "set-cookie" and v.startswith("campus_phone_sid="))
        cookie = cookie.split(";", 1)[0]
        status, _, body = self._req("GET", "/api/state?after=0", cookie=cookie)
        self.assertEqual(status, 200)
        status, _, body = self._req(
            "POST", "/api/action",
            body={"action": "check", "args": {"request_id": "r1"}},
            headers={"Origin": self.base, "X-Campus-Csrf": payload["csrf"]},
            cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(self.api_calls, [("check", "r1")])


class LayoutStaticTests(unittest.TestCase):
    """375/430 布局静态检查：不截图、不假像素，只查结构性约束。"""

    def test_mobile_layout_statics(self):
        html = (PHONE_DIR / "index.html").read_text(encoding="utf-8")
        css = (PHONE_DIR / "styles.css").read_text(encoding="utf-8")
        self.assertIn('name="viewport"', html)
        self.assertIn("width=device-width", html)
        self.assertIn("max-width: 430px", css)
        self.assertIn("overflow-x: hidden", css)
        self.assertIn("min-height: 44px", css)
        self.assertNotIn("display: grid", css, "单栏布局不引入多列网格")
        self.assertIn("inputmode=", html, "数字键盘只给配对码/次数")
        report = Path("<tmp>/night-run-B-20261030/evidence/phone-ui-layout-375-430.txt")
        report.write_text(
            "375/430 布局静态检查（无截图、无像素断言）\n"
            "viewport=%s\nmax-width430=%s\noverflow-x-hidden=%s\nmin-tap-44px=%s\n"
            "真实手机像素与操作未验证。\n" % (
                "width=device-width" in html, "max-width: 430px" in css,
                "overflow-x: hidden" in css, "min-height: 44px" in css),
            encoding="utf-8")

    def test_relogin_captcha_group_is_one_switch(self):
        """验证码图、输入框、三个按钮必须同进同退，否则会出现「有框没图」的空输入。"""
        html = (PHONE_DIR / "index.html").read_text(encoding="utf-8")
        start = html.index('id="relogin-captcha-group"')
        relogin_button = html.index('id="btn-relogin"', start)
        block = html[start:relogin_button]
        for needle in ('id="captcha"', 'id="code"', 'id="btn-relogin-submit"',
                       'id="btn-relogin-refresh"', 'id="btn-relogin-cancel"'):
            self.assertIn(needle, block, "%s 不在验证码整组里" % needle)
        self.assertGreater(relogin_button, start,
                           "「在手机上重登」要留在组外常驻")
        self.assertIn('id="relogin-captcha-group" hidden', html,
                      "默认状态必须是收起")

    def test_offline_notice_is_a_first_class_element(self):
        html = (PHONE_DIR / "index.html").read_text(encoding="utf-8")
        for needle in ('id="offline-note"', 'id="stale-note"'):
            self.assertIn(needle, html)
        self.assertLess(html.index('id="last-sync"'), html.index('id="offline-note"'))
        css = (PHONE_DIR / "styles.css").read_text(encoding="utf-8")
        self.assertIn("position: sticky", css, "状态条要吸顶，断网时刷新还在拇指边")
        self.assertIn("button.wide", css)

    def test_mobile_console_order_and_controls(self):
        """手机页顺序＝手机上的真实任务顺序：今天 → 即将开放 → 已报名 → 更多。"""
        html = (PHONE_DIR / "index.html").read_text(encoding="utf-8")
        ids = ['id="conn"', 'id="last-sync"', 'id="login-expired-banner"',
               'id="today-items"', 'id="upcoming-items"', 'id="signed-summary"',
               'id="bookmark-hint"', 'id="more-panel"', 'id="filter-panel"',
               'id="retry-panel"', 'id="logs-panel"', 'id="relogin-panel"']
        positions = []
        for needle in ids:
            self.assertIn(needle, html, "手机页缺少 %s" % needle)
            positions.append(html.index(needle))
        self.assertEqual(positions, sorted(positions),
                         "顺序必须是 状态→今天→即将开放→已报名→书签→更多")
        # 报名按钮必须在「今天要参加」卡片里，不能在抽屉里
        self.assertLess(html.index('id="today-items"'), html.index('id="btn-start"'))
        self.assertLess(html.index('id="btn-start"'), html.index('id="more-panel"'))
        # 原生折叠用 details/summary，不引入自定义弹层
        self.assertIn("<details", html)
        self.assertNotIn("window.confirm", html)

    def test_mobile_palette_and_touch_targets(self):
        css = (PHONE_DIR / "styles.css").read_text(encoding="utf-8")
        for token in ("--hall:", "--paper:", "--ink:", "--blue:", "--line:"):
            self.assertIn(token, css, "手机端必须复用桌面色板 %s" % token)
        self.assertIn("var(--hall)", css)
        self.assertIn("min-height: 44px", css)
        self.assertIn("prefers-reduced-motion", css)
        html = (PHONE_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn("打开后建议加入手机书签，方便下次访问。", html)

    def test_desktop_entry_keeps_existing_contracts(self):
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="retry-for"', html)
        self.assertNotIn('id="phone-panel"', html)
        self.assertIn('id="phone-access-detail"', html)
        self.assertIn('id="btn-phone-feature-install"', html)
        self.assertIn('id="btn-ocr-feature-install"', html)
        self.assertIn('src="views/phone.js"', html)
        self.assertNotIn("onclick=", html, "桌面仍不内联脚本")

    def test_help_channel_guide_statics(self):
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        for needle in ('id="phone-channel-state"', 'id="btn-tailscale-recheck"',
                       'id="phone-channel-warn"', 'id="phone-bookmark-hint"',
                       'id="btn-phone-address-copy"', 'id="phone-address-alt-line"',
                       'id="phone-stop-confirm"', 'id="btn-phone-stop-cancel"',
                       "先扫二维码", "重启后需重新扫码"):
            self.assertIn(needle, html, "帮助入口缺少 %s" % needle)
        # 四步说明只解释环境准备，不把配对码拼进地址或按钮
        self.assertNotIn("pair_code=", html)
        self.assertNotIn("window.confirm", html)

    def test_help_cross_device_credential_contracts(self):
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        # 远程通道只允许 Tailscale 与 Cloudflare，不给普通局域网入口
        select = re.search(
            r'<select id="phone-channel".*?</select>', html, re.S)
        self.assertIsNotNone(select, "帮助里必须有远程通道选择")
        self.assertEqual(re.findall(r'value="([^"]+)"', select.group(0)),
                         ["tailscale", "cloudflare"])
        # 文案明确先扫码再输入配对码
        self.assertIn("先扫二维码，再输入配对码", html)
        self.assertIn('id="phone-qr"', html)
        self.assertIn('id="phone-code"', html)
        # 账号区域：保存/清除 + 人工验证码降级提示；密码框按密码类型
        self.assertIn('id="credential-editor"', html)
        self.assertIn('id="btn-credentials-save"', html)
        self.assertIn('id="btn-credentials-clear"', html)
        self.assertRegex(html, r'id="credential-pass"[^>]*type="password"')
        self.assertIn("人工输入", html, "未安装 ddddocr 必须提示人工降级")


class PhoneSyncPolicyTests(unittest.TestCase):
    """自适应同步：空闲 15 秒、忙碌 2 秒、未配对不排、401 停表、隐藏停表。"""

    def _state_ok(self):
        return """
const okState = {status: 200, json: () => Promise.resolve({
  state: { activities: [], busy: %s, plan: null,
           retry_options: { default: 120, choices: [] } },
  events: [], reset: false, seq: 1 })};
"""

    def test_idle_syncs_every_fifteen_seconds(self):
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.paired = true;
ui.model.busy = false;
globalThis.__fetch = async () => ({status: 200, json: async () => ({
  state: { activities: [], busy: false, plan: null,
           retry_options: { default: 120, choices: [] } },
  events: [], reset: false, seq: 1 })});
await ui.poll(true);
out.push(__timerDelays());
""")
        self.assertEqual(values, [[15000]])

    def test_busy_plan_syncs_every_two_seconds(self):
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.paired = true;
ui.model.busy = true;
globalThis.__fetch = async () => ({status: 200, json: async () => ({
  state: { activities: [], busy: true, plan: null,
           retry_options: { default: 120, choices: [] } },
  events: [], reset: false, seq: 1 })});
await ui.poll(true);
out.push(__timerDelays());
""")
        self.assertEqual(values, [[2000]])

    def test_relogin_in_flight_counts_as_active(self):
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.paired = true;
ui.model.busy = false;
globalThis.__fetch = async () => ({status: 200, json: async () => ({
  state: { activities: [], busy: false, plan: null,
           login_relay: {mode: "manual", state: "waiting_code", flow_id: "f",
                         challenge_id: "c", image: "", expires_in: null},
           retry_options: { default: 120, choices: [] } },
  events: [], reset: false, seq: 1 })});
await ui.poll(true);
out.push(__timerDelays());
""")
        self.assertEqual(values, [[2000]], "验证码在等人工，界面数字在动，同步要跟上")

    def test_hidden_page_does_not_schedule(self):
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.paired = true;
document.hidden = true;
globalThis.__fetch = async () => ({status: 200, json: async () => ({
  state: { activities: [], busy: false, plan: null,
           retry_options: { default: 120, choices: [] } },
  events: [], reset: false, seq: 1 })});
await ui.poll(true);
out.push(__timers.size);
document.hidden = false;
await ui.poll(true);
out.push(__timers.size);
""")
        self.assertEqual(values, [0, 1], "后台一个定时器都不许留")

    def test_unpaired_page_never_requests(self):
        """首屏探测只在可能已有会话时才发：没 cookie 就停在配对页，一个请求都不发。"""
        values = run_phone_js("""
let calls = 0;
globalThis.__fetch = async () => { calls += 1; return {status: 200, json: async () => ({})}; };
const ui = PhoneUI;
ui.model.paired = false;
if (ui.model.pollTimer) clearTimeout(ui.model.pollTimer);
ui.model.pollTimer = null;
out.push([calls, __timers.size, $("pair").hidden]);
""")
        self.assertEqual(values, [[0, 0, False]], "没配对的页面不许自己发请求或排定时器")

    def test_401_stops_the_automatic_sync(self):
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.paired = true;
globalThis.__fetch = async () => ({status: 401, json: async () => ({ok: false, error: "need_pair"})});
await ui.poll(true);
out.push([ui.model.paired, __timers.size, $("app").hidden, $("pair").hidden]);
""")
        self.assertEqual(values, [[False, 0, True, False]])

    def test_thirty_seconds_before_anything_is_stale(self):
        values = run_phone_js("""
const now = Date.now();
out.push([PhoneModel.isStale(now - 29000, now),
          PhoneModel.isStale(now - 31000, now)]);
""")
        self.assertEqual(values, [[False, True]])

    def test_successful_sync_clears_only_the_stale_banner(self):
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.selected = ["a1"];
ui.model.paired = true;
ui.model.lastOkAt = 0;                    // 过时：点开始会被门禁挡住
await ui.startPlan();
const stale = [ui.model.bannerKind, $("banner").hidden];
const ok = {status: 200, json: async () => ({
  state: { activities: [], busy: false, plan: null,
           retry_options: { default: 120, choices: [] } },
  events: [], reset: false, seq: 1 })};
globalThis.__fetch = async () => ok;
ui.model.lastOkAt = Date.now();
await ui.poll(true);
const cleared = $("banner").hidden;
globalThis.__fetch = async () => ({status: 403, json: async () => ({ok: false, error: "bad_csrf"})});
ui.model.lastOkAt = Date.now();
await ui.poll(true);
const err = [ui.model.bannerKind, $("banner").hidden];
globalThis.__fetch = async () => ok;
await ui.poll(true);
out.push(stale, cleared, err, $("banner").hidden);
""")
        self.assertEqual(values[0], ["stale_action", False])
        self.assertTrue(values[1], "成功同步要清掉「状态已过时」")
        self.assertEqual(values[2], ["error", False])
        self.assertFalse(values[3], "403 的提示不能被一次成功同步抹掉")

    def test_manual_refresh_keeps_one_request_and_one_timer(self):
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.paired = true;
let calls = 0;
let release;
globalThis.__fetch = (path) => {
  calls += 1;
  return new Promise((resolve) => { release = () => resolve({status: 200, json: async () => ({
    state: { activities: [], busy: false, plan: null,
             retry_options: { default: 120, choices: [] } },
    events: [], reset: false, seq: 1 })}); });
};
const first = ui.poll(true);
await ui.poll(true);        // 在途时再点刷新：不发第二个请求
release();
await first;
out.push([calls, __timers.size]);
""")
        self.assertEqual(values, [[1, 1]], "单飞 + 只留一个定时器")



class WorkbenchPhoneTests(unittest.TestCase):
    """新手机页（设计第 10 节 / 原型 Phone*）：账号密码默认不保存、条款未同意只读、连不上电脑红条、核对计划提醒。"""

    def test_account_password_is_used_once_unless_save_is_ticked(self):
        """电脑上没保存账号时手机露出账号密码：默认只用这一次，勾选才保存；发出后密码框清空；保存过就不再要。"""
        html = (PHONE_DIR / "index.html").read_text(encoding="utf-8")
        at = html.index('id="relogin-save"')
        tag = html[html.rindex("<input", 0, at):html.index(">", at)]
        self.assertNotIn("checked", tag, "「保存到这台电脑」默认不勾")
        values = run_phone_js('''
const ui = PhoneUI;
const posts = [];
globalThis.__fetch = async (path, opts) => {
  if (opts && opts.body) posts.push(JSON.parse(opts.body));
  return {status: 200, json: async () => ({ok: true, mode: "manual"})};
};
ui.model.lastOkAt = Date.now();
ui.ingest({state: {terms_ok: true, relogin_setup: {saved: false, account_hint: "", ocr_ready: false, paused: false}}});
ui.refreshControls();
const shown = !$("relogin-account").hidden;
$("relogin-user").value = "u1"; $("relogin-pass").value = "p1";
await ui.beginRelogin();
const once = posts[posts.length - 1];
const cleared = $("relogin-pass").value;
ui.model.reloginStarting = false;
$("relogin-pass").value = "p2"; $("relogin-save").checked = true;
await ui.beginRelogin();
const saved = posts[posts.length - 1];
ui.ingest({state: {relogin_setup: {saved: true, account_hint: "u*", ocr_ready: true, paused: false}}});
ui.refreshControls();
const hidden = $("relogin-account").hidden;
ui.model.reloginStarting = false;
await ui.beginRelogin();
const fromComputer = posts[posts.length - 1];
ui.ingest({state: {relogin_setup: {saved: true, account_hint: "u*", ocr_ready: true, paused: true}}});
ui.refreshControls();
out.push({shown, once, cleared, saved, hidden, fromComputer, pausedShown: !$("relogin-account").hidden});
''')
        r = values[0]
        self.assertTrue(r["shown"], "电脑上没保存账号：手机露出账号密码")
        self.assertEqual(r["once"]["action"], "phone_relogin_begin")
        self.assertEqual(r["once"]["args"], {"username": "u1", "password": "p1", "save": False},
                         "默认只用这一次，不保存")
        self.assertEqual(r["cleared"], "", "发出后密码框立刻清空")
        self.assertTrue(r["saved"]["args"]["save"], "勾选才保存到电脑")
        self.assertTrue(r["hidden"], "电脑上保存过账号就不再要")
        self.assertEqual(r["fromComputer"]["args"], {}, "用电脑上保存的账号时不带账号密码")
        self.assertTrue(r["pausedShown"], "保存的密码学校不认：重新露出输入")

    def test_terms_not_accepted_keeps_the_phone_read_only(self):
        """电脑没同意条款：手机停在缓存，不能开始也不能重新登录，顶部说明原因；同意后提示收起。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state: {terms_ok: false, busy: false, activities: [{id: "a1", name: "甲"}]}});
ui.model.selected = ["a1"];
ui.refreshControls();
const locked = {start: $("btn-start").disabled, relogin: $("btn-relogin").disabled,
  banner: $("banner").textContent, bannerHidden: $("banner").hidden};
ui.ingest({state: {terms_ok: true}});
ui.refreshControls();
out.push({locked, start: $("btn-start").disabled, relogin: $("btn-relogin").disabled,
  bannerHidden: $("banner").hidden});
''')
        r = values[0]
        self.assertTrue(r["locked"]["start"], "没同意条款不能开始")
        self.assertTrue(r["locked"]["relogin"], "没同意条款不能重新登录")
        self.assertFalse(r["locked"]["bannerHidden"])
        self.assertIn("还没同意使用条款", r["locked"]["banner"])
        self.assertIn("停在上次的结果", r["locked"]["banner"], "说明现在看到的是缓存")
        self.assertFalse(r["start"], "同意后恢复")
        self.assertFalse(r["relogin"])
        self.assertTrue(r["bannerHidden"], "同意后条款提示收起")

    def test_offline_bar_is_red(self):
        """连不上电脑是红条（原型 PhoneOffline 的 tone bad），比琥珀色提醒更显眼。"""
        css = (PHONE_DIR / "styles.css").read_text(encoding="utf-8")
        self.assertIn("#offline-note.warn { color: var(--bad); background: var(--bad-tint);", css)
        html = (PHONE_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="offline-note" class="warn" role="alert"', html)

    def test_review_lists_the_plan_and_the_same_reminders(self):
        """点「开始」先核对：列出已选场次、尝试设置和与电脑同一套的提醒；有提醒按钮叫「仍然开始」；确认后才真的开始。"""
        values = run_phone_js('''
const ui = PhoneUI;
const posts = [];
globalThis.__fetch = async (path, opts) => {
  if (opts && opts.body) posts.push(JSON.parse(opts.body).action);
  return {status: 200, json: async () => ({ok: true, plan_id: "p1"})};
};
ui.model.lastOkAt = Date.now();
ui.ingest({state: {terms_ok: true, busy: false, business_clock: {state: "holdover"},
  relogin_setup: {saved: false, ocr_ready: false, paused: false},
  activities: [{id: "a1", name: "甲活动", seconds_to_open: 2 * 86400}]}});
ui.model.selected = ["a1"];
ui.refreshControls();
$("btn-start").click();
const review = {hidden: $("review-panel").hidden, items: $("review-items").innerHTML,
  warns: $("review-warns").innerHTML, label: $("btn-review-start").textContent, posts: posts.slice()};
$("btn-review-back").click();
const back = {hidden: $("review-panel").hidden, posts: posts.slice()};
const quiet = PhoneModel.preStartWarnings({clockState: "ready", retry: {retry_for_s: 120},
  reloginSetup: {saved: true, ocr_ready: true, paused: false}}, [{id: "b1", seconds_to_open: 600, sign_end_ts: 1}]);
out.push({review, back, quiet});
''')
        r = values[0]
        self.assertFalse(r["review"]["hidden"], "点开始先出核对面板")
        self.assertIn("甲活动", r["review"]["items"])
        self.assertIn("上次的校准结果", r["review"]["warns"], "沿用上次校准要提醒")
        self.assertIn("自动登录没开全", r["review"]["warns"], "等 1 小时以上又没开全自动登录要提醒")
        self.assertIn("24 小时以后", r["review"]["warns"], "24 小时以后要提醒")
        self.assertEqual(r["review"]["label"], "仍然开始报名计划", "有提醒只改名，不拦")
        self.assertEqual(r["review"]["posts"], [], "核对时还没开始")
        self.assertTrue(r["back"]["hidden"], "「返回」收起核对")
        self.assertEqual(r["back"]["posts"], [], "返回不开始")
        self.assertEqual(r["quiet"], [], "都正常时没有提醒")
        js = (PHONE_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("seconds_to_open", js, "开放时间用后端给的秒数，不读手机时钟")

    def test_running_plan_says_keep_going_and_edit_on_the_computer(self):
        """运行中：重新登录成功写「报名计划照常继续」；手机只能停止，修改要回电脑。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const running = {busy: true, plan: {plan_id: "p1", status: "running", source: "phone",
  tasks: [{task_id: "t1", name: "甲活动", status: "waiting", path: "direct"}]}, activities: []};
/* 走真实轮询：poll 把快照交给 ingest 再画计划行 */
globalThis.__fetch = async () => ({status: 200, json: async () => ({state: running, events: []})});
await ui.poll(true);
ui.ingest({state: {login_relay: {state: "success", flow_id: "f1", live: true}}});
out.push([$("relogin-note").textContent, $("plan-line").textContent]);
''')
        note, line = values[0]
        self.assertEqual(note, "重新登录成功，报名计划照常继续")
        self.assertIn("要修改计划，回电脑上改", line)
        self.assertIn("（从手机开始）", line)

    def test_task_lines_use_the_computer_vocabulary(self):
        """每场一句话与电脑同一套说法：名额已满不是工具出错、待核对不自动重发、等自动登录、改用页面点击。"""
        values = run_phone_js('''
out.push([
  PhoneModel.taskText({status: "failed", stop_reason: "full"}),
  PhoneModel.taskText({status: "failed", stop_reason: "unconfirmed"}),
  PhoneModel.taskText({status: "waiting", login_wait: "waiting"}),
  PhoneModel.taskText({status: "submitting", path: "click", path_reason: "接口不可用"}),
  PhoneModel.taskText({status: "already_signed"}),
  PhoneModel.taskText({status: "failed", outcome_label: "学校拒绝"}),
]);
''')
        full, unconfirmed, waiting, click, signed, failed = values[0]
        self.assertIn("名额已满", full)
        self.assertIn("不是工具出错", full)
        self.assertIn("待核对", unconfirmed)
        self.assertIn("不会再自动重发", unconfirmed)
        self.assertIn("自动登录", waiting)
        self.assertIn("改用页面点击：接口不可用", click)
        self.assertEqual(signed, "已报名")
        self.assertEqual(failed, "报名未成功：学校拒绝")


if __name__ == "__main__":
    unittest.main()
