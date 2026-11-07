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

    def test_bucket_uses_beijing_sign_start_without_open_ts(self):
        """真实手机快照只有 sign_start：按 UTC+8 解析，24 小时内算「今天」（M7）。"""
        values = run_phone_js("""
const nowS = Math.floor(Date.UTC(2026, 10, 4, 4, 0, 0) / 1000);  /* 北京时间 12:00 */
out.push(Math.floor(Date.UTC(2026, 10, 4, 12, 0, 0) / 1000));
out.push(PhoneModel.openEpochOf({ sign_start: "2026-11-04 20:00:00" }));
out.push(PhoneModel.bucketOf({ signed: false, sign_start: "2026-11-04 20:00:00" }, nowS));
out.push(PhoneModel.bucketOf({ signed: false, sign_start: "2026-11-06 09:00:00" }, nowS));
out.push(PhoneModel.bucketOf({ signed: false, sign_start: "2026/11/04 20:00:00" }, nowS));
out.push(PhoneModel.bucketOf({ signed: false, open_ts: nowS + 600,
  sign_start: "2026-12-31 20:00:00" }, nowS));
""")
        self.assertEqual(values[1], values[0], "20:00 北京时间必须换算成 12:00 UTC（UTC+8）")
        self.assertEqual(values[2], "today", "24 小时内开放要进「今天」")
        self.assertEqual(values[3], "upcoming", "更远的进「即将开放」")
        self.assertEqual(values[4], "upcoming", "解析不了的文本不猜，按「以后」")
        self.assertEqual(values[5], "today", "有 open_ts 时以它为准")

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
''', files=["views/phone.js", "views/settings.js"])
        # fe-ocr-login 同步：验证码识别一节的状态、按钮绘制从 phone.js 搬到 settings.js（paintOcrDownload），
        # 所以这里把 settings.js 一起加载；断言本身（加载失败 chip、重新导入按钮）一字未改
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
''', files=["views/phone.js", "views/settings.js"])
        # fe-ocr-login 同步：同上，验证码识别的「重新导入」按钮由 settings.js 绘制
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
        # fe-phone 同步：下拉框换成两张单选卡（PH16），两条通道同时各显示各的状态；
        # 四步清单与 Cloudflare 警告段按 PH21 删除，说明收进卡片，所以改读两张卡和提示行（PH20）
        values = run_phone_js('''
PhonePanel.state.advanced = {features:{phone_control:{ready:true, available:true}}, channels:{
  tailscale:{available:false, state:"missing", text:"电脑上没有 Tailscale"},
  cloudflare:{available:true, state:"available", text:"可用"}}};
PhonePanel.channel = "cloudflare";
PhonePanel.paint();
out.push({ts:$("#phone-chan-tailscale-status").textContent,
          cf:$("#phone-chan-cloudflare-status").textContent,
          cfCard:$("#phone-chan-cloudflare-card").className,
          cfChecked:$("#phone-chan-cloudflare").checked,
          recheckHidden:$("#btn-tailscale-recheck").hidden,
          hintHidden:$("#phone-channel-hint").hidden,
          startDisabled:$("#btn-phone-start").disabled});
PhonePanel.channel = "tailscale";
PhonePanel.paint();
out.push({tsCard:$("#phone-chan-tailscale-card").className,
          tsText:$("#phone-chan-tailscale-text").textContent,
          recheckHidden:$("#btn-tailscale-recheck").hidden,
          hint:$("#phone-channel-hint").textContent,
          startDisabled:$("#btn-phone-start").disabled});
''', files=["views/phone.js"])
        cloudflare, tailscale = values
        self.assertEqual(cloudflare, {"ts": "未安装", "cf": "可用", "cfCard": "chan on",
                                      "cfChecked": True, "recheckHidden": True,
                                      "hintHidden": True, "startDisabled": False})
        self.assertEqual(tailscale["tsCard"], "chan on")
        self.assertEqual(tailscale["tsText"], "电脑和手机都要装好并登录同一个账号；工具不会替你安装。")
        self.assertFalse(tailscale["recheckHidden"], "选了没装的 Tailscale 才给重新检测（PH19）")
        self.assertEqual(tailscale["hint"], "还差一步：装好 Tailscale 后点“重新检测”，或者改用 Cloudflare。")
        self.assertTrue(tailscale["startDisabled"], "Tailscale 没连上时开启按钮禁用（PH18）")

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
        # 配对码过期/被用掉后会换新码，界面必须说一声并给出剩余时间。
        # fe-phone 同步：倒计时句照原型改成「m:ss 后失效，一码只能用一次」（PH25 的文案，审核决定 A5）；
        # 换码提示从抽屉底部的 helpStatus 改为配对区里就地显示（PH30），所以读 #phone-pair-note
        values = run_phone_js('''
PhonePanel.state.running = true;
PhonePanel.state.advanced = {features:{phone_control:{ready:true, available:true}},
  channels:{tailscale:{available:true, state:"connected"}}, credential:{}};
PhonePanel.state.pair_code_status = {code:"111111", expires_in:265, seq:1,
                                    reason:"started"};
PhonePanel.paint();
out.push({code:$("#phone-code").textContent,
          note:$("#pair-code-note").innerHTML,
          pairHidden:$("#phone-pair").hidden,
          noticeHidden:$("#phone-pair-note").hidden});
PhonePanel.state.pair_code_status = {code:"222222", expires_in:300, seq:2,
                                    reason:"expired"};
PhonePanel.paint();
out.push({code:$("#phone-code").textContent,
          note:$("#pair-code-note").innerHTML,
          notice:$("#phone-pair-note").textContent,
          noticeHidden:$("#phone-pair-note").hidden});
''', files=["views/phone.js"])
        first, second = values
        self.assertEqual(first["code"], "111111")
        self.assertEqual(first["note"], "<b>4:25</b> 后失效，一码只能用一次")
        self.assertFalse(first["pairHidden"], "还没连上时配对区要显示")
        self.assertTrue(first["noticeHidden"], "第一张码不算换码，不提示")
        self.assertEqual(second["code"], "222222")
        self.assertEqual(second["note"], "<b>5:00</b> 后失效，一码只能用一次")
        self.assertEqual(second["notice"], "配对码已过期，已经换成新的。")
        self.assertFalse(second["noticeHidden"])

class ReloginCardUiTests(unittest.TestCase):
    """电脑续登录：ddddocr 与账号保存分开说，清除账号必须先确认。"""

    def test_missing_ocr_still_saves_account(self):
        # fe-ocr-login 同步（CR03、CR07、CR08）：总状态 chip 与「验证码识别：…」状态行按原型删除，
        # 「没装验证码识别也能存账号」改读自动登录结论行（原型第四档「还缺验证码识别组件」）；
        # 保存仍走 save_relogin_credentials，不退成只存内存——这一条断言原样保留
        values = run_phone_js("""
const calls = [];
globalThis.__api = async (name) => { calls.push(name); return {ok:true, saved:true}; };
PhonePanel.state.advanced = {
  features:{relogin_ocr:{available:false, ready:false, status:"missing"}},
  credential:{available:true, store_available:true, saved:false, ocr_ready:false}};
PhonePanel.paint();
out.push({auto: $("#relogin-auto-path").textContent,
          slot: $("#btn-credentials-manage").textContent});
PhonePanel.state.advanced.credential = {available:true, store_available:true, saved:true,
  username:"20230001", ocr_ready:false};
PhonePanel.paint();
out.push({auto: $("#relogin-auto-path").textContent,
          autoCls: $("#relogin-auto-path").className,
          slot: $("#btn-credentials-manage").textContent});
$("#credential-user").value = "20230001";
$("#credential-pass").value = "secret";
await PhonePanel.saveCredentials();
out.push({calls: calls.slice()});
""", files=["views/phone.js"])
        # helpStatus 会往 out 里补提示，这里只取自己 push 的结构
        none, saved_row = values[0], values[1]
        second = [row for row in values if "calls" in row][-1]
        self.assertIn("还没有账号密码", none["auto"])
        self.assertEqual(none["slot"], "填写账号密码")
        self.assertIn("还缺验证码识别组件", saved_row["auto"], "没装验证码识别也要说清缺什么、会怎样")
        self.assertIn("要你输验证码", saved_row["auto"])
        self.assertEqual(saved_row["autoCls"], "up-warn")
        self.assertEqual(saved_row["slot"], "更换")
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
        # fe-ocr-login 同步（CR03、CR06、CR07）：总状态 chip 删除；账号行改成「已保存账号 st****01。」；
        # 自动登录结论行逐字照原型第二档「已启用…不用你动手」。打码、最近一次登录、手机路径三条断言保留
        values = run_phone_js("""
PhonePanel.state.advanced = {
  features:{relogin_ocr:{available:true, ready:true, status:"ready"}},
  credential:{available:true, store_available:true, saved:true,
    username:"20230001", ocr_ready:true, last_origin:"auto_ocr",
    automatic:{last_used_ago_s:90, last_used_method:"auto_ocr"}}};
PhonePanel.paint();
out.push({cred: $("#relogin-credential-status").textContent,
          credHidden: $("#relogin-credential-status").hidden,
          last: $("#relogin-last-used").textContent,
          auto: $("#relogin-auto-path").textContent,
          autoCls: $("#relogin-auto-path").className,
          phone: $("#relogin-phone-path").textContent});
""", files=["views/phone.js"])
        row = values[0]
        self.assertFalse(row["credHidden"])
        # 旧断言「卡片写出完整账号」改为只露首尾各两位（设计 9.3：界面上的账号一律打码）
        self.assertEqual(row["cred"], "已保存账号 20****01。")
        self.assertNotIn("20230001", row["cred"], "完整账号不得出现在界面上")
        self.assertIn("电脑自动恢复", row["last"])
        self.assertEqual(row["auto"], "失效后自动登录：已启用。登录失效时电脑自己重新登录，报名计划等开放或提交时也一样，不用你动手。")
        self.assertEqual(row["autoCls"], "up-ok")
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
        # fe-phone 同步：通道从下拉框改成两张单选卡（PH16），启动中整组禁用；关闭按钮文案照原型改成
        # 「关闭手机访问」（PH29）；Cloudflare 启动中的提示就在按钮下一行（PH20），不再写抽屉底部
        values = run_phone_js('''
const calls = [];
let release;
globalThis.__api = (name, ...args) => {
  calls.push([name].concat(args));
  if (name === "start_phone_access") return new Promise((resolve) => { release = resolve; });
  return Promise.resolve({ok:true, running:true, address:"https://x.trycloudflare.com"});
};
PhonePanel.state.advanced = {features:{phone_control:{ready:true, available:true}},
  channels:{cloudflare:{available:true, state:"available"}}};
PhonePanel.channel = "cloudflare";
const task = PhonePanel.toggleStart();
await Promise.resolve();
out.push({mark:"pending", hidden: $("#btn-phone-start").hidden,
          disabled: $("#btn-phone-start").disabled,
          text: $("#btn-phone-start").textContent,
          channelDisabled: $("#phone-chan-cloudflare").disabled && $("#phone-chan-tailscale").disabled,
          hint: $("#phone-channel-hint").textContent,
          lead: $("#phone-feature-note").textContent});
await PhonePanel.toggleStart();
out.push({mark:"calls", starts: calls.filter((c) => c[0] === "start_phone_access")});
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
        self.assertEqual(marks["pending"]["hint"], "正在建立临时隧道，最多等 20 秒。")
        self.assertEqual(marks["pending"]["lead"], "正在开启，先不要切换通道。")
        self.assertEqual(marks["calls"]["starts"], [["start_phone_access", "cloudflare"]],
                         "连点两次只能发一次启动请求，且开的是卡片里选的那条")
        self.assertTrue(marks["done"]["startHidden"])
        self.assertFalse(marks["done"]["stopHidden"])
        self.assertEqual(marks["done"]["stopText"], "关闭手机访问")

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
        # fe-phone 同步：复制结果不再写抽屉底部（PH30）。成功时按钮 1.6 秒内显示「已复制」（PH26），
        # 失败才在已开启那块就地红字说明
        values = run_phone_js('''
PhonePanel.state.running = true;
PhonePanel.state.address = "http://pc.tail.ts.net:8765/";
await PhonePanel.copyAddress();
out.push({err:$("#phone-on-error").textContent, errHidden:$("#phone-on-error").hidden,
          label:$("#btn-phone-address-copy").textContent});
globalThis.navigator = {clipboard:{writeText: async (text) => { out.push(text); }}};
await PhonePanel.copyAddress();
out.push({err:$("#phone-on-error").textContent, errHidden:$("#phone-on-error").hidden,
          label:$("#btn-phone-address-copy").textContent,
          timers:__timerDelays()});
''', files=["views/phone.js"])
        failed, copied, done = values
        self.assertEqual(failed["err"], "复制没有成功，请手动选中地址。")
        self.assertFalse(failed["errHidden"])
        self.assertEqual(failed["label"], "复制")
        self.assertEqual(copied, "http://pc.tail.ts.net:8765/")
        self.assertTrue(done["errHidden"])
        self.assertEqual(done["label"], "已复制")
        self.assertIn(1600, done["timers"], "「已复制」1.6 秒后变回「复制」")

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
        # fe-phone 同步：下拉框换成两张单选卡（PH16），每张卡的 radio 都要绑定 change，选卡仍调偏好接口
        values = run_phone_js('''
const calls = [];
globalThis.__api = async (name, value) => { calls.push([name, value]); return {ok:true}; };
PhonePanel.wire();
out.push(["tailscale", "cloudflare"].every((key) =>
  typeof ($("phone-chan-" + key).listeners.change || [])[0] === "function"));
$("phone-chan-cloudflare").listeners.change[0]();
for (let i = 0; i < 8; i += 1) await Promise.resolve();
out.push(calls);
out.push(PhonePanel.channel);
''', files=["views/phone.js"])
        wired, calls, chosen = values
        self.assertTrue(wired, "两张通道卡都必须绑定 change")
        self.assertIn(["set_phone_access_preferences", "cloudflare"], calls)
        self.assertEqual(chosen, "cloudflare")


class ComponentDownloadUiTests(unittest.TestCase):
    """组件下载态：进度、失败、取消，以及「缺 cloudflared 时入口不许消失」。"""

    def _features(self, **download):
        return ("PhonePanel.state.advanced = {channels:{cloudflare:{available:false,"
                "state:'missing',text:'组件包里没有校验过的 cloudflared'}},"
                "features:{phone_control:{ready:false, download:%s}}};"
                % json.dumps(download, ensure_ascii=False))

    def test_downloading_shows_progress_and_offers_cancel(self):
        # fe-phone 同步：进度文字与数字拆成左右两处（PH13），进度条改成 div 进度块（role=progressbar，墨色），
        # 取消按钮在标题行右侧；下载中没有状态 chip（PH06）
        snippet = self._features(state="downloading", downloaded=32 * 1048576,
                                 total_bytes=100 * 1048576) + '''
PhonePanel.paint();
out.push({text:$("#phone-prog-text").textContent,
          num:$("#phone-prog-num").textContent,
          progress:$("#phone-component-progress")["attr_aria-valuenow"],
          fill:$("#phone-prog-fill").style.width,
          loadingHidden:$("#phone-loading").hidden,
          missingHidden:$("#phone-missing").hidden,
          installHidden:$("#btn-phone-component-install").hidden,
          cancelHidden:$("#btn-phone-component-cancel").hidden,
          cancelText:$("#btn-phone-component-cancel").textContent,
          chipHidden:$("#phone-feature-status").hidden,
          startDisabled:$("#btn-phone-start").disabled});
'''
        row = run_phone_js(snippet, files=["views/phone.js"])[0]
        self.assertEqual(row["text"], "正在下载手机控制组件")
        self.assertEqual(row["num"], "32.0 / 100.0 MB")
        self.assertEqual(row["progress"], "32")
        self.assertEqual(row["fill"], "32%")
        self.assertFalse(row["loadingHidden"])
        self.assertTrue(row["missingHidden"])
        self.assertTrue(row["installHidden"], "下载中不能再点安装")
        self.assertFalse(row["cancelHidden"])
        self.assertEqual(row["cancelText"], "取消下载")
        self.assertTrue(row["chipHidden"])
        self.assertTrue(row["startDisabled"], "组件没落地就别让开通道")

    def test_failure_shows_reason_and_allows_retry(self):
        # fe-phone 同步：失败后回到没装态，标题行按钮叫「重新下载」、红条照原型拼句（PH11）；
        # 认不出的错误码回落后端原话。旧的「手机控制组件：安装失败」状态行按 PH03 删除
        snippet = self._features(state="failed", text="下载超时，请重试。") + '''
PhonePanel.paint();
out.push({error:$("#phone-component-error").textContent,
          errorHidden:$("#phone-component-error").hidden,
          installHidden:$("#btn-phone-component-install").hidden,
          installText:$("#btn-phone-component-install").textContent,
          importHidden:$("#phone-import-line").hidden});
PhonePanel.state.advanced.features.phone_control.download = {state:"failed", error_code:"network_error",
  text:"暂时连不上 GitHub，请检查网络后重试。"};
PhonePanel.paint();
out.push({error:$("#phone-component-error").textContent});
PhonePanel.state.advanced.features.phone_control.download = {state:"failed", error_code:"timeout",
  text:"下载超时，请重试。"};
PhonePanel.paint();
out.push({error:$("#phone-component-error").textContent});
'''
        row, network, timeout = run_phone_js(snippet, files=["views/phone.js"])
        self.assertEqual(row["error"], "下载超时，请重试。")
        self.assertFalse(row["errorHidden"])
        self.assertFalse(row["installHidden"], "失败后必须能重试")
        self.assertEqual(row["installText"], "重新下载")
        self.assertFalse(row["importHidden"], "下载失败后才露出导入链接（PH10）")
        self.assertEqual(network["error"], "下载没有完成：连不上发布页，可以重试。")
        self.assertEqual(timeout["error"], "下载没有完成：网络中断，可以重试。")

    def test_missing_cloudflared_keeps_the_install_entry(self):
        # fe-phone 同步：没装时的入口改成标题行的「下载并安装」（PH07），旧的「手机控制组件：未安装」状态行删除；
        # 组件 ready 但缺 cloudflared 是原型没画的一档，保留现状：入口「安装/更换组件包」不许消失
        snippet = self._features(state="missing") + '''
PhonePanel.paint();
out.push({installHidden:$("#btn-phone-component-install").hidden,
          installText:$("#btn-phone-component-install").textContent,
          featureHidden:$("#btn-phone-feature-install").hidden});
PhonePanel.state.advanced.features.phone_control = {ready:true, available:true, download:{state:"installed"}};
PhonePanel.paint();
out.push({featureHidden:$("#btn-phone-feature-install").hidden,
          featureText:$("#btn-phone-feature-install").textContent,
          cf:$("#phone-chan-cloudflare-status").textContent});
'''
        missing, ready = run_phone_js(snippet, files=["views/phone.js"])
        self.assertFalse(missing["installHidden"], "缺组件时安装入口不能消失")
        self.assertEqual(missing["installText"], "下载并安装")
        self.assertTrue(missing["featureHidden"])
        self.assertFalse(ready["featureHidden"], "ready 但缺 cloudflared 时补装入口不能消失")
        self.assertEqual(ready["featureText"], "安装/更换组件包")
        self.assertEqual(ready["cf"], "不可用")

    def test_cancelled_state_says_nothing_was_changed(self):
        # fe-phone 同步：取消后回到没装态，文案照原型改成「下载已取消，没有装任何东西。」（PH12）
        snippet = self._features(state="cancelled") + '''
PhonePanel.paint();
out.push({text:$("#phone-component-state").textContent,
          textHidden:$("#phone-component-state").hidden,
          installHidden:$("#btn-phone-component-install").hidden,
          installText:$("#btn-phone-component-install").textContent,
          cancelHidden:$("#btn-phone-component-cancel").hidden,
          importHidden:$("#phone-import-line").hidden});
'''
        row = run_phone_js(snippet, files=["views/phone.js"])[0]
        self.assertEqual(row["text"], "下载已取消，没有装任何东西。")
        self.assertFalse(row["textHidden"])
        self.assertFalse(row["installHidden"])
        self.assertEqual(row["installText"], "下载并安装")
        self.assertTrue(row["cancelHidden"])
        self.assertTrue(row["importHidden"], "取消不是失败，不露导入链接")

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
        # fe-phone 同步：Cloudflare 警告段与两处书签句按 PH21、PH22 删除；开启后只留一行通道说明（PH27）：
        # 临时地址用警告色说要重新扫码，固定地址才建议存书签。界面仍不许自己切通道
        snippet = self._features(state="installed") + '''
PhonePanel.state.advanced.features.phone_control.ready = true;
PhonePanel.state.running = true;
PhonePanel.state.active_channel = "cloudflare";
PhonePanel.paint();
out.push({cls:$("#phone-channel-note").className, note:$("#phone-channel-note").textContent,
          chosen:PhonePanel.channel});
PhonePanel.state.active_channel = "tailscale";
PhonePanel.paint();
out.push({cls:$("#phone-channel-note").className, note:$("#phone-channel-note").textContent});
'''
        cloudflare, tailscale = run_phone_js(snippet, files=["views/phone.js"])
        self.assertEqual(cloudflare["cls"], "ph-warn")
        self.assertEqual(cloudflare["note"], "这是临时地址：关闭访问或重启程序后就会变，手机要重新扫码配对。")
        self.assertEqual(cloudflare["chosen"], "", "界面不许自己切通道")
        self.assertEqual(tailscale["cls"], "ph-note")
        self.assertEqual(tailscale["note"], "地址固定，建议在手机上存成书签，下次直接打开。")


class PhoneAccessStateMachineTests(unittest.TestCase):
    """fe-phone：设置抽屉手机访问一组照原型 phView 的状态机（settings-gap 一、PH01–PH32）。"""

    PHONE = "PhonePanel.state.advanced = {features:{phone_control:%s}, channels:%s, credential:%s};"

    def _state(self, feature, channels=None, credential=None):
        return self.PHONE % (json.dumps(feature, ensure_ascii=False),
                             json.dumps(channels or {}, ensure_ascii=False),
                             json.dumps(credential or {}, ensure_ascii=False))

    def test_download_and_install_downloads_instead_of_opening_the_import_dialog(self):
        """PH07：没装时点「下载并安装」调 download_advanced_feature，不打开导入弹窗（决策 010 第 54 行）。"""
        values = run_phone_js(self._state({"ready": False, "available": False,
                                           "download": {"state": "available"}}) + """
const calls = [];
let opened = 0;
globalThis.__api = async (name, ...args) => { calls.push([name].concat(args)); return {ok:true}; };
PhonePanel.openComponents = () => { opened += 1; };
PhonePanel.wire();
for (let i = 0; i < 8; i += 1) await Promise.resolve();
PhonePanel.paint();
out.push({hidden:$("#btn-phone-component-install").hidden,
          text:$("#btn-phone-component-install").textContent,
          missingHidden:$("#phone-missing").hidden,
          detailHidden:$("#phone-access-detail").hidden,
          size:$("#phone-size-note").hidden});
calls.length = 0;
$("#btn-phone-component-install").click();
for (let i = 0; i < 8; i += 1) await Promise.resolve();
out.push({calls:calls.filter((c) => c[0] !== "phone_access_state" && c[0] !== "advanced_component_location"),
          opened:opened});
""", files=["views/phone.js"])
        shown, clicked = values
        self.assertEqual(shown, {"hidden": False, "text": "下载并安装", "missingHidden": False,
                                 "detailHidden": True, "size": False})
        self.assertEqual(clicked["calls"], [["download_advanced_feature", "phone_control"]])
        self.assertEqual(clicked["opened"], 0, "「下载并安装」不能再打开导入弹窗")

    def test_import_link_appears_only_after_a_download_failure(self):
        """PH10：导入链接只在下载失败后出现，点了打开现有导入弹窗。"""
        values = run_phone_js(self._state({"ready": False, "available": False,
                                           "download": {"state": "available"}}) + """
let opened = 0;
PhonePanel.openComponents = () => { opened += 1; };
PhonePanel.wire();
PhonePanel.paint();
out.push($("#phone-import-line").hidden);
PhonePanel.state.advanced.features.phone_control.download = {state:"downloading", downloaded:1, total_bytes:10};
PhonePanel.paint();
out.push($("#phone-import-line").hidden || $("#phone-missing").hidden);
PhonePanel.state.advanced.features.phone_control.download = {state:"failed", error_code:"network_error"};
PhonePanel.paint();
out.push([$("#phone-import-line").hidden, $("#phone-missing").hidden]);
$("#btn-phone-import").click();
out.push(opened);
""", files=["views/phone.js"])
        self.assertEqual(values, [True, True, [False, False], 1])

    def test_cancel_returns_to_not_installed_and_says_nothing_was_installed(self):
        """PH12：取消下载后回到没装态，按钮变回「下载并安装」，并说一句「下载已取消，没有装任何东西。」"""
        values = run_phone_js(self._state({"ready": False, "available": False,
                                           "download": {"state": "downloading", "downloaded": 5,
                                                        "total_bytes": 10}}) + """
const calls = [];
globalThis.__api = async (name, ...args) => {
  calls.push([name].concat(args));
  if (name === "phone_access_state") return {ok:true, running:false, advanced:{features:{phone_control:{
    ready:false, available:false, download:{state:"cancelled"}}}, channels:{}, credential:{}}};
  return {ok:true};
};
PhonePanel.wire();
PhonePanel.state.advanced.features.phone_control.download = {state:"downloading", downloaded:5, total_bytes:10};
PhonePanel.paint();
out.push({loading:!$("#phone-loading").hidden, cancel:!$("#btn-phone-component-cancel").hidden});
$("#btn-phone-component-cancel").click();
for (let i = 0; i < 10; i += 1) await Promise.resolve();
out.push({calls:calls.filter((c) => c[0] === "cancel_advanced_feature_download"),
          missing:!$("#phone-missing").hidden, loading:!$("#phone-loading").hidden,
          install:$("#btn-phone-component-install").hidden ? "" : $("#btn-phone-component-install").textContent,
          note:$("#phone-component-state").hidden ? "" : $("#phone-component-state").textContent});
""", files=["views/phone.js"])
        before, after = values
        self.assertEqual(before, {"loading": True, "cancel": True})
        self.assertEqual(after, {"calls": [["cancel_advanced_feature_download", "phone_control"]],
                                 "missing": True, "loading": False, "install": "下载并安装",
                                 "note": "下载已取消，没有装任何东西。"})

    def test_no_pairing_and_no_live_session_is_not_connected(self):
        """PH23（审核决定 A4）：paired_count 为 0 且没有活动会话就不是「已连接」；抽屉和顶栏同一条规则。"""
        values = run_phone_js("globalThis.S = {statusCard: null};\n" + self._state(
            {"ready": True, "available": True},
            {"tailscale": {"available": True, "state": "connected"}}) + """
const st = PhonePanel.state;
st.running = true; st.address = "http://pc.tail.ts.net:8765/";
st.pair_code_status = {code:"123456", expires_in:120, seq:3, reason:"paired"};
const read = () => ({chip:$("#phone-feature-status").textContent, ok:!$("#phone-ok").hidden,
  pair:!$("#phone-pair").hidden, add:!$("#btn-phone-add-pair").hidden,
  badge:$("#phone-badge-text").textContent});
st.paired_count = 0; st.live_session = false;
PhonePanel.paint(); out.push(read());
st.paired_count = 1;
PhonePanel.paint(); out.push(read());
st.paired_count = 0; st.live_session = true;
PhonePanel.paint(); out.push(read());
""", files=["views/status-cards.js", "views/phone.js"])
        waiting, paired, restored = values
        self.assertEqual(waiting, {"chip": "等手机连接", "ok": False, "pair": True, "add": False,
                                   "badge": "等手机连接"},
                         "reason=paired 只是换码原因，不能当成已连接")
        self.assertEqual(paired, {"chip": "手机已连接", "ok": True, "pair": False, "add": True,
                                  "badge": "手机已连接"})
        self.assertEqual(restored, paired, "设备 cookie 恢复的会话也算已连接")

    def test_add_another_phone_reopens_pairing_until_the_next_pairing(self):
        """PH29：「再配对一台手机」重新显示配对区；下一台配上（paired_count 变大）后自动收起。"""
        values = run_phone_js(self._state({"ready": True, "available": True}) + """
const st = PhonePanel.state;
st.running = true; st.paired_count = 1; st.pair_code_status = {code:"123456", expires_in:300};
PhonePanel.wire();
PhonePanel.paint();
out.push(!$("#phone-pair").hidden);
$("#btn-phone-add-pair").click();
out.push([!$("#phone-pair").hidden, !$("#btn-phone-add-pair").hidden]);
st.paired_count = 2;
PhonePanel.paint();
out.push([!$("#phone-pair").hidden, !$("#btn-phone-add-pair").hidden]);
""", files=["views/phone.js"])
        self.assertEqual(values, [False, [True, False], [False, True]])

    def test_save_tip_shows_only_without_a_saved_or_this_run_account(self):
        """PH24（审核决定 A3）：先看 saved 再看 staged；两样都没有才出现「出门前建议保存账号密码」。"""
        values = run_phone_js(self._state({"ready": True, "available": True}) + """
const st = PhonePanel.state;
st.running = true; st.paired_count = 1;
const tip = (cred) => { st.advanced.credential = cred; PhonePanel.paint(); return !$("#phone-cred-tip").hidden; };
out.push(tip({saved:false, staged:false}));
out.push(tip({saved:false, staged:true}));
out.push(tip({saved:true, staged:true}));
out.push(tip({saved:true, staged:false}));
st.paired_count = 0;
out.push(tip({saved:false, staged:false}));
""", files=["views/phone.js"])
        self.assertEqual(values, [True, False, False, False, False])

    def test_save_tip_link_opens_the_login_group_with_the_form(self):
        """PH24「去保存」：打开设置的登录组并展开账号密码表单。"""
        values = run_phone_js(self._state({"ready": True, "available": True}) + """
const opened = [];
globalThis.openSettings = (section) => { opened.push(section); };
$("#credential-editor").hidden = true;
PhonePanel.wire();
$("#btn-phone-cred-go").click();
out.push([opened, $("#credential-editor").hidden]);
""", files=["views/phone.js"])
        self.assertEqual(values, [[["login"], False]])

    def test_location_box_uses_the_desktop_only_interface_and_hides_without_a_path(self):
        """PH09：「会装到 / 装在」只走电脑端 B3 接口；取不到位置就不显示，不编路径。"""
        values = run_phone_js(self._state({"ready": False, "available": False}) + """
const calls = [];
let loc = {ok:true, path:"<数据目录>/advanced/phone_control", short:"…advanced/phone_control", exists:false};
globalThis.__api = async (name, ...args) => {
  calls.push([name].concat(args));
  if (name === "advanced_component_location") return loc;
  return {ok:true};
};
await PhonePanel.refresh();
out.push({before:!$("#phone-loc-before").hidden, after:!$("#phone-loc-after").hidden,
          text:$("#phone-loc-before-path").textContent, title:$("#phone-loc-before").title});
PhonePanel.state.advanced.features.phone_control = {ready:true, available:true};
PhonePanel.paint();
out.push({before:!$("#phone-loc-before").hidden, after:!$("#phone-loc-after").hidden,
          text:$("#phone-loc-after-path").textContent});
PhonePanel.wire();
$("#btn-phone-open-loc").click();
for (let i = 0; i < 8; i += 1) await Promise.resolve();
out.push(calls.filter((c) => c[0] === "open_advanced_component_dir"));
PhonePanel.location = null;
loc = {ok:false, reason:"bad_feature"};
await PhonePanel.refresh();
out.push({before:!$("#phone-loc-before").hidden, after:!$("#phone-loc-after").hidden});
""", files=["views/phone.js"])
        missing, ready, opened, unknown = values
        self.assertEqual(missing, {"before": True, "after": False, "text": "…advanced/phone_control",
                                   "title": "<数据目录>/advanced/phone_control"})
        self.assertEqual(ready, {"before": False, "after": True, "text": "…advanced/phone_control"})
        self.assertEqual(opened, [["open_advanced_component_dir", "phone_control"]])
        self.assertEqual(unknown, {"before": False, "after": False})

    def test_stop_asks_in_a_red_block_and_hides_the_stop_row(self):
        """PH28：关闭前红底确认块，确认时收起「关闭手机访问」那一行；确认按钮是红色 btn-stop。"""
        values = run_phone_js(self._state({"ready": True, "available": True}) + """
PhonePanel.state.running = true;
PhonePanel.wire();
PhonePanel.paint();
out.push([!$("#phone-stop-confirm").hidden, !$("#phone-stop-row").hidden]);
$("#btn-phone-stop").click();
out.push([!$("#phone-stop-confirm").hidden, !$("#phone-stop-row").hidden]);
$("#btn-phone-stop-cancel").click();
out.push([!$("#phone-stop-confirm").hidden, !$("#phone-stop-row").hidden]);
""", files=["views/phone.js"])
        self.assertEqual(values, [[False, True], [True, False], [False, True]])
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="btn btn-stop" id="btn-phone-stop-confirm"', html)
        self.assertIn("关闭后手机立刻失去权限，下次连接要重新扫码配对。", html)

    def test_off_state_reports_tunnel_exit_installed_and_closed_inline(self):
        """PH31、PH32、PH30：隧道断开红条、看着装好的那一句、关闭后的那一句都在本块就地显示。"""
        values = run_phone_js(self._state({"ready": False, "available": False,
                                           "download": {"state": "verifying"}}) + """
const st = PhonePanel.state;
PhonePanel.paint();
out.push({chip:$("#phone-feature-status").hidden, cancel:$("#btn-phone-component-cancel").textContent,
          cancelDisabled:$("#btn-phone-component-cancel").disabled,
          text:$("#phone-prog-text").textContent});
st.advanced.features.phone_control = {ready:true, available:true, download:{state:"installed"}};
PhonePanel.paint();
out.push({chip:$("#phone-feature-status").textContent, note:$("#phone-off-note").textContent});
st.advanced.channels = {cloudflare:{available:true, state:"exited", error:"tunnel_exited"}};
PhonePanel.paint();
out.push($("#phone-off-error").textContent);
globalThis.__api = async (name) => name === "phone_access_state"
  ? {ok:true, running:false} : {ok:true};
st.running = true;
await PhonePanel.toggleStop();
out.push($("#phone-off-note").textContent);
""", files=["views/phone.js"])
        verifying, installed, gone, closed = values
        self.assertEqual(verifying, {"chip": True, "cancel": "校验中…", "cancelDisabled": True,
                                     "text": "下载完成，正在校验组件…"})
        self.assertEqual(installed, {"chip": "未开启", "note": "手机控制组件已安装，选一条通道就能开启。"})
        self.assertEqual(gone, "Cloudflare 隧道断了，旧地址和二维码已失效。重新开启后要重新扫码配对。")
        self.assertEqual(closed, "手机访问已关闭，手机需要重新配对才能再进。")

    def test_installed_but_disabled_enables_through_the_backend(self):
        """原型没画、保留现状的一档：组件在本机但启用位没开时，「启用手机控制」走 B2，不打开导入弹窗。"""
        values = run_phone_js(self._state({"ready": False, "available": True, "status": "ready"}) + """
const calls = [];
let opened = 0;
globalThis.__api = async (name, ...args) => { calls.push([name].concat(args)); return {ok:true}; };
PhonePanel.openComponents = () => { opened += 1; };
PhonePanel.wire();
PhonePanel.paint();
$("#btn-phone-feature-install").click();
for (let i = 0; i < 8; i += 1) await Promise.resolve();
out.push([calls.filter((c) => c[0] === "enable_advanced_feature"), opened]);
""", files=["views/phone.js"])
        self.assertEqual(values, [[[["enable_advanced_feature", "phone_control"]], 0]])

    def test_static_copy_follows_the_prototype(self):
        """PH04、PH08、IM02：多出的二级行删掉；体积只做「现在读不到」形态；导入弹窗不再说本程序不联网下载。"""
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        view = (LOCAL / "ui" / "views" / "phone.js").read_text(encoding="utf-8")
        self.assertIn("可选组件，大小以发布页为准（现在读不到）。下载后自动校验并启用，不会自动升级。", html)
        self.assertNotIn("约 18.4 MB", html + view, "打开设置不联网，不写死体积（审核决定 4）")
        self.assertNotIn("只提供 Tailscale 与 Cloudflare 两种远程通道", html)
        self.assertNotIn("安装手机控制", html)
        self.assertEqual(html.count("本程序不联网下载组件"), 0)
        self.assertEqual(view.count("下载已取消，没有装任何东西。"), 1)
        self.assertIn("一直下载不了的话，可以到发布页手动下载组件包，再", html)


class OcrAndLoginRecoveryTests(unittest.TestCase):
    """fe-ocr-login：验证码识别三态与启用、登录恢复结构与只用这一次、本机数据一句、导入弹窗
    （settings-gap 二 OC、三 CR、四 DT、五 IM）。验证码识别一节由 settings.js 绘制，所以两个脚本一起加载。"""

    FILES = ["views/phone.js", "views/settings.js"]

    def _run(self, snippet):
        return run_phone_js(snippet, files=self.FILES)

    def test_enable_calls_the_enable_interface_and_never_opens_the_import_dialog(self):
        """OC08、冲突 6：已装好但没启用时，标题行是「启用」，点它调 enable_advanced_feature("relogin_ocr")，不打开导入弹窗。"""
        values = self._run("""
const calls = [];
let opened = 0;
globalThis.__api = async (name, ...args) => { calls.push([name].concat(args)); return {ok:true}; };
PhonePanel.openComponents = () => { opened += 1; };
PhonePanel.wire();
wireSettings();
for (let i = 0; i < 8; i += 1) await Promise.resolve();
PhonePanel.state.advanced = {features:{relogin_ocr:{available:true, enabled:false, ready:false,
  status:"ready", package_version:"1.2.0", download:{state:"available"}}}, credential:{}};
PhonePanel.paint();
out.push({enable: $("#btn-ocr-enable").hidden,
          download: $("#btn-ocr-download").hidden, chip: $("#ocr-title-chip").hidden,
          doneChip: $("#ocr-feature-status").hidden,
          lead: $("#ocr-download-state").textContent,
          offNote: $("#ocr-off-note").hidden,
          missing: $("#ocr-missing").hidden, importLine: $("#ocr-import-line").hidden});
calls.length = 0;
$("#btn-ocr-enable").click();
for (let i = 0; i < 12; i += 1) await Promise.resolve();
out.push({calls: calls.filter((c) => c[0] === "enable_advanced_feature"), opened: opened,
          note: $("#ocr-note").textContent});
""")
        shown, clicked = values[0], values[-1]
        # 按钮名、chip 字样、说明句是 index.html 里的静态文字，由 test_static_copy_follows_the_prototype 核对
        self.assertFalse(shown["enable"], "已装好没启用：标题行右侧是「启用」")
        self.assertTrue(shown["download"], "已装好就不再露出「下载并安装」")
        self.assertFalse(shown["chip"], "已装没启用：标题旁挂中性 chip「未启用」")
        self.assertTrue(shown["doneChip"])
        self.assertEqual(shown["lead"], "已装好（版本 1.2.0），还没启用。启用后，登录失效时电脑会自己认验证码；"
                                        "配合“登录恢复”里的账号密码，就能无人值守自动登录。")
        self.assertFalse(shown["offNote"])
        self.assertTrue(shown["missing"])
        self.assertTrue(shown["importLine"])
        self.assertEqual(clicked["calls"], [["enable_advanced_feature", "relogin_ocr"]])
        self.assertEqual(clicked["opened"], 0, "「启用」不能再打开导入弹窗")
        self.assertEqual(clicked["note"], "验证码识别已启用。")

    def test_enable_failure_is_said_in_place(self):
        """OC08：启用没成功，后端的原话就地显示在本节红条里，不走抽屉底部。"""
        values = self._run("""
globalThis.__api = async (name) => name === "enable_advanced_feature"
  ? {ok:false, reason:"not_available", error:"not_available", text:"这个组件还没装好，不能启用。"} : {ok:true};
PhonePanel.wire();
wireSettings();
PhonePanel.state.advanced = {features:{relogin_ocr:{available:true, ready:false, status:"ready"}}, credential:{}};
PhonePanel.paint();
$("#btn-ocr-enable").click();
for (let i = 0; i < 12; i += 1) await Promise.resolve();
out.push([$("#ocr-download-error").hidden, $("#ocr-download-error").textContent]);
""")
        self.assertEqual(values[-1], [False, "这个组件还没装好，不能启用。"])

    def test_missing_is_one_click_and_the_import_link_only_follows_a_failure(self):
        """OC04、OC10–OC13：没装时「下载并安装」，失败后「重新下载」+ 红条 + 导入链接；取消后回到没装态。"""
        values = self._run("""
const opened = [];
globalThis.__api = async () => ({ok:true});
PhonePanel.openComponents = (key) => { opened.push(key); };
PhonePanel.wire();
wireSettings();
const set = (download) => {
  PhonePanel.state.advanced = {features:{relogin_ocr:{available:false, ready:false, status:"missing", download:download}}, credential:{}};
  PhonePanel.paint();
};
set({state:"available"});
out.push({btn: [$("#btn-ocr-download").hidden, $("#btn-ocr-download").textContent],
          importLine: $("#ocr-import-line").hidden, size: $("#ocr-missing").hidden,
          lead: $("#ocr-download-state").textContent, err: $("#ocr-download-error").hidden});
set({state:"downloading", downloaded:9961472, total_bytes:33128448});
out.push({cancel: [$("#btn-ocr-cancel").hidden, $("#btn-ocr-cancel").textContent],
          loading: $("#ocr-loading").hidden, num: $("#ocr-prog-num").textContent,
          text: $("#ocr-prog-text").textContent, now: $("#ocr-component-progress").getAttribute("aria-valuenow"),
          fill: $("#ocr-prog-fill").style.width, missing: $("#ocr-missing").hidden});
set({state:"verifying"});
out.push({cancel: [$("#btn-ocr-cancel").textContent, $("#btn-ocr-cancel").disabled],
          text: $("#ocr-prog-text").textContent});
set({state:"failed", error_code:"network_error", text:"后端原话"});
out.push({btn: $("#btn-ocr-download").textContent, err: $("#ocr-download-error").textContent,
          importLine: $("#ocr-import-line").hidden});
$("#btn-ocr-import").click();
set({state:"cancelled"});
out.push({note: $("#ocr-note").textContent, btn: [$("#btn-ocr-download").hidden, $("#btn-ocr-download").textContent],
          err: $("#ocr-download-error").hidden});
out.push({opened: opened});
""")
        idle, loading, verifying, failed, cancelled, link = values
        self.assertEqual(idle["btn"], [False, "下载并安装"])
        self.assertTrue(idle["importLine"], "没失败过就不露导入链接")
        self.assertFalse(idle["size"], "没装时显示体积说明和「会装到」那一块")
        self.assertEqual(idle["lead"], "登录失效时，电脑能自己认验证码，配合“登录恢复”里的账号密码就能全自动登录。"
                                       "没装或认不出来时，由你在手机上手动输入。")
        self.assertTrue(idle["err"])
        self.assertEqual(loading["cancel"], [False, "取消下载"])
        self.assertFalse(loading["loading"])
        self.assertTrue(loading["missing"])
        self.assertEqual(loading["num"], "9.5 / 31.6 MB")
        self.assertEqual(loading["text"], "正在下载验证码识别组件")
        self.assertEqual((loading["now"], loading["fill"]), ("30", "30%"))
        self.assertEqual(verifying, {"cancel": ["校验中…", True], "text": "下载完成，正在校验组件…"})
        self.assertEqual(failed["btn"], "重新下载")
        self.assertEqual(failed["err"], "下载没有完成：连不上发布页，可以重试。")
        self.assertFalse(failed["importLine"])
        self.assertEqual(cancelled["note"], "下载已取消，没有装任何东西。")
        self.assertEqual(cancelled["btn"], [False, "下载并安装"])
        self.assertTrue(cancelled["err"])
        self.assertEqual(link["opened"], ["relogin_ocr"], "导入链接打开的是验证码识别的导入")

    def test_ocr_feedback_is_in_place_and_location_uses_the_desktop_interface(self):
        """OC06、OC07、OC15：位置只走 B3；装好后说一句；下载没开始的原话就地显示，不走抽屉底部。"""
        values = self._run("""
const calls = [];
globalThis.__api = async (name, ...args) => {
  calls.push([name].concat(args));
  if (name === "advanced_component_location") return {ok:true, path:"<数据目录>/advanced/relogin_ocr", short:"…/advanced/relogin_ocr", exists:false};
  if (name === "download_advanced_feature") return {ok:false, text:"现在连不上，稍后再试。"};
  return {ok:true};
};
PhonePanel.wire();
wireSettings();
const set = (feature) => {
  PhonePanel.state.advanced = {features:{relogin_ocr:feature}, credential:{}};
  PhonePanel.paint();
};
set({available:false, ready:false, status:"missing", download:{state:"available"}});
await ocrLoadLocation();
paintOcrDownload();
out.push({before: [$("#ocr-loc-before").hidden, $("#ocr-loc-before-path").textContent], after: $("#ocr-loc-after").hidden});
await PhonePanel.downloadComponent("relogin_ocr");
out.push({err: $("#ocr-download-error").textContent});
set({available:false, ready:false, status:"missing", download:{state:"downloading", downloaded:1, total_bytes:10}});
set({available:true, ready:true, status:"ready", package_version:"1.2.0", download:{state:"installed"}});
out.push({chip: [$("#ocr-feature-status").hidden, $("#ocr-feature-status").textContent],
          lead: $("#ocr-download-state").textContent, note: $("#ocr-note").textContent,
          after: [$("#ocr-loc-after").hidden, $("#ocr-loc-after-path").textContent], before: $("#ocr-loc-before").hidden});
calls.length = 0;
$("#btn-ocr-open-loc").click();
for (let i = 0; i < 4; i += 1) await Promise.resolve();
out.push({opened: calls.filter((c) => c[0] === "open_advanced_component_dir")});
""")
        located = values[0]
        failed = [v for v in values if "err" in v][-1]
        installed = [v for v in values if "chip" in v][-1]
        opened = values[-1]
        self.assertEqual(located["before"], [False, "…/advanced/relogin_ocr"])
        self.assertTrue(located["after"])
        self.assertEqual(failed["err"], "现在连不上，稍后再试。")
        self.assertEqual(installed["chip"], [False, "已启用"])
        self.assertEqual(installed["lead"], "版本 1.2.0。电脑会自己认验证码，连续认错 3 次再转给手机手动输入。")
        self.assertEqual(installed["note"], "验证码识别组件已安装并启用。")
        self.assertEqual(installed["after"], [False, "…/advanced/relogin_ocr"])
        self.assertTrue(installed["before"])
        self.assertEqual(opened["opened"], [["open_advanced_component_dir", "relogin_ocr"]])
        helped = [v for v in values if isinstance(v, dict) and "tone" in v]
        self.assertEqual(helped, [], "验证码识别的反馈不再走抽屉底部的 helpStatus")

    def test_this_run_account_sentence_shows_only_without_a_saved_account(self):
        """CR06、审核决定 A3：先看 saved 再看 staged；「关闭工具后自动清除」那句只在 !saved && staged 时出现，账号用 staged_hint。"""
        values = self._run("""
const show = (cred) => {
  PhonePanel.state.advanced = {features:{relogin_ocr:{available:false, ready:false, status:"missing"}}, credential:cred};
  PhonePanel.paint();
  return {line: $("#relogin-credential-status").textContent, hidden: $("#relogin-credential-status").hidden,
          slot: $("#btn-credentials-manage").textContent, clearRow: $("#relogin-clear-row").hidden};
};
out.push(show({available:true, store_available:true, saved:false, staged:true, staged_hint:"st****01"}));
out.push(show({available:true, store_available:true, saved:true, username:"20230001", staged:true, staged_hint:"20****01"}));
out.push(show({available:true, store_available:true, saved:false, staged:false, staged_hint:""}));
out.push(show({available:true, store_available:true, saved:false, staged:true, staged_hint:""}));
""")
        once, saved, none, no_hint = values
        self.assertEqual(once["line"], "这次运行可以用账号 st****01 重新登录，关闭工具后自动清除。")
        self.assertFalse(once["hidden"])
        self.assertEqual(once["slot"], "更换")
        self.assertTrue(once["clearRow"], "「清除已保存」只有保存过的账号才有，只用这一次没有")
        self.assertEqual(saved["line"], "已保存账号 20****01。")
        self.assertNotIn("关闭工具后自动清除", saved["line"], "已保存时即使暂存区也有，也不说「这次运行」")
        self.assertFalse(saved["clearRow"])
        self.assertTrue(none["hidden"], "没有账号时不显示这一行")
        self.assertEqual(none["slot"], "填写账号密码")
        self.assertTrue(no_hint["hidden"], "拿不到打码账号就不显示，不自己编")

    def test_auto_login_line_counts_this_run_account_when_ocr_is_enabled(self):
        """CR07、CR20（冲突 5）：只用这一次的账号加识别已启用，结论行写「已启用」；识别没启用 / 没装各有各的说法。"""
        values = self._run("""
const line = (cred, ocr) => {
  PhonePanel.state.advanced = {features:{relogin_ocr: ocr}, credential:cred};
  PhonePanel.paint();
  return [$("#relogin-auto-path").textContent, $("#relogin-auto-path").className];
};
const once = {available:true, store_available:true, saved:false, staged:true, staged_hint:"st****01"};
out.push(line(once, {available:true, ready:true, status:"ready"}));
out.push(line(once, {available:true, ready:false, status:"ready"}));
out.push(line(once, {available:false, ready:false, status:"missing"}));
out.push(line({available:true, store_available:true, saved:false, staged:false}, {available:true, ready:true, status:"ready"}));
out.push(line({available:true, store_available:true, saved:false, staged:false, automatic:{state:"paused"}}, {available:true, ready:true, status:"ready"}));
out.push(line({available:true, store_available:true, saved:true, username:"20230001", paused:true}, {available:true, ready:true, status:"ready"}));
""")
        enabled, installed, missing, none, rejected, saved_bad = values
        self.assertEqual(enabled, ["失效后自动登录：已启用。登录失效时电脑自己重新登录，报名计划等开放或提交时也一样，不用你动手。", "up-ok"])
        self.assertEqual(installed, ["失效后自动登录：验证码识别本机已装，还没启用（在上面“高级功能”里点“启用”）。"
                                     "现在登录失效时要你输验证码；报名计划开放前 100 秒内失效的场次会直接结束。", "up-warn"])
        self.assertEqual(missing, ["失效后自动登录：还缺验证码识别组件（在上面的“高级功能”里一键安装）。"
                                   "现在登录失效时要你输验证码；报名计划开放前 100 秒内失效的场次会直接结束。", "up-warn"])
        self.assertEqual(none[0], "失效后自动登录：未启用，还没有账号密码。登录失效后要手动重新登录；"
                                  "报名计划开放前 100 秒内失效的场次会直接结束。")
        self.assertEqual(rejected, none, "这次那份被学校拒了：表里没有这一档，按「还没有账号密码」显示")
        self.assertIn("已启用", saved_bad[0], "保存的密码被拒走单独的红字，结论行不再写括号（CR07）")
        self.assertNotIn("（", saved_bad[0].split("已启用")[0])

    def test_bad_saved_password_has_its_own_red_line(self):
        """CR18：保存的密码学校不认，是单独一条红字，表单展开时不显示。"""
        values = self._run("""
PhonePanel.state.advanced = {features:{}, credential:{available:true, store_available:true, saved:true,
  username:"20230001", paused:true}};
PhonePanel.paint();
out.push($("#relogin-bad").hidden);
PhonePanel.openCredForm();
out.push($("#relogin-bad").hidden);
PhonePanel.state.advanced.credential.paused = false;
PhonePanel.cancelCredForm();
out.push($("#relogin-bad").hidden);
""")
        # 红字本身是 index.html 里的静态文字（test_static_copy_follows_the_prototype 逐字核对），这里只看显隐
        self.assertEqual(values, [False, True, True])

    def test_credential_form_follows_the_prototype(self):
        """CR05、CR11–CR15、CR19：展开表单、勾选「只在这次运行中用」改按钮名并改走内存接口、成功后收起并就地说一句、取消清空。"""
        values = self._run("""
const calls = [];
globalThis.__api = async (name, ...args) => { calls.push([name].concat(args.map((x, i) => (i === 1 ? "***" : x)))); return {ok:true}; };
PhonePanel.wire();
for (let i = 0; i < 8; i += 1) await Promise.resolve();
PhonePanel.state.advanced = {features:{}, credential:{available:true, store_available:true, saved:false}};
PhonePanel.paint();
out.push({formHidden: $("#credential-editor").hidden, slotHidden: $("#btn-credentials-manage").hidden});
$("#btn-credentials-manage").click();
out.push({formHidden: $("#credential-editor").hidden, slotHidden: $("#btn-credentials-manage").hidden,
          save: [$("#btn-credentials-save").textContent, $("#btn-credentials-save").disabled]});
$("#credential-user").value = "20230001";
$("#credential-pass").value = "fictional-secret";
PhonePanel.paintCredForm();
out.push({save: [$("#btn-credentials-save").textContent, $("#btn-credentials-save").disabled]});
$("#credential-once").checked = true;
PhonePanel.paintCredForm();
out.push({save: $("#btn-credentials-save").textContent});
calls.length = 0;
await PhonePanel.saveCredentials();
out.push({calls: calls.filter((c) => c[0] === "prepare_phone_relogin" || c[0] === "save_relogin_credentials"),
          formHidden: $("#credential-editor").hidden, note: $("#credential-note").textContent,
          pass: $("#credential-pass").value});
$("#btn-credentials-manage").click();
$("#credential-user").value = "x";
$("#btn-credentials-cancel").click();
out.push({formHidden: $("#credential-editor").hidden, user: $("#credential-user").value});
$("#btn-credentials-manage").click();
$("#credential-user").value = "20230001";
$("#credential-pass").value = "fictional-secret";
$("#credential-once").checked = false;
calls.length = 0;
await PhonePanel.saveCredentials();
out.push({calls: calls.filter((c) => c[0] === "prepare_phone_relogin" || c[0] === "save_relogin_credentials"),
          note: $("#credential-note").textContent});
""")
        closed, opened, typed, once_label, once_saved, cancelled, saved = values
        self.assertEqual(closed, {"formHidden": True, "slotHidden": False})
        self.assertEqual(opened, {"formHidden": False, "slotHidden": True, "save": ["保存到本机", True]})
        self.assertEqual(typed["save"], ["保存到本机", False])
        self.assertEqual(once_label["save"], "只用这一次")
        self.assertEqual(once_saved["calls"], [["prepare_phone_relogin", "20230001", "***"]],
                         "勾了只在这次运行中用：只进内存，不落盘")
        self.assertTrue(once_saved["formHidden"], "保存成功后收起表单（CR11）")
        self.assertEqual(once_saved["note"], "已准备好，只在这次运行中使用。")
        self.assertEqual(once_saved["pass"], "", "密码框保存后必须清空")
        self.assertEqual(cancelled, {"formHidden": True, "user": ""})
        self.assertEqual(saved["calls"], [["save_relogin_credentials", "20230001", "***"]])
        self.assertEqual(saved["note"], "已加密保存到本机。")

    def test_clear_flow_uses_the_prototype_wording(self):
        """CR16、CR17、CR19：「清除已保存」→ 红底确认块 → 清除后就地说一句；确认展开时标题行按钮和清除行都收起。"""
        values = self._run("""
const calls = [];
globalThis.__api = async (name) => { calls.push(name); return {ok:true}; };
PhonePanel.wire();
for (let i = 0; i < 8; i += 1) await Promise.resolve();
PhonePanel.state.advanced = {features:{}, credential:{available:true, store_available:true, saved:true, username:"20230001"}};
PhonePanel.paint();
out.push({row: $("#relogin-clear-row").hidden, confirm: $("#relogin-clear-confirm").hidden});
$("#btn-credentials-clear").click();
out.push({row: $("#relogin-clear-row").hidden, confirm: $("#relogin-clear-confirm").hidden,
          slot: $("#btn-credentials-manage").hidden});
$("#btn-relogin-clear-confirm").click();
for (let i = 0; i < 12; i += 1) await Promise.resolve();
out.push({calls: calls.filter((c) => c === "clear_relogin_credentials"), note: $("#credential-note").textContent});
""")
        self.assertEqual(values[0], {"row": False, "confirm": True})
        self.assertEqual(values[1], {"row": True, "confirm": False, "slot": True})
        self.assertEqual(values[2], {"calls": ["clear_relogin_credentials"], "note": "已清除本机保存的账号密码。"})

    def test_static_copy_follows_the_prototype(self):
        """CR01、CR02、CR04、CR13、CR17、DT01、DT04、IM01、IM02：静态文案逐字照原型。"""
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        view = (LOCAL / "ui" / "views" / "phone.js").read_text(encoding="utf-8")
        for text in ("登录信息、设置、运行记录和下载的组件，都只保存在这台电脑。",
                     "登录失效时用账号密码自动登录。账号密码只用 Windows 当前用户加密保存在本机，手机页看不到。",
                     "登录时，工具会替你勾选学校登录页上的“我已阅读并同意《隐私协议》”。",
                     "只在这次运行中用，不保存到本机",
                     "清除后，电脑不会再自动登录，手机上重新登录也要重新输入账号密码。",
                     "保存的密码学校不认，自动登录已暂停。点“更换”输入新密码。",
                     "可选组件，大小以发布页为准（现在读不到）。下载后自动校验并启用，不会自动升级。",
                     "这一项关系到自动登录，所以装好了也不会自己打开。",
                     "一直下载不了的话，可以到发布页手动下载组件包，再",
                     'id="btn-ocr-enable" type="button" hidden>启用</button>',
                     'id="ocr-title-chip" hidden>未启用</span>',
                     "导入验证码识别组件", "选择文件…"):
            self.assertIn(text, html, "缺少原型文案：%s" % text)
        self.assertNotIn("登录信息、设置和运行记录都只保存在这台电脑。", html, "旧的本机数据说明句要换掉（DT01）")
        self.assertNotIn("保存的账号与失效后自动登录", html, "CR01：登录组标题后面没有副标题")
        self.assertNotIn("电脑续登录", html, "CR02：可见标题改成「登录恢复」")
        self.assertNotIn('id="relogin-overall-status"', html, "CR03：总状态 chip 删除")
        self.assertNotIn('id="relogin-ocr-status"', html, "CR08：验证码识别状态行并入结论行")
        self.assertNotIn("清除后，电脑不会再自动恢复登录", html)
        self.assertEqual(view.count("下载已取消，没有装任何东西。"), 1)
        # DT04：抽屉里按钮名、组件名用中文双引号，不用「」
        self.assertNotIn("点「重新检测」", view)
        self.assertNotIn("重新安装「手机控制」", view)

    def test_import_dialog_opens_per_component_and_checks_on_pick(self):
        """IM01：弹窗一次导入一个组件，标题随组件变；选完文件立刻自检，通过才能点「安装这份」。.exe 不进后端。"""
        values = self._run("""
const calls = [];
const paths = ["C:/downloads/relogin_ocr-1.2.0.zip", "C:/downloads/TailscaleSetup-1.76.exe"];
let nth = 0;
globalThis.__api = async (name, ...args) => {
  calls.push([name].concat(args));
  if (name === "pick_advanced_component") return {ok:true, path: paths[nth++]};
  if (name === "inspect_advanced_component") return {ok:true, kind:"component", feature:"relogin_ocr", version:"1.2.0", text:"已识别为「验证码识别」组件包。"};
  return {ok:true};
};
PhonePanel.openComponents("relogin_ocr");
out.push({title: $("#dlg-components-title").textContent, phoneRow: $("#comp-phone").hidden, ocrRow: $("#comp-ocr").hidden,
          phoneInstall: $("#btn-comp-phone-install").hidden, ocrInstall: [$("#btn-comp-ocr-install").hidden, $("#btn-comp-ocr-install").disabled]});
await PhonePanel.pickComponent("relogin_ocr");
out.push({note: $("#comp-ocr-note").textContent, tone: $("#comp-ocr-note").dataset.tone,
          install: $("#btn-comp-ocr-install").disabled, path: $("#comp-ocr-path").value});
calls.length = 0;
await PhonePanel.pickComponent("relogin_ocr");
out.push({note: $("#comp-ocr-note").textContent, tone: $("#comp-ocr-note").dataset.tone,
          install: $("#btn-comp-ocr-install").disabled,
          inspected: calls.filter((c) => c[0] === "inspect_advanced_component").length});
PhonePanel.openComponents("phone_control");
out.push({title: $("#dlg-components-title").textContent, phoneRow: $("#comp-phone").hidden, ocrRow: $("#comp-ocr").hidden});
""")
        opened, passed, exe, phone = values
        self.assertEqual(opened["title"], "导入验证码识别组件")
        self.assertTrue(opened["phoneRow"])
        self.assertFalse(opened["ocrRow"])
        self.assertTrue(opened["phoneInstall"])
        self.assertEqual(opened["ocrInstall"], [False, True])
        self.assertEqual(passed["note"], "已识别为「验证码识别」组件包，版本 1.2.0。")
        self.assertEqual(passed["tone"], "ok")
        self.assertFalse(passed["install"], "自检通过才能安装")
        self.assertEqual(passed["path"], "C:/downloads/relogin_ocr-1.2.0.zip")
        self.assertEqual(exe["note"], "这是 Tailscale 的安装程序，不是组件包。Tailscale 要用官方安装包装好并登录，不用在这里导入。")
        self.assertEqual(exe["tone"], "warn")
        self.assertTrue(exe["install"], "自检没过就不能安装")
        self.assertEqual(exe["inspected"], 0, ".exe 不再走后端自检（裸 cloudflared 入口已去掉）")
        self.assertEqual(phone, {"title": "导入手机控制组件", "phoneRow": False, "ocrRow": True})

    def test_import_check_copy_follows_the_actual_reply_fields(self):
        """IM03：文案照原型，但只说回包里真有的东西——通过时有 version，失败时没有包自己的版本，也没有核过哈希。"""
        values = self._run("""
$("#help-version").textContent = "1.2.0";
const c = (key, path, info) => importCheckText(key, path, info);
out.push(c("relogin_ocr", "a/relogin_ocr-1.2.0.zip", {ok:true, kind:"component", feature:"relogin_ocr", version:"1.2.0", text:"已识别为「验证码识别」组件包。"}));
out.push(c("relogin_ocr", "a/phone_control-1.2.0.zip", {ok:false, kind:"wrong_feature", feature:"phone_control", text:"这是「手机控制」的组件包，不是这里要装的「验证码识别」。"}));
out.push(c("relogin_ocr", "a/x.zip", {ok:false, kind:"not_component", feature:"", text:"这个 ZIP 里没有组件清单（manifest.json），不是本程序的组件包。"}));
out.push(c("relogin_ocr", "a/relogin_ocr-1.1.0.zip", {ok:false, kind:"incompatible_manifest", feature:"relogin_ocr", text:"组件清单不合法（incompatible_manifest），请用与当前版本配套的组件包。"}));
$("#help-version").textContent = "—";
out.push(c("relogin_ocr", "a/relogin_ocr-1.1.0.zip", {ok:false, kind:"incompatible_manifest", feature:"relogin_ocr", text:"后端原话"}));
out.push(c("relogin_ocr", "a/其他.exe", {ok:false, kind:"not_zip"}));
out.push(c("relogin_ocr", "a/x.zip", null));
""")
        self.assertEqual(values[0], "已识别为「验证码识别」组件包，版本 1.2.0。")
        self.assertEqual(values[1], "这是「手机控制」的组件包，不是这里要装的「验证码识别」。")
        self.assertEqual(values[2], "这个 ZIP 里没有组件清单，不是本程序的组件包。")
        self.assertEqual(values[3], "这个组件包和现在的 1.2.0 不配套。到发布页下载 1.2.0 的组件包。")
        self.assertEqual(values[4], "后端原话", "读不到程序版本就不编，照后端原话说")
        self.assertEqual(values[5], "这里需要组件包 ZIP，不是可执行文件。")
        self.assertEqual(values[6], "自检没有返回结论。")

    def test_import_success_closes_the_dialog_and_says_so_in_the_ocr_section(self):
        """OC15、IM01：导入装好后关掉弹窗，在验证码识别那一节说「已导入并启用」。"""
        values = self._run("""
globalThis.__api = async (name) => {
  if (name === "pick_advanced_component") return {ok:true, path:"C:/d/relogin_ocr-1.2.0.zip"};
  if (name === "inspect_advanced_component") return {ok:true, version:"1.2.0"};
  return {ok:true};
};
wireSettings();
PhonePanel.openComponents("relogin_ocr");
await PhonePanel.pickComponent("relogin_ocr");
PhonePanel.state.advanced = {features:{relogin_ocr:{available:true, ready:true, status:"ready", package_version:"1.2.0"}}, credential:{}};
await PhonePanel.installComponent("relogin_ocr");
out.push({note: $("#ocr-note").textContent, noteHidden: $("#ocr-note").hidden});
""")
        self.assertEqual(values[-1], {"note": "验证码识别组件已导入并启用。", "noteHidden": False})


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
        report = Path(tempfile.gettempdir()) / "night-run-B-20261030" / "evidence" / "phone-ui-layout-375-430.txt"
        report.parent.mkdir(parents=True, exist_ok=True)
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
        # fe-phone 同步：PH21 删了 Tailscale 四步清单与 Cloudflare 警告段（#phone-channel-warn、「重启后需重新扫码」），
        # PH22 删了两处书签句（#phone-bookmark-hint），PH16 的单选卡取代了 #phone-channel-state 状态行；
        # 「先扫二维码」换成原型的引导句（PH25 文案，审核决定 A5）
        for needle in ('id="phone-channel"', 'role="radiogroup"', 'id="btn-tailscale-recheck"',
                       'id="btn-phone-address-copy"', 'id="phone-address-alt-line"',
                       'id="phone-stop-confirm"', 'id="btn-phone-stop-cancel"',
                       "手机扫码打开页面，再输入这 6 位配对码", "下次连接要重新扫码配对"):
            self.assertIn(needle, html, "帮助入口缺少 %s" % needle)
        for gone in ('id="phone-channel-warn"', 'id="phone-bookmark-hint"', 'id="tailscale-guide"',
                     'id="phone-qr-note"'):
            self.assertNotIn(gone, html, "%s 按原型删除（PH21、PH22）" % gone)
        # 四步说明只解释环境准备，不把配对码拼进地址或按钮
        self.assertNotIn("pair_code=", html)
        self.assertNotIn("window.confirm", html)

    def test_help_cross_device_credential_contracts(self):
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        # 远程通道只允许 Tailscale 与 Cloudflare，不给普通局域网入口
        # fe-phone 同步：下拉框换成两张单选卡（PH16），按 radio 的 value 核对
        self.assertEqual(re.findall(r'name="phone-chan"[^>]*value="([^"]+)"', html),
                         ["tailscale", "cloudflare"])
        # 文案明确先扫码再输入配对码（fe-phone 同步：照原型的引导句，PH25 文案）
        self.assertIn("手机扫码打开页面，再输入这 6 位配对码", html)
        self.assertIn('id="phone-qr"', html)
        self.assertIn('id="phone-code"', html)
        # 账号区域：保存/清除 + 人工验证码降级提示；密码框按密码类型
        self.assertIn('id="credential-editor"', html)
        self.assertIn('id="btn-credentials-save"', html)
        self.assertIn('id="btn-credentials-clear"', html)
        self.assertRegex(html, r'id="credential-pass"[^>]*type="password"')
        # fe-ocr-login 同步：OC03 的 lead 照原型写「没装或认不出来时，由你在手机上手动输入」，不再有「人工输入」四个字
        self.assertIn("手动输入", html, "未安装 ddddocr 必须提示人工降级")


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
