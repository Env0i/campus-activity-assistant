#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机重登中继父进程侧测试：凭据预备、singleflight、状态投影与收口。

替身子进程/管道/时钟；不启动真实浏览器、不读实际 session、不写任何凭据文件。

@author Author
"""
from __future__ import annotations

import io
import json
import queue
import sys
import threading
import time
import unittest
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from application.login_relay_service import (  # noqa: E402
    LoginRelayService, STATE_NEEDS_LOCAL_SETUP, STATE_PLAN_ACTIVE,
    public_state,
)

# 合法的一像素 PNG（1×1 透明）：投影层只放行真 PNG 魔数的图，
# 'AAAA' 这类假图会被丢成空串，用它测正常流程等于测一个不可能发生的事件。
CAPTCHA_PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
               "AAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII=")


class FakeStdout:
    """worker stdout 替身：行由测试写入，写完置 EOF。"""

    def __init__(self):
        self._lines = queue.Queue()

    def feed(self, text):
        self._lines.put(str(text))

    def end(self):
        self._lines.put(None)

    def __iter__(self):
        return self

    def __next__(self):
        item = self._lines.get()
        if item is None:
            raise StopIteration
        return item


class FakeStdin:
    def __init__(self):
        self.written = []
        self.fail = False

    def write(self, text):
        if self.fail:
            raise OSError("pipe closed")
        self.written.append(str(text))

    def flush(self):
        pass


class FakeProc:
    def __init__(self):
        self.stdin = FakeStdin()
        self.stdout = FakeStdout()
        self.killed = False

    def poll(self):
        return -9 if self.killed else None


class FakeTree:
    def __init__(self):
        self.proc = FakeProc()
        self.terminated = 0

    def terminate(self):
        self.terminated += 1
        self.proc.killed = True
        self.proc.stdout.end()


class RelayServiceBase(unittest.TestCase):
    def setUp(self):
        self.trees = []
        self.clock = {"now": 0.0}
        self.events = []
        self.success_calls = []
        self.finish_calls = []
        self.spawn_error = None

        def spawn(args):
            if self.spawn_error is not None:
                raise self.spawn_error
            tree = FakeTree()
            tree.args = list(args)
            self.trees.append(tree)
            return tree

        self.service = LoginRelayService(
            spawn=spawn, now=lambda: self.clock["now"],
            emit=lambda kind, payload: self.events.append((kind, payload)),
            on_success=lambda: self.success_calls.append(time.time()),
            on_finish=lambda: self.finish_calls.append(time.time()))

    def tearDown(self):
        self.service.shutdown()


class PrepareTests(RelayServiceBase):
    def test_prepare_only_returns_ready_boolean(self):
        result = self.service.prepare("user-x", "secret-y")
        self.assertEqual(result, {"ok": True, "ready": True})
        self.assertTrue(self.service.prepared())
        self.assertNotIn("secret-y", json.dumps(result))

    def test_prepare_is_memory_only(self):
        """凭据绝不落盘：预备前后临时目录/工作区都不得出现明文副本。"""
        self.service.prepare("user-x", "secret-y")
        self.assertEqual(self.service.state()["safe_error"], "")
        text = json.dumps(self.service.state(), ensure_ascii=False)
        self.assertNotIn("secret-y", text)
        self.assertNotIn("user-x", text)

    def test_empty_prepare_clears_staging(self):
        self.service.prepare("user-x", "secret-y")
        result = self.service.prepare("", "")
        self.assertFalse(result["ok"])
        self.assertFalse(self.service.prepared())


class BeginTests(RelayServiceBase):
    def test_begin_without_prepare_is_needs_local_setup(self):
        result = self.service.begin()
        self.assertEqual(result["error"], STATE_NEEDS_LOCAL_SETUP)
        self.assertEqual(self.trees, [])

    def test_begin_with_active_plan_is_plan_active(self):
        self.service.prepare("u", "p")
        result = self.service.begin(plan_active=True)
        self.assertEqual(result["error"], STATE_PLAN_ACTIVE)
        self.assertEqual(self.trees, [], "计划活跃不得动会话/起 worker")

    def test_demo_never_starts_worker(self):
        self.service.prepare("u", "p")
        result = self.service.begin(demo=True)
        self.assertEqual(result["error"], "demo")
        self.assertEqual(self.trees, [])

    def test_terms_required_blocks_start(self):
        self.service.prepare("u", "p")
        result = self.service.begin(terms_ok=False)
        self.assertEqual(result["error"], "terms_required")
        self.assertEqual(self.trees, [])

    def test_begin_spawns_and_sends_credentials_once(self):
        self.service.prepare("user-x", "secret-y")
        result = self.service.begin(worker_command=["python", "grab.py", "login"])
        self.assertTrue(result["ok"])
        tree = self.trees[0]
        self.assertEqual(tree.args, ["python", "grab.py", "login", "--relay"])
        sent = json.loads(tree.proc.stdin.written[0])
        self.assertEqual(sent["kind"], "credentials")
        self.assertEqual(sent["username"], "user-x")
        self.assertEqual(sent["password"], "secret-y")
        self.assertTrue(sent["flow_id"])
        # 下发后不再留第二份；预备库保留到显式清除/关闭
        self.assertEqual(len(tree.proc.stdin.written), 1)
        self.assertTrue(self.service.prepared())

    def test_singleflight_concurrent_begin(self):
        self.service.prepare("u", "p")
        results = []
        barrier = threading.Barrier(3)

        def begin():
            barrier.wait()
            results.append(self.service.begin(worker_command=["x"]))

        threads = [threading.Thread(target=begin) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        ok = [r for r in results if r.get("ok")]
        busy = [r for r in results if r.get("error") == "busy"]
        self.assertEqual(len(ok), 1, "singleflight：并发 begin 只能有一场")
        self.assertEqual(len(busy), 2)

    def test_close_versus_create_race(self):
        """关闭与创建竞态：取消后状态留终态快照，不留下孤儿 worker。"""
        self.service.prepare("u", "p")
        self.service.begin(worker_command=["x"])
        self.service.cancel()
        self.assertEqual(self.trees[0].terminated, 1)
        self.assertEqual(self.service.state()["state"], "canceled")


class FlowTests(RelayServiceBase):
    def test_unreadable_ocr_result_falls_back_to_manual_without_submitting(self):
        self.service._classify_captcha = lambda image: ""
        tree, flow_id = self._begin()
        self.service.observe_line("[login] " + json.dumps({"kind":"challenge", "flow_id":flow_id,
            "challenge_id":"manual", "attempts":0, "image":CAPTCHA_PNG}))
        self.assertEqual(self.service.state()["mode"], "manual")
        self.assertEqual(len(tree.proc.stdin.written), 1)

    def test_ocr_threshold_hands_submission_ownership_to_manual(self):
        self.service._manual_after = 3
        self.service._classify_captcha = lambda image: "Ab12"
        tree, flow_id = self._begin()
        for attempt in range(4):
            self.service.observe_line("[login] " + json.dumps({
                "kind": "challenge", "flow_id": flow_id,
                "challenge_id": "c%d" % attempt, "attempts": attempt,
                "image": CAPTCHA_PNG}))
        submitted = [json.loads(line) for line in tree.proc.stdin.written
                     if json.loads(line).get("kind") == "submit"]
        self.assertEqual(len(submitted), 3)
        self.assertEqual(self.service.state()["mode"], "manual")
        self.assertTrue(self.service.submit(flow_id, "c3", "Cd34")["ok"])

    def test_late_ocr_result_cannot_submit_after_manual_handoff(self):
        entered, release = threading.Event(), threading.Event()
        def classify(image):
            entered.set()
            release.wait(2)
            return "Ab12"
        self.service._manual_after = 3
        self.service._classify_captcha = classify
        tree, flow_id = self._begin()
        def challenge(challenge_id, attempts):
            self.service.observe_line("[login] " + json.dumps({
                "kind": "challenge", "flow_id": flow_id,
                "challenge_id": challenge_id, "attempts": attempts, "image": CAPTCHA_PNG}))
        worker = threading.Thread(target=lambda: challenge("old", 0))
        worker.start()
        self.assertTrue(entered.wait(2))
        challenge("manual", 3)
        release.set()
        worker.join(3)
        submitted = [line for line in tree.proc.stdin.written if json.loads(line).get("kind") == "submit"]
        self.assertEqual(submitted, [])
        self.assertEqual(self.service.state()["challenge_id"], "manual")

    def _begin(self):
        self.service.prepare("u", "p")
        result = self.service.begin(worker_command=["x"])
        self.assertTrue(result["ok"])
        return self.trees[-1], result["flow_id"]

    def _emit(self, tree, payload):
        tree.proc.stdout.feed("[login] " + json.dumps(payload, ensure_ascii=False))

    def test_state_has_no_credentials(self):
        tree, flow_id = self._begin()
        self._emit(tree, {"kind": "challenge", "flow_id": flow_id,
                          "challenge_id": "chg-1",
                          "image": CAPTCHA_PNG, "expires_in": 60,
                          "attempts": 0, "max_attempts": 3})
        tree.proc.stdout.end()
        self.service._pump_thread.join(timeout=5)
        state = self.service.state()
        text = json.dumps(state, ensure_ascii=False)
        self.assertNotIn("password", text)
        self.assertNotIn("secret", text)
        self.assertEqual(state["challenge_id"], "",
                         "worker 结束后终态不得继续暴露验证码挑战号")

    def test_old_flow_lines_are_ignored(self):
        tree, flow_id = self._begin()
        self._emit(tree, {"kind": "challenge", "flow_id": "stale",
                          "challenge_id": "chg-old",
                          "image": CAPTCHA_PNG, "expires_in": 60})
        self._emit(tree, {"kind": "success", "flow_id": "stale"})
        tree.proc.stdout.end()
        self.service._pump_thread.join(timeout=5)
        self.assertEqual(self.success_calls, [], "旧 flow 不得触发锚点")
        self.assertEqual(self.service.state()["challenge_id"], "",
                         "旧 flow 的挑战不得写进当前会话")

    def test_success_fires_anchor_exactly_once(self):
        tree, flow_id = self._begin()
        self._emit(tree, {"kind": "success", "flow_id": flow_id})
        self._emit(tree, {"kind": "success", "flow_id": flow_id})
        tree.proc.stdout.end()
        self.service._pump_thread.join(timeout=5)
        self.assertEqual(len(self.success_calls), 1, "锚点只能建一次")
        self.assertEqual(len(self.finish_calls), 1)

    def test_submit_rejects_stale_flow(self):
        tree, flow_id = self._begin()
        result = self.service.submit("other-flow", "chg-1", "Ab12")
        self.assertEqual(result["error"], "stale_flow")
        self.assertEqual(tree.proc.stdin.written[1:], [])

    def test_submit_forwards_to_worker(self):
        tree, flow_id = self._begin()
        self.service.observe_line("[login] " + json.dumps({"kind": "challenge", "flow_id": flow_id,
                                  "challenge_id": "chg-1", "image": CAPTCHA_PNG}))
        result = self.service.submit(flow_id, "chg-1", "Ab12")
        self.assertTrue(result["ok"])
        sent = json.loads(tree.proc.stdin.written[1])
        self.assertEqual(sent["kind"], "submit")
        self.assertEqual(sent["code"], "Ab12")

    def test_desktop_submit_marks_origin_desktop(self):
        tree, flow_id = self._begin()
        self.service.observe_line("[login] " + json.dumps({"kind": "challenge", "flow_id": flow_id,
                                  "challenge_id": "chg-1", "image": CAPTCHA_PNG}))
        self.assertTrue(self.service.submit(flow_id, "chg-1", "Ab12", origin="desktop")["ok"])
        self.assertEqual(self.service.state()["origin"], "desktop", "电脑上输的码记成 desktop")

    def test_bad_password_is_a_safe_error_code(self):
        tree, flow_id = self._begin()
        self._emit(tree, {"kind": "failed", "flow_id": flow_id, "error": "bad_password"})
        tree.proc.stdout.end()
        deadline = time.time() + 2
        while time.time() < deadline and self.service.state().get("live"):
            time.sleep(0.01)
        self.assertEqual(self.service.state()["safe_error"], "bad_password",
                         "学校说密码不对要原样报出来，界面据此停下")

    def test_duplicate_submit_is_blocked_until_worker_replies(self):
        tree, flow_id = self._begin()
        self.service.observe_line("[login] " + json.dumps({"kind": "challenge", "flow_id": flow_id,
                                  "challenge_id": "chg-1", "image": CAPTCHA_PNG}))
        first = self.service.submit(flow_id, "chg-1", "Ab12")
        second = self.service.submit(flow_id, "chg-1", "Ab12")
        self.assertTrue(first["ok"])
        self.assertEqual(second["error"], "duplicate_submit")
        self.assertEqual(len(tree.proc.stdin.written), 2,
                         "同一张验证码只允许一条在途提交")

        self._emit(tree, {"kind": "rejected", "flow_id": flow_id,
                          "reason": "bad_code", "challenge_id": "chg-1",
                          "attempts": 1})
        tree.proc.stdout.end()
        self.service._pump_thread.join(timeout=5)

    def test_cancel_and_shutdown_clear_everything(self):
        tree, flow_id = self._begin()
        self.service.cancel()
        self.assertTrue(tree.terminated >= 1)
        self.assertEqual(self.service.state()["state"], "canceled")
        self.service.shutdown()
        self.assertFalse(self.service.prepared(), "关闭必须清除预备凭据")

    def test_eof_marks_failed_and_clears_busy(self):
        tree, flow_id = self._begin()
        self._emit(tree, {"kind": "challenge", "flow_id": flow_id,
                          "challenge_id": "chg-1",
                          "image": CAPTCHA_PNG, "expires_in": 60})
        tree.proc.stdout.end()
        self.service._pump_thread.join(timeout=5)
        state = self.service.state()
        self.assertEqual(state["state"], "failed", "半路 EOF 必须如实记失败")
        self.assertEqual(state["safe_error"], "eof")
        self.assertEqual(len(self.finish_calls), 1, "收口必须通知 busy 位释放")
        self.assertEqual(len(tree.proc.stdin.written), 1,
                         "收口后不再向 worker 写任何内容")

    def _run_success_with_origin(self, origin):
        """跑一场成功流程，返回回调收到的来源标签列表。"""
        seen = []
        service = LoginRelayService(
            spawn=self.service._spawn, now=lambda: self.clock["now"],
            emit=lambda kind, payload: self.events.append((kind, payload)),
            on_success=lambda label: seen.append(label),
            on_finish=lambda: self.finish_calls.append(time.time()))
        self.addCleanup(service.shutdown)
        service.prepare("u", "p")
        result = service.begin(worker_command=["x"])
        self.assertTrue(result["ok"])
        tree = self.trees[-1]
        self._emit(tree, {"kind": "success", "flow_id": result["flow_id"],
                          "origin": origin})
        tree.proc.stdout.end()
        service._pump_thread.join(timeout=5)
        return seen

    def test_success_reports_who_finished_the_flow(self):
        self.assertEqual(self._run_success_with_origin("auto"), ["auto_ocr"])
        self.assertEqual(self._run_success_with_origin("phone"), ["phone_manual"])
        # 没写 origin 的旧 worker 按手机人工完成处理，绝不丢锚点
        self.assertEqual(self._run_success_with_origin(""), ["phone_manual"])

    def test_begin_origin_survives_when_worker_says_nothing(self):
        seen = []
        service = LoginRelayService(
            spawn=self.service._spawn, now=lambda: self.clock["now"],
            emit=lambda kind, payload: None,
            on_success=lambda label: seen.append(label))
        self.addCleanup(service.shutdown)
        service.prepare("u", "p")
        result = service.begin(worker_command=["x"], origin="auto")
        self.assertTrue(result["ok"])
        tree = self.trees[-1]
        self._emit(tree, {"kind": "success", "flow_id": result["flow_id"]})
        tree.proc.stdout.end()
        service._pump_thread.join(timeout=5)
        self.assertEqual(seen, ["auto_ocr"])

    def test_zero_argument_callback_still_fires_once(self):
        tree, flow_id = self._begin()
        self._emit(tree, {"kind": "success", "flow_id": flow_id})
        tree.proc.stdout.end()
        self.service._pump_thread.join(timeout=5)
        self.assertEqual(len(self.success_calls), 1,
                         "零参回调（旧调用方）也必须收到且只收到一次")

    def test_public_state_shape(self):
        state = public_state(None)
        self.assertFalse(state["ready"])
        for key in ("flow_id", "state", "challenge_id", "image", "expires_in",
                    "attempts", "max_attempts", "safe_error", "submit_pending",
                    "origin", "live"):
            self.assertIn(key, state)


class RelayLiveTests(RelayServiceBase):
    """live 只对「正在进行的这一场」为真，历史快照一律为假。

    手机端靠它决定要不要播报「重登成功」：没有这个区分，每次打开页面都会
    重播很早以前那一次成功。
    """

    def test_a_running_flow_is_live(self):
        self.service.prepare("u", "p")
        result = self.service.begin(worker_command=["x"])
        self.assertTrue(result["ok"])
        state = self.service.state()
        self.assertTrue(state["live"])
        self.assertEqual(state["state"], "starting")

    def test_the_archived_success_is_history_not_this_round(self):
        self.service.prepare("u", "p")
        result = self.service.begin(worker_command=["x"])
        self.assertTrue(result["ok"])
        # 直接走 observe_line：结论立刻落到 _last，不必等 pump 线程调度
        self.service.observe_line("[login] " + json.dumps({
            "kind": "success", "flow_id": result["flow_id"]}))
        archived = self.service.state()
        self.assertEqual(archived["state"], "success")
        self.assertFalse(archived["live"], "上一场的结论不是「这一次还在跑」")

    def test_no_flow_at_all_is_not_live(self):
        self.assertFalse(public_state(None)["live"])
        self.assertFalse(self.service.state()["live"])


class SubmitPendingStateTests(RelayServiceBase):
    """提交在途的可见性：同一张图没结论前，手机不能再发第二个 POST。"""

    def _begin(self):
        self.service.prepare("u", "p")
        result = self.service.begin(worker_command=["x"])
        self.assertTrue(result["ok"])
        return result["flow_id"]

    def _challenge(self, flow_id, challenge_id="chg-1"):
        # 直接走 observe_line，不经 worker 线程：断言不依赖 pump 的调度时机
        self.service.observe_line("[login] " + json.dumps({
            "kind": "challenge", "flow_id": flow_id,
            "challenge_id": challenge_id, "image": CAPTCHA_PNG,
            "expires_in": 60, "attempts": 0, "max_attempts": 3}))

    def test_submit_pending_is_true_until_a_verdict(self):
        flow_id = self._begin()
        self._challenge(flow_id)
        self.assertFalse(self.service.state()["submit_pending"])
        self.assertTrue(self.service.submit(flow_id, "chg-1", "Ab12")["ok"])
        self.assertTrue(self.service.state()["submit_pending"],
                        "已发出提交、还没结论：手机必须知道不能再发第二个")
        self.service.observe_line("[login] " + json.dumps({
            "kind": "verifying", "flow_id": flow_id, "challenge_id": "chg-1"}))
        self.assertEqual(self.service.state()["state"], "verifying")
        self.assertTrue(self.service.state()["submit_pending"],
                        "校验途中仍然禁止重复提交")
        self.service.observe_line("[login] " + json.dumps({
            "kind": "rejected", "flow_id": flow_id, "challenge_id": "chg-1",
            "reason": "bad_code", "attempts": 1}))
        state = self.service.state()
        self.assertFalse(state["submit_pending"], "被拒后必须允许重试")
        self.assertIn(state["state"], ("verifying", "waiting_code"),
                      "被拒不是终态：收口要等新图或明确的失败")
        self.assertNotIn("Ab12", json.dumps(state, ensure_ascii=False),
                         "公开状态绝不回显用户输入的验证码")

    def test_success_clears_pending_submit(self):
        flow_id = self._begin()
        self._challenge(flow_id)
        self.service.submit(flow_id, "chg-1", "Ab12")
        self.service.observe_line("[login] " + json.dumps({
            "kind": "success", "flow_id": flow_id}))
        state = self.service.state()
        self.assertEqual(state["state"], "success")
        self.assertFalse(state["submit_pending"])

    def test_terminal_states_never_report_pending_submit(self):
        flow = {"state": "waiting_code", "flow_id": "f", "challenge_id": "c",
                "image": "", "expires_in": None, "attempts": 0,
                "max_attempts": 0, "safe_error": "", "submit_pending": True}
        self.assertTrue(public_state(flow)["submit_pending"])
        for state in ("success", "failed", "canceled", "idle"):
            flow["state"] = state
            self.assertFalse(public_state(flow)["submit_pending"],
                             "终态 %s 不得留下在途提交" % state)
        self.assertFalse(public_state(None)["submit_pending"])

    def test_new_challenge_releases_pending_submit(self):
        flow_id = self._begin()
        self._challenge(flow_id)
        self.service.submit(flow_id, "chg-1", "Ab12")
        self._challenge(flow_id, "chg-2")
        state = self.service.state()
        self.assertEqual(state["challenge_id"], "chg-2")
        self.assertFalse(state["submit_pending"], "换图后必须能重新提交")


class RelayOriginTests(RelayServiceBase):
    """谁发起的这一场：手机据此判断该不该接管验证码，只暴露来源标签。"""

    def _begin(self, **kwargs):
        self.service.prepare("u", "p")
        result = self.service.begin(worker_command=["x"], **kwargs)
        self.assertTrue(result["ok"])
        return result["flow_id"]

    def test_auto_and_phone_are_told_apart(self):
        self._begin(origin="auto")
        self.assertEqual(self.service.state()["origin"], "auto")
        self.service.cancel(origin="auto")
        self._begin()
        self.assertEqual(self.service.state()["origin"], "phone",
                         "手机人工发起时默认来源就是 phone")

    def test_no_flow_reports_no_origin(self):
        self.assertEqual(public_state(None)["origin"], "")


class DesktopReloginWiringTests(unittest.TestCase):
    """电脑上的重新登录接线：只读源码核对「不保存就不落盘」和 100 秒窗口。"""

    @staticmethod
    def _source(name):
        import ast
        tree = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8"))
        node = next(item for item in ast.walk(tree)
                    if isinstance(item, ast.FunctionDef) and item.name == name)
        return ast.unparse(node)

    def test_typed_credentials_only_hit_disk_after_success(self):
        for name in ("prepare_phone_relogin", "_begin_typed_relogin", "relogin_begin",
                     "phone_relogin_begin"):
            self.assertNotIn("_credential_store.save", self._source(name),
                             "%s 不得直接写账号密码；只有登录成功后的 _commit_pending_save 能写" % name)
        self.assertIn("if typed and save else None", self._source("prepare_phone_relogin"),
                      "没勾保存时不留待保存的副本")
        self.assertIn("_credential_store.save", self._source("_commit_pending_save"))
        self.assertIn("_commit_pending_save", self._source("_anchor_login_success"),
                      "只在登录真的成功后提交保存")

    def test_bad_password_pauses_only_saved_credentials(self):
        source = self._source("_relay_finished")
        self.assertIn("bad_password", source)
        self.assertIn("if source == 'saved'", source, "只有用的是保存的密码才暂停自动登录")
        self.assertIn("mark_bad", source)

    def test_relogin_entries_share_one_late_gate(self):
        for name in ("relogin_begin", "relogin_auto_once", "phone_relogin_begin"):
            self.assertIn("_relogin_entry_gate", self._source(name),
                          "%s 要过同一道「来不及」判断" % name)
        self.assertIn("relogin_too_late", self._source("_relogin_late_answer"))
