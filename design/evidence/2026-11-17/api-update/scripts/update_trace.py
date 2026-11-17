# -*- coding: utf-8 -*-
"""不变区对照：同一组替身端口驱动 Api 的更新链路，把每一步的返回值、事件和
bootstrap 里的 update_check 录下来，用于「拆结构前后一模一样」的比对。

用法（都在仓库根）：

    python -B design/evidence/<日期>/api-update/scripts/update_trace.py --repo .
    python -B .../update_trace.py --repo . --out trace.json
    python -B .../update_trace.py --compare a.json b.json

只替换网络与磁盘端口：check_latest_release、updater 的下载/落盘/启动、版本路径、
线程创建、关窗推迟动作。产品逻辑一行不改，也不联网。

@author Author
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

INSTALLER_NAME = "campus-activity-watch-installer-v9.9.9-win-x64.exe"


def clean(value):
    """录进对照文件的值：只留可比对的原始类型，对象只留类型名。"""
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return "<%s>" % type(value).__name__


class Trace:
    """按顺序记录每一步，供两边的对照逐项比。"""

    def __init__(self):
        self.steps: list[dict] = []

    def __call__(self, name, func, *args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - 异常也是被对照的返回值
            result = {"raised": type(exc).__name__}
        self.steps.append({"step": name, "result": clean(result)})
        return result

    def drain(self, queue):
        """把排队的后台线程跑完（场景里线程不真的并发，结果才可比）。"""
        ran = 0
        while queue:
            thread = queue.pop(0)
            thread.target(*thread.args, **thread.kwargs)
            ran += 1
        self.steps.append({"step": "run_background", "ran": ran})

    def bootstrap(self, api):
        info = api.bootstrap()
        self.steps.append({"step": "bootstrap.update_check",
                           "result": clean(info.get("update_check"))})


def make_thread_class(queue):
    """替换 threading.Thread：构造即排队，drain 时按序执行。"""

    class ManualThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None, name=None, **_):
            self.target, self.args, self.kwargs = target, tuple(args or ()), dict(kwargs or {})

        def start(self):
            queue.append(self)

        def join(self, timeout=None):
            return None

        def is_alive(self):
            return False

    return ManualThread


class Proxy:
    """只替换少数属性的模块替身：其余名字原样透传，别处照常用真模块。"""

    def __init__(self, real, **overrides):
        self._real = real
        self._overrides = overrides

    def __getattr__(self, name):
        if name in self._overrides:
            return self._overrides[name]
        return getattr(self._real, name)


class Ctx:
    """一个场景的运行上下文。"""

    def __init__(self, api, app, updater, queue):
        self.api, self.app, self.updater, self.queue = api, app, updater, queue
        self.trace = Trace()

    def prefill(self, check_result=None):
        """前置：跑一次检查更新，把安装器放进状态里（记步）。检查结论由场景的替身给。"""
        self.trace("check_update(prefill)", self.api.check_update, "prefill")
        self.trace.drain(self.queue)
        return check_result


def available(extra=None):
    payload = {"state": "available", "current_version": "1.2.3", "latest_version": "9.9.9",
               "url": "https://example.invalid/latest", "text": "有新版本可用。",
               "error_code": "",
               "installer": {"name": INSTALLER_NAME,
                             "url": "https://example.invalid/" + INSTALLER_NAME,
                             "bytes": 4, "sha256": "ab" * 32}}
    payload.update(extra or {})
    return payload


def payload_installer():
    """带版本目录包（full）的安装器：走版本切换那条路。"""
    target = {"version": "9.9.9",
              "files": [{"path": "campus-activity-watch.exe", "bytes": 3, "sha256": "aa" * 32}],
              "target_manifest_sha256": "00" * 32}
    return available({"installer": {
        "name": INSTALLER_NAME, "url": "https://example.invalid/" + INSTALLER_NAME,
        "bytes": 4, "sha256": "ab" * 32,
        "full": {"name": "payload.zip", "url": "https://example.invalid/payload.zip",
                 "bytes": 4, "sha256": "cd" * 32, "target_version": "9.9.9",
                 "target_manifest": target}}})


def installed_download(name="fake-temp/campus-update/" + INSTALLER_NAME):
    """下载成功替身：按 2/4、4/4 回推两次进度。"""

    def download(url, **kwargs):
        progress = kwargs.get("progress")
        if progress:
            progress(2, 4)
            progress(4, 4)
        return {"ok": True, "path": name, "bytes": 4, "sha256": "ab" * 32}

    return download


def scenario_check_available(ctx):
    ctx.trace("check_update", ctx.api.check_update, "c1")
    ctx.trace.drain(ctx.queue)
    ctx.trace.bootstrap(ctx.api)


def scenario_check_current(ctx):
    ctx.trace("check_update", ctx.api.check_update, "c2")
    ctx.trace.drain(ctx.queue)
    ctx.trace.bootstrap(ctx.api)


def scenario_check_raises(ctx):
    ctx.trace("check_update", ctx.api.check_update, "c3")
    ctx.trace.drain(ctx.queue)
    ctx.trace.bootstrap(ctx.api)


def scenario_check_bad_id(ctx):
    ctx.trace("check_update", ctx.api.check_update, "bad id")
    ctx.trace("update_download", ctx.api.update_download, "bad id")
    ctx.trace("update_launch", ctx.api.update_launch, "bad id")


def scenario_check_closing(ctx):
    ctx.api._closing = True
    ctx.trace("check_update", ctx.api.check_update, "c5")
    ctx.trace("update_download", ctx.api.update_download, "c5")
    ctx.trace("update_launch", ctx.api.update_launch, "c5")


def scenario_check_in_flight(ctx):
    ctx.trace("check_update", ctx.api.check_update, "c6a")
    ctx.trace("check_update", ctx.api.check_update, "c6b")
    ctx.trace.bootstrap(ctx.api)
    ctx.trace.drain(ctx.queue)
    ctx.trace("check_update", ctx.api.check_update, "c6c")
    ctx.trace.drain(ctx.queue)
    ctx.trace.bootstrap(ctx.api)


def scenario_download_success(ctx):
    ctx.prefill(available())
    ctx.trace("update_download", ctx.api.update_download, "d1")
    ctx.trace.drain(ctx.queue)
    ctx.trace.bootstrap(ctx.api)


def scenario_download_cancel(ctx):
    ctx.prefill(available())
    ctx.trace("update_cancel", ctx.api.update_cancel)
    ctx.trace("update_download", ctx.api.update_download, "d2")
    ctx.trace.drain(ctx.queue)
    ctx.trace.bootstrap(ctx.api)


def scenario_download_failed(ctx):
    ctx.prefill(available())
    ctx.trace("update_download", ctx.api.update_download, "d3")
    ctx.trace.drain(ctx.queue)
    ctx.trace.bootstrap(ctx.api)


def scenario_download_version_payload(ctx):
    ctx.prefill(payload_installer())
    ctx.trace("update_download", ctx.api.update_download, "d4")
    ctx.trace.drain(ctx.queue)
    ctx.trace.bootstrap(ctx.api)


def scenario_download_version_fallback(ctx):
    ctx.prefill(payload_installer())
    ctx.trace("update_download", ctx.api.update_download, "d5")
    ctx.trace.drain(ctx.queue)
    ctx.trace.bootstrap(ctx.api)


def scenario_launch_installer(ctx):
    ctx.prefill(available())
    ctx.trace("update_download", ctx.api.update_download, "d6")
    ctx.trace.drain(ctx.queue)
    ctx.trace("update_launch", ctx.api.update_launch, "d6")
    ctx.trace.bootstrap(ctx.api)


def scenario_launch_installer_failed(ctx):
    ctx.prefill(available())
    ctx.trace("update_download", ctx.api.update_download, "d7")
    ctx.trace.drain(ctx.queue)
    ctx.trace("update_launch", ctx.api.update_launch, "d7")
    ctx.trace.bootstrap(ctx.api)


def scenario_launch_version_switch(ctx):
    ctx.prefill(payload_installer())
    ctx.trace("update_download", ctx.api.update_download, "d8")
    ctx.trace.drain(ctx.queue)
    ctx.trace("update_launch", ctx.api.update_launch, "d8")
    ctx.trace.bootstrap(ctx.api)


def scenario_launch_without_artifact(ctx):
    ctx.trace("update_launch", ctx.api.update_launch, "l1")
    ctx.trace.bootstrap(ctx.api)


def _switch_stub(state):
    return lambda *args, **kwargs: state[0]


def _stub_paths():
    return {"root": Path("fake") / "versions",
            "current_file": Path("fake") / "current.json",
            "base_dir": Path("fake") / "versions" / "1.2.3"}


def download_stubs(app, updater, switch, stage_ok=True):
    """下载相关的替身端口；switch 是可变列表，便于在中途改判据。"""
    def stage(base_dir, archive, staging_dir, **kwargs):
        if stage_ok:
            return {"ok": True, "path": str(staging_dir)}
        return {"ok": False, "error_code": "apply_failed", "detail": "目标清单不一致"}

    return [
        mock.patch.object(app, "version_switch_available", _switch_stub(switch)),
        mock.patch.object(app, "update_version_paths", _stub_paths),
        mock.patch.object(updater, "download_installer", installed_download()),
        mock.patch.object(updater, "download_payload", installed_download("fake-temp/payload.zip")),
        mock.patch.object(updater, "stage_update", stage),
        mock.patch.object(updater, "cleanup_download", lambda path: None),
        mock.patch.object(updater, "cleanup_staging", lambda *a, **k: None),
    ]


def launch_stubs(app, ok=True):
    """启动相关的替身端口：更新启动器与安装器都只记录、不真起进程。"""
    def popen(args, **kwargs):
        return mock.Mock()

    return [
        mock.patch.object(app, "sys", Proxy(app.sys, frozen=True)),
        mock.patch.object(app, "resolve_update_launcher_path",
                          lambda *a, **k: Path("fake") / "update-launcher.exe"),
        mock.patch.object(app, "subprocess", Proxy(app.subprocess, Popen=popen)),
        mock.patch.object(app, "defer_close_action", lambda callback, delay=0.25: None),
        mock.patch.object(app.updater, "launch_installer",
                          lambda path: {"ok": ok, "path": path} if ok else
                          {"ok": False, "error_code": "launch_failed", "text": "没能启动"}),
    ]


SCENARIOS = {
    "check_available": (scenario_check_available, "available"),
    "check_current": (scenario_check_current, "current"),
    "check_raises": (scenario_check_raises, "raises"),
    "check_bad_id": (scenario_check_bad_id, "none"),
    "check_closing": (scenario_check_closing, "none"),
    "check_in_flight": (scenario_check_in_flight, "deferred"),
    "download_success": (scenario_download_success, "available"),
    "download_cancel": (scenario_download_cancel, "cancel"),
    "download_failed": (scenario_download_failed, "failed"),
    "download_version_payload": (scenario_download_version_payload, "payload"),
    "download_version_fallback": (scenario_download_version_fallback, "fallback"),
    "launch_installer": (scenario_launch_installer, "launch"),
    "launch_installer_failed": (scenario_launch_installer_failed, "launch_failed"),
    "launch_version_switch": (scenario_launch_version_switch, "switch"),
    "launch_without_artifact": (scenario_launch_without_artifact, "none"),
}

CHECK_RESULTS = {
    "available": available,
    "payload": payload_installer,
    "fallback": payload_installer,
    "switch": payload_installer,
    "current": lambda: {"state": "current", "current_version": "1.2.3",
                        "latest_version": "1.2.3", "url": "https://example.invalid/latest",
                        "text": "已是最新版本。", "error_code": "", "installer": None},
}

DOWNLOAD_RESULTS = {
    "available": installed_download(),
    "cancel": lambda url, **kwargs: {"ok": False, "error_code": "cancelled", "text": "已取消"},
    "failed": lambda url, **kwargs: {"ok": False, "error_code": "hash_mismatch",
                                     "text": "哈希不符"},
    "payload": installed_download("fake-temp/payload.zip"),
    "fallback": installed_download(),   # 版本包失败后回退安装器用同一个成功替身
    "launch": installed_download(),
    "launch_failed": installed_download(),
    "switch": installed_download("fake-temp/payload.zip"),
    "none": installed_download(),
}


def scenario_patches(app, updater, kind):
    """按场景种类拼出要打的替身端口。"""
    switch = [kind in ("payload", "fallback", "switch")]
    patches = [mock.patch.object(app, "check_latest_release",
                                 return_value=CHECK_RESULTS.get(kind, available)())]
    if kind == "raises":
        patches[0] = mock.patch.object(app, "check_latest_release",
                                       side_effect=RuntimeError("boom"))
    if kind in ("payload", "fallback", "switch", "launch", "launch_failed", "available"):
        patches += download_stubs(app, updater, switch, stage_ok=kind != "fallback")
    if kind == "cancel":
        patches.append(mock.patch.object(updater, "download_installer",
                                         DOWNLOAD_RESULTS["cancel"]))
    if kind == "failed":
        patches.append(mock.patch.object(updater, "download_installer",
                                         DOWNLOAD_RESULTS["failed"]))
    if kind in ("launch", "launch_failed", "switch"):
        patches += launch_stubs(app, ok=kind != "launch_failed")
    return patches


def run_scenario(app, updater, name):
    scenario, kind = SCENARIOS[name]
    queue: list = []
    events: list = []
    tmp = Path(tempfile.mkdtemp(prefix="campus-update-trace-"))
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(
            app, "threading", Proxy(app.threading, Thread=make_thread_class(queue))))
        stack.enter_context(mock.patch.object(app, "PREFS", tmp / "ui.json"))
        stack.enter_context(mock.patch.object(app, "DEVICE_FILE", tmp / "devices.json"))
        stack.enter_context(mock.patch.object(app, "DEMO", True))
        stack.enter_context(mock.patch.object(app, "load_prefs", lambda: {}))
        stack.enter_context(mock.patch.object(app, "login_state", lambda *a, **k: {}))
        stack.enter_context(mock.patch.object(
            app, "get_lifecycle", lambda: mock.Mock(snapshot=lambda: {})))
        for patch in scenario_patches(app, updater, kind):
            stack.enter_context(patch)
        api = app.Api(clock=app._TestWallClock())
        monitor = getattr(api, "_auto_relogin", None)
        api._emit = lambda kind, payload: events.append(
            {"kind": kind, "payload": clean(payload)})
        ctx = Ctx(api, app, updater, queue)
        try:
            scenario(ctx)
        finally:
            if monitor is not None:
                monitor.stop()
    return {"steps": ctx.trace.steps, "events": events}


def _flatten(node, prefix=""):
    if isinstance(node, dict):
        for key in node:
            yield from _flatten(node[key], "%s/%s" % (prefix, key))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _flatten(item, "%s[%d]" % (prefix, index))
    else:
        yield prefix, node


def compare(left, right):
    """逐项比对两份对照，输出比了多少步、不同多少步。"""
    flat_left = dict(_flatten(left))
    flat_right = dict(_flatten(right))
    keys = sorted(set(flat_left) | set(flat_right))
    diffs = [key for key in keys if flat_left.get(key) != flat_right.get(key)]
    print("比了 %d 项，相同 %d 项，不同 %d 项" % (len(keys), len(keys) - len(diffs), len(diffs)))
    for key in diffs[:40]:
        print("  差异 %s: %r != %r" % (key, flat_left.get(key), flat_right.get(key)))
    return 0 if not diffs else 1


def build_trace(repo: Path) -> dict:
    sys.path.insert(0, str(repo / "local" / "tests"))
    sys.path.insert(0, str(repo / "local"))
    import app  # noqa: PLC0415 - 必须在 sys.path 就位后再导入
    import updater  # noqa: PLC0415
    from fixtures.business_clock import TestWallClock  # noqa: PLC0415

    app._TestWallClock = TestWallClock
    return {name: run_scenario(app, updater, name) for name in SCENARIOS}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="更新链路的不变区对照")
    parser.add_argument("--repo", default=".", help="仓库根（默认当前目录）")
    parser.add_argument("--out", help="把对照写到这个文件；省略则打印到 stdout")
    parser.add_argument("--compare", nargs=2, metavar=("LEFT", "RIGHT"),
                        help="比对两份已有的对照文件")
    args = parser.parse_args(argv)
    if args.compare:
        left = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
        right = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))
        return compare(left, right)
    trace = build_trace(Path(args.repo).resolve())
    text = json.dumps(trace, ensure_ascii=False, indent=1, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("已写出 %d 个场景" % len(trace))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
