# -*- coding: utf-8 -*-
"""跨功能协调对象：一把普通锁、关闭屏障、四个在途槽位与四张进程登记表。

设计口径见 design/evidence/2026-11-17/api-coordination/design.md 第一节与
busy.md 的 G1/G2。拆分只搬状态与判定，不改语义：

- **一把不可重入 Lock**。关闭屏障（closing）、进程创建与登记、计划最终接纳
  共用它——快照取到时，任何「已开始创建」的进程必然已登记完成（closing.md
  第三节第 2 步），拆成两把锁这条保证就做不回来。
- **只持有「职责就是全局互斥」的状态**。`_activities`、`_last_check`、`_plan`
  这类业务缓存留在所属服务：别人读它们是为了快照而不是互斥。
- **持锁期间不调用任何服务**。唯一的读取是已发布计划状态端口：它返回
  PlanCoordinator 在锁外写入、锁外读取的不可变字符串，不取任何锁，因此
  不成环（test_concurrency_guards 的规则二/规则三守着这条）。
- 判定方法带 `_locked` 后缀：调用方必须已经持有 `lock`。这里不再自己取锁，
  否则同一线程会在这把不可重入锁上自锁。

@author Author
"""
from __future__ import annotations

import threading


class Coordinator:
    """协调锁与全局互斥状态的唯一持有者。

    `plan_state` 是无锁的只读端口，返回已发布计划状态（""、"ready"、"running"
    等）。判定里的短路顺序与拆分前 `Api._is_busy_locked` /
    `Api._cancel_busy_reason_locked` 逐行一致，返回值也不变。
    """

    def __init__(self, *, plan_state=None) -> None:
        # 关闭屏障、进程登记与计划最终接纳的同一把锁（不可重入）。
        self._lock = threading.Lock()
        # 已发布计划状态的只读端口：由组合根接到「当前计划」，无计划时返回空串。
        self._plan_state = plan_state or (lambda: "")
        # 关闭已开始：一旦为真不再接受新工作，也没有任何地方置回假。
        self.closing = False
        # 取消报名在途：G1/G2/G3/G4/G5/G10 都读它（busy.md 第三节第 4 条）。
        self.cancelling = False
        # 在途槽位：check / list / 组件事务各自单飞，但别家判定也要读。
        self.checking = False
        self.listing = False
        self.advanced_busy = False
        # 单 worker 与它的受管进程树：stop/shutdown 用它一网打尽 Playwright 后代。
        self.proc = None
        self.proc_tree = None
        # 计划任务登记表：进程与受管树（task_id -> ProcessTree）。
        self.plan_procs: dict[str, object] = {}
        self.plan_trees: dict = {}
        # check/list 这类短命 worker 的登记表：key 是进程对象，value 是受管树。
        self.aux_procs: set = set()
        self.aux_trees: dict = {}
        # 「收尾已完成」用同一个 Event 表达：后到的 shutdown 在锁外等它，
        # 返回即代表收尾真正完成（FB2）。
        self.shutdown_done_event = threading.Event()

    @property
    def lock(self) -> threading.Lock:
        """唯一那把协调锁；`Api._lock` 指向同一对象，旧字段读写语义不变。"""
        return self._lock

    # ---------- 忙碌判定（调用方持 lock） ----------
    def is_busy_locked(self) -> bool:
        """G1：有没有正在占着全局忙碌位的活。调用方持 lock。"""
        if self.cancelling:
            return True      # 取消报名占着同一把忙碌标记（X3）
        if self.proc and self.proc.poll() is None:
            return True
        # 只读协调器已发布的不可变状态：持协调锁时绝不取协调器锁（P2-1）。
        if self._plan_state() in {"ready", "running"}:
            return True
        return any(proc.poll() is None for proc in self.plan_procs.values())

    def cancel_busy_reason_locked(self) -> str:
        """G2：取消能不能开始，返回占用原因，空串表示空闲。调用方持 lock。"""
        if self.closing:
            return "closing"
        if self.cancelling:
            return "cancelling"
        if self._plan_state() in {"ready", "running"}:
            return "plan_running"
        if any(proc.poll() is None for proc in self.plan_procs.values()):
            return "plan_running"
        if self.proc and self.proc.poll() is None:
            return "task_running"
        if self.checking or self.listing or self.advanced_busy:
            return "refreshing"
        return ""


class CoordinatorFields:
    """把协调对象的状态以拆分前的旧字段名暴露给组合根的显式代理。

    `Api` 继承本类后，`api._closing`、`api._plan_procs` 这些旧名字的读写
    （含整表替换 `api._plan_procs = {...}`）语义与拆分前完全一致，动作代码
    一行不用改；状态的**唯一**归属仍是 `Coordinator`。属性放在这里而不是
    `app.py`，是为了不让纯转发的样板把外观文件再次撑大。
    """

    @property
    def _closing(self) -> bool: return self._coord.closing
    @_closing.setter
    def _closing(self, value: bool) -> None: self._coord.closing = value
    @property
    def _cancelling(self) -> bool: return self._coord.cancelling
    @_cancelling.setter
    def _cancelling(self, value: bool) -> None: self._coord.cancelling = value
    @property
    def _checking(self) -> bool: return self._coord.checking
    @_checking.setter
    def _checking(self, value: bool) -> None: self._coord.checking = value
    @property
    def _listing(self) -> bool: return self._coord.listing
    @_listing.setter
    def _listing(self, value: bool) -> None: self._coord.listing = value
    @property
    def _advanced_busy(self) -> bool: return self._coord.advanced_busy
    @_advanced_busy.setter
    def _advanced_busy(self, value: bool) -> None: self._coord.advanced_busy = value
    @property
    def _proc(self): return self._coord.proc
    @_proc.setter
    def _proc(self, value) -> None: self._coord.proc = value
    @property
    def _proc_tree(self): return self._coord.proc_tree
    @_proc_tree.setter
    def _proc_tree(self, value) -> None: self._coord.proc_tree = value
    @property
    def _plan_procs(self) -> dict: return self._coord.plan_procs
    @_plan_procs.setter
    def _plan_procs(self, value: dict) -> None: self._coord.plan_procs = value
    @property
    def _plan_trees(self) -> dict: return self._coord.plan_trees
    @_plan_trees.setter
    def _plan_trees(self, value: dict) -> None: self._coord.plan_trees = value
    @property
    def _aux_procs(self) -> set: return self._coord.aux_procs
    @_aux_procs.setter
    def _aux_procs(self, value: set) -> None: self._coord.aux_procs = value
    @property
    def _aux_trees(self) -> dict: return self._coord.aux_trees
    @_aux_trees.setter
    def _aux_trees(self, value: dict) -> None: self._coord.aux_trees = value
    @property
    def _shutdown_done_event(self) -> threading.Event: return self._coord.shutdown_done_event
    @_shutdown_done_event.setter
    def _shutdown_done_event(self, value: threading.Event) -> None: self._coord.shutdown_done_event = value
