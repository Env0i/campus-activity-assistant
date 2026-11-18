# -*- coding: utf-8 -*-
"""桌面关停屏障与本实例资源的有序收尾。"""
from __future__ import annotations


class DesktopLifecycle:
    def __init__(self, *, lock, coordination, plan_manager, ports):
        self._lock = lock
        self._coord = coordination
        self._plan_manager = plan_manager
        self._ports = ports

    def _snapshot(self):
        with self._lock:
            if self._coord.closing:
                return self._coord.shutdown_done_event, None
            # 置关闭屏障与所有进程快照共用创建登记时的同一把锁。
            self._coord.closing = True
            return None, (self._plan_manager.plan,
                          list(self._coord.plan_procs.values()),
                          list(self._coord.plan_trees.values()),
                          list(self._coord.aux_procs),
                          list(self._coord.aux_trees.items()),
                          self._coord.proc, self._coord.proc_tree)

    def shutdown(self):
        self._ports["stop_tray"]()
        done, snapshot = self._snapshot()
        if done is not None:
            done.wait()
            return
        try:
            self._shutdown_services()
            plan, plan_procs, plan_trees, aux_procs, aux_trees, proc, proc_tree = snapshot
            if plan:
                try:
                    plan.stop()
                except Exception:
                    pass
            self._stop_plan_trees(plan_procs, plan_trees)
            self._stop_aux_trees(aux_procs, aux_trees)
            if proc_tree is not None:
                try:
                    proc_tree.terminate()
                except Exception:
                    pass
                finally:
                    proc_tree.close()
            elif proc and proc.poll() is None:
                self._ports["kill_tree"](proc)
        finally:
            self._coord.shutdown_done_event.set()

    def _shutdown_services(self):
        for service in self._ports["components"]():
            if service is not None:
                service.shutdown()
        self._ports["stop_auto_relogin"]()
        try:
            self._ports["shutdown_relay"]()
        except Exception:
            pass
        try:
            self._ports["stop_tunnel"]()
            self._ports["shutdown_phone"]()
            self._ports["clear_phone_channel"]()
        except Exception:
            pass

    def _stop_plan_trees(self, procs, trees):
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

    def _stop_aux_trees(self, procs, trees):
        covered = set()
        for proc, tree in trees:
            try:
                if tree.terminate():
                    covered.add(id(proc))
            except Exception:
                pass
        for proc in procs:
            if id(proc) not in covered:
                self._ports["kill_tree"](proc)
        for _proc, tree in trees:
            try:
                tree.close()
            except Exception:
                pass
