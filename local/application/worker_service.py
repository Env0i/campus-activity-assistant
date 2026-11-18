# -*- coding: utf-8 -*-
"""桌面 worker 的受管创建、登记、输出和回收。"""
from __future__ import annotations

import subprocess
import threading


class WorkerService:
    def __init__(self, *, lock, coordination, login, ports):
        self._lock = lock
        self._coord = coordination
        self._login = login
        self._ports = ports

    def run(self, args, timeout):
        with self._lock:
            if self._coord.closing:
                raise self._ports["closing_error"]("程序正在关闭，已取消本次 worker 调用")
            tree = self._ports["spawn"](args, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc = tree.proc
            self._coord.aux_trees[proc] = tree
            self._coord.aux_procs.add(proc)
        try:
            try:
                out, err = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                terminated = False
                try:
                    terminated = bool(tree.terminate())
                except Exception:
                    pass
                if not terminated:
                    self._ports["kill_tree"](proc)
                try:
                    proc.communicate(timeout=5)
                except Exception:
                    pass
                return {"code": -1, "out": "[X] 执行超时（%d 秒）" % timeout,
                        "stdout": "", "stderr": ""}
        finally:
            with self._lock:
                self._coord.aux_procs.discard(proc)
                registered_tree = self._coord.aux_trees.pop(proc, None)
            if registered_tree is not None:
                registered_tree.close()
        return {"code": proc.returncode, "out": (out or "") + (err or ""),
                "stdout": out or "", "stderr": err or ""}

    def spawn(self, args, label, kind="grab"):
        problem = self._ports["worker_problem"]()
        if problem:
            self._ports["diagnose_problem"](problem)
            return {"ok": False, "text": self._ports["problem_text"](problem), "error": problem}
        try:
            with self._lock:
                if self._coord.closing:
                    return {"ok": False, "text": "程序正在关闭，已取消本次「%s」" % label}
                if self._ports["busy"]():
                    return {"ok": False, "text": "已经有一个任务在跑，先等它结束"}
                tree = self._ports["spawn"](args)
                self._coord.proc = tree.proc
                self._coord.proc_tree = tree
                proc = tree.proc
        except self._ports["spawn_failure"] as exc:
            self._ports["emit"]("log", "[X] worker 没能取得进程树所有权：%s" % exc)
            return {"ok": False, "text": "worker 没能启动（本机不允许接管子进程），请重试"}
        except OSError as exc:
            err_code = self._ports["component_error"](exc)
            self._ports["emit"]("log", "[X] 组件诊断 %s：%s: %s" % (err_code, type(exc).__name__, exc))
            return {"ok": False, "text": self._ports["problem_text"](err_code), "error": err_code}
        threading.Thread(target=self._ports["pump"], args=(proc, label, kind), daemon=True).start()
        return {"ok": True}

    def spawn_relay(self, args):
        problem = self._ports["worker_problem"]()
        if problem:
            raise RuntimeError(problem)
        with self._lock:
            if self._coord.closing:
                raise RuntimeError("closing")
            single = self._coord.proc is not None and self._coord.proc.poll() is None
            if single or self._coord.checking or self._coord.listing or self._coord.cancelling:
                raise RuntimeError("busy")
            tree = self._ports["spawn"](args, stdin=subprocess.PIPE, bufsize=1)
            self._coord.proc = tree.proc
            self._coord.proc_tree = tree
            self._login.relay_proc_tree = tree
        return self._ports["relay_tree"](tree)

    def pump(self, proc, label, kind="grab"):
        self._ports["emit"]("log", "▶ " + label)
        tail = []
        for line in proc.stdout or []:
            line = line.rstrip("\r\n")
            if not line:
                continue
            tail.append(line)
            del tail[:-40]
            if line.startswith("[login] "):
                self._ports["observe_relay"](line)
            self._ports["emit"]("log", line)
        proc.wait()
        ok, reason = self._ports["done_result"](kind, proc.returncode, tail)
        if kind == "login" and ok:
            try:
                self._ports["anchor_login"]()
            except Exception as exc:  # noqa: BLE001 - 锚点失败不吞掉登录结论
                self._ports["emit"]("log", "[!] 登录成功，但会话时间锚点没有写成：%s" % exc)
        self._ports["emit"]("done", {"ok": ok, "code": proc.returncode,
                                   "reason": reason, "label": label, "kind": kind})
        with self._lock:
            if self._coord.proc is proc:
                self._coord.proc = None
                tree = self._coord.proc_tree
                self._coord.proc_tree = None
            else:
                tree = None
        if tree is not None:
            tree.close()

    def terminate_plan_procs(self):
        with self._lock:
            trees = list(self._coord.plan_trees.values())
            procs = list(self._coord.plan_procs.values())
        covered = set()
        for tree in trees:
            try:
                if tree.terminate():
                    covered.add(id(tree.proc))
            except Exception:
                pass
        for proc in procs:
            if id(proc) not in covered:
                self._ports["kill_tree"](proc)
