# -*- coding: utf-8 -*-
"""Cloudflare Quick Tunnel 子进程生命周期管理。"""
from __future__ import annotations

import os
import queue
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import ipaddress
import json


URL_RE = re.compile(r"https://[A-Za-z0-9-]+\.trycloudflare\.com")
TAILSCALE_IP_RE = re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.(?:\d{1,3})\.(?:\d{1,3})\b")


def parse_tailscale_ips(text: str) -> list[str]:
    """从 tailscale ip/status 输出中取 CGNAT IPv4，拒绝普通局域网地址。"""
    found = []
    for value in TAILSCALE_IP_RE.findall(str(text or "")):
        try:
            addr = ipaddress.ip_address(value)
        except ValueError:
            continue
        if addr not in ipaddress.ip_network("100.64.0.0/10"):
            continue
        if value not in found:
            found.append(value)
    return found


def parse_magicdns(status_json) -> str:
    """取 Tailscale 自机 MagicDNS 名称，不返回带尾点的 FQDN。"""
    data = status_json
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (TypeError, ValueError):
            return ""
    if not isinstance(data, dict):
        return ""
    self_info = data.get("Self") or data.get("self") or {}
    value = self_info.get("DNSName") or self_info.get("dnsName") or ""
    return str(value).strip().rstrip(".")


def parse_backend_state(status_json) -> str:
    """取 Tailscale 守护进程的 BackendState 原始值；拿不到时返回空串。

    空串表示「没有办法判断」，与「取值不认识」是两件事：
    前者按已登录但未连上处理，后者必须报探测失败，不能猜成已连接。
    """
    data = status_json
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (TypeError, ValueError):
            return ""
    if not isinstance(data, dict):
        return ""
    value = data.get("BackendState") or data.get("backendState") or ""
    return str(value).strip()


# 认识但还没就绪的取值：都要给出可操作提示，不能冒充「已连接」也不能当成「未安装」
_TAILSCALE_NOT_READY = {
    "Stopped": "Tailscale 没有在运行，请先在电脑上打开 Tailscale。",
    "NoState": "Tailscale 没有在运行，请先在电脑上打开 Tailscale。",
    "Starting": "Tailscale 正在启动，稍等几秒再点重新检测。",
    "NeedsMachineAuth": "Tailscale 等待这台设备被授权，请先在 Tailscale 后台批准。",
}
_TAILSCALE_RUNNING = "Running"
_TAILSCALE_NEEDS_LOGIN = "NeedsLogin"


# Windows 上 Tailscale 默认装在 Program Files，安装包不会把 CLI 加进 PATH
_TAILSCALE_WINDOWS_DIRS = (
    ("ProgramFiles", "Tailscale"),
    ("ProgramFiles(x86)", "Tailscale"),
    ("LOCALAPPDATA", "Tailscale"),
)


def resolve_tailscale(*, which=shutil.which, env=None) -> str:
    """找 Tailscale CLI：先看 PATH，再看 Windows 默认安装目录。"""
    found = which("tailscale") or which("tailscale.exe")
    if found:
        return found
    environment = os.environ if env is None else env
    for variable, folder in _TAILSCALE_WINDOWS_DIRS:
        root = str(environment.get(variable) or "").strip()
        if not root:
            continue
        candidate = Path(root) / folder / "tailscale.exe"
        if candidate.is_file():
            return str(candidate)
    return ""


def _hidden_window_kwargs(runner) -> dict:
    """Windows 上别弹黑色命令行窗口。

    帮助面板每几秒探一次 Tailscale，跑的是 tailscale.exe；不隐藏就会反复闪一个 cmd。
    只在使用真正的 subprocess.run 时才加这些参数：测试传自己的 runner，
    往里塞它不认识的参数会把测试替身顶崩。
    """
    if runner is not subprocess.run or os.name != "nt":
        return {}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if not flags:
        return {}
    kwargs = {"creationflags": flags}
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    except (AttributeError, TypeError, ValueError):
        startupinfo = None
    if startupinfo is not None:
        kwargs["startupinfo"] = startupinfo
    return kwargs


def tailscale_endpoint(*, runner=subprocess.run, which=shutil.which, env=None) -> dict:
    """只读探测 Tailscale；不自动安装、不改防火墙、不启动守护进程。"""
    exe = resolve_tailscale(which=which, env=env)
    if not exe:
        return {"available": False, "error": "tailscale_missing", "state": "missing",
                "text": "电脑上没有 Tailscale，请在电脑和手机安装并登录同一 tailnet。"}
    try:
        hidden = _hidden_window_kwargs(runner)
        ips = runner([exe, "ip", "-4"], check=False, capture_output=True,
                     text=True, encoding="utf-8", errors="replace", timeout=5,
                     **hidden)
        addresses = parse_tailscale_ips(getattr(ips, "stdout", ""))
        status = runner([exe, "status", "--json"], check=False,
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=5, **hidden)
        magic = parse_magicdns(getattr(status, "stdout", ""))
        backend = parse_backend_state(getattr(status, "stdout", ""))
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": "tailscale_probe_failed",
                "state": "probe_failed",
                "text": "Tailscale 状态暂时读不到：%s" % type(exc).__name__}
    recognized = {_TAILSCALE_RUNNING, _TAILSCALE_NEEDS_LOGIN} | set(_TAILSCALE_NOT_READY)
    if backend and backend not in recognized:
        # 不认识的状态宁可报失败，也不能让界面显示成已连接
        return {"available": False, "error": "tailscale_probe_failed",
                "state": "probe_failed",
                "text": "Tailscale 返回了无法识别的状态：%s，请重新检测。" % backend}
    if not addresses:
        if backend in _TAILSCALE_NOT_READY:
            return {"available": False, "error": "tailscale_probe_failed",
                    "state": "probe_failed", "backend": backend,
                    "text": "%s：%s" % (backend, _TAILSCALE_NOT_READY[backend])}
        return {"available": False, "error": "tailscale_not_logged_in",
                "state": "not_logged_in", "backend": backend,
                "text": "Tailscale 尚未登录，先在电脑和手机登录同一 tailnet。"}
    public_host = magic or addresses[0]
    return {"available": True, "bind_host": addresses[0],
            "addresses": addresses, "magicdns": magic,
            "public_host": public_host, "state": "connected", "backend": backend,
            "text": "已找到 Tailscale 远程地址"}


def resolve_cloudflared(*, resource_root: Path | None = None,
                        here: Path | None = None, root=None) -> str:
    """只返回组件包校验过的 cloudflared 路径。

    两个 path 参数为兼容既有调用保留；PATH 上的、解释器目录里的和 resource_root/bin
    下的二进制都无法证明版本与哈希，采信它们等于绕开组件包校验，所以一律不看。
    """
    from infrastructure import component_packages
    return component_packages.cloudflared(root=root)


def verify_managed_cloudflared(path, *, root=None) -> str:
    """启动前再验证一次：只认受管组件里那一个，且 manifest/哈希/版本仍然对。

    组件可能在程序启动之后被替换或删掉，初始化时缓存的路径不能直接拿去执行；
    校验不过就返回空串，调用方据此拒绝启动，而不是硬跑一个来路不明的二进制。
    """
    from infrastructure import component_packages
    trusted = component_packages.cloudflared(root=root)
    if not trusted:
        return ""
    try:
        if Path(trusted).resolve() != Path(str(path or "")).resolve():
            return ""
    except (OSError, ValueError):
        return ""
    return trusted


def spawn_cloudflared(args, **kwargs):
    """将隧道进程纳入 Job，父进程异常结束时也能回收。"""
    from infrastructure import process_tree
    tree = process_tree.spawn_owned(
        args, cwd=str(Path(args[0]).resolve().parent), env=os.environ.copy(),
        stdin=kwargs.get("stdin"), stdout=kwargs.get("stdout", subprocess.PIPE),
        stderr=kwargs.get("stderr", subprocess.STDOUT))

    def watch_exit():
        try:
            tree.proc.wait()
        finally:
            tree.close()

    try:
        threading.Thread(target=watch_exit, name="cloudflared-job",
                         daemon=True).start()
    except BaseException:
        try:
            tree.terminate()
        finally:
            tree.close()
        raise
    return tree.proc


class CloudflareTunnel:
    def __init__(self, executable: str = "", *, popen=subprocess.Popen,
                 now=time.monotonic, verify=None, usage=None):
        self.executable = str(executable or "")
        self._popen = popen
        self._now = now
        self._verify = verify
        self._usage_factory = usage
        self._usage = None
        self._state_lock = threading.Lock()
        self._proc = None
        self._queue = queue.Queue()
        self._reader = None
        self.public_url = ""

    def _release_usage(self, proc=None):
        with self._state_lock:
            if proc is not None and self._proc is not proc:
                return
            usage, self._usage = self._usage, None
        if usage is not None:
            usage.__exit__(None, None, None)

    def start(self, local_url: str, timeout_s: float = 20.0) -> dict:
        if self._proc is not None and self._proc.poll() is None:
            return {"ok": False, "error": "already_running", "url": self.public_url}
        self._release_usage(self._proc)
        self._proc = None
        if not self.executable:
            return {"ok": False, "error": "cloudflared_missing",
                    "text": "找不到 cloudflared，请安装后再启用 Cloudflare 通道。"}
        try:
            if self._usage_factory is not None:
                usage = self._usage_factory(self.executable)
                checked = usage.__enter__()
                self._usage = usage
                if not checked:
                    self._release_usage()
                    self.executable = ""
                    return {"ok": False, "error": "cloudflared_untrusted",
                            "text": "cloudflared 组件校验没通过（可能被替换或删除），请重新安装手机控制组件。"}
                self.executable = str(checked)
            if self._verify is not None:
                checked = self._verify(self.executable)
                if not checked or (self._usage is not None and
                                   Path(str(checked)).resolve() != Path(self.executable).resolve()):
                    self._release_usage()
                    self.executable = ""
                    return {"ok": False, "error": "cloudflared_untrusted",
                            "text": "cloudflared 组件校验没通过（可能被替换或删除），请重新安装手机控制组件。"}
                self.executable = str(checked)
            proc = self._popen(
                [self.executable, "tunnel", "--url", str(local_url)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                               | getattr(subprocess, "CREATE_NO_WINDOW", 0)),
            )
        except Exception as exc:  # noqa: BLE001
            self._release_usage()
            return {"ok": False, "error": "tunnel_start_failed",
                    "text": "Cloudflare 隧道启动失败：%s" % type(exc).__name__}
        self._proc = proc
        self._queue = queue.Queue()

        if self._usage is not None:
            def watch_exit():
                while proc.poll() is None:
                    time.sleep(0.1)
                self._release_usage(proc)

            threading.Thread(target=watch_exit, name="cloudflared-exit",
                             daemon=True).start()

        def read_lines():
            try:
                for line in proc.stdout or ():
                    self._queue.put(str(line))
            finally:
                self._queue.put(None)

        self._reader = threading.Thread(target=read_lines, name="cloudflared-log",
                                         daemon=True)
        self._reader.start()
        deadline = self._now() + float(timeout_s)
        while self._now() < deadline:
            try:
                line = self._queue.get(timeout=0.2)
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue
            if line is None:
                break
            match = URL_RE.search(line)
            if match:
                self.public_url = match.group(0)
                return {"ok": True, "url": self.public_url}
        self.stop()
        return {"ok": False, "error": "tunnel_url_timeout",
                "text": "Cloudflare 没有返回可用地址，请检查 cloudflared 输出。"}

    def status(self) -> dict:
        """只读隧道状态：子进程退出后立刻认为地址失效，不做宽限也不重启。

        快速隧道每次启动都是新域名，旧地址即使还能连也不属于本工具了；
        宽限只会让人拿着一个注定打不开的地址去扫码。
        """
        proc = self._proc
        if proc is None:
            return {"running": False, "public_url": "", "state": "stopped",
                    "temporary": True, "restart_requires_pairing": True}
        if proc.poll() is not None:
            # 进程已经退出：地址必须先清掉，免得界面继续展示一个死链
            self._release_usage(proc)
            self._proc = None
            self.public_url = ""
            return {"running": False, "public_url": "", "state": "exited",
                    "error": "tunnel_exited",
                    "text": "Cloudflare 隧道已退出，重新开启会得到新地址。",
                    "temporary": True, "restart_requires_pairing": True}
        return {"running": True, "public_url": self.public_url,
                "state": "running", "temporary": True,
                "restart_requires_pairing": True}

    def stop(self) -> dict:
        proc = self._proc
        self.public_url = ""
        if proc is None:
            return {"ok": True}
        try:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=3)
        except Exception:  # noqa: BLE001
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:
                pass
        if proc.poll() is None:
            return {"ok": False, "error": "tunnel_stop_failed",
                    "text": "Cloudflare 隧道仍在运行，请重试关闭。"}
        self._release_usage(proc)
        self._proc = None
        return {"ok": True}


__all__ = ["CloudflareTunnel", "URL_RE", "resolve_cloudflared", "resolve_tailscale",
           "spawn_cloudflared",
           "_hidden_window_kwargs",
           "parse_tailscale_ips", "parse_magicdns", "parse_backend_state",
           "tailscale_endpoint"]
