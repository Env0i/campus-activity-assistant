"""登录探测复查（决策 015）：单次 4001 先隔 LOGIN_RECHECK_S 复查一次，两次都是 4001 才判失效。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

LOCAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOCAL))
import grab  # noqa: E402


class _Budget:
    """够用的假预算：记录 sleep，不真的等。"""

    def __init__(self, remaining):
        self.remaining = remaining
        self.slept = []

    def remaining_s(self):
        return self.remaining

    def sleep(self, seconds, monotonic_now=None):
        self.slept.append(seconds)


class ProbeRecheckTests(unittest.TestCase):
    def _run(self, replies, budget=None, tokens=("tok-1",)):
        calls = []
        replies = list(replies)
        token_seq = list(tokens)

        def fake_post(path, payload=None, tok=None, timeout=None, budget=None):
            calls.append(tok)
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply

        def fake_token():
            return token_seq.pop(0) if len(token_seq) > 1 else token_seq[0]

        with patch.object(grab, "_post", fake_post), \
                patch.object(grab, "token", fake_token), \
                patch.object(grab, "log", lambda msg: None), \
                patch.object(grab.time, "sleep", lambda s: None):
            result = grab.probe_token(budget)
        return result, calls

    def test_two_4001_is_expired(self):
        (state, _), calls = self._run([{"code": 4001}, {"code": 4001}])
        self.assertEqual(state, "expired")
        self.assertEqual(len(calls), 2)

    def test_4001_then_ok_is_valid(self):
        (state, _), calls = self._run([{"code": 4001}, {"code": 1}])
        self.assertEqual(state, "valid")
        self.assertEqual(len(calls), 2)

    def test_4001_then_other_error_is_unknown(self):
        (state, _), _ = self._run([{"code": 4001}, {"code": -1, "message": "TimeoutError"}])
        self.assertEqual(state, "unknown", "复查不是 4001 就不能判失效")

    def test_recheck_reads_fresh_token(self):
        # 复查前别处刚重新登录：用新 token 复查
        (state, _), calls = self._run([{"code": 4001}, {"code": 1}], tokens=("old", "new"))
        self.assertEqual(state, "valid")
        self.assertEqual(calls, ["old", "new"])

    def test_tight_budget_judges_on_single_reply(self):
        budget = _Budget(remaining=grab.LOGIN_RECHECK_S)
        (state, _), calls = self._run([{"code": 4001}], budget=budget)
        self.assertEqual(state, "expired")
        self.assertEqual(len(calls), 1, "预算不够复查时只查一次")
        self.assertEqual(budget.slept, [])

    def test_budget_sleep_used_when_budget_given(self):
        budget = _Budget(remaining=30.0)
        (state, _), _ = self._run([{"code": 4001}, {"code": 1}], budget=budget)
        self.assertEqual(state, "valid")
        self.assertEqual(budget.slept, [grab.LOGIN_RECHECK_S])

    def test_first_ok_needs_no_recheck(self):
        (state, _), calls = self._run([{"code": 1}])
        self.assertEqual(state, "valid")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
