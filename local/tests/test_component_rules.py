#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组件读状态等锁规则测试：连续等锁满 30 秒才算「检查超时」。

纯函数测试：不读文件、不读墙钟、不起线程。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from domain.component_rules import COMPONENT_CHECK_TIMEOUT_S, check_timed_out  # noqa: E402


class ComponentCheckTimeoutTests(unittest.TestCase):
    """「检查超时」边界：29 秒没到、30 秒整到；非数字按没超时。"""

    def test_boundary_is_thirty_seconds_inclusive(self):
        self.assertFalse(check_timed_out(29))
        self.assertTrue(check_timed_out(30))
        self.assertTrue(check_timed_out(31))

    def test_zero_and_fractional_waits_do_not_time_out(self):
        self.assertFalse(check_timed_out(0))
        self.assertFalse(check_timed_out(29.9))

    def test_non_numeric_wait_counts_as_not_timed_out(self):
        for bad in (None, "", "abc", [], {}):
            with self.subTest(value=repr(bad)):
                self.assertFalse(check_timed_out(bad))

    def test_threshold_is_thirty_seconds(self):
        self.assertEqual(COMPONENT_CHECK_TIMEOUT_S, 30)


if __name__ == "__main__":
    unittest.main()
