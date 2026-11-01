# -*- coding: utf-8 -*-
"""自动恢复调度的假时钟与接线回归；不读取本机凭据。

@author Author
"""
import sys
import threading
import json
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from application.auto_relogin import AutoReloginMonitor


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.allowed = True
        self.checks = []
        self.starts = []
        self.flow = {"state": "idle"}
        self.monitor = AutoReloginMonitor(
            now=lambda: self.now, check=lambda: self.checks.append(self.now),
            start=self.begin, eligible=lambda: self.allowed, state=lambda: self.flow)
        self.addCleanup(self.monitor.stop)

    def begin(self):
        self.starts.append(self.now)
        self.flow = {"state": "starting", "flow_id": str(len(self.starts))}
        return {"ok": True, "flow_id": self.flow["flow_id"]}

    def test_initial_wait_period_and_disabled_gate(self):
        self.monitor.tick()
        self.assertEqual(self.checks, [])
        self.now = 60
        self.monitor.tick()
        self.assertEqual(self.checks, [60])
        self.now = 120
        self.allowed = False
        self.monitor.tick()
        self.assertEqual(self.checks, [60])
        self.allowed = True
        self.monitor.tick()
        self.assertEqual(self.checks, [60, 120])

    def test_only_expired_starts_and_waiting_code_stays_inflight(self):
        for result in ("unknown", "network", "bad_clock", "none", "valid"):
            self.monitor.observe_check(result)
            self.monitor.tick()
        self.assertEqual(self.starts, [])
        self.monitor.observe_check("expired")
        self.monitor.tick()
        for phase in ("starting", "waiting_code", "verifying"):
            self.flow["state"] = phase
            self.now += 1000
            self.monitor.tick()
        self.assertEqual(len(self.starts), 1)

    def test_a_takeover_by_another_source_is_not_a_failure(self):
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.assertEqual(len(self.starts), 1)
        # 手机端另开一场人工重登：中继换成了一条新的、还在跑的流程
        self.flow = {"state": "waiting_code", "flow_id": "phone-1", "live": True}
        self.monitor.tick()
        snapshot = self.monitor.snapshot()
        self.assertEqual(snapshot["failures"], 0,
                         "人主动接手不是自动重登失败，不能累加失败次数")
        self.assertFalse(snapshot["inflight"], "槽位要放回去，别一直占着")

    def test_our_own_flow_vanishing_still_counts_as_a_failure(self):
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.assertEqual(len(self.starts), 1)
        # 中继里什么都没有了：这一轮确实没跑成
        self.flow = {"state": "idle", "flow_id": "", "live": False}
        self.monitor.tick()
        self.assertEqual(self.monitor.snapshot()["failures"], 1)

    def test_backoff_cap_success_reset_and_clear_suppress(self):
        self.monitor.observe_check("expired")
        for wait in (60, 120, 300, 900, 900):
            self.monitor.tick()
            self.flow["state"] = "failed"
            self.monitor.tick()
            started = len(self.starts)
            self.now += wait - 1
            self.monitor.tick()
            self.assertEqual(len(self.starts), started)
            self.now += 1
        self.monitor.tick()
        self.flow["state"] = "success"
        self.monitor.tick()
        self.assertEqual(self.monitor.snapshot()["failures"], 0)
        started = len(self.starts)
        self.monitor.observe_check("expired")
        self.monitor.reset()
        self.allowed = False
        self.now += 5000
        self.monitor.tick()
        self.assertEqual(len(self.starts), started)

    def test_success_records_recent_use_without_sensitive_fields(self):
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.flow["state"] = "success"
        self.monitor.tick()
        snapshot = self.monitor.snapshot()
        self.assertEqual(snapshot["last_used_method"], "auto_ocr")
        self.assertEqual(snapshot["last_used_ago_s"], 0)
        text = json.dumps(snapshot, ensure_ascii=False)
        for leaked in ("secret", "password", "token", "code"):
            self.assertNotIn(leaked, text)
        # 历史事实不被 reset 擦掉：界面要能解释「上次是谁完成的」
        self.now += 125
        self.monitor.reset()
        later = self.monitor.snapshot()
        self.assertEqual(later["last_used_method"], "auto_ocr")
        self.assertEqual(later["last_used_ago_s"], 125)

    def test_callbacks_can_reenter_and_concurrent_tick_is_singleflight(self):
        entered, release = threading.Event(), threading.Event()
        def begin():
            self.monitor.snapshot()
            entered.set()
            release.wait(2)
            return self.begin()
        self.monitor._start_relogin = begin
        self.monitor.observe_check("expired")
        thread = threading.Thread(target=self.monitor.tick)
        thread.start()
        self.assertTrue(entered.wait(1))
        self.monitor.tick()
        release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(self.starts), 1)

    def test_stop_wakes_wait_and_prevents_more_work(self):
        self.monitor.start()
        self.monitor.stop()
        self.assertFalse(self.monitor._thread.is_alive())
        self.now = 1000
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.assertEqual(self.starts + self.checks, [])


class RelayRaceTests(unittest.TestCase):
    def test_spawn_reservation_and_old_finish_cannot_replace_new_flow(self):
        from application.login_relay_service import LoginRelayService
        from test_login_relay import FakeWorker
        entered, release = threading.Event(), threading.Event()
        workers = []
        def spawn(_args):
            worker = FakeWorker()
            workers.append(worker)
            entered.set()
            release.wait(2)
            return worker
        service = LoginRelayService(spawn=spawn, now=lambda: 0)
        self.addCleanup(service.shutdown)
        service.prepare("fictional", "fictional")
        answers = []
        thread = threading.Thread(target=lambda: answers.append(
            service.begin(worker_command=["fake"], origin="auto")))
        thread.start()
        self.assertTrue(entered.wait(1))
        try:
            self.assertEqual(service.begin(worker_command=["fake"])["error"], "busy")
        finally:
            release.set()
            thread.join(3)
        old = service._flow
        self.assertEqual(service.cancel(origin="phone").get("skipped"), "foreign_origin")
        service.cancel()
        service.begin(worker_command=["fake"])
        current = service.state()["flow_id"]
        service._finish(old)
        service._handle_line(old, '[login] {"kind":"success","flow_id":"%s"}' % old["flow_id"])
        self.assertEqual(service.state()["flow_id"], current)


if __name__ == "__main__":
    unittest.main()
