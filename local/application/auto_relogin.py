# -*- coding: utf-8 -*-
"""独立于手机开关的自动恢复调度，只消费注入的检查结果与会话终态。

@author Author
"""
from __future__ import annotations

import threading


class AutoReloginMonitor:
    def __init__(self, *, now, check, start, eligible, state, period=60, paused=None):
        self._now = now
        # 保存的密码被学校拒绝过就暂停：不再拿同一份密码去撞，等用户写入新密码
        self._paused = paused
        self._check = check
        self._start_relogin = start
        self._eligible = eligible
        self._state = state
        self._period = period
        self._next_check = now() + period
        self._retry_at = 0
        self._expired = False
        self._inflight = False
        self._flow_id = ""
        self._failures = 0
        self._phase = "waiting"
        self._generation = 0
        self._working = False
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        # 最近一次「自动发起重登」的事实，只记时间与方法，不记账号/验证码
        self._last_used_at = None      # 从未用过就是 None，0 表示「刚刚」
        self._last_used_method = ""

    def start(self):
        with self._lock:
            if self._thread is not None or self._stop.is_set():
                return
            self._thread = threading.Thread(target=self._run, name="auto-relogin", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)

    def _run(self):
        while not self._stop.wait(1):
            self.tick()

    def observe_check(self, result):
        with self._lock:
            self._expired = result == "expired"
            self._next_check = self._now() + self._period

    def request_recover(self):
        """报名进程确认登录失效、在等新登录态（决策 015）：下一拍立即自动登录一次。

        已经有一轮自动登录在跑就不重复发起；会跳过失败后的退避等待。
        """
        with self._lock:
            if self._inflight:
                return
            self._expired = True
            self._retry_at = 0

    def reset(self):
        with self._lock:
            self._generation += 1
            self._expired = self._inflight = False
            self._flow_id = ""
            self._failures = 0
            self._retry_at = 0
            self._next_check = self._now() + self._period
            self._phase = "waiting"

    def snapshot(self):
        with self._lock:
            return {"state": self._phase, "inflight": self._inflight,
                    "failures": self._failures,
                    "retry_in": max(0, int(self._retry_at - self._now())),
                    # 单调钟只对「多久以前」有意义；原样给时间戳会让界面误当墙钟
                    "last_used_ago_s": (max(0, int(self._now() - self._last_used_at))
                                        if self._last_used_at is not None else None),
                    "last_used_method": self._last_used_method}

    def _failed(self, now):
        self._failures += 1
        self._retry_at = now + (60, 120, 300, 900)[min(self._failures - 1, 3)]
        self._inflight = False
        self._phase = "backoff"

    def tick(self):
        # 只占调度槽；外部回调可能重入 Api/monitor，绝不在锁内调用。
        with self._lock:
            if self._working or self._stop.is_set():
                return
            self._working = True
            generation = self._generation
            inflight, flow_id = self._inflight, self._flow_id
        try:
            now = self._now()
            if inflight:
                state = self._state()
                with self._lock:
                    if generation != self._generation:
                        return
                    if state.get("flow_id") != flow_id:
                        # flow 被换掉了。区分两种原因：别的来源（手机发起、桌面
                        # 手动重登）接管 —— 那是人主动接手，不是自动重登失败；
                        # 自己的流程凭空消失 —— 才算这一轮没跑成。
                        taken_over = bool(state.get("live")) and bool(
                            state.get("flow_id"))
                        if taken_over:
                            self._inflight = False
                            self._phase = "idle"
                        else:
                            self._failed(now)
                    elif state.get("state") == "success":
                        self._inflight = self._expired = False
                        self._failures = 0
                        self._retry_at = 0
                        self._phase = "success"
                        self._next_check = now + self._period
                    elif state.get("state") in ("failed", "canceled", "idle"):
                        self._failed(now)
                    else:
                        self._phase = str(state.get("state") or "starting")
                return
            if self._paused is not None and self._paused():
                with self._lock:
                    if generation == self._generation:
                        self._phase = "paused"
                return
            if not self._eligible():
                return
            with self._lock:
                if generation != self._generation or self._stop.is_set():
                    return
                recover = self._expired and now >= self._retry_at
                check = not self._expired and now >= self._next_check
                if check:
                    self._next_check = now + self._period
            if recover:
                result = self._start_relogin()
                with self._lock:
                    if generation != self._generation:
                        return
                    if result.get("ok"):
                        self._inflight = True
                        self._flow_id = str(result.get("flow_id") or "")
                        self._phase = "starting"
                        # 只记「什么时候、用什么方式」发起，方便界面解释最近一次自动恢复
                        self._last_used_at = now
                        self._last_used_method = "auto_ocr"
                    else:
                        self._failed(now)
            elif check:
                self._check()
        except Exception:
            # 门禁/状态故障按未知处理；不读取文件、不把异常内容带进公开状态。
            with self._lock:
                if generation == self._generation:
                    if self._expired:
                        self._failed(self._now())
                    else:
                        self._phase = "unknown"
        finally:
            with self._lock:
                self._working = False
