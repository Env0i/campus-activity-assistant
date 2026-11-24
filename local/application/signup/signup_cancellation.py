# -*- coding: utf-8 -*-
"""电脑端单场取消：占位、执行与活动列表回写。"""
from __future__ import annotations

from domain.signup import cancel_rules


class SignupCancellation:
    def __init__(self, *, lock, coordination, activity_list, ports, busy_text):
        self._lock = lock
        self._coord = coordination
        self._activity_list = activity_list
        self._ports = ports
        self._busy_text = busy_text

    def refusal(self, kind, reason):
        result = {"ok": False, "kind": kind, "reason": reason}
        text = self._busy_text.get(reason) if kind == "busy" else ""
        if text:
            result["message"] = text
        return result

    def cancel(self, activity_id=""):
        gate = self._ports["terms_gate"]()
        if gate is not None:
            return dict(gate, kind="precheck_failed", reason="terms_required")
        aid = activity_id.strip() if isinstance(activity_id, str) else ""
        with self._lock:
            item = self._activity_list.activities.get(aid) if aid else None
            if not item or not item.get("signed"):
                return self.refusal("precheck_failed", "not_in_list")
            busy = self._coord.cancel_busy_reason_locked()
            if busy:
                return self.refusal("busy", busy)
            self._coord.cancelling = True
        try:
            result = self._ports["run"](aid)
        finally:
            with self._lock:
                self._coord.cancelling = False
        self._ports["emit"]("log", "取消报名：%s%s" % (
            result.get("kind"), "（%s）" % result["reason"] if result.get("reason") else ""))
        if result.get("kind") == "cancelled":
            self._ports["after"](aid)
        return result

    def run(self, aid):
        if self._ports["demo"]():
            return {"ok": True, "kind": "cancelled", "demo": True}
        problem = self._ports["worker_problem"]()
        if problem:
            self._ports["diagnose_problem"](problem)
            return self.refusal("precheck_failed", "worker_unavailable")
        try:
            res = self._ports["worker"](aid)
        except self._ports["closing_error"]:
            return self.refusal("busy", "closing")
        except OSError as exc:
            self._ports["diagnose_error"](exc)
            return self.refusal("precheck_failed", "worker_unavailable")
        except Exception:  # noqa: BLE001 - 无法确定 worker 是否已经发出请求
            return cancel_rules.unknown_result()
        return cancel_rules.normalize_worker_result(res.get("stdout", ""))

    def after_cancelled(self, aid):
        with self._lock:
            activities = self._activity_list.activities
            item = activities.get(aid)
            if item:
                item = dict(item)
                item["signed"] = False
                item["signed_source"] = "cancelled"
                item["sync_pending"] = False
                activities[aid] = item
            items = [dict(it) for it in activities.values()]
            previous_last = self._activity_list.last
        self._ports["emit"]("activities", {"ok": True, "items": items, "request_id": ""})
        # 此事件不属于某次刷新，恢复刷新终态以保留对账语义。
        with self._lock:
            self._activity_list.last = previous_last
