"""回包分类表（决策 015）的纯函数用例：每行用学校真实文案，冲突文案里的活动名用占位。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from domain.signup_reply import (  # noqa: E402
    STOP_REASON_LABELS,
    TERMINAL_STOP_REASONS,
    classify_signup_reply,
    stop_reason_label,
)
from domain.retry_rules import retry_payload  # noqa: E402


class ClassifyTests(unittest.TestCase):
    def kind(self, code, message):
        return classify_signup_reply(code, message).kind

    def test_success_by_code_only(self):
        self.assertEqual(self.kind(1, "操作成功！"), "success")
        self.assertEqual(self.kind("1", ""), "success")

    def test_real_replies_from_evidence(self):
        cases = [
            (500, "报名未开始！", "not_open"),
            (500, "报名人数已满", "full"),
            (500, "活动时间与已参与活动时间冲突：<活动名>", "conflict"),
            (500, "报名已结束！", "closed"),
            (0, "版本不兼容，请刷新页面或清除缓存后重试", "version"),
            (0, "版本不兼容，请刷新页面或清除缓存后重试。", "version"),
            (0, "您的请求已超时，请刷新页面后重新提交", "stale_ts"),
            (0, "Cache 'hd-info' does not allow 'null' values", "no_activity"),
            (4001, "身份验证失败！", "login_invalid"),
        ]
        for code, message, expect in cases:
            with self.subTest(message=message):
                self.assertEqual(self.kind(code, message), expect)

    def test_login_words_without_4001_are_not_login_invalid(self):
        self.assertEqual(self.kind(0, "请登录后完成身份验证"), "unknown")
        self.assertEqual(self.kind(500, "身份验证失败"), "unknown")

    def test_unknown_and_garbage_inputs_never_raise(self):
        for code, message in ((0, "系统繁忙，请稍后再试"), (None, None), ("x", 123), (500, "")):
            with self.subTest(code=code, message=message):
                self.assertEqual(self.kind(code, message), "unknown")

    def test_raw_keeps_full_message(self):
        long_text = "活动时间与已参与活动时间冲突：" + "很长的活动名" * 10
        reply = classify_signup_reply(500, long_text)
        self.assertEqual(reply.raw, "code:500 " + long_text)
        self.assertEqual(reply.label, "时间冲突", "界面结论不带学校原文")


class StopReasonLabelTests(unittest.TestCase):
    def test_every_terminal_kind_has_a_label(self):
        for stop_reason in list(TERMINAL_STOP_REASONS.values()) + ["clock_skew", "unknown_reply", "page_unavailable"]:
            with self.subTest(stop_reason=stop_reason):
                self.assertTrue(stop_reason_label(stop_reason))
        self.assertEqual(set(STOP_REASON_LABELS),
                         set(TERMINAL_STOP_REASONS.values()) | {"clock_skew", "unknown_reply", "page_unavailable"})

    def test_old_stop_reasons_have_no_label(self):
        for stop_reason in ("success", "max_attempts", "retry_duration", "login_invalid", "", None):
            self.assertEqual(stop_reason_label(stop_reason), "")

    def test_retry_payload_carries_outcome_label_only_for_new_reasons(self):
        class Spec:
            sign_end = ""

        full = retry_payload({"stop_reason": "full", "attempts": 1}, Spec(), stop_reason="")
        self.assertEqual(full["outcome_label"], "名额已满")
        old = retry_payload({"stop_reason": "max_attempts", "attempts": 3}, Spec(), stop_reason="")
        self.assertNotIn("outcome_label", old)


if __name__ == "__main__":
    unittest.main()
