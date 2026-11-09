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
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from application.phone_service import PhoneAccessService  # noqa: E402
from domain.phone_rules import IP_FAIL_LIMIT  # noqa: E402
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

    def test_pair_view_led_cap_and_states_follow_prototype(self):
        """PA03：点阵屏与四态说明照原型 renderVals 的 pair 段（Phone.dc.html:908-910）。"""
        values = run_phone_js("""
const empty = PhoneModel.pairView("", 0, "");
out.push({cap: empty.cap, tag: empty.tag, tone: empty.led.tone,
          cant: empty.cantSubmit, cells: empty.led.dots.length === empty.led.cols * 7});
const typing = PhoneModel.pairView("12", 0, "");
out.push({cap: typing.cap, blink: typing.led.dots.filter((d) => d.cls === "blink").length});
const full = PhoneModel.pairView("123456", 0, "");
out.push({cap: full.cap, cant: full.cantSubmit, cols: full.led.cols});
const wrong = PhoneModel.pairView("9", 0, "配对码不对，请核对后重试。再错 2 次要等 60 秒。");
out.push({tone: wrong.led.tone, hasErr: wrong.hasErr, cap: wrong.cap});
const locked = PhoneModel.pairView("123456", 47, "");
out.push({tag: locked.tag, tone: locked.led.tone, cap: locked.cap,
          cant: locked.cantSubmit, blink: locked.led.dots.filter((d) => d.cls === "blink").length});
""")
        self.assertEqual(values[0]["cap"], "点上面的点阵屏，输入电脑上的 6 位数")
        self.assertEqual(values[0]["tag"], "输入配对码")
        self.assertEqual(values[0]["tone"], "amber")
        self.assertTrue(values[0]["cant"], "空输入不能提交")
        self.assertTrue(values[0]["cells"], "点阵点数 = 列数 × 7 行")
        self.assertEqual(values[1]["cap"], "还差 4 位")
        self.assertGreater(values[1]["blink"], 0, "空位上有光标点在闪")
        self.assertEqual(values[2]["cap"], "输完了，点“配对”")
        self.assertFalse(values[2]["cant"])
        # 空格字形 2 列 + 它自己的间隙 1 列：6 位数字直排是 35 列，插了空格是 38 列
        self.assertEqual(values[2]["cols"], 38, "LED 文本满 3 位插空格")
        self.assertEqual(values[3]["tone"], "red", "EX04：配错后 LED 红色调")
        self.assertTrue(values[3]["hasErr"])
        self.assertEqual(values[3]["cap"], "还差 5 位")
        self.assertEqual(values[4]["tag"], "已锁定")
        self.assertEqual(values[4]["tone"], "off", "锁定时 LED 转 off")
        self.assertEqual(values[4]["cap"], "47 秒后可以再试")
        self.assertTrue(values[4]["cant"])
        self.assertEqual(values[4]["blink"], 0, "锁定时光标不闪")

    def test_pair_failure_copy_and_countdown_tick(self):
        """PA04/EX03/EX04：配错与锁定文案；倒计时只做呈现递减。"""
        values = run_phone_js("""
out.push(PhoneModel.pairWrongText(2));
out.push(PhoneModel.pairWrongText(1));
out.push(PhoneModel.pairWrongText(0));
out.push(PhoneModel.pairLockedText());
out.push(PhoneModel.pairTickLeft(47));
out.push(PhoneModel.pairTickLeft(1));
out.push(PhoneModel.pairTickLeft(0));
""")
        self.assertEqual(values[0], "配对码不对，请核对后重试。再错 2 次要等 60 秒。")
        self.assertEqual(values[1], "配对码不对，请核对后重试。再错 1 次要等 60 秒。")
        self.assertEqual(values[2], "配对码不对，请核对后重试。",
                         "第 3 次失败已到上限：不拼「再错 0 次」尾句，下一次应答就是锁定态")
        self.assertEqual(values[3], "尝试次数过多，请稍后再试。换一台设备也一样要等。")
        self.assertEqual(values[4:], [46, 0, 0], "每秒一步递减，0 停住")


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
out.push(document.getElementById("conn-text").textContent);
""")
        # 原断言钉住旧顶栏文案「离线/未知」：G01 要求 pill 三态对齐原型（已连接/离线/同步中）。
        # 本用例的时序是「先失败后把 lastOkAt 拨旧」——失败发生在 lastOkAt 还新鲜时，
        # syncOffline 已把重试计数清零，属于静默过期，按 G13 决策显示「同步中」；
        # 真正的「离线」档（从未连上或过期且在重试）在 test_offline_says_why 里单独断言
        self.assertEqual(values, [2000, 4000, True, "同步中"])

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
        # 末位原断言钉住「取消钮藏在验证码组里」的旧结构：RL01 照原型把 取消/换一张图
        # 挪进页脚 .sh-f（Phone.dc.html:347），流程结束回到表单初态仍可「取消」收起，
        # 所以取消钮改为可见（False），其余四项（图/提交/换图收起）不变
        self.assertEqual(values, ["c1", [False, True], "Ab12",
                                  [False, True, True, False, True]])

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
        # 末位原断言钉住旧对账句「提交结果未知，正在对账…」：RL02 把对账态归并进原型三句
        # （「正在登录，请等结果」，映射表见 PhoneModel.RELOGIN_BUSY 注释），锁定与对账不变
        self.assertEqual(values, ["phone_relogin_submit", "reconcile",
                                  [1, True, False], "正在登录，请等结果"])

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
        """校验途中不能说成"结束"，更不能让人对同一张图再发一次。

        原断言钉住「输入区留着但禁用」的旧实现：RL02 照原型把 verifying 归并成忙态
        spin「正在登录，请等结果」（Phone.dc.html:887），表单整组收起且 sheet 由
        busyLock 锁死（Esc/遮罩/关闭钮都不收）——「不能重发」由更强的
        「整组收起 + sheet 不可关」承载，提交钮 disabled 仍为 True。
        """
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
        self.assertEqual(values, [[True, True, True, True], "c1", "正在登录，请等结果"])

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
        """没有在进行的重登只是 idle，不是「结束」，更不能盖掉上一次的原因。

        B-P2-1（RL05）：失败句分支——eof 等其余安全码保留「重新登录结束：{码}」
        通用句；bad_password 直出英文码看不懂，映射成原型整句（两处「结束」呈现
        同一映射：更多面板的 #relogin-note 与重登 sheet 红条 #rel-err）。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
$("relogin-note").textContent = "还不能开始：bad_csrf";
ui.ingest({state:{login_relay:{state:"idle"}}});
out.push([$("relogin-note").textContent, $("btn-relogin").hidden,
          $("btn-relogin-submit").hidden]);
ui.ingest({state:{login_relay:{state:"failed", safe_error:"eof", live:true}}});
out.push($("relogin-note").textContent);
ui.ingest({state:{login_relay:{state:"failed", safe_error:"bad_password", live:true}}});
out.push($("relogin-note").textContent);
ui.openRelogin();
out.push($("rel-err").textContent);
''')
        # 用语统一：「重登」→「重新登录」（设计第 12 节用词表）；bad_password 走原型句
        self.assertEqual(values[0], ["还不能开始：bad_csrf", False, True])
        self.assertEqual(values[1], "重新登录结束：eof", "eof 走通用句")
        self.assertEqual(values[2],
                         "学校说账号或密码不对。为了避免账号被锁，没有重试。核对后再登录。",
                         "bad_password 走原型句（B-P2-1）")
        self.assertEqual(values[3],
                         "学校说账号或密码不对。为了避免账号被锁，没有重试。核对后再登录。",
                         "RL05 红条同一映射")

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
        # 前两位不变（历史成功不重播）；末位原断言钉住旧句「重新登录成功，正在刷新列表」：
        # RL08 完成态两套文案照原型（Phone.dc.html:894），非忙态要说明计划不会自动重新开始
        self.assertEqual(values, [[True, True],
                                  "重新登录成功，活动列表已刷新。计划不会自动重新开始，要你重新核对后再点开始。"])

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
        """电脑在认图时，手机连输入框都不该出现——留个空框只会让人以为轮到自己。

        末位原断言钉住旧结构里常驻的入口主钮（False）：RL03（Phone.dc.html:888）auto 态
        照原型只留忙态「电脑正在自动登录」与「收起，在后台继续」，表单含主钮整组收起，
        所以主钮随之隐藏（True）；验证码组照旧收起。
        """
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const png = "%s";
ui.ingest({state:{login_relay:{mode:"auto", state:"waiting_code", retrying:true,
  flow_id:"f1", challenge_id:"c1", image:png, attempts:1, auto_failures:0,
  expires_in:null}}});
out.push([$("relogin-captcha-group").hidden, $("btn-relogin").hidden]);
''' % CAPTCHA_PNG)
        self.assertEqual(values, [[True, True]])

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
        # 首组原断言钉住旧结构里常驻的入口主钮：RL03（Phone.dc.html:888）auto 态照原型
        # 只留忙态与「收起，在后台继续」，表单含主钮整组收起，主钮随之隐藏（True）
        self.assertEqual(values[0], [True, True])
        self.assertEqual(values[1], [False, False, False, True])

    def test_offline_says_why_and_keeps_refresh_tappable(self):
        """断网时界面必须自己说明原因，刷新按钮不能被一起禁掉。

        原断言整条读 #offline-note 的 textContent。EX01 照原型把红条改成
        .alert 结构（标题/正文/重试钮三件，Phone.dc.html:852），文案拆进子元素，
        断言随之改读子元素——检查强度不降：标题句、正文句、钮文案、重试计数
        逐字核对，另补 N=0 时标题不带「已重试」尾缀的原型口径。
        """
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = 0;                    // 从没连上过 = 判旧
ui.refreshControls();
const first = [$("offline-note").hidden, $("offline-note-title").textContent,
               $("offline-note-text").textContent, $("btn-offline-retry").textContent,
               $("stale-note").hidden, $("btn-refresh").disabled,
               $("conn-text").textContent];
globalThis.__fetch = async () => { throw new Error("offline"); };
await ui.poll(true);
await ui.poll(true);
out.push(first);
out.push([ui.model.offlineTries, $("offline-note-title").textContent,
          $("btn-offline-retry").textContent]);
''')
        self.assertFalse(values[0][0], "离线提示必须显示")
        self.assertEqual(values[0][1], "连不上电脑",
                         "N=0 时标题不带「已重试」尾缀（原型 Phone:852）")
        self.assertEqual(values[0][2], "确认电脑开着、程序没退出。如果只是手机断网，电脑上的计划不受影响。")
        self.assertEqual(values[0][3], "重试", "告警条上要有「重试」钮（EX01）")
        self.assertFalse(values[0][4], "还要告诉用户先刷新")
        self.assertFalse(values[0][5], "刷新按钮必须可点")
        # G01/G13：从未连上过是「离线」档（bad），不是静默过期的「同步中」
        self.assertEqual(values[0][6], "离线")
        self.assertEqual(values[1][0], 2)
        self.assertEqual(values[1][1], "连不上电脑，已重试 2 次",
                         "重试次数要让用户看见（原型「，已重试 N 次」尾缀）")
        self.assertEqual(values[1][2], "重试")

    def test_refresh_button_shows_it_is_working(self):
        # G01 改动原因：刷新钮照原型改成图标钮（aria 刷新），不再写「刷新中…」文字；
        # 忙态改由按钮 disabled + pill「同步中」表达，所以改读这两处
        values = run_phone_js('''
const ui = PhoneUI;
let release;
globalThis.__fetch = () => new Promise((resolve) => {
  release = () => resolve({status: 200, json: async () => ({})});
});
const pending = ui.poll(true);
const during = [$("btn-refresh").disabled, $("conn-text").textContent];
release();
await pending;
out.push(during);
out.push([$("btn-refresh").disabled, $("conn-text").textContent]);
''')
        self.assertEqual(values[0], [True, "同步中"])
        self.assertEqual(values[1], [False, "已连接"])

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


class ReloginSheetTests(unittest.TestCase):
    """RL01–RL08：重登 sheet 六态（原型 sh.isRelogin/rel 段，Phone.dc.html:326-350/881-905）。"""

    def test_lead_four_states_and_relbad_red_error(self):
        """RL04/RL07：lead 四态切换 + paused 红错无 lead。"""
        values = run_phone_js('''
out.push(PhoneModel.relLead({mode:"manual", live:true, attempts:3}, {saved:true, ocr_ready:true}));
out.push(PhoneModel.relLead(null, {saved:true, ocr_ready:false}));
out.push(PhoneModel.relLead(null, {saved:false, ocr_ready:false}));
out.push(PhoneModel.relLead(null, {saved:false, ocr_ready:true}));
out.push(PhoneModel.relLead(null, {saved:true, ocr_ready:true, paused:true}));
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state:{relogin_setup:{saved:true, account_hint:"u*", ocr_ready:true, paused:true}}});
ui.openRelogin();
out.push([$("rel-err").hidden, $("rel-err").textContent,
          $("rel-lead").hidden, $("relogin-account").hidden, $("rel-auto").hidden]);
''')
        self.assertEqual(values[0], "电脑连续 3 次没认对验证码，换你来输。账号密码由电脑自动填写。")
        self.assertEqual(values[1], "电脑会自动填账号密码，你只要输验证码。")
        self.assertEqual(values[2], "电脑上没有保存账号密码，账号、密码和验证码都要输。")
        self.assertEqual(values[3], "电脑上没有保存账号密码，输入账号和密码就行。")
        self.assertEqual(values[4], "", "RL07：relbad 无 lead，红错由固定句承担")
        self.assertEqual(values[5],
                         [False,
                          "电脑上保存的密码学校不认，自动登录已暂停。请输入新的账号密码；勾选保存会替换旧的。",
                          True, False, False],
                         "RL07：paused 走红错+露出账号密码字段")

    def test_relconfirm_intercepts_before_begin(self):
        """RL06：确认层先拦一步，begin 不被直接调；「自动登录一次」才发。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
let posts = 0;
globalThis.__fetch = async (path, opts) => {
  if (opts && opts.body) posts += 1;
  return {status: 200, json: async () => ({ok: true, mode: "auto"})};
};
ui.ingest({state:{relogin_setup:{saved:true, account_hint:"u*", ocr_ready:true, paused:false}}});
ui.openRelogin();
out.push([posts,
          $("rel-text").textContent.indexOf("用电脑上存的账号密码登录一次") === 0,
          $("rel-text").textContent.indexOf("计划不会自动开始") > 0,
          $("btn-relogin-auto").hidden, $("btn-relogin").hidden,
          $("relogin-account").hidden]);
$("btn-relogin-auto").click();
for (let i = 0; i < 30; i++) await Promise.resolve();
out.push([posts, ui.model.reloginStarting]);
''')
        self.assertEqual(values[0], [0, True, True, False, True, True],
                         "确认层只展示不发起；主钮换成「自动登录一次」")
        self.assertEqual(values[1], [1, False], "点确认才发 begin，且单飞锁已释放")

    def test_relconfirm_tail_switches_with_plan_busy(self):
        """RL06：计划在跑时尾句换「成功后报名计划照常继续。」（原型 Phone:889 口径）。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.model.busy = true;
ui.ingest({state:{relogin_setup:{saved:true, account_hint:"u*", ocr_ready:true, paused:false}}});
ui.openRelogin();
out.push($("rel-text").textContent.indexOf("成功后报名计划照常继续。") > 0);
''')
        self.assertTrue(values[0])

    def test_busy_phrases_and_verifying_sheet_lock(self):
        """RL02：忙态三句归并；verifying 收表单且 sheet 锁死（关闭钮藏起）。

        「正在准备…」只在本地 begin 在途且装了识别时出现（原型 relNeedCap 分支，
        Phone.dc.html:886）；auto 快照的忙态统一是 RL03 的「电脑正在自动登录」。
        """
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state:{login_relay:{mode:"manual", state:"starting", flow_id:"f", live:true}}});
out.push($("rel-busy-text").textContent);
globalThis.__fetch = async () => ({status: 200, json: async () => ({ok: true, mode: "auto"})});
ui.ingest({state:{relogin_setup:{saved:true, ocr_ready:true}}});
const flight = ui.beginRelogin();    // 本地 begin 在途：正在准备…
out.push($("rel-busy-text").textContent);
await flight;
ui.ingest({state:{login_relay:{mode:"manual", state:"verifying", flow_id:"f", live:true}}});
out.push([$("rel-busy-text").textContent, $("rel-form").hidden]);
ui.openSheet("relogin");
ui.model.reloginSubmitting = true;   // 提交在途（对账态同句，映射见 RELOGIN_BUSY）
ui.refreshControls();
out.push([$("btn-sheet-close").hidden, $("rel-spin").hidden,
          $("rel-busy-text").textContent]);
''')
        self.assertEqual(values[0], "正在向电脑要验证码…")
        self.assertEqual(values[1], "正在准备…")
        self.assertEqual(values[2], ["正在登录，请等结果", True])
        self.assertEqual(values[3], [True, False, "正在登录，请等结果"],
                         "RL02/验证中：spin 三句之一 + busyLock 拦关闭")

    def test_done_postscript_both_branches(self):
        """RL08：附言两支（已保存/只在这次有效）随本轮是否输账号+勾保存。"""
        values = run_phone_js('''
const ui = PhoneUI;
const posts = [];
globalThis.__fetch = async (path, opts) => {
  if (opts && opts.body) posts.push(JSON.parse(opts.body).action);
  return {status: 200, json: async () => ({ok: true, mode: "manual"})};
};
ui.model.lastOkAt = Date.now();
ui.ingest({state:{relogin_setup:{saved:false, account_hint:"", ocr_ready:false, paused:false}}});
ui.refreshControls();               // setup 到手后字段才亮（与 test_account_password 同一前置）
$("relogin-user").value = "u1"; $("relogin-pass").value = "p1";
$("relogin-save").checked = true;
await ui.beginRelogin();
ui.ingest({state:{login_relay:{mode:"manual", state:"success", flow_id:"f1", live:true}}});
out.push([posts[posts.length - 1], $("rel-text").textContent, $("btn-relogin-done").textContent]);
$("relogin-pass").value = "p2"; $("relogin-save").checked = false;
await ui.beginRelogin();
ui.ingest({state:{login_relay:{mode:"manual", state:"success", flow_id:"f2", live:true}}});
out.push($("rel-text").textContent);
''')
        self.assertEqual(values[0][0], "phone_relogin_begin")
        self.assertIn("重新登录成功，活动列表已刷新。计划不会自动重新开始，要你重新核对后再点开始。",
                      values[0][1], "非忙态主文案照 RL08")
        self.assertIn("账号已加密保存到电脑，下次失效时只要输验证码。",
                      values[0][1], "勾了保存：附言带 saveGain（没装识别→只要输验证码）")
        self.assertEqual(values[0][2], "完成")
        self.assertIn("账号只在这次运行中有效，关闭工具后清除。", values[1],
                      "没勾保存：附言说只在这次有效")

    def test_done_while_busy_says_plan_continues(self):
        """RL08：忙时完成句照原型（报名计划照常继续），无输账号就不带附言。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.model.busy = true;
ui.ingest({state:{login_relay:{mode:"auto", state:"success", flow_id:"f", live:true}}});
out.push([$("rel-text").textContent, $("rel-spin").hidden, $("btn-relogin-done").textContent]);
''')
        self.assertEqual(values[0], ["重新登录成功，报名计划照常继续。", True, "完成"])

    def test_auto_state_shows_progress_and_background_button(self):
        """RL03：auto 忙态句 + 说明文 + 「收起，在后台继续」；auto 不锁 sheet。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state:{login_relay:{mode:"auto", state:"waiting_code", retrying:true, live:true,
  flow_id:"f", challenge_id:"", image:"", attempts:1, auto_failures:0}}});
out.push([$("rel-spin").hidden, $("rel-busy-text").textContent,
          $("rel-text").textContent,
          $("btn-relogin-done").textContent, $("rel-form").hidden,
          $("relogin-captcha-group").hidden]);
ui.openSheet("relogin");
out.push($("sheet-root").hidden);
ui.closeSheet();
out.push($("sheet-root").hidden);
''')
        self.assertEqual(values[0], [False, "电脑正在自动登录",
                                     "验证码由电脑识别，手机上不用操作。电脑连续认错 3 次，才会转给你输入。",
                                     "收起，在后台继续", True, True])
        self.assertFalse(values[1])
        self.assertTrue(values[2], "auto 态不进 busyLock：收起，在后台继续要能关")

    def test_handoff_lead_hides_account_fields(self):
        """RL04 态 1：连续认错交接——lead 换句、账号密码字段收起（电脑自己填）。"""
        values = run_phone_js('''
const ui = PhoneUI;
const png = "%s";
ui.model.lastOkAt = Date.now();
ui.ingest({state:{relogin_setup:{saved:true, account_hint:"u*", ocr_ready:true, paused:false}}});
ui.ingest({state:{login_relay:{mode:"manual", state:"waiting_code", flow_id:"f",
  challenge_id:"c", image:png, live:true, attempts:3, auto_failures:0}}});
out.push([$("rel-lead").textContent, $("relogin-account").hidden,
          $("relogin-captcha-group").hidden, $("btn-relogin-submit").hidden,
          $("btn-relogin-refresh").hidden, $("btn-relogin-cancel").hidden,
          $("btn-relogin").hidden]);
''' % CAPTCHA_PNG)
        self.assertEqual(values[0], [
            "电脑连续 3 次没认对验证码，换你来输。账号密码由电脑自动填写。",
            True, False, False, False, False, True])

    def test_rel_can_submit_gates(self):
        """relCanSubmit（原型 Phone:675）：账号密码都填、验证码 4 位才放行主钮。"""
        values = run_phone_js('''
out.push([PhoneModel.relCanSubmit({needAcct:true, user:"u", pass:"p"}),
          PhoneModel.relCanSubmit({needAcct:true, user:"", pass:"p"}),
          PhoneModel.relCanSubmit({needAcct:true, user:"u", pass:""}),
          PhoneModel.relCanSubmit({needCap:true, code:"Ab12"}),
          PhoneModel.relCanSubmit({needCap:true, code:"Ab1"}),
          PhoneModel.relCanSubmit({needAcct:false})]);
''')
        self.assertEqual(values[0], [True, False, False, True, False, True])


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
out.push([ui.model.pending.done, actions[0].action, actions[0].args.request_id,
          ui.model.pending.outcome]);
''')
        self.assertEqual(values, [False, [True, "cancel_start_request", "late", "canceled"]])

    def test_terminal_pending_releases_start_immediately(self):
        """A-BUG-1：取消等待后 pending 已有终态结论，15 秒窗口不再锁死开始——
        立即 start 要发出全新 request_id，且不再提示「上一次开始还没核对完」。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.model.selected = ["a1"];
ui.model.items = [{id: "a1", name: "甲活动", sign_start: "2026-11-09 14:30:00"}];
const posts = [];
globalThis.__fetch = async (url, opts) => {
  if (opts && opts.method) posts.push(JSON.parse(opts.body));
  return {status: 200, json: async () => ({ok: true})};
};
ui.model.pending = {request_id: "req-old", at: Date.now() - 1000, done: true,
                    outcome: "canceled"};
await ui.startPlan();
out.push({posted: posts.length, rid: posts[0] && posts[0].args.request_id,
          old: "req-old", banner: $("banner").textContent});
''')
        r = values[0]
        self.assertEqual(r["posted"], 1, "canceled 终态立即放行新的开始")
        self.assertNotEqual(r["rid"], r["old"], "发的是新 request_id")
        self.assertEqual(r["banner"], "", "终态不再提示「还没核对完」")

    def test_accepted_pending_keeps_the_double_click_window(self):
        """A-BUG-1：accepted 仍保留 15 秒防双击窗口（计划可能已开跑，等快照接管
        busy），但提示只在未决时给——accepted 窗口内静默拦，不发第二个请求。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.model.selected = ["a1"];
const posts = [];
globalThis.__fetch = async (url, opts) => {
  if (opts && opts.method) posts.push(JSON.parse(opts.body).action);
  return {status: 200, json: async () => ({ok: true})};
};
ui.model.pending = {request_id: "req-1", at: Date.now(), done: true,
                    outcome: "accepted"};
await ui.startPlan();
out.push({posted: posts.length, banner: $("banner").textContent});
ui.model.pending = {request_id: "req-2", at: Date.now(), done: false};
await ui.startPlan();
out.push({posted: posts.length, banner: $("banner").textContent});
''')
        accepted, undecided = values
        self.assertEqual(accepted["posted"], 0, "accepted 窗口内防双击拦下")
        self.assertEqual(accepted["banner"], "", "已受理不是「还没核对完」：不给提示")
        self.assertEqual(undecided["posted"], 0, "未决照旧拦")
        self.assertEqual(undecided["banner"], "上一次开始还没核对完，请先等结果",
                         "提示只在未决时给")

    def test_reconciled_rejection_reaches_the_banner(self):
        """A-BUG-3：对账 returned rejected/canceled 不能静默收口——回包文本（有则）
        或状态词亮到 banner；accepted 照旧清提示。reconcile 由 ingest 在未决
        pending 上触发（fire-and-forget），用微任务循环等它落地。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const answers = [
  {ok: true, state: "rejected", text: "计划没能开始，请再试一次"},
  {ok: true, state: "canceled"},
  {ok: true, state: "accepted"}];
let i = 0;
globalThis.__fetch = async () => ({status: 200, json: async () => answers[i++]});
const run = async (rid) => {
  ui.model.pending = {request_id: rid, at: Date.now(), done: false};
  ui.ingest({state: {}});
  for (let k = 0; k < 20; k += 1) await Promise.resolve();
};
await run("r1");
out.push({banner: $("banner").textContent, done: ui.model.pending.done,
          outcome: ui.model.pending.outcome});
await run("r2");
out.push({banner: $("banner").textContent, outcome: ui.model.pending.outcome});
await run("r3");
out.push({banner: $("banner").textContent, outcome: ui.model.pending.outcome});
''')
        rejected, canceled, accepted = values
        self.assertEqual(rejected["banner"], "计划没能开始，请再试一次",
                         "rejected：回包文本亮到 banner")
        self.assertEqual([rejected["done"], rejected["outcome"]], [True, "rejected"])
        self.assertEqual(canceled["banner"], "开始已取消",
                         "canceled 无回包文本：状态词亮到 banner")
        self.assertEqual(canceled["outcome"], "canceled")
        self.assertEqual(accepted["banner"], "", "accepted 照旧清提示")
        self.assertEqual(accepted["outcome"], "accepted")


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


class PairStatesDomTests(unittest.TestCase):
    """PA03/EX03/EX04：点阵屏四态、锁定与配错态（BE1 结构化字段驱动）。"""

    def test_wrong_code_shows_remaining_attempts_and_red_led(self):
        values = run_phone_js('''
$("pair-code").value = "999999";
globalThis.__fetch = async () => ({status: 403, json: async () => ({
  ok: false, error: "bad_code", text: "配对码不对，请核对后重试",
  locked: false, retry_after_s: 0, remaining_attempts: 2})});
$("btn-pair").click();
for (let i = 0; i < 20; i += 1) await Promise.resolve();
out.push({err: $("pair-error").textContent, hidden: $("pair-error").hidden,
          tone: $("pair-led-wrap").className, tag: $("pair-tag").textContent,
          cap: $("pair-cap").textContent, code: $("pair-code").value});
''')
        row = values[0]
        self.assertEqual(row["err"], "配对码不对，请核对后重试。再错 2 次要等 60 秒。")
        self.assertFalse(row["hidden"])
        self.assertIn("red", row["tone"], "EX04：配错后 LED 红色调")
        self.assertEqual(row["tag"], "输入配对码")
        self.assertEqual(row["cap"], "点上面的点阵屏，输入电脑上的 6 位数")
        self.assertEqual(row["code"], "", "原型 submitPair：失败清空重输")

    def test_locked_state_disables_input_and_counts_down(self):
        values = run_phone_js('''
$("pair-code").value = "999999";
globalThis.__fetch = async () => ({status: 403, json: async () => ({
  ok: false, error: "locked", text: "尝试次数过多，请稍后再试",
  locked: true, retry_after_s: 47, remaining_attempts: 0})});
$("btn-pair").click();
for (let i = 0; i < 20; i += 1) await Promise.resolve();
out.push({err: $("pair-error").textContent, tag: $("pair-tag").textContent,
          tagCls: $("pair-tag").className, cap: $("pair-cap").textContent,
          btn: $("btn-pair").disabled, input: $("pair-code").disabled,
          tone: $("pair-led-wrap").className});
__fireTimers();        // 呈现 tick：每秒只递减显示值
out.push($("pair-cap").textContent);
''')
        row, after_tick = values
        self.assertEqual(row["err"], "尝试次数过多，请稍后再试。换一台设备也一样要等。")
        self.assertEqual(row["tag"], "已锁定")
        self.assertIn("red", row["tagCls"], "EX03：tag「已锁定」红")
        self.assertEqual(row["cap"], "47 秒后可以再试", "倒计时秒数来自服务端 retry_after_s")
        self.assertTrue(row["btn"], "锁定时配对钮禁用")
        self.assertTrue(row["input"], "锁定时输入禁用")
        self.assertIn("off", row["tone"], "锁定时 LED 转 off")
        self.assertEqual(after_tick, "46 秒后可以再试", "每秒 tick 只做呈现递减")

    def test_countdown_end_releases_input_for_the_next_try(self):
        values = run_phone_js('''
$("pair-code").value = "999999";
globalThis.__fetch = async () => ({status: 403, json: async () => ({
  ok: false, error: "locked", text: "尝试次数过多，请稍后再试",
  locked: true, retry_after_s: 1, remaining_attempts: 0})});
$("btn-pair").click();
for (let i = 0; i < 20; i += 1) await Promise.resolve();
out.push([$("btn-pair").disabled, $("pair-code").disabled, $("pair-cap").textContent,
          $("pair-error").hidden]);
__fireTimers();
out.push([$("btn-pair").disabled, $("pair-code").disabled, $("pair-cap").textContent,
          $("pair-error").hidden, $("pair-error").textContent]);
''')
        locked, after = values
        self.assertEqual(locked, [True, True, "1 秒后可以再试", False])
        self.assertEqual(after, [True, False, "点上面的点阵屏，输入电脑上的 6 位数", True, ""],
                         "归零只放开呈现层（输入不再禁用；空输入仍不可提交），服务端是唯一闸门；"
                         "UI-F6（原型 lockLeft 归零清 pairErr）：旧错误条一并收回")

    def test_need_pair_repaints_the_pair_screen(self):
        """A-BUG-5：401 回配对页时锁定态要一并清干净——stopPairLock 只回收倒计时，
        曾漏掉重画，屏上残留「已锁定」tag 与禁用的输入。"""
        values = run_phone_js('''
PhoneUI.beginPairLock(30);                 // 制造锁定态
PhoneUI.renderPair();
out.push([$("pair-tag").textContent, $("pair-code").disabled]);
globalThis.__fetch = async () => ({status: 401, json: async () => ({})});
await PhoneUI.poll(true);
out.push([$("pair-tag").textContent, $("pair-code").disabled, PhoneUI.model.pairLockLeft,
          $("pair").hidden]);
''')
        locked, back = values
        self.assertEqual(locked, ["已锁定", True], "前置：锁定态成立")
        self.assertEqual(back, ["输入配对码", False, 0, False],
                         "回配对页按当前模型重画：tag 复位、输入放开（A-BUG-5）")

    def test_pair_is_single_flight(self):
        """A-BUG-6：配对在途锁防双击双发——配对码一次一用，双击的第二个请求
        必失败还白吃一次失败计数；在途时第二次调用直接返回。"""
        values = run_phone_js('''
$("pair-code").value = "482913";
let calls = 0;
globalThis.__fetch = async (path) => {
  calls += 1;
  return path === "/pair"
    ? {status: 200, json: async () => ({ok: true, csrf: "c1"})}
    : {status: 200, json: async () => ({state: {}, events: []})};
};
const first = PhoneUI.pair();
const second = PhoneUI.pair();          // 在途中的第二次点击：直接返回
await Promise.all([first, second]);
out.push([calls, $("pair").hidden, PhoneUI.model.pairing]);
''')
        self.assertEqual(values[0], [2, True, False],
                         "/pair 只发一次（另一请求是 poll 的 state），配对成功进主界面，锁已放开")

    def test_pair_success_shows_dismissable_connected_alert(self):
        """UI-F13（原型 .alert.ok，Phone.dc.html:36/857）：配对成功给「已连接电脑」
        两句静态告警 + 「知道了」钮；关闭后本会话不再出现。两句与色档是静态
        markup（vm 沙箱元素不解析 HTML），源码断言钉住，行为断言管开关。"""
        values = run_phone_js('''
$("pair-code").value = "482913";
globalThis.__fetch = async (path) => path === "/pair"
  ? {status: 200, json: async () => ({ok: true, csrf: "c1"})}
  : {status: 200, json: async () => ({state: {}, events: []})};
$("btn-pair").click();
for (let i = 0; i < 20; i += 1) await Promise.resolve();
out.push($("pair-ok-alert").hidden);
$("btn-pair-ok").click();
out.push($("pair-ok-alert").hidden);
''')
        shown, dismissed = values
        self.assertFalse(shown, "配对成功后告警可见")
        self.assertTrue(dismissed, "「知道了」收起，本会话不再出现")
        html = (PHONE_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="pair-ok-alert" class="alert ok"', html,
                      "alert.ok 色档照原型（Phone.dc.html:36）")
        self.assertIn("<b>已连接电脑</b><span>建议把这一页存成书签，下次直接打开。</span>", html,
                      "两句照原型逐字（Phone.dc.html:857）")
        self.assertIn('id="btn-pair-ok"', html)
        css = (PHONE_DIR / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".alert.ok {", css, "色档样式已落 styles.css")

    def test_pairing_success_leaves_no_lock_or_error(self):
        values = run_phone_js('''
$("pair-code").value = "482913";
PhoneUI.beginPairLock(30);          // 先制造锁定态，再用成功回包走完配对
globalThis.__fetch = async (path, opts) => {
  const body = JSON.parse(opts.body);
  if (path === "/pair") {
    return {status: 200, json: async () => ({ok: true, csrf: "c1",
      cookie: "campus_phone_sid=t; HttpOnly", csrf_cookie: "campus_phone_csrf=c; Path=/",
      code: body.code})};
  }
  return {status: 200, json: async () => ({state: {}, events: [], reset: false, seq: 1})};
};
$("btn-pair").click();
for (let i = 0; i < 20; i += 1) await Promise.resolve();
out.push([$("pair").hidden, $("app").hidden, PhoneUI.model.pairLockLeft,
          $("pair-error").textContent, $("pair-error").hidden]);
''')
        self.assertEqual(values[0], [True, False, 0, "", True],
                         "配对成功进主界面，锁定倒计时与错误条一并收回")


class RunWaitModelTests(unittest.TestCase):
    """G04/G10/RW02/RW03：LED 计划板、四站 rail、任务卡与确认文案（run-wait 任务）。

    全部走 PhoneModel 纯函数（node vm 跑真实 app.js），渲染函数只做 DOM；
    时刻口径与 ListDetailModelTests 一致：业务此刻＝北京时间 2026-11-08 12:00:00。"""

    NOW_JS = 'const nowS = Date.UTC(2026, 10, 8, 4, 0, 0) / 1000;   /* 北京时间 11-08 12:00:00 */'

    def test_run_board_waiting_led_thresholds_and_batch_copy(self):
        """G04 等待板（原型 running 分支，Phone.dc.html:813-817）：LED 琥珀、≤10 秒转红、
        tag 按 gap>5/≤5 分等开放/即将开放；同批多场副题「这一批 N 场」；
        cap「开放时间」+capB 按业务此刻算日偏移（hms 带明天前缀）。"""
        values = run_phone_js(self.NOW_JS + """
const mk = (sign_start, status) => ({ name: "甲活动", status: status || "waiting",
  signup_mode: "pre_register", sign_start: sign_start });
const batch = PhoneModel.runBoard(
  { tasks: [mk("2026-11-09 14:30:00"), mk("2026-11-09 14:30:00")] }, nowS, false);
out.push({ tag: batch.tag, tone: batch.led.tone, cap: batch.led.cap,
           capB: batch.led.capB, sub: batch.sub, title: batch.title });
const soon = PhoneModel.runBoard({ tasks: [mk("2026-11-08 12:00:08")] }, nowS, false);
out.push({ tag: soon.tag, tone: soon.led.tone });
const edge = PhoneModel.runBoard({ tasks: [mk("2026-11-08 12:00:03")] }, nowS, false);
out.push({ tag: edge.tag, tone: edge.led.tone });
const single = PhoneModel.runBoard({ tasks: [mk("2026-11-09 14:30:00")] }, nowS, false);
out.push({ sub: single.sub, capB: single.led.capB });
out.push(PhoneModel.runBoard({ tasks: [] }, nowS, false));
""")
        batch, soon, edge, single, empty = values
        self.assertEqual(batch["tag"], "等开放")
        self.assertEqual(batch["tone"], "amber")
        self.assertEqual(batch["cap"], "开放时间")
        self.assertEqual(batch["capB"], "明天 14:30:00", "capB 是 hms 带明天/后天前缀的口径")
        self.assertEqual(batch["sub"], "这一批 2 场同时提交，到点自动开始。")
        self.assertEqual(batch["title"], "甲活动", "板题＝当前场名")
        self.assertEqual(soon["tag"], "等开放")
        self.assertEqual(soon["tone"], "red", "≤10 秒转红（原型 gap>5/≤10 口径）")
        self.assertEqual(edge["tag"], "即将开放", "gap ≤ 5 换「即将开放」")
        self.assertEqual(edge["tone"], "red")
        self.assertEqual(single["sub"], "这一场等开放，到点自动开始。")
        self.assertEqual(single["capB"], "明天 14:30:00")
        self.assertIsNone(empty, "没有场次不给运行板（busy 无快照时整块隐藏）")

    def test_run_board_submitting_and_rail_states(self):
        """G04 提交板与四站 rail（Phone:809-825）：tag/LED 红、cap「本次尝试到」；
        rail done/now/hot 按原型 passed() 口径，via=click（path）第二站叫「打开页面」；
        离线 LED 转 dim 档（「状态已过时」的 cap 替换归 EX01）。"""
        values = run_phone_js(self.NOW_JS + """
const task = { name: "乙活动", status: "submitting", signup_mode: "instant_signup",
  attempts: 3, last_reason: "学校暂时没有回应", retry_deadline: nowS + 40,
  run_started_at: nowS - 100, page_opened_at: nowS - 50,
  path: "click", path_reason: "直发模块不可用" };
const board = PhoneModel.runBoard({ tasks: [task] }, nowS, false);
out.push({ tag: board.tag, tagTone: board.tagTone, tone: board.led.tone,
           cap: board.led.cap, capB: board.led.capB, sub: board.sub,
           rail: board.rail.map((s) => s.label + ":" + s.state) });
const early = PhoneModel.runBoard(
  { tasks: [{ name: "乙活动", status: "waiting", signup_mode: "pre_register",
              sign_start: "2026-11-08 12:30:00", run_started_at: nowS - 10 }] }, nowS, false);
out.push(early.rail.map((s) => s.label + ":" + s.state));
out.push(PhoneModel.runBoard({ tasks: [task] }, nowS, true).led.tone);
const multi = PhoneModel.runBoard(
  { tasks: [task, Object.assign({}, task, { name: "丙活动" })] }, nowS, false);
out.push(multi.sub);
""")
        submitting, early, off_tone, multi = values
        self.assertEqual(submitting["tag"], "正在提交")
        self.assertEqual(submitting["tagTone"], "red")
        self.assertEqual(submitting["tone"], "red")
        self.assertEqual(submitting["cap"], "本次尝试到")
        self.assertEqual(submitting["capB"], "12:00:40")
        self.assertEqual(submitting["sub"], "已提交 3 次，最近：学校暂时没有回应")
        self.assertEqual(submitting["rail"],
                         ["启动:done", "打开页面:done", "开放提交:hot", "核对结果:"])
        self.assertEqual(early, ["启动:done", "准备好:now", "开放提交:", "核对结果:"],
                         "页开完第二站 done、只拉起过 worker 是 now（原型 passed 口径）")
        self.assertEqual(off_tone, "dim", "离线用 dim 档（提交态原型 off?'dim':'red'）")
        self.assertEqual(multi, "正在提交 2 场，每场结果单独显示。")

    def test_task_card_follows_prototype_detail_priority(self):
        """G10 任务卡（原型 card()，Phone.dc.html:842-848）：状态词与 tone 映射照抄；
        detail 优先级照抄——等待明细 → 页点击尾注 → 提交中明细覆盖；
        终态场 detail：RS02 三句照原型（success/full/unconfirmed，Phone:560/564/565），
        其余仍用电脑口径 taskText，取消场给 reason；取消钮只给等待中的场。"""
        values = run_phone_js(self.NOW_JS + """
const waiting = PhoneModel.taskCard({ name: "甲", status: "waiting", signup_mode: "pre_register",
  sign_start: "2026-11-09 14:30:00" }, 0, nowS);
out.push(waiting);
const prepared = PhoneModel.taskCard({ name: "甲", status: "waiting", signup_mode: "pre_register",
  sign_start: "2026-11-09 14:30:00", page_opened_at: nowS - 5 }, 0, nowS);
out.push(prepared);
const instant = PhoneModel.taskCard({ name: "乙", status: "waiting", signup_mode: "instant_signup",
  sign_start: "2026-11-08 11:00:00" }, 0, nowS);
out.push(instant);
const click = PhoneModel.taskCard({ name: "丙", status: "waiting", signup_mode: "pre_register",
  sign_start: "2026-11-09 14:30:00", path: "click", path_reason: "直发模块不可用" }, 0, nowS);
out.push(click);
const submitting = PhoneModel.taskCard({ name: "丁", status: "submitting", attempts: 2,
  path: "click", path_reason: "直发模块不可用", retry_deadline: nowS + 60, max_attempts: 3 },
  3, nowS);
out.push(submitting);
const unlimited = PhoneModel.taskCard({ name: "戊", status: "submitting", attempts: 1,
  retry_deadline: nowS + 60, max_attempts: 0 }, 0, nowS);
out.push(unlimited);
const full = PhoneModel.taskCard({ name: "己", status: "failed", stop_reason: "full" }, 0, nowS);
out.push(full);
const unconfirmed = PhoneModel.taskCard({ name: "庚", status: "failed",
  stop_reason: "unconfirmed" }, 0, nowS);
out.push(unconfirmed);
const failed = PhoneModel.taskCard({ name: "辛", status: "failed", outcome_label: "学校拒绝" }, 0, nowS);
out.push(failed);
const canceled = PhoneModel.taskCard({ name: "壬", status: "canceled",
  reason: "用户取消了这一场" }, 0, nowS);
out.push(canceled);
const success = PhoneModel.taskCard({ name: "癸", status: "success" }, 0, nowS);
out.push(success);
""")
        (waiting, prepared, instant, click, submitting, unlimited,
         full, unconfirmed, failed, canceled, success) = values
        self.assertEqual(waiting["label"], "等待开放")
        self.assertEqual(waiting["tone"], "")
        self.assertEqual(waiting["detail"], "等到 明天 14:30:00 开放")
        self.assertTrue(waiting["canCancel"])
        self.assertEqual(prepared["detail"], "已准备好，明天 14:30:00 开放时提交",
                         "详情页已开（page_opened_at）即「已准备好」")
        self.assertEqual(instant["label"], "准备报名")
        self.assertEqual(instant["detail"], "已开放，正在准备提交")
        self.assertTrue(click["detail"].endswith("。改用页面点击：直发模块不可用"),
                        "页点击尾注接在等待明细后（原型 detail 顺序）")
        self.assertEqual(submitting["label"], "提交中")
        self.assertEqual(submitting["tone"], "run")
        self.assertEqual(submitting["detail"], "已提交 2 次（上限 3 次），重试到 12:01:00")
        self.assertNotIn("改用页面点击", submitting["detail"], "提交明细覆盖页点击尾注（原型顺序）")
        self.assertFalse(submitting["canCancel"])
        self.assertEqual(unlimited["detail"], "已提交 1 次（不限次数），重试到 12:01:00")
        self.assertEqual(full["label"], "名额已满")
        self.assertEqual(full["tone"], "")
        self.assertIn("不是工具出错", full["detail"], "名额已满照 RS02 原型句（Phone:560，点名不是工具出错）")
        self.assertEqual(unconfirmed["label"], "待核对")
        self.assertEqual(unconfirmed["tone"], "ask")
        self.assertEqual(failed["label"], "报名未成功")
        self.assertEqual(failed["tone"], "bad")
        self.assertEqual(failed["detail"], "报名未成功：学校拒绝")
        self.assertEqual(canceled["label"], "已取消")
        self.assertEqual(canceled["detail"], "用户取消了这一场")
        self.assertFalse(canceled["canCancel"], "取消钮只给等待中的场（原型 canCancel）")
        self.assertEqual(success["label"], "报名成功")
        self.assertEqual(success["tone"], "ok")
        # 原断言钉住旧 taskText 单句「已报名」：RS02 照原型把终态原因三句接进任务卡 detail
        # （Phone.dc.html:564 逐字，运行中与结果态同一张卡），断言随之改读原型句
        self.assertEqual(success["detail"], "学校回“操作成功”，结束时向学校核对过：已报名")

    def test_pending_board_two_stages_follow_prototype(self):
        """RW02 等待板两档（Phone:799-803）：15 秒对账窗内「正在核对开始结果/请先不要重复点击。」，
        超窗「还没有查到开始结果/电脑可能已经开始…」；LED --:--:-- off 档、tag 核对中(off)。"""
        values = run_phone_js("""
const at = 1000;
const fresh = PhoneModel.pendingBoard({ at: at, done: false }, at + 5000);
out.push({ cap: fresh.led.cap, capB: fresh.led.capB, tone: fresh.led.tone, text: fresh.led.aria,
           tag: fresh.tag, tagTone: fresh.tagTone, title: fresh.title, sub: fresh.sub });
const stale = PhoneModel.pendingBoard({ at: at, done: false },
                                      at + PhoneModel.PENDING_WINDOW_MS);
out.push({ cap: stale.led.cap, sub: stale.sub, title: stale.title });
out.push(PhoneModel.pendingLong({ at: at, done: true }, at + 99999));
out.push(PhoneModel.pendingLong(null, at));
""")
        fresh, stale, done, none = values
        self.assertEqual(fresh["cap"], "正在核对开始结果")
        self.assertEqual(fresh["capB"], "")
        self.assertEqual(fresh["tone"], "off")
        self.assertEqual(fresh["text"], "正在核对开始结果  --:--:--",
                         "aria＝cap+capB+text（ledOf 既有拼法，capB 空时中间留双空格）")
        self.assertEqual(fresh["tag"], "核对中")
        self.assertEqual(fresh["tagTone"], "off")
        self.assertEqual(fresh["title"], "开始请求已发出")
        self.assertEqual(fresh["sub"], "请先不要重复点击。")
        self.assertEqual(stale["cap"], "还没有查到开始结果")
        self.assertEqual(stale["sub"],
                         "电脑可能已经开始，也可能没收到。工具只查询结果，不会重复发送。")
        self.assertEqual(stale["title"], "开始请求已发出")
        self.assertFalse(done)
        self.assertFalse(none)

    def test_confirm_copy_follows_prototype(self):
        """RW03/SH03/SH04 确认文案（Phone:874-879）逐字照原型（含弯引号），取消一场带场名。"""
        values = run_phone_js("""
out.push(PhoneModel.confirmView("cancelstart"));
out.push(PhoneModel.confirmView("stop"));
out.push(PhoneModel.confirmView("cancelTask", "甲活动"));
out.push(PhoneModel.confirmView("nope"));
""")
        cancelstart, stop, cancel_task, none = values
        self.assertEqual(cancelstart["title"], "取消这次等待？")
        self.assertEqual(cancelstart["text"],
                         "只是不再等这次结果。如果计划其实已经启动，刷新后还要再点“停止计划”。")
        self.assertEqual([cancelstart["no"], cancelstart["yes"]], ["继续等", "取消等待"])
        self.assertEqual(stop["title"], "停止报名计划？")
        self.assertEqual(stop["text"],
                         "工具会停止后续尝试。已经发出的提交仍可能成功，停止不会取消已成功的报名。")
        self.assertEqual([stop["no"], stop["yes"]], ["继续计划", "停止计划"])
        self.assertEqual(cancel_task["title"], "取消这一场？")
        self.assertEqual(cancel_task["text"], "「甲活动」还没提交，取消后不会再报名，其他场次继续。")
        self.assertEqual([cancel_task["no"], cancel_task["yes"]], ["先不取消", "取消这一场"])
        self.assertIsNone(none)


class RunWaitDomTests(unittest.TestCase):
    """G04/G10/RW01/RW03 的 DOM 层：运行板/任务卡/收起列表与确认槽（最小受控 DOM）。"""

    def test_busy_plan_renders_board_cards_and_collapsed_list(self):
        """G04/G10/RW01：运行中显示 LED 计划板与四站 rail，任务卡逐场承载结论，
        活动列表默认收起，「查看活动列表」展开且 aria-expanded 随动。"""
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const running = { busy: true, plan: { plan_id: "p1", status: "running", source: "phone",
  tasks: [
    { task_id: "t1", name: "甲活动", status: "waiting", signup_mode: "pre_register",
      sign_start: "2026-11-09 14:30:00", path: "direct", max_attempts: 0 },
    { task_id: "t2", name: "乙活动", status: "waiting", signup_mode: "pre_register",
      sign_start: "2026-11-09 14:30:00", path: "direct", max_attempts: 0 }] },
  activities: [{ id: "a1", name: "丙活动", sign_start: "2026-11-08 20:00:00" }] };
globalThis.__fetch = async () => ({ status: 200,
  json: async () => ({ state: running, events: [] }) });
await ui.poll(true);
out.push({
  board: !$("plan-board").hidden,
  tag: $("board-tag-text").textContent,
  cap: $("board-cap-text").textContent,
  title: $("board-title").textContent,
  sub: $("board-sub").textContent,
  railHidden: $("board-rail").hidden,
  rail: $("board-rail").childElementCount,
  cards: $("plan-tasks").childElementCount,
  cardCancel: (() => { const kids = $("plan-tasks").firstChild._children;
                       return kids[kids.length - 1].textContent; })(),
  tipHidden: $("run-tip").hidden,
  tip: $("run-tip").textContent,
  toggleHidden: $("btn-toggle-list").hidden,
  toggleText: $("btn-toggle-list").textContent,
  expanded: $("btn-toggle-list")["attr_aria-expanded"],
  listHidden: $("today-items").hidden,
  fbarHidden: $("fbar").hidden,
  barTitle: $("bar-title").textContent,
});
$("btn-toggle-list").click();
out.push([$("today-items").hidden, $("btn-toggle-list").textContent,
          $("btn-toggle-list")["attr_aria-expanded"]]);
""")
        row, expanded = values
        # 沙箱的 createElement 对同标签返回共享实例，重复元素（卡/站台）的动态内容不可逐个读；
        # 每场结论与四站标签由 RunWaitModelTests 的纯函数用例逐字断言，这里只验结构：
        # 板可见、rail 四站、卡两张、卡上带取消钮，以及 unique id 元素的文案
        self.assertTrue(row["board"], "运行中显示 LED 计划板（G04）")
        self.assertEqual(row["tag"], "等开放")
        self.assertEqual(row["cap"], "开放时间")
        self.assertEqual(row["title"], "甲活动")
        self.assertEqual(row["sub"], "这一批 2 场同时提交，到点自动开始。")
        self.assertFalse(row["railHidden"], "运行中有四站 rail")
        self.assertEqual(row["rail"], 4, "四站＝启动/准备好或打开页面/开放提交/核对结果")
        self.assertEqual(row["cards"], 2, "每场一张卡（G10）")
        self.assertEqual(row["cardCancel"], "取消这一场",
                         "等待场的卡带取消钮（取末尾子元素读，共享实例不逐个读）")
        self.assertFalse(row["tipHidden"])
        self.assertIn("手机能锁屏，电脑不能关机或睡眠", row["tip"])
        self.assertFalse(row["toggleHidden"], "运行中给「查看活动列表」钮")
        self.assertEqual(row["toggleText"], "查看活动列表")
        self.assertEqual(row["expanded"], "false")
        self.assertTrue(row["listHidden"], "运行中活动列表默认收起（RW01）")
        self.assertTrue(row["fbarHidden"])
        self.assertEqual(row["barTitle"], "计划进行中（从手机开始）",
                         "来源标注并入 bar-t（产品注记）")
        self.assertEqual(expanded, [False, "收起活动列表", "true"],
                         "点钮展开列表并随动 aria-expanded/文案")

    def test_cancel_start_asks_in_a_sheet_before_posting(self):
        """RW03（用户决策 1：confirm 上 sheet）：点「取消等待」先弹确认槽（原型 Phone:879 文案），
        「继续等」只收 sheet 不发请求，「取消等待」才发 cancel_start_request；
        成功后保留「已取消这次开始」。"""
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.paired = true;
ui.model.lastOkAt = Date.now();
ui.model.pending = { request_id: "late", at: Date.now(), done: false };
const posts = [];
globalThis.__fetch = async (path, opts) => {
  if (opts && opts.method) posts.push(JSON.parse(opts.body).action);
  return { status: 200, json: async () => ({ ok: true, state: "canceled", request_id: "late" }) };
};
$("btn-cancel-start").click();
out.push({ sheetOpen: !$("sheet-root").hidden, title: $("sheet-title").textContent,
           text: $("confirm-text").textContent,
           no: $("btn-confirm-no").textContent, yes: $("btn-confirm-yes").textContent,
           posts: posts.slice() });
$("btn-confirm-no").click();
out.push({ sheetOpen: !$("sheet-root").hidden, posts: posts.slice() });
$("btn-cancel-start").click();
$("btn-confirm-yes").click();
for (let i = 0; i < 20; i += 1) await Promise.resolve();
out.push({ posts: posts.slice(), pendingDone: ui.model.pending.done,
           banner: $("banner").textContent });
""")
        opened, kept, confirmed = values
        self.assertTrue(opened["sheetOpen"])
        self.assertEqual(opened["title"], "取消这次等待？")
        self.assertEqual(opened["text"],
                         "只是不再等这次结果。如果计划其实已经启动，刷新后还要再点“停止计划”。")
        self.assertEqual([opened["no"], opened["yes"]], ["继续等", "取消等待"])
        self.assertEqual(opened["posts"], [], "确认之前不发任何写动作")
        self.assertFalse(kept["sheetOpen"], "「继续等」只收起确认槽")
        self.assertEqual(kept["posts"], [])
        self.assertEqual(confirmed["posts"], ["cancel_start_request"])
        self.assertTrue(confirmed["pendingDone"])
        self.assertIn("已取消这次开始", confirmed["banner"], "成功句保留")


class ListDetailModelTests(unittest.TestCase):
    """G05/G07/G08/G09/LD01–LD04：列表分组、距开放、段钮计数、草稿板与勾选冲突。

    全部走 PhoneModel 纯函数（node vm 跑真实 app.js）——分组/距离/计数是前端聚合，
    渲染函数只做 DOM，所以断言直接调函数，不搜字符串。"""

    def _items(self):
        # “现在”固定为北京时间 2026-11-08 14:00；场次时间都是学校本地时间文本
        return [
            {"id": "o1", "name": "即时场", "place": "学生事务中心",
             "sign_start": "2026-11-08 10:00:00",
             "act_start": "2026-11-08 19:00:00", "act_end": "2026-11-08 21:00:00"},
            {"id": "t1", "name": "甲场", "place": "报告厅",
             "sign_start": "2026-11-08 20:00:00",
             "act_start": "2026-11-08 19:00:00", "act_end": "2026-11-08 21:00:00"},
            {"id": "t2", "name": "乙场", "place": "报告厅",
             "sign_start": "2026-11-08 22:00:00",
             "act_start": "2026-11-08 20:00:00", "act_end": "2026-11-08 22:00:00"},
            {"id": "m1", "name": "明天场", "sign_start": "2026-11-09 09:00:00"},
            {"id": "w1", "name": "后天场", "sign_start": "2026-11-10 09:00:00"},
            {"id": "f1", "name": "大后天场", "sign_start": "2026-11-13 09:00:00"},
            {"id": "u1", "name": "待公布场", "sign_start": ""},
            {"id": "s1", "name": "已报名场", "sign_start": "2026-11-08 08:00:00", "signed": True},
            {"id": "c1", "name": "已截止场", "sign_start": "2026-11-08 08:00:00",
             "sign_end": "2026-11-08 12:00:00"},
        ]

    def _view(self, items, selected=None, busy=False, now_s=True):
        return run_phone_js("""
const items = %s;
const nowS = Date.UTC(2026, 10, 8, 6, 0, 0) / 1000;   /* 北京时间 11-08 14:00 */
const view = PhoneModel.listView(items, { q: "", status: "all", time: "all" },
  { nowS: %s, wallS: nowS, selected: %s, busy: %s });
out.push(view.groups.map((g) => [g.title, g.note, g.n, g.cls, g.nowBefore].join("|")));
out.push([view.counts.free, view.counts.signed, view.counts.all]);
out.push(view.groups.map((g) => g.now));
out.push(view.groups.map((g) => g.rows.map((r) => r.id + ":" +
  r.flags.map((f) => f.text + ":" + f.cls).join(",")).join(" ")));
const o = view.groups[0].rows[0];
out.push([o.time, o.left, o.leftCls, o.timeCls, o.place]);
const t = view.groups[1].rows[0];
out.push([t.time, t.left]);
const c = view.groups[view.groups.length - 1].rows[0];
out.push([c.time, c.disabled, c.cls.indexOf("dim") >= 0]);
""" % (json.dumps(items, ensure_ascii=False),
       "nowS" if now_s else "null",
       json.dumps(selected or [], ensure_ascii=False),
       "true" if busy else "false"))

    def test_groups_counts_flags_and_nowline_follow_prototype(self):
        """G07/G08：组名序、组注、计数、「现在」分隔行与旗标（原型 Phone:413-423/728-763/931）。"""
        groups, counts, nows, rows, open_row, pre_row, closed_row = self._view(self._items())
        # 原型组名序；「更晚开放」是真实列表超出原型演示范围（只到后天）时的归组，不丢行
        self.assertEqual([g.split("|")[0] for g in groups],
                         ["正在开放", "今天", "明天", "后天", "待公布", "更晚开放", "已报名", "已截止"])
        self.assertEqual(groups[0], "正在开放|现在就能报|1|open|false")
        self.assertEqual(groups[1], "今天||2||true", "首个非开放组前插「现在」分隔行")
        self.assertEqual(groups[-1], "已截止|只能查看|1||false")
        self.assertEqual(counts, [6, 1, 9], "计数对全部活动按开放状态聚合（free=open+pre）")
        self.assertEqual(nows[1], "14:00", "「现在 {HH:MM}」用业务北京时间")
        self.assertEqual(rows[0], "o1:立即报名:warn")
        self.assertEqual(rows[1], "t1:下一场:next t2:预报名:", "最早开放且不撞已报名的 pre 场是「下一场」")
        self.assertEqual(rows[6], "s1:已报名:signed")
        self.assertEqual(rows[7], "c1:已截止:mute")
        self.assertEqual(open_row, ["10:00", "已开放", "", "", "学生事务中心"],
                         "时刻大字是开放的北京时间 HH:MM；已开放行带地点")
        self.assertEqual(pre_row, ["20:00", "6 时 0 分"], "距开放照原型 leftCn")
        self.assertEqual(closed_row, ["08:00", True, True], "已截止行不可勾并整行变暗")

    def test_row_left_countdown_soon_and_clock_down(self):
        """G05 距开放：原型 leftCn 分档；<10 分钟 soon 橙色；时钟不可用写「待校准」。"""
        values = run_phone_js("""
out.push(PhoneModel.leftCn(95));
out.push(PhoneModel.leftCn(3600 * 5 + 60));
out.push(PhoneModel.leftCn(3600 * 10));
out.push(PhoneModel.leftCn(3600 * 11));
out.push(PhoneModel.leftCn(45));
out.push(PhoneModel.leftCn(-3));
const items = [{ id: "s0", name: "马上开放", sign_start: "2026-11-08 14:05:00" }];
const nowS = Date.UTC(2026, 10, 8, 6, 0, 0) / 1000;
const soon = PhoneModel.listView(items, {}, { nowS: nowS, wallS: nowS, selected: [], busy: false });
out.push([soon.groups[0].rows[0].left, soon.groups[0].rows[0].leftCls]);
const down = PhoneModel.listView(items, {}, { nowS: null, wallS: nowS, selected: [], busy: false });
out.push([down.groups[0].rows[0].left, down.groups[0].rows[0].leftCls,
          down.groups[0].rows[0].flags.map((f) => f.text)]);
""")
        # 原型 leftCn（Phone.dc.html:369-376）逐字：≥10 小时取整小时，不足 1 小时带秒
        self.assertEqual(values[:6], ["1 分 35 秒", "5 时 1 分", "10 小时后", "11 小时后", "45 秒", "0 秒"])
        self.assertEqual(values[6], ["5 分 0 秒", "soon"], "<10 分钟标 soon 橙色")
        self.assertEqual(values[7], ["待校准", "", ["下一场"]],
                         "时钟不可用写待校准，不读手机墙钟凑倒计时")

    def test_pick_conflict_keeps_selection_and_warns(self):
        """LD04（原型 toggle，Phone:700）：撞场保留原选择并给提示条；行警 busy 时不显。"""
        items = [
            {"id": "t1", "name": "甲场", "sign_start": "2026-11-08 20:00:00",
             "act_start": "2026-11-08 19:00:00", "act_end": "2026-11-08 21:00:00"},
            {"id": "t2", "name": "乙场", "sign_start": "2026-11-08 22:00:00",
             "act_start": "2026-11-08 20:00:00", "act_end": "2026-11-08 22:00:00"},
            {"id": "t3", "name": "丙场", "sign_start": "2026-11-09 09:00:00",
             "act_start": "2026-11-09 19:00:00", "act_end": "2026-11-09 21:00:00"},
        ]
        values = run_phone_js("""
const items = %s;
const nowS = Date.UTC(2026, 10, 8, 6, 0, 0) / 1000;
const first = PhoneModel.pickItem([], items, "t1", true);
out.push(first.selected);
const second = PhoneModel.pickItem(first.selected, items, "t2", true);
out.push([second.selected, second.notice]);
const off = PhoneModel.pickItem(second.selected, items, "t2", false);
out.push([off.selected, off.notice]);
const view = PhoneModel.listView(items, {}, { nowS: nowS, wallS: nowS, selected: ["t1"], busy: false });
const row2 = view.groups[0].rows.find((r) => r.id === "t2");
out.push([row2.warn, row2.hasWarn, row2.selected]);
const busyView = PhoneModel.listView(items, {}, { nowS: nowS, wallS: nowS, selected: ["t1"], busy: true });
out.push(busyView.groups[0].rows.find((r) => r.id === "t2").hasWarn);
""" % json.dumps(items, ensure_ascii=False))
        self.assertEqual(values[0], ["t1"])
        self.assertEqual(values[1], [["t1"],
                                     "「乙场」与「甲场」的活动时间重叠，只能选其中一场。已保留原选择。"],
                         "撞场时保留原选择，不静默禁用")
        self.assertEqual(values[2], [["t1"], ""], "取消勾选清掉提示")
        self.assertEqual(values[3], ["与已选的「甲场」时间重叠", True, False], "G05 行警")
        self.assertFalse(values[4], "busy 时行警不显")

    def test_draft_board_confirms_selection_and_next_pick(self):
        """LD01/LD02（原型 draft 分支，Phone:783-794）：已选确认页、未选详情卡、待校准与空档。"""
        items = [
            {"id": "o1", "name": "开放中的讲座", "place": "学生事务中心",
             "sign_start": "2026-11-08 10:00:00",
             "act_start": "2026-11-08 19:00:00", "act_end": "2026-11-08 21:00:00"},
            {"id": "p1", "name": "下一场讲座", "place": "图书馆报告厅",
             "sign_start": "2026-11-08 20:00:00",
             "act_start": "2026-11-08 19:00:00", "act_end": "2026-11-08 21:00:00"},
        ]
        values = run_phone_js("""
const items = %s;
const nowS = Date.UTC(2026, 10, 8, 6, 0, 0) / 1000;
const picked = PhoneModel.draftBoard(items, nowS, ["p1"]);
out.push([picked.tag, picked.title, picked.sub, picked.led.cap, picked.led.capB, picked.pickId]);
const openPicked = PhoneModel.draftBoard(items, nowS, ["o1"]);
out.push([openPicked.led.cap, openPicked.led.capB]);
const next = PhoneModel.draftBoard(items, nowS, []);
out.push([next.tag, next.title, next.sub, next.pickId, next.led.cap, next.led.capB]);
const down = PhoneModel.draftBoard(items, null, ["p1"]);
out.push([down.led.tone, down.led.cap]);
const none = PhoneModel.draftBoard([{ id: "s9", name: "已报名", signed: true }], nowS, []);
out.push([none.tag, none.title, none.pickId]);
""" % json.dumps(items, ensure_ascii=False))
        self.assertEqual(
            values[0],
            ["已选 1 场", "核对后再开始", "勾选不会开始报名。", "下一批开放", "20:00:00", ""],
            "LD01：板头计数 + 板题副题 + LED 下一批倒计时")
        self.assertEqual(values[1], ["已开放，可以立即报名", "现在"], "选的全是已开放场：LED 不再倒计时")
        self.assertEqual(
            values[2],
            ["开放中", "开放中的讲座", "学生事务中心，11月8日 19:00–21:00", "o1",
             "已开放，可以立即报名", "现在"],
            "LD02：未选时给下一场详情卡（地点，时段）与「选这一场」")
        self.assertEqual(values[3], ["off", "电脑上的北京时间待校准"], "时钟不可用只给待校准屏")
        self.assertEqual(values[4], ["暂时没有", "没有可报名的场次", ""])

    def test_list_notice_and_search_toggle(self):
        """LD04 提示条显示在列表区（role=alert）；LD03 搜索钮开合整页搜索并清关键词。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.model.items = [
  { id: "a", name: "甲场", sign_start: "2026-11-08 20:00:00",
    act_start: "2026-11-08 19:00:00", act_end: "2026-11-08 21:00:00" },
  { id: "b", name: "乙场", sign_start: "2026-11-08 22:00:00",
    act_start: "2026-11-08 20:00:00", act_end: "2026-11-08 22:00:00" },
];
ui.model.selected = ["a"];
const res = PhoneModel.pickItem(ui.model.selected, ui.model.items, "b", true);
ui.model.selected = res.selected;
ui.model.notice = res.notice;
ui.renderItems();
out.push([$("list-notice").textContent, $("list-notice").hidden]);
$("btn-search").click();
out.push([$("search-view").hidden, ui.model.filter.q, $("btn-search")["attr_aria-expanded"]]);
$("search-q").value = "乙";
$("search-q").listeners.input[0]();
out.push([ui.model.filter.q, $("q").value]);
''')
        self.assertEqual(
            values[0],
            ["「乙场」与「甲场」的活动时间重叠，只能选其中一场。已保留原选择。", False],
            "LD04 提示条在列表区可见")
        self.assertEqual(values[1], [False, "", "true"], "搜索钮展开整页搜索并清空关键词")
        self.assertEqual(values[2], ["乙", "乙"], "搜索框与折叠内 #q 写同一个关键词")


class SheetShellTests(unittest.TestCase):
    """G03 sheet 外壳：开/关与焦点归还、验证中不关（busyLock）、SH06 网络失败红条。"""

    def test_open_close_switch_and_busy_lock(self):
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.openSheet("more");
out.push([$("sheet-root").hidden, $("sheet-title").textContent,
          $("more-panel").hidden, $("review-panel").hidden]);
ui.closeSheet();
out.push([$("sheet-root").hidden, $("more-panel").hidden, $("review-panel").hidden]);
ui.openSheet("review");
out.push([$("sheet-root").hidden, $("review-panel").hidden, $("more-panel").hidden,
          $("sheet-title").textContent]);
ui.model.reloginSubmitting = true;        // 验证中：Esc、点遮罩、关闭钮都不收
ui.closeSheet();
out.push([$("sheet-root").hidden, $("btn-sheet-close").hidden]);
ui.closeSheet(true);                      // force（比如确认后真的开始）仍能收
out.push($("sheet-root").hidden);
ui.model.reloginSubmitting = false;
ui.openSheet("more");
ui.closeSheet();
out.push($("sheet-root").hidden);
''')
        self.assertEqual(values[0], [False, "更多", False, True])
        self.assertEqual(values[1], [True, True, True])
        self.assertEqual(values[2], [False, False, True, "核对计划"])
        self.assertEqual(values[3], [False, True], "验证中不关，且关闭钮藏起来")
        self.assertTrue(values[4], "force 关闭不受 busyLock 限制")
        self.assertTrue(values[5], "验证结束后恢复可关")

    def test_open_rejects_unknown_and_double_open(self):
        # vm 装置的元素默认 hidden:false，没被 JS 写过的属性不可断言：
        # 「没开」改读 model.sheetId，开关结果再读元素
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.openSheet("nope");
out.push(ui.model.sheetId);
ui.openSheet("more");
ui.openSheet("review");                   // 一次只开一张
out.push([ui.model.sheetId, $("more-panel").hidden, $("review-panel").hidden]);
''')
        self.assertEqual(values[0], "", "未知 sheet 不开")
        self.assertEqual(values[1], ["more", False, True], "已开着时不再换内容")

    def test_relogin_entry_switches_from_an_open_sheet(self):
        """A-P1：更多面板开着时点「在手机上重新登录」要能切到重登 sheet——
        openRelogin 先收旧 sheet 再开重登（openSheet 的「一次一张」守卫曾把
        这次切换拦掉，入口钮点不动）；旧面板收起、sheet 根仍开着。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.openSheet("more");
out.push([ui.model.sheetId, $("more-panel").hidden]);
$("btn-relogin-open").click();            // 更多面板里的入口钮
out.push([ui.model.sheetId, $("sheet-title").textContent, $("more-panel").hidden,
          $("relogin-panel").hidden, $("relogin-foot").hidden, $("sheet-root").hidden]);
''')
        self.assertEqual(values[0], ["more", False])
        self.assertEqual(values[1], ["relogin", "在手机上重新登录", True, False, False, False],
                         "从 more 切到 relogin：more 收起、重登面板与页脚可见")

    def test_relogin_fields_are_cleared_when_the_sheet_closes(self):
        """SEC-P3-3：重登 sheet 收起（含「取消」路径）即清账号/密码/验证码输入，
        重开时不得残留上一轮的密码。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.openSheet("relogin");
$("relogin-user").value = "u1";
$("relogin-pass").value = "p1";
$("code").value = "ab12";
ui.closeSheet(true);
out.push([$("relogin-user").value, $("relogin-pass").value, $("code").value]);
ui.openSheet("relogin");
out.push([$("relogin-user").value, $("relogin-pass").value, $("code").value]);
ui.closeSheet(true);
ui.openSheet("relogin");
$("relogin-pass").value = "p2";
$("btn-relogin-cancel").click();          // 取消路径：先撤流程再收 sheet
for (let i = 0; i < 10; i += 1) await Promise.resolve();
out.push([$("relogin-user").value, $("relogin-pass").value, $("code").value]);
''')
        self.assertEqual(values, [["", "", ""], ["", "", ""], ["", "", ""]],
                         "收起即清空（force 关与取消路径都算），重开不残留")

    def test_network_failure_shows_red_bar_in_sheet(self):
        """SH06：sheet 开着时写动作发不出去，红条就地说明；关掉 sheet 红条清空。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.model.selected = ["a1"];
ui.openSheet("review");
globalThis.__fetch = async () => { throw new Error("offline"); };
await ui.startPlan();
out.push([$("sheet-err").hidden, $("sheet-err").textContent]);
ui.closeSheet();
ui.openSheet("review");
out.push($("sheet-err").hidden);
''')
        self.assertEqual(
            values[0],
            [False, "网络不通，这次操作没有发出去。电脑上的计划还在跑，恢复连接后再试。"])
        self.assertTrue(values[1], "重开 sheet 不把上一张的错误带过来")

    def test_network_failure_without_sheet_keeps_banner_path(self):
        """没开 sheet 时写动作失败仍走主屏 banner，不冒出空红条。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.model.selected = ["a1"];
globalThis.__fetch = async () => { throw new Error("offline"); };
await ui.startPlan();
out.push([$("sheet-err").textContent, $("banner").hidden]);
''')
        # sheet-err 不被写入（无 sheet 时不冒红条），banner 照旧兜底
        self.assertEqual(values, [["", False]])


class SheetsOpsModelTests(unittest.TestCase):
    """SH01/SH02/SH05 纯函数层：核对批次头三支（batchMap）、提醒三支（pwList）、登录行四态（loginLine）。"""

    def test_review_batches_follow_prototype_batch_map(self):
        """SH01 批次头三支（原型 batchMap，Phone.dc.html:767-779）：已开放（stOf=open）
        同归「现在」批＝立即报名 N 场；未开放按开放时刻分批——同时刻同批＝
        预报名，同时提交 N 场、单场＝预报名 1 场；时刻 HH:MM:SS（跨天带日前缀，
        原型 hms(open) 的等价换算）；移除 aria=从计划移除 {名}；条目带「活动 {时段}」。"""
        items = [
            {"id": "o1", "name": "乙场", "sign_start": "2026-11-08 10:00:00",
             "act_start": "2026-11-08 19:00:00", "act_end": "2026-11-08 21:00:00"},
            {"id": "o2", "name": "甲场", "sign_start": "2026-11-08 09:00:00"},
            {"id": "t1", "name": "丙场", "sign_start": "2026-11-08 20:00:00"},
            {"id": "t2", "name": "丁场", "sign_start": "2026-11-08 20:00:00"},
            {"id": "m1", "name": "明天场", "sign_start": "2026-11-09 09:00:00"},
        ]
        values = run_phone_js("""
const nowS = Date.UTC(2026, 10, 8, 6, 0, 0) / 1000;   /* 北京时间 11-08 14:00 */
const batches = PhoneModel.reviewBatches(%s, nowS);
out.push(batches.map((b) => [b.time, b.note, b.items.length].join("|")));
out.push(batches.map((b) => b.items.map((i) => i.aria).join(",")));
out.push([batches[0].items[1].act, batches[2].items[0].act]);
""" % json.dumps(items, ensure_ascii=False))
        heads, arias, acts = values
        self.assertEqual(heads, [
            "现在|立即报名 2 场|2",
            "20:00:00|预报名，同时提交 2 场|2",
            "明天 09:00:00|预报名 1 场|1",
        ])
        self.assertEqual(arias, [
            "从计划移除 甲场,从计划移除 乙场",
            "从计划移除 丙场,从计划移除 丁场",
            "从计划移除 明天场",
        ], "批内按开放时刻升序（原型 sel.sort）")
        self.assertEqual(acts, ["活动 11月8日 19:00–21:00", "开放 2026-11-09 09:00:00"],
                         "条目「活动 {时段}」；缺举办时段回退「开放 …」（记 deviation）")

    def test_pre_start_warnings_follow_prototype_pw_list(self):
        """SH02 提醒三支（原型 pwList，Phone.dc.html:912-916 逐字）：retry=0 缺截止
        只点第一场（原型 pwNe[0]，多场其余不点名记 deviation）；等待久按
        保存账号×识别 分「没装验证码识别/输验证码」与「没开自动登录/重新登录」两支
        （保存的密码不对并入「没有」支）；24 小时句独立成条。"""
        values = run_phone_js("""
const items = [
  {id: "a1", name: "甲活动", seconds_to_open: 7200, sign_start: "2026-11-08 16:00:00"},
  {id: "a2", name: "乙活动", seconds_to_open: 90000, sign_start: "2026-11-09 15:00:00"},
  {id: "a3", name: "丙活动", seconds_to_open: 172800, sign_start: "2026-11-10 14:00:00"}];
const mk = (retry, setup, picked) => PhoneModel.preStartWarnings(
  {clockState: "ready", retry: {retry_for_s: retry}, reloginSetup: setup}, picked || items);
out.push(mk(0, {saved: true, ocr_ready: true, paused: false},
            [{id: "n1", name: "无截止场", seconds_to_open: 600},
             {id: "n2", name: "也没截止", seconds_to_open: 700}]));
out.push(mk(0, {saved: false, ocr_ready: true, paused: false},
            [{id: "n2", name: "也没截止", seconds_to_open: 700}]));
out.push(mk(120, {saved: true, ocr_ready: false, paused: false}));
out.push(mk(120, {saved: false, ocr_ready: false, paused: false}));
out.push(mk(120, {saved: true, ocr_ready: true, paused: false}));
out.push(mk(120, {saved: true, ocr_ready: true, paused: true}));
""")
        no_end_two, no_end_one, wait_saved, wait_unsaved, wait_ok, wait_paused = values
        self.assertEqual(no_end_two, [
            "「无截止场」没给报名截止时间，“直到报名截止”对它只会尝试 2 分钟。"])
        self.assertEqual(no_end_one, [
            "「也没截止」没给报名截止时间，“直到报名截止”对它只会尝试 2 分钟。"])
        self.assertEqual(wait_saved, [
            "要等到 14:00，电脑上没装验证码识别。中途登录失效要你输验证码；开放前 100 秒内失效，那场就结束。",
            "有场次在 24 小时后才开放，电脑要开着、不能睡眠。"])
        self.assertEqual(wait_unsaved, [
            "要等到 14:00，电脑上没开自动登录。中途登录失效要你重新登录；开放前 100 秒内失效，那场就结束。",
            "有场次在 24 小时后才开放，电脑要开着、不能睡眠。"])
        self.assertEqual(wait_ok, [
            "有场次在 24 小时后才开放，电脑要开着、不能睡眠。"],
            "有保存账号且装了识别：不提醒等待久（原型 !(pwHas&&ocrOn)），24 小时句独立")
        self.assertEqual(wait_paused[0],
                         "要等到 14:00，电脑上没开自动登录。中途登录失效要你重新登录；开放前 100 秒内失效，那场就结束。",
                         "保存的密码不对（paused）并入「没保存账号」支")

    def test_pre_start_warning_carries_day_prefix(self):
        """UI-F4（原型 pwHas 句 hms(pwLast).slice(0,-3)，Phone:915）：「要等到」带
        明天/后天日前缀——丢前缀会把「明天 13:00」说成「13:00」。"""
        values = run_phone_js("""
const nowS = Math.floor(Date.UTC(2026, 10, 8, 4, 0, 0) / 1000);  /* 北京 11-08 12:00 */
const model = { clockState: "ready", retry: {retry_for_s: 120},
  reloginSetup: {saved: false, ocr_ready: false, paused: false} };
PhoneModel.setClock(model, {state: "ready", epoch_s: nowS,
  tick_s: 1000, sampled_tick_s: 1000});
const items = [{id: "a1", name: "甲", seconds_to_open: 90000,
  sign_start: "2026-11-09 13:00:00"}];
out.push(PhoneModel.preStartWarnings(model, items));
""")
        self.assertTrue(values[0], "等待久提醒成立（前置）")
        self.assertIn("要等到明天 13:00，", values[0][0],
                      "目标时刻带「明天」日前缀（UI-F4）")

    def test_login_line_four_states_follow_prototype(self):
        """SH05 登录行四态（原型 loginLine，Phone.dc.html:937 逐字）：
        前半句按登录态（session_expired/session_present），后半句按 保存账号×识别 四组合；
        保存的密码不对（paused）并入「没保存账号」支（与 relNeedAcct 同口径）。"""
        values = run_phone_js("""
const mk = (login, setup) => PhoneModel.loginLine(login, setup);
out.push(mk({session_present: true}, {saved: true, ocr_ready: true, paused: false}));
out.push(mk({session_present: true}, {saved: true, ocr_ready: false, paused: false}));
out.push(mk({session_present: true}, {saved: false, ocr_ready: true, paused: false}));
out.push(mk({session_present: true}, {saved: false, ocr_ready: false, paused: false}));
out.push(mk({session_expired: true, session_present: true}, {saved: true, ocr_ready: true, paused: false}));
out.push(mk(null, null));
out.push(mk({session_present: true}, {saved: true, ocr_ready: true, paused: true}));
""")
        valid_ocr, valid_cap, nosave_ocr, nosave_cap, expired, bare, paused = values
        self.assertEqual(valid_ocr, "电脑上的登录有效。失效时电脑会自己重新登录。")
        self.assertEqual(valid_cap, "电脑上的登录有效。失效时只需在这里输验证码。")
        self.assertEqual(nosave_ocr, "电脑上的登录有效。电脑上没保存账号，重新登录要输账号和密码。")
        self.assertEqual(nosave_cap, "电脑上的登录有效。电脑上没保存账号，重新登录要输账号、密码和验证码。")
        self.assertEqual(expired, "电脑上的登录已失效。失效时电脑会自己重新登录。")
        self.assertEqual(bare, "电脑上的登录有效。电脑上没保存账号，重新登录要输账号、密码和验证码。",
                         "快照没到手：按未失效、未保存呈现，不猜")
        self.assertEqual(paused, "电脑上的登录有效。电脑上没保存账号，重新登录要输账号和密码。")


class SheetsOpsDomTests(unittest.TestCase):
    """SH01 移除钮反选与 SH03/SH04 确认槽的 DOM 层（最小受控 DOM）。"""

    def test_review_remove_toggles_off_and_closes_when_empty(self):
        """SH01 移除钮（原型 tk.remove，Phone:771）：事件委托按 dataset.id 走现有勾选反选，
        不发任何写动作；移除后底栏「已选 N 场」随动，计划空了就关 sheet。"""
        values = run_phone_js('''
const ui = PhoneUI;
const posts = [];
globalThis.__fetch = async (path, opts) => {
  if (opts && opts.method) posts.push(JSON.parse(opts.body).action);
  return {status: 200, json: async () => ({state: {}, events: []})};
};
ui.model.lastOkAt = Date.now();
ui.ingest({state: {terms_ok: true, busy: false, activities: [
  {id: "a1", name: "甲活动", sign_start: "2026-11-08 20:00:00"},
  {id: "a2", name: "乙活动", sign_start: "2026-11-09 09:00:00"}]}});
ui.model.selected = ["a1", "a2"];
ui.refreshControls();
$("btn-start").click();
const opened = {sheet: !$("sheet-root").hidden, title: $("sheet-title").textContent};
/* vm 沙箱同标签元素共享实例：移除钮不带自身监听（委托在 #review-items 上），
   这里直接给委托监听喂 {target: 带 dataset.id 的钮}，与真实点击同一代码路径 */
const btn = document.createElement("button");
btn.dataset.id = "a1";
$("review-items").listeners.click[0]({ target: btn });
const afterOne = {selected: ui.model.selected.slice(), sheet: !$("sheet-root").hidden,
                  bar: $("bar-title").textContent, posts: posts.slice()};
btn.dataset.id = "a2";
$("review-items").listeners.click[0]({ target: btn });
const afterAll = {selected: ui.model.selected.slice(), sheet: !$("sheet-root").hidden};
out.push({opened, afterOne, afterAll});
''')
        opened, after_one, after_all = (values[0]["opened"], values[0]["afterOne"],
                                        values[0]["afterAll"])
        self.assertTrue(opened["sheet"])
        self.assertEqual(opened["title"], "核对计划")
        self.assertEqual(after_one["selected"], ["a2"], "移除＝勾选反选，另一场保留")
        self.assertTrue(after_one["sheet"], "还有场次时核对 sheet 不关")
        self.assertEqual(after_one["bar"], "已选 1 场", "底栏计数随动")
        self.assertEqual(after_one["posts"], [], "移除不发任何写动作")
        self.assertEqual(after_all["selected"], [])
        self.assertFalse(after_all["sheet"], "移除后计划空了就关 sheet（原型 setState sheet:''）")

    def test_stop_and_cancel_task_confirm_sheets_follow_prototype(self):
        """SH03/SH04 确认槽（原型 isConfirm，Phone.dc.html:874-877）：
        停止＝题/文/双钮逐字（继续计划/停止计划，红 b-stop）；
        取消一场＝文案带活动名。确认之前不发任何写动作。"""
        values = run_phone_js('''
const ui = PhoneUI;
const posts = [];
globalThis.__fetch = async (path, opts) => {
  if (opts && opts.method) posts.push(JSON.parse(opts.body).action);
  return {status: 200, json: async () => ({ok: true})};
};
ui.model.lastOkAt = Date.now();
ui.askConfirm("stop");
out.push({title: $("sheet-title").textContent, text: $("confirm-text").textContent,
          no: $("btn-confirm-no").textContent, yes: $("btn-confirm-yes").textContent,
          posts: posts.slice()});
ui.closeSheet(true);
ui.askConfirm("cancelTask", "甲活动");
out.push({title: $("sheet-title").textContent, text: $("confirm-text").textContent,
          no: $("btn-confirm-no").textContent, yes: $("btn-confirm-yes").textContent});
ui.closeSheet(true);
out.push(ui.model.confirm);
''')
        stop, cancel, closed = values
        self.assertEqual(stop["title"], "停止报名计划？")
        self.assertEqual(stop["text"],
                         "工具会停止后续尝试。已经发出的提交仍可能成功，停止不会取消已成功的报名。")
        self.assertEqual([stop["no"], stop["yes"]], ["继续计划", "停止计划"])
        # 停止钮红色是静态标记（vm 沙箱元素不解析 class）：照原型 b-stop（Phone:313）查源码
        html = (PHONE_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="btn-confirm-yes" class="b b-stop"', html)
        self.assertEqual(stop["posts"], [], "确认槽只呈现，不发动作")
        self.assertEqual(cancel["title"], "取消这一场？")
        self.assertEqual(cancel["text"], "「甲活动」还没提交，取消后不会再报名，其他场次继续。")
        self.assertEqual([cancel["no"], cancel["yes"]], ["先不取消", "取消这一场"])
        self.assertIsNone(closed, "收 sheet 时确认档一并清掉")

    def test_cancel_task_posts_the_tapped_card_task_id(self):
        """B-P1-1：取消一场发被点卡片那一场的 task_id——后端（Api.cancel_task→
        PlanCoordinator.cancel_task→phone_rules 白名单）本就收任意 task_id，
        桌面端也早在发任意 taskId，前端不再固定发 tasks[0]。确认槽记住 taskId，
        确认后随 cancel_task 原样发出；卡上取消钮按场次传 task_id 用源码钉住
        （vm 沙箱同标签元素共享实例，逐卡点击不可读）。"""
        values = run_phone_js('''
const ui = PhoneUI;
const posts = [];
ui.model.lastOkAt = Date.now();
const running = { busy: true, plan: { plan_id: "p1", status: "running", source: "phone",
  tasks: [
    { task_id: "t1", name: "甲活动", status: "waiting", signup_mode: "pre_register",
      sign_start: "2026-11-09 14:30:00", path: "direct" },
    { task_id: "t2", name: "乙活动", status: "waiting", signup_mode: "pre_register",
      sign_start: "2026-11-09 14:30:00", path: "direct" }] },
  activities: [] };
globalThis.__fetch = async (path, opts) => {
  if (opts && opts.method) posts.push(JSON.parse(opts.body));
  return { status: 200, json: async () => ({ state: running, events: [] }) };
};
await ui.poll(true);
out.push({ cards: $("plan-tasks").childElementCount });
/* 第二张卡的取消钮做的事＝askConfirm("cancelTask", "乙活动", "t2")： */
ui.askConfirm("cancelTask", "乙活动", "t2");
out.push({ slot: ui.model.confirm, text: $("confirm-text").textContent });
$("btn-confirm-yes").click();
for (let i = 0; i < 20; i += 1) await Promise.resolve();
out.push({ posts: posts.filter((p) => p.action === "cancel_task").slice() });
''')
        js = (PHONE_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn('askConfirm("cancelTask", card.name, task.task_id)', js,
                      "卡上取消钮按被点场次传 task_id（B-P1-1）")
        cards, slot, posted = values
        self.assertEqual(cards["cards"], 2, "多场计划：每场一张卡")
        self.assertEqual(slot["slot"], {"kind": "cancelTask", "taskId": "t2"},
                         "确认槽记住被点卡片的 task_id")
        self.assertIn("「乙活动」", slot["text"], "确认文案带对应场名")
        self.assertEqual(posted["posts"],
                         [{"action": "cancel_task",
                           "args": {"plan_id": "p1", "task_id": "t2"}}],
                         "发出的是被点卡片的 task_id，不是 tasks[0]")

    def test_confirm_action_failure_keeps_the_sheet_with_red_bar(self):
        """UI-F5：确认动作失败不静默收场——confirm sheet 保持打开，失败句写进
        #sheet-err（SH06 showSheetError），双钮重新可点；成功才收 sheet。"""
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const posts = [];
let mode = "fail";
globalThis.__fetch = async (path, opts) => {
  if (opts && opts.method) posts.push(JSON.parse(opts.body).action);
  return {status: 200, json: async () => mode === "fail"
    ? {ok: false, error: "busy", text: "计划在运行，先停下来再取消"}
    : {ok: true}};
};
ui.model.plan = {plan_id: "p1", tasks: []};
ui.askConfirm("stop");
$("btn-confirm-yes").click();
for (let i = 0; i < 20; i += 1) await Promise.resolve();
out.push({ sheet: !$("sheet-root").hidden, errShown: !$("sheet-err").hidden,
           err: $("sheet-err").textContent, yesDisabled: $("btn-confirm-yes").disabled,
           posts: posts.slice() });
mode = "ok";
$("btn-confirm-yes").click();             // 失败后可重试：这次成功收 sheet
for (let i = 0; i < 20; i += 1) await Promise.resolve();
out.push({ sheet: !$("sheet-root").hidden, posts: posts.slice() });
''')
        failed, retried = values
        self.assertTrue(failed["sheet"], "失败时确认 sheet 保持打开")
        self.assertTrue(failed["errShown"])
        self.assertEqual(failed["err"], "没能停止计划：计划在运行，先停下来再取消",
                         "失败句就地写进 #sheet-err")
        self.assertFalse(failed["yesDisabled"], "双钮重新放开，可重试")
        self.assertEqual(failed["posts"], ["stop_plan"])
        self.assertFalse(retried["sheet"], "成功才收 sheet")
        self.assertEqual(retried["posts"], ["stop_plan", "stop_plan"])


class ResultTermsModelTests(unittest.TestCase):
    """RS01/RS02/TM01：结果页统计与六支板头、任务卡原因三句、条款板（result-and-terms 任务）。

    全部走 PhoneModel 纯函数（node vm 跑真实 app.js），渲染函数只做 DOM；
    统计口径＝plan.tasks 的 status/stop_reason 前端聚合（名额已满=failed+full、
    待核对=failed+unconfirmed、未成功=其余 failed、已取消=canceled），与 taskText 一致；
    stopped 取计划级 status（signup_plan 停止后的终态快照即 stopped）。"""

    def test_result_view_counts_and_heads_follow_prototype(self):
        """RS01（原型 res 段，Phone.dc.html:828-840）：五类统计只显非零、tone ok/wait/bad/ask/wait
        照 res.counts（832）；六支板头照 834-839 逐支；canRetry=未成功+已取消（833）；
        未全部终态/在跑/没有计划都不出结果页。"""
        values = run_phone_js("""
const mk = (status, extra) => Object.assign({ status: status }, extra || {});
out.push(PhoneModel.resultView(
  { status: "completed", tasks: [mk("success"), mk("already_signed")] }, false));
out.push(PhoneModel.resultView({ status: "partial", tasks: [
  mk("success"), mk("failed", { stop_reason: "full" }),
  mk("failed", { stop_reason: "unconfirmed" }), mk("failed"), mk("canceled")] }, false));
out.push(PhoneModel.resultView(
  { status: "partial", tasks: [mk("success"), mk("failed", { stop_reason: "full" })] }, false).text);
out.push(PhoneModel.resultView(
  { status: "partial", tasks: [mk("success"), mk("canceled")] }, false).text);
out.push(PhoneModel.resultView(
  { status: "stopped", tasks: [mk("success"), mk("canceled")] }, false));
out.push(PhoneModel.resultView(
  { status: "stopped", tasks: [mk("failed", { stop_reason: "unconfirmed" })] }, false));
out.push(PhoneModel.resultView(
  { status: "failed", tasks: [mk("failed", { stop_reason: "unconfirmed" })] }, false));
out.push(PhoneModel.resultView(
  { status: "failed", tasks: [mk("failed", { stop_reason: "full" })] }, false));
out.push(PhoneModel.resultView({ status: "failed", tasks: [mk("failed")] }, false));
out.push(PhoneModel.resultView({ status: "running", tasks: [mk("waiting")] }, false));
out.push(PhoneModel.resultView({ status: "running", tasks: [mk("waiting")] }, true));
out.push(PhoneModel.resultView(null, false));
out.push(PhoneModel.termsBoard());
""")
        (all_ok, partial, ok_full_text, ok_none_text, stopped, stopped_ask,
         ask_only, full_only, bad_only, running, busy, none_, terms) = values
        # 全成功支（Phone:835）
        self.assertEqual(all_ok["head"], {"text": "报名成功", "tone": "green"})
        self.assertEqual(all_ok["title"], "报名计划完成")
        self.assertEqual(all_ok["text"], "每场结束时都向学校核对过。")
        self.assertEqual(all_ok["counts"], [{"tone": "ok", "n": 2, "text": "已报名"}])
        self.assertEqual(all_ok["boardCls"], "st-ok")
        self.assertFalse(all_ok["canRetry"])
        # 混合支（Phone:836）：五类统计只显非零、次序与 tone 照原型 res.counts（832）
        self.assertEqual(partial["head"], {"text": "部分完成", "tone": ""})
        self.assertEqual(partial["title"], "报名计划部分完成")
        self.assertEqual(partial["text"], "有 1 场需要到活动页核对，结果以学校为准。")
        self.assertEqual(partial["counts"], [
            {"tone": "ok", "n": 1, "text": "已报名"},
            {"tone": "wait", "n": 1, "text": "名额已满"},
            {"tone": "bad", "n": 1, "text": "未成功"},
            {"tone": "ask", "n": 1, "text": "待核对"},
            {"tone": "wait", "n": 1, "text": "已取消"}])
        self.assertEqual(partial["boardCls"], "st-warn")
        self.assertTrue(partial["canRetry"], "未成功+已取消都能重选（canRetry）")
        # partial 副题的另两支（Phone:836）
        self.assertEqual(ok_full_text, "有 1 场名额已满，不是工具出错。")
        self.assertEqual(ok_none_text, "结果以学校活动页为准。")
        # 停止支（Phone:834）：无待核对＝off 档、无描边；有待核对＝默认 tag + st-warn
        self.assertEqual(stopped["head"], {"text": "已停止", "tone": "off"})
        self.assertEqual(stopped["title"], "报名计划已停止")
        self.assertEqual(stopped["text"], "已提交的场次保留原状态，还没提交的场次已取消。")
        self.assertEqual(stopped["boardCls"], "")
        self.assertEqual(stopped_ask["head"], {"text": "已停止，需确认", "tone": ""})
        self.assertEqual(stopped_ask["boardCls"], "st-warn")
        # 其余三支（Phone:837-839）
        self.assertEqual(ask_only["head"], {"text": "需确认", "tone": ""})
        self.assertEqual(ask_only["title"], "计划已结束，有 1 场需确认")
        self.assertEqual(ask_only["text"], "工具不会自动重发，到学校活动页核对。")
        self.assertEqual(ask_only["boardCls"], "st-warn")
        self.assertEqual(full_only["head"], {"text": "名额已满", "tone": ""})
        self.assertEqual(full_only["title"], "这次没报上：名额满了")
        self.assertEqual(full_only["text"], "学校的名额在开放后被报满了，不是工具出错。")
        self.assertEqual(full_only["boardCls"], "st-warn")
        self.assertEqual(bad_only["head"], {"text": "未成功", "tone": "red"})
        self.assertEqual(bad_only["title"], "报名计划没有成功")
        self.assertEqual(bad_only["text"], "每场的原因都列在下面。")
        self.assertEqual(bad_only["boardCls"], "st-bad")
        self.assertTrue(bad_only["canRetry"])
        # 门禁：未全部终态、在跑、没有计划都不出结果页
        self.assertIsNone(running)
        self.assertIsNone(busy)
        self.assertIsNone(none_)
        # TM01 条款板（Phone:798 逐字）
        self.assertEqual(terms["tag"], "已暂停")
        self.assertEqual(terms["tagTone"], "off")
        self.assertEqual(terms["led"]["cap"], "电脑上同意条款后才能报名")
        self.assertEqual(terms["title"], "电脑上还没有同意条款")
        self.assertEqual(terms["sub"], "同意前只能看缓存，不能报名，也不能重新登录。")

    def test_task_card_result_reasons_follow_prototype(self):
        """RS02 任务卡原因三句（原型 advance 的 reason，Phone.dc.html:560/564/565）逐字照抄，
        次数取 attempts；计划停止的取消场给原型整句（finishState，Phone:580），
        手动取消透传后端 reason（signup_plan 给「用户取消了这一场」）。"""
        values = run_phone_js("""
out.push(PhoneModel.taskCard({ name: "甲", status: "success" }, 0, null).detail);
out.push(PhoneModel.taskCard({ name: "乙", status: "failed", stop_reason: "full",
  attempts: 2 }, 0, null).detail);
out.push(PhoneModel.taskCard({ name: "丙", status: "failed", stop_reason: "unconfirmed",
  attempts: 4 }, 0, null).detail);
out.push(PhoneModel.taskCard({ name: "丁", status: "canceled", reason: "计划已停止" }, 0, null).detail);
out.push(PhoneModel.taskCard({ name: "戊", status: "canceled", reason: "用户取消了这一场" }, 0, null).detail);
""")
        success, full, unconfirmed, stopped, manual = values
        self.assertEqual(success, "学校回“操作成功”，结束时向学校核对过：已报名")
        self.assertEqual(full,
                         "学校说报名人数已满，这一场到此结束，不再提交。不是工具出错。已提交 2 次")
        self.assertEqual(unconfirmed,
                         "已提交 4 次，没拿到确定回应；结束时向学校核对也没查到结果。"
                         "去活动页看一眼，或稍后刷新核对。工具不会再自动重发。")
        self.assertEqual(stopped, "计划已停止，这一场没有提交")
        self.assertEqual(manual, "用户取消了这一场")


class ResultTermsDomTests(unittest.TestCase):
    """RS01 的 DOM 层：结果板（统计区换 LED）、底栏纵排两钮与回草稿两动作（最小受控 DOM）。"""

    def test_result_board_and_stack_bar_follow_prototype(self):
        """RS01（原型 isResult，Phone.dc.html:262/295）：计划结束板换统计区（LED/cap 收起）、
        板描边 st-warn、任务卡继续渲染；底栏 .bar.stack 纵排两钮——「完成，回到活动列表」
        清计划回草稿，「重新选择未成功的场次」把仍可选的未成功场放回选择集。"""
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const done = { busy: false, plan: { plan_id: "p9", status: "partial",
  tasks: [
    { task_id: "t1", activity_id: "a1", name: "甲活动", status: "success" },
    { task_id: "t2", activity_id: "a2", name: "乙活动", status: "canceled",
      reason: "计划已停止" } ] },
  activities: [
    { id: "a1", name: "甲活动", sign_start: "2026-11-08 10:00:00", signed: true },
    { id: "a2", name: "乙活动", sign_start: "2026-11-09 20:00:00" }] };
globalThis.__fetch = async () => ({ status: 200, json: async () => ({ state: done, events: [] }) });
await ui.poll(true);
out.push({
  board: !$("plan-board").hidden,
  cls: $("plan-board").className,
  tag: $("board-tag-text").textContent,
  ledHidden: $("board-led-wrap").hidden,
  capHidden: $("board-cap").hidden,
  statsShown: !$("board-stats").hidden,
  stats: $("board-stats").childElementCount,
  title: $("board-title").textContent, sub: $("board-sub").textContent,
  barCls: $("action-bar").className,
  infoHidden: $("bar-info").hidden,
  reselectShown: !$("btn-reselect").hidden,
  finishShown: !$("btn-finish").hidden,
  cards: $("plan-tasks").childElementCount,
  toggleHidden: $("btn-toggle-list").hidden,
});
$("btn-reselect").click();
out.push({ selected: ui.model.selected.slice(), planCleared: ui.model.plan === null,
           barCls: $("action-bar").className, boardTitle: $("board-title").textContent });
ui.model.plan = done.plan;
ui.model.dismissedPlanId = "";
ui.renderItems();
$("btn-finish").click();
out.push({ selected: ui.model.selected.slice(), planCleared: ui.model.plan === null,
           barCls: $("action-bar").className,
           boardTitle: $("board-title").textContent });
""")
        board, reselect, finish = values
        self.assertTrue(board["board"], "计划结束显示结果板")
        self.assertIn("st-warn", board["cls"], "板描边照 boardCls（st-warn）")
        self.assertEqual(board["tag"], "部分完成")
        self.assertEqual(board["title"], "报名计划部分完成")
        self.assertEqual(board["sub"], "结果以学校活动页为准。")
        self.assertTrue(board["ledHidden"], "结果态 LED 收起（原型 isResult）")
        self.assertTrue(board["capHidden"])
        self.assertTrue(board["statsShown"], "换统计大数字区")
        self.assertEqual(board["stats"], 2, "两类非零计数（已报名/已取消）")
        self.assertEqual(board["barCls"], "bar stack", "底栏纵排（原型 .bar.stack）")
        self.assertTrue(board["infoHidden"], "结果态左侧标题不出（原型无 bar-t）")
        self.assertTrue(board["reselectShown"], "有未成功场时给「重新选择」钮")
        self.assertTrue(board["finishShown"])
        self.assertEqual(board["cards"], 2, "结果态任务卡继续渲染（原型 hasTasks）")
        self.assertFalse(board["toggleHidden"], "结果态也给「查看活动列表」钮")
        # 重新选择：成功的场不放回（已报名），取消的场仍可选→放回选择集
        self.assertEqual(reselect["selected"], ["a2"])
        self.assertTrue(reselect["planCleared"])
        self.assertEqual(reselect["barCls"], "bar", "回草稿后底栏复原")
        self.assertEqual(reselect["boardTitle"], "核对后再开始",
                         "放回的场进了选择集，板回「核对后再开始」")
        # 完成：清空选择、只回草稿
        self.assertEqual(finish["selected"], [])
        self.assertTrue(finish["planCleared"])
        self.assertEqual(finish["barCls"], "bar")
        self.assertEqual(finish["boardTitle"], "乙活动")

    def test_finish_and_reselect_clear_task_cards_immediately(self):
        """A-BUG-2：完成/重新选择后旧任务卡立即消失——两动作原先只调 renderItems
        （不重画任务卡），旧卡要残留到下一次 poll 才被清掉。"""
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const done = { busy: false, plan: { plan_id: "p9", status: "partial",
  tasks: [
    { task_id: "t1", activity_id: "a1", name: "甲活动", status: "success" },
    { task_id: "t2", activity_id: "a2", name: "乙活动", status: "canceled",
      reason: "计划已停止" } ] },
  activities: [
    { id: "a1", name: "甲活动", sign_start: "2026-11-08 10:00:00", signed: true },
    { id: "a2", name: "乙活动", sign_start: "2026-11-09 20:00:00" }] };
globalThis.__fetch = async () => ({ status: 200, json: async () => ({ state: done, events: [] }) });
await ui.poll(true);
out.push({ shown: !$("plan-tasks").hidden, cards: $("plan-tasks").childElementCount });
$("btn-finish").click();
out.push({ cleared: !$("plan-tasks").hidden ? false : $("plan-tasks").textContent === "" });
""")
        before, after = values
        self.assertTrue(before["shown"], "结果态任务卡可见（前置）")
        self.assertEqual(before["cards"], 2)
        self.assertTrue(after["cleared"], "完成后 #plan-tasks 立即清空（hidden 且无文案）")

    def test_signed_groups_render_in_main_list_and_summary_only_in_result(self):
        """UI-F1（G07，原型 Phone.dc.html:285-289）：已报名/已截止组照原型进主列表
        （组条+旗标+计数连排，段钮放行时与其他组同排）；details#signed-summary 按
        用户决策 2 只在结果态作「已报名汇总」入口（草稿态列表已直接展示这些行，
        折叠区收起不与列表重复）。R-P3-7：汇总行集不过段钮过滤，与「已报名 N 场」
        计数同一口径，修掉「折叠区有数无行」。"""
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const state = { busy: false, plan: null,
  activities: [
    /* 相对北京时间的今天（手机页按 SCHOOL_TZ 分组，本机日期会差一天）：写死日期会随翻页把「明天」变成「今天」（2026-11-09 全量实测分组数 6→4）；
       断言不变，只把夹具日期改成相对值。 */
    { id: "a1", name: "甲活动", sign_start: "%s 10:00:00", signed: true },
    { id: "a2", name: "乙活动", sign_start: "%s 20:00:00" },
    { id: "a3", name: "丙活动", sign_start: "%s 09:00:00", closed: true } ] };
ui.model.filter.status = "all";          // 先定段钮再拉快照：沙箱 textContent 清不空子元素，只渲染一次
globalThis.__fetch = async () => ({ status: 200, json: async () => ({ state, events: [] }) });
await ui.poll(true);
out.push({ draft: {
  summaryHidden: $("signed-summary").hidden,
  upcomingKids: $("upcoming-items").childElementCount } });
const plan = { plan_id: "p2", status: "completed",
  tasks: [{ task_id: "t1", activity_id: "a1", name: "甲活动", status: "success" }] };
ui.model.plan = plan;
ui.renderItems();
out.push({ result: {
  summaryShown: !$("signed-summary").hidden,
  count: $("signed-count").textContent,
  rows: $("signed-items").childElementCount } });
""" % tuple((datetime.now(timezone(timedelta(hours=8))) + timedelta(days=o)).strftime("%Y-%m-%d")
            for o in (-1, 1, -2)))
        draft, result = values
        # 组条+行的结构计数：明天(乙) + 已报名(甲) + 已截止(丙) 各占 grp+row = 6 个子元素
        self.assertEqual(draft["draft"]["upcomingKids"], 6,
                         "已报名/已截止组照原型渲染进主列表（组条+行连排）")
        self.assertTrue(draft["draft"]["summaryHidden"],
                        "草稿态列表已直接展示已报名行，折叠区收起（决策 2）")
        self.assertTrue(result["result"]["summaryShown"], "结果态汇总入口出现")
        self.assertEqual([result["result"]["count"], result["result"]["rows"]], ["1", 1],
                         "汇总行集与计数同一口径（不过段钮过滤，R-P3-7）")

    def test_signed_summary_view_follows_list_view_groups(self):
        """UI-F1 纯函数口径：listView 的组序含 已报名/已截止，注＝空/只能查看，
        与原型组条（组名+注+计数连排，Phone.dc.html:287）一致。"""
        values = run_phone_js("""
const nowS = Math.floor(Date.UTC(2026, 10, 8, 4, 0, 0) / 1000);
const items = [
  { id: "a1", name: "甲活动", sign_start: "2026-11-08 10:00:00", signed: true },
  { id: "a2", name: "乙活动", sign_start: "2026-11-07 09:00:00", closed: true },
  { id: "a3", name: "丙活动", sign_start: "2026-11-09 20:00:00" }];
const view = PhoneModel.listView(items, {q: "", status: "all", time: "all"}, {nowS: nowS});
out.push(view.groups.map((g) => [g.title, g.note, g.n, g.cls]));
""")
        (tomorrow, signed, closed) = values[0]
        self.assertEqual(tomorrow[0], "明天")
        self.assertEqual(signed, ["已报名", "", 1, "signed"], "已报名组：注空、cls signed")
        self.assertEqual(closed, ["已截止", "只能查看", 1, ""], "已截止组：注「只能查看」")


class ExceptionStatesTests(unittest.TestCase):
    """EX01/EX02/EX05/EX06：离线、登录失效、电脑列表失败、时钟待校准（exceptions 任务）。

    呈现走最小受控 DOM（run_phone_js），模型口径走 PhoneModel 纯函数；
    时刻只用快照/业务时钟，不读手机墙钟（决策 012）。"""

    def test_silent_stale_hides_red_bar_but_retrying_shows_it(self):
        """EX01：静默过期（pill「同步中」）不亮红条，由 #stale-note 说明；
        正在重试才是「离线」档，红条带「已重试 N 次」，重试钮＝一次 poll(true)。"""
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.lastOkAt = Date.now() - PhoneModel.staleAfterMs - 1;   // 静默过期
ui.refreshControls();
out.push([$("offline-note").hidden, $("stale-note").hidden, $("conn-text").textContent]);
ui.model.offlineTries = 2;                                      // 正在重试
ui.refreshControls();
out.push([$("offline-note").hidden, $("offline-note-title").textContent,
          $("conn-text").textContent, $("btn-offline-retry").textContent]);
let fetched = 0;
globalThis.__fetch = async () => { fetched += 1; throw new Error("offline"); };
$("btn-offline-retry").click();
for (let i = 0; i < 20; i += 1) await Promise.resolve();
out.push(fetched);
""")
        silent, retrying, clicks = values
        self.assertEqual(silent, [True, False, "同步中"],
                         "静默过期不亮红条：红条只给「离线」档，过期由 stale-note 说")
        self.assertEqual(retrying, [False, "连不上电脑，已重试 2 次", "离线", "重试"])
        self.assertEqual(clicks, 1, "「重试」钮复用现有刷新（poll(true)）")

    def test_running_board_off_cap_shows_last_sync(self):
        """EX01（原型 Phone:826）：离线运行板 LED 转 dim，cap 换「状态已过时 /
        最后同步 HH:MM:SS」；最后同步用同步成功时记下的北京时间，缺了落 --:--:--；
        在线时 cap 照旧。"""
        values = run_phone_js("""
const nowS = Date.UTC(2026, 10, 8, 4, 0, 0) / 1000;
const task = { name: "甲", status: "submitting", retry_deadline: nowS + 40, attempts: 1 };
const off = PhoneModel.runBoard({ tasks: [task] }, nowS, true, "14:19:40");
out.push([off.led.tone, off.led.cap, off.led.capB]);
const noClock = PhoneModel.runBoard({ tasks: [task] }, nowS, true, "");
out.push(noClock.led.capB);
const fresh = PhoneModel.runBoard({ tasks: [task] }, nowS, false, "14:19:40");
out.push([fresh.led.tone, fresh.led.cap, fresh.led.capB]);
""")
        self.assertEqual(values[0], ["dim", "状态已过时", "最后同步 14:19:40"])
        self.assertEqual(values[1], "最后同步 --:--:--",
                         "钟不可用没记下时刻：落 --:--:--，不用手机墙钟编一个")
        self.assertEqual(values[2], ["red", "本次尝试到", "12:00:40"])

    def test_stop_stays_tappable_when_offline(self):
        """EX01（原型 Phone:868「断网时也可以点停止」）：离线运行态底栏主钮不隐藏、
        不禁用。"""
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.lastOkAt = 0;                    // 从没连上过 = 离线
ui.model.busy = true;
ui.model.plan = { plan_id: "p1", tasks: [
  { task_id: "t1", name: "甲", status: "submitting" }] };
ui.refreshControls();
out.push([$("btn-stop").hidden, $("btn-stop").disabled, $("bar-title").textContent]);
""")
        self.assertEqual(values[0], [False, False, "计划进行中"])

    def test_offline_draft_bar_says_connect_first(self):
        """UI-F3：草稿态离线时底栏副题说「连上电脑后才能开始」——原实现直出
        场次计数（「1 场预报名」），像是在邀请一个必然失败的操作。"""
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.lastOkAt = 0;                    // 从没连上过 = 离线
ui.model.selected = ["a1"];
ui.refreshControls();
out.push([$("bar-sub").textContent, $("btn-start").disabled]);
""")
        self.assertEqual(values[0], ["连上电脑后才能开始", True],
                         "离线副题（UI-F3），主钮禁用与既有门禁一致")

    def test_login_expired_alert_and_bar_point_to_relogin(self):
        """EX02（原型 Phone:854/864）：登录失效告警两句 + 「重新登录」钮开重登 sheet；
        底栏副题「还差一步：重新登录」、主钮换「重新登录」，点击开 sheet 不发 start_plan。"""
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state: {terms_ok: true, login: {session_expired: true, session_present: true},
  activities: [{id: "a1", name: "甲活动", sign_start: "2026-11-08 20:00:00"}]}});
ui.model.selected = ["a1"];
ui.refreshControls();
out.push({alertShown: !$("login-expired-banner").hidden,
          barTitle: $("bar-title").textContent, barSub: $("bar-sub").textContent,
          startLabel: $("btn-start").textContent, startDisabled: $("btn-start").disabled,
          offlineShown: !$("offline-note").hidden});
const posts = [];
globalThis.__fetch = async (path, opts) => {
  if (opts && opts.method) posts.push(JSON.parse(opts.body).action);
  return {status: 200, json: async () => ({ok: true})};
};
$("btn-banner-relogin").click();
out.push({sheet: !$("sheet-root").hidden, title: $("sheet-title").textContent});
ui.closeSheet(true);
$("btn-start").click();
out.push({sheet: !$("sheet-root").hidden, posts: posts.slice()});
""")
        bar, alertSheet, startSheet = values
        self.assertTrue(bar["alertShown"])
        self.assertFalse(bar["offlineShown"], "pill 已连接（EX02），离线告警不得串台")
        self.assertEqual(bar["barTitle"], "已选 1 场")
        self.assertEqual(bar["barSub"], "还差一步：重新登录")
        self.assertEqual(bar["startLabel"], "重新登录")
        self.assertFalse(bar["startDisabled"],
                         "重新登录正是修复入口：canStart 不拦登录失效，钮保持可点")
        self.assertEqual([alertSheet["sheet"], alertSheet["title"]], [True, "在手机上重新登录"])
        self.assertEqual([startSheet["sheet"], startSheet["posts"]], [True, []],
                         "底栏主钮指向重登，不发任何写动作")

    def test_login_expired_pure_predicate(self):
        """EX02 口径：session_expired 或 session_present=false 都算失效（与 loginLine 一致）。"""
        values = run_phone_js("""
out.push(PhoneModel.loginExpired(null));
out.push(PhoneModel.loginExpired({}));
out.push(PhoneModel.loginExpired({session_present: true}));
out.push(PhoneModel.loginExpired({session_present: false}));
out.push(PhoneModel.loginExpired({session_expired: true, session_present: true}));
""")
        self.assertEqual(values, [False, False, False, True, True])

    def test_pc_list_error_alert_hides_bar_until_recovered(self):
        """EX05（原型 Phone:855/860）：电脑列表失败告警两句照原型、HH:MM 来自
        pc_list_error.at；草稿态底栏整条不出现；恢复（快照回 null）后告警收起、
        底栏回到「已选 N 场」。"""
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state: {terms_ok: true, busy: false,
  pc_list_error: {reason: "活动列表没能加载", at: "14:12"},
  activities: [{id: "a1", name: "甲活动", sign_start: "2026-11-08 20:00:00"}]}});
ui.model.selected = ["a1"];
ui.refreshControls();
out.push({alertShown: !$("pclist-alert").hidden,
          alertTitle: $("pclist-alert-title").textContent,
          alertText: $("pclist-alert-text").textContent,
          barHidden: $("action-bar").hidden,
          termsShown: !$("terms-alert").hidden});
ui.ingest({state: {pc_list_error: null}});
ui.refreshControls();
out.push([$("pclist-alert").hidden, $("action-bar").hidden, $("bar-sub").textContent]);
""")
        failed, recovered = values
        self.assertTrue(failed["alertShown"])
        self.assertEqual(failed["alertTitle"], "电脑上的活动列表没加载",
                         "EX05 题句照原型（Phone.dc.html:855）")
        self.assertEqual(failed["alertText"],
                         "电脑那边连不上学校站点，现在显示的是 14:12 更新的列表。恢复后会自动更新。")
        self.assertTrue(failed["barHidden"], "EX05：底栏不出现（原型 pclisterr 无 bar）")
        self.assertFalse(failed["termsShown"], "告警互斥：列表失败时条款告警不并排亮")
        self.assertEqual(recovered, [True, False, "1 场预报名"])

    def test_pc_list_error_without_time_falls_back_to_cache_wording(self):
        """EX05 防御：快照缺 at（旧后端/异常）不出空时刻，退回「缓存列表」措辞。"""
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state: {pc_list_error: {reason: "活动列表没能加载"}}});
ui.refreshControls();
out.push([$("pclist-alert").hidden, $("pclist-alert-text").textContent]);
""")
        self.assertEqual(values[0], [False, "电脑那边连不上学校站点，现在显示的是缓存列表。恢复后会自动更新。"])

    def test_alert_priority_chain_follows_prototype(self):
        """原型 alert 链（Phone.dc.html:851-856）：离线 > 条款 > 登录失效 > 列表失败 > 时钟。
        多条同时成立时只亮最优先的一条。"""
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.lastOkAt = 0;                  // 离线最优先
ui.model.termsOk = false;
ui.model.login = {session_expired: true, session_present: true};
ui.model.pcListError = {reason: "x", at: "14:12"};
ui.model.clockState = "unavailable";
ui.refreshControls();
out.push([$("offline-note").hidden, $("terms-alert").hidden,
          $("login-expired-banner").hidden, $("pclist-alert").hidden,
          $("pcclock-alert").hidden]);
ui.model.lastOkAt = Date.now();         // 离线解除 → 条款
ui.refreshControls();
out.push([$("offline-note").hidden, $("terms-alert").hidden,
          $("login-expired-banner").hidden, $("pclist-alert").hidden,
          $("pcclock-alert").hidden]);
ui.model.termsOk = true;                // → 登录失效
ui.refreshControls();
out.push([$("terms-alert").hidden, $("login-expired-banner").hidden,
          $("pclist-alert").hidden, $("pcclock-alert").hidden]);
ui.model.login = null;                  // → 列表失败
ui.refreshControls();
out.push([$("login-expired-banner").hidden, $("pclist-alert").hidden,
          $("pcclock-alert").hidden]);
ui.model.pcListError = null;            // → 时钟
ui.refreshControls();
out.push([$("pclist-alert").hidden, $("pcclock-alert").hidden]);
""")
        off, terms, expired, pc_list, clock = values
        self.assertEqual(off, [False, True, True, True, True])
        self.assertEqual(terms, [True, False, True, True, True])
        self.assertEqual(expired, [True, False, True, True])
        self.assertEqual(pc_list, [True, False, True])
        self.assertEqual(clock, [True, False])

    def test_clock_unavailable_blocks_start_and_shows_pending_calibration(self):
        """EX06（原型 Phone:856/865/928）：时钟不可用时告警亮、板头北京时间位写「待校准」、
        底栏副题换「电脑校准北京时间后才能开始」、canStart 拦（决策 012）；
        校准恢复后全部回到正常呈现。"""
        values = run_phone_js("""
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state: {terms_ok: true, busy: false,
  business_clock: {state: "unavailable"},
  activities: [{id: "a1", name: "甲活动", sign_start: "2026-11-08 20:00:00"}]}});
ui.model.selected = ["a1"];
ui.refreshControls();
ui.renderItems();
out.push({alertShown: !$("pcclock-alert").hidden,
          alertTitle: $("pcclock-alert-title").textContent,
          alertText: $("pcclock-alert-text").textContent,
          nowText: $("board-now-text").textContent,
          barSub: $("bar-sub").textContent,
          startDisabled: $("btn-start").disabled,
          canStart: PhoneModel.canStart(ui.model)});
ui.ingest({state: {business_clock: {state: "ready",
  epoch_s: Date.UTC(2026, 10, 8, 6, 0, 0) / 1000,
  tick_s: 1000000, sampled_tick_s: 1000000}}});
ui.refreshControls();
ui.renderItems();
out.push({alertShown: !$("pcclock-alert").hidden,
          nowText: $("board-now-text").textContent,
          startDisabled: $("btn-start").disabled});
""")
        down, ready = values
        self.assertTrue(down["alertShown"])
        # EX06 两句照原型逐字（Phone.dc.html:856，无钮）
        self.assertEqual(down["alertTitle"], "电脑上的北京时间还没校准")
        self.assertEqual(down["alertText"], "校准后才能开始报名计划，现在可以先选活动。")
        self.assertEqual(down["nowText"], "待校准")
        self.assertEqual(down["barSub"], "电脑校准北京时间后才能开始")
        self.assertTrue(down["startDisabled"])
        self.assertFalse(down["canStart"], "EX06：clockState unavailable 直接拦开始（决策 012）")
        self.assertEqual(ready, {"alertShown": False, "nowText": "14:00:00", "startDisabled": False},
                         "校准恢复：告警收起、板头回北京时间、开始可用")

    def test_clock_unavailable_pure_predicate(self):
        """EX06/A-BUG-4 口径：canStart 拦快照明说的 unavailable；syncing 由服务端拦，
        前端不额外拦（保持既有口径）。A-BUG-4（决策 012「时间不可信不能开始」）：
        快照声称 ready/holdover 但投影不出可信时刻的档也要拦——business_clock 字段
        缺失（setClock 得不到 clock 对象）与 holdover 样本超 900 秒各一档。"""
        values = run_phone_js("""
const base = { lastOkAt: 1000, nowMs: 1000 + 100, busy: false, selected: ["a1"] };
out.push(PhoneModel.canStart(Object.assign({}, base, {clockState: "unavailable"})));
out.push(PhoneModel.canStart(Object.assign({}, base, {clockState: "ready"})));
out.push(PhoneModel.canStart(Object.assign({}, base, {clockState: "syncing"})));
out.push(PhoneModel.canStart(Object.assign({}, base, {clockState: "holdover"})));
/* A-BUG-4 两档：字段齐全的 ready 放行；holdover 样本已超 900 秒拦截 */
const good = {}; PhoneModel.setClock(good, {state: "ready",
  epoch_s: 2000, tick_s: 1000, sampled_tick_s: 1000});
out.push(PhoneModel.canStart(Object.assign({}, base, {clockState: "ready", clock: good.clock})));
const aged = {}; PhoneModel.setClock(aged, {state: "holdover",
  epoch_s: 2000, tick_s: 1000, sampled_tick_s: 1000, age_s: 950});
out.push(PhoneModel.canStart(Object.assign({}, base, {clockState: "holdover", clock: aged.clock})));
""")
        self.assertEqual(values, [False, False, True, False, True, False])

    def test_last_ok_text_recorded_from_clock_snapshot(self):
        """EX01 口径：「最后同步」的北京时间在同步成功时记下（快照 epoch 投影），
        钟不可用时不记（空串）。"""
        values = run_phone_js("""
const ui = PhoneUI;
ui.ingest({state: {business_clock: {state: "ready",
  epoch_s: Date.UTC(2026, 10, 8, 6, 19, 40) / 1000,
  tick_s: 1000000, sampled_tick_s: 1000000}}});
out.push(ui.model.lastOkText);
ui.ingest({state: {business_clock: {state: "unavailable"}}});
out.push(ui.model.lastOkText);
""")
        self.assertEqual(values, ["14:19:40", ""])


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

    def test_pair_failure_passes_structured_fields_through_403(self):
        """BE1 透传：_post_pair 的 403 JSON 原样带 locked/retry_after_s/remaining_attempts，
        text 保持旧文案；鉴权/Host/Origin/csrf 逻辑不动。"""
        wrong = "000000" if self.code != "000000" else "111111"
        status, _headers, body = self._req(
            "POST", "/pair", body={"code": wrong},
            headers={"Origin": self.base})
        self.assertEqual(status, 403)
        payload = json.loads(body)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "bad_code")
        self.assertEqual(payload["text"], "配对码不对，请核对后重试")
        self.assertFalse(payload["locked"])
        self.assertEqual(payload["retry_after_s"], 0)
        self.assertEqual(payload["remaining_attempts"], IP_FAIL_LIMIT - 1)


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
        # 原断言整文件禁「display: grid」钉住的是页面单栏布局不用多列网格；
        # PA03 点阵屏（原型 .led）是字形点阵，照原型用 grid 排点，属可视化件不是布局网格。
        # G05（list-detail）：列表行（原型 .row，Phone.dc.html:98）照原型是「勾选框/时刻大字/
        # 主体」的行内固定三列 grid，同样不是页面级多栏布局——剔除清单为此扩 .row 一条。
        # G04/G10（run-wait）：四站进度（原型 .rail，Phone.dc.html:67）与任务卡（原型 .task，
        # Phone.dc.html:146）同为原型自带的行内固定列 grid，不是页面级多栏布局——再扩这两条。
        # SH01/SH02（sheets-ops）：核对条目（原型 .tk，Phone.dc.html:178「主体+移除钮」两列）
        # 与提醒列表（原型 .pw，Phone.dc.html:217 单列 list grid）同为原型自带的行内固定
        # 列 grid——再扩这两条。检查强度不降：剔除这六条后其余样式仍不得出现 display: grid
        without_led = re.sub(r"(?m)^\s*\.led\s*\{[^}]*\}", "", css)
        without_led = re.sub(r"(?m)^\s*\.row\s*\{[^}]*\}", "", without_led)
        without_led = re.sub(r"(?m)^\s*\.rail\s*\{[^}]*\}", "", without_led)
        without_led = re.sub(r"(?m)^\s*\.task\s*\{[^}]*\}", "", without_led)
        without_led = re.sub(r"(?m)^\s*\.tk\s*\{[^}]*\}", "", without_led)
        without_led = re.sub(r"(?m)^\s*\.pw\s*\{[^}]*\}", "", without_led)
        self.assertNotIn("display: grid", without_led,
                         "单栏布局不引入多列网格（点阵屏/列表行/四站/任务卡/核对条目/提醒列表除外）")
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
        """验证码图与输入框必须同进同退，否则会出现「有框没图」的空输入。

        原断言把 提交/换图/取消 三个按钮也钉在验证码组里：RL01/G11 照原型把主钮、
        换一张图、取消挪进页脚 .sh-f（Phone.dc.html:347）——「没保存只填账号密码」的态
        没有验证码也要能取消，按钮与验证码组解耦是原型本意。检查强度不降：
        图+输入仍是同一开关、默认收起、页脚五个动作钮齐全且都在重登面板内。
        """
        html = (PHONE_DIR / "index.html").read_text(encoding="utf-8")
        start = html.index('id="relogin-captcha-group"')
        block = html[start:html.index('id="rel-auto"', start)]
        for needle in ('id="captcha"', 'id="code"'):
            self.assertIn(needle, block, "%s 不在验证码整组里" % needle)
        self.assertIn('id="relogin-captcha-group" hidden', html,
                      "默认状态必须是收起")
        panel = html[html.index('id="relogin-panel"'):]
        for needle in ('id="btn-relogin"', 'id="btn-relogin-submit"',
                       'id="btn-relogin-refresh"', 'id="btn-relogin-cancel"',
                       'id="btn-relogin-auto"', 'id="btn-relogin-done"'):
            self.assertIn(needle, panel, "%s 不在重登 sheet 里" % needle)

    def test_offline_notice_is_a_first_class_element(self):
        html = (PHONE_DIR / "index.html").read_text(encoding="utf-8")
        for needle in ('id="offline-note"', 'id="stale-note"'):
            self.assertIn(needle, html)
        # 原断言钉住「#last-sync 在 offline-note 之前的独立行」：G01 照原型把「最近同步」
        # 并进更多面板（原型顶栏没有独立同步行），顶栏位置断言随之删除
        css = (PHONE_DIR / "styles.css").read_text(encoding="utf-8")
        self.assertIn("position: sticky", css, "状态条要吸顶，断网时刷新还在拇指边")
        self.assertIn("button.wide", css)

    def test_mobile_console_order_and_controls(self):
        """手机页顺序＝手机上的真实任务顺序：今天 → 即将开放 → 已报名 → 更多。

        G01 改动原因：#last-sync 原是顶栏下的独立行，照原型并进更多面板（原型顶栏没有），
        顺序断言里把它挪到 more-panel 之后、filter-panel 之前。
        relogin-sheet 迁移：#relogin-panel 原在 more-panel 内（relogin-section 段），
        现迁为 sheet 独立槽（review-panel 之后），文档序仍在 logs-panel 之后，断言序不变。
        sheets-ops 改动原因（SH01/SH05）：#retry-panel 原在更多面板（重试设置节），
        随尝试字段迁进核对 sheet（#review-panel 内），故从上面的顺序清单移出、
        改为单独断言 review-panel < retry-panel < relogin-panel；
        更多面板节序照原型改组（开放时间→登录→电脑窗口→运行记录），
        原「重新登录」节（relogin-entry）由登录节取代，#relogin-note 随迁登录节。
        result-and-terms 改动原因（TM01）：#terms-alert 是新增的条款告警条（原型 .alert，
        Phone.dc.html:853，位于 #banner 与登录失效条之间），加入顺序清单。
        """
        html = (PHONE_DIR / "index.html").read_text(encoding="utf-8")
        ids = ['id="conn"', 'id="terms-alert"', 'id="login-expired-banner"',
               'id="today-items"', 'id="upcoming-items"', 'id="signed-summary"',
               'id="bookmark-hint"', 'id="more-panel"', 'id="last-sync"',
               'id="filter-panel"', 'id="login-line"', 'id="logs-panel"', 'id="relogin-panel"']
        positions = []
        for needle in ids:
            self.assertIn(needle, html, "手机页缺少 %s" % needle)
            positions.append(html.index(needle))
        self.assertEqual(positions, sorted(positions),
                         "顺序必须是 状态→今天→即将开放→已报名→书签→更多")
        retry_at = html.index('id="retry-panel"')
        self.assertLess(html.index('id="review-panel"'), retry_at,
                        "尝试设置已迁进核对 sheet（SH01）")
        self.assertLess(retry_at, html.index('id="relogin-panel"'))
        self.assertLess(html.index('id="retry-panel"'), html.index('id="review-policy"'),
                        "fhint 跟在尝试字段后（SH01）")
        # 原断言钉住「报名按钮在 today 卡内」：G02 照原型把开始/停止/取消移进底部固定操作条
        # （原型 .bar，位于更多面板之后的页面末尾），位置断言随之改读 action-bar
        self.assertLess(html.index('id="more-panel"'), html.index('id="action-bar"'))
        self.assertLess(html.index('id="action-bar"'), html.index('id="btn-start"'))
        # 已报名折叠区仍是 details/summary（NEEDS-HUMAN 2 保留为入口）；
        # 操作弹层按用户决策 1 改用 sheet 外壳（G03），不再沿用「不引入自定义弹层」的旧口径
        self.assertIn("<details", html)
        self.assertNotIn("window.confirm", html)

    def test_pair_intro_two_sentences_are_pinned(self):
        """T-缺口（PA02）：配对页的两句说明被静态钉住——照原型逐字落的
        （配对码在哪、手机只是遥控器），改动必须过审计，不得悄悄走样。"""
        html = (PHONE_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn("配对码在电脑的“设置 → 手机访问”里，5 分钟内有效，只能用一次。", html,
                      "PA02 第一句：配对码在哪里、时效与一次性")
        self.assertIn("手机只是遥控器，真正报名的还是电脑，所以电脑要开着、不能睡眠。", html,
                      "PA02 第二句：手机与电脑的分工")

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
        """电脑没同意条款：手机停在缓存，不能开始也不能重新登录；条款告警、整板暂停、
        列表行全禁用、底栏副题换成条款门；同意后全部恢复。

        原断言钉住 #banner kind=terms 的单句。TM01 照原型把告警换成专用告警条两句
        （原型 .alert，Phone.dc.html:853——原单句文案退役），并补整板「已暂停」
        （Phone:798）、列表行全禁用（Phone:742）与底栏副题（Phone:863），
        断言随之改读 #terms-alert 与板/行/底栏。
        """
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state: {terms_ok: false, busy: false,
  business_clock: {state: "ready", epoch_s: Date.UTC(2026, 10, 8, 6, 0, 0) / 1000,
                   tick_s: 1000000, sampled_tick_s: 1000000},
  activities: [{id: "a1", name: "甲活动", sign_start: "2026-11-08 20:00:00"}]}});
ui.model.selected = ["a1"];
ui.refreshControls();
ui.renderItems();
const locked = {start: $("btn-start").disabled, relogin: $("btn-relogin").disabled,
  alertTitle: $("terms-alert-title").textContent, alertText: $("terms-alert-text").textContent,
  alertHidden: $("terms-alert").hidden,
  tag: $("board-tag-text").textContent, tagCls: $("board-tag").className,
  boardTitle: $("board-title").textContent, boardSub: $("board-sub").textContent,
  cap: $("board-cap-text").textContent,
  barSub: $("bar-sub").textContent,
  row: (() => { const row = $("items")._children[2];
                return [row._children[0].disabled, row.className.indexOf("dim") >= 0]; })()};
ui.ingest({state: {terms_ok: true}});
ui.refreshControls();
ui.renderItems();
out.push({locked, start: $("btn-start").disabled, relogin: $("btn-relogin").disabled,
  alertHidden: $("terms-alert").hidden, boardTitle: $("board-title").textContent,
  barSub: $("bar-sub").textContent,
  row: (() => { const row = $("items")._children[2];
                return [row._children[0].disabled, row.className.indexOf("dim") >= 0]; })()});
''')
        r = values[0]
        self.assertTrue(r["locked"]["start"], "没同意条款不能开始")
        self.assertTrue(r["locked"]["relogin"], "没同意条款不能重新登录")
        self.assertFalse(r["locked"]["alertHidden"], "条款告警可见")
        # TM01 两句照原型逐字（Phone.dc.html:853，无钮）
        self.assertEqual(r["locked"]["alertTitle"], "电脑上还没有同意使用条款")
        self.assertEqual(r["locked"]["alertText"],
                         "回电脑同意后才能登录和报名。现在显示的是上次的缓存。")
        self.assertEqual(r["locked"]["tag"], "已暂停")
        self.assertIn("off", r["locked"]["tagCls"], "板 tag 走 off 档（原型 Phone:798）")
        self.assertEqual(r["locked"]["boardTitle"], "电脑上还没有同意条款")
        self.assertEqual(r["locked"]["boardSub"], "同意前只能看缓存，不能报名，也不能重新登录。")
        self.assertEqual(r["locked"]["cap"], "电脑上同意条款后才能报名")
        self.assertEqual(r["locked"]["barSub"], "电脑上同意条款后才能开始",
                         "底栏副题照原型（Phone:863）")
        self.assertEqual(r["locked"]["row"], [True, True],
                         "列表行 checkbox 禁用并整行变暗（TM01，Phone:742）")
        self.assertFalse(r["start"], "同意后恢复")
        self.assertFalse(r["relogin"])
        self.assertTrue(r["alertHidden"], "同意后条款告警收起")
        self.assertEqual(r["boardTitle"], "核对后再开始", "同意后回到草稿板")
        self.assertEqual(r["row"], [False, False], "同意后行恢复可选、不再变暗")
        self.assertEqual(r["barSub"], "1 场预报名", "同意后底栏副题回到场次注")

    def test_offline_bar_is_red(self):
        """连不上电脑是红条（原型 PhoneOffline 的 tone bad），比琥珀色提醒更显眼。

        原断言钉住旧 #offline-note.warn 覆盖写法。EX01 照原型把红条改成
        .alert.bad（Phone.dc.html:35），样式与结构断言随之改读新标记——
        检查强度不降：色档、结构与 role=alert 都还在。
        """
        css = (PHONE_DIR / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".alert.bad {\n  background: var(--bad-tint);\n  color: #7e2119;", css)
        html = (PHONE_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="offline-note" class="alert bad" role="alert"', html)
        self.assertIn('id="btn-offline-retry"', html)

    def test_review_lists_the_plan_and_the_same_reminders(self):
        """点「开始」先核对：批次头列已选场次（SH01）、尝试设置与同一套提醒（SH02）；
        有提醒按钮叫「仍然开始」；确认后才真的开始。

        原断言钉住 #review-items 的 <li> 清单与旧提醒句。SH01 照原型改成批次头+条目
        （原型 batchMap，Phone.dc.html:767-779；vm 沙箱同标签元素共享、动态内容不可逐个读，
        内容断言改走 PhoneModel.reviewBatches 纯函数 + 结构计数）；SH02 三支句式照原型
        pwList（Phone:912-916）改写，提醒断言随之逐句更新；场次补 sign_start
        （批次头与「要等到 HH:MM」需要绝对开放时刻，seconds_to_open 继续管间隔阈值）。"""
        values = run_phone_js('''
const ui = PhoneUI;
const posts = [];
globalThis.__fetch = async (path, opts) => {
  if (opts && opts.body) posts.push(JSON.parse(opts.body).action);
  return {status: 200, json: async () => ({ok: true, plan_id: "p1"})};
};
ui.model.lastOkAt = Date.now();
ui.ingest({state: {terms_ok: true, busy: false,
  /* holdover 快照带全字段：A-BUG-4 后「声称 holdover 却没有 clock 对象」会被
     canStart 拦（决策 012），核对 sheet 就打不开——本用例只测核对渲染，给全字段 */
  business_clock: {state: "holdover", epoch_s: Date.UTC(2026, 10, 10, 6, 0, 0) / 1000,
                   tick_s: 1000000, sampled_tick_s: 1000000},
  relogin_setup: {saved: false, ocr_ready: false, paused: false},
  activities: [{id: "a1", name: "甲活动", seconds_to_open: 2 * 86400,
                sign_start: "2026-11-10 14:00:00"}]}});
ui.model.selected = ["a1"];
ui.refreshControls();
const picked = [{id: "a1", name: "甲活动", seconds_to_open: 2 * 86400,
                 sign_start: "2026-11-10 14:00:00"}];
$("btn-start").click();
const review = {hidden: $("review-panel").hidden, nodes: $("review-items").childElementCount,
  batches: PhoneModel.reviewBatches(picked, null),
  warns: $("review-warns").innerHTML, warnsShown: !$("review-warns").hidden,
  hint: $("review-policy").textContent, hintShown: !$("review-policy").hidden,
  label: $("btn-review-start").textContent, posts: posts.slice()};
$("btn-review-back").click();
const back = {hidden: $("review-panel").hidden, posts: posts.slice()};
const quiet = PhoneModel.preStartWarnings({clockState: "ready", retry: {retry_for_s: 120},
  reloginSetup: {saved: true, ocr_ready: true, paused: false}}, [{id: "b1", seconds_to_open: 600, sign_end_ts: 1}]);
out.push({review, back, quiet});
''')
        r = values[0]
        self.assertFalse(r["review"]["hidden"], "点开始先出核对面板")
        self.assertEqual(r["review"]["nodes"], 2, "一个批次头 + 一个条目（SH01 批次渲染）")
        batch = r["review"]["batches"][0]
        self.assertEqual([batch["time"], batch["note"]], ["14:00:00", "预报名 1 场"],
                         "批次头时刻 HH:MM:SS（原型 hms(open)，Phone:770）")
        self.assertEqual(batch["items"][0]["aria"], "从计划移除 甲活动")
        self.assertEqual(batch["items"][0]["act"], "开放 2026-11-10 14:00:00",
                         "缺举办时段时回退「开放 …」说明")
        self.assertTrue(r["review"]["warnsShown"], "有提醒时提醒块可见（原型 hasPreWarn）")
        self.assertIn("上次的校准结果", r["review"]["warns"], "沿用上次校准要提醒（原型板未画、电脑端有）")
        self.assertIn("要等到 14:00，电脑上没开自动登录", r["review"]["warns"],
                      "等待久且自动登录开不全（SH02，Phone:915）")
        self.assertIn("中途登录失效要你重新登录", r["review"]["warns"],
                      "没保存账号的一支（SH02）")
        self.assertIn("有场次在 24 小时后才开放，电脑要开着、不能睡眠。", r["review"]["warns"],
                      "24 小时句照原型（SH02，Phone:916）")
        self.assertEqual(r["review"]["label"], "仍然开始报名计划", "有提醒只改名，不拦")
        self.assertEqual(r["review"]["hint"], "", "retry=2 分钟无 fhint")
        self.assertFalse(r["review"]["hintShown"])
        self.assertEqual(r["review"]["posts"], [], "核对时还没开始")
        self.assertTrue(r["back"]["hidden"], "「返回」收起核对")
        self.assertEqual(r["back"]["posts"], [], "返回不开始")
        self.assertEqual(r["quiet"], [], "都正常时没有提醒")
        js = (PHONE_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("seconds_to_open", js, "开放时间用后端给的秒数，不读手机时钟")

    def test_running_plan_says_keep_going_and_edit_on_the_computer(self):
        """运行中：重新登录成功写「报名计划照常继续」；tip 说明锁屏与改计划回电脑，来源标注在 bar-t。

        原断言钉住 #plan-line 一行拼接的「要修改计划，回电脑上改」+「（从手机开始）」：
        G10（run-wait）把每场结论改由任务卡承载、结尾句换原型 tip（Phone.dc.html:276）、
        来源标注并入 bar-t，断言随之改读 #run-tip 与 #bar-title。
        """
        values = run_phone_js('''
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const running = {busy: true, plan: {plan_id: "p1", status: "running", source: "phone",
  tasks: [{task_id: "t1", name: "甲活动", status: "waiting", path: "direct"}]}, activities: []};
/* 走真实轮询：poll 把快照交给 ingest 再画任务卡与 tip */
globalThis.__fetch = async () => ({status: 200, json: async () => ({state: running, events: []})});
await ui.poll(true);
ui.ingest({state: {login_relay: {state: "success", flow_id: "f1", live: true}}});
out.push([$("relogin-note").textContent, $("run-tip").textContent, $("bar-title").textContent]);
''')
        note, tip, bar = values[0]
        # 原断言钉住旧句（无句号）：RL08 完成态文案照原型（Phone.dc.html:894）补全句号
        self.assertEqual(note, "重新登录成功，报名计划照常继续。")
        self.assertIn("手机能锁屏，电脑不能关机或睡眠", tip)
        self.assertIn("要改，回电脑点“修改计划”，或者停止后重新选。", tip)
        self.assertIn("（从手机开始）", bar)

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
