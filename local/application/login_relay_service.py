# -*- coding: utf-8 -*-
"""手机重登中继的父进程侧：凭据预备、子进程会话、stdin 发送与公开状态投影。

凭据只活在当前进程内存：本机 js_api 预备、stdin 单次下发后清掉临时副本，
绝不写 prefs/文件/命令行/env/日志；手机 HTTP 白名单也读不到这份数据。
一个 Api 只有一个在途 relay（singleflight），与 _spawn/start_plan 同一把
关闭屏障锁；shutdown/stop_phone_access 有界取消。任何响应只暴露布尔与
安全状态，不回显账号密码。

@author Author
"""
from __future__ import annotations

import inspect
import json
import queue
import re
import secrets
import threading

from domain.phone_rules import clip_text

# OCR 自动提交前的形状门禁：与 worker 的 valid_code 一致，四位 ASCII 字母数字
_VALID_CODE_RE = re.compile(r"^[0-9A-Za-z]{4}$")

# relay 公开状态的阶段名（手机/桌面据此显示，不含任何凭据）
STATE_IDLE = "idle"
STATE_NEEDS_LOCAL_SETUP = "needs_local_setup"
STATE_PLAN_ACTIVE = "plan_active"
STATE_STARTING = "starting"
STATE_WAITING_CODE = "waiting_code"
STATE_VERIFYING = "verifying"
STATE_SUCCESS = "success"
STATE_FAILED = "failed"
STATE_CANCELED = "canceled"

_SAFE_ERRORS = {
    "needs_local_setup", "plan_active", "terms_required", "busy",
    "spawn_failed", "bad_page", "bad_response", "token_unverified",
    "expired", "canceled", "eof", "timeout", "internal", "demo",
    "max_tries",
}

# 公开投影的终态：结论已定，旧验证码图/挑战号/剩余秒不再对外暴露
_TERMINAL_STATES = (STATE_IDLE, STATE_SUCCESS, STATE_FAILED, STATE_CANCELED)


def public_state(flow, now=None) -> dict:
    """公开状态投影：只出布尔与安全码，任何凭据/图像外的秘密都不得出现。

    验证码没有倒计时和提交次数上限；保留字段名以兼容旧手机页面，但活动场
    返回 expires_in=None、max_attempts=0。success/failed/canceled/idle 终态只留结论：旧验证码图、挑战号与剩余秒
    一律清空；flow_id、状态名、安全错误码、尝试计数原样保留。

    submit_pending 表示「这一张已经发出去、还在等结论」：手机据此继续禁用
    提交按钮，避免网络异常后把同一张图再发一遍。终态恒 False。

    origin 说明这一场是谁发起的（auto=电脑自动、phone=手机人工）：手机据此判断
    该不该接管验证码。它只是一个来源标签，不含任何凭据。

    live 表示「这一场现在还在进行」。中继在没有在途流程时会返回上一场的结论
    快照，那是历史，不是本次结果：手机端只应按 live 播报「重登成功」，否则每次
    打开页面都会重播很早以前那一次的成功。终态（含刚收到的 success）也算结束，
    因为结论已经落地，剩下的只是 worker 收尾。
    """
    if flow is None:
        return {"ready": False, "state": STATE_IDLE, "flow_id": "",
                "challenge_id": "", "image": "", "expires_in": 0,
                "attempts": 0, "max_attempts": 0, "safe_error": "",
                "submit_pending": False, "origin": "", "live": False}
    state = str(flow.get("state") or STATE_IDLE)
    terminal = state in _TERMINAL_STATES
    return {
        "ready": True,
        "state": state,
        "origin": str(flow.get("origin") or ""),
        "mode": str(flow.get("mode") or "manual"),
        "flow_id": str(flow.get("flow_id") or ""),
        "challenge_id": "" if terminal else str(flow.get("challenge_id") or ""),
        "image": "" if terminal else str(flow.get("image") or ""),
        "expires_in": 0 if terminal else None,
        "attempts": max(0, int(flow.get("attempts") or 0)),
        "max_attempts": 0,
        "safe_error": str(flow.get("safe_error") or ""),
        "submit_pending": False if terminal else bool(flow.get("submit_pending")),
        "live": not terminal,
    }


def _accepts_origin(callback) -> bool:
    """判断成功回调是否收一个来源标签。

    旧调用方传的是零参 lambda；用签名判断比「先传参、失败再退回零参」干净，
    也不必让异常参与正常流程。取不到签名（如某些 Mock）时按零参处理。
    """
    try:
        params = inspect.signature(callback).parameters
    except (TypeError, ValueError):
        return False
    for param in params.values():
        if param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
            return True
        if param.kind is param.VAR_POSITIONAL:
            return True
    return False


class LoginRelayService:
    """手机重登中继：单飞会话管理 + 子进程 stdin/stdout 桥。"""

    def __init__(self, *, spawn, now, emit=None, log=None,
                  on_success=None, on_finish=None, classify_captcha=None, manual_after=0):
        self._spawn = spawn          # (args) -> 进程树句柄（stdin/stdout 在 proc 上）
        self._now = now              # 单调秒读数（deadline 用）
        self._emit = emit or (lambda _kind, _payload: None)
        self._log = log or (lambda _msg: None)
        self._on_success = on_success or (lambda: None)
        self._success_takes_origin = _accepts_origin(self._on_success)
        self._on_finish = on_finish or (lambda: None)
        self._classify_captcha = classify_captcha
        self._manual_after = max(0, int(manual_after))
        self._lock = threading.Lock()
        self._staged = None          # {"username","password"}：仅进程内存
        self._flow = None            # 当前在途 flow（dict）
        self._last = None            # 最近一场的公开终态（手机显示收尾结论）
        self._proc = None
        self._stdin = None
        self._reader = None
        self._pump_thread = None
        self._closed = False
        self._threads = []

    # ---------- 本机凭据预备（desktop js_api） ----------
    def prepare(self, username, password) -> dict:
        """暂存账号密码到进程内存；响应只回 ready 布尔，绝不回显内容。"""
        user = str(username or "")
        secret = str(password or "")
        if not user or not secret:
            with self._lock:
                self._staged = None
            return {"ok": False, "ready": False, "error": "needs_local_setup"}
        with self._lock:
            self._staged = {"username": user, "password": secret}
        return {"ok": True, "ready": True}

    def prepared(self) -> bool:
        with self._lock:
            return self._staged is not None

    def clear_staged(self) -> None:
        with self._lock:
            self._staged = None

    # ---------- 会话生命周期 ----------
    def begin(self, *, plan_active: bool = False, terms_ok: bool = True,
              demo: bool = False, worker_command=None,
              origin: str = "phone", manual: bool = False) -> dict:
        """开始一场中继：单飞、条款、计划活跃都在这里拦下。

        origin 记录发起方（phone=手机、auto=无人值守 OCR）：手机入口的
        撤销只清 phone 场，独立 OCR 重登不受手机开关影响。
        """
        with self._lock:
            if self._closed:
                return {"ok": False, "error": "canceled"}
            if demo:
                return {"ok": False, "error": "demo",
                        "text": "演示模式不联网，不会启动重登。"}
            if self._flow is not None:
                return {"ok": False, "error": "busy", "text": "已有一次重登在进行"}
            if not terms_ok:
                return {"ok": False, "error": "terms_required",
                        "text": "请先在电脑上同意使用条款"}
            if plan_active:
                return {"ok": False, "error": "plan_active",
                        "text": "报名计划仍在运行：先停止并等终态，再重登"}
            if self._staged is None:
                return {"ok": False, "error": "needs_local_setup",
                        "text": "请先在电脑上准备账号密码"}
            creds = dict(self._staged)
            if worker_command is None:
                return {"ok": False, "error": "spawn_failed", "text": "缺少 worker 命令"}
            flow_id = secrets.token_hex(8)
            flow = {"flow_id": flow_id, "state": STATE_STARTING, "challenge_id": "",
                    "image": "", "expires_in": None, "deadline": None,
                    "attempts": 0, "max_attempts": 0,
                    "safe_error": "", "tree": None, "success_fired": False,
                    "submit_pending": False,
                    "mode": "manual" if manual or not callable(self._classify_captcha) else "auto",
                    "origin": str(origin or "phone"), "stdin": None,
                    "lines": queue.Queue(), "reader_done": threading.Event()}
            # spawn 前预留；不能持服务锁调用 Api，否则与关闭屏障反向成环。
            self._flow = flow
        args = list(worker_command) + ["--relay"]
        try:
            tree = self._spawn(args)
        except Exception as exc:  # noqa: BLE001 - 只回类型，不回堆栈
            creds.clear()
            self._finish(flow)
            return {"ok": False, "error": "spawn_failed",
                    "text": "重登进程没能启动：%s" % type(exc).__name__}
        proc = getattr(tree, "proc", tree)
        stdin = getattr(proc, "stdin", None)
        if stdin is None:
            creds.clear()
            try:
                tree.terminate()
            except Exception:  # noqa: BLE001
                pass
            self._finish(flow)
            return {"ok": False, "error": "spawn_failed", "text": "重登进程没有输入管道"}
        with self._lock:
            canceled = self._flow is not flow or self._closed
            if not canceled:
                flow.update(tree=tree, stdin=stdin)
                self._proc = tree
                self._stdin = stdin
        if canceled:
            creds.clear()
            tree.terminate()
            self._on_finish()
            return {"ok": False, "error": "canceled"}
        # 首行下发凭据后立刻清掉这份临时副本；预备库保留到关闭/显式清除
        sent = self._send(flow, {"kind": "credentials", "flow_id": flow_id,
                    "username": creds["username"], "password": creds["password"]})
        creds.clear()
        if not sent:
            self.cancel()
            return {"ok": False, "error": "spawn_failed"}
        self._reader = threading.Thread(target=self._read_stdout,
                                        args=(flow, proc), name="relay-out", daemon=True)
        self._pump_thread = threading.Thread(target=self._pump, args=(flow,),
                                             name="relay-pump", daemon=True)
        with self._lock:
            self._threads = [t for t in self._threads if t.is_alive()]
            self._threads.extend((self._reader, self._pump_thread))
            self._reader.start()
            self._pump_thread.start()
        return {"ok": True, "flow_id": flow_id}

    def submit(self, flow_id, challenge_id, code) -> dict:
        with self._lock:
            flow = self._flow
            stdin = self._stdin
        if flow is None:
            return {"ok": False, "error": "no_flow", "text": "当前没有进行中的重登"}
        if str(flow_id or "") != str(flow.get("flow_id") or ""):
            return {"ok": False, "error": "stale_flow", "text": "这次重登已经结束"}
        if stdin is None:
            return {"ok": False, "error": "no_flow", "text": "重登进程已结束"}
        status = self._send_submit(flow, {"kind": "submit", "flow_id": flow.get("flow_id"),
                    "challenge_id": str(challenge_id or ""),
                    "code": str(code or "")})
        if status == "duplicate":
            return {"ok": False, "error": "duplicate_submit", "text": "验证码正在提交，请等待结果"}
        return {"ok": status == "sent"}

    def cancel(self, origin=None) -> dict:
        """取消在途 relay。origin 给定时只动该来源的场。

        手机停止/手机撤销传 origin="phone"：独立 OCR 重登（auto）不受手机
        开关牵连；关闭收尾不带 origin，任何场都收。
        """
        with self._lock:
            flow = self._flow
            if (flow is not None and origin is not None
                    and str(flow.get("origin") or "phone") != str(origin)):
                return {"ok": True, "skipped": "foreign_origin"}
            tree = self._proc
            self._flow = None
            self._proc = None
            self._stdin = None
            if flow is not None:
                flow["state"] = STATE_CANCELED
                flow["reader_done"].set()
                self._last = public_state(flow, self._now())
        if tree is not None:
            try:
                tree.terminate()
            except Exception:  # noqa: BLE001
                pass
        if flow is not None:
            self._on_finish()
        return {"ok": True}

    def shutdown(self) -> None:
        """关闭工具时收口：取消中继并清除预备凭据。"""
        with self._lock:
            self._closed = True
        self.cancel()
        self.clear_staged()
        for thread in list(self._threads):
            if thread is not threading.current_thread():
                thread.join(timeout=1.0)

    def state(self) -> dict:
        with self._lock:
            flow = self._flow
            if flow is not None:
                return public_state(flow, self._now())
            if self._last is None:
                return public_state(None)
            # 上一场的结论留档是给手机看收尾信息的，但它不是「这一场」：
            # live 一律置 False，手机端据此不再把历史成功播成本次结果。
            last = dict(self._last)
            last["live"] = False
            return last

    def observe_line(self, line: str) -> None:
        """_pump 识别 [login] 结构行后转交这里；无在途 flow 时静默丢弃。"""
        with self._lock:
            flow = self._flow
        if flow is not None:
            self._handle_line(flow, str(line or ""))

    # ---------- 内部：stdout 读取与结构行分发 ----------
    def _send(self, flow, payload: dict) -> bool:
        line = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            if self._flow is not flow or flow.get("stdin") is None:
                return False
            try:
                flow["stdin"].write(line + "\n")
                flow["stdin"].flush()
                return True
            except Exception:  # noqa: BLE001 - 管道断了由收口逻辑处理
                return False

    def _send_submit(self, flow, payload: dict, *, automatic=False) -> str:
        """串行化验证码提交，避免同一张图在父进程并发写入多次。"""
        with self._lock:
            if self._flow is not flow or flow.get("stdin") is None:
                return "stale"
            if str(payload.get("challenge_id") or "") != str(flow.get("challenge_id") or ""):
                return "stale"
            if automatic and flow.get("mode") != "auto":
                return "stale"
            if not automatic and flow.get("mode") == "auto":
                return "auto"
            if flow.get("submit_pending"):
                return "duplicate"
            flow["submit_pending"] = True
            try:
                flow["stdin"].write(json.dumps(payload, ensure_ascii=False) + "\n")
                flow["stdin"].flush()
                if not automatic:
                    flow["origin"] = "phone"
                return "sent"
            except Exception:  # noqa: BLE001 - 管道断了由收口逻辑处理
                flow["submit_pending"] = False
                return "failed"

    def _read_stdout(self, flow, proc) -> None:
        try:
            for line in proc.stdout or []:
                flow["lines"].put(line.rstrip("\r\n"))
        finally:
            flow["reader_done"].set()

    def _pump(self, flow) -> None:
        """逐行取 [login] 结构行更新 flow；结束时收口，不回调 HTTP 客户端。"""
        while True:
            try:
                line = flow["lines"].get(timeout=0.2)
            except queue.Empty:
                if flow["reader_done"].is_set():
                    break
                continue
            if not line:
                continue
            self._handle_line(flow, line)
        self._finish(flow)

    def _handle_line(self, flow, line: str) -> None:
        prefix = "[login] "
        if not line.startswith(prefix):
            return
        try:
            data = json.loads(line[len(prefix):])
        except ValueError:
            return
        if not isinstance(data, dict):
            return
        if str(data.get("flow_id") or "") != str(flow.get("flow_id") or ""):
            return                      # 旧 flow 的行不得改写当前会话
        kind = str(data.get("kind") or "")
        success = False
        with self._lock:
            if self._flow is not flow or flow["state"] in (
                    STATE_SUCCESS, STATE_FAILED, STATE_CANCELED):
                return
            try:
                if kind == "challenge":
                    challenge_id = str(data.get("challenge_id") or "")
                    if challenge_id and challenge_id == str(flow.get("challenge_id") or ""):
                        # 同一 challenge 的事件更新（重复投递）：不清空输入状态、
                        # 不清空已输入状态，只非破坏性同步计数，也不补发事件
                        # ——新事件会被手机当成新验证码，清掉正在输入的码。
                        flow["attempts"] = max(int(flow.get("attempts") or 0),
                                               max(0, int(data.get("attempts") or 0)))
                        flow["max_attempts"] = 0
                        return
                    flow["submit_pending"] = False
                    flow["state"] = STATE_WAITING_CODE
                    flow["challenge_id"] = challenge_id
                    image = str(data.get("image") or "")
                    flow["image"] = image if image.startswith("data:image/png;base64,") else ""
                    flow["expires_in"] = None
                    flow["deadline"] = None
                    flow["attempts"] = max(0, int(data.get("attempts") or 0))
                    if self._manual_after and flow["attempts"] >= self._manual_after:
                        flow["mode"] = "manual"
                    flow["max_attempts"] = 0
                elif kind == "rejected":
                    flow["submit_pending"] = False
                    flow["attempts"] = max(0, int(data.get("attempts") or 0))
                    flow["safe_error"] = _safe(data.get("reason"))
                elif kind == "verifying":
                    flow["state"] = STATE_VERIFYING
                elif kind == "success":
                    # worker 若自己声明了完成方（它跑过 OCR），以它为准；
                    # 没声明就沿用开局时的来源
                    declared = str(data.get("origin") or "")
                    if declared in ("auto", "phone"):
                        flow["origin"] = declared
                    flow["state"] = STATE_SUCCESS
                    flow["safe_error"] = ""
                    success = not flow.get("success_fired")
                    flow["success_fired"] = True
                elif kind in ("failed", "canceled"):
                    flow["state"] = STATE_FAILED if kind == "failed" else STATE_CANCELED
                    flow["safe_error"] = _safe(data.get("error"))
            except (TypeError, ValueError, OverflowError):
                return
            snapshot = public_state(flow, self._now())
        if (kind == "challenge" and snapshot.get("mode") == "auto"
                and callable(self._classify_captcha) and snapshot["image"]):
            try:
                code = str(self._classify_captcha(snapshot["image"]) or "")
            except Exception:
                code = ""
            if not _VALID_CODE_RE.fullmatch(code):
                with self._lock:
                    if self._flow is flow and flow.get("challenge_id") == snapshot["challenge_id"]:
                        flow["mode"] = "manual"
                        snapshot = public_state(flow, self._now())
            if _VALID_CODE_RE.fullmatch(code) and self._send_submit(flow, {
                    "kind": "submit", "flow_id": snapshot["flow_id"],
                    "challenge_id": snapshot["challenge_id"], "code": code}, automatic=True) == "sent":
                with self._lock:
                    if self._flow is flow:
                        flow["state"] = STATE_VERIFYING
                        snapshot = public_state(flow, self._now())
        if success:
            self._notify_success(flow)
        self._emit("phone_relogin", snapshot)

    def _notify_success(self, flow) -> None:
        """成功回调只触发一次，并带上「这一场是谁完成的」。

        auto=无人值守（ddddocr 或上次留下的码），phone=手机人工输入。
        回调签名可能是零参（旧调用方），也可能是收一个来源标签：两种都支持，
        绝不因为签名差异把「登录真的成功了」这件事丢掉。
        """
        raw = str((flow or {}).get("origin") or "phone")
        origin = "auto_ocr" if raw == "auto" else "phone_manual"
        try:
            if self._success_takes_origin:
                self._on_success(origin)
            else:
                self._on_success()
        except TypeError:
            # 兜底：签名判断猜错时也别把「登录成功」这个事实丢掉
            try:
                self._on_success()
            except Exception:
                pass
        except Exception:
            pass

    def _finish(self, flow) -> None:
        with self._lock:
            if self._flow is not flow:
                return
        if flow.get("state") in (STATE_STARTING, STATE_WAITING_CODE,
                                 STATE_VERIFYING):
            flow["state"] = STATE_FAILED
            flow["safe_error"] = flow.get("safe_error") or "eof"
        tree = flow.get("tree")
        if tree is not None:
            try:
                tree.terminate()
            except Exception:  # noqa: BLE001
                pass
        snapshot = public_state(flow, self._now())
        with self._lock:
            if self._flow is not flow:
                return
            self._flow = None
            self._proc = None
            self._stdin = None
            self._last = snapshot
        self._emit("phone_relogin", snapshot)
        try:
            self._on_finish()
        except Exception:  # noqa: BLE001
            pass


def _safe(value) -> str:
    text = str(value or "")
    return text if text in _SAFE_ERRORS else "internal"
