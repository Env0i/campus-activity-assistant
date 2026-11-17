#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机动作 ↔ 真实 Api 方法签名守卫：白名单里的每个动作都必须绑得上 Api。

手机经 PhoneAccessService.dispatch → _call 按动作名反射调 Api，参数靠 kwargs 展开。
此前没有任何用例比对「白名单动作 + 参数键」与 Api 的真实签名：Api 改一个参数名、
或动作被指到一个不存在的方法，别处用例照旧全绿，手机上只是静默收到 internal /
not_available。这里用 create_autospec 出的「真签名、不执行」替身，把 12 个动作各按
「全键」与「最小键」派发一次，两次都必须成功且恰好落在预期方法上一次。

替身不构造 app.Api（构造会起自动重登线程）；不连学校、不起进程、不读墙钟。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import create_autospec

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from application.phone_service import PhoneAccessService  # noqa: E402
from domain.phone_rules import ACTION_PARAMS  # noqa: E402

_IMPORT_ERROR = ""
try:
    import app as local_app
except Exception as exc:  # pragma: no cover - 环境缺 pywebview 时跳过
    local_app = None
    _IMPORT_ERROR = "%s: %s" % (type(exc).__name__, exc)

# 动作 → 预期落点的 Api 方法（写死，不从 phone_service 抄映射）。
# 2026-11-17 api-coordination 结论：dispatch 只对 save_retry_policy 改名转发成
# save_prefs（参数 prefs={"retry_policy": ...}）；其余 11 个动作同名直调；
# start_plan 另由 dispatch 补 source="phone"（有专测）。
ACTION_TARGETS = {
    "cancel_start_request": "cancel_start_request",
    "cancel_task": "cancel_task",
    "check": "check",
    "list_activities": "list_activities",
    "phone_relogin_begin": "phone_relogin_begin",
    "phone_relogin_cancel": "phone_relogin_cancel",
    "phone_relogin_submit": "phone_relogin_submit",
    "save_retry_policy": "save_prefs",
    "show_window": "show_window",
    "start_plan": "start_plan",
    "start_request_state": "start_request_state",
    "stop_plan": "stop_plan",
}

# 全键派发：每个动作恰好覆盖 ACTION_PARAMS 里允许的全部参数键（有专测比对）。
FULL_ARGS = {
    "list_activities": {"request_id": "req-list-1"},
    "check": {"request_id": "req-check-1"},
    "start_plan": {
        "items": [{"id": "act-1", "request_id": "req-item-1"}],
        "headed": True,
        "retry_policy": {"retry_for_s": 120, "max_attempts": 3},
        "request_id": "req-plan-1",
    },
    "start_request_state": {"request_id": "req-state-1"},
    "cancel_start_request": {"request_id": "req-cancel-1"},
    "stop_plan": {"plan_id": "plan-1"},
    "cancel_task": {"plan_id": "plan-1", "task_id": "task-1"},
    "save_retry_policy": {"retry_policy": {"retry_for_s": 600, "max_attempts": 2}},
    "show_window": {},
    "phone_relogin_begin": {"username": "demo-user", "password": "demo-pass",
                            "save": True},
    "phone_relogin_submit": {"flow_id": "flow-1", "challenge_id": "challenge-1",
                             "code": "AB12"},
    "phone_relogin_cancel": {"flow_id": "flow-1"},
}

# 最小键派发：只带 normalize_action 之外还绕不过去的必填键；全可选的动作为空。
MINIMAL_ARGS = {
    "list_activities": {},
    "check": {},
    "start_plan": {"items": [{"id": "act-1"}]},
    "start_request_state": {"request_id": "req-state-1"},
    "cancel_start_request": {"request_id": "req-cancel-1"},
    "stop_plan": {"plan_id": "plan-1"},
    "cancel_task": {"plan_id": "plan-1", "task_id": "task-1"},
    "save_retry_policy": {"retry_policy": {}},
    "show_window": {},
    "phone_relogin_begin": {},
    "phone_relogin_submit": {},
    "phone_relogin_cancel": {},
}


class _FakeServer:
    """dispatch 不碰 server；只为满足 PhoneAccessService 的构造契约。"""

    def __init__(self, host, port, service):
        self.host = host
        self.port = port
        self.service = service

    def start(self):
        pass

    def stop(self):
        pass

    def address(self):
        return "http://%s:%d" % (self.host, self.port or 8765)


class PhoneActionSignatureTests(unittest.TestCase):
    """白名单动作的真实签名守卫：签名一漂移，手机动作就会静默变成 internal。"""

    @classmethod
    def setUpClass(cls):
        if local_app is None:
            raise unittest.SkipTest("无法导入 local/app.py：%s" % _IMPORT_ERROR)
        cls.api_class = local_app.Api

    def _dispatch(self, action, args):
        """真 dispatch + 真签名的替身 Api：返回 (结果, 替身)。每次都用新替身记调用。"""
        api = create_autospec(self.api_class, instance=True)
        service = PhoneAccessService(
            api=api, now=lambda: 1000.0,
            state_of=lambda: {"plan": {"plan_id": "plan-1"}, "login": {}},
            server_factory=lambda host, port, svc: _FakeServer(host, port, svc))
        self.addCleanup(service.stop)
        return service.dispatch(action, args), api

    def _assert_pinned(self, action, args, variant):
        """一次派发必须成功，且只命中预期方法一次（其余白名单目标一次都不许碰）。"""
        result, api = self._dispatch(action, args)
        target = ACTION_TARGETS[action]
        where = "%s/%s → Api.%s" % (action, variant, target)
        self.assertNotIn(result.get("error"), ("internal", "not_available"),
                         "%s：签名对不上或被拒（%s）" % (where, result))
        self.assertTrue(result.get("ok"), "%s：派发失败（%s）" % (where, result))
        method = getattr(api, target, None)
        self.assertIsNotNone(method, "%s：Api 上没有这个方法，动作会得到 not_available" % where)
        self.assertEqual(1, method.call_count, "%s：预期恰好一次真实调用" % where)
        for other in set(ACTION_TARGETS.values()) - {target}:
            other_method = getattr(api, other, None)
            if other_method is not None:
                self.assertEqual(0, other_method.call_count,
                                 "%s：不该顺带调 Api.%s" % (where, other))

    def test_all_actions_bind_to_real_api_signatures(self):
        """12 个动作 × 全键/最小键两次派发，全部对齐真实签名（共 24 次断言）。"""
        for action in sorted(ACTION_PARAMS):
            with self.subTest(action=action, variant="all-keys"):
                self._assert_pinned(action, FULL_ARGS[action], "all-keys")
            with self.subTest(action=action, variant="minimal"):
                self._assert_pinned(action, MINIMAL_ARGS[action], "minimal")

    def test_tables_cover_the_whole_whitelist(self):
        """新增动作而不扩展本文件时立刻变红：三张表必须与白名单键集合完全相等。"""
        self.assertEqual(set(ACTION_PARAMS), set(ACTION_TARGETS),
                         "动作→方法表与白名单不一致")
        self.assertEqual(set(ACTION_PARAMS), set(FULL_ARGS),
                         "全键派发表与白名单不一致")
        self.assertEqual(set(ACTION_PARAMS), set(MINIMAL_ARGS),
                         "最小键派发表与白名单不一致")
        for action, allowed in ACTION_PARAMS.items():
            self.assertEqual(allowed, set(FULL_ARGS[action]),
                             "%s 的全键派发没覆盖白名单里的参数键" % action)
            self.assertLessEqual(set(MINIMAL_ARGS[action]), allowed,
                                 "%s 的最小键派发带了白名单外的键" % action)

    def test_start_plan_dispatch_marks_source_phone(self):
        """start_plan 的来源由服务端写死 phone：手机请求体带不进 source。"""
        result, api = self._dispatch("start_plan", FULL_ARGS["start_plan"])
        self.assertTrue(result.get("ok"), result)
        api.start_plan.assert_called_once()
        _, kwargs = api.start_plan.call_args
        self.assertEqual("phone", kwargs.get("source"))

    def test_save_retry_policy_rewrites_into_prefs(self):
        """save_retry_policy 只许落到 save_prefs(prefs={"retry_policy": ...})。"""
        policy = {"retry_for_s": 600, "max_attempts": 2}
        result, api = self._dispatch("save_retry_policy", {"retry_policy": policy})
        self.assertTrue(result.get("ok"), result)
        api.save_prefs.assert_called_once_with(prefs={"retry_policy": policy})


if __name__ == "__main__":
    unittest.main()
