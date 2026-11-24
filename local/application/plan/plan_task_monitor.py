# -*- coding: utf-8 -*-
"""单活动 worker 的输出消费、看门狗监督与有界收尾辅助。

从 plan_service.run_plan_task 拆出；只使用标准库与 domain 纯函数。

@author Author
"""
from __future__ import annotations

from dataclasses import dataclass
import queue
import threading
import time

from domain.common.time_text import task_deadline
from domain.plan.plan_rules import classify_task_stop
from domain.signup.retry_rules import (
    ATTEMPT_RE, attempts_of, parse_retry_line, progress_event_status,
)
from domain.signup.retry_window import (
    ADAPTIVE_RETRY, DEFAULT_RETRY_SECONDS, extension_cap, extension_delta,
)
from domain.worker.worker_lines import parse_checkpoint_line, worker_message


@dataclass
class TaskMonitorState:
    """单活动监督运行期的共享上下文。"""

    spec: object
    tree: object
    proc: object
    auto_extend: bool
    extend_cap: float | None
    supervise: threading.Condition
    shared: dict
    supervised: dict
    observed: dict
    lines: queue.Queue
    reader_done: threading.Event
    tail: list
    clock_now: object
    clock_unavailable: object
    status: object
    emit: object
    on_login_wait: object
    reader: threading.Thread
    watchdog: threading.Thread | None
    canceled: bool = False


def _compute_watch_delay(deadline: float | None, business_now: float | None,
                         retry_for_s: int, grace_s: float) -> float | None:
    """业务截止换算成一次性单调监督上限；校时失效时退回初始预算 + grace。"""
    if not deadline:
        return None
    if business_now is not None:
        return max(0.0, deadline - business_now) + grace_s
    budget_s = (float(retry_for_s)
                if retry_for_s and retry_for_s > 0
                else float(DEFAULT_RETRY_SECONDS))
    return budget_s + grace_s


def _start_reader(proc, lines: queue.Queue,
                  reader_done: threading.Event) -> threading.Thread:
    def read_output() -> None:
        try:
            for line in proc.stdout or []:
                lines.put(line.rstrip("\r\n"))
        finally:
            reader_done.set()

    reader = threading.Thread(target=read_output, name="signup-output", daemon=True)
    reader.start()
    return reader


def _start_watchdog(state: TaskMonitorState,
                    watch_delay: float | None) -> threading.Thread | None:
    """按单调截止启动看门狗；扩窗后唤醒重算剩余等待。"""
    if watch_delay is None:
        return None

    def _watchdog() -> None:
        with state.supervise:
            while not state.shared["closed"] and state.shared["hard_stop"] is not None:
                remaining = state.shared["hard_stop"] - time.monotonic()
                if remaining <= 0:
                    break
                state.supervise.wait(remaining)
            if state.shared["closed"] or state.shared["hard_stop"] is None:
                return
            state.supervised["fired"] = True
        state.tree.terminate()

    with state.supervise:
        state.shared["hard_stop"] = time.monotonic() + watch_delay
    watchdog = threading.Thread(target=_watchdog, name="signup-watchdog", daemon=True)
    watchdog.start()
    return watchdog


def start_task_monitor(spec, tree, proc, business_now: float | None,
                       grace_s: float, epoch_of, *, clock_now,
                       clock_unavailable, status, emit,
                       on_login_wait) -> TaskMonitorState:
    """初始化输出读线程与父层看门狗，返回监督上下文。"""
    retry_for_s = getattr(spec, "retry_for_s", 120)
    deadline = task_deadline(spec, epoch_of)
    auto_extend = retry_for_s == ADAPTIVE_RETRY
    end_epoch = epoch_of(spec.sign_end) if getattr(spec, "sign_end", "") else None
    extend_cap = (extension_cap(float(getattr(spec, "retry_started_at", 0) or 0),
                                end_epoch)
                  if auto_extend else None)
    lines: "queue.Queue[str]" = queue.Queue()
    reader_done = threading.Event()
    state = TaskMonitorState(
        spec=spec, tree=tree, proc=proc, auto_extend=auto_extend,
        extend_cap=extend_cap, supervise=threading.Condition(),
        shared={"hard_stop": None, "accepted": deadline,
                "closed": False, "stop_seen": False},
        supervised={"fired": False}, observed={"attempts": 0},
        lines=lines, reader_done=reader_done, tail=[],
        clock_now=clock_now, clock_unavailable=clock_unavailable,
        status=status, emit=emit, on_login_wait=on_login_wait,
        reader=_start_reader(proc, lines, reader_done), watchdog=None,
    )
    watch_delay = _compute_watch_delay(deadline, business_now, retry_for_s, grace_s)
    state.watchdog = _start_watchdog(state, watch_delay)
    return state


def _accept_window_extension(state: TaskMonitorState, parsed: dict) -> None:
    """合法 window_extended 才平移单调截止；其余一律 0 增量。"""
    if not state.auto_extend:
        return
    with state.supervise:
        if state.shared["closed"] or state.shared["stop_seen"] or state.supervised["fired"]:
            return
        delta = extension_delta(state.shared["accepted"], parsed.get("retry_deadline"),
                                state.extend_cap, True)
        if delta <= 0:
            return
        if state.shared["hard_stop"] is not None:
            state.shared["hard_stop"] += delta
        state.shared["accepted"] = state.shared["accepted"] + delta
        state.supervise.notify_all()


def _emit_checkpoint(line: str, status) -> None:
    checkpoint = parse_checkpoint_line(line)
    if checkpoint and status:
        kind, at = checkpoint
        field = {"worker_started": "run_started_at",
                 "page_opened": "page_opened_at",
                 "watch_started": "watch_started_at"}[kind]
        status("submitting", {field: at})


def _record_attempt(message: str, observed: dict, status) -> None:
    hit = ATTEMPT_RE.match(message)
    if hit:
        observed["attempts"] = max(observed["attempts"], int(hit.group(1)))
        if status:
            status("submitting", {"attempts": int(hit.group(1)),
                                  "last_reason": hit.group(2).strip()})


def _emit_retry_progress(state: TaskMonitorState, parsed: dict) -> None:
    payload = {}
    if parsed.get("retry_deadline"):
        payload["retry_deadline"] = str(parsed["retry_deadline"])
    if parsed.get("attempts") and not parsed.get("stop_reason"):
        try:
            payload["attempts"] = int(parsed["attempts"])
        except (TypeError, ValueError):
            pass
    if parsed.get("phase") and not parsed.get("stop_reason"):
        payload["phase"] = str(parsed["phase"])
    if not parsed.get("stop_reason"):
        event_now = None
        if parsed.get("kind") == "login_wait":
            try:
                event_now = state.clock_now()
            except state.clock_unavailable:
                event_now = None
        payload.update(progress_event_status(parsed, event_now))
    if payload:
        state.status("submitting", payload)


def _handle_parsed_retry(state: TaskMonitorState, parsed: dict) -> None:
    raw_attempts = parsed.get("attempts")
    if raw_attempts not in (None, ""):
        try:
            state.observed["attempts"] = max(state.observed["attempts"],
                                             int(raw_attempts))
        except (TypeError, ValueError):
            pass
    if parsed.get("stop_reason"):
        with state.supervise:
            state.shared["stop_seen"] = True
    elif parsed.get("kind") == "window_extended":
        _accept_window_extension(state, parsed)
    elif parsed.get("kind") == "login_wait" and state.on_login_wait is not None:
        try:
            state.on_login_wait()
        except Exception:  # noqa: BLE001 - 通知失败只是等不到，worker 会按登录失效收口
            pass
    if state.status:
        _emit_retry_progress(state, parsed)


def feed_worker_line(state: TaskMonitorState, line: str) -> None:
    """输出行统一入口：落日志、存尾巴，并把源事件时间与遥测推成任务 detail。"""
    state.tail.append(line)
    del state.tail[:-40]
    state.emit("log", "[%s] %s" % (state.spec.name, line))
    _emit_checkpoint(line, state.status)
    message = worker_message(line)
    _record_attempt(message, state.observed, state.status)
    parsed = parse_retry_line(message)
    if parsed:
        _handle_parsed_retry(state, parsed)


def drain_monitor_lines(state: TaskMonitorState) -> None:
    try:
        while True:
            line = state.lines.get_nowait()
            if line:
                feed_worker_line(state, line)
    except queue.Empty:
        pass


def cleanup_task_monitor(state: TaskMonitorState, tree, proc) -> None:
    """按固定顺序撤销监督、收走进程树并有界回收管道与线程。"""
    with state.supervise:
        state.shared["closed"] = True
        state.supervise.notify_all()
    if state.watchdog is not None:
        state.watchdog.join(timeout=2.0)
    try:
        tree.terminate()
    except Exception:
        pass
    state.reader.join(timeout=2.0)
    if state.reader_done.is_set() and proc.stdout:
        try:
            proc.stdout.close()
        except Exception:
            pass
    try:
        tree.close()
    except Exception:
        pass


def classify_monitored_stop(spec, code, state: TaskMonitorState,
                            epoch_of) -> dict:
    """从尾行提取结构化终态并委托纯策略分类。"""
    stop: dict = {}
    for line in reversed(state.tail):
        parsed = parse_retry_line(worker_message(line))
        if parsed and parsed.get("stop_reason"):
            stop = parsed
            break
    attempts_seen = max(state.observed["attempts"], attempts_of(stop))
    return classify_task_stop(spec, code, state.tail, state.canceled,
                              state.supervised["fired"], stop, attempts_seen,
                              epoch_of)
