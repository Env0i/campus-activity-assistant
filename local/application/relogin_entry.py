# -*- coding: utf-8 -*-
"""重新登录入口：桌面与手机共用的那道门，以及自动重登的发起与收尾。

状态不复制一份：协调对象（关闭屏障、单 worker、计划任务登记）仍归
`Coordinator`，只读；中继来源标签、待保存副本、密码被拒标记、发起时刻本来
就在 `LoginRecovery` 上，经构造注入的对象读写；只有「这一次 login_wait 放行」
是本服务自己的状态。

判断先落到 `domain.login_rules` 的纯函数（不读墙钟、不拿锁、参数全显式），
这里只做端口调用。锁的用法与搬家前一致：凡是在 Api 锁里做的判断仍在同一把
协调锁里做，持锁期间不调别的服务，事件发布与中继调用一律在锁外。

@author Author
"""
from __future__ import annotations

import time

from domain import login_rules


class ReloginEntry:
    """重登入口与自动重登门的编排；副作用全部经 ports 注入。"""

    def __init__(self, *, coordination, lock, login_recovery, credential_lock, ports):
        self._coord = coordination
        self._lock = lock
        self._login = login_recovery
        self._credential_lock = credential_lock
        self._ports = ports
        # 报名进程发来 login_wait（决策 015）：只放行一次计划运行中的自动登录
        self.login_wait_pending = False

    # ---------- 能力判据：电脑能不能自己把登录补回来 ----------
    def _silent_relogin_ready(self) -> tuple[bool, str]:
        """只看「能力」：条款、识别、可用账号、密码没被拒过；瞬时忙碌由资格判定另判。"""
        if self._ports["demo"]():
            return False, "demo"
        try:
            if self._ports["terms_gate"]() is not None:
                return False, "terms"
            if not (self._ports["has_credentials"]() or self._once_credentials_staged()):
                return False, "no_credentials"
            if not self._ports["ocr_ready"](self._ports["load_prefs"]()):
                return False, "ocr_missing"
            if self._auto_relogin_paused():
                return False, "paused"
        except Exception:  # noqa: BLE001 - 判据读不到就按「不能」处理，界面照旧提醒
            return False, "unknown"
        return True, ""

    def _silent_relogin_state(self) -> tuple[bool, str]:
        """check 载荷里的静默恢复态；结论部分在 domain.login_rules。"""
        ready, reason = self._silent_relogin_ready()
        try:
            relay = self._ports["relay"]().state() or {}
        except Exception:  # noqa: BLE001 - 中继读不到按「没有在跑」处理
            relay = {}
        try:
            failures = int(self._ports["monitor"]().snapshot().get("failures") or 0)
        except Exception:  # noqa: BLE001 - 调度器读不到按「没失败过」处理
            failures = 0
        return login_rules.silent_relogin_state(
            ready=ready, ready_reason=reason, relay=relay, auto_failures=failures)

    def _auto_relogin_eligible(self) -> bool:
        """这一拍能不能自动登录：先看忙碌位与进程，再看能力判据。"""
        with self._lock:
            blocked = login_rules.auto_relogin_blocked(
                closing=self._coord.closing,
                advanced_busy=self._coord.advanced_busy,
                checking=self._coord.checking,
                listing=self._coord.listing,
                cancelling=self._coord.cancelling,
                login_wait_pending=self.login_wait_pending,
                proc_running=bool(self._coord.proc and self._coord.proc.poll() is None),
                plan_procs_running=any(
                    proc.poll() is None for proc in self._coord.plan_procs.values()))
        if blocked:
            return False
        return self._silent_relogin_ready()[0]

    def _once_credentials_staged(self) -> bool:
        """这次运行内存里有没有「只用这一次」（手输、没保存）的账号密码。

        只认手输来源：中继暂存区也可能放着「手机重登用保存账号预备」的副本。
        """
        with self._lock:
            typed = self._login.relay_creds_source == "typed"
        return typed and self._ports["relay"]().has_staged()

    def _auto_relogin_paused(self) -> bool:
        """自动登录该不该暂停到用户更新密码。

        保存的密码被拒过（落盘标记）照旧暂停；没有保存的账号时，只用这一次的那份
        被拒过（内存标记）也暂停。有保存的账号时以保存的为准。
        """
        if self._ports["credentials_bad"]():
            return True
        with self._lock:
            rejected = self._login.once_creds_rejected
        return rejected and not self._ports["has_credentials"]()

    def _request_auto_relogin(self) -> None:
        """报名进程发来 login_wait：放行这一次计划运行中的自动登录，并让调度立即动手。"""
        with self._lock:
            self.login_wait_pending = True
        self._ports["monitor"]().request_recover()

    def _relogin_wait_s(self) -> float:
        """worker 确认登录失效后能等多久：电脑能自己登录（有账号密码、识别已装）才等。"""
        return self._ports["wait_s"]() if self._silent_relogin_ready()[0] else 0.0

    def _relogin_ocr_ready(self) -> bool:
        """电脑这边有没有「自己认验证码」的能力。"""
        return bool(self._ports["ocr_ready"](self._ports["load_prefs"]()))

    def _manual_relogin_wanted(self, relay=None) -> bool:
        """验证码该不该交给手机上的人来打；判据在 domain.login_rules。"""
        if not self._relogin_ocr_ready():
            return True
        relay = self._ports["relay"]().state() if relay is None else relay
        failures = int(self._ports["monitor"]().snapshot().get("failures") or 0)
        return login_rules.manual_relogin_wanted(
            ocr_ready=True, relay=relay, auto_failures=failures,
            manual_after=self._ports["manual_after"]())

    def _phone_relay_view(self) -> dict:
        """手机 /api/state 里的重登投影。

        机器还在认的时候图和挑战号都不下发（手机看不到就不会抢同一张图）；
        mode/retrying/retry_in 让手机显示「重试中」而不是当成已经结束。
        """
        relay = dict(self._ports["relay"]().state())
        auto = self._ports["monitor"]().snapshot()
        manual = self._manual_relogin_wanted(relay)
        state = str(relay.get("state") or "")
        retrying = bool(auto.get("inflight")) or state in ("starting", "verifying")
        if not manual:
            relay["image"] = ""
            relay["challenge_id"] = ""
        relay["mode"] = "manual" if manual else "auto"
        relay["retrying"] = retrying
        relay["retry_in"] = max(0, int(auto.get("retry_in") or 0))
        relay["auto_failures"] = max(0, int(auto.get("failures") or 0))
        # live 原样透传：手机端只有在本场真的还在跑时才播报「重登成功」
        relay["live"] = bool(relay.get("live"))
        return relay

    # ---------- 自动重登的发起 ----------
    def _begin_auto_relogin(self) -> dict:
        """发起一轮自动登录，结果写进运行记录（带耗时与失败分类，不带账号）；busy 不落盘。"""
        began = time.monotonic()
        result = self._begin_auto_relogin_once()
        if result.get("ok"):
            self._login.auto_relogin_started_at = began
            self._ports["log_event"]("auto_relogin_started",
                                     elapsed_s=time.monotonic() - began)
        elif result.get("error") != "busy":
            self._ports["log_event"]("auto_relogin_start_failed", level="WARN",
                                     reason=str(result.get("error") or "unknown"),
                                     elapsed_s=time.monotonic() - began)
            # 发起失败界面收不到中继事件，会一直显示「自动登录中」；推一次当前状态让顶栏收起。
            # 推送失败不影响发起结果，所以吞掉异常。
            try:
                self._ports["emit"]("phone_relogin", self._ports["relay"]().state())
            except Exception:  # noqa: BLE001 - 推送失败不影响发起结果
                pass
        return result

    def _begin_auto_relogin_once(self) -> dict:
        with self._credential_lock:
            if self._auto_relogin_paused():
                return {"ok": False, "error": "bad_password"}
            if not self._auto_relogin_eligible():
                return {"ok": False, "error": "busy"}
            stored = {}
            try:
                if self._ports["has_credentials"]():
                    # 有保存的用保存的（两者都有时以保存的为准）
                    stored = self._ports["load_credentials"]()
                    result = self._ports["relay"]().prepare(stored["username"],
                                                           stored["password"])
                    if not result.get("ok"):
                        return result
                    source = "saved"
                elif self._once_credentials_staged():
                    # 没保存、只有这次的：直接用中继内存里那份，不取出、不复制、不落盘
                    source = "typed"
                else:
                    return {"ok": False, "error": "needs_local_setup"}
                with self._lock:
                    self._login.relay_creds_source = source
                    self._login.pending_save = None
                manual = int(self._ports["monitor"]().snapshot().get("failures") or 0) \
                    >= self._ports["manual_after"]()
                return self._ports["relay"]().begin(
                    origin="auto", worker_command=self._ports["worker_command"]("login"),
                    manual=manual)
            except Exception:  # noqa: BLE001 - 凭据读不出来按「没准备好」处理
                return {"ok": False, "error": "needs_local_setup"}
            finally:
                stored.clear()
                # 一次 login_wait 只放行一轮自动登录：发起过就收回（成败都一样）
                with self._lock:
                    self.login_wait_pending = False

    # ---------- 凭据：保存、清除、只在本机 --------------------------
    def prepare_phone_relogin(self, username: str = "", password: str = "",
                              save: bool = False) -> dict:
        """桌面「准备手机重登」：账号密码只进内存，响应只回 ready 布尔。

        绝不写偏好、文件、命令行、环境或日志；save=True 时等登录成功后才写进电脑。
        """
        user = str(username or "").strip()
        secret = str(password or "")
        typed = bool(user and secret)
        if not typed:
            if self._ports["store_available"]():
                try:
                    stored = self._ports["load_credentials"]()
                    user, secret = stored["username"], stored["password"]
                except Exception:  # noqa: BLE001 - 读不到就当没填
                    user, secret = "", ""
        result = self._ports["relay"]().prepare(user, secret)
        if result.get("ok"):
            with self._lock:
                self._login.relay_creds_source = "typed" if typed else "saved"
                if typed:
                    # 用户输了新的账号密码：解除只用这一次那份被拒后的暂停
                    self._login.once_creds_rejected = False
                self._login.pending_save = ({"username": user, "password": secret}
                                            if typed and save else None)
        user = ""
        secret = ""
        if result.get("ok"):
            self._ports["emit"]("log", "已为手机重新登录准备好账号（只在本工具内存里）")
        return result

    def _commit_pending_save(self) -> None:
        """登录成功后才落盘这次手输、又勾了保存的账号密码；没有就什么都不做。"""
        with self._lock:
            pending = self._login.pending_save
            self._login.pending_save = None
        if not pending:
            return
        try:
            with self._credential_lock:
                self._ports["save_credentials"](pending["username"], pending["password"])
                self._ports["monitor"]().reset()
            self._ports["emit"]("log", "账号密码已保存到这台电脑（加密存储）")
        except Exception as exc:  # noqa: BLE001 - 保存失败不影响「已经登录成功」
            self._ports["emit"]("log", "账号密码没有保存成功：%s" % type(exc).__name__)
        finally:
            pending.clear()

    def save_relogin_credentials(self, username: str = "", password: str = "") -> dict:
        """保存续登录用的账号密码（本机加密存储落盘）。

        只依赖本机加密存储：识别组件只决定能不能自动认，手机人工输码同样要用这份账号。
        """
        user = str(username or "").strip()
        secret = str(password or "")
        if not user or not secret:
            return {"ok": False, "error": "needs_local_setup",
                    "text": "请输入账号和密码。"}
        if not self._ports["store_available"]():
            return {"ok": False, "error": "store_unavailable",
                    "text": "本机加密存储不可用，暂时无法保存账号密码。"}
        try:
            with self._credential_lock:
                self._ports["save_credentials"](user, secret)
                with self._lock:
                    self._login.once_creds_rejected = False
                self._ports["monitor"]().reset()
        except Exception as exc:  # noqa: BLE001 - 只回类型名，不带内容
            return {"ok": False, "error": "credential_save_failed",
                    "text": "账号密码暂时没有保存：%s" % type(exc).__name__}
        return {"ok": True, "saved": True, "username": user}

    def clear_relogin_credentials(self) -> dict:
        with self._credential_lock:
            self._ports["clear_credentials"]()
            self._ports["relay"]().clear_staged()
            with self._lock:
                self._login.once_creds_rejected = False
            self._ports["relay"]().cancel(origin="auto")
            self._ports["monitor"]().reset()
        return {"ok": True, "saved": False}

    # ---------- 登录成功之后 ----------
    def _anchor_login_success(self, origin: str = "") -> None:
        """新登录真实成功后建立 v2 锚点；没有可信时钟就不写（不拿系统时间冒充）。

        只走 login worker 成功路径：check/refresh/bootstrap 都不续期。origin 由中继
        给出，只用于「上一次是怎么完成的」这一行说明，不参与任何判断。
        """
        self._commit_pending_save()
        if origin in ("auto_ocr", "phone_manual"):
            with self._lock:
                self._ports["note_origin"](origin)
                began = self._login.auto_relogin_started_at
            if origin == "auto_ocr":
                self._ports["log_event"](
                    "auto_relogin_ok",
                    **({"elapsed_s": time.monotonic() - began} if began is not None else {}))
            # 重登成功时桌面还停在「登录已过期」：补一次正常的登录检查，
            # 让顶栏状态、活动列表和时间锚点跟着刷新。check 自带忙碌去重，
            # 手动重登、自动重登走的是同一条路。
            self._ports["refresh_check"]()
        try:
            lower, upper = self._ports["clock_bounds"]()
            token = self._ports["session_token"]()
        except Exception:  # noqa: BLE001 - 时钟或会话读不出来就不建锚点
            return
        if not token or not (upper >= lower):
            return
        self._ports["save_anchor"](token, (lower + upper) / 2.0, (upper - lower) / 2.0)

    # ---------- 入口门：演示、条款、关闭、来不及 ----------
    def _relogin_late_answer(self) -> "dict | None":
        """计划运行中还来不来得及重新登录（架构方案 4.3）；来得及返回 None。"""
        with self._lock:
            plan = self._ports["plan"]()
        if plan is None:
            return login_rules.late_relogin_answer(
                has_plan=False, tasks=[], now=0.0, open_epoch=None)
        try:
            tasks = (plan.snapshot() or {}).get("tasks") or []
            now = self._ports["clock_now"]()
        except Exception:  # noqa: BLE001 - 时钟读不出来按来不及处理
            return login_rules.late_relogin_answer(
                has_plan=True, tasks=[], now=0.0, open_epoch=None, clock_unavailable=True)
        return login_rules.late_relogin_answer(
            has_plan=True, tasks=tasks, now=now, open_epoch=self._ports["epoch_of"])

    def _relogin_entry_gate(self) -> "dict | None":
        """电脑和手机重新登录共同的前置门：演示、条款、关闭、来不及。"""
        if self._ports["demo"]():
            return {"ok": False, "error": "demo", "text": "演示模式不联网，不会启动重新登录。"}
        gate = self._ports["terms_gate"]()
        if gate is not None:
            return {"ok": False, "error": "terms_required", "text": "请先在电脑上同意使用条款"}
        with self._lock:
            if self._coord.closing:
                return {"ok": False, "text": "程序正在关闭，已取消本次重新登录"}
        return self._relogin_late_answer()

    def _relogin_manual_case(self) -> str:
        """用户是从哪一步开始重新登录的，只用于日志与文案，不参与判断。"""
        has, bad = False, False
        try:
            has = bool(self._ports["has_credentials"]())
            if has:
                bad = bool(self._ports["credentials_bad"]())
        except Exception:  # noqa: BLE001 - 任一处读不出来都回到「从登录开始」
            has = bad = False
        return login_rules.relogin_manual_case(has_credentials=has, credentials_bad=bad)

    def _begin_typed_relogin(self, username: str, password: str, save: bool,
                             origin: str) -> dict:
        """用这次手输的账号密码登录：只进内存，save=True 才在成功后写进电脑。"""
        prepared = self.prepare_phone_relogin(username, password, save=save)
        if not prepared.get("ok"):
            return dict(prepared, text="请输入账号和密码。")
        manual = not self._relogin_ocr_ready()
        extra = {} if origin == "phone" else {"origin": origin}
        result = self._ports["relay"]().begin(
            plan_active=False, worker_command=self._ports["worker_command"]("login"),
            manual=manual, **extra)
        if result.get("ok"):
            self._ports["log_event"]("relogin_manual_started", case="login", origin=origin)
        else:
            with self._lock:
                self._login.pending_save = None
        return dict(result, mode="manual" if manual else "auto")

    # ---------- 电脑上的重新登录 ----------
    def relogin_begin(self, username: str = "", password: str = "", save: bool = False) -> dict:
        """电脑上点「重新登录」：填了就用这次的（save=True 成功后才存），没填用保存的；
        保存的密码被拒过就停下让用户换密码；装了识别电脑自己认，认出上限转人工。
        和手机共用同一场流程，同一时间只有一场；计划来不及时返回 plan_late。
        """
        gate = self._relogin_entry_gate()
        if gate is not None:
            return gate
        if str(username or "").strip() and str(password or ""):
            return self._begin_typed_relogin(username, password, bool(save), origin="desktop")
        if not self._ports["has_credentials"]():
            return {"ok": False, "error": "needs_local_setup", "text": "请输入账号和密码。"}
        if self._ports["credentials_bad"]():
            return {"ok": False, "error": "bad_password",
                    "text": "保存的密码学校不认，自动登录已暂停。请输入新的账号密码。"}
        prepared = self.prepare_phone_relogin()
        if not prepared.get("ok"):
            return {"ok": False, "error": "needs_local_setup", "text": "请输入账号和密码。"}
        manual = not self._relogin_ocr_ready()
        result = self._ports["relay"]().begin(
            plan_active=False, worker_command=self._ports["worker_command"]("login"),
            manual=manual, origin="desktop")
        if result.get("ok"):
            self._ports["log_event"]("relogin_manual_started",
                                     case=self._relogin_manual_case(), origin="desktop")
        return dict(result, mode="manual" if manual else "auto")

    def relogin_cancel(self, flow_id: str = "") -> dict:
        """取消电脑上发起或接手的这一场登录；旧场的 flow_id 不取消新场。"""
        state = self._ports["relay"]().state()
        if (flow_id and state.get("live") and state.get("flow_id")
                and flow_id != state.get("flow_id")):
            return {"ok": False, "error": "stale_flow", "text": "这次重新登录已经结束"}
        return self._ports["relay"]().cancel()

    def relogin_auto_once(self) -> dict:
        """有保存的账号又装了验证码识别：用户确认后让电脑自动登录一次。"""
        gate = self._relogin_entry_gate()
        if gate is not None:
            return gate
        if self._ports["credentials_bad"]():
            return {"ok": False, "error": "bad_password",
                    "text": "保存的密码学校不认，自动登录已暂停。请输入新的账号密码。"}
        current = self._ports["relay"]().state()
        if current.get("live"):
            return {"ok": True, "mode": "auto", "flow_id": str(current.get("flow_id") or ""),
                    "text": "已经在登录了，等它结束。"}
        result = self._begin_auto_relogin()
        if not result.get("ok") and result.get("error") == "busy":
            return dict(result, text="电脑正在检查登录或加载活动，稍后再试。")
        return dict(result, mode="auto")

    # ---------- 手机上的重新登录 ----------
    def phone_relogin_begin(self, username: str = "", password: str = "",
                            save: bool = False) -> dict:
        if not self._ports["demo"]() and self._ports["terms_gate"]() is not None:
            return {"ok": False, "error": "terms_required",
                    "text": "请先在电脑上同意使用条款"}
        # 演示、关闭中、计划来不及（有场次在提交或离开放不到 100 秒）都在这一道门里
        gate = self._relogin_entry_gate()
        if gate is not None:
            return gate
        if str(username or "").strip() and str(password or ""):
            # 手机上输的账号密码：默认只在电脑内存里，勾了「保存到这台电脑」才在成功后写盘
            return self._begin_typed_relogin(username, password, bool(save), origin="phone")
        if not self._manual_relogin_wanted():
            # 电脑自己会认图：手机别另开一场人工重登，只回报进度。
            # 已经有一场在跑就什么都不做——重复点按钮不该变成第二个 worker。
            current = self._ports["relay"]().state()
            state = str(current.get("state") or "")
            # 只有真的还在跑的流程才算忙：历史快照里剩下的 waiting_code/verifying
            # 不代表「现在别再开一场」，否则一次残留会让手机永远点不动
            busy = bool(current.get("live")) and state not in (
                "idle", "success", "failed", "canceled")
            if not busy:
                started = self._begin_auto_relogin()
                if not started.get("ok") and started.get("error") != "busy":
                    return started
            return {"ok": True, "mode": "auto",
                    "text": "电脑正在自动登录，手机上不用再操作"}
        if not self._ports["relay"]().prepared():
            self.prepare_phone_relogin()
        # 能走到这里说明计划来得及（_relogin_entry_gate 已判过 100 秒窗口）
        return self._ports["relay"]().begin(
            plan_active=False, worker_command=self._ports["worker_command"]("login"),
            manual=True)

    def phone_relogin_cancel(self, flow_id: str = "") -> dict:
        state = self._ports["relay"]().state()
        # 历史快照的 flow_id 不属于现在这一场：拿它挡取消只会让用户点了没反应
        if (flow_id and state.get("live") and state.get("flow_id")
                and flow_id != state.get("flow_id")):
            return {"ok": False, "error": "stale_flow",
                    "text": "这次重新登录已经结束"}
        return self._ports["relay"]().cancel(
            origin=None if state.get("mode") == "manual" else "phone")


class ReloginEntryFields:
    """「这一次 login_wait 放行」的旧字段名代理（Api 继承，动作代码一行不改）。"""

    @property
    def _login_wait_pending(self) -> bool: return self._relogin_entry.login_wait_pending

    @_login_wait_pending.setter
    def _login_wait_pending(self, value: bool) -> None:
        self._relogin_entry.login_wait_pending = value
