# -*- coding: utf-8 -*-
"""活动列表单飞、缓存和结果发布。"""
from __future__ import annotations

import json
import copy
import threading
import time

class ActivityListService:
    def __init__(self, *, coordination, lock, ports, sync_window):
        self._coordination = coordination
        self._lock = lock
        self._ports = ports
        self._sync_window = sync_window
        self.activities = {}
        self.request_id = ""
        self.last = {"request_id": "", "payload": None}
        self.pc_list_error = None
        self.pc_list_ok_at = ""

    def snapshot(self):
        with self._lock:
            return self.snapshot_locked()

    def snapshot_locked(self):
        """调用方已持协调锁；对外返回独立副本。"""
        return copy.deepcopy(self.activities)

    def list_activities(self, request_id=""):
        gate = self._ports["terms_gate"](request_id)
        if gate is not None:
            return dict(gate, queued=False)
        with self._lock:
            if self._coordination.closing:
                return {"ok": False, "queued": False, "request_id": request_id,
                        "text": "程序正在关闭，已取消拉取活动列表"}
            if self._coordination.cancelling:
                return {"ok": False, "queued": False, "request_id": request_id,
                        "text": "正在取消报名，等它结束再刷新"}
            if self._coordination.listing:
                answer = {"ok": True, "queued": True, "skipped": "已经在拉活动列表",
                          "request_id": self.request_id}
                if self.last.get("payload") and self.last.get("request_id") == self.request_id:
                    answer["result"] = self.last["payload"]
                return answer
            self._coordination.listing = True
            self.request_id = request_id or ""
        threading.Thread(target=self._ports["do_list"], daemon=True).start()
        return {"ok": True, "queued": True, "request_id": request_id}

    def clock_text(self):
        try:
            return self._ports["school_time_text"]()[11:16]
        except Exception:
            return ""

    def note_error(self, reason):
        when = self._ports["clock_text"]()
        with self._lock:
            self.pc_list_error = {"reason": str(reason), "at": self.pc_list_ok_at or when}

    def do_list(self):
        try:
            self._ports["do_list_inner"]()
        except self._ports["closing_error"]:
            self._ports["emit"]("activities", {"ok": False,
                                "text": "程序正在关闭，活动列表加载已取消", "items": []})
        except OSError as exc:
            err_code = self._ports["component_error"](exc)
            self._ports["emit"]("log", "[X] 组件诊断 %s：%s: %s" % (err_code, type(exc).__name__, exc))
            self._ports["note_error"]("列表程序启动失败")
            self._ports["emit"]("activities", {"ok": False, "text": self._ports["worker_problem"](err_code),
                                               "items": [], "runtime_error": err_code})
        except Exception as exc:
            self._ports["emit"]("log", "[X] 列表请求异常 %s: %s" % (type(exc).__name__, exc))
            self._ports["note_error"]("活动列表没能加载")
            self._ports["emit"]("activities", {"ok": False, "text": "活动列表没能加载", "items": []})
        finally:
            with self._lock:
                self._coordination.listing = False

    def merge(self, items):
        try:
            now = float(self._ports["clock_now"]())
        except Exception:
            now = None
        return self._ports["merge_rules"](items, self.activities, now, self._sync_window())

    def do_list_inner(self):
        if self._ports["demo"]():
            items = self._ports["demo_items"]()
            self.activities = {str(it["id"]): it for it in items}
            with self._lock:
                self.pc_list_error = None
                self.pc_list_ok_at = self._ports["clock_text"]()
            self._ports["emit"]("activities", {"ok": True, "items": items})
            return
        clock_wait_s = self._ports["wait_clock"]()
        started = time.monotonic()
        res = self._ports["run_list"]()
        elapsed = time.monotonic() - started
        if res["code"] != 0:
            self._ports["note_error"]("活动列表没能加载")
            self._ports["emit"]("activities", {"ok": False, "text": res["out"].strip(), "items": []})
            return
        try:
            items = json.loads(res.get("stdout", res["out"]).strip() or "[]")
        except json.JSONDecodeError:
            self._ports["note_error"]("活动列表解析失败")
            self._ports["emit"]("activities", {"ok": False, "text": "活动列表解析失败", "items": []})
            return
        self._ports["emit"]("log", _timing_text(res, elapsed, clock_wait_s))
        try:
            now = self._ports["clock_now"]()
        except Exception:
            now = None
        items = self._ports["merge"](items)
        for item in items:
            item["seconds_to_open"] = self._ports["seconds_until"](item.get("sign_start"), now)
        with self._lock:
            self.activities = {str(it.get("id")): dict(it) for it in items if it.get("id")}
            self.pc_list_error = None
            self.pc_list_ok_at = self._ports["clock_text"]()
        pending = sum(1 for it in items if it.get("attendance_state") == "pending")
        failed = sum(1 for it in items if it.get("attendance_state") == "unknown")
        self._ports["emit"]("activities", {"ok": True, "items": items,
                                           "attendance": {"pending": pending, "unknown": failed}})


def _timing_text(res, elapsed, clock_wait_s):
    fallback = "活动列表用时 %.1f 秒" % elapsed
    try:
        for line in (res.get("stderr") or "").splitlines():
            if not line.startswith("[timing] list "):
                continue
            fields = dict(part.split("=", 1) for part in line[len("[timing] list "):].split() if "=" in part)
            total_s = float(fields["total_s"])
            extra = "，等北京时间约 %.1f 秒" % clock_wait_s if clock_wait_s >= 0.05 else ""
            source = fields.get("filter_time_source", "clock")
            if source == "school_date":
                extra += "，按学校服务器时间筛选"
            elif source == "none":
                extra += "，时钟和学校时间都不可用"
            return ("活动列表用时 %.1f 秒：程序启动约 %.1f 秒，联网约 %.1f 秒"
                    "（列表约 %d 页，补详情 %d 场%s）" %
                    (elapsed, max(0.0, elapsed - total_s), total_s,
                     int(fields.get("pages", 0)), int(fields.get("details", 0)), extra))
    except Exception:
        pass
    return fallback


class ActivityListFields:
    @property
    def _activities(self): return self._activity_list.activities
    @_activities.setter
    def _activities(self, value): self._activity_list.activities = value
    @_activities.deleter
    def _activities(self): del self._activity_list.activities
    @property
    def _list_request_id(self): return self._activity_list.request_id
    @_list_request_id.setter
    def _list_request_id(self, value): self._activity_list.request_id = value
    @_list_request_id.deleter
    def _list_request_id(self): del self._activity_list.request_id
    @property
    def _list_last(self): return self._activity_list.last
    @_list_last.setter
    def _list_last(self, value): self._activity_list.last = value
    @_list_last.deleter
    def _list_last(self): del self._activity_list.last
    @property
    def _pc_list_error(self): return self._activity_list.pc_list_error
    @_pc_list_error.setter
    def _pc_list_error(self, value): self._activity_list.pc_list_error = value
    @_pc_list_error.deleter
    def _pc_list_error(self): del self._activity_list.pc_list_error
    @property
    def _pc_list_ok_at(self): return self._activity_list.pc_list_ok_at
    @_pc_list_ok_at.setter
    def _pc_list_ok_at(self, value): self._activity_list.pc_list_ok_at = value
    @_pc_list_ok_at.deleter
    def _pc_list_ok_at(self): del self._activity_list.pc_list_ok_at
