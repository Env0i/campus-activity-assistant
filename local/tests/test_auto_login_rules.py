# -*- coding: utf-8 -*-
"""自动登录六态的纯规则测试。

Author
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.login_rules import AUTO_LOGIN_STATES, auto_login_state


class AutoLoginStateTests(unittest.TestCase):
    def test_states_are_frozen_and_complete(self):
        self.assertEqual(AUTO_LOGIN_STATES,
                         ("idle", "running", "handoff", "backoff", "blocked", "manual"))

    def test_idle_when_session_is_valid_even_if_not_ready(self):
        self.assertEqual(auto_login_state(expired=False, ready=(False, "terms"),
                                          block="terms", relay={}, inflight=False,
                                          handoff=False, failures=0, retry_in_s=0),
                         {"auto_state": "idle", "auto_block": "", "auto_retry_in_s": None})

    def test_manual_live_flow_has_priority_over_expired(self):
        result = auto_login_state(
            expired=True, ready=(True, ""), block="", relay={"live": True, "origin": "desktop"},
            inflight=True, handoff=False, failures=0, retry_in_s=0)
        self.assertEqual(result["auto_state"], "manual")

    def test_handoff_has_priority_over_inflight(self):
        result = auto_login_state(
            expired=True, ready=(True, ""), block="", relay={"live": True, "origin": "auto",
                                                              "mode": "manual"},
            inflight=True, handoff=False, failures=0, retry_in_s=0)
        self.assertEqual(result["auto_state"], "handoff")

    def test_live_auto_flow_without_manual_mode_is_running(self):
        result = auto_login_state(
            expired=True, ready=(True, ""), block="", relay={"live": True, "origin": "auto",
                                                              "mode": "auto"},
            inflight=False, handoff=False, failures=0, retry_in_s=0)
        self.assertEqual(result["auto_state"], "running")

    def test_blocked_copies_reason_and_only_exposes_block(self):
        result = auto_login_state(
            expired=True, ready=(False, "ocr_missing"), block="ocr_missing", relay={},
            inflight=False, handoff=False, failures=0, retry_in_s=0)
        self.assertEqual(result,
                         {"auto_state": "blocked", "auto_block": "ocr_missing",
                          "auto_retry_in_s": None})

    def test_backoff_needs_positive_retry_and_running_when_due(self):
        backoff = auto_login_state(
            expired=True, ready=(True, ""), block="", relay={}, inflight=False,
            handoff=False, failures=1, retry_in_s=7)
        due = auto_login_state(
            expired=True, ready=(True, ""), block="", relay={}, inflight=False,
            handoff=False, failures=1, retry_in_s=0)
        self.assertEqual(backoff["auto_state"], "backoff")
        self.assertEqual(backoff["auto_retry_in_s"], 7)
        self.assertEqual(due, {"auto_state": "running", "auto_block": "", "auto_retry_in_s": None})


    def test_scheduler_handoff_flag_alone_is_backoff_when_relay_not_live(self):
        # 电脑那一场已结束（中继不在进行），调度器的 handoff 标记可能还没清：不算转人工
        result = auto_login_state(
            expired=True, ready=(True, ""), block="", relay={"live": False}, inflight=False,
            handoff=True, failures=1, retry_in_s=60)
        self.assertEqual(result, {"auto_state": "backoff", "auto_block": "",
                                  "auto_retry_in_s": 60})

    def test_scheduler_handoff_flag_alone_with_inflight_is_running(self):
        result = auto_login_state(
            expired=True, ready=(True, ""), block="", relay={"live": False}, inflight=True,
            handoff=True, failures=0, retry_in_s=0)
        self.assertEqual(result["auto_state"], "running")

    def test_relay_own_handoff_flag_while_live_auto_is_handoff(self):
        result = auto_login_state(
            expired=True, ready=(True, ""), block="",
            relay={"live": True, "origin": "auto", "mode": "auto", "handoff": True},
            inflight=False, handoff=False, failures=0, retry_in_s=0)
        self.assertEqual(result["auto_state"], "handoff")


if __name__ == "__main__":
    unittest.main()
