#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""变异证明：三道守卫不是空转——每条变异都必须让预期的用例变红。

口径：
- 全程不碰工作区。每条变异在 tempfile.mkdtemp() 建的临时副本里做，副本只拷
  local/（排除 data、config.json、运行时产物与字节码），跑完即删。
- 副本要带上本批新加的测试与夹具：它们还在工作区未入库，所以从工作区的
  local/ 拷贝，而不是从 git 检出。
- 四个副本并行，每条变异只跑它对应的那一份守卫测试；退出码非 0（首红）即算
  证明成立，收集 stderr 里的 FAIL/ERROR 行作为「实际红的用例」。
- 任何一条变异没让测试变红（survived），或 find 串在目标文件里不是恰好一次，
  都算失败，脚本退出码 1。

复跑（仓库根，用装齐本仓库依赖的解释器）：
    PYTHONIOENCODING=utf-8 python -B design/evidence/2026-11-17/api-guards/scripts/mutate.py

@author Author
"""
from __future__ import annotations

import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
LOCAL = REPO / "local"

# 副本不带：数据与凭据（不读取）、运行时产物、字节码缓存
COPY_IGNORE = shutil.ignore_patterns(
    "data", "config.json", "_site_build.py", "bin", "__pycache__", "*.pyc",
    "*.log", "*.log.*", "*.lock")

# 守卫名 → 测试文件名（副本里按 discover -s local/tests -p 跑）
GUARD_PATTERN = {
    "signatures": "test_phone_action_signatures.py",
    "lock-order": "test_lock_order.py",
    "busy-matrix": "test_busy_matrix.py",
}

# 每条变异：edits 是 (相对 local/ 的文件, find, replace)，find 必须恰好出现一次。
MUTATIONS = [
    # ---------- 签名守卫 ----------
    {
        "id": "sig-1",
        "guard": "signatures",
        "where": "local/app.py start_plan 签名：request_id 改名成 request_id2",
        "expect": "test_all_actions_bind_to_real_api_signatures（start_plan 全键派发）"
                  " 与 test_start_plan_dispatch_marks_source_phone",
        "edits": [(
            "app.py",
            '                   retry_policy: dict | None = None, request_id: str = "",\n'
            '                   source: str = "desktop") -> dict:',
            '                   retry_policy: dict | None = None, request_id2: str = "",\n'
            '                   source: str = "desktop") -> dict:')],
    },
    {
        "id": "sig-2",
        "guard": "signatures",
        "where": "phone_service.dispatch：save_retry_policy 的改写目标改成不存在的方法",
        "expect": "test_save_retry_policy_rewrites_into_prefs（落到 not_available）",
        "edits": [(
            "application/phone_service.py",
            '        return self._call("save_prefs",',
            '        return self._call("save_prefs_gone",')],
    },
    {
        "id": "sig-3",
        "guard": "signatures",
        "where": "phone_rules.ACTION_PARAMS：给 check 加一个 Api.check 不接的键",
        "expect": "test_tables_cover_the_whole_whitelist（全键表没盖住新键）",
        "edits": [(
            "domain/phone_rules.py",
            '    "check": {"request_id"},',
            '    "check": {"request_id", "volume"},')],
    },
    {
        "id": "sig-4",
        "guard": "signatures",
        "where": "local/app.py check 签名：加一个没有默认值的前置参数",
        "expect": "test_all_actions_bind_to_real_api_signatures（check 两种派发都 internal）",
        "edits": [(
            "app.py",
            '    def check(self, request_id: str = "") -> dict:',
            '    def check(self, mandatory_probe: str, request_id: str = "") -> dict:')],
    },
    # ---------- 锁序守卫 ----------
    {
        "id": "lock-1",
        "guard": "lock-order",
        "where": "local/app.py check：持协调锁的块里加一层凭据锁（3→1 降级）",
        "expect": "test_lock_level_only_rises",
        "edits": [(
            "app.py",
            '        with self._lock:\n'
            '            if self._closing:\n'
            '                # 关闭拒绝是取消语义：不给组件码，不再起线程',
            '        with self._lock:\n'
            '            with self._credential_lock:\n'
            '                pass\n'
            '            if self._closing:\n'
            '                # 关闭拒绝是取消语义：不给组件码，不再起线程')],
    },
    {
        "id": "lock-2",
        "guard": "lock-order",
        "where": "local/app.py check：持协调锁时加一句 self._relay.cancel()",
        "expect": "test_coordination_lock_calls_only_published_status",
        "edits": [(
            "app.py",
            '        with self._lock:\n'
            '            if self._closing:\n'
            '                # 关闭拒绝是取消语义：不给组件码，不再起线程',
            '        with self._lock:\n'
            '            self._relay.cancel()\n'
            '            if self._closing:\n'
            '                # 关闭拒绝是取消语义：不给组件码，不再起线程')],
    },
    {
        "id": "lock-3",
        "guard": "lock-order",
        "where": "login_relay_service.cancel：锁外的 self._on_finish() 挪进 with（服务持锁调端口）",
        "expect": "test_service_locks_avoid_injected_ports（_on_finish 不在白名单与冻结表）",
        "edits": [
            ("application/login_relay_service.py",
             '            if flow is not None:\n'
             '                flow["state"] = STATE_CANCELED\n'
             '                flow["reader_done"].set()\n'
             '                self._last = public_state(flow, self._now())',
             '            if flow is not None:\n'
             '                flow["state"] = STATE_CANCELED\n'
             '                flow["reader_done"].set()\n'
             '                self._last = public_state(flow, self._now())\n'
             '                self._on_finish()'),
            ("application/login_relay_service.py",
             '        if flow is not None:\n'
             '            self._on_finish()\n'
             '        return {"ok": True}',
             '        return {"ok": True}'),
        ],
    },
    {
        "id": "lock-4",
        "guard": "lock-order",
        "where": "local/app.py check：新加一把没定级的 self._x_lock 并在 with 里用",
        "expect": "test_new_locks_must_be_leveled",
        "edits": [(
            "app.py",
            '        # 条款门禁：登录态校验要访问学校接口，未获授权就不起线程（后端最终防线）\n'
            '        gate = self._terms_gate(request_id)',
            '        # 条款门禁：登录态校验要访问学校接口，未获授权就不起线程（后端最终防线）\n'
            '        with self._x_lock:\n'
            '            pass\n'
            '        gate = self._terms_gate(request_id)')],
    },
    {
        "id": "lock-5",
        "guard": "lock-order",
        "where": "local/app.py remove_advanced_feature：3 处重入之一改成不取锁的 _stop_phone_access()",
        "expect": "test_reentry_equals_the_frozen_legacy_list（重入变 2 条，不等于冻结的 3 条）",
        "edits": [(
            "app.py",
            '                if key == _advanced_features.PHONE_CONTROL:\n'
            '                    self.stop_phone_access()',
            '                if key == _advanced_features.PHONE_CONTROL:\n'
            '                    self._stop_phone_access()')],
    },
    # ---------- 矩阵守卫 ----------
    {
        "id": "matrix-1",
        "guard": "busy-matrix",
        "where": "local/app.py _is_busy_locked：加 or self._advanced_busy",
        "expect": "test_row_start_plan 的「组件事务在途」子用例（放行变拒绝）",
        "edits": [(
            "app.py",
            '        if self._cancelling:\n'
            '            return True      # 取消报名占着同一把忙碌标记（X3）',
            '        if self._cancelling:\n'
            '            return True      # 取消报名占着同一把忙碌标记（X3）\n'
            '        if self._advanced_busy:\n'
            '            return True')],
    },
    {
        "id": "matrix-2",
        "guard": "busy-matrix",
        "where": "local/app.py _start_phone_access：门里删掉 self._advanced_busy",
        "expect": "test_row_start_phone_access 的「组件事务在途」子用例（拒绝变放行）",
        "edits": [(
            "app.py",
            '        with self._lock:\n'
            '            if self._closing or self._advanced_busy:\n'
            '                return {"ok": False, "text": "程序正在关闭，手机访问没有开启"}',
            '        with self._lock:\n'
            '            if self._closing:\n'
            '                return {"ok": False, "text": "程序正在关闭，手机访问没有开启"}')],
    },
    {
        "id": "matrix-3",
        "guard": "busy-matrix",
        "where": "local/app.py check：门里删掉 _cancelling",
        "expect": "test_row_check 的「取消报名在途」子用例（拒绝变放行）",
        "edits": [(
            "app.py",
            '                        "text": "程序正在关闭，已取消本次检查"}\n'
            '            if self._cancelling:\n'
            '                return {"ok": False, "queued": False, "request_id": request_id,\n'
            '                        "text": "正在取消报名，等它结束再刷新"}',
            '                        "text": "程序正在关闭，已取消本次检查"}')],
    },
    {
        "id": "matrix-4",
        "guard": "busy-matrix",
        "where": "local/app.py remove_advanced_feature：移除门也问 _is_busy_locked()",
        "expect": "test_row_component_remove 的「取消报名在途 / 单 worker 在跑 / 计划在跑」子用例",
        "edits": [(
            "app.py",
            '            with self._lock:\n'
            '                if self._closing or self._advanced_busy:\n'
            '                    return {"ok": False, "text": "请等待当前操作结束。"}\n'
            '                self._advanced_busy = True',
            '            with self._lock:\n'
            '                if self._closing or self._advanced_busy or self._is_busy_locked():\n'
            '                    return {"ok": False, "text": "请等待当前操作结束。"}\n'
            '                self._advanced_busy = True')],
    },
    {
        "id": "matrix-5",
        "guard": "busy-matrix",
        "where": "local/app.py _spawn_relay_worker：门里删掉 _checking",
        "expect": "test_row_manual_relogin 的「check 在途」子用例（拒绝变放行）",
        "edits": [(
            "app.py",
            '            if single or self._checking or self._listing or self._cancelling:',
            '            if single or self._listing or self._cancelling:')],
    },
    # ---------- 返修补充（2026-11-23：计划进程列 / 服务类内部 / 锁外发布） ----------
    {
        "id": "matrix-6",
        "guard": "busy-matrix",
        "where": "local/app.py _is_busy_locked：_plan_procs 那句换成 return False",
        "expect": "test_row_start_plan / login / grab / component_download / "
                  "component_install 的「计划进程在跑」子用例（拒绝变放行）",
        "edits": [(
            "app.py",
            '        if self._plan:\n'
            '            if self._plan.published_status() in {"ready", "running"}:\n'
            '                return True\n'
            '        return any(proc.poll() is None for proc in self._plan_procs.values())',
            '        if self._plan:\n'
            '            if self._plan.published_status() in {"ready", "running"}:\n'
            '                return True\n'
            '        return False')],
    },
    {
        "id": "matrix-7",
        "guard": "busy-matrix",
        "where": "local/app.py _relogin_blocked_locked：_plan_procs 那句换成 return False",
        "expect": "test_row_auto_relogin 的「计划进程在跑」子用例（拒绝变放行）",
        "edits": [(
            "app.py",
            '        if self._login_wait_pending:\n'
            '            return False\n'
            '        if self._proc and self._proc.poll() is None:\n'
            '            return True\n'
            '        return any(proc.poll() is None for proc in self._plan_procs.values())',
            '        if self._login_wait_pending:\n'
            '            return False\n'
            '        if self._proc and self._proc.poll() is None:\n'
            '            return True\n'
            '        return False')],
    },
    {
        "id": "lock-6",
        "guard": "lock-order",
        "where": "phone_service.revoke_all：持 _event_lock（等级 6）再拿 _lock（等级 5）",
        "expect": "test_service_lock_level_only_rises（服务类内部 6→5 降级）",
        "edits": [(
            "application/phone_service.py",
            '    def revoke_all(self) -> None:\n'
            '        with self._lock:\n'
            '            self._sessions.clear()',
            '    def revoke_all(self) -> None:\n'
            '        with self._event_lock:\n'
            '            with self._lock:\n'
            '                self._sessions.clear()')],
    },
    {
        "id": "lock-7",
        "guard": "lock-order",
        "where": "signup_plan.cancel_task：self._publish 挪进 with self._lock（锁内发布）",
        "expect": "test_publish_stays_outside_the_coordinator_lock"
                  "（同时 5→3 降级也让 test_service_lock_level_only_rises 红）",
        "edits": [(
            "signup_plan.py",
            '            if state in {"queued", "waiting"}:\n'
            '                payload = self._set_state_locked(str(task_id), "canceled",\n'
            '                                                {"reason": "你取消了这一场"})\n'
            '        if payload is not None:\n'
            '            self._publish("task", payload)\n'
            '        return True',
            '            if state in {"queued", "waiting"}:\n'
            '                payload = self._set_state_locked(str(task_id), "canceled",\n'
            '                                                {"reason": "你取消了这一场"})\n'
            '                if payload is not None:\n'
            '                    self._publish("task", payload)\n'
            '        return True')],
    },
]

_RED_LINE = re.compile(r"^(FAIL|ERROR): (.*?)(?:$|\n)", re.MULTILINE)
_SUMMARY = re.compile(r"^(Ran \d+ tests? in .*|OK.*|FAILED.*)$", re.MULTILINE)


def _apply_edit(root: Path, rel: str, find: str, replace: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    count = text.count(find)
    if count != 1:
        raise RuntimeError("%s 里 find 串出现 %d 次（要求恰好 1 次）" % (rel, count))
    path.write_text(text.replace(find, replace), encoding="utf-8")


def _red_cases(stderr_text: str) -> list[str]:
    cases = _RED_LINE.findall(stderr_text)
    seen: list[str] = []
    for _kind, name in cases:
        name = name.strip()
        # subTest 失败长成 "test_x (module.Class.test_x) (row='…', column='…')"：
        # 去重时只看括号外的方法名与括号里的行列参数
        if name not in seen:
            seen.append(name)
    return seen


def _summary_of(stderr_text: str) -> str:
    lines = _SUMMARY.findall(stderr_text)
    return " / ".join(line.strip() for line in lines[-3:])


def run_one(mutation: dict) -> dict:
    """一条变异：建副本 → 改文件 → 跑对应守卫 → 删副本。返回结论字典。"""
    work = Path(tempfile.mkdtemp(prefix="campus-mutate-"))
    try:
        shutil.copytree(LOCAL, work / "local", ignore=COPY_IGNORE)
        # app.py 导入期就要读仓库根的 VERSION（读不到直接 SystemExit，而且
        # SystemExit 不是 Exception，测试模块的兜底 try/except 接不住它）：
        # 副本根必须带上 VERSION，否则任何变异都只会以装载失败告红
        version = REPO / "VERSION"
        if version.is_file():
            shutil.copy2(version, work / "VERSION")
        root = work / "local"
        for rel, find, replace in mutation["edits"]:
            _apply_edit(root, rel, find, replace)
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        proc = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover",
             "-s", "local/tests", "-p", GUARD_PATTERN[mutation["guard"]]],
            cwd=str(work), env=env, capture_output=True, timeout=600)
        stderr_text = proc.stderr.decode("utf-8", "replace")
        result = {
            "id": mutation["id"],
            "guard": mutation["guard"],
            "where": mutation["where"],
            "expect": mutation["expect"],
            "red": proc.returncode != 0,
            "exit_code": proc.returncode,
            "cases": _red_cases(stderr_text) if proc.returncode != 0 else [],
            "summary": _summary_of(stderr_text),
        }
        return result
    except Exception as exc:  # noqa: BLE001 - 单条变异挂了也要报清原因
        return {"id": mutation["id"], "guard": mutation["guard"],
                "where": mutation["where"], "expect": mutation["expect"],
                "red": False, "error": "%s: %s" % (type(exc).__name__, exc),
                "cases": [], "summary": ""}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    print("变异证明：共 %d 条，四个副本并行，每条首红即停\n" % len(MUTATIONS))
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(run_one, MUTATIONS):
            results.append(result)
            state = "红了" if result["red"] else "存活"
            print("[%s] %s（%s）—— %s" % (state, result["id"], result["guard"],
                                          result["where"]))
    print()
    survivors = [item for item in results if not item["red"]]
    print("## 变异表")
    print()
    print("| 编号 | 守卫 | 改了哪一行 | 预期红的用例 | 实际红的用例 | 结论 |")
    print("|---|---|---|---|---|---|")
    for item in results:
        actual = "<br>".join(item["cases"][:6]) if item["cases"] else (
            item.get("error") or item.get("summary") or "—")
        print("| %s | %s | %s | %s | %s | %s |" % (
            item["id"], item["guard"], item["where"], item["expect"], actual,
            "红" if item["red"] else "存活"))
    print()
    if survivors:
        print("存活 %d 条：%s" % (len(survivors),
                                  ", ".join(item["id"] for item in survivors)))
        return 1
    print("全部 %d 条变异都让预期的守卫变红。" % len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
