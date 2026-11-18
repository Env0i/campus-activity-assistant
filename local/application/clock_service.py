# -*- coding: utf-8 -*-
"""业务时钟的展示、重校与计划前监测。"""
from __future__ import annotations

import threading
import time


class ClockService:
    def __init__(self, *, clock, lock, coordination, plan_manager, ports):
        self.clock = clock
        self.syncing = False
        self.monitor_started = False
        self._lock = lock
        self._coord = coordination
        self._plan_manager = plan_manager
        self._ports = ports

    def now(self):
        return time.time() if self._ports["demo"]() else self.clock.now()

    def ready(self):
        try:
            if self.clock.state() not in ("ready", "holdover"):
                return False
            lower, upper = self.clock.bounds()
        except Exception:
            return False
        return bool(upper >= lower)

    def wait_for_list(self):
        if self._ports["ready"]():
            return 0.0
        self._ports["emit"]("log", "北京时间校准中，稍后加载活动")
        started = time.monotonic()
        deadline = started + float(self._ports["list_wait"]())
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            with self._lock:
                if self._coord.closing:
                    break
            time.sleep(min(self._ports["list_poll"](), remaining))
            if self._ports["ready"]():
                break
        return time.monotonic() - started

    def payload(self):
        if self._ports["demo"]():
            return {"schema": 1, "owner_id": "demo-clock", "generation": 1,
                    "state": "ready", "epoch_s": time.time(), "tick_s": 0,
                    "sampled_tick_s": 0, "uncertainty_s": None,
                    "source": "演示时间（离线，非真实授时）", "age_s": 0,
                    "sync_status": "succeeded", "sync_round": 1,
                    "retry_attempt": 0, "retry_in_s": 0,
                    "last_failure_source": "", "last_failure_reason": "",
                    "reason": "演示模式不联网：顶栏时间仅供演示"}
        return self._ports["snapshot"]()

    def snapshot(self):
        try:
            return self.clock.snapshot()
        except Exception as exc:
            return {"schema": 1, "state": "unavailable", "reason": str(exc),
                    "retry_attempt": 0, "retry_in_s": 0,
                    "last_failure_source": "", "last_failure_reason": ""}

    def sync(self):
        with self._lock:
            if self.syncing:
                return {"ok": True, "queued": True, "dedup": True}
            self.syncing = True
        threading.Thread(target=self._sync_worker, name="clock-resync", daemon=True).start()
        return {"ok": True, "queued": True}

    def _sync_worker(self):
        try:
            state = "ready" if self._ports["demo"]() else self.clock.sync()
        except Exception:
            state = "unavailable"
        with self._lock:
            self.syncing = False
        self._ports["emit"]("business_clock", self._ports["payload"]()
                            if self._ports["demo"]() else self._ports["snapshot"]())
        return state

    def start_monitor(self):
        if self.monitor_started:
            return
        self.monitor_started = True
        threading.Thread(target=self._monitor, name="clock-monitor", daemon=True).start()

    def _monitor(self):
        requested_for = None
        while True:
            time.sleep(5)
            try:
                with self._lock:
                    plan = self._plan_manager.plan
                if plan is None:
                    requested_for = None
                    continue
                nxt = plan.next_prepare_epoch()
                if nxt is None:
                    continue
                left = nxt - self._ports["now"]()
                if 0 < left <= 20 and requested_for != plan.plan_id:
                    self.clock.request_resync()
                    requested_for = plan.plan_id
            except Exception:
                continue


class ClockFields:
    @property
    def _clock(self): return self._clock_service.clock
    @_clock.setter
    def _clock(self, value): self._clock_service.clock = value
    @property
    def _clock_syncing(self): return self._clock_service.syncing
    @_clock_syncing.setter
    def _clock_syncing(self, value): self._clock_service.syncing = value
    @property
    def _clock_monitor_started(self): return self._clock_service.monitor_started
    @_clock_monitor_started.setter
    def _clock_monitor_started(self, value): self._clock_service.monitor_started = value
