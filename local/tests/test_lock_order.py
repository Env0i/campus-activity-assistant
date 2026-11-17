#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""锁序守卫：本仓库的锁只许按固定等级「由外层向里层」升序获取。

拆分 Api 时最大的风险是锁悄悄换了位置：把某段临界区搬进服务后，外层锁与内层锁的
先后关系一反转，现有用例照样全绿——因为死锁只在真并发下出现，而且往往几百次里才
撞上一次。本文件只读源码（ast 解析，绝不 import 产品代码），守三条不变量：

1. 等级只升：持等级 N 的锁时，只能再拿等级 > N 的锁（嵌套越深，号只会变大）。
   Api 与各服务类内部都查：每个 `with` 块的直接嵌套、以及块内经同类方法往下追
   ≤6 层拿到的锁都要升序；同号重入只允许冻结表里的 RLock 既有重入。
2. 协调锁不碰服务：持 `Api._lock` 期间只许调 `self._plan.published_status()`——
   它读的是锁外发布的不可变状态。别的服务调用一律不许进来，否则「Api 锁 → 服务锁」
   会和服务里「服务锁 → 回调 Api」的那条边成环。
3. 服务锁不碰注入端口：服务拿着自己的锁（或叶子锁）时不许调构造注入的端口——
   端口是界面层塞进来的回调，一旦它在里面反手取 Api 锁，环就成立。只有逐条核对
   过「它自己不取跨层锁」的叶子端口才在白名单里；唯一例外是发布端口 emit——
   已逐条核对过「持发布锁调它只会再取更高等级的锁」，记在 ORDERED_PORTS。

等级表（2026-11-23 发布锁定级返修：`_publish` 持发布锁调 emit 端口，端口接到
app.py:2958 的闭包会拿 Api._lock 与服务/事件锁，故发布锁必须在协调锁之外；
Api._lock 的取证见 design/evidence/2026-11-17/api-coordination/locks.md）：

    1  Api._credential_lock          凭据锁 RLock
    2  Api._phone_access_lock        手机访问锁 RLock
    3  PlanCoordinator._emit_lock    发布锁 Lock（_publish 持它调 emit 端口，
                                    端口实际会拿 Api._lock 与服务/事件锁）
    4  Api._lock                     协调锁 Lock（证据计 96 处 with / 64 个方法；
                                    嵌套 def 的获取处在证据里被重复归属，本扫描器
                                    按唯一获取处计 93 处）
    5  服务锁：LoginRelayService / AutoReloginMonitor / PhoneAccessService /
       AdvancedComponentService / UpdateService / PlanCoordinator 的 `_lock`
    6  叶子锁：PhoneAccessService._event_lock、模块级 _PHONE_LOG_LOCK 与
       _LIFECYCLE_LOCK

开工 HEAD 上就存在、但不在这一批修的存量违例记在冻结表里：实际必须**恰好**等于
冻结表——多一条说明这一批改坏了，少一条说明存量已经消失，要把对应条目删掉。

扫描口径（写清楚才守得住）：规则一同时看 Api 与 SERVICE_FILES 里的每个服务类——
直接嵌套的 `with` 与「经同类方法链 ≤6 层」拿到的锁都算；update_service 的模块级
函数（run_check/run_download/run_version_download）里 `state.X` 沿既有约定当
`self.X` 对待。嵌套 def 里的调用不算外层块的调用（闭包定义时不持锁）。规则二只看
Api；规则三进服务类，其中「持 _emit_lock 调 emit」单独记进 ORDERED_PORTS。另有
一道独立断言钉住 P2-1：PlanCoordinator 对 `self._publish` 的调用（直接、或经同类
方法链 ≤6 层追到的）一律不许出现在 `with self._lock:` 块内——状态写入在锁内、
事件发布在锁外；谁把发布挪进锁内，这道断言与规则一（_lock(5)→_emit_lock(3)
降级）两道都抓。

@author Author
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
LOCAL_DIR = TESTS_DIR.parent
APP_FILE = LOCAL_DIR / "app.py"

# 服务模块：锁等级 5/6 的持有者（相对 local/ 的路径即源码里的模块键）
SERVICE_FILES = (
    "application/login_relay_service.py",
    "application/auto_relogin.py",
    "application/phone_service.py",
    "application/advanced_component_service.py",
    "application/update_service.py",
    "application/plan_service.py",
    "signup_plan.py",
)

# 等级表：键是「类名.属性名」，模块级锁直接用名字
LEVELS: dict[str, int] = {
    "Api._credential_lock": 1,
    "Api._phone_access_lock": 2,
    "PlanCoordinator._emit_lock": 3,
    "Api._lock": 4,
    "LoginRelayService._lock": 5,
    "AutoReloginMonitor._lock": 5,
    "PhoneAccessService._lock": 5,
    "AdvancedComponentService._lock": 5,
    "UpdateService._lock": 5,
    "PlanCoordinator._lock": 5,
    "PhoneAccessService._event_lock": 6,
    "_PHONE_LOG_LOCK": 6,
    "_LIFECYCLE_LOCK": 6,
}

SERVICE_CLASSES = (
    "LoginRelayService", "AutoReloginMonitor", "PhoneAccessService",
    "AdvancedComponentService", "UpdateService", "PlanCoordinator",
)

# 同号重入的冻结老账（Api 侧）：三条都是「持 _phone_access_lock 又调 stop_phone_access()」。
# 下一批改用不取锁的 _stop_phone_access() 后，这份表应删空。
FROZEN_REENTRY: tuple[tuple[str, str, str], ...] = (
    # app.py install_advanced_feature:1664 —— 停手机访问前先换包，历史写法
    ("install_advanced_feature", "Api._phone_access_lock", "Api._phone_access_lock"),
    # app.py _install_selected_feature:1712 —— 同上，导入组件的共用通道
    ("_install_selected_feature", "Api._phone_access_lock", "Api._phone_access_lock"),
    # app.py remove_advanced_feature:1740 —— 移除手机控制组件前先停服务
    ("remove_advanced_feature", "Api._phone_access_lock", "Api._phone_access_lock"),
)

# 服务类内部的同号重入（均为 RLock 的既有重入）：实际必须恰好等于这张表。
# 键是「类.方法」——服务类之间方法重名（如 snapshot），裸方法名分不清归属。
FROZEN_SERVICE_REENTRY: tuple[tuple[str, str, str], ...] = (
    # signup_plan.py cancel_task:380 —— 持 _lock 调 _set_state_locked，它在
    # signup_plan.py:537 自己再进一次 _lock（RLock 重入；锁内只改状态不回调）
    ("PlanCoordinator.cancel_task", "PlanCoordinator._lock", "PlanCoordinator._lock"),
    # signup_plan.py stop:395 —— 停止路径在锁内把未启动场次落终态，同上调
    # _set_state_locked:537 再进一次 _lock
    ("PlanCoordinator.stop", "PlanCoordinator._lock", "PlanCoordinator._lock"),
)

# 持协调锁时唯一放行的服务调用：published_status 只读锁外发布的不可变字符串。
# 三处都是同一句 `self._plan.published_status()`（证据里的「恰好一个服务方法」
# 指方法而不是调用处）；三个方法都注明「调用方持 self._lock」。
FROZEN_COORD_CALLS: tuple[tuple[str, str], ...] = (
    # app.py:2397 _cancel_busy_reason_locked（docstring：调用方持 self._lock）
    ("_cancel_busy_reason_locked", "self._plan.published_status"),
    # app.py:4295 _is_busy_locked（busy 判定只读已发布状态，P2-1）
    ("_is_busy_locked", "self._plan.published_status"),
    # app.py:2631 login（持 _lock 复核计划是否在跑）
    ("login", "self._plan.published_status"),
)

# 叶子端口白名单：逐条核对过「它自己不取跨层锁」的注入端口。
# 键是（类, 端口属性）；注释写清真实接线与为什么不构成环。
LEAF_PORTS: tuple[tuple[str, str], ...] = (
    # 接线 app.py:960 now=time.monotonic：只读单调钟，不取任何锁
    ("LoginRelayService", "_now"),
    # 接线 app.py:973 now=time.monotonic：同上
    ("AutoReloginMonitor", "_now"),
    # 接线 app.py:900 now=self._clock_now → business_clock.BusinessClock.now:307，
    # 只可重入自己的 RLock（叶子，持锁期间不外调），5→叶子 是升序
    ("PhoneAccessService", "_now"),
    # 接线 app.py:975 log=self._log_event:1949：只拿 grab.log 的跨进程文件锁（叶子）
    ("AutoReloginMonitor", "_log"),
    # 接线 app.py:902 log=phone_log:151：只拿 _PHONE_LOG_LOCK（等级 6 叶子）
    ("PhoneAccessService", "_log"),
    # 接线 app.py:883 is_closing=self._update_is_closing:2055：只读一个布尔，不取锁
    ("UpdateService", "_is_closing"),
    # 接线 AdvancedComponentService 未注入 version → component_packages.version:88，
    # 只读 VERSION 文件，无锁
    ("AdvancedComponentService", "_version"),
)

# 已核对过取锁顺序的发布端口（键：(模块, 方法, 端口)）：持 _emit_lock（等级 3）
# 调它们时，端口接到的代码只会再取更高等级的锁，顺序成立不成环。这张表必须与
# 扫描器实际发现的「持 _emit_lock 调端口」恰好相等；存量消失时条目只许删。
ORDERED_PORTS: tuple[tuple[str, str, str], ...] = (
    # signup_plan.py _publish:353 持 _emit_lock 调 emit 端口。端口接到 app.py:2958
    # _start_plan_inner 里定义的闭包：非 plan_done 事件先在 with self._lock
    # （app.py:2968，等级 4）里对账，再调 Api._emit（app.py:1094）；plan_done
    # 路径在 app.py:2983 再进 with self._lock。Api._emit 又会碰
    # LoginRelayService 的状态投影（relay._lock，等级 5）与
    # PhoneAccessService.record_event（_event_lock，等级 6）。这些锁全都高于
    # 持有的 _emit_lock（3），等级只升、不成环——这正是发布锁必须排在协调锁
    # 之外的原因。
    ("signup_plan.py", "_publish", "emit"),
)

# 服务锁期间调端口的冻结老账：(模块, 方法, 端口)。每条都是既存事实，不在这一批修。
# 原第四条（signup_plan.py _publish 持 _emit_lock 调 emit）经取锁顺序核对后
# 挪进上面的 ORDERED_PORTS——它是发布锁定级的依据，不是待修存量。
FROZEN_PORTS: tuple[tuple[str, str, str], ...] = (
    # advanced_component_service.py snapshot:138 → _refresh_idle_state:112 取 _status，
    # 而 _status 实际是 component_packages.feature_status → status:701 会取 _LOCK
    ("application/advanced_component_service.py", "snapshot", "_status"),
    # phone_service.py pair:280 持 _lock 写设备信任，PhoneSessionStore.add_device:62
    # 取自己的 RLock（等级表外的底层锁）
    ("application/phone_service.py", "pair", "_device_store"),
    # phone_service.py authenticate_or_restore:369 同上，validate_device:82 取同一把锁
    ("application/phone_service.py", "authenticate_or_restore", "_device_store"),
)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _dotted(node: ast.AST) -> str:
    """`self._relay.cancel` 这类属性链拼成点号串；拼不出来返回空串。"""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return ""
    parts.append(node.id)
    return ".".join(reversed(parts))


def _last_name(node: ast.AST) -> str:
    """表达式链尾的名字：`_update_service.UpdateService` → `UpdateService`。"""
    dotted = _dotted(node)
    return dotted.rsplit(".", 1)[-1] if dotted else ""


def _lock_id(expr: ast.AST, owner: str | None, module: str) -> str | None:
    """`with` 目标表达式 → 等级表里的锁名字；认不出返回 None。

    - `self.<attr>`：归属当前类（Api 或某个服务类）；
    - 模块级 `_XXX_LOCK`：名字本身；
    - update_service 里的 `state._lock`：那个 `state` 就是 UpdateService 实例；
    - plan_service.run_plan_task 的 `lock` 形参：唯一调用方传的是 Api._lock
      （app.py:4313），因此按 Api._lock 计获取处；它不参与规则一的嵌套分析。
    """
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        base, attr = expr.value.id, expr.attr
        lock = ""
        if base == "self" and owner:
            lock = "%s.%s" % (owner, attr)
        elif base == "state" and module == "application/update_service.py":
            lock = "UpdateService.%s" % attr
        return lock if lock in LEVELS else None
    if isinstance(expr, ast.Name):
        if expr.id == "lock" and module == "application/plan_service.py":
            return "Api._lock"
        return expr.id if expr.id in LEVELS else None
    return None


def _iter_withs(fn: ast.AST, owner: str | None, module: str):
    """函数体里每个 `with`：产出 (节点, 外层锁元组, 本块锁元组)。

    嵌套 def 里的 `with` 也计入（它确实在同一个实例上取同一把锁），但外层锁从零
    算起——闭包是定义时创建、调用时才执行，定义它的那一刻并不持锁。

    `with A, B:` 按书写顺序当作「先 A 后 B」依次获取：本仓库的多项目写法只有
    「凭据锁 → 手机访问锁」（1→2，升序）与「Api 锁 → 服务锁」，所以按顺序比较
    既符合实际也可能被破坏。`with (...)` 的换行写法由 ast 归一，同样适用。
    """
    found: list[tuple[ast.With, tuple[str, ...], tuple[str, ...]]] = []

    def visit(node: ast.AST, outer: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visit(child, ())
                continue
            if isinstance(child, ast.Lambda):
                continue
            if isinstance(child, ast.With):
                ids = tuple(lock for lock in (_lock_id(item.context_expr, owner, module)
                                              for item in child.items) if lock)
                found.append((child, outer, ids))
                visit(child, outer + ids)
            else:
                visit(child, outer)

    visit(fn, ())
    return found


def _calls_in(node: ast.AST):
    """块内（语句级包含）的 Call 节点；嵌套 def/类的函数体不算——定义时不执行。"""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                              ast.Lambda)):
            continue
        if isinstance(child, ast.Call):
            yield child
        yield from _calls_in(child)


class _LockGraph:
    """一次扫描的索引：类、方法、服务属性、锁获取处，以及同类的调用闭包。"""

    def __init__(self, trees: dict[str, ast.Module]):
        self.trees = trees
        self.classes: dict[tuple[str, str], ast.ClassDef] = {}
        self.functions: dict[tuple[str, str], ast.AST] = {}
        for module, tree in trees.items():
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    self.classes[(module, node.name)] = node
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.functions[(module, node.name)] = node
        self.api_key = ("app.py", "Api")
        self._methods: dict[tuple[str, str], dict[str, ast.AST]] = {}
        self._attrs: dict[str, tuple[str, str]] | None = None

    def methods(self, key: tuple[str, str]) -> dict[str, ast.AST]:
        if key not in self._methods:
            cls = self.classes.get(key)
            self._methods[key] = {} if cls is None else {
                node.name: node for node in cls.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        return self._methods[key]

    def _ctor(self, value: ast.AST, fn: ast.AST) -> tuple[str, str] | None:
        """构造调用 → (模块, 类名)：认服务类名，也认先把实例存局部变量再赋值的写法。"""
        if isinstance(value, ast.Call):
            return self._known(_last_name(value.func))
        if isinstance(value, ast.Name):
            for node in ast.walk(fn):
                if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                    continue
                if any(isinstance(t, ast.Name) and t.id == value.id for t in node.targets):
                    return self._known(_last_name(node.value.func))
        return None

    def _known(self, name: str) -> tuple[str, str] | None:
        for key in self.classes:
            if key[1] == name and name in SERVICE_CLASSES:
                return key
        return None

    def service_attrs(self) -> dict[str, tuple[str, str]]:
        """Api 的 `self.<属性>` → 服务类。来源是 Api 各方法里的 `self.x = 构造()`。"""
        if self._attrs is not None:
            return self._attrs
        mapping: dict[str, tuple[str, str]] = {}
        for fn in self.methods(self.api_key).values():
            for node in ast.walk(fn):
                if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                    continue
                target = node.targets[0]
                if not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                        and target.value.id == "self"):
                    continue
                key = self._ctor(node.value, fn)
                if key is not None:
                    mapping[target.attr] = key
        self._attrs = mapping
        return mapping

    def service_keys(self) -> list[tuple[str, str]]:
        return [key for key in self.classes if key[1] in SERVICE_CLASSES]

    def closure_locks(self, key: tuple[str, str], method: str, depth: int = 0,
                      seen: frozenset[str] = frozenset()) -> set[str]:
        """方法（含同类方法调用，6 层）可能获取的锁；认不出就是空集。"""
        fn = self.methods(key).get(method)
        if fn is None or depth > 6 or method in seen:
            return set()
        out = {lock for _, _, ids in _iter_withs(fn, key[1], key[0]) for lock in ids}
        for call in _calls_in(fn):
            parts = _dotted(call.func).split(".")
            if len(parts) == 2 and parts[0] == "self" and parts[1] in self.methods(key):
                out |= self.closure_locks(key, parts[1], depth + 1, seen | {method})
        return out

    def callee_locks(self, call: ast.Call) -> set[str]:
        """块内一次调用可能获取的锁：Api 方法链（≤6 层）或一层进服务类。"""
        parts = _dotted(call.func).split(".")
        if len(parts) == 2 and parts[0] == "self":
            return self.closure_locks(self.api_key, parts[1])
        if len(parts) == 3 and parts[0] == "self":
            key = self.service_attrs().get(parts[1])
            if key is not None:
                return self.closure_locks(key, parts[2])
        return set()

    def ports(self, key: tuple[str, str]) -> dict[str, str]:
        """构造注入的端口：`__init__` 形参被赋到哪个 self 属性上。

        认 `self._x = param`、`self._x = param or 默认`、`self.x = param if ... else ...`；
        `self._next = now() + 1` 这种「用形参算出的值」不算端口（它不可调用）。
        """
        fn = self.methods(key).get("__init__")
        if fn is None:
            return {}
        params = {arg.arg for arg in list(fn.args.args) + list(fn.args.kwonlyargs)}
        params.discard("self")
        found: dict[str, str] = {}
        for node in ast.walk(fn):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            attr = next((t.attr for t in targets if isinstance(t, ast.Attribute)
                         and isinstance(t.value, ast.Name) and t.value.id == "self"), "")
            param = _port_param(node.value, params)
            if attr and param:
                found[attr] = param
        return found

    def acquisitions(self) -> dict[str, int]:
        """每把锁的获取处（`with` 里的一项算一处，多项目按书写顺序各算一处）。"""
        counts: dict[str, int] = {}
        for (module, _name), fn in self.functions.items():
            for _, _, ids in _iter_withs(fn, None, module):
                for lock in ids:
                    counts[lock] = counts.get(lock, 0) + 1
        for key in self.classes:
            for fn in self.methods(key).values():
                for _, _, ids in _iter_withs(fn, key[1], key[0]):
                    for lock in ids:
                        counts[lock] = counts.get(lock, 0) + 1
        return counts

    def blocks(self):
        """全部 `with`：产出 (模块, 归属方法名, 节点, 外层锁, 本块锁)。"""
        for (module, name), fn in self.functions.items():
            for node, outer, ids in _iter_withs(fn, None, module):
                yield module, name, node, outer, ids
        for key in self.classes:
            for name, fn in self.methods(key).items():
                for node, outer, ids in _iter_withs(fn, key[1], key[0]):
                    yield key[0], name, node, outer, ids


def _port_param(value: ast.AST, params: set[str]) -> str:
    """赋值右侧是不是「就是这个形参」：Name / `param or 默认` / `param if .. else ..`。"""
    if isinstance(value, ast.Name):
        return value.id if value.id in params else ""
    if isinstance(value, ast.BoolOp) and isinstance(value.values[0], ast.Name):
        return value.values[0].id if value.values[0].id in params else ""
    if isinstance(value, ast.IfExp) and isinstance(value.body, ast.Name):
        return value.body.id if value.body.id in params else ""
    return ""


def _deepest(holding) -> str | None:
    """当前最深的那把锁（等级最高者）——后拿的锁只需比它大。"""
    locks = list(holding)
    return max(locks, key=lambda lock: LEVELS[lock]) if locks else None


def _judge(record: dict, method: str, line: int, holding, inner: str) -> None:
    base = _deepest(holding)
    if base is None:
        return
    if LEVELS[inner] < LEVELS[base]:
        record["down"].append((method, line, base, inner))
    elif LEVELS[inner] == LEVELS[base]:
        record["equal"].append((method, line, base, inner))


def _rule_one(graph: _LockGraph) -> dict[str, list[tuple]]:
    """持等级 N 时只许拿等级 > N：直接嵌套 + Api 方法链 + 一层进服务类。"""
    record: dict[str, list[tuple]] = {"down": [], "equal": []}
    for name, fn in graph.methods(graph.api_key).items():
        for node, outer, ids in _iter_withs(fn, "Api", "app.py"):
            holding = list(outer)
            for inner in ids:
                _judge(record, name, node.lineno, holding, inner)
                holding.append(inner)      # `with A, B:` 按书写顺序当作依次获取
            for call in _calls_in(node):
                for lock in graph.callee_locks(call):
                    _judge(record, name, call.lineno, holding, lock)
    return {kind: sorted(set(items)) for kind, items in record.items()}


def _rule_one_services(graph: _LockGraph) -> dict[str, list[tuple]]:
    """规则一的服务类部分：SERVICE_FILES 每个服务类内部等级只许升。

    与 Api 同口径：每个 `with` 块的直接嵌套、以及块内经同类方法（≤6 层）拿到的
    锁都要升序。记录的归属名是「类.方法」（服务类之间方法重名，裸名分不清）。
    update_service 的模块级函数（run_check/run_download/run_version_download）
    里 `state._lock` 就是那个 UpdateService 实例的锁、`state.X()` 就是它的方法
    （既有约定，见 _lock_id 的注释），按同类规则查。
    """
    record: dict[str, list[tuple]] = {"down": [], "equal": []}

    def scan(fn: ast.AST, key: tuple[str, str], label: str, base: str) -> None:
        for node, outer, ids in _iter_withs(fn, key[1], key[0]):
            holding = list(outer)
            for inner in ids:
                _judge(record, label, node.lineno, holding, inner)
                holding.append(inner)
            for call in _calls_in(node):
                parts = _dotted(call.func).split(".")
                if len(parts) == 2 and parts[0] == base and parts[1] in graph.methods(key):
                    for lock in graph.closure_locks(key, parts[1]):
                        _judge(record, label, call.lineno, holding, lock)

    for key in graph.service_keys():
        for name, fn in graph.methods(key).items():
            scan(fn, key, "%s.%s" % (key[1], name), "self")
    state_key = ("application/update_service.py", "UpdateService")
    for (module, name), fn in graph.functions.items():
        if module == state_key[0]:
            scan(fn, state_key, name, "state")
    return {kind: sorted(set(items)) for kind, items in record.items()}


def _service_calls(graph: _LockGraph, node: ast.AST, attrs, owner: str,
                   depth: int = 0, seen: frozenset[str] = frozenset()) -> list[tuple[str, str]]:
    """块内对 `self.<服务>.<方法>()` 的调用；经 Api 方法最多追 6 层。

    owner 是这条调用**写在哪个方法里**（追进去以后就换成被调方法），这样冻结表
    记的是真实源码位置，而不是从哪个入口一路持锁下来的。
    """
    out: list[tuple[str, str]] = []
    for call in _calls_in(node):
        dotted = _dotted(call.func)
        parts = dotted.split(".")
        if len(parts) == 3 and parts[0] == "self" and parts[1] in attrs:
            out.append((owner, dotted))
        elif len(parts) == 2 and parts[0] == "self" and parts[1] in graph.methods(graph.api_key):
            if depth < 6 and parts[1] not in seen:
                callee = graph.methods(graph.api_key)[parts[1]]
                out += _service_calls(graph, callee, attrs, parts[1],
                                      depth + 1, seen | {parts[1]})
    return out


def _rule_two(graph: _LockGraph) -> list[tuple[str, str]]:
    """持 Api._lock 时只许调 self._plan.published_status()。

    只认 `self.<服务属性>.<方法>()` 这种写法：`plan = self._plan` 的局部别名
    （app.py 里 7 处 snapshot/start）不追。开工 HEAD 上这 7 处全部落在 with 之外
    （逐个核过外层 with 栈为空）；将来若有人在持锁块里用别名调服务，规则二看不见
    ——真要这么改，先把别名解析补进这里。
    """
    attrs = graph.service_attrs()
    hits: list[tuple[str, str]] = []
    for name, fn in graph.methods(graph.api_key).items():
        for node, _outer, ids in _iter_withs(fn, "Api", "app.py"):
            if "Api._lock" in ids:
                hits.extend(_service_calls(graph, node, attrs, name))
    return sorted(set(hits))


def _port_calls(graph: _LockGraph, key: tuple[str, str], node: ast.AST, ports,
                depth: int = 0, seen: frozenset[str] = frozenset()) -> list[tuple[int, str]]:
    """块内对注入端口的调用（含同类方法递归 6 层，端口按属性名归一）。"""
    out: list[tuple[int, str]] = []
    for call in _calls_in(node):
        parts = _dotted(call.func).split(".")
        if len(parts) < 2 or parts[0] not in ("self", "state"):
            continue
        attr = parts[1]
        if attr in ports:
            out.append((call.lineno, attr))
        elif depth < 6 and parts[1] in graph.methods(key) and parts[1] not in seen:
            callee = graph.methods(key)[parts[1]]
            out += _port_calls(graph, key, callee, ports, depth + 1, seen | {parts[1]})
    return out


def _rule_three(graph: _LockGraph) -> set[tuple[str, str, str, str]]:
    """服务持自己的锁（或叶子锁）时调了哪些注入端口：(模块, 类, 方法, 端口)。"""
    found: set[tuple[str, str, str, str]] = set()
    for key in graph.service_keys():
        ports = graph.ports(key)
        for name, fn in graph.methods(key).items():
            for node, _outer, ids in _iter_withs(fn, key[1], key[0]):
                if not any(lock.startswith(key[1] + ".") for lock in ids):
                    continue
                for _line, port in _port_calls(graph, key, node, ports):
                    found.add((key[0], key[1], name, port))
    # update_service 的 run_check/run_download 是模块级函数，`state._lock` 就是
    # 那个 UpdateService 实例的锁：按同类规则查（模块级函数里没有 self）。
    key = ("application/update_service.py", "UpdateService")
    ports = graph.ports(key)
    for (module, name), fn in graph.functions.items():
        if module != key[0]:
            continue
        for node, _outer, ids in _iter_withs(fn, key[1], module):
            if not any(lock.startswith(key[1] + ".") for lock in ids):
                continue
            for _line, port in _port_calls(graph, key, node, ports):
                found.add((module, key[1], name, port))
    return found


def _ordered_ports(graph: _LockGraph) -> set[tuple[str, str, str]]:
    """持 PlanCoordinator._emit_lock 期间调到的注入端口：(模块, 方法, 端口)。

    发布锁（等级 3）持锁调 emit 是本仓库唯一「持锁调端口、端口会再取更高等级锁」
    的有意设计（P2-1 的锁外发布 + 串行化）；这些位置必须与 ORDERED_PORTS 恰好
    相等——多一条是新的未核对端口，少一条说明存量已消失，要删表。
    """
    found: set[tuple[str, str, str]] = set()
    key = ("signup_plan.py", "PlanCoordinator")
    ports = graph.ports(key)
    for name, fn in graph.methods(key).items():
        for node, _outer, ids in _iter_withs(fn, key[1], key[0]):
            if "PlanCoordinator._emit_lock" not in ids:
                continue
            for _line, port in _port_calls(graph, key, node, ports):
                found.add((key[0], name, port))
    return found


def _publish_inside_coord_lock(graph: _LockGraph) -> list[tuple[str, int]]:
    """持 PlanCoordinator._lock 期间（直接或经同类方法链 ≤6 层）调到 _publish 的位置。

    P2-1：状态写入在 _lock 内、事件发布一律在锁外（今天调用处是 start:368、
    cancel_task:383、stop:402、_run:484、_set_state:532，全在锁外）。谁把发布
    挪进锁内，这里就红；那时 _lock(5)→_emit_lock(3) 同时也是规则一的降级，
    两道都抓。
    """
    key = ("signup_plan.py", "PlanCoordinator")
    hits: list[tuple[str, int]] = []

    def reach(node: ast.AST, depth: int, seen: frozenset[str]) -> None:
        for call in _calls_in(node):
            parts = _dotted(call.func).split(".")
            if len(parts) != 2 or parts[0] != "self":
                continue
            if parts[1] == "_publish":
                hits.append((key[1], call.lineno))
            elif depth < 6 and parts[1] in graph.methods(key) and parts[1] not in seen:
                reach(graph.methods(key)[parts[1]], depth + 1, seen | {parts[1]})

    for name, fn in graph.methods(key).items():
        for node, _outer, ids in _iter_withs(fn, key[1], key[0]):
            if "PlanCoordinator._lock" in ids:
                reach(node, 0, frozenset({name}))
    return sorted(set(hits))


def _unknown_locks(graph: _LockGraph) -> list[tuple[str, str, int, str]]:
    """名字里带 lock 却不在等级表里的 `with` 目标：新锁必须先上等级表。"""
    found: list[tuple[str, str, int, str]] = []
    for module, method, node, _outer, _ids in graph.blocks():
        for item in node.items:
            shown = _dotted(item.context_expr)
            if not shown:
                continue
            tail = shown.rsplit(".", 1)[-1]
            if "lock" not in tail.lower():
                continue
            owner = _owner_class(graph, module, method)
            if _lock_id(item.context_expr, owner, module) is None:
                found.append((module, method, node.lineno, shown))
    return found


def _owner_class(graph: _LockGraph, module: str, method: str) -> str | None:
    for key in graph.classes:
        if key[0] == module and method in graph.methods(key):
            return key[1]
    return None


def _load_graph() -> _LockGraph:
    trees = {"app.py": _parse(APP_FILE)}
    for rel in SERVICE_FILES:
        trees[rel] = _parse(LOCAL_DIR / rel)
    return _LockGraph(trees)


def scan_all() -> dict[str, object]:
    """一次扫描的全部结论（测试与排障共用；排障时直接打印这个字典）。"""
    graph = _load_graph()
    rule_one = _rule_one(graph)
    rule_one_services = _rule_one_services(graph)
    return {
        "counts": graph.acquisitions(),
        "down": rule_one["down"],
        "equal": rule_one["equal"],
        "service_down": rule_one_services["down"],
        "service_equal": rule_one_services["equal"],
        "coord_calls": _rule_two(graph),
        "ports": _rule_three(graph),
        "ordered_ports": _ordered_ports(graph),
        "publish_in_lock": _publish_inside_coord_lock(graph),
        "unknown": _unknown_locks(graph),
        "service_attrs": {attr: key[1] for attr, key in graph.service_attrs().items()},
    }


class LockOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = scan_all()

    def test_scanner_recognizes_the_inventoried_acquisitions(self):
        """扫描器必须看得见证据里数过的锁：认少了说明守卫是空的。"""
        counts = self.report["counts"]
        self.assertGreaterEqual(counts.get("Api._lock", 0), 90,
                                "Api._lock 获取处：%s" % (counts.get("Api._lock"),))
        self.assertGreaterEqual(counts.get("Api._credential_lock", 0), 12,
                                "凭据锁获取处：%s" % (counts.get("Api._credential_lock"),))
        self.assertGreaterEqual(counts.get("Api._phone_access_lock", 0), 9,
                                "手机访问锁获取处：%s" % (counts.get("Api._phone_access_lock"),))
        self.assertEqual(sorted(set(self.report["service_attrs"].values())),
                         sorted(SERVICE_CLASSES), "Api 里认不全服务属性")

    def test_new_locks_must_be_leveled(self):
        """新出现的 *_lock 必须先写进等级表，不能就这么用了。"""
        self.assertEqual(self.report["unknown"], [],
                         "这些锁不在等级表里：%s" % (self.report["unknown"],))

    def test_lock_level_only_rises(self):
        """持一把锁时只许拿更高等级的锁：Api 内降级一律不许。"""
        self.assertEqual(self.report["down"], [],
                         "Api 锁序降级的获取处：%s" % (self.report["down"],))

    def test_reentry_equals_the_frozen_legacy_list(self):
        """同号重入必须恰好是冻结的三条（都走 RLock）；多一条少一条都要改表。"""
        actual = sorted({(method, outer, inner)
                         for method, _line, outer, inner in self.report["equal"]})
        self.assertEqual(actual, sorted(set(FROZEN_REENTRY)))

    def test_service_lock_level_only_rises(self):
        """服务类内部同样只许升序：降级一条都不许有（开工清点时无存量）。"""
        self.assertEqual(self.report["service_down"], [],
                         "服务类锁序降级的获取处：%s" % (self.report["service_down"],))

    def test_service_reentry_equals_the_frozen_legacy_list(self):
        """服务类内部的同号重入必须恰好是冻结的两条（RLock 既有重入）。"""
        actual = sorted({(method, outer, inner)
                         for method, _line, outer, inner in self.report["service_equal"]})
        self.assertEqual(actual, sorted(set(FROZEN_SERVICE_REENTRY)))

    def test_coordination_lock_calls_only_published_status(self):
        """持协调锁时只许读锁外发布的计划状态。"""
        self.assertEqual(sorted(set(self.report["coord_calls"])),
                         sorted(set(FROZEN_COORD_CALLS)))
        self.assertEqual(_published_status_body(),
                         "return str(self._status_cache)",
                         "published_status 变复杂了，规则二的放行理由要重核")

    def test_service_locks_avoid_injected_ports(self):
        """服务持锁时不碰注入端口；白名单/有序端口/冻结表必须恰好覆盖全部实际情况。"""
        frozen = set(FROZEN_PORTS)
        allowed = set(LEAF_PORTS)
        ordered = set(ORDERED_PORTS)
        actual = self.report["ports"]
        extra = sorted(item for item in actual
                       if (item[0], item[2], item[3]) not in frozen
                       and (item[0], item[2], item[3]) not in ordered
                       and (item[1], item[3]) not in allowed)
        self.assertEqual(extra, [], "服务持锁期间调了新的注入端口：%s" % (extra,))
        seen = {(module, method, port) for module, _cls, method, port in actual}
        self.assertEqual(sorted(frozen - seen), [],
                         "冻结表里这些已经不再违规，请删掉（清单只许变短）")
        used = {(cls, port) for _module, cls, _method, port in actual}
        self.assertEqual(sorted(allowed - used), [],
                         "白名单里这些端口当前没被持锁调用，核对记录已过期")

    def test_ordered_ports_match_the_scanner(self):
        """持发布锁调端口的位置必须恰好等于 ORDERED_PORTS（只许因存量消失变短）。"""
        self.assertEqual(sorted(self.report["ordered_ports"]),
                         sorted(set(ORDERED_PORTS)),
                         "持 _emit_lock 调端口的位置与 ORDERED_PORTS 不符：%s"
                         % (sorted(self.report["ordered_ports"]),))

    def test_publish_stays_outside_the_coordinator_lock(self):
        """P2-1：协调器的事件发布一律在状态锁外（锁内只写状态，不碰回调）。"""
        self.assertEqual(self.report["publish_in_lock"], [],
                         "持 PlanCoordinator._lock 期间调到了 _publish：%s"
                         % (self.report["publish_in_lock"],))


def _published_status_body() -> str:
    """PlanCoordinator.published_status 的函数体源码（锁外可读的最后一环）。

    规则二完全依赖「它不取协调器锁、也不调任何端口」：signup_plan.py:347-349
    的实现只有一行 `return str(self._status_cache)`，缓存写在 _lock 内、读在锁外。
    """
    tree = _parse(LOCAL_DIR / "signup_plan.py")
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "PlanCoordinator":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "published_status":
                    return ast.unparse(item).split("\n")[-1].strip()
    return ""


class ScannerSelfTests(unittest.TestCase):
    """守卫自己也要被守住：合成一段写得出的违规，每类都必须被抓到。"""

    @classmethod
    def setUpClass(cls):
        cls.graph = _LockGraph({
            "app.py": _parse_text("""
class Api:
    def __init__(self):
        self._lock = object()
        self._credential_lock = object()
        self._phone = PhoneAccessService()
        self._relay = LoginRelayService()

    def down(self):
        with self._lock:
            with self._credential_lock:
                pass

    def new_lock(self):
        with self._x_lock:
            pass

    def service_call(self):
        with self._lock:
            self._relay.cancel()

    def api_chain(self):
        with self._lock:
            self._helper()

    def _helper(self):
        self._phone.pair()
"""),
            "application/login_relay_service.py": _parse_text("""
class LoginRelayService:
    def __init__(self, *, now):
        self._now = now
        self._lock = object()

    def cancel(self):
        with self._lock:
            self._now()
"""),
            "application/phone_service.py": _parse_text("""
class PhoneAccessService:
    def __init__(self, *, api):
        self._api = api
        self._lock = object()
        self._event_lock = object()

    def pair(self):
        with self._lock:
            self._api.start_plan()

    def service_down(self):
        with self._event_lock:
            with self._lock:
                pass
"""),
        })

    def test_flags_a_level_down_acquisition(self):
        self.assertEqual(_rule_one(self.graph)["down"],
                         [("down", 10, "Api._lock", "Api._credential_lock")])

    def test_flags_an_unleveled_new_lock(self):
        self.assertEqual(_unknown_locks(self.graph),
                         [("app.py", "new_lock", 14, "self._x_lock")])

    def test_flags_a_service_port_under_a_service_lock(self):
        self.assertEqual(_rule_three(self.graph),
                         {("application/login_relay_service.py", "LoginRelayService",
                           "cancel", "_now"),
                          ("application/phone_service.py", "PhoneAccessService",
                           "pair", "_api")})

    def test_flags_a_service_call_under_the_coordination_lock(self):
        self.assertEqual(_rule_two(self.graph),
                         [("_helper", "self._phone.pair"),
                          ("service_call", "self._relay.cancel")])

    def test_flags_a_service_level_down_acquisition(self):
        """服务类内部的降级嵌套也必须被抓到：持事件锁（6）再拿服务锁（5）不行。"""
        self.assertEqual(_rule_one_services(self.graph)["down"],
                         [("PhoneAccessService.service_down", 13,
                           "PhoneAccessService._event_lock",
                           "PhoneAccessService._lock")])
        self.assertEqual(_rule_one_services(self.graph)["equal"], [])

    def test_flags_publish_inside_the_coordinator_lock(self):
        """把 _publish 挪进协调器锁内：锁外发布断言与规则一降级两道都抓。"""
        graph = _LockGraph({"signup_plan.py": _parse_text("""
class PlanCoordinator:
    def __init__(self, *, runner, emit):
        self.runner = runner
        self.emit = emit
        self._lock = object()
        self._emit_lock = object()

    def evil(self):
        with self._lock:
            self._publish("task", {})

    def _publish(self, kind, payload):
        with self._emit_lock:
            self.emit(kind, payload)
""")})
        self.assertEqual(_publish_inside_coord_lock(graph),
                         [("PlanCoordinator", 10)])
        self.assertEqual(_rule_one_services(graph)["down"],
                         [("PlanCoordinator.evil", 10, "PlanCoordinator._lock",
                           "PlanCoordinator._emit_lock")])
        self.assertEqual(_ordered_ports(graph),
                         {("signup_plan.py", "_publish", "emit")})

    def test_does_not_descend_into_nested_definitions(self):
        """`with` 里的闭包是定义不是调用：闭包体内取锁不算在外层块里。"""
        graph = _LockGraph({"app.py": _parse_text("""
class Api:
    def build(self):
        with self._lock:
            def later():
                with self._credential_lock:
                    pass
            return later
""")})
        self.assertEqual(_rule_one(graph)["down"], [])
        self.assertEqual(_rule_one(graph)["equal"], [])


def _parse_text(source: str) -> ast.Module:
    return ast.parse(source.lstrip("\n"))


if __name__ == "__main__":
    unittest.main()
