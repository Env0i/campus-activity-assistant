# -*- coding: utf-8 -*-
"""计划任务用例：单活动 worker 的启动、监督与终态收尾。

端口全部显式注入（worker 命令、环境、进程树创建、关闭判定、学校时间换算、
时钟不可用异常类型），application 不碰 Windows API 与具体路径，也不直接
依赖 business_clock/time_contract 等混合具体模块；进程树所有权在
infrastructure.desktop.process_tree。取消只终止对应进程，不影响同批其他任务。

@author Author
"""
from __future__ import annotations

import subprocess
import threading
import time

from application.plan.plan_admission import PlanAdmission as PlanAdmission
from application.plan.plan_admission import PlanFields as PlanFields
from application.plan.plan_task_monitor import (
    classify_monitored_stop,
    cleanup_task_monitor,
    drain_monitor_lines,
    start_task_monitor,
)
from domain.common.errors import ClosingError
from domain.signup.retry_window import ADAPTIVE_RETRY, DEFAULT_RETRY_SECONDS


def plan_done_notice(tasks) -> tuple:
    """后台结束通知的标题与正文。

    正文按「N 场成功，N 场待核对，N 场名额已满，N 场没成功」写，为 0 的不写；
    名额已满按 stop_reason=full 单列，待核对按 unconfirmed 单列，其余没成功的归一类。
    """
    ok = pending = full = other = 0
    for task in tasks or []:
        task = task if isinstance(task, dict) else {}
        status = str(task.get("status") or "")
        reason = str(task.get("stop_reason") or "")
        if status in ("success", "already_signed"):
            ok += 1
        elif reason == "unconfirmed":
            pending += 1
        elif reason == "full":
            full += 1
        else:
            other += 1
    parts = [("%d 场成功" % ok) if ok else "", ("%d 场待核对" % pending) if pending else "",
             ("%d 场名额已满" % full) if full else "", ("%d 场没成功" % other) if other else ""]
    text = "，".join(part for part in parts if part) or "这次计划没有场次。"
    # 标题三态照原型 Main 的 toastTitle：全成功=完成；有成功也有没成功=部分完成；
    # 一场都没成功（含没有场次）=结束。
    if ok and not (pending or full or other):
        title = "报名计划完成"
    elif ok:
        title = "报名计划部分完成"
    else:
        title = "报名计划结束"
    return title, text


def _resolve_at_text(spec, clock_now, epoch_of, time_text_of, clock_unavailable):
    """把已开放或无开放时刻的场次改写为当前业务北京时间；时钟不可用时保持原定值。"""
    at_text = spec.sign_start
    at_ts = epoch_of(spec.sign_start)
    try:
        business_now = clock_now()
    except clock_unavailable:
        business_now = None
    if at_ts is not None and business_now is not None and at_ts <= business_now:
        at_text = time_text_of(epoch=business_now)
    elif at_ts is None and business_now is not None and not spec.sign_start:
        at_text = time_text_of(epoch=business_now)
    return at_text, business_now


def _build_grab_args(spec, at_text: str, worker_command,
                     relogin_wait_s: float) -> list[str]:
    """装配单活动 worker 的命令行参数；三种重试模式保持原有语义。"""
    retry_for_s = getattr(spec, "retry_for_s", 120)
    args = worker_command(
        "grab", "--activity-id", spec.activity_id, "--name", spec.name,
        "--at", at_text, "--lead", str(max(0, int(spec.lead_s or 0))),
        "--max-attempts", str(spec.max_attempts))
    if retry_for_s == ADAPTIVE_RETRY:
        args += ["--window", str(int(DEFAULT_RETRY_SECONDS))]
    else:
        args += ["--retry-for", str(retry_for_s)]
    if spec.sign_end:
        args += ["--sign-end", spec.sign_end]
    if getattr(spec, "retry_started_at", 0):
        args += ["--retry-start", "%.3f" % float(spec.retry_started_at)]
    if spec.headed:
        args.append("--headed")
    if relogin_wait_s and relogin_wait_s > 0:
        args += ["--relogin-wait", str(int(relogin_wait_s))]
    return args


def _emit_task_start(spec, business_now: float | None, status, emit) -> None:
    if status and business_now is not None:
        status("submitting", {"worker_spawned_at": business_now})
    mode = str(getattr(spec, "signup_mode", "") or "")
    if mode == "pre_register":
        emit("log", "▶ [%s] 预报名：等待报名开放" % spec.name)
    elif mode == "instant_signup":
        emit("log", "▶ [%s] 立即报名：抢名额" % spec.name)
    else:
        emit("log", "▶ [%s] 等待并抢报名" % spec.name)


def _wait_proc_exit(state, proc) -> int:
    try:
        return proc.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        state.supervised["fired"] = True
        state.tree.terminate()
        try:
            return proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            return -1


def _run_monitor_loop(state, proc, cancel_event: threading.Event) -> int:
    """主监督循环：轮询取消/退出/超限并有界排空输出行。"""
    canceled = False
    killed = False
    reader_done = state.reader_done
    while True:
        if cancel_event.is_set() and not killed:
            canceled = True
            state.canceled = True
            killed = True
            state.tree.terminate()
        if proc.poll() is not None and (canceled or reader_done.is_set()):
            break
        if state.supervised["fired"]:
            break
        with state.supervise:
            stop_at = state.shared["hard_stop"]
        if stop_at is not None and time.monotonic() >= stop_at:
            state.supervised["fired"] = True
            state.tree.terminate()
            break
        drain_monitor_lines(state)
        time.sleep(0.05)
    reader_done.wait(1.5)
    drain_monitor_lines(state)
    return _wait_proc_exit(state, proc)


def run_plan_task(spec, cancel_event: threading.Event, status: callable, *,
                  emit, lock, plan_procs: dict, clock_now, is_closing,
                  worker_command, env, spawn, cwd: str, grace_s: float,
                  epoch_of, time_text_of, clock_unavailable,
                  relogin_wait_s: float = 0.0, on_login_wait=None,
                  plan_trees: dict | None = None) -> dict:
    """运行一个单活动脚本；取消只终止对应进程，不影响同批其他任务。

    emit(kind, payload) 发结构化事件；lock/plan_procs 是 Api 的进程登记表；
    plan_trees 是配套的受管树登记表（Api 的 stop/shutdown 用它收后代）；
    spawn(args, cwd=..., env=...) 创建并取得进程树所有权（infrastructure）。
    """
    at_text, business_now = _resolve_at_text(
        spec, clock_now, epoch_of, time_text_of, clock_unavailable)
    args = _build_grab_args(spec, at_text, worker_command, relogin_wait_s)
    with lock:
        if is_closing():
            raise ClosingError("程序正在关闭，本场次未启动")
        tree = spawn(args, cwd=cwd, env=env())
        proc = tree.proc
        plan_procs[spec.task_id] = proc
        if plan_trees is not None:
            plan_trees[spec.task_id] = tree
    _emit_task_start(spec, business_now, status, emit)
    monitor = start_task_monitor(
        spec, tree, proc, business_now, grace_s, epoch_of,
        clock_now=clock_now, clock_unavailable=clock_unavailable,
        status=status, emit=emit, on_login_wait=on_login_wait)
    code = None
    try:
        code = _run_monitor_loop(monitor, proc, cancel_event)
    finally:
        cleanup_task_monitor(monitor, tree, proc)
        with lock:
            plan_procs.pop(spec.task_id, None)
            if plan_trees is not None:
                plan_trees.pop(spec.task_id, None)
    return classify_monitored_stop(spec, code, monitor, epoch_of)
