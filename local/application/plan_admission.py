# -*- coding: utf-8 -*-
"""计划接纳、请求对账与终态发布；状态共用协调锁。"""
from __future__ import annotations

import re
import time
import uuid

from domain import plan_rules, retry_rules


class PlanAdmission:
    START_KEEP = 32
    FINISHED_PLAN_KEEP = 32

    def __init__(self, *, lock, coordination, activity_list, login, ports):
        self._lock = lock
        self._coord = coordination
        self._activity_list = activity_list
        self._login = login
        self._ports = ports
        self.plan = None
        self.last_plan = None
        self.start_requests = {}
        self.start_order = []
        self.canceled_start_ids = set()
        self.plan_generation = 0
        self.latest_plan_id = ""
        self.finished_plan_ids = {}
        self.next_plan_source = "desktop"
        self.plan_sources = {}

    def prune_finished_plans_locked(self):
        if len(self.finished_plan_ids) > self.FINISHED_PLAN_KEEP:
            for plan_id in list(self.finished_plan_ids)[:-self.FINISHED_PLAN_KEEP]:
                self.finished_plan_ids.pop(plan_id, None)

    def protect_start(self, request_id):
        record = self.start_requests.get(request_id) or {}
        state = record.get("state")
        if state == "pending":
            return True
        if state != "accepted":
            return False
        plan_id = str(record.get("plan_id") or "")
        return bool(plan_id and plan_id == self.latest_plan_id
                    and self.plan is not None and self.plan.plan_id == plan_id)

    def remember_start(self, request_id, state, **extra):
        record = dict(self.start_requests.get(request_id) or {})
        record.update({"state": state, "at": record.get("at") or time.time()})
        record.update(extra)
        self.start_requests[request_id] = record
        if request_id in self.start_order:
            self.start_order.remove(request_id)
        self.start_order.append(request_id)
        while len(self.start_order) > self.START_KEEP:
            victim = next((rid for rid in self.start_order if not self.protect_start(rid)), None)
            if victim is None:
                break
            self.start_order.remove(victim)
            self.start_requests.pop(victim, None)

    @staticmethod
    def start_replay(record, request_id):
        state = record.get("state")
        if state in {"accepted", "rejected"}:
            return dict(record.get("result") or {}, request_id=request_id, duplicate=True)
        if state == "canceled":
            return {"ok": False, "text": "这次开始已取消，可以重新发起。",
                    "request_id": request_id, "canceled": True}
        return {"ok": True, "queued": True, "pending": True, "request_id": request_id,
                "text": "正在确认是否启动，请稍候"}

    def start_request_state(self, request_id):
        rid = str(request_id or "")
        with self._lock:
            record = self.start_requests.get(rid)
            if record is None and rid in self.canceled_start_ids:
                record = {"state": "canceled"}
            plan = self.plan
            generation = (self.plan_generation if str(record.get("plan_id") or "")
                          == self.latest_plan_id else 0) if record else 0
        if not record:
            return {"ok": True, "state": "unknown", "request_id": rid,
                    "text": "没有这次开始的记录，可能程序重启过"}
        state = str(record.get("state") or "unknown")
        plan_id = str(record.get("plan_id") or "")
        payload = {"ok": True, "state": state, "plan_id": plan_id, "request_id": rid,
                   "plan_generation": generation}
        if state == "accepted":
            if plan is not None and plan.plan_id == plan_id:
                snapshot = plan.snapshot()
                payload["running"] = snapshot.get("status") in {"ready", "running"}
                payload["snapshot"] = snapshot
            else:
                payload["running"] = False
                payload["finished"] = True
                payload["snapshot"] = record.get("snapshot") or {
                    "status": record.get("final_status") or "unknown", "summary": {}, "tasks": []}
            payload["status"] = (payload.get("snapshot") or {}).get("status")
        else:
            payload["text"] = str((record.get("result") or {}).get("text") or "")
        return payload

    def cancel_start_request(self, request_id):
        rid = str(request_id or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", rid):
            return {"ok": False, "text": "开始请求标识无效，请重试。"}
        with self._lock:
            record = self.start_requests.get(rid)
            if rid in self.canceled_start_ids:
                return {"ok": True, "state": "canceled", "request_id": rid}
            if (not record or record.get("state") == "pending") and len(self.canceled_start_ids) >= 1024:
                return {"ok": False, "error": "cancel_capacity", "text": "取消记录已满，请等待本次对账结果。"}
            if not record:
                self.canceled_start_ids.add(rid)
                self.remember_start(rid, "canceled")
                return {"ok": True, "state": "canceled", "request_id": rid}
            if record.get("state") == "canceled":
                return {"ok": True, "state": "canceled", "request_id": rid}
            if record.get("state") == "pending":
                self.canceled_start_ids.add(rid)
                record["state"] = "canceled"
                return {"ok": True, "state": "canceled", "request_id": rid}
            if record.get("state") == "accepted":
                return {"ok": False, "state": "accepted", "plan_id": str(record.get("plan_id") or ""),
                        "request_id": rid, "text": "这次开始已经被接纳，请用「停止计划」结束"}
            return {"ok": False, "state": record.get("state"), "text": "这次开始已经有结论，不能再取消"}

    def _begin_request(self, rid):
        with self._lock:
            known = self.start_requests.get(rid)
            if rid in self.canceled_start_ids:
                known = {"state": "canceled"}
            if known is not None:
                return self.start_replay(known, rid)
            self.remember_start(rid, "pending")
        return None

    def _finish_request(self, rid, result):
        with self._lock:
            record = self.start_requests.get(rid) or {}
            state = record.get("state")
            if state == "canceled":
                result = {"ok": False, "text": "这次开始已取消，可以重新发起。", "canceled": True}
            elif state == "accepted":
                result = dict(record.get("result") or result)
            else:
                self.remember_start(rid, "accepted" if result.get("ok") else "rejected",
                                    plan_id=str(result.get("plan_id") or ""), result=dict(result))
        return dict(result, request_id=rid)

    def start_plan(self, items, headed=False, retry_policy=None, request_id="", source="desktop"):
        rid = request_id if isinstance(request_id, str) else ""
        if rid and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", rid):
            return {"ok": False, "text": "开始请求标识无效，请重试。"}
        if rid:
            replay = self._begin_request(rid)
            if replay is not None:
                return replay
        gate = self._ports["terms_gate"]()
        if gate is not None:
            rejected = dict(gate)
            if rid:
                rejected["request_id"] = rid
                with self._lock:
                    if (self.start_requests.get(rid) or {}).get("state") == "pending":
                        self.remember_start(rid, "rejected", result=rejected)
            return rejected
        with self._lock:
            self.next_plan_source = "phone" if source == "phone" else "desktop"
        try:
            result = self._ports["start_inner"](items, headed, retry_policy, rid)
        except Exception as exc:  # noqa: BLE001 - 异常也需留下对账结论
            with self._lock:
                record = self.start_requests.get(rid) or {}
                if rid and record.get("state") not in {"accepted", "canceled"}:
                    self.remember_start(rid, "rejected", result={"ok": False,
                                        "text": "开始计划时本机异常：%s" % type(exc).__name__})
            return {"ok": False, "text": "开始计划时本机异常：%s" % type(exc).__name__, "request_id": rid}
        return self._finish_request(rid, result) if rid else result

    def _busy_gate_locked(self):
        if self._coord.closing:
            return {"ok": False, "text": "程序正在关闭，已取消开始计划"}
        if not self._ports["demo"]() and not self._ports["clock_ready"]():
            return {"ok": False, "text": "北京时间在开始前失去校准，这次没有启动；稍后重试。"}
        if self._coord.is_busy_locked():
            return {"ok": False, "text": "已有登录、报名或计划在运行，先停止后再开始"}
        return None

    def _login_gate(self):
        if self._ports["demo"]():
            return None
        problem = self._ports["worker_problem"]()
        if problem:
            return {"ok": False, "text": "%s；计划没法开始" % self._ports["worker_problem_text"](problem),
                    "error": problem}
        with self._lock:
            checking = self._coord.checking
            last = dict(self._login.last_check)
        if checking:
            return {"ok": False, "text": "正在检查登录态，等这次检查完成再开始"}
        result = last.get("result") or "unknown"
        messages = {"none": "还没有登录：打开顶栏的登录状态，点「登录」先登录一次",
                    "expired": "登录态已失效：打开顶栏的登录状态，点「重新登录」后再开始"}
        if result != "valid":
            return {"ok": False, "text": messages.get(result,
                    "暂时无法确认登录态：点「刷新」重试，确认登录有效后再开始")}
        return None

    def _prepare_items(self, items, accepted_at):
        normalized, error = plan_rules.normalize_plan_items(items, self._activity_list.activities, accepted_at)
        if error is not None:
            return None, error
        error = plan_rules.closed_items_error(normalized, accepted_at, self._ports["classify"])
        if error is not None:
            return None, error
        with self._lock:
            signed = [dict(item) for item in self._activity_list.activities.values() if item.get("signed")]
        checked = plan_rules.check_conflicts(normalized, accepted_at, signed, self._ports["validate"])
        return (normalized, None) if checked["ok"] else (None, checked)

    def _reserve(self, plan, plan_id, request_id, events):
        with self._lock:
            error = self._busy_gate_locked()
            if error is not None:
                return error
            if request_id and self.start_requests.get(request_id, {}).get("state") == "canceled":
                return {"ok": False, "text": "这次开始已取消，可以重新发起。", "canceled": True}
            self.plan = plan
            self.last_plan = None
            self.plan_generation += 1
            events.generation = self.plan_generation
            self.latest_plan_id = plan_id
            if request_id:
                self.remember_start(request_id, "accepted", plan_id=plan_id,
                                    result={"ok": True, "queued": True, "plan_id": plan_id})
        return None

    def run_task(self, spec, cancel_event, status):
        if self._ports["demo"]():
            status("submitting", {"detail": "演示：正在提交"})
            for _ in range(4):
                if cancel_event.is_set():
                    return {"status": "canceled", "reason": "你取消了这一场"}
                time.sleep(0.05)
            if spec.activity_id.endswith("career"):
                return {"status": "failed", "code": 2, "reason": "演示：名额已满"}
            return {"status": "success", "code": 0, "reason": "演示：报名成功"}
        try:
            return self._ports["run_task"](spec, cancel_event, status)
        except self._ports["spawn_failure"] as exc:
            return {"status": "failed", "code": None, "reason": "本场没能启动：%s" % exc,
                    "stop_reason": "spawn_failed", "attempts": 0}
        except self._ports["closing_error"]:
            return {"status": "canceled", "code": None, "reason": "程序正在关闭，本场次未启动"}

    def start_plan_inner(self, items, headed, retry_policy, request_id=""):
        with self._lock:
            source = self.next_plan_source
            self.next_plan_source = "desktop"
        if not isinstance(items, list) or not items:
            return {"ok": False, "text": "先至少选择一场活动"}
        if not self._ports["demo"]() and not self._ports["clock_ready"]():
            return {"ok": False, "text": "北京时间还没有校准，暂不能开始自动报名；稍后点「重新校时」再试。"}
        accepted_at = self._ports["clock_now"]()
        with self._lock:
            error = self._busy_gate_locked()
        if error is not None:
            return error
        error = self._login_gate()
        if error is not None:
            return error
        normalized, error = self._prepare_items(items, accepted_at)
        if error is not None:
            return error
        policy = retry_policy if isinstance(retry_policy, dict) else {}
        retry_for = retry_rules.policy_int(policy.get("retry_for_s"), 120, minimum=retry_rules.ADAPTIVE_RETRY)
        max_attempts = retry_rules.policy_int(policy.get("max_attempts"), 0)
        plan_id = uuid.uuid4().hex[:12]
        with self._lock:
            self.plan_sources[plan_id] = source
            for stale in list(self.plan_sources)[:-16]:
                self.plan_sources.pop(stale, None)
        specs = [self._ports["task_spec"](item, "task-%02d-%s" % (i + 1, item["id"]), headed,
                                        retry_for_s=retry_for, max_attempts=max_attempts, now=accepted_at)
                 for i, item in enumerate(normalized)]
        events = PlanEvents(self, plan_id, source)
        plan = self._ports["coordinator"](plan_id, specs, self.run_task, events.emit,
                                          now=self._ports["clock_now"])
        events.plan = plan
        error = self._reserve(plan, plan_id, request_id, events)
        if error is not None:
            return error
        try:
            plan.start()
        except Exception:
            with self._lock:
                if self.plan is plan:
                    self.plan = None
                if request_id:
                    self.remember_start(request_id, "rejected", plan_id="",
                                        result={"ok": False, "text": "计划没能开始，请再试一次"})
            return {"ok": False, "text": "计划没能开始，请再试一次"}
        return {"ok": True, "queued": True, "plan_id": plan_id, "plan_generation": events.generation}


class PlanEvents:
    """先提交终态再发布；旧计划不能覆盖或广播新计划的状态。"""

    def __init__(self, owner, plan_id, source):
        self.owner = owner
        self.plan_id = plan_id
        self.source = source
        self.generation = 0
        self.plan = None

    def annotated(self, payload):
        data = dict(payload) if isinstance(payload, dict) else {}
        data.setdefault("plan_id", self.plan_id)
        data["plan_generation"] = self.generation
        data["source"] = self.source
        if "request_id" not in data:
            rid = next((key for key, value in self.owner.start_requests.items()
                        if value.get("plan_id") == self.plan_id), "")
            if rid:
                data["request_id"] = rid
        return data

    def emit(self, kind, payload):
        owner = self.owner
        if kind == "task" and isinstance(payload, dict):
            status = str(payload.get("status") or "")
            if status in {"success", "already_signed"}:
                owner._ports["confirm_signed"](str(payload.get("activity_id") or ""), status)
        if kind != "plan_done":
            with owner._lock:
                latest = owner.latest_plan_id == self.plan_id
                forward = self.annotated(payload) if latest else None
            if latest:
                owner._ports["emit"](kind, forward)
            return
        try:
            snapshot = self.plan.snapshot()
        except Exception:
            snapshot = None
        with owner._lock:
            forward = self._finish_locked(payload, snapshot)
        if forward is not None:
            owner._ports["emit"]("plan_done", forward)
            owner._ports["notify_done"](snapshot)

    def _finish_locked(self, payload, snapshot):
        owner = self.owner
        owns_slot = owner.plan is self.plan
        if owns_slot:
            owner.plan = None
        elif owner.plan is None and owner.latest_plan_id == self.plan_id:
            owns_slot = True
        first_done = not owner.finished_plan_ids.get(self.plan_id)
        if owns_slot and first_done:
            owner.finished_plan_ids[self.plan_id] = True
            owner.prune_finished_plans_locked()
            owner.last_plan = snapshot
        if first_done:
            rid = next((key for key, value in owner.start_requests.items()
                        if value.get("plan_id") == self.plan_id), "")
            if rid:
                status = str(payload.get("status") or (snapshot or {}).get("status") or "")
                owner.remember_start(rid, "accepted", plan_id=self.plan_id, finished=True,
                                     final_status=status, snapshot={"status": status,
                                     "summary": payload.get("summary") or {},
                                     "tasks": (snapshot or {}).get("tasks") or []})
        return self.annotated(payload) if owner.latest_plan_id == self.plan_id else None


class PlanFields:
    """旧字段显式代理到计划服务，兼容组合根与已有夹具。"""

    @property
    def _plan(self): return self._plan_manager.plan
    @_plan.setter
    def _plan(self, value): self._plan_manager.plan = value
    @property
    def _last_plan(self): return self._plan_manager.last_plan
    @_last_plan.setter
    def _last_plan(self, value): self._plan_manager.last_plan = value
    @property
    def _start_requests(self): return self._plan_manager.start_requests
    @_start_requests.setter
    def _start_requests(self, value): self._plan_manager.start_requests = value
    @property
    def _start_order(self): return self._plan_manager.start_order
    @_start_order.setter
    def _start_order(self, value): self._plan_manager.start_order = value
    @property
    def _canceled_start_ids(self): return self._plan_manager.canceled_start_ids
    @_canceled_start_ids.setter
    def _canceled_start_ids(self, value): self._plan_manager.canceled_start_ids = value
    @property
    def _plan_generation(self): return self._plan_manager.plan_generation
    @_plan_generation.setter
    def _plan_generation(self, value): self._plan_manager.plan_generation = value
    @property
    def _latest_plan_id(self): return self._plan_manager.latest_plan_id
    @_latest_plan_id.setter
    def _latest_plan_id(self, value): self._plan_manager.latest_plan_id = value
    @property
    def _finished_plan_ids(self): return self._plan_manager.finished_plan_ids
    @_finished_plan_ids.setter
    def _finished_plan_ids(self, value): self._plan_manager.finished_plan_ids = value
    @property
    def _next_plan_source(self): return self._plan_manager.next_plan_source
    @_next_plan_source.setter
    def _next_plan_source(self, value): self._plan_manager.next_plan_source = value
    @property
    def _plan_sources(self): return self._plan_manager.plan_sources
    @_plan_sources.setter
    def _plan_sources(self, value): self._plan_manager.plan_sources = value
