#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机重登 worker 侧编排测试：fake page/input/token/post/pipe/clock。

不启动真实浏览器、不读实际 session、不连学校；凭据绝不落盘、不进 HTTP。

@author Author
"""
from __future__ import annotations

import io
import json
import os
import queue
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

import login_relay  # noqa: E402
import grab  # noqa: E402
from application.login_relay_service import (  # noqa: E402
    LoginRelayService, public_state,
)
from grab import save_verified_files  # noqa: E402
from login_relay import (  # noqa: E402
    ChallengeBook, extract_captcha_image, fill_login_form, parse_client_line,
    run_http_relay, run_relay, valid_code,
)

TMP_ROOT = tempfile.gettempdir()

PNG_B64 = ("data:image/png;base64,"
           "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
           "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


class FakeStdin:
    """管道替身：行由测试写入，close 后 reader 收 EOF。"""

    def __init__(self):
        self._lines = queue.Queue()

    def write_line(self, text):
        self._lines.put(str(text))

    def close(self):
        self._lines.put(None)

    def __iter__(self):
        return self

    def __next__(self):
        item = self._lines.get()
        if item is None:
            raise StopIteration
        return item


class FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    def nth(self, index):
        self.page.nth_calls.append((self.selector, index))
        return self

    def fill(self, text):
        self.page.fills.append((self.selector, text))

    def click(self):
        self.page.clicks.append(self.selector)
        if self.selector == login_relay.SUBMIT_SELECTOR and self.page.on_submit:
            self.page.on_submit()


class FakeResponse:
    def __init__(self, url, payload):
        self.url = url
        self._body = json.dumps(payload).encode("utf-8")

    def body(self):
        return self._body


class FakeCtx:
    def __init__(self):
        self.closed = False

    def storage_state(self):
        return {"cookies": []}

    def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakePage:
    def __init__(self):
        self.fills = []
        self.clicks = []
        self.nth_calls = []
        self.handlers = {}
        self.closed = False
        self.token = ""
        self.storage = {}
        self.on_submit = None
        self.on_goto = None
        self.fail_locate = False
        self.clock = None

    def locator(self, selector):
        if self.fail_locate:
            raise RuntimeError("no such element: %s" % selector)
        return FakeLocator(self, selector)

    def on(self, event, fn):
        self.handlers[event] = fn

    def goto(self, url):
        self.gone_to = url
        if self.on_goto:
            self.on_goto()

    def is_closed(self):
        return self.closed

    def wait_for_timeout(self, ms):
        if self.clock is not None:
            self.clock["now"] += max(0.0, ms / 1000.0)

    def evaluate(self, js):
        if "getItem('%s')" % login_relay.TOKEN_KEY in js or "xgUniToken" in js:
            return self.token
        return dict(self.storage)

    def emit_response(self, url, payload):
        self.handlers["response"](FakeResponse(url, payload))


class FakeDeps:
    login_url = "http://school.example/stu/#/login"

    def __init__(self):
        self.clock = {"now": 100.0}
        self.page = FakePage()
        self.page.clock = self.clock
        self.ctx = FakeCtx()
        self.browser = FakeBrowser()
        self.posts = []
        self.post_result = {"code": "1"}
        self.sessions = []
        self.states = []
        self.ids = 0
        self.fail_open = False

    def now(self):
        return self.clock["now"]

    def sleep(self, seconds):
        self.clock["now"] += float(seconds)

    def new_id(self):
        self.ids += 1
        return "chg-%d" % self.ids

    def open_page(self):
        if self.fail_open:
            raise RuntimeError("no browser")
        return self.page, self.ctx, self.browser

    def post(self, path, payload, tok):
        self.posts.append((path, payload, tok))
        return self.post_result

    def save_session(self, session):
        self.sessions.append(session)

    def save_state(self, state):
        self.states.append(state)


def run_scripted(deps, stdin, lines):
    """把脚本行先写进 FakeStdin 再跑 run_relay；返回 (code, 输出行)。"""
    for line in lines:
        stdin.write_line(json.dumps(line, ensure_ascii=False))
    out = io.StringIO()
    code = run_relay(deps=deps, stdin=stdin, stdout=out)
    stdin.close()          # 放行 reader 线程退出（生产里父进程握着管道）
    parsed = []
    for raw in out.getvalue().splitlines():
        if raw.startswith(login_relay.LOGIN_PREFIX):
            parsed.append(json.loads(raw[len(login_relay.LOGIN_PREFIX):]))
    return code, parsed


def credentials(flow="flow-1"):
    return {"kind": "credentials", "flow_id": flow,
            "username": "user-x", "password": "secret-y"}


class PureRuleTests(unittest.TestCase):
    def test_school_request_signature_matches_public_bundle_vector(self):
        body = b'{"client":"x","userType":"2"}'
        headers = grab.sign_request_headers(
            "/auth/login", body, 1700000000123,
            "0123456789abcdef0123456789abcdef",
        )
        self.assertEqual(headers, {
            "X-Page-Ticket":
                "604bc7c55e6b1333fc25a9ea68800771be52c9df6a24651dc020f3f7d89aa1ae",
            "X-Timestamp": "1700000000123",
            "X-Nonce": "0123456789abcdef0123456789abcdef",
            "X-Token":
                "==QDPMjLB53bpRhJ9pWBBIjYZhHG6kAU85XCh0naHcCDhRwd14CV99nfLkyC+5FPLEGSrZiLS1Hb+9QLt9XT/sQdAEFG6Akb85XG24WacRTM3Fwc2wSVl9Wf",
        })

    def test_valid_code_requires_four_alnum(self):
        self.assertTrue(valid_code("Ab12"))
        self.assertFalse(valid_code("abc"))
        self.assertFalse(valid_code("Ab123"))
        self.assertFalse(valid_code("ab 1"))
        self.assertFalse(valid_code(""))

    def test_parse_client_line_rejects_garbage(self):
        self.assertIsNone(parse_client_line("not-json"))
        self.assertIsNone(parse_client_line("[1,2]"))
        self.assertIsNone(parse_client_line("x" * 5000))
        self.assertEqual(parse_client_line('{"kind":"cancel"}')["kind"], "cancel")

    def test_extract_captcha_image_requires_png(self):
        self.assertEqual(extract_captcha_image({"data": {"image": PNG_B64}}), PNG_B64)
        self.assertIsNone(extract_captcha_image({"data": {"image": "data:image/png;base64,zzz"}}))
        self.assertIsNone(extract_captcha_image({"data": {"image": "data:image/jpeg;base64,AAAA"}}))
        self.assertIsNone(extract_captcha_image({"data": {}}))
        self.assertIsNone(extract_captcha_image(None))

    def test_fill_login_form_uses_server_selectors(self):
        page = FakePage()
        fill_login_form(page, "u", "p", "Ab12")
        self.assertEqual(page.nth_calls, [("input", 0), ("input", 1), ("input", 2)])
        self.assertEqual(page.clicks, ["uni-checkbox", "uni-button.view-form-box-btn"])
        self.assertEqual([text for _sel, text in page.fills], ["u", "p", "Ab12"])


class ChallengeBookTests(unittest.TestCase):
    def test_accepts_once_then_consumed(self):
        book = ChallengeBook("flow-1")
        self.assertTrue(book.open_challenge("chg-1", 10.0))
        ok, err = book.accept("flow-1", "chg-1", "Ab12", 10.0)
        self.assertTrue(ok)
        again, err = book.accept("flow-1", "chg-1", "Ab12", 10.0)
        self.assertFalse(again)
        self.assertEqual(err, "consumed")

    def test_stale_flow_and_challenge_rejected(self):
        book = ChallengeBook("flow-1")
        book.open_challenge("chg-1", 10.0)
        self.assertEqual(book.accept("other", "chg-1", "Ab12", 10.0)[1], "stale_flow")
        self.assertEqual(book.accept("flow-1", "chg-9", "Ab12", 10.0)[1], "stale_challenge")

    def test_delayed_challenge_stays_valid_and_bad_code_is_rejected(self):
        book = ChallengeBook("flow-1", ttl_s=60, max_tries=1)
        book.open_challenge("chg-1", 10.0)
        self.assertEqual(book.accept("flow-1", "chg-1", "Ab12", 71.0), (True, ""))
        book.open_challenge("chg-2", 100.0)
        self.assertEqual(book.accept("flow-1", "chg-2", "ab!", 100.0)[1], "bad_code")

    def test_refresh_gap_blocks_rapid_reopen(self):
        book = ChallengeBook("flow-1", refresh_gap_s=3.0)
        self.assertTrue(book.open_challenge("chg-1", 10.0))
        self.assertFalse(book.open_challenge("chg-2", 11.0))
        self.assertTrue(book.open_challenge("chg-3", 13.0))

    def test_submission_count_has_no_upper_bound(self):
        book = ChallengeBook("flow-1", max_tries=3, refresh_gap_s=0.0)
        for index in range(5):
            book.open_challenge("chg-%d" % index, 10.0 + index)
            self.assertTrue(book.accept("flow-1", "chg-%d" % index, "Ab12",
                                        10.0 + index)[0])


class RelaySessionTests(unittest.TestCase):
    def _happy(self, deps, *, token_after="new-token-1", login_code=1):
        page = deps.page
        page.storage = {"user": json.dumps({"xm": "张三", "xh": "1"}), "xm": "张三"}

        def on_goto():
            page.emit_response("http://school.example/api/captcha",
                               {"data": {"image": PNG_B64}})

        def on_submit():
            page.emit_response("http://school.example/api/login",
                               {"code": login_code, "msg": "ok"})
            page.token = token_after

        page.on_goto = on_goto
        page.on_submit = on_submit
        return page

    def _submit(self, code="Ab12", flow="flow-1", challenge="chg-1"):
        return {"kind": "submit", "flow_id": flow, "challenge_id": challenge,
                "code": code}

    def test_success_requires_new_token_and_verified_post(self):
        deps = FakeDeps()
        self._happy(deps)
        stdin = FakeStdin()
        code, lines = run_scripted(deps, stdin, [credentials(), self._submit()])
        self.assertEqual(code, 0)
        self.assertTrue(any(line.get("kind") == "success" for line in lines))
        self.assertEqual(deps.posts[0][2], "new-token-1")
        self.assertEqual(deps.sessions[0]["token"], "new-token-1")
        self.assertEqual(deps.sessions[0]["name"], "张三")

    def test_old_token_passing_probe_is_not_success(self):
        """旧 token 轮询成功不得冒充新登录成功。"""
        deps = FakeDeps()
        page = self._happy(deps, token_after="old-token")
        page.token = "old-token"          # 开页前就有旧 token
        stdin = FakeStdin()
        code, lines = run_scripted(deps, stdin, [credentials(), self._submit()])
        self.assertEqual(code, 3)
        self.assertEqual(lines[-1]["error"], "token_unverified")
        self.assertEqual(deps.sessions, [], "失败不得改写旧会话")
        self.assertEqual(deps.states, [])

    def test_new_token_failing_probe_is_not_success(self):
        deps = FakeDeps()
        self._happy(deps)
        deps.post_result = {"code": 4001}
        stdin = FakeStdin()
        code, lines = run_scripted(deps, stdin, [credentials(), self._submit()])
        self.assertEqual(code, 3)
        self.assertEqual(lines[-1]["error"], "token_unverified")
        self.assertEqual(deps.sessions, [])
        self.assertEqual(deps.states, [], "校验失败不得覆盖 storage_state")

    def test_login_response_required_before_success(self):
        """只有 captcha、没有 login 应答：不得凭旧 token 成功。"""
        deps = FakeDeps()
        page = deps.page
        page.token = "old"

        def on_goto():
            page.emit_response("http://school.example/api/captcha",
                               {"data": {"image": PNG_B64}})

        page.on_goto = on_goto
        stdin = FakeStdin()
        code, lines = run_scripted(deps, stdin, [
            credentials(),
            {"kind": "cancel", "flow_id": "flow-1"},
        ])
        self.assertEqual(code, 5)
        self.assertEqual(deps.sessions, [])

    def test_credentials_never_appear_in_output(self):
        deps = FakeDeps()
        self._happy(deps)
        stdin = FakeStdin()
        _, lines = run_scripted(deps, stdin, [credentials(), self._submit()])
        text = json.dumps(lines, ensure_ascii=False)
        self.assertNotIn("secret-y", text)
        self.assertNotIn("user-x", text)
        self.assertNotIn("new-token-1", text)

    def test_bad_page_structure_fails_safely(self):
        deps = FakeDeps()
        page = self._happy(deps)
        page.fail_locate = True
        stdin = FakeStdin()
        code, lines = run_scripted(deps, stdin, [credentials(), self._submit()])
        self.assertEqual(code, 2)
        self.assertEqual(lines[-1]["error"], "bad_page")
        self.assertEqual(deps.sessions, [], "页面结构不符不得假成功")

    def test_open_page_failure_and_cancel_and_eof_cleanup(self):
        deps = FakeDeps()
        deps.fail_open = True
        stdin = FakeStdin()
        code, lines = run_scripted(deps, stdin, [credentials()])
        self.assertEqual(code, 2)
        self.assertEqual(lines[-1]["error"], "bad_page")

        deps = FakeDeps()
        self._happy(deps)
        stdin = FakeStdin()
        code, lines = run_scripted(deps, stdin, [
            credentials(),
            {"kind": "cancel", "flow_id": "flow-1"},
        ])
        self.assertEqual(code, 5)
        self.assertTrue(deps.ctx.closed and deps.browser.closed)

        deps = FakeDeps()
        stdin = FakeStdin()
        stdin.close()                    # 父进程先关管道：worker 必须收口
        code, lines = run_scripted(deps, stdin, [])
        self.assertEqual(code, 1)
        self.assertEqual(lines[-1]["error"], "eof")

    def test_stale_and_illegal_codes_are_rejected(self):
        deps = FakeDeps()
        self._happy(deps)
        stdin = FakeStdin()
        code, lines = run_scripted(deps, stdin, [
            credentials(),
            self._submit(code="Ab12", flow="old-flow"),
            self._submit(code="xy!"),
            self._submit(code="Ab12"),
        ])
        kinds = [(line.get("kind"), line.get("reason")) for line in lines]
        self.assertIn(("rejected", "stale_flow"), kinds)
        self.assertIn(("rejected", "bad_code"), kinds)
        self.assertTrue(any(kind == "success" for kind, _ in kinds))

    def test_delayed_challenge_is_still_accepted(self):
        deps = FakeDeps()
        self._happy(deps)
        stdin = FakeStdin()
        code, lines = run_scripted(deps, stdin, [credentials(), self._submit()])
        self.assertEqual(code, 0)
        self.assertTrue(any(line.get("kind") == "success" for line in lines))
        self.assertEqual(len(deps.sessions), 1)

    def test_duplicate_code_and_old_challenge_rejected(self):
        deps = FakeDeps()
        self._happy(deps)
        stdin = FakeStdin()
        code, lines = run_scripted(deps, stdin, [
            credentials(),
            self._submit(code="Ab12"),
            self._submit(code="Bb34"),          # 旧挑战已消费
        ])
        kinds = [(line.get("kind"), line.get("reason")) for line in lines]
        self.assertIn(("rejected", "consumed"), kinds)
        self.assertTrue(any(kind == "success" for kind, _ in kinds))


class HeldPipe:
    """stdout 替身：测试收尾前不给 EOF，让 pump 保持等待。"""

    def __init__(self):
        self._q = queue.Queue()

    def __iter__(self):
        return self

    def __next__(self):
        item = self._q.get()
        if item is None:
            raise StopIteration
        return item

    def close(self):
        self._q.put(None)


class LineSink:
    """stdin 替身：记录每行下发，绝不落盘。"""

    def __init__(self):
        self.written = []

    def write(self, text):
        self.written.append(str(text))

    def flush(self):
        pass


class FakeWorker:
    def __init__(self):
        self.stdin = LineSink()
        self.stdout = HeldPipe()
        self.terminated = False

    def terminate(self):
        self.terminated = True
        self.stdout.close()


class OcrFallbackTests(unittest.TestCase):
    """relay 侧 ddddocr 门禁：识别无效/失败一律保留人工输入，不自动提交。"""

    def setUp(self):
        self.worker = FakeWorker()
        self.classify_result = ""
        self.classify_raises = False
        self.anchor_calls = []

        def classify(_image):
            if self.classify_raises:
                raise RuntimeError("ocr engine broken")
            return self.classify_result

        self.service = LoginRelayService(
            spawn=lambda _args: self.worker, now=lambda: 100.0,
            on_success=lambda: self.anchor_calls.append(1),
            classify_captcha=classify)
        self.addCleanup(self._teardown)
        self.assertTrue(self.service.prepare("user", "S3cret-pass")["ok"])
        started = self.service.begin(worker_command=["login-worker"])
        self.assertTrue(started["ok"], started)
        self.flow_id = started["flow_id"]

    def _teardown(self):
        self.service.cancel()
        self.worker.stdout.close()
        self.service.shutdown()

    def _challenge_line(self, **fields):
        payload = {"flow_id": self.flow_id, "kind": "challenge",
                   "challenge_id": "c1", "image": PNG_B64,
                   "expires_in": None, "attempts": 0, "max_attempts": 0}
        payload.update(fields)
        return "[login] " + json.dumps(payload)

    def _submits(self):
        out = []
        for text in self.worker.stdin.written:
            try:
                data = json.loads(text)
            except ValueError:
                continue
            if data.get("kind") == "submit":
                out.append(data)
        return out

    def test_valid_ocr_code_is_submitted_automatically(self):
        self.classify_result = "Ab12"
        self.service.observe_line(self._challenge_line())
        submits = self._submits()
        self.assertEqual(len(submits), 1)
        self.assertEqual(submits[0]["code"], "Ab12")
        self.assertEqual(submits[0]["challenge_id"], "c1")
        self.assertEqual(self.service.state()["state"], "verifying")

    def test_empty_ocr_keeps_manual_input(self):
        self.classify_result = ""
        self.service.observe_line(self._challenge_line())
        self.assertEqual(self._submits(), [])
        state = self.service.state()
        self.assertEqual(state["state"], "waiting_code")
        self.assertEqual(state["image"], PNG_B64, "人工输入仍要拿到验证码图")

    def test_wrong_shape_code_is_not_auto_submitted(self):
        for bad in ("12", "12345", "ab!d", "Ab 2", "ＡＢ１２"):
            self.classify_result = bad
            with self.subTest(code=bad):
                self.service.observe_line(self._challenge_line())
                self.assertEqual(self._submits(), [])
                self.assertEqual(self.service.state()["state"], "waiting_code")

    def test_engine_exception_keeps_manual_input(self):
        self.classify_raises = True
        self.service.observe_line(self._challenge_line())
        self.assertEqual(self._submits(), [])
        self.assertEqual(self.service.state()["state"], "waiting_code")

    def test_manual_submit_still_works_after_ocr_miss(self):
        self.classify_result = ""
        self.service.observe_line(self._challenge_line())
        result = self.service.submit(self.flow_id, "c1", "Ab12")
        self.assertTrue(result["ok"])
        self.assertEqual([s["code"] for s in self._submits()], ["Ab12"])

    def test_state_projection_never_carries_credentials(self):
        self.classify_result = "Ab12"
        self.service.observe_line(self._challenge_line())
        text = str(self.service.state())
        self.assertNotIn("S3cret-pass", text)
        self.assertNotIn("password", text.lower())


class ChallengeProjectionTests(unittest.TestCase):
    """验证码公开状态不提供倒计时，也不提供提交次数上限。"""

    def setUp(self):
        self.worker = FakeWorker()
        self.clock = {"now": 100.0}
        self.events = []
        self.service = LoginRelayService(
            spawn=lambda _args: self.worker, now=lambda: self.clock["now"],
            emit=lambda kind, payload: self.events.append((kind, payload)))
        self.addCleanup(self._teardown)
        self.assertTrue(self.service.prepare("user", "pass")["ok"])
        started = self.service.begin(worker_command=["login-worker"])
        self.assertTrue(started["ok"], started)
        self.flow_id = started["flow_id"]

    def _teardown(self):
        self.service.cancel()
        self.worker.stdout.close()
        self.service.shutdown()

    def _challenge(self, **fields):
        payload = {"flow_id": self.flow_id, "kind": "challenge",
                   "challenge_id": "c1", "image": PNG_B64,
                       "expires_in": None, "attempts": 0, "max_attempts": 0}
        payload.update(fields)
        self.service.observe_line("[login] " + json.dumps(payload))

    def test_active_challenge_has_no_countdown(self):
        self._challenge()
        self.assertIsNone(self.service.state()["expires_in"])
        self.clock["now"] = 100.5
        self.assertIsNone(self.service.state()["expires_in"])
        self.clock["now"] = 130.0
        self.assertIsNone(self.service.state()["expires_in"])
        self.clock["now"] = 159.999
        self.assertIsNone(self.service.state()["expires_in"])
        self.clock["now"] = 161.0
        self.assertIsNone(self.service.state()["expires_in"])

    def test_same_challenge_update_does_not_reset_ttl(self):
        self._challenge()
        self.clock["now"] = 130.0
        self._challenge()
        self.assertIsNone(self.service.state()["expires_in"],
                          "同一 challenge 的事件更新不得引入倒计时")
        self.clock["now"] = 161.0
        self.assertIsNone(self.service.state()["expires_in"])

    def test_same_challenge_update_does_not_clear_entered_state(self):
        self._challenge()
        self.service.observe_line("[login] " + json.dumps({
            "flow_id": self.flow_id, "kind": "rejected", "reason": "bad_code",
            "challenge_id": "c1", "attempts": 1}))
        self.assertEqual(self.service.state()["attempts"], 1)
        events_before = len(self.events)
        self._challenge(attempts=0)             # 陈旧重放：归零不得生效
        state = self.service.state()
        self.assertEqual(state["attempts"], 1,
                         "同一 challenge 的事件更新不得清空已输入状态")
        self.assertEqual(state["challenge_id"], "c1")
        self.assertEqual(state["image"], PNG_B64)
        self.assertEqual(len(self.events), events_before,
                         "重放不得补发事件：手机会把新事件当新验证码清掉正在输入的码")

    def test_same_challenge_update_does_not_revert_verifying(self):
        self._challenge()
        self.service.observe_line("[login] " + json.dumps({
            "flow_id": self.flow_id, "kind": "verifying", "challenge_id": "c1"}))
        self.assertEqual(self.service.state()["state"], "verifying")
        self._challenge()
        self.assertEqual(self.service.state()["state"], "verifying",
                         "同一 challenge 的事件更新不得清掉已提交的验证进度")

    def test_new_challenge_gets_fresh_deadline(self):
        self._challenge()
        self.clock["now"] = 130.0
        self._challenge(challenge_id="c2")
        state = self.service.state()
        self.assertEqual(state["challenge_id"], "c2")
        self.assertIsNone(state["expires_in"])
        self.clock["now"] = 190.0
        self.assertIsNone(self.service.state()["expires_in"])

    def test_public_state_keeps_old_call_compatible(self):
        self.assertEqual(public_state(None)["expires_in"], 0)
        flow = {"state": "waiting_code", "flow_id": "f", "challenge_id": "c",
                "image": "", "expires_in": 60, "attempts": 0,
                "max_attempts": 3, "safe_error": ""}
        self.assertIsNone(public_state(flow)["expires_in"])
        self.assertIsNone(public_state(flow, 133.3)["expires_in"])
        self.assertIsNone(public_state(flow, 250.0)["expires_in"])


class TerminalStateCleanupTests(unittest.TestCase):
    """终态对外清理：success/failed/canceled/idle 不再暴露旧图、挑战与剩余秒。"""

    def setUp(self):
        self.worker = FakeWorker()
        self.clock = {"now": 100.0}
        self.events = []
        self.service = LoginRelayService(
            spawn=lambda _args: self.worker, now=lambda: self.clock["now"],
            emit=lambda kind, payload: self.events.append((kind, payload)))
        self.addCleanup(self._teardown)
        self.assertTrue(self.service.prepare("user", "pass")["ok"])
        started = self.service.begin(worker_command=["login-worker"])
        self.assertTrue(started["ok"], started)
        self.flow_id = started["flow_id"]

    def _teardown(self):
        self.service.cancel()
        self.worker.stdout.close()
        self.service.shutdown()

    def _line(self, kind, **fields):
        payload = {"flow_id": self.flow_id, "kind": kind}
        payload.update(fields)
        self.service.observe_line("[login] " + json.dumps(payload))

    def _challenge(self, **fields):
        payload = {"challenge_id": "c1", "image": PNG_B64,
                   "expires_in": None, "attempts": 0, "max_attempts": 0}
        payload.update(fields)
        self._line("challenge", **payload)

    def _assert_cleaned(self, state, *, state_name, safe_error="", attempts=0):
        self.assertEqual(state["state"], state_name)
        self.assertEqual(state["image"], "", "终态不得再暴露验证码图")
        self.assertEqual(state["challenge_id"], "", "终态不得再暴露挑战号")
        self.assertEqual(state["expires_in"], 0, "终态不得再暴露剩余秒")
        self.assertEqual(state["flow_id"], self.flow_id, "flow_id 不受清理影响")
        self.assertEqual(state["safe_error"], safe_error, "安全错误码不受清理影响")
        self.assertEqual(state["attempts"], attempts, "尝试计数不受清理影响")
        self.assertEqual(state["max_attempts"], 0)

    def test_public_state_terminal_states_zero_image_and_challenge(self):
        flow = {"state": "waiting_code", "flow_id": "f", "challenge_id": "c",
                "image": PNG_B64, "expires_in": 60, "deadline": 200.0,
                "attempts": 1, "max_attempts": 3, "safe_error": "expired"}
        for name in ("success", "failed", "canceled", "idle"):
            flow["state"] = name
            out = public_state(flow, 133.3)
            self.assertEqual(out["image"], "")
            self.assertEqual(out["challenge_id"], "")
            self.assertEqual(out["expires_in"], 0)
            self.assertEqual(out["flow_id"], "f")
            self.assertEqual(out["state"], name)
            self.assertEqual(out["safe_error"], "expired")
            self.assertEqual(out["attempts"], 1)
            self.assertEqual(out["max_attempts"], 0)
        flow["state"] = "waiting_code"
        out = public_state(flow, 133.3)
        self.assertEqual(out["image"], PNG_B64, "非终态照常放行验证码图")
        self.assertEqual(out["challenge_id"], "c")
        self.assertIsNone(out["expires_in"])

    def test_success_path_cleans_public_state(self):
        self._challenge()
        self.assertEqual(self.service.state()["image"], PNG_B64)
        self._line("success")
        self._assert_cleaned(self.service.state(), state_name="success")
        self._assert_cleaned(self.events[-1][1], state_name="success",
                             safe_error="", attempts=0)

    def test_failed_path_cleans_public_state_and_keeps_error(self):
        self._challenge(attempts=2)
        self._line("failed", error="bad_page")
        self._assert_cleaned(self.service.state(), state_name="failed",
                             safe_error="bad_page", attempts=2)
        self._assert_cleaned(self.events[-1][1], state_name="failed",
                             safe_error="bad_page", attempts=2)

    def test_cancel_path_cleans_public_state(self):
        self._challenge()
        self.assertTrue(self.service.cancel()["ok"])
        self._assert_cleaned(self.service.state(), state_name="canceled")

    def test_eof_path_cleans_public_state(self):
        self._challenge()
        self.worker.stdout.close()
        self.service._pump_thread.join(timeout=5)
        self._assert_cleaned(self.service.state(), state_name="failed",
                             safe_error="eof")
        self._assert_cleaned(self.events[-1][1], state_name="failed",
                             safe_error="eof")

    def test_shutdown_path_cleans_public_state(self):
        self._challenge()
        self.service.shutdown()
        self._assert_cleaned(self.service.state(), state_name="canceled")


class HttpDeps(FakeDeps):
    """匿名 HTTP 替身；成功只允许通过双文件事务端口保存。"""

    def __init__(self):
        super().__init__()
        self.responses = {
            login_relay.AUTH_CAPTCHA_PATH: {
                "code": 1, "data": {"key": "uuid-new", "image": PNG_B64}},
            login_relay.AUTH_LOGIN_PATH: {
                "code": 1, "data": {"token": "token-new"}},
            "/rjyHd/listActivity": {"code": 1},
        }
        self.saved = []
        self.fail_save = False

    def sleep(self, seconds):
        super().sleep(seconds)
        # 假时钟推进仍需给真实 stdin reader 一次调度机会。
        time.sleep(0.0001)

    def post(self, path, payload, tok):
        self.posts.append((path, dict(payload), tok))
        response = self.responses[path]
        if isinstance(response, Exception):
            raise response
        return response

    def save_verified(self, state, session):
        if self.fail_save:
            raise OSError("secret-y token-new")
        self.saved.append((state, session))


def run_http_scripted(deps, mode="submit"):
    stdin = FakeStdin()
    stdin.write_line(json.dumps(credentials()))

    class Output(io.StringIO):
        def write(self, text):
            count = super().write(text)
            for raw in text.splitlines():
                if not raw.startswith(login_relay.LOGIN_PREFIX):
                    continue
                event = json.loads(raw[len(login_relay.LOGIN_PREFIX):])
                if event.get("kind") != "challenge":
                    continue
                if mode == "expired":
                    deps.clock["now"] += login_relay.CHALLENGE_TTL_S + 1
                if mode != "cancel":
                    stdin.write_line(json.dumps({
                        "kind": "submit", "flow_id": "flow-1", "code": "Ab12",
                        "challenge_id": "wrong" if mode == "wrong" else event["challenge_id"]}))
                if mode in ("cancel", "wrong", "expired"):
                    stdin.write_line(json.dumps({"kind": "cancel", "flow_id": "flow-1"}))
            return count

    output = Output()
    try:
        with mock.patch.object(login_relay, "_relay_session", return_value=73) as fallback:
            code = run_http_relay(deps=deps, stdin=stdin, stdout=output, pw_deps=object())
    finally:
        stdin.close()
    events = [json.loads(line[len(login_relay.LOGIN_PREFIX):])
              for line in output.getvalue().splitlines()
              if line.startswith(login_relay.LOGIN_PREFIX)]
    return code, events, fallback, output.getvalue()


class HttpRelayTests(unittest.TestCase):
    def test_anonymous_flow_verifies_this_token_then_saves_once(self):
        deps = HttpDeps()
        code, events, fallback, output = run_http_scripted(deps)
        self.assertEqual(code, 0)
        fallback.assert_not_called()
        self.assertEqual(deps.posts[0], (login_relay.AUTH_CAPTCHA_PATH,
                         {"client": login_relay.AUTH_CLIENT, "userType": "2"}, ""))
        self.assertEqual(deps.posts[1], (login_relay.AUTH_LOGIN_PATH, {
            "userName": "user-x", "pwd": "secret-y", "code": "Ab12",
            "uuid": "uuid-new", "userType": "2", "client": login_relay.AUTH_CLIENT,
            "grantType": "pwd"}, ""))
        self.assertEqual(deps.posts[2][0], "/rjyHd/listActivity")
        self.assertEqual(deps.posts[2][2], "token-new")
        self.assertEqual(len(deps.saved), 1)
        self.assertEqual(deps.saved[0][1]["token"], "token-new")
        self.assertEqual(deps.saved[0][0]["origins"][0]["localStorage"],
                         [{"name": login_relay.TOKEN_KEY, "value": "token-new"}])
        self.assertEqual(deps.states + deps.sessions, [])
        self.assertEqual(events[-1]["kind"], "success")
        for secret in ("user-x", "secret-y", "token-new"):
            self.assertNotIn(secret, output)

    def test_captcha_refusal_with_image_never_submits_credentials(self):
        for code in (0, -1, 2, "0"):
            with self.subTest(code=code):
                deps = HttpDeps()
                deps.responses[login_relay.AUTH_CAPTCHA_PATH]["code"] = code
                result, events, fallback, _ = run_http_scripted(deps)
                self.assertNotEqual(result, 0)
                self.assertEqual(len(deps.posts), 1)
                fallback.assert_not_called()
                self.assertNotIn("challenge", [e["kind"] for e in events])

    def test_unknown_network_or_malformed_captcha_never_falls_back(self):
        for response in ([], {"code": -1}, TimeoutError("secret-y")):
            with self.subTest(response=type(response).__name__):
                deps = HttpDeps()
                deps.responses[login_relay.AUTH_CAPTCHA_PATH] = response
                result, _, fallback, output = run_http_scripted(deps)
                self.assertNotEqual(result, 0)
                fallback.assert_not_called()
                self.assertEqual(len(deps.posts), 1)
                self.assertNotIn("secret-y", output)

    def test_success_contract_change_falls_back_once(self):
        deps = HttpDeps()
        deps.responses[login_relay.AUTH_CAPTCHA_PATH] = {"code": 1, "data": {}}
        result, _, fallback, _ = run_http_scripted(deps)
        self.assertEqual(result, 73)
        fallback.assert_called_once()
        self.assertEqual(len(deps.posts), 1)
        self.assertEqual(deps.saved, [])

    def test_password_unknown_and_network_refusals_do_not_retry(self):
        for response in ({"code": 0, "message": "password error"}, {"code": 9},
                         {"code": -1}, [], TimeoutError("secret-y token-new"),
                         {"code": 1, "data": {}}):
            with self.subTest(response=type(response).__name__):
                deps = HttpDeps()
                deps.responses[login_relay.AUTH_LOGIN_PATH] = response
                result, events, fallback, output = run_http_scripted(deps)
                self.assertNotEqual(result, 0)
                self.assertEqual([p[0] for p in deps.posts],
                                 [login_relay.AUTH_CAPTCHA_PATH, login_relay.AUTH_LOGIN_PATH])
                self.assertEqual(deps.saved, [])
                fallback.assert_not_called()
                self.assertNotIn("success", [e["kind"] for e in events])
                self.assertNotIn("secret-y", output)
                # 这些都不在官网实测的「账号或密码错误！」清单里：不得误报成密码错，
                # 否则会替用户把自动登录停掉
                self.assertEqual({e.get("error") for e in events if e["kind"] == "failed"},
                                 {"bad_response"}, "原因不明的拒绝不得报成密码错")

    def test_verified_captcha_message_refreshes_with_new_uuid(self):
        deps = HttpDeps()
        deps.refresh_gap_s = 0.0
        deps.responses[login_relay.AUTH_LOGIN_PATH] = {
            "code": 0, "message": "登录失败，验证码不正确！",
        }
        book = login_relay.ChallengeBook("flow-1", refresh_gap_s=0.0)
        self.assertTrue(book.open_challenge("old-challenge", 100.0))
        output = io.StringIO()
        result = login_relay._http_login(
            deps, output, book, "flow-1", "user-x", "secret-y",
            {"uuid": "old-uuid"}, "Ab12", 1000.0,
        )
        self.assertIsNone(result)
        self.assertEqual([path for path, _payload, _tok in deps.posts], [
            login_relay.AUTH_LOGIN_PATH, login_relay.AUTH_CAPTCHA_PATH,
        ])
        self.assertEqual(book.challenge_id, "chg-1")

    def test_verified_password_message_stops_without_refresh(self):
        deps = HttpDeps()
        deps.responses[login_relay.AUTH_LOGIN_PATH] = {
            "code": 0, "message": "账号或密码错误！",
        }
        book = login_relay.ChallengeBook("flow-1", refresh_gap_s=0.0)
        self.assertTrue(book.open_challenge("challenge", 100.0))
        output = io.StringIO()
        result = login_relay._http_login(
            deps, output, book, "flow-1", "user-x", "secret-y",
            {"uuid": "uuid"}, "Ab12", 1000.0,
        )
        self.assertEqual(result, 2)
        self.assertEqual([path for path, _payload, _tok in deps.posts], [
            login_relay.AUTH_LOGIN_PATH,
        ])
        # 官网实测文案要单独报 bad_password：界面据此暂停自动登录，
        # 不能和「原因不明的拒绝」共用 bad_response
        self.assertIn('"error": "bad_password"', output.getvalue())
        self.assertNotIn('"bad_response"', output.getvalue())

    def test_verify_and_save_errors_never_emit_success(self):
        for failure in ("verify", "save"):
            with self.subTest(failure=failure):
                deps = HttpDeps()
                deps.fail_save = failure == "save"
                if failure == "verify":
                    deps.responses["/rjyHd/listActivity"] = {"code": 4001}
                result, events, _, output = run_http_scripted(deps)
                self.assertNotEqual(result, 0)
                self.assertNotIn("success", [e["kind"] for e in events])
                self.assertEqual([p[0] for p in deps.posts], [
                    login_relay.AUTH_CAPTCHA_PATH, login_relay.AUTH_LOGIN_PATH,
                    "/rjyHd/listActivity"])
                self.assertEqual(events[-1]["error"],
                                 "token_unverified" if failure == "verify" else "internal")
                self.assertEqual(deps.saved + deps.states + deps.sessions, [])
                self.assertNotIn("secret-y", output)

    def test_cancel_wrong_and_expired_challenge_never_send_password(self):
        for mode in ("cancel", "wrong", "expired"):
            with self.subTest(mode=mode):
                deps = HttpDeps()
                result, _, fallback, _ = run_http_scripted(deps, mode)
                self.assertNotEqual(result, 0)
                self.assertEqual(len(deps.posts), 1)
                self.assertEqual(deps.saved, [])
                fallback.assert_not_called()


class VerifiedFilesTests(unittest.TestCase):
    def test_second_replace_failure_restores_all_original_combinations(self):
        for state_exists in (False, True):
            for session_exists in (False, True):
                with self.subTest(state=state_exists, session=session_exists):
                    with tempfile.TemporaryDirectory(dir=TMP_ROOT) as directory:
                        root = Path(directory)
                        state, session = root / "state.json", root / "session.json"
                        originals = {state: b"original state\r\n", session: b"original session"}
                        for path, exists in ((state, state_exists), (session, session_exists)):
                            if exists:
                                path.write_bytes(originals[path])
                        replace = os.replace
                        calls = []

                        def fail_second(src, dst):
                            calls.append(dst)
                            if len(calls) == 2:
                                raise OSError("second replace failed")
                            return replace(src, dst)

                        with mock.patch("grab.os.replace", side_effect=fail_second):
                            with self.assertRaises(OSError):
                                save_verified_files({"new": 1}, {"new": 2}, state, session)
                        for path, exists in ((state, state_exists), (session, session_exists)):
                            self.assertEqual(path.exists(), exists)
                            if exists:
                                self.assertEqual(path.read_bytes(), originals[path])
                        self.assertEqual(list(root.glob("*.tmp")), [])

    def test_success_replaces_both_documents(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as directory:
            root = Path(directory)
            state, session = root / "state.json", root / "session.json"
            save_verified_files({"new": 1}, {"new": 2}, state, session)
            self.assertEqual(json.loads(state.read_text(encoding="utf-8")), {"new": 1})
            self.assertEqual(json.loads(session.read_text(encoding="utf-8")), {"new": 2})
            self.assertEqual(list(root.glob("*.tmp")), [])
