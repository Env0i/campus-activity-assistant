"""报名进程进度事件 → 任务快照字段（决策 015）：路径、等自动登录。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.retry_rules import parse_retry_line, progress_event_status  # noqa: E402


class ProgressEventStatusTests(unittest.TestCase):
    def test_path_event_keeps_reason_with_spaces(self):
        # worker 把原因里的空格换成不换行空格，整行才不会被按空格切碎
        reason = "取不到运行时密钥（返回里没有可用密钥（code=1 x））".replace(" ", " ")
        parsed = parse_retry_line("[retry] kind=path path=click path_reason=" + reason)
        self.assertEqual(progress_event_status(parsed),
                         {"path": "click",
                          "path_reason": "取不到运行时密钥（返回里没有可用密钥（code=1 x））"})

    def test_login_wait_and_resume(self):
        wait = progress_event_status(parse_retry_line("[retry] kind=login_wait wait_s=45"), 1000.0)
        self.assertEqual(wait, {"login_wait": "waiting", "login_wait_until": 1045})
        no_clock = progress_event_status(parse_retry_line("[retry] kind=login_wait wait_s=45"), None)
        self.assertEqual(no_clock["login_wait_until"], "")
        done = progress_event_status(parse_retry_line("[retry] kind=login_resumed"), 1000.0)
        self.assertEqual(done, {"login_wait": "", "login_wait_until": ""})

    def test_other_events_add_nothing(self):
        for line in ("[retry] kind=submit attempts=1 request_id=req-1 phase=full_speed",
                     "[retry] kind=window retry_deadline=1 sign_end=0"):
            self.assertEqual(progress_event_status(parse_retry_line(line), 1.0), {})
        self.assertEqual(progress_event_status(None, 1.0), {})


if __name__ == "__main__":
    unittest.main()
