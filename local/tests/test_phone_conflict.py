#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机页：不可加入、点按展开原因、跨天时段、报后可退、可取消至的去处说明（计划 20261107-conflict-cancel，fe-phone-page）。

纯规则走 PhoneModel（node vm 直接执行真实函数）；行与面板的 DOM 用测试里的轻量元素替身逐个构造，
再把 renderItems 画出来的树拿来核对。手机页不放取消按钮：整个 ui/m 下不得出现 cancel_signup。
不连学校，断行与像素以 Edge / 手机浏览器截图为准，这里不测。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from test_phone_ui import PHONE_DIR, run_phone_js  # noqa: E402

WJ = "⁠"

# 北京时间 2026-11-06 14:00 的业务时钟快照；三场活动用通用名
SETUP = r"""
const NOW_S = Date.UTC(2026, 10, 6, 6, 0, 0) / 1000;
function clockAt(model, state, age) {
  PhoneModel.setClock(model, { state: state || "ready", epoch_s: NOW_S, tick_s: 50, sampled_tick_s: 50, age_s: age || 0 });
}
const base = { place: "学生公寓", sign_start: "2026-11-01 08:00:00" };
const signedA = Object.assign({}, base, { id: "s1", name: "宿舍查寝", signed: true, cancel_allowed: true,
  sign_end: "2026-11-08 14:00:00", act_start: "2026-11-08 22:40:00", act_end: "2026-11-10 23:20:00" });
const clashB = Object.assign({}, base, { id: "b1", name: "模拟面试", signed: false, cancel_allowed: null,
  sign_end: "2026-11-08 10:00:00", act_start: "2026-11-09 08:00:00", act_end: "2026-11-09 17:00:00" });
const clashC = Object.assign({}, base, { id: "c1", name: "职业规划讲座", signed: false, cancel_allowed: false,
  sign_end: "2026-11-08 10:00:00", act_start: "2026-11-10 09:00:00", act_end: "2026-11-10 11:00:00" });
const freeD = Object.assign({}, base, { id: "d1", name: "社区志愿服务日", signed: false, cancel_allowed: true,
  sign_end: "2026-11-08 10:00:00", act_start: "2026-11-07 09:00:00", act_end: "2026-11-07 11:30:00" });
"""

# 用真实元素替身重画：每次 createElement 给一个新元素，子树可递归读取
DOM = r"""
function mk(tag) {
  const el = { tag: tag, children: [], className: "", dataset: {}, style: {}, textContent: "", listeners: {},
    attrs: {}, disabled: false, checked: false, hidden: false, type: "",
    appendChild(c) { this.children.push(c); return c; },
    addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); },
    setAttribute(k, v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k]; },
    classList: { remove() {}, add() {} } };
  return el;
}
document.createElement = (tag) => mk(tag);
function walk(el, fn) { fn(el); (el.children || []).forEach((c) => walk(c, fn)); }
function texts(el) { const out = []; walk(el, (n) => { if (n.textContent) out.push(n.textContent); }); return out.join("|"); }
function tags(el, tag) { const out = []; walk(el, (n) => { if (n.tag === tag) out.push(n); }); return out; }
function draw(ui) {
  ["#items", "#upcoming-items", "#signed-items"].forEach((id) => { $(id)._children.length = 0; });
  ui.renderItems();
  const rows = {};
  ["#items", "#upcoming-items", "#signed-items"].forEach((id) => { $(id)._children.forEach((li) => { rows[li.dataset.id] = li; }); });
  return rows;
}
/* 原断言按旧行几何导航：行曾是 li，点按监听在第一个子元素（label）上，原因面板是行的第二个子节点。
   G05（list-detail）把行改成 label.row 本身：dataset.id 与点按监听都在行上，原因面板是行内的 div.why；
   原断言钉住的是旧结构，助手随之改为行上直接点按、按 div.why 计数，检查强度不变（面板 0→1→0）。 */
function whyOf(li) { return tags(li, "div").filter((d) => d.className === "why").length; }
function clickRow(li) { li.listeners.click[0]({ preventDefault() {} }); }
"""


class PhoneClashRulesTests(unittest.TestCase):
    def test_signed_clash_uses_a_half_open_interval_like_the_desktop(self):
        out = run_phone_js(SETUP + r"""
const touching = Object.assign({}, clashB, { id: "t1", act_start: "2026-11-10 23:20:00", act_end: "2026-11-11 01:00:00" });
const closed = Object.assign({}, clashB, { id: "x1", closed: true });
const noTime = Object.assign({}, clashB, { id: "n1", act_start: "", act_end: "" });
const items = [signedA, clashB, touching, closed, noTime];
const pick = (it) => { const hit = PhoneModel.signedClash(it, items); return hit ? hit.id : null; };
out.push({ overlap: pick(clashB), touching: pick(touching), closed: pick(closed), noTime: pick(noTime),
  signedSelf: pick(signedA), free: PhoneModel.signedClash(freeD, [signedA, freeD]) });
""")[0]
        self.assertEqual(out["overlap"], "s1")
        self.assertIsNone(out["touching"], "首尾相接不算重叠")
        self.assertIsNone(out["closed"], "已截止的行不画不可加入")
        self.assertIsNone(out["noTime"])
        self.assertIsNone(out["signedSelf"])
        self.assertIsNone(out["free"])

    def test_actionable_keeps_its_old_signature_and_blocks_clashes_when_given_the_list(self):
        out = run_phone_js(SETUP + r"""
out.push([PhoneModel.actionable(clashB), PhoneModel.actionable(clashB, [signedA, clashB]), PhoneModel.actionable(freeD, [signedA, freeD])]);
""")[0]
        self.assertEqual(out, [True, False, True])

    def test_refund_flag_three_states(self):
        out = run_phone_js(SETUP + r"""
out.push({ yes: PhoneModel.refundFlag(freeD), no: PhoneModel.refundFlag(clashC), nul: PhoneModel.refundFlag(clashB),
  signed: PhoneModel.refundFlag(signedA), closed: PhoneModel.refundFlag(Object.assign({}, freeD, { closed: true })) });
""")[0]
        self.assertEqual(out["yes"], {"text": "报后可退", "no": False})
        self.assertEqual(out["no"], {"text": "报后不可退", "no": True})
        self.assertIsNone(out["nul"], "cancel_allowed 为 null 时不写")
        self.assertIsNone(out["signed"])
        self.assertIsNone(out["closed"])


class PhoneTimeTextTests(unittest.TestCase):
    def test_cross_day_same_day_and_midnight(self):
        out = run_phone_js(SETUP + r"""
const mk = (s, e) => ({ act_start: s, act_end: e });
out.push({
  cross: PhoneModel.actSpan(mk("2026-11-08 22:40:00", "2026-11-10 23:20:00")),
  same: PhoneModel.actSpan(mk("2026-11-09 08:00:00", "2026-11-09 17:00:00")),
  mid1: PhoneModel.actSpan(mk("2026-11-08 22:00:00", "2026-11-09 00:00:00")),
  mid3: PhoneModel.actSpan(mk("2026-11-08 22:40:00", "2026-11-11 00:00:00")),
  bad: PhoneModel.actSpan(mk("", "")),
  days: [PhoneModel.spanDays(mk("2026-11-08 22:40:00", "2026-11-11 00:00:00")), PhoneModel.spanDays(mk("2026-11-08 22:00:00", "2026-11-09 00:00:00"))],
});
""")[0]
        self.assertEqual(out["cross"], "11月8日 22:40 – 11月10日 23:20（%s跨%s3%s天%s）" % (WJ, WJ, WJ, WJ))
        self.assertEqual(out["same"], "11月9日 08:00–17:00")
        self.assertEqual(out["mid1"], "11月8日 22:00–24:00")
        self.assertEqual(out["mid3"], "11月8日 22:40 – 11月11日 00:00（%s跨%s3%s天%s）" % (WJ, WJ, WJ, WJ),
                         "结束恰为 00:00 算前一天：8、9、10 日共三天")
        self.assertEqual(out["bad"], "")
        self.assertEqual(out["days"], [3, 1])


class PhoneCancelNoteTests(unittest.TestCase):
    def test_note_only_when_allowed_and_inside_the_window(self):
        out = run_phone_js(SETUP + r"""
const model = { clock: null };
const none = PhoneModel.cancelNote(signedA, PhoneModel.businessNowS(model));   // 还没有时钟快照
clockAt(model);
const nowS = PhoneModel.businessNowS(model);
out.push({ none, nowS, ok: PhoneModel.cancelNote(signedA, nowS),
  no: PhoneModel.cancelNote(Object.assign({}, signedA, { cancel_allowed: false }), nowS),
  nul: PhoneModel.cancelNote(Object.assign({}, signedA, { cancel_allowed: null }), nowS),
  late: PhoneModel.cancelNote(Object.assign({}, signedA, { sign_end: "2026-11-06 10:00:00" }), nowS),
  early: PhoneModel.cancelNote(Object.assign({}, signedA, { sign_start: "2026-11-07 08:00:00" }), nowS),
  unsigned: PhoneModel.cancelNote(clashB, nowS) });
""")[0]
        self.assertEqual(out["none"], "", "没有可信北京时间就不说")
        self.assertAlmostEqual(out["nowS"], 1793944800, delta=5)
        self.assertEqual(out["ok"], "可取消至 11月8日 14:00，在电脑上或" + WJ.join("学校网站取消。"))
        for key in ("no", "nul", "late", "early", "unsigned"):
            self.assertEqual(out[key], "", key)

    def test_clock_snapshot_rules(self):
        out = run_phone_js(SETUP + r"""
const m = {};
clockAt(m, "ready", 0);
const ready = PhoneModel.businessNowS(m);
clockAt(m, "holdover", 10);
const holdover = PhoneModel.businessNowS(m);
clockAt(m, "unavailable", 0);
const unavailable = PhoneModel.businessNowS(m);
clockAt(m, "ready", 1000);                      // 快照年龄已超过 900 秒
const stale = PhoneModel.businessNowS(m);
PhoneModel.setClock(m, { state: "ready" });     // 字段缺失
out.push({ ready, holdover, unavailable, stale, broken: PhoneModel.businessNowS(m) });
""")[0]
        self.assertAlmostEqual(out["ready"], 1793944800, delta=5)
        self.assertAlmostEqual(out["holdover"], 1793944800, delta=5)
        self.assertIsNone(out["unavailable"])
        self.assertIsNone(out["stale"])
        self.assertIsNone(out["broken"])

    def test_no_cancel_call_anywhere_in_the_phone_page(self):
        for path in PHONE_DIR.rglob("*"):
            if path.is_file() and path.suffix in {".js", ".html", ".css"}:
                self.assertNotIn("cancel_signup", path.read_text(encoding="utf-8"), str(path.name))
        from domain.phone_rules import ACTION_PARAMS  # noqa: WPS433
        self.assertNotIn("cancel_signup", ACTION_PARAMS, "手机白名单不加任何取消报名")


class PhoneWhyTests(unittest.TestCase):
    def test_four_resolution_sentences_match_the_desktop_bubble(self):
        out = run_phone_js(SETUP + r"""
const m = {}; clockAt(m); const nowS = PhoneModel.businessNowS(m);
const res = {};
const variants = { a: signedA, b: Object.assign({}, signedA, { cancel_allowed: false }),
  c: Object.assign({}, signedA, { sign_end: "2026-11-06 10:00:00" }), d: Object.assign({}, signedA, { cancel_allowed: null }) };
Object.keys(variants).forEach((k) => { const v = PhoneModel.whyView(clashB, variants[k], nowS); res[k] = { way: v.way, hasGo: v.hasGo, kind: v.wayKind }; });
res.view = PhoneModel.whyView(clashB, signedA, nowS);
res.noClock = PhoneModel.whyView(clashB, signedA, null).way;
out.push(res);
""")[0]
        self.assertEqual(out["a"]["way"], "想报这一场，要先取消「宿舍查寝」的报名，11月8日 14:00 前可以取消。")
        self.assertTrue(out["a"]["hasGo"])
        self.assertEqual(out["b"]["way"], "「宿舍查寝」报名后不能取消，" + WJ.join("这一场报不了。"))
        self.assertEqual(out["c"]["way"], "「宿舍查寝」的取消时间已过（截至 11月6日 10:00），" + WJ.join("这一场报不了。"))
        self.assertEqual(out["d"]["way"], "「宿舍查寝」能不能取消还没查到，刷新后再看。")
        self.assertEqual(out["noClock"], out["d"]["way"], "没有可信北京时间时不猜窗口，按还没查到说")
        self.assertEqual([out[k]["hasGo"] for k in "bcd"], [False] * 3)
        view = out["view"]
        self.assertEqual(view["title"], "和已报名的活动时间重叠")
        self.assertEqual([r["label"] for r in view["rows"]], ["已报名", "这一场"])
        self.assertEqual(view["days"], ["11月8日", "11月9日", "11月10日"])
        self.assertEqual(len(view["cuts"]), 2)

    def test_toggle_keeps_one_open_at_a_time(self):
        out = run_phone_js(r"""
const m = { whyId: "" };
out.push([PhoneModel.toggleWhy(m, "a"), PhoneModel.toggleWhy(m, "b"), PhoneModel.toggleWhy(m, "b"), PhoneModel.toggleWhy(m, "a")]);
""")[0]
        self.assertEqual(out, ["a", "b", "", "a"])


class PhoneRowDomTests(unittest.TestCase):
    def test_clash_row_is_disabled_and_tap_toggles_the_reason(self):
        out = run_phone_js(SETUP + DOM + r"""
const ui = PhoneUI;
ui.model.items = [signedA, clashB, clashC, freeD];
clockAt(ui.model);
let rows = draw(ui);
const flagOf = (li) => tags(li, "span").filter((s) => s.className === "flag clash").length;
const boxOf = (li) => tags(li, "input")[0];
/* 原断言读 dataset.clash：G05 把冲突标识改为行类名 .clash（原型 row.cls），断言随之读类名 */
const first = { b: { disabled: boxOf(rows.b1).disabled, flag: flagOf(rows.b1), text: texts(rows.b1), clash: rows.b1.className, why: whyOf(rows.b1) },
  free: { disabled: boxOf(rows.d1).disabled, flag: flagOf(rows.d1), why: whyOf(rows.d1) } };
// 点按第一条重叠行：展开
clickRow(rows.b1);
rows = draw(ui);
const opened = { id: ui.model.whyId, b: whyOf(rows.b1), c: whyOf(rows.c1), text: texts(rows.b1) };
// 点第二条：第一条自动收起
clickRow(rows.c1);
rows = draw(ui);
const second = { id: ui.model.whyId, b: whyOf(rows.b1), c: whyOf(rows.c1), text: texts(rows.c1) };
// 再点第二条：收起
clickRow(rows.c1);
rows = draw(ui);
out.push({ first, opened, second, closed: { id: ui.model.whyId, c: whyOf(rows.c1) } });
""")[0]
        self.assertTrue(out["first"]["b"]["disabled"], "重叠行复选框禁用")
        self.assertEqual(out["first"]["b"]["flag"], 1)
        self.assertIn("不可加入", out["first"]["b"]["text"])
        self.assertIn("clash", out["first"]["b"]["clash"], "冲突行带 .clash 类")
        self.assertEqual(out["first"]["b"]["why"], 0, "没点之前没有原因面板")
        self.assertFalse(out["first"]["free"]["disabled"])
        self.assertEqual(out["first"]["free"]["flag"], 0)
        self.assertEqual(out["opened"]["id"], "b1")
        self.assertEqual(out["opened"]["b"], 1, "点按后行内多出原因面板")
        self.assertEqual(out["opened"]["c"], 0)
        self.assertIn("和已报名的活动时间重叠", out["opened"]["text"])
        self.assertIn("去已报名那场", out["opened"]["text"], "宿舍查寝可取消：有去已报名那场")
        self.assertEqual(out["second"]["id"], "c1")
        self.assertEqual(out["second"]["b"], 0, "展开第二条时第一条收起")
        self.assertEqual(out["second"]["c"], 1)
        self.assertIn("想报这一场，要先取消「宿舍查寝」的报名", out["second"]["text"])
        self.assertEqual(out["closed"], {"id": "", "c": 0}, "再点同一行收起")

    def test_reason_panel_for_the_no_cancel_case_has_no_link(self):
        out = run_phone_js(SETUP + DOM + r"""
const ui = PhoneUI;
ui.model.items = [Object.assign({}, signedA, { cancel_allowed: false }), clashB];
clockAt(ui.model);
let rows = draw(ui);
/* 原断言点行的第一个子元素：G05 后监听在行（label.row）上，改为行上直接点按 */
clickRow(rows.b1);
rows = draw(ui);
out.push({ text: texts(rows.b1), buttons: tags(rows.b1, "button").length });
""")[0]
        self.assertIn("「宿舍查寝」报名后不能取消，", out["text"])
        self.assertEqual(out["buttons"], 0)

    def test_inline_time_refund_and_note_and_no_buttons_on_signed_rows(self):
        out = run_phone_js(SETUP + DOM + r"""
const ui = PhoneUI;
ui.model.items = [signedA, clashB, clashC, freeD];
/* 原断言隐含「所有行都可见」：G08 段钮默认「可报名」，已报名行只在「全部」段渲染，
   看已报名行须先切段，断言语义不变 */
ui.model.filter.status = "all";
clockAt(ui.model);
const rows = draw(ui);
const nul = Object.assign({}, freeD, { id: "n1", name: "不明退改", cancel_allowed: null });
ui.model.items.push(nul);
const rows2 = draw(ui);
out.push({ signed: texts(rows.s1), signedButtons: tags(rows.s1, "button").length,
  clashC: texts(rows.c1), free: texts(rows.d1), nul: texts(rows2.n1),
  rfNo: tags(rows.c1, "span").some((s) => s.className === "rf no"), rfYes: tags(rows.d1, "span").some((s) => s.className === "rf") });
""")[0]
        self.assertIn("11月8日 22:40 – 11月10日 23:20（%s跨%s3%s天%s）" % (WJ, WJ, WJ, WJ), out["signed"])
        self.assertIn("可取消至 11月8日 14:00，在电脑上或" + WJ.join("学校网站取消。"), out["signed"])
        self.assertEqual(out["signedButtons"], 0, "手机上没有取消按钮")
        self.assertIn("报后不可退", out["clashC"])
        self.assertTrue(out["rfNo"])
        self.assertIn("报后可退", out["free"])
        self.assertTrue(out["rfYes"])
        self.assertNotIn("报后", out["nul"], "cancel_allowed 为 null 时不写")

    def test_no_note_without_a_trusted_clock(self):
        out = run_phone_js(SETUP + DOM + r"""
const ui = PhoneUI;
ui.model.items = [signedA];
/* G08 段钮默认「可报名」，已报名行只在「全部」段渲染：看已报名行须先切段 */
ui.model.filter.status = "all";
ui.model.clock = null;
const rows = draw(ui);
out.push(texts(rows.s1));
""")[0]
        self.assertNotIn("可取消至", out)


if __name__ == "__main__":
    unittest.main()
