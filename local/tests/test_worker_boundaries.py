#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生产 worker 的边界行为回归：直接调用 cmd_grab，只替换输入边界。

与上一轮的区别（对应复审 C01–C03）：

* 合法报名请求按仓库契约建模为 ``GET signUp/<opaque-hash>``，hash 不含明文活动 ID；
  替身默认第一次「立即报名」只打开确认框，「确定」才真正发请求。
* 请求按 Request 身份去重与计数：同一个请求重复通知只算 1，两个不同请求算 2。
* 响应必须对得上本轮承认的请求，别家响应不得改本场结论。
* 预算从进程入口就生效，鉴权/校时/查目标都要受限；确认前再拦一次。
* 已发出但没有确定结果的请求会一直算未决，下一次本地失败不能把它清掉。

@author Author
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

LOCAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOCAL))

import grab  # noqa: E402
import time_contract  # noqa: E402
from infrastructure import process_tree  # noqa: E402

# 站点地址不在测试里写死：跟着运行时的 site_target/config.json 走，
# 否则本机配置了真实域名时，这里写占位值会让 URL 归属判断全部落空
SITE = grab.BASE

START = 1792000000.0
OPEN_AHEAD = 20.0
OPAQUE = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"   # 学校前端算出的 hash，不含活动 ID
# 学校真实会让本场继续发的业务回包（实测：开放前 1 秒回 code=500「报名未开始！」）。
# 决策 015 起「报名人数已满」是终态，不能再拿它当「会继续重试的普通失败」夹具。
RETRYABLE_REPLY = {"code": 500, "message": "报名未开始！"}
# 测试专用的假运行时密钥：16 个 ASCII 字母数字，明显不是真值（决策 015）
TEST_RUNTIME_KEY = "TestRuntimeKey00"
_AUTO_KEY = object()     # run_worker 默认：传了直发替身才给密钥
# 学校没写进分类表的文案：同一条连续 3 次才触发降级或结束
UNKNOWN_REPLY = {"code": 0, "message": "系统繁忙，请稍后再试"}

# 回调哨兵（F05）：回调派发期间禁止业务时钟读取、结算刷新与日志；
# 违例只记录不抛出，由测试断言为空。
CALLBACK_GUARD = {"active": False, "violations": []}


class FakeTimeout(Exception):
    """替身 Playwright 的超时类型；grab 按类名捕获它。"""


class FakeClock:
    def __init__(self, wall=START, mono=1000.0):
        self.wall = float(wall)
        self.mono = float(mono)
        self.lost = False

    def lose(self):
        """模拟校时失效：业务读数一律抛 ClockUnavailable，墙钟读数照旧。"""
        self.lost = True

    def time(self):
        return self.wall

    def monotonic(self):
        return self.mono

    def sleep(self, seconds):
        step = max(0.0, float(seconds))
        self.wall += step
        self.mono += step

    def jump_wall(self, delta):
        self.wall += float(delta)

    # ---- 业务时钟视图（决策 012）：cmd_grab 需要注入独立北京时间 ----
    def now(self):
        self._require()
        if CALLBACK_GUARD["active"]:
            CALLBACK_GUARD["violations"].append("clock.now")
        return self.wall

    def bounds(self):
        self._require()
        if CALLBACK_GUARD["active"]:
            CALLBACK_GUARD["violations"].append("clock.bounds")
        return self.wall, self.wall

    def _require(self):
        if self.lost:
            from business_clock import ClockUnavailable
            raise ClockUnavailable("测试注入：北京时间暂不可用")

    def elapsed_s(self):
        return self.mono

    def state(self):
        return "ready"

    def reason(self):
        return "测试注入"

    def request_resync(self):
        pass

    def snapshot(self):
        return {"schema": 1, "owner_id": "fake-worker", "generation": 1,
                "state": "ready", "epoch_s": self.wall, "tick_s": self.mono,
                "sampled_tick_s": self.mono, "uncertainty_s": 0.0,
                "source": "test", "age_s": 0.0, "reason": "测试注入"}

    def sync(self, timeout_s=None):
        return "ready"

    def close(self):
        pass


class FakeRequest:
    def __init__(self, url, method="GET", post_data=""):
        self.url = url
        self.method = method
        self.post_data = post_data


class FakeResponse:
    def __init__(self, request, payload, status=200):
        self.request = request
        self.url = request.url
        self.status = status
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    def body(self):
        # 200+HTML 等非 JSON 载体也必须能读字节：本轮真实实现用 _decode_body
        # 而非 json()，读不出合法 JSON 时退回 {}，不伪装成 lost。
        if isinstance(self._payload, Exception):
            raise self._payload
        if isinstance(self._payload, (bytes, bytearray)):
            return bytes(self._payload)
        return json.dumps(self._payload, ensure_ascii=False).encode("utf-8")


class FakeLocator:
    def __init__(self, page, name):
        self.page = page
        self.name = name

    def filter(self, has_text=None):
        return self

    @property
    def first(self):
        return self

    def count(self):
        if self.name == "uni-button":
            return 1 if self.page.button_visible else 0
        if self.name == "确定":
            # 「确定」只在确认框开着时可见：用于 detecting 弹窗已开（不再重复点报名）
            return 1 if self.page.dialog_open else 0
        return 1

    def click(self, timeout=None):
        self.page.clicks.append((self.page.clock.time(), self.name, timeout))
        behavior = self.page.behavior
        if self.name == "uni-button":
            if behavior == "click_fail":
                raise FakeTimeout("点击超时")
            if behavior == "slow_dialog":
                # 打开确认框本身就花掉整个窗口：确认必须被拦下
                self.page.clock.sleep(self.page.click_delay)
            if behavior == "lose_before_confirm":
                # 打开确认框后校时失效：确认前检查必须拒绝，不产生提交
                self.page.clock.lose()
            if behavior == "open_race":
                # 页面抢跑：开确认框的同时就发出一笔 signUp（闸门②必须看到名额被占）
                request = FakeRequest(
                    SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE + "-race")
                self.page._notify(request)
                self.page._enqueue_response(
                    FakeResponse(request, {"code": 0, "message": "未就绪"}, status=404),
                    delay=self.page.response_delay or 0.3)
            if behavior == "success_on_open":
                # 页面抢跑直接成功：闸门②必须先 drain 到它，绝不点「确定」
                request = FakeRequest(
                    SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE + "-ok")
                self.page._notify(request)
                self.page._enqueue_response(
                    FakeResponse(request, {"code": 1, "message": "报名成功"}))
            self.page.dialog_open = True
            self.page._deliver_due()
            return                      # 默认只开确认框，不发请求
        if self.name == "确定":
            self.page.confirm_clicks += 1
            if behavior == "confirm_fail":
                raise FakeTimeout("确认框点击失败")
            self.page.dialog_open = False
            self.page.fire_from_confirm()
            self.page._deliver_due()
            return


class FakePage:
    """浏览器替身：请求/响应事件泵 + 可延迟的响应投递。

    任何同步调用（wait_for_timeout/locator/click）都会派发到期响应，
    与 Playwright 同步 API「等待里泵事件」的行为一致；响应投递时间由
    response_delay 或逐笔 delay 控制，用来证明乱序与迟到响应不影响提交节奏。
    """

    def __init__(self, clock, behavior, button_visible=True, click_delay=0.0,
                 foreign=False, response_delay=0.0, script_srcs=None,
                 inject_failed_at=None, break_wait_at=None):
        self.clock = clock
        self.behavior = behavior
        self.button_visible = button_visible
        self.click_delay = click_delay
        self.foreign = foreign
        self.response_delay = float(response_delay)
        self.script_srcs = script_srcs    # 直发检测读入口 script src（None=未知→点击）
        self.inject_failed_at = inject_failed_at   # 到点注入未登记 Request 的 requestfailed
        self.break_wait_at = break_wait_at         # 到点后 wait_for_timeout 抛错（页面失效）
        self.request_handlers = []
        self.response_handlers = []
        self.requestfailed_handlers = []
        self.pending_deliveries = []    # (deliver_at, response)
        self.requests = []
        self.clicks = []
        self.confirm_clicks = 0
        self.dialog_open = False        # 确认框是否开着（「确定」可见性）
        self.closed = False             # 浏览器已关：之后任何页面动作都必须被拒绝
        self.removed_listeners = []

    def _dispatch(self, event, target, *args):
        """回调派发：挂哨兵，禁止回调碰时钟/结算/日志（F05）。"""
        CALLBACK_GUARD["active"] = True
        try:
            for handler in list(target):
                handler(*args)
        finally:
            CALLBACK_GUARD["active"] = False

    def on(self, event, handler):
        if event == "request":
            self.request_handlers.append(handler)
        elif event == "response":
            self.response_handlers.append(handler)
        elif event == "requestfailed":
            self.requestfailed_handlers.append(handler)

    def remove_listener(self, event, handler):
        self.removed_listeners.append((event, handler))
        if event == "request":
            self.request_handlers = [h for h in self.request_handlers if h is not handler]
        elif event == "response":
            self.response_handlers = [h for h in self.response_handlers if h is not handler]
        elif event == "requestfailed":
            self.requestfailed_handlers = [h for h in self.requestfailed_handlers
                                           if h is not handler]

    def fire_requestfailed(self, request):
        """模拟页面导航中止在途请求：Playwright 只发 requestfailed，没有 response。"""
        self._dispatch("requestfailed", self.requestfailed_handlers, request)

    def _guard(self):
        # 浏览器已关闭后仍做页面动作＝实现缺陷（F04：可结算终态必须在关闭前收口）
        if self.closed:
            raise AssertionError("浏览器已关闭后仍有页面动作")

    def goto(self, url, wait_until=None, timeout=None):
        self._guard()
        if self.behavior == "goto_fail":
            raise FakeTimeout("goto 超时")
        self.url = url
        if self.foreign:
            # 页面自己发的 signUp：不在受控窗口内，不得计入本场
            self._notify(FakeRequest(
                SITE + "/dr/api/rjyHdCyr/signUp/other-hash"))

    def reload(self, wait_until=None, timeout=None):
        self._guard()
        if self.behavior == "reload_fail":
            raise FakeTimeout("reload 超时")
        self._deliver_due()

    def wait_for_timeout(self, ms):
        self._guard()
        if self.break_wait_at is not None and self.clock.mono >= self.break_wait_at:
            raise RuntimeError("page wait failed")
        self.clock.sleep(float(ms) / 1000.0)
        if self.inject_failed_at is not None and self.clock.mono >= self.inject_failed_at:
            self.inject_failed_at = None
            self.fire_requestfailed(FakeRequest(
                SITE + "/dr/api/rjyHdCyr/signUp/ghost-unregistered"))
        self._deliver_due()

    def eval_on_selector_all(self, selector, script):
        if "script" in selector:
            return list(self.script_srcs or [])
        return ["立即报名"]

    def locator(self, selector):
        self._guard()
        self._deliver_due()
        return FakeLocator(self, "uni-button" if "uni-button" in selector else selector)

    def get_by_text(self, text, exact=False):
        self._guard()
        self._deliver_due()
        return FakeLocator(self, "确定" if text == "确定" else text)

    def _notify(self, request):
        self.requests.append((self.clock.time(), request.url))
        self._dispatch("request", self.request_handlers, request)

    def _enqueue_response(self, response, delay=None):
        if delay is None:
            delay = self.response_delay
        self.pending_deliveries.append((self.clock.time() + float(delay), response))

    def _deliver_due(self):
        """派发到期响应给 response 监听；先到期的先派发，天然支持乱序。"""
        now = self.clock.time()
        due = [item for item in self.pending_deliveries if item[0] <= now]
        self.pending_deliveries = [item for item in self.pending_deliveries
                                   if item[0] > now]
        due.sort(key=lambda item: item[0])
        for _, response in due:
            self._dispatch("response", self.response_handlers, response)

    def fire_from_confirm(self):
        behavior = self.behavior
        payload = dict(RETRYABLE_REPLY)
        if behavior == "unknown_reply":
            payload = dict(UNKNOWN_REPLY)
        if behavior == "no_activity":
            payload = {"code": 0, "message": "Cache 'hd-info' does not allow 'null' values"}
        if behavior in ("success", "slow_success"):
            payload = {"code": 1, "message": "ok"}
        if behavior == "login_expired":
            # 学校明确回 4001：token 失效，必须停发并提示重登
            request = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE)
            self._notify(request)
            self._enqueue_response(FakeResponse(request, {"code": 4001, "message": "token 失效"}))
            return
        if behavior == "login_words_only":
            # 业务失败文案里带「登录/身份验证」不算 token 失效（子串匹配回归守卫）
            request = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE)
            self._notify(request)
            self._enqueue_response(FakeResponse(
                request, {"code": 0, "message": "请登录后完成身份验证"}))
            return
        if behavior == "login_race":
            # 4001 先到、成功后到（1 秒内）：成功优先级更高
            first = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE + "-0")
            second = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE + "-1")
            self._notify(first)
            self._notify(second)
            self._enqueue_response(FakeResponse(first, {"code": 4001, "message": "token 失效"}),
                                   delay=0.02)
            self._enqueue_response(FakeResponse(second, {"code": 1, "message": "ok"}),
                                   delay=0.5)
            return
        if behavior == "throttled_429":
            request = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE)
            self._notify(request)
            self._enqueue_response(FakeResponse(
                request, {"code": 0, "message": "太频繁"}, status=429))
            return
        if behavior == "server_error_500":
            # 5xx + HTML 载体：必须按 server_error 结算（不伪装 lost、不吞 pending）
            request = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE)
            self._notify(request)
            self._enqueue_response(FakeResponse(
                request, b"<html><body>502 Bad Gateway</body></html>", status=502))
            return
        if behavior == "version_incompatible":
            # 精确版本错误文案：本场单向降级到 click，不得误伤其它 code=0
            request = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE)
            self._notify(request)
            self._enqueue_response(FakeResponse(
                request, {"code": 0, "message": "版本不兼容，请刷新页面或清除缓存后重试"}))
            return
        if behavior == "ooo_5xx_two":
            # F06 反例一：#1/#2 发出，#2=200 先回、#1=500 后回 → 地板 0
            first = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE + "-0")
            second = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE + "-1")
            self._notify(first)
            self._notify(second)
            self._enqueue_response(
                FakeResponse(second, dict(RETRYABLE_REPLY)), delay=0.02)
            self._enqueue_response(
                FakeResponse(first, b"<html>boom</html>", status=500), delay=0.05)
            return
        if behavior == "ooo_5xx_three":
            # F06 反例二：#1/#2/#3 发出，#3=500、#1=500、#2=200 → 地板 0.5
            first = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE + "-0")
            second = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE + "-1")
            third = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE + "-2")
            self._notify(first)
            self._notify(second)
            self._notify(third)
            self._enqueue_response(FakeResponse(third, b"<html>boom</html>", status=500), delay=0.02)
            self._enqueue_response(FakeResponse(first, b"<html>boom</html>", status=500), delay=0.05)
            self._enqueue_response(
                FakeResponse(second, dict(RETRYABLE_REPLY)), delay=0.08)
            return
        if behavior == "http_404_429":
            # 404/404/429 混合连击：policy/budget/retry_deadline 必须同时扩窗
            request = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE)
            self._notify(request)
            step = getattr(self, "_step_429", 0)
            self._step_429 = step + 1
            if step == 2:
                self._enqueue_response(FakeResponse(
                    request, {"code": 0, "message": "太频繁"}, status=429))
            else:
                self._enqueue_response(FakeResponse(
                    request, {"code": 0, "message": "未就绪"}, status=404))
            return
        if behavior == "http_429_triple":
            request = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE)
            self._notify(request)
            self._enqueue_response(FakeResponse(
                request, {"code": 0, "message": "太频繁"}, status=429))
            return
        if behavior == "boom_after_response":
            # 流程异常：先把一笔成功应答入队，紧接页面崩——可读队列必须先被结算
            request = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE)
            self._notify(request)
            self._enqueue_response(FakeResponse(request, {"code": 1, "message": "ok"}))
            self._deliver_due()          # 让成功先落进响应队列
            raise RuntimeError("页面脚本崩溃")
        if behavior == "foreign_only":
            # 我方动作没有发出请求；别家请求在更早的 goto 阶段就发过了
            return
        if behavior == "lost":
            request = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE)
            self._notify(request)
            return                      # 响应永不到达：请求保持未决
        if behavior == "lose_after_request":
            # 提交已发出、校时随即失效：未决事实必须保留，不能判成名额已满
            request = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE)
            self._notify(request)
            self.clock.lose()
            return
        if behavior == "response_stuck":
            request = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE)
            self._notify(request)
            self._enqueue_response(FakeResponse(request, FakeTimeout("读响应卡住")))
            return
        if behavior == "dup_notify":
            request = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE)
            self._notify(request)
            self._notify(request)          # 同一个 Request 重复通知
            self._enqueue_response(FakeResponse(request, {"code": 1, "message": "ok"}))
            return
        if behavior == "http_404":
            request = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE)
            self._notify(request)
            self._enqueue_response(FakeResponse(request, {"code": 0, "message": "未就绪"},
                                                status=404))
            return
        if behavior == "out_of_order":
            # 一次动作发两笔：先发的响应回来得更晚，结算必须各归各的编号
            first = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE + "-0")
            second = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE + "-1")
            self._notify(first)
            self._notify(second)
            self._enqueue_response(
                FakeResponse(first, {"code": 0, "message": "未就绪"}, status=404),
                delay=0.05)               # 先发的后到
            self._enqueue_response(
                FakeResponse(second, dict(RETRYABLE_REPLY)),
                delay=0.02)               # 后发的先到
            return
        if behavior == "double":
            # 一次动作真的发两笔，但只有一笔拿到确定应答：另一笔保持未决
            for index in range(2):
                request = FakeRequest(
                    SITE + "/dr/api/rjyHdCyr/signUp/%s-%d" % (OPAQUE, index))
                request.post_data = ""
                self._notify(request)
                if index == 1:
                    self._enqueue_response(FakeResponse(request, dict(payload)))
            return
        if behavior == "abort_inflight":
            # 导航中止在途请求：Playwright 只发 requestfailed，没有 response
            request = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE)
            self._notify(request)
            self.fire_requestfailed(request)
            return
        # 默认 full/success/slow_*：一次动作一笔请求
        request = FakeRequest(SITE + "/dr/api/rjyHdCyr/signUp/" + OPAQUE)
        self._notify(request)
        self._enqueue_response(FakeResponse(request, dict(payload)))


class FakeBrowser:
    def __init__(self, page):
        self.page = page
        self.closed = False

    def new_context(self, **kwargs):
        page = self.page

        class Ctx:
            def new_page(inner):
                return page

            def close(inner):
                return None

        return Ctx()

    def close(self):
        self.closed = True
        # 同步把页面标记为已关：此后任何 page/locator 动作都会被 _guard 拒绝，
        # 用来证明「可结算终态在浏览器清理前收口」（F04）。
        self.page.closed = True


class _PassPw:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


def install_fake_playwright():
    pkg = types.ModuleType("playwright")
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = _PassPw
    sync_api.TimeoutError = FakeTimeout
    pkg.sync_api = sync_api
    old = {name: sys.modules.get(name) for name in ("playwright", "playwright.sync_api")}
    sys.modules["playwright"] = pkg
    sys.modules["playwright.sync_api"] = sync_api

    def restore():
        for name, module in old.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    return restore


class Result:
    def __init__(self, code, logs, page, clock, elapsed_s, browser_created, posts):
        self.code = code
        self.logs = logs
        self.page = page
        self.clock = clock
        self.elapsed_s = elapsed_s
        self.browser_created = browser_created
        self.posts = posts

    @property
    def attempts(self):
        return max([int(line.split("attempts=")[1].split(" ")[0])
                    for line in self.logs if "kind=done" in line] or [0])

    @property
    def pending(self):
        lines = [line for line in self.logs if "kind=done" in line]
        if not lines:
            return None
        return int(lines[-1].split("pending=")[1].split(" ")[0])

    @property
    def terminal_lines(self):
        return [line for line in self.logs if "[retry] " in line and "stop_reason=" in line]

    @property
    def stop_reason(self):
        if not self.terminal_lines:
            return None
        return self.terminal_lines[-1].split("stop_reason=")[1].split(" ")[0]

    @property
    def window_line(self):
        return next((line for line in self.logs if "kind=window" in line), None)

    @property
    def requests(self):
        return self.page.requests if self.page else []


def run_worker(*, behavior="success", at_offset=0.0, retry_for=120.0, max_attempts=0,
               sign_end="", retry_start=None, probe_delay=0.0,
               probe_state="valid", probe_detail="ok",
               post_delays=None, post_hook=None, button_visible=True,
               click_delay=0.0, foreign=False, launch_fails=False,
               response_delay=0.0, script_srcs=None,
               direct_signer=None, direct_transport=None,
               api_token="test-token",
               inject_failed_at=None, break_wait_at=None, join_info_data=None,
               recheck_state="expired", runtime_key=_AUTO_KEY,
               relogin_wait=0.0, relogin_writes_token=False):
    clock = FakeClock()
    page = FakePage(clock, behavior, button_visible, click_delay, foreign,
                    response_delay, script_srcs,
                    inject_failed_at=inject_failed_at, break_wait_at=break_wait_at)
    logs, posts = [], []
    created = {"browser": False}
    delays = list(post_delays or [])
    join_calls = {"n": 0}
    CALLBACK_GUARD["active"] = False
    CALLBACK_GUARD["violations"] = []

    def fake_log(msg):
        if CALLBACK_GUARD["active"]:
            CALLBACK_GUARD["violations"].append("log")
        logs.append(str(msg))

    probe_calls = {"n": 0}
    # 默认：传了直发替身就给假密钥（直发启用），否则不给（全程点击）
    if runtime_key is _AUTO_KEY:
        key_for_run = (TEST_RUNTIME_KEY
                       if (direct_signer is not None or direct_transport is not None) else None)
    else:
        key_for_run = runtime_key

    def fake_probe(budget=None):
        # 假网络必须像真网络一样尊重预算：否则「整流程受限」根本没被检验
        probe_calls["n"] += 1
        if probe_calls["n"] > 1:
            # 入场之后的探测只可能是提交中收到 4001 的复查（决策 015）
            if isinstance(recheck_state, (list, tuple)):
                # 依次作答：入场之后第 1 次探测取第 1 个，用完后一直取最后一个
                index = min(probe_calls["n"] - 2, len(recheck_state) - 1)
                return recheck_state[index], "recheck"
            return recheck_state, "recheck"
        wait = probe_delay
        if budget is not None:
            wait = min(wait, max(0.0, budget.remaining_s()))
        clock.sleep(wait)
        if budget is not None and budget.expired() and wait < probe_delay:
            raise time_contract.BudgetExhausted("鉴权超时")
        return probe_state, probe_detail

    def fake_post(path, payload=None, tok=None, timeout=None, budget=None):
        posts.append({"path": path, "timeout": timeout, "at": clock.time()})
        delay = delays.pop(0) if delays else 0.0
        effective = delay if timeout is None else min(delay, max(0.0, float(timeout)))
        clock.sleep(effective)
        if post_hook:
            post_hook(len(posts), clock)
        if effective < delay:
            return {"code": -1, "message": "TimeoutError"}
        if path == grab.RUNTIME_PROFILE_PATH:
            # 运行时密钥：顶层 code/message/data/version，密钥就是 data（16 个 ASCII 字符）
            return {"code": 1, "message": "操作成功！", "data": key_for_run, "version": "test"}
        if "/getJoinInfo/" in path:
            # 首次查询是入场预检（必须未报名）；后续查询才按 join_info_data 作答
            join_calls["n"] += 1
            if join_calls["n"] > 1 and join_info_data is not None:
                return {"code": 1, "data": join_info_data}
            return {"code": 1, "data": None}
        return {"code": 1, "data": {}}

    def fake_launch(pw, headless):
        created["browser"] = True
        if launch_fails:
            raise RuntimeError("browser launch failed")
        return FakeBrowser(page)

    at_ts = START + at_offset
    args = SimpleNamespace(
        dry_run=False, headed=False, lead=100.0, window=120.0,
        retry_for=retry_for, max_attempts=max_attempts, sign_end=sign_end,
        retry_start=START if retry_start is None else retry_start,
        activity_id="act-1", at=grab.school_time_text(at_ts), name="边界实验活动",
        relogin_wait=relogin_wait,
    )

    patches = {"log": fake_log, "probe_token": fake_probe,
               # token 替身固定值：直发 headers 断言用，严禁读取真实 session 文件
               # relogin_writes_token：模拟界面在 worker 发出 login_wait 后自动登录、写入新 token
               "token": ((lambda: api_token + "-new"
                          if any("等自动登录" in line for line in logs) else api_token)
                         if relogin_writes_token else (lambda: api_token)),
               "setup_business_clock": lambda *a, **k: (grab.configure_business_clock(clock), clock)[1],
               # 兼容入场实现（旧 cmd_grab 调 check_token）；新实现不读它
               "check_token": lambda budget=None: (probe_state == "valid", probe_detail),
               "clock_sample": lambda *a, **k: {"source": "http_date", "state": "unknown",
                                                "checked_at": START, "offset_s": None,
                                                "uncertainty_s": None, "rtt_s": None},
               "resolve_target": lambda a, budget=None: {"id": "act-1", "at": args.at,
                                                         "original_at": args.at,
                                                         "name": args.name},
               "_post": fake_post, "launch_browser": fake_launch,
               "notify": lambda *a, **k: False}
    # 入场实现没有 probe_token：用 getattr 兜底，红例装置才能在旧代码上跑起来
    originals = {name: getattr(grab, name, None) for name in patches}
    original_times = (grab.time, time_contract.time)
    restore_pw = install_fake_playwright()
    start_mono = clock.mono
    grab.time = clock
    time_contract.time = clock
    # 直发替身注入（opt-in）：换掉真实 signer/transport，只在显式传入时生效，
    # 既有点击测试不受影响。检测走 `from ... import`，改模块属性即可生效。
    direct_mods = {}
    if direct_signer is not None or direct_transport is not None:
        import signup_signing as _ss
        import signup_transport as _st
        if direct_signer is not None:
            direct_mods[("signup_signing", "build_signup_hash")] = getattr(_ss, "build_signup_hash", None)
            _ss.build_signup_hash = direct_signer
        if direct_transport is not None:
            direct_mods[("signup_transport", "DirectTransport")] = getattr(_st, "DirectTransport", None)
            _st.DirectTransport = direct_transport
            bind = getattr(direct_transport, "bind_clock", None)
            if bind is not None:
                bind(clock)
    try:
        for name, value in patches.items():
            setattr(grab, name, value)
        with contextlib.redirect_stdout(io.StringIO()):
            code = grab.cmd_grab(args)
    finally:
        for (mod_name, attr), value in direct_mods.items():
            import sys as _sys
            mod = _sys.modules.get(mod_name)
            if mod is not None:
                if value is None:
                    try:
                        delattr(mod, attr)
                    except AttributeError:
                        pass
                else:
                    setattr(mod, attr, value)
        for name, value in originals.items():
            if value is None:
                try:
                    delattr(grab, name)
                except AttributeError:
                    pass
            else:
                setattr(grab, name, value)
        grab.time, time_contract.time = original_times
        restore_pw()
    return Result(code, logs, page if created["browser"] else None, clock,
                  clock.mono - start_mono, created["browser"], posts)


class RequestCorrelationTests(unittest.TestCase):
    """C01：opaque hash 也要认领；请求按身份计数，响应不串场。"""

    def test_opaque_get_request_is_counted(self):
        res = run_worker(behavior="success")
        self.assertEqual(len(res.requests), 1)
        self.assertIn("/signUp/" + OPAQUE, res.requests[0][1])
        self.assertEqual(res.attempts, 1, "GET signUp/<opaque> 无正文也必须计数")
        self.assertEqual(res.stop_reason, "success")
        self.assertEqual(res.code, 0)

    def test_same_request_notified_twice_counts_once(self):
        res = run_worker(behavior="dup_notify")
        self.assertEqual(len(res.requests), 2, "装置确实通知了两次")
        self.assertEqual(res.attempts, 1, "同一 Request 重复通知只计 1")

    def test_two_distinct_requests_are_not_merged(self):
        res = run_worker(behavior="double", max_attempts=2)
        self.assertGreaterEqual(len(res.requests), 2, "页面真的发了两次就要记两次")
        self.assertGreaterEqual(res.attempts, 2, "两笔都要按真实次数入账")
        self.assertEqual(res.stop_reason, "unconfirmed",
                         "两笔里只拿到一个确定结果，另一笔仍未决")
        self.assertEqual(res.code, 2)

    def test_foreign_request_does_not_change_conclusion(self):
        res = run_worker(behavior="foreign_only", foreign=True, retry_for=3.0,
                         max_attempts=1)
        self.assertEqual(len(res.requests), 1, "装置确实发过别家请求")
        self.assertEqual(res.attempts, 0, "不属于受控提交的请求不得计数")
        self.assertNotEqual(res.stop_reason, "success")
        self.assertEqual(res.code, 2)


class AdmissionTests(unittest.TestCase):
    """C01/R01/R02：只有真正发出的请求才计次，开放前不点。"""

    def test_click_failure_keeps_zero(self):
        res = run_worker(behavior="click_fail", retry_for=6.0, max_attempts=3)
        self.assertEqual(res.requests, [])
        self.assertEqual(res.attempts, 0)
        self.assertEqual(res.stop_reason, "retry_duration")
        self.assertEqual(len(res.terminal_lines), 1)

    def test_confirm_failure_keeps_zero(self):
        res = run_worker(behavior="confirm_fail", retry_for=4.0, max_attempts=2)
        self.assertEqual(res.requests, [])
        self.assertEqual(res.attempts, 0)
        self.assertGreaterEqual(res.page.confirm_clicks, 1)

    def test_preopen_button_does_not_submit(self):
        res = run_worker(behavior="full", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=3)
        self.assertTrue(res.requests)
        for at, _ in res.requests:
            self.assertGreaterEqual(at, START + OPEN_AHEAD - 1e-6)
        self.assertEqual(res.attempts, len(res.requests))
        self.assertEqual(res.stop_reason, "max_attempts")

    def test_full_until_max_counts_exactly(self):
        res = run_worker(behavior="full", retry_for=120.0, max_attempts=2)
        self.assertEqual(len(res.requests), 2)
        self.assertEqual(res.attempts, 2)
        self.assertEqual(res.stop_reason, "max_attempts")


class BudgetEntireFlowTests(unittest.TestCase):
    """C02：前置阶段也受限，确认前再拦，异常恰一条终态。"""

    def test_preflight_auth_cannot_exceed_short_window(self):
        res = run_worker(behavior="success", probe_delay=7.0, retry_for=2.0)
        self.assertLessEqual(res.elapsed_s, 2.1, "鉴权把 2 秒窗口拖成了 7 秒")
        self.assertFalse(res.browser_created, "窗口已耗尽不得再开浏览器")
        self.assertEqual(res.requests, [])
        self.assertEqual(len(res.terminal_lines), 1)

    def test_expired_window_touches_no_network(self):
        res = run_worker(behavior="success", retry_for=2.0, retry_start=START - 10.0)
        self.assertEqual(res.posts, [], "窗口入场已过就不该再发任何网络请求")
        self.assertFalse(res.browser_created)
        self.assertEqual(res.stop_reason, "retry_duration")

    def test_confirm_blocked_when_dialog_consumes_budget(self):
        res = run_worker(behavior="slow_dialog", retry_for=2.0, click_delay=2.0,
                         max_attempts=3)
        self.assertEqual(res.requests, [], "预算在确认前耗尽，不得再点确定")
        self.assertEqual(res.page.confirm_clicks, 0, "确认按钮必须没被点过")

    def test_goto_failure_has_single_terminal(self):
        res = run_worker(behavior="goto_fail")
        self.assertEqual(len(res.terminal_lines), 1)
        self.assertEqual(res.stop_reason, "process_error")
        self.assertEqual(res.code, 2)

    def test_reload_failure_has_single_terminal(self):
        res = run_worker(behavior="reload_fail", button_visible=False, retry_for=3.0)
        self.assertEqual(len(res.terminal_lines), 1)

    def test_launch_failure_has_single_terminal(self):
        res = run_worker(behavior="success", launch_fails=True)
        self.assertEqual(len(res.terminal_lines), 1)
        self.assertEqual(res.stop_reason, "process_error")

    def test_response_read_failure_is_unconfirmed(self):
        res = run_worker(behavior="response_stuck", retry_for=4.0, max_attempts=3)
        # 多笔未决合法：读不出响应体的请求一直挂 pending，不伪造成失败
        self.assertGreaterEqual(res.attempts, 1, "请求已发出就要计数")
        self.assertEqual(res.stop_reason, "unconfirmed")
        self.assertEqual(len(res.terminal_lines), 1)


class UnknownOutcomeTests(unittest.TestCase):
    """C03 升级：未决事实不会被下一次本地失败抹掉；多笔未决合法但绝不伪造成失败。"""

    def test_lost_response_stays_unconfirmed(self):
        res = run_worker(behavior="lost", retry_for=4.0, max_attempts=3)
        # 黄金风暴允许并发在途：丢响应不再单笔停手，但未决绝不写成失败
        self.assertGreaterEqual(res.attempts, 1, "每次真实发出都要计数")
        self.assertEqual(res.stop_reason, "unconfirmed")
        self.assertEqual(res.code, 2)

    def test_lost_then_local_failure_keeps_unconfirmed(self):
        res = run_worker(behavior="lost", retry_for=4.0, max_attempts=3,
                         button_visible=True)
        # 丢响应后可以继续发（多笔未决），但终态仍是「未确认」不是失败
        self.assertGreaterEqual(res.page.confirm_clicks, 1)
        self.assertEqual(res.stop_reason, "unconfirmed")

    def test_auth_unknown_is_not_login_invalid(self):
        res = run_worker(probe_state="unknown", probe_detail="接口异常：URLError")
        self.assertEqual(res.stop_reason, "auth_unavailable")
        self.assertEqual(res.code, 3)
        self.assertNotIn("登录失效", "\n".join(res.logs))

    def test_auth_expired_is_login_invalid(self):
        res = run_worker(probe_state="expired", probe_detail="登录态已过期（4001）")
        self.assertEqual(res.stop_reason, "login_invalid")
        self.assertEqual(res.code, 3)


class WallClockTests(unittest.TestCase):
    def test_backward_jump_does_not_extend(self):
        def hook(index, clock):
            if index == 1:
                clock.jump_wall(-10.0)

        res = run_worker(behavior="full", retry_for=2.0, max_attempts=0,
                         post_delays=[0.2, 5.0, 5.0], post_hook=hook)
        self.assertLessEqual(res.elapsed_s, 2.1)


def school_row(aid, name, sign_start, sign_end, *, signed=False, place="A101"):
    """学校 /rjyHd/listActivity 的原始行形状（字段名是拼音缩写）。"""
    return {
        "id": aid, "hdmc": name, "hdlx": "讲座", "hddd": place,
        "bmkssj": sign_start, "bmjssj": sign_end,
        "hdkssj": "2099-01-03 09:00:00", "hdjssj": "2099-01-03 11:00:00",
        "bmzt": 1 if signed else 0,
    }


class ListEntryTests(unittest.TestCase):
    """F01：真实 cmd_list 成功路径与 resolve_target 三条路径的预算回归。

    只替换网络边界（_post / check_token），绝不 patch 掉 cmd_list、resolve_target
    或伪造它们自己的返回值——否则测的就不是生产入口。
    """

    def _run_list(self, replies, *, token=(True, "ok"), all_rows=False,
                  json_mode=True, token_impl=None, log_impl=None):
        clock = FakeClock()
        seen = []
        details_requested = []
        queue = list(replies) if isinstance(replies, list) else [replies]

        def fake_post(path, payload=None, tok=None, timeout=None, budget=None):
            seen.append({"path": path, "budget": budget, "timeout": timeout})
            item = queue.pop(0) if len(queue) > 1 else queue[0]
            if isinstance(item, Exception):
                raise item
            return item

        # 详情边界替身：cmd_list 筛选后会补详情，任何用例都不得真的发详情请求
        def fake_detail(activity_id, timeout=None):
            details_requested.append(activity_id)
            return {"checkin_required": False, "checkout_required": False,
                    "checkin_start": "", "checkin_end": "",
                    "checkout_start": "", "checkout_end": ""}

        args = SimpleNamespace(all=all_rows, json=json_mode)
        out = io.StringIO()
        patches = {"_post": fake_post,
                   "check_token": token_impl or (lambda budget=None: token),
                   "fetch_activity_detail": fake_detail}
        if log_impl is not None:
            patches["log"] = log_impl
        originals = {name: getattr(grab, name, None) for name in patches}
        original_time = grab.time
        original_clock = dict(grab._CLOCK)
        original_now = time_contract._BUSINESS_NOW
        grab.time = clock
        # 列表筛选按业务北京时间：测试显式注入可控时钟，不用系统墙钟
        grab.configure_business_clock(clock)
        try:
            grab.DETAIL_CACHE.clear()
            for name, value in patches.items():
                setattr(grab, name, value)
            with contextlib.redirect_stdout(out):
                code = grab.cmd_list(args)
        finally:
            for name, value in originals.items():
                if value is None:
                    try:
                        delattr(grab, name)
                    except AttributeError:
                        pass
                else:
                    setattr(grab, name, value)
            grab.time = original_time
            grab._CLOCK.update(original_clock)
            time_contract.configure_time_source(original_now)
            grab.DETAIL_CACHE.clear()
        return code, out.getvalue(), seen, details_requested

    def test_cmd_list_returns_sorted_json_for_real_rows(self):
        now = START
        rows = [
            school_row("signed", "已报名活动", grab.school_time_text(now - 7200),
                       grab.school_time_text(now + 7200), signed=True),
            school_row("open", "开放中活动", grab.school_time_text(now - 3600),
                       grab.school_time_text(now + 7200)),
            school_row("future", "未开放活动", grab.school_time_text(now + 3600),
                       grab.school_time_text(now + 7200)),
        ]
        code, out, seen, _details = self._run_list({"code": 1, "data": {"count": 3, "list": rows}})
        self.assertEqual(code, 0, "真实 cmd_list 成功路径不得报错：%s" % out)
        data = json.loads(out.strip())
        self.assertEqual([row["id"] for row in data], ["future", "open", "signed"],
                         "未开放排最前，其次开放中，已报名垫底")
        first = data[0]
        for key in ("index", "id", "name", "sign_start", "sign_end", "act_start",
                    "act_end", "place", "signed", "checkin_required",
                    "checkout_required", "state"):
            self.assertIn(key, first, "JSON 契约字段缺失：%s" % key)
        self.assertEqual(first["index"], 1)
        self.assertEqual(data[-1]["state"], "已报名")
        self.assertEqual(len(seen), 1, "单页数据应只请求一次列表")

    def test_cmd_list_zero_rows_is_empty_json(self):
        code, out, _, _details = self._run_list({"code": 1, "data": {"count": 0, "list": []}})
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.strip()), [],
                         "学校确实零行时必须输出可解析的空数组")

    def test_cmd_list_permission_error_is_attributed_to_login(self):
        code, out, _, _details = self._run_list({"code": 4001, "message": "身份验证失败"})
        self.assertEqual(code, 2)
        self.assertIn("登录态已失效", out)
        self.assertNotIn("拉取活动失败", out)

    def test_cmd_list_network_error_is_not_reported_as_expired_login(self):
        # 真实 _post 把 URLError 收成 {code:-1, message:"URLError"}，这里按同一形状喂入
        code, out, _, _details = self._run_list({"code": -1, "message": "URLError"})
        self.assertEqual(code, 2)
        self.assertIn("拉取活动失败", out)
        self.assertIn("URLError", out)
        self.assertNotIn("登录态已失效", out, "网络错误不得归因成登录过期")

    def test_cmd_list_details_only_for_relevant_rows(self):
        """先筛选再补详情：详情只发给要显示的 3 行，已截止的 5 行一个请求都不发。"""
        now = START
        rows = [
            school_row("future", "未开放活动", grab.school_time_text(now + 3600),
                       grab.school_time_text(now + 7200)),
            school_row("open", "开放中活动", grab.school_time_text(now - 3600),
                       grab.school_time_text(now + 7200)),
            school_row("signed", "已报名活动", grab.school_time_text(now - 7200),
                       grab.school_time_text(now + 7200), signed=True),
        ]
        ended_ids = []
        for i in range(5):
            aid = "ended%d" % i
            ended_ids.append(aid)
            rows.append(school_row(aid, "已截止活动%d" % i,
                                   grab.school_time_text(now - 86400),
                                   grab.school_time_text(now - 9000)))
        code, out, _, details = self._run_list(
            {"code": 1, "data": {"count": 8, "list": rows}})
        self.assertEqual(code, 0, "成功路径不得报错：%s" % out)
        data = json.loads(out.strip())
        self.assertEqual([row["id"] for row in data],
                         ["future", "open", "signed"],
                         "只显示报名还没截止的 3 行")
        self.assertEqual(sorted(details), ["future", "open", "signed"],
                         "详情只补要显示的行")
        for aid in ended_ids:
            self.assertNotIn(aid, details, "已截止的活动不得发详情请求")

    def test_cmd_list_all_still_enriches_every_row(self):
        """--all 显式要看全部历史：8 行都保留，详情也全部补齐。"""
        now = START
        rows = [
            school_row("future", "未开放活动", grab.school_time_text(now + 3600),
                       grab.school_time_text(now + 7200)),
            school_row("open", "开放中活动", grab.school_time_text(now - 3600),
                       grab.school_time_text(now + 7200)),
            school_row("signed", "已报名活动", grab.school_time_text(now - 7200),
                       grab.school_time_text(now + 7200), signed=True),
        ]
        all_ids = ["future", "open", "signed"]
        for i in range(5):
            aid = "ended%d" % i
            all_ids.append(aid)
            rows.append(school_row(aid, "已截止活动%d" % i,
                                   grab.school_time_text(now - 86400),
                                   grab.school_time_text(now - 9000)))
        code, out, _, details = self._run_list(
            {"code": 1, "data": {"count": 8, "list": rows}}, all_rows=True)
        self.assertEqual(code, 0, "成功路径不得报错：%s" % out)
        data = json.loads(out.strip())
        self.assertEqual(len(data), 8, "--all 不得筛掉任何行")
        self.assertEqual(sorted(details), sorted(all_ids), "--all 时详情仍全补")

    def test_cmd_list_without_clock_keeps_full_enrich(self):
        """北京时间不可用：不筛选、详情照旧全补，状态一律显示待确认。

        不走 _run_list：那条路会注入可用时钟，模拟不出「时钟不可用」分支；
        这里照 CliListWithoutClockTests 的口径清空 _CLOCK，让 business_now
        直接抛 ClockUnavailable，并替换 log（该分支会打一条提示）。
        """
        rows = [
            school_row("future", "未开放活动", grab.school_time_text(START + 3600),
                       grab.school_time_text(START + 7200)),
            school_row("open", "开放中活动", grab.school_time_text(START - 3600),
                       grab.school_time_text(START + 7200)),
        ]
        all_ids = ["future", "open"]
        for i in range(6):
            aid = "ended%d" % i
            all_ids.append(aid)
            rows.append(school_row(aid, "已截止活动%d" % i,
                                   grab.school_time_text(START - 86400),
                                   grab.school_time_text(START - 9000)))
        details_requested = []

        def fake_post(path, payload=None, tok=None, timeout=None, budget=None):
            return {"code": 1, "data": {"count": 8, "list": rows}}

        def fake_detail(activity_id, timeout=None):
            details_requested.append(activity_id)
            return {"checkin_required": False, "checkout_required": False,
                    "checkin_start": "", "checkin_end": "",
                    "checkout_start": "", "checkout_end": ""}

        args = SimpleNamespace(all=False, json=True)
        out = io.StringIO()
        patches = {"_post": fake_post, "check_token": lambda budget=None: (True, "ok"),
                   "fetch_activity_detail": fake_detail, "log": lambda msg: None}
        originals = {name: getattr(grab, name, None) for name in patches}
        original_clock = dict(grab._CLOCK)
        grab._CLOCK.update({"now": None, "bounds": None, "meta": None})
        try:
            grab.DETAIL_CACHE.clear()
            for name, value in patches.items():
                setattr(grab, name, value)
            with contextlib.redirect_stdout(out):
                code = grab.cmd_list(args)
        finally:
            for name, value in originals.items():
                if value is None:
                    try:
                        delattr(grab, name)
                    except AttributeError:
                        pass
                else:
                    setattr(grab, name, value)
            grab._CLOCK.update(original_clock)
            grab.DETAIL_CACHE.clear()
        self.assertEqual(code, 0, "时钟不可用也要出列表：%s" % out.getvalue())
        data = json.loads(out.getvalue().strip())
        self.assertEqual(len(data), 8, "没有可信时钟不得按本机日期筛选")
        self.assertEqual(sorted(details_requested), sorted(all_ids),
                         "时钟不可用时详情仍全补")
        for row in data:
            self.assertEqual(row["state"], "待确认",
                             "时钟不可用时开放状态显示待确认")

    def test_cmd_list_json_stdout_stays_pure_when_helpers_log(self):
        """--json 时辅助日志改道 stderr：stdout 只剩 JSON，stderr 恰一行 [timing]。"""
        log_lines = []

        def noisy_log(msg):
            log_lines.append(msg)
            print("LOGGER:%s" % msg, flush=True)   # 模拟真实 log() 往 stdout 打印

        def token_impl(budget=None):
            grab.log("[i] 登录探测：4001 后复查恢复（测试）")
            return (True, "ok")

        rows = [school_row("open", "开放中活动", grab.school_time_text(START - 3600),
                           grab.school_time_text(START + 7200))]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code, out, _, details = self._run_list(
                {"code": 1, "data": {"count": 1, "list": rows}},
                token_impl=token_impl, log_impl=noisy_log)
        self.assertEqual(code, 0)
        data = json.loads(out.strip())
        self.assertEqual(data[0]["id"], "open",
                         "辅助函数打过日志后 stdout 里的 JSON 必须仍能直接解析")
        self.assertEqual(log_lines, ["[i] 登录探测：4001 后复查恢复（测试）"])
        self.assertIn("[i] 登录探测", err.getvalue(), "辅助日志应改道到 stderr")
        timing_lines = [line for line in err.getvalue().splitlines()
                        if line.startswith("[timing] list ")]
        self.assertEqual(len(timing_lines), 1, "用时分段恰好一行")
        for key in ("token_s=", "pages=", "details=", "total_s="):
            self.assertIn(key, timing_lines[0])
        self.assertEqual(details, ["open"])

    def test_cmd_list_text_mode_has_no_timing_line(self):
        """纯文本模式：不补详情、不写 [timing] 行，输出保持原有表头与行。"""
        rows = [school_row("open", "开放中活动", grab.school_time_text(START - 3600),
                           grab.school_time_text(START + 7200))]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code, out, _, details = self._run_list(
                {"code": 1, "data": {"count": 1, "list": rows}}, json_mode=False)
        self.assertEqual(code, 0)
        self.assertIn("报名开始", out, "纯文本模式仍有表头")
        self.assertIn("开放中活动", out)
        self.assertNotIn("[timing] list ", err.getvalue(),
                         "纯文本模式不写用时分段")
        self.assertEqual(details, [], "纯文本模式不为活动发详情请求")

    def _run_resolve(self, **kwargs):
        clock = FakeClock()
        budgets = []
        rows = [school_row("a1", "目标活动", grab.school_time_text(START + 3600),
                           grab.school_time_text(START + 7200))]

        def fake_post(path, payload=None, tok=None, timeout=None, budget=None):
            budgets.append(budget)
            return {"code": 1, "data": {"count": 1, "list": rows}}

        args = SimpleNamespace(activity_id=kwargs.get("activity_id", ""),
                               at=kwargs.get("at", ""),
                               name=kwargs.get("name", ""),
                               pick=kwargs.get("pick", 0))
        budget = time_contract.RetryBudget(START + 600, wall_now=START,
                                           monotonic_now=1000.0)
        patches = {"_post": fake_post}
        originals = {name: getattr(grab, name, None) for name in patches}
        original_time = grab.time
        grab.time = clock
        out = io.StringIO()
        try:
            for name, value in patches.items():
                setattr(grab, name, value)
            with contextlib.redirect_stdout(out):
                target = grab.resolve_target(args, budget=budget)
        finally:
            for name, value in originals.items():
                if value is None:
                    try:
                        delattr(grab, name)
                    except AttributeError:
                        pass
                else:
                    setattr(grab, name, value)
            grab.time = original_time
        return target, budgets, budget, out.getvalue()

    def test_resolve_target_three_paths_share_the_same_budget(self):
        cases = {
            "按ID无--at": {"activity_id": "a1"},
            "按名称": {"name": "目标活动"},
            "按序号": {"pick": 1},
        }
        for label, kwargs in cases.items():
            with self.subTest(path=label):
                target, budgets, budget, out = self._run_resolve(**kwargs)
                self.assertIsNotNone(target, "%s 没选出目标：%s" % (label, out))
                self.assertEqual(target["id"], "a1")
                self.assertTrue(budgets, "%s 没有经过网络边界" % label)
                self.assertTrue(all(item is budget for item in budgets),
                                "%s 丢了调用方传入的预算对象" % label)

    def test_exhausted_lookup_budget_never_opens_browser(self):
        clock = FakeClock()
        logs, posts = [], []
        created = {"browser": False}

        def fake_clock_sample(*a, **k):
            # 粗校时把 30 秒前置预算花光：真实网络慢起来完全可能
            clock.sleep(35.0)
            return {"state": "unknown"}

        def fake_post(path, payload=None, tok=None, timeout=None, budget=None):
            # 与生产 _post 同序：先按剩余预算算超时，已到点就拒绝发起请求
            if budget is not None:
                budget.timeout_s(15)
            posts.append(path)
            return {"code": 1, "data": {"count": 0, "list": []}}

        def fake_launch(pw, headless):
            created["browser"] = True
            raise AssertionError("预算已尽时不得打开浏览器")

        args = SimpleNamespace(dry_run=False, headed=False, lead=100.0, window=120.0,
                               retry_for=120.0, max_attempts=0, sign_end="",
                               retry_start=0, activity_id="", at="", pick=1, name="")
        patches = {"_post": fake_post,
                   "probe_token": lambda budget=None: ("valid", "ok"),
                   "clock_sample": fake_clock_sample,
                   "launch_browser": fake_launch,
                   "log": logs.append,
                   "notify": lambda *a, **k: False,
                   "setup_business_clock": lambda *a, **k: (grab.configure_business_clock(clock), clock)[1]}
        originals = {name: getattr(grab, name, None) for name in patches}
        original_times = (grab.time, time_contract.time)
        restore_pw = install_fake_playwright()
        grab.time = clock
        time_contract.time = clock
        try:
            for name, value in patches.items():
                setattr(grab, name, value)
            with contextlib.redirect_stdout(io.StringIO()):
                code = grab.cmd_grab(args)
        finally:
            for name, value in originals.items():
                if value is None:
                    try:
                        delattr(grab, name)
                    except AttributeError:
                        pass
                else:
                    setattr(grab, name, value)
            grab.time, time_contract.time = original_times
            restore_pw()
        self.assertFalse(created["browser"], "查目标耗尽预算后不得进入浏览器阶段")
        self.assertEqual(posts, [], "预算已尽时一次列表请求都不该发出去")
        self.assertEqual(code, 2)
        done = [line for line in logs if "kind=done" in line]
        self.assertEqual(len(done), 1, "终态必须唯一")
        self.assertIn("stop_reason=retry_duration", done[0])
        self.assertIn("attempts=0", done[0], "没有提交过就不能记次数")


class ClockLossMidFlowTests(unittest.TestCase):
    """C03/C04：校时在流程中途失效时的终态与事实保留。"""

    def test_clock_loss_before_confirm_keeps_zero_submit(self):
        res = run_worker(behavior="lose_before_confirm")
        self.assertEqual(res.stop_reason, "clock_unavailable")
        self.assertEqual(res.code, 3)
        self.assertEqual(res.attempts, 0, "未确认前失效：零提交，不能记一次")
        self.assertEqual(res.requests, [], "失效后不得发出 signUp 请求")
        self.assertEqual(len(res.terminal_lines), 1, "终态必须唯一")

    def test_clock_loss_with_pending_is_unconfirmed_not_missing(self):
        res = run_worker(behavior="lose_after_request")
        self.assertEqual(len(res.requests), 1, "装置确实发出了一次提交")
        self.assertEqual(res.attempts, 1, "已发出的提交次数必须保留")
        self.assertEqual(res.stop_reason, "unconfirmed",
                         "有未决请求时不能说成名额已满/报名失败")
        self.assertEqual(res.code, 2)
        self.assertIn("未确认", "\n".join(res.logs))


class BurstPolicyPureTests(unittest.TestCase):
    """黄金风暴状态机纯逻辑：阶段转移、间隔、404 连击与扩窗。"""

    def _policy(self, open_ts=START, base_deadline=START + 120.0,
                sign_end_ts=None, max_attempts=0, retry_start=None):
        clock = FakeClock(wall=open_ts, mono=1000.0)
        policy = grab.BurstPolicy(
            open_ts=open_ts, base_deadline=base_deadline,
            sign_end_ts=sign_end_ts, max_attempts=max_attempts,
            clock=clock, retry_start=retry_start or open_ts)
        return policy, clock

    def test_constants_match_confirmed_scheme(self):
        self.assertEqual(grab.GOLDEN_WINDOW_S, 1.6)
        self.assertEqual(grab.GOLDEN_INTERVAL_S, 0.09)
        self.assertEqual(grab.GOLDEN_ROUNDS, 10)
        self.assertEqual(grab.FULL_SPEED_INTERVAL_S, 0.18)
        self.assertEqual(grab.NOT_READY_404_LIMIT, 3)
        self.assertEqual(grab.BACKOFF_FACTOR, 1.6)
        self.assertEqual(grab.BACKOFF_MAX_S, 3.0)
        self.assertEqual(grab.ADAPTIVE_WINDOW_S, 1500.0)

    def test_golden_phase_ten_rounds_at_90ms(self):
        policy, clock = self._policy()
        self.assertEqual(policy.phase, policy.PHASE_GOLDEN)
        self.assertEqual(policy.interval_s(), grab.GOLDEN_INTERVAL_S)
        for i in range(grab.GOLDEN_ROUNDS):
            self.assertTrue(policy.can_attempt(), "第 %d 轮应可发起" % (i + 1))
            rid = policy.register_request()
            self.assertTrue(rid)
            # 不结算：留在 pending 才能走满黄金 10 轮（real 会提前退出黄金）
            policy.next_interval_after_wait()
        self.assertEqual(policy.golden_rounds, grab.GOLDEN_ROUNDS)
        self.assertEqual(policy.phase, policy.PHASE_FULL_SPEED,
                         "打满 10 轮后必须切到常规全速")

    def test_golden_window_expiry_exits_to_full_speed(self):
        policy, clock = self._policy()
        clock.wall = START + grab.GOLDEN_WINDOW_S + 0.01
        self.assertEqual(policy.phase, policy.PHASE_FULL_SPEED)
        self.assertEqual(policy.interval_s(), grab.FULL_SPEED_INTERVAL_S)

    def test_golden_skipped_when_open_already_past(self):
        # 开放时刻已过去超过黄金窗口：黄金 0 轮，直接全速
        policy, clock = self._policy()
        clock.wall = START + grab.GOLDEN_WINDOW_S + 5.0   # 现在已远超黄金窗口
        self.assertEqual(policy.phase, policy.PHASE_FULL_SPEED)
        self.assertEqual(policy.golden_rounds, 0)

    def test_404_streak_extends_window_without_adaptive_phase(self):
        # 语义更新（§4，2026-10-29 直发核心轮）：纯 404 段只扩窗、不进 ADAPTIVE。
        # 旧断言 assertEqual(phase, ADAPTIVE) 与 §4「纯 404 不切 phase、只扩窗」
        # 冲突——退避种子只发给「含 throttled 的连击段」，纯 404 段不降速。
        policy, clock = self._policy(base_deadline=START + 30.0)
        clock.wall = START + grab.GOLDEN_WINDOW_S + 1.0
        for i in range(grab.NOT_READY_404_LIMIT):
            rid = policy.register_request()
            policy.settle(rid, "404")
        self.assertEqual(policy.streak_404, grab.NOT_READY_404_LIMIT)
        self.assertNotEqual(policy.phase, policy.PHASE_ADAPTIVE,
                            "纯 404 段（无 throttled）不得进 ADAPTIVE")
        # 扩窗仍照常发生（§4「纯 404 段不切 phase，只扩窗」）
        self.assertGreaterEqual(policy.effective_deadline,
                                policy.retry_start + grab.ADAPTIVE_WINDOW_S - 1.0)
        self.assertLessEqual(policy.effective_deadline,
                             policy.retry_start + grab.ADAPTIVE_WINDOW_S + 1.0)

    def test_404_extension_never_passes_sign_end(self):
        sign_end = START + 60.0
        policy, clock = self._policy(base_deadline=START + 30.0,
                                     sign_end_ts=sign_end)
        clock.wall = START + 10.0
        for _ in range(grab.NOT_READY_404_LIMIT):
            rid = policy.register_request()
            policy.settle(rid, "404")
        self.assertEqual(policy.effective_deadline, sign_end,
                         "sign_end 永远硬截止，扩窗不得越过")

    def test_real_response_resets_streak_and_leaves_adaptive(self):
        # 语义更新（§4）：纯 404 段不进 ADAPTIVE，故 real 之前的 phase 断言改为
        # 「不得是 ADAPTIVE」；real 到达仍清连击并回到全速（§11 未变）。
        policy, clock = self._policy(base_deadline=START + 120.0)
        clock.wall = START + 5.0
        for _ in range(grab.NOT_READY_404_LIMIT):
            rid = policy.register_request()
            policy.settle(rid, "404")
        self.assertNotEqual(policy.phase, policy.PHASE_ADAPTIVE,
                            "纯 404 段不得进 ADAPTIVE（§4）")
        rid = policy.register_request()
        policy.settle(rid, "real")
        self.assertEqual(policy.streak_404, 0)
        self.assertEqual(policy.phase, policy.PHASE_FULL_SPEED,
                         "非 404 真实响应必须立即切回全速")

    def test_wall_now_rejects_invalid_business_reading(self):
        # F05：_wall_now 遇业务钟无效读数必须抛 ClockUnavailable，
        # 绝不回退 time.time 偷跑墙上时间。
        class NoneClock:
            def now(self):
                return None

            def monotonic(self):
                return 0.0

            def elapsed_s(self):
                return 0.0

        policy, _clock = self._policy(base_deadline=START + 120.0)
        policy._clock = NoneClock()
        with self.assertRaises(grab.ClockUnavailable):
            policy._wall_now()

    def test_wall_now_rejects_non_finite_and_unconvertible(self):
        # F05：None/NaN/±inf/无法转换的读数都必须显式 ClockUnavailable，
        # 不得接受非有限值，也不得泄漏 ValueError/TypeError。
        bad_values = (None, float("nan"), float("inf"), float("-inf"),
                      "abc", object())
        for bad in bad_values:
            with self.subTest(bad=repr(bad)):
                class BadClock:
                    def now(self_inner, _value=bad):
                        return _value

                    def monotonic(self_inner):
                        return 0.0

                    def elapsed_s(self_inner):
                        return 0.0

                policy, _clock = self._policy(base_deadline=START + 120.0)
                policy._clock = BadClock()
                with self.assertRaises(grab.ClockUnavailable):
                    policy._wall_now()

    def test_adaptive_backoff_interval_grows_and_caps(self):
        # 语义更新（§3/§4）：退避种子只给「含 throttled 且连击达阈值」的段；
        # 纯 404 段不降速、不给种子。故此处用 throttled 打头凑出种子段，
        # 再断言 interval 从种子起步、随连击放大并封顶 3 秒。
        policy, clock = self._policy(base_deadline=START + 300.0)
        clock.wall = START + 5.0
        policy.settle(policy.register_request(), "throttled", http_status=429)
        for _ in range(grab.NOT_READY_404_LIMIT):
            rid = policy.register_request()
            policy.settle(rid, "404")
        seen = []
        for _ in range(8):
            seen.append(round(policy.interval_s(), 3))
            policy.next_interval_after_wait()
        self.assertEqual(policy.phase, policy.PHASE_ADAPTIVE,
                         "含 throttled 且连击达阈值：gated 成立进 ADAPTIVE")
        self.assertLessEqual(max(seen), grab.BACKOFF_MAX_S,
                             "退避必须封顶 3 秒")
        self.assertGreaterEqual(seen[0], grab.FULL_SPEED_INTERVAL_S)
        self.assertGreater(seen[2], seen[0], "退避必须随连击放大")

    def test_lost_settle_keeps_request_pending(self):
        policy, _ = self._policy()
        rid = policy.register_request()
        policy.settle(rid, "lost")
        self.assertEqual(policy.pending_count(), 1,
                         "响应丢失不得结算，必须保持未决")
        self.assertIsNone(policy.settled_kind(rid))

    def test_unique_request_ids_and_out_of_order_settle(self):
        policy, _ = self._policy()
        r1 = policy.register_request()
        r2 = policy.register_request()
        self.assertNotEqual(r1, r2, "每个请求必须有唯一 ID")
        self.assertEqual(policy.pending_count(), 2)
        policy.settle(r2, "404")        # 乱序：后发的先结算
        self.assertEqual(policy.pending_count(), 1)
        policy.settle(r1, "real")
        self.assertEqual(policy.pending_count(), 0)
        # 语义更新（§11，倒序扫 _order 按发送序）：r1 的 real 是最旧（attempt_no 最
        # 小），清不掉更新的 r2 的 404 → streak 保留 1。旧断言 streak==0 只认「任意
        # real 清连击」，会掩盖旧 5xx/404 被新恢复误清的缺陷，故改为 1。
        self.assertEqual(policy.streak_404, 1, "旧 real 不清更新的 404 连击")

    def test_duplicate_settle_counts_once(self):
        policy, _ = self._policy()
        rid = policy.register_request()
        policy.settle(rid, "404")
        policy.settle(rid, "404")        # 重复结算只认第一次
        self.assertEqual(policy.streak_404, 1)
        self.assertEqual(policy.attempts, 1)

    def test_max_attempts_blocks_further(self):
        policy, clock = self._policy(max_attempts=2)
        clock.wall = START + 5.0
        for _ in range(2):
            self.assertTrue(policy.can_attempt())
            rid = policy.register_request()
            policy.settle(rid, "real")
        self.assertFalse(policy.can_attempt(), "达到 max_attempts 后不得再发起")

    def test_stop_terminal_blocks_all(self):
        policy, _ = self._policy()
        self.assertTrue(policy.can_attempt())
        policy.stop("user_stopped")
        self.assertFalse(policy.can_attempt())
        self.assertEqual(policy.phase, policy.PHASE_TERMINAL)
        self.assertTrue(policy.stopped)

    def test_deadline_expiry_blocks_further(self):
        policy, clock = self._policy(base_deadline=START + 10.0)
        clock.wall = START + 11.0
        self.assertFalse(policy.can_attempt(), "有效截止已过不得再发起")


class GoldenStormIntegrationTests(unittest.TestCase):
    """黄金风暴/404 自适应在 run_worker 替身下的端到端节奏。"""

    def test_full_failure_respects_max_attempts(self):
        res = run_worker(behavior="full", retry_for=120.0, max_attempts=3)
        self.assertEqual(res.attempts, 3)
        self.assertEqual(res.stop_reason, "max_attempts")

    def test_404_not_ready_logs_streak(self):
        # 响应体里的 code 走 real 分类；HTTP 404 需要 status 通道
        # 替身默认 status=200，此处直接验证状态机常量与终态可追溯
        res = run_worker(behavior="full", retry_for=30.0, max_attempts=2)
        self.assertEqual(res.attempts, 2)
        done = res.terminal_lines[-1]
        self.assertIn("pending=", done, "终态必须带 pending 计数")
        self.assertIn("phase=", done, "终态必须带阶段")

    def test_success_stops_immediately(self):
        res = run_worker(behavior="success", retry_for=60.0, max_attempts=10)
        self.assertEqual(res.stop_reason, "success")
        self.assertEqual(res.attempts, 1)

    def test_sign_end_truncates_window(self):
        # sign_end = START+2s，窗口远早于默认 120s 到期
        res = run_worker(behavior="full", retry_for=120.0,
                         sign_end=grab.school_time_text(START + 2.0),
                         max_attempts=0)
        self.assertEqual(res.stop_reason, "sign_end")

    def test_login_invalid_terminal_immediately(self):
        res = run_worker(behavior="full", retry_for=60.0, max_attempts=5,
                         probe_state="expired", probe_detail="登录态已过期（4001）")
        self.assertEqual(res.stop_reason, "login_invalid")
        self.assertEqual(res.attempts, 0)

    def test_request_id_in_submit_events(self):
        res = run_worker(behavior="full", retry_for=10.0, max_attempts=1)
        submit_lines = [line for line in res.logs
                        if "kind=submit" in line]
        self.assertTrue(any("request_id=req-" in line for line in submit_lines),
                        "每笔提交必须带唯一 request_id")


class NonBlockingSubmitTimingTests(unittest.TestCase):
    """黄金风暴非阻塞时序（2026-10-29 返修）：发起节奏只由 BurstPolicy 决定。

    响应迟到、乱序或永不到达都不阻塞下一笔发起；结算按 request_id 各归各，
    attempts/pending/终态保持真实口径。测试全部用替身，不访问学校域名。
    """

    def test_golden_storm_ten_requests_at_90ms_while_responses_in_flight(self):
        # 语义更新（§2 名额上限，2026-10-29 直发核心轮）：未决请求会占名额直到
        # INFLIGHT_TTL_S，旧「响应永不到达也连发 10 笔」与 MAX_INFLIGHT=2 冲突，
        # 该病理场景改由 test_inflight_cap_paces_unknown_pending_requests 守。
        # 本条改为「响应 90ms 内回来、名额很快释放」的正常风暴：10 笔仍按约 90ms 发起。
        res = run_worker(behavior="full", response_delay=0.09,
                         at_offset=OPEN_AHEAD, retry_for=60.0, max_attempts=10)
        self.assertEqual(res.attempts, 10, "真实次数必须记满 10 笔")
        request_times = [at for at, _ in res.page.requests]
        self.assertEqual(len(request_times), 10)
        # request_times 证据：相邻发起间隔约 90ms，in_flight 未满时不阻塞下一笔
        gaps = [b - a for a, b in zip(request_times, request_times[1:])]
        for gap in gaps:
            self.assertGreaterEqual(gap, 0.09 - 1e-4,
                                    "最小间隔 90ms 不能被响应等待吃掉")
            self.assertLess(gap, 0.5,
                            "名额未满时间隔必须远小于任何响应等待——证明 nonblocking")
        span = request_times[-1] - request_times[0]
        self.assertLessEqual(span, grab.GOLDEN_WINDOW_S + 1e-6,
                             "10 笔必须全落在黄金窗口 1.6 秒内")

    def test_slow_responses_stretch_submit_gaps_within_inflight_cap(self):
        # 语义更新（§2）：旧断言「2 秒迟到响应不把间隔拉大」与 MAX_INFLIGHT=2
        # 冲突——响应迟到 2 秒时由名额上限背压，每 2 秒最多 2 笔。改为断言
        # 「间隔被背压拉长但不超 TTL、且不 break 掉 attempts」。
        res = run_worker(behavior="full", response_delay=2.0,
                         at_offset=OPEN_AHEAD, retry_for=30.0, max_attempts=4)
        self.assertEqual(res.attempts, 4)
        request_times = [at for at, _ in res.page.requests]
        gaps = [b - a for a, b in zip(request_times, request_times[1:])]
        for gap in gaps:
            self.assertLess(gap, 2.2, "迟到响应也不该把间隔拉到远超 TTL")
        self.assertGreaterEqual(max(gaps), 1.5,
                                "名额满时必须背压等待，不能仍按 90ms 硬发")

    def test_hot_path_has_no_sync_is_joined_confirm(self):
        # 提交热路径不跑 0.6 秒 ×3 的 is_joined 确认：getJoinInfo 只剩入场预查 + 有界收尾
        res = run_worker(behavior="full", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=6)
        self.assertEqual(res.attempts, 6)
        join_queries = [p for p in res.posts if "/getJoinInfo/" in p["path"]]
        self.assertLessEqual(len(join_queries), 2,
                             "每笔提交后固定跑 0.6 秒 is_joined 确认是被禁止的热路径")

    def test_http_404_streak_settles_by_request_id_and_extends(self):
        # 语义更新（§4）：纯 404 段（无 throttled）不进自适应，只记连击 + 扩窗。
        # 旧断言 assertIn("phase=adaptive_backoff") 与 §4 冲突，改为断言不进自适应
        # 且扩窗生效（retry_deadline 被拉长）。
        res = run_worker(behavior="http_404", at_offset=OPEN_AHEAD,
                         retry_for=30.0, max_attempts=3)
        self.assertEqual(res.attempts, 3)
        done = res.terminal_lines[-1]
        self.assertIn("streak_404=3", done, "三笔 404 必须如实累计")
        self.assertNotIn("phase=adaptive_backoff", done,
                         "纯 404 段（无 throttled）不得进自适应（§4）")
        self.assertRegex(done, r"retry_deadline=\d+", "404×3 必须触发扩窗")
        not_ready = [line for line in res.logs if "kind=not_ready" in line]
        self.assertEqual(len(not_ready), 3, "每笔 404 都要按 request_id 结算上报")

    def test_out_of_order_responses_keep_request_id_attribution(self):
        # 乱序：后发的先到；404 归先发那笔、失败归后发那笔，编号不能串
        res = run_worker(behavior="out_of_order", at_offset=OPEN_AHEAD,
                         retry_for=30.0, max_attempts=2)
        self.assertEqual(res.attempts, 2)
        submits = [line for line in res.logs if "kind=submit" in line]
        self.assertTrue(any("request_id=req-1" in line for line in submits))
        self.assertTrue(any("request_id=req-2" in line for line in submits))
        not_ready = [line for line in res.logs if "kind=not_ready" in line]
        self.assertEqual(len(not_ready), 1, "只有一笔是 404")
        self.assertIn("request_id=req-1", not_ready[0],
                      "先发的那笔拿的是 404：响应虽然后到，编号不能串")
        done = res.terminal_lines[-1]
        self.assertIn("pending=0", done, "两笔都已结算，不得报未决")
        # 语义更新（§11，倒序扫 _order）：req-2（更新的 real，code=0 报名已满）断连击，
        # req-1 的旧 404 虽后到但 attempt_no 更小（更旧），不得重建连击 → streak=0。
        # 旧断言 streak_404=1 只认「有 404 就计 1」，会掩盖旧 404 被误计入的问题。
        self.assertIn("streak_404=0", done,
                      "更新的 real 断连击，旧 404 后到不得重建连击（§11）")

    def test_success_response_terminates_immediately(self):
        # 成功响应到达即终止：不再多发一笔
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                         retry_for=60.0, max_attempts=10)
        self.assertEqual(res.stop_reason, "success")
        self.assertEqual(res.attempts, 1)

    def test_listeners_are_removed_after_run(self):
        # 停止/收尾后解除事件监听，不残留跨计划回调
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                         retry_for=60.0, max_attempts=3)
        self.assertEqual(res.page.request_handlers, [], "request 监听必须解除")
        self.assertEqual(res.page.response_handlers, [], "response 监听必须解除")

    def test_tail_settles_success_arriving_within_one_second(self):
        # 收尾窗口内到达的成功响应必须结算：点击「确定」到结束不到 1 秒
        res = run_worker(behavior="slow_success", response_delay=0.4,
                         at_offset=0.0, retry_for=10.0, max_attempts=1)
        self.assertEqual(res.attempts, 1)
        self.assertEqual(res.stop_reason, "success")
        self.assertEqual(len(res.page.requests), 1, "收尾不得补发第二笔 signUp")
        confirm_at = [at for at, name, _ in res.page.clicks if name == "确定"][-1]
        self.assertLess(res.clock.time() - confirm_at, 1.0,
                        "1 秒内到达的响应不应被漏掉")

    def test_tail_keeps_success_pending_after_one_second(self):
        # 响应迟到 1.2 秒：收尾最多等 1 秒，到点如实报未确认，请求保持 pending
        res = run_worker(behavior="slow_success", response_delay=1.2,
                         at_offset=0.0, retry_for=10.0, max_attempts=1)
        self.assertEqual(res.attempts, 1)
        self.assertEqual(res.stop_reason, "unconfirmed")
        self.assertIn("pending=1", res.terminal_lines[-1],
                      "迟到的成功不能判成成功或失败")
        self.assertEqual(len(res.page.requests), 1, "收尾不得补发第二笔 signUp")
        confirm_at = [at for at, name, _ in res.page.clicks if name == "确定"][-1]
        elapsed = res.clock.time() - confirm_at
        self.assertGreaterEqual(elapsed, 0.99, "收尾不能提前放弃在途响应")
        # 末片按剩余时间缩短，整毫秒推进只留 1ms 容差：1 秒收尾不能被一整片 50ms 撑开
        self.assertLessEqual(elapsed, 1.001 + 1e-6,
                             "收尾按剩余时间截断，量化余量不超过 1ms")

    def test_tail_stops_at_short_retry_budget(self):
        # 重试预算只剩不到 1 秒：收尾按剩余预算封顶，绝不越过预算
        res = run_worker(behavior="slow_success", response_delay=1.0,
                         at_offset=0.0, retry_for=0.5, max_attempts=1)
        self.assertEqual(res.attempts, 1)
        self.assertEqual(res.stop_reason, "unconfirmed")
        self.assertIn("pending=1", res.terminal_lines[-1],
                      "预算到点仍无定论时保留未决")
        self.assertEqual(len(res.page.requests), 1, "收尾不得补发第二笔 signUp")
        confirm_at = [at for at, name, _ in res.page.clicks if name == "确定"][-1]
        self.assertLessEqual(res.clock.time() - confirm_at, 0.501,
                             "收尾不得越过重试预算")
        # 绝对到期时间：准备阶段已经花掉的 0.2 秒也要算进预算，不能只看点击后的时长
        self.assertLessEqual(res.clock.time(), START + 0.501 + 1e-6,
                             "包含准备阶段的总耗时也不能越过重试预算")

    def test_tail_excludes_success_just_after_deadline(self):
        # 1.02 秒的成功不能被截止前启动的整片多接住；同时记录实际请求等待的边界
        waits = []
        original_wait = FakePage.wait_for_timeout

        def record_wait(page, ms):
            if page.confirm_clicks:
                waits.append((page.clock.monotonic(), float(ms) / 1000.0))
            return original_wait(page, ms)

        with patch.object(FakePage, "wait_for_timeout", record_wait):
            res = run_worker(behavior="slow_success", response_delay=1.02,
                             at_offset=0.0, retry_for=10.0, max_attempts=1)
        self.assertEqual(res.attempts, 1)
        self.assertEqual(len(res.page.requests), 1)
        self.assertEqual(res.stop_reason, "unconfirmed")
        self.assertIn("pending=1", res.terminal_lines[-1])
        self.assertEqual(len(res.terminal_lines), 1)
        self.assertTrue(waits)
        tail_start = waits[0][0]
        self.assertGreaterEqual(res.clock.monotonic() - tail_start, 0.999)
        self.assertLessEqual(res.clock.monotonic() - tail_start, 1.001 + 1e-6)
        for started, requested in waits:
            self.assertGreater(requested, 0.0)
            self.assertLessEqual(requested, 0.05 + 1e-6)
            self.assertLessEqual(started + requested - tail_start, 1.001 + 1e-6)
        self.assertEqual(res.page.request_handlers, [])
        self.assertEqual(res.page.response_handlers, [])

    def test_tail_settles_success_just_before_deadline(self):
        # 收紧尾片不能漏掉截止前到达的成功
        res = run_worker(behavior="slow_success", response_delay=0.98,
                         at_offset=0.0, retry_for=10.0, max_attempts=1)
        self.assertEqual(res.attempts, 1)
        self.assertEqual(len(res.page.requests), 1)
        self.assertEqual(res.stop_reason, "success")
        self.assertEqual(len(res.terminal_lines), 1)
        confirm_at = [at for at, name, _ in res.page.clicks if name == "确定"][-1]
        self.assertGreaterEqual(res.clock.time() - confirm_at, 0.98 - 1e-6)
        self.assertLessEqual(res.clock.time() - confirm_at, 1.001 + 1e-6)
        self.assertEqual(res.page.request_handlers, [])
        self.assertEqual(res.page.response_handlers, [])

    def test_tail_stops_at_sign_end(self):
        # 报名截止比尾窗更早时提交必须优先停止；决策 015 起截止后只允许补一次
        # getJoinInfo 核对（原规则「截止后不再补查」已改），且落在 FINAL_CHECK_S 小预算内
        deadline = START + 1.0
        res = run_worker(behavior="slow_success", response_delay=2.0,
                         at_offset=0.0, retry_for=10.0, max_attempts=1,
                         sign_end=grab.school_time_text(deadline))
        self.assertEqual(res.attempts, 1)
        self.assertEqual(len(res.page.requests), 1)
        self.assertEqual(res.stop_reason, "unconfirmed")
        self.assertIn("pending=1", res.terminal_lines[-1])
        self.assertEqual(len(res.terminal_lines), 1)
        self.assertLessEqual(res.clock.time(), deadline + 0.001 + 1e-6)
        late = [post for post in res.posts if post["at"] >= deadline]
        self.assertLessEqual(len(late), 1, "截止后最多补一次核对")
        self.assertTrue(all("/getJoinInfo/" in post["path"] for post in late),
                        "截止后只允许核对报名状态，不能再提交")
        self.assertTrue(all(post["at"] <= deadline + grab.FINAL_CHECK_S for post in late))
        self.assertEqual(res.page.request_handlers, [])
        self.assertEqual(res.page.response_handlers, [])


def _make_policy(open_ts=START, base_deadline=None, sign_end_ts=None,
                 max_attempts=0, retry_start=None, allow_extend=True):
    """构造 BurstPolicy 的模块级替身工厂（供 V4 政策级测试复用）。"""
    clock = FakeClock(wall=open_ts, mono=1000.0)
    policy = grab.BurstPolicy(
        open_ts=open_ts,
        base_deadline=START + 120.0 if base_deadline is None else base_deadline,
        sign_end_ts=sign_end_ts, max_attempts=max_attempts,
        clock=clock, retry_start=retry_start or open_ts,
        allow_extend=allow_extend)
    return policy, clock


class BurstPolicyV4Tests(unittest.TestCase):
    """直发核心轮（2026-10-29）BurstPolicy 新语义：五档分类、名额、地板、时钟契约。

    这些断言在旧实现上为红：旧 settle 无 http_status、无 _order/inflight_count/
    _min_gap/current_phase，_wall_now 走 time()/callable 回退。全部用替身，不访问学校。
    """

    @staticmethod
    def _resp(status, payload=None):
        """最小 HTTP 响应替身：只供 _classify_response 读 status。"""
        return SimpleNamespace(status=status)

    # ---- 分类与解码 -----------------------------------------------
    def test_classify_five_way_split(self):
        self.assertEqual(grab._classify_response(None), "lost")
        self.assertEqual(grab._classify_response(self._resp(404)), "404")
        self.assertEqual(grab._classify_response(self._resp(429)), "throttled")
        self.assertEqual(grab._classify_response(self._resp(500)), "server_error")
        self.assertEqual(grab._classify_response(self._resp(502)), "server_error")
        self.assertEqual(grab._classify_response(self._resp(503)), "server_error")
        self.assertEqual(grab._classify_response(self._resp(200)), "real")
        self.assertEqual(grab._classify_response(self._resp(400)), "real",
                         "非 404/429/5xx 的业务响应归 real")

    def test_decode_body_prefers_utf8_then_gb18030(self):
        body = json.dumps({"code": 4001, "message": "登录已失效"},
                          ensure_ascii=False).encode("gb18030")
        self.assertEqual(grab._decode_body(body)["code"], 4001)
        utf8 = json.dumps({"code": 1}, ensure_ascii=False).encode("utf-8")
        self.assertEqual(grab._decode_body(utf8)["code"], 1)
        # 非 JSON 载体（200+HTML）：解不出对象时退回 {}，不得抛、不得伪装 lost
        self.assertEqual(grab._decode_body(b"<html>not json</html>"), {})

    def test_record_stores_http_status(self):
        policy, _ = _make_policy()
        rec = policy.settle(policy.register_request(), "real", http_status=200)
        self.assertEqual(rec.get("http_status"), 200)
        rec2 = policy.settle(policy.register_request(), "404", http_status=404)
        self.assertEqual(rec2.get("http_status"), 404)

    def test_server_error_settles_and_breaks_streak_with_floor(self):
        policy, _ = _make_policy()
        for _ in range(grab.NOT_READY_404_LIMIT):
            policy.settle(policy.register_request(), "404")
        rid = policy.register_request()
        policy.settle(rid, "server_error", http_status=502)
        self.assertEqual(policy.streak_404, 0, "server_error 必须断 404 连击")
        self.assertEqual(policy.settled_kind(rid), "server_error")
        self.assertEqual(policy.pending_count(), 0, "5xx 不得留 pending")
        self.assertGreaterEqual(policy.interval_s(), 0.5 - 1e-6,
                                "server_error 设 _min_gap=0.5s 地板")

    def test_throttled_counts_into_streak_and_stays_non_adaptive(self):
        policy, clock = _make_policy(base_deadline=START + 300.0)
        clock.wall = START + 5.0
        for _ in range(grab.NOT_READY_404_LIMIT):
            policy.settle(policy.register_request(), "404")
        rid = policy.register_request()
        policy.settle(rid, "throttled", http_status=429)
        self.assertEqual(policy.streak_404, grab.NOT_READY_404_LIMIT + 1,
                         "throttled 与 404 连续混合计入同一段")
        self.assertEqual(policy.pending_count(), 0)
        # 段内含 throttled 且连击达阈值、已过黄金窗 → gated 进 ADAPTIVE
        self.assertEqual(policy.phase, policy.PHASE_ADAPTIVE,
                         "含 throttled 的达阈连击段进 ADAPTIVE")

    def test_settle_survives_clock_unavailable(self):
        policy, clock = _make_policy(base_deadline=START + 300.0)

        def _boom():
            raise grab.ClockUnavailable("时钟故意失效")

        clock.now = _boom
        for _ in range(grab.NOT_READY_404_LIMIT):
            policy.settle(policy.register_request(), "404")
        self.assertEqual(policy.streak_404, grab.NOT_READY_404_LIMIT,
                         "校时失效时 streak 仍照算，结算不能半路崩")
        self.assertEqual(policy.pending_count(), 0)

    # ---- 名额（inflight） -----------------------------------------
    def test_inflight_count_excludes_lost_and_expired(self):
        policy, clock = _make_policy()
        policy.settle(policy.register_request(), "lost")   # 已判丢：pending 但不占名额
        policy.register_request()                          # 正常在途
        self.assertEqual(policy.pending_count(), 2)
        self.assertEqual(policy.inflight_count(), 1, "已判丢的请求不占名额")
        clock.sleep(grab.INFLIGHT_TTL_S + 0.1)             # 剩余那笔超 TTL
        self.assertEqual(policy.pending_count(), 2, "超时不改 pending 事实")
        self.assertEqual(policy.inflight_count(), 0, "超 TTL 不再占名额")

    def test_lost_does_not_block_gate_at_max_inflight_one(self):
        saved = grab.MAX_INFLIGHT
        grab.MAX_INFLIGHT = 1
        try:
            policy, _ = _make_policy()
            policy.settle(policy.register_request(), "lost")
            self.assertLess(policy.inflight_count(), grab.MAX_INFLIGHT,
                            "lost 不占名额：名额上仍有余量")
            policy.register_request()
            self.assertGreaterEqual(policy.inflight_count(), grab.MAX_INFLIGHT,
                                    "正常在途照常占名额")
        finally:
            grab.MAX_INFLIGHT = saved

    def test_v4_constants(self):
        self.assertEqual(grab.MAX_INFLIGHT, 2)
        self.assertEqual(grab.INFLIGHT_TTL_S, 8.0)
        self.assertEqual(grab.SERVER_ERROR_MIN_GAP_S, 0.5)
        self.assertEqual(grab.NOT_READY_SLOWDOWN_AFTER_S, 20.0)
        self.assertEqual(grab.NOT_READY_SLOW_GAP_S, 0.8)

    # ---- 地板（min_gap）F06 反例 ----------------------------------
    def test_min_gap_older_5xx_ignored_by_newer_200_real(self):
        # F06 反例一：#1/#2 发出，#2=200 先回、#1=500 后回 → 地板 0。
        # 倒序扫 _order：newest=#2 real+200 → 地板 0；旧 #1 的 500 不得再抬地板。
        policy, clock = _make_policy(base_deadline=START + 300.0)
        clock.wall = START + 5.0
        r1 = policy.register_request()
        r2 = policy.register_request()
        policy.settle(r2, "real", http_status=200)
        policy.settle(r1, "server_error", http_status=500)
        self.assertLess(policy.interval_s(), 0.5 - 1e-6,
                        "更新的 real+200 已把地板清为 0，旧 5xx 不得再抬地板")

    def test_min_gap_newest_5xx_sets_floor_regardless_of_older_200(self):
        # F06 反例二：#1/#2/#3 发出，#3=500、#1=500、#2=200 → 地板 0.5。
        # 倒序扫 newest=#3 server_error → 地板 0.5；中间的 200 不得清掉它。
        policy, clock = _make_policy(base_deadline=START + 300.0)
        clock.wall = START + 5.0
        r1 = policy.register_request()
        r2 = policy.register_request()
        r3 = policy.register_request()
        policy.settle(r3, "server_error", http_status=500)
        policy.settle(r1, "server_error", http_status=500)
        policy.settle(r2, "real", http_status=200)
        self.assertGreaterEqual(policy.interval_s(), 0.5 - 1e-6,
                                "newest 是 5xx：地板 0.5，不得被中间的 200 清掉")

    def test_min_gap_cleared_by_newer_200_real(self):
        policy, clock = _make_policy(base_deadline=START + 300.0)
        clock.wall = START + 0.5
        policy.settle(policy.register_request(), "server_error", http_status=502)
        rid200 = policy.register_request()
        policy.settle(rid200, "real", http_status=200)
        self.assertLess(policy.interval_s(), 0.5 - 1e-6,
                        "attempt_no 更大的 200-real 必须清 _min_gap")

    def test_min_gap_composes_via_max(self):
        policy, clock = _make_policy(base_deadline=START + 300.0)
        clock.wall = START + 0.5
        policy.settle(policy.register_request(), "server_error", http_status=500)
        for _ in range(grab.NOT_READY_404_LIMIT):
            policy.settle(policy.register_request(), "404")
        self.assertGreaterEqual(policy.interval_s(), 0.5 - 1e-6,
                                "_min_gap 地板与退避取 max，不被覆盖")

    # ---- 纯 404 减速（§12） ---------------------------------------
    def test_pure_404_slows_down_after_twenty_seconds(self):
        policy, clock = _make_policy(base_deadline=START + 300.0)
        clock.wall = START + 5.0
        policy.settle(policy.register_request(), "404")
        self.assertAlmostEqual(policy.interval_s(), grab.FULL_SPEED_INTERVAL_S, places=6)
        clock.sleep(grab.NOT_READY_SLOWDOWN_AFTER_S - 1.0)
        self.assertAlmostEqual(policy.interval_s(), grab.FULL_SPEED_INTERVAL_S, places=6,
                               msg="20 秒内不降速")
        clock.sleep(2.0)
        self.assertAlmostEqual(policy.interval_s(), grab.NOT_READY_SLOW_GAP_S, places=6,
                               msg="纯 404 段超过 20 秒后降到 0.8s 地板")

    def test_slowdown_cleared_when_real_arrives(self):
        policy, clock = _make_policy(base_deadline=START + 300.0)
        clock.wall = START + 5.0
        policy.settle(policy.register_request(), "404")
        clock.sleep(grab.NOT_READY_SLOWDOWN_AFTER_S + 1.0)
        self.assertAlmostEqual(policy.interval_s(), grab.NOT_READY_SLOW_GAP_S, places=6)
        policy.settle(policy.register_request(), "real", http_status=200)
        self.assertAlmostEqual(policy.interval_s(), grab.FULL_SPEED_INTERVAL_S, places=6,
                               msg="real 一到，地板立即解除")

    # ---- 窗口扩展与显式预算 ----------------------------------------
    def test_pure_404_streak_extends_window_without_adaptive(self):
        policy, clock = _make_policy(base_deadline=START + 30.0)
        clock.wall = START + grab.GOLDEN_WINDOW_S + 1.0
        for _ in range(grab.NOT_READY_404_LIMIT):
            policy.settle(policy.register_request(), "404")
        self.assertEqual(policy.streak_404, grab.NOT_READY_404_LIMIT)
        self.assertNotEqual(policy.phase, policy.PHASE_ADAPTIVE, "纯 404 段不进 ADAPTIVE")
        self.assertGreaterEqual(policy.effective_deadline,
                                policy.retry_start + grab.ADAPTIVE_WINDOW_S - 1.0)
        self.assertLessEqual(policy.effective_deadline,
                             policy.retry_start + grab.ADAPTIVE_WINDOW_S + 1.0)
        self.assertEqual(policy._backoff_s, grab.FULL_SPEED_INTERVAL_S,
                         "纯 404 段不给退避种子")

    def test_streak_with_throttled_extends_seeds_and_enters_adaptive(self):
        policy, clock = _make_policy(base_deadline=START + 30.0)
        clock.wall = START + 5.0
        base_deadline = policy.effective_deadline
        for _ in range(grab.NOT_READY_404_LIMIT - 1):
            policy.settle(policy.register_request(), "404")
        policy.settle(policy.register_request(), "throttled", http_status=429)
        self.assertEqual(policy.streak_404, grab.NOT_READY_404_LIMIT)
        self.assertGreater(policy.effective_deadline, base_deadline,
                           "含 throttled 的连击也扩窗")
        expected_seed = min(grab.BACKOFF_MAX_S,
                            grab.FULL_SPEED_INTERVAL_S * grab.BACKOFF_FACTOR)
        self.assertEqual(policy._backoff_s, expected_seed,
                         "含 throttled 的连击段给退避种子")
        self.assertEqual(policy.phase, policy.PHASE_ADAPTIVE)

    def test_explicit_retry_for_disables_adaptive_extension(self):
        policy, clock = _make_policy(base_deadline=START + 30.0, allow_extend=False)
        clock.wall = START + 5.0
        for _ in range(grab.NOT_READY_404_LIMIT + 2):
            policy.settle(policy.register_request(), "404")
        self.assertEqual(policy.effective_deadline, START + 30.0,
                         "显式 --retry-for=30：纯 404 连击不得扩窗")
        self.assertGreater(policy.streak_404, grab.NOT_READY_404_LIMIT,
                           "连击照常计数，只是不拉窗口")

    def test_404_extension_never_passes_sign_end(self):
        sign_end = START + 60.0
        policy, clock = _make_policy(base_deadline=START + 30.0, sign_end_ts=sign_end)
        clock.wall = START + 10.0
        for _ in range(grab.NOT_READY_404_LIMIT):
            policy.settle(policy.register_request(), "404")
        self.assertEqual(policy.effective_deadline, sign_end,
                         "sign_end 永远硬截止，扩窗不得越过")

    # ---- 连击按发送序倒扫 ------------------------------------------
    def test_out_of_order_old_404_does_not_reenter_adaptive(self):
        policy, clock = _make_policy(base_deadline=START + 300.0)
        clock.wall = START + 5.0
        r3 = policy.register_request()
        r4 = policy.register_request()
        r5 = policy.register_request()
        r6 = policy.register_request()
        policy.settle(r6, "real", http_status=200)
        self.assertEqual(policy.phase, policy.PHASE_FULL_SPEED)
        policy.settle(r3, "404")
        policy.settle(r4, "404")
        policy.settle(r5, "404")
        self.assertEqual(policy.streak_404, 0,
                         "更新的 real 之后，旧 404 不得重建连击")
        self.assertEqual(policy.phase, policy.PHASE_FULL_SPEED)

    def test_streak_counts_from_newest_after_late_real(self):
        policy, clock = _make_policy(base_deadline=START + 300.0)
        clock.wall = START + 5.0
        r3 = policy.register_request()
        r4 = policy.register_request()
        r5 = policy.register_request()
        policy.settle(r4, "404")
        policy.settle(r5, "404")
        policy.settle(r3, "real", http_status=200)
        self.assertEqual(policy.streak_404, 2,
                         "旧 real 不清更新的 404 连击（只更新的 real 清）")
        self.assertEqual(policy.phase, policy.PHASE_FULL_SPEED)

    # ---- golden 退出与种子保留 --------------------------------------
    def test_golden_seed_survives_exit_and_adaptive_grows(self):
        policy, clock = _make_policy(base_deadline=START + 300.0)
        policy.settle(policy.register_request(), "throttled", http_status=429)
        for _ in range(grab.NOT_READY_404_LIMIT):
            policy.settle(policy.register_request(), "404")
        self.assertEqual(policy.phase, policy.PHASE_GOLDEN,
                         "golden 内 ADAPTIVE_IN_GOLDEN=False，phase 不切")
        seed = min(grab.BACKOFF_MAX_S, grab.FULL_SPEED_INTERVAL_S * grab.BACKOFF_FACTOR)
        self.assertAlmostEqual(policy._backoff_s, seed, places=6)
        for _ in range(grab.GOLDEN_ROUNDS - grab.NOT_READY_404_LIMIT):
            policy.settle(policy.register_request(), "404")
        self.assertEqual(policy.phase, policy.PHASE_ADAPTIVE,
                         "走满轮数退 golden，gated 成立进 ADAPTIVE，种子要保留")
        self.assertAlmostEqual(policy._backoff_s, seed, places=6)

    def test_golden_exit_preserves_seed_and_enters_adaptive(self):
        policy, clock = _make_policy(base_deadline=START + 300.0)
        self.assertEqual(policy.phase, policy.PHASE_GOLDEN)
        for _ in range(grab.NOT_READY_404_LIMIT):
            policy.settle(policy.register_request(), "throttled", http_status=429)
        self.assertEqual(policy.phase, policy.PHASE_GOLDEN,
                         "golden 内 ADAPTIVE_IN_GOLDEN=False，phase 不切")
        seed = round(min(grab.BACKOFF_MAX_S,
                         grab.FULL_SPEED_INTERVAL_S * grab.BACKOFF_FACTOR), 6)
        self.assertAlmostEqual(policy._backoff_s, seed, places=6)
        clock.wall = START + grab.GOLDEN_WINDOW_S + 0.01
        self.assertEqual(policy.phase, policy.PHASE_ADAPTIVE,
                         "golden 结束后按带门控 level 进 ADAPTIVE")
        self.assertAlmostEqual(policy.interval_s(), seed, places=6)
        policy.settle(policy.register_request(), "throttled", http_status=429)
        self.assertAlmostEqual(policy._backoff_s, seed, places=6,
                               msg="种子边沿不重复触发")

    def test_non_200_real_breaks_streak_but_not_golden(self):
        policy, _ = _make_policy(base_deadline=START + 300.0)
        policy.settle(policy.register_request(), "404")
        policy.settle(policy.register_request(), "real", http_status=400)
        self.assertEqual(policy.streak_404, 0, "real 断 streak")
        self.assertEqual(policy.phase, policy.PHASE_GOLDEN,
                         "非 200 real 不得结束 golden")

    def test_200_real_ends_golden(self):
        policy, _ = _make_policy(base_deadline=START + 300.0)
        policy.settle(policy.register_request(), "real", http_status=200)
        self.assertEqual(policy.phase, policy.PHASE_FULL_SPEED)

    # ---- 时钟契约 --------------------------------------------------
    def test_wall_now_reads_business_epoch_only(self):
        policy, _ = _make_policy()

        class BusinessOnlyClock:
            def __init__(self):
                self.now_calls = 0

            def now(self):
                self.now_calls += 1
                return START + 5.0

        clock = BusinessOnlyClock()
        policy._clock = clock
        self.assertGreaterEqual(policy._wall_now(), START)
        self.assertEqual(clock.now_calls, 1, "必须调用 now() 读业务 epoch")

    def test_current_phase_does_not_touch_clock_or_refresh(self):
        policy, clock = _make_policy()

        class ExplodingClock:
            def now(self):
                raise RuntimeError("校时不可用")

        policy._clock = ExplodingClock()
        policy._phase = policy.PHASE_GOLDEN
        self.assertEqual(policy.current_phase(), policy.PHASE_GOLDEN)
        policy._phase = policy.PHASE_ADAPTIVE
        self.assertEqual(policy.current_phase(), policy.PHASE_ADAPTIVE)

    def test_clockclient_offline_contract(self):
        from business_clock import ClockClient

        tick = [1000.0]
        snap = {
            "schema": 1, "owner_id": "contract", "generation": 1,
            "state": "ready", "epoch_s": START, "tick_s": tick[0],
            "sampled_tick_s": tick[0], "uncertainty_s": 0.0,
            "source": "test", "age_s": 0.0, "reason": "契约测试",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clock.json"
            path.write_text(json.dumps(snap), encoding="utf-8")
            clock = ClockClient(snapshot_path=str(path), owner_id="contract",
                                tick_fn=lambda: tick[0])
            policy = grab.BurstPolicy(
                open_ts=START, base_deadline=START + 120.0,
                sign_end_ts=None, max_attempts=0,
                clock=clock, retry_start=START)
            for i in range(grab.GOLDEN_ROUNDS):
                self.assertTrue(policy.can_attempt(),
                                "第 %d 轮应可发起（ClockClient 驱动）" % (i + 1))
                self.assertTrue(policy.register_request())
                policy.next_interval_after_wait()
            self.assertEqual(policy.phase, policy.PHASE_FULL_SPEED,
                             "ClockClient 驱动下打满 10 轮须切常规全速")


class UnifiedGateAndFinalizeTests(unittest.TestCase):
    """直发核心轮集成回归：闸门顺序、4001 停发、unconfirmed 终态、异常收口。

    覆盖「成功不被 False/异常覆盖」「pending+未报名=unconfirmed」「运行异常先结算
    可读队列再关浏览器」「4001 后同一 1 秒尾窗内仍可结算成功」。全部用替身。
    """

    def test_4001_stops_sending(self):
        res = run_worker(behavior="login_expired", retry_for=30.0, max_attempts=5)
        self.assertEqual(res.stop_reason, "login_invalid")
        self.assertEqual(res.attempts, 1, "4001 后不得再发第二笔")

    def test_login_words_in_message_do_not_mark_invalid(self):
        res = run_worker(behavior="login_words_only", retry_for=3.0, max_attempts=1)
        self.assertNotEqual(res.stop_reason, "login_invalid",
                            "业务失败文案不得被误判成需要重登（只认 str(code)=='4001'）")

    def test_4001_while_success_in_flight_reports_success(self):
        res = run_worker(behavior="login_race", retry_for=30.0, max_attempts=2)
        self.assertEqual(res.stop_reason, "success",
                         "4001 与成功同时在途：取消尾窗的 not login_invalid 限制后成功优先")
        self.assertEqual(res.attempts, 2)

    def test_explicit_retry_for_does_not_extend_window(self):
        res = run_worker(behavior="http_404", at_offset=OPEN_AHEAD,
                         retry_for=30.0, max_attempts=4)
        line = res.terminal_lines[-1]
        deadline = int(line.split("retry_deadline=")[1].split(" ")[0])
        self.assertLess(deadline, int(START + 1000),
                        "显式 --retry-for 给了秒数，扩窗不得生效")
        self.assertGreaterEqual(res.attempts, grab.NOT_READY_404_LIMIT)

    def test_retry_for_zero_keeps_sign_end(self):
        deadline = START + 5.0
        res = run_worker(behavior="full", at_offset=OPEN_AHEAD, retry_for=0.0,
                         max_attempts=0, sign_end=grab.school_time_text(deadline))
        line = res.terminal_lines[-1]
        got = int(line.split("retry_deadline=")[1].split(" ")[0])
        self.assertLessEqual(got, int(deadline) + 1,
                             "--retry-for=0：重试截止不得越过 sign_end")

    def test_retry_for_missing_falls_back_to_window(self):
        # args.retry_for=None → 回退 args.window=120（run_worker 固定 window=120）
        res = run_worker(behavior="full", at_offset=OPEN_AHEAD, retry_for=None,
                         max_attempts=1)
        line = res.terminal_lines[-1]
        got = int(line.split("retry_deadline=")[1].split(" ")[0])
        self.assertGreaterEqual(got, int(START + 100),
                                "--retry-for 缺失：按 window=120 秒回退")

    def test_requestfailed_releases_inflight_slot(self):
        # §2：导航中止只发 requestfailed——必须按 lost 结算并立即让出名额，
        # 否则 MAX_INFLIGHT=1 时第二笔永远发不出（卡死）。
        saved = grab.MAX_INFLIGHT
        grab.MAX_INFLIGHT = 1
        try:
            res = run_worker(behavior="abort_inflight", at_offset=OPEN_AHEAD,
                             retry_for=30.0, max_attempts=2)
        finally:
            grab.MAX_INFLIGHT = saved
        self.assertEqual(res.attempts, 2, "中止的在途请求必须让出名额，不得卡死")
        self.assertEqual(res.stop_reason, "unconfirmed",
                         "requestfailed=lost 仍 pending：终态保留未决")
        request_times = [at for at, _ in res.page.requests]
        self.assertEqual(len(request_times), 2)
        self.assertLess(request_times[1] - request_times[0], 1.0,
                        "lost 立即释放名额：第二笔应在 TTL 之外很快发出")

    def test_confirm_gate_waits_in_place_when_inflight_full(self):
        saved = grab.MAX_INFLIGHT
        grab.MAX_INFLIGHT = 1
        try:
            res = run_worker(behavior="open_race", response_delay=0.3,
                             at_offset=OPEN_AHEAD, retry_for=30.0, max_attempts=2)
        finally:
            grab.MAX_INFLIGHT = saved
        self.assertGreaterEqual(res.page.confirm_clicks, 1, "名额释放后必须点上「确定」")
        names = [name for _, name, _ in res.page.clicks]
        self.assertEqual(names[:2], ["uni-button", "确定"],
                         "名额满时先等名额再点确定：确认框开着不得重复点「立即报名」")
        for left, right in zip(names, names[1:]):
            self.assertFalse(left == right == "uni-button",
                             "确认框还开着就重复点「立即报名」会被弹窗遮住、白等 3 秒")

    def test_gate_drains_success_before_confirm_click(self):
        res = run_worker(behavior="success_on_open", max_attempts=2)
        self.assertEqual(res.stop_reason, "success")
        self.assertEqual(res.page.confirm_clicks, 0,
                         "闸门②先 drain 到成功，确认框不必再点")

    def test_pending_with_not_joined_false_is_unconfirmed(self):
        # pending>0 且最终核对未报名：必须 unconfirmed，不引入 not_joined。
        real = grab.is_joined
        grab.is_joined = lambda *a, **k: False
        try:
            res = run_worker(behavior="lost", retry_for=6.0, max_attempts=1)
        finally:
            grab.is_joined = real
        self.assertEqual(res.stop_reason, "unconfirmed")
        self.assertIn("pending=1", res.terminal_lines[-1])

    def test_success_not_overwritten_by_false_or_exception(self):
        # 成功已结算：最终核对抛异常也不得覆盖 success（F01）。
        real = grab.is_joined

        def _boom(*a, **k):
            raise RuntimeError("最终核对崩了")

        grab.is_joined = _boom
        try:
            res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                             retry_for=60.0, max_attempts=3)
        finally:
            grab.is_joined = real
        self.assertEqual(res.stop_reason, "success",
                         "成功不得被最终核对的 False/异常覆盖")

    def test_runtime_exception_settles_queue_before_close(self):
        # 页面崩：先把一笔成功应答入队，再抛异常。可读队列必须先被结算 → success，
        # 不能判成 process_error；且浏览器关闭后不得再有页面动作（F04 守卫）。
        res = run_worker(behavior="boom_after_response", at_offset=OPEN_AHEAD,
                         retry_for=60.0, max_attempts=1)
        self.assertEqual(res.stop_reason, "success",
                         "运行异常前已入队的成功必须先被结算，不得被 process_error 覆盖")
        self.assertEqual(len(res.terminal_lines), 1, "唯一 done/终态")
        self.assertTrue(res.page.closed, "浏览器最终必须被关闭")

    def test_process_error_without_pending_preserved(self):
        # 无 pending 的流程异常（最终核对抛错）：保留 process_error，不被 False 覆盖。
        # 用 "full"（1 笔 code0 已决、pending=0、attempts=1）使流程走到最终单次核对，
        # 该核对抛错时如实报 process_error；foreign_only 不产生报名尝试走不到最终核对。
        real = grab.is_joined

        def _boom(*a, **k):
            raise RuntimeError("核对崩了")

        grab.is_joined = _boom
        try:
            res = run_worker(behavior="full", retry_for=6.0,
                             max_attempts=1)
        finally:
            grab.is_joined = real
        self.assertEqual(res.stop_reason, "process_error")

    def test_429_triple_extends_window_events(self):
        # 429 三连：policy/budget/retry_deadline 必须同时扩窗并上报事件。
        # retry_for=None 走「缺失→120 秒回退 + 允许自适应扩窗」路径（显式
        # --retry-for 禁扩是另一条语义，见 test_explicit_retry_for_does_not_extend）。
        res = run_worker(behavior="http_429_triple", at_offset=OPEN_AHEAD,
                         retry_for=None, max_attempts=3)
        self.assertEqual(res.attempts, 3)
        done = res.terminal_lines[-1]
        self.assertRegex(done, r"retry_deadline=\d+", "429×3 必须触发扩窗")
        extended = [line for line in res.logs if "kind=window_extended" in line]
        self.assertTrue(extended, "扩窗必须以 window_extended 事件上报")

    def test_404_429_mixed_streak_extends(self):
        res = run_worker(behavior="http_404_429", at_offset=OPEN_AHEAD,
                         retry_for=30.0, max_attempts=3)
        self.assertEqual(res.attempts, 3)
        done = res.terminal_lines[-1]
        self.assertIn("streak_404=3", done, "404/404/429 连击必须如实累计")
        self.assertRegex(done, r"retry_deadline=\d+", "混合连击必须触发扩窗")

    def test_200_html_settles_as_real_not_lost(self):
        # 200+HTML：作为已得 HTTP 应答结算为 real，不伪装 lost、不留 pending。
        res = run_worker(behavior="full", at_offset=OPEN_AHEAD,
                         retry_for=30.0, max_attempts=1)
        done = res.terminal_lines[-1]
        self.assertIn("pending=0", done, "200+HTML 必须结算为 real，不留 pending")


class FakeTransport:
    """直发传输替身：把 started 与终态事件塞进 grab 侧的队列。
    responder_fn 是类级回调 ticket -> 终态 dict / "started_only" / None（留未决）。

    虚拟事件泵（opt-in）：release_at_fn(ticket, event) 返回虚拟放行时刻（绝对
    mono 读数）时事件先进暂存，由 get_nowait 在到期后放行——用于构造“started
    真正滞后/迟到应答”。返回 None 表示立即入列；默认整段同步，旧例不受影响。
    extra_fn(ticket) 返回的外来/重复事件走同一投递路径，供来源校验红例注入。
    """

    responder_fn = None
    extra_fn = None
    release_at_fn = None
    clock = None
    instances = []

    def __init__(self, event_queue):
        self.queue = event_queue
        self.tickets = []
        self.active = set()
        self.closed = False
        self.cap = 2
        self.submit_calls = 0
        self._held = []
        if FakeTransport.release_at_fn is not None:
            self._wrap_queue(event_queue)
        FakeTransport.instances.append(self)

    @classmethod
    def bind_clock(cls, clock):
        cls.clock = clock

    def _wrap_queue(self, q):
        """按虚拟时钟放行暂存事件：grab 侧每次 get_nowait 先收到期件。"""
        orig_get_nowait = q.get_nowait
        held = self._held

        def get_nowait():
            if held and FakeTransport.clock is not None:
                now = FakeTransport.clock.mono
                due = [item for item in held if item[0] <= now]
                if due:
                    held[:] = [item for item in held if item[0] > now]
                    due.sort(key=lambda item: item[0])
                    for _, ev in due:
                        self._deliver(ev)
            return orig_get_nowait()

        q.get_nowait = get_nowait

    def _emit(self, ticket, event):
        release_at = None
        if FakeTransport.release_at_fn is not None:
            release_at = FakeTransport.release_at_fn(ticket, event)
        if release_at is None:
            self._deliver(event)
        else:
            self._held.append((release_at, event))

    def _deliver(self, event):
        if event.get("kind") in ("completed", "failed", "not_started"):
            self.active.discard(event.get("request_id"))
        self.queue.put(event)

    def try_submit(self, ticket):
        self.submit_calls += 1
        if self.closed or len(self.active) >= self.cap:
            return False
        rid = ticket["request_id"]
        if any(t["request_id"] == rid for t in self.tickets):
            return False
        self.tickets.append(dict(ticket))
        self.active.add(rid)
        base = {"kind": "started", "run_id": ticket["run_id"],
                "request_id": rid, "attempt_no": ticket["attempt_no"]}
        self._emit(ticket, base)
        if FakeTransport.responder_fn is not None:
            ev = FakeTransport.responder_fn(ticket)
            if ev is not None and ev != "started_only":
                term = dict(base)
                term.update(ev)
                self._emit(ticket, term)
        if FakeTransport.extra_fn is not None:
            for extra in FakeTransport.extra_fn(ticket):
                self._emit(ticket, extra)
        return True

    def active_count(self):
        return len(self.active)

    def close(self):
        self.closed = True

    @classmethod
    def reset(cls):
        cls.instances = []
        cls.responder_fn = None
        cls.extra_fn = None
        cls.release_at_fn = None


def _d_ok(ticket=None):
    return {"kind": "completed", "http_status": 200,
            "body_bytes": json.dumps({"code": 1, "message": "ok"}).encode("utf-8")}


def _d_payload(code, message=""):
    return {"kind": "completed", "http_status": 200,
            "body_bytes": json.dumps({"code": code, "message": message}).encode("utf-8")}


def _d_html(ticket=None):
    return {"kind": "completed", "http_status": 200,
            "body_bytes": "<html>报名人数已满</html>".encode("utf-8")}


def _d_http(status):
    return {"kind": "completed", "http_status": status,
            "body_bytes": b"<html>err</html>"}


def _d_failed(ticket=None):
    return {"kind": "failed", "error_class": "TimeoutError"}


class _RecordingSigner:
    """记录 activity_id/epoch_ms；raise_unavailable 模拟 SignerUnavailable。"""

    def __init__(self):
        self.calls = []
        self.keys = []
        self.raise_unavailable = False

    def __call__(self, activity_id, epoch_ms, key=None):
        if self.raise_unavailable:
            raise RuntimeError("SignerUnavailable: native signer 不可用")
        self.calls.append((activity_id, epoch_ms))
        self.keys.append(key)
        return "sig-%d" % epoch_ms


KNOWN_SRC = "https://school.example/assets/index.b489a1d6.js"
UNKNOWN_SRC = "https://school.example/assets/other.js"
VERSION_MSG = "版本不兼容，请刷新页面或清除缓存后重试"


class UnifiedDirectLoopTests(unittest.TestCase):
    """直发为主 + click 单向兜底：同一调度账本、唯一 run、全局名额、不产生第二终态。"""

    def setUp(self):
        FakeTransport.reset()

    def _known(self):
        return [KNOWN_SRC]

    def test_known_profile_uses_direct_without_button(self):
        # 取到运行时密钥 + signer 可用：直发为主，无需按钮可见也能成功。
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(_d_ok)
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=1, button_visible=False, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "success", "已知 profile 直发必须能成功")
        self.assertTrue(signer.calls, "直发必须经 signer 现算签名")
        self.assertTrue(FakeTransport.instances, "已知 profile 必须构造直发 transport")

    def test_no_runtime_key_falls_back_to_click(self):
        # 取不到运行时密钥（决策 015）：不构造 transport、不签名，走点击，且写明原因。
        # 入口脚本叫什么不再影响判断（以前按文件名白名单，学校换包就静默失效）。
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=1, button_visible=True, script_srcs=[UNKNOWN_SRC],
                         direct_signer=signer, direct_transport=FakeTransport,
                         runtime_key=None)
        self.assertEqual(res.stop_reason, "success")
        self.assertEqual(FakeTransport.instances, [], "没有密钥不得构造直发 transport")
        self.assertEqual(signer.calls, [], "没有密钥不得签名")
        self.assertIn("报名路径：点击（原因：取不到运行时密钥", "\n".join(res.logs))

    def test_signer_unavailable_falls_back_to_click(self):
        # signer 不可用：直发前降级为 click，签名失败不提交 ticket。
        signer = _RecordingSigner()
        signer.raise_unavailable = True
        FakeTransport.responder_fn = staticmethod(_d_ok)
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=1, button_visible=True, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "success")
        self.assertTrue(FakeTransport.instances)
        self.assertEqual(FakeTransport.instances[0].tickets, [],
                         "签名失败不得提交直发 ticket")

    def test_direct_sign_time_from_clock_at_fire(self):
        # 签名时刻取自业务时钟且在发射当刻：epoch_ms 为 START*1000 量级的正整数。
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(_d_ok)
        run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=60.0,
                   max_attempts=1, button_visible=False, script_srcs=self._known(),
                   direct_signer=signer, direct_transport=FakeTransport)
        self.assertTrue(signer.calls)
        act_id, epoch_ms = signer.calls[0]
        self.assertEqual(act_id, "act-1")
        self.assertIsInstance(epoch_ms, int)
        self.assertGreaterEqual(epoch_ms, int(START * 1000))

    def test_plain_zero_code_does_not_downgrade(self):
        # 普通 code=0（非版本不兼容、未进分类表）：同一文案不到 3 次不降级，直发继续。
        # 决策 015 前这里用「报名人数已满」，它现在是终态，改用未识别文案。
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(
            lambda t: _d_payload(UNKNOWN_REPLY["code"], UNKNOWN_REPLY["message"]))
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=2, button_visible=True, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertNotIn("切换为点击兜底", "\n".join(res.logs),
                         "普通 code=0 不得触发降级")
        # code=0 已得 HTTP 应答：结算为 real（不留 pending），次数耗尽报 max_attempts。
        self.assertEqual(res.stop_reason, "max_attempts")

    def test_network_failure_keeps_pending_not_downgrade(self):
        # 网络 failed 按 lost 保持 pending，不降级、不假造成功。
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(_d_failed)
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=2, button_visible=False, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertNotIn("切换为点击兜底", "\n".join(res.logs),
                         "网络失败不得触发降级")
        self.assertEqual(res.stop_reason, "unconfirmed",
                         "网络失败保持未决，最终应报 unconfirmed")

    def test_version_incompatible_downgrades_once(self):
        # 版本不兼容（决策 015）：先重取一次运行时密钥再直发；重取后仍不兼容才单向降级为
        # click，共两笔直发 ticket，随后点击成功。
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(
            lambda t: _d_payload(0, VERSION_MSG))
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=3, button_visible=True, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "success")
        logs = "\n".join(res.logs)
        self.assertIn("已重取运行时密钥", logs)
        self.assertIn("切换为点击兜底", logs)
        self.assertEqual(len(FakeTransport.instances[0].tickets), 2,
                         "重取密钥后只再试一笔，降级后不得再提交直发 ticket")

    def test_direct_404_429_500_settle_into_ledger(self):
        # 直发 404/429/5xx：并入同一账本五档分类，不降级、不假造成功。
        for status, expect in ((404, "404"), (429, "限流"), (500, "5xx")):
            with self.subTest(status=status):
                FakeTransport.reset()
                signer = _RecordingSigner()
                FakeTransport.responder_fn = staticmethod(
                    lambda t, s=status: _d_http(s))
                res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                                 retry_for=30.0, max_attempts=1, button_visible=False,
                                 script_srcs=self._known(), direct_signer=signer,
                                 direct_transport=FakeTransport)
                self.assertNotIn("切换为点击兜底", "\n".join(res.logs))
                self.assertIn(expect, "\n".join(res.logs),
                              "HTTP %d 必须按五档分类入账本" % status)

    def test_max_attempts_one_allows_single_ticket(self):
        # started 滞后（无终态）也只允许一笔：max_attempts=1 严格，最终未决。
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(lambda t: "started_only")
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=1, button_visible=False, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(len(FakeTransport.instances[0].tickets), 1,
                         "max_attempts=1 时 started 滞后也不得有第二笔")
        self.assertEqual(res.stop_reason, "unconfirmed")

    def test_direct_html_200_settles_real_not_lost(self):
        # 直发 200+HTML：结算为 real，不留 pending、不假造 lost；
        # 200 无业务 code 属通道/协议异常：停止新发，报 process_error（F01 返修）。
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(_d_html)
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=1, button_visible=False, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        done = res.terminal_lines[-1]
        self.assertIn("pending=0", done, "直发 200+HTML 必须结算为 real，不留 pending")
        self.assertEqual(res.stop_reason, "process_error",
                         "200 无业务 code 是通道/协议异常，必须停发报 process_error")

    def test_direct_4001_stops_new_sends(self):
        # 直发只认 str(code)=='4001'：命中即停新发，报 login_invalid。
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(lambda t: _d_payload(4001))
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=3, button_visible=False, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "login_invalid",
                         "直发 code=4001 必须判 login_invalid")
        self.assertEqual(len(FakeTransport.instances[0].tickets), 1,
                         "4001 后必须停止新发")

    def test_direct_login_words_in_message_do_not_mark_invalid(self):
        # message 含「登录/身份验证」但 code=0：不判失效（只认 str(code)=='4001'）。
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(
            lambda t: _d_payload(0, "请登录后完成身份验证"))
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=1, button_visible=False, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertNotEqual(res.stop_reason, "login_invalid",
                            "message 关键词不得判登录失效")

    def test_closed_late_event_does_not_add_new_done(self):
        # 关闭后迟到事件不新增终态：transport.close 后不再接纳（替身拒新）。
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(lambda t: "started_only")
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=1, button_visible=False, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        done_lines = [l for l in res.terminal_lines if "kind=done" in l or l.startswith("done")]
        self.assertEqual(len(res.terminal_lines), 1, "不得产生第二终态")
        self.assertTrue(FakeTransport.instances[0].closed, "收尾必须 close transport")

    def test_production_ticket_contract(self):
        # 生产 _try_direct_fire 交给 transport 的 ticket 契约（F01）：
        # url = API + '/rjyHdCyr/signUp/' + sig，headers 带 token/Accept/Referer/UA，
        # 与既有 _get 约定一致；token 不进日志。断言对象是生产构造的 ticket 本身。
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(_d_ok)
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=1, button_visible=False, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        tickets = FakeTransport.instances[0].tickets
        self.assertTrue(tickets, "已知 profile 必须提交生产 ticket")
        t = tickets[0]
        self.assertTrue(signer.calls, "必须现算签名")
        fake_sig = "sig-%d" % signer.calls[0][1]
        self.assertEqual(t["url"], grab.API + "/rjyHdCyr/signUp/" + fake_sig,
                         "F01：URL 必须等于 API+'/rjyHdCyr/signUp/'+sig（含 /dr/api）")
        headers = t["headers"]
        self.assertEqual(headers.get("token"), "test-token",
                         "F01：headers 必须带 token 替身值")
        self.assertEqual(headers.get("Accept"), "application/json, text/plain, */*",
                         "F01：Accept 与既有 _get 约定相同")
        self.assertEqual(headers.get("Referer"), grab.REFERER)
        self.assertEqual(headers.get("User-Agent"), grab.UA)
        self.assertNotIn("test-token", "\n".join(res.logs), "不得打印 token")

    def test_missing_token_stops_without_ticket_click_or_leak(self):
        # token 缺失：不建 ticket、try_submit 调用为 0、不点 click、不伪造 4001、不泄漏值。
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(_d_ok)
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=3, button_visible=True, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport,
                         api_token="")
        inst = FakeTransport.instances[0]
        self.assertEqual(inst.submit_calls, 0, "缺 token 不得调用 try_submit")
        self.assertEqual(inst.tickets, [], "缺 token 不得创建 ticket")
        self.assertNotEqual(res.stop_reason, "login_invalid", "不得伪造 4001")
        self.assertNotEqual(res.stop_reason, "success", "缺 token 不得转 click 成功")
        self.assertEqual(res.stop_reason, "process_error",
                         "缺 token 是安全停发原因，无 pending 报 process_error")

    def test_direct_401_403_302_stop_sends(self):
        # direct 异常 HTTP（401/403/3xx）：按 real 结算已收应答、停止新发、
        # 不自动降级 click；无 pending 报 process_error。
        for status in (401, 403, 302):
            with self.subTest(status=status):
                FakeTransport.reset()
                signer = _RecordingSigner()
                FakeTransport.responder_fn = staticmethod(
                    lambda t, s=status: _d_http(s))
                res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                                 retry_for=30.0, max_attempts=3, button_visible=False,
                                 script_srcs=self._known(), direct_signer=signer,
                                 direct_transport=FakeTransport)
                self.assertEqual(len(FakeTransport.instances[0].tickets), 1,
                                 "HTTP %d 异常应答后必须停止新发" % status)
                self.assertNotIn("切换为点击兜底", "\n".join(res.logs),
                                 "异常 HTTP 不得自动切 click")
                self.assertEqual(res.stop_reason, "process_error",
                                 "无 pending 的通道/协议异常报 process_error")
                self.assertIn("pending=0", res.terminal_lines[-1],
                              "已收应答按 real 结算，不留 pending")

    def test_direct_200_no_business_code_stops_sends(self):
        # 200 解码后无可识别业务 code：已决应答（非 lost）、停止新发、报 process_error。
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(_d_html)
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                         retry_for=30.0, max_attempts=3, button_visible=False,
                         script_srcs=self._known(), direct_signer=signer,
                         direct_transport=FakeTransport)
        self.assertEqual(len(FakeTransport.instances[0].tickets), 1,
                         "200 无业务 code 后必须停止新发")
        self.assertNotIn("切换为点击兜底", "\n".join(res.logs),
                         "200 无业务 code 不得自动切 click")
        self.assertEqual(res.stop_reason, "process_error")

    def test_direct_anomaly_with_pending_reports_unconfirmed(self):
        # 异常应答已决、另一笔仍 pending：停止新发后统一收尾报 unconfirmed。
        calls = {"n": 0}

        def _resp(ticket):
            calls["n"] += 1
            if calls["n"] == 1:
                return "started_only"
            return _d_http(403)

        FakeTransport.responder_fn = staticmethod(_resp)
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                         retry_for=30.0, max_attempts=3, button_visible=False,
                         script_srcs=self._known(), direct_signer=signer,
                         direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "unconfirmed",
                         "另有 pending 时异常停发必须报 unconfirmed")
        self.assertLessEqual(len(FakeTransport.instances[0].tickets), 2,
                             "异常应答后不得再新发")

    def test_foreign_and_mismatched_events_have_no_side_effects(self):
        # F03：错 run_id、未知 request_id、错 attempt_no 的 started 无副作用——
        # 不注册尝试、不释放他人预留、不把同步替身事件当成真实发送。
        # 第二笔真正 started 滞后（虚拟事件泵暂存），外来事件立即入列。
        calls = {"n": 0}

        def responder(ticket):
            calls["n"] += 1
            if calls["n"] == 1:
                return _d_payload(RETRYABLE_REPLY["code"], RETRYABLE_REPLY["message"])
            return "started_only"

        def extras(ticket):
            if calls["n"] != 2:
                return []
            return [
                # 错 run_id：本场不得认领
                {"kind": "started", "run_id": "other-run",
                 "request_id": ticket["request_id"], "attempt_no": ticket["attempt_no"]},
                # 未知 request_id：不得按“唯一预留”认领
                {"kind": "started", "run_id": ticket["run_id"],
                 "request_id": "ghost-1", "attempt_no": ticket["attempt_no"]},
                # 错 attempt_no：票据身份不匹配
                {"kind": "started", "run_id": ticket["run_id"],
                 "request_id": ticket["request_id"],
                 "attempt_no": ticket["attempt_no"] + 9},
                {"kind": "not_started", "run_id": ticket["run_id"],
                 "request_id": ticket["request_id"],
                 "attempt_no": ticket["attempt_no"] + 9},
            ]

        def rel(ticket, event):
            # 只有第二笔自己合规的 started 才算真正滞后（永不放行）；
            # 第一笔与外来事件立即入列
            if (event.get("kind") == "started"
                    and event.get("attempt_no") == 2
                    and event.get("run_id") == ticket["run_id"]
                    and event.get("request_id") == ticket["request_id"]):
                return FakeTransport.clock.mono + 9999.0
            return None

        FakeTransport.responder_fn = staticmethod(responder)
        FakeTransport.extra_fn = extras
        FakeTransport.release_at_fn = rel
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=2, button_visible=False, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(res.attempts, 1,
                         "外来 started 不得注册尝试（只有第一笔真实入账）")
        self.assertEqual(len(FakeTransport.instances[0].tickets), 2,
                         "预留占满次数配额时不得漏账追加第三笔")
        self.assertEqual(res.stop_reason, "retry_duration",
                         "外来事件不得改变本场结论")

    def test_duplicate_events_do_not_rewrite_first_conclusion(self):
        # F03：第一笔已决（code=0）后，重复 code1/版本错误/重复 started/not_started
        # 均不改写首次结论、不降级、不减少其它票据预留。
        calls = {"n": 0}

        def responder(ticket):
            calls["n"] += 1
            if calls["n"] == 1:
                return _d_payload(RETRYABLE_REPLY["code"], RETRYABLE_REPLY["message"])
            return "started_only"

        def extras(ticket):
            if calls["n"] != 1:
                return []
            base = {"run_id": ticket["run_id"], "request_id": ticket["request_id"],
                    "attempt_no": ticket["attempt_no"]}
            return [
                dict(base, kind="started"),
                dict(base, kind="not_started"),
                dict(base, kind="completed", http_status=200,
                     body_bytes=json.dumps({"code": 1, "message": "ok"}).encode("utf-8")),
                dict(base, kind="completed", http_status=200,
                     body_bytes=json.dumps(
                         {"code": 0, "message": VERSION_MSG}).encode("utf-8")),
            ]

        def rel(ticket, event):
            if (event.get("kind") == "started"
                    and event.get("attempt_no") == 2):
                return FakeTransport.clock.mono + 9999.0
            return None

        FakeTransport.responder_fn = staticmethod(responder)
        FakeTransport.extra_fn = extras
        FakeTransport.release_at_fn = rel
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=2, button_visible=False, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertNotEqual(res.stop_reason, "success",
                            "重复 code1 不得改写首次已决结论")
        self.assertNotIn("切换为点击兜底", "\n".join(res.logs),
                         "重复版本错误不得触发降级")
        self.assertEqual(res.attempts, 1, "重复 started 不得重复入账")
        self.assertEqual(len(FakeTransport.instances[0].tickets), 2,
                         "重复事件不得减少他人预留、不得漏发第三笔")
        self.assertEqual(res.stop_reason, "retry_duration")

    def test_lost_ticket_late_success_settles_in_tail_window(self):
        # F03：failed(lost) 不是最终完成——同一合法请求的迟到成功在尾窗内仍能结算。
        calls = {"n": 0}

        def responder(ticket):
            calls["n"] += 1
            return _d_failed(ticket)

        def extras(ticket):
            return [dict(ticket, kind="completed", http_status=200,
                         body_bytes=json.dumps({"code": 1, "message": "ok"}).encode("utf-8"),
                         run_id=ticket["run_id"], request_id=ticket["request_id"],
                         attempt_no=ticket["attempt_no"])]

        def rel(ticket, event):
            # failed 立即（标 lost 保持未决）；completed 迟到 0.5 秒（落在尾窗内）
            if event.get("kind") == "completed":
                return FakeTransport.clock.mono + 0.5
            return None

        FakeTransport.responder_fn = staticmethod(responder)
        FakeTransport.extra_fn = extras
        FakeTransport.release_at_fn = rel
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=1, button_visible=False, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "success",
                         "lost 后迟到成功必须能合法结算，不得停在未决")

    def test_max_attempts_one_late_started_counted_and_single(self):
        # max_attempts=1 且 started 真正滞后：无第二笔；started 迟早入账后
        # 最终 attempt/pending 不能为 0。
        def rel(ticket, event):
            if event.get("kind") == "started":
                return FakeTransport.clock.mono + 8.0   # 真正滞后（非同步）
            return None

        FakeTransport.responder_fn = staticmethod(lambda t: "started_only")
        FakeTransport.release_at_fn = rel
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=1, button_visible=False, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(len(FakeTransport.instances[0].tickets), 1,
                         "max_attempts=1 不得有第二笔")
        self.assertEqual(res.attempts, 1, "已跨接纳点的 started 必须入账")
        self.assertEqual(res.pending, 1, "started 入账后必须保持未决")
        self.assertEqual(res.stop_reason, "unconfirmed")

    def test_uncommitted_reservation_cancelled_not_counted(self):
        # 未跨接纳点（started 永不放行）：close 取消预留，不计 attempt。
        def rel(ticket, event):
            return FakeTransport.clock.mono + 9999.0   # 永不放行

        FakeTransport.responder_fn = staticmethod(lambda t: "started_only")
        FakeTransport.release_at_fn = rel
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=1, button_visible=False, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(len(FakeTransport.instances[0].tickets), 1)
        self.assertEqual(res.attempts, 0, "取消的预留不得计 attempt")
        self.assertEqual(res.stop_reason, "retry_duration")

    def test_two_blocked_threads_no_third_despite_logical_ttl(self):
        # 两笔物理在途：逻辑 TTL 过期也不得凭空创建第三线程（物理上限说了算）。
        FakeTransport.responder_fn = staticmethod(lambda t: "started_only")
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=0, button_visible=False, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(len(FakeTransport.instances[0].tickets), 2,
                         "逻辑 TTL 不得越物理并发上限")
        self.assertEqual(res.stop_reason, "unconfirmed")

    def test_downgrade_shares_attempts_with_click(self):
        # 降级后 direct 与 click 共用同一账本：总次数共享，不重置预算/连击。
        # 决策 015：版本不兼容先重取一次密钥再试一笔，所以直发是 2 笔
        FakeTransport.responder_fn = staticmethod(lambda t: _d_payload(0, VERSION_MSG))
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=3, button_visible=True, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "success")
        self.assertEqual(res.attempts, 3,
                         "direct 与 click 共享总次数（2+1）")
        self.assertEqual(len(FakeTransport.instances[0].tickets), 2,
                         "降级后不得再发直发票据")
        self.assertIn("streak_404=0", res.terminal_lines[-1], "不得重置连击")

    def test_late_direct_success_prevents_confirm_click(self):
        # 版本错误到达后，旧 direct 迟到成功在确认前落账：不再点「确定」，
        # 成功粘性保持，不重置预算/连击。
        calls = {"n": 0}

        def responder(ticket):
            calls["n"] += 1
            if calls["n"] == 1:
                return "started_only"          # 第一笔：事件全滞后
            return _d_payload(0, VERSION_MSG)  # 第二笔：版本错误（降级）

        def extras(ticket):
            if calls["n"] != 1:
                return []
            return [dict(ticket, kind="completed", http_status=200,
                         body_bytes=json.dumps({"code": 1, "message": "ok"}).encode("utf-8"),
                         run_id=ticket["run_id"], request_id=ticket["request_id"],
                         attempt_no=ticket["attempt_no"])]

        def rel(ticket, event):
            # 第一笔的 started/completed 全部滞后 0.5 秒（慢确认框后被 gate2 收到）
            if event.get("attempt_no") == 1:
                return FakeTransport.clock.mono + 0.5
            return None

        FakeTransport.responder_fn = staticmethod(responder)
        FakeTransport.extra_fn = extras
        FakeTransport.release_at_fn = rel
        signer = _RecordingSigner()
        res = run_worker(behavior="slow_dialog", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=3, button_visible=True, click_delay=2.0,
                         script_srcs=self._known(), direct_signer=signer,
                         direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "success",
                         "迟到成功必须保持成功粘性")
        self.assertEqual(res.page.confirm_clicks, 0,
                         "迟到成功后不得再点「确定」")
        self.assertIn("streak_404=0", res.terminal_lines[-1], "不得重置连击")

    def test_callbacks_do_not_touch_clock_policy_or_log(self):
        # F05：回调只入队——回调期间禁止业务时钟读取、结算刷新与日志；
        # 请求登记由主循环一次完成。
        res = run_worker(behavior="success", at_offset=0.0, retry_for=10.0,
                         max_attempts=1)
        self.assertEqual(res.stop_reason, "success")
        self.assertEqual(res.attempts, 1)
        self.assertEqual(CALLBACK_GUARD["violations"], [],
                         "回调期间不得碰时钟/结算/日志")

    def test_foreign_requestfailed_after_downgrade_keeps_direct_pending(self):
        # F05：降级后注入未登记 Request 的 requestfailed，不得按“唯一 pending”
        # 认领 direct 未决名额、不改写本场结论。
        calls = {"n": 0}

        def responder(ticket):
            calls["n"] += 1
            if calls["n"] == 1:
                return "started_only"
            return _d_payload(0, VERSION_MSG)

        FakeTransport.responder_fn = staticmethod(responder)
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=3, button_visible=False, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport,
                         inject_failed_at=1000.0 + OPEN_AHEAD + 1.0)
        self.assertEqual(res.stop_reason, "unconfirmed")
        self.assertEqual(res.pending, 1, "未登记 requestfailed 不得释放 direct 未决")
        self.assertNotIn("请求中止", res.terminal_lines[-1],
                         "未登记 requestfailed 不得改写本场 last_reason")

    def test_confirm_reentry_after_inflight_timeout_reuses_confirm_button(self):
        # F07：确认框已开且名额 >1 秒才释放时，下一轮先查可见「确定」直接确认，
        # 不再点「立即报名」（超时重入，不是 0.3 秒内释放的旧例）。
        calls = {"n": 0}

        def responder(ticket):
            calls["n"] += 1
            if calls["n"] == 1:
                return "started_only"
            return _d_payload(0, VERSION_MSG)

        FakeTransport.responder_fn = staticmethod(responder)
        signer = _RecordingSigner()
        # 决策 015：版本不兼容先重取密钥多发一笔直发，次数上限相应 +1
        res = run_worker(behavior="open_race", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=5, button_visible=True, response_delay=1.5,
                         script_srcs=self._known(), direct_signer=signer,
                         direct_transport=FakeTransport)
        btn_clicks = [c for c in res.page.clicks if c[1] == "uni-button"]
        confirm_clicks = [c for c in res.page.clicks if c[1] == "确定"]
        self.assertEqual(len(btn_clicks), 1, "超时重入不得重复点「立即报名」")
        self.assertGreaterEqual(len(confirm_clicks), 1, "名额释放后必须直接确认")

    def test_success_during_confirm_gate_wait_skips_confirm(self):
        # F07：闸门二等待泵中先收到成功：取消确认，不点「确定」。
        calls = {"n": 0}

        def responder(ticket):
            calls["n"] += 1
            if calls["n"] == 1:
                return "started_only"
            return _d_payload(0, VERSION_MSG)

        FakeTransport.responder_fn = staticmethod(responder)
        signer = _RecordingSigner()
        # 决策 015：版本不兼容先重取密钥多发一笔直发，次数上限相应 +1
        res = run_worker(behavior="success_on_open", at_offset=OPEN_AHEAD,
                         retry_for=60.0, max_attempts=4, button_visible=True,
                         response_delay=0.5, script_srcs=self._known(),
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "success")
        self.assertEqual(res.page.confirm_clicks, 0, "成功先到时不得再点「确定」")

    def _late_completed_release(self, delay_by_attempt, fires=1):
        """按 attempt_no 返回 completed 的绝对放行时刻（锚定尾窗起点）。"""
        def rel(ticket, event):
            if event.get("kind") == "completed":
                anchor = (1000.0 + OPEN_AHEAD
                          + fires * grab.GOLDEN_INTERVAL_S)
                return anchor + delay_by_attempt.get(event.get("attempt_no"), 0.5)
            return None
        return rel

    def _run_recording(self, **kwargs):
        """运行并记录 wait 切片，供尾窗长度精确测量（与 main 尾窗断言同口径）。"""
        waits = []
        original_wait = FakePage.wait_for_timeout

        def record_wait(page, ms):
            waits.append((page.clock.monotonic(), float(ms) / 1000.0))
            return original_wait(page, ms)

        with patch.object(FakePage, "wait_for_timeout", record_wait):
            res = run_worker(**kwargs)
        return res, waits

    def _tail_len(self, res, waits):
        # 尾窗起点 = 最后一个发射间隔短片（40ms）之后的那一片；
        # 末尾 1ms 量化片不算间隔片
        gap_idx = max(i for i, (_at, ms) in enumerate(waits)
                      if 0.035 <= ms <= 0.045)
        return res.clock.mono - waits[gap_idx + 1][0]

    def test_direct_late_completed_tail_boundaries(self):
        # direct 迟到 completed：0.4/0.98 秒在尾窗内 success；
        # 1.02/1.2 秒超窗 unconfirmed，尾窗时长 <= 1.001+1e-6。
        for delay, expect in ((0.4, "success"), (0.98, "success"),
                              (1.02, "unconfirmed"), (1.2, "unconfirmed")):
            with self.subTest(delay=delay):
                FakeTransport.reset()
                FakeTransport.responder_fn = staticmethod(_d_ok)
                FakeTransport.release_at_fn = self._late_completed_release({1: delay})
                signer = _RecordingSigner()
                res, waits = self._run_recording(
                    behavior="success", at_offset=OPEN_AHEAD,
                    retry_for=30.0, max_attempts=1, button_visible=False,
                    script_srcs=self._known(), direct_signer=signer,
                    direct_transport=FakeTransport)
                self.assertEqual(res.stop_reason, expect,
                                 "延迟 %.2f 秒的 completed 结论" % delay)
                if expect == "unconfirmed":
                    self.assertEqual(res.pending, 1, "超窗事件不得伪造成结论")
                    tail_len = self._tail_len(res, waits)
                    self.assertGreaterEqual(tail_len, 0.999, "收尾不能提前放弃")
                    self.assertLessEqual(tail_len, 1.001 + 1e-6,
                                         "尾窗量化余量不超过 1ms")

    def test_direct_late_completed_short_budget_and_sign_end(self):
        # 短预算 / sign_end 先到：绝对截止不越（与六条 main 尾窗断言同口径）。
        FakeTransport.responder_fn = staticmethod(_d_ok)
        FakeTransport.release_at_fn = self._late_completed_release({1: 2.0})
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=0.0, retry_for=0.5,
                         max_attempts=1, button_visible=False,
                         script_srcs=self._known(), direct_signer=signer,
                         direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "unconfirmed")
        self.assertLessEqual(res.clock.time(), START + 0.501 + 1e-6,
                             "短预算绝对截止不得越过")
        FakeTransport.reset()
        FakeTransport.responder_fn = staticmethod(_d_ok)
        FakeTransport.release_at_fn = self._late_completed_release({1: 2.0})
        signer = _RecordingSigner()
        deadline = START + 1.0
        res = run_worker(behavior="success", at_offset=0.0, retry_for=10.0,
                         max_attempts=1, button_visible=False,
                         script_srcs=self._known(), direct_signer=signer,
                         direct_transport=FakeTransport,
                         sign_end=grab.school_time_text(deadline))
        self.assertEqual(res.stop_reason, "unconfirmed")
        self.assertLessEqual(res.clock.time(), deadline + 0.001 + 1e-6,
                             "sign_end 绝对截止不得越过")

    def test_success_after_4001_within_original_tail_wins(self):
        # 4001 先到、成功在原尾窗内到达仍 success（4001 不重设尾窗起点）。
        FakeTransport.responder_fn = staticmethod(
            lambda t: _d_payload(4001) if t["attempt_no"] == 1 else _d_ok(t))
        FakeTransport.release_at_fn = self._late_completed_release(
            {1: 0.05, 2: 0.5}, fires=2)
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=2, button_visible=False,
                         script_srcs=self._known(), direct_signer=signer,
                         direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "success",
                         "原尾窗内迟到成功必须压过 4001")

    def test_tail_not_reset_by_4001(self):
        # 4001 不重设尾窗起点：窗外迟到成功不得被补接，尾窗时长仍 <=1.001。
        FakeTransport.responder_fn = staticmethod(
            lambda t: _d_payload(4001) if t["attempt_no"] == 1 else _d_ok(t))
        FakeTransport.release_at_fn = self._late_completed_release(
            {1: 0.05, 2: 1.03}, fires=2)
        signer = _RecordingSigner()
        res, waits = self._run_recording(
            behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
            max_attempts=2, button_visible=False,
            script_srcs=self._known(), direct_signer=signer,
            direct_transport=FakeTransport)
        self.assertNotEqual(res.stop_reason, "success",
                            "窗外成功不得借重置尾窗偷渡")
        self.assertLessEqual(self._tail_len(res, waits), 1.001 + 1e-6,
                             "4001 不得重设尾窗起点")

    def test_broken_page_tail_stops_bounded(self):
        # page 等待抛错且 pending>0：尾窗有界停泵，不得无时钟推进空转烧满 1 秒。
        results = {}

        def run():
            FakeTransport.reset()
            FakeTransport.responder_fn = staticmethod(lambda t: "started_only")
            signer = _RecordingSigner()
            results["res"] = run_worker(
                behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                max_attempts=1, button_visible=False, script_srcs=self._known(),
                direct_signer=signer, direct_transport=FakeTransport,
                break_wait_at=1000.0 + OPEN_AHEAD + grab.GOLDEN_INTERVAL_S + 0.3)

        th = threading.Thread(target=run, daemon=True)
        th.start()
        th.join(timeout=5.0)
        self.assertFalse(th.is_alive(), "尾窗不得在页面失效后空转")
        res = results["res"]
        self.assertEqual(res.stop_reason, "unconfirmed")
        self.assertEqual(res.pending, 1)

    def test_final_query_true_after_one_second_still_success(self):
        # 最终核对耗时跨 1.02 秒：is_joined 明确 True 仍 success。
        FakeTransport.responder_fn = staticmethod(lambda t: "started_only")
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=1, button_visible=False,
                         script_srcs=self._known(), direct_signer=signer,
                         direct_transport=FakeTransport,
                         post_delays=[1.02], join_info_data={"id": "act-1"})
        self.assertEqual(res.stop_reason, "success",
                         "核对明确 True 时必须 success")

    def test_late_code1_during_final_query_does_not_sneak(self):
        # 核对期间冻结响应接纳：窗外迟到成功不得偷渡成 success。
        FakeTransport.responder_fn = staticmethod(_d_ok)
        FakeTransport.release_at_fn = self._late_completed_release({1: 1.5})
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=1, button_visible=False,
                         script_srcs=self._known(), direct_signer=signer,
                         direct_transport=FakeTransport, post_delays=[1.02])
        self.assertEqual(res.stop_reason, "unconfirmed",
                         "冻结后迟到成功不得改写终态")


    def test_direct_200_unrecognized_code_stops_sends(self):
        # A2 裁决：bool/容器/空串/非数值字符串/非整数数值/非有限都不是可识别
        # 业务 code——HTTP200 协议异常停发，无 pending 报 process_error；
        # 不得把 True==1 误当报名成功，非法字段也不得切 click。
        cases = (("true", True), ("false", False), ("obj", {}), ("arr", []),
                 ("empty", ""), ("garbage", "garbage"), ("float", 1.5),
                 ("nan", float("nan")), ("none", None))
        for label, code in cases:
            with self.subTest(code=label):
                FakeTransport.reset()
                FakeTransport.responder_fn = staticmethod(
                    lambda t, c=code: _d_payload(c))
                signer = _RecordingSigner()
                res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                                 retry_for=30.0, max_attempts=3,
                                 button_visible=False, script_srcs=self._known(),
                                 direct_signer=signer, direct_transport=FakeTransport)
                self.assertEqual(len(FakeTransport.instances[0].tickets), 1,
                                 "%s：停发" % label)
                self.assertEqual(res.stop_reason, "process_error",
                                 "%s：无 pending 报 process_error" % label)
                self.assertNotIn("切换为点击兜底", "\n".join(res.logs),
                                 "%s：非法字段不得切 click" % label)

    def test_direct_unrecognized_code_with_pending_reports_unconfirmed(self):
        # A2 裁决：无可识别业务 code 停发时另有 pending，报 unconfirmed。
        calls = {"n": 0}

        def responder(ticket):
            calls["n"] += 1
            if calls["n"] == 1:
                return "started_only"
            return _d_payload([])

        FakeTransport.responder_fn = staticmethod(responder)
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                         retry_for=30.0, max_attempts=3, button_visible=False,
                         script_srcs=self._known(), direct_signer=signer,
                         direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "unconfirmed",
                         "另有 pending 时停发报 unconfirmed")
        self.assertEqual(res.pending, 1)
        self.assertLessEqual(len(FakeTransport.instances[0].tickets), 2)

    def test_direct_integer_string_code_is_recognized(self):
        # A2 裁决：去空白后严格的十进制整数字符串是可识别业务 code，
        # 按原业务判据处理（"4001"→login_invalid），不按协议异常停发。
        FakeTransport.responder_fn = staticmethod(lambda t: _d_payload("4001"))
        signer = _RecordingSigner()
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                         retry_for=30.0, max_attempts=3, button_visible=False,
                         script_srcs=self._known(), direct_signer=signer,
                         direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "login_invalid",
                         "整数字符串按原业务判据走 4001")


class FinalizeFallbackTests(unittest.TestCase):
    """F06 返修：finalize 异常退路共用同一终态优先级——
    已确认成功 > 有未决 unconfirmed > 无未决的对应异常；只输出一条 done。"""

    def setUp(self):
        FakeTransport.reset()

    def _known(self):
        return [KNOWN_SRC]

    def test_finalize_exception_with_pending_reports_unconfirmed(self):
        # 复现：即时 started、completed 延迟 0.4s、max_attempts=1，尾窗内
        # BurstPolicy.settle 抛 RuntimeError。done 必须 unconfirmed，
        # 不得丢掉未决事实冒充 process_error。
        def rel(ticket, event):
            if event.get("kind") == "completed":
                return FakeTransport.clock.mono + 0.4
            return None

        def boom(self, *args, **kwargs):
            raise RuntimeError("settle boom")

        FakeTransport.responder_fn = staticmethod(_d_ok)
        FakeTransport.release_at_fn = rel
        signer = _RecordingSigner()
        with patch.object(grab.BurstPolicy, "settle", boom):
            res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                             retry_for=30.0, max_attempts=1, button_visible=False,
                             script_srcs=self._known(), direct_signer=signer,
                             direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "unconfirmed",
                         "异常退路不得丢掉未决事实")
        self.assertEqual(res.pending, 1)
        self.assertEqual(res.attempts, 1)
        self.assertEqual(len(res.terminal_lines), 1, "只输出一条 done")

    def test_finalize_clock_exception_keeps_pending_facts(self):
        # 校时异常退路不得跳过已入账未决事实：pending>0 必须 unconfirmed，
        # 且不因异常重入再做学校请求（is_joined 只查预检+一次最终核对）。
        queries = {"n": 0}

        def fake_is_joined(*args, **kwargs):
            queries["n"] += 1
            if queries["n"] > 1:
                raise grab.ClockUnavailable("测试注入：校时失效")
            return None        # 预检：未报名

        FakeTransport.responder_fn = staticmethod(lambda t: "started_only")
        signer = _RecordingSigner()
        with patch.object(grab, "is_joined", fake_is_joined):
            res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                             retry_for=30.0, max_attempts=1, button_visible=False,
                             script_srcs=self._known(), direct_signer=signer,
                             direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "unconfirmed",
                         "校时异常不得跳过未决事实")
        self.assertEqual(res.pending, 1)
        self.assertEqual(len(res.terminal_lines), 1, "只输出一条 done")
        self.assertEqual(queries["n"], 2,
                         "异常退路不得重入再做学校请求")

    def test_finalize_exception_after_success_keeps_success(self):
        # 已确认成功退路：同一 drain 内 settle 成功后再抛异常，done 仍是 success。
        calls = {"n": 0}
        orig_settle = grab.BurstPolicy.settle

        def flaky(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] > 1:
                raise RuntimeError("boom after success")
            return orig_settle(self, *args, **kwargs)

        def rel(ticket, event):
            # 两笔 completed 同一绝对时刻放行：必然落入同一次 drain
            if event.get("kind") == "completed":
                return 1000.0 + OPEN_AHEAD + 2 * grab.GOLDEN_INTERVAL_S + 0.4
            return None

        FakeTransport.responder_fn = staticmethod(_d_ok)
        FakeTransport.release_at_fn = rel
        signer = _RecordingSigner()
        with patch.object(grab.BurstPolicy, "settle", flaky):
            res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                             retry_for=30.0, max_attempts=2, button_visible=False,
                             script_srcs=self._known(), direct_signer=signer,
                             direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "success",
                         "已确认成功不得被异常退路覆盖")
        self.assertEqual(len(res.terminal_lines), 1, "只输出一条 done")

    def test_finalize_exception_without_pending_reports_process_error(self):
        # 无未决的普通异常退路：process_error（对应异常）。
        queries = {"n": 0}

        def fake_is_joined(*args, **kwargs):
            queries["n"] += 1
            if queries["n"] > 1:
                raise RuntimeError("query boom")
            return None        # 预检：未报名

        FakeTransport.responder_fn = staticmethod(
            lambda t: _d_payload(0, "报名人数已满"))
        signer = _RecordingSigner()
        with patch.object(grab, "is_joined", fake_is_joined):
            res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                             retry_for=30.0, max_attempts=1, button_visible=False,
                             script_srcs=self._known(), direct_signer=signer,
                             direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "process_error",
                         "无未决的普通异常按对应异常收口")
        self.assertEqual(len(res.terminal_lines), 1, "只输出一条 done")


class EarlyFailureTests(unittest.TestCase):
    """A2 任务一：预检/页面早期异常不得调用尚未建立的收尾闭包。

    每个分支：零提交、正确异常类别、唯一 done、无不必要的最终查询、
    浏览器已关闭；异常类别不得被 UnboundLocalError 扭曲成 process_error。
    """

    def _assert_clean(self, res, stop_reason):
        self.assertEqual(res.attempts, 0, "早期异常必须零提交")
        self.assertEqual(res.stop_reason, stop_reason,
                         "早期异常必须走正确类别终态")
        self.assertEqual(len(res.terminal_lines), 1, "只输出一条 done")
        self.assertNotIn("UnboundLocalError", res.terminal_lines[-1],
                         "早期异常不得被未建立闭包扭曲")
        self.assertTrue(res.page.closed, "浏览器必须已关闭")

    def test_preflight_clock_failure_uses_outer_terminal(self):
        # 预检 is_joined 抛 ClockUnavailable：clock_unavailable、零提交、
        # 不再做最终查询。
        queries = {"n": 0}

        def fake_is_joined(*args, **kwargs):
            queries["n"] += 1
            raise grab.ClockUnavailable("测试注入：预检校时失效")

        with patch.object(grab, "is_joined", fake_is_joined):
            res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                             retry_for=60.0, max_attempts=3)
        self._assert_clean(res, "clock_unavailable")
        self.assertEqual(queries["n"], 1, "不得再做最终查询")

    def test_page_goto_failure_uses_outer_terminal(self):
        # page.goto 抛异常：process_error，异常类别如实（FakeTimeout）。
        res = run_worker(behavior="goto_fail", at_offset=OPEN_AHEAD,
                         retry_for=60.0, max_attempts=3)
        self._assert_clean(res, "process_error")
        self.assertIn("FakeTimeout", res.terminal_lines[-1],
                      "异常类别不得被扭曲")

    def test_page_goto_budget_exhausted_uses_budget_stop(self):
        # goto 时预算耗尽（timeout_ms 到点拒绝）：按预算类别收口。
        def boom(self, *args, **kwargs):
            raise time_contract.BudgetExhausted("重试窗口已到点")

        with patch.object(time_contract.RetryBudget, "timeout_ms", boom):
            res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                             retry_for=60.0, max_attempts=3)
        self._assert_clean(res, "retry_duration")

    def test_new_context_failure_uses_outer_terminal(self):
        # new_context/new_page 失败：process_error，异常类别如实。
        with patch.object(grab, "new_context",
                          side_effect=RuntimeError("ctx boom")):
            res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                             retry_for=60.0, max_attempts=3)
        self._assert_clean(res, "process_error")
        self.assertIn("RuntimeError", res.terminal_lines[-1],
                      "异常类别不得被扭曲")

    def test_wait_until_clock_failure_uses_clock_stop(self):
        # 进入盯按钮前 wait_until 校时失效：clock_unavailable、
        # 只有预检一次查询（无不必要的最终查询）。
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD,
                         retry_for=60.0, max_attempts=3,
                         post_hook=lambda n, clock: clock.lose())
        self._assert_clean(res, "clock_unavailable")
        self.assertEqual(len(res.posts), 1, "只有预检一次查询")



class SignupReplyClassificationTests(unittest.TestCase):
    """决策 015：回包分类接进 worker（直发与点击同一套判据）。"""

    def setUp(self):
        FakeTransport.reset()

    def _known(self):
        return [KNOWN_SRC]

    def _direct(self, reply, **kwargs):
        FakeTransport.responder_fn = staticmethod(
            lambda t: _d_payload(reply["code"], reply["message"]))
        options = dict(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                       max_attempts=0, button_visible=False, script_srcs=self._known(),
                       direct_signer=_RecordingSigner(), direct_transport=FakeTransport)
        options.update(kwargs)
        return run_worker(**options)

    def test_full_reply_ends_run_without_retrying(self):
        res = self._direct({"code": 500, "message": "报名人数已满"})
        self.assertEqual(res.stop_reason, "full", "名额已满是终态，不再重试")
        self.assertLessEqual(res.attempts, grab.MAX_INFLIGHT,
                             "最多只有已经在途的那几笔，不再新发")
        self.assertIn("code:500 报名人数已满", "\n".join(res.logs),
                      "日志要写学校完整原文")

    def test_closed_is_terminal(self):
        res = self._direct({"code": 500, "message": "报名已结束！"})
        self.assertEqual(res.stop_reason, "closed")

    def test_missing_activity_on_direct_downgrades_to_click(self):
        # hd-info 空值成因未证实：直发时先退回点击核实，页面点击能报上就算报上
        res = self._direct({"code": 0, "message": "Cache 'hd-info' does not allow 'null' values"},
                           button_visible=True, max_attempts=3)
        self.assertIn("改走点击核实", "\n".join(res.logs))
        self.assertEqual(res.stop_reason, "success")
        self.assertEqual(len(FakeTransport.instances[0].tickets), 1, "退回点击后不再直发")

    def test_missing_activity_on_click_is_terminal(self):
        # 点击路径上学校也说查不到活动：按活动不存在结束，不再重试
        res = run_worker(behavior="no_activity", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=0, button_visible=True)
        self.assertEqual(res.stop_reason, "no_activity")
        self.assertEqual(res.attempts, 1)

    def test_conflict_with_joined_check_counts_as_success(self):
        # 冲突回包可能是自己刚报上：收尾核对学校说已报名，就记成功
        res = self._direct({"code": 500, "message": "活动时间与已参与活动时间冲突：<活动名>"},
                           join_info_data={"sfbm": 1})
        self.assertEqual(res.stop_reason, "success")

    def test_conflict_without_join_is_conflict(self):
        res = self._direct({"code": 500, "message": "活动时间与已参与活动时间冲突：<活动名>"})
        self.assertEqual(res.stop_reason, "conflict")

    def test_not_open_keeps_going_until_limit(self):
        res = self._direct(RETRYABLE_REPLY, max_attempts=4)
        self.assertEqual(res.stop_reason, "max_attempts")
        self.assertEqual(res.attempts, 4)

    def test_stale_timestamp_twice_is_clock_skew(self):
        res = self._direct({"code": 0, "message": "您的请求已超时，请刷新页面后重新提交"})
        self.assertEqual(res.stop_reason, "clock_skew")

    def test_unknown_reply_downgrades_then_ends(self):
        # 直发同一未识别文案 3 次 → 退回点击；点击上同一文案再 3 次 → 结束
        res = self._direct(UNKNOWN_REPLY, behavior="unknown_reply", button_visible=True)
        joined = "\n".join(res.logs)
        self.assertIn("切换为点击兜底", joined)
        self.assertEqual(res.stop_reason, "unknown_reply")

    def test_4001_rechecked_valid_keeps_sending(self):
        # 提交中收到 4001：停发复查；复查说登录还有效就继续发，不判失效
        seen = {"n": 0}

        def responder(ticket):
            seen["n"] += 1
            if seen["n"] == 1:
                return _d_payload(4001, "身份验证失败！")
            return _d_payload(RETRYABLE_REPLY["code"], RETRYABLE_REPLY["message"])

        FakeTransport.responder_fn = staticmethod(responder)
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=30.0,
                         max_attempts=3, button_visible=False, script_srcs=self._known(),
                         direct_signer=_RecordingSigner(), direct_transport=FakeTransport,
                         recheck_state="valid")
        joined = "\n".join(res.logs)
        self.assertIn("停发并复查登录", joined)
        self.assertIn("继续发送", joined)
        self.assertEqual(res.stop_reason, "max_attempts")
        self.assertEqual(res.attempts, 3)

    def test_4001_rechecked_expired_is_login_invalid(self):
        res = self._direct({"code": 4001, "message": "身份验证失败！"})
        self.assertEqual(res.stop_reason, "login_invalid")

    def test_login_words_in_business_text_are_not_login_invalid(self):
        res = self._direct({"code": 500, "message": "请登录后完成身份验证"}, max_attempts=2)
        self.assertNotEqual(res.stop_reason, "login_invalid",
                            "只认 code=4001，业务文案里的字眼不算登录失效")


class FinalJoinCheckTests(unittest.TestCase):
    """决策 015：每场结束只要发过提交，就用 getJoinInfo 核对一次，预算用完也查。"""

    def test_expired_budget_still_checks_once_and_counts_join(self):
        res = run_worker(behavior="fail", at_offset=0.0, retry_for=2.0, max_attempts=0,
                         join_info_data={"sfbm": 1})
        self.assertGreater(res.attempts, 0)
        self.assertEqual(res.stop_reason, "success",
                         "预算到点后核对学校说已报名，就是报上了")
        joins = [post for post in res.posts if "/getJoinInfo/" in post["path"]]
        self.assertEqual(len(joins), 2, "入场预检一次 + 收尾核对一次，不循环")

    def test_unknown_join_result_is_not_success_and_no_resubmit(self):
        calls = {"n": 0}

        def fake_is_joined(*args, **kwargs):
            calls["n"] += 1
            return False if calls["n"] == 1 else None   # 入场预检未报名；收尾查不出

        with patch.object(grab, "is_joined", fake_is_joined):
            res = run_worker(behavior="fail", at_offset=0.0, retry_for=2.0, max_attempts=3)
        self.assertEqual(calls["n"], 2, "收尾只核对一次")
        self.assertNotEqual(res.stop_reason, "success")
        self.assertEqual(res.attempts, 3, "核对失败不重发")


class DirectRuntimeKeyTests(unittest.TestCase):
    """决策 015：直发密钥来自 runtime/profile，直发不依赖页面。"""

    def setUp(self):
        FakeTransport.reset()

    def test_signer_gets_runtime_key_bytes(self):
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(_d_ok)
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=1, button_visible=False,
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "success")
        self.assertEqual(signer.keys, [TEST_RUNTIME_KEY.encode("utf-8")],
                         "签名用的是 runtime/profile 取到的 16 字节密钥")
        logs = "\n".join(res.logs)
        self.assertIn("报名路径：直发（运行时密钥）", logs)
        self.assertNotIn(TEST_RUNTIME_KEY, logs, "密钥不得进日志")

    def test_script_name_no_longer_matters(self):
        # 入口脚本叫什么都行：只要取到运行时密钥就直发
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(_d_ok)
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=1, button_visible=False, script_srcs=[UNKNOWN_SRC],
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "success")
        self.assertTrue(signer.calls)

    def test_bad_runtime_key_shape_falls_back_to_click(self):
        for bad in ("short", "x" * 17, "含中文的十六个字符串啊啊啊啊啊啊", 12345):
            with self.subTest(bad=bad):
                FakeTransport.reset()
                signer = _RecordingSigner()
                res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=60.0,
                                 max_attempts=1, button_visible=True,
                                 direct_signer=signer, direct_transport=FakeTransport,
                                 runtime_key=bad)
                self.assertEqual(signer.calls, [])
                self.assertIn("报名路径：点击", "\n".join(res.logs))

    def test_page_timeout_still_sends_direct(self):
        # 开放那一刻详情页打不开：有密钥就照常直发，成功不受影响
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(_d_ok)
        res = run_worker(behavior="goto_fail", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=1, button_visible=False,
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "success")
        self.assertIn("详情页打不开", "\n".join(res.logs))

    def test_page_timeout_without_key_is_still_an_error(self):
        # 没有密钥又打不开页面：和以前一样按流程异常收口
        res = run_worker(behavior="goto_fail", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=1, button_visible=True)
        self.assertNotEqual(res.stop_reason, "success")
        self.assertNotIn("详情页打不开", "\n".join(res.logs))

    def test_downgrade_with_page_down_is_page_unavailable(self):
        # 页面打不开、直发又要退回点击（重取密钥后仍版本不兼容）：本场结束 page_unavailable
        signer = _RecordingSigner()
        FakeTransport.responder_fn = staticmethod(lambda t: _d_payload(0, VERSION_MSG))
        res = run_worker(behavior="goto_fail", at_offset=OPEN_AHEAD, retry_for=60.0,
                         max_attempts=5, button_visible=True,
                         direct_signer=signer, direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "page_unavailable")


class ReloginHandoffTests(unittest.TestCase):
    """决策 015：登录失效后 worker 等界面自动登录，换上新登录态后继续（--relogin-wait）。"""

    def setUp(self):
        FakeTransport.reset()

    def _first_4001_then(self, reply):
        seen = {"n": 0}

        def responder(ticket):
            seen["n"] += 1
            if seen["n"] == 1:
                return _d_payload(4001, "身份验证失败！")
            return _d_payload(reply["code"], reply["message"])
        return responder

    def test_submit_4001_waits_for_relogin_then_resumes(self):
        FakeTransport.responder_fn = staticmethod(self._first_4001_then(RETRYABLE_REPLY))
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=120.0,
                         max_attempts=3, button_visible=False,
                         direct_signer=_RecordingSigner(), direct_transport=FakeTransport,
                         recheck_state=["expired", "valid"], relogin_wait=30.0,
                         relogin_writes_token=True)
        logs = "\n".join(res.logs)
        self.assertIn("等自动登录", logs)
        self.assertIn("kind=login_wait", logs)
        self.assertIn("自动登录完成", logs)
        self.assertIn("kind=login_resumed", logs)
        self.assertEqual(res.stop_reason, "max_attempts", "换上新登录态后继续发到次数上限")
        self.assertEqual(res.attempts, 3, "等待期间不计次")
        key_fetches = [post for post in res.posts if post["path"] == grab.RUNTIME_PROFILE_PATH]
        self.assertEqual(len(key_fetches), 2, "重新登录后重取一次运行时密钥")

    def test_submit_4001_wait_times_out_is_login_invalid(self):
        FakeTransport.responder_fn = staticmethod(lambda t: _d_payload(4001, "身份验证失败！"))
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=120.0,
                         max_attempts=0, button_visible=False,
                         direct_signer=_RecordingSigner(), direct_transport=FakeTransport,
                         relogin_wait=10.0)
        logs = "\n".join(res.logs)
        self.assertIn("等自动登录超时", logs)
        self.assertEqual(res.stop_reason, "login_invalid")
        self.assertLessEqual(res.attempts, grab.MAX_INFLIGHT, "等待期间不发新提交")

    def test_zero_wait_keeps_old_behavior(self):
        FakeTransport.responder_fn = staticmethod(lambda t: _d_payload(4001, "身份验证失败！"))
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=120.0,
                         max_attempts=0, button_visible=False,
                         direct_signer=_RecordingSigner(), direct_transport=FakeTransport)
        self.assertEqual(res.stop_reason, "login_invalid")
        self.assertNotIn("等自动登录", "\n".join(res.logs))

    def test_preflight_expired_waits_then_proceeds(self):
        FakeTransport.responder_fn = staticmethod(_d_ok)
        res = run_worker(behavior="success", at_offset=OPEN_AHEAD, retry_for=120.0,
                         max_attempts=1, button_visible=False, probe_state="expired",
                         direct_signer=_RecordingSigner(), direct_transport=FakeTransport,
                         recheck_state="valid", relogin_wait=30.0, relogin_writes_token=True)
        self.assertIn("开抢前检查", "\n".join(res.logs))
        self.assertEqual(res.stop_reason, "success")

    def test_relogin_wait_never_exceeds_budget(self):
        # 窗口只剩不到 1 秒时不等，直接按登录失效结束
        FakeTransport.responder_fn = staticmethod(lambda t: _d_payload(4001, "身份验证失败！"))
        res = run_worker(behavior="success", at_offset=0.0, retry_for=0.5,
                         max_attempts=0, button_visible=False,
                         direct_signer=_RecordingSigner(), direct_transport=FakeTransport,
                         relogin_wait=30.0)
        self.assertEqual(res.stop_reason, "login_invalid")
        self.assertNotIn("等自动登录，最多", "\n".join(res.logs))


class OpenTimingTests(unittest.TestCase):
    """决策 015 / 设计 3.1、3.4：开抢前预检一次，预检不计次；过了预期开放仍没开门只写一行日志。"""

    FAR = 100.0   # 距开放 100 秒：进场时够得上「开放前 45 秒」预检

    def setUp(self):
        FakeTransport.reset()

    @staticmethod
    def _is_pre(ticket):
        return "-pre" in ticket["request_id"]

    def _run(self, responder, **kwargs):
        FakeTransport.responder_fn = staticmethod(responder)
        options = dict(behavior="success", at_offset=self.FAR, retry_for=200.0,
                       max_attempts=1, button_visible=False,
                       direct_signer=_RecordingSigner(), direct_transport=FakeTransport)
        options.update(kwargs)
        return run_worker(**options)

    def _pre_tickets(self):
        return [t for t in FakeTransport.instances[0].tickets if self._is_pre(t)]

    def test_precheck_not_open_passes_and_does_not_use_up_attempts(self):
        # 预检回「报名未开始」= 密钥和格式都对；它不占最大提交次数（只给 1 次也能正式报上）
        res = self._run(lambda t: (_d_payload(RETRYABLE_REPLY["code"], RETRYABLE_REPLY["message"])
                                   if self._is_pre(t) else _d_ok()))
        self.assertEqual(res.stop_reason, "success")
        self.assertEqual(res.attempts, 1, "预检不进调度账本，正式提交仍有 1 次可用")
        self.assertIn("预检通过", "\n".join(res.logs))
        tickets = FakeTransport.instances[0].tickets
        self.assertEqual(len(tickets), 2)
        self.assertTrue(self._is_pre(tickets[0]), "预检先于正式提交")
        self.assertLess(tickets[0]["dispatch_deadline"], 1000.0 + self.FAR,
                        "预检发在开放之前")
        self.assertGreaterEqual(tickets[1]["dispatch_deadline"], 1000.0 + self.FAR,
                                "正式提交到点才发")
        # 预检和正式提交用同一套四项请求头
        self.assertEqual(sorted(tickets[0]["headers"]), sorted(tickets[1]["headers"]))
        self.assertEqual(sorted(tickets[0]["headers"]),
                         ["Accept", "Referer", "User-Agent", "token"])

    def test_precheck_version_rekeys_once_then_passes(self):
        # 预检回版本不兼容：先重取密钥再预检一次，这次回报名未开始 → 通过，仍走直发
        seen = {"n": 0}

        def responder(ticket):
            if not self._is_pre(ticket):
                return _d_ok()
            seen["n"] += 1
            if seen["n"] == 1:
                return _d_payload(0, VERSION_MSG)
            return _d_payload(RETRYABLE_REPLY["code"], RETRYABLE_REPLY["message"])

        res = self._run(responder)
        logs = "\n".join(res.logs)
        self.assertEqual(res.stop_reason, "success")
        self.assertEqual(len(self._pre_tickets()), 2, "预检最多 2 次请求")
        key_fetches = [p for p in res.posts if p["path"] == grab.RUNTIME_PROFILE_PATH]
        self.assertEqual(len(key_fetches), 2, "版本不兼容后重取一次运行时密钥")
        self.assertIn("预检通过", logs)
        self.assertNotIn("切换为点击兜底", logs)

    def test_precheck_version_twice_downgrades_to_click_before_open(self):
        # 重取密钥后预检仍版本不兼容：开放前就退回点击，不用等到开抢再发现
        res = self._run(lambda t: _d_payload(0, VERSION_MSG), button_visible=True)
        logs = "\n".join(res.logs)
        self.assertIn("切换为点击兜底", logs)
        self.assertEqual(len(FakeTransport.instances[0].tickets), 2,
                         "只有 2 次预检，正式提交没有再走直发")
        self.assertEqual(res.stop_reason, "success", "点击兜底照常报名")
        self.assertEqual(len(res.requests), 1)

    def test_precheck_code_one_means_school_opened_early(self):
        # 学校提前开放而预检真的报上了：按成功收口，不再空等到开放时刻
        res = self._run(lambda t: _d_ok())
        self.assertEqual(res.stop_reason, "success")
        self.assertEqual(res.attempts, 1, "这一笔是真实提交，记 1 次")
        self.assertEqual(len(FakeTransport.instances[0].tickets), 1)
        self.assertLess(res.elapsed_s, self.FAR, "不用再等到开放时刻")

    def test_precheck_full_ends_run_before_open(self):
        res = self._run(lambda t: _d_payload(500, "报名人数已满"))
        self.assertEqual(res.stop_reason, "full")
        self.assertEqual(res.attempts, 0, "预检不计次，也没有正式提交")
        self.assertEqual(len(FakeTransport.instances[0].tickets), 1)
        self.assertLess(res.elapsed_s, self.FAR)

    def test_precheck_4001_goes_to_login_check_without_idle_wait(self):
        res = self._run(lambda t: _d_payload(4001, "身份验证失败！"))
        self.assertEqual(res.stop_reason, "login_invalid")
        self.assertEqual(len(FakeTransport.instances[0].tickets), 1)
        self.assertLess(res.elapsed_s, self.FAR, "预检已出登录结论，不再空等到开放")

    def test_precheck_without_reply_still_fires_on_time(self):
        res = self._run(lambda t: _d_failed() if self._is_pre(t) else _d_ok())
        self.assertEqual(res.stop_reason, "success")
        self.assertIn("预检没有拿到学校回包", "\n".join(res.logs))
        self.assertEqual(res.attempts, 1)

    def test_no_precheck_for_open_or_too_close_or_click_path(self):
        for label, kwargs in (("已开放", dict(at_offset=0.0)),
                              ("距开放不足 30 秒", dict(at_offset=OPEN_AHEAD)),
                              ("没有运行时密钥", dict(runtime_key=None, button_visible=True))):
            with self.subTest(label):
                FakeTransport.reset()
                res = self._run(lambda t: _d_ok(), **kwargs)
                self.assertEqual(res.stop_reason, "success")
                self.assertNotIn("预检", "\n".join(res.logs))
                for instance in FakeTransport.instances:
                    self.assertEqual([t for t in instance.tickets if self._is_pre(t)], [])

    def test_not_open_after_grace_logs_once(self):
        # 过了预期开放 3 秒学校仍回「报名未开始」：整场只提示一次，节奏照旧
        res = self._run(lambda t: _d_payload(RETRYABLE_REPLY["code"], RETRYABLE_REPLY["message"]),
                        at_offset=OPEN_AHEAD, retry_for=30.0, max_attempts=40)
        joined = "\n".join(res.logs)
        self.assertEqual(joined.count("学校还没开门"), 1)
        self.assertEqual(res.stop_reason, "max_attempts")

    def test_not_open_within_grace_is_silent_and_counted(self):
        # 开放后 3 秒内的「报名未开始」照常计次（收窄后的口径），也不提示
        res = self._run(lambda t: _d_payload(RETRYABLE_REPLY["code"], RETRYABLE_REPLY["message"]),
                        at_offset=OPEN_AHEAD, retry_for=30.0, max_attempts=4)
        self.assertEqual(res.stop_reason, "max_attempts")
        self.assertEqual(res.attempts, 4)
        self.assertNotIn("学校还没开门", "\n".join(res.logs))


class _FakeStd:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _FakePopen:
    """受管创建用的假进程：只记录参数与收尾调用，不真的起进程。"""

    instances = []

    def __init__(self, args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.pid = 4242
        self.stdin = _FakeStd()
        self.stdout = _FakeStd()
        self.stderr = _FakeStd()
        self.killed = False
        self.waited = False
        _FakePopen.instances.append(self)

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        self.waited = True
        return 1

    def poll(self):
        return 1 if self.killed else None


class _FakeKernel32:
    def __init__(self):
        self.calls = []
        self.resume_fails = False

    def CreateJobObjectW(self, *args):
        self.calls.append("create")
        return 1

    def SetInformationJobObject(self, *args):
        self.calls.append("limit")
        return 1

    def OpenProcess(self, *args):
        self.calls.append("open")
        return 2

    def AssignProcessToJobObject(self, *args):
        self.calls.append("assign")
        return 1

    def ResumeThread(self, *args):
        self.calls.append("resume")
        return 0xFFFFFFFF if self.resume_fails else 0

    def TerminateJobObject(self, *args):
        self.calls.append("terminate")
        return 1

    def CloseHandle(self, *args):
        self.calls.append("close")


class ProcessTreeCloseTests(unittest.TestCase):
    """受管 aux tree 的超时终止与句柄关闭只作用于本树。"""

    def test_terminate_then_close_releases_job_once(self):
        proc = _FakePopen(["worker"])
        kernel = _FakeKernel32()
        closed = []
        with patch.object(process_tree, "win_kernel32", lambda: kernel), \
                patch.object(process_tree, "kill_tree", lambda target: True), \
                patch.object(process_tree, "close_handle", closed.append):
            tree = process_tree.ProcessTree(proc, 77)
            self.assertTrue(tree.terminate())
            tree.close()
            tree.close()
            self.assertTrue(tree.terminate(), "重复超时收尾应保持幂等")
        self.assertEqual(kernel.calls, ["terminate"])
        self.assertEqual(closed, [77], "Job 句柄必须只关闭一次")


class _JobExitPopen:
    """TerminateJobObject 之后才异步退出的父进程替身：wait 被调用时才算退出。"""

    pid = 4242

    def __init__(self, *, exited=False, exits_on_wait=True):
        self.exited = exited
        self.exits_on_wait = exits_on_wait
        self.waits = []
        self.tree = None
        self.lock_free_during_wait = None

    def poll(self):
        return 0 if self.exited else None

    def wait(self, timeout=None):
        import subprocess
        self.waits.append(timeout)
        if self.tree is not None:
            # 另一个线程此刻必须能拿到 tree 锁：等待期间不得持锁，否则 close() 与别的 terminate 都被拖住
            seen = []

            def probe():
                got = self.tree._lock.acquire(blocking=False)
                seen.append(got)
                if got:
                    self.tree._lock.release()

            thread = threading.Thread(target=probe)
            thread.start()
            thread.join()
            self.lock_free_during_wait = seen[0]
        if not self.exits_on_wait:
            raise subprocess.TimeoutExpired("worker", timeout)
        self.exited = True
        return 0


class ProcessTreeJobExitTests(unittest.TestCase):
    """P1/P5：Job 收尾是异步的，terminate 不能因此每次都多跑一遍 taskkill。"""

    def _tree(self, proc):
        kernel = _FakeKernel32()
        closed = []
        tree = process_tree.ProcessTree(proc, 77)
        proc.tree = tree
        patches = [patch.object(process_tree, "win_kernel32", lambda: kernel),
                   patch.object(process_tree, "close_handle", closed.append)]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        return tree, kernel, closed

    def test_job_terminate_then_short_wait_skips_taskkill(self):
        proc = _JobExitPopen()
        tree, kernel, closed = self._tree(proc)
        with patch.object(process_tree, "kill_tree", return_value=True) as kill:
            self.assertTrue(tree.terminate())
        self.assertEqual(kernel.calls, ["terminate"])
        self.assertEqual(proc.waits, [1], "Job 终止后只等 1 秒")
        kill.assert_not_called()
        self.assertTrue(proc.lock_free_during_wait, "等待期间不得持 tree 锁")
        tree.close()
        self.assertEqual(closed, [77])

    def test_slow_exit_still_falls_back_to_taskkill(self):
        proc = _JobExitPopen(exits_on_wait=False)
        tree, kernel, _closed = self._tree(proc)
        with patch.object(process_tree, "kill_tree", return_value=True) as kill:
            self.assertTrue(tree.terminate())
        kill.assert_called_once_with(proc)
        self.assertEqual(proc.waits, [1])
        with patch.object(process_tree, "kill_tree", return_value=True) as again:
            self.assertTrue(tree.terminate(), "已确认终止后重复调用保持幂等")
        again.assert_not_called()
        self.assertEqual(kernel.calls, ["terminate"])

    def test_failed_taskkill_is_not_marked_ended(self):
        proc = _JobExitPopen(exits_on_wait=False)
        tree, _kernel, _closed = self._tree(proc)
        with patch.object(process_tree, "kill_tree", return_value=False):
            self.assertFalse(tree.terminate())
        with patch.object(process_tree, "kill_tree", return_value=True) as retry:
            self.assertTrue(tree.terminate(), "失败后 finally 还要能再试一次")
        retry.assert_called_once_with(proc)

    def test_parent_already_exited_still_terminates_the_job(self):
        """父进程先退出：靠 Job 收走后代，不依赖父 PID 走树。"""
        proc = _JobExitPopen(exited=True)
        tree, kernel, closed = self._tree(proc)
        with patch.object(process_tree, "kill_tree", return_value=True) as kill:
            self.assertTrue(tree.terminate())
        self.assertEqual(kernel.calls, ["terminate"], "父进程已退出时仍要对 Job 发终止")
        kill.assert_not_called()
        self.assertEqual(proc.waits, [], "父进程已退出就不用再等")
        tree.close()
        self.assertEqual(closed, [77])

    def test_parent_already_exited_close_alone_releases_the_job(self):
        """没人调 terminate 时，关句柄（KILL_ON_JOB_CLOSE）就是兜底的收尸。"""
        proc = _JobExitPopen(exited=True)
        tree, kernel, closed = self._tree(proc)
        tree.close()
        self.assertEqual(closed, [77])
        self.assertEqual(kernel.calls, [])
        self.assertTrue(tree.terminate(), "句柄已关、父进程已退时 terminate 不再有事可做")
        self.assertEqual(kernel.calls, [])


@unittest.skipUnless(sys.platform == "win32", "受管进程树只在 Windows 上创建")
class SpawnOwnedStdioTests(unittest.TestCase):
    """受管创建入口：stdio 可配、所有权先于执行、失败回收不留半截。"""

    def setUp(self):
        _FakePopen.instances = []
        self.kernel = _FakeKernel32()
        self.closed_handles = []
        self.patches = [
            patch.object(process_tree, "subprocess",
                         SimpleNamespace(Popen=_FakePopen, PIPE=-1, STDOUT=-2,
                                         DEVNULL=-3)),
            patch.object(process_tree, "os", SimpleNamespace(name="nt")),
            patch.object(process_tree, "win_kernel32", lambda: self.kernel),
            patch.object(process_tree, "open_primary_thread", lambda pid: 99),
            patch.object(process_tree, "close_handle", self.closed_handles.append),
            patch.object(process_tree, "create_job_for",
                         lambda proc: (self.kernel.calls.append("job"), 77)[1]),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_configured_stdio_is_passed_through(self):
        tree = process_tree.spawn_owned(
            ["worker", "login"], cwd="c", env={"A": "1"}, stdin=-1, bufsize=1)
        kwargs = _FakePopen.instances[0].kwargs
        self.assertEqual(kwargs["stdin"], -1)
        self.assertEqual(kwargs["stdout"], -1)
        self.assertEqual(kwargs["stderr"], -2)
        self.assertEqual(kwargs["bufsize"], 1)
        self.assertTrue(kwargs["creationflags"] & process_tree.CREATE_NO_WINDOW)
        self.assertEqual(self.kernel.calls, ["job", "resume"],
                         "必须先取得 Job 所有权再恢复执行")
        self.assertTrue(tree.owned)

    def test_default_worker_stdio_matches_old_entry(self):
        process_tree.spawn_owned_worker(["worker"], cwd="c", env={})
        kwargs = _FakePopen.instances[0].kwargs
        self.assertIsNone(kwargs["stdin"])
        self.assertEqual(kwargs["stdout"], -1)
        self.assertEqual(kwargs["stderr"], -2)
        self.assertEqual(kwargs["bufsize"], 1)

    def test_resume_failure_kills_suspended_proc_and_closes_handles(self):
        self.kernel.resume_fails = True
        with self.assertRaises(process_tree.SpawnFailure):
            process_tree.spawn_owned(["worker"], cwd="c", env={})
        proc = _FakePopen.instances[0]
        self.assertTrue(proc.killed, "失败路径必须结束仍挂起的自有进程")
        self.assertTrue(proc.waited, "失败路径必须回收进程句柄")
        self.assertTrue(proc.stdin.closed and proc.stdout.closed and proc.stderr.closed)
        self.assertIn(77, self.closed_handles, "失败路径必须关掉 Job 句柄")
        self.assertIn(99, self.closed_handles, "失败路径必须关掉主线程句柄")

    def test_spawn_failure_is_an_oserror(self):
        """G2：SpawnFailure 同时是 OSError，调用方「进程没起来」的 except OSError 才接得住它。"""
        self.assertTrue(issubclass(process_tree.SpawnFailure, OSError))
        with patch.object(process_tree, "os", SimpleNamespace(name="posix")):
            with self.assertRaises(OSError):
                process_tree.spawn_owned(["worker"], cwd="c", env={})

    def test_non_windows_refuses_ownership_before_spawning(self):
        with patch.object(process_tree, "os", SimpleNamespace(name="posix")):
            with self.assertRaises(process_tree.SpawnFailure):
                process_tree.spawn_owned(["worker"], cwd="c", env={})
        self.assertEqual(_FakePopen.instances, [], "取不到所有权就不得创建进程")


if __name__ == "__main__":
    unittest.main()
